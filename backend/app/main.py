from fastapi import FastAPI

from app.api.routers import health
from app.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="AI Test Runner API")
    app.state.settings = settings
    app.include_router(health.router)
    return app
