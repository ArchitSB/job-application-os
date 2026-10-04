"""Atomic research intake. All identity, eligibility and persistence decisions live here."""

from datetime import datetime, timezone
from ipaddress import ip_address
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import HTTPException
from pydantic import HttpUrl, ValidationError
from sqlalchemy import and_, or_, select, text
from sqlalchemy.orm import Session

from app.core.config import PROJECT_ROOT
from app.models import AutomationRun, Company, JobLead, ResumeProfile, UserProfile
from app.schemas.domain import LeadCreate, LeadRead
from app.schemas.integration import DuplicateByCompany
from app.schemas.lead_hunter import (
    CandidateFacts,
    HunterBatch,
    HunterContext,
    HunterItem,
    HunterReport,
    ResearchJob,
)
from app.services.companies import resolve_company
from app.services.duplicates import check_duplicate
from app.services.lead_matching import assess
from app.services.normalization import normalize_company, normalize_text, normalize_url
from app.services.workflow import event, rules, save_lead

SOURCES = {
    "linkedin",
    "telegram",
    "naukri",
    "wellfound",
    "hnhiring",
    "unstop",
    "company_portal",
    "referral",
    "email",
    "other",
}


class ResearchEvidenceError(ValueError):
    """Safe, constant error messages suitable for the per-result report."""


def get_context(db: Session) -> HunterContext:
    profile = db.get(UserProfile, 1)
    if profile is None:
        raise HTTPException(409, "Initialize the application profile before researching jobs")
    facts = CandidateFacts.model_validate_json((PROJECT_ROOT / "config/lead-hunter-profile.json").read_text())
    return HunterContext(
        full_name=profile.full_name,
        current_role=profile.current_role,
        current_company=profile.current_company,
        location=profile.location,
        candidate=facts,
        active_resume_profiles={
            r.profile_type.value: r.description
            for r in db.scalars(select(ResumeProfile).where(ResumeProfile.active.is_(True)))
        },
        rules=rules(db),
    )


def public_url(value: str) -> str:
    """Syntax only; never fetch URLs. Disallow credentials, local targets and obvious secret parameters."""
    parsed = HttpUrl(value)
    parts = urlsplit(str(parsed))
    host = parts.hostname or ""
    if (
        parts.username
        or parts.password
        or "." not in host
        or host.endswith((".local", ".localhost", ".internal"))
    ):
        raise ResearchEvidenceError("Use a public, credential-free source URL")
    try:
        address = ip_address(host)
    except ValueError:
        address = None
    if address and not address.is_global:
        raise ResearchEvidenceError("Local/private URLs are not public research evidence")
    from urllib.parse import parse_qsl

    if any(
        k.casefold() in {"token", "access_token", "api_key", "password", "key", "auth", "signature"}
        for k, _ in parse_qsl(parts.query)
    ):
        raise ResearchEvidenceError("Source URL must not contain credentials or access tokens")
    return value.strip()


def normalize_result(job: ResearchJob, now: datetime) -> ResearchJob:
    result = job.model_copy(deep=True)
    if not normalize_company(job.company_name) or not normalize_text(job.role_title):
        raise ResearchEvidenceError("Company and role must contain letters or numbers")
    if job.evidence_status == "unavailable":
        raise ResearchEvidenceError("Source inaccessible or not researched; skipped")
    if not job.research.evidence_excerpt or not job.research.evidence_excerpt.strip():
        raise ResearchEvidenceError(
            "Supply an actual source excerpt; an unsupported job claim cannot be stored"
        )
    if not (job.source_post_url or job.job_url):
        raise ResearchEvidenceError("A source post or job URL is required for research provenance")
    if job.canonical_job_url and not job.canonical_url_evidence:
        raise ResearchEvidenceError(
            "Canonical URL requires evidence of the source-to-career-page relationship"
        )
    for key in ("source_post_url", "job_url", "application_url", "canonical_job_url"):
        value = getattr(result, key)
        if value:
            setattr(result, key, public_url(value))
    if result.research.recruiter_linkedin:
        result.research.recruiter_linkedin = public_url(result.research.recruiter_linkedin)
    result.research.source_urls = list(
        dict.fromkeys(
            public_url(v) for v in [*(result.research.source_urls or []), job.source_post_url or job.job_url]
        )
    )
    source = job.source.casefold().replace(" ", "_")
    result.source = source if source in SOURCES else "other"
    result.research.original_source = job.source
    result.research.evidence_status = job.evidence_status
    result.research.canonical_job_url = job.canonical_job_url
    result.research.canonical_url_evidence = job.canonical_url_evidence
    result.research.skills = list(dict.fromkeys(s.strip() for s in result.research.skills if s.strip()))
    result.research.retrieved_at = result.research.retrieved_at or now
    if result.research.retrieved_at > now:
        raise ResearchEvidenceError("retrieved_at cannot be in the future")
    return result


def identity_urls(job: ResearchJob) -> set[str]:
    return {normalize_url(u) for u in (job.job_url, job.application_url, job.canonical_job_url) if u}


def lead_duplicate(db: Session, job: ResearchJob):
    """Return (record, confidence, needs_review, reason); ambiguous cross-board matches never merge."""
    urls = identity_urls(job)
    company = normalize_company(job.company_name)
    role = normalize_text(job.role_title)
    conditions = [and_(Company.normalized_name == company, JobLead.normalized_role_title == role)]
    if urls:
        conditions.append(JobLead.identity_urls.overlap(sorted(urls)))
    query = select(JobLead).join(Company).where(or_(*conditions)).order_by(JobLead.created_at, JobLead.id)
    ambiguous = None
    for lead in db.scalars(query.execution_options(yield_per=100)):
        same_company = normalize_company(lead.company_name) == company
        same_role = lead.normalized_role_title == role
        old_urls = set(lead.identity_urls)
        same_source = (
            job.source == lead.source
            and job.research.original_source.casefold()
            == ((lead.research or {}).get("original_source") or lead.source).casefold()
        )
        if same_company and same_role and job.external_job_id and lead.external_job_id and same_source:
            if job.external_job_id == lead.external_job_id:
                return lead, 1.0, False, "Same source-scoped external job ID"
            continue
        new_jobs = {normalize_url(u) for u in (job.job_url, job.canonical_job_url) if u}
        old_jobs = old_urls - (
            {normalize_url(lead.application_url)} if lead.application_url != lead.job_url else set()
        )
        if new_jobs & old_jobs:
            return lead, 1.0, False, "Same canonical job URL"
        distinct_jobs = bool(new_jobs and old_jobs and not new_jobs & old_jobs)
        if urls & old_urls and same_company and same_role and not distinct_jobs:
            return lead, 1.0, False, "Same application URL without conflicting job identifiers"
        if same_company and same_role:
            location_conflict = bool(
                job.location
                and lead.location
                and normalize_text(job.location) != normalize_text(lead.location)
            )
            source_match = bool(
                job.source_post_url and normalize_url(job.source_post_url) == normalize_url(lead.source_url)
            )
            if source_match and not distinct_jobs and not location_conflict:
                return (
                    lead,
                    0.95,
                    False,
                    "Same company, role and source post without conflicting job identifiers",
                )
            # Different IDs on the SAME board/domain indicate distinct openings. Different boards do not.
            if distinct_jobs:
                hosts = {urlsplit(u).hostname for u in new_jobs}
                old_hosts = {urlsplit(u).hostname for u in old_jobs}
                if same_source and hosts & old_hosts:
                    continue
            ambiguous = (
                lead,
                0.8,
                True,
                "Same company/role; location differs and job identity needs review"
                if location_conflict
                else "Same company/role with compatible or unknown location; canonical job identity needs review",
            )
    return ambiguous or (None, 0.0, False, "No matching lead")


def process_research(db: Session, batch: HunterBatch, actor: str) -> HunterReport:
    now = datetime.now(timezone.utc)
    context = get_context(db)
    # Same lock order as application/intake paths. Concurrent hunter requests cannot check then insert twice.
    db.execute(text("SELECT pg_advisory_xact_lock(7240819201)"))
    db.execute(text("SELECT pg_advisory_xact_lock(7240819202)"))
    run = None
    if not batch.dry_run:
        run = AutomationRun(
            run_type="lead_hunter",
            agent=actor,
            started_at=now,
            status="running",
            input_metadata={
                "parameters": batch.parameters.model_dump(mode="json"),
                "result_count": len(batch.results),
                "scoring_version": context.scoring_version,
                "candidate_facts": context.candidate.model_dump(mode="json"),
                "rules": context.rules.model_dump(mode="json"),
                "active_resume_profiles": context.active_resume_profiles,
            },
        )
        db.add(run)
        db.flush()
    items = []
    new_count = 0
    # Dry-run keeps virtual accepted identities so duplicates within the preview are also caught.
    preview_urls = set()
    preview_roles = set()
    for index, raw in enumerate(batch.results):
        item = HunterItem(index=index, outcome="skipped", reason="")
        items.append(item)
        write_started = False
        try:
            job = normalize_result(raw, now)
            item.normalized_company = normalize_company(job.company_name)
            item.normalized_role = normalize_text(job.role_title)
            item.source_url = job.source_post_url or job.job_url
            item.job_url = job.canonical_job_url or job.job_url
            match = assess(job, batch.parameters, context, now=now)
            item.match = match
            if job.source == "other" and job.source != raw.source.casefold():
                match.warnings.append(
                    "Unsupported source label preserved as original_source; classified as other."
                )
            if job.evidence_status == "search_snippet":
                match.warnings.append("Search snippet evidence only; full job page not verified.")
            # Build the existing schema before writes (validates emails, lengths and source-supported facts).
            values = dict(
                role_title=job.role_title,
                description=job.description,
                location=job.location,
                employment_type=job.employment_type,
                source=job.source,
                source_url=job.source_post_url or job.job_url,
                job_url=job.canonical_job_url or job.job_url,
                application_url=job.application_url,
                external_job_id=job.external_job_id,
                posted_at=job.posted_at,
                discovered_at=now,
                contact_name=job.recruiter_name,
                contact_email=job.recruiter_email,
                raw_post_text=job.raw_post_text,
                requirements=job.research.skills or None,
                fit_score=match.score,
                recommended_resume_type=match.recommended_resume_type,
                fit_reason=f"{match.category}: {match.breakdown}; " + "; ".join(match.warnings),
                status="discovered",
            )
            company = resolve_company(db, job.company_name, job.company_id)
            LeadCreate(company_id=company.id if company else UUID(int=0), **values)
            duplicate = check_duplicate(
                db,
                DuplicateByCompany(
                    company=job.company_name,
                    company_id=company.id if company else None,
                    role_title=job.role_title,
                    job_url=values["job_url"],
                    application_url=job.application_url,
                    source_url=values["source_url"],
                    source=job.source,
                    external_job_id=job.external_job_id,
                    contact_email=job.recruiter_email,
                ),
                company or Company(name=job.company_name, normalized_name=item.normalized_company),
            )
            if duplicate.is_duplicate:
                item.outcome = "review_required" if duplicate.requires_review else "existing"
                item.reason, item.confidence = duplicate.reason, duplicate.confidence
                item.matched_application_id = duplicate.matched_application_id
                continue
            lead, confidence, review, reason = lead_duplicate(db, job)
            if lead:
                item.outcome = "review_required" if review else "existing"
                item.lead_id, item.confidence, item.reason = lead.id, confidence, reason
                if not batch.dry_run and not review:
                    write_started = True
                    lead.identity_urls = sorted(set(lead.identity_urls) | identity_urls(job))
                    # Preserve curated facts/status; append evidence as an audit observation.
                    event(
                        db,
                        "lead_research_observed",
                        actor,
                        lead=lead,
                        run_id=run.id,
                        metadata={
                            "source": job.source,
                            "source_urls": job.research.source_urls,
                            "evidence_excerpt": job.research.evidence_excerpt,
                            "evidence_status": job.evidence_status,
                        },
                    )
                continue
            key = (item.normalized_company, item.normalized_role, normalize_text(job.location or ""))
            if batch.dry_run and (identity_urls(job) & preview_urls or key in preview_roles):
                item.outcome, item.reason = (
                    "review_required",
                    "Possible duplicate within this preview; storage performs a fresh database check",
                )
                continue
            if match.ineligible_reasons:
                item.reason = "; ".join(match.ineligible_reasons)
                continue
            allowed_sources = {s.casefold().replace(" ", "_") for s in batch.parameters.sources}
            if (
                allowed_sources
                and job.source not in allowed_sources
                and raw.source.casefold().replace(" ", "_") not in allowed_sources
            ):
                item.reason = "Source not requested"
                continue
            if match.score < batch.parameters.minimum_score:
                item.reason = "Below minimum match score"
                continue
            if new_count >= batch.parameters.max_leads:
                item.reason = "Requested new-lead limit reached"
                continue
            if batch.dry_run:
                item.outcome, item.reason = "would_create", "Eligible for storage; preview writes nothing"
                preview_urls.update(identity_urls(job))
                preview_roles.add(key)
            else:
                write_started = True
                company = company or resolve_company(db, job.company_name, create=True)
                job.research.scoring_version = context.scoring_version
                job.research.score_breakdown = match.breakdown
                job.research.matching_warnings = match.warnings
                values.update(company_id=company.id, research=job.research.model_dump(mode="json"))
                lead = save_lead(db, values, actor, commit=False)
                # Keep the board URL as an alias when a supported canonical URL was supplied.
                lead.identity_urls = sorted(set(lead.identity_urls) | identity_urls(job))
                event(
                    db,
                    "lead_matched",
                    actor,
                    lead=lead,
                    run_id=run.id,
                    metadata={"match": match.model_dump(mode="json"), "evidence_status": job.evidence_status},
                )
                db.flush()
                item.lead_id, item.lead = lead.id, LeadRead.model_validate(lead)
                item.outcome, item.reason = "created", "New researched lead stored; no application created"
            new_count += 1
        except ResearchEvidenceError as error:
            if write_started:
                raise
            item.reason = str(error)
        except (ValueError, ValidationError):
            if write_started:
                raise
            # Do not echo raw values (URLs or source text could contain credentials).
            item.reason = "Invalid or missing source evidence, URL, company/role or contact data; correct the supplied result"
        except HTTPException as error:
            if write_started:
                raise
            if error.status_code not in {404, 409, 422}:
                raise
            item.outcome, item.reason = "review_required", str(error.detail)
    report = HunterReport(
        run_id=run.id if run else None,
        dry_run=batch.dry_run,
        created=sum(i.outcome == "created" for i in items),
        existing=sum(i.outcome == "existing" for i in items),
        review_required=sum(i.outcome == "review_required" for i in items),
        skipped=sum(i.outcome == "skipped" for i in items),
        items=items,
        skipped_sources=batch.skipped_sources,
    )
    if run:
        run.status, run.completed_at = "completed", datetime.now(timezone.utc)
        run.output_metadata = report.model_dump(mode="json", exclude={"items"})
        run.output_metadata["items"] = [i.model_dump(mode="json", exclude={"lead"}) for i in items]
        db.commit()
    return report
