from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import AwareDatetime
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models import (
    Application,
    ApplicationEvent,
    ApplicationRules,
    AutomationRun,
    Company,
    Contact,
    EmailDraft,
    JobLead,
    ResumeProfile,
    UserProfile,
)
from app.schemas import domain as s
from app.services.dashboard import dashboard
from app.services.duplicates import check_duplicate
from app.services.normalization import normalize_company
from app.services.workflow import event, get_record, rules, save_application, save_draft, save_lead

router = APIRouter()
DB = Annotated[Session, Depends(get_session)]
Actor = Annotated[Literal["user", "hermes", "system"], Header(alias="X-Actor")]


class Filters:
    def __init__(
        self,
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100),
        search: str | None = Query(None, max_length=200),
        status: str | None = None,
        source: str | None = None,
        resume_type: s.ResumeType | None = None,
        date_from: AwareDatetime | None = None,
        date_to: AwareDatetime | None = None,
        application_method: s.ApplicationMethod | None = None,
    ):
        if date_from and date_to and date_from > date_to:
            raise HTTPException(422, "date_from must be before date_to")
        self.page, self.page_size, self.search = page, page_size, search
        self.status, self.source, self.resume_type = status, source, resume_type
        self.date_from, self.date_to = date_from, date_to
        self.application_method = application_method


F = Annotated[Filters, Depends()]


def listing(db: Session, model, filters: Filters, search_columns: list, *conditions):
    query = select(model).where(*conditions)
    if filters.application_method and model is Application:
        query = query.where(Application.application_method == filters.application_method)
    if filters.search and search_columns:
        value = filters.search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(or_(*(col.ilike(f"%{value}%", escape="\\") for col in search_columns)))
    for field in ("status", "source"):
        if getattr(filters, field) and hasattr(model, field):
            query = query.where(getattr(model, field) == getattr(filters, field))
    if filters.resume_type:
        column = (
            getattr(model, "recommended_resume_type", None)
            if model is JobLead
            else getattr(model, "resume_type", None)
        )
        if column is not None:
            query = query.where(column == filters.resume_type)
    date_column = model.discovered_at if model is JobLead else getattr(model, "created_at", None)
    if date_column is not None:
        if filters.date_from:
            query = query.where(date_column >= filters.date_from)
        if filters.date_to:
            query = query.where(date_column <= filters.date_to)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    order = model.occurred_at if model is ApplicationEvent else model.created_at
    items = db.scalars(
        query.order_by(order.desc(), model.id)
        .offset((filters.page - 1) * filters.page_size)
        .limit(filters.page_size)
    ).all()
    return {"items": items, "total": total, "page": filters.page, "page_size": filters.page_size}


@router.get("/companies", response_model=s.Page[s.CompanyRead], tags=["companies"])
def companies(db: DB, f: F):
    return listing(db, Company, f, [Company.name, Company.normalized_name])


@router.get("/companies/{record_id}", response_model=s.CompanyRead, tags=["companies"])
def company(record_id: UUID, db: DB):
    return get_record(db, Company, record_id)


@router.post("/companies", response_model=s.CompanyRead, status_code=201, tags=["companies"])
def create_company(data: s.CompanyCreate, db: DB):
    values = data.model_dump()
    if values["domain"]:
        values["domain"] = values["domain"].lower().removeprefix("www.")
    record = Company(**values, normalized_name=normalize_company(data.name))
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/leads", response_model=s.Page[s.LeadRead], tags=["leads"])
def leads(db: DB, f: F):
    return listing(db, JobLead, f, [JobLead.role_title, JobLead.company_name, JobLead.description])


@router.get("/leads/{record_id}", response_model=s.LeadRead, tags=["leads"])
def lead(record_id: UUID, db: DB):
    return get_record(db, JobLead, record_id)


@router.post("/leads", response_model=s.LeadRead, status_code=201, tags=["leads"])
def create_lead(data: s.LeadCreate, db: DB, actor: Actor = "user"):
    return save_lead(db, data.model_dump(exclude_none=True), actor)


@router.patch("/leads/{record_id}", response_model=s.LeadRead, tags=["leads"])
def update_lead(record_id: UUID, data: s.LeadPatch, db: DB, actor: Actor = "user"):
    return save_lead(db, data.model_dump(exclude_unset=True), actor, record_id)


@router.get("/leads/{record_id}/events", response_model=s.Page[s.EventRead], tags=["events"])
def lead_events(record_id: UUID, db: DB, f: F):
    get_record(db, JobLead, record_id)
    return listing(db, ApplicationEvent, f, [], ApplicationEvent.job_lead_id == record_id)


@router.post("/applications/check-duplicate", response_model=s.DuplicateResult, tags=["applications"])
def duplicate(data: s.DuplicateCheck, db: DB):
    company = get_record(db, Company, data.company_id)
    return check_duplicate(db, data, company)


@router.get("/applications", response_model=s.Page[s.ApplicationRead], tags=["applications"])
def applications(db: DB, f: F):
    return listing(db, Application, f, [Application.role_title, Application.company_name, Application.notes])


@router.get("/applications/{record_id}", response_model=s.ApplicationRead, tags=["applications"])
def application(record_id: UUID, db: DB):
    return get_record(db, Application, record_id)


@router.post("/applications", response_model=s.ApplicationRead, status_code=201, tags=["applications"])
def create_application(data: s.ApplicationCreate, db: DB, actor: Actor = "user"):
    return save_application(db, data.model_dump(), actor)


@router.patch("/applications/{record_id}", response_model=s.ApplicationRead, tags=["applications"])
def update_application(record_id: UUID, data: s.ApplicationPatch, db: DB, actor: Actor = "user"):
    return save_application(db, data.model_dump(exclude_unset=True), actor, record_id)


@router.get("/applications/{record_id}/events", response_model=s.Page[s.EventRead], tags=["events"])
def application_events(record_id: UUID, db: DB, f: F):
    get_record(db, Application, record_id)
    return listing(db, ApplicationEvent, f, [], ApplicationEvent.application_id == record_id)


@router.post("/applications/{record_id}/events", response_model=s.EventRead, status_code=201, tags=["events"])
def create_event(record_id: UUID, data: s.EventCreate, db: DB, actor: Actor = "user"):
    app = get_record(db, Application, record_id)
    if data.automation_run_id:
        get_record(db, AutomationRun, data.automation_run_id)
    record = event(
        db, data.event_type, actor, application=app, metadata=data.metadata, run_id=data.automation_run_id
    )
    db.commit()
    db.refresh(record)
    return record


@router.get("/contacts", response_model=s.Page[s.ContactRead], tags=["contacts"])
def contacts(db: DB, f: F):
    return listing(db, Contact, f, [Contact.name, Contact.email])


@router.post("/contacts", response_model=s.ContactRead, status_code=201, tags=["contacts"])
def create_contact(data: s.ContactCreate, db: DB):
    if data.company_id:
        get_record(db, Company, data.company_id)
    record = Contact(**data.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/resumes", response_model=list[s.ResumeRead], tags=["resumes"])
def resumes(db: DB):
    return db.scalars(select(ResumeProfile).order_by(ResumeProfile.profile_type)).all()


@router.get("/email-drafts", response_model=s.Page[s.DraftRead], tags=["email drafts"])
def drafts(db: DB, f: F):
    return listing(db, EmailDraft, f, [EmailDraft.subject, EmailDraft.recipient_email])


@router.get("/email-drafts/{record_id}", response_model=s.DraftRead, tags=["email drafts"])
def draft(record_id: UUID, db: DB):
    return get_record(db, EmailDraft, record_id)


@router.post("/email-drafts", response_model=s.DraftRead, status_code=201, tags=["email drafts"])
def create_draft(data: s.DraftCreate, db: DB, actor: Actor = "user"):
    return save_draft(db, data.model_dump(), actor)


@router.patch("/email-drafts/{record_id}", response_model=s.DraftRead, tags=["email drafts"])
def update_draft(record_id: UUID, data: s.DraftPatch, db: DB, actor: Actor = "user"):
    return save_draft(db, data.model_dump(exclude_unset=True), actor, record_id)


@router.get("/dashboard/summary", response_model=s.Dashboard, tags=["dashboard"])
def summary(db: DB):
    return dashboard(db)


@router.get("/rules", response_model=s.Rules, tags=["settings"])
def get_rules(db: DB):
    return rules(db)


@router.patch("/rules", response_model=s.Rules, tags=["settings"])
def update_rules(data: s.RulesPatch, db: DB, actor: Actor = "user"):
    if actor != "user":
        raise HTTPException(403, "Only the user can configure application rules")
    record = db.get(ApplicationRules, 1, with_for_update=True)
    values = rules(db).model_dump()
    values.update(data.model_dump(exclude_unset=True))
    validated = s.Rules(**values)
    if record:
        record.settings = validated.model_dump()
    else:
        db.add(ApplicationRules(id=1, settings=validated.model_dump()))
    db.commit()
    return validated


@router.get("/profile", response_model=s.Profile, tags=["settings"])
def profile(db: DB):
    record = db.get(UserProfile, 1)
    if not record:
        raise HTTPException(404, "Profile not seeded; run the seed command")
    return record


@router.patch("/profile", response_model=s.Profile, tags=["settings"])
def update_profile(data: s.ProfilePatch, db: DB, actor: Actor = "user"):
    if actor != "user":
        raise HTTPException(403, "Only the user can edit profile information")
    record = db.get(UserProfile, 1, with_for_update=True)
    if not record:
        raise HTTPException(404, "Profile not seeded")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return record


@router.get("/automation-runs", response_model=s.Page[s.RunRead], tags=["automation records"])
def runs(db: DB, f: F):
    return listing(db, AutomationRun, f, [AutomationRun.agent, AutomationRun.run_type])


@router.post("/automation-runs", response_model=s.RunRead, status_code=201, tags=["automation records"])
def create_run(data: s.RunCreate, db: DB):
    record = AutomationRun(**data.model_dump(), status="pending")
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.patch("/automation-runs/{record_id}", response_model=s.RunRead, tags=["automation records"])
def update_run(record_id: UUID, data: s.RunPatch, db: DB):
    record = get_record(db, AutomationRun, record_id, lock=True)
    allowed = {"pending": {"running", "cancelled"}, "running": {"completed", "failed", "cancelled"}}
    if data.status not in allowed.get(record.status, set()):
        raise HTTPException(409, "Invalid automation run transition")
    record.status = data.status
    record.output_metadata = data.output_metadata
    record.error_information = data.error_information
    if data.status == "running":
        record.started_at = datetime.now(timezone.utc)
    else:
        record.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)
    return record


@router.patch("/resumes/{record_id}", response_model=s.ResumeRead, tags=["resumes"])
def update_resume(record_id: UUID, data: s.ResumePatch, db: DB, actor: Actor = "user"):
    from pathlib import Path

    from app.core.config import PROJECT_ROOT

    if actor != "user":
        raise HTTPException(403, "Only the user can configure resume files")
    record = get_record(db, ResumeProfile, record_id, lock=True)
    values = data.model_dump(exclude_unset=True)
    if data.local_path:
        root = (PROJECT_ROOT / "resumes").resolve()
        path = (PROJECT_ROOT / data.local_path).resolve()
        if (
            Path(data.local_path).is_absolute()
            or not path.is_relative_to(root)
            or path.suffix.lower() != ".pdf"
            or not path.is_file()
        ):
            raise HTTPException(422, "local_path must identify an existing PDF inside resumes/")
        values["local_path"] = str(path.relative_to(PROJECT_ROOT))
    for key, value in values.items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return record
