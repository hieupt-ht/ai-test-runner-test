"""Kết quả mới nhất của từng case trong một dự án."""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentUser, ServicesDep
from app.api.project_access import load_project
from app.api.project_scope import scope_for
from app.core.models.project import Project
from app.core.models.run import Result, ResultStatus, RunStatus
from app.core.models.test_case import TestCase
from app.core.models.user import Role, normalize_email
from app.core.permissions import Action

router = APIRouter(prefix="/api/projects/{project_id}/results", tags=["results"])


class ResultItem(BaseModel):
    case_id: str
    case_title: str
    screen_id: str
    screen_name: str
    status: ResultStatus
    reason: str
    failed_step: int | None
    evidence: str
    run_id: str
    finished_at: datetime


@router.get("")
def list_results(
    project_id: str,
    user: CurrentUser,
    services: ServicesDep,
    status: ResultStatus | None = None,
    screen_id: str | None = None,
) -> list[ResultItem]:
    project = load_project(services, user, project_id, Action.VIEW_PROJECT, allow_archived=True)
    return results_for_project(services, project, user, status=status, screen_id=screen_id)


def results_for_project(
    services: ServicesDep,
    project: Project,
    user: CurrentUser,
    *,
    status: ResultStatus | None = None,
    screen_id: str | None = None,
    cases: list[TestCase] | None = None,
) -> list[ResultItem]:
    """Đọc kết quả một dự án; `cases` giúp Tổng quan không đọc lại tab TestCases."""
    scope = scope_for(services, project)
    runs = [
        run
        for run in scope.runs.list_all()
        if run.status == RunStatus.COMPLETED and run.finished_at is not None
    ]
    if not runs:
        return []

    # Một lượt đọc Results và TestCases cho toàn bộ run; run mới hơn được giữ trước.
    results_by_run: dict[str, list[Result]] = {}
    for result in scope.results.list_all():
        results_by_run.setdefault(result.run_id, []).append(result)
    case_list = scope.test_cases.list_all() if cases is None else cases
    cases_by_id = {case.id: case for case in case_list}
    screen_names = {screen.id: screen.name for screen in scope.screens.list_all()}
    latest: dict[str, ResultItem] = {}
    for run in sorted(
        runs, key=lambda item: (item.finished_at or item.started_at, item.id), reverse=True
    ):
        if run.finished_at is None:
            continue
        for result in results_by_run.get(run.id, []):
            case = cases_by_id.get(result.test_case_id)
            if case is None or case.id in latest:
                continue
            if screen_id is not None and case.screen_id != screen_id:
                continue
            if user.role == Role.TESTER and case.created_by != normalize_email(user.email):
                continue
            # Lọc sau khi tìm mới nhất; kết quả cũ khớp lọc không được hiện thay.
            latest[case.id] = ResultItem(
                case_id=case.id,
                case_title=case.title,
                screen_id=case.screen_id,
                screen_name=screen_names.get(case.screen_id, case.screen_id),
                status=result.status,
                reason=result.reason,
                failed_step=result.failed_step,
                evidence=result.evidence.legacy_url or "",
                run_id=run.id,
                finished_at=run.finished_at,
            )
    return [item for item in latest.values() if status is None or item.status == status]
