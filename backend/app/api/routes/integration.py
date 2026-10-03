"""HTTP conveniences for name-based intake. All state still uses existing services."""

from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select, text

from app.api.routes.platform import DB, Actor
from app.models import Application, Company, Contact, EmailDraft
from app.schemas.domain import CompanyRead, ContactRead, DraftRead, DuplicateResult, LeadRead
from app.schemas.integration import DraftApproval, DuplicateByCompany, LeadIntake, LeadIntakeResult
from app.services.duplicates import check_duplicate
from app.services.normalization import normalize_company
from app.services.workflow import event, get_record, save_draft, save_lead

router = APIRouter(tags=["integration helpers"])


def resolve_company(db, name: str, company_id: UUID | None = None, *, create=False):
    normalized = normalize_company(name)
    if not normalized:
        raise HTTPException(422, "Company name must contain letters or numbers")
    if company_id:
        company = get_record(db, Company, company_id)
        if company.normalized_name != normalized:
            raise HTTPException(422, "company_id does not match company_name")
        return company
    matches = db.scalars(select(Company).where(Company.normalized_name == normalized).limit(2)).all()
    if len(matches) > 1:
        raise HTTPException(
            409, "Company name is ambiguous. Search companies and supply the correct company_id."
        )
    if matches:
        return matches[0]
    if not create:
        return None
    company = Company(name=name, normalized_name=normalized)
    db.add(company)
    db.flush()
    return company


@router.get("/contacts/{record_id}", response_model=ContactRead)
def contact(record_id: UUID, db: DB):
    return get_record(db, Contact, record_id)


@router.post("/leads/intake", response_model=LeadIntakeResult, status_code=201)
def intake(data: LeadIntake, db: DB, actor: Actor = "hermes"):
    # Serialize name resolution for concurrent intake requests without introducing a unique name constraint.
    db.execute(text("SELECT pg_advisory_xact_lock(7240819202)"))
    company = resolve_company(db, data.company_name, data.company_id, create=True)
    duplicate = check_duplicate(
        db,
        DuplicateByCompany(
            company=data.company_name,
            **{
                key: value
                for key, value in data.model_dump().items()
                if key in DuplicateByCompany.model_fields
            },
        ),
        company,
    )
    values = data.model_dump(exclude={"company_name"}, exclude_none=True)
    values["company_id"] = company.id
    lead = save_lead(db, values, actor)
    return LeadIntakeResult(
        lead=LeadRead.model_validate(lead), company=CompanyRead.model_validate(company), duplicate=duplicate
    )


@router.post("/applications/check-duplicate-by-name", response_model=DuplicateResult)
def duplicate_by_name(data: DuplicateByCompany, db: DB):
    company = resolve_company(db, data.company, data.company_id)
    if company is None:
        # A transient lookup value, never persisted. URL matches can still cross company names.
        company = Company(name=data.company, normalized_name=normalize_company(data.company))
    return check_duplicate(db, data, company)


@router.post("/email-drafts/{record_id}/approve", response_model=DraftRead)
def approve_draft(record_id: UUID, data: DraftApproval, db: DB, actor: Actor = "hermes"):
    if actor != "user":
        raise HTTPException(403, "User confirmation is required for approval")
    draft = get_record(db, EmailDraft, record_id, lock=True)
    if draft.updated_at != data.expected_updated_at:
        raise HTTPException(
            409, "Draft changed since it was shown. Review the latest content before approving."
        )
    if draft.status != "reviewed":
        raise HTTPException(409, "Only a reviewed draft can be approved")
    application = get_record(db, Application, draft.application_id)
    event(
        db,
        "email_approved",
        actor,
        application=application,
        metadata={"draft_id": str(draft.id), "confirmation": "reviewed_content_version"},
    )
    return save_draft(db, {"status": "approved"}, actor, record_id)
