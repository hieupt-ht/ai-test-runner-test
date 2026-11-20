import logging

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentUser, ServicesDep
from app.api.project_facts import load_facts
from app.api.project_scope import ProjectScope, scope_for
from app.api.routers.results import ResultItem, results_for_project
from app.api.services import Services
from app.core.models.assignment import MyAssignment, ReturnedCase
from app.core.models.project import Project
from app.core.models.stats import MyDashboard, MyPet, ProjectFacts, ProjectProgress
from app.core.models.test_case import TestCase, TestCaseStatus
from app.core.models.user import Role, User
from app.core.services.stats import build_pet, daily_counts, progress
from app.core.sheets.gateway import SheetAccessDeniedError
from app.core.sheets.table import MissingColumnsError
from app.core.time import today_in_vietnam

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
                pending_review += sum(case.status == TestCaseStatus.IN_REVIEW for case in cases)
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


def _facts_of_projects(
    services: Services, wanted: list[Project]
) -> list[tuple[Project, ProjectFacts]]:
    """Bản tóm tắt của từng project; project có Sheet hỏng thì bỏ qua (giống `my_overview`)."""
    found: list[tuple[Project, ProjectFacts]] = []
    for project in wanted:
        try:
            found.append((project, load_facts(services, scope_for(services, project))))
        except (SheetAccessDeniedError, MissingColumnsError):
            logger.warning("Bỏ qua project %s: không đọc được Sheet", project.id, exc_info=True)
    return found


def _my_projects(services: Services, user: User, *, include_archived: bool) -> list[Project]:
    """Admin thấy mọi project; người khác chỉ thấy project mình là thành viên."""
    all_projects = services.projects.list_all()
    if user.role != Role.ADMIN:
        mine = set(services.members.projects_of(user.email))
        all_projects = [project for project in all_projects if project.id in mine]
    return [project for project in all_projects if include_archived or not project.archived]


@router.get("/pet")
def my_pet(user: CurrentUser, services: ServicesDep) -> MyPet:
    """Con nhím của tôi. Project đã lưu trữ vẫn tính để nhím không bị nhỏ lại."""
    found = _facts_of_projects(services, _my_projects(services, user, include_archived=True))
    return build_pet([facts for _, facts in found], user.email, today_in_vietnam())


@router.get("/dashboard")
def my_dashboard(user: CurrentUser, services: ServicesDep) -> MyDashboard:
    """Tiến độ từng project đang hoạt động và số lần chạy 14 ngày qua của tôi."""
    found = _facts_of_projects(services, _my_projects(services, user, include_archived=False))
    items: list[ProjectProgress] = []
    for project, facts in found:
        done, total = progress(facts)
        items.append(
            ProjectProgress(
                project_id=project.id, project_name=project.name, done=done, total=total
            )
        )
    daily = daily_counts([facts for _, facts in found], today_in_vietnam())
    return MyDashboard(projects=items, daily=daily)


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
            case_counts=_count_by_status(cases, a.screen_id),
            returned_cases=returned.get(a.screen_id, []),
        )
        for a in mine
    ]


def _count_by_status(cases: list[TestCase], screen_id: str) -> dict[TestCaseStatus, int]:
    """Đếm mọi case (không tính Lưu trữ) trên màn hình, kể cả case do người khác tạo hoặc nhập hộ.

    Đủ các trạng thái còn lại (không có thì 0).
    """
    counts: dict[TestCaseStatus, int] = {
        status: 0 for status in TestCaseStatus if status != TestCaseStatus.ARCHIVED
    }
    for case in cases:
        if case.status != TestCaseStatus.ARCHIVED and case.screen_id == screen_id:
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
