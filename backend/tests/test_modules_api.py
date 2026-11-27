from datetime import date

import fakeredis
import pytest
from fastapi.testclient import TestClient

from app.core.models.assignment import AssignmentStatus
from app.core.models.project import Project
from app.core.repositories.assignments import AssignmentRepository
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.modules import ModuleAssignmentRepository
from app.core.repositories.projects import ProjectRepository
from tests.conftest import SHEET_A, make_project
from tests.fakes import FakeSheetsGateway

DEADLINE = date(2026, 12, 1)


@pytest.fixture
def project(
    projects: ProjectRepository, members: ProjectMemberRepository, gateway: FakeSheetsGateway
) -> Project:
    return make_project(projects, members, gateway, member_emails=("lead@x.com", "tester@x.com"))


def modules_url(project: Project) -> str:
    return f"/api/projects/{project.id}/modules"


def screens_url(project: Project) -> str:
    return f"/api/projects/{project.id}/screens"


def make_module(client: TestClient, project: Project, name: str = "Tài khoản") -> dict:
    response = client.post(modules_url(project), json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def make_screen(
    client: TestClient, project: Project, name: str = "Đăng nhập", module_id: str = ""
) -> dict:
    response = client.post(screens_url(project), json={"name": name, "module_id": module_id})
    assert response.status_code == 201, response.text
    return response.json()


def test_qa_creates_lists_and_deletes_module(
    client_as_qa_lead: TestClient, project: Project
) -> None:
    created = make_module(client_as_qa_lead, project)
    assert created["id"] == "MD-0001"

    listed = client_as_qa_lead.get(modules_url(project)).json()
    assert [(m["id"], m["name"], m["screen_count"], m["workers"]) for m in listed] == [
        ("MD-0001", "Tài khoản", 0, [])
    ]

    renamed = client_as_qa_lead.patch(
        f"{modules_url(project)}/MD-0001", json={"name": "Người dùng"}
    )
    assert renamed.json()["name"] == "Người dùng"

    assert client_as_qa_lead.delete(f"{modules_url(project)}/MD-0001").status_code == 204
    assert client_as_qa_lead.get(modules_url(project)).json() == []


def test_duplicate_module_name_rejected(client_as_qa_lead: TestClient, project: Project) -> None:
    make_module(client_as_qa_lead, project, "Tài khoản")

    response = client_as_qa_lead.post(modules_url(project), json={"name": " tài khoản "})

    assert response.status_code == 422
    assert response.json() == {"detail": "Đã có module tên này"}


def test_tester_can_create_module(client_as_tester: TestClient, project: Project) -> None:
    # Luật mới (2026-11-27): tester tự tạo module, tạo xong tự nhận
    assert client_as_tester.post(modules_url(project), json={"name": "X"}).status_code == 201
    assert client_as_tester.get(modules_url(project)).status_code == 200


def test_delete_module_with_screens_is_409(client_as_qa_lead: TestClient, project: Project) -> None:
    module = make_module(client_as_qa_lead, project)
    make_screen(client_as_qa_lead, project, module_id=module["id"])

    response = client_as_qa_lead.delete(f"{modules_url(project)}/{module['id']}")

    assert response.status_code == 409
    assert response.json() == {"detail": "Module còn màn hình, hãy chuyển hoặc xoá màn hình trước"}


def test_delete_module_removes_its_module_assignments(
    client_as_qa_lead: TestClient,
    project: Project,
    gateway: FakeSheetsGateway,
    redis: fakeredis.FakeRedis,
) -> None:
    make_module(client_as_qa_lead, project, "A")
    make_module(client_as_qa_lead, project, "B")
    repo = ModuleAssignmentRepository(gateway, SHEET_A, redis, project.id)
    repo.create_many([("MD-0001", "tester@x.com", DEADLINE), ("MD-0002", "tester@x.com", DEADLINE)])

    assert client_as_qa_lead.delete(f"{modules_url(project)}/MD-0001").status_code == 204

    assert [item.module_id for item in repo.list_all()] == ["MD-0002"]


def test_module_unknown_is_404(client_as_qa_lead: TestClient, project: Project) -> None:
    assert client_as_qa_lead.delete(f"{modules_url(project)}/MD-0999").status_code == 404
    patched = client_as_qa_lead.patch(f"{modules_url(project)}/MD-0999", json={"name": "X"})
    assert patched.status_code == 404


def test_module_view_counts_screens_and_workers(
    client_as_qa_lead: TestClient,
    project: Project,
    gateway: FakeSheetsGateway,
    redis: fakeredis.FakeRedis,
) -> None:
    module = make_module(client_as_qa_lead, project)
    make_screen(client_as_qa_lead, project, "A", module["id"])
    make_screen(client_as_qa_lead, project, "B", module["id"])
    ModuleAssignmentRepository(gateway, SHEET_A, redis, project.id).create_many(
        [(module["id"], "tester@x.com", DEADLINE)]
    )

    view = client_as_qa_lead.get(modules_url(project)).json()[0]

    assert view["screen_count"] == 2
    assert view["workers"][0]["email"] == "tester@x.com"
    assert view["workers"][0]["deadline"] == "2026-12-01"
    assert view["workers"][0]["assignment_id"] == "MA-0001"


def test_screen_created_in_module(client_as_qa_lead: TestClient, project: Project) -> None:
    module = make_module(client_as_qa_lead, project)

    screen = make_screen(client_as_qa_lead, project, module_id=module["id"])

    assert screen["module_id"] == module["id"]


def test_screen_in_unknown_module_rejected(client_as_qa_lead: TestClient, project: Project) -> None:
    response = client_as_qa_lead.post(
        screens_url(project), json={"name": "X", "module_id": "MD-0999"}
    )

    assert response.status_code == 422


def test_move_screen_into_module_with_same_name_rejected(
    client_as_qa_lead: TestClient, project: Project
) -> None:
    module = make_module(client_as_qa_lead, project)
    make_screen(client_as_qa_lead, project, "Đăng nhập", module["id"])
    other = make_screen(client_as_qa_lead, project, "đăng nhập ")

    response = client_as_qa_lead.patch(
        f"{screens_url(project)}/{other['id']}", json={"module_id": module["id"]}
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Module đã có màn hình tên này"}


def test_duplicate_screen_name_in_same_module_rejected_on_create(
    client_as_qa_lead: TestClient, project: Project
) -> None:
    module = make_module(client_as_qa_lead, project)
    make_screen(client_as_qa_lead, project, "Đăng nhập", module["id"])

    response = client_as_qa_lead.post(
        screens_url(project), json={"name": "Đăng nhập", "module_id": module["id"]}
    )

    assert response.status_code == 422


def test_same_screen_name_in_two_modules_allowed(
    client_as_qa_lead: TestClient, project: Project
) -> None:
    first = make_module(client_as_qa_lead, project, "A")
    second = make_module(client_as_qa_lead, project, "B")

    make_screen(client_as_qa_lead, project, "Đăng nhập", first["id"])
    make_screen(client_as_qa_lead, project, "Đăng nhập", second["id"])


def test_delete_empty_screen_in_module_removes_assignments(
    client_as_qa_lead: TestClient,
    project: Project,
    gateway: FakeSheetsGateway,
    redis: fakeredis.FakeRedis,
) -> None:
    module = make_module(client_as_qa_lead, project)
    screen = make_screen(client_as_qa_lead, project, module_id=module["id"])
    assignments = AssignmentRepository(gateway, SHEET_A, redis, project.id)
    assignments.create(
        screen_id=screen["id"],
        assignee_email="tester@x.com",
        deadline=DEADLINE,
        status=AssignmentStatus.TODO,
    )

    response = client_as_qa_lead.delete(f"{screens_url(project)}/{screen['id']}")

    assert response.status_code == 204
    assert assignments.list_all() == []


def test_delete_screen_without_module_still_blocked_by_assignment(
    client_as_qa_lead: TestClient,
    project: Project,
    gateway: FakeSheetsGateway,
    redis: fakeredis.FakeRedis,
) -> None:
    screen = make_screen(client_as_qa_lead, project)
    AssignmentRepository(gateway, SHEET_A, redis, project.id).create(
        screen_id=screen["id"], assignee_email="tester@x.com", deadline=DEADLINE
    )

    response = client_as_qa_lead.delete(f"{screens_url(project)}/{screen['id']}")

    assert response.status_code == 409


def test_module_writes_go_to_audit_log(
    client_as_qa_lead: TestClient, project: Project, gateway: FakeSheetsGateway
) -> None:
    make_module(client_as_qa_lead, project)

    assert gateway.data[SHEET_A]["AuditLog"][-1][1:5] == [
        "lead@x.com",
        "CREATE",
        "module",
        "MD-0001",
    ]
