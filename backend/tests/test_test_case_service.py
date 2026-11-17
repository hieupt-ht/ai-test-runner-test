"""Nghiệp vụ test case: quyền theo case, chuyển trạng thái, AuditLog, trạng thái việc."""

from collections.abc import Callable
from datetime import timedelta

import fakeredis
import pytest

from app.core.assignment_status import AssignmentStatusUpdater
from app.core.locks.redis_lock import redis_lock
from app.core.models.assignment import AssignmentStatus
from app.core.models.media import Media, MediaKind
from app.core.models.project import Project
from app.core.models.test_case import (
    Priority,
    Severity,
    TestCase,
    TestCaseContent,
    TestCaseStatus,
    TestStep,
)
from app.core.models.user import Role
from app.core.repositories.assignments import AssignmentRepository
from app.core.repositories.audit_log import AuditLogRepository
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import ProjectRepository
from app.core.repositories.screens import ScreenRepository
from app.core.repositories.test_cases import TestCaseRepository, VersionConflictError
from app.core.services.test_cases import (
    CaseAction,
    InvalidTestCaseError,
    InvalidTransitionError,
    TestCasePermissionError,
    TestCaseService,
)
from app.core.time import today_in_vietnam
from tests.conftest import make_project, make_user
from tests.fakes import FakeSheetsGateway

LEAD = make_user("lead@x.com", role=Role.QA_LEAD)
TESTER_A = make_user("a@x.com", role=Role.TESTER)
TESTER_B = make_user("b@x.com", role=Role.TESTER)
VIEWER = make_user("viewer@x.com", role=Role.VIEWER)


def content(title: str = "Đăng nhập đúng") -> TestCaseContent:
    return TestCaseContent(
        title=title,
        steps=[TestStep(action="Nhập email", expected="")],
        expected_result="Vào được trang chính",
        severity=Severity.HIGH,
        priority=Priority.P1,
    )


class Env:
    """Các repository và service của một dự án."""

    def __init__(
        self,
        gateway: FakeSheetsGateway,
        redis: fakeredis.FakeRedis,
        project: Project,
        members: ProjectMemberRepository,
    ) -> None:
        sheet = project.spreadsheet_id
        self.project = project
        self.gateway = gateway
        self.screens = ScreenRepository(gateway, sheet, redis, project.id, lock_wait_seconds=0.1)
        self.assignments = AssignmentRepository(
            gateway, sheet, redis, project.id, lock_wait_seconds=0.1
        )
        self.test_cases = TestCaseRepository(
            gateway, sheet, redis, project.id, lock_wait_seconds=0.1
        )
        self.service = TestCaseService(
            project_id=project.id,
            test_cases=self.test_cases,
            screens=self.screens,
            assignments=self.assignments,
            members=members,
            status_updater=AssignmentStatusUpdater(self.assignments, self.test_cases),
            audit_log=AuditLogRepository(gateway, sheet),
        )

    def assignment_status(self, email: str) -> AssignmentStatus:
        (found,) = [a for a in self.assignments.list_all() if a.assignee_email == email]
        return found.status

    def audit_rows(self) -> int:
        return len(self.gateway.data[self.project.spreadsheet_id]["AuditLog"])


@pytest.fixture
def env(
    gateway: FakeSheetsGateway,
    redis: fakeredis.FakeRedis,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
) -> Env:
    project = make_project(
        projects,
        members,
        gateway,
        member_emails=(LEAD.email, TESTER_A.email, TESTER_B.email, VIEWER.email),
    )
    built = Env(gateway, redis, project, members)
    built.screens.create(name="Đăng nhập", description="", route="", code_paths=[])
    built.screens.create(name="Đăng ký", description="", route="", code_paths=[])
    built.assignments.create(
        screen_id="SC-0001",
        assignee_email=TESTER_A.email,
        deadline=today_in_vietnam() + timedelta(days=7),
    )
    return built


@pytest.fixture
def case_of_a(env: Env) -> Callable[[], TestCase]:
    return lambda: env.service.create(TESTER_A, screen_id="SC-0001", content=content())


def test_tester_creates_case_on_assigned_screen_and_assignment_becomes_writing(env: Env) -> None:
    case = env.service.create(TESTER_A, screen_id="SC-0001", content=content())

    assert case.id == "TC-000001"
    assert case.status == TestCaseStatus.DRAFT
    assert case.created_by == "a@x.com"
    assert env.assignment_status("a@x.com") == AssignmentStatus.WRITING
    assert env.service.history(case.id)[0].action == "CREATE"


def test_create_on_unknown_screen_is_invalid(env: Env) -> None:
    with pytest.raises(InvalidTestCaseError, match="Không tìm thấy màn hình"):
        env.service.create(LEAD, screen_id="SC-9999", content=content())


def test_tester_edit_rules(env: Env, case_of_a: Callable[[], TestCase]) -> None:
    case = case_of_a()

    with pytest.raises(TestCasePermissionError):
        env.service.update_content(TESTER_B, case.id, version=1, content=content("Khác"))
    with pytest.raises(TestCasePermissionError):
        env.service.create(TESTER_B, screen_id="SC-0001", content=content())
    with pytest.raises(TestCasePermissionError):
        env.service.create(VIEWER, screen_id="SC-0001", content=content())

    # Bỏ giao việc của A: vẫn sửa được case mình tạo.
    (assignment,) = env.assignments.list_all()
    env.assignments.delete(assignment.id)
    updated = env.service.update_content(TESTER_A, case.id, version=1, content=content("Mới"))
    assert updated.title == "Mới"
    # ...nhưng không còn tạo được case mới trên màn hình đó.
    with pytest.raises(TestCasePermissionError):
        env.service.create(TESTER_A, screen_id="SC-0001", content=content())


def test_full_review_flow(env: Env, case_of_a: Callable[[], TestCase]) -> None:
    case = case_of_a()
    assert case.version == 1

    submitted = env.service.transition(TESTER_A, case.id, CaseAction.SUBMIT, version=1)
    assert (submitted.status, submitted.version) == (TestCaseStatus.IN_REVIEW, 2)
    assert env.assignment_status("a@x.com") == AssignmentStatus.IN_REVIEW

    approved = env.service.transition(LEAD, case.id, CaseAction.APPROVE, version=2)
    assert (approved.status, approved.version) == (TestCaseStatus.APPROVED, 3)
    assert env.assignment_status("a@x.com") == AssignmentStatus.APPROVED


def test_return_requires_comment_and_is_in_history(
    env: Env, case_of_a: Callable[[], TestCase]
) -> None:
    case = case_of_a()
    env.service.transition(TESTER_A, case.id, CaseAction.SUBMIT, version=1)

    with pytest.raises(InvalidTestCaseError, match="Trả lại phải kèm nhận xét"):
        env.service.transition(LEAD, case.id, CaseAction.RETURN, version=2, comment="  ")

    returned = env.service.transition(
        LEAD, case.id, CaseAction.RETURN, version=2, comment="Thiếu bước đăng xuất"
    )

    assert returned.status == TestCaseStatus.DRAFT
    latest = env.service.history(case.id)[0]
    assert latest.action == "RETURN"
    assert latest.diff["comment"] == "Thiếu bước đăng xuất"
    assert latest.diff["status"] == ["IN_REVIEW", "DRAFT"]


def test_editing_approved_case_moves_it_back_to_draft(
    env: Env, case_of_a: Callable[[], TestCase]
) -> None:
    case = case_of_a()
    env.service.transition(TESTER_A, case.id, CaseAction.SUBMIT, version=1)
    env.service.transition(LEAD, case.id, CaseAction.APPROVE, version=2)

    edited = env.service.update_content(TESTER_A, case.id, version=3, content=content("Sửa"))

    assert edited.status == TestCaseStatus.DRAFT
    assert edited.version == 4
    assert env.assignment_status("a@x.com") == AssignmentStatus.WRITING
    diff = env.service.history(case.id)[0].diff
    assert diff["title"] == ["Đăng nhập đúng", "Sửa"]
    assert diff["status"] == ["APPROVED", "DRAFT"]


def test_unchanged_content_does_not_write(env: Env, case_of_a: Callable[[], TestCase]) -> None:
    case = case_of_a()
    rows_before = env.audit_rows()

    result = env.service.update_content(TESTER_A, case.id, version=1, content=content())

    assert result.version == 1
    assert env.test_cases.get(case.id) == case
    assert env.audit_rows() == rows_before


def test_invalid_transitions(env: Env, case_of_a: Callable[[], TestCase]) -> None:
    case = case_of_a()

    with pytest.raises(InvalidTransitionError, match="đang ở trạng thái DRAFT"):
        env.service.transition(LEAD, case.id, CaseAction.APPROVE, version=1)
    with pytest.raises(InvalidTransitionError):
        env.service.transition(LEAD, case.id, CaseAction.RESTORE, version=1)

    env.service.transition(TESTER_A, case.id, CaseAction.DEPRECATE, version=1)
    with pytest.raises(InvalidTransitionError, match="hãy khôi phục trước khi sửa"):
        env.service.update_content(TESTER_A, case.id, version=2, content=content("Sửa"))
    with pytest.raises(InvalidTransitionError):
        env.service.transition(TESTER_A, case.id, CaseAction.DEPRECATE, version=2)


def test_tester_cannot_approve_or_restore(env: Env, case_of_a: Callable[[], TestCase]) -> None:
    case = case_of_a()
    env.service.transition(TESTER_A, case.id, CaseAction.SUBMIT, version=1)
    with pytest.raises(TestCasePermissionError):
        env.service.transition(TESTER_A, case.id, CaseAction.APPROVE, version=2)

    env.service.transition(LEAD, case.id, CaseAction.APPROVE, version=2)
    env.service.transition(TESTER_A, case.id, CaseAction.DEPRECATE, version=3)
    with pytest.raises(TestCasePermissionError):
        env.service.transition(TESTER_A, case.id, CaseAction.RESTORE, version=4)


def test_approve_with_stale_version_is_conflict(
    env: Env, case_of_a: Callable[[], TestCase]
) -> None:
    case = case_of_a()
    env.service.transition(TESTER_A, case.id, CaseAction.SUBMIT, version=1)  # version 2
    env.service.update_content(TESTER_A, case.id, version=2, content=content("Sửa"))  # v3, DRAFT

    with pytest.raises(VersionConflictError):
        env.service.transition(LEAD, case.id, CaseAction.APPROVE, version=2)

    current = env.service.get_case(case.id)
    assert current.status == TestCaseStatus.DRAFT
    assert current.version == 3


def test_deprecate_and_restore(env: Env, case_of_a: Callable[[], TestCase]) -> None:
    case = case_of_a()

    deprecated = env.service.transition(TESTER_A, case.id, CaseAction.DEPRECATE, version=1)
    assert deprecated.status == TestCaseStatus.DEPRECATED
    assert env.assignment_status("a@x.com") == AssignmentStatus.TODO

    restored = env.service.transition(LEAD, case.id, CaseAction.RESTORE, version=2)
    assert restored.status == TestCaseStatus.DRAFT
    assert env.assignment_status("a@x.com") == AssignmentStatus.WRITING
    assert [e.action for e in env.service.history(case.id)] == ["RESTORE", "DEPRECATE", "CREATE"]


def _case_rows(env: Env) -> int:
    return len(env.test_cases.list_all())


def test_create_still_returns_case_when_status_refresh_times_out(
    env: Env, redis: fakeredis.FakeRedis
) -> None:
    # Giữ khoá assignments từ chỗ khác: refresh_screen sẽ hết giờ chờ (0.1 giây)
    with redis_lock(redis, f"lock:{env.project.id}:assignments", wait_seconds=0.1):
        case = env.service.create(TESTER_A, screen_id="SC-0001", content=content())

    assert case.id == "TC-000001"
    assert _case_rows(env) == 1


def test_update_still_returns_case_when_status_refresh_times_out(
    env: Env, redis: fakeredis.FakeRedis, case_of_a: Callable[[], TestCase]
) -> None:
    case = case_of_a()

    with redis_lock(redis, f"lock:{env.project.id}:assignments", wait_seconds=0.1):
        saved = env.service.update_content(TESTER_A, case.id, version=1, content=content("Mới"))

    assert saved.version == 2 and saved.title == "Mới"
    assert _case_rows(env) == 1


def test_editing_draft_content_does_not_touch_assignments_tab(
    env: Env, case_of_a: Callable[[], TestCase]
) -> None:
    case = case_of_a()
    env.gateway.calls.clear()

    env.service.update_content(TESTER_A, case.id, version=1, content=content("Sửa tiêu đề"))

    # Trạng thái case vẫn là Nháp nên trạng thái việc không thể đổi: khỏi đọc/ghi Assignments.
    assert not [call for call in env.gateway.calls if "Assignments" in call]
    assert env.assignment_status("a@x.com") == AssignmentStatus.WRITING


def test_editing_approved_case_still_refreshes_assignment(
    env: Env, case_of_a: Callable[[], TestCase]
) -> None:
    case = case_of_a()
    env.service.transition(TESTER_A, case.id, CaseAction.SUBMIT, version=1)
    env.service.transition(LEAD, case.id, CaseAction.APPROVE, version=2)
    assert env.assignment_status("a@x.com") == AssignmentStatus.APPROVED

    # Sửa case đã duyệt thì case về Nháp → việc phải quay lại "Đang viết".
    env.service.update_content(TESTER_A, case.id, version=3, content=content("Sửa"))

    assert env.assignment_status("a@x.com") == AssignmentStatus.WRITING


# --- Duyệt hàng loạt ---


def _in_review_case(env: Env, title: str, screen_id: str = "SC-0001") -> TestCase:
    case = env.service.create(TESTER_A, screen_id=screen_id, content=content(title))
    return env.service.transition(TESTER_A, case.id, CaseAction.SUBMIT, version=1)


def test_approve_many_approves_each_case_and_audits_each(env: Env) -> None:
    first = _in_review_case(env, "Case 1")
    second = _in_review_case(env, "Case 2")
    audit_before = env.audit_rows()

    result = env.service.approve_many(
        LEAD, [(first.id, first.version), (second.id, second.version)]
    )

    assert [case.id for case in result.approved] == [first.id, second.id]
    assert result.skipped == []
    assert all(case.status == TestCaseStatus.APPROVED for case in env.test_cases.list_all())
    assert env.audit_rows() == audit_before + 2
    assert env.assignment_status("a@x.com") == AssignmentStatus.APPROVED


def test_approve_many_skips_bad_cases_and_reports_reason(env: Env) -> None:
    good = _in_review_case(env, "Tốt")
    stale = _in_review_case(env, "Bản cũ")
    draft = env.service.create(TESTER_A, screen_id="SC-0001", content=content("Nháp"))

    result = env.service.approve_many(
        LEAD,
        [
            (good.id, good.version),
            (stale.id, stale.version - 1),  # version cũ -> xung đột
            (draft.id, draft.version),  # đang Nháp -> sai trạng thái
            ("TC-999999", 1),  # không tồn tại
        ],
    )

    assert [case.id for case in result.approved] == [good.id]
    assert [item.case_id for item in result.skipped] == [stale.id, draft.id, "TC-999999"]
    assert all(item.reason for item in result.skipped)
    assert env.service.get_case(stale.id).status == TestCaseStatus.IN_REVIEW


def test_approve_many_requires_reviewer(env: Env) -> None:
    case = _in_review_case(env, "Case")

    with pytest.raises(TestCasePermissionError):
        env.service.approve_many(TESTER_A, [(case.id, case.version)])

    assert env.service.get_case(case.id).status == TestCaseStatus.IN_REVIEW


def test_approve_many_holds_tab_lock_once_and_releases_it(
    env: Env, redis: fakeredis.FakeRedis
) -> None:
    first = _in_review_case(env, "Case 1")
    second = _in_review_case(env, "Case 2")

    env.service.approve_many(LEAD, [(first.id, first.version), (second.id, second.version)])

    # nhả khoá hết: người khác lấy được ngay, và việc tính lại trạng thái đã chạy được sau đó
    with redis_lock(redis, f"lock:{env.project.id}:test-cases", wait_seconds=0.1):
        pass


def test_approve_many_refreshes_each_screen_once(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    first = _in_review_case(env, "Case 1")
    second = _in_review_case(env, "Case 2")
    refreshed: list[str] = []
    monkeypatch.setattr(env.service._status_updater, "refresh_screen", refreshed.append)

    env.service.approve_many(LEAD, [(first.id, first.version), (second.id, second.version)])

    assert refreshed == ["SC-0001"]


# ----- Sửa case đã gửi tại chỗ (Task 8) -----


class EditSink:
    """Ghi lại các lần service báo "case đã sửa" (không gọi GitHub)."""

    def __init__(self) -> None:
        self.edits: list[tuple[str, list[str], bool]] = []

    def sync_case(self, project: Project, case: TestCase, *, screen_name: str = "") -> None:
        pass

    def note_case_edited(
        self, project: Project, case: TestCase, *, changed: list[str], needs_rerun: bool
    ) -> None:
        self.edits.append((case.id, changed, needs_rerun))


def service_with(
    env: Env, *, review: bool, sink: EditSink, has_results: bool = False
) -> TestCaseService:
    return TestCaseService(
        project_id=env.project.id,
        test_cases=env.test_cases,
        screens=env.screens,
        assignments=env.assignments,
        members=env.service._members,
        status_updater=AssignmentStatusUpdater(env.assignments, env.test_cases),
        audit_log=AuditLogRepository(env.gateway, env.project.spreadsheet_id),
        issue_sync=sink,
        project=env.project.model_copy(update={"require_review": review}),
        has_results=lambda case_id: has_results,
    )


def approved_case(env: Env, service: TestCaseService) -> TestCase:
    case = service.create(TESTER_A, screen_id="SC-0001", content=content())
    return service.transition(TESTER_A, case.id, CaseAction.SUBMIT, version=1)


def test_edit_approved_keeps_status_when_review_off(env: Env) -> None:
    sink = EditSink()
    service = service_with(env, review=False, sink=sink)
    case = approved_case(env, service)
    assert case.status == TestCaseStatus.APPROVED

    saved = service.update_content(
        TESTER_A, case.id, version=case.version, content=content("Tiêu đề khác")
    )

    assert saved.status == TestCaseStatus.APPROVED
    assert saved.version == case.version + 1
    assert sink.edits == [(case.id, ["Tiêu đề"], False)]


def test_edit_steps_with_results_requests_rerun(env: Env) -> None:
    sink = EditSink()
    service = service_with(env, review=False, sink=sink, has_results=True)
    case = approved_case(env, service)
    changed = content().model_copy(update={"steps": [TestStep(action="Bước mới", expected="")]})

    service.update_content(TESTER_A, case.id, version=case.version, content=changed)

    assert sink.edits[-1] == (case.id, ["Các bước"], True)


def test_edit_steps_without_results_no_rerun(env: Env) -> None:
    sink = EditSink()
    service = service_with(env, review=False, sink=sink, has_results=False)
    case = approved_case(env, service)
    changed = content().model_copy(update={"steps": [TestStep(action="Bước mới", expected="")]})

    service.update_content(TESTER_A, case.id, version=case.version, content=changed)

    assert sink.edits[-1][2] is False


def test_edit_with_review_on_resets_to_draft_and_sends_no_note(env: Env) -> None:
    sink = EditSink()
    service = service_with(env, review=True, sink=sink)
    case = service.create(TESTER_A, screen_id="SC-0001", content=content())
    service.transition(TESTER_A, case.id, CaseAction.SUBMIT, version=1)
    service.transition(LEAD, case.id, CaseAction.APPROVE, version=2)

    saved = service.update_content(
        TESTER_A, case.id, version=3, content=content("Tiêu đề khác")
    )

    assert saved.status == TestCaseStatus.DRAFT
    assert sink.edits == []


# --- Ảnh/video hướng dẫn: kiểm tra cloud và dọn file ---


class FakeJanitor:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def delete(self, items: list[Media]) -> None:
        self.deleted.extend(item.public_id for item in items)


def image(public_id: str, cloud: str = "mine") -> Media:
    return Media(
        kind=MediaKind.IMAGE,
        url=f"https://res.cloudinary.com/{cloud}/image/upload/{public_id}.png",
        public_id=public_id,
        note="chụp màn hình",
    )


def with_media(env: Env, janitor: FakeJanitor, cloud_name: str = "mine") -> TestCaseService:
    return TestCaseService(
        project_id=env.project.id,
        test_cases=env.test_cases,
        screens=env.screens,
        assignments=env.assignments,
        members=env.service._members,
        status_updater=AssignmentStatusUpdater(env.assignments, env.test_cases),
        audit_log=AuditLogRepository(env.gateway, env.project.spreadsheet_id),
        cloud_name=cloud_name,
        janitor=janitor,  # type: ignore[arg-type]
    )


def content_with(case_media: list[Media], step_media: list[Media]) -> TestCaseContent:
    base = content()
    return base.model_copy(
        update={
            "guide_media": case_media,
            "steps": [TestStep(action="Nhập email", expected="", guide_media=step_media)],
        }
    )


def test_media_removed_from_case_is_sent_to_janitor(env: Env) -> None:
    janitor = FakeJanitor()
    service = with_media(env, janitor)
    case = service.create(
        TESTER_A, screen_id="SC-0001", content=content_with([image("a"), image("b")], [])
    )

    service.update_content(
        TESTER_A, case.id, version=1, content=content_with([image("b")], [])
    )

    assert janitor.deleted == ["a"]


def test_media_removed_from_a_step_is_also_cleaned(env: Env) -> None:
    janitor = FakeJanitor()
    service = with_media(env, janitor)
    case = service.create(
        TESTER_A, screen_id="SC-0001", content=content_with([], [image("s1")])
    )

    service.update_content(TESTER_A, case.id, version=1, content=content_with([], []))

    assert janitor.deleted == ["s1"]


def test_unchanged_media_is_not_deleted(env: Env) -> None:
    janitor = FakeJanitor()
    service = with_media(env, janitor)
    case = service.create(TESTER_A, screen_id="SC-0001", content=content_with([image("a")], []))

    renamed = content_with([image("a")], []).model_copy(update={"title": "Tên mới"})
    service.update_content(TESTER_A, case.id, version=1, content=renamed)

    assert janitor.deleted == []


def test_foreign_cloud_media_is_invalid_and_sheet_unchanged(env: Env) -> None:
    janitor = FakeJanitor()
    service = with_media(env, janitor)
    rows_before = len(env.gateway.data[env.project.spreadsheet_id]["TestCases"])

    with pytest.raises(InvalidTestCaseError, match="không thuộc kho Cloudinary"):
        service.create(
            TESTER_A,
            screen_id="SC-0001",
            content=content_with([image("x", cloud="other")], []),
        )

    assert len(env.gateway.data[env.project.spreadsheet_id]["TestCases"]) == rows_before
    case = service.create(TESTER_A, screen_id="SC-0001", content=content())
    with pytest.raises(InvalidTestCaseError):
        service.update_content(
            TESTER_A, case.id, version=1, content=content_with([], [image("y", cloud="other")])
        )
    assert env.test_cases.get(case.id).version == 1  # type: ignore[union-attr]
    assert janitor.deleted == []


def test_media_without_cloudinary_config_is_invalid(env: Env) -> None:
    service = with_media(env, FakeJanitor(), cloud_name="")
    with pytest.raises(InvalidTestCaseError, match="Chưa cấu hình Cloudinary"):
        service.create(TESTER_A, screen_id="SC-0001", content=content_with([image("a")], []))


def test_audit_diff_keeps_only_kind_and_note_of_media(env: Env) -> None:
    service = with_media(env, FakeJanitor())
    case = service.create(
        TESTER_A, screen_id="SC-0001", content=content_with([image("a")], [image("s1")])
    )
    service.update_content(
        TESTER_A, case.id, version=1, content=content_with([image("b")], [])
    )

    rows = env.gateway.data[env.project.spreadsheet_id]["AuditLog"]
    assert "res.cloudinary.com" not in str(rows)
    assert "chụp màn hình" in str(rows)  # ghi chú vẫn còn trong lịch sử
