"""Gom các đối tượng dùng chung (Redis, repository, OAuth) vào một chỗ.

App thật dựng chúng từ cấu hình; test truyền vào bản giả.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from redis import Redis

from app.api.oauth import GoogleOAuth, OAuthClient
from app.api.sessions import SessionStore
from app.core.repositories.audit_log import AuditLogRepository
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


def is_configured(settings: Settings) -> bool:
    return bool(settings.google_service_account_json and settings.system_spreadsheet_id)


def load_service_account_info(value: str) -> dict[str, Any]:
    """Biến môi trường có thể là nội dung JSON, hoặc đường dẫn tới file key."""
    text = value if value.lstrip().startswith("{") else Path(value).read_text(encoding="utf-8")
    info: dict[str, Any] = json.loads(text)
    return info


def build_gateway(settings: Settings) -> SheetsGateway:
    return GoogleSheetsGateway(load_service_account_info(settings.google_service_account_json))


def build_services(settings: Settings, gateway: SheetsGateway) -> Services:
    redis = Redis.from_url(settings.redis_url)
    return Services(
        redis=redis,
        users=UserRepository(
            gateway,
            settings.system_spreadsheet_id,
            redis,
            cache_ttl_seconds=settings.user_cache_ttl_seconds,
        ),
        audit_log=AuditLogRepository(gateway, settings.system_spreadsheet_id),
        sessions=SessionStore(redis, ttl_seconds=settings.session_ttl_seconds),
        oauth=GoogleOAuth(settings.google_client_id, settings.google_client_secret),
    )
