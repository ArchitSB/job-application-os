"""Optional source-supported lead facts. No inferred facts are required for a lead."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class LeadResearch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    experience_required: str | None = None
    minimum_experience_years: Annotated[float, Field(ge=0, le=60)] | None = None
    salary_min: Annotated[float, Field(ge=0)] | None = None
    salary_max: Annotated[float, Field(ge=0)] | None = None
    salary_currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] | None = None
    salary_period: Literal["year", "month", "hour"] | None = None
    skills: list[str] = Field(default_factory=list)
    work_mode: Literal["remote", "hybrid", "onsite"] | None = None
    recruiter_linkedin: str | None = None
    notes: str | None = None
    original_source: str | None = None
    evidence_status: Literal["page_read", "search_snippet", "unavailable"] | None = None
    canonical_job_url: str | None = None
    canonical_url_evidence: str | None = None
    evidence_excerpt: str | None = None
    retrieved_at: AwareDatetime | None = None
    source_urls: list[str] = Field(default_factory=list)
    scoring_version: str | None = None
    score_breakdown: dict[str, int] = Field(default_factory=dict)
    matching_warnings: list[str] = Field(default_factory=list)
