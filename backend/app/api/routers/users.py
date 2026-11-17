from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.api.deps import CurrentUser, ServicesDep, require
from app.core.locks.redis_lock import LockTimeout
from app.core.models.user import Role, User
from app.core.passwords import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH
from app.core.permissions import Action
from app.core.repositories.users import UserAlreadyExistsError, UserNotFoundError
from app.core.services.users import CannotChangeSelfError, UserService

router = APIRouter(prefix="/api/users", tags=["users"])

Name = Annotated[str, Field(min_length=1, max_length=100)]
# Mật khẩu giữ nguyên khoảng trắng đầu/cuối (ghi đè str_strip_whitespace của model).
Password = Annotated[
    str,
    StringConstraints(
        strip_whitespace=False, min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH
    ),
]


class CreateUserRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    name: Name
    role: Role
    password: Password


class UpdateUserRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: Name | None = None
    role: Role | None = None
    active: bool | None = None


class ResetPasswordRequest(BaseModel):
    password: Password


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
            user, email=body.email, name=body.name, role=body.role, password=body.password
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


@router.post("/{email}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    email: str, body: ResetPasswordRequest, user: CurrentUser, services: ServicesDep
) -> None:
    require(user, Action.MANAGE_USERS)
    try:
        _service(services).reset_password(user, email, body.password)
    except UserNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy người dùng") from None
    except LockTimeout:
        raise _busy_error() from None
    services.sessions.delete_all_for(email)  # bắt người đó đăng nhập lại bằng mật khẩu mới


def _busy_error() -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT, "Dữ liệu đang được người khác cập nhật, vui lòng thử lại"
    )
