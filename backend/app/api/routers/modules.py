import logging
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import CurrentUser, ServicesDep
from app.api.project_access import load_project
from app.api.project_scope import module_work_for, scope_for
from app.api.services import Services
from app.core.locks.redis_lock import LockTimeout
from app.core.models.module import Module, ModuleAssignment
from app.core.models.user import Role, User
from app.core.permissions import Action
from app.core.repositories.modules import ModuleAssignmentNotFoundError, ModuleNotFoundError
from app.core.services.assignments import InvalidAssignmentError
from app.core.services.module_work import ModuleWorkPermissionError, ModuleWorkService
from app.core.services.modules import (
    DuplicateModuleNameError,
    ModuleHasScreensError,
    ModuleService,
    ModuleView,
)
from app.core.time import today_in_vietnam

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects/{project_id}/modules", tags=["modules"])

ModuleName = Annotated[str, Field(min_length=1, max_length=100)]
Description = Annotated[str, Field(max_length=2000)]

NOT_FOUND = "Không tìm thấy module"
WORKER_NOT_FOUND = "Không tìm thấy việc nhận module"
NO_PERMISSION = "Bạn không có quyền thực hiện thao tác này"
HAS_SCREENS = "Module còn màn hình, hãy chuyển hoặc xoá màn hình trước"


class CreateModuleRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: ModuleName
    description: Description = ""


class AssignWorkersRequest(BaseModel):
    emails: Annotated[list[str], Field(min_length=1, max_length=20)]
    deadline: date


class ChangeDeadlineRequest(BaseModel):
    deadline: date


class UnassignResult(BaseModel):
    removed_screen_assignments: int


class UpdateModuleRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: ModuleName | None = None
    description: Description | None = None


def _service(services: Services, user: User, project_id: str, action: Action) -> ModuleService:
    project = load_project(services, user, project_id, action)
    scope = scope_for(services, project)
    return ModuleService(
        scope.modules, scope.screens, scope.module_assignments, services.users, scope.audit_log
    )


def _busy() -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, "Dữ liệu đang được cập nhật, vui lòng thử lại")


@router.get("")
def list_modules(project_id: str, user: CurrentUser, services: ServicesDep) -> list[ModuleView]:
    return _service(services, user, project_id, Action.VIEW_PROJECT).list_modules()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_module(
    project_id: str, body: CreateModuleRequest, user: CurrentUser, services: ServicesDep
) -> Module:
    # Tester cũng được tạo module (miễn tên không trùng); đổi tên/xoá vẫn chỉ QA
    service = _service(services, user, project_id, Action.EDIT_TEST_CASE)
    try:
        module = service.create_module(user, name=body.name, description=body.description)
    except DuplicateModuleNameError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    except LockTimeout:
        raise _busy() from None
    if user.role == Role.TESTER:
        _claim_new_module(services, user, project_id, service, module)
    return module


def _delete_orphan(service: ModuleService, user: User, module: Module) -> None:
    """Xoá module vừa tạo; vướng khoá thì thử lại vài lần (nhận hết giờ cũng do khoá đó)."""
    for attempt in range(3):
        try:
            service.delete_module(user, module.id)
            return
        except LockTimeout:
            if attempt < 2:
                continue
            logger.warning("Không xoá được module %s (khoá bận)", module.id)
        except Exception:
            logger.warning("Không xoá được module %s sau khi nhận lỗi", module.id, exc_info=True)
            return


def _claim_new_module(
    services: Services, user: User, project_id: str, service: ModuleService, module: Module
) -> None:
    """Tester tạo module thì nhận luôn (hạn 7 ngày). Nhận lỗi thì xoá module để khỏi mồ côi."""
    try:
        work_service_for(services, user, project_id, Action.EDIT_TEST_CASE).assign(
            user,
            module_id=module.id,
            emails=[user.email],
            deadline=today_in_vietnam() + timedelta(days=7),
        )
    except Exception as error:
        _delete_orphan(service, user, module)
        if isinstance(error, LockTimeout):
            raise _busy() from None
        raise


@router.patch("/{module_id}")
def update_module(
    project_id: str,
    module_id: str,
    body: UpdateModuleRequest,
    user: CurrentUser,
    services: ServicesDep,
) -> Module:
    service = _service(services, user, project_id, Action.MANAGE_SCREENS)
    try:
        return service.update_module(user, module_id, name=body.name, description=body.description)
    except DuplicateModuleNameError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    except ModuleNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND) from None
    except LockTimeout:
        raise _busy() from None


@router.delete("/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_module(
    project_id: str, module_id: str, user: CurrentUser, services: ServicesDep
) -> Response:
    service = _service(services, user, project_id, Action.MANAGE_SCREENS)
    try:
        service.delete_module(user, module_id)
    except ModuleHasScreensError:
        raise HTTPException(status.HTTP_409_CONFLICT, HAS_SCREENS) from None
    except ModuleNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND) from None
    except LockTimeout:
        raise _busy() from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def work_service_for(
    services: Services, user: User, project_id: str, action: Action
) -> ModuleWorkService:
    """Dùng chung với router màn hình và import: dựng ModuleWorkService từ phạm vi dự án."""
    project = load_project(services, user, project_id, action)
    scope = scope_for(services, project)
    return module_work_for(services, scope)


@router.post("/{module_id}/workers", status_code=status.HTTP_201_CREATED)
def assign_workers(
    project_id: str,
    module_id: str,
    body: AssignWorkersRequest,
    user: CurrentUser,
    services: ServicesDep,
) -> list[ModuleAssignment]:
    service = work_service_for(services, user, project_id, Action.EDIT_TEST_CASE)
    try:
        return service.assign(user, module_id=module_id, emails=body.emails, deadline=body.deadline)
    except ModuleWorkPermissionError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, NO_PERMISSION) from None
    except InvalidAssignmentError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    except ModuleNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND) from None
    except LockTimeout:
        raise _busy() from None


@router.patch("/{module_id}/workers/{worker_id}")
def change_worker_deadline(
    project_id: str,
    module_id: str,
    worker_id: str,
    body: ChangeDeadlineRequest,
    user: CurrentUser,
    services: ServicesDep,
) -> ModuleAssignment:
    service = work_service_for(services, user, project_id, Action.EDIT_TEST_CASE)
    try:
        return service.change_deadline(user, worker_id, body.deadline, module_id=module_id)
    except ModuleWorkPermissionError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, NO_PERMISSION) from None
    except InvalidAssignmentError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    except ModuleAssignmentNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, WORKER_NOT_FOUND) from None
    except LockTimeout:
        raise _busy() from None


@router.delete("/{module_id}/workers/{worker_id}")
def unassign_worker(
    project_id: str, module_id: str, worker_id: str, user: CurrentUser, services: ServicesDep
) -> UnassignResult:
    service = work_service_for(services, user, project_id, Action.EDIT_TEST_CASE)
    try:
        removed = service.unassign(user, worker_id, module_id=module_id)
    except ModuleWorkPermissionError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, NO_PERMISSION) from None
    except ModuleAssignmentNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, WORKER_NOT_FOUND) from None
    except LockTimeout:
        raise _busy() from None
    return UnassignResult(removed_screen_assignments=removed)
