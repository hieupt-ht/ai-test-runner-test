from datetime import timedelta

import fakeredis
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.models.project import Project
from app.core.models.user import Role
from app.core.notifications import NotificationStore
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import ProjectRepository
from app.core.repositories.users import UserRepository
from app.core.time import today_in_vietnam
from tests.conftest import SYSTEM_SHEET_ID, client_for, make_project, make_user
from tests.fakes import FakeOAuth, FakeSheetsGateway


@pytest.fixture
def project(
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
    users: UserRepository,
) -> Project:
    users.create(make_user("binh@x.com", role=Role.TESTER, name="Bình"))
    users.create(make_user("khoa@x.com", role=Role.TESTER, active=False))
    return make_project(projects, members, gateway, member_emails=("lead@x.com",))


@pytest.fixture
def lead(app: FastAPI, oauth: FakeOAuth, users: UserRepository, project: Project) -> TestClient:
    return client_for(app, oauth, users, "lead@x.com", Role.QA_LEAD)


def members_url(project: Project) -> str:
    return f"/api/projects/{project.id}/members"


def test_qa_lead_adds_and_removes_member(
    lead: TestClient, project: Project, gateway: FakeSheetsGateway,
    redis: fakeredis.FakeRedis,
) -> None:
    added = lead.post(members_url(project), json={"email": " Binh@X.com"})

    assert added.status_code == 201
    assert added.json()["name"] == "Bình"
    assert added.json()["role"] == "TESTER"
    listed = lead.get(members_url(project)).json()
    assert {member["email"] for member in listed} == {"lead@x.com", "binh@x.com"}
    audit = gateway.data[SYSTEM_SHEET_ID]["AuditLog"][-1]
    assert audit[2:5] == ["CREATE", "project_member", f"{project.id}:binh@x.com"]
    assert [item.type for item in NotificationStore(redis).list("binh@x.com")] == [
        "member_added"
    ]
    assert NotificationStore(redis).list("lead@x.com") == []

    assert lead.delete(f"{members_url(project)}/binh@x.com").status_code == 204
    assert {m["email"] for m in lead.get(members_url(project)).json()} == {"lead@x.com"}


def test_add_member_succeeds_when_notification_fails(
    lead: TestClient, project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    def fail(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("Redis lỗi")

    monkeypatch.setattr(NotificationStore, "add", fail)
    response = lead.post(members_url(project), json={"email": "binh@x.com"})

    assert response.status_code == 201
    assert calls == 1
    assert {member["email"] for member in lead.get(members_url(project)).json()} == {
        "lead@x.com", "binh@x.com"
    }


@pytest.mark.parametrize("email", ["khong-co@x.com", "khoa@x.com"])
def test_add_inactive_or_unknown_user_is_422(
    lead: TestClient, project: Project, email: str
) -> None:
    response = lead.post(members_url(project), json={"email": email})

    assert response.status_code == 422
    assert response.json() == {"detail": "Người dùng không tồn tại hoặc đã bị khoá"}


def test_add_duplicate_is_409(lead: TestClient, project: Project) -> None:
    lead.post(members_url(project), json={"email": "binh@x.com"})

    response = lead.post(members_url(project), json={"email": "binh@x.com"})

    assert response.status_code == 409
    assert response.json() == {"detail": "Người này đã là thành viên"}


def test_remove_member_with_assignments_is_409(lead: TestClient, project: Project) -> None:
    lead.post(members_url(project), json={"email": "binh@x.com"})
    lead.post(f"/api/projects/{project.id}/screens", json={"name": "Đăng nhập"})
    deadline = (today_in_vietnam() + timedelta(days=3)).isoformat()
    lead.post(
        f"/api/projects/{project.id}/assignments",
        json={"screen_id": "SC-0001", "assignee_emails": ["binh@x.com"], "deadline": deadline},
    )

    response = lead.delete(f"{members_url(project)}/binh@x.com")

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Người này đang được giao 1 màn hình, hãy bỏ giao việc trước"
    }


def test_remove_unknown_member_is_404(lead: TestClient, project: Project) -> None:
    assert lead.delete(f"{members_url(project)}/khong-co@x.com").status_code == 404


def test_tester_cannot_manage_members(
    app: FastAPI,
    oauth: FakeOAuth,
    users: UserRepository,
    members: ProjectMemberRepository,
    project: Project,
) -> None:
    members.add(project.id, "binh@x.com")
    tester = client_for(app, oauth, users, "binh@x.com", Role.TESTER)

    assert tester.get(members_url(project)).status_code == 200
    assert tester.post(members_url(project), json={"email": "lead@x.com"}).status_code == 403


def test_non_member_gets_404(client_as_tester: TestClient, project: Project) -> None:
    assert client_as_tester.get(members_url(project)).status_code == 404
