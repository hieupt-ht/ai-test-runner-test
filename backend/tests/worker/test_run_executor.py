import json
import socket
import sys
import threading
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path

import pytest
from fastapi import FastAPI

from app.api.project_scope import ProjectScope, scope_for
from app.api.services import Services
from app.core.models.project import Project
from app.core.models.run import ResultStatus, Run, RunScope, RunStatus
from app.core.models.test_case import (
    AutoStep,
    AutoType,
    Priority,
    Severity,
    TestCase,
    TestCaseContent,
    TestCaseStatus,
    TestStep,
)
from app.core.run_queue import RunJob, RunQueue
from app.settings import Settings
from app.worker.app_process import AppStartError
from app.worker.case_runner import CaseOutcome, LoginError
from app.worker.config import ProjectWorkerConfig
from app.worker.run_executor import CaseSessionLike, RunExecutor, real_session_opener
from tests.conftest import make_project
from tests.fakes import FakeSheetsGateway

LEAD = "lead@x.com"
SITE_SCRIPT = Path(__file__).parent / "site.py"


def passed() -> CaseOutcome:
    return CaseOutcome(ResultStatus.PASS, "", None, None)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class FakeOpener:
    """Thay cho việc bật app + mở trình duyệt thật."""

    def __init__(self, artifacts_dir: Path) -> None:
        self.artifacts_dir = artifacts_dir
        self.outcomes: dict[str, CaseOutcome] = {}
        self.ran: list[str] = []
        self.opened = 0
        self.closed = 0
        self.open_error: Exception | None = None
        self.on_case: Callable[[TestCase], None] | None = None

    def __call__(
        self, project: Project, config: ProjectWorkerConfig, run_id: str
    ) -> AbstractContextManager[CaseSessionLike]:
        @contextmanager
        def session() -> Iterator[CaseSessionLike]:
            if self.open_error is not None:
                raise self.open_error
            self.opened += 1
            try:
                yield self
            finally:
                self.closed += 1

        return session()

    def run(self, case: TestCase) -> CaseOutcome:
        self.ran.append(case.id)
        if self.on_case is not None:
            self.on_case(case)
        return self.outcomes.get(case.id, passed())


class Env:
    def __init__(self, app: FastAPI, gateway: FakeSheetsGateway, tmp_path: Path) -> None:
        self.services: Services = app.state.services
        self.project = make_project(self.services.projects, self.services.members, gateway)
        self.scope: ProjectScope = scope_for(self.services, self.project)
        self.queue = RunQueue(self.services.redis)
        self.tmp_path = tmp_path
        self.config_path = tmp_path / "worker-projects.json"
        self.write_config({self.project.id: self.project_config()})
        self.settings = Settings(
            _env_file=None, worker_config_path=self.config_path, artifacts_dir=tmp_path / "art"
        )
        self.services.artifacts_dir = tmp_path / "art"
        self.opener = FakeOpener(tmp_path / "art")
        self.clock = FakeClock()

    def project_config(
        self, command: str = "x", url: str = "http://localhost:1"
    ) -> dict[str, object]:
        return {
            "app_path": str(self.tmp_path),
            "start_command": command,
            "app_url": url,
            "test_email": "qa@x.com",
            "test_password": "pw",
        }

    def write_config(self, data: dict[str, object]) -> None:
        self.config_path.write_text(json.dumps(data), encoding="utf-8")

    def executor(
        self, *, flush_every_cases: int = 10, flush_every_seconds: float = 30.0
    ) -> RunExecutor:
        return RunExecutor(
            self.services,
            self.settings,
            self.queue,
            self.opener,
            clock=self.clock,
            flush_every_cases=flush_every_cases,
            flush_every_seconds=flush_every_seconds,
        )

    def approved_cases(self, count: int, *, with_auto: bool = True) -> list[TestCase]:
        cases: list[TestCase] = []
        for number in range(count):
            auto = AutoStep(type=AutoType.GOTO, value="/form") if with_auto else None
            content = TestCaseContent(
                title=f"Case {number}",
                steps=[TestStep(action="Mở", expected="", auto=auto)],
                expected_result="ổn",
                severity=Severity.HIGH,
                priority=Priority.P1,
            )
            created = self.scope.test_cases.create(
                screen_id="SC-0001", content=content, actor=LEAD
            )
            approved = created.model_copy(update={"status": TestCaseStatus.APPROVED})
            cases.append(
                self.scope.test_cases.save(approved, expected_version=created.version, actor=LEAD)
            )
        return cases

    def enqueue(self, cases: list[TestCase]) -> RunJob:
        run = self.scope.runs.create(
            triggered_by=LEAD, scope=RunScope(), branch="main", total=len(cases)
        )
        job = RunJob(
            project_id=self.project.id, run_id=run.id, case_ids=[case.id for case in cases]
        )
        self.queue.push(job)
        return job

    def run_of(self, job: RunJob) -> Run:
        run = self.scope.runs.get(job.run_id)
        assert run is not None
        return run


@pytest.fixture
def env(app: FastAPI, gateway: FakeSheetsGateway, tmp_path: Path) -> Env:
    return Env(app, gateway, tmp_path)


def test_execute_marks_completed_and_counts_results(env: Env) -> None:
    cases = env.approved_cases(3)
    env.opener.outcomes[cases[1].id] = CaseOutcome(
        ResultStatus.FAIL,
        "Không thấy chữ",
        1,
        env.tmp_path / "art" / env.project.id / "RUN-0001" / "x.png",
    )
    job = env.enqueue(cases)

    env.executor().execute(job)

    run = env.run_of(job)
    assert run.status == RunStatus.COMPLETED
    assert (run.total, run.passed, run.failed) == (3, 2, 1)
    assert run.finished_at is not None
    results = env.scope.results.list_for_run(job.run_id)
    assert [r.test_case_id for r in results] == [case.id for case in cases]
    assert results[1].failed_step == 1
    assert results[1].screenshot == "RUN-0001/x.png"
    assert results[0].id == f"{job.run_id}-{cases[0].id}"
    assert (env.opener.opened, env.opener.closed) == (1, 1)


def test_results_are_written_in_batches(env: Env, gateway: FakeSheetsGateway) -> None:
    job = env.enqueue(env.approved_cases(25))

    env.executor(flush_every_cases=10).execute(job)

    assert gateway.calls.count("append:Results") == 3
    assert len(env.scope.results.list_for_run(job.run_id)) == 25


def test_time_based_flush(env: Env) -> None:
    job = env.enqueue(env.approved_cases(3))
    seen_during_third: list[int] = []

    def on_case(case: TestCase) -> None:
        if len(env.opener.ran) == 3:
            seen_during_third.append(len(env.scope.results.list_for_run(job.run_id)))
        env.clock.now += 20  # mỗi case "mất" 20 giây

    env.opener.on_case = on_case

    env.executor(flush_every_cases=10, flush_every_seconds=30).execute(job)

    assert seen_during_third == [2]  # hai case đầu đã được ghi trước khi case 3 chạy


def test_blocked_result_is_recorded_and_run_still_completes(env: Env) -> None:
    cases = env.approved_cases(2, with_auto=False)
    for case in cases:
        env.opener.outcomes[case.id] = CaseOutcome(
            ResultStatus.BLOCKED, "Chưa có bước tự động", None, None
        )
    job = env.enqueue(cases)

    env.executor().execute(job)

    run = env.run_of(job)
    assert run.status == RunStatus.COMPLETED
    assert (run.passed, run.failed) == (0, 0)
    results = env.scope.results.list_for_run(job.run_id)
    assert {r.status for r in results} == {ResultStatus.BLOCKED}
    assert results[0].reason == "Chưa có bước tự động"


def test_cancel_between_cases_stops_and_keeps_written_results(env: Env) -> None:
    cases = env.approved_cases(5)
    job = env.enqueue(cases)

    def on_case(case: TestCase) -> None:
        if len(env.opener.ran) == 3:
            env.queue.request_cancel(env.project.id, job.run_id)

    env.opener.on_case = on_case

    env.executor().execute(job)

    run = env.run_of(job)
    assert run.status == RunStatus.CANCELLED
    assert run.finished_at is not None
    assert len(env.scope.results.list_for_run(job.run_id)) == 3
    assert env.opener.ran == [case.id for case in cases[:3]]
    assert env.opener.closed == 1


def test_cancelled_queued_run_is_skipped(env: Env) -> None:
    job = env.enqueue(env.approved_cases(2))
    env.scope.runs.cancel_if_queued(job.run_id)

    env.executor().execute(job)

    assert env.run_of(job).status == RunStatus.CANCELLED
    assert env.opener.opened == 0
    assert env.scope.results.list_for_run(job.run_id) == []


@pytest.mark.parametrize(
    "error",
    [AppStartError("App chưa sẵn sàng tại http://x"), LoginError("Đăng nhập thất bại ở bước 2")],
)
def test_app_or_login_error_fails_run_with_note_and_no_results(
    env: Env, error: Exception
) -> None:
    job = env.enqueue(env.approved_cases(2))
    env.opener.open_error = error

    env.executor().execute(job)

    run = env.run_of(job)
    assert run.status == RunStatus.FAILED
    assert run.finished_at is not None
    assert env.queue.get_note(env.project.id, job.run_id) == str(error)
    assert env.scope.results.list_for_run(job.run_id) == []


def test_missing_project_config_fails_run_with_note(env: Env) -> None:
    env.write_config({})
    job = env.enqueue(env.approved_cases(1))

    env.executor().execute(job)

    assert env.run_of(job).status == RunStatus.FAILED
    assert env.project.id in env.queue.get_note(env.project.id, job.run_id)
    assert env.opener.opened == 0


def test_unexpected_case_exception_becomes_inconclusive_and_continues(env: Env) -> None:
    cases = env.approved_cases(3)
    job = env.enqueue(cases)

    def on_case(case: TestCase) -> None:
        if case.id == cases[1].id:
            raise RuntimeError("trình duyệt sập")

    env.opener.on_case = on_case

    env.executor().execute(job)

    results = env.scope.results.list_for_run(job.run_id)
    assert [r.status for r in results] == [
        ResultStatus.PASS,
        ResultStatus.INCONCLUSIVE,
        ResultStatus.PASS,
    ]
    assert "RuntimeError" in results[1].reason
    assert env.run_of(job).status == RunStatus.COMPLETED


def test_case_no_longer_approved_is_skipped(env: Env) -> None:
    cases = env.approved_cases(2)
    job = env.enqueue(cases)
    edited = cases[0].model_copy(update={"status": TestCaseStatus.DRAFT})
    env.scope.test_cases.save(edited, expected_version=cases[0].version, actor=LEAD)

    env.executor().execute(job)

    assert env.opener.ran == [cases[1].id]
    run = env.run_of(job)
    assert run.total == 1
    assert [r.test_case_id for r in env.scope.results.list_for_run(job.run_id)] == [cases[1].id]


def test_unexpected_executor_error_fails_run_and_closes_session(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.repositories.runs import ResultRepository

    def broken(self: ResultRepository, results: list[object]) -> None:
        raise RuntimeError("Google hỏng")

    monkeypatch.setattr(ResultRepository, "append_batch", broken)
    job = env.enqueue(env.approved_cases(2))

    env.executor().execute(job)

    assert env.run_of(job).status == RunStatus.FAILED
    assert "RuntimeError" in env.queue.get_note(env.project.id, job.run_id)
    assert "Google hỏng" not in env.queue.get_note(env.project.id, job.run_id)
    assert env.opener.closed == 1


def test_recover_marks_running_runs_failed_and_keeps_queued(env: Env) -> None:
    running = env.enqueue(env.approved_cases(1))
    env.scope.runs.claim(running.run_id)

    fixed = env.executor().recover_interrupted_runs()

    assert fixed == 1
    run = env.run_of(running)
    assert run.status == RunStatus.FAILED
    assert run.finished_at is not None
    assert env.queue.get_note(env.project.id, running.run_id) == "Worker bị dừng giữa chừng"
    # Run đã xong thì dự án được chạy lại, và run QUEUED không bị đụng tới.
    queued = env.enqueue(env.approved_cases(1))
    assert env.executor().recover_interrupted_runs() == 0
    assert env.run_of(queued).status == RunStatus.QUEUED


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_real_opener_runs_cases_end_to_end(env: Env) -> None:
    """Bật "app" thật (trang giả), đăng nhập, chạy hai case bằng Chromium thật."""
    port = free_port()
    config = env.project_config(
        command=f'"{sys.executable}" "{SITE_SCRIPT}" {port}', url=f"http://127.0.0.1:{port}"
    )
    config["login_steps"] = [
        {"type": "goto", "value": "/login"},
        {"type": "fill", "target": {"by": "label", "value": "Email"}, "value": "{email}"},
        {"type": "click", "target": {"by": "text", "value": "Đăng nhập"}},
    ]
    env.write_config({env.project.id: config})
    good, bad = env.approved_cases(2)

    def with_steps(case: TestCase, *steps: AutoStep) -> TestCase:
        updated = case.model_copy(
            update={"steps": [TestStep(action=f"b{i}", auto=s) for i, s in enumerate(steps)]}
        )
        return env.scope.test_cases.save(updated, expected_version=case.version, actor=LEAD)

    see = AutoStep(type=AutoType.SEE_TEXT, value="Xin chào")
    home = AutoStep(type=AutoType.GOTO, value="/home")
    wrong = AutoStep(type=AutoType.SEE_TEXT, value="Chữ không tồn tại")
    with_steps(good, home, see)
    with_steps(bad, home, wrong)
    job = env.enqueue([good, bad])
    env.settings.step_timeout_ms = 1500
    env.settings.app_start_timeout_seconds = 30
    executor = RunExecutor(
        env.services, env.settings, env.queue, real_session_opener(env.settings)
    )

    # Fixture `browser` của session đang giữ một phiên Playwright trong luồng chính, mà Playwright
    # không cho hai phiên đồng bộ cùng một luồng, nên chạy executor ở luồng riêng (như worker thật).
    worker = threading.Thread(target=executor.execute, args=(job,))
    worker.start()
    worker.join(timeout=120)
    assert not worker.is_alive()

    run = env.run_of(job)
    assert run.status == RunStatus.COMPLETED, env.queue.get_note(env.project.id, job.run_id)
    results = {r.test_case_id: r for r in env.scope.results.list_for_run(job.run_id)}
    assert results[good.id].status == ResultStatus.PASS
    assert results[bad.id].status == ResultStatus.FAIL
    assert results[bad.id].failed_step == 2
    assert results[bad.id].screenshot == f"{job.run_id}/{bad.id}.png"
    assert (env.tmp_path / "art" / env.project.id / job.run_id / f"{bad.id}.png").is_file()
