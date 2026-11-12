"""Đọc/ghi tab `ProjectMembers` của Sheet hệ thống.

Danh sách thành viên được đọc ở mọi request vào dự án (để kiểm tra quyền),
nên được cache giống danh sách user.
"""

import json
from contextlib import AbstractContextManager

from redis import Redis

from app.core.cache import GenerationCache
from app.core.locks.redis_lock import redis_lock
from app.core.models.project import ProjectMember
from app.core.models.user import normalize_email
from app.core.sheets.gateway import SheetsGateway
from app.core.sheets.schema import PROJECT_MEMBER_COLUMNS, PROJECT_MEMBERS_TAB
from app.core.sheets.table import SheetTable
from app.core.time import from_iso, to_iso, utc_now

CACHE_KEY = "cache:members"
TAB_LOCK_KEY = "lock:system:project-members"


class MemberAlreadyExistsError(Exception):
    pass


class MemberNotFoundError(Exception):
    pass


class ProjectMemberRepository:
    def __init__(
        self,
        gateway: SheetsGateway,
        spreadsheet_id: str,
        redis: Redis,
        *,
        cache_ttl_seconds: int,
        lock_wait_seconds: float = 5.0,
    ) -> None:
        self._table = SheetTable(
            gateway, spreadsheet_id, PROJECT_MEMBERS_TAB, PROJECT_MEMBER_COLUMNS
        )
        self._redis = redis
        self._cache = GenerationCache(redis, CACHE_KEY, cache_ttl_seconds)
        self._lock_wait_seconds = lock_wait_seconds

    def list_all(self) -> list[ProjectMember]:
        cached = self._cache.get()
        if cached is not None:
            return [ProjectMember.model_validate(item) for item in json.loads(cached)]

        generation_before = self._cache.generation()
        members = [
            ProjectMember(
                project_id=record["project_id"],
                email=normalize_email(record["email"]),
                added_at=from_iso(record["added_at"]),
            )
            for record in self._table.read_all()
        ]
        payload = json.dumps([member.model_dump(mode="json") for member in members])
        self._cache.set_if_unchanged(generation_before, payload)
        return members

    def list_for_project(self, project_id: str) -> list[ProjectMember]:
        return [member for member in self.list_all() if member.project_id == project_id]

    def projects_of(self, email: str) -> list[str]:
        wanted = normalize_email(email)
        return [member.project_id for member in self.list_all() if member.email == wanted]

    def is_member(self, project_id: str, email: str) -> bool:
        return project_id in self.projects_of(email)

    def add(self, project_id: str, email: str) -> ProjectMember:
        member = ProjectMember(
            project_id=project_id, email=normalize_email(email), added_at=utc_now()
        )
        with self._lock():
            if self._find_row(project_id, member.email) is not None:
                raise MemberAlreadyExistsError(member.email)
            self._table.append(
                {
                    "project_id": member.project_id,
                    "email": member.email,
                    "added_at": to_iso(member.added_at),
                }
            )
        self._cache.invalidate()
        return member

    def remove(self, project_id: str, email: str) -> None:
        with self._lock():
            # Tìm lại số dòng ngay trong khoá, rồi xoá đúng dòng đó.
            row_number = self._find_row(project_id, normalize_email(email))
            if row_number is None:
                raise MemberNotFoundError(email)
            self._table.delete_row(row_number)
        self._cache.invalidate()

    def _find_row(self, project_id: str, email: str) -> int | None:
        """Số dòng trên Sheet của cặp (dự án, email)."""
        for row_number, record in self._table.read_rows_numbered():
            same_project = record["project_id"] == project_id
            if same_project and normalize_email(record["email"]) == email:
                return row_number
        return None

    def _lock(self) -> AbstractContextManager[None]:
        return redis_lock(self._redis, TAB_LOCK_KEY, wait_seconds=self._lock_wait_seconds)
