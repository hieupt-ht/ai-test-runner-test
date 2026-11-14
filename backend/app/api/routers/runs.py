import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, ServicesDep
from app.api.project_access import load_project
from app.api.project_scope import ProjectScope, scope_for
from app.api.services import Services
from app.core.locks.redis_lock import LockTimeout
from app.core.models.project import Project
from app.core.models.run import Result, Run, RunScope
from app.core.permissions import Action
from app.core.repositories.runs import RunInProgressError, RunNotFoundError
from app.core.run_queue import RunQueue
from app.core.services.runs import NoCasesError, RunService, TooManyCasesError

router = APIRouter(prefix="/api/projects/{project_id}/runs", tags=["runs"])

NOT_FOUND = "Không tìm thấy lần chạy"
BUSY = "Dữ liệu đang được cập nhật, vui lòng thử lại"
SCREENSHOT_NAME = re.compile(r"^[A-Za-z0-9._-]+\.png$")


class RunView(Run):
    """Run kèm lý do lỗi (nếu có) và tên người bấm chạy."""

    note: str
    triggered_by_name: str


class ResultView(Result):
    test_case_title: str


class RunDetail(RunView):
    results: list[ResultView]


class StartRunRequest(BaseModel):
    scope: RunScope = Field(default_factory=RunScope)


class PreviewResponse(BaseModel):
    count: int


def _context(
    services: Services, project: Project
) -> tuple[ProjectScope, RunQueue, RunService]:
    scope = scope_for(services, project)
    queue = RunQueue(services.redis)
    service = RunService(
        project, scope.test_cases, scope.runs, queue, max_cases=services.max_cases_per_run
    )
    return scope, queue, service


def _view(services: Services, queue: RunQueue, run: Run) -> RunView:
    triggerer = services.users.get(run.triggered_by)
    return RunView(
        **run.model_dump(),
        note=queue.get_note(run.id),
        triggered_by_name=triggerer.name if triggerer is not None else run.triggered_by,
    )


def _get_run(scope: ProjectScope, run_id: str) -> Run:
    run = scope.runs.get(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return run


@router.post("/preview")
def preview_run(
    project_id: str, body: RunScope, user: CurrentUser, services: ServicesDep
) -> PreviewResponse:
    project = load_project(services, user, project_id, Action.TRIGGER_RUN)
    _, _, service = _context(services, project)
    return PreviewResponse(count=service.count(body))


@router.post("", status_code=status.HTTP_201_CREATED)
def start_run(
    project_id: str, body: StartRunRequest, user: CurrentUser, services: ServicesDep
) -> RunView:
    project = load_project(services, user, project_id, Action.TRIGGER_RUN)
    _, queue, service = _context(services, project)
    try:
        run = service.start(user.email, body.scope)
    except RunInProgressError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from None
    except (NoCasesError, TooManyCasesError) as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    except LockTimeout:
        raise HTTPException(status.HTTP_409_CONFLICT, BUSY) from None
    return _view(services, queue, run)


@router.get("")
def list_runs(project_id: str, user: CurrentUser, services: ServicesDep) -> list[RunView]:
    project = load_project(services, user, project_id, Action.VIEW_PROJECT)
    scope, queue, _ = _context(services, project)
    return [_view(services, queue, run) for run in scope.runs.list_all()]


@router.get("/{run_id}")
def get_run(project_id: str, run_id: str, user: CurrentUser, services: ServicesDep) -> RunDetail:
    project = load_project(services, user, project_id, Action.VIEW_PROJECT)
    scope, queue, _ = _context(services, project)
    run = _get_run(scope, run_id)
    titles = {case.id: case.title for case in scope.test_cases.list_all()}
    results = [
        ResultView(**result.model_dump(), test_case_title=titles.get(result.test_case_id, ""))
        for result in scope.results.list_for_run(run_id)
    ]
    return RunDetail(**_view(services, queue, run).model_dump(), results=results)


@router.post("/{run_id}/cancel")
def cancel_run(project_id: str, run_id: str, user: CurrentUser, services: ServicesDep) -> RunView:
    project = load_project(services, user, project_id, Action.TRIGGER_RUN)
    _, queue, service = _context(services, project)
    try:
        run = service.cancel(run_id)
    except RunNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND) from None
    except LockTimeout:
        raise HTTPException(status.HTTP_409_CONFLICT, BUSY) from None
    return _view(services, queue, run)


@router.get("/{run_id}/screenshots/{filename}")
def get_screenshot(
    project_id: str, run_id: str, filename: str, user: CurrentUser, services: ServicesDep
) -> FileResponse:
    project = load_project(services, user, project_id, Action.VIEW_PROJECT)
    scope = scope_for(services, project)
    _get_run(scope, run_id)  # run phải thuộc dự án này, không thì ảnh của dự án khác bị lộ

    folder = (services.artifacts_dir / run_id).resolve()
    path = (folder / filename).resolve()
    if not SCREENSHOT_NAME.match(filename) or not _is_inside(path, folder) or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy ảnh chụp")
    return FileResponse(path, media_type="image/png")


def _is_inside(path: Path, folder: Path) -> bool:
    return path.parent == folder
