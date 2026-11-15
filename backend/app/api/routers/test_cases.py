from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, ServicesDep
from app.api.project_access import load_project
from app.api.project_scope import scope_for
from app.api.services import Services
from app.core.assignment_status import AssignmentStatusUpdater
from app.core.locks.redis_lock import LockTimeout
from app.core.models.project import Project
from app.core.models.test_case import TestCase, TestCaseContent
from app.core.models.user import User
from app.core.permissions import Action
from app.core.repositories.audit_log import AuditEntry
from app.core.repositories.test_cases import TestCaseNotFoundError, VersionConflictError
from app.core.services.issue_sync import IssueSyncer
from app.core.services.notify import Notifier
from app.core.services.test_cases import (
    CaseAction,
    InvalidTestCaseError,
    InvalidTransitionError,
    SyncIssuesResult,
    TestCasePermissionError,
    TestCaseService,
)

router = APIRouter(prefix="/api/projects/{project_id}/test-cases", tags=["test-cases"])

NOT_FOUND = "Không tìm thấy test case"
NO_PERMISSION = "Bạn không có quyền thực hiện thao tác này"
BUSY = "Dữ liệu đang được cập nhật, vui lòng thử lại"
MAX_BATCH_SIZE = 200


class TestCaseDetail(TestCase):
    """Test case kèm quyền của người đang xem, để giao diện ẩn/hiện nút."""

    __test__ = False  # pytest đừng tưởng đây là lớp test

    can_edit: bool
    can_review: bool
    can_archive: bool


class ConflictResponse(BaseModel):
    """Phản hồi 409 khi version cũ: kèm bản mới nhất để giao diện cho người dùng so sánh."""

    detail: str
    latest: TestCase


class CreateTestCaseRequest(TestCaseContent):
    screen_id: str


class UpdateTestCaseRequest(TestCaseContent):
    version: int


class ApproveItem(BaseModel):
    case_id: str
    version: int


class BatchApproveRequest(BaseModel):
    items: list[ApproveItem] = Field(min_length=1, max_length=MAX_BATCH_SIZE)


class SkippedItem(BaseModel):
    case_id: str
    reason: str


class BatchApproveResponse(BaseModel):
    approved: list[TestCase]
    skipped: list[SkippedItem]


class TransitionRequest(BaseModel):
    version: int
    comment: str = ""


def _service(services: Services, user: User, project_id: str, action: Action) -> TestCaseService:
    return _service_for(services, load_project(services, user, project_id, action))


def _service_for(services: Services, project: Project) -> TestCaseService:
    scope = scope_for(services, project)
    return TestCaseService(
        project_id=project.id,
        test_cases=scope.test_cases,
        screens=scope.screens,
        assignments=scope.assignments,
        members=services.members,
        status_updater=AssignmentStatusUpdater(scope.assignments, scope.test_cases),
        audit_log=scope.audit_log,
        issue_sync=services.issue_sync,
        project=project,
        issue_syncer=(
            IssueSyncer(services.github, app_base_url=services.app_base_url)
            if services.github
            else None
        ),
        notifier=Notifier(services.notifications),
    )


def _content_of(body: TestCaseContent) -> TestCaseContent:
    """Lấy riêng phần nội dung (bỏ `screen_id` / `version` của lớp con)."""
    fields = set(TestCaseContent.model_fields)
    return TestCaseContent.model_validate(body.model_dump(include=fields))


def _conflict_response(services: Services, error: VersionConflictError) -> JSONResponse:
    """409 kèm bản mới nhất. Tên người sửa lấy từ tab Users, không có thì dùng email."""
    latest = error.latest
    editor = services.users.get(latest.updated_by)
    name = editor.name if editor is not None else latest.updated_by
    body = ConflictResponse(
        detail=f"Case này vừa được {name} cập nhật. Vui lòng tải lại.", latest=latest
    )
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=body.model_dump(mode="json"))


def _write(
    services: Services,
    action: Callable[[], TestCase],
    *,
    transition_status: int = status.HTTP_409_CONFLICT,
) -> TestCase | JSONResponse:
    """Chạy một thao tác ghi và đổi các lỗi nghiệp vụ thành phản hồi HTTP."""
    try:
        return action()
    except VersionConflictError as error:
        return _conflict_response(services, error)
    except InvalidTestCaseError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    except TestCasePermissionError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, NO_PERMISSION) from None
    except InvalidTransitionError as error:
        raise HTTPException(transition_status, str(error)) from None
    except TestCaseNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND) from None
    except LockTimeout:
        raise HTTPException(status.HTTP_409_CONFLICT, BUSY) from None


@router.get("")
def list_test_cases(
    project_id: str,
    user: CurrentUser,
    services: ServicesDep,
    include_archived: bool = Query(default=False),
) -> list[TestCase]:
    cases = _service(services, user, project_id, Action.VIEW_PROJECT).list_cases()
    if include_archived:
        return cases
    return [case for case in cases if case.status.value != "ARCHIVED"]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TestCase)
def create_test_case(
    project_id: str, body: CreateTestCaseRequest, user: CurrentUser, services: ServicesDep
) -> TestCase | JSONResponse:
    service = _service(services, user, project_id, Action.EDIT_TEST_CASE)
    return _write(
        services,
        lambda: service.create(user, screen_id=body.screen_id, content=_content_of(body)),
    )


@router.get("/{case_id}")
def get_test_case(
    project_id: str, case_id: str, user: CurrentUser, services: ServicesDep
) -> TestCaseDetail:
    project = load_project(services, user, project_id, Action.VIEW_PROJECT)
    service = _service_for(services, project)
    try:
        case = service.get_case(case_id)
    except TestCaseNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND) from None
    return TestCaseDetail(
        **case.model_dump(),
        # Dự án đã lưu trữ chỉ để xem, nên không ai được sửa hay duyệt
        can_edit=not project.archived and service.can_edit(user, case),
        can_review=not project.archived and service.can_review(user),
        can_archive=not project.archived and service.can_archive(user, case),
    )


@router.put("/{case_id}", response_model=TestCase, responses={409: {"model": ConflictResponse}})
def update_test_case(
    project_id: str,
    case_id: str,
    body: UpdateTestCaseRequest,
    user: CurrentUser,
    services: ServicesDep,
) -> TestCase | JSONResponse:
    service = _service(services, user, project_id, Action.EDIT_TEST_CASE)
    return _write(
        services,
        lambda: service.update_content(
            user, case_id, version=body.version, content=_content_of(body)
        ),
    )


def _transition_route(path: str, case_action: CaseAction, permission: Action) -> None:
    """Đăng ký một route chuyển trạng thái; các route chỉ khác tên thao tác và quyền."""

    def endpoint(
        project_id: str,
        case_id: str,
        body: TransitionRequest,
        user: CurrentUser,
        services: ServicesDep,
    ) -> TestCase | JSONResponse:
        service = _service(services, user, project_id, permission)
        return _write(
            services,
            lambda: service.transition(
                user, case_id, case_action, version=body.version, comment=body.comment
            ),
        )

    router.add_api_route(
        path,
        endpoint,
        methods=["POST"],
        response_model=TestCase,
        responses={409: {"model": ConflictResponse}},
        name=f"{case_action.value.lower()}_test_case",
    )


_transition_route("/{case_id}/submit", CaseAction.SUBMIT, Action.EDIT_TEST_CASE)
_transition_route("/{case_id}/approve", CaseAction.APPROVE, Action.REVIEW_TEST_CASE)
_transition_route("/{case_id}/return", CaseAction.RETURN, Action.REVIEW_TEST_CASE)
_transition_route("/{case_id}/deprecate", CaseAction.DEPRECATE, Action.EDIT_TEST_CASE)
_transition_route("/{case_id}/restore", CaseAction.RESTORE, Action.REVIEW_TEST_CASE)


def _archive_route(path: str, action: CaseAction) -> None:
    def endpoint(
        project_id: str,
        case_id: str,
        body: TransitionRequest,
        user: CurrentUser,
        services: ServicesDep,
    ) -> Response | JSONResponse:
        result = _write(
            services,
            lambda: _service(services, user, project_id, Action.EDIT_TEST_CASE).transition(
                user, case_id, action, version=body.version
            ),
            transition_status=status.HTTP_400_BAD_REQUEST,
        )
        if isinstance(result, TestCase):
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        return result

    router.add_api_route(
        path,
        endpoint,
        methods=["POST"],
        status_code=status.HTTP_204_NO_CONTENT,
        response_model=None,
        name=f"{action.value.lower()}_test_case",
    )


_archive_route("/{case_id}/archive", CaseAction.ARCHIVE)
_archive_route("/{case_id}/unarchive", CaseAction.UNARCHIVE)


@router.post("/approve-batch", response_model=BatchApproveResponse)
def approve_test_cases(
    project_id: str, body: BatchApproveRequest, user: CurrentUser, services: ServicesDep
) -> BatchApproveResponse:
    """Duyệt nhiều case một lượt; case lỗi được bỏ qua và báo lại, không làm hỏng cả lượt."""
    service = _service(services, user, project_id, Action.REVIEW_TEST_CASE)
    try:
        result = service.approve_many(user, [(item.case_id, item.version) for item in body.items])
    except TestCasePermissionError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, NO_PERMISSION) from None
    except LockTimeout:
        raise HTTPException(status.HTTP_409_CONFLICT, BUSY) from None
    return BatchApproveResponse(
        approved=result.approved,
        skipped=[SkippedItem(case_id=i.case_id, reason=i.reason) for i in result.skipped],
    )


@router.post("/sync-issues", response_model=SyncIssuesResult)
def sync_test_case_issues(
    project_id: str, user: CurrentUser, services: ServicesDep
) -> SyncIssuesResult:
    service = _service(services, user, project_id, Action.REVIEW_TEST_CASE)
    if services.github is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "GitHub chưa được cấu hình")
    try:
        return service.sync_issues(user)
    except TestCasePermissionError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, NO_PERMISSION) from None


@router.get("/{case_id}/history")
def test_case_history(
    project_id: str, case_id: str, user: CurrentUser, services: ServicesDep
) -> list[AuditEntry]:
    service = _service(services, user, project_id, Action.VIEW_PROJECT)
    try:
        service.get_case(case_id)  # id lạ thì báo 404 chứ không trả danh sách rỗng
    except TestCaseNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND) from None
    return service.history(case_id)
