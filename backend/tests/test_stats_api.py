"""API số liệu và bảng xếp hạng của một project."""

# Dùng lại fixture của test kết quả tay; pytest cần tên fixture trùng tên tham số nên ruff báo F811.
# ruff: noqa: F811

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.models.project import Project
from app.core.models.user import Role
from app.core.repositories.users import UserRepository
from tests.conftest import client_for
from tests.test_manual_results_api import (  # noqa: F401
    an,
    fail_body,
    lead,
    new_case,
    project,
    result_body,
    submit,
)


def stats_url(project: Project) -> str:
    return f"/api/projects/{project.id}/stats"


def board_url(project: Project, query: str = "") -> str:
    return f"/api/projects/{project.id}/leaderboard{query}"


def test_member_sees_project_stats(an: TestClient, project: Project) -> None:
    case = new_case(an, project)
    assert submit(an, project, case["id"], fail_body(project)).status_code == 201

    body = an.get(stats_url(project)).json()

    assert body["total_cases"] == 1
    assert body["open_bugs"] == 1
    assert body["pass_rate"] == 0.0
    assert len(body["daily"]) == 14


def test_non_member_gets_404(app: FastAPI, users: UserRepository, project: Project) -> None:
    outsider = client_for(app, users, "ngoai@x.com", Role.TESTER)
    assert outsider.get(stats_url(project)).status_code == 404
    assert outsider.get(board_url(project)).status_code == 404


def test_admin_sees_any_project_stats(
    app: FastAPI, users: UserRepository, project: Project
) -> None:
    admin = client_for(app, users, "admin@x.com", Role.ADMIN)
    assert admin.get(stats_url(project)).status_code == 200
    assert admin.get(board_url(project)).status_code == 200


def test_leaderboard_returns_names_not_result_details(an: TestClient, project: Project) -> None:
    case = new_case(an, project)
    submit(an, project, case["id"], fail_body(project))

    body = an.get(board_url(project, "?period=all")).json()

    assert set(body) == {"period", "cases", "bugs"}
    (row,) = body["bugs"]["top"]
    assert set(row) == {"rank", "email", "name", "count"}
    assert (row["email"], row["name"], row["count"]) == ("an@x.com", "An Nguyễn", 1)


def test_leaderboard_rejects_unknown_period(an: TestClient, project: Project) -> None:
    assert an.get(board_url(project, "?period=year")).status_code == 422


def test_manual_result_updates_stats_right_away(an: TestClient, project: Project) -> None:
    case = new_case(an, project)
    assert an.get(stats_url(project)).json()["open_bugs"] == 0  # đã được cache

    submit(an, project, case["id"], fail_body(project))

    assert an.get(stats_url(project)).json()["open_bugs"] == 1
