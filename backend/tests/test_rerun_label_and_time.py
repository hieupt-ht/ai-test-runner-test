"""Test hai chi tiết của tính năng chạy lại: giờ Việt Nam và tự bỏ nhãn needs-rerun."""

from datetime import UTC, datetime

import pytest

from app.core.github.client import IssueInfo
from app.core.services.rerun_request import RERUN_LABEL, format_rerun_comment
from app.core.services.result_issue_sync import sync_issue_state
from tests.fakes import FakeGitHub


def test_rerun_comment_uses_vietnam_time() -> None:
    # 07:42 UTC = 14:42 giờ Việt Nam
    body = format_rerun_comment("QA", datetime(2026, 11, 15, 7, 42, tzinfo=UTC))

    assert "2026-11-15 14:42" in body


@pytest.mark.parametrize("passed", [True, False])
def test_new_result_removes_needs_rerun_label(passed: bool) -> None:
    github = FakeGitHub()
    issue = github.create_issue(
        "org/web",
        title="Case",
        body="",
        labels=["tc:TC-000001", RERUN_LABEL, "test: fail"],
    )

    sync_issue_state(github, "org/web", issue, passed)

    updated: IssueInfo = github.issues["org/web"][0][0]
    assert RERUN_LABEL not in updated.labels
    assert "tc:TC-000001" in updated.labels
