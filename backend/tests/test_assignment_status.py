"""Trạng thái việc được giao tự suy ra từ test case của tester."""

from datetime import UTC, datetime, timedelta

import fakeredis
import pytest

from app.core.assignment_status import AssignmentStatusUpdater, derive_assignment_status
from app.core.locks.redis_lock import LockTimeout
from app.core.models.assignment import AssignmentStatus
from app.core.models.test_case import (
    ExecutionMode,
    Priority,
    Severity,
    TestCase,
    TestCaseContent,
    TestCaseStatus,
    TestStep,
)
from app.core.repositories.assignments import AssignmentRepository
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import ProjectRepository
from app.core.repositories.test_cases import TestCaseRepository
from app.core.time import today_in_vietnam
from tests.conftest import make_project
from tests.fakes import FakeSheetsGateway

SCREEN = "SC-0001"
TESTER = "a@x.com"
NOW = datetime(2026, 11, 13, tzinfo=UTC)


def make_case(
    status: str,
    *,
    case_id: str = "TC-000001",
    screen_id: str = SCREEN,
    created_by: str = TESTER,
) -> TestCase:
    return TestCase(
        id=case_id,
        screen_id=screen_id,
        title="Đăng nhập",
        steps=[TestStep(action="Bấm nút", expected="")],
        expected_result="Thành công",
        severity=Severity.LOW,
        priority=Priority.P1,
        status=TestCaseStatus(status),
        created_by=created_by,
        updated_by=created_by,
        created_at=NOW,
        updated_at=NOW,
        version=1,
    )


def derive(cases: list[TestCase], **kwargs: frozenset[str]) -> AssignmentStatus:
    return derive_assignment_status(cases, screen_id=SCREEN, tester_email=TESTER, **kwargs)


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ([], "TODO"),
        (["DEPRECATED"], "TODO"),
        (["DRAFT", "APPROVED"], "WRITING"),
        (["IN_REVIEW", "APPROVED"], "IN_REVIEW"),
        (["APPROVED", "APPROVED", "DEPRECATED"], "APPROVED"),
    ],
)
def test_derive_status(statuses: list[str], expected: str) -> None:
    cases = [make_case(s, case_id=f"TC-{i:06d}") for i, s in enumerate(statuses, start=1)]

    assert derive(cases) == AssignmentStatus(expected)


def test_only_counts_this_testers_cases_on_this_screen() -> None:
    cases = [
        make_case("DRAFT", created_by="other@x.com"),
        make_case("DRAFT", screen_id="SC-0002"),
    ]

    assert derive(cases) == AssignmentStatus.TODO


def test_tested_when_all_approved_cases_have_results() -> None:
    cases = [make_case("APPROVED", case_id="TC-000001"), make_case("APPROVED", case_id="TC-000002")]

    assert derive(cases, tested_case_ids=frozenset({"TC-000001", "TC-000002"})) == (
        AssignmentStatus.TESTED
    )
    assert derive(cases, tested_case_ids=frozenset({"TC-000001"})) == AssignmentStatus.APPROVED


class Setup:
    """Repository dùng chung giữa các test; `updater()` dựng bộ repository RIÊNG như một request."""

    def __init__(
        self,
        gateway: FakeSheetsGateway,
        redis: fakeredis.FakeRedis,
        sheet: str,
        project_id: str,
    ) -> None:
        self._args = (gateway, sheet, redis, project_id)
        self.assignments = self._assignments()
        self.test_cases = self._test_cases()

    def _assignments(self) -> AssignmentRepository:
        return AssignmentRepository(*self._args, lock_wait_seconds=0.1)

    def _test_cases(self) -> TestCaseRepository:
        return TestCaseRepository(*self._args, lock_wait_seconds=0.1)

    def updater(self) -> AssignmentStatusUpdater:
        return AssignmentStatusUpdater(self._assignments(), self._test_cases())


@pytest.fixture
def setup(
    gateway: FakeSheetsGateway,
    redis: fakeredis.FakeRedis,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
) -> Setup:
    project = make_project(projects, members, gateway)
    return Setup(gateway, redis, project.spreadsheet_id, project.id)


def add_draft_case(setup: Setup, actor: str) -> None:
    content = TestCaseContent(
        title="Đăng nhập",
        steps=[TestStep(action="Bấm nút")],
        expected_result="Thành công",
        severity=Severity.LOW,
        priority=Priority.P1,
    )
    setup.test_cases.create(screen_id=SCREEN, content=content, actor=actor)


def test_refresh_updates_only_changed_rows(gateway: FakeSheetsGateway, setup: Setup) -> None:
    deadline = today_in_vietnam() + timedelta(days=7)
    setup.assignments.create(screen_id=SCREEN, assignee_email="a@x.com", deadline=deadline)
    setup.assignments.create(screen_id=SCREEN, assignee_email="b@x.com", deadline=deadline)
    add_draft_case(setup, "a@x.com")
    gateway.calls.clear()

    setup.updater().refresh_screen(SCREEN)

    statuses = {a.assignee_email: a.status for a in setup.assignments.list_all()}
    assert statuses == {"a@x.com": AssignmentStatus.WRITING, "b@x.com": AssignmentStatus.TODO}
    assert [c for c in gateway.calls if c.startswith("update:Assignments!")] == [
        "update:Assignments!2"
    ]


def test_refresh_reads_cases_inside_lock(gateway: FakeSheetsGateway, setup: Setup) -> None:
    """Request chen vào sau lần đọc TestCases phải bị khoá chặn lại."""
    deadline = today_in_vietnam() + timedelta(days=7)
    setup.assignments.create(screen_id=SCREEN, assignee_email="a@x.com", deadline=deadline)
    add_draft_case(setup, "a@x.com")
    blocked: list[bool] = []

    def competing_refresh() -> None:
        try:
            setup.updater().refresh_screen(SCREEN)
        except LockTimeout:  # bị khoá chặn lại: đúng như mong muốn
            blocked.append(True)
        else:
            blocked.append(False)

    gateway.after_next_read["TestCases"] = competing_refresh

    setup.updater().refresh_screen(SCREEN)

    assert blocked == [True]
    assert setup.assignments.list_all()[0].status == AssignmentStatus.WRITING


def _with_mode(case: TestCase, mode: ExecutionMode) -> TestCase:
    return case.model_copy(update={"execution_mode": mode})


def test_all_manual_tested_is_tested() -> None:
    cases = [
        _with_mode(make_case("TESTED", case_id="TC-000001"), ExecutionMode.MANUAL),
        _with_mode(make_case("TESTED", case_id="TC-000002"), ExecutionMode.MANUAL),
    ]
    assert derive(cases) == AssignmentStatus.TESTED


def test_mixed_manual_tested_and_automation_approved_is_approved() -> None:
    cases = [
        _with_mode(make_case("TESTED", case_id="TC-000001"), ExecutionMode.MANUAL),
        _with_mode(make_case("APPROVED", case_id="TC-000002"), ExecutionMode.AUTOMATION),
    ]
    assert derive(cases) == AssignmentStatus.APPROVED


def test_manual_draft_is_writing() -> None:
    cases = [_with_mode(make_case("DRAFT"), ExecutionMode.MANUAL)]
    assert derive(cases) == AssignmentStatus.WRITING
