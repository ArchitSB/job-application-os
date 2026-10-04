from fastapi import APIRouter

from app.api.routes.platform import DB, Actor
from app.schemas.lead_hunter import HunterBatch, HunterContext, HunterReport
from app.services.lead_hunter import get_context, process_research

router = APIRouter(prefix="/lead-hunter", tags=["lead hunter"])


@router.get("/context", response_model=HunterContext)
def context(db: DB):
    return get_context(db)


@router.post("/research", response_model=HunterReport)
def research(data: HunterBatch, db: DB, actor: Actor = "hermes"):
    return process_research(db, data, actor)
