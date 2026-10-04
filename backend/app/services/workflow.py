"""Transactional mutations, approval boundaries and append-only event history."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import (
    Application,
    ApplicationEvent,
    ApplicationRules,
    Company,
    EmailDraft,
    JobLead,
    ResumeProfile,
)
from app.schemas.domain import ApplicationCreate, DuplicateCheck, Rules
from app.schemas.research import LeadResearch
from app.services.duplicates import check_duplicate
from app.services.normalization import normalize_company, normalize_text, normalize_url


def get_record(session: Session, model, record_id: UUID, *, lock: bool = False):
    query = select(model).where(model.id == record_id)
    if lock:
        query = query.with_for_update()
    result = session.scalar(query)
    if result is None:
        raise HTTPException(404, "Record not found")
    return result


def event(
    session: Session, event_type: str, actor: str, *, application=None, lead=None, metadata=None, run_id=None
):
    record = ApplicationEvent(
        application_id=application.id if application else None,
        job_lead_id=lead.id if lead else (application.job_lead_id if application else None),
        event_type=event_type,
        actor=actor,
        event_metadata=metadata or {},
        automation_run_id=run_id,
    )
    session.add(record)
    return record


def rules(session: Session) -> Rules:
    record = session.get(ApplicationRules, 1)
    return Rules.model_validate(record.settings) if record else Rules()


def enforce_rules(session: Session, company: Company, data: dict, actor: str, lead=None):
    settings = rules(session)
    if normalize_company(company.name) in {normalize_company(v) for v in settings.excluded_companies}:
        raise HTTPException(409, "Company is excluded by application rules")
    if normalize_text(data["role_title"]) in {normalize_text(v) for v in settings.excluded_roles}:
        raise HTTPException(409, "Role is excluded by application rules")
    if lead and settings.maximum_application_age_days and lead.posted_at:
        if lead.posted_at < datetime.now(timezone.utc) - timedelta(
            days=settings.maximum_application_age_days
        ):
            raise HTTPException(409, "Lead is older than the configured maximum application age")
    status = data.get("status", "discovered")
    if actor != "user" and status == "approved":
        raise HTTPException(409, "Only the user can approve an application")
    if actor != "user" and status in {"applied", "awaiting_response", "interview", "offer"}:
        raise HTTPException(
            409,
            "External submission outcomes must be recorded by the user until authenticated integrations exist",
        )


def application_values(session: Session, data: dict, actor: str, existing=None):
    company = get_record(session, Company, data["company_id"])
    lead = get_record(session, JobLead, data["job_lead_id"]) if data.get("job_lead_id") else None
    if lead:
        if lead.company_id != company.id:
            raise HTTPException(422, "Lead and application must belong to the same company")
        if existing is None:
            for name in (
                "job_url",
                "application_url",
                "source_url",
                "contact_name",
                "contact_email",
                "external_job_id",
            ):
                if data.get(name) is None:
                    data[name] = getattr(lead, name)
            if data.get("source") == "other":
                data["source"] = lead.source
    if not session.scalar(
        select(ResumeProfile.id).where(
            ResumeProfile.profile_type == data["resume_type"], ResumeProfile.active.is_(True)
        )
    ):
        raise HTTPException(422, "Selected resume profile is not active")
    identity_fields = {
        "company_id",
        "role_title",
        "job_lead_id",
        "job_url",
        "application_url",
        "source_url",
        "source",
        "external_job_id",
        "contact_email",
    }
    identity_changed = existing is None or any(data.get(k) != getattr(existing, k) for k in identity_fields)
    status_changed = existing is None or data.get("status") != existing.status
    if identity_changed or (
        status_changed
        and data.get("status")
        in {"approved", "prepared", "applied", "awaiting_response", "interview", "offer"}
    ):
        enforce_rules(session, company, data, actor, lead)
    if (
        actor != "user"
        and status_changed
        and data.get("status") == "prepared"
        and rules(session).user_approval_required
    ):
        approved = bool(lead and lead.status == "approved") or bool(
            existing and existing.status == "approved"
        )
        if not approved:
            raise HTTPException(409, "User approval is required before automated preparation")
    if existing and (
        data["resume_type"] != existing.resume_type
        or data["application_method"] != existing.application_method
    ):
        if session.scalar(
            select(EmailDraft.id)
            .where(EmailDraft.application_id == existing.id, EmailDraft.status != "cancelled")
            .limit(1)
        ):
            raise HTTPException(409, "Cancel outstanding drafts before changing resume or application method")
    duplicate_input = {name: data[name] for name in DuplicateCheck.model_fields if name in data}
    duplicate_input["exclude_application_id"] = existing.id if existing else None
    duplicate = check_duplicate(session, DuplicateCheck(**duplicate_input), company)
    override = data.pop("duplicate_override_reason", None)
    if identity_changed and duplicate.is_duplicate:
        if not (duplicate.requires_review and override and actor == "user"):
            raise HTTPException(409, {"code": "duplicate_application", **duplicate.model_dump(mode="json")})
    data.update(
        company_name=company.name,
        normalized_company_name=company.normalized_name,
        normalized_role_title=normalize_text(data["role_title"]),
    )
    data["job_url_key"] = normalize_url(data.get("job_url"))
    data["application_url_key"] = normalize_url(data.get("application_url"))
    data["source_url_key"] = normalize_url(data.get("source_url"))
    data["contact_email_key"] = str(data["contact_email"]).casefold() if data.get("contact_email") else None
    data["date_applied"] = data.pop("applied_at", None)
    if (
        data.get("status") in {"applied", "awaiting_response", "interview", "offer"}
        and data["date_applied"] is None
    ):
        data["date_applied"] = datetime.now(timezone.utc)
    return data, lead, override


def save_application(session: Session, data: dict, actor: str, record_id: UUID | None = None):
    # Serialize check-and-write to close concurrent duplicate races across API workers.
    # This is a deliberate small-system lock, released on commit/rollback.
    session.execute(text("SELECT pg_advisory_xact_lock(7240819201)"))
    existing = get_record(session, Application, record_id, lock=True) if record_id else None
    changes = sorted(data.keys())
    old_status = existing.status if existing else None
    if existing:
        full = {
            name: getattr(existing, name)
            for name in ApplicationCreate.model_fields
            if name not in {"applied_at", "duplicate_override_reason"}
        }
        full["applied_at"] = existing.date_applied
        full.update(data)
        data = full
    values, lead, override = application_values(session, data, actor, existing)
    if existing:
        for key, value in values.items():
            setattr(existing, key, value)
        record = existing
    else:
        record = Application(**values)
        session.add(record)
    session.flush()
    event_type = "application_created" if existing is None else "application_updated"
    event(
        session,
        event_type,
        actor,
        application=record,
        metadata={
            "changed_fields": changes,
            "previous_status": old_status,
            "status": record.status,
            **({"duplicate_override_reason": override} if override else {}),
        },
    )
    if lead and lead.status != "converted":
        lead.status = "converted"
        event(session, "lead_converted", actor, application=record, lead=lead)
    session.commit()
    session.refresh(record)
    return record


def save_lead(session: Session, data: dict, actor: str, record_id=None, *, commit: bool = True):
    if data.get("research") is not None:
        data["research"] = LeadResearch.model_validate(data["research"]).model_dump(mode="json")
    record = get_record(session, JobLead, record_id, lock=True) if record_id else None
    identity_changed = record is None or any(
        key in data and data[key] != getattr(record, key) for key in ("job_url", "application_url")
    )
    if data.get("status") == "converted":
        raise HTTPException(409, "Create an application to convert a lead")
    if record and record.status == "converted" and data.get("status", "converted") != "converted":
        raise HTTPException(409, "A converted lead retains its application history")
    if actor != "user" and data.get("status") == "approved":
        raise HTTPException(409, "Only the user can approve a lead")
    if record and "company_id" in data and data["company_id"] != record.company_id:
        if session.scalar(select(Application.id).where(Application.job_lead_id == record.id).limit(1)):
            raise HTTPException(409, "Cannot change company after lead conversion")
    company = get_record(session, Company, data.get("company_id", record.company_id if record else None))
    data["company_name"] = company.name
    if "role_title" in data:
        data["normalized_role_title"] = normalize_text(data["role_title"])
    if data.get("discovered_at") is None:
        data.pop("discovered_at", None)
    old_status = record.status if record else None
    if record:
        for key, value in data.items():
            setattr(record, key, value)
    else:
        record = JobLead(**data)
        session.add(record)
    if identity_changed:
        record.identity_urls = sorted(
            {normalize_url(url) for url in (record.job_url, record.application_url) if url}
        )
    session.flush()
    kind = (
        "lead_created"
        if record_id is None
        else ("lead_" + record.status if old_status != record.status else "lead_updated")
    )
    event(
        session, kind, actor, lead=record, metadata={"previous_status": old_status, "status": record.status}
    )
    if commit:
        session.commit()
        session.refresh(record)
    else:
        session.flush()
    return record


DRAFT_TRANSITIONS = {
    "draft": {"reviewed", "cancelled"},
    "reviewed": {"draft", "approved", "cancelled"},
    "approved": {"draft", "sent", "failed", "cancelled"},
    "failed": {"draft", "cancelled"},
    "sent": set(),
    "cancelled": {"draft"},
}


def save_draft(session: Session, data: dict, actor: str, record_id=None):
    draft = get_record(session, EmailDraft, record_id, lock=True) if record_id else None
    app_id = draft.application_id if draft else data["application_id"]
    application = get_record(session, Application, app_id, lock=True)
    if application.application_method != "email":
        raise HTTPException(409, "Email drafts require an email application")
    resume_type = data.get("resume_type", draft.resume_type if draft else None)
    if resume_type != application.resume_type:
        raise HTTPException(422, "Draft resume type must match the application")
    if draft:
        if draft.status == "sent":
            raise HTTPException(409, "Sent drafts are immutable; create a new draft")
        requested = data.get("status", draft.status)
        edited = any(k != "status" and getattr(draft, k) != v for k, v in data.items())
        if edited and draft.status in {"reviewed", "approved"}:
            if requested in {"approved", "sent"} and "status" in data:
                raise HTTPException(409, "Content changes must be reviewed again before approval")
            requested = "draft"
        if requested != draft.status and requested not in DRAFT_TRANSITIONS[draft.status]:
            raise HTTPException(409, f"Cannot transition draft from {draft.status} to {requested}")
        if requested in {"approved", "sent"} and requested != draft.status and actor != "user":
            raise HTTPException(409, "Only the user can approve or record sent email")
        for key, value in data.items():
            if key != "status":
                setattr(draft, key, value)
        draft.status = requested
        if requested == "draft":
            draft.approved_at = None
        elif requested == "approved" and draft.approved_at is None:
            draft.approved_at = datetime.now(timezone.utc)
        elif requested == "sent":
            draft.sent_at = datetime.now(timezone.utc)
            application.status = "applied"
            application.date_applied = application.date_applied or draft.sent_at
        kind = "email_sent_recorded" if requested == "sent" else "email_draft_updated"
    else:
        draft = EmailDraft(**data, generated_by=actor, status="draft")
        session.add(draft)
        kind = "email_drafted"
    session.flush()
    event(
        session,
        kind,
        actor,
        application=application,
        metadata={"draft_id": str(draft.id), "status": draft.status},
    )
    session.commit()
    session.refresh(draft)
    return draft
