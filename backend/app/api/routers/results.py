"""Kết quả mới nhất của từng case trong một dự án."""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentUser, ServicesDep
from app.api.project_access import load_project
from app.api.project_scope import scope_for
from app.core.models.run import Result, ResultStatus, RunStatus
from app.core.models.user import Role, normalize_email
from app.core.permissions import Action

router = APIRouter(prefix="/api/projects/{project_id}/results", tags=["results"])


class ResultItem(BaseModel):
    case_id: str
    case_title: str
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
) -> list[ResultItem]:
    project = load_project(services, user, project_id, Action.VIEW_PROJECT, allow_archived=True)
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
    cases = {case.id: case for case in scope.test_cases.list_all()}
    latest: dict[str, ResultItem] = {}
    for run in sorted(
        runs, key=lambda item: (item.finished_at or item.started_at, item.id), reverse=True
    ):
        if run.finished_at is None:
            continue
        for result in results_by_run.get(run.id, []):
            case = cases.get(result.test_case_id)
            if case is None or case.id in latest:
                continue
            if user.role == Role.TESTER and case.created_by != normalize_email(user.email):
                continue
            # Lọc sau khi tìm mới nhất; kết quả cũ khớp lọc không được hiện thay.
            latest[case.id] = ResultItem(
                case_id=case.id,
                case_title=case.title,
                status=result.status,
                reason=result.reason,
                failed_step=result.failed_step,
                evidence=result.screenshot or "",
                run_id=run.id,
                finished_at=run.finished_at,
            )
    return [item for item in latest.values() if status is None or item.status == status]
