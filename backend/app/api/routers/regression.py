"""Chạy bộ regression: tạo một run gom các case regression đã duyệt, rồi kết thúc khi xong.

App không tự chạy test. Nó tạo run, đánh dấu `needs-rerun` lên issue của từng case để Codex biết,
và Codex gửi kết quả về kèm `run_id` (xem `agent.py`).
"""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, ServicesDep
from app.api.project_access import load_project
from app.api.project_scope import scope_for
from app.api.services import Services
from app.core.locks.redis_lock import LockTimeout
from app.core.models.project import Project
from app.core.models.run import Run, RunStatus
from app.core.models.test_case import ExecutionMode, TestCaseStatus
from app.core.permissions import Action
from app.core.repositories.runs import InvalidRunStateError, RunNotFoundError
from app.core.services.issue_sync import BackgroundIssueSync
from app.core.services.rerun_request import request_rerun_on_issue
from app.core.time import utc_now

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_id}/regression-runs", tags=["regression"])


class CreateRegressionRequest(BaseModel):
    build_version: Annotated[str, Field(min_length=1, max_length=50)]


def _request_reruns(
    services: Services, project: Project, case_ids: list[str], user_name: str, run_id: str
) -> None:
    """Gắn `needs-rerun` + comment mã run lên issue của từng case, chạy ở luồng GitHub riêng."""
    github = services.github
    if github is None:
        return
    requested_at = utc_now()

    def work() -> None:
        for case_id in case_ids:
            try:
                request_rerun_on_issue(
                    github,
                    repo=project.repo_full_name,
                    case_id=case_id,
                    user_name=user_name,
                    requested_at=requested_at,
                    run_id=run_id,
                )
            except Exception:
                logger.warning("Không yêu cầu chạy lại được case %s", case_id, exc_info=True)

    if isinstance(services.issue_sync, BackgroundIssueSync):
        services.issue_sync.submit(work)
    else:
        work()


@router.get("")
def list_open_regression_runs(
    project_id: str, user: CurrentUser, services: ServicesDep
) -> list[Run]:
    """Các lần chạy regression còn đang mở (giao diện dùng để hiện nút "Kết thúc")."""
    project = load_project(services, user, project_id, Action.VIEW_PROJECT)
    return [
        run
        for run in scope_for(services, project).runs.list_all()
        if run.scope.regression_only and run.status == RunStatus.RUNNING
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_regression_run(
    project_id: str, body: CreateRegressionRequest, user: CurrentUser, services: ServicesDep
) -> Run:
    project = load_project(services, user, project_id, Action.REVIEW_TEST_CASE)
    scope = scope_for(services, project)
    case_ids = [
        case.id
        for case in scope.test_cases.list_all()
        if case.regression
        and case.status == TestCaseStatus.APPROVED
        and case.execution_mode == ExecutionMode.AUTOMATION  # case test tay do tester tự chạy
    ]
    if not case_ids:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Không có case regression nào đã duyệt"
        )
    try:
        run = scope.runs.create_regression(
            triggered_by=user.email,
            branch=project.branch,
            build_version=body.build_version,
            case_ids=case_ids,
        )
    except LockTimeout:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Đang có thao tác khác với lần chạy, hãy thử lại"
        ) from None
    _request_reruns(services, project, case_ids, user.name, run.id)
    return run


@router.post("/{run_id}/finish")
def finish_regression_run(
    project_id: str, run_id: str, user: CurrentUser, services: ServicesDep
) -> Run:
    project = load_project(services, user, project_id, Action.REVIEW_TEST_CASE)
    try:
        return scope_for(services, project).runs.finish(run_id)
    except RunNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy lần chạy") from None
    except InvalidRunStateError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Lần chạy này đã kết thúc hoặc không phải lần chạy regression",
        ) from None
    except LockTimeout:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Đang có thao tác khác với lần chạy, hãy thử lại"
        ) from None
