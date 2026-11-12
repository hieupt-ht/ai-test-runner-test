"""Sinh mã theo từng dự án: SC-0001, AS-0001...

Bộ đếm lưu ở tab `Meta` của Sheet dự án (cột key, value), ví dụ `next_screen_id = 3`.
Lưu trên Sheet (không lưu trong Redis) để mất Redis cũng không bị trùng mã.
"""

from redis import Redis

from app.core.locks.redis_lock import redis_lock
from app.core.sheets.gateway import SheetsGateway
from app.core.sheets.schema import META_COLUMNS, META_TAB
from app.core.sheets.table import SheetTable


class IdGenerator:
    def __init__(
        self,
        gateway: SheetsGateway,
        spreadsheet_id: str,
        redis: Redis,
        project_id: str,
        *,
        lock_wait_seconds: float = 5.0,
    ) -> None:
        self._meta = SheetTable(gateway, spreadsheet_id, META_TAB, META_COLUMNS)
        self._redis = redis
        self._project_id = project_id
        self._lock_wait_seconds = lock_wait_seconds

    def next_id(self, entity: str, prefix: str) -> str:
        key = f"next_{entity}_id"
        lock_key = f"lock:id:{self._project_id}:{entity}"
        with redis_lock(self._redis, lock_key, wait_seconds=self._lock_wait_seconds):
            row_number = self._meta.find_row_number("key", key)
            if row_number is None:
                number = 1
                self._meta.append({"key": key, "value": str(number + 1)})
            else:
                number = int(self._meta.read_row(row_number)["value"] or "1")
                self._meta.update(row_number, {"key": key, "value": str(number + 1)})
        return f"{prefix}-{number:04d}"
