"""Đọc/ghi tab `Assignments` trong Sheet riêng của một dự án."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date

from redis import Redis

from app.core.ids import IdGenerator
from app.core.locks.redis_lock import redis_lock
from app.core.models.assignment import Assignment, AssignmentStatus
from app.core.models.user import normalize_email
from app.core.sheets.gateway import SheetsGateway
from app.core.sheets.schema import ASSIGNMENT_COLUMNS, ASSIGNMENTS_TAB
from app.core.sheets.table import Record, SheetTable
from app.core.time import from_iso, to_iso, utc_now


class AssignmentNotFoundError(Exception):
    pass


def _to_record(assignment: Assignment) -> Record:
    return {
        "id": assignment.id,
        "screen_id": assignment.screen_id,
        "assignee_email": assignment.assignee_email,
        "deadline": assignment.deadline.isoformat(),  # dạng 2026-11-30
        "status": assignment.status.value,
        "updated_at": to_iso(assignment.updated_at),
    }


def _from_record(record: Record) -> Assignment:
    return Assignment(
        id=record["id"],
        screen_id=record["screen_id"],
        assignee_email=normalize_email(record["assignee_email"]),
        deadline=date.fromisoformat(record["deadline"]),
        status=AssignmentStatus(record["status"] or AssignmentStatus.TODO),
        updated_at=from_iso(record["updated_at"]),
    )


class AssignmentRepository:
    def __init__(
        self,
        gateway: SheetsGateway,
        spreadsheet_id: str,
        redis: Redis,
        project_id: str,
        *,
        lock_wait_seconds: float = 5.0,
    ) -> None:
        self._table = SheetTable(gateway, spreadsheet_id, ASSIGNMENTS_TAB, ASSIGNMENT_COLUMNS)
        self._ids = IdGenerator(
            gateway, spreadsheet_id, redis, project_id, lock_wait_seconds=lock_wait_seconds
        )
        self._redis = redis
        self._lock_key = f"lock:{project_id}:assignments"
        self._lock_wait_seconds = lock_wait_seconds
        self._holding_lock = False

    def list_all(self) -> list[Assignment]:
        assignments = [_from_record(record) for record in self._table.read_all()]
        return sorted(assignments, key=lambda assignment: assignment.id)

    def get(self, assignment_id: str) -> Assignment | None:
        return next((a for a in self.list_all() if a.id == assignment_id), None)

    def create(
        self,
        *,
        screen_id: str,
        assignee_email: str,
        deadline: date,
        status: AssignmentStatus = AssignmentStatus.TODO,
    ) -> Assignment:
        assignment = Assignment(
            id=self._ids.next_id("assignment", "AS"),
            screen_id=screen_id,
            assignee_email=normalize_email(assignee_email),
            deadline=deadline,
            status=status,
            updated_at=utc_now(),
        )
        with self.lock():
            self._table.append(_to_record(assignment))
        return assignment

    def update(self, assignment: Assignment) -> Assignment:
        assignment = assignment.model_copy(update={"updated_at": utc_now()})
        with self.lock():
            row_number = self._table.find_row_number("id", assignment.id)
            if row_number is None:
                raise AssignmentNotFoundError(assignment.id)
            self._table.update(row_number, _to_record(assignment))
        return assignment

    def delete(self, assignment_id: str) -> None:
        with self.lock():
            row_number = self._table.find_row_number("id", assignment_id)
            if row_number is None:
                raise AssignmentNotFoundError(assignment_id)
            self._table.delete_row(row_number)

    @contextmanager
    def lock(self) -> Iterator[None]:
        """Khoá cả tab Assignments của dự án.

        Service dùng khoá này để bọc trọn "kiểm tra rồi ghi", ví dụ: kiểm tra tester chưa
        có việc rồi mới bỏ tester khỏi dự án. Trong lúc giữ khoá vẫn gọi được create()/
        delete(): gọi lồng nhau trên CÙNG repository thì chỉ khoá Redis một lần
        (khoá Redis không cho chính mình lấy lại lần hai). Mỗi request dựng repository riêng,
        nên request khác vẫn phải chờ.
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
