# Hermes integration

A working local MCP bridge is now available in `backend/mcp/`. It exposes the
25 tools documented in [Hermes MCP setup](hermes-mcp-setup.md), using the SDK and
stdio configuration supported by the existing local Hermes installation. Hermes
configuration is already working; this project has not changed it. Lead Hunter
is the first implemented skill; application/portal agents remain future work.

The implemented path is **Hermes → stdio MCP → FastAPI → PostgreSQL**. Hermes has
no direct database access through this bridge and does not import internal ORM
models. All duplicate decisions, conversions and persistence remain in existing
API services. Lead Hunter is implemented as a project skill; the other operator roles below remain future work.

The API runs at `http://127.0.0.1:8000`; OpenAPI is available at `/openapi.json` and
interactive documentation at `/docs`. JSON requests and responses use explicit
Pydantic schemas. UUIDs are strings, dates include time zones. `X-Actor: hermes`
labels events; `user` is the default. This header is self-asserted, not proof of
identity. Do not expose the current unauthenticated API to the network.

## Authentication to add before integration

Introduce a scoped, revocable service token or OAuth client identity stored in an
external vault/environment, never in this database or an LLM prompt. Derive the
actor from that authenticated identity. Restrict Hermes to appropriate endpoints;
reserve user approval for an authenticated human. Add request/run correlation and
idempotency keys before performing externally visible actions. External Gmail,
portal and model credentials belong to the integration's vault layer.

## Operators and endpoints

| Operator | Contract |
|---|---|
| Lead Hunter (implemented) | Hermes public research → get_lead_hunter_context / ingest_lead_research → FastAPI matching, lead/application deduplication and storage. [Setup and workflow](lead-hunter.md). No scraping or application creation. |
| Job Matcher | GET `/leads/{id}`, `/resumes`, `/rules`. Read the full description and responsibilities. PATCH lead category, recommended_resume_type, fit_score/fit_reason and status. Null means unassessed. Do not choose solely from title keywords or invent requirements. |
| Application Agent | Check duplicates, explicitly choose a resume, POST `/applications`, then POST `/email-drafts` for email applications. Follow the writing guide below. Await user review and approval. |
| Portal Agent | Read `/profile`, `/resumes`, application and lead. Prepare a form outside this service in a future integration; obtain human approval before submission and record outcomes/events. No browser tooling is implemented here. |

The integration chain is User → Hermes → Job Application OS MCP → FastAPI → PostgreSQL.
The database is authoritative when memory and records disagree.

## Safe sequence

1. Read `/rules` and the target lead. Check age, exclusions and preferences.
2. POST `/applications/check-duplicate` with company_id, role_title, job_url,
   application_url, source_url, source, external_job_id, contact_email and lead ID
   where available. Read confidence, reason, signals and matched_application_id.
3. Stop on a strong match. Ask the user to review an ambiguous match. Only the
   user may provide a duplicate_override_reason; never invent a reason.
4. POST `/applications` with explicit company_id, method and resume_type. Writes
   repeat the check under a transaction lock; a prior check is not a reservation.
5. User approval is recorded with an application/lead status change. Prepare
   work through the API, respecting persisted rules.
6. POST an email draft. It is unsent regardless of how plausible its body looks.
   Request review and approval. No endpoint here sends an email or submits a form.
7. After a human performs the external action, the user records the draft as
   sent, or PATCHes the application to applied with applied_at and any external
   application ID. The system appends state-change events transactionally.
8. POST `/applications/{id}/events` for evidence such as recruiter_replied,
   interview_scheduled, portal_started or portal_submitted. Manual event entries
   do not themselves cause status changes or external actions.

`POST /automation-runs` creates a pending execution record. PATCH it to running,
then completed/failed/cancelled. Events can include automation_run_id. Store
sanitized evidence and outcomes, never credentials or browser session data.

## Error and retry contract

Lists return `{items, total, page, page_size}` with a maximum page_size of 100;
`GET /resumes` returns the two profile records. Use filters and pagination.

- 422: invalid fields, unknown keys, invalid FK pairing or resume mismatch.
- 404: referenced record not found.
- 409: duplicate candidate, invalid workflow transition, policy conflict or a
  database constraint. Duplicate errors include explainable match details.
- 503: database unavailable. Retry with backoff; don't assume a mutation failed
  before checking persisted state. Generic event POSTs are not idempotent yet.

Use the live OpenAPI schemas instead of guessing required fields. The local
header-based actor convention must be replaced before autonomous integrations
are permitted. See [application workflow](application-workflow.md) and
[email style](email-style.md).


## Current MCP usage

Use the named tools in the [complete catalog](hermes-mcp-setup.md#tools-and-input-shapes).
`create_job_lead` captures supplied information and may create its missing company;
it does not discover a job. `check_application_duplicate` calls the deterministic
service even when the company name is new. `convert_lead_to_application` invokes
existing application creation, so it atomically changes lead state and writes
history. Application writes still use actor hermes and cannot bypass user-only
transitions.

`approve_email_draft` approves only reviewed content after a client-mediated user
confirmation. A version-checked API helper rejects edits made while confirmation
was pending. It does not mark the application applied or populate sent_at. Use
existing UI review before approval. The only additional side effect is an
email_approved audit event, alongside the existing draft-update event.

The bridge has no sending, scraping, browser, arbitrary SQL/shell, authentication
credential or filesystem-access tools. It has no resource or prompt endpoints
that expose local files. Keep the API on loopback until authentication is added.
