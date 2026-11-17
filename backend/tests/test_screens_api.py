import fakeredis
import pytest
from fastapi.testclient import TestClient

from app.core.models.project import Project
from app.core.models.test_case import Priority, Severity, TestCaseContent, TestStep
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import ProjectRepository
from app.core.repositories.test_cases import TestCaseRepository
from tests.conftest import SHEET_A, make_project
from tests.fakes import FakeSheetsGateway


@pytest.fixture
def project(
    projects: ProjectRepository, members: ProjectMemberRepository, gateway: FakeSheetsGateway
) -> Project:
    return make_project(
        projects, members, gateway, member_emails=("lead@x.com", "tester@x.com")
    )


def screens_url(project: Project) -> str:
    return f"/api/projects/{project.id}/screens"


def login_screen(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "name": "Đăng nhập",
        "description": "Màn hình đăng nhập",
        "route": "/login",
        "code_paths": ["src/pages/login.tsx", "  api/auth/ "],
    }
    body.update(overrides)
    return body


def test_create_list_update_delete_screen(
    client_as_qa_lead: TestClient, project: Project
) -> None:
    first = client_as_qa_lead.post(screens_url(project), json=login_screen())
    second = client_as_qa_lead.post(screens_url(project), json=login_screen(name="Giỏ hàng"))

    assert first.status_code == 201
    assert first.json()["id"] == "SC-0001"
    assert first.json()["code_paths"] == ["src/pages/login.tsx", "api/auth/"]
    assert second.json()["id"] == "SC-0002"

    updated = client_as_qa_lead.patch(
        f"{screens_url(project)}/SC-0001", json={"name": "Đăng nhập mới", "code_paths": []}
    )
    assert updated.json()["name"] == "Đăng nhập mới"
    assert updated.json()["code_paths"] == []
    assert updated.json()["route"] == "/login"  # trường không gửi thì giữ nguyên

    assert client_as_qa_lead.delete(f"{screens_url(project)}/SC-0002").status_code == 204
    listed = client_as_qa_lead.get(screens_url(project)).json()
    assert [screen["id"] for screen in listed] == ["SC-0001"]


@pytest.mark.parametrize("bad", ["/etc/passwd", "../secret", "src/../x", "a\\b", "", "x" * 201])
def test_rejects_bad_code_paths(client_as_qa_lead: TestClient, project: Project, bad: str) -> None:
    response = client_as_qa_lead.post(screens_url(project), json=login_screen(code_paths=[bad]))

    assert response.status_code == 422


def test_unknown_screen_is_404(client_as_qa_lead: TestClient, project: Project) -> None:
    response = client_as_qa_lead.patch(f"{screens_url(project)}/SC-0999", json={"name": "X"})

    assert response.status_code == 404
    assert response.json() == {"detail": "Không tìm thấy màn hình"}


def test_tester_can_view_but_not_create(client_as_tester: TestClient, project: Project) -> None:
    assert client_as_tester.get(screens_url(project)).status_code == 200
    assert client_as_tester.post(screens_url(project), json=login_screen()).status_code == 403


def test_non_member_gets_404(
    client_as_tester: TestClient,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    other = make_project(projects, members, gateway)

    assert client_as_tester.get(screens_url(other)).status_code == 404


def test_archived_project_rejects_writes(
    client_as_admin: TestClient,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    archived = make_project(projects, members, gateway, archived=True)

    response = client_as_admin.post(screens_url(archived), json=login_screen())

    assert response.status_code == 409
    assert response.json() == {"detail": "Dự án đã được lưu trữ"}


def test_writes_go_to_project_audit_log(
    client_as_qa_lead: TestClient, project: Project, gateway: FakeSheetsGateway
) -> None:
    client_as_qa_lead.post(screens_url(project), json=login_screen())

    audit = gateway.data[SHEET_A]["AuditLog"][-1]
    assert audit[1:5] == ["lead@x.com", "CREATE", "screen", "SC-0001"]


def test_delete_screen_with_test_case_is_409(
    client_as_qa_lead: TestClient,
    project: Project,
    gateway: FakeSheetsGateway,
    redis: fakeredis.FakeRedis,
) -> None:
    created = client_as_qa_lead.post(screens_url(project), json=login_screen())
    screen_id = created.json()["id"]
    TestCaseRepository(gateway, SHEET_A, redis, project.id, lock_wait_seconds=0.1).create(
        screen_id=screen_id,
        content=TestCaseContent(
            title="Đăng nhập đúng",
            steps=[TestStep(action="Bấm Đăng nhập", expected="")],
            expected_result="Vào được trang chủ",
            severity=Severity.LOW,
            priority=Priority.P1,
        ),
        actor="tester@x.com",
    )

    response = client_as_qa_lead.delete(f"{screens_url(project)}/{screen_id}")

    assert response.status_code == 409
    assert response.json() == {"detail": "Màn hình đang có test case, không xoá được"}
    assert len(client_as_qa_lead.get(screens_url(project)).json()) == 1


def test_screen_dev_owner_defaults_empty_and_round_trips(
    project: Project, gateway: FakeSheetsGateway, redis: fakeredis.FakeRedis
) -> None:
    from app.core.repositories.screens import ScreenRepository

    repo = ScreenRepository(gateway, SHEET_A, redis, project.id)
    screen = repo.create(name="Đăng nhập", description="", route="/login", code_paths=[])
    assert screen.dev_owner == ""

    repo.update(screen.model_copy(update={"dev_owner": "nguyenvana"}))

    saved = repo.get(screen.id)
    assert saved is not None and saved.dev_owner == "nguyenvana"
    # Dòng cũ không có ô dev_owner vẫn đọc ra ""
    gateway.data[SHEET_A]["Screens"][1] = gateway.data[SHEET_A]["Screens"][1][:6]
    repo._cache.invalidate()
    old = repo.get(screen.id)
    assert old is not None and old.dev_owner == ""


def test_dev_owner_is_saved_without_leading_at(
    client_as_qa_lead: TestClient, project: Project
) -> None:
    created = client_as_qa_lead.post(
        screens_url(project), json=login_screen(dev_owner="@nguyenvana")
    )
    assert created.status_code == 201
    assert created.json()["dev_owner"] == "nguyenvana"

    updated = client_as_qa_lead.patch(
        f"{screens_url(project)}/{created.json()['id']}", json={"dev_owner": "@tran-b"}
    )
    assert updated.json()["dev_owner"] == "tran-b"


def test_dev_owner_can_be_cleared(client_as_qa_lead: TestClient, project: Project) -> None:
    created = client_as_qa_lead.post(screens_url(project), json=login_screen(dev_owner="abc"))
    cleared = client_as_qa_lead.patch(
        f"{screens_url(project)}/{created.json()['id']}", json={"dev_owner": ""}
    )
    assert cleared.status_code == 200
    assert cleared.json()["dev_owner"] == ""


@pytest.mark.parametrize("bad", ["a b", "-abc", "abc-", "a--b", "x" * 40, "a/b"])
def test_bad_dev_owner_is_422(client_as_qa_lead: TestClient, project: Project, bad: str) -> None:
    response = client_as_qa_lead.post(screens_url(project), json=login_screen(dev_owner=bad))
    assert response.status_code == 422


def test_tester_cannot_set_dev_owner(client_as_tester: TestClient, project: Project) -> None:
    response = client_as_tester.post(screens_url(project), json=login_screen(dev_owner="abc"))
    assert response.status_code == 403
