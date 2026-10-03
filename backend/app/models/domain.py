"""Persistent job-management records; AI annotations are optional data."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.application import ResumeType, controlled_string


class Record:
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Company(Record, Base):
    __tablename__ = "companies"
    name: Mapped[str] = mapped_column(String(255))
    normalized_name: Mapped[str] = mapped_column(String(255), index=True)
    domain: Mapped[str | None] = mapped_column(String(255), index=True)
    website: Mapped[str | None] = mapped_column(Text)
    linkedin_url: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)


class JobLead(Record, Base):
    __tablename__ = "job_leads"
    __table_args__ = (
        CheckConstraint(
            "status IN ('discovered','reviewing','shortlisted','rejected','duplicate','approved','converted','expired')",
            name="lead_status",
        ),
        CheckConstraint("fit_score IS NULL OR (fit_score >= 0 AND fit_score <= 100)", name="fit_score_range"),
        Index("ix_job_leads_company_role", "company_id", "normalized_role_title"),
    )
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="RESTRICT"))
    company_name: Mapped[str] = mapped_column(String(255))
    role_title: Mapped[str] = mapped_column(String(255))
    normalized_role_title: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255))
    employment_type: Mapped[str | None] = mapped_column(String(100))
    source: Mapped[str] = mapped_column(String(50), index=True)
    source_url: Mapped[str | None] = mapped_column(Text)
    job_url: Mapped[str | None] = mapped_column(Text)
    application_url: Mapped[str | None] = mapped_column(Text)
    external_job_id: Mapped[str | None] = mapped_column(String(255), index=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    contact_name: Mapped[str | None] = mapped_column(String(255))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    raw_post_text: Mapped[str | None] = mapped_column(Text)
    requirements: Mapped[list[str] | None] = mapped_column(JSONB)
    salary_text: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(100))
    recommended_resume_type: Mapped[ResumeType | None] = mapped_column(
        controlled_string(ResumeType, "lead_resume_type"), index=True
    )
    fit_score: Mapped[float | None]
    fit_reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), server_default="discovered", index=True)


class Contact(Record, Base):
    __tablename__ = "contacts"
    company_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    linkedin_url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)


class ResumeProfile(Record, Base):
    __tablename__ = "resume_profiles"
    profile_type: Mapped[ResumeType] = mapped_column(
        controlled_string(ResumeType, "profile_type"), unique=True
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    drive_url: Mapped[str | None] = mapped_column(Text)
    local_path: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(server_default=text("true"))


class EmailDraft(Record, Base):
    __tablename__ = "email_drafts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','reviewed','approved','sent','failed','cancelled')", name="draft_status"
        ),
    )
    application_id: Mapped[UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="RESTRICT"), index=True
    )
    recipient_email: Mapped[str] = mapped_column(String(320))
    recipient_name: Mapped[str | None] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    resume_type: Mapped[ResumeType] = mapped_column(controlled_string(ResumeType, "draft_resume_type"))
    status: Mapped[str] = mapped_column(String(30), server_default="draft", index=True)
    generated_by: Mapped[str] = mapped_column(String(100), server_default="user")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AutomationRun(Record, Base):
    __tablename__ = "automation_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','running','completed','failed','cancelled')", name="run_status"
        ),
    )
    run_type: Mapped[str] = mapped_column(String(100))
    agent: Mapped[str] = mapped_column(String(100))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), server_default="pending", index=True)
    input_metadata: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    output_metadata: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    error_information: Mapped[str | None] = mapped_column(Text)


class ApplicationEvent(Base):
    __tablename__ = "application_events"
    __table_args__ = (
        CheckConstraint("application_id IS NOT NULL OR job_lead_id IS NOT NULL", name="event_subject"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    application_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("applications.id", ondelete="RESTRICT"), index=True
    )
    job_lead_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("job_leads.id", ondelete="RESTRICT"), index=True
    )
    automation_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("automation_runs.id", ondelete="RESTRICT"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(100))
    event_metadata: Mapped[dict] = mapped_column("metadata", JSONB, server_default=text("'{}'::jsonb"))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    actor: Mapped[str] = mapped_column(String(100))


class ApplicationRules(Base):
    __tablename__ = "application_rules"
    __table_args__ = (CheckConstraint("id = 1", name="rules_singleton"),)
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    settings: Mapped[dict] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserProfile(Base):
    __tablename__ = "user_profile"
    __table_args__ = (CheckConstraint("id = 1", name="profile_singleton"),)
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    full_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(320))
    phone: Mapped[str] = mapped_column(String(50))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(50))
    location: Mapped[str | None] = mapped_column(String(255))
    current_company: Mapped[str | None] = mapped_column(String(255))
    current_role: Mapped[str | None] = mapped_column(String(255))
    current_stipend: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    stipend_currency: Mapped[str] = mapped_column(String(3), server_default="INR")
    notice_period: Mapped[int | None]  # days
    portfolio_url: Mapped[str | None] = mapped_column(Text)
    github_url: Mapped[str | None] = mapped_column(Text)
    linkedin_url: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
