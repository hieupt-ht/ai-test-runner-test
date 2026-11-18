"""Đồng bộ issue theo repo và trạng thái case."""

from collections.abc import Callable
from concurrent.futures import Future
from datetime import UTC, datetime

import pytest

from app.core.github.client import GitHubError
from app.core.models.project import Project
from app.core.models.test_case import ExecutionMode, Platform, TestCaseStatus
from app.core.services.issue_sync import BackgroundIssueSync, IssueSyncer
from tests.fakes import FakeGitHub
from tests.test_issue_format import make_case


def make_project() -> Project:
    return Project(
        id="PRJ-0001",
        name="Dự án",
        repo_full_name="org/web",
        branch="main",
        staging_url="",
        spreadsheet_id="sheet-1",
        archived=False,
        created_at=datetime.now(UTC),
    )


def test_approved_case_without_issue_creates_one_with_labels() -> None:
    github = FakeGitHub()
    result = IssueSyncer(github, app_base_url="https://runner.example.com").sync_case(
        make_project(), make_case()
    )
    assert result == "created"
    issue, body = github.issues["org/web"][0]
    assert issue.labels == ["test-case", "tc:TC-000123", "status:APPROVED", "platform: web"]
    assert "Mã dự án: `PRJ-0001`" in body
    assert (
        "Endpoint: `https://runner.example.com/api/agent/projects/PRJ-0001/results`"
        in body
    )


def test_draft_case_without_issue_is_skipped() -> None:
    github = FakeGitHub()
    assert (
        IssueSyncer(github).sync_case(make_project(), make_case(status=TestCaseStatus.DRAFT))
        == "skipped"
    )
    assert not github.issues


def test_second_sync_updates_not_duplicates() -> None:
    github = FakeGitHub()
    syncer = IssueSyncer(github)
    project, case = make_project(), make_case()
    assert syncer.sync_case(project, case) == "created"
    assert syncer.sync_case(project, case) == "updated"
    assert len(github.issues["org/web"]) == 1


def test_status_change_replaces_status_label() -> None:
    github = FakeGitHub()
    syncer = IssueSyncer(github)
    project = make_project()
    syncer.sync_case(project, make_case())
    syncer.sync_case(project, make_case(status=TestCaseStatus.DRAFT))
    assert github.issues["org/web"][0][0].labels == [
        "test-case",
        "tc:TC-000123",
        "status:DRAFT",
        "platform: web",
    ]


def test_update_keeps_result_labels() -> None:
    github = FakeGitHub()
    syncer = IssueSyncer(github)
    project = make_project()
    syncer.sync_case(project, make_case())
    old, body = github.issues["org/web"][0]
    github.issues["org/web"][0] = (
        old.model_copy(
            update={"labels": [*old.labels, "needs-rerun", "test: fail", "bug: cần sửa"]}
        ),
        body,
    )

    syncer.sync_case(project, make_case(platform=Platform.ANDROID))

    labels = github.issues["org/web"][0][0].labels
    assert "platform: android" in labels
    assert "platform: web" not in labels
    for kept in ("needs-rerun", "test: fail", "bug: cần sửa", "test-case", "tc:TC-000123"):
        assert kept in labels
    assert labels.count("status:APPROVED") == 1


def test_update_replaces_old_status_label() -> None:
    github = FakeGitHub()
    syncer = IssueSyncer(github)
    project = make_project()
    syncer.sync_case(project, make_case())
    syncer.sync_case(project, make_case(status=TestCaseStatus.DRAFT))
    labels = github.issues["org/web"][0][0].labels
    assert "status:DRAFT" in labels
    assert "status:APPROVED" not in labels


def test_deprecated_closes_and_restore_reopens() -> None:
    github = FakeGitHub()
    syncer = IssueSyncer(github)
    project = make_project()
    syncer.sync_case(project, make_case())
    assert syncer.sync_case(project, make_case(status=TestCaseStatus.DEPRECATED)) == "closed"
    assert github.issues["org/web"][0][0].state == "closed"
    assert syncer.sync_case(project, make_case()) == "reopened"
    assert github.issues["org/web"][0][0].state == "open"


def test_no_github_configured_is_skipped() -> None:
    assert IssueSyncer(None).sync_case(make_project(), make_case()) == "skipped"


def test_archived_project_is_skipped() -> None:
    github = FakeGitHub()
    project = make_project().model_copy(update={"archived": True})
    assert IssueSyncer(github).sync_case(project, make_case()) == "skipped"
    assert not github.calls


class ImmediateExecutor:
    def submit(self, fn: Callable[..., None], /, *args: object, **kwargs: object) -> Future[None]:
        future: Future[None] = Future()
        try:
            fn(*args, **kwargs)
            future.set_result(None)
        except Exception as error:
            future.set_exception(error)
        return future


def test_background_swallows_github_error_and_logs_case_id_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    github = FakeGitHub()
    github.fail_with = GitHubError("GitHub trả lỗi 404")
    sink = BackgroundIssueSync(IssueSyncer(github), executor=ImmediateExecutor())
    sink.sync_case(make_project(), make_case(title="Tựa đề bí mật"))
    assert "TC-000123" in caplog.text
    assert "Tựa đề bí mật" not in caplog.text


def test_same_case_id_in_two_projects_gets_issues_in_their_own_repos() -> None:
    github = FakeGitHub()
    syncer = IssueSyncer(github)
    project = make_project()
    other = project.model_copy(update={"id": "PRJ-0002", "repo_full_name": "other/app"})
    syncer.sync_case(project, make_case())
    syncer.sync_case(other, make_case())
    assert len(github.issues["org/web"]) == len(github.issues["other/app"]) == 1


def test_note_case_edited_comments_then_requests_rerun() -> None:
    github = FakeGitHub()
    syncer = IssueSyncer(github)
    project, case = make_project(), make_case(version=3)
    syncer.sync_case(project, case)

    syncer.note_case_edited(project, case, changed=["Các bước", "Nền tảng"], needs_rerun=True)

    bodies = [c.body for c in github.issue_comments["org/web"][1]]
    assert "📝 Case đã sửa lên v3: Các bước, Nền tảng" in bodies[0]
    assert "needs-rerun" in github.issues["org/web"][0][0].labels


def test_note_case_edited_without_rerun_only_comments() -> None:
    github = FakeGitHub()
    syncer = IssueSyncer(github)
    project, case = make_project(), make_case(version=2)
    syncer.sync_case(project, case)

    syncer.note_case_edited(project, case, changed=["Tiêu đề"], needs_rerun=False)

    assert "needs-rerun" not in github.issues["org/web"][0][0].labels
    assert len(github.issue_comments["org/web"][1]) == 1


def test_background_note_runs_after_sync() -> None:
    github = FakeGitHub()
    sink = BackgroundIssueSync(IssueSyncer(github), executor=ImmediateExecutor())
    project, case = make_project(), make_case(version=3)

    sink.sync_case(project, case)
    sink.note_case_edited(project, case, changed=["Các bước"], needs_rerun=False)

    assert github.calls.index("create") < github.calls.index("comments:create")


def test_manual_draft_case_is_skipped_but_tested_case_creates_issue() -> None:
    github = FakeGitHub()
    syncer = IssueSyncer(github)
    manual = {"execution_mode": ExecutionMode.MANUAL}

    assert (
        syncer.sync_case(make_project(), make_case(status=TestCaseStatus.APPROVED, **manual))
        == "skipped"
    )
    assert (
        syncer.sync_case(make_project(), make_case(status=TestCaseStatus.TESTED, **manual))
        == "created"
    )
    assert "mode: manual" in github.issues["org/web"][0][0].labels


def test_switching_to_automation_drops_mode_label() -> None:
    github = FakeGitHub()
    syncer = IssueSyncer(github)
    syncer.sync_case(
        make_project(),
        make_case(status=TestCaseStatus.TESTED, execution_mode=ExecutionMode.MANUAL),
    )

    syncer.sync_case(make_project(), make_case(status=TestCaseStatus.APPROVED))

    assert "mode: manual" not in github.issues["org/web"][0][0].labels
