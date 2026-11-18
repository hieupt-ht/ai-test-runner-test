"""Thùng rác dự án: xoá vĩnh viễn dự án đã lưu trữ (repository + API)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.models.user import Role
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import ProjectNotFoundError, ProjectRepository
from app.core.repositories.users import UserRepository
from tests.conftest import SHEET_A, SHEET_B, SYSTEM_SHEET_ID, client_for, make_project
from tests.fakes import FakeSheetsGateway


def test_delete_removes_project_row(
    projects: ProjectRepository, members: ProjectMemberRepository, gateway: FakeSheetsGateway
) -> None:
    project = make_project(projects, members, gateway)
    projects.delete(project.id)
    assert projects.get(project.id) is None
    assert projects.list_all() == []


def test_delete_unknown_project_raises(projects: ProjectRepository) -> None:
    with pytest.raises(ProjectNotFoundError):
        projects.delete("PRJ-9999")


def test_delete_frees_spreadsheet_for_reuse(
    projects: ProjectRepository, members: ProjectMemberRepository, gateway: FakeSheetsGateway
) -> None:
    project = make_project(projects, members, gateway)
    projects.delete(project.id)
    assert projects.find_by_spreadsheet(SHEET_A) is None


def test_remove_all_for_project_keeps_other_projects(
    projects: ProjectRepository, members: ProjectMemberRepository, gateway: FakeSheetsGateway
) -> None:
    a = make_project(projects, members, gateway, member_emails=("x@x.com", "y@x.com"))
    b = make_project(
        projects, members, gateway, name="Dự án B", sheet=SHEET_B, member_emails=("x@x.com",)
    )
    assert members.remove_all_for_project(a.id) == 2
    assert members.list_for_project(a.id) == []
    assert [m.email for m in members.list_for_project(b.id)] == ["x@x.com"]


def test_remove_all_for_project_with_no_members_returns_zero(
    projects: ProjectRepository, members: ProjectMemberRepository, gateway: FakeSheetsGateway
) -> None:
    project = make_project(projects, members, gateway)
    assert members.remove_all_for_project(project.id) == 0


# ----- API -----


def _delete(client: TestClient, project_id: str, name: str) -> int:
    # TestClient.delete không nhận body nên gọi request().
    return client.request("DELETE", f"/api/projects/{project_id}", json={"name": name}).status_code


def test_admin_deletes_archived_project(
    client_as_admin: TestClient,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    project = make_project(
        projects, members, gateway, member_emails=("lead@x.com",), archived=True
    )

    assert _delete(client_as_admin, project.id, "Dự án A") == 204

    assert client_as_admin.get("/api/projects").json() == []
    assert members.list_for_project(project.id) == []
    assert gateway.data[SYSTEM_SHEET_ID]["AuditLog"][-1][2:5] == ["DELETE", "project", project.id]


def test_delete_active_project_is_409(
    client_as_admin: TestClient,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    project = make_project(projects, members, gateway, member_emails=("lead@x.com",))

    assert _delete(client_as_admin, project.id, "Dự án A") == 409

    assert projects.get(project.id) is not None
    assert len(members.list_for_project(project.id)) == 1


def test_delete_with_wrong_name_is_422(
    client_as_admin: TestClient,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    project = make_project(
        projects, members, gateway, member_emails=("lead@x.com",), archived=True
    )

    assert _delete(client_as_admin, project.id, "Dự án B") == 422

    assert projects.get(project.id) is not None
    assert len(members.list_for_project(project.id)) == 1


def test_delete_name_is_trimmed(
    client_as_admin: TestClient,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    project = make_project(projects, members, gateway, archived=True)
    assert _delete(client_as_admin, project.id, "  Dự án A  ") == 204


def test_delete_requires_admin(
    app: FastAPI,
    users: UserRepository,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    project = make_project(
        projects, members, gateway, member_emails=("lead@x.com",), archived=True
    )
    lead = client_for(app, users, "lead@x.com", Role.QA_LEAD)

    assert _delete(lead, project.id, "Dự án A") == 403

    assert projects.get(project.id) is not None
    assert len(members.list_for_project(project.id)) == 1


def test_delete_unknown_project_is_404(client_as_admin: TestClient) -> None:
    assert _delete(client_as_admin, "PRJ-9999", "x") == 404


def test_delete_does_not_touch_other_project_members(
    client_as_admin: TestClient,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    a = make_project(projects, members, gateway, member_emails=("x@x.com",), archived=True)
    b = make_project(
        projects, members, gateway, name="Dự án B", sheet=SHEET_B, member_emails=("x@x.com",)
    )

    assert _delete(client_as_admin, a.id, "Dự án A") == 204

    assert [m.email for m in members.list_for_project(b.id)] == ["x@x.com"]
    assert projects.get(b.id) is not None


def test_spreadsheet_can_be_reused_after_delete(
    client_as_admin: TestClient,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    project = make_project(projects, members, gateway, archived=True)
    assert _delete(client_as_admin, project.id, "Dự án A") == 204

    body = {
        "name": "Dự án mới",
        "repo_full_name": "org/web",
        "branch": "main",
        "staging_url": "",
        "spreadsheet": SHEET_A,
    }
    assert client_as_admin.post("/api/projects", json=body).status_code == 201
