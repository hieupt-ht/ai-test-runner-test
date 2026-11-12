import logging
import secrets

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.api.routers import auth, health, users
from app.api.services import Services
from app.settings import Settings, get_settings

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="AI Test Runner API")
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
    return app
