from datetime import timedelta

from fastapi import FastAPI

from app.api.project_scope import scope_for
from app.core.models.project import Project
from app.core.models.run import Result, ResultStatus, RunScope, RunStatus
from app.core.models.test_case import Priority, Severity, TestCaseContent, TestCaseStatus, TestStep
from app.core.models.user import Role
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import ProjectRepository
from app.core.repositories.users import UserRepository
from app.core.time import utc_now
from tests.conftest import SHEET_B, client_for, make_project
from tests.fakes import FakeOAuth, FakeSheetsGateway


def _add_case(app: FastAPI, project: Project, *, title: str, status: TestCaseStatus) -> str:
    scope = scope_for(app.state.services, project)
    case = scope.test_cases.create(
        screen_id="SC-0001",
        content=TestCaseContent(
            title=title,
            steps=[TestStep(action="Mở trang")],
            expected_result="Thành công",
            severity=Severity.HIGH,
            priority=Priority.P1,
        ),
        actor="tester@x.com",
    )
    if status != TestCaseStatus.DRAFT:
        case = scope.test_cases.save(
            case.model_copy(update={"status": status}),
            expected_version=case.version,
            actor="tester@x.com",
        )
    return case.id


def _add_result(app: FastAPI, project: Project, case_id: str) -> None:
    scope = scope_for(app.state.services, project)
    run = scope.runs.create(triggered_by="agent", scope=RunScope(), branch="main", total=1)
    run.status = RunStatus.COMPLETED
    run.finished_at = utc_now() + timedelta(seconds=1)
    scope.runs.save(run)
    scope.results.append_batch(
        [
            Result(
                id=f"{run.id}-{case_id}",
                run_id=run.id,
                test_case_id=case_id,
                status=ResultStatus.PASS,
                reason="Đạt",
                failed_step=None,
                screenshot=None,
                created_at=run.finished_at,
            )
        ]
    )


def test_qa_overview_counts_pending_cases_and_finds_result_across_projects(
    app: FastAPI,
    oauth: FakeOAuth,
    users: UserRepository,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    first = make_project(
        projects, members, gateway, name="Dự án A", member_emails=("lead@x.com",)
    )
    second = make_project(
        projects,
        members,
        gateway,
        name="Dự án B",
        sheet=SHEET_B,
        member_emails=("lead@x.com",),
    )
    _add_case(app, first, title="Case nháp", status=TestCaseStatus.DRAFT)
    pending_id = _add_case(
        app, second, title="Case đang chờ QA", status=TestCaseStatus.IN_REVIEW
    )
    _add_result(app, second, pending_id)
    lead = client_for(app, oauth, users, "lead@x.com", Role.QA_LEAD)

    response = lead.get("/api/me/overview")

    assert response.status_code == 200
    assert response.json()["pending_review"] == 1
    assert response.json()["latest_result"]["case_id"] == pending_id
    assert response.json()["latest_result"]["case_title"] == "Case đang chờ QA"
