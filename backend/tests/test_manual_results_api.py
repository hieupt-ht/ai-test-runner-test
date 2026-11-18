"""Tester gửi kết quả test tay: Run + Result + case TESTED + issue GitHub."""

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.models.project import Project
from app.core.models.user import Role
from app.core.notifications import NotificationStore
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import ProjectRepository
from app.core.repositories.users import UserRepository
from tests.conftest import client_for, make_project, make_user
from tests.fakes import FakeGitHub, FakeSheetsGateway
from tests.test_test_cases_api import BODY, NEXT_WEEK

CLOUD = "mine"
TWO_STEPS = [
    {"action": "Mở trang đăng nhập", "expected": "Thấy form"},
    {"action": "Bấm Đăng nhập", "expected": "Vào trang chủ"},
]


@pytest.fixture
def project(
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
    users: UserRepository,
) -> Project:
    users.create(make_user("an@x.com", role=Role.TESTER, name="An Nguyễn"))
    users.create(make_user("binh@x.com", role=Role.TESTER))
    return make_project(
        projects, members, gateway, member_emails=("an@x.com", "binh@x.com", "lead@x.com")
    )


@pytest.fixture
def lead(app: FastAPI, users: UserRepository, project: Project) -> TestClient:
    browser = client_for(app, users, "lead@x.com", Role.QA_LEAD)
    browser.post(f"/api/projects/{project.id}/screens", json={"name": "Đăng nhập"})
    browser.post(
        f"/api/projects/{project.id}/assignments",
        json={"screen_id": "SC-0001", "assignee_emails": ["an@x.com"], "deadline": NEXT_WEEK},
    )
    app.state.services.cloud_name = CLOUD
    return browser


@pytest.fixture
def an(app: FastAPI, users: UserRepository, lead: TestClient) -> TestClient:
    return client_for(app, users, "an@x.com", Role.TESTER)


def cases_url(project: Project, suffix: str = "") -> str:
    return f"/api/projects/{project.id}/test-cases{suffix}"


def new_case(an: TestClient, project: Project, **changes: Any) -> dict[str, Any]:
    """Case do tester tạo; mặc định là Manual (không gửi execution_mode)."""
    body = {key: value for key, value in BODY.items() if key != "execution_mode"}
    body["steps"] = TWO_STEPS
    response = an.post(cases_url(project), json={**body, **changes})
    assert response.status_code == 201
    case: dict[str, Any] = response.json()
    return case


def result_body(**changes: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "status": "PASS",
        "step_results": [
            {"step_no": 1, "status": "PASS", "actual": "Thấy form"},
            {"step_no": 2, "status": "PASS", "actual": "Vào trang chủ"},
        ],
        "actual_result": "Đăng nhập được",
        "environment": "Chrome 130 / Windows 11",
        "build_version": "1.4.2",
        "version": 1,
    }
    body.update(changes)
    return body


def fail_body(**changes: Any) -> dict[str, Any]:
    body = result_body(
        status="FAIL",
        step_results=[
            {"step_no": 1, "status": "PASS"},
            {"step_no": 2, "status": "FAIL", "actual": "Báo lỗi 500"},
        ],
        reason="Bấm Đăng nhập thì báo lỗi 500",
        failed_step=2,
    )
    body.update(changes)
    return body


def submit(browser: TestClient, project: Project, case_id: str, body: dict[str, Any]) -> Any:
    return browser.post(cases_url(project, f"/{case_id}/manual-results"), json=body)


def rows(gateway: FakeSheetsGateway, project: Project, tab: str) -> list[dict[str, str]]:
    table = gateway.data[project.spreadsheet_id][tab]
    return [dict(zip(table[0], row, strict=False)) for row in table[1:]]


def media(
    name: str, *, project: Project, folder: str = "evidence", kind: str = "image"
) -> dict[str, str]:
    public_id = f"ai-test-runner/{project.id}/{folder}/{name}"
    return {
        "kind": kind,
        "url": f"https://res.cloudinary.com/{CLOUD}/{kind}/upload/{public_id}.png",
        "public_id": public_id,
    }


def case_status(an: TestClient, project: Project, case_id: str) -> str:
    status: str = an.get(cases_url(project, f"/{case_id}")).json()["status"]
    return status


def test_tester_submits_pass_marks_tested(
    an: TestClient, project: Project, gateway: FakeSheetsGateway
) -> None:
    case = new_case(an, project)

    response = submit(an, project, case["id"], result_body())

    assert response.status_code == 201
    assert response.json()["case"]["status"] == "TESTED"
    (run,) = rows(gateway, project, "Runs")
    assert run["status"] == "COMPLETED"
    assert run["triggered_by"] == "an@x.com"
    assert case["id"] in run["scope"]
    (result,) = rows(gateway, project, "Results")
    assert result["executed_by"] == "an@x.com"
    assert result["case_version"] == "1"
    assert result["status"] == "PASS"
    assert response.json()["run_id"] == run["id"]


def test_manual_fail_requires_reason_and_failed_step(
    an: TestClient, project: Project, gateway: FakeSheetsGateway
) -> None:
    case = new_case(an, project)

    no_reason = submit(an, project, case["id"], fail_body(reason="  "))
    no_step = submit(an, project, case["id"], fail_body(failed_step=None))
    bad_step = submit(an, project, case["id"], fail_body(failed_step=3))

    assert [no_reason.status_code, no_step.status_code, bad_step.status_code] == [422] * 3
    assert rows(gateway, project, "Runs") == []


@pytest.mark.parametrize(
    "step_results",
    [
        [{"step_no": 1, "status": "PASS"}],  # thiếu bước 2
        [{"step_no": n, "status": "PASS"} for n in (1, 2, 3)],  # thừa bước 3
        [{"step_no": 1, "status": "PASS"}, {"step_no": 1, "status": "PASS"}],  # trùng
    ],
)
def test_manual_result_step_mismatch_is_422_without_run(
    an: TestClient,
    project: Project,
    gateway: FakeSheetsGateway,
    step_results: list[dict[str, Any]],
) -> None:
    case = new_case(an, project)

    response = submit(an, project, case["id"], result_body(step_results=step_results))

    assert response.status_code == 422
    assert rows(gateway, project, "Runs") == []
    assert case_status(an, project, case["id"]) == "DRAFT"


@pytest.mark.parametrize("which", ["guide-folder", "other-project"])
def test_manual_result_rejects_non_evidence_folder(
    an: TestClient, project: Project, gateway: FakeSheetsGateway, which: str
) -> None:
    case = new_case(an, project)
    if which == "guide-folder":
        bad = media("x", project=project, folder="guide")
    else:
        bad = {**media("x", project=project), "public_id": "ai-test-runner/PRJ-0002/evidence/x"}

    response = submit(an, project, case["id"], result_body(evidence={"screenshots": [bad]}))

    assert response.status_code == 422
    assert rows(gateway, project, "Runs") == []


def test_manual_result_accepts_own_evidence(
    an: TestClient, project: Project, gateway: FakeSheetsGateway
) -> None:
    case = new_case(an, project)
    body = result_body(
        evidence={
            "video": media("v", project=project, kind="video"),
            "screenshots": [media("s", project=project)],
        }
    )

    assert submit(an, project, case["id"], body).status_code == 201
    (result,) = rows(gateway, project, "Results")
    assert f"ai-test-runner/{project.id}/evidence/s" in result["evidence_json"]


def test_manual_result_stale_version_is_409(an: TestClient, project: Project) -> None:
    case = new_case(an, project)

    assert submit(an, project, case["id"], result_body(version=7)).status_code == 409


def test_manual_result_on_automation_case_is_409(an: TestClient, project: Project) -> None:
    case = new_case(an, project, execution_mode="AUTOMATION")

    assert submit(an, project, case["id"], result_body()).status_code == 409


def test_manual_result_on_archived_project_is_409(
    an: TestClient, project: Project, projects: ProjectRepository
) -> None:
    case = new_case(an, project)
    projects.update(project.model_copy(update={"archived": True}))

    assert submit(an, project, case["id"], result_body()).status_code == 409


def test_other_tester_without_assignment_is_403(
    app: FastAPI, users: UserRepository, an: TestClient, project: Project
) -> None:
    case = new_case(an, project)
    binh = client_for(app, users, "binh@x.com", Role.TESTER)

    assert submit(binh, project, case["id"], result_body()).status_code == 403


def test_manual_blocked_keeps_draft_and_no_issue(
    an: TestClient, project: Project, github: FakeGitHub, gateway: FakeSheetsGateway
) -> None:
    case = new_case(an, project)

    response = submit(
        an, project, case["id"], result_body(status="BLOCKED", reason="Staging đang sập")
    )

    assert response.status_code == 201
    assert response.json()["case"]["status"] == "DRAFT"
    assert rows(gateway, project, "Results")[0]["status"] == "BLOCKED"
    assert github.issues == {}


def test_first_fail_creates_issue_assigns_and_labels(
    an: TestClient, project: Project, github: FakeGitHub
) -> None:
    case = new_case(an, project)

    response = submit(an, project, case["id"], fail_body(assignee="nguyenvana"))

    assert response.status_code == 201
    ((issue, body),) = github.issues[project.repo_full_name]
    for label in ("mode: manual", "status:TESTED", "test: fail", "bug: cần sửa"):
        assert label in issue.labels
    assert "Báo cáo cho AI Test Runner" not in body
    assert github.assignees[issue.number] == ["nguyenvana"]
    comment = github.issue_comments[project.repo_full_name][issue.number][0].body
    assert "**Người chạy:** An Nguyễn (test tay)" in comment
    assert "an@x.com" not in comment


def test_manual_fail_then_pass_closes_issue(
    an: TestClient, project: Project, github: FakeGitHub, gateway: FakeSheetsGateway
) -> None:
    case = new_case(an, project)
    first = submit(an, project, case["id"], fail_body(assignee="nguyenvana"))
    version = first.json()["case"]["version"]

    second = submit(an, project, case["id"], result_body(version=version))

    assert second.status_code == 201
    assert second.json()["case"]["status"] == "TESTED"
    assert len(rows(gateway, project, "Runs")) == 2
    ((issue, _),) = github.issues[project.repo_full_name]
    assert issue.state == "closed"
    assert "test: pass" in issue.labels
    assert "bug: cần sửa" not in issue.labels


def test_manual_result_sheet_error_marks_run_failed_503(
    an: TestClient,
    project: Project,
    gateway: FakeSheetsGateway,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = new_case(an, project)
    original = gateway.append_rows

    def fail_results(sheet: str, tab: str, new_rows: list[list[str]]) -> None:
        if tab == "Results":
            raise RuntimeError("Sheet tạm lỗi")
        original(sheet, tab, new_rows)

    monkeypatch.setattr(gateway, "append_rows", fail_results)

    response = submit(an, project, case["id"], result_body())

    assert response.status_code == 503
    assert rows(gateway, project, "Runs")[0]["status"] == "FAILED"
    assert case_status(an, project, case["id"]) == "DRAFT"


def test_manual_fail_notifies_case_creator_and_leads(
    app: FastAPI, an: TestClient, project: Project
) -> None:
    case = new_case(an, project)

    submit(an, project, case["id"], fail_body())

    store: NotificationStore = app.state.services.notifications
    for email in ("lead@x.com", "an@x.com"):
        assert [n.type for n in store.list(email) if n.type == "results_recorded"] == [
            "results_recorded"
        ]


def test_case_detail_has_last_result_for_manual_only(an: TestClient, project: Project) -> None:
    manual = new_case(an, project)
    auto = new_case(an, project, execution_mode="AUTOMATION", title="Case tự động")
    assert an.get(cases_url(project, f"/{manual['id']}")).json()["last_result"] is None

    submit(an, project, manual["id"], fail_body())

    detail = an.get(cases_url(project, f"/{manual['id']}")).json()
    assert detail["last_result"]["status"] == "FAIL"
    assert detail["last_result"]["run_id"] == "RUN-0001"
    assert an.get(cases_url(project, f"/{auto['id']}")).json()["last_result"] is None


def test_dev_owner_defaults_to_screen_dev(
    an: TestClient, lead: TestClient, project: Project, gateway: FakeSheetsGateway
) -> None:
    lead.patch(f"/api/projects/{project.id}/screens/SC-0001", json={"dev_owner": "nguyenvana"})
    case = new_case(an, project)

    submit(an, project, case["id"], result_body())

    assert rows(gateway, project, "Results")[0]["dev_owner"] == "nguyenvana"
