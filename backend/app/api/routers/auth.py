import logging

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from app.api.deps import CurrentUser, ServicesDep
from app.api.routers.users import Password
from app.api.sessions import SESSION_COOKIE
from app.core.models.user import User
from app.core.services.auth import (
    LoginLockedError,
    WrongCurrentPasswordError,
    authenticate,
    change_password,
)
from app.settings import Settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

LOGIN_FAILED = "Email hoặc mật khẩu không đúng"
LOGIN_LOCKED = "Bạn đã nhập sai quá nhiều lần. Vui lòng thử lại sau 15 phút"


class LoginRequest(BaseModel):
    email: str
    password: str  # không strip: khoảng trắng có thể là một phần của mật khẩu


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: Password


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def set_session_cookie(response: Response, settings: Settings, session_id: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.app_base_url.startswith("https"),
    )


@router.post("/auth/login")
async def login(body: LoginRequest, request: Request, services: ServicesDep) -> Response:
    try:
        # Đọc Sheet là việc chặn (blocking), nên chạy trong threadpool.
        user = await run_in_threadpool(
            authenticate, services.users, body.email, body.password, services.login_throttle
        )
    except LoginLockedError:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, LOGIN_LOCKED) from None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, LOGIN_FAILED)

    response = JSONResponse(user.model_dump(mode="json"))
    set_session_cookie(response, _settings(request), services.sessions.create(user.email))
    return response


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, services: ServicesDep) -> Response:
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id:
        services.sessions.delete(session_id)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(SESSION_COOKIE)
    return response


@router.post("/auth/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_my_password(
    body: ChangePasswordRequest, user: CurrentUser, request: Request, services: ServicesDep
) -> Response:
    try:
        await run_in_threadpool(
            change_password,
            services.users,
            user.email,
            body.current_password,
            body.new_password,
            services.login_throttle,
        )
    except LoginLockedError:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, LOGIN_LOCKED) from None
    except WrongCurrentPasswordError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Mật khẩu hiện tại không đúng") from None

    # Đăng xuất mọi nơi, rồi cấp phiên mới cho trình duyệt đang dùng.
    services.sessions.delete_all_for(user.email)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    set_session_cookie(response, _settings(request), services.sessions.create(user.email))
    return response


@router.get("/me")
def me(user: CurrentUser) -> User:
    return user
