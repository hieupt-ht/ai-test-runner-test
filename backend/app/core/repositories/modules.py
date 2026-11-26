"""Đọc/ghi hai tab `Modules` và `ModuleAssignments` trong Sheet riêng của một dự án."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date

from redis import Redis

from app.core.cache import CachedList
from app.core.ids import IdGenerator
from app.core.locks.redis_lock import redis_lock
from app.core.models.module import Module, ModuleAssignment
from app.core.models.user import normalize_email
from app.core.sheets.gateway import SheetsGateway
from app.core.sheets.schema import (
    MODULE_ASSIGNMENT_COLUMNS,
    MODULE_ASSIGNMENTS_TAB,
    MODULE_COLUMNS,
    MODULES_TAB,
)
from app.core.sheets.table import Record, SheetTable
from app.core.time import from_iso, to_iso, utc_now


class ModuleNotFoundError(Exception):
    pass


class ModuleAssignmentNotFoundError(Exception):
    pass


def _module_to_record(module: Module) -> Record:
    return {
        "id": module.id,
        "name": module.name,
        "description": module.description,
        "created_at": to_iso(module.created_at),
    }


def _module_from_record(record: Record) -> Module:
    return Module(
        id=record["id"],
        name=record["name"],
        description=record["description"],
        created_at=from_iso(record["created_at"]),
    )


def _assignment_to_record(item: ModuleAssignment) -> Record:
    return {
        "id": item.id,
        "module_id": item.module_id,
        "assignee_email": item.assignee_email,
        "deadline": item.deadline.isoformat(),
        "created_at": to_iso(item.created_at),
    }


def _assignment_from_record(record: Record) -> ModuleAssignment:
    return ModuleAssignment(
        id=record["id"],
        module_id=record["module_id"],
        assignee_email=normalize_email(record["assignee_email"]),
        deadline=date.fromisoformat(record["deadline"]),
        created_at=from_iso(record["created_at"]),
    )


class ModuleRepository:
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
        self._table = SheetTable(gateway, spreadsheet_id, MODULES_TAB, MODULE_COLUMNS)
        self._cache = CachedList(redis, f"cache:{project_id}:modules", cache_ttl_seconds, Module)
        self._ids = IdGenerator(
            gateway, spreadsheet_id, redis, project_id, lock_wait_seconds=lock_wait_seconds
        )
        self._redis = redis
        self._lock_key = f"lock:{project_id}:modules"
        self._lock_wait_seconds = lock_wait_seconds
        self._holding_lock = False

    def list_all(self) -> list[Module]:
        return self._cache.read(self._read_sheet, bypass=self._holding_lock)

    def _read_sheet(self) -> list[Module]:
        modules = [_module_from_record(record) for record in self._table.read_all()]
        return sorted(modules, key=lambda module: module.id)

    def get(self, module_id: str) -> Module | None:
        return next((m for m in self.list_all() if m.id == module_id), None)

    def create(self, *, name: str, description: str) -> Module:
        module = Module(
            id=self._ids.next_id("module", "MD"),
            name=name,
            description=description,
            created_at=utc_now(),
        )
        with self.lock():
            self._table.append(_module_to_record(module))
            self._cache.invalidate()
        return module

    def update(self, module: Module) -> Module:
        with self.lock():
            row_number = self._table.find_row_number("id", module.id)
            if row_number is None:
                raise ModuleNotFoundError(module.id)
            self._table.update(row_number, _module_to_record(module))
            self._cache.invalidate()
        return module

    def delete(self, module_id: str) -> None:
        with self.lock():
            row_number = self._table.find_row_number("id", module_id)
            if row_number is None:
                raise ModuleNotFoundError(module_id)
            self._table.delete_row(row_number)
            self._cache.invalidate()

    @contextmanager
    def lock(self) -> Iterator[None]:
        """Khoá tab Modules; gọi lồng trên CÙNG repository chỉ khoá Redis một lần."""
        if self._holding_lock:
            yield
            return
        with redis_lock(self._redis, self._lock_key, wait_seconds=self._lock_wait_seconds):
            self._holding_lock = True
            try:
                yield
            finally:
                self._holding_lock = False


class ModuleAssignmentRepository:
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
        self._table = SheetTable(
            gateway, spreadsheet_id, MODULE_ASSIGNMENTS_TAB, MODULE_ASSIGNMENT_COLUMNS
        )
        self._cache = CachedList(
            redis, f"cache:{project_id}:module-assignments", cache_ttl_seconds, ModuleAssignment
        )
        self._ids = IdGenerator(
            gateway, spreadsheet_id, redis, project_id, lock_wait_seconds=lock_wait_seconds
        )
        self._redis = redis
        # Khoá riêng (không dùng chung khoá Assignments) để hai repository khoá lồng nhau được
        self._lock_key = f"lock:{project_id}:module-assignments"
        self._lock_wait_seconds = lock_wait_seconds
        self._holding_lock = False

    def list_all(self) -> list[ModuleAssignment]:
        return self._cache.read(self._read_sheet, bypass=self._holding_lock)

    def _read_sheet(self) -> list[ModuleAssignment]:
        items = [_assignment_from_record(record) for record in self._table.read_all()]
        return sorted(items, key=lambda item: item.id)

    def create_many(self, items: list[tuple[str, str, date]]) -> list[ModuleAssignment]:
        """Tạo nhiều dòng một lượt: `items` là (module_id, email, hạn)."""
        if not items:
            return []
        now = utc_now()
        with self.lock():
            ids = self._ids.next_ids("module_assignment", "MA", len(items))
            created = [
                ModuleAssignment(
                    id=item_id,
                    module_id=module_id,
                    assignee_email=normalize_email(email),
                    deadline=deadline,
                    created_at=now,
                )
                for item_id, (module_id, email, deadline) in zip(ids, items, strict=True)
            ]
            self._table.append_many([_assignment_to_record(item) for item in created])
            self._cache.invalidate()
        return created

    def update_many(self, items: list[ModuleAssignment]) -> list[ModuleAssignment]:
        if not items:
            return []
        with self.lock():
            rows = {r["id"]: n for n, r in self._table.read_rows_numbered()}
            for item in items:
                if item.id not in rows:
                    raise ModuleAssignmentNotFoundError(item.id)
            self._table.update_many([(rows[i.id], _assignment_to_record(i)) for i in items])
            self._cache.invalidate()
        return items

    def delete_many(self, ids: list[str]) -> None:
        """Xoá nhiều dòng (xoá từ dòng dưới lên để số dòng không lệch)."""
        if not ids:
            return
        with self.lock():
            rows = {r["id"]: n for n, r in self._table.read_rows_numbered()}
            for item_id in ids:
                if item_id not in rows:
                    raise ModuleAssignmentNotFoundError(item_id)
            self._table.delete_rows([rows[i] for i in ids])
            self._cache.invalidate()

    @contextmanager
    def lock(self) -> Iterator[None]:
        """Khoá tab ModuleAssignments; gọi lồng trên CÙNG repository chỉ khoá Redis một lần."""
        if self._holding_lock:
            yield
            return
        with redis_lock(self._redis, self._lock_key, wait_seconds=self._lock_wait_seconds):
            self._holding_lock = True
            try:
                yield
            finally:
                self._holding_lock = False
