"""Đọc/ghi tab `Users` của Sheet hệ thống.

Danh sách user được đọc ở MỌI request (để kiểm tra quyền), nên được cache trong Redis
vài phút để không vượt giới hạn đọc của Google. Cache bị xoá ngay sau mỗi lần ghi.
"""

import json
import logging
from contextlib import AbstractContextManager

from pydantic import ValidationError
from redis import Redis

from app.core.locks.redis_lock import redis_lock
from app.core.models.user import Role, User, normalize_email
from app.core.sheets.gateway import SheetsGateway
from app.core.sheets.schema import USER_COLUMNS, USERS_TAB
from app.core.sheets.table import Record, SheetTable
from app.core.time import from_iso, to_iso

logger = logging.getLogger(__name__)

CACHE_KEY = "cache:users"
TRUE_TEXTS = {"true", "1", "yes"}


class UserAlreadyExistsError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


def _to_record(user: User) -> Record:
    return {
        "email": normalize_email(user.email),
        "name": user.name,
        "role": user.role.value,
        "active": "TRUE" if user.active else "FALSE",
        "created_at": to_iso(user.created_at),
    }


def _from_record(record: Record) -> User:
    return User(
        email=normalize_email(record["email"]),
        name=record["name"],
        role=Role(record["role"]),
        active=record["active"].strip().lower() in TRUE_TEXTS,
        created_at=from_iso(record["created_at"]),
    )


class UserRepository:
    def __init__(
        self,
        gateway: SheetsGateway,
        spreadsheet_id: str,
        redis: Redis,
        *,
        cache_ttl_seconds: int,
        lock_wait_seconds: float = 5.0,
    ) -> None:
        self._table = SheetTable(gateway, spreadsheet_id, USERS_TAB, USER_COLUMNS)
        self._redis = redis
        self._cache_ttl_seconds = cache_ttl_seconds
        self._lock_wait_seconds = lock_wait_seconds

    def list_all(self) -> list[User]:
        cached = self._redis.get(CACHE_KEY)
        if cached is not None:
            return [User.model_validate(item) for item in json.loads(cached)]

        users = self._read_from_sheet()
        payload = json.dumps([user.model_dump(mode="json") for user in users])
        self._redis.set(CACHE_KEY, payload, ex=self._cache_ttl_seconds)
        return users

    def get(self, email: str) -> User | None:
        wanted = normalize_email(email)
        return next((user for user in self.list_all() if user.email == wanted), None)

    def is_empty(self) -> bool:
        return not self._read_from_sheet()

    def create(self, user: User) -> User:
        user = user.model_copy(update={"email": normalize_email(user.email)})
        with self._lock(user.email):
            # Kiểm tra trực tiếp trên Sheet (không qua cache) để chắc chắn không trùng.
            if self._table.find_row_number("email", user.email) is not None:
                raise UserAlreadyExistsError(user.email)
            self._table.append(_to_record(user))
        self._clear_cache()
        return user

    def update(self, user: User) -> User:
        user = user.model_copy(update={"email": normalize_email(user.email)})
        with self._lock(user.email):
            # Tìm lại số dòng ngay trong khoá, không dùng số dòng đã biết từ trước.
            row_number = self._table.find_row_number("email", user.email)
            if row_number is None:
                raise UserNotFoundError(user.email)
            self._table.update(row_number, _to_record(user))
        self._clear_cache()
        return user

    def _read_from_sheet(self) -> list[User]:
        users: list[User] = []
        for record in self._table.read_all():
            try:
                users.append(_from_record(record))
            except (ValueError, ValidationError):
                # Một dòng bị sửa tay sai định dạng không được làm hỏng cả app.
                logger.warning("Bỏ qua dòng user sai định dạng: %s", record.get("email"))
        return users

    def _lock(self, email: str) -> AbstractContextManager[None]:
        return redis_lock(
            self._redis, f"lock:system:user:{email}", wait_seconds=self._lock_wait_seconds
        )

    def _clear_cache(self) -> None:
        self._redis.delete(CACHE_KEY)
