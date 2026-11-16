import logging

from authlib.integrations.base_client.errors import OAuthError
from fastapi import APIRouter, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse, Response

from app.api.deps import CurrentUser, ServicesDep
from app.api.sessions import SESSION_COOKIE
from app.core.models.user import User
from app.core.services.auth import authenticate
from app.settings import Settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


@router.get("/auth/login")
async def login(request: Request, services: ServicesDep) -> Response:
    redirect_uri = f"{_settings(request).app_base_url}/api/auth/callback"
    return await services.oauth.authorize_redirect(request, redirect_uri)


@router.get("/auth/callback")
async def callback(request: Request, services: ServicesDep) -> Response:
    try:
        identity = await services.oauth.fetch_identity(request)
    except OAuthError as error:
        # Người dùng bấm Huỷ ở Google, hoặc tải lại/mở trang callback ở tab khác.
        logger.info("Đăng nhập Google không thành công: %s", error.error)
        return RedirectResponse("/login?error=oauth_failed", status.HTTP_302_FOUND)
    # Đọc Sheet là việc chặn (blocking), nên chạy trong threadpool.
    user = await run_in_threadpool(authenticate, services.users, identity.email)
    if user is None:
        return RedirectResponse("/login?error=not_allowed", status.HTTP_302_FOUND)

    settings = _settings(request)
    session_id = services.sessions.create(user.email)
    response = RedirectResponse("/", status.HTTP_302_FOUND)
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.app_base_url.startswith("https"),
    )
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
