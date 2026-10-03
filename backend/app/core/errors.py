import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException

logger = logging.getLogger("job_application_os")


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        detail = exc.detail
        error = detail if isinstance(detail, dict) else {"code": f"http_{exc.status_code}", "message": detail}
        return JSONResponse(status_code=exc.status_code, content={"error": error}, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        fields = [{"field": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()]
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "validation_error", "message": "Invalid request", "fields": fields}},
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        # Never log SQL parameters, connection strings, profile values or draft bodies.
        logger.error(
            "Database operation failed: %s %s (%s)", request.method, request.url.path, type(exc).__name__
        )
        conflict = isinstance(exc, IntegrityError)
        return JSONResponse(
            status_code=409 if conflict else 503,
            content={
                "error": {
                    "code": "data_conflict" if conflict else "database_unavailable",
                    "message": "The change conflicts with stored data"
                    if conflict
                    else "Database temporarily unavailable",
                }
            },
        )
