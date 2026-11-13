"""Đọc/ghi tab `TestCases` trong Sheet riêng của một dự án.

Không cache test case: nhiều người cùng sửa, đọc thẳng từ Sheet cho chắc (spec 9.7).
Chống ghi đè nhau bằng số `version`: người lưu phải nói mình đang dựa trên version nào.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from redis import Redis

from app.core.ids import IdGenerator
from app.core.locks.redis_lock import redis_lock
from app.core.models.test_case import (
    Priority,
    Severity,
    TestCase,
    TestCaseContent,
    TestCaseStatus,
    TestStep,
)
from app.core.sheets.gateway import SheetsGateway
from app.core.sheets.schema import TEST_CASE_COLUMNS, TEST_CASES_TAB
from app.core.sheets.table import Record, SheetTable
from app.core.time import from_iso, to_iso, utc_now


class TestCaseNotFoundError(Exception):
    pass


class VersionConflictError(Exception):
    """Có người đã sửa case từ lúc mình đọc. `latest` là bản đang có trên Sheet."""

    def __init__(self, latest: TestCase) -> None:
        super().__init__(f"Xung đột version ở {latest.id}")
        self.latest = latest


def _now_like_sheet() -> datetime:
    """Giờ hiện tại cắt bỏ phần lẻ giây, đúng như những gì Sheet lưu (để đọc lại không lệch)."""
    return utc_now().replace(microsecond=0)


def _to_record(case: TestCase) -> Record:
    steps = [{"action": step.action, "expected": step.expected} for step in case.steps]
    return {
        "id": case.id,
        "screen_id": case.screen_id,
        "title": case.title,
        "precondition": case.precondition,
        "test_data": case.test_data,
        "steps": json.dumps(steps, ensure_ascii=False),  # giữ nguyên tiếng Việt
        "expected_result": case.expected_result,
        "severity": case.severity.value,
        "priority": case.priority.value,
        "status": case.status.value,
        "created_by": case.created_by,
        "updated_by": case.updated_by,
        "created_at": to_iso(case.created_at),
        "updated_at": to_iso(case.updated_at),
        "version": str(case.version),
    }


def _from_record(record: Record) -> TestCase:
    return TestCase(
        id=record["id"],
        screen_id=record["screen_id"],
        title=record["title"],
        precondition=record["precondition"],
        test_data=record["test_data"],
        steps=[TestStep(**step) for step in json.loads(record["steps"])],
        expected_result=record["expected_result"],
        severity=Severity(record["severity"]),
        priority=Priority(record["priority"]),
        status=TestCaseStatus(record["status"]),
        created_by=record["created_by"],
        updated_by=record["updated_by"],
        created_at=from_iso(record["created_at"]),
        updated_at=from_iso(record["updated_at"]),
        version=int(record["version"]),
    )


class TestCaseRepository:
    def __init__(
        self,
        gateway: SheetsGateway,
        spreadsheet_id: str,
        redis: Redis,
        project_id: str,
        *,
        lock_wait_seconds: float = 5.0,
    ) -> None:
        self._table = SheetTable(gateway, spreadsheet_id, TEST_CASES_TAB, TEST_CASE_COLUMNS)
        self._ids = IdGenerator(
            gateway, spreadsheet_id, redis, project_id, lock_wait_seconds=lock_wait_seconds
        )
        self._redis = redis
        self._project_id = project_id
        self._lock_key = f"lock:{project_id}:test-cases"
        self._lock_wait_seconds = lock_wait_seconds
        self._holding_lock = False

    def list_all(self) -> list[TestCase]:
        cases = [_from_record(record) for record in self._table.read_all()]
        return sorted(cases, key=lambda case: case.id)

    def get(self, case_id: str) -> TestCase | None:
        return next((case for case in self.list_all() if case.id == case_id), None)

    def create(self, *, screen_id: str, content: TestCaseContent, actor: str) -> TestCase:
        now = _now_like_sheet()
        case = TestCase(
            **content.model_dump(),
            id=self._ids.next_id("tc", "TC", digits=6),
            screen_id=screen_id,
            status=TestCaseStatus.DRAFT,
            created_by=actor,
            updated_by=actor,
            created_at=now,
            updated_at=now,
            version=1,
        )
        with self.lock():
            self._table.append(_to_record(case))
        return case

    def save(self, case: TestCase, *, expected_version: int, actor: str) -> TestCase:
        """Ghi `case` nếu version trên Sheet còn đúng `expected_version`.

        Khoá theo từng bản ghi (tab TestCases không bao giờ xoá dòng nên dòng không dịch chỗ).
        Version trên Sheet khác -> có người sửa trước, báo VersionConflictError kèm bản mới nhất.
        """
        record_lock_key = f"lock:{self._project_id}:test-case:{case.id}"
        with redis_lock(self._redis, record_lock_key, wait_seconds=self._lock_wait_seconds):
            row_number = self._table.find_row_number("id", case.id)
            if row_number is None:
                raise TestCaseNotFoundError(case.id)
            current = _from_record(self._table.read_row(row_number))
            if current.version != expected_version:
                raise VersionConflictError(current)
            saved = case.model_copy(
                update={
                    "version": expected_version + 1,
                    "updated_by": actor,
                    "updated_at": _now_like_sheet(),
                }
            )
            self._table.update(row_number, _to_record(saved))
        return saved

    @contextmanager
    def lock(self) -> Iterator[None]:
        """Khoá cả tab TestCases của dự án (dùng khi tạo case).

        Service bọc "kiểm tra màn hình còn tồn tại rồi tạo case" trong khoá này. Gọi lồng nhau
        trên CÙNG repository thì chỉ khoá Redis một lần (khoá Redis không cho chính mình lấy
        lại lần hai). Thứ tự khoá khi lồng: assignments trước, test-cases sau.
        """
        if self._holding_lock:
            yield
            return
        with redis_lock(self._redis, self._lock_key, wait_seconds=self._lock_wait_seconds):
            self._holding_lock = True
            try:
                yield
            finally:
                self._holding_lock = False
