from collections.abc import Callable
from datetime import UTC, datetime

import fakeredis
import pytest

from app.core.bootstrap import bootstrap_project_spreadsheet
from app.core.models.media import Media, MediaKind
from app.core.models.run import (
    Evidence,
    Result,
    ResultStatus,
    Run,
    RunScope,
    RunStatus,
    StepResult,
)
from app.core.models.test_case import Priority
from app.core.repositories.runs import (
    InvalidRunStateError,
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
            evidence=Evidence(legacy_url=f"{run_id}/{case_id}.png") if step else Evidence(),
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
    assert first_run[0].evidence.legacy_url == "RUN-0001/TC-000001.png"
    assert first_run[1].failed_step is None
    assert first_run[1].evidence == Evidence()
    assert [r.status for r in results.list_for_run("RUN-0002")] == [ResultStatus.BLOCKED]


def test_get_uses_a_single_sheet_read(repo: RunRepository, gateway: FakeSheetsGateway) -> None:
    """Giao diện hỏi chi tiết run mỗi vài giây; mỗi lượt đọc Google đều tính vào hạn mức."""
    run = new_run(repo)
    gateway.calls.clear()

    assert repo.get(run.id) is not None

    writes = ("append", "update", "delete", "add_tab")
    reads = [call for call in gateway.calls if not call.startswith(writes)]
    assert len(reads) == 1


def _results_repo(gateway: FakeSheetsGateway) -> ResultRepository:
    gateway.data.setdefault(SHEET, {})
    bootstrap_project_spreadsheet(gateway, SHEET)
    return ResultRepository(gateway, SHEET)


def _add_row_with_evidence(gateway: FakeSheetsGateway, evidence_json: str) -> None:
    """Thêm một dòng Results có sẵn `evidence_json` (giả lập dữ liệu do bản cũ ghi)."""
    header = gateway.data[SHEET]["Results"][0]
    row = [""] * len(header)
    for column, value in {
        "id": "RUN-0001-TC-000001",
        "run_id": "RUN-0001",
        "test_case_id": "TC-000001",
        "status": "FAIL",
        "evidence_json": evidence_json,
        "created_at": "2026-11-14T09:00:00Z",
    }.items():
        row[header.index(column)] = value
    gateway.data[SHEET]["Results"].append(row)


def test_legacy_evidence_still_reads(gateway: FakeSheetsGateway) -> None:
    results = _results_repo(gateway)
    _add_row_with_evidence(gateway, '{"screenshot": "https://x/a.png"}')

    assert results.list_all()[0].evidence == Evidence(legacy_url="https://x/a.png")


def test_empty_new_cells_default(gateway: FakeSheetsGateway) -> None:
    results = _results_repo(gateway)
    _add_row_with_evidence(gateway, "")

    result = results.list_all()[0]

    assert result.evidence == Evidence()
    assert result.step_results == [] and result.case_version is None
    assert (result.environment, result.executed_by, result.dev_owner) == ("", "", "")
    assert (result.actual_result, result.defect_url) == ("", "")


def test_round_trip_step_results_video_and_environment(gateway: FakeSheetsGateway) -> None:
    results = _results_repo(gateway)
    shot = Media(
        kind=MediaKind.IMAGE, url="https://res.cloudinary.com/c/image/upload/s.png", public_id="s"
    )
    video = Media(
        kind=MediaKind.VIDEO, url="https://res.cloudinary.com/c/video/upload/v.mp4", public_id="v"
    )
    saved = Result(
        id="RUN-0001-TC-000001",
        run_id="RUN-0001",
        test_case_id="TC-000001",
        status=ResultStatus.FAIL,
        reason="Không thấy nút",
        failed_step=2,
        evidence=Evidence(video=video, screenshots=[shot]),
        step_results=[
            StepResult(step_no=1, status="PASS"),
            StepResult(step_no=2, status="FAIL", actual="Màn hình trắng", screenshot=shot),
        ],
        actual_result="Màn hình trắng",
        environment="Pixel 7 / Android 14",
        executed_by="codex-windows",
        case_version=3,
        dev_owner="nguyenvana",
        defect_url="https://github.com/o/r/issues/9",
        created_at=datetime(2026, 11, 16, 9, 0, 0, tzinfo=UTC),
    )

    results.append_batch([saved])

    assert results.list_all() == [saved]


def test_run_new_fields_round_trip(repo: RunRepository) -> None:
    run = repo.create(
        triggered_by=LEAD,
        scope=RunScope(regression_only=True, case_ids=["TC-000001"]),
        branch="main",
        total=1,
    )
    repo.save(run.model_copy(update={"build_version": "1.4.2"}))

    saved = repo.get(run.id)

    assert saved is not None and saved.build_version == "1.4.2"
    assert saved.scope.regression_only is True and saved.scope.case_ids == ["TC-000001"]


# ---- Run regression: chạy nhiều lần gửi kết quả, cộng dồn vào cùng một run ----


def new_regression(repo: RunRepository, case_ids: list[str] | None = None) -> Run:
    return repo.create_regression(
        triggered_by=LEAD,
        branch="main",
        build_version="1.4.2",
        case_ids=case_ids or ["TC-1", "TC-2"],
    )


def make_result(run_id: str, case_id: str, status: ResultStatus = ResultStatus.PASS) -> Result:
    return Result(
        id=f"{run_id}-{case_id}",
        run_id=run_id,
        test_case_id=case_id,
        status=status,
        reason="",
        failed_step=None,
        created_at=datetime.now(UTC),
    )


def test_create_regression_is_running_with_case_list(repo: RunRepository) -> None:
    run = new_regression(repo)

    assert run.status == RunStatus.RUNNING
    assert run.scope.regression_only is True
    assert run.scope.case_ids == ["TC-1", "TC-2"]
    assert run.total == 2
    assert run.build_version == "1.4.2"


def test_regression_run_does_not_block_normal_run(repo: RunRepository) -> None:
    regression = new_regression(repo)

    normal = new_run(repo)

    assert normal.status == RunStatus.QUEUED
    assert repo.active() is not None
    assert repo.active().id == normal.id  # type: ignore[union-attr]
    assert regression.id != normal.id


def test_regression_can_start_while_normal_run_active(repo: RunRepository) -> None:
    new_run(repo)

    assert new_regression(repo).status == RunStatus.RUNNING


def test_active_ignores_regression_run(repo: RunRepository) -> None:
    new_regression(repo)

    assert repo.active() is None


def test_add_results_accumulates_and_completes_when_all_cases_done(
    repo: RunRepository, gateway: FakeSheetsGateway
) -> None:
    run = new_regression(repo)

    first = repo.add_results(run.id, [make_result(run.id, "TC-1")])
    assert first.status == RunStatus.RUNNING
    assert (first.passed, first.failed, first.finished_at) == (1, 0, None)

    second = repo.add_results(run.id, [make_result(run.id, "TC-2", ResultStatus.FAIL)])
    assert second.status == RunStatus.COMPLETED
    assert (second.passed, second.failed) == (1, 1)
    assert second.finished_at is not None
    assert len(ResultRepository(gateway, SHEET).list_for_run(run.id)) == 2


def test_add_results_same_case_twice_is_not_counted_twice(repo: RunRepository) -> None:
    run = new_regression(repo)

    repo.add_results(run.id, [make_result(run.id, "TC-1")])
    again = repo.add_results(run.id, [make_result(run.id, "TC-1")])

    assert (again.passed, again.failed, again.total) == (1, 0, 2)
    assert again.status == RunStatus.RUNNING


def test_add_results_on_normal_or_finished_run_is_rejected(repo: RunRepository) -> None:
    normal = new_run(repo)
    with pytest.raises(InvalidRunStateError):
        repo.add_results(normal.id, [make_result(normal.id, "TC-1")])

    run = new_regression(repo)
    repo.finish(run.id)
    with pytest.raises(InvalidRunStateError):
        repo.add_results(run.id, [make_result(run.id, "TC-1")])


def test_add_results_unknown_run_raises(repo: RunRepository) -> None:
    with pytest.raises(RunNotFoundError):
        repo.add_results("RUN-9999", [])


def test_finish_regression_run_completes_it(repo: RunRepository) -> None:
    run = new_regression(repo)

    finished = repo.finish(run.id)

    assert finished.status == RunStatus.COMPLETED
    assert finished.finished_at is not None
    with pytest.raises(InvalidRunStateError):
        repo.finish(run.id)


def test_finish_normal_run_is_rejected(repo: RunRepository) -> None:
    normal = new_run(repo)

    with pytest.raises(InvalidRunStateError):
        repo.finish(normal.id)
