"""API ký upload: tester ký cho ảnh hướng dẫn, agent ký cho bằng chứng; không bao giờ lộ secret."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.media.cloudinary import CloudinarySigner
from app.core.media.drive import DriveError
from app.core.models.project import Project
from app.core.models.user import Role
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import ProjectRepository
from app.core.repositories.users import UserRepository
from tests.conftest import client_for, make_project, make_user
from tests.fakes import FakeDrive, FakeSheetsGateway

SECRET = "super-secret-value"
GUIDE = {"kind": "image", "purpose": "guide"}


@pytest.fixture
def project(
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
    users: UserRepository,
) -> Project:
    users.create(make_user("an@x.com", role=Role.TESTER))
    users.create(make_user("viewer@x.com", role=Role.VIEWER))
    return make_project(projects, members, gateway, member_emails=("an@x.com", "viewer@x.com"))


@pytest.fixture
def signer(app: FastAPI) -> CloudinarySigner:
    signer = CloudinarySigner("demo", "key123", SECRET)
    app.state.services.cloudinary_signer = signer
    return signer


@pytest.fixture
def an(app: FastAPI, users: UserRepository, project: Project) -> TestClient:
    return client_for(app, users, "an@x.com", Role.TESTER)


def sign_path(project: Project) -> str:
    return f"/api/projects/{project.id}/media/sign"


def agent_path(project: Project) -> str:
    return f"/api/agent/projects/{project.id}/media/sign"


def test_sign_endpoint_never_returns_secret(
    an: TestClient, project: Project, signer: CloudinarySigner
) -> None:
    response = an.post(sign_path(project), json={"kind": "video", "purpose": "guide"})

    assert response.status_code == 200
    body = response.json()
    assert body["folder"] == f"ai-test-runner/{project.id}/guide"
    assert body["resource_type"] == "video"
    assert body["api_key"] == "key123"
    assert "api_secret" not in body and SECRET not in json.dumps(body)


def test_media_sign_accepts_evidence_purpose(
    an: TestClient, project: Project, signer: CloudinarySigner
) -> None:
    """Tester chạy test tay được tải bằng chứng lên thư mục evidence của chính dự án."""
    response = an.post(sign_path(project), json={"kind": "image", "purpose": "evidence"})

    assert response.status_code == 200
    assert response.json()["folder"] == f"ai-test-runner/{project.id}/evidence"


def test_sign_rejects_unknown_purpose(
    an: TestClient, project: Project, signer: CloudinarySigner
) -> None:
    response = an.post(sign_path(project), json={"kind": "image", "purpose": "other"})

    assert response.status_code == 422


def test_viewer_cannot_sign(
    app: FastAPI,
    users: UserRepository,
    project: Project,
    signer: CloudinarySigner,
) -> None:
    viewer = client_for(app, users, "viewer@x.com", Role.VIEWER)
    assert viewer.post(sign_path(project), json=GUIDE).status_code == 403


def test_sign_503_when_not_configured(an: TestClient, project: Project) -> None:
    response = an.post(sign_path(project), json=GUIDE)
    assert response.status_code == 503
    assert response.json()["detail"] == "Chưa cấu hình Cloudinary"


def test_agent_sign_requires_token(
    app: FastAPI, client: TestClient, project: Project, signer: CloudinarySigner
) -> None:
    app.state.settings.agent_api_token = "agent-token"

    assert client.post(agent_path(project), json={"kind": "image"}).status_code == 401
    wrong = client.post(
        agent_path(project), json={"kind": "image"}, headers={"Authorization": "Bearer nope"}
    )
    assert wrong.status_code == 401


def test_agent_sign_uses_evidence_folder(
    app: FastAPI, client: TestClient, project: Project, signer: CloudinarySigner
) -> None:
    app.state.settings.agent_api_token = "agent-token"

    response = client.post(
        agent_path(project),
        json={"kind": "image"},
        headers={"Authorization": "Bearer agent-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["folder"] == f"ai-test-runner/{project.id}/evidence"
    assert SECRET not in json.dumps(body)


def test_agent_sign_404_when_token_not_configured(
    client: TestClient, project: Project, signer: CloudinarySigner
) -> None:
    assert client.post(agent_path(project), json={"kind": "image"}).status_code == 404


def test_agent_sign_503_when_cloudinary_not_configured(
    app: FastAPI, client: TestClient, project: Project
) -> None:
    app.state.settings.agent_api_token = "agent-token"
    response = client.post(
        agent_path(project),
        json={"kind": "image"},
        headers={"Authorization": "Bearer agent-token"},
    )
    assert response.status_code == 503


# ----- Dự án lưu ở Google Drive -----

PNG = ("a.png", b"abc", "image/png")


@pytest.fixture
def drive(app: FastAPI) -> FakeDrive:
    fake = FakeDrive()
    app.state.services.drive = fake
    return fake


@pytest.fixture
def drive_project(project: Project, projects: ProjectRepository) -> Project:
    return projects.update(project.model_copy(update={"storage": "drive"}))


def upload_path(project: Project) -> str:
    return f"/api/projects/{project.id}/media/upload"


def agent_upload_path(project: Project) -> str:
    return f"/api/agent/projects/{project.id}/media/upload"


def test_upload_to_drive_returns_media(
    an: TestClient, drive_project: Project, drive: FakeDrive
) -> None:
    response = an.post(upload_path(drive_project), files={"file": PNG}, data={"purpose": "guide"})

    assert response.status_code == 200
    assert response.json()["public_id"] == "F1"
    assert drive.uploads == [
        {"project_id": drive_project.id, "purpose": "guide", "kind": "image", "bytes": b"abc"}
    ]


def test_upload_rejects_wrong_type_before_calling_drive(
    an: TestClient, drive_project: Project, drive: FakeDrive
) -> None:
    files = {"file": ("a.exe", b"abc", "application/x-msdownload")}

    response = an.post(upload_path(drive_project), files=files, data={"purpose": "guide"})

    assert response.status_code == 415
    assert drive.uploads == []


def test_upload_rejects_too_large_before_calling_drive(
    an: TestClient, drive_project: Project, drive: FakeDrive
) -> None:
    big = ("a.png", b"x" * (10 * 1024 * 1024 + 1), "image/png")

    response = an.post(upload_path(drive_project), files={"file": big}, data={"purpose": "guide"})

    assert response.status_code == 413
    assert drive.uploads == []


def test_upload_503_when_drive_not_configured(an: TestClient, drive_project: Project) -> None:
    response = an.post(upload_path(drive_project), files={"file": PNG}, data={"purpose": "guide"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Chưa cấu hình Google Drive"


def test_upload_409_for_cloudinary_project(
    an: TestClient, project: Project, drive: FakeDrive
) -> None:
    response = an.post(upload_path(project), files={"file": PNG}, data={"purpose": "guide"})

    assert response.status_code == 409
    assert drive.uploads == []


def test_sign_409_for_drive_project(
    an: TestClient, drive_project: Project, signer: CloudinarySigner
) -> None:
    assert an.post(sign_path(drive_project), json=GUIDE).status_code == 409


def test_viewer_cannot_upload(
    app: FastAPI, users: UserRepository, drive_project: Project, drive: FakeDrive
) -> None:
    viewer = client_for(app, users, "viewer@x.com", Role.VIEWER)

    response = viewer.post(
        upload_path(drive_project), files={"file": PNG}, data={"purpose": "guide"}
    )

    assert response.status_code == 403


def test_tester_can_upload_evidence_to_drive(
    an: TestClient, drive_project: Project, drive: FakeDrive
) -> None:
    response = an.post(
        upload_path(drive_project), files={"file": PNG}, data={"purpose": "evidence"}
    )

    assert response.status_code == 200
    assert drive.uploads[0]["purpose"] == "evidence"


def test_upload_rejects_unknown_purpose(
    an: TestClient, drive_project: Project, drive: FakeDrive
) -> None:
    response = an.post(upload_path(drive_project), files={"file": PNG}, data={"purpose": "x"})

    assert response.status_code == 422
    assert drive.uploads == []


def test_drive_error_returns_502_with_safe_message(
    an: TestClient, drive_project: Project, drive: FakeDrive
) -> None:
    drive.error = DriveError("Không tải được lên Google Drive")

    response = an.post(upload_path(drive_project), files={"file": PNG}, data={"purpose": "guide"})

    assert response.status_code == 502
    assert response.json()["detail"] == "Không tải được lên Google Drive"


def test_agent_upload_requires_token(
    app: FastAPI, client: TestClient, drive_project: Project, drive: FakeDrive
) -> None:
    app.state.settings.agent_api_token = "agent-token"

    response = client.post(agent_upload_path(drive_project), files={"file": PNG})

    assert response.status_code == 401
    assert drive.uploads == []


def test_agent_upload_uses_evidence_folder(
    app: FastAPI, client: TestClient, drive_project: Project, drive: FakeDrive
) -> None:
    app.state.settings.agent_api_token = "agent-token"

    response = client.post(
        agent_upload_path(drive_project),
        files={"file": PNG},
        headers={"Authorization": "Bearer agent-token"},
    )

    assert response.status_code == 200
    assert drive.uploads[0]["purpose"] == "evidence"


def test_agent_sign_409_for_drive_project(
    app: FastAPI, client: TestClient, drive_project: Project, signer: CloudinarySigner
) -> None:
    app.state.settings.agent_api_token = "agent-token"

    response = client.post(
        agent_path(drive_project),
        json={"kind": "image"},
        headers={"Authorization": "Bearer agent-token"},
    )

    assert response.status_code == 409


def test_agent_storage_endpoint(
    app: FastAPI, client: TestClient, project: Project, drive_project: Project
) -> None:
    app.state.settings.agent_api_token = "agent-token"
    headers = {"Authorization": "Bearer agent-token"}
    path = f"/api/agent/projects/{project.id}/media/storage"

    assert client.get(path, headers=headers).json() == {"storage": "drive"}
    assert client.get(path).status_code == 401
