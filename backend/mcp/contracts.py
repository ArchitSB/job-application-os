"""MCP-specific inputs reuse only public Pydantic API contracts, never ORM models."""

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from app.schemas.domain import (
    ApplicationMethod,
    ApplicationRead,
    ApplicationStatus,
    Dashboard,
    EventCreate,
    EventRead,
    Input,
    LeadStatus,
    Name,
    ResumeRead,
    ResumeType,
)


class Search(Input):
    search: Annotated[str, Field(max_length=200)] | None = None
    status: str | None = None
    source: str | None = None
    resume_type: ResumeType | None = None
    date_from: AwareDatetime | None = None
    date_to: AwareDatetime | None = None
    page: Annotated[int, Field(ge=1)] = 1
    page_size: Annotated[int, Field(ge=1, le=100)] = 25

    @model_validator(mode="after")
    def date_order(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must be before date_to")
        return self


class LeadSearch(Search):
    status: LeadStatus | None = None


class ApplicationSearch(Search):
    status: ApplicationStatus | None = None
    application_method: ApplicationMethod | None = None


class DraftSearch(Search):
    status: Literal["draft", "reviewed", "approved", "sent", "failed", "cancelled"] | None = None


class ConvertLead(Input):
    lead_id: UUID
    application_method: ApplicationMethod
    resume_type: ResumeType
    notes: str | None = None


class StatusUpdate(Input):
    application_id: UUID
    status: ApplicationStatus
    applied_at: AwareDatetime | None = None
    notes: str | None = None


class EventInput(EventCreate):
    actor: Literal["user", "hermes", "system"] = "hermes"


class Confirmation(Input):
    approve: bool = Field(description="True only if you approve the exact operation shown.")


class ResumeList(Input):
    profiles: list[ResumeRead]


class BasicSearch(Input):
    search: Name | None = None
    page: Annotated[int, Field(ge=1)] = 1
    page_size: Annotated[int, Field(ge=1, le=100)] = 25


# MCP SDK builds output JSON schemas in validation mode. Strip ORM-only aliases
# while retaining the public API field names and types on the wire.
class ApplicationOutput(ApplicationRead):
    applied_at: AwareDatetime | None = Field()


class EventOutput(EventRead):
    metadata: dict[str, Any] = Field()


class DashboardOutput(Dashboard):
    recent_applications: list[ApplicationOutput]
