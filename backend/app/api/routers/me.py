import logging

from fastapi import APIRouter

from app.api.deps import CurrentUser, ServicesDep
from app.api.project_scope import scope_for
from app.api.services import Services
from app.core.models.assignment import MyAssignment
from app.core.models.project import Project
from app.core.sheets.gateway import SheetAccessDeniedError
from app.core.sheets.table import MissingColumnsError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/me", tags=["me"])


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
        )
        for a in mine
    ]
