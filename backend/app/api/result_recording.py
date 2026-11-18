"""Phần dùng chung khi ghi kết quả test: báo cho người liên quan và cập nhật issue GitHub.

Agent (`routers/agent.py`) và tester test tay (`routers/manual_results.py`) cùng dùng.
Cả hai hàm chỉ ghi log khi lỗi: kết quả đã nằm trong Sheet, không được vì thế mà báo lỗi.
"""

import logging
from collections.abc import Iterable

from app.api.services import Services
from app.core.models.project import Project
from app.core.models.run import Result, Run
from app.core.models.test_case import TestCase
from app.core.models.user import Role
from app.core.services.notify import Notifier
from app.core.services.result_issue_sync import sync_result_issue

logger = logging.getLogger(__name__)


def notify_results_recorded(
    services: Services, project: Project, run: Run, *, failed_case_creators: Iterable[str]
) -> None:
    """Báo cho Admin, QA Lead của dự án và người tạo các case FAIL là lần chạy đã xong."""
    try:
        member_emails = {member.email for member in services.members.list_for_project(project.id)}
        recipients = {
            user.email
            for user in services.users.list_all()
            if user.active
            and (
                user.role == Role.ADMIN
                or (user.role == Role.QA_LEAD and user.email in member_emails)
            )
        }
        recipients.update(failed_case_creators)
        Notifier(services.notifications).results_recorded(
            emails=sorted(recipients),
            project_id=project.id,
            run_id=run.id,
            failed=run.failed,
            total=run.total,
        )
    except Exception:
        logger.warning("Không xác định được người nhận kết quả run %s", run.id, exc_info=True)


def sync_issues_for_results(
    services: Services,
    project: Project,
    run: Run,
    results: list[Result],
    cases: dict[str, TestCase],
    *,
    duration: float = 0,
    runner_name: str | None = None,
) -> None:
    """Đưa từng kết quả lên issue của case (comment + nhãn + trạng thái mở/đóng)."""
    if services.github is None:
        return
    for result in results:
        case = cases.get(result.test_case_id)
        if case is None:
            continue
        try:
            sync_result_issue(
                services.github,
                repo=project.repo_full_name,
                project_id=project.id,
                app_url=services.app_base_url,
                run=run,
                result=result,
                case=case,
                duration=duration,
                runner_name=runner_name,
            )
        except Exception:
            logger.warning(
                "Không đồng bộ được issue GitHub cho case %s của dự án %s",
                result.test_case_id,
                project.id,
                exc_info=True,
            )
