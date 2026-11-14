import pytest
from fastapi import FastAPI

from app.api.project_scope import ProjectScope, scope_for
from app.api.services import Services
from app.core.models.run import RunScope, RunStatus
from app.core.models.test_case import (
    Priority,
    Severity,
    TestCase,
    TestCaseContent,
    TestCaseStatus,
    TestStep,
)
from app.core.repositories.runs import RunInProgressError, RunNotFoundError
from app.core.run_queue import RunQueue
from app.core.services.runs import NoCasesError, RunService, TooManyCasesError
from tests.conftest import make_project
from tests.fakes import FakeSheetsGateway

LEAD = "lead@x.com"


class Setup:
    def __init__(self, app: FastAPI, gateway: FakeSheetsGateway) -> None:
        services: Services = app.state.services
        self.project = make_project(services.projects, services.members, gateway)
        self.scope: ProjectScope = scope_for(services, self.project)
        self.queue = RunQueue(services.redis)

    def service(self, max_cases: int = 200) -> RunService:
        return RunService(
            self.project, self.scope.test_cases, self.scope.runs, self.queue, max_cases=max_cases
        )

    def case(
        self,
        *,
        screen: str = "SC-0001",
        priority: Priority = Priority.P1,
        severity: Severity = Severity.HIGH,
        status: TestCaseStatus = TestCaseStatus.APPROVED,
    ) -> TestCase:
        content = TestCaseContent(
            title="Một case",
            steps=[TestStep(action="Mở")],
            expected_result="ổn",
            severity=severity,
            priority=priority,
        )
        created = self.scope.test_cases.create(screen_id=screen, content=content, actor=LEAD)
        if status == TestCaseStatus.DRAFT:
            return created
        updated = created.model_copy(update={"status": status})
        return self.scope.test_cases.save(updated, expected_version=created.version, actor=LEAD)


@pytest.fixture
def setup(app: FastAPI, gateway: FakeSheetsGateway) -> Setup:
    return Setup(app, gateway)


def test_only_approved_cases_are_selected(setup: Setup) -> None:
    approved = setup.case()
    setup.case(status=TestCaseStatus.DRAFT)
    setup.case(status=TestCaseStatus.IN_REVIEW)
    setup.case(status=TestCaseStatus.DEPRECATED)

    selected = setup.service().select_cases(RunScope())

    assert [case.id for case in selected] == [approved.id]


def test_scope_filters_by_screen_priority_severity(setup: Setup) -> None:
    keep = setup.case(screen="SC-0001", priority=Priority.P1, severity=Severity.HIGH)
    setup.case(screen="SC-0002", priority=Priority.P1, severity=Severity.HIGH)
    setup.case(screen="SC-0001", priority=Priority.P3, severity=Severity.HIGH)
    setup.case(screen="SC-0001", priority=Priority.P1, severity=Severity.LOW)
    service = setup.service()

    scope = RunScope(
        screen_ids=["SC-0001"], priorities=[Priority.P1], severities=[Severity.HIGH]
    )

    assert [case.id for case in service.select_cases(scope)] == [keep.id]
    assert service.count(scope) == 1
    assert service.count(RunScope()) == 4


def test_empty_scope_result_raises_no_cases(setup: Setup) -> None:
    setup.case(status=TestCaseStatus.DRAFT)

    with pytest.raises(NoCasesError, match="Không có test case đã duyệt"):
        setup.service().start(LEAD, RunScope())


def test_too_many_cases_raises(setup: Setup) -> None:
    for _ in range(3):
        setup.case()

    with pytest.raises(TooManyCasesError, match="3 case.*2 case"):
        setup.service(max_cases=2).start(LEAD, RunScope())


def test_start_creates_queued_run_and_pushes_job_with_case_ids(setup: Setup) -> None:
    cases = [setup.case(), setup.case()]

    run = setup.service().start(LEAD, RunScope())

    assert run.status == RunStatus.QUEUED
    assert run.total == 2
    assert run.branch == setup.project.branch
    job = setup.queue.pop(timeout_seconds=1)
    assert job is not None
    assert (job.project_id, job.run_id) == (setup.project.id, run.id)
    assert job.case_ids == [case.id for case in cases]


def test_start_while_active_raises_in_progress_and_pushes_nothing(setup: Setup) -> None:
    setup.case()
    service = setup.service()
    service.start(LEAD, RunScope())
    assert setup.queue.pop(timeout_seconds=1) is not None

    with pytest.raises(RunInProgressError):
        service.start(LEAD, RunScope())

    assert setup.queue.pop(timeout_seconds=1) is None


def test_cancel_queued_run_is_cancelled_directly(setup: Setup) -> None:
    setup.case()
    service = setup.service()
    run = service.start(LEAD, RunScope())

    cancelled = service.cancel(run.id)

    assert cancelled.status == RunStatus.CANCELLED
    assert setup.queue.is_cancelled(setup.project.id, run.id) is False


def test_cancel_running_run_sets_flag(setup: Setup) -> None:
    setup.case()
    service = setup.service()
    run = service.start(LEAD, RunScope())
    setup.scope.runs.claim(run.id)

    result = service.cancel(run.id)

    assert result.status == RunStatus.RUNNING  # worker mới là bên chuyển sang CANCELLED
    assert setup.queue.is_cancelled(setup.project.id, run.id) is True


def test_cancel_finished_run_is_noop(setup: Setup) -> None:
    setup.case()
    service = setup.service()
    run = service.start(LEAD, RunScope())
    run.status = RunStatus.COMPLETED
    setup.scope.runs.save(run)

    result = service.cancel(run.id)

    assert result.status == RunStatus.COMPLETED
    assert setup.queue.is_cancelled(setup.project.id, run.id) is False


def test_cancel_unknown_run_raises(setup: Setup) -> None:
    with pytest.raises(RunNotFoundError):
        setup.service().cancel("RUN-9999")
