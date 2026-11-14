from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.project_scope import scope_for
from app.api.services import Services
from app.core.models.project import Project
from app.core.models.run import Result, ResultStatus, RunStatus
from app.core.models.test_case import (
    Priority,
    Severity,
    TestCaseContent,
    TestCaseStatus,
    TestStep,
)
from app.core.models.user import Role
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import ProjectRepository
from app.core.repositories.users import UserRepository
from app.core.run_queue import RunQueue
from tests.conftest import SHEET_B, client_for, make_project
from tests.fakes import FakeOAuth, FakeSheetsGateway

IN_PROGRESS = "Dự án đang có một lần chạy chưa xong"


@pytest.fixture
def project(
    projects: ProjectRepository, members: ProjectMemberRepository, gateway: FakeSheetsGateway
) -> Project:
    return make_project(
        projects,
        members,
        gateway,
        member_emails=("lead@x.com", "an@x.com", "viewer@x.com"),
    )


@pytest.fixture
def services(app: FastAPI, tmp_path: Path) -> Services:
    services: Services = app.state.services
    services.artifacts_dir = tmp_path
    return services


def approve_case(services: Services, project: Project, title: str = "Đăng nhập") -> str:
    scope = scope_for(services, project)
    content = TestCaseContent(
        title=title,
        steps=[TestStep(action="Mở")],
        expected_result="ổn",
        severity=Severity.HIGH,
        priority=Priority.P1,
    )
    created = scope.test_cases.create(screen_id="SC-0001", content=content, actor="lead@x.com")
    approved = created.model_copy(update={"status": TestCaseStatus.APPROVED})
    scope.test_cases.save(approved, expected_version=created.version, actor="lead@x.com")
    return created.id


@pytest.fixture
def lead(
    app: FastAPI, oauth: FakeOAuth, users: UserRepository, project: Project, services: Services
) -> TestClient:
    return client_for(app, oauth, users, "lead@x.com", Role.QA_LEAD)


@pytest.fixture
def tester(app: FastAPI, oauth: FakeOAuth, users: UserRepository, lead: TestClient) -> TestClient:
    return client_for(app, oauth, users, "an@x.com", Role.TESTER)


@pytest.fixture
def viewer(app: FastAPI, oauth: FakeOAuth, users: UserRepository, lead: TestClient) -> TestClient:
    return client_for(app, oauth, users, "viewer@x.com", Role.VIEWER)


def url(project: Project, suffix: str = "") -> str:
    return f"/api/projects/{project.id}/runs{suffix}"


def test_tester_cannot_start_run(tester: TestClient, project: Project, services: Services) -> None:
    approve_case(services, project)

    assert tester.post(url(project), json={"scope": {}}).status_code == 403
    assert tester.post(url(project, "/preview"), json={}).status_code == 403


def test_viewer_can_list_runs_but_not_start(
    viewer: TestClient, lead: TestClient, project: Project, services: Services
) -> None:
    approve_case(services, project)
    lead.post(url(project), json={"scope": {}})

    assert viewer.post(url(project), json={"scope": {}}).status_code == 403
    listed = viewer.get(url(project))
    assert listed.status_code == 200
    assert [run["id"] for run in listed.json()] == ["RUN-0001"]


def test_start_run_returns_201_and_job_in_queue(
    lead: TestClient, project: Project, services: Services
) -> None:
    case_id = approve_case(services, project)

    response = lead.post(url(project), json={"scope": {}})

    assert response.status_code == 201
    body = response.json()
    assert (body["id"], body["status"], body["total"]) == ("RUN-0001", "QUEUED", 1)
    assert body["triggered_by"] == "lead@x.com"
    job = RunQueue(services.redis).pop(timeout_seconds=1)
    assert job is not None
    assert job.case_ids == [case_id]


def test_second_start_returns_409(lead: TestClient, project: Project, services: Services) -> None:
    approve_case(services, project)
    lead.post(url(project), json={"scope": {}})

    second = lead.post(url(project), json={"scope": {}})

    assert second.status_code == 409
    assert second.json() == {"detail": IN_PROGRESS}


def test_start_without_approved_cases_is_422(lead: TestClient, project: Project) -> None:
    response = lead.post(url(project), json={"scope": {}})

    assert response.status_code == 422
    assert response.json() == {"detail": "Không có test case đã duyệt trong phạm vi này"}


def test_start_over_limit_is_422(lead: TestClient, project: Project, services: Services) -> None:
    services.max_cases_per_run = 1
    approve_case(services, project)
    approve_case(services, project, "Case 2")

    response = lead.post(url(project), json={"scope": {}})

    assert response.status_code == 422
    assert "vượt giới hạn 1 case" in response.json()["detail"]


def test_preview_returns_count(lead: TestClient, project: Project, services: Services) -> None:
    approve_case(services, project)
    approve_case(services, project, "Case 2")

    assert lead.post(url(project, "/preview"), json={}).json() == {"count": 2}
    only_other_screen = {"screen_ids": ["SC-0009"]}
    assert lead.post(url(project, "/preview"), json=only_other_screen).json() == {"count": 0}


def test_other_project_member_gets_404(
    app: FastAPI,
    oauth: FakeOAuth,
    users: UserRepository,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
    project: Project,
) -> None:
    other = make_project(projects, members, gateway, name="B", sheet=SHEET_B)
    outsider = client_for(app, oauth, users, "out@x.com", Role.QA_LEAD)

    assert outsider.get(url(project)).status_code == 404
    assert outsider.post(url(other), json={"scope": {}}).status_code == 404


def test_get_run_includes_results_with_titles(
    lead: TestClient, project: Project, services: Services
) -> None:
    case_id = approve_case(services, project, "Đăng nhập thành công")
    run_id = lead.post(url(project), json={"scope": {}}).json()["id"]
    scope = scope_for(services, project)
    scope.results.append_batch([
        Result(
            id=f"{run_id}-{case_id}",
            run_id=run_id,
            test_case_id=case_id,
            status=ResultStatus.FAIL,
            reason="Không thấy chữ",
            failed_step=2,
            screenshot=f"{run_id}/{case_id}.png",
            created_at=datetime(2026, 11, 14, tzinfo=UTC),
        )
    ])
    RunQueue(services.redis).set_note(project.id, run_id, "ghi chú thử")

    body = lead.get(url(project, f"/{run_id}")).json()

    assert body["note"] == "ghi chú thử"
    assert len(body["results"]) == 1
    result = body["results"][0]
    assert result["test_case_title"] == "Đăng nhập thành công"
    assert (result["status"], result["failed_step"]) == ("FAIL", 2)
    assert lead.get(url(project, "/RUN-9999")).json() == {"detail": "Không tìm thấy lần chạy"}


def test_cancel_returns_updated_run(
    lead: TestClient, tester: TestClient, project: Project, services: Services
) -> None:
    approve_case(services, project)
    run_id = lead.post(url(project), json={"scope": {}}).json()["id"]

    assert tester.post(url(project, f"/{run_id}/cancel")).status_code == 403
    response = lead.post(url(project, f"/{run_id}/cancel"))

    assert response.status_code == 200
    assert response.json()["status"] == RunStatus.CANCELLED.value
    assert lead.post(url(project, "/RUN-9999/cancel")).status_code == 404


def make_run_with_screenshot(
    lead: TestClient, project: Project, services: Services, tmp_path: Path
) -> str:
    approve_case(services, project)
    run_id = lead.post(url(project), json={"scope": {}}).json()["id"]
    folder = tmp_path / project.id / run_id
    folder.mkdir(parents=True)
    (folder / "TC-000001.png").write_bytes(b"\x89PNG fake")
    return run_id


def test_screenshot_served_for_own_run(
    lead: TestClient, viewer: TestClient, project: Project, services: Services, tmp_path: Path
) -> None:
    run_id = make_run_with_screenshot(lead, project, services, tmp_path)

    response = viewer.get(url(project, f"/{run_id}/screenshots/TC-000001.png"))

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == b"\x89PNG fake"


@pytest.mark.parametrize(
    "filename", ["..%2fsecret.png", "%2e%2e%2fsecret.png", "x.txt", "TC-000001.PNG", "a b.png"]
)
def test_screenshot_rejects_path_traversal_and_other_files(
    lead: TestClient, project: Project, services: Services, tmp_path: Path, filename: str
) -> None:
    run_id = make_run_with_screenshot(lead, project, services, tmp_path)
    (tmp_path / "secret.png").write_bytes("bí mật".encode())

    response = lead.get(url(project, f"/{run_id}/screenshots/{filename}"))

    assert response.status_code == 404
    assert "mật".encode() not in response.content


def test_screenshot_missing_file_is_404(
    lead: TestClient, project: Project, services: Services, tmp_path: Path
) -> None:
    run_id = make_run_with_screenshot(lead, project, services, tmp_path)

    assert lead.get(url(project, f"/{run_id}/screenshots/TC-999999.png")).status_code == 404


def test_screenshot_of_run_in_other_project_is_404(
    app: FastAPI,
    oauth: FakeOAuth,
    users: UserRepository,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
    lead: TestClient,
    project: Project,
    services: Services,
    tmp_path: Path,
) -> None:
    run_id = make_run_with_screenshot(lead, project, services, tmp_path)
    other = make_project(
        projects, members, gateway, name="B", sheet=SHEET_B, member_emails=("lead@x.com",)
    )

    response = lead.get(url(other, f"/{run_id}/screenshots/TC-000001.png"))

    assert response.status_code == 404


def test_same_run_id_in_two_projects_never_serves_the_other_projects_screenshot(
    lead: TestClient,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
    project: Project,
    services: Services,
    tmp_path: Path,
) -> None:
    """Mã run RUN-0001 có ở MỌI dự án; ảnh của dự án A không được lộ sang dự án B."""
    run_a = make_run_with_screenshot(lead, project, services, tmp_path)
    other = make_project(
        projects, members, gateway, name="B", sheet=SHEET_B, member_emails=("lead@x.com",)
    )
    approve_case(services, other)
    run_b = lead.post(url(other), json={"scope": {}}).json()["id"]
    assert run_a == run_b == "RUN-0001"

    in_a = lead.get(url(project, f"/{run_a}/screenshots/TC-000001.png"))
    in_b = lead.get(url(other, f"/{run_b}/screenshots/TC-000001.png"))

    assert in_a.status_code == 200
    assert in_b.status_code == 404


def test_run_note_of_one_project_is_not_shown_on_same_run_id_of_another(
    lead: TestClient,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
    project: Project,
    services: Services,
) -> None:
    approve_case(services, project)
    lead.post(url(project), json={"scope": {}})
    RunQueue(services.redis).set_note(project.id, "RUN-0001", "Bí mật của dự án A")
    other = make_project(
        projects, members, gateway, name="B", sheet=SHEET_B, member_emails=("lead@x.com",)
    )
    approve_case(services, other)
    lead.post(url(other), json={"scope": {}})

    body = lead.get(url(other, "/RUN-0001")).json()

    assert body["note"] == ""
