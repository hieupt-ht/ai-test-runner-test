import fakeredis
import pytest

from app.core.bootstrap import ConfigError, bootstrap_system_spreadsheet
from app.core.models.user import Role
from app.core.passwords import verify_password
from app.core.repositories.users import UserRepository
from app.core.sheets.schema import SYSTEM_TABS
from tests.conftest import make_user
from tests.fakes import FakeSheetsGateway

SHEET_ID = "new-sheet"


def setup(tabs: dict[str, list[list[str]]]) -> tuple[FakeSheetsGateway, UserRepository]:
    gateway = FakeSheetsGateway({SHEET_ID: tabs})
    users = UserRepository(gateway, SHEET_ID, fakeredis.FakeRedis(), cache_ttl_seconds=300)
    return gateway, users


def test_creates_missing_tabs_with_headers() -> None:
    gateway, users = setup({"Users": [list(SYSTEM_TABS["Users"])]})

    created = bootstrap_system_spreadsheet(gateway, SHEET_ID, users, "")

    assert created == ["Projects", "ProjectMembers", "AuditLog"]
    for tab, columns in SYSTEM_TABS.items():
        assert gateway.data[SHEET_ID][tab][0] == columns


def test_adds_bootstrap_admin_when_users_empty() -> None:
    gateway, users = setup({})

    bootstrap_system_spreadsheet(gateway, SHEET_ID, users, "  Boss@X.com ", "mat-khau-1")

    admin = users.get("boss@x.com")
    assert admin is not None
    assert admin.role == Role.ADMIN
    assert admin.active


def test_adds_bootstrap_admin_with_password() -> None:
    gateway, users = setup({})

    bootstrap_system_spreadsheet(gateway, SHEET_ID, users, "boss@x.com", "mat-khau-1")

    assert verify_password("mat-khau-1", users.get_password_hash("boss@x.com"))
    assert users.get_password_hash("boss@x.com") != "mat-khau-1"


def test_missing_password_raises_config_error() -> None:
    gateway, users = setup({})

    with pytest.raises(ConfigError, match="BOOTSTRAP_ADMIN_PASSWORD"):
        bootstrap_system_spreadsheet(gateway, SHEET_ID, users, "boss@x.com", "")


def test_existing_admin_without_hash_gets_hash() -> None:
    gateway, users = setup({})
    bootstrap_system_spreadsheet(gateway, SHEET_ID, users, "")
    users.create(make_user("boss@x.com", role=Role.ADMIN))  # Admin từ bản cũ, chưa có mật khẩu

    bootstrap_system_spreadsheet(gateway, SHEET_ID, users, "boss@x.com", "mat-khau-1")

    assert verify_password("mat-khau-1", users.get_password_hash("boss@x.com"))


def test_existing_hash_not_overwritten() -> None:
    gateway, users = setup({})
    bootstrap_system_spreadsheet(gateway, SHEET_ID, users, "boss@x.com", "mat-khau-1")

    bootstrap_system_spreadsheet(gateway, SHEET_ID, users, "boss@x.com", "mat-khau-moi")

    assert verify_password("mat-khau-1", users.get_password_hash("boss@x.com"))


def test_old_users_tab_gets_password_hash_column() -> None:
    old = ["email", "name", "role", "active", "created_at"]
    gateway, users = setup({"Users": [old]})

    bootstrap_system_spreadsheet(gateway, SHEET_ID, users, "")

    assert gateway.data[SHEET_ID]["Users"][0][-1] == "password_hash"


def test_does_not_add_admin_when_users_exist() -> None:
    gateway, users = setup({})
    bootstrap_system_spreadsheet(gateway, SHEET_ID, users, "")
    users.create(make_user("an@x.com"))

    bootstrap_system_spreadsheet(gateway, SHEET_ID, users, "boss@x.com", "mat-khau-1")

    assert users.get("boss@x.com") is None


def test_existing_tab_with_missing_column_gets_it_appended() -> None:
    gateway, users = setup({"Users": [["email", "name", "active", "created_at"]]})

    bootstrap_system_spreadsheet(gateway, SHEET_ID, users, "")

    # Cột còn thiếu được thêm vào cuối, không báo lỗi
    assert gateway.data[SHEET_ID]["Users"][0] == [
        "email",
        "name",
        "active",
        "created_at",
        "role",
        "password_hash",
    ]


def test_running_twice_is_idempotent() -> None:
    gateway, users = setup({})

    bootstrap_system_spreadsheet(gateway, SHEET_ID, users, "boss@x.com", "mat-khau-1")
    created_again = bootstrap_system_spreadsheet(
        gateway, SHEET_ID, users, "boss@x.com", "mat-khau-1"
    )

    assert created_again == []
    assert len(users.list_all()) == 1


def test_start_services_skips_when_not_configured() -> None:
    from app.main import start_real_services
    from app.settings import Settings

    assert start_real_services(Settings(_env_file=None)) is None


def test_start_services_requires_session_secret_when_configured() -> None:
    from app.core.bootstrap import ConfigError
    from app.main import start_real_services
    from app.settings import Settings

    settings = Settings(
        _env_file=None, google_service_account_json="{}", system_spreadsheet_id="abc"
    )

    with pytest.raises(ConfigError, match="SESSION_SECRET"):
        start_real_services(settings)


def test_bootstrap_project_upgrades_old_tabs() -> None:
    from app.core.bootstrap import bootstrap_project_spreadsheet
    from app.core.sheets.schema import TEST_CASE_COLUMNS

    old_header = TEST_CASE_COLUMNS[:15]
    gateway = FakeSheetsGateway({SHEET_ID: {"TestCases": [list(old_header)]}})

    bootstrap_project_spreadsheet(gateway, SHEET_ID)

    assert gateway.data[SHEET_ID]["TestCases"][0] == TEST_CASE_COLUMNS


def test_upgrade_skips_archived_and_survives_errors() -> None:
    from types import SimpleNamespace

    from app.core.bootstrap import upgrade_project_spreadsheets

    gateway = FakeSheetsGateway({"ok": {}, "bad": {}, "old": {}})
    gateway.denied.add("bad")
    projects = SimpleNamespace(
        list_all=lambda: [
            SimpleNamespace(id="P1", spreadsheet_id="bad", archived=False),
            SimpleNamespace(id="P2", spreadsheet_id="ok", archived=False),
            SimpleNamespace(id="P3", spreadsheet_id="old", archived=True),
        ]
    )

    upgrade_project_spreadsheets(projects, gateway)  # type: ignore[arg-type]

    assert "TestCases" in gateway.data["ok"]  # dự án lỗi không chặn dự án sau
    assert gateway.data["old"] == {}  # dự án lưu trữ không bị đụng tới


def test_project_bootstrap_adds_module_tabs_and_column() -> None:
    from app.core.bootstrap import bootstrap_project_spreadsheet

    old_screens = [
        "id",
        "name",
        "description",
        "route",
        "code_paths",
        "created_at",
        "dev_owner",
        "media_json",
    ]
    gateway = FakeSheetsGateway({"proj": {"Screens": [old_screens]}})

    created = bootstrap_project_spreadsheet(gateway, "proj")

    assert "Modules" in created and "ModuleAssignments" in created
    assert gateway.data["proj"]["Screens"][0][-1] == "module_id"
    assert gateway.data["proj"]["Modules"][0] == ["id", "name", "description", "created_at"]
