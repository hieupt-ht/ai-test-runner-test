"""Đọc/ghi tab `Screens` trong Sheet riêng của một dự án."""

import json
from contextlib import AbstractContextManager

from redis import Redis

from app.core.cache import CachedList
from app.core.ids import IdGenerator
from app.core.locks.redis_lock import redis_lock
from app.core.models.screen import Screen
from app.core.sheets.gateway import SheetsGateway
from app.core.sheets.schema import SCREEN_COLUMNS, SCREENS_TAB
from app.core.sheets.table import Record, SheetTable
from app.core.time import from_iso, to_iso, utc_now


class ScreenNotFoundError(Exception):
    pass


def _to_record(screen: Screen) -> Record:
    return {
        "id": screen.id,
        "name": screen.name,
        "description": screen.description,
        "route": screen.route,
        # Danh sách đường dẫn lưu thành chuỗi JSON trong một ô
        "code_paths": json.dumps(screen.code_paths, ensure_ascii=False),
        "created_at": to_iso(screen.created_at),
        "dev_owner": screen.dev_owner,
    }


def _from_record(record: Record) -> Screen:
    return Screen(
        id=record["id"],
        name=record["name"],
        description=record["description"],
        route=record["route"],
        code_paths=json.loads(record["code_paths"] or "[]"),
        created_at=from_iso(record["created_at"]),
        dev_owner=record["dev_owner"],
    )


class ScreenRepository:
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
        self._table = SheetTable(gateway, spreadsheet_id, SCREENS_TAB, SCREEN_COLUMNS)
        self._cache = CachedList(redis, f"cache:{project_id}:screens", cache_ttl_seconds, Screen)
        self._ids = IdGenerator(
            gateway, spreadsheet_id, redis, project_id, lock_wait_seconds=lock_wait_seconds
        )
        self._redis = redis
        self._lock_key = f"lock:{project_id}:screens"
        self._lock_wait_seconds = lock_wait_seconds

    def list_all(self) -> list[Screen]:
        return self._cache.read(self._read_sheet)

    def _read_sheet(self) -> list[Screen]:
        screens = [_from_record(record) for record in self._table.read_all()]
        return sorted(screens, key=lambda screen: screen.id)

    def get(self, screen_id: str) -> Screen | None:
        return next((screen for screen in self.list_all() if screen.id == screen_id), None)

    def create(self, *, name: str, description: str, route: str, code_paths: list[str]) -> Screen:
        screen = Screen(
            id=self._ids.next_id("screen", "SC"),
            name=name,
            description=description,
            route=route,
            code_paths=code_paths,
            created_at=utc_now(),
        )
        with self._lock():
            self._table.append(_to_record(screen))
            self._cache.invalidate()
        return screen

    def update(self, screen: Screen) -> Screen:
        with self._lock():
            row_number = self._table.find_row_number("id", screen.id)
            if row_number is None:
                raise ScreenNotFoundError(screen.id)
            self._table.update(row_number, _to_record(screen))
            self._cache.invalidate()
        return screen

    def delete(self, screen_id: str) -> None:
        with self._lock():
            row_number = self._table.find_row_number("id", screen_id)
            if row_number is None:
                raise ScreenNotFoundError(screen_id)
            self._table.delete_row(row_number)
            self._cache.invalidate()

    def _lock(self) -> AbstractContextManager[None]:
        return redis_lock(self._redis, self._lock_key, wait_seconds=self._lock_wait_seconds)
