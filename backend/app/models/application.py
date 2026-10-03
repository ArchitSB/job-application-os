from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, Enum, FetchedValue, ForeignKey, Index, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ApplicationMethod, ApplicationStatus, ResumeType
from app.db.base import Base


def controlled_string(enum_class: type[StrEnum], name: str) -> Enum:
    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        Index("ix_applications_normalized_company_role", "normalized_company_name", "normalized_role_title"),
        Index("ix_applications_normalized_role_title", "normalized_role_title"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    company_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    job_lead_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("job_leads.id", ondelete="RESTRICT"), index=True
    )
    application_url: Mapped[str | None] = mapped_column(Text)
    external_job_id: Mapped[str | None] = mapped_column(String(255), index=True)
    external_application_id: Mapped[str | None] = mapped_column(String(255))
    job_url_key: Mapped[str | None] = mapped_column(Text, index=True)
    application_url_key: Mapped[str | None] = mapped_column(Text, index=True)
    source_url_key: Mapped[str | None] = mapped_column(Text, index=True)
    contact_email_key: Mapped[str | None] = mapped_column(String(320), index=True)
    company_name: Mapped[str] = mapped_column(String(255))
    normalized_company_name: Mapped[str] = mapped_column(String(255))
    role_title: Mapped[str] = mapped_column(String(255))
    normalized_role_title: Mapped[str] = mapped_column(String(255))
    job_url: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), index=True)
    source_url: Mapped[str | None] = mapped_column(Text)
    application_method: Mapped[ApplicationMethod] = mapped_column(
        controlled_string(ApplicationMethod, "application_method")
    )
    resume_type: Mapped[ResumeType] = mapped_column(controlled_string(ResumeType, "resume_type"), index=True)
    contact_name: Mapped[str | None] = mapped_column(String(255))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    date_found: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    date_applied: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[ApplicationStatus] = mapped_column(
        controlled_string(ApplicationStatus, "application_status"),
        server_default="discovered",
        index=True,
    )
    email_subject: Mapped[str | None] = mapped_column(Text)
    email_body: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        server_onupdate=FetchedValue(),
    )
