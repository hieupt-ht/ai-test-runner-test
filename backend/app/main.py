import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from starlette.middleware.sessions import SessionMiddleware

from app.api.routers import (
    agent,
    assignments,
    auth,
    github,
    health,
    me,
    media,
    members,
    notifications,
    projects,
    regression,
    results,
    screens,
    test_cases,
    users,
)
from app.api.services import Services, build_gateway, build_services, is_configured
from app.core.bootstrap import (
    ConfigError,
    bootstrap_system_spreadsheet,
    upgrade_project_spreadsheets,
)
from app.settings import Settings, get_settings

logger = logging.getLogger(__name__)


def start_real_services(settings: Settings) -> Services | None:
    """Dựng kết nối thật tới Google Sheets và Redis, rồi chuẩn bị Sheet hệ thống.

    Chưa cấu hình Google Sheets thì trả về None: app vẫn chạy, các API cần dữ liệu trả 503.
    """
    if not is_configured(settings):
        logger.warning("Chưa cấu hình GOOGLE_SERVICE_ACCOUNT_JSON / SYSTEM_SPREADSHEET_ID.")
        return None
    if not settings.session_secret:
        raise ConfigError("Thiếu SESSION_SECRET trong .env")

    gateway = build_gateway(settings)
    services = build_services(settings, gateway)
    created_tabs = bootstrap_system_spreadsheet(
        gateway, settings.system_spreadsheet_id, services.users, settings.bootstrap_admin_email,
        settings.bootstrap_admin_password,
    )
    if created_tabs:
        logger.info("Đã tạo các tab: %s", ", ".join(created_tabs))
    upgrade_project_spreadsheets(services.projects, gateway)
    return services


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Test truyền sẵn services giả; app thật thì dựng services lúc khởi động.
        if app.state.services is None:
            app.state.services = await run_in_threadpool(start_real_services, settings)
        yield

    app = FastAPI(title="AI Test Runner API", lifespan=lifespan)
    app.state.settings = settings
    app.state.services = services

    # Starlette dùng cookie tạm này để giữ "state" của OAuth giữa lúc đi và lúc về từ Google.
    session_secret = settings.session_secret or secrets.token_urlsafe(32)
    if not settings.session_secret:
        logger.warning("Chưa đặt SESSION_SECRET, đang dùng khoá ngẫu nhiên tạm thời.")
    app.add_middleware(SessionMiddleware, secret_key=session_secret, same_site="lax")

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(projects.router)
    app.include_router(github.router)
    app.include_router(screens.router)
    app.include_router(assignments.router)
    app.include_router(agent.router)
    app.include_router(media.router)
    app.include_router(test_cases.router)
    app.include_router(me.router)
    app.include_router(members.router)
    app.include_router(notifications.router)
    app.include_router(results.router)
    app.include_router(regression.router)
    return app
