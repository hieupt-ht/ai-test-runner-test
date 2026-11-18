"""API ghi kết quả cho agent bên ngoài, xác thực bằng token riêng."""

import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field

from app.api.media_upload import require_storage, upload_to_drive
from app.api.project_scope import scope_for
from app.api.result_recording import notify_results_recorded, sync_issues_for_results
from app.api.services import Services
from app.core.locks.redis_lock import LockTimeout
from app.core.media.cloudinary import SignedUpload
from app.core.models.media import (
    NOT_CONFIGURED,
    ForeignMediaError,
    Media,
    MediaKind,
    ensure_own_media,
)
from app.core.models.project import Project
from app.core.models.run import (
    Evidence,
    Result,
    ResultStatus,
    Run,
    RunScope,
    RunStatus,
    StepResult,
)
from app.core.models.test_case import ExecutionMode, TestCaseStatus
from app.core.repositories.runs import InvalidRunStateError, RunInProgressError
from app.core.services.evidence_retention import prune_evidence
from app.core.time import utc_now
from app.settings import Settings

router = APIRouter(prefix="/api/agent/projects/{project_id}", tags=["agent"])
logger = logging.getLogger(__name__)

NOT_OPEN_REGRESSION = "Lần chạy này đã kết thúc hoặc không phải lần chạy regression"


class AgentEvidence(BaseModel):
    """Bằng chứng dạng mới: một video và các ảnh chụp (đã đẩy lên Cloudinary)."""

    video: Media | None = None
    screenshots: list[Media] = Field(default_factory=list, max_length=20)


class AgentResult(BaseModel):
    test_case_id: str
    status: ResultStatus
    reason: str = Field(default="", max_length=2000)
    failed_step: int | None = Field(default=None, ge=1)
    # Chuỗi (kiểu cũ: một link) hoặc đối tượng (kiểu mới)
    evidence: str | AgentEvidence = Field(default="", union_mode="left_to_right")
    step_results: list[StepResult] = Field(default_factory=list, max_length=50)
    actual_result: str = Field(default="", max_length=2000)
    environment: str = Field(default="", max_length=200)
    executed_by: str = Field(default="", max_length=50)
    case_version: int | None = Field(default=None, ge=1)


class AgentResultsRequest(BaseModel):
    results: list[AgentResult] = Field(max_length=200)
    build_version: str = Field(default="", max_length=50)
    duration_seconds: float = Field(default=0, ge=0, le=86400)
    # Chạy bộ regression: mã lần chạy lấy từ comment trên issue
    run_id: str | None = Field(default=None, max_length=30)


class IgnoredResult(BaseModel):
    test_case_id: str
    reason: str


class AgentResultsResponse(BaseModel):
    run_id: str
    written: int
    ignored: list[IgnoredResult]


def _to_evidence(raw: str | AgentEvidence) -> Evidence:
    """Đổi bằng chứng agent gửi sang dạng lưu; chuỗi cũ chỉ nhận khi là link https."""
    if isinstance(raw, str):
        return Evidence(legacy_url=raw if raw.startswith("https://") else None)
    return Evidence(video=raw.video, screenshots=raw.screenshots)


def _all_media(item: AgentResult) -> list[Media]:
    """Mọi ảnh/video trong một kết quả, để kiểm tra có đúng kho Cloudinary của app."""
    found: list[Media] = []
    if isinstance(item.evidence, AgentEvidence):
        if item.evidence.video is not None:
            found.append(item.evidence.video)
        found.extend(item.evidence.screenshots)
    found.extend(step.screenshot for step in item.step_results if step.screenshot is not None)
    return found


def _check_token(request: Request) -> None:
    settings: Settings = request.app.state.settings
    if not settings.agent_api_token:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy")

    bearer = request.headers.get("Authorization", "")
    supplied = bearer.removeprefix("Bearer ") if bearer.startswith("Bearer ") else ""
    if not supplied or not secrets.compare_digest(supplied, settings.agent_api_token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token không hợp lệ")


def _open_project(project_id: str, request: Request) -> tuple[Services, Project]:
    """Lấy dịch vụ và dự án đang mở (chưa lưu trữ) cho các endpoint media của agent."""
    services: Services | None = request.app.state.services
    if services is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Dịch vụ chưa sẵn sàng")
    project = services.projects.get(project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy dự án")
    if project.archived:
        raise HTTPException(status.HTTP_409_CONFLICT, "Dự án đã lưu trữ")
    return services, project


class AgentSignRequest(BaseModel):
    kind: MediaKind


@router.post(
    "/media/sign", response_model=SignedUpload, dependencies=[Depends(_check_token)]
)
def sign_agent_upload(project_id: str, body: AgentSignRequest, request: Request) -> SignedUpload:
    """Codex xin chữ ký để đẩy ảnh/video bằng chứng thẳng lên Cloudinary (thư mục `evidence`)."""
    services, project = _open_project(project_id, request)
    require_storage(project, "cloudinary")
    if services.cloudinary_signer is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, NOT_CONFIGURED)
    return services.cloudinary_signer.sign(project.id, "evidence", body.kind)


@router.post("/media/upload", response_model=Media, dependencies=[Depends(_check_token)])
def upload_agent_media(project_id: str, file: UploadFile, request: Request) -> Media:
    """Dự án lưu ở Google Drive: Codex gửi file bằng chứng cho app, app đẩy lên Drive."""
    services, project = _open_project(project_id, request)
    return upload_to_drive(services, project, "evidence", file)


@router.get("/media/storage", dependencies=[Depends(_check_token)])
def agent_media_storage(project_id: str, request: Request) -> dict[str, str]:
    """Codex hỏi dự án lưu ảnh/video ở đâu để chọn đúng cách tải lên."""
    _, project = _open_project(project_id, request)
    return {"storage": project.storage}


@router.post("/results", response_model=AgentResultsResponse, dependencies=[Depends(_check_token)])
def write_agent_results(
    project_id: str, body: AgentResultsRequest, request: Request
) -> AgentResultsResponse:

    services: Services | None = request.app.state.services
    if services is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Dịch vụ chưa sẵn sàng")
    project = services.projects.get(project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy dự án")
    if project.archived:
        raise HTTPException(status.HTTP_409_CONFLICT, "Dự án đã lưu trữ")

    scope = scope_for(services, project)
    all_cases = {case.id: case for case in scope.test_cases.list_all()}
    approved = {
        case_id: case
        for case_id, case in all_cases.items()
        if case.status == TestCaseStatus.APPROVED
        and case.execution_mode == ExecutionMode.AUTOMATION
    }
    # Có run_id: kết quả thuộc một lần chạy regression đang mở, không tạo run mới
    regression_run: Run | None = None
    if body.run_id is not None:
        regression_run = scope.runs.get(body.run_id)
        if regression_run is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy lần chạy")
        if not (
            regression_run.scope.regression_only and regression_run.status == RunStatus.RUNNING
        ):
            raise HTTPException(status.HTTP_409_CONFLICT, NOT_OPEN_REGRESSION)
    accepted: list[AgentResult] = []
    ignored: list[IgnoredResult] = []
    for item in body.results:
        known = all_cases.get(item.test_case_id)
        if known is not None and known.execution_mode == ExecutionMode.MANUAL:
            # Case test tay do tester chạy; agent không được ghi kết quả
            ignored.append(IgnoredResult(test_case_id=item.test_case_id, reason="Case test tay"))
        elif item.test_case_id not in approved:
            ignored.append(
                IgnoredResult(
                    test_case_id=item.test_case_id, reason="Case không tồn tại hoặc chưa duyệt"
                )
            )
        elif regression_run is not None and item.test_case_id not in regression_run.scope.case_ids:
            ignored.append(
                IgnoredResult(
                    test_case_id=item.test_case_id, reason="Case không thuộc lần chạy này"
                )
            )
        else:
            accepted.append(item)

    # Link sai kho Cloudinary thì từ chối cả request, chưa tạo Run nào
    try:
        for item in accepted:
            ensure_own_media(_all_media(item), services.cloud_name, services.drive is not None)
    except ForeignMediaError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None

    if regression_run is not None:
        run = regression_run
    else:
        try:
            run = scope.runs.create(
                triggered_by="codex-agent",
                scope=RunScope(),
                branch=project.branch,
                total=len(accepted),
                build_version=body.build_version,
            )
        except (RunInProgressError, LockTimeout):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Đang có một lần ghi kết quả khác, hãy thử lại",
            ) from None

    # Đọc màn hình một lần để ghi lại dev phụ trách tại thời điểm này
    dev_by_screen = {screen.id: screen.dev_owner for screen in scope.screens.list_all()}
    results = [
        Result(
            id=f"{run.id}-{item.test_case_id}",
            run_id=run.id,
            test_case_id=item.test_case_id,
            status=item.status,
            reason=item.reason,
            failed_step=item.failed_step,
            evidence=_to_evidence(item.evidence),
            step_results=item.step_results,
            actual_result=item.actual_result,
            environment=item.environment,
            executed_by=item.executed_by,
            case_version=item.case_version,
            dev_owner=dev_by_screen.get(approved[item.test_case_id].screen_id, ""),
            created_at=utc_now(),
        )
        for item in accepted
    ]
    if regression_run is not None:
        # Run regression cộng dồn: add_results ghi kết quả, đếm và tự hoàn tất khi đủ case
        try:
            run = scope.runs.add_results(regression_run.id, results)
        except InvalidRunStateError:
            raise HTTPException(status.HTTP_409_CONFLICT, NOT_OPEN_REGRESSION) from None
        except LockTimeout:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Đang có một lần ghi kết quả khác, hãy thử lại"
            ) from None
        except Exception:
            logger.error("Không ghi được kết quả vào run %s", regression_run.id, exc_info=True)
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Không ghi được kết quả, hãy kiểm tra Sheet trước khi thử lại",
            ) from None
    else:
        try:
            scope.results.append_batch(results)
        except Exception:
            run.status = RunStatus.FAILED
            run.finished_at = utc_now()
            try:
                scope.runs.save(run)
            except Exception:
                logger.error(
                    "Không đánh dấu được run %s của dự án %s là FAILED", run.id, project.id
                )
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Không ghi được kết quả, hãy kiểm tra Sheet trước khi thử lại",
            ) from None
        run.status = RunStatus.COMPLETED
        run.finished_at = utc_now()
        run.passed = sum(item.status == ResultStatus.PASS for item in accepted)
        run.failed = sum(item.status == ResultStatus.FAIL for item in accepted)
        scope.runs.save(run)
    # Run regression gửi từng đợt: chỉ báo một lần khi cả run đã xong
    if regression_run is None or run.status == RunStatus.COMPLETED:
        notify_results_recorded(
            services,
            project,
            run,
            failed_case_creators=(
                approved[item.test_case_id].created_by
                for item in accepted
                if item.status == ResultStatus.FAIL
            ),
        )
    sync_issues_for_results(
        services, project, run, results, approved, duration=body.duration_seconds
    )
    # Dọn bằng chứng cũ của các case vừa chạy (lỗi chỉ ghi log, không ảnh hưởng kết quả)
    prune_evidence(scope.results, services.media_janitor, {item.test_case_id for item in accepted})
    return AgentResultsResponse(run_id=run.id, written=len(results), ignored=ignored)
