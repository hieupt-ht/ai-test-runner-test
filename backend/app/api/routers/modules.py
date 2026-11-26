from typing import Annotated

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import CurrentUser, ServicesDep
from app.api.project_access import load_project
from app.api.project_scope import scope_for
from app.api.services import Services
from app.core.locks.redis_lock import LockTimeout
from app.core.models.module import Module
from app.core.models.user import User
from app.core.permissions import Action
from app.core.repositories.modules import ModuleNotFoundError
from app.core.services.modules import (
    DuplicateModuleNameError,
    ModuleHasScreensError,
    ModuleService,
    ModuleView,
)

router = APIRouter(prefix="/api/projects/{project_id}/modules", tags=["modules"])

ModuleName = Annotated[str, Field(min_length=1, max_length=100)]
Description = Annotated[str, Field(max_length=2000)]

NOT_FOUND = "Không tìm thấy module"
HAS_SCREENS = "Module còn màn hình, hãy chuyển hoặc xoá màn hình trước"


class CreateModuleRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: ModuleName
    description: Description = ""


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
    service = _service(services, user, project_id, Action.MANAGE_SCREENS)
    try:
        return service.create_module(user, name=body.name, description=body.description)
    except DuplicateModuleNameError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    except LockTimeout:
        raise _busy() from None


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
