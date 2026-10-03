from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, Enum, FetchedValue, Index, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ApplicationMethod(StrEnum):
    EMAIL = "email"
    PORTAL = "portal"
    PLATFORM = "platform"
    OTHER = "other"


class ResumeType(StrEnum):
    TECHNICAL = "technical"
    PRODUCT = "product"


class ApplicationStatus(StrEnum):
    DISCOVERED = "discovered"
    SHORTLISTED = "shortlisted"
    APPROVED = "approved"
    PREPARED = "prepared"
    APPLIED = "applied"
    AWAITING_RESPONSE = "awaiting_response"
    INTERVIEW = "interview"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    OFFER = "offer"
    SKIPPED = "skipped"


def controlled_string(enum_class: type[StrEnum], name: str) -> Enum:
    return Enum(
        enum_class, name=name, native_enum=False, create_constraint=True,
        validate_strings=True, values_callable=lambda members: [member.value for member in members],
    )


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        Index("ix_applications_normalized_company_role", "normalized_company_name", "normalized_role_title"),
        Index("ix_applications_normalized_role_title", "normalized_role_title"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    company_name: Mapped[str] = mapped_column(String(255))
    normalized_company_name: Mapped[str] = mapped_column(String(255))
    role_title: Mapped[str] = mapped_column(String(255))
    normalized_role_title: Mapped[str] = mapped_column(String(255))
    job_url: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50))
    source_url: Mapped[str | None] = mapped_column(Text)
    application_method: Mapped[ApplicationMethod] = mapped_column(controlled_string(ApplicationMethod, "application_method"))
    resume_type: Mapped[ResumeType] = mapped_column(controlled_string(ResumeType, "resume_type"))
    contact_name: Mapped[str | None] = mapped_column(String(255))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    date_found: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    date_applied: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[ApplicationStatus] = mapped_column(
        controlled_string(ApplicationStatus, "application_status"), server_default="discovered",
    )
    email_subject: Mapped[str | None] = mapped_column(Text)
    email_body: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), server_onupdate=FetchedValue(),
    )
