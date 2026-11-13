"""Nghiệp vụ test case: quyền theo case, chuyển trạng thái, AuditLog, trạng thái việc."""

from collections.abc import Callable
from datetime import timedelta

import fakeredis
import pytest

from app.core.assignment_status import AssignmentStatusUpdater
from app.core.models.assignment import AssignmentStatus
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
