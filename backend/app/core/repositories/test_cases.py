"""Đọc/ghi tab `TestCases` trong Sheet riêng của một dự án.

Danh sách case được cache ngắn trong Redis (xoá ngay sau mỗi lần ghi), nhưng việc kiểm tra
phiên bản khi lưu (`save`) luôn đọc thẳng từ Sheet trong khoá, nên cache cũ không gây mất dữ liệu.
Chống ghi đè nhau bằng số `version`: người lưu phải nói mình đang dựa trên version nào.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from redis import Redis

from app.core.cache import CachedList
from app.core.ids import IdGenerator
from app.core.locks.redis_lock import redis_lock
from app.core.models.media import Media
from app.core.models.test_case import (
    ExecutionMode,
    Platform,
    Priority,
    Severity,
    TestCase,
    TestCaseContent,
    TestCaseStatus,
    TestStep,
    TestType,
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
    steps = [
        {
            "action": step.action,
            "expected": step.expected,
            "guide_media": [media.model_dump(mode="json") for media in step.guide_media],
        }
        for step in case.steps
    ]
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
        "platform": case.platform.value,
        "test_type": case.test_type.value,
        "regression": "TRUE" if case.regression else "FALSE",
        "start_point": case.start_point,
        "guide_media_json": json.dumps(
            [media.model_dump(mode="json") for media in case.guide_media], ensure_ascii=False
        ),
        "postcondition": case.postcondition,
        "requirement_ref": case.requirement_ref,
        "execution_mode": case.execution_mode.value,
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
        # Dòng cũ có các ô mới trống: dùng giá trị mặc định
        platform=Platform(record["platform"] or Platform.WEB),
        test_type=TestType(record["test_type"] or TestType.FUNCTIONAL),
        regression=record["regression"].strip().upper() == "TRUE",
        start_point=record["start_point"],
        guide_media=[Media(**item) for item in json.loads(record["guide_media_json"] or "[]")],
        postcondition=record["postcondition"],
        requirement_ref=record["requirement_ref"],
        # Case cũ (ô trống) được viết cho agent chạy nên đọc thành AUTOMATION
        execution_mode=ExecutionMode(
            record["execution_mode"].strip().upper() or ExecutionMode.AUTOMATION
        ),
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
        cache_ttl_seconds: int = 0,
    ) -> None:
        self._table = SheetTable(gateway, spreadsheet_id, TEST_CASES_TAB, TEST_CASE_COLUMNS)
        self._cache = CachedList(
            redis, f"cache:{project_id}:test-cases", cache_ttl_seconds, TestCase
        )
        self._ids = IdGenerator(
            gateway, spreadsheet_id, redis, project_id, lock_wait_seconds=lock_wait_seconds
        )
        self._redis = redis
        self._project_id = project_id
        self._lock_key = f"lock:{project_id}:test-cases"
        self._lock_wait_seconds = lock_wait_seconds
        self._holding_lock = False

    def list_all(self) -> list[TestCase]:
        # Đang giữ khoá tab (để kiểm tra rồi tạo) thì phải đọc thẳng Sheet, không qua cache.
        return self._cache.read(self._read_sheet, bypass=self._holding_lock)

    def _read_sheet(self) -> list[TestCase]:
        cases = [_from_record(record) for record in self._table.read_all()]
        return sorted(cases, key=lambda case: case.id)

    def get(self, case_id: str) -> TestCase | None:
        """Lấy từ danh sách đã cache (nếu bật); không có cache thì chỉ đọc cột id và đúng dòng."""
        if self._cache.enabled:
            return next((case for case in self.list_all() if case.id == case_id), None)
        found = self._table.find_record("id", case_id)
        return None if found is None else _from_record(found.record)

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
            self._cache.invalidate()
        return case

    def create_many(
        self, items: list[tuple[str, TestCaseContent]], *, actor: str
    ) -> list[TestCase]:
        """Tạo nhiều case một lượt: `items` là (screen_id, nội dung); cấp mã và ghi một lần."""
        if not items:
            return []
        now = _now_like_sheet()
        with self.lock():
            case_ids = self._ids.next_ids("tc", "TC", len(items), digits=6)
            cases = [
                TestCase(
                    **content.model_dump(),
                    id=case_id,
                    screen_id=screen_id,
                    status=TestCaseStatus.DRAFT,
                    created_by=actor,
                    updated_by=actor,
                    created_at=now,
                    updated_at=now,
                    version=1,
                )
                for case_id, (screen_id, content) in zip(case_ids, items, strict=True)
            ]
            self._table.append_many([_to_record(case) for case in cases])
            self._cache.invalidate()
        return cases

    def save(self, case: TestCase, *, expected_version: int, actor: str) -> TestCase:
        """Ghi `case` nếu version trên Sheet còn đúng `expected_version`.

        Khoá theo từng bản ghi (tab TestCases không bao giờ xoá dòng nên dòng không dịch chỗ).
        Version trên Sheet khác -> có người sửa trước, báo VersionConflictError kèm bản mới nhất.
        """
        record_lock_key = f"lock:{self._project_id}:test-case:{case.id}"
        with redis_lock(self._redis, record_lock_key, wait_seconds=self._lock_wait_seconds):
            found = self._table.find_record("id", case.id)
            if found is None:
                raise TestCaseNotFoundError(case.id)
            current = _from_record(found.record)
            if current.version != expected_version:
                raise VersionConflictError(current)
            saved = case.model_copy(
                update={
                    "version": expected_version + 1,
                    "updated_by": actor,
                    "updated_at": _now_like_sheet(),
                }
            )
            self._table.update_found(found, _to_record(saved))
            self._cache.invalidate()
        return saved

    def approve_all_in_review(self, actor: str) -> list[TestCase]:
        """Duyệt luôn mọi case IN_REVIEW (khi dự án tắt bước duyệt). Trả các case đã đổi.

        Giữ khoá tab, đọc thẳng Sheet (không qua cache), tăng version và ghi tất cả
        bằng một lượt. Không có case nào chờ duyệt thì không ghi gì.
        """
        with self.lock():
            numbered = self._table.read_rows_numbered()
            now = _now_like_sheet()
            changed: list[tuple[int, TestCase]] = []
            for row_number, record in numbered:
                case = _from_record(record)
                if case.status != TestCaseStatus.IN_REVIEW:
                    continue
                approved = case.model_copy(
                    update={
                        "status": TestCaseStatus.APPROVED,
                        "version": case.version + 1,
                        "updated_by": actor,
                        "updated_at": now,
                    }
                )
                changed.append((row_number, approved))
            if not changed:
                return []
            self._table.update_many([(row, _to_record(case)) for row, case in changed])
            self._cache.invalidate()
        return [case for _, case in changed]

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
