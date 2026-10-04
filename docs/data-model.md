# Data model

| Table | Purpose / relationships |
|---|---|
| `companies` | Non-unique normalized names, optional domain and public URLs; shared by leads, applications and contacts. |
| `job_leads` | Discovered opportunities with source, URLs, external job ID, raw post, description, requirements, dates and contact snapshot. Company FK required. Classification, recommended resume, fit score and reason are nullable. |
| `applications` | Deliberately selected applications, linked to company and optionally lead, with explicit method and resume. Retains legacy snapshots, source and `date_applied`; API exposes the latter as `applied_at`. |
| `application_events` | Append-only activity (database trigger rejects updates/deletes): application and/or lead FK, optional automation run FK, event type, JSONB metadata, server time and actor. Lead-only events are possible before conversion. |
| `contacts` | Recruiter/founder/hiring contacts; optional company FK. Email is not unique across applications. |
| `resume_profiles` | Seeded technical/product identities; descriptions, Drive links, optional repository-relative PDF path and active state. No credential storage or automatic downloads. |
| `email_drafts` | Recipient, content, chosen resume, draft/review/approval/sent timestamps and author. Application FK required. No sending behavior. |
| `automation_runs` | Future operator execution records, pending/running/completed/failed/cancelled status, start/end, JSONB input/output and sanitized error information. Recording a run does not execute an agent. |
| `application_rules` | Singleton JSONB policy validated by the Rules schema; editable through `/rules`. |
| `user_profile` | Typed singleton form information, public links, stipend in INR/month and notice period in days. No authentication credentials. |

UUID identities and `timestamptz` are used for domain records. Singleton settings
use integer ID 1 with database checks. Most mutable records have automatic
created/updated timestamps; events record occurrence time. FK deletion uses
RESTRICT to preserve history. There are no destructive delete endpoints.

## Controlled values

- Application method: email, portal, platform, referral, other.
- Resume: technical, product. Selection is explicit; a lead's recommendation does
  not silently choose the application's resume.
- Lead status: discovered, reviewing, shortlisted, rejected, duplicate, approved,
  converted, expired. Conversion is performed by creating an application, not by
  directly assigning `converted`.
- Application status: discovered, shortlisted, approved, prepared, applied,
  awaiting_response, interview, rejected, withdrawn, offer, skipped.
- Draft status: draft, reviewed, approved, sent, failed, cancelled.
- Source is an extensible lowercase identifier: linkedin, telegram, naukri,
  wellfound, hnhiring, unstop, company_portal, referral, email, other or a future
  adapter identifier. It is not a provider-specific enum.

## Queries and policy

Index coverage includes normalized company/role, canonical URL keys, external
job IDs, FKs, source/status and timestamps. Lead and application lists use SQL
filters, counts, LIMIT/OFFSET pagination, and stable timestamp/UUID ordering.
Date ranges are inclusive and timezone-aware: discovered_at for leads, created_at
for application lists. Dashboard week/month totals use actual applied dates in
the Asia/Kolkata calendar, starting the week on Monday; future dates are excluded.

Excluded companies/roles and maximum lead age are enforced for application
creation and relevant progression. Preferred categories/locations and remote
preference are matching inputs, not destructive filters. `user_approval_required`
controls whether Hermes may mark an unapproved application prepared. Email and
portal approval flags are persisted for future adapters; current endpoints keep
manual approval/recording mandatory even if those flags are disabled. No flag can
enable sending or submission in this phase.

Seeds use conflict-do-nothing inserts, so rerunning them does not reset edited
personal information, rules or resume profiles. Local PDFs may be placed manually
in `resumes/` and registered with `PATCH /resumes/{id}`; absolute paths, traversal,
non-PDF paths and missing files are rejected. PDF contents are not served by this
API. Files, `.env`, caches and node_modules are excluded from Git.

## Lead research (0004)

`job_leads.research` is nullable typed JSONB for experience, salary, skills, work
mode, recruiter LinkedIn, notes, provenance and deterministic score breakdown.
`identity_urls` is a non-unique GIN-indexed text array of normalized job URLs and
verified aliases; old rows are backfilled. Additional sightings live in
append-only lead events, associated with `AutomationRun` research reports. No
new statuses, application columns or uniqueness constraints were introduced.
