"""Đọc/ghi tab `Projects` của Sheet hệ thống.

Không cache: danh sách dự án chỉ đọc khi mở trang dự án, không phải ở mọi request.
"""

import re
from contextlib import AbstractContextManager

from redis import Redis

from app.core.locks.redis_lock import redis_lock
from app.core.models.project import Project
from app.core.sheets.gateway import SheetsGateway
from app.core.sheets.schema import PROJECT_COLUMNS, PROJECTS_TAB
from app.core.sheets.table import Record, SheetTable
from app.core.time import from_iso, to_iso, utc_now

TAB_LOCK_KEY = "lock:system:projects"
_ID_NUMBER = re.compile(r"^PRJ-(\d+)$")


class ProjectNotFoundError(Exception):
    pass


def _to_record(project: Project) -> Record:
    return {
        "id": project.id,
        "name": project.name,
        "repo_full_name": project.repo_full_name,
        "branch": project.branch,
        "staging_url": project.staging_url,
        "spreadsheet_id": project.spreadsheet_id,
        "archived": "TRUE" if project.archived else "FALSE",
        "created_at": to_iso(project.created_at),
    }


def _from_record(record: Record) -> Project:
    return Project(
        id=record["id"],
        name=record["name"],
        repo_full_name=record["repo_full_name"],
        branch=record["branch"],
        staging_url=record["staging_url"],
        spreadsheet_id=record["spreadsheet_id"],
        archived=record["archived"].strip().upper() == "TRUE",
        created_at=from_iso(record["created_at"]),
    )


def _next_project_id(existing: list[Project]) -> str:
    """Mã mới = số lớn nhất đang có + 1 (PRJ-0001, PRJ-0002...)."""
    numbers = [int(match.group(1)) for p in existing if (match := _ID_NUMBER.match(p.id))]
    return f"PRJ-{max(numbers, default=0) + 1:04d}"


class ProjectRepository:
    def __init__(
        self,
        gateway: SheetsGateway,
        spreadsheet_id: str,
        redis: Redis,
        *,
        lock_wait_seconds: float = 5.0,
    ) -> None:
        self._table = SheetTable(gateway, spreadsheet_id, PROJECTS_TAB, PROJECT_COLUMNS)
        self._redis = redis
        self._lock_wait_seconds = lock_wait_seconds

    def list_all(self) -> list[Project]:
        return [_from_record(record) for record in self._table.read_all()]

    def get(self, project_id: str) -> Project | None:
        return next((p for p in self.list_all() if p.id == project_id), None)

    def find_by_spreadsheet(self, spreadsheet_id: str) -> Project | None:
        return next((p for p in self.list_all() if p.spreadsheet_id == spreadsheet_id), None)

    def create(
        self,
        *,
        name: str,
        repo_full_name: str,
        branch: str,
        staging_url: str,
        spreadsheet_id: str,
    ) -> Project:
        with self._lock():
            project = Project(
                id=_next_project_id(self.list_all()),
                name=name,
                repo_full_name=repo_full_name,
                branch=branch,
                staging_url=staging_url,
                spreadsheet_id=spreadsheet_id,
                archived=False,
                created_at=utc_now(),
            )
            self._table.append(_to_record(project))
        return project

    def update(self, project: Project) -> Project:
        with self._lock():
            row_number = self._table.find_row_number("id", project.id)
            if row_number is None:
                raise ProjectNotFoundError(project.id)
            self._table.update(row_number, _to_record(project))
        return project

    def _lock(self) -> AbstractContextManager[None]:
        return redis_lock(self._redis, TAB_LOCK_KEY, wait_seconds=self._lock_wait_seconds)
