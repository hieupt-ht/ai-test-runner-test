"""Đọc/ghi tab `Runs` và `Results` trong Sheet riêng của một dự án.

- Mỗi dự án chỉ có một run đang chạy: `create` kiểm tra lại NGAY TRONG KHOÁ tab.
- Chuyển QUEUED → RUNNING (`claim`) và QUEUED → CANCELLED (`cancel_if_queued`) cùng dùng khoá
  của run, nên worker nhận job và người dùng bấm huỷ không thể cùng thắng.
- Kết quả chỉ được thêm vào (ghi theo lô), không bao giờ sửa trong M4.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from redis import Redis

from app.core.ids import IdGenerator
from app.core.locks.redis_lock import redis_lock
from app.core.models.run import (
    ACTIVE_RUN_STATUSES,
    Evidence,
    Result,
    ResultStatus,
    Run,
    RunScope,
    RunStatus,
    StepResult,
)
from app.core.sheets.gateway import SheetsGateway
from app.core.sheets.schema import RESULT_COLUMNS, RESULTS_TAB, RUN_COLUMNS, RUNS_TAB
from app.core.sheets.table import Record, SheetTable
from app.core.time import from_iso, to_iso, utc_now


class RunInProgressError(Exception):
    """Dự án đang có một run `QUEUED` hoặc `RUNNING`."""


class RunNotFoundError(Exception):
    pass


def _now() -> datetime:
    """Giờ hiện tại cắt phần lẻ giây, đúng như những gì Sheet lưu."""
    return utc_now().replace(microsecond=0)


def _run_to_record(run: Run) -> Record:
    return {
        "id": run.id,
        "triggered_by": run.triggered_by,
        "scope": run.scope.model_dump_json(),
        "branch": run.branch,
        "commit_sha": run.commit_sha,
        "status": run.status.value,
        "started_at": to_iso(run.started_at),
        "finished_at": "" if run.finished_at is None else to_iso(run.finished_at),
        "total": str(run.total),
        "passed": str(run.passed),
        "failed": str(run.failed),
        "tokens_used": str(run.tokens_used),
        "build_version": run.build_version,
    }


def _run_from_record(record: Record) -> Run:
    return Run(
        id=record["id"],
        triggered_by=record["triggered_by"],
        scope=RunScope.model_validate_json(record["scope"] or "{}"),
        branch=record["branch"],
        commit_sha=record["commit_sha"],
        status=RunStatus(record["status"]),
        started_at=from_iso(record["started_at"]),
        finished_at=from_iso(record["finished_at"]) if record["finished_at"] else None,
        total=int(record["total"] or 0),
        passed=int(record["passed"] or 0),
        failed=int(record["failed"] or 0),
        tokens_used=int(record["tokens_used"] or 0),
        build_version=record["build_version"],
    )


class RunRepository:
    def __init__(
        self,
        gateway: SheetsGateway,
        spreadsheet_id: str,
        redis: Redis,
        project_id: str,
        *,
        lock_wait_seconds: float = 5.0,
    ) -> None:
        self._table = SheetTable(gateway, spreadsheet_id, RUNS_TAB, RUN_COLUMNS)
        self._ids = IdGenerator(
            gateway, spreadsheet_id, redis, project_id, lock_wait_seconds=lock_wait_seconds
        )
        self._redis = redis
        self._project_id = project_id
        self._lock_wait_seconds = lock_wait_seconds

    def list_all(self) -> list[Run]:
        """Mọi run, mới nhất trước."""
        runs = [_run_from_record(record) for record in self._table.read_all()]
        return sorted(runs, key=lambda run: run.id, reverse=True)

    def get(self, run_id: str) -> Run | None:
        # Tab Runs nhỏ, nên đọc cả tab một lượt (1 lần gọi Google) rẻ hơn tìm theo cột rồi đọc dòng
        # (3 lần gọi). Giao diện hỏi chi tiết run mỗi vài giây, mỗi lượt đọc đều tính vào hạn mức.
        return next((run for run in self.list_all() if run.id == run_id), None)

    def active(self) -> Run | None:
        return next((run for run in self.list_all() if run.status in ACTIVE_RUN_STATUSES), None)

    def create(self, *, triggered_by: str, scope: RunScope, branch: str, total: int) -> Run:
        with self._tab_lock():
            if any(run.status in ACTIVE_RUN_STATUSES for run in self.list_all()):
                raise RunInProgressError("Dự án đang có một lần chạy chưa xong")
            run = Run(
                id=self._ids.next_id("run", "RUN", digits=4),
                triggered_by=triggered_by,
                scope=scope,
                branch=branch,
                commit_sha="",
                status=RunStatus.QUEUED,
                started_at=_now(),
                finished_at=None,
                total=total,
                passed=0,
                failed=0,
                tokens_used=0,
            )
            self._table.append(_run_to_record(run))
        return run

    def save(self, run: Run) -> Run:
        with self._run_lock(run.id):
            row_number = self._table.find_row_number("id", run.id)
            if row_number is None:
                raise RunNotFoundError(run.id)
            self._table.update(row_number, _run_to_record(run))
        return run

    def claim(self, run_id: str) -> Run | None:
        """QUEUED → RUNNING. Trả None nếu run không còn ở QUEUED (đã huỷ hoặc đã có người nhận)."""
        with self._run_lock(run_id):
            found = self._table.find_record("id", run_id)
            if found is None:
                raise RunNotFoundError(run_id)
            run = _run_from_record(found.record)
            if run.status != RunStatus.QUEUED:
                return None
            run.status = RunStatus.RUNNING
            self._table.update_found(found, _run_to_record(run))
            return run

    def cancel_if_queued(self, run_id: str) -> bool:
        """QUEUED → CANCELLED. Trả False nếu run không còn ở QUEUED."""
        with self._run_lock(run_id):
            found = self._table.find_record("id", run_id)
            if found is None:
                raise RunNotFoundError(run_id)
            run = _run_from_record(found.record)
            if run.status != RunStatus.QUEUED:
                return False
            run.status = RunStatus.CANCELLED
            run.finished_at = _now()
            self._table.update_found(found, _run_to_record(run))
            return True

    @contextmanager
    def _tab_lock(self) -> Iterator[None]:
        with redis_lock(
            self._redis, f"lock:{self._project_id}:runs", wait_seconds=self._lock_wait_seconds
        ):
            yield

    @contextmanager
    def _run_lock(self, run_id: str) -> Iterator[None]:
        with redis_lock(
            self._redis,
            f"lock:{self._project_id}:run:{run_id}",
            wait_seconds=self._lock_wait_seconds,
        ):
            yield


def _result_to_record(result: Result) -> Record:
    # Bằng chứng mặc định (không có gì) thì để ô trống cho gọn
    evidence = result.evidence.model_dump_json(exclude_defaults=True)
    return {
        "id": result.id,
        "run_id": result.run_id,
        "test_case_id": result.test_case_id,
        "status": result.status.value,
        "reason": result.reason,
        "failed_step": "" if result.failed_step is None else str(result.failed_step),
        "evidence_json": "" if evidence == "{}" else evidence,
        "tokens_used": "0",
        "issue_url": "",
        "reviewed_by": "",
        "review_note": "",
        "created_at": to_iso(result.created_at),
        "step_results_json": json.dumps(
            [step.model_dump(mode="json") for step in result.step_results], ensure_ascii=False
        )
        if result.step_results
        else "",
        "actual_result": result.actual_result,
        "environment": result.environment,
        "executed_by": result.executed_by,
        "case_version": "" if result.case_version is None else str(result.case_version),
        "dev_owner": result.dev_owner,
        "defect_url": result.defect_url,
    }


def _evidence_from_json(text: str) -> Evidence:
    """Đọc `evidence_json`; bản cũ lưu {"screenshot": "<link>"} thì đổi thành `legacy_url`."""
    if not text:
        return Evidence()
    data = json.loads(text)
    if "screenshot" in data:
        legacy = data.pop("screenshot")
        data.setdefault("legacy_url", legacy)
    return Evidence.model_validate(data)


def _result_from_record(record: Record) -> Result:
    return Result(
        id=record["id"],
        run_id=record["run_id"],
        test_case_id=record["test_case_id"],
        status=ResultStatus(record["status"]),
        reason=record["reason"],
        failed_step=int(record["failed_step"]) if record["failed_step"] else None,
        created_at=from_iso(record["created_at"]),
        evidence=_evidence_from_json(record["evidence_json"]),
        step_results=[
            StepResult.model_validate(item)
            for item in json.loads(record["step_results_json"] or "[]")
        ],
        actual_result=record["actual_result"],
        environment=record["environment"],
        executed_by=record["executed_by"],
        case_version=int(record["case_version"]) if record["case_version"] else None,
        dev_owner=record["dev_owner"],
        defect_url=record["defect_url"],
    )


class ResultRepository:
    def __init__(self, gateway: SheetsGateway, spreadsheet_id: str) -> None:
        self._table = SheetTable(gateway, spreadsheet_id, RESULTS_TAB, RESULT_COLUMNS)

    def append_batch(self, results: list[Result]) -> None:
        """Ghi nhiều kết quả bằng đúng một lời gọi Google."""
        self._table.append_many([_result_to_record(result) for result in results])

    def list_all(self) -> list[Result]:
        """Đọc toàn bộ Results một lượt để tổng hợp nhiều run mà không đọc lặp Sheet."""
        return [_result_from_record(record) for record in self._table.read_all()]

    def list_for_run(self, run_id: str) -> list[Result]:
        return [result for result in self.list_all() if result.run_id == run_id]
