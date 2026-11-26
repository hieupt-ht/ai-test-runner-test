"""Nhập test case theo module: tự tạo màn hình còn thiếu, tự giao việc, quyền nhận module."""

from datetime import timedelta
from typing import Any

import pytest

from app.core.models.user import Role
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.modules import ModuleAssignmentRepository, ModuleRepository
from app.core.repositories.users import UserRepository
from app.core.services.case_import import ImportIssue
from app.core.services.module_work import ModuleWorkService
from app.core.services.notify import Notifier
from app.core.services.test_cases import (
    ImportModuleNotFoundError,
    ImportWriteError,
    TestCaseService,
)
from app.core.sheets.gateway import SheetAccessDeniedError
from app.core.time import today_in_vietnam
from tests.conftest import SYSTEM_SHEET_ID, make_user
from tests.test_case_import_service import AN, LEAD, VIEWER, Env, row
from tests.xlsx_helpers import make_xlsx

DEADLINE = today_in_vietnam() + timedelta(days=7)
CLAIM_FIRST = "Hãy nhận module trước khi nhập"


class ModuleEnv(Env):
    """Env có thêm module và các repository/service để nhập theo module."""

    def __init__(self) -> None:
        super().__init__()
        sheet = self.project.spreadsheet_id
        pid = self.project.id
        self.members_repo = ProjectMemberRepository(
            self.gateway, SYSTEM_SHEET_ID, self.redis, cache_ttl_seconds=300, lock_wait_seconds=0.1
        )
        self.users = UserRepository(
            self.gateway, SYSTEM_SHEET_ID, self.redis, cache_ttl_seconds=300, lock_wait_seconds=0.1
        )
        for user in (LEAD, AN, VIEWER):
            self.users.create(user)
        self.modules = ModuleRepository(self.gateway, sheet, self.redis, pid, lock_wait_seconds=0.1)
        self.module_assignments = ModuleAssignmentRepository(
            self.gateway, sheet, self.redis, pid, lock_wait_seconds=0.1
        )
        self.module_work = ModuleWorkService(
            project_id=pid,
            modules=self.modules,
            screens=self.screens,
            assignments=self.assignments,
            module_assignments=self.module_assignments,
            test_cases=self.test_cases,
            members=self.members_repo,
            users=self.users,
            audit_log=self.audit_log,
        )
        self.service = TestCaseService(
            project_id=pid,
            test_cases=self.test_cases,
            screens=self.screens,
            assignments=self.assignments,
            members=self.members_repo,
            status_updater=self.status_updater,
            audit_log=self.audit_log,
            notifier=Notifier(self.store),
            modules=self.modules,
            module_assignments=self.module_assignments,
            module_work=self.module_work,
        )

    def make_module(self, *existing_screens: str) -> str:
        module = self.modules.create(name="Tài khoản", description="")
        for name in existing_screens:
            self.screens.create(
                name=name, description="", route="", code_paths=[], module_id=module.id
            )
        return module.id

    def pairs(self) -> list[tuple[str, str]]:
        return sorted((a.screen_id, a.assignee_email) for a in self.assignments.list_all())

    def screens_in(self, module_id: str) -> list[str]:
        return sorted(s.name for s in self.screens.list_all() if s.module_id == module_id)


@pytest.fixture
def env() -> ModuleEnv:
    return ModuleEnv()


def test_tester_imports_into_claimed_module_creates_screens_and_assignments(
    env: ModuleEnv,
) -> None:
    module = env.make_module("Hồ sơ")  # SC-0003
    env.module_work.assign(AN, module_id=module, emails=[AN.email], deadline=DEADLINE)
    # Màn hình thêm thẳng vào Sheet (không qua móc), nên AN chưa được giao
    env.screens.create(name="Cài đặt", description="", route="", code_paths=[], module_id=module)
    data = make_xlsx(
        [
            row("A1", "Hồ sơ"),
            row("A2", "Cài đặt", title="Đổi mật khẩu"),
            row("A3", "Đăng ký", title="Đăng ký mới"),
            row("A4", " đăng ký ", title="Đăng ký lỗi"),
        ]
    )

    outcome = env.service.import_cases(AN, data, module_id=module)

    assert outcome.errors == []
    assert len(outcome.created) == 4
    assert env.screens_in(module) == ["Cài đặt", "Hồ sơ", "Đăng ký"]
    new_id = next(s.id for s in env.screens.list_all() if s.name == "Đăng ký")
    assert [c.screen_id for c in outcome.created].count(new_id) == 2
    assert (new_id, AN.email) in env.pairs()
    assert ("SC-0004", AN.email) in env.pairs()
    audit = env.gateway.data[env.project.spreadsheet_id]["AuditLog"][1:]
    assert [r[2:5] for r in audit if r[3] == "screen"] == [["CREATE", "screen", new_id]]


def test_tester_without_claim_gets_claim_first_error(env: ModuleEnv) -> None:
    module = env.make_module()
    data = make_xlsx([row("A1", "Đăng ký")])

    preview = env.service.preview_import(AN, data, module_id=module)
    outcome = env.service.import_cases(AN, data, module_id=module)

    assert preview.errors == [ImportIssue(row=None, message=CLAIM_FIRST)]
    assert outcome.errors == [ImportIssue(row=None, message=CLAIM_FIRST)]
    assert outcome.created == []
    assert env.screens_in(module) == []


def test_qa_imports_into_module_without_claim(env: ModuleEnv) -> None:
    module = env.make_module()
    data = make_xlsx([row("A1", "Đăng ký"), row("A2", "Hồ sơ", title="Khác")])

    outcome = env.service.import_cases(LEAD, data, module_id=module)

    assert outcome.errors == []
    assert len(outcome.created) == 2
    assert env.screens_in(module) == ["Hồ sơ", "Đăng ký"]
    assert env.pairs() == [("SC-0001", AN.email)]  # chỉ việc có sẵn từ đầu


def test_reimport_after_failed_case_write_reuses_screen(
    env: ModuleEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = env.make_module()
    data = make_xlsx([row("A1", "Đăng ký")])
    real_create_many = env.test_cases.create_many
    calls = {"n": 0}

    def flaky(items: Any, *, actor: str) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            raise SheetAccessDeniedError("x")
        return real_create_many(items, actor=actor)

    monkeypatch.setattr(env.test_cases, "create_many", flaky)
    with pytest.raises(ImportWriteError):
        env.service.import_cases(LEAD, data, module_id=module)
    assert env.screens_in(module) == ["Đăng ký"]

    outcome = env.service.import_cases(LEAD, data, module_id=module)

    assert len(outcome.created) == 1
    assert env.screens_in(module) == ["Đăng ký"]


def test_import_without_module_keeps_old_behaviour(env: ModuleEnv) -> None:
    data = make_xlsx([row("A1", "Màn hình lạ")])

    outcome = env.service.import_cases(LEAD, data)

    assert [e.message for e in outcome.errors] == ["Không tìm thấy màn hình này trong dự án"]
    assert len(env.screens.list_all()) == 2


def test_import_into_unknown_module_raises(env: ModuleEnv) -> None:
    with pytest.raises(ImportModuleNotFoundError):
        env.service.import_cases(LEAD, make_xlsx([row("A1", "X")]), module_id="MD-0999")
    with pytest.raises(ImportModuleNotFoundError):
        env.service.preview_import(LEAD, make_xlsx([row("A1", "X")]), module_id="MD-0999")


def test_new_screens_assigned_to_other_workers_skipping_inactive(env: ModuleEnv) -> None:
    module = env.make_module()
    other = make_user("binh@x.com", role=Role.TESTER)
    gone = make_user("gone@x.com", role=Role.TESTER)
    for user in (other, gone):
        env.users.create(user)
        env.members_repo.add(env.project.id, user.email)
    env.module_work.assign(
        LEAD, module_id=module, emails=[AN.email, other.email, gone.email], deadline=DEADLINE
    )
    env.users.update(gone.model_copy(update={"active": False}))

    outcome = env.service.import_cases(LEAD, make_xlsx([row("A1", "Đăng ký")]), module_id=module)

    new_id = outcome.created[0].screen_id
    assert {email for sid, email in env.pairs() if sid == new_id} == {AN.email, other.email}


def test_preview_returns_new_screens_and_writes_nothing(env: ModuleEnv) -> None:
    module = env.make_module()
    data = make_xlsx(
        [row("A1", "Đăng ký"), row("A2", " đăng ký ", title="Hai"), row("A3", "Hồ sơ")]
    )
    env.gateway.calls.clear()

    result = env.service.preview_import(LEAD, data, module_id=module)

    assert result.errors == []
    assert result.new_screens == ["Đăng ký", "Hồ sơ"]
    assert [c for c in env.gateway.calls if c.startswith(("append", "update", "delete"))] == []


def test_import_writes_each_tab_once(env: ModuleEnv) -> None:
    module = env.make_module("Hồ sơ")
    env.module_work.assign(AN, module_id=module, emails=[AN.email], deadline=DEADLINE)
    data = make_xlsx(
        [
            row("A1", "Hồ sơ"),
            row("A2", "Đăng ký", title="Một"),
            row("A3", "Thanh toán", title="Hai"),
        ]
    )
    env.gateway.calls.clear()

    env.service.import_cases(AN, data, module_id=module)

    for tab in ("Screens", "Assignments", "TestCases"):
        assert env.gateway.calls.count(f"append:{tab}") == 1, tab
