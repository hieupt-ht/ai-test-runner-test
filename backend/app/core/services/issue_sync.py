"""Đồng bộ một test case từ Sheet sang issue ở repo của dự án."""

import logging
from collections.abc import Callable
from concurrent.futures import Executor, ThreadPoolExecutor
from typing import Literal, Protocol

from app.core.github.client import GitHubClient
from app.core.github.issue_format import case_label, render_issue
from app.core.models.project import Project
from app.core.models.screen import Screen
from app.core.models.test_case import ExecutionMode, TestCase, TestCaseStatus
from app.core.services.rerun_request import request_rerun_on_issue
from app.core.time import utc_now

SyncResult = Literal["created", "updated", "closed", "reopened", "skipped"]
logger = logging.getLogger(__name__)


class IssueSink(Protocol):
    def sync_case(
        self,
        project: Project,
        case: TestCase,
        *,
        screen_name: str = "",
        screen: Screen | None = None,
    ) -> None: ...

    def note_case_edited(
        self, project: Project, case: TestCase, *, changed: list[str], needs_rerun: bool
    ) -> None: ...


# Nhãn do app tự sinh từ case: được thay mới mỗi lần đồng bộ. Mọi nhãn khác giữ nguyên.
APP_LABEL_PREFIXES = ("status:", "platform:", "mode:")


def _merge_labels(new_labels: list[str], old_labels: list[str]) -> list[str]:
    """Nhãn mới của case + nhãn cũ không do app sinh (needs-rerun, test: fail, nhãn tay...)."""
    kept = [
        label
        for label in old_labels
        if label not in new_labels and not label.startswith(APP_LABEL_PREFIXES)
    ]
    return [*new_labels, *kept]


def _should_create_issue(case: TestCase) -> bool:
    """Case Automation: tạo issue khi đã duyệt. Case test tay: khi đã có kết quả (TESTED)."""
    if case.execution_mode == ExecutionMode.MANUAL:
        return case.status == TestCaseStatus.TESTED
    return case.status == TestCaseStatus.APPROVED


class IssueSyncer:
    def __init__(
        self,
        github: GitHubClient | None,
        *,
        app_base_url: str = "http://localhost:3000",
    ) -> None:
        self._github = github
        self._app_base_url = app_base_url

    def sync_case(
        self,
        project: Project,
        case: TestCase,
        *,
        screen_name: str = "",
        screen: Screen | None = None,
    ) -> SyncResult:
        github = self._github
        if github is None or project.archived:
            return "skipped"

        content = render_issue(
            case,
            project=project,
            screen=screen,
            screen_name=screen_name,
            project_id=project.id,
            app_base_url=self._app_base_url,
        )
        # Mã case chỉ duy nhất bên trong một dự án; luôn tìm trong repo của dự án đó.
        existing = github.find_issue_by_label(project.repo_full_name, content.labels[1])
        if existing is None and not _should_create_issue(case):
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
            labels=_merge_labels(content.labels, existing.labels),
            state=state,
        )
        if state == "closed" and existing.state == "open":
            return "closed"
        if state == "open" and existing.state == "closed":
            return "reopened"
        return "updated"


    def note_case_edited(
        self, project: Project, case: TestCase, *, changed: list[str], needs_rerun: bool
    ) -> None:
        """Comment "case đã sửa" lên issue; đổi phần ảnh hưởng kết quả cũ thì yêu cầu chạy lại."""
        github = self._github
        if github is None or project.archived:
            return
        issue = github.find_issue_by_label(project.repo_full_name, case_label(case.id))
        if issue is None:
            return
        body = f"📝 Case đã sửa lên v{case.version}: {', '.join(changed)}"
        github.create_issue_comment(project.repo_full_name, issue.number, body)
        if needs_rerun:
            request_rerun_on_issue(
                github,
                repo=project.repo_full_name,
                case_id=case.id,
                user_name=case.updated_by,
                requested_at=utc_now(),
            )


class BackgroundIssueSync:
    """Một luồng duy nhất để không gọi GitHub dồn dập."""

    def __init__(self, syncer: IssueSyncer, *, executor: Executor | None = None) -> None:
        self._syncer = syncer
        self._executor = executor or ThreadPoolExecutor(max_workers=1)

    def sync_case(
        self,
        project: Project,
        case: TestCase,
        *,
        screen_name: str = "",
        screen: Screen | None = None,
    ) -> None:
        self._executor.submit(self._sync_safely, project, case, screen_name, screen)

    def submit(self, work: Callable[[], None]) -> None:
        """Chạy một việc GitHub trên cùng luồng duy nhất (nối đuôi các việc trước đó)."""
        self._executor.submit(work)

    def note_case_edited(
        self, project: Project, case: TestCase, *, changed: list[str], needs_rerun: bool
    ) -> None:
        # Cùng executor một luồng với sync_case nên luôn chạy SAU lần đồng bộ trước đó
        self._executor.submit(self._note_safely, project, case, changed, needs_rerun)

    def _note_safely(
        self, project: Project, case: TestCase, changed: list[str], needs_rerun: bool
    ) -> None:
        try:
            self._syncer.note_case_edited(project, case, changed=changed, needs_rerun=needs_rerun)
        except Exception:
            logger.warning("Không báo được case %s đã sửa lên issue", case.id)

    def _sync_safely(
        self, project: Project, case: TestCase, screen_name: str, screen: Screen | None
    ) -> None:
        try:
            self._syncer.sync_case(project, case, screen_name=screen_name, screen=screen)
        except Exception:
            logger.warning("Không đồng bộ được issue cho case %s của dự án %s", case.id, project.id)
