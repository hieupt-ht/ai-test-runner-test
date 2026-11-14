"""Chạy cả một run: bật app, đăng nhập, chạy từng case, ghi kết quả theo lô.

Quy tắc chính:
- Chỉ nhận run còn `QUEUED` (đã huỷ hoặc đã có người nhận thì bỏ qua).
- Chỉ chạy case còn `APPROVED` tại thời điểm chạy (case bị sửa/xoá giữa chừng thì bỏ).
- Lỗi của app/đăng nhập/cấu hình → cả run `FAILED` kèm lý do, không ghi FAIL cho từng case.
- Huỷ: kiểm tra cờ giữa các case; kết quả đã chạy vẫn được ghi, run thành `CANCELLED`.
- Log chỉ ghi `run_id`, không ghi nội dung test case hay mật khẩu.
"""

import logging
import time
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import datetime
from typing import Protocol

from playwright.sync_api import sync_playwright

from app.api.project_scope import ProjectScope, scope_for
from app.api.services import Services
from app.core.models.project import Project
from app.core.models.run import Result, ResultStatus, Run, RunStatus
from app.core.models.test_case import TestCase, TestCaseStatus
from app.core.repositories.runs import RunNotFoundError
from app.core.run_queue import RunJob, RunQueue
from app.core.time import utc_now
from app.settings import Settings
from app.worker.app_process import AppStartError, running_app
from app.worker.case_runner import CaseOutcome, CaseSession, LoginError, perform_login
from app.worker.config import ProjectWorkerConfig, WorkerConfigError, load_project_config

logger = logging.getLogger(__name__)

MAX_ERROR_TEXT = 200
INTERRUPTED_NOTE = "Worker bị dừng giữa chừng"


class CaseSessionLike(Protocol):
    def run(self, case: TestCase) -> CaseOutcome: ...


# (project, cấu hình app, run_id) → khối `with` bật app, đăng nhập, rồi đưa ra một CaseSession.
# Thoát khối thì dọn hết (tắt trình duyệt, tắt app).
SessionOpener = Callable[
    [Project, ProjectWorkerConfig, str], AbstractContextManager[CaseSessionLike]
]


def real_session_opener(settings: Settings) -> SessionOpener:
    def open_session(
        project: Project, config: ProjectWorkerConfig, run_id: str
    ) -> AbstractContextManager[CaseSessionLike]:
        @contextmanager
        def session() -> Iterator[CaseSessionLike]:
            with (
                running_app(config, timeout_seconds=settings.app_start_timeout_seconds),
                sync_playwright() as playwright,
            ):
                browser = playwright.chromium.launch(headless=True)
                try:
                    state = perform_login(
                        browser, config, step_timeout_ms=settings.step_timeout_ms
                    )
                    yield CaseSession(
                        browser,
                        state,
                        config.app_url,
                        settings.artifacts_dir / project.id,
                        run_id,
                        step_timeout_ms=settings.step_timeout_ms,
                        case_timeout_seconds=settings.case_timeout_seconds,
                    )
                finally:
                    browser.close()

        return session()

    return open_session


def _now() -> datetime:
    return utc_now().replace(microsecond=0)


class RunExecutor:
    def __init__(
        self,
        services: Services,
        settings: Settings,
        queue: RunQueue,
        open_session: SessionOpener,
        *,
        clock: Callable[[], float] = time.monotonic,
        flush_every_cases: int = 10,
        flush_every_seconds: float = 30.0,
    ) -> None:
        self._services = services
        self._settings = settings
        self._queue = queue
        self._open_session = open_session
        self._clock = clock
        self._flush_every_cases = flush_every_cases
        self._flush_every_seconds = flush_every_seconds

    # ---------- một job ----------

    def execute(self, job: RunJob) -> None:
        project = self._services.projects.get(job.project_id)
        if project is None:
            logger.warning("Bỏ qua run %s: không còn dự án %s", job.run_id, job.project_id)
            return
        scope = scope_for(self._services, project)
        try:
            run = scope.runs.claim(job.run_id)
        except RunNotFoundError:
            logger.warning("Bỏ qua run %s: không thấy trong Sheet", job.run_id)
            return
        if run is None:
            logger.info("Bỏ qua run %s: không còn ở trạng thái QUEUED", job.run_id)
            return

        try:
            self._run(project, scope, run, job)
        except Exception as error:
            logger.exception("Run %s gặp lỗi không mong đợi", run.id)
            self._fail(scope, run, f"Lỗi không mong đợi: {type(error).__name__}")

    def _run(self, project: Project, scope: ProjectScope, run: Run, job: RunJob) -> None:
        cases = self._approved_cases(scope, job)
        run.total = len(cases)
        scope.runs.save(run)

        try:
            config = load_project_config(self._settings.worker_config_path, project.id)
            with self._open_session(project, config, run.id) as session:
                cancelled = self._run_cases(scope, run, cases, session)
        except (WorkerConfigError, AppStartError, LoginError) as error:
            self._fail(scope, run, str(error))
            return

        run.status = RunStatus.CANCELLED if cancelled else RunStatus.COMPLETED
        run.finished_at = _now()
        scope.runs.save(run)

    def _approved_cases(self, scope: ProjectScope, job: RunJob) -> list[TestCase]:
        by_id = {case.id: case for case in scope.test_cases.list_all()}
        found = (by_id.get(case_id) for case_id in job.case_ids)
        return [case for case in found if case and case.status == TestCaseStatus.APPROVED]

    def _run_cases(
        self, scope: ProjectScope, run: Run, cases: list[TestCase], session: CaseSessionLike
    ) -> bool:
        """Chạy lần lượt các case. Trả True nếu bị huỷ giữa chừng."""
        pending: list[Result] = []
        last_flush = self._clock()

        def flush() -> None:
            nonlocal last_flush
            if pending:
                scope.results.append_batch(list(pending))
                pending.clear()
            scope.runs.save(run)
            last_flush = self._clock()

        try:
            for case in cases:
                if self._queue.is_cancelled(scope.project.id, run.id):
                    return True
                outcome = self._run_case(session, case)
                pending.append(self._to_result(scope.project.id, run.id, case, outcome))
                run.passed += outcome.status == ResultStatus.PASS
                run.failed += outcome.status == ResultStatus.FAIL
                too_many = len(pending) >= self._flush_every_cases
                too_long = self._clock() - last_flush >= self._flush_every_seconds
                if too_many or too_long:
                    flush()
            return self._queue.is_cancelled(scope.project.id, run.id)
        finally:
            flush()

    def _run_case(self, session: CaseSessionLike, case: TestCase) -> CaseOutcome:
        try:
            return session.run(case)
        except Exception as error:  # lỗi bất ngờ của một case không được làm chết cả run
            text = f"{type(error).__name__}: {error}"[:MAX_ERROR_TEXT]
            return CaseOutcome(ResultStatus.INCONCLUSIVE, f"Lỗi của worker: {text}", None, None)

    def _to_result(
        self, project_id: str, run_id: str, case: TestCase, outcome: CaseOutcome
    ) -> Result:
        screenshot: str | None = None
        if outcome.screenshot is not None:
            try:
                screenshot = outcome.screenshot.relative_to(
                    self._settings.artifacts_dir / project_id
                ).as_posix()
            except ValueError:
                screenshot = f"{run_id}/{case.id}.png"
        return Result(
            id=f"{run_id}-{case.id}",
            run_id=run_id,
            test_case_id=case.id,
            status=outcome.status,
            reason=outcome.reason,
            failed_step=outcome.failed_step,
            screenshot=screenshot,
            created_at=_now(),
        )

    def _fail(self, scope: ProjectScope, run: Run, note: str) -> None:
        run.status = RunStatus.FAILED
        run.finished_at = _now()
        scope.runs.save(run)
        self._queue.set_note(scope.project.id, run.id, note)

    # ---------- khởi động lại ----------

    def recover_interrupted_runs(self) -> int:
        """Run đang `RUNNING` mà worker đã chết thì kẹt mãi và khoá cả dự án: đánh dấu FAILED."""
        fixed = 0
        for project in self._services.projects.list_all():
            if project.archived:
                continue
            try:
                scope = scope_for(self._services, project)
                for run in scope.runs.list_all():
                    if run.status == RunStatus.RUNNING:
                        self._fail(scope, run, INTERRUPTED_NOTE)
                        fixed += 1
            except Exception:
                logger.exception("Không kiểm tra được run dở của dự án %s", project.id)
        return fixed
