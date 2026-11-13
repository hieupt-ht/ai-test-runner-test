from datetime import timedelta

import fakeredis
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.assignment_status import AssignmentStatusUpdater
from app.core.models.project import Project
from app.core.models.test_case import (
    Priority,
    Severity,
    TestCase,
    TestCaseContent,
    TestCaseStatus,
    TestStep,
)
from app.core.models.user import Role
from app.core.repositories.assignments import AssignmentRepository
from app.core.repositories.audit_log import AuditLogRepository
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import ProjectRepository
from app.core.repositories.test_cases import TestCaseRepository
from app.core.repositories.users import UserRepository
from app.core.time import today_in_vietnam
from tests.conftest import SHEET_A, SHEET_B, client_for, make_project, make_user
from tests.fakes import FakeOAuth, FakeSheetsGateway

NEXT_WEEK = (today_in_vietnam() + timedelta(days=7)).isoformat()
YESTERDAY = (today_in_vietnam() - timedelta(days=1)).isoformat()


@pytest.fixture
def project(
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
    users: UserRepository,
) -> Project:
    for user in (
        make_user("tester@x.com", role=Role.TESTER),
        make_user("tester2@x.com", role=Role.TESTER),
        make_user("viewer-member@x.com", role=Role.VIEWER),
        make_user("inactive-tester@x.com", role=Role.TESTER, active=False),
    ):
        if users.get(user.email) is None:
            users.create(user)
    return make_project(
        projects,
        members,
        gateway,
        member_emails=(
            "lead@x.com",
            "tester@x.com",
            "tester2@x.com",
            "viewer-member@x.com",
            "inactive-tester@x.com",
        ),
    )


@pytest.fixture
def lead(app: FastAPI, oauth: FakeOAuth, users: UserRepository, project: Project) -> TestClient:
    browser = client_for(app, oauth, users, "lead@x.com", Role.QA_LEAD)
    browser.post(f"/api/projects/{project.id}/screens", json={"name": "Đăng nhập"})
    return browser


def assignments_url(project: Project) -> str:
    return f"/api/projects/{project.id}/assignments"


def assign(
    browser: TestClient, project: Project, emails: list[str], deadline: str = NEXT_WEEK
) -> httpx.Response:
    response: httpx.Response = browser.post(
        assignments_url(project),
        json={"screen_id": "SC-0001", "assignee_emails": emails, "deadline": deadline},
    )
    return response


def test_assign_screen_to_two_testers(lead: TestClient, project: Project) -> None:
    response = assign(lead, project, ["tester@x.com", " Tester2@X.com"])

    assert response.status_code == 201
    created = response.json()
    assert [a["id"] for a in created] == ["AS-0001", "AS-0002"]
    assert [a["assignee_email"] for a in created] == ["tester@x.com", "tester2@x.com"]
    assert {a["status"] for a in created} == {"TODO"}


def test_assign_skips_existing_pair(lead: TestClient, project: Project) -> None:
    assign(lead, project, ["tester@x.com"])

    response = assign(lead, project, ["tester@x.com", "tester2@x.com"])

    assert [a["assignee_email"] for a in response.json()] == ["tester2@x.com"]
    assert len(lead.get(assignments_url(project)).json()) == 2


def test_deadline_in_past_is_422(lead: TestClient, project: Project) -> None:
    response = assign(lead, project, ["tester@x.com"], deadline=YESTERDAY)

    assert response.status_code == 422
    assert response.json() == {"detail": "Deadline phải từ hôm nay trở đi"}


def test_unknown_screen_is_422(lead: TestClient, project: Project) -> None:
    response = lead.post(
        assignments_url(project),
        json={"screen_id": "SC-0999", "assignee_emails": ["tester@x.com"], "deadline": NEXT_WEEK},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Không tìm thấy màn hình"}


@pytest.mark.parametrize(
    "who", ["not-member@x.com", "viewer-member@x.com", "inactive-tester@x.com"]
)
def test_assignee_must_be_active_tester_member(
    lead: TestClient, project: Project, who: str
) -> None:
    response = assign(lead, project, [who])

    assert response.status_code == 422
    assert response.json() == {"detail": f"{who} không phải tester đang hoạt động của dự án"}


def test_change_deadline_and_unassign(lead: TestClient, project: Project) -> None:
    assign(lead, project, ["tester@x.com"])
    later = (today_in_vietnam() + timedelta(days=10)).isoformat()

    patched = lead.patch(f"{assignments_url(project)}/AS-0001", json={"deadline": later})
    deleted = lead.delete(f"{assignments_url(project)}/AS-0001")

    assert patched.json()["deadline"] == later
    assert deleted.status_code == 204
    assert lead.get(assignments_url(project)).json() == []


def test_delete_screen_with_assignment_is_409(lead: TestClient, project: Project) -> None:
    assign(lead, project, ["tester@x.com"])

    response = lead.delete(f"/api/projects/{project.id}/screens/SC-0001")

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Màn hình đang được giao cho tester, hãy bỏ giao việc trước"
    }


def test_tester_cannot_assign(
    app: FastAPI, oauth: FakeOAuth, users: UserRepository, lead: TestClient, project: Project
) -> None:
    tester = client_for(app, oauth, users, "tester@x.com", Role.TESTER)

    assert assign(tester, project, ["tester2@x.com"]).status_code == 403


def test_my_assignments_across_projects(
    app: FastAPI,
    oauth: FakeOAuth,
    users: UserRepository,
    lead: TestClient,
    project: Project,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    other = make_project(
        projects,
        members,
        gateway,
        name="Dự án B",
        sheet=SHEET_B,
        member_emails=("lead@x.com", "tester@x.com"),
    )
    lead.post(f"/api/projects/{other.id}/screens", json={"name": "Giỏ hàng"})
    soon = (today_in_vietnam() + timedelta(days=2)).isoformat()
    assign(lead, project, ["tester@x.com"], deadline=NEXT_WEEK)
    assign(lead, other, ["tester@x.com"], deadline=soon)
    projects.update(other.model_copy(update={"archived": True}))  # dự án lưu trữ bị bỏ qua

    tester = client_for(app, oauth, users, "tester@x.com", Role.TESTER)
    mine = tester.get("/api/me/assignments").json()

    assert [(a["project_name"], a["screen_name"]) for a in mine] == [("Dự án A", "Đăng nhập")]

    projects.update(other.model_copy(update={"archived": False}))
    mine = tester.get("/api/me/assignments").json()
    assert [a["deadline"] for a in mine] == [soon, NEXT_WEEK]  # sắp xếp theo deadline


def test_non_member_gets_404(client_as_tester: TestClient, project: Project) -> None:
    other_project_url = assignments_url(project).replace(project.id, "PRJ-0099")

    assert client_as_tester.get(other_project_url).status_code == 404


@pytest.mark.parametrize("breakage", ["denied", "missing_columns"])
def test_my_assignments_skips_project_with_broken_sheet(
    app: FastAPI,
    oauth: FakeOAuth,
    users: UserRepository,
    lead: TestClient,
    project: Project,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
    breakage: str,
) -> None:
    make_project(
        projects,
        members,
        gateway,
        name="Dự án B",
        sheet=SHEET_B,
        member_emails=("lead@x.com", "tester@x.com"),
    )
    assign(lead, project, ["tester@x.com"])
    # Sheet của dự án B bị hỏng: hết quyền, hoặc ai đó xoá mất cột
    if breakage == "denied":
        gateway.denied.add(SHEET_B)
    else:
        gateway.data[SHEET_B]["Assignments"][0] = ["id"]

    tester = client_for(app, oauth, users, "tester@x.com", Role.TESTER)
    response = tester.get("/api/me/assignments")

    assert response.status_code == 200
    assert [a["project_name"] for a in response.json()] == ["Dự án A"]


def add_case(
    gateway: FakeSheetsGateway,
    redis: fakeredis.FakeRedis,
    project: Project,
    *,
    status: TestCaseStatus = TestCaseStatus.DRAFT,
    created_by: str = "tester@x.com",
) -> TestCase:
    """Tạo thẳng một test case trên SC-0001 qua repository (bỏ qua API)."""
    repo = TestCaseRepository(
        gateway, SHEET_A, redis, project.id, lock_wait_seconds=0.1, cache_ttl_seconds=60
    )
    content = TestCaseContent(
        title="Đăng nhập đúng",
        steps=[TestStep(action="Bấm Đăng nhập", expected="")],
        expected_result="Vào được trang chủ",
        severity=Severity.LOW,
        priority=Priority.P1,
    )
    case = repo.create(screen_id="SC-0001", content=content, actor=created_by)
    if status == TestCaseStatus.DRAFT:
        return case
    return repo.save(
        case.model_copy(update={"status": status}), expected_version=case.version, actor=created_by
    )


def test_reassign_tester_keeps_derived_status(
    lead: TestClient,
    project: Project,
    gateway: FakeSheetsGateway,
    redis: fakeredis.FakeRedis,
) -> None:
    assign(lead, project, ["tester@x.com"])
    add_case(gateway, redis, project)  # A có case DRAFT trên SC-0001
    lead.delete(f"{assignments_url(project)}/AS-0001")

    again = assign(lead, project, ["tester@x.com"])

    assert again.json()[0]["status"] == "WRITING"


def test_my_assignments_include_case_counts(
    app: FastAPI,
    oauth: FakeOAuth,
    users: UserRepository,
    lead: TestClient,
    project: Project,
    gateway: FakeSheetsGateway,
    redis: fakeredis.FakeRedis,
) -> None:
    assign(lead, project, ["tester@x.com"])
    add_case(gateway, redis, project)
    add_case(gateway, redis, project)
    add_case(gateway, redis, project, status=TestCaseStatus.IN_REVIEW)
    add_case(gateway, redis, project, created_by="tester2@x.com")  # của người khác, không tính

    AssignmentStatusUpdater(
        AssignmentRepository(
            gateway, SHEET_A, redis, project.id, lock_wait_seconds=0.1, cache_ttl_seconds=60
        ),
        TestCaseRepository(
            gateway, SHEET_A, redis, project.id, lock_wait_seconds=0.1, cache_ttl_seconds=60
        ),
    ).refresh_screen("SC-0001")

    tester = client_for(app, oauth, users, "tester@x.com", Role.TESTER)
    mine = tester.get("/api/me/assignments").json()

    assert mine[0]["status"] == "WRITING"
    assert mine[0]["case_counts"] == {
        "DRAFT": 2,
        "IN_REVIEW": 1,
        "APPROVED": 0,
        "DEPRECATED": 0,
    }


def test_my_assignments_list_returned_cases_with_reason(
    app: FastAPI,
    oauth: FakeOAuth,
    users: UserRepository,
    lead: TestClient,
    project: Project,
    gateway: FakeSheetsGateway,
    redis: fakeredis.FakeRedis,
) -> None:
    assign(lead, project, ["tester@x.com"])
    returned = add_case(gateway, redis, project)  # DRAFT, rồi bị QA trả lại
    add_case(gateway, redis, project)  # DRAFT mới viết, chưa từng bị trả lại
    AuditLogRepository(gateway, SHEET_A).record(
        actor="lead@x.com",
        action="RETURN",
        entity="test_case",
        entity_id=returned.id,
        diff={"status": ["IN_REVIEW", "DRAFT"], "comment": "Thiếu bước đăng xuất"},
    )

    tester = client_for(app, oauth, users, "tester@x.com", Role.TESTER)
    mine = tester.get("/api/me/assignments").json()

    assert mine[0]["returned_cases"] == [
        {
            "case_id": returned.id,
            "title": "Đăng nhập đúng",
            "comment": "Thiếu bước đăng xuất",
            "returned_by": "lead@x.com",
        }
    ]
