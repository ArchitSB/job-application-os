from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    application = FastAPI(title=get_settings().app_name, version="0.1.0")
    application.include_router(health_router)
    return application
