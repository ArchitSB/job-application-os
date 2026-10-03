from difflib import SequenceMatcher

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Application, Company
from app.schemas.domain import DuplicateCheck, DuplicateResult
from app.services.normalization import normalize_text, normalize_url


def check_duplicate(session: Session, data: DuplicateCheck, company: Company) -> DuplicateResult:
    role = normalize_text(data.role_title)
    urls = {normalize_url(v) for v in (data.job_url, data.application_url) if v}
    source_url = normalize_url(data.source_url)
    conditions = [Application.normalized_company_name == company.normalized_name]
    if urls:
        conditions += [Application.job_url_key.in_(urls), Application.application_url_key.in_(urls)]
    if data.job_lead_id:
        conditions.append(Application.job_lead_id == data.job_lead_id)
    # Iterate server-side candidate batches instead of loading the database into memory.
    query = select(Application).where(or_(*conditions)).order_by(Application.created_at, Application.id)
    if data.exclude_application_id:
        query = query.where(Application.id != data.exclude_application_id)
    best = DuplicateResult(is_duplicate=False, confidence=0, reason="No matching application found.")
    for existing in session.scalars(query.execution_options(yield_per=100)):
        same_company = existing.normalized_company_name == company.normalized_name
        same_role = existing.normalized_role_title == role
        old_urls = {u for u in (existing.job_url_key, existing.application_url_key) if u}
        same_lead = data.job_lead_id is not None and existing.job_lead_id == data.job_lead_id
        same_external = (
            same_company
            and data.external_job_id is not None
            and data.source == existing.source
            and data.external_job_id == existing.external_job_id
        )
        if urls & old_urls or same_lead or same_external:
            signal = (
                "same_job_lead"
                if same_lead
                else ("same_external_job_id" if same_external else "same_job_url")
            )
            return DuplicateResult(
                is_duplicate=True,
                confidence=1,
                matched_application_id=existing.id,
                reason="An application already exists for this job identifier.",
                signals=[signal],
            )
        # Different explicit job identifiers allow legitimate repeat titles at the same company.
        distinct = bool(
            (urls and old_urls and not urls & old_urls)
            or (
                data.external_job_id
                and existing.external_job_id
                and data.source == existing.source
                and data.external_job_id != existing.external_job_id
            )
        )
        same_email = bool(
            data.contact_email and existing.contact_email_key == str(data.contact_email).casefold()
        )
        same_source = bool(source_url and source_url == existing.source_url_key)
        if same_company and same_role and not distinct:
            signals = ["normalized_company", "normalized_role"]
            if same_email:
                signals.append("contact_email")
            if same_source:
                signals.append("source_url")
            confidence = 0.85 + (0.05 if same_email else 0) + (0.05 if same_source else 0)
            if confidence > best.confidence:
                best = DuplicateResult(
                    is_duplicate=True,
                    confidence=confidence,
                    matched_application_id=existing.id,
                    reason="Same company and role without distinct job identifiers; review required.",
                    signals=signals,
                    requires_review=True,
                )
        elif same_company and not distinct and not best.is_duplicate:
            similarity = SequenceMatcher(None, role, existing.normalized_role_title).ratio()
            if similarity >= 0.72 and similarity * 0.5 > best.confidence:
                best = DuplicateResult(
                    is_duplicate=False,
                    confidence=round(similarity * 0.5, 2),
                    matched_application_id=existing.id,
                    reason="Similar role title; different roles are allowed.",
                    signals=["role_similarity"],
                    requires_review=True,
                )
    return best
