from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.services.health import check_database

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/db")
def database_health(session: Annotated[Session, Depends(get_session)]) -> dict[str, str]:
    try:
        reachable = check_database(session)
    except SQLAlchemyError:
        # Never expose connection strings or driver errors to API clients.
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    if not reachable:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ok", "database": "reachable"}
