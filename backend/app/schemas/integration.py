"""Small API conveniences used by integrations, without persistence dependencies."""

from uuid import UUID

from pydantic import AwareDatetime

from app.schemas.domain import CompanyRead, DuplicateCheck, DuplicateResult, Input, LeadCreate, LeadRead, Name


class LeadIntake(LeadCreate):
    company_id: UUID | None = None
    company_name: Name


class DuplicateByCompany(DuplicateCheck):
    company_id: UUID | None = None
    company: Name


class LeadIntakeResult(Input):
    lead: LeadRead
    company: CompanyRead
    duplicate: DuplicateResult


class DraftApproval(Input):
    expected_updated_at: AwareDatetime
