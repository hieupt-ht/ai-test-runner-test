"""Số liệu và bảng xếp hạng của một project (cho trang Tổng quan project)."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, ServicesDep
from app.api.project_access import load_project
from app.api.project_facts import load_facts
from app.api.project_scope import scope_for
from app.core.models.stats import Leaderboard, Period, ProjectStats
from app.core.models.user import normalize_email
from app.core.permissions import Action
from app.core.services.stats import leaderboard, project_stats
from app.core.time import today_in_vietnam

router = APIRouter(prefix="/api/projects/{project_id}", tags=["stats"])


@router.get("/stats")
def get_stats(project_id: str, user: CurrentUser, services: ServicesDep) -> ProjectStats:
    project = load_project(services, user, project_id, Action.VIEW_PROJECT)
    scope = scope_for(services, project)
    screen_names = {screen.id: screen.name for screen in scope.screens.list_all()}
    return project_stats(load_facts(services, scope), screen_names, today_in_vietnam())


@router.get("/leaderboard")
def get_leaderboard(
    project_id: str,
    user: CurrentUser,
    services: ServicesDep,
    period: Period = Period.WEEK,
) -> Leaderboard:
    project = load_project(services, user, project_id, Action.VIEW_PROJECT)
    scope = scope_for(services, project)
    names = {normalize_email(item.email): item.name for item in services.users.list_all()}
    return leaderboard(
        load_facts(services, scope), names, period, today_in_vietnam(), me=user.email
    )
