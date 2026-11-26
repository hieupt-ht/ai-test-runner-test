import fakeredis
import pytest

from app.core.bootstrap import bootstrap_project_spreadsheet
from app.core.models.user import Role
from app.core.repositories.assignments import AssignmentRepository
from app.core.repositories.audit_log import AuditLogRepository
from app.core.repositories.modules import ModuleRepository
from app.core.repositories.screens import ScreenRepository
from app.core.repositories.test_cases import TestCaseRepository
from app.core.services.screens import ScreenService
from tests.conftest import make_user
from tests.fakes import FakeSheetsGateway


def test_failed_assignment_hook_removes_the_new_screen(
    gateway: FakeSheetsGateway, redis: fakeredis.FakeRedis
) -> None:
    """Giao việc lỗi thì không để lại màn hình mồ côi (không ai được giao)."""
    sheet = "project-sheet"
    gateway.data.setdefault(sheet, {})
    bootstrap_project_spreadsheet(gateway, sheet)
    pid = "PRJ-0001"
    modules = ModuleRepository(gateway, sheet, redis, pid)
    module = modules.create(name="Tài khoản", description="")
    screens = ScreenRepository(gateway, sheet, redis, pid)

    def boom(screen_ids: list[str], module_id: str) -> None:
        raise RuntimeError("Google lỗi")

    service = ScreenService(
        screens,
        AssignmentRepository(gateway, sheet, redis, pid),
        TestCaseRepository(gateway, sheet, redis, pid),
        AuditLogRepository(gateway, sheet),
        modules=modules,
        on_screens_added=boom,
    )

    with pytest.raises(RuntimeError):
        service.create_screen(
            make_user("lead@x.com", role=Role.QA_LEAD),
            name="Đăng nhập",
            description="",
            route="",
            code_paths=[],
            module_id=module.id,
        )

    assert screens.list_all() == []
