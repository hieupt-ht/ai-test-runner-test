"""Các fixture dùng chung cho test."""

from datetime import UTC, datetime

import fakeredis
import pytest

from app.core.models.user import Role, User
from app.core.repositories.audit_log import AuditLogRepository
from app.core.repositories.users import UserRepository
from app.core.sheets.schema import SYSTEM_TABS
from tests.fakes import FakeSheetsGateway

SYSTEM_SHEET_ID = "system-sheet"


def make_user(
    email: str, *, role: Role = Role.TESTER, active: bool = True, name: str = "Người dùng"
) -> User:
    return User(
        email=email,
        name=name,
        role=role,
        active=active,
        created_at=datetime(2026, 11, 12, tzinfo=UTC),
    )


@pytest.fixture
def gateway() -> FakeSheetsGateway:
    """Sheet hệ thống giả, đã có đủ các tab với hàng tiêu đề."""
    tabs = {tab: [list(columns)] for tab, columns in SYSTEM_TABS.items()}
    return FakeSheetsGateway({SYSTEM_SHEET_ID: tabs})


@pytest.fixture
def redis() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis()


@pytest.fixture
def users(gateway: FakeSheetsGateway, redis: fakeredis.FakeRedis) -> UserRepository:
    return UserRepository(
        gateway, SYSTEM_SHEET_ID, redis, cache_ttl_seconds=300, lock_wait_seconds=0.1
    )


@pytest.fixture
def audit_log(gateway: FakeSheetsGateway) -> AuditLogRepository:
    return AuditLogRepository(gateway, SYSTEM_SHEET_ID)
