"""Nghiệp vụ test case: quyền theo từng case, chuyển trạng thái, AuditLog.

Sau mỗi lần ghi, service ghi AuditLog rồi tính lại trạng thái việc của màn hình.
Việc tính lại lấy khoá `assignments`, nên luôn chạy SAU KHI đã nhả khoá `test-cases`
(thứ tự khoá: assignments trước, test-cases sau, không bao giờ ngược lại).
"""

from enum import StrEnum
from typing import Any

from app.core.assignment_status import AssignmentStatusUpdater
from app.core.models.test_case import TestCase, TestCaseContent, TestCaseStatus
from app.core.models.user import User, normalize_email
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

AUDIT_ENTITY = "test_case"
MAX_COMMENT_LENGTH = 1000


class CaseAction(StrEnum):
    SUBMIT = "SUBMIT"
    APPROVE = "APPROVE"
    RETURN = "RETURN"
    DEPRECATE = "DEPRECATE"
    RESTORE = "RESTORE"


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
}
# Người duyệt (QA Lead/Admin) mới được làm; còn lại cần quyền sửa case.
_REVIEW_ACTIONS = {CaseAction.APPROVE, CaseAction.RETURN, CaseAction.RESTORE}

_CONTENT_FIELDS = list(TestCaseContent.model_fields)


def _content_of(case: TestCase) -> dict[str, Any]:
    """Phần nội dung của case, dạng dict thuần JSON để so sánh và ghi diff."""
    return case.model_dump(mode="json", include=set(_CONTENT_FIELDS))


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
    ) -> None:
        self._project_id = project_id
        self._test_cases = test_cases
        self._screens = screens
        self._assignments = assignments
        self._members = members
        self._status_updater = status_updater
        self._audit_log = audit_log

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
        self._status_updater.refresh_screen(case.screen_id)
        return case

    def update_content(
        self, user: User, case_id: str, *, version: int, content: TestCaseContent
    ) -> TestCase:
        case = self.get_case(case_id)
        self._require_edit(user, case)
        self._require_version(case, version)
        if case.status == TestCaseStatus.DEPRECATED:
            raise InvalidTransitionError("Case đã ngừng dùng, hãy khôi phục trước khi sửa")

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
        if action in _REVIEW_ACTIONS:
            if not self.can_review(user):
                raise TestCasePermissionError("Bạn không có quyền duyệt test case")
        else:
            self._require_edit(user, case)
        self._require_version(case, version)

        allowed_from, target = _TRANSITIONS[action]
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
        return self._save(user, case, {"status": target}, version, action.value, diff)

    # --- Nội bộ ---

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
    ) -> TestCase:
        # `case` vừa đọc từ Sheet: chỉ đổi đúng các trường trong `changes`, còn lại giữ nguyên.
        saved = self._test_cases.save(
            case.model_copy(update=changes),
            expected_version=version,
            actor=normalize_email(user.email),
        )
        self._audit(user, audit_action, saved.id, diff)
        self._status_updater.refresh_screen(saved.screen_id)
        return saved

    def _audit(self, user: User, action: str, case_id: str, diff: dict[str, Any]) -> None:
        self._audit_log.record(
            actor=user.email, action=action, entity=AUDIT_ENTITY, entity_id=case_id, diff=diff
        )
