"""Các fixture dùng chung cho test."""

from datetime import UTC, datetime

import fakeredis
import pytest
from fastapi.testclient import TestClient

from app.api.oauth import GoogleIdentity
from app.api.services import Services
from app.api.sessions import SessionStore
from app.core.models.user import Role, User
from app.core.repositories.audit_log import AuditLogRepository
from app.core.repositories.users import UserRepository
from app.core.sheets.schema import SYSTEM_TABS
from app.main import create_app
from app.settings import Settings
from tests.fakes import FakeOAuth, FakeSheetsGateway

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


@pytest.fixture
def oauth() -> FakeOAuth:
    return FakeOAuth()


@pytest.fixture
def client(
    users: UserRepository,
    audit_log: AuditLogRepository,
    redis: fakeredis.FakeRedis,
    oauth: FakeOAuth,
) -> TestClient:
    """App thật, nhưng Sheets, Redis và Google đều là bản giả."""
    services = Services(
        redis=redis,
        users=users,
        audit_log=audit_log,
        sessions=SessionStore(redis, ttl_seconds=3600),
        oauth=oauth,
    )
    settings = Settings(
        _env_file=None, session_secret="test-secret", app_base_url="http://localhost:3000"
    )
    return TestClient(create_app(settings, services=services), follow_redirects=False)


def log_in_as(
    client: TestClient, oauth: FakeOAuth, users: UserRepository, email: str, role: Role
) -> None:
    """Tạo user (nếu chưa có) rồi đăng nhập qua luồng OAuth giả."""
    if users.get(email) is None:
        users.create(make_user(email, role=role))
    oauth.identity = GoogleIdentity(email=email, name="Ai đó")
    response = client.get("/api/auth/callback")
    assert response.headers["location"] == "/"


@pytest.fixture
def client_as_admin(client: TestClient, oauth: FakeOAuth, users: UserRepository) -> TestClient:
    log_in_as(client, oauth, users, "admin@x.com", Role.ADMIN)
    return client


@pytest.fixture
def client_as_qa_lead(client: TestClient, oauth: FakeOAuth, users: UserRepository) -> TestClient:
    log_in_as(client, oauth, users, "lead@x.com", Role.QA_LEAD)
    return client
