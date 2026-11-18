"""Tester tự chạy case test tay rồi gửi kết quả (từng bước, bằng chứng) lên app."""

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, ServicesDep
from app.api.project_access import load_project
from app.api.project_scope import ProjectScope, scope_for
from app.api.result_recording import notify_results_recorded, sync_issues_for_results
from app.api.routers.agent import AgentEvidence
from app.api.routers.test_cases import service_for
from app.api.services import Services
from app.core.locks.redis_lock import LockTimeout
from app.core.models.media import DRIVE_PREFIX, ForeignMediaError, Media, ensure_own_media
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
from app.core.models.test_case import ExecutionMode, TestCase, TestCaseStatus
from app.core.models.user import User
from app.core.permissions import Action
from app.core.repositories.runs import RunInProgressError
from app.core.repositories.test_cases import TestCaseNotFoundError
from app.core.services.evidence_retention import prune_evidence
from app.core.services.issue_sync import BackgroundIssueSync, IssueSyncer
from app.core.services.test_cases import TestCaseService
from app.core.time import utc_now

router = APIRouter(prefix="/api/projects/{project_id}/test-cases", tags=["manual-results"])
logger = logging.getLogger(__name__)

# Tên GitHub hợp lệ hoặc để trống (cùng luật với ô "Dev phụ trách" ở màn hình)
_ASSIGNEE_PATTERN = r"^([A-Za-z0-9]+(-[A-Za-z0-9]+)*)?$"


class ManualResultRequest(BaseModel):
    status: Literal["PASS", "FAIL", "BLOCKED"]
    step_results: list[StepResult] = Field(default_factory=list, max_length=50)
    actual_result: str = Field(default="", max_length=2000)
    reason: str = Field(default="", max_length=2000)
    failed_step: int | None = Field(default=None, ge=1)
    evidence: AgentEvidence = Field(default_factory=AgentEvidence)
    environment: str = Field(min_length=1, max_length=200)
    build_version: str = Field(default="", max_length=50)
    assignee: str = Field(default="", max_length=39, pattern=_ASSIGNEE_PATTERN)  # dev sửa lỗi
    version: int = Field(ge=1)  # phiên bản case người chạy đang xem


class ManualResultResponse(BaseModel):
    run_id: str
    case: TestCase


def _unprocessable(message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)


def _check_case_state(case: TestCase, version: int) -> None:
    if case.execution_mode != ExecutionMode.MANUAL:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Case này chạy tự động, không gửi kết quả tay được"
        )
    if case.status not in (TestCaseStatus.DRAFT, TestCaseStatus.TESTED):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Chỉ gửi kết quả khi case đang Nháp hoặc Đã kiểm thử"
        )
    if version != case.version:
        raise HTTPException(status.HTTP_409_CONFLICT, "Case vừa được sửa, hãy tải lại")


def _check_steps(body: ManualResultRequest, case: TestCase) -> None:
    step_count = len(case.steps)
    if sorted(step.step_no for step in body.step_results) != list(range(1, step_count + 1)):
        raise _unprocessable(f"Cần đúng một kết quả cho mỗi bước (từ 1 đến {step_count})")
    if body.status == "FAIL":
        if not body.reason.strip():
            raise _unprocessable("Kết quả Không đạt cần mô tả lỗi")
        if body.failed_step is None or body.failed_step > step_count:
            raise _unprocessable(f"Cần chọn bước lỗi (từ 1 đến {step_count})")


def _all_media(body: ManualResultRequest) -> list[Media]:
    found: list[Media] = [] if body.evidence.video is None else [body.evidence.video]
    found.extend(body.evidence.screenshots)
    found.extend(step.screenshot for step in body.step_results if step.screenshot is not None)
    return found


def _check_media(services: Services, project: Project, body: ManualResultRequest) -> None:
    items = _all_media(body)
    try:
        ensure_own_media(items, services.cloud_name, services.drive is not None)
    except ForeignMediaError as error:
        raise _unprocessable(str(error)) from None
    # Ảnh Cloudinary phải nằm đúng thư mục bằng chứng của CHÍNH dự án này
    prefix = f"ai-test-runner/{project.id}/evidence/"
    for item in items:
        if not item.url.startswith(DRIVE_PREFIX) and not item.public_id.startswith(prefix):
            raise _unprocessable("Ảnh/video bằng chứng không nằm đúng thư mục của dự án")


def _fail_run(scope: ProjectScope, run: Run) -> None:
    run.status = RunStatus.FAILED
    run.finished_at = utc_now()
    try:
        scope.runs.save(run)
    except Exception:
        logger.error("Không đánh dấu được run %s là FAILED", run.id)


@router.post(
    "/{case_id}/manual-results",
    response_model=ManualResultResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_manual_result(
    project_id: str,
    case_id: str,
    body: ManualResultRequest,
    user: CurrentUser,
    services: ServicesDep,
) -> ManualResultResponse:
    project = load_project(services, user, project_id, Action.EDIT_TEST_CASE, allow_archived=True)
    if project.archived:
        raise HTTPException(status.HTTP_409_CONFLICT, "Dự án đã lưu trữ")
    service = service_for(services, project)
    try:
        case = service.get_case(case_id)
    except TestCaseNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy test case") from None
    if not service.can_edit(user, case):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bạn không có quyền sửa test case này")
    _check_case_state(case, body.version)
    _check_steps(body, case)
    _check_media(services, project, body)

    scope = scope_for(services, project)
    result_status = ResultStatus(body.status)
    try:
        run = scope.runs.create(
            triggered_by=user.email,
            scope=RunScope(case_ids=[case.id]),
            branch=project.branch,
            total=1,
            build_version=body.build_version,
        )
    except (RunInProgressError, LockTimeout):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Đang có một lần ghi kết quả khác, hãy thử lại"
        ) from None

    screen = scope.screens.get(case.screen_id)
    result = Result(
        id=f"{run.id}-{case.id}",
        run_id=run.id,
        test_case_id=case.id,
        status=result_status,
        reason=body.reason,
        failed_step=body.failed_step,
        evidence=Evidence(video=body.evidence.video, screenshots=body.evidence.screenshots),
        step_results=sorted(body.step_results, key=lambda step: step.step_no),
        actual_result=body.actual_result,
        environment=body.environment,
        executed_by=user.email,
        case_version=body.version,
        dev_owner=body.assignee or (screen.dev_owner if screen else ""),
        created_at=utc_now(),
    )
    try:
        scope.results.append_batch([result])
    except Exception:
        logger.error("Không ghi được kết quả test tay vào run %s", run.id, exc_info=True)
        _fail_run(scope, run)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Không ghi được kết quả, hãy kiểm tra Sheet trước khi thử lại",
        ) from None
    run.status = RunStatus.COMPLETED
    run.finished_at = utc_now()
    run.passed = int(result_status == ResultStatus.PASS)
    run.failed = int(result_status == ResultStatus.FAIL)
    scope.runs.save(run)

    saved_case = _mark_tested(service, user, case, result_status, body.version)
    notify_results_recorded(
        services,
        project,
        run,
        failed_case_creators=[case.created_by] if result_status == ResultStatus.FAIL else [],
    )
    if result_status != ResultStatus.BLOCKED:
        _sync_issue(services, project, run, result, saved_case, user)
    prune_evidence(scope.results, services.media_janitor, {case.id})
    return ManualResultResponse(run_id=run.id, case=saved_case)


def _mark_tested(
    service: TestCaseService, user: User, case: TestCase, result: ResultStatus, version: int
) -> TestCase:
    """PASS/FAIL thì case thành TESTED. Lỗi chỉ ghi log vì kết quả đã nằm trong Sheet."""
    if result == ResultStatus.BLOCKED:
        return case
    try:
        return service.mark_tested(user, case.id, version=version)
    except Exception:
        logger.warning("Không chuyển case %s sang TESTED", case.id, exc_info=True)
        return case


def _sync_issue(
    services: Services, project: Project, run: Run, result: Result, case: TestCase, user: User
) -> None:
    """Tạo/cập nhật issue của case rồi đưa kết quả lên đó (issue trước, comment sau)."""
    github = services.github
    if github is None:
        return
    screen = None
    try:
        screen = scope_for(services, project).screens.get(case.screen_id)
    except Exception:
        logger.warning("Không đọc được màn hình của case %s", case.id, exc_info=True)

    def work() -> None:
        try:
            IssueSyncer(github, app_base_url=services.app_base_url).sync_case(
                project, case, screen_name=screen.name if screen else "", screen=screen
            )
        except Exception:
            logger.warning("Không đồng bộ được issue cho case %s", case.id, exc_info=True)
        sync_issues_for_results(
            services, project, run, [result], {case.id: case}, runner_name=user.name
        )

    if isinstance(services.issue_sync, BackgroundIssueSync):
        # Nối đuôi luồng nền: chạy SAU lần đồng bộ mà mark_tested đã xếp hàng
        services.issue_sync.submit(work)
    else:
        work()
