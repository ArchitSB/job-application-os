"""Versioned, explainable ranking of supplied facts, without network or LLM calls."""

from datetime import datetime, timedelta, timezone

from app.schemas.lead_hunter import HunterContext, HunterParameters, MatchAssessment, ResearchJob
from app.services.normalization import normalize_company, normalize_text


def tokens(value: str) -> set[str]:
    return set(normalize_text(value).split())


def contains(text: str, phrase: str) -> bool:
    return f" {normalize_text(phrase)} " in f" {normalize_text(text)} "


def assess(
    job: ResearchJob, params: HunterParameters, context: HunterContext, *, now=None
) -> MatchAssessment:
    now = now or datetime.now(timezone.utc)
    facts = job.research
    warnings, excluded = [], []
    parts = {}
    title = normalize_text(job.role_title)
    description = job.description or job.raw_post_text or ""
    known = {normalize_text(s) for s in context.candidate.skills}
    required = {normalize_text(s) for s in facts.skills}
    overlap = known & required
    desired = {normalize_text(s) for s in params.technologies}
    # Preferences never become candidate skills. Report absent evidence rather than claim expertise.
    parts["skills"] = round(30 * len(overlap) / len(required)) if required else 0
    if not required:
        warnings.append("Required technologies unknown (0/30).")
    if desired and not desired & required:
        warnings.append("Preferred technologies are not evidenced in this result.")
    role_match = any(contains(title, role) for role in params.role_keywords)
    if not params.role_keywords:
        role_match = False
        warnings.append("No preferred roles configured.")
    parts["role"] = 25 if role_match else 0
    if not role_match:
        warnings.append("Title does not match the requested role phrases (0/25).")
    senior = bool(tokens(title) & {"senior", "staff", "principal", "lead", "director", "manager", "head"})
    if params.experience_level == "entry" and senior:
        excluded.append("Seniority exceeds entry-level preference.")
    if params.experience_level == "senior" and not senior:
        warnings.append("Senior scope is not established by the title.")
    years = facts.minimum_experience_years
    if years is not None and years > params.max_required_experience_years:
        excluded.append("Minimum experience exceeds requested search range.")
    actual_years = context.candidate.experience_years
    if years is not None and actual_years is not None and years > actual_years:
        excluded.append("Known candidate experience is below the stated minimum.")
    parts["experience"] = (
        15 if years == 0 or (years is not None and actual_years is not None and actual_years >= years) else 0
    )
    if not parts["experience"]:
        warnings.append(
            "Experience eligibility is unknown or unmet (0/15); search range is not candidate tenure."
        )
    wanted_locations = params.locations or context.rules.preferred_locations
    local_match = bool(job.location and any(contains(job.location, loc) for loc in wanted_locations))
    mode = facts.work_mode
    remote_allowed = (
        mode == "remote"
        and params.work_mode in {"any", "remote"}
        and context.rules.remote_preference != "onsite"
    )
    parts["location"] = 10 if local_match or remote_allowed else 0
    if params.work_mode != "any" and mode and params.work_mode != mode:
        excluded.append("Work mode does not match the request.")
    if params.work_mode != "any" and mode is None:
        excluded.append("Work mode unknown; cannot satisfy the requested mode.")
    if context.rules.remote_preference == "only" and mode and mode != "remote":
        excluded.append("Application rules require remote work.")
    if context.rules.remote_preference == "only" and mode is None:
        excluded.append("Remote-only rule requires explicit remote evidence.")
    if context.rules.remote_preference == "onsite" and mode and mode != "onsite":
        excluded.append("Application rules require onsite work.")
    if not mode:
        warnings.append("Work mode unknown; remote eligibility is unconfirmed.")
    if not parts["location"]:
        warnings.append("Location preference is unconfirmed (0/10).")
    employment = normalize_text(job.employment_type or "")
    parts["employment"] = (
        10
        if employment
        and (
            not params.employment_types or employment in {normalize_text(v) for v in params.employment_types}
        )
        else 0
    )
    if employment and params.employment_types and not parts["employment"]:
        excluded.append("Employment type does not match the request.")
    if not employment:
        warnings.append("Employment type unknown (0/10).")
    projects = [area for area in context.candidate.project_areas if contains(description, area)]
    parts["project_alignment"] = 10 if projects else 0
    if not projects:
        warnings.append("Description does not establish relevant project alignment (0/10).")
    if normalize_company(job.company_name) in {
        normalize_company(v) for v in context.rules.excluded_companies
    }:
        excluded.append("Company excluded by application rules.")
    if title in {normalize_text(v) for v in context.rules.excluded_roles}:
        excluded.append("Role excluded by application rules.")
    days = params.recency_days
    if context.rules.maximum_application_age_days:
        days = (
            min(days, context.rules.maximum_application_age_days)
            if days
            else context.rules.maximum_application_age_days
        )
    if job.posted_at:
        if job.posted_at > now + timedelta(minutes=5):
            excluded.append("Posting date is in the future.")
        elif days and job.posted_at < now - timedelta(days=days):
            excluded.append("Posting is outside the allowed recency window.")
    elif params.recency_days and not params.include_unknown_posted_at:
        excluded.append("Posting date unknown; cannot satisfy the requested recency window.")
    else:
        warnings.append("Posting date unknown; recency is not verified.")
    if params.salary_min is not None:
        if (
            facts.salary_max is None
            or facts.salary_currency != params.salary_currency
            or facts.salary_period != params.salary_period
        ):
            warnings.append("Salary unknown or currency/period differs; preference cannot be verified.")
        elif facts.salary_max < params.salary_min:
            excluded.append("Advertised salary ceiling is below the requested minimum.")
    # A recommendation needs role AND responsibility/skill evidence AND an active resume.
    technical_role = bool(tokens(title) & {"engineer", "developer", "sde"})
    technical_context = bool(overlap) and any(
        contains(description, a)
        for a in ("backend", "software", "systems", "full stack", "engineering", "ai", "llm")
    )
    product_role = contains(title, "product")
    product_context = any(
        contains(description, a)
        for a in ("product discovery", "stakeholder", "user research", "requirements")
    )
    recommendation = None
    if technical_role and technical_context and not product_role:
        recommendation = "technical"
    elif product_role and product_context and not technical_role:
        recommendation = "product"
    if recommendation not in context.active_resume_profiles:
        recommendation = None
    category = (
        "engineering" if recommendation == "technical" else "product" if recommendation == "product" else None
    )
    if (
        category
        and context.rules.preferred_role_categories
        and category not in context.rules.preferred_role_categories
    ):
        excluded.append("Role category is outside application preferences.")
    if recommendation is None:
        warnings.append(
            "Resume selection requires review; insufficient or mixed role/responsibility evidence."
        )
    score = sum(parts.values())
    if excluded:
        score = min(score, 39)
    band = next(
        label
        for minimum, label in [(90, "Excellent"), (75, "Strong"), (60, "Possible"), (40, "Weak"), (0, "Poor")]
        if score >= minimum
    )
    return MatchAssessment(
        score=score,
        category=band,
        breakdown=parts,
        warnings=warnings,
        ineligible_reasons=excluded,
        recommended_resume_type=recommendation,
    )
