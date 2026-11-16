import logging

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentUser, ServicesDep
from app.api.project_scope import ProjectScope, scope_for
from app.api.routers.results import ResultItem, results_for_project
from app.api.services import Services
from app.core.models.assignment import MyAssignment, ReturnedCase
from app.core.models.project import Project
from app.core.models.test_case import TestCase, TestCaseStatus
from app.core.models.user import Role
from app.core.sheets.gateway import SheetAccessDeniedError
from app.core.sheets.table import MissingColumnsError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/me", tags=["me"])


class OverviewSummary(BaseModel):
    pending_review: int = 0
    latest_result: ResultItem | None = None


@router.get("/overview")
def my_overview(user: CurrentUser, services: ServicesDep) -> OverviewSummary:
    """Số case chờ duyệt và kết quả mới nhất trên mọi dự án người dùng được xem."""
    if user.role not in {Role.QA_LEAD, Role.ADMIN}:
        return OverviewSummary()

    if user.role == Role.ADMIN:
        visible_projects = services.projects.list_all()
    else:
        my_project_ids = set(services.members.projects_of(user.email))
        visible_projects = [
            project
            for project in services.projects.list_all()
            if project.id in my_project_ids and not project.archived
        ]

    pending_review = 0
    latest_result: ResultItem | None = None
    for project in visible_projects:
        try:
            scope = scope_for(services, project)
            cases = scope.test_cases.list_all()
            if not project.archived:
                pending_review += sum(
                    case.status == TestCaseStatus.IN_REVIEW for case in cases
                )
            project_results = results_for_project(services, project, user, cases=cases)
            if project_results:
                candidate = max(project_results, key=lambda item: item.finished_at)
                if latest_result is None or candidate.finished_at > latest_result.finished_at:
                    latest_result = candidate
        except (SheetAccessDeniedError, MissingColumnsError):
            logger.warning(
                "Bỏ qua dữ liệu Tổng quan của dự án %s vì không đọc được Sheet",
                project.id,
                exc_info=True,
            )
    return OverviewSummary(pending_review=pending_review, latest_result=latest_result)


@router.get("/assignments")
def my_assignments(user: CurrentUser, services: ServicesDep) -> list[MyAssignment]:
    """Trang "Việc của tôi": mọi màn hình user được giao, ở mọi dự án đang hoạt động."""
    my_project_ids = set(services.members.projects_of(user.email))
    active_projects = [
        project
        for project in services.projects.list_all()
        if project.id in my_project_ids and not project.archived
    ]

    result: list[MyAssignment] = []
    for project in active_projects:
        try:
            result.extend(_assignments_in(services, project, user.email))
        except (SheetAccessDeniedError, MissingColumnsError):
            # Sheet của MỘT dự án bị hỏng (mất quyền, mất cột) thì bỏ qua dự án đó,
            # vẫn hiện việc ở các dự án khác. Ghi log để Admin biết mà sửa.
            logger.warning("Bỏ qua dự án %s: không đọc được Sheet", project.id, exc_info=True)
    return sorted(result, key=lambda item: (item.deadline, item.project_name))


def _assignments_in(services: Services, project: Project, email: str) -> list[MyAssignment]:
    scope = scope_for(services, project)
    mine = [a for a in scope.assignments.list_all() if a.assignee_email == email]
    if not mine:
        return []
    cases = scope.test_cases.list_all()
    returned = _returned_cases(scope, cases, email)
    screen_names = {screen.id: screen.name for screen in scope.screens.list_all()}
    return [
        MyAssignment(
            assignment_id=a.id,
            project_id=project.id,
            project_name=project.name,
            screen_id=a.screen_id,
            screen_name=screen_names.get(a.screen_id, a.screen_id),
            deadline=a.deadline,
            status=a.status,
            case_counts=_count_by_status(cases, a.screen_id, email),
            returned_cases=returned.get(a.screen_id, []),
        )
        for a in mine
    ]


def _count_by_status(
    cases: list[TestCase], screen_id: str, email: str
) -> dict[TestCaseStatus, int]:
    """Đếm case do `email` tạo trên màn hình, đủ 4 trạng thái (không có thì 0)."""
    counts: dict[TestCaseStatus, int] = {
        status: 0 for status in TestCaseStatus if status != TestCaseStatus.ARCHIVED
    }
    for case in cases:
        if (
            case.status != TestCaseStatus.ARCHIVED
            and case.screen_id == screen_id
            and case.created_by == email
        ):
            counts[case.status] += 1
    return counts


def _returned_cases(
    scope: ProjectScope, cases: list[TestCase], email: str
) -> dict[str, list[ReturnedCase]]:
    """Case Nháp của `email` đang ở trạng thái "bị trả lại", gom theo màn hình."""
    drafts = [c for c in cases if c.created_by == email and c.status == TestCaseStatus.DRAFT]
    if not drafts:
        return {}  # không có Nháp thì khỏi đọc AuditLog
    returns = scope.audit_log.latest_returns("test_case", [c.id for c in drafts])
    result: dict[str, list[ReturnedCase]] = {}
    for case in drafts:
        if case.id in returns:
            entry = returns[case.id]
            result.setdefault(case.screen_id, []).append(
                ReturnedCase(
                    case_id=case.id,
                    title=case.title,
                    comment=str(entry.diff.get("comment", "")),
                    returned_by=entry.actor,
                )
            )
    return result
