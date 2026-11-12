"""Gom các đối tượng dùng chung (Redis, repository, OAuth, GitHub) vào một chỗ.

App thật dựng chúng từ cấu hình; test truyền vào bản giả.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from redis import Redis

from app.api.oauth import GoogleOAuth, OAuthClient
from app.api.sessions import SessionStore
from app.core.github.client import GitHubAppClient, GitHubClient
from app.core.repositories.audit_log import AuditLogRepository
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import ProjectRepository
from app.core.repositories.users import UserRepository
from app.core.sheets.gateway import GoogleSheetsGateway, SheetsGateway
from app.settings import Settings


@dataclass
class Services:
    redis: Redis
    users: UserRepository
    audit_log: AuditLogRepository
    sessions: SessionStore
    oauth: OAuthClient
    gateway: SheetsGateway
    system_spreadsheet_id: str
    service_account_email: str
    projects: ProjectRepository
    members: ProjectMemberRepository
    github: GitHubClient | None  # None khi chưa cấu hình GitHub App
    lock_wait_seconds: float = 5.0


def is_configured(settings: Settings) -> bool:
    return bool(settings.google_service_account_json and settings.system_spreadsheet_id)


def load_service_account_info(value: str) -> dict[str, Any]:
    """Biến môi trường có thể là nội dung JSON, hoặc đường dẫn tới file key."""
    text = value.strip().strip("'")
    if not text.startswith("{"):
        text = Path(text).read_text(encoding="utf-8")
    info: dict[str, Any] = json.loads(text)
    return info


def build_gateway(settings: Settings) -> GoogleSheetsGateway:
    return GoogleSheetsGateway(load_service_account_info(settings.google_service_account_json))


def build_github(settings: Settings) -> GitHubClient | None:
    if not (settings.github_app_id and settings.github_app_private_key):
        return None
    return GitHubAppClient(settings.github_app_id, settings.github_app_private_key)


def build_services(settings: Settings, gateway: GoogleSheetsGateway) -> Services:
    redis = Redis.from_url(settings.redis_url)
    system_sheet = settings.system_spreadsheet_id
    return Services(
        redis=redis,
        users=UserRepository(
            gateway, system_sheet, redis, cache_ttl_seconds=settings.user_cache_ttl_seconds
        ),
        audit_log=AuditLogRepository(gateway, system_sheet),
        sessions=SessionStore(redis, ttl_seconds=settings.session_ttl_seconds),
        oauth=GoogleOAuth(settings.google_client_id, settings.google_client_secret),
        gateway=gateway,
        system_spreadsheet_id=system_sheet,
        service_account_email=gateway.service_account_email,
        projects=ProjectRepository(gateway, system_sheet, redis),
        members=ProjectMemberRepository(
            gateway, system_sheet, redis, cache_ttl_seconds=settings.user_cache_ttl_seconds
        ),
        github=build_github(settings),
    )
