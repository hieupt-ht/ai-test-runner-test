"""Agent chỉ ghi kết quả bằng token riêng, đúng dự án và case đã duyệt."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.models.project import Project
from app.core.models.user import Role
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import ProjectRepository
from app.core.repositories.users import UserRepository
from tests.conftest import SHEET_B, client_for, make_project, make_user
from tests.fakes import FakeOAuth, FakeSheetsGateway
from tests.test_test_cases_api import NEXT_WEEK, create

RESULT = {"test_case_id": "TC-000001", "status": "PASS", "reason": "Đạt"}


@pytest.fixture
def project(
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
    users: UserRepository,
) -> Project:
    users.create(make_user("an@x.com", role=Role.TESTER))
    return make_project(projects, members, gateway, member_emails=("an@x.com", "lead@x.com"))


@pytest.fixture
def lead(app: FastAPI, oauth: FakeOAuth, users: UserRepository, project: Project) -> TestClient:
    browser = client_for(app, oauth, users, "lead@x.com", Role.QA_LEAD)
    browser.post(f"/api/projects/{project.id}/screens", json={"name": "Đăng nhập"})
    browser.post(
        f"/api/projects/{project.id}/assignments",
        json={
            "screen_id": "SC-0001",
            "assignee_emails": ["an@x.com"],
            "deadline": NEXT_WEEK,
        },
    )
    return browser


@pytest.fixture
def an(app: FastAPI, oauth: FakeOAuth, users: UserRepository, lead: TestClient) -> TestClient:
    return client_for(app, oauth, users, "an@x.com", Role.TESTER)


def path(project: Project) -> str:
    return f"/api/agent/projects/{project.id}/results"


def approve_case(an: TestClient, lead: TestClient, project: Project) -> None:
    case = create(an, project).json()
    an.post(f"/api/projects/{project.id}/test-cases/{case['id']}/submit", json={"version": 1})
    lead.post(f"/api/projects/{project.id}/test-cases/{case['id']}/approve", json={"version": 2})


def test_disabled_when_token_not_configured_is_404(client: TestClient, project: Project) -> None:
    assert client.post(path(project), json={"results": [RESULT]}).status_code == 404
    assert client.post(path(project), json={"results": "bad"}).status_code == 404


def test_wrong_or_missing_token_is_401(app: FastAPI, client: TestClient, project: Project) -> None:
    app.state.settings.agent_api_token = "test-token"
    for headers in ({}, {"Authorization": "Bearer wrong"}):
        response = client.post(path(project), json={"results": [RESULT]}, headers=headers)
        assert response.status_code == 401
        assert response.json() == {"detail": "Token không hợp lệ"}
        invalid = client.post(path(project), json={"results": "bad"}, headers=headers)
        assert invalid.status_code == 401


def test_valid_token_writes_run_and_results_in_one_batch(
    app: FastAPI,
    client: TestClient,
    an: TestClient,
    lead: TestClient,
    project: Project,
    gateway: FakeSheetsGateway,
) -> None:
    app.state.settings.agent_api_token = "test-token"
    approve_case(an, lead, project)
    response = client.post(
        path(project), json={"results": [RESULT]}, headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 200
    assert response.json() == {"run_id": "RUN-0001", "written": 1, "ignored": []}
    assert gateway.calls.count("append:Results") == 1
    rows = gateway.data[project.spreadsheet_id]
    assert len(rows["Runs"]) == 2 and len(rows["Results"]) == 2
    run = dict(zip(rows["Runs"][0], rows["Runs"][1], strict=True))
    assert (run["status"], run["total"], run["passed"], run["failed"]) == (
        "COMPLETED",
        "1",
        "1",
        "0",
    )


def test_unknown_and_draft_cases_are_ignored(
    app: FastAPI,
    client: TestClient,
    an: TestClient,
    project: Project,
    gateway: FakeSheetsGateway,
) -> None:
    app.state.settings.agent_api_token = "test-token"
    create(an, project)
    response = client.post(
        path(project),
        json={
            "results": [
                RESULT,
                {"test_case_id": "TC-999999", "status": "FAIL", "reason": "Không thấy"},
            ]
        },
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    assert response.json()["written"] == 0
    assert len(response.json()["ignored"]) == 2
    assert len(gateway.data[project.spreadsheet_id]["Results"]) == 1


def test_over_200_results_is_422(app: FastAPI, client: TestClient, project: Project) -> None:
    app.state.settings.agent_api_token = "test-token"
    response = client.post(
        path(project),
        json={"results": [RESULT] * 201},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 422


def test_archived_project_is_409(
    app: FastAPI,
    client: TestClient,
    project: Project,
    projects: ProjectRepository,
) -> None:
    app.state.settings.agent_api_token = "test-token"
    projects.update(project.model_copy(update={"archived": True}))
    response = client.post(
        path(project), json={"results": [RESULT]}, headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 409


def test_token_never_in_response_or_logs(
    app: FastAPI,
    client: TestClient,
    project: Project,
    caplog: pytest.LogCaptureFixture,
) -> None:
    app.state.settings.agent_api_token = "private-test-token"
    response = client.post(
        path(project),
        json={"results": [RESULT]},
        headers={"Authorization": "Bearer private-test-token"},
    )
    assert "private-test-token" not in response.text
    assert "private-test-token" not in caplog.text


def test_same_case_id_in_other_project_writes_only_to_url_project(
    app: FastAPI,
    client: TestClient,
    an: TestClient,
    lead: TestClient,
    project: Project,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    app.state.settings.agent_api_token = "test-token"
    approve_case(an, lead, project)
    other = make_project(projects, members, gateway, sheet=SHEET_B)
    response = client.post(
        path(project), json={"results": [RESULT]}, headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 200
    assert len(gateway.data[project.spreadsheet_id]["Results"]) == 2
    assert len(gateway.data[other.spreadsheet_id]["Results"]) == 1


def test_case_of_other_project_is_ignored(
    app: FastAPI,
    client: TestClient,
    an: TestClient,
    lead: TestClient,
    project: Project,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    app.state.settings.agent_api_token = "test-token"
    other = make_project(
        projects, members, gateway, sheet=SHEET_B, member_emails=("an@x.com", "lead@x.com")
    )
    lead.post(f"/api/projects/{other.id}/screens", json={"name": "Đăng nhập"})
    lead.post(
        f"/api/projects/{other.id}/assignments",
        json={
            "screen_id": "SC-0001",
            "assignee_emails": ["an@x.com"],
            "deadline": NEXT_WEEK,
        },
    )
    approve_case(an, lead, other)
    response = client.post(
        path(project), json={"results": [RESULT]}, headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 200
    assert response.json()["written"] == 0
    assert response.json()["ignored"][0]["test_case_id"] == "TC-000001"


def test_two_posts_at_same_time_second_gets_409(
    app: FastAPI,
    client: TestClient,
    an: TestClient,
    lead: TestClient,
    project: Project,
    gateway: FakeSheetsGateway,
) -> None:
    app.state.settings.agent_api_token = "test-token"
    approve_case(an, lead, project)
    responses: list[int] = []
    headers = {"Authorization": "Bearer test-token"}

    def competing_post() -> None:
        responses.append(
            client.post(path(project), json={"results": [RESULT]}, headers=headers).status_code
        )

    gateway.after_next_read["Runs"] = competing_post
    first = client.post(path(project), json={"results": [RESULT]}, headers=headers)
    assert first.status_code == 200
    assert responses == [409]


def test_results_write_failure_marks_run_failed(
    app: FastAPI,
    client: TestClient,
    an: TestClient,
    lead: TestClient,
    project: Project,
    gateway: FakeSheetsGateway,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.state.settings.agent_api_token = "test-token"
    approve_case(an, lead, project)
    original = gateway.append_rows

    def fail_results(sheet: str, tab: str, rows: list[list[str]]) -> None:
        if tab == "Results":
            raise RuntimeError("Sheet tạm lỗi")
        original(sheet, tab, rows)

    monkeypatch.setattr(gateway, "append_rows", fail_results)
    response = client.post(
        path(project), json={"results": [RESULT]}, headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 503
    run_rows = gateway.data[project.spreadsheet_id]["Runs"]
    run = dict(zip(run_rows[0], run_rows[1], strict=True))
    assert run["status"] == "FAILED"
