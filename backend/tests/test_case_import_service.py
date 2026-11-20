"""Nhập test case hàng loạt từ file Excel: quyền, hết-hoặc-không, số lượt gọi Sheet, thông báo."""

from datetime import timedelta
from typing import Any

import fakeredis
import pytest

from app.core.assignment_status import AssignmentStatusUpdater
from app.core.models.assignment import AssignmentStatus
from app.core.models.test_case import (
    ExecutionMode,
    Priority,
    Severity,
    TestCaseContent,
    TestCaseStatus,
    TestStep,
)
from app.core.models.user import Role
from app.core.notifications import NotificationStore
from app.core.repositories.assignments import AssignmentRepository
from app.core.repositories.audit_log import AuditLogRepository
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import ProjectRepository
from app.core.repositories.screens import ScreenRepository
from app.core.repositories.test_cases import TestCaseRepository
from app.core.services.case_import import ImportIssue, ParsedCase, ParseResult, check_import
from app.core.services.notify import Notifier
from app.core.services.test_cases import (
    ImportWriteError,
    TestCasePermissionError,
    TestCaseService,
)
from app.core.sheets.gateway import SheetAccessDeniedError
from app.core.sheets.schema import SYSTEM_TABS
from app.core.time import today_in_vietnam
from tests.conftest import SYSTEM_SHEET_ID, make_project, make_user
from tests.fakes import FakeSheetsGateway, make_http_error
from tests.xlsx_helpers import HEADERS, make_xlsx

LEAD = make_user("lead@x.com", role=Role.QA_LEAD)
AN = make_user("an@x.com", role=Role.TESTER)
VIEWER = make_user("viewer@x.com", role=Role.VIEWER)

NOT_ASSIGNED = "Bạn chưa được giao màn hình này"


def row(group: str, screen: str, title: str = "Đăng nhập đúng", step: str = "Bấm") -> list[Any]:
    """Một dòng đủ 16 cột theo mẫu (cột không nêu thì để trống)."""
    cells = {
        "Mã nhóm": group,
        "Màn hình": screen,
        "Tiêu đề": title,
        "Bước làm": step,
        "Kết quả mong đợi": "Vào được",
        "Mức độ": "HIGH",
        "Ưu tiên": "P1",
    }
    return [cells.get(header, "") for header in HEADERS]


class Env:
    """Một dự án mới tinh: Sheet giả, Redis giả, 2 màn hình, an được giao SC-0001."""

    def __init__(self) -> None:
        tabs = {tab: [list(columns)] for tab, columns in SYSTEM_TABS.items()}
        self.gateway = FakeSheetsGateway({SYSTEM_SHEET_ID: tabs})
        self.redis = fakeredis.FakeRedis()
        projects = ProjectRepository(
            self.gateway, SYSTEM_SHEET_ID, self.redis, cache_ttl_seconds=300, lock_wait_seconds=0.1
        )
        members = ProjectMemberRepository(
            self.gateway, SYSTEM_SHEET_ID, self.redis, cache_ttl_seconds=300, lock_wait_seconds=0.1
        )
        self.project = make_project(
            projects, members, self.gateway, member_emails=(LEAD.email, AN.email, VIEWER.email)
        )
        sheet = self.project.spreadsheet_id
        pid = self.project.id
        self.screens = ScreenRepository(self.gateway, sheet, self.redis, pid, lock_wait_seconds=0.1)
        self.assignments = AssignmentRepository(
            self.gateway, sheet, self.redis, pid, lock_wait_seconds=0.1
        )
        self.test_cases = TestCaseRepository(
            self.gateway, sheet, self.redis, pid, lock_wait_seconds=0.1
        )
        self.audit_log = AuditLogRepository(self.gateway, sheet)
        self.store = NotificationStore(self.redis)
        self.status_updater = AssignmentStatusUpdater(self.assignments, self.test_cases)
        self.service = TestCaseService(
            project_id=pid,
            test_cases=self.test_cases,
            screens=self.screens,
            assignments=self.assignments,
            members=members,
            status_updater=self.status_updater,
            audit_log=self.audit_log,
            notifier=Notifier(self.store),
        )
        self.screens.create(name="Đăng nhập", description="", route="", code_paths=[])
        self.screens.create(name="Giỏ hàng", description="", route="", code_paths=[])
        self.assign("SC-0001", AN.email)

    def assign(self, screen_id: str, email: str) -> None:
        self.assignments.create(
            screen_id=screen_id,
            assignee_email=email,
            deadline=today_in_vietnam() + timedelta(days=7),
        )

    def audit_actions(self) -> list[str]:
        rows = self.gateway.data[self.project.spreadsheet_id]["AuditLog"][1:]
        return [r[2] for r in rows]

    def appends(self) -> list[str]:
        return [c for c in self.gateway.calls if c in ("append:TestCases", "append:AuditLog")]


@pytest.fixture
def env() -> Env:
    return Env()


def test_lead_imports_all_screens(env: Env) -> None:
    data = make_xlsx([row("A1", "SC-0001"), row("A2", "Giỏ hàng", title="Thêm vào giỏ")])

    outcome = env.service.import_cases(LEAD, data)

    assert outcome.errors == []
    assert [c.screen_id for c in outcome.created] == ["SC-0001", "SC-0002"]
    for case in outcome.created:
        assert case.execution_mode == ExecutionMode.MANUAL
        assert case.status == TestCaseStatus.DRAFT
        assert case.created_by == "lead@x.com"
        assert case.version == 1
    assert len(env.test_cases.list_all()) == 2
    assert env.audit_actions() == ["IMPORT", "IMPORT"]
    history = env.service.history(outcome.created[0].id)
    assert history[0].diff["title"] == "Đăng nhập đúng"


def test_tester_cannot_import_unassigned_screen(env: Env) -> None:
    data = make_xlsx([row("A1", "SC-0001"), row("A2", "SC-0002")])

    outcome = env.service.import_cases(AN, data)

    assert outcome.created == []
    assert outcome.errors == [ImportIssue(row=3, column="Màn hình", message=NOT_ASSIGNED)]
    assert env.test_cases.list_all() == []


def test_tester_imports_assigned_screen(env: Env) -> None:
    outcome = env.service.import_cases(AN, make_xlsx([row("A1", "SC-0001")]))

    assert [c.created_by for c in outcome.created] == ["an@x.com"]


def test_viewer_cannot_preview_or_import(env: Env) -> None:
    data = make_xlsx([row("A1", "SC-0001")])
    with pytest.raises(TestCasePermissionError):
        env.service.preview_import(VIEWER, data)
    with pytest.raises(TestCasePermissionError):
        env.service.import_cases(VIEWER, data)


def test_errors_write_nothing(env: Env) -> None:
    data = make_xlsx([row("A1", "SC-0001"), row("A2", "SC-0001", title="")])
    env.gateway.calls.clear()

    outcome = env.service.import_cases(LEAD, data)

    assert outcome.created == []
    assert [(e.row, e.column) for e in outcome.errors] == [(3, "Tiêu đề")]
    assert env.test_cases.list_all() == []
    assert env.audit_actions() == []
    assert env.appends() == []


def test_screen_deleted_between_preview_and_import(env: Env) -> None:
    data = make_xlsx([row("A1", "SC-0001"), row("A2", "SC-0002")])
    assert env.service.preview_import(LEAD, data).errors == []

    env.screens.delete("SC-0002")
    env.gateway.calls.clear()
    outcome = env.service.import_cases(LEAD, data)

    assert outcome.created == []
    assert [(e.row, e.column) for e in outcome.errors] == [(3, "Màn hình")]
    assert env.test_cases.list_all() == []
    assert env.appends() == []


def test_duplicate_title_warns_not_blocks(env: Env) -> None:
    existing = TestCaseContent(
        title="Đăng nhập đúng",
        steps=[TestStep(action="Bấm", expected="")],
        expected_result="Vào được",
        severity=Severity.HIGH,
        priority=Priority.P1,
    )
    env.service.create(LEAD, screen_id="SC-0001", content=existing)
    data = make_xlsx([row("A1", "SC-0001", title="  đăng NHẬP đúng ")])

    preview = env.service.preview_import(LEAD, data)
    assert preview.errors == []
    assert [w.message for w in preview.warnings] == ["Màn hình Đăng nhập đã có case cùng tiêu đề"]

    outcome = env.service.import_cases(LEAD, data)
    assert len(outcome.created) == 1
    assert len(env.test_cases.list_all()) == 2


def _import_calls(count: int) -> int:
    fresh = Env()
    rows = [row(f"G{i}", "SC-0001", title=f"Case {i}") for i in range(count)]
    data = make_xlsx(rows)
    fresh.gateway.calls.clear()
    outcome = fresh.service.import_cases(LEAD, data)
    assert len(outcome.created) == count
    return len(fresh.gateway.calls)


def test_import_call_count_constant() -> None:
    assert _import_calls(1) == _import_calls(100)


def test_assignment_status_refreshed_once_per_screen(env: Env) -> None:
    env.service.import_cases(LEAD, make_xlsx([row("A1", "SC-0001"), row("A2", "SC-0001")]))

    (assignment,) = env.assignments.list_all()
    assert assignment.status == AssignmentStatus.WRITING


def test_lead_import_notifies_assigned_testers_once(env: Env) -> None:
    env.assign("SC-0002", AN.email)
    env.assign("SC-0001", LEAD.email)  # người nhập không tự báo cho mình
    data = make_xlsx(
        [row("A1", "SC-0001"), row("A2", "SC-0002"), row("A3", "SC-0001", title="Sai mật khẩu")]
    )

    env.service.import_cases(LEAD, data)

    (notification,) = env.store.list(AN.email)
    assert notification.type == "cases_imported"
    assert notification.title == "Có 3 case mới cần chạy ở: Đăng nhập, Giỏ hàng"
    assert notification.link == f"/projects/{env.project.id}/test-cases"
    assert env.store.list(LEAD.email) == []


def test_tester_self_import_does_not_notify(env: Env) -> None:
    env.service.import_cases(AN, make_xlsx([row("A1", "SC-0001")]))

    assert env.store.list(AN.email) == []


def test_sheet_error_before_write_raises_import_write_error(env: Env) -> None:
    data = make_xlsx([row("A1", "SC-0001")])
    sheet = env.project.spreadsheet_id
    # Lần đọc tab TestCases (cuối cùng trước khi ghi) xong thì Sheet "mất quyền"
    env.gateway.after_next_read["TestCases"] = lambda: env.gateway.denied.add(sheet)

    with pytest.raises(ImportWriteError):
        env.service.import_cases(LEAD, data)

    env.gateway.denied.clear()
    assert env.test_cases.list_all() == []


def test_audit_failure_after_write_is_logged_only(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(entries: Any) -> None:
        raise SheetAccessDeniedError("sheet")

    monkeypatch.setattr(env.audit_log, "record_many", broken)

    outcome = env.service.import_cases(LEAD, make_xlsx([row("A1", "SC-0001")]))

    assert len(outcome.created) == 1
    assert len(env.test_cases.list_all()) == 1


def test_google_error_in_status_refresh_does_not_fail_import(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Google lỗi 429/5xx lúc tính lại trạng thái của MỘT màn hình: case đã ghi vẫn trả về,
    màn hình còn lại vẫn được tính lại, thông báo vẫn gửi (để người dùng không nhập lại)."""
    env.assign("SC-0002", AN.email)
    refreshed: list[str] = []

    def flaky(screen_id: str) -> None:
        if screen_id == "SC-0001":
            raise make_http_error(429)
        refreshed.append(screen_id)

    monkeypatch.setattr(env.status_updater, "refresh_screen", flaky)
    data = make_xlsx([row("A1", "SC-0001"), row("A2", "SC-0002")])

    outcome = env.service.import_cases(LEAD, data)

    assert len(outcome.created) == 2
    assert refreshed == ["SC-0002"]
    (notification,) = env.store.list(AN.email)
    assert notification.title == "Có 2 case mới cần chạy ở: Đăng nhập, Giỏ hàng"


def test_non_http_error_in_status_refresh_does_not_fail_import(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lỗi mạng (TimeoutError...) lúc tính lại trạng thái cũng không làm hỏng việc nhập:
    case đã ghi rồi, báo lỗi 500 sẽ khiến người dùng nhập lại và sinh case trùng."""

    def broken(screen_id: str) -> None:
        raise TimeoutError("mạng chậm")

    monkeypatch.setattr(env.status_updater, "refresh_screen", broken)

    outcome = env.service.import_cases(LEAD, make_xlsx([row("A1", "SC-0001")]))

    assert len(outcome.created) == 1
    assert len(env.test_cases.list_all()) == 1


# --- check_import (hàm thuần) ---


def _parsed(screen_id: str, title: str, row_number: int = 2) -> ParsedCase:
    content = TestCaseContent(
        title=title,
        steps=[TestStep(action="Bấm", expected="")],
        expected_result="Vào được",
        severity=Severity.HIGH,
        priority=Priority.P1,
    )
    return ParsedCase(
        group="A1",
        row=row_number,
        screen_id=screen_id,
        screen_name="Đăng nhập",
        title=title,
        step_count=1,
        content=content,
    )


def test_check_import_none_allows_every_screen() -> None:
    result = ParseResult(cases=[_parsed("SC-0009", "X")])

    assert check_import(result, existing=[], allowed_screen_ids=None).errors == []


def test_check_import_ignores_archived_and_deprecated_duplicates(env: Env) -> None:
    created = env.service.import_cases(LEAD, make_xlsx([row("A1", "SC-0001", title="X")]))
    (case,) = created.created
    archived = case.model_copy(update={"status": TestCaseStatus.ARCHIVED})
    deprecated = case.model_copy(update={"status": TestCaseStatus.DEPRECATED})
    result = ParseResult(cases=[_parsed("SC-0001", "x")])

    checked = check_import(result, existing=[archived, deprecated], allowed_screen_ids={"SC-0001"})

    assert checked.warnings == []
    assert checked.errors == []
