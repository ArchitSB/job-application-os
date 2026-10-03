"""Public API contracts. Unknown fields are rejected rather than silently discarded."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Any, ClassVar, Generic, Literal, TypeVar, get_args
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    create_model,
    model_validator,
)

from app.core.enums import ApplicationMethod, ApplicationStatus, ResumeType


def http_url(value: str) -> str:
    HttpUrl(value)
    return value


URL = Annotated[str, AfterValidator(http_url), Field(max_length=4000)]
Name = Annotated[str, Field(min_length=1, max_length=255)]
Source = Annotated[str, Field(min_length=1, max_length=50, pattern=r"^[a-z][a-z0-9_]*$")]
LeadStatus = Literal[
    "discovered", "reviewing", "shortlisted", "rejected", "duplicate", "approved", "converted", "expired"
]
DraftStatus = Literal["draft", "reviewed", "approved", "sent", "failed", "cancelled"]


class Input(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, from_attributes=True, populate_by_name=True
    )


class Record(Input):
    id: UUID
    created_at: AwareDatetime
    updated_at: AwareDatetime


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class CompanyCreate(Input):
    name: Name
    domain: Annotated[str, Field(max_length=255, pattern=r"^[A-Za-z0-9.-]+$")] | None = None
    website: URL | None = None
    linkedin_url: URL | None = None
    notes: str | None = None


class CompanyRead(CompanyCreate, Record):
    normalized_name: str


class LeadCreate(Input):
    company_id: UUID
    role_title: Name
    description: str | None = None
    location: Name | None = None
    employment_type: Annotated[str, Field(max_length=100)] | None = None
    source: Source = "other"
    source_url: URL | None = None
    job_url: URL | None = None
    application_url: URL | None = None
    external_job_id: Name | None = None
    posted_at: AwareDatetime | None = None
    discovered_at: AwareDatetime | None = None
    contact_name: Name | None = None
    contact_email: EmailStr | None = None
    raw_post_text: str | None = None
    requirements: list[str] | None = None
    salary_text: str | None = None
    category: Annotated[str, Field(max_length=100)] | None = None
    recommended_resume_type: ResumeType | None = None
    fit_score: Annotated[float, Field(ge=0, le=100)] | None = None
    fit_reason: str | None = None
    status: LeadStatus = "discovered"


class LeadRead(LeadCreate, Record):
    company_name: str
    normalized_role_title: str
    discovered_at: AwareDatetime


class DuplicateCheck(Input):
    company_id: UUID
    role_title: Name
    job_lead_id: UUID | None = None
    job_url: URL | None = None
    application_url: URL | None = None
    source_url: URL | None = None
    source: Source = "other"
    contact_email: EmailStr | None = None
    external_job_id: Name | None = None
    exclude_application_id: UUID | None = None


class DuplicateResult(Input):
    is_duplicate: bool
    confidence: float
    matched_application_id: UUID | None = None
    reason: str
    signals: list[str] = Field(default_factory=list)
    requires_review: bool = False


class ApplicationCreate(Input):
    company_id: UUID
    job_lead_id: UUID | None = None
    role_title: Name
    application_method: ApplicationMethod
    resume_type: ResumeType
    status: ApplicationStatus = ApplicationStatus.DISCOVERED
    applied_at: AwareDatetime | None = None
    contact_name: Name | None = None
    contact_email: EmailStr | None = None
    job_url: URL | None = None
    application_url: URL | None = None
    source: Source = "other"
    source_url: URL | None = None
    external_job_id: Name | None = None
    external_application_id: Name | None = None
    email_subject: str | None = None
    email_body: str | None = None
    notes: str | None = None
    duplicate_override_reason: Annotated[str, Field(min_length=10, max_length=2000)] | None = None


class ApplicationRead(Record):
    company_id: UUID | None
    company_name: str
    normalized_company_name: str
    job_lead_id: UUID | None
    role_title: str
    normalized_role_title: str
    application_method: ApplicationMethod
    resume_type: ResumeType
    status: ApplicationStatus
    applied_at: AwareDatetime | None = Field(validation_alias="date_applied")
    contact_name: str | None
    contact_email: str | None
    job_url: str | None
    application_url: str | None
    source: str
    source_url: str | None
    external_job_id: str | None
    external_application_id: str | None
    email_subject: str | None
    email_body: str | None
    notes: str | None


class ContactCreate(Input):
    company_id: UUID | None = None
    name: Name
    email: EmailStr | None = None
    linkedin_url: URL | None = None
    title: Name | None = None
    notes: str | None = None


class ContactRead(ContactCreate, Record):
    pass


class ResumeRead(Record):
    profile_type: ResumeType
    name: str
    description: str | None
    drive_url: str | None
    local_path: str | None
    active: bool


class DraftCreate(Input):
    application_id: UUID
    recipient_email: EmailStr
    recipient_name: Name | None = None
    subject: Annotated[str, Field(min_length=1, max_length=1000)]
    body: Annotated[str, Field(min_length=1, max_length=50000)]
    resume_type: ResumeType


class DraftRead(DraftCreate, Record):
    status: DraftStatus
    generated_by: str
    approved_at: AwareDatetime | None
    sent_at: AwareDatetime | None


class EventCreate(Input):
    event_type: Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")]
    metadata: dict[str, Any] = Field(default_factory=dict)
    automation_run_id: UUID | None = None


class EventRead(Input):
    id: UUID
    application_id: UUID | None
    job_lead_id: UUID | None
    automation_run_id: UUID | None
    event_type: str
    metadata: dict[str, Any] = Field(validation_alias="event_metadata")
    actor: str
    occurred_at: AwareDatetime


class Rules(Input):
    maximum_application_age_days: Annotated[int, Field(ge=1, le=3650)] | None = 60
    preferred_role_categories: list[str] = Field(default_factory=lambda: ["engineering", "product"])
    excluded_companies: list[str] = Field(default_factory=list)
    excluded_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=lambda: ["Bengaluru", "Remote"])
    remote_preference: Literal["any", "preferred", "only", "onsite"] = "preferred"
    user_approval_required: bool = True
    email_sending_requires_approval: bool = True
    portal_submission_requires_approval: bool = True


class Profile(Input):
    full_name: Name
    email: EmailStr
    phone: Annotated[str, Field(min_length=1, max_length=50)]
    date_of_birth: date | None = None
    gender: Annotated[str, Field(max_length=50)] | None = None
    location: Name | None = None
    current_company: Name | None = None
    current_role: Name | None = None
    current_stipend: Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)] | None = None
    stipend_currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] = "INR"
    notice_period: Annotated[int, Field(ge=0, le=365)] | None = None
    portfolio_url: URL | None = None
    github_url: URL | None = None
    linkedin_url: URL | None = None


class RunCreate(Input):
    run_type: Annotated[str, Field(min_length=1, max_length=100)]
    agent: Annotated[str, Field(min_length=1, max_length=100)]
    input_metadata: dict[str, Any] = Field(default_factory=dict)


class RunPatch(Input):
    status: Literal["running", "completed", "failed", "cancelled"]
    output_metadata: dict[str, Any] = Field(default_factory=dict)
    error_information: str | None = None


class RunRead(RunCreate, Record):
    status: str
    started_at: AwareDatetime | None
    completed_at: AwareDatetime | None
    output_metadata: dict[str, Any]
    error_information: str | None


class PartialInput(Input):
    non_nullable: ClassVar[set[str]] = set()

    @model_validator(mode="after")
    def reject_null(self):
        for name in self.model_fields_set & self.non_nullable:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


def partial(name: str, schema: type[Input], exclude: set[str] | None = None):
    """PATCH preserves explicit null for nullable fields and rejects it otherwise."""
    from copy import deepcopy

    fields = {}
    non_nullable = set()
    for key, field in schema.model_fields.items():
        if key in (exclude or set()):
            continue
        info = deepcopy(field)
        info.default = None
        info.default_factory = None
        fields[key] = (field.annotation | None, info)
        if type(None) not in get_args(field.annotation):
            non_nullable.add(key)
    result = create_model(name, __base__=PartialInput, **fields)
    result.non_nullable = non_nullable
    return result


LeadPatch = partial("LeadPatch", LeadCreate)
ApplicationPatch = partial("ApplicationPatch", ApplicationCreate)
ProfilePatch = partial("ProfilePatch", Profile)
RulesPatch = partial("RulesPatch", Rules)


class DraftPatch(PartialInput):
    non_nullable = {"recipient_email", "subject", "body", "resume_type", "status"}
    recipient_email: EmailStr | None = None
    recipient_name: Name | None = None
    subject: Annotated[str, Field(min_length=1, max_length=1000)] | None = None
    body: Annotated[str, Field(min_length=1, max_length=50000)] | None = None
    resume_type: ResumeType | None = None
    status: DraftStatus | None = None


class Dashboard(Input):
    total_leads: int
    new_leads: int
    shortlisted_leads: int
    total_applications: int
    applications_this_week: int
    applications_this_month: int
    awaiting_responses: int
    interviews: int
    rejections: int
    offers: int
    applications_by_resume_type: dict[str, int]
    applications_by_source: dict[str, int]
    applications_by_method: dict[str, int]
    recent_applications: list[ApplicationRead]


class ResumePatch(PartialInput):
    non_nullable = {"name", "active"}
    name: Name | None = None
    description: str | None = None
    drive_url: URL | None = None
    local_path: str | None = None
    active: bool | None = None
