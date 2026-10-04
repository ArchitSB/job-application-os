"""Conservative company resolution shared by intake workflows."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from app.models import Company
from app.services.normalization import normalize_company
from app.services.workflow import get_record


def resolve_company(db, name: str, company_id: UUID | None = None, *, create=False):
    normalized = normalize_company(name)
    if not normalized:
        raise HTTPException(422, "Company name must contain letters or numbers")
    if company_id:
        company = get_record(db, Company, company_id)
        if company.normalized_name != normalized:
            raise HTTPException(422, "company_id does not match company_name")
        return company
    matches = db.scalars(select(Company).where(Company.normalized_name == normalized).limit(2)).all()
    if len(matches) > 1:
        raise HTTPException(
            409, "Company name is ambiguous. Search companies and supply the correct company_id."
        )
    if matches:
        return matches[0]
    if not create:
        return None
    company = Company(name=name, normalized_name=normalized)
    db.add(company)
    db.flush()
    return company
