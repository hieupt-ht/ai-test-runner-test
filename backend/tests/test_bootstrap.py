import fakeredis
import pytest

from app.core.bootstrap import bootstrap_system_spreadsheet
from app.core.models.user import Role
from app.core.repositories.users import UserRepository
from app.core.sheets.schema import SYSTEM_TABS
from app.core.sheets.table import MissingColumnsError
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

    bootstrap_system_spreadsheet(gateway, SHEET_ID, users, "  Boss@X.com ")

    admin = users.get("boss@x.com")
    assert admin is not None
    assert admin.role == Role.ADMIN
    assert admin.active


def test_does_not_add_admin_when_users_exist() -> None:
    gateway, users = setup({})
    bootstrap_system_spreadsheet(gateway, SHEET_ID, users, "")
    users.create(make_user("an@x.com"))

    bootstrap_system_spreadsheet(gateway, SHEET_ID, users, "boss@x.com")

    assert users.get("boss@x.com") is None


def test_existing_tab_with_missing_column_raises() -> None:
    gateway, users = setup({"Users": [["email", "name", "active", "created_at"]]})

    with pytest.raises(MissingColumnsError, match="role"):
        bootstrap_system_spreadsheet(gateway, SHEET_ID, users, "")


def test_running_twice_is_idempotent() -> None:
    gateway, users = setup({})

    bootstrap_system_spreadsheet(gateway, SHEET_ID, users, "boss@x.com")
    created_again = bootstrap_system_spreadsheet(gateway, SHEET_ID, users, "boss@x.com")

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
