"""Agent chỉ ghi kết quả bằng token riêng, đúng dự án và case đã duyệt."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.project_scope import scope_for
from app.core.models.project import Project
from app.core.models.user import Role
from app.core.notifications import NotificationStore
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import ProjectRepository
from app.core.repositories.users import UserRepository
from tests.conftest import SHEET_B, client_for, make_project, make_user
from tests.fakes import FakeGitHub, FakeOAuth, FakeSheetsGateway
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


def test_agent_result_succeeds_when_notification_fails(
    app: FastAPI,
    client: TestClient,
    an: TestClient,
    lead: TestClient,
    project: Project,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.state.settings.agent_api_token = "test-token"
    approve_case(an, lead, project)
    calls = 0

    def fail(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("Redis lỗi")

    monkeypatch.setattr(NotificationStore, "add", fail)
    response = client.post(
        path(project), json={"results": [RESULT]}, headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 200
    assert calls >= 1
    assert response.json()["written"] == 1


@pytest.mark.parametrize("result_status", ["PASS", "FAIL"])
def test_agent_result_notifies_leads_and_failed_case_creator(
    app: FastAPI, client: TestClient, client_as_admin: TestClient,
    an: TestClient, lead: TestClient, project: Project, result_status: str,
) -> None:
    app.state.settings.agent_api_token = "test-token"
    approve_case(an, lead, project)
    response = client.post(
        path(project),
        json={"results": [{**RESULT, "status": result_status}]},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    store = app.state.services.notifications
    assert [item.type for item in store.list("lead@x.com") if item.type == "results_recorded"] == [
        "results_recorded"
    ]
    assert [item.type for item in store.list("admin@x.com") if item.type == "results_recorded"] == [
        "results_recorded"
    ]
    assert [item.type for item in store.list("an@x.com") if item.type == "results_recorded"] == (
        ["results_recorded"] if result_status == "FAIL" else []
    )


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


def test_result_comment_is_updated_and_issue_state_follows_pass_fail(
    app: FastAPI,
    client: TestClient,
    an: TestClient,
    lead: TestClient,
    project: Project,
    github: FakeGitHub,
) -> None:
    app.state.settings.agent_api_token = "test-token"
    case = create(an, project, test_data="email=secret@example.com,password=supersecret").json()
    an.post(f"/api/projects/{project.id}/test-cases/{case['id']}/submit", json={"version": 1})
    lead.post(f"/api/projects/{project.id}/test-cases/{case['id']}/approve", json={"version": 2})
    github.create_issue(
        project.repo_full_name,
        title="Test case",
        body="",
        labels=[f"tc:{case['id']}", "test-case"],
    )

    for result_status in ("PASS", "FAIL"):
        response = client.post(
            path(project),
            json={
                "results": [{
                    **RESULT,
                    "test_case_id": case["id"],
                    "status": result_status,
                    "reason": "email=secret@example.com; password=supersecret",
                    "evidence": "javascript:alert(1)",
                    "failed_step": 1 if result_status == "FAIL" else None,
                }]
            },
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 200
        issue_after_run = github.issues[project.repo_full_name][0][0]
        if result_status == "PASS":
            assert issue_after_run.state == "closed"
            assert "test: pass" in issue_after_run.labels
            assert "test: fail" not in issue_after_run.labels

    issue = github.issues[project.repo_full_name][0][0]
    comments = github.issue_comments[project.repo_full_name][issue.number]
    assert len(comments) == 1
    body = comments[0].body
    assert body.count("<!-- ai-test-runner-result -->") == 1
    assert "secret@example.com" not in body
    assert "supersecret" not in body
    assert "javascript:" not in body
    assert issue.state == "open"
    assert "test: fail" in issue.labels
    assert "test: pass" not in issue.labels
    assert github.calls.count("comments:create") == 1
    assert github.calls.count("comments:update") == 1
    assert github.labels[project.repo_full_name]["test: pass"] == "2da44e"
    assert github.labels[project.repo_full_name]["test: fail"] == "d73a4a"


def test_github_result_sync_failure_does_not_fail_app_write(
    app: FastAPI,
    client: TestClient,
    an: TestClient,
    lead: TestClient,
    project: Project,
    gateway: FakeSheetsGateway,
    github: FakeGitHub,
) -> None:
    app.state.settings.agent_api_token = "test-token"
    approve_case(an, lead, project)
    github.fail_with = RuntimeError("GitHub không khả dụng")

    response = client.post(
        path(project), json={"results": [RESULT]}, headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 200
    assert response.json()["written"] == 1
    assert len(gateway.data[project.spreadsheet_id]["Results"]) == 2


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


# ---------- Task 15: kết quả mở rộng (từng bước, video, môi trường) ----------

AUTH = {"Authorization": "Bearer test-token"}


def media(cloud: str, name: str = "a", kind: str = "image") -> dict[str, str]:
    return {
        "kind": kind,
        "url": f"https://res.cloudinary.com/{cloud}/{kind}/upload/{name}.png",
        "public_id": name,
    }


def stored_results(project: Project, gateway: FakeSheetsGateway) -> list[dict[str, str]]:
    rows = gateway.data[project.spreadsheet_id]["Results"]
    return [dict(zip(rows[0], row, strict=False)) for row in rows[1:]]


def post_results(
    app: FastAPI,
    client: TestClient,
    project: Project,
    results: list[dict[str, object]],
    **extra: object,
) -> object:
    app.state.settings.agent_api_token = "test-token"
    return client.post(path(project), json={"results": results, **extra}, headers=AUTH)


def test_old_string_evidence_still_accepted(
    app: FastAPI, client: TestClient, an: TestClient, lead: TestClient,
    project: Project, gateway: FakeSheetsGateway,
) -> None:
    approve_case(an, lead, project)
    response = post_results(
        app, client, project, [{**RESULT, "evidence": "https://example.com/a.png"}]
    )
    assert response.status_code == 200
    assert "https://example.com/a.png" in stored_results(project, gateway)[0]["evidence_json"]
    assert "legacy_url" in stored_results(project, gateway)[0]["evidence_json"]


def test_old_string_evidence_not_https_is_dropped(
    app: FastAPI, client: TestClient, an: TestClient, lead: TestClient,
    project: Project, gateway: FakeSheetsGateway,
) -> None:
    approve_case(an, lead, project)
    post_results(app, client, project, [{**RESULT, "evidence": "javascript:alert(1)"}])
    assert stored_results(project, gateway)[0]["evidence_json"] == ""


def test_new_evidence_and_steps_stored(
    app: FastAPI, client: TestClient, an: TestClient, lead: TestClient,
    project: Project, gateway: FakeSheetsGateway,
) -> None:
    app.state.services.cloud_name = "mine"
    approve_case(an, lead, project)
    response = post_results(
        app, client, project,
        [{
            **RESULT,
            "evidence": {
                "video": media("mine", "v", "video"),
                "screenshots": [media("mine", "s1")],
            },
            "step_results": [
                {"step_no": 1, "status": "PASS", "actual": "ok"},
                {"step_no": 2, "status": "FAIL", "screenshot": media("mine", "s2")},
            ],
            "actual_result": "Thấy lỗi",
            "environment": "Pixel 7 / Android 14",
            "executed_by": "codex-windows",
            "case_version": 3,
        }],
    )
    assert response.status_code == 200
    row = stored_results(project, gateway)[0]
    assert '"v"' in row["evidence_json"] and '"s1"' in row["evidence_json"]
    assert '"s2"' in row["step_results_json"]
    assert row["actual_result"] == "Thấy lỗi"
    assert row["environment"] == "Pixel 7 / Android 14"
    assert row["executed_by"] == "codex-windows"
    assert row["case_version"] == "3"


def test_foreign_cloud_rejected_and_no_run_created(
    app: FastAPI, client: TestClient, an: TestClient, lead: TestClient,
    project: Project, gateway: FakeSheetsGateway,
) -> None:
    app.state.services.cloud_name = "mine"
    approve_case(an, lead, project)
    response = post_results(
        app, client, project,
        [{**RESULT, "evidence": {"screenshots": [media("other")]}}],
    )
    assert response.status_code == 422
    assert len(gateway.data[project.spreadsheet_id]["Runs"]) == 1  # chỉ còn dòng tiêu đề
    assert len(gateway.data[project.spreadsheet_id]["Results"]) == 1


def test_dev_owner_snapshot_from_screen(
    app: FastAPI, client: TestClient, an: TestClient, lead: TestClient,
    project: Project, gateway: FakeSheetsGateway,
) -> None:
    approve_case(an, lead, project)
    screens = app.state.services
    scope = scope_for(screens, screens.projects.get(project.id))
    screen = scope.screens.list_all()[0]
    scope.screens.update(screen.model_copy(update={"dev_owner": "nguyenvana"}))
    post_results(app, client, project, [RESULT])
    assert stored_results(project, gateway)[0]["dev_owner"] == "nguyenvana"


def test_build_version_saved_on_run(
    app: FastAPI, client: TestClient, an: TestClient, lead: TestClient,
    project: Project, gateway: FakeSheetsGateway,
) -> None:
    approve_case(an, lead, project)
    post_results(app, client, project, [RESULT], build_version="1.4.2")
    rows = gateway.data[project.spreadsheet_id]["Runs"]
    run = dict(zip(rows[0], rows[1], strict=False))
    assert run["build_version"] == "1.4.2"


def test_sixth_run_prunes_oldest_evidence_and_deletes_files(
    app: FastAPI, client: TestClient, an: TestClient, lead: TestClient,
    project: Project, gateway: FakeSheetsGateway,
) -> None:
    app.state.services.cloud_name = "mine"
    deleted: list[str] = []

    class Janitor:
        def delete(self, items: list[object]) -> None:
            deleted.extend(item.public_id for item in items)  # type: ignore[attr-defined]

    app.state.services.media_janitor = Janitor()
    approve_case(an, lead, project)
    for n in range(1, 7):
        post_results(
            app, client, project,
            [{**RESULT, "evidence": {"screenshots": [media("mine", f"s{n}")]}}],
        )
    rows = stored_results(project, gateway)
    assert deleted == ["s1"]
    assert rows[0]["evidence_json"] == '{"pruned": true}'
    assert all("pruned" not in row["evidence_json"] for row in rows[1:])
