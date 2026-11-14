"""API ghi kết quả cho agent bên ngoài, xác thực bằng token riêng."""

import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.project_scope import scope_for
from app.api.services import Services
from app.core.locks.redis_lock import LockTimeout
from app.core.models.run import Result, ResultStatus, RunScope, RunStatus
from app.core.models.test_case import TestCaseStatus
from app.core.models.user import Role
from app.core.repositories.runs import RunInProgressError
from app.core.services.notify import Notifier
from app.core.time import utc_now
from app.settings import Settings

router = APIRouter(prefix="/api/agent/projects/{project_id}", tags=["agent"])
logger = logging.getLogger(__name__)


class AgentResult(BaseModel):
    test_case_id: str
    status: ResultStatus
    reason: str = Field(default="", max_length=2000)
    failed_step: int | None = Field(default=None, ge=1)
    evidence: str = Field(default="", max_length=2000)


class AgentResultsRequest(BaseModel):
    results: list[AgentResult] = Field(max_length=200)


class IgnoredResult(BaseModel):
    test_case_id: str
    reason: str


class AgentResultsResponse(BaseModel):
    run_id: str
    written: int
    ignored: list[IgnoredResult]


def _check_token(request: Request) -> None:
    settings: Settings = request.app.state.settings
    if not settings.agent_api_token:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy")

    bearer = request.headers.get("Authorization", "")
    supplied = bearer.removeprefix("Bearer ") if bearer.startswith("Bearer ") else ""
    if not supplied or not secrets.compare_digest(supplied, settings.agent_api_token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token không hợp lệ")


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
    approved = {
        case.id: case
        for case in scope.test_cases.list_all()
        if case.status == TestCaseStatus.APPROVED
    }
    accepted: list[AgentResult] = []
    ignored: list[IgnoredResult] = []
    for item in body.results:
        if item.test_case_id in approved:
            accepted.append(item)
        else:
            ignored.append(
                IgnoredResult(
                    test_case_id=item.test_case_id, reason="Case không tồn tại hoặc chưa duyệt"
                )
            )

    try:
        run = scope.runs.create(
            triggered_by="codex-agent",
            scope=RunScope(),
            branch=project.branch,
            total=len(accepted),
        )
    except (RunInProgressError, LockTimeout):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Đang có một lần ghi kết quả khác, hãy thử lại",
        ) from None

    results = [
        Result(
            id=f"{run.id}-{item.test_case_id}",
            run_id=run.id,
            test_case_id=item.test_case_id,
            status=item.status,
            reason=item.reason,
            failed_step=item.failed_step,
            screenshot=item.evidence or None,
            created_at=utc_now(),
        )
        for item in accepted
    ]
    try:
        scope.results.append_batch(results)
    except Exception:
        run.status = RunStatus.FAILED
        run.finished_at = utc_now()
        try:
            scope.runs.save(run)
        except Exception:
            logger.error("Không đánh dấu được run %s của dự án %s là FAILED", run.id, project.id)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Không ghi được kết quả, hãy kiểm tra Sheet trước khi thử lại",
        ) from None
    run.status = RunStatus.COMPLETED
    run.finished_at = utc_now()
    run.passed = sum(item.status == ResultStatus.PASS for item in accepted)
    run.failed = sum(item.status == ResultStatus.FAIL for item in accepted)
    scope.runs.save(run)
    try:
        member_emails = {
            member.email for member in services.members.list_for_project(project.id)
        }
        recipients = {
            user.email
            for user in services.users.list_all()
            if user.active
            and (
                user.role == Role.ADMIN
                or (user.role == Role.QA_LEAD and user.email in member_emails)
            )
        }
        recipients.update(
            approved[item.test_case_id].created_by
            for item in accepted
            if item.status == ResultStatus.FAIL
        )
        Notifier(services.notifications).results_recorded(
            emails=sorted(recipients), project_id=project.id, run_id=run.id,
            failed=run.failed, total=run.total,
        )
    except Exception:
        logger.warning("Không xác định được người nhận kết quả run %s", run.id, exc_info=True)
    return AgentResultsResponse(run_id=run.id, written=len(results), ignored=ignored)
