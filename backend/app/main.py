from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.integration import router as integration_router
from app.api.routes.lead_hunter import router as lead_hunter_router
from app.api.routes.platform import router as platform_router
from app.core.config import get_settings
from app.core.errors import install_error_handlers


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version="0.2.0",
        description="Local personal application management. No authentication; bind to loopback only.",
    )
    application.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"]
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type", "X-Actor"],
    )
    install_error_handlers(application)
    application.include_router(health_router)
    application.include_router(integration_router)
    application.include_router(lead_hunter_router)
    application.include_router(platform_router)
    return application
