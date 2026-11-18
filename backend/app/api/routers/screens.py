from typing import Annotated

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from app.api.deps import CurrentUser, ServicesDep
from app.api.project_access import load_project
from app.api.project_scope import scope_for
from app.api.services import Services
from app.core.locks.redis_lock import LockTimeout
from app.core.models.media import MediaList
from app.core.models.screen import MAX_CODE_PATHS, CodePath, Screen
from app.core.models.user import User
from app.core.permissions import Action
from app.core.repositories.screens import ScreenNotFoundError
from app.core.services.screens import (
    InvalidScreenError,
    ScreenHasTestCasesError,
    ScreenInUseError,
    ScreenService,
)

router = APIRouter(prefix="/api/projects/{project_id}/screens", tags=["screens"])

ScreenName = Annotated[str, Field(min_length=1, max_length=100)]
Description = Annotated[str, Field(max_length=2000)]
Route = Annotated[str, Field(max_length=200)]
CodePaths = Annotated[list[CodePath], Field(max_length=MAX_CODE_PATHS)]


def _strip_at(value: object) -> object:
    """Người dùng hay gõ `@tên`; GitHub cần tên trần nên bỏ `@` ở đầu trước khi kiểm tra."""
    return value.strip().removeprefix("@") if isinstance(value, str) else value


# Tên tài khoản GitHub: chữ/số/dấu gạch, không bắt đầu hay kết thúc bằng "-", tối đa 39 ký tự.
# Chuỗi rỗng nghĩa là chưa có dev phụ trách.
GitHubUsername = Annotated[
    str,
    BeforeValidator(_strip_at),
    Field(max_length=39, pattern=r"^$|^[A-Za-z0-9]+(-[A-Za-z0-9]+)*$"),
]

NOT_FOUND = "Không tìm thấy màn hình"


class CreateScreenRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: ScreenName
    description: Description = ""
    route: Route = ""
    code_paths: CodePaths = []
    dev_owner: GitHubUsername = ""
    media: MediaList = []


class UpdateScreenRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: ScreenName | None = None
    description: Description | None = None
    route: Route | None = None
    code_paths: CodePaths | None = None
    dev_owner: GitHubUsername | None = None
    media: MediaList | None = None


def _service(services: Services, user: User, project_id: str, action: Action) -> ScreenService:
    project = load_project(services, user, project_id, action)
    scope = scope_for(services, project)
    return ScreenService(
        scope.screens,
        scope.assignments,
        scope.test_cases,
        scope.audit_log,
        cloud_name=services.cloud_name,
        drive_enabled=services.drive is not None,
        janitor=services.media_janitor,
    )


def _busy() -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, "Dữ liệu đang được cập nhật, vui lòng thử lại")


@router.get("")
def list_screens(project_id: str, user: CurrentUser, services: ServicesDep) -> list[Screen]:
    return _service(services, user, project_id, Action.VIEW_PROJECT).list_screens()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_screen(
    project_id: str, body: CreateScreenRequest, user: CurrentUser, services: ServicesDep
) -> Screen:
    service = _service(services, user, project_id, Action.MANAGE_SCREENS)
    try:
        return service.create_screen(
            user,
            name=body.name,
            description=body.description,
            route=body.route,
            code_paths=body.code_paths,
            dev_owner=body.dev_owner,
            media=body.media,
        )
    except InvalidScreenError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    except LockTimeout:
        raise _busy() from None


@router.patch("/{screen_id}")
def update_screen(
    project_id: str,
    screen_id: str,
    body: UpdateScreenRequest,
    user: CurrentUser,
    services: ServicesDep,
) -> Screen:
    service = _service(services, user, project_id, Action.MANAGE_SCREENS)
    try:
        return service.update_screen(
            user,
            screen_id,
            name=body.name,
            description=body.description,
            route=body.route,
            code_paths=body.code_paths,
            dev_owner=body.dev_owner,
            media=body.media,
        )
    except InvalidScreenError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    except ScreenNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND) from None
    except LockTimeout:
        raise _busy() from None


@router.delete("/{screen_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_screen(
    project_id: str, screen_id: str, user: CurrentUser, services: ServicesDep
) -> Response:
    service = _service(services, user, project_id, Action.MANAGE_SCREENS)
    try:
        service.delete_screen(user, screen_id)
    except ScreenInUseError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Màn hình đang được giao cho tester, hãy bỏ giao việc trước",
        ) from None
    except ScreenHasTestCasesError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Màn hình đang có test case, không xoá được"
        ) from None
    except ScreenNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND) from None
    except LockTimeout:
        raise _busy() from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
