"""Các fixture dùng chung cho test."""

from datetime import UTC, datetime

import fakeredis
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.services import Services
from app.api.sessions import SessionStore
from app.core.bootstrap import bootstrap_project_spreadsheet
from app.core.login_throttle import LoginThrottle
from app.core.models.project import Project
from app.core.models.user import Role, User
from app.core.notifications import NotificationStore
from app.core.passwords import hash_password
from app.core.repositories.audit_log import AuditLogRepository
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import ProjectRepository
from app.core.repositories.users import UserRepository
from app.core.sheets.schema import SYSTEM_TABS
from app.main import create_app
from app.settings import Settings
from tests.fakes import FakeGitHub, FakeSheetsGateway

SYSTEM_SHEET_ID = "1SystemSheetId000000000000000000"
SHEET_A = "1ProjectSheetA00000000000000000"
SHEET_B = "1ProjectSheetB00000000000000000"


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


@pytest.fixture(autouse=True)
def fast_password_hasher(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hạ chi phí argon2 trong test cho chạy nhanh (bản thật vẫn dùng mặc định)."""
    from argon2 import PasswordHasher

    monkeypatch.setattr(
        "app.core.passwords._hasher", PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
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
def github() -> FakeGitHub:
    return FakeGitHub({"org/web": ["develop", "main"], "org/api": ["main"]})


@pytest.fixture
def app(
    users: UserRepository,
    audit_log: AuditLogRepository,
    redis: fakeredis.FakeRedis,
    gateway: FakeSheetsGateway,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    github: FakeGitHub,
) -> FastAPI:
    """App thật, nhưng Sheets, Redis, Google và GitHub đều là bản giả."""
    services = Services(
        redis=redis,
        notifications=NotificationStore(redis),
        users=users,
        audit_log=audit_log,
        sessions=SessionStore(redis, ttl_seconds=3600),
        login_throttle=LoginThrottle(redis),
        gateway=gateway,
        system_spreadsheet_id=SYSTEM_SHEET_ID,
        service_account_email=gateway.service_account_email,
        projects=projects,
        members=members,
        github=github,
        lock_wait_seconds=0.1,
    )
    settings = Settings(
        _env_file=None,
        session_secret="test-secret",
        app_base_url="http://localhost:3000",
        # Test không được phụ thuộc token thật đang có trong môi trường chạy.
        agent_api_token="",
    )
    return create_app(settings, services=services)


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, follow_redirects=False)


def client_for(app: FastAPI, users: UserRepository, email: str, role: Role) -> TestClient:
    """Một trình duyệt riêng (cookie riêng) đã đăng nhập bằng `email`."""
    browser = TestClient(app, follow_redirects=False)
    log_in_as(browser, users, email, role)
    return browser


def make_project(
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
    *,
    name: str = "Dự án A",
    sheet: str = SHEET_A,
    member_emails: tuple[str, ...] = (),
    archived: bool = False,
) -> Project:
    """Tạo sẵn một dự án (kèm Sheet dự án giả đã có đủ tab) mà không qua API."""
    gateway.data.setdefault(sheet, {})
    bootstrap_project_spreadsheet(gateway, sheet)
    project = projects.create(
        name=name, repo_full_name="org/web", branch="main", staging_url="", spreadsheet_id=sheet
    )
    if archived:
        project = projects.update(project.model_copy(update={"archived": True}))
    for email in member_emails:
        members.add(project.id, email)
    return project


TEST_PASSWORD = "mat-khau-test"


def log_in_as(
    client: TestClient,
    users: UserRepository,
    email: str,
    role: Role,
    password: str = TEST_PASSWORD,
) -> None:
    """Tạo user (nếu chưa có) kèm mật khẩu thật, rồi đăng nhập qua API."""
    if users.get(email) is None:
        users.create(make_user(email, role=role), password_hash=hash_password(password))
    elif not users.get_password_hash(email):
        users.set_password_hash(email, hash_password(password))  # user tạo sẵn, chưa có mật khẩu
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text


@pytest.fixture
def client_as_admin(client: TestClient, users: UserRepository) -> TestClient:
    log_in_as(client, users, "admin@x.com", Role.ADMIN)
    return client


@pytest.fixture
def client_as_qa_lead(client: TestClient, users: UserRepository) -> TestClient:
    log_in_as(client, users, "lead@x.com", Role.QA_LEAD)
    return client


@pytest.fixture
def projects(gateway: FakeSheetsGateway, redis: fakeredis.FakeRedis) -> ProjectRepository:
    return ProjectRepository(
        gateway, SYSTEM_SHEET_ID, redis, cache_ttl_seconds=300, lock_wait_seconds=0.1
    )


@pytest.fixture
def members(gateway: FakeSheetsGateway, redis: fakeredis.FakeRedis) -> ProjectMemberRepository:
    return ProjectMemberRepository(
        gateway, SYSTEM_SHEET_ID, redis, cache_ttl_seconds=300, lock_wait_seconds=0.1
    )


@pytest.fixture
def client_as_tester(client: TestClient, users: UserRepository) -> TestClient:
    log_in_as(client, users, "tester@x.com", Role.TESTER)
    return client
