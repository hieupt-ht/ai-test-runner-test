from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.project_scope import scope_for
from app.core.models.project import Project
from app.core.models.run import Evidence, Result, ResultStatus, RunScope, RunStatus, StepResult
from app.core.models.test_case import (
    Platform,
    Priority,
    Severity,
    TestCaseContent,
    TestStep,
)
from app.core.models.user import Role
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import ProjectRepository
from app.core.repositories.users import UserRepository
from app.core.time import utc_now
from tests.conftest import client_for, make_project, make_user
from tests.fakes import FakeOAuth, FakeSheetsGateway


@pytest.fixture
def project(
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
    users: UserRepository,
) -> Project:
    users.create(make_user("an@x.com", role=Role.TESTER))
    users.create(make_user("binh@x.com", role=Role.TESTER))
    users.create(make_user("outsider@x.com", role=Role.TESTER))
    return make_project(
        projects,
        members,
        gateway,
        member_emails=("lead@x.com", "an@x.com", "binh@x.com"),
    )


def browser(
    app: FastAPI, oauth: FakeOAuth, users: UserRepository, email: str, role: Role
) -> TestClient:
    return client_for(app, oauth, users, email, role)


def seed_results(app: FastAPI, project: Project) -> tuple[str, str]:
    scope = scope_for(app.state.services, project)
    login_screen = scope.screens.create(
        name="Đăng nhập", description="", route="/login", code_paths=[]
    )
    home_screen = scope.screens.create(
        name="Trang chủ", description="", route="/", code_paths=[]
    )
    content = TestCaseContent(
        title="Đăng nhập",
        steps=[TestStep(action="Mở trang")],
        expected_result="Thành công",
        severity=Severity.HIGH,
        priority=Priority.P1,
    )
    first = scope.test_cases.create(screen_id=login_screen.id, content=content, actor="an@x.com")
    second = scope.test_cases.create(
        screen_id=home_screen.id,
        content=content.model_copy(update={"title": "Đăng xuất"}),
        actor="binh@x.com",
    )
    for index, rows in enumerate(
        [
            [(first.id, ResultStatus.PASS), (second.id, ResultStatus.PASS)],
            [(first.id, ResultStatus.FAIL)],
        ]
    ):
        run = scope.runs.create(
            triggered_by="agent", scope=RunScope(), branch="main", total=len(rows)
        )
        run.status = RunStatus.COMPLETED
        run.finished_at = utc_now() + timedelta(seconds=index)
        scope.runs.save(run)
        scope.results.append_batch(
            [
                Result(
                    id=f"{run.id}-{case_id}",
                    run_id=run.id,
                    test_case_id=case_id,
                    status=result_status,
                    reason="Lỗi đăng nhập" if result_status == ResultStatus.FAIL else "Đạt",
                    failed_step=2 if result_status == ResultStatus.FAIL else None,
                    evidence=Evidence(legacy_url="https://example.com/evidence")
                    if result_status == ResultStatus.FAIL
                    else Evidence(),
                    created_at=run.finished_at,
                )
                for case_id, result_status in rows
            ]
        )
    return first.id, second.id


def path(project: Project, status: str = "") -> str:
    return f"/api/projects/{project.id}/results{status}"


def test_qa_lead_sees_all_latest_results(
    app: FastAPI,
    oauth: FakeOAuth,
    users: UserRepository,
    project: Project,
    gateway: FakeSheetsGateway,
) -> None:
    first_id, second_id = seed_results(app, project)
    gateway.calls.clear()

    response = browser(app, oauth, users, "lead@x.com", Role.QA_LEAD).get(path(project))

    assert response.status_code == 200
    items = {item["case_id"]: item for item in response.json()}
    assert set(items) == {first_id, second_id}
    assert items[first_id]["status"] == "FAIL"
    assert items[first_id]["case_title"] == "Đăng nhập"
    assert items[first_id]["reason"] == "Lỗi đăng nhập"
    assert items[first_id]["failed_step"] == 2
    assert items[first_id]["evidence"]["legacy_url"] == "https://example.com/evidence"
    assert items[first_id]["run_id"] == "RUN-0002"
    assert items[first_id]["finished_at"]
    assert items[first_id]["screen_id"] == "SC-0001"
    assert items[first_id]["screen_name"] == "Đăng nhập"
    assert gateway.calls.count("Runs") == 1
    assert gateway.calls.count("Results") == 1
    assert gateway.calls.count("Screens") == 1


def test_tester_sees_only_own_cases(
    app: FastAPI,
    oauth: FakeOAuth,
    users: UserRepository,
    project: Project,
) -> None:
    first_id, _ = seed_results(app, project)

    response = browser(app, oauth, users, "an@x.com", Role.TESTER).get(path(project))

    assert response.status_code == 200
    assert [item["case_id"] for item in response.json()] == [first_id]


def test_filter_by_status(
    app: FastAPI,
    oauth: FakeOAuth,
    users: UserRepository,
    project: Project,
) -> None:
    first_id, _ = seed_results(app, project)

    response = browser(app, oauth, users, "lead@x.com", Role.QA_LEAD).get(
        path(project, "?status=FAIL")
    )

    assert response.status_code == 200
    assert [item["case_id"] for item in response.json()] == [first_id]


def test_filter_by_screen_id(
    app: FastAPI,
    oauth: FakeOAuth,
    users: UserRepository,
    project: Project,
) -> None:
    first_id, _ = seed_results(app, project)

    response = browser(app, oauth, users, "lead@x.com", Role.QA_LEAD).get(
        path(project, "?screen_id=SC-0001")
    )

    assert response.status_code == 200
    assert [item["case_id"] for item in response.json()] == [first_id]


def test_missing_screen_uses_screen_id_as_name(
    app: FastAPI,
    oauth: FakeOAuth,
    users: UserRepository,
    project: Project,
) -> None:
    scope = scope_for(app.state.services, project)
    case = scope.test_cases.create(
        screen_id="SC-DELETED",
        content=TestCaseContent(
            title="Màn hình đã xóa",
            steps=[TestStep(action="Mở trang")],
            expected_result="Thành công",
            severity=Severity.MEDIUM,
            priority=Priority.P2,
        ),
        actor="an@x.com",
    )
    run = scope.runs.create(triggered_by="agent", scope=RunScope(), branch="main", total=1)
    run.status = RunStatus.COMPLETED
    run.finished_at = utc_now()
    scope.runs.save(run)
    scope.results.append_batch(
        [
            Result(
                id=f"{run.id}-{case.id}",
                run_id=run.id,
                test_case_id=case.id,
                status=ResultStatus.PASS,
                reason="Đạt",
                failed_step=None,
                created_at=run.finished_at,
            )
        ]
    )

    response = browser(app, oauth, users, "lead@x.com", Role.QA_LEAD).get(path(project))

    assert response.status_code == 200
    assert response.json()[0]["screen_id"] == "SC-DELETED"
    assert response.json()[0]["screen_name"] == "SC-DELETED"


def test_non_member_forbidden(
    app: FastAPI,
    oauth: FakeOAuth,
    users: UserRepository,
    project: Project,
) -> None:
    response = browser(app, oauth, users, "outsider@x.com", Role.TESTER).get(path(project))

    assert response.status_code == 404
    assert response.json() == {"detail": "Không tìm thấy dự án"}


def test_no_runs_returns_empty_list(
    app: FastAPI,
    oauth: FakeOAuth,
    users: UserRepository,
    project: Project,
) -> None:
    response = browser(app, oauth, users, "lead@x.com", Role.QA_LEAD).get(path(project))

    assert response.status_code == 200
    assert response.json() == []


def test_archived_project_results_remain_visible(
    app: FastAPI,
    oauth: FakeOAuth,
    users: UserRepository,
    projects: ProjectRepository,
    project: Project,
) -> None:
    seed_results(app, project)
    projects.update(project.model_copy(update={"archived": True}))

    response = browser(app, oauth, users, "lead@x.com", Role.QA_LEAD).get(path(project))

    assert response.status_code == 200
    assert len(response.json()) == 2


# ---------- Task 19: thông tin đầy đủ và bộ lọc mới ----------


def seed_mixed(app: FastAPI, project: Project) -> tuple[str, str]:
    """Hai Run: RUN-0001 có case web và case Android (regression); RUN-0002 chỉ có case web."""
    scope = scope_for(app.state.services, project)
    screen = scope.screens.create(name="Đăng nhập", description="", route="/", code_paths=[])
    content = TestCaseContent(
        title="Web",
        steps=[TestStep(action="Mở trang")],
        expected_result="Ok",
        severity=Severity.HIGH,
        priority=Priority.P1,
    )
    web = scope.test_cases.create(screen_id=screen.id, content=content, actor="an@x.com")
    android = scope.test_cases.create(
        screen_id=screen.id,
        content=content.model_copy(
            update={"title": "Android", "platform": Platform.ANDROID, "regression": True}
        ),
        actor="an@x.com",
    )
    for index, rows in enumerate([[web.id, android.id], [web.id]]):
        run = scope.runs.create(
            triggered_by="agent", scope=RunScope(), branch="main", total=len(rows),
            build_version=f"1.0.{index}",
        )
        run.status = RunStatus.COMPLETED
        run.finished_at = utc_now() + timedelta(seconds=index)
        scope.runs.save(run)
        scope.results.append_batch(
            [
                Result(
                    id=f"{run.id}-{case_id}", run_id=run.id, test_case_id=case_id,
                    status=ResultStatus.FAIL, reason="Lỗi", failed_step=1,
                    created_at=run.finished_at,
                    step_results=[StepResult(step_no=1, status="FAIL", actual="Sai")],
                    actual_result="Thấy lỗi", environment="Pixel 7", executed_by="codex-win",
                    case_version=1, dev_owner="nguyenvana",
                )
                for case_id in rows
            ]
        )
    return web.id, android.id


def lead_get(
    app: FastAPI, oauth: FakeOAuth, users: UserRepository, project: Project, query: str = ""
) -> list[dict[str, object]]:
    client = browser(app, oauth, users, "lead@x.com", Role.QA_LEAD)
    response = client.get(path(project, query))
    assert response.status_code == 200
    return response.json()


def test_item_has_full_detail(
    app: FastAPI, oauth: FakeOAuth, users: UserRepository, project: Project
) -> None:
    web, _ = seed_mixed(app, project)
    item = next(i for i in lead_get(app, oauth, users, project) if i["case_id"] == web)
    assert item["platform"] == "WEB" and item["regression"] is False
    assert item["case_version"] == 1 and item["environment"] == "Pixel 7"
    assert item["executed_by"] == "codex-win" and item["dev_owner"] == "nguyenvana"
    assert item["actual_result"] == "Thấy lỗi"
    assert item["step_results"][0]["actual"] == "Sai"
    assert item["build_version"] == "1.0.1"
    assert item["issue_url"] == (
        f"https://github.com/{project.repo_full_name}/issues?q=label%3Atc%3A{web}"
    )


def test_filter_by_platform(
    app: FastAPI, oauth: FakeOAuth, users: UserRepository, project: Project
) -> None:
    _, android = seed_mixed(app, project)
    items = lead_get(app, oauth, users, project, "?platform=ANDROID")
    assert [i["case_id"] for i in items] == [android]


def test_run_id_filter_returns_that_run_even_if_newer_exists(
    app: FastAPI, oauth: FakeOAuth, users: UserRepository, project: Project
) -> None:
    web, android = seed_mixed(app, project)
    items = lead_get(app, oauth, users, project, "?run_id=RUN-0001")
    assert {i["case_id"] for i in items} == {web, android}
    assert {i["run_id"] for i in items} == {"RUN-0001"}


def test_regression_only_filter(
    app: FastAPI, oauth: FakeOAuth, users: UserRepository, project: Project
) -> None:
    _, android = seed_mixed(app, project)
    items = lead_get(app, oauth, users, project, "?regression_only=true")
    assert [i["case_id"] for i in items] == [android]
