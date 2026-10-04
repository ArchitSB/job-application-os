"""Typed research handoff: Hermes supplies evidence, the API evaluates and stores it."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from app.schemas.domain import Input, LeadRead, Name, Rules
from app.schemas.research import LeadResearch

Words = Annotated[list[Name], Field(max_length=50)]


class HunterParameters(Input):
    role_keywords: Words = Field(
        default_factory=lambda: [
            "Backend Engineer",
            "SDE",
            "Software Engineer",
            "AI Engineer",
            "Full Stack Engineer",
        ]
    )
    technologies: Words = Field(default_factory=list)
    experience_level: Literal["entry", "mid", "senior", "any"] = "entry"
    max_required_experience_years: Annotated[float, Field(ge=0, le=60)] = 2
    locations: Words = Field(
        default_factory=lambda: ["India", "Bengaluru", "Gurgaon", "Hyderabad", "Delhi NCR", "Pune"]
    )
    work_mode: Literal["any", "remote", "hybrid", "onsite"] = "any"
    employment_types: Words = Field(default_factory=list)
    sources: Words = Field(default_factory=list)
    salary_min: Annotated[float, Field(ge=0)] | None = None
    salary_currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] = "INR"
    salary_period: Literal["year", "month", "hour"] = "year"
    max_leads: Annotated[int, Field(ge=1, le=50)] = 10
    recency_days: Annotated[int, Field(ge=1, le=365)] | None = None
    include_unknown_posted_at: bool = False
    minimum_score: Annotated[int, Field(ge=0, le=100)] = 60


class CandidateFacts(Input):
    """User-provided facts, separate from job-search preferences. Unknown tenure stays unknown."""

    skills: Words
    project_areas: Words
    experience_years: Annotated[float, Field(ge=0, le=60)] | None = None
    provenance: str


class HunterContext(Input):
    full_name: str
    current_role: str | None
    current_company: str | None
    location: str | None
    candidate: CandidateFacts
    active_resume_profiles: dict[str, str | None]
    rules: Rules
    defaults: HunterParameters = Field(default_factory=HunterParameters)
    scoring_version: str = "lead-hunter-v1"


class ResearchJob(Input):
    company_name: Name
    role_title: Name
    company_id: UUID | None = None
    description: Annotated[str, Field(max_length=20000)] | None = None
    location: Name | None = None
    employment_type: Name | None = None
    source: Name = "other"
    # Validate URLs per item in the service so one unusable result does not discard the batch.
    source_post_url: Annotated[str, Field(max_length=4000)] | None = None
    job_url: Annotated[str, Field(max_length=4000)] | None = None
    application_url: Annotated[str, Field(max_length=4000)] | None = None
    canonical_job_url: Annotated[str, Field(max_length=4000)] | None = None
    canonical_url_evidence: Annotated[str, Field(max_length=2000)] | None = None
    external_job_id: Name | None = None
    posted_at: AwareDatetime | None = None
    recruiter_name: Name | None = None
    recruiter_email: Annotated[str, Field(max_length=320)] | None = None
    raw_post_text: Annotated[str, Field(max_length=30000)] | None = None
    evidence_status: Literal["page_read", "search_snippet", "unavailable"] = "unavailable"
    research: LeadResearch = Field(default_factory=LeadResearch)

    @model_validator(mode="after")
    def salary_order(self):
        if self.research.salary_min is not None and self.research.salary_max is not None:
            if self.research.salary_min > self.research.salary_max:
                raise ValueError("salary_min must not exceed salary_max")
        return self


class HunterBatch(Input):
    parameters: HunterParameters = Field(default_factory=HunterParameters)
    results: Annotated[list[ResearchJob], Field(min_length=1, max_length=100)]
    skipped_sources: Annotated[list[Name], Field(max_length=50)] = Field(default_factory=list)
    dry_run: bool = False


class MatchAssessment(Input):
    score: int
    category: Literal["Excellent", "Strong", "Possible", "Weak", "Poor"]
    breakdown: dict[str, int]
    warnings: list[str]
    ineligible_reasons: list[str]
    recommended_resume_type: Literal["technical", "product"] | None = None


class HunterItem(Input):
    index: int
    outcome: Literal["created", "existing", "review_required", "skipped", "would_create"]
    reason: str
    normalized_company: str | None = None
    normalized_role: str | None = None
    source_url: str | None = None
    job_url: str | None = None
    lead_id: UUID | None = None
    matched_application_id: UUID | None = None
    confidence: float = 0
    match: MatchAssessment | None = None
    lead: LeadRead | None = None


class HunterReport(Input):
    run_id: UUID | None = None
    dry_run: bool
    created: int
    existing: int
    review_required: int
    skipped: int
    items: list[HunterItem]
    skipped_sources: list[str]
    note: str = "Evidence supplied by Hermes; API did not fetch or independently verify websites. No applications, drafts, emails or submissions created."
