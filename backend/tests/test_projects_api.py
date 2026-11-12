from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.models.user import Role
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import ProjectRepository
from app.core.repositories.users import UserRepository
from app.core.sheets.schema import PROJECT_TABS
from tests.conftest import SHEET_A, SHEET_B, SYSTEM_SHEET_ID, client_for, make_project
from tests.fakes import FakeGitHub, FakeOAuth, FakeSheetsGateway

LINK_A = f"  https://docs.google.com/spreadsheets/d/{SHEET_A}/edit#gid=0 "


def create_body(**overrides: str) -> dict[str, str]:
    body = {
        "name": "Shop online",
        "repo_full_name": "org/web",
        "branch": "main",
        "staging_url": "",
        "spreadsheet": LINK_A,
    }
    body.update(overrides)
    return body


# ----- Tạo dự án -----


def test_admin_creates_project_and_tabs_are_bootstrapped(
    client_as_admin: TestClient, gateway: FakeSheetsGateway
) -> None:
    gateway.data[SHEET_A] = {}

    response = client_as_admin.post("/api/projects", json=create_body())

    assert response.status_code == 201
    project = response.json()
    assert project["id"] == "PRJ-0001"
    assert project["spreadsheet_id"] == SHEET_A
    for tab, columns in PROJECT_TABS.items():
        assert gateway.data[SHEET_A][tab][0] == columns
    audit = gateway.data[SYSTEM_SHEET_ID]["AuditLog"][-1]
    assert audit[2:5] == ["CREATE", "project", "PRJ-0001"]


def test_create_rejects_invalid_spreadsheet(client_as_admin: TestClient) -> None:
    response = client_as_admin.post("/api/projects", json=create_body(spreadsheet="abc"))

    assert response.status_code == 422
    assert response.json() == {"detail": "Link hoặc ID Google Sheet không hợp lệ"}


def test_create_rejects_system_or_used_spreadsheet(
    client_as_admin: TestClient,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    make_project(projects, members, gateway, sheet=SHEET_B)

    for sheet in (SYSTEM_SHEET_ID, SHEET_B):
        response = client_as_admin.post("/api/projects", json=create_body(spreadsheet=sheet))
        assert response.status_code == 409
        assert response.json() == {"detail": "Google Sheet này đã được dùng cho dự án khác"}


def test_create_rejects_unknown_repo_or_branch(client_as_admin: TestClient) -> None:
    unknown_repo = client_as_admin.post("/api/projects", json=create_body(repo_full_name="x/y"))
    unknown_branch = client_as_admin.post("/api/projects", json=create_body(branch="nope"))

    assert unknown_repo.status_code == 422
    assert unknown_repo.json() == {"detail": "Repo không có trong danh sách GitHub App được cài"}
    assert unknown_branch.status_code == 422
    assert unknown_branch.json() == {"detail": "Không tìm thấy branch nope trong repo org/web"}


def test_create_reports_missing_sheet_permission_with_sa_email(
    client_as_admin: TestClient, gateway: FakeSheetsGateway
) -> None:
    gateway.denied.add(SHEET_A)

    response = client_as_admin.post("/api/projects", json=create_body())

    assert response.status_code == 422
    assert "sa@test.iam.gserviceaccount.com" in response.json()["detail"]


def test_non_admin_cannot_create(client_as_qa_lead: TestClient) -> None:
    assert client_as_qa_lead.post("/api/projects", json=create_body()).status_code == 403


# ----- Xem dự án -----


def test_list_shows_only_member_projects_for_non_admin(
    client_as_tester: TestClient,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    make_project(projects, members, gateway, name="Của tôi", member_emails=("tester@x.com",))
    make_project(projects, members, gateway, name="Không phải", sheet=SHEET_B)

    response = client_as_tester.get("/api/projects")

    assert [project["name"] for project in response.json()] == ["Của tôi"]


def test_non_member_gets_404(
    client_as_tester: TestClient,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    project = make_project(projects, members, gateway)

    response = client_as_tester.get(f"/api/projects/{project.id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Không tìm thấy dự án"}


def test_detail_includes_permissions(
    client_as_qa_lead: TestClient,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    project = make_project(projects, members, gateway, member_emails=("lead@x.com",))

    permissions = client_as_qa_lead.get(f"/api/projects/{project.id}").json()["permissions"]

    assert "MANAGE_SCREENS" in permissions
    assert "MANAGE_PROJECTS" not in permissions


def test_archived_project_hidden_for_non_admin(
    app: FastAPI,
    oauth: FakeOAuth,
    users: UserRepository,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    project = make_project(
        projects, members, gateway, member_emails=("lead@x.com",), archived=True
    )
    lead = client_for(app, oauth, users, "lead@x.com", Role.QA_LEAD)
    admin = client_for(app, oauth, users, "admin@x.com", Role.ADMIN)

    assert lead.get("/api/projects").json() == []
    assert lead.get(f"/api/projects/{project.id}").status_code == 404
    assert admin.get(f"/api/projects/{project.id}").json()["archived"] is True


# ----- Sửa dự án -----


def test_admin_renames_and_archives(
    client_as_admin: TestClient,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    project = make_project(projects, members, gateway)

    response = client_as_admin.patch(
        f"/api/projects/{project.id}", json={"name": "Tên mới", "archived": True}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Tên mới"
    assert response.json()["archived"] is True


def test_change_to_unknown_branch_is_422(
    client_as_admin: TestClient,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    project = make_project(projects, members, gateway)

    response = client_as_admin.patch(f"/api/projects/{project.id}", json={"branch": "nope"})

    assert response.status_code == 422


# ----- GitHub và service account -----


def test_list_github_repositories_and_branches(client_as_admin: TestClient) -> None:
    repos = client_as_admin.get("/api/github/repositories").json()
    branches = client_as_admin.get("/api/github/repositories/org/web/branches").json()

    assert [repo["full_name"] for repo in repos] == ["org/api", "org/web"]
    assert branches == ["develop", "main"]


def test_github_not_configured_is_503(app: FastAPI, client_as_admin: TestClient) -> None:
    app.state.services.github = None

    response = client_as_admin.get("/api/github/repositories")

    assert response.status_code == 503
    assert response.json() == {"detail": "Chưa cấu hình GitHub App. Xem README."}


def test_service_account_email(client_as_admin: TestClient, github: FakeGitHub) -> None:
    response = client_as_admin.get("/api/settings/service-account")

    assert response.json() == {"email": "sa@test.iam.gserviceaccount.com"}


def test_admin_can_clear_staging_url(
    client_as_admin: TestClient,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    project = make_project(projects, members, gateway)
    client_as_admin.patch(f"/api/projects/{project.id}", json={"staging_url": "https://st.x.com"})

    response = client_as_admin.patch(f"/api/projects/{project.id}", json={"staging_url": ""})

    assert response.json()["staging_url"] == ""
