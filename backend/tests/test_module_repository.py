from datetime import date

import fakeredis
import pytest

from app.core.bootstrap import bootstrap_project_spreadsheet
from app.core.models.assignment import AssignmentStatus
from app.core.repositories.assignments import AssignmentRepository
from app.core.repositories.modules import ModuleAssignmentRepository, ModuleRepository
from app.core.repositories.screens import ScreenRepository
from tests.fakes import FakeSheetsGateway

SHEET = "project-sheet"
DEADLINE = date(2026, 12, 1)


@pytest.fixture
def parts(
    gateway: FakeSheetsGateway, redis: fakeredis.FakeRedis
) -> tuple[FakeSheetsGateway, ModuleRepository, ModuleAssignmentRepository, ScreenRepository]:
    gateway.data.setdefault(SHEET, {})
    bootstrap_project_spreadsheet(gateway, SHEET)
    args = (gateway, SHEET, redis, "p1")
    return (
        gateway,
        ModuleRepository(*args),
        ModuleAssignmentRepository(*args),
        ScreenRepository(*args),
    )


def test_create_module_gets_md_id(parts) -> None:
    _, modules, _, _ = parts

    module = modules.create(name="Tài khoản", description="")

    assert module.id == "MD-0001"
    assert [m.id for m in modules.list_all()] == ["MD-0001"]


def test_module_assignments_create_many_writes_once(parts) -> None:
    gateway, _, module_assignments, _ = parts

    created = module_assignments.create_many(
        [
            ("MD-0001", "a@x.com", DEADLINE),
            ("MD-0001", "b@x.com", DEADLINE),
            ("MD-0002", "a@x.com", DEADLINE),
        ]
    )

    assert [m.id for m in created] == ["MA-0001", "MA-0002", "MA-0003"]
    assert gateway.calls.count("append:ModuleAssignments") == 1


def test_screen_create_many_sets_module_and_writes_once(parts) -> None:
    gateway, _, _, screens = parts

    created = screens.create_many(["Đăng ký", "Hồ sơ"], module_id="MD-0001")

    assert [s.module_id for s in created] == ["MD-0001", "MD-0001"]
    assert [s.description for s in created] == ["", ""]
    assert [s.route for s in created] == ["", ""]
    assert [s.code_paths for s in created] == [[], []]
    assert gateway.calls.count("append:Screens") == 1
    assert [s.name for s in screens.list_all()] == ["Đăng ký", "Hồ sơ"]


def test_screen_lock_is_reentrant(parts) -> None:
    _, _, _, screens = parts

    with screens.lock():
        screens.create(name="A", description="", route="", code_paths=[])
        screens.create_many(["B"], module_id="")

    assert len(screens.list_all()) == 2


def test_assignment_create_many_and_delete_many(parts, gateway, redis) -> None:
    gateway_, *_ = parts
    assignments = AssignmentRepository(gateway_, SHEET, redis, "p1")

    created = assignments.create_many(
        [
            ("SC-0001", "a@x.com", DEADLINE, AssignmentStatus.TODO),
            ("SC-0002", "a@x.com", DEADLINE, AssignmentStatus.TODO),
            ("SC-0003", "b@x.com", DEADLINE, AssignmentStatus.TODO),
        ]
    )
    assert [a.id for a in created] == ["AS-0001", "AS-0002", "AS-0003"]

    assignments.delete_many(["AS-0001", "AS-0003"])

    assert [a.id for a in assignments.list_all()] == ["AS-0002"]


def test_assignment_update_many(parts, redis) -> None:
    gateway_, *_ = parts
    assignments = AssignmentRepository(gateway_, SHEET, redis, "p1")
    created = assignments.create_many([("SC-0001", "a@x.com", DEADLINE, AssignmentStatus.TODO)])

    assignments.update_many([created[0].model_copy(update={"deadline": date(2026, 12, 9)})])

    assert assignments.list_all()[0].deadline == date(2026, 12, 9)


def test_module_assignment_delete_and_update_many(parts) -> None:
    _, _, module_assignments, _ = parts
    created = module_assignments.create_many(
        [("MD-0001", "a@x.com", DEADLINE), ("MD-0001", "b@x.com", DEADLINE)]
    )

    module_assignments.update_many([created[1].model_copy(update={"deadline": date(2026, 12, 9)})])
    module_assignments.delete_many([created[0].id])

    rest = module_assignments.list_all()
    assert [(m.id, m.deadline) for m in rest] == [("MA-0002", date(2026, 12, 9))]


def test_old_screen_row_without_module_id_reads_empty(parts) -> None:
    gateway, _, _, screens = parts
    gateway.data[SHEET]["Screens"] = [
        [
            "id",
            "name",
            "description",
            "route",
            "code_paths",
            "created_at",
            "dev_owner",
            "media_json",
            "module_id",
        ],
        ["SC-0001", "Cũ", "", "", "[]", "2026-11-12T00:00:00Z", "", ""],
    ]

    assert screens.list_all()[0].module_id == ""


def test_delete_many_is_one_google_call(parts, redis) -> None:
    gateway_, _, module_assignments, _ = parts
    assignments = AssignmentRepository(gateway_, SHEET, redis, "p1")
    created = assignments.create_many(
        [(f"SC-000{n}", "a@x.com", DEADLINE, AssignmentStatus.TODO) for n in range(1, 5)]
    )
    rows = module_assignments.create_many([("MD-0001", f"t{n}@x.com", DEADLINE) for n in range(3)])
    gateway_.calls.clear()

    assignments.delete_many([created[0].id, created[2].id, created[3].id])
    module_assignments.delete_many([rows[0].id, rows[2].id])

    assert [a.id for a in assignments.list_all()] == [created[1].id]
    assert [m.id for m in module_assignments.list_all()] == [rows[1].id]
    assert gateway_.calls.count("delete_rows:Assignments") == 1
    assert gateway_.calls.count("delete_rows:ModuleAssignments") == 1
    assert not [c for c in gateway_.calls if c.startswith("delete:")]
