import logging

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from app.api.deps import CurrentUser, ServicesDep
from app.api.sessions import SESSION_COOKIE
from app.core.models.user import User
from app.core.services.auth import LoginLockedError, authenticate
from app.settings import Settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

LOGIN_FAILED = "Email hoặc mật khẩu không đúng"
LOGIN_LOCKED = "Bạn đã nhập sai quá nhiều lần. Vui lòng thử lại sau 15 phút"


class LoginRequest(BaseModel):
    email: str
    password: str  # không strip: khoảng trắng có thể là một phần của mật khẩu


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


@router.get("/me")
def me(user: CurrentUser) -> User:
    return user
