from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.api.deps import CurrentUser, ServicesDep, require
from app.core.locks.redis_lock import LockTimeout
from app.core.models.user import Role, User
from app.core.permissions import Action
from app.core.repositories.users import UserAlreadyExistsError, UserNotFoundError
from app.core.services.users import CannotChangeSelfError, UserService

router = APIRouter(prefix="/api/users", tags=["users"])

Name = Annotated[str, Field(min_length=1, max_length=100)]


class CreateUserRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    name: Name
    role: Role


class UpdateUserRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: Name | None = None
    role: Role | None = None
    active: bool | None = None


def _service(services: ServicesDep) -> UserService:
    return UserService(services.users, services.audit_log)


@router.get("")
def list_users(user: CurrentUser, services: ServicesDep) -> list[User]:
    require(user, Action.MANAGE_USERS)
    return _service(services).list_users()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(body: CreateUserRequest, user: CurrentUser, services: ServicesDep) -> User:
    require(user, Action.MANAGE_USERS)
    try:
        return _service(services).create_user(
            user, email=body.email, name=body.name, role=body.role
        )
    except UserAlreadyExistsError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email này đã có trong hệ thống") from None
    except LockTimeout:
        raise _busy_error() from None


@router.patch("/{email}")
def update_user(
    email: str, body: UpdateUserRequest, user: CurrentUser, services: ServicesDep
) -> User:
    require(user, Action.MANAGE_USERS)
    try:
        return _service(services).update_user(
            user, email, name=body.name, role=body.role, active=body.active
        )
    except UserNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy người dùng") from None
    except CannotChangeSelfError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Bạn không thể tự khoá hoặc tự hạ quyền của chính mình"
        ) from None
    except LockTimeout:
        raise _busy_error() from None


def _busy_error() -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT, "Dữ liệu đang được người khác cập nhật, vui lòng thử lại"
    )
