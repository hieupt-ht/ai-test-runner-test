"""API ký upload: tester ký cho ảnh hướng dẫn, agent ký cho bằng chứng; không bao giờ lộ secret."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.media.cloudinary import CloudinarySigner
from app.core.models.project import Project
from app.core.models.user import Role
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import ProjectRepository
from app.core.repositories.users import UserRepository
from tests.conftest import client_for, make_project, make_user
from tests.fakes import FakeSheetsGateway

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


def test_tester_cannot_sign_for_evidence_folder(
    an: TestClient, project: Project, signer: CloudinarySigner
) -> None:
    response = an.post(sign_path(project), json={"kind": "image", "purpose": "evidence"})
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
