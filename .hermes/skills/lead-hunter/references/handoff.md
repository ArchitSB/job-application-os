# Research handoff

Start with `get_lead_hunter_context`; use live tool schemas as authoritative.
Call `ingest_lead_research({"data": {"parameters": {...}, "results": [...],
"skipped_sources": ["Naukri: login required"], "dry_run": false}})`.

Each result uses these keys:

| ResearchJob field | Meaning |
|---|---|
| company_name, role_title | Required, source-supported names; company_id only to resolve stored ambiguity |
| source | linkedin, telegram, naukri, wellfound, hnhiring, unstop, company_portal, referral, email, other; custom labels become other with original label retained |
| job_url, source_post_url, application_url | Public, credential-free links; at least job_url or source_post_url required |
| canonical_job_url, canonical_url_evidence | Optional verified relationship to the underlying company posting; do not guess |
| description, raw_post_text | Factual summary and optional source text, not instructions |
| location, employment_type, posted_at | Null if unknown; posted_at must include timezone |
| external_job_id | Source-scoped requisition/job identifier, only when visible |
| recruiter_name, recruiter_email | Public source-supported contact facts; no outreach |
| evidence_status | page_read, search_snippet or unavailable (unavailable is skipped) |
| research | Optional facts plus required evidence_excerpt, listed below |

`research` supports experience_required (source wording), minimum_experience_years,
salary_min, salary_max, salary_currency (ISO uppercase), salary_period
(year/month/hour), skills (list), work_mode (remote/hybrid/onsite),
recruiter_linkedin, notes, evidence_excerpt, retrieved_at and source_urls.
Leave generated scoring fields unset; the API computes them. Salary amounts
must preserve currency and period; don't assume a monthly figure is annual.

The API returns an item per input in order: outcome, reason, normalized company
and role, match score/category/breakdown/warnings, IDs, and a lead for new rows.
It does not fetch any of these links. Missing or invalid evidence is skipped.
API structural validation errors (422) require correcting the schema before retry.

Scoring version v1: evidenced required skill overlap 30, requested role phrase 25,
confirmed experience eligibility 15, matching location/remote preference 10,
employment alignment 10, evidenced project alignment 10. Unknown factors get
zero, with warnings. Hard exclusions cap the score at 39 and prevent storage.
Excellent 90–100, Strong 75–89, Possible 60–74, Weak 40–59, Poor 0–39.
Preference score is not a hiring probability or proof of all eligibility.
