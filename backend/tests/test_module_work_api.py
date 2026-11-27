from datetime import timedelta

import fakeredis
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.models.project import Project
from app.core.models.user import Role
from app.core.notifications import NotificationStore
from app.core.repositories.assignments import AssignmentRepository
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.modules import ModuleAssignmentRepository
from app.core.repositories.projects import ProjectRepository
from app.core.repositories.users import UserRepository
from app.core.services.module_work import ModuleWorkService
from app.core.time import today_in_vietnam
from tests.conftest import SHEET_A, client_for, make_project, make_user
from tests.fakes import FakeSheetsGateway

NEXT_WEEK = (today_in_vietnam() + timedelta(days=7)).isoformat()
IN_TWO_WEEKS = (today_in_vietnam() + timedelta(days=14)).isoformat()
YESTERDAY = (today_in_vietnam() - timedelta(days=1)).isoformat()

CASE_BODY = {
    "title": "Đăng nhập thành công",
    "steps": [{"action": "Nhập email và mật khẩu", "expected": "Vào trang chủ"}],
    "expected_result": "Đăng nhập được",
    "severity": "HIGH",
    "priority": "P1",
    "execution_mode": "AUTOMATION",
}


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
def lead(app: FastAPI, users: UserRepository, project: Project) -> TestClient:
    return client_for(app, users, "lead@x.com", Role.QA_LEAD)


@pytest.fixture
def tester(app: FastAPI, users: UserRepository, project: Project) -> TestClient:
    return client_for(app, users, "tester@x.com", Role.TESTER)


@pytest.fixture
def tester2(app: FastAPI, users: UserRepository, project: Project) -> TestClient:
    return client_for(app, users, "tester2@x.com", Role.TESTER)


def base(project: Project) -> str:
    return f"/api/projects/{project.id}"


def make_module_with_screens(lead: TestClient, project: Project, count: int = 3) -> str:
    module = lead.post(f"{base(project)}/modules", json={"name": "Tài khoản"}).json()["id"]
    for index in range(count):
        response = lead.post(
            f"{base(project)}/screens", json={"name": f"Màn {index}", "module_id": module}
        )
        assert response.status_code == 201, response.text
    return module


def workers_url(project: Project, module_id: str, suffix: str = "") -> str:
    return f"{base(project)}/modules/{module_id}/workers{suffix}"


def assign(
    client: TestClient,
    project: Project,
    module_id: str,
    emails: list[str],
    deadline: str = NEXT_WEEK,
) -> httpx.Response:
    return client.post(
        workers_url(project, module_id), json={"emails": emails, "deadline": deadline}
    )


def repos(
    gateway: FakeSheetsGateway, redis: fakeredis.FakeRedis, project: Project
) -> tuple[AssignmentRepository, ModuleAssignmentRepository]:
    return (
        AssignmentRepository(gateway, SHEET_A, redis, project.id),
        ModuleAssignmentRepository(gateway, SHEET_A, redis, project.id),
    )


def test_qa_assigns_empty_module(
    lead: TestClient,
    project: Project,
    gateway: FakeSheetsGateway,
    redis: fakeredis.FakeRedis,
) -> None:
    module = make_module_with_screens(lead, project, count=0)

    response = assign(lead, project, module, ["tester@x.com"])

    assert response.status_code == 201
    assert [m["assignee_email"] for m in response.json()] == ["tester@x.com"]
    assignments, module_assignments = repos(gateway, redis, project)
    assert len(module_assignments.list_all()) == 1
    assert assignments.list_all() == []


def test_assign_module_creates_assignment_per_screen_in_one_write(
    lead: TestClient,
    project: Project,
    gateway: FakeSheetsGateway,
    redis: fakeredis.FakeRedis,
) -> None:
    module = make_module_with_screens(lead, project, count=3)
    gateway.calls.clear()

    response = assign(lead, project, module, ["tester@x.com", "tester2@x.com"])

    assert response.status_code == 201
    assignments, _ = repos(gateway, redis, project)
    assert len(assignments.list_all()) == 6
    assert gateway.calls.count("append:Assignments") == 1
    assert gateway.calls.count("append:ModuleAssignments") == 1


def test_tester_claims_module_already_taken(
    lead: TestClient, tester: TestClient, tester2: TestClient, project: Project
) -> None:
    module = make_module_with_screens(lead, project)
    assert assign(tester, project, module, ["tester@x.com"]).status_code == 201

    response = assign(tester2, project, module, ["tester2@x.com"])

    assert response.status_code == 201
    listed = lead.get(f"{base(project)}/modules").json()[0]
    assert {w["email"] for w in listed["workers"]} == {"tester@x.com", "tester2@x.com"}


def test_tester_cannot_assign_other_tester(
    lead: TestClient, tester: TestClient, project: Project
) -> None:
    module = make_module_with_screens(lead, project)

    assert assign(tester, project, module, ["tester2@x.com"]).status_code == 403
    assert assign(tester, project, module, ["tester@x.com", "tester2@x.com"]).status_code == 403


def test_assign_rejects_non_tester_and_past_deadline(lead: TestClient, project: Project) -> None:
    module = make_module_with_screens(lead, project)

    assert assign(lead, project, module, ["viewer-member@x.com"]).status_code == 422
    assert assign(lead, project, module, ["inactive-tester@x.com"]).status_code == 422
    assert assign(lead, project, module, ["tester@x.com"], YESTERDAY).status_code == 422
    assert assign(lead, project, "MD-0999", ["tester@x.com"]).status_code == 404


def test_unassign_removes_screen_assignments_keeps_cases(
    lead: TestClient,
    tester: TestClient,
    project: Project,
    gateway: FakeSheetsGateway,
    redis: fakeredis.FakeRedis,
) -> None:
    module = make_module_with_screens(lead, project, count=2)
    worker_id = assign(tester, project, module, ["tester@x.com"]).json()[0]["id"]
    created = tester.post(f"{base(project)}/test-cases", json={**CASE_BODY, "screen_id": "SC-0001"})
    assert created.status_code == 201

    response = tester.delete(workers_url(project, module, f"/{worker_id}"))

    assert response.status_code == 200
    assert response.json() == {"removed_screen_assignments": 2}
    assignments, module_assignments = repos(gateway, redis, project)
    assert assignments.list_all() == []
    assert module_assignments.list_all() == []
    cases = lead.get(f"{base(project)}/test-cases").json()
    assert [c["id"] for c in cases] == [created.json()["id"]]


def test_tester_cannot_unassign_someone_else(
    lead: TestClient, tester: TestClient, tester2: TestClient, project: Project
) -> None:
    module = make_module_with_screens(lead, project)
    worker_id = assign(tester, project, module, ["tester@x.com"]).json()[0]["id"]

    assert tester2.delete(workers_url(project, module, f"/{worker_id}")).status_code == 403
    assert lead.delete(workers_url(project, module, f"/{worker_id}")).status_code == 200


def test_change_deadline_updates_all_screen_assignments(
    lead: TestClient,
    project: Project,
    gateway: FakeSheetsGateway,
    redis: fakeredis.FakeRedis,
) -> None:
    module = make_module_with_screens(lead, project, count=2)
    worker_id = assign(lead, project, module, ["tester@x.com"]).json()[0]["id"]

    response = lead.patch(
        workers_url(project, module, f"/{worker_id}"), json={"deadline": IN_TWO_WEEKS}
    )

    assert response.status_code == 200
    assert response.json()["deadline"] == IN_TWO_WEEKS
    assignments, module_assignments = repos(gateway, redis, project)
    assert {a.deadline.isoformat() for a in assignments.list_all()} == {IN_TWO_WEEKS}
    assert module_assignments.list_all()[0].deadline.isoformat() == IN_TWO_WEEKS


def test_tester_cannot_change_someone_elses_deadline(
    lead: TestClient, tester2: TestClient, project: Project
) -> None:
    module = make_module_with_screens(lead, project)
    worker_id = assign(lead, project, module, ["tester@x.com"]).json()[0]["id"]

    response = tester2.patch(
        workers_url(project, module, f"/{worker_id}"), json={"deadline": IN_TWO_WEEKS}
    )

    assert response.status_code == 403


def test_screen_added_to_module_is_assigned_to_workers(
    lead: TestClient, tester: TestClient, project: Project
) -> None:
    module = make_module_with_screens(lead, project, count=1)
    assign(tester, project, module, ["tester@x.com"])

    new_screen = lead.post(
        f"{base(project)}/screens", json={"name": "Màn mới", "module_id": module}
    ).json()

    mine = tester.get(f"{base(project)}/assignments").json()
    assert new_screen["id"] in {a["screen_id"] for a in mine}
    created = tester.post(
        f"{base(project)}/test-cases", json={**CASE_BODY, "screen_id": new_screen["id"]}
    )
    assert created.status_code == 201


def test_screen_moved_into_module_is_assigned_to_workers(
    lead: TestClient, tester: TestClient, project: Project
) -> None:
    module = make_module_with_screens(lead, project, count=0)
    assign(tester, project, module, ["tester@x.com"])
    loose = lead.post(f"{base(project)}/screens", json={"name": "Rời"}).json()

    lead.patch(f"{base(project)}/screens/{loose['id']}", json={"module_id": module})

    mine = tester.get(f"{base(project)}/assignments").json()
    assert [a["screen_id"] for a in mine] == [loose["id"]]


def test_assign_skips_already_assigned_screens(
    lead: TestClient,
    project: Project,
    gateway: FakeSheetsGateway,
    redis: fakeredis.FakeRedis,
) -> None:
    module = make_module_with_screens(lead, project, count=2)
    lead.post(
        f"{base(project)}/assignments",
        json={"screen_id": "SC-0001", "assignee_emails": ["tester@x.com"], "deadline": NEXT_WEEK},
    )

    assign(lead, project, module, ["tester@x.com"])

    assignments, _ = repos(gateway, redis, project)
    pairs = [(a.screen_id, a.assignee_email) for a in assignments.list_all()]
    assert sorted(pairs) == [("SC-0001", "tester@x.com"), ("SC-0002", "tester@x.com")]


def test_qa_assign_sends_one_notification_per_tester(
    lead: TestClient, project: Project, redis: fakeredis.FakeRedis
) -> None:
    module = make_module_with_screens(lead, project, count=3)

    assign(lead, project, module, ["tester@x.com", "tester2@x.com"])

    store = NotificationStore(redis)
    for email in ("tester@x.com", "tester2@x.com"):
        items = store.list(email)
        assert [i.type for i in items] == ["module_assigned"]
        assert items[0].link == f"/projects/{project.id}/screens?module={module}"
    assert store.list("lead@x.com") == []


def test_self_claim_sends_no_notification(
    lead: TestClient, tester: TestClient, project: Project, redis: fakeredis.FakeRedis
) -> None:
    module = make_module_with_screens(lead, project)

    assign(tester, project, module, ["tester@x.com"])

    assert NotificationStore(redis).list("tester@x.com") == []


def test_default_deadline_is_latest_or_next_week(
    lead: TestClient,
    project: Project,
    gateway: FakeSheetsGateway,
    redis: fakeredis.FakeRedis,
    members: ProjectMemberRepository,
    users: UserRepository,
) -> None:
    from app.core.repositories.audit_log import AuditLogRepository
    from app.core.repositories.modules import ModuleRepository
    from app.core.repositories.screens import ScreenRepository
    from app.core.repositories.test_cases import TestCaseRepository
    from app.core.services.module_work import ModuleWorkService

    module = make_module_with_screens(lead, project, count=0)
    args = (gateway, SHEET_A, redis, project.id)
    assignments, module_assignments = repos(gateway, redis, project)
    service = ModuleWorkService(
        project_id=project.id,
        modules=ModuleRepository(*args),
        screens=ScreenRepository(*args),
        assignments=assignments,
        module_assignments=module_assignments,
        test_cases=TestCaseRepository(*args),
        members=members,
        users=users,
        audit_log=AuditLogRepository(gateway, SHEET_A),
    )

    assert service.default_deadline(module) == today_in_vietnam() + timedelta(days=7)
    assign(lead, project, module, ["tester@x.com"], IN_TWO_WEEKS)
    assign(lead, project, module, ["tester2@x.com"], NEXT_WEEK)
    assert service.default_deadline(module).isoformat() == IN_TWO_WEEKS


def test_assign_new_screens_skips_member_who_left(
    lead: TestClient,
    project: Project,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
    redis: fakeredis.FakeRedis,
) -> None:
    module = make_module_with_screens(lead, project, count=0)
    assign(lead, project, module, ["tester@x.com", "tester2@x.com"])
    members.remove(project.id, "tester2@x.com")  # còn dòng ModuleAssignments nhưng đã rời dự án

    lead.post(f"{base(project)}/screens", json={"name": "Màn mới", "module_id": module})

    assignments, _ = repos(gateway, redis, project)
    assert [a.assignee_email for a in assignments.list_all()] == ["tester@x.com"]


def test_assign_again_with_new_deadline_updates_it(
    lead: TestClient,
    project: Project,
    gateway: FakeSheetsGateway,
    redis: fakeredis.FakeRedis,
) -> None:
    module = make_module_with_screens(lead, project, count=2)
    assign(lead, project, module, ["tester@x.com"])

    response = assign(lead, project, module, ["tester@x.com"], deadline=IN_TWO_WEEKS)

    assert response.status_code == 201
    assert [w["deadline"] for w in response.json()] == [IN_TWO_WEEKS]
    assignments, module_assignments = repos(gateway, redis, project)
    assert len(module_assignments.list_all()) == 1
    assert module_assignments.list_all()[0].deadline.isoformat() == IN_TWO_WEEKS
    assert {a.deadline.isoformat() for a in assignments.list_all()} == {IN_TWO_WEEKS}


def test_assign_again_with_same_deadline_returns_nothing(
    lead: TestClient, project: Project
) -> None:
    module = make_module_with_screens(lead, project, count=1)
    assign(lead, project, module, ["tester@x.com"])

    response = assign(lead, project, module, ["tester@x.com"])

    assert response.status_code == 201
    assert response.json() == []


def test_tester_creates_module_and_claims_it(tester: TestClient, project: Project) -> None:
    response = tester.post(f"{base(project)}/modules", json={"name": "Thanh toán"})

    assert response.status_code == 201
    module = tester.get(f"{base(project)}/modules").json()[0]
    assert [w["email"] for w in module["workers"]] == ["tester@x.com"]
    assert module["workers"][0]["deadline"] == NEXT_WEEK


def test_tester_cannot_create_duplicate_module(
    lead: TestClient, tester: TestClient, project: Project
) -> None:
    lead.post(f"{base(project)}/modules", json={"name": "Thanh toán"})

    response = tester.post(f"{base(project)}/modules", json={"name": "THANH TOÁN"})

    assert response.status_code == 422
    assert response.json()["detail"] == "Đã có module tên này"
    assert tester.get(f"{base(project)}/modules").json()[0]["workers"] == []


def test_lead_creating_module_does_not_claim_it(lead: TestClient, project: Project) -> None:
    lead.post(f"{base(project)}/modules", json={"name": "Thanh toán"})

    assert lead.get(f"{base(project)}/modules").json()[0]["workers"] == []


def test_tester_still_cannot_rename_or_delete_module(tester: TestClient, project: Project) -> None:
    module_id = tester.post(f"{base(project)}/modules", json={"name": "Thanh toán"}).json()["id"]

    renamed = tester.patch(f"{base(project)}/modules/{module_id}", json={"name": "X"})
    assert renamed.status_code == 403
    assert tester.delete(f"{base(project)}/modules/{module_id}").status_code == 403


def test_failed_claim_removes_new_module(
    tester: TestClient, project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(self, *args, **kwargs):
        raise RuntimeError("Google lỗi")

    monkeypatch.setattr(ModuleWorkService, "assign", boom)

    with pytest.raises(RuntimeError):
        tester.post(f"{base(project)}/modules", json={"name": "Thanh toán"})

    monkeypatch.undo()
    assert tester.get(f"{base(project)}/modules").json() == []
