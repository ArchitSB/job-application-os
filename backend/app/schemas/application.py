from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.models.application import ApplicationMethod, ApplicationStatus, ResumeType


class ApplicationCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    company_name: str = Field(min_length=1, max_length=255)
    normalized_company_name: str = Field(min_length=1, max_length=255)
    role_title: str = Field(min_length=1, max_length=255)
    normalized_role_title: str = Field(min_length=1, max_length=255)
    job_url: str | None = None
    source: str = Field(min_length=1, max_length=50)
    source_url: str | None = None
    application_method: ApplicationMethod
    resume_type: ResumeType
    contact_name: str | None = Field(default=None, max_length=255)
    contact_email: str | None = Field(default=None, max_length=320)
    date_found: AwareDatetime | None = None
    date_applied: AwareDatetime | None = None
    status: ApplicationStatus = ApplicationStatus.DISCOVERED
    email_subject: str | None = None
    email_body: str | None = None
    notes: str | None = None


class ApplicationRead(ApplicationCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: AwareDatetime
    updated_at: AwareDatetime
