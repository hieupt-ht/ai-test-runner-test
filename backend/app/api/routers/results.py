"""Kết quả mới nhất của từng case trong một dự án."""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentUser, ServicesDep
from app.api.project_access import load_project
from app.api.project_scope import scope_for
from app.core.models.project import Project
from app.core.models.run import Evidence, Result, ResultStatus, Run, RunStatus, StepResult
from app.core.models.test_case import Platform, TestCase
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
    evidence: Evidence
    run_id: str
    finished_at: datetime
    platform: Platform
    regression: bool
    case_version: int | None
    environment: str
    executed_by: str
    dev_owner: str
    actual_result: str
    step_results: list[StepResult]
    build_version: str
    # Link tìm issue theo nhãn `tc:<id>` (không gọi GitHub nên không tốn lượt)
    issue_url: str


@router.get("")
def list_results(
    project_id: str,
    user: CurrentUser,
    services: ServicesDep,
    status: ResultStatus | None = None,
    screen_id: str | None = None,
    platform: Platform | None = None,
    run_id: str | None = None,
    regression_only: bool = False,
) -> list[ResultItem]:
    project = load_project(services, user, project_id, Action.VIEW_PROJECT, allow_archived=True)
    return results_for_project(
        services,
        project,
        user,
        status=status,
        screen_id=screen_id,
        platform=platform,
        run_id=run_id,
        regression_only=regression_only,
    )


def _has_results(run: Run) -> bool:
    """Run xong thì có kết quả; run regression đang chạy cũng hiện ngay các kết quả đã gửi."""
    if run.status == RunStatus.COMPLETED:
        return run.finished_at is not None
    return run.scope.regression_only and run.status == RunStatus.RUNNING


def results_for_project(
    services: ServicesDep,
    project: Project,
    user: CurrentUser,
    *,
    status: ResultStatus | None = None,
    screen_id: str | None = None,
    platform: Platform | None = None,
    run_id: str | None = None,
    regression_only: bool = False,
    cases: list[TestCase] | None = None,
) -> list[ResultItem]:
    """Đọc kết quả một dự án; `cases` giúp Tổng quan không đọc lại tab TestCases."""
    scope = scope_for(services, project)
    runs = [
        run
        for run in scope.runs.list_all()
        if _has_results(run)
        and (run_id is None or run.id == run_id)  # có run_id: chỉ lấy đúng Run đó
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
    me = normalize_email(user.email)
    # Tester xem kết quả case mình tạo, và mọi case thuộc màn hình được giao cho mình
    assigned_screens = (
        {a.screen_id for a in scope.assignments.list_all() if a.assignee_email == me}
        if user.role == Role.TESTER
        else set()
    )
    latest: dict[str, ResultItem] = {}
    for run in sorted(
        runs, key=lambda item: (item.finished_at or item.started_at, item.id), reverse=True
    ):
        for result in results_by_run.get(run.id, []):
            case = cases_by_id.get(result.test_case_id)
            if case is None or case.id in latest:
                continue
            if screen_id is not None and case.screen_id != screen_id:
                continue
            if platform is not None and case.platform != platform:
                continue
            if regression_only and not case.regression:
                continue
            if (
                user.role == Role.TESTER
                and case.created_by != me
                and case.screen_id not in assigned_screens
            ):
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
                evidence=result.evidence,
                run_id=run.id,
                finished_at=run.finished_at or run.started_at,
                platform=case.platform,
                regression=case.regression,
                case_version=result.case_version,
                environment=result.environment,
                executed_by=result.executed_by,
                dev_owner=result.dev_owner,
                actual_result=result.actual_result,
                step_results=result.step_results,
                build_version=run.build_version,
                issue_url=(
                    f"https://github.com/{project.repo_full_name}/issues"
                    f"?q=label%3Atc%3A{case.id}"
                ),
            )
    return [item for item in latest.values() if status is None or item.status == status]
