"""API nhím (/me/pet) và tổng quan của tôi (/me/dashboard)."""

from datetime import datetime

from fastapi import FastAPI

from app.api.project_scope import scope_for
from app.core.models.project import Project
from app.core.models.run import Result, ResultStatus
from app.core.models.test_case import Priority, Severity, TestCaseContent, TestCaseStatus, TestStep
from app.core.models.user import Role
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import ProjectRepository
from app.core.repositories.users import UserRepository
from app.core.time import VIETNAM
from tests.conftest import SHEET_B, client_for, make_project
from tests.fakes import FakeSheetsGateway

AN = "an@x.com"


def add_case(app: FastAPI, project: Project, *, status: TestCaseStatus) -> str:
    scope = scope_for(app.state.services, project)
    case = scope.test_cases.create(
        screen_id="SC-0001",
        content=TestCaseContent(
            title="Đăng nhập",
            steps=[TestStep(action="Mở trang")],
            expected_result="Vào được",
            severity=Severity.HIGH,
            priority=Priority.P1,
        ),
        actor="minh@x.com",
    )
    if status != TestCaseStatus.DRAFT:
        case = scope.test_cases.save(
            case.model_copy(update={"status": status}),
            expected_version=case.version,
            actor="minh@x.com",
        )
    return case.id


def add_bugs(app: FastAPI, project: Project, count: int, *, by: str = AN) -> None:
    """An bắt `count` bug (mỗi bug một case riêng) ngay hôm nay."""
    scope = scope_for(app.state.services, project)
    for _ in range(count):
        case_id = add_case(app, project, status=TestCaseStatus.APPROVED)
        scope.results.append_batch(
            [
                Result(
                    id=f"RUN-0001-{case_id}",
                    run_id="RUN-0001",
                    test_case_id=case_id,
                    status=ResultStatus.FAIL,
                    reason="Lỗi",
                    failed_step=1,
                    created_at=datetime.now(VIETNAM),
                    executed_by=by,
                    case_version=1,
                )
            ]
        )


def two_projects(
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
    *,
    an_in_b: bool = False,
) -> tuple[Project, Project]:
    first = make_project(projects, members, gateway, name="Dự án A", member_emails=(AN,))
    second = make_project(
        projects,
        members,
        gateway,
        name="Dự án B",
        sheet=SHEET_B,
        member_emails=(AN,) if an_in_b else ("minh@x.com",),
    )
    return first, second


def test_pet_counts_bugs_in_my_projects_only(
    app: FastAPI,
    users: UserRepository,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    project_a, project_b = two_projects(projects, members, gateway)
    add_bugs(app, project_a, 3)
    add_bugs(app, project_b, 2)

    pet = client_for(app, users, AN, Role.TESTER).get("/api/me/pet").json()

    assert pet["bugs"] == 3


def test_new_user_pet_is_baby_and_normal(app: FastAPI, users: UserRepository) -> None:
    pet = client_for(app, users, AN, Role.TESTER).get("/api/me/pet").json()
    assert pet == {
        "level": 1,
        "bugs": 0,
        "bugs_to_next": 5,
        "streak": 0,
        "missed_days": 0,
        "mood": "NORMAL",
    }


def test_pet_happy_after_catching_bug_today(
    app: FastAPI,
    users: UserRepository,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    project_a, _ = two_projects(projects, members, gateway)
    add_bugs(app, project_a, 1)

    pet = client_for(app, users, AN, Role.TESTER).get("/api/me/pet").json()

    assert (pet["mood"], pet["streak"]) == ("HAPPY", 1)


def test_dashboard_lists_progress_and_14_days(
    app: FastAPI,
    users: UserRepository,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    project_a, project_b = two_projects(projects, members, gateway, an_in_b=True)
    add_case(app, project_a, status=TestCaseStatus.APPROVED)
    add_case(app, project_a, status=TestCaseStatus.DRAFT)

    body = client_for(app, users, AN, Role.TESTER).get("/api/me/dashboard").json()

    assert len(body["projects"]) == 2
    assert len(body["daily"]) == 14
    by_id = {item["project_id"]: item for item in body["projects"]}
    assert by_id[project_a.id] == {
        "project_id": project_a.id,
        "project_name": "Dự án A",
        "done": 1,
        "total": 2,
    }
    assert by_id[project_b.id]["total"] == 0


def test_broken_project_sheet_is_skipped(
    app: FastAPI,
    users: UserRepository,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    project_a, project_b = two_projects(projects, members, gateway, an_in_b=True)
    add_bugs(app, project_a, 2)
    add_bugs(app, project_b, 4)
    gateway.denied.add(SHEET_B)
    browser = client_for(app, users, AN, Role.TESTER)

    pet = browser.get("/api/me/pet")
    dashboard = browser.get("/api/me/dashboard")

    assert pet.status_code == 200
    assert pet.json()["bugs"] == 2
    assert dashboard.status_code == 200
    assert [item["project_id"] for item in dashboard.json()["projects"]] == [project_a.id]
