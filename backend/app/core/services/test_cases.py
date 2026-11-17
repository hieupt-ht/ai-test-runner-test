"""Nghiệp vụ test case: quyền theo từng case, chuyển trạng thái, AuditLog.

Sau mỗi lần ghi, service ghi AuditLog rồi tính lại trạng thái việc của màn hình.
Việc tính lại lấy khoá `assignments`, nên luôn chạy SAU KHI đã nhả khoá `test-cases`
(thứ tự khoá: assignments trước, test-cases sau, không bao giờ ngược lại).
"""

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.core.assignment_status import AssignmentStatusUpdater
from app.core.locks.redis_lock import LockTimeout
from app.core.models.project import Project
from app.core.models.test_case import TestCase, TestCaseContent, TestCaseStatus
from app.core.models.user import Role, User, normalize_email
from app.core.permissions import Action, can
from app.core.repositories.assignments import AssignmentRepository
from app.core.repositories.audit_log import AuditEntry, AuditLogRepository
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.screens import ScreenRepository
from app.core.repositories.test_cases import (
    TestCaseNotFoundError,
    TestCaseRepository,
    VersionConflictError,
)
from app.core.repositories.users import UserRepository
from app.core.services.issue_sync import IssueSink, IssueSyncer
from app.core.services.notify import Notifier
from app.core.sheets.gateway import SheetAccessDeniedError
from app.core.sheets.table import MissingColumnsError

logger = logging.getLogger(__name__)

AUDIT_ENTITY = "test_case"
MAX_COMMENT_LENGTH = 1000
MAX_SYNC_BATCH_SIZE = 200
REVIEW_OFF = "Dự án đang tắt bước duyệt"


class CaseAction(StrEnum):
    SUBMIT = "SUBMIT"
    APPROVE = "APPROVE"
    RETURN = "RETURN"
    DEPRECATE = "DEPRECATE"
    RESTORE = "RESTORE"
    ARCHIVE = "ARCHIVE"
    UNARCHIVE = "UNARCHIVE"


class InvalidTestCaseError(Exception):
    """Dữ liệu không hợp lệ (trả 422). `str(error)` là câu báo tiếng Việt."""


class TestCasePermissionError(Exception):
    """Không đủ quyền với case này (trả 403)."""

    __test__ = False  # pytest đừng tưởng đây là lớp test


class InvalidTransitionError(Exception):
    """Thao tác không hợp lệ ở trạng thái hiện tại (trả 409). `str(error)` là câu tiếng Việt."""


# Thao tác -> (trạng thái được phép đi từ đó, trạng thái đích). DEPRECATE xử lý riêng.
_TRANSITIONS: dict[CaseAction, tuple[set[TestCaseStatus], TestCaseStatus]] = {
    CaseAction.SUBMIT: ({TestCaseStatus.DRAFT}, TestCaseStatus.IN_REVIEW),
    CaseAction.APPROVE: ({TestCaseStatus.IN_REVIEW}, TestCaseStatus.APPROVED),
    CaseAction.RETURN: ({TestCaseStatus.IN_REVIEW}, TestCaseStatus.DRAFT),
    CaseAction.DEPRECATE: (
        {TestCaseStatus.DRAFT, TestCaseStatus.IN_REVIEW, TestCaseStatus.APPROVED},
        TestCaseStatus.DEPRECATED,
    ),
    CaseAction.RESTORE: ({TestCaseStatus.DEPRECATED}, TestCaseStatus.DRAFT),
    CaseAction.ARCHIVE: (
        {TestCaseStatus.APPROVED, TestCaseStatus.TESTED},
        TestCaseStatus.ARCHIVED,
    ),
    CaseAction.UNARCHIVE: ({TestCaseStatus.ARCHIVED}, TestCaseStatus.TESTED),
}
# Người duyệt (QA Lead/Admin) mới được làm; còn lại cần quyền sửa case.
_REVIEW_ACTIONS = {CaseAction.APPROVE, CaseAction.RETURN, CaseAction.RESTORE}

_CONTENT_FIELDS = list(TestCaseContent.model_fields)


def _content_of(case: TestCase) -> dict[str, Any]:
    """Phần nội dung của case, dạng dict thuần JSON để so sánh và ghi diff."""
    return case.model_dump(mode="json", include=set(_CONTENT_FIELDS))


@dataclass(frozen=True)
class SkippedCase:
    """Một case bị bỏ qua khi duyệt hàng loạt, kèm lý do để hiện cho người duyệt."""

    case_id: str
    reason: str


@dataclass
class BatchApproveResult:
    approved: list[TestCase] = field(default_factory=list)
    skipped: list[SkippedCase] = field(default_factory=list)


class SyncIssuesResult(BaseModel):
    created: int = 0
    updated: int = 0
    closed: int = 0
    reopened: int = 0
    skipped: int = 0
    failed: list[SkippedCase] = Field(default_factory=list)


class TestCaseService:
    __test__ = False  # pytest đừng tưởng đây là lớp test

    def __init__(
        self,
        *,
        project_id: str,
        test_cases: TestCaseRepository,
        screens: ScreenRepository,
        assignments: AssignmentRepository,
        members: ProjectMemberRepository,
        status_updater: AssignmentStatusUpdater,
        audit_log: AuditLogRepository,
        issue_sync: IssueSink | None = None,
        project: Project | None = None,
        issue_syncer: IssueSyncer | None = None,
        notifier: Notifier | None = None,
        users: UserRepository | None = None,
    ) -> None:
        self._project_id = project_id
        self._test_cases = test_cases
        self._screens = screens
        self._assignments = assignments
        self._members = members
        self._status_updater = status_updater
        self._audit_log = audit_log
        self._issue_sync = issue_sync
        self._project = project
        self._issue_syncer = issue_syncer
        self._notifier = notifier
        self._users = users
        self._screen_names: dict[str, str] | None = None

    @property
    def review_enabled(self) -> bool:
        """Dự án có bắt buộc QA duyệt không. Không biết dự án thì giữ hành vi cũ (có duyệt)."""
        return self._project is None or self._project.require_review

    # --- Đọc ---

    def list_cases(self) -> list[TestCase]:
        return self._test_cases.list_all()

    def get_case(self, case_id: str) -> TestCase:
        case = self._test_cases.get(case_id)
        if case is None:
            raise TestCaseNotFoundError(case_id)
        return case

    def history(self, case_id: str) -> list[AuditEntry]:
        return self._audit_log.list_for(AUDIT_ENTITY, case_id)

    # --- Quyền ---

    def _is_member(self, user: User) -> bool:
        return self._members.is_member(self._project_id, user.email)

    def _is_assigned(self, user: User, screen_id: str) -> bool:
        email = normalize_email(user.email)
        return any(
            a.screen_id == screen_id and a.assignee_email == email
            for a in self._assignments.list_all()
        )

    def can_edit(self, user: User, case: TestCase) -> bool:
        owns_or_assigned = case.created_by == normalize_email(user.email) or self._is_assigned(
            user, case.screen_id
        )
        return can(
            user,
            Action.EDIT_TEST_CASE,
            is_member=self._is_member(user),
            owns_or_assigned=owns_or_assigned,
        )

    def can_review(self, user: User) -> bool:
        return can(user, Action.REVIEW_TEST_CASE, is_member=self._is_member(user))

    def can_archive(self, user: User, case: TestCase) -> bool:
        return self.can_review(user) or (
            user.role == Role.TESTER
            and case.created_by == normalize_email(user.email)
            and self.can_edit(user, case)
        )

    # --- Ghi ---

    def create(self, user: User, *, screen_id: str, content: TestCaseContent) -> TestCase:
        allowed = can(
            user,
            Action.EDIT_TEST_CASE,
            is_member=self._is_member(user),
            owns_or_assigned=self._is_assigned(user, screen_id),
        )
        if not allowed:
            raise TestCasePermissionError("Bạn không có quyền tạo test case cho màn hình này")

        # Kiểm tra màn hình rồi tạo case trong CÙNG một khoá: màn hình không bị xoá chen vào giữa.
        with self._test_cases.lock():
            if self._screens.get(screen_id) is None:
                raise InvalidTestCaseError("Không tìm thấy màn hình")
            case = self._test_cases.create(
                screen_id=screen_id, content=content, actor=normalize_email(user.email)
            )

        self._audit(user, "CREATE", case.id, case.model_dump(mode="json"))
        self._sync_issue(case)
        self._refresh_status(case.screen_id)
        return case

    def update_content(
        self, user: User, case_id: str, *, version: int, content: TestCaseContent
    ) -> TestCase:
        case = self.get_case(case_id)
        self._require_edit(user, case)
        self._require_version(case, version)
        if case.status in (TestCaseStatus.DEPRECATED, TestCaseStatus.ARCHIVED):
            raise InvalidTransitionError(
                "Case đã lưu trữ hoặc ngừng dùng, hãy khôi phục trước khi sửa"
            )

        old_content = _content_of(case)
        new_content = content.model_dump(mode="json")
        if old_content == new_content:
            return case  # không đổi gì thì không ghi, không tăng version

        diff: dict[str, Any] = {
            field: [old_content[field], new_content[field]]
            for field in _CONTENT_FIELDS
            if old_content[field] != new_content[field]
        }
        # lấy từng trường (không dùng model_dump) để `steps` vẫn là TestStep chứ không thành dict
        changes: dict[str, Any] = {field: getattr(content, field) for field in _CONTENT_FIELDS}
        if case.status in (TestCaseStatus.IN_REVIEW, TestCaseStatus.APPROVED):
            # Nội dung đã đổi thì phải duyệt lại từ đầu.
            diff["status"] = [case.status.value, TestCaseStatus.DRAFT.value]
            changes["status"] = TestCaseStatus.DRAFT
        return self._save(user, case, changes, version, "UPDATE", diff)

    def transition(
        self, user: User, case_id: str, action: CaseAction, *, version: int, comment: str = ""
    ) -> TestCase:
        case = self.get_case(case_id)
        return self._transition_case(user, case, action, version, comment, refresh=True)

    def approve_many(self, user: User, items: list[tuple[str, int]]) -> BatchApproveResult:
        """Duyệt nhiều case một lượt; `items` là danh sách (case_id, version người duyệt đang xem).

        Lấy khoá tab TestCases một lần cho cả lượt và đọc Sheet một lần. Mỗi case vẫn kiểm tra
        version và trạng thái riêng: case lỗi thì bỏ qua (kèm lý do), các case còn lại vẫn được
        duyệt. Trạng thái việc chỉ tính lại một lần cho mỗi màn hình, sau khi đã nhả khoá.
        """
        if not self.can_review(user):
            raise TestCasePermissionError("Bạn không có quyền duyệt test case")
        if not self.review_enabled:
            raise InvalidTransitionError(REVIEW_OFF)

        result = BatchApproveResult()
        with self._test_cases.lock():
            by_id = {case.id: case for case in self._test_cases.list_all()}
            for case_id, version in items:
                case = by_id.get(case_id)
                try:
                    if case is None:
                        raise TestCaseNotFoundError(case_id)
                    result.approved.append(
                        self._transition_case(user, case, CaseAction.APPROVE, version, "")
                    )
                except TestCaseNotFoundError:
                    result.skipped.append(SkippedCase(case_id, "Không tìm thấy test case"))
                except VersionConflictError:
                    result.skipped.append(SkippedCase(case_id, "Case vừa được người khác cập nhật"))
                except InvalidTransitionError as error:
                    result.skipped.append(SkippedCase(case_id, str(error)))

        for screen_id in dict.fromkeys(case.screen_id for case in result.approved):
            self._refresh_status(screen_id)
        return result

    def approve_all_in_review(self, user: User) -> list[TestCase]:
        """Dự án vừa tắt bước duyệt: duyệt luôn mọi case đang chờ, một lượt ghi Sheet.

        Mỗi case ghi một dòng AuditLog `AUTO_APPROVE` rồi đẩy đồng bộ issue (nền, một luồng).
        """
        approved = self._test_cases.approve_all_in_review(normalize_email(user.email))
        for case in approved:
            self._audit(
                user,
                "AUTO_APPROVE",
                case.id,
                {"status": [TestCaseStatus.IN_REVIEW.value, TestCaseStatus.APPROVED.value]},
            )
            self._sync_issue(case)
        for screen_id in dict.fromkeys(case.screen_id for case in approved):
            self._refresh_status(screen_id)
        return approved

    def sync_issues(self, user: User) -> SyncIssuesResult:
        if not self.can_review(user):
            raise TestCasePermissionError("Bạn không có quyền đồng bộ issue")
        if self._issue_syncer is None or self._project is None:
            raise RuntimeError("GitHub chưa được cấu hình")

        result = SyncIssuesResult()
        screen_names = {screen.id: screen.name for screen in self._screens.list_all()}
        for case in self._test_cases.list_all()[:MAX_SYNC_BATCH_SIZE]:
            try:
                outcome = self._issue_syncer.sync_case(
                    self._project, case, screen_name=screen_names.get(case.screen_id, "")
                )
                setattr(result, outcome, getattr(result, outcome) + 1)
            except Exception as error:
                result.failed.append(SkippedCase(case.id, str(error)))
                if "giới hạn" in str(error):
                    break
        return result

    # --- Nội bộ ---

    def _transition_case(
        self,
        user: User,
        case: TestCase,
        action: CaseAction,
        version: int,
        comment: str,
        *,
        refresh: bool = False,
    ) -> TestCase:
        if action in {CaseAction.ARCHIVE, CaseAction.UNARCHIVE}:
            if not self.can_archive(user, case):
                raise TestCasePermissionError("Bạn không có quyền lưu trữ test case này")
        elif action in _REVIEW_ACTIONS:
            if not self.can_review(user):
                raise TestCasePermissionError("Bạn không có quyền duyệt test case")
            if action in {CaseAction.APPROVE, CaseAction.RETURN} and not self.review_enabled:
                raise InvalidTransitionError(REVIEW_OFF)
        else:
            self._require_edit(user, case)
        self._require_version(case, version)

        allowed_from, target = _TRANSITIONS[action]
        if action == CaseAction.SUBMIT and not self.review_enabled:
            target = TestCaseStatus.APPROVED  # tắt bước duyệt: gửi là duyệt luôn
        if case.status not in allowed_from:
            raise InvalidTransitionError(
                f"Không thể thực hiện thao tác này khi case đang ở trạng thái {case.status.value}"
            )

        diff: dict[str, Any] = {"status": [case.status.value, target.value]}
        if action == CaseAction.RETURN:
            comment = comment.strip()
            if not 1 <= len(comment) <= MAX_COMMENT_LENGTH:
                raise InvalidTestCaseError("Trả lại phải kèm nhận xét")
            diff["comment"] = comment
        saved = self._save(
            user, case, {"status": target}, version, action.value, diff, refresh=refresh
        )
        if action == CaseAction.SUBMIT and target == TestCaseStatus.IN_REVIEW:
            self._notify_submitted(user, saved)
        if self._notifier is not None and case.created_by != normalize_email(user.email):
            if action == CaseAction.RETURN:
                self._notifier.case_returned(
                    email=case.created_by, project_id=self._project_id,
                    case_id=case.id, comment=comment,
                )
            elif action == CaseAction.APPROVE:
                self._notifier.case_approved(
                    email=case.created_by, project_id=self._project_id, case_id=case.id
                )
        return saved

    def _notify_submitted(self, actor: User, case: TestCase) -> None:
        """Báo cho người có quyền duyệt; lỗi đọc người nhận không làm hỏng việc gửi duyệt."""
        if self._notifier is None or self._users is None:
            return
        try:
            member_emails = {
                member.email for member in self._members.list_for_project(self._project_id)
            }
            actor_email = normalize_email(actor.email)
            recipients = [
                user.email
                for user in self._users.list_all()
                if user.active
                and user.email != actor_email
                and (
                    user.role == Role.ADMIN
                    or (user.role == Role.QA_LEAD and user.email in member_emails)
                )
            ]
            self._notifier.case_submitted(
                emails=recipients, project_id=self._project_id, case_id=case.id
            )
        except Exception:
            logger.warning(
                "Không xác định được người nhận khi case %s được gửi duyệt",
                case.id,
                exc_info=True,
            )

    def _require_edit(self, user: User, case: TestCase) -> None:
        if not self.can_edit(user, case):
            raise TestCasePermissionError("Bạn không có quyền sửa test case này")

    @staticmethod
    def _require_version(case: TestCase, version: int) -> None:
        """Báo xung đột ngay nếu người dùng đang xem bản cũ (trước cả kiểm tra trạng thái)."""
        if case.version != version:
            raise VersionConflictError(case)

    def _save(
        self,
        user: User,
        case: TestCase,
        changes: dict[str, Any],
        version: int,
        audit_action: str,
        diff: dict[str, Any],
        *,
        refresh: bool = True,
    ) -> TestCase:
        # `case` vừa đọc từ Sheet: chỉ đổi đúng các trường trong `changes`, còn lại giữ nguyên.
        saved = self._test_cases.save(
            case.model_copy(update=changes),
            expected_version=version,
            actor=normalize_email(user.email),
        )
        self._audit(user, audit_action, saved.id, diff)
        self._sync_issue(saved)
        # Trạng thái việc chỉ phụ thuộc trạng thái của các case. Case không đổi trạng thái
        # (ví dụ sửa chữ trong case Nháp) thì khỏi tính lại, đỡ vài lượt gọi Google.
        if refresh and "status" in changes:
            self._refresh_status(saved.screen_id)
        return saved

    def _sync_issue(self, case: TestCase) -> None:
        if self._issue_sync is None or self._project is None:
            return
        try:
            if self._screen_names is None:
                self._screen_names = {screen.id: screen.name for screen in self._screens.list_all()}
            self._issue_sync.sync_case(
                self._project, case, screen_name=self._screen_names.get(case.screen_id, "")
            )
        except Exception:
            # Case đã được ghi vào Sheet; lỗi GitHub không được khiến người dùng tạo lại.
            logger.warning("Không gửi được đồng bộ issue cho case %s", case.id, exc_info=True)

    def _refresh_status(self, screen_id: str) -> None:
        """Tính lại trạng thái việc, cố gắng hết sức: case đã ghi rồi thì không được báo lỗi.

        Nếu báo lỗi ở đây, người dùng tưởng chưa lưu và bấm lại, thế là sinh ra case trùng.
        Lần ghi sau của màn hình này sẽ tính lại cho đúng.
        """
        try:
            self._status_updater.refresh_screen(screen_id)
        except (LockTimeout, SheetAccessDeniedError, MissingColumnsError):
            logger.warning("Không tính lại được trạng thái việc của %s", screen_id, exc_info=True)

    def _audit(self, user: User, action: str, case_id: str, diff: dict[str, Any]) -> None:
        self._audit_log.record(
            actor=user.email, action=action, entity=AUDIT_ENTITY, entity_id=case_id, diff=diff
        )
