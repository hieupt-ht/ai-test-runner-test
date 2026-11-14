"""Nghiệp vụ chạy test: chọn case, tạo run, đẩy job cho worker, huỷ run."""

from app.core.models.project import Project
from app.core.models.run import Run, RunScope, RunStatus
from app.core.models.test_case import TestCase, TestCaseStatus
from app.core.repositories.runs import RunNotFoundError, RunRepository
from app.core.repositories.test_cases import TestCaseRepository
from app.core.run_queue import RunJob, RunQueue


class NoCasesError(Exception):
    pass


class TooManyCasesError(Exception):
    pass


class RunService:
    def __init__(
        self,
        project: Project,
        test_cases: TestCaseRepository,
        runs: RunRepository,
        queue: RunQueue,
        *,
        max_cases: int,
    ) -> None:
        self._project = project
        self._test_cases = test_cases
        self._runs = runs
        self._queue = queue
        self._max_cases = max_cases

    def select_cases(self, scope: RunScope) -> list[TestCase]:
        """Case `APPROVED` nằm trong phạm vi. Danh sách tiêu chí rỗng nghĩa là không lọc."""

        def matches(case: TestCase) -> bool:
            return (
                case.status == TestCaseStatus.APPROVED
                and (not scope.screen_ids or case.screen_id in scope.screen_ids)
                and (not scope.priorities or case.priority in scope.priorities)
                and (not scope.severities or case.severity in scope.severities)
            )

        return sorted((c for c in self._test_cases.list_all() if matches(c)), key=lambda c: c.id)

    def count(self, scope: RunScope) -> int:
        return len(self.select_cases(scope))

    def start(self, triggered_by: str, scope: RunScope) -> Run:
        cases = self.select_cases(scope)
        if not cases:
            raise NoCasesError("Không có test case đã duyệt trong phạm vi này")
        if len(cases) > self._max_cases:
            raise TooManyCasesError(
                f"Phạm vi có {len(cases)} case, vượt giới hạn {self._max_cases} case mỗi lần chạy"
            )
        # RunInProgressError (đang có run chưa xong) được truyền thẳng lên cho người gọi.
        run = self._runs.create(
            triggered_by=triggered_by,
            scope=scope,
            branch=self._project.branch,
            total=len(cases),
        )
        self._queue.push(
            RunJob(project_id=self._project.id, run_id=run.id, case_ids=[c.id for c in cases])
        )
        return run

    def cancel(self, run_id: str) -> Run:
        """Run chưa chạy thì huỷ ngay; đang chạy thì báo worker dừng sau case hiện tại."""
        run = self._runs.get(run_id)
        if run is None:
            raise RunNotFoundError(run_id)
        if run.status == RunStatus.QUEUED and self._runs.cancel_if_queued(run_id):
            return self._reload(run_id)
        # Hoặc đang chạy, hoặc vừa được worker nhận giữa chừng: báo worker dừng.
        current = self._reload(run_id)
        if current.status == RunStatus.RUNNING:
            self._queue.request_cancel(self._project.id, run_id)
        return current

    def _reload(self, run_id: str) -> Run:
        run = self._runs.get(run_id)
        if run is None:
            raise RunNotFoundError(run_id)
        return run
