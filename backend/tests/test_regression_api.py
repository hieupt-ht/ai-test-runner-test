"""Chạy bộ regression: tạo run, gắn yêu cầu chạy lại lên issue, gửi kết quả theo run_id."""

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.project_scope import scope_for
from app.core.models.project import Project
from app.core.models.test_case import TestCaseStatus
from tests import test_agent_results_api as base
from tests.fakes import FakeGitHub
from tests.test_test_cases_api import create

TOKEN = {"Authorization": "Bearer test-token"}

# Dùng lại các fixture dự án / QA Lead / tester của test agent
project = base.project
lead = base.lead
an = base.an


def regression_url(project: Project, tail: str = "") -> str:
    return f"/api/projects/{project.id}/regression-runs{tail}"


def approved_case(an: TestClient, lead: TestClient, project: Project, **changes: Any) -> str:
    case = create(an, project, **changes).json()
    an.post(f"/api/projects/{project.id}/test-cases/{case['id']}/submit", json={"version": 1})
    lead.post(f"/api/projects/{project.id}/test-cases/{case['id']}/approve", json={"version": 2})
    return str(case["id"])


def seed_three(
    an: TestClient, lead: TestClient, project: Project
) -> tuple[str, str, str]:
    """2 case regression + 1 case thường, đã duyệt và đã có issue trên GitHub giả."""
    ids = (
        approved_case(an, lead, project, regression=True),
        approved_case(an, lead, project, regression=True),
        approved_case(an, lead, project),
    )
    lead.post(f"/api/projects/{project.id}/test-cases/sync-issues")
    return ids


def test_create_regression_run_takes_only_approved_regression_cases(
    an: TestClient, lead: TestClient, project: Project, github: FakeGitHub
) -> None:
    first, second, _normal = seed_three(an, lead, project)

    response = lead.post(regression_url(project), json={"build_version": "1.4.2"})

    assert response.status_code == 201
    run = response.json()
    assert run["id"] == "RUN-0001"
    assert run["status"] == "RUNNING"
    assert run["total"] == 2
    assert run["build_version"] == "1.4.2"
    assert run["scope"]["regression_only"] is True
    assert run["scope"]["case_ids"] == [first, second]
    commented = [
        body
        for comments in github.issue_comments["org/web"].values()
        for comment in comments
        if (body := comment.body) and "RUN-0001" in body
    ]
    assert len(commented) == 2
    assert 'gửi kèm "run_id"' in commented[0]


def test_create_regression_without_cases_is_400(
    an: TestClient, lead: TestClient, project: Project
) -> None:
    approved_case(an, lead, project)  # chỉ có case thường

    response = lead.post(regression_url(project), json={"build_version": "1.0"})

    assert response.status_code == 400
    assert "Không có case regression nào đã duyệt" in response.json()["detail"]


def test_tester_cannot_create_or_finish_regression(
    an: TestClient, lead: TestClient, project: Project
) -> None:
    seed_three(an, lead, project)

    assert an.post(regression_url(project), json={"build_version": "1"}).status_code == 403
    assert an.post(regression_url(project, "/RUN-0001/finish")).status_code == 403


@pytest.mark.parametrize("build_version", ["", "x" * 51])
def test_build_version_must_be_1_to_50_chars(
    an: TestClient, lead: TestClient, project: Project, build_version: str
) -> None:
    seed_three(an, lead, project)

    response = lead.post(regression_url(project), json={"build_version": build_version})

    assert response.status_code == 422


def test_finish_regression_run_then_finish_again_is_409(
    an: TestClient, lead: TestClient, project: Project
) -> None:
    seed_three(an, lead, project)
    run_id = lead.post(regression_url(project), json={"build_version": "1"}).json()["id"]

    done = lead.post(regression_url(project, f"/{run_id}/finish"))

    assert done.status_code == 200
    assert done.json()["status"] == "COMPLETED"
    assert lead.post(regression_url(project, f"/{run_id}/finish")).status_code == 409
    assert lead.post(regression_url(project, "/RUN-9999/finish")).status_code == 404


def test_regression_still_created_when_github_is_down(
    an: TestClient, lead: TestClient, project: Project, github: FakeGitHub
) -> None:
    seed_three(an, lead, project)
    github.fail_with = RuntimeError("GitHub không khả dụng")

    response = lead.post(regression_url(project), json={"build_version": "1"})

    assert response.status_code == 201


# ---------- Codex gửi kết quả kèm run_id ----------


def post_results(client: TestClient, project: Project, run_id: str | None, *cases: str) -> Any:
    body: dict[str, Any] = {
        "results": [{"test_case_id": case, "status": "PASS", "reason": "Đạt"} for case in cases]
    }
    if run_id is not None:
        body["run_id"] = run_id
    return client.post(
        f"/api/agent/projects/{project.id}/results", json=body, headers=TOKEN
    )


@pytest.fixture
def agent(app: Any, client: TestClient) -> TestClient:
    app.state.settings.agent_api_token = "test-token"
    return client


def test_agent_results_with_run_id_accumulate_until_run_completes(
    agent: TestClient, an: TestClient, lead: TestClient, project: Project
) -> None:
    first, second, _normal = seed_three(an, lead, project)
    run_id = lead.post(regression_url(project), json={"build_version": "1"}).json()["id"]

    one = post_results(agent, project, run_id, first)
    assert one.status_code == 200
    assert one.json()["run_id"] == run_id

    # Mới có 1/2 case: run vẫn đang chạy, kết quả đã hiện ở trang Kết quả
    items = lead.get(f"/api/projects/{project.id}/results").json()
    assert [(item["case_id"], item["run_id"]) for item in items] == [(first, run_id)]

    two = post_results(agent, project, run_id, second)
    assert two.status_code == 200
    # Đủ 2/2 case: cả hai kết quả đều hiện, cùng một lần chạy
    items = lead.get(f"/api/projects/{project.id}/results").json()
    assert sorted((item["case_id"], item["run_id"]) for item in items) == sorted(
        [(first, run_id), (second, run_id)]
    )
    # Run đã tự hoàn tất nên bấm "Kết thúc" nữa sẽ bị từ chối
    assert lead.post(regression_url(project, f"/{run_id}/finish")).status_code == 409


def test_agent_run_totals_after_both_cases(
    agent: TestClient, an: TestClient, lead: TestClient, project: Project, app: Any
) -> None:
    from app.api.project_scope import scope_for

    first, second, _normal = seed_three(an, lead, project)
    run_id = lead.post(regression_url(project), json={"build_version": "1"}).json()["id"]
    post_results(agent, project, run_id, first)
    post_results(agent, project, run_id, second)

    run = scope_for(app.state.services, project).runs.get(run_id)

    assert run is not None
    assert run.status.value == "COMPLETED"
    assert run.passed + run.failed == 2


def test_agent_run_id_of_normal_run_is_409(
    agent: TestClient, an: TestClient, lead: TestClient, project: Project
) -> None:
    first, _second, _normal = seed_three(an, lead, project)
    # Gửi không kèm run_id: app tạo một run thường (đã COMPLETED)
    normal_run = post_results(agent, project, None, first).json()["run_id"]

    response = post_results(agent, project, normal_run, first)

    assert response.status_code == 409
    assert "không phải lần chạy regression" in response.json()["detail"]


def test_agent_case_outside_run_scope_is_ignored(
    agent: TestClient, an: TestClient, lead: TestClient, project: Project
) -> None:
    first, _second, normal = seed_three(an, lead, project)
    run_id = lead.post(regression_url(project), json={"build_version": "1"}).json()["id"]

    response = post_results(agent, project, run_id, first, normal)

    body = response.json()
    assert response.status_code == 200
    assert body["written"] == 1
    assert [item["test_case_id"] for item in body["ignored"]] == [normal]


def test_agent_unknown_run_id_is_404(
    agent: TestClient, an: TestClient, lead: TestClient, project: Project
) -> None:
    first, _second, _normal = seed_three(an, lead, project)

    assert post_results(agent, project, "RUN-9999", first).status_code == 404


def test_list_open_regression_runs_for_the_finish_button(
    an: TestClient, lead: TestClient, project: Project
) -> None:
    seed_three(an, lead, project)
    assert lead.get(regression_url(project)).json() == []

    run_id = lead.post(regression_url(project), json={"build_version": "1"}).json()["id"]
    assert [run["id"] for run in an.get(regression_url(project)).json()] == [run_id]

    lead.post(regression_url(project, f"/{run_id}/finish"))
    assert lead.get(regression_url(project)).json() == []


def test_regression_run_skips_manual_cases(
    app: FastAPI, an: TestClient, lead: TestClient, project: Project
) -> None:
    auto = approved_case(an, lead, project, regression=True)
    manual = create(an, project, regression=True, execution_mode="MANUAL").json()["id"]
    scope = scope_for(app.state.services, project)
    scope.test_cases.save(
        scope.test_cases.get(manual).model_copy(update={"status": TestCaseStatus.APPROVED}),  # type: ignore[union-attr]
        expected_version=1,
        actor="lead@x.com",
    )

    response = lead.post(regression_url(project), json={"build_version": "1.0"})

    assert response.status_code == 201
    assert response.json()["scope"]["case_ids"] == [auto]
