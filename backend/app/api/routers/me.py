from fastapi import APIRouter

from app.api.deps import CurrentUser, ServicesDep
from app.api.project_scope import scope_for
from app.core.models.assignment import MyAssignment

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
        scope = scope_for(services, project)
        mine = [a for a in scope.assignments.list_all() if a.assignee_email == user.email]
        if not mine:
            continue
        screen_names = {screen.id: screen.name for screen in scope.screens.list_all()}
        result.extend(
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
        )
    return sorted(result, key=lambda item: (item.deadline, item.project_name))
