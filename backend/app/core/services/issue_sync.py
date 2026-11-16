"""Đồng bộ một test case từ Sheet sang issue ở repo của dự án."""

import logging
from concurrent.futures import Executor, ThreadPoolExecutor
from typing import Literal, Protocol

from app.core.github.client import GitHubClient
from app.core.github.issue_format import render_issue
from app.core.models.project import Project
from app.core.models.test_case import TestCase, TestCaseStatus

SyncResult = Literal["created", "updated", "closed", "reopened", "skipped"]
logger = logging.getLogger(__name__)


class IssueSink(Protocol):
    def sync_case(self, project: Project, case: TestCase, *, screen_name: str = "") -> None: ...


class IssueSyncer:
    def __init__(
        self,
        github: GitHubClient | None,
        *,
        app_base_url: str = "http://localhost:3000",
    ) -> None:
        self._github = github
        self._app_base_url = app_base_url

    def sync_case(self, project: Project, case: TestCase, *, screen_name: str = "") -> SyncResult:
        github = self._github
        if github is None or project.archived:
            return "skipped"

        content = render_issue(
            case,
            screen_name=screen_name,
            project_id=project.id,
            app_base_url=self._app_base_url,
        )
        # Mã case chỉ duy nhất bên trong một dự án; luôn tìm trong repo của dự án đó.
        existing = github.find_issue_by_label(project.repo_full_name, content.labels[1])
        if existing is None and case.status != TestCaseStatus.APPROVED:
            return "skipped"

        for label in content.labels:
            github.ensure_label(project.repo_full_name, label)

        if existing is None:
            github.create_issue(
                project.repo_full_name,
                title=content.title,
                body=content.body,
                labels=content.labels,
            )
            return "created"

        state: Literal["open", "closed"] = (
            "closed" if case.status == TestCaseStatus.DEPRECATED else "open"
        )
        github.update_issue(
            project.repo_full_name,
            existing.number,
            title=content.title,
            body=content.body,
            labels=content.labels,
            state=state,
        )
        if state == "closed" and existing.state == "open":
            return "closed"
        if state == "open" and existing.state == "closed":
            return "reopened"
        return "updated"


class BackgroundIssueSync:
    """Một luồng duy nhất để không gọi GitHub dồn dập."""

    def __init__(self, syncer: IssueSyncer, *, executor: Executor | None = None) -> None:
        self._syncer = syncer
        self._executor = executor or ThreadPoolExecutor(max_workers=1)

    def sync_case(self, project: Project, case: TestCase, *, screen_name: str = "") -> None:
        self._executor.submit(self._sync_safely, project, case, screen_name)

    def _sync_safely(self, project: Project, case: TestCase, screen_name: str) -> None:
        try:
            self._syncer.sync_case(project, case, screen_name=screen_name)
        except Exception:
            logger.warning("Không đồng bộ được issue cho case %s của dự án %s", case.id, project.id)
