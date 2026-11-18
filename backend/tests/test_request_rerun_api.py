"""Test endpoint yêu cầu chạy lại case FAIL/BLOCKED."""

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.github.client import GitHubError
from app.core.github.issue_format import case_label
from app.core.models.project import Project
from app.core.models.user import Role
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import ProjectRepository
from app.core.repositories.users import UserRepository
from tests.conftest import client_for, make_project, make_user
from tests.fakes import FakeGitHub, FakeSheetsGateway
from tests.test_results_api import seed_results

RERUN_MARKER = "<!-- ai-test-runner-rerun -->"


@pytest.fixture
def project(
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
    users: UserRepository,
) -> Project:
    users.create(make_user("an@x.com", role=Role.TESTER))
    users.create(make_user("binh@x.com", role=Role.TESTER))
    return make_project(
        projects,
        members,
        gateway,
        member_emails=("lead@x.com", "an@x.com", "binh@x.com"),
    )


def rerun_url(project: Project, case_id: str) -> str:
    return f"/api/projects/{project.id}/test-cases/{case_id}/request-rerun"


def closed_issue(github: FakeGitHub, project: Project, case_id: str) -> None:
    """Tạo sẵn issue của case: đã đóng và đang có cả hai nhãn kết quả cũ."""
    issue = github.create_issue(
        project.repo_full_name,
        title="Case",
        body="",
        labels=[case_label(case_id), "test: fail", "test: pass"],
    )
    github.update_issue_state_and_labels(
        project.repo_full_name, issue.number, state="closed", labels=issue.labels
    )


def test_qa_lead_request_rerun_does_three_github_actions(
    app: FastAPI,
    users: UserRepository,
    project: Project,
    github: FakeGitHub,
) -> None:
    failed_id, _ = seed_results(app, project)  # case đầu có kết quả mới nhất là FAIL
    closed_issue(github, project, failed_id)
    lead = client_for(app, users, "lead@x.com", Role.QA_LEAD)

    response = lead.post(rerun_url(project, failed_id))

    assert response.status_code == 204
    issue, _ = github.issues[project.repo_full_name][0]
    # 1. có comment đánh dấu yêu cầu chạy lại
    comments = github.issue_comments[project.repo_full_name][issue.number]
    assert len(comments) == 1
    assert RERUN_MARKER in comments[0].body
    assert "Yêu cầu chạy lại" in comments[0].body
    # 2. issue được mở lại
    assert issue.state == "open"
    # 3. nhãn needs-rerun có màu, nhãn kết quả cũ bị bỏ
    assert github.labels[project.repo_full_name]["needs-rerun"] == "e6a817"
    assert "needs-rerun" in issue.labels
    assert "test: pass" not in issue.labels
    assert "test: fail" not in issue.labels
    assert case_label(failed_id) in issue.labels


def test_tester_cannot_request_rerun(
    app: FastAPI,
    users: UserRepository,
    project: Project,
) -> None:
    failed_id, _ = seed_results(app, project)

    response = client_for(app, users, "an@x.com", Role.TESTER).post(
        rerun_url(project, failed_id)
    )

    assert response.status_code == 403


def test_pass_case_is_rejected(
    app: FastAPI,
    users: UserRepository,
    project: Project,
) -> None:
    _, passed_id = seed_results(app, project)

    response = client_for(app, users, "lead@x.com", Role.QA_LEAD).post(
        rerun_url(project, passed_id)
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Case này không có kết quả FAIL hoặc BLOCKED"}


def test_case_without_result_is_rejected(
    app: FastAPI,
    users: UserRepository,
    project: Project,
) -> None:
    response = client_for(app, users, "lead@x.com", Role.QA_LEAD).post(
        rerun_url(project, "TC-999999")
    )

    assert response.status_code == 400


def test_without_github_is_503(
    app: FastAPI,
    users: UserRepository,
    project: Project,
) -> None:
    failed_id, _ = seed_results(app, project)
    app.state.services.github = None

    response = client_for(app, users, "lead@x.com", Role.QA_LEAD).post(
        rerun_url(project, failed_id)
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Chưa cấu hình GitHub"}


def test_github_error_still_returns_204_and_logs_warning(
    app: FastAPI,
    users: UserRepository,
    project: Project,
    github: FakeGitHub,
    caplog: pytest.LogCaptureFixture,
) -> None:
    failed_id, _ = seed_results(app, project)
    closed_issue(github, project, failed_id)
    github.fail_with = GitHubError("GitHub tạm lỗi")
    lead: TestClient = client_for(app, users, "lead@x.com", Role.QA_LEAD)

    with caplog.at_level(logging.WARNING):
        response = lead.post(rerun_url(project, failed_id))

    assert response.status_code == 204
    assert any(record.levelno == logging.WARNING for record in caplog.records)
