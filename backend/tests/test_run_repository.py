from collections.abc import Callable
from datetime import UTC, datetime

import fakeredis
import pytest

from app.core.bootstrap import bootstrap_project_spreadsheet
from app.core.models.run import Result, ResultStatus, Run, RunScope, RunStatus
from app.core.models.test_case import Priority
from app.core.repositories.runs import (
    ResultRepository,
    RunInProgressError,
    RunNotFoundError,
    RunRepository,
)
from tests.fakes import FakeSheetsGateway

SHEET = "project-sheet"
LEAD = "lead@x.com"


@pytest.fixture
def repo_factory(
    gateway: FakeSheetsGateway, redis: fakeredis.FakeRedis
) -> Callable[[], RunRepository]:
    gateway.data.setdefault(SHEET, {})
    bootstrap_project_spreadsheet(gateway, SHEET)

    def build() -> RunRepository:
        return RunRepository(gateway, SHEET, redis, "PRJ-0001", lock_wait_seconds=0.1)

    return build


@pytest.fixture
def repo(repo_factory: Callable[[], RunRepository]) -> RunRepository:
    return repo_factory()


def new_run(repo: RunRepository, total: int = 3) -> Run:
    return repo.create(triggered_by=LEAD, scope=RunScope(), branch="main", total=total)


def test_create_run_is_queued_with_sequential_ids(repo: RunRepository) -> None:
    first = new_run(repo)
    first.status = RunStatus.COMPLETED
    repo.save(first)
    second = new_run(repo)

    assert (first.id, second.id) == ("RUN-0001", "RUN-0002")
    assert second.status == RunStatus.QUEUED
    assert second.finished_at is None
    assert second.total == 3


@pytest.mark.parametrize("active", [RunStatus.QUEUED, RunStatus.RUNNING])
def test_second_create_while_active_is_rejected(repo: RunRepository, active: RunStatus) -> None:
    first = new_run(repo)
    first.status = active
    repo.save(first)

    with pytest.raises(RunInProgressError):
        new_run(repo)


@pytest.mark.parametrize("done", [RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED])
def test_create_allowed_after_run_finished(repo: RunRepository, done: RunStatus) -> None:
    first = new_run(repo)
    first.status = done
    repo.save(first)

    assert new_run(repo).status == RunStatus.QUEUED


def test_two_creates_at_same_time_only_one_wins(
    gateway: FakeSheetsGateway, repo_factory: Callable[[], RunRepository]
) -> None:
    outcomes: list[str] = []

    def competing_request() -> None:
        try:
            new_run(repo_factory())
            outcomes.append("created")
        except Exception as error:  # khoá chặn lại (LockTimeout) hoặc thấy run đang chạy
            outcomes.append(type(error).__name__)

    gateway.after_next_read["Runs"] = competing_request

    new_run(repo_factory())

    assert len(repo_factory().list_all()) == 1
    assert outcomes
    assert outcomes[0] != "created"


def test_claim_only_from_queued(repo: RunRepository) -> None:
    run = new_run(repo)

    claimed = repo.claim(run.id)

    assert claimed is not None
    assert claimed.status == RunStatus.RUNNING
    assert repo.claim(run.id) is None


def test_cancel_if_queued_blocks_later_claim(repo: RunRepository) -> None:
    run = new_run(repo)

    assert repo.cancel_if_queued(run.id) is True

    cancelled = repo.get(run.id)
    assert cancelled is not None
    assert cancelled.status == RunStatus.CANCELLED
    assert cancelled.finished_at is not None
    assert repo.claim(run.id) is None
    assert repo.cancel_if_queued(run.id) is False


def test_cancel_if_queued_unknown_run_raises(repo: RunRepository) -> None:
    with pytest.raises(RunNotFoundError):
        repo.cancel_if_queued("RUN-9999")


def test_run_scope_round_trips(repo: RunRepository) -> None:
    scope = RunScope(screen_ids=["SC-0001"], priorities=[Priority.P1])
    created = repo.create(triggered_by=LEAD, scope=scope, branch="main", total=1)

    loaded = repo.get(created.id)

    assert loaded is not None
    assert loaded.scope == scope


def test_list_all_is_newest_first_and_active_finds_queued(repo: RunRepository) -> None:
    first = new_run(repo)
    first.status = RunStatus.COMPLETED
    repo.save(first)
    second = new_run(repo)

    assert [run.id for run in repo.list_all()] == [second.id, first.id]
    active = repo.active()
    assert active is not None
    assert active.id == second.id


def test_results_append_batch_and_list_for_run(gateway: FakeSheetsGateway) -> None:
    gateway.data.setdefault(SHEET, {})
    bootstrap_project_spreadsheet(gateway, SHEET)
    results = ResultRepository(gateway, SHEET)
    moment = datetime(2026, 11, 14, 9, 0, 0, tzinfo=UTC)

    def make(run_id: str, case_id: str, status: ResultStatus, step: int | None = None) -> Result:
        return Result(
            id=f"{run_id}-{case_id}",
            run_id=run_id,
            test_case_id=case_id,
            status=status,
            reason="Không thấy Đăng nhập",
            failed_step=step,
            screenshot=f"{run_id}/{case_id}.png" if step else None,
            created_at=moment,
        )

    results.append_batch([
        make("RUN-0001", "TC-000001", ResultStatus.FAIL, 2),
        make("RUN-0001", "TC-000002", ResultStatus.PASS),
        make("RUN-0002", "TC-000001", ResultStatus.BLOCKED),
    ])

    assert gateway.calls.count("append:Results") == 1
    first_run = results.list_for_run("RUN-0001")
    assert [r.test_case_id for r in first_run] == ["TC-000001", "TC-000002"]
    assert first_run[0].failed_step == 2
    assert first_run[0].screenshot == "RUN-0001/TC-000001.png"
    assert first_run[1].failed_step is None
    assert first_run[1].screenshot is None
    assert [r.status for r in results.list_for_run("RUN-0002")] == [ResultStatus.BLOCKED]
