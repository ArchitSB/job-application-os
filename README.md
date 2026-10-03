# Job Application OS

A local application-management platform for Archit Singh Baghel: capture leads,
review opportunities, choose a resume, prepare applications and email drafts,
and keep a reliable history. PostgreSQL is the source of truth. Future Hermes
operators will consume this API; no agents or external automation run today.

## Stack and layout

Python 3.12+, FastAPI, Pydantic Settings, SQLAlchemy 2.x, psycopg3, Alembic and
PostgreSQL 18. The UI uses React, TypeScript, Vite and Tailwind CSS.

```text
backend/app/       models, schemas, routes, deterministic services and configuration
backend/tests/     unit and transaction-isolated PostgreSQL API tests
frontend/          dashboard, lists, forms, settings and event history
alembic/           preserved 0001 and additive 0002/0003 migrations
scripts/           optional project role/database provisioning
resumes/           manually supplied PDFs (ignored by Git)
docs/              architecture, data model, workflows and Hermes contracts
```

## Existing PostgreSQL

This project uses **localhost:5432**, database/user **job_application_os**, on the
existing local PostgreSQL 18 server. On this machine PostgreSQL manages data under
`/var/lib/postgresql/18/main`. Other projects' databases and users are not touched.
There is no Docker or project-local PostgreSQL server. Old ignored `.local` files,
if present, are unused; never start the earlier cluster for this application.

`.env` already contains the working project connection. Keep it private and do
not replace it with the example. For a fresh checkout only:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.lock -e '.[dev]'
cp .env.example .env
chmod 600 .env
# Configure DATABASE_URL with your project role credentials.
```

For a machine where the project database does not exist, run
`python scripts/provision_database.py` after setting `.env`. It prompts for the
local PostgreSQL administrator password without saving it, creates only the
project role/database when absent, and never alters existing roles or databases.
The application itself uses the project login, never the superuser.

## Start the backend

From the repository root, with the existing PostgreSQL service running:

```bash
source .venv/bin/activate
alembic upgrade head
python -m app.services.seed
uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

Seeds create technical/product resume profiles from the supplied Drive links,
the owner's form profile, and default rules. Re-running does not overwrite edits.
No PDFs are downloaded. Configure local copies through `PATCH /resumes/{id}`
after manually placing them in `resumes/`.

## Start the frontend

Use a second terminal; Node.js 22 and npm are available in this environment:

```bash
cd frontend
npm ci
npm run dev
```

Open **http://127.0.0.1:5173**. Vite proxies `/api` to the backend on port 8000.
The UI includes Dashboard, Leads, Applications, Companies, Contacts, Email Drafts,
Resume Profiles and Profile & Rules. Start by creating a company, capturing a
lead, and selecting **Create application** in the lead details.

Keep both servers bound to loopback: authentication is intentionally absent.
`X-Actor` is an audit label, not a security credential. Current CORS origins are
configured through `CORS_ORIGINS` in Pydantic Settings.

## API

Interactive contracts: **http://127.0.0.1:8000/docs**; machine contract:
`/openapi.json`. Responses are schema-validated JSON.

| Resource | Operations |
|---|---|
| `/health`, `/health/db` | Liveness and database connectivity |
| `/companies`, `/companies/{id}` | List, create, retrieve |
| `/leads`, `/leads/{id}` | List, create, retrieve, patch |
| `/applications`, `/applications/{id}` | List, create, retrieve, patch |
| `/applications/check-duplicate` | Explainable duplicate check |
| `/applications/{id}/events` | Paginated history and append event |
| `/leads/{id}/events` | Lead history before/after conversion |
| `/contacts` | List and create |
| `/resumes`, `/resumes/{id}` | Read profiles; patch metadata/local PDF configuration |
| `/email-drafts`, `/email-drafts/{id}` | List, create, retrieve, patch/review/approve |
| `/dashboard/summary` | Aggregated totals, groupings and recent applications |
| `/profile`, `/rules` | Read and patch personal form values and application policy |
| `/automation-runs`, `/automation-runs/{id}` | Record future runs and outcomes; no execution |

List responses use `{items, total, page, page_size}`; page_size is capped at 100.
`/resumes` returns an array. Leads/applications support `search`, `status`, `source`,
`resume_type`, `date_from`, `date_to`, `page` and `page_size`. Application lists
also support `application_method`. Date inputs must include a timezone. Date
filters cover lead discovery or application creation, while dashboard weekly and
monthly metrics count actual applied timestamps in the India calendar.

Duplicate prevention runs on create and identity updates inside a serialized
transaction. Exact job identifiers block duplicates; ambiguous company/role
matches can be overridden by the user with an audited explanation. Different
explicit openings are allowed. Use job-specific URLs; generic recruiting pages
belong in source_url rather than being used as unique job identifiers.

Draft approval and sending are separate. Editing reviewed/approved content
requires another review. Setting a draft to sent only **records that the user
already sent it elsewhere**; no email is sent. Sent drafts and audit events cannot
be edited. All significant application/lead/draft transitions append events.

## Validation

```bash
source .venv/bin/activate
pytest --basetemp=.cache/pytest-tmp
RUN_DB_TESTS=1 pytest --basetemp=.cache/pytest-tmp
ruff check backend scripts alembic/env.py alembic/versions/0002_job_management_platform.py alembic/versions/0003_audit_and_reporting_indexes.py
python -m compileall -q backend scripts alembic
alembic current
alembic check
cd frontend
npm run build
npm run typecheck
npm run format:check
```

The default tests do not require a database; integration tests require migrations
and run against PostgreSQL using outer transactions rolled back after each test,
including API handlers that commit. No mock SQLite schema replaces PostgreSQL.
Tests cover duplicate cases, CRUD creation/update, conversion, approval/reset,
events, rules, profile validation, resume paths and dashboard queries.
The MCP test suite additionally verifies real stdio and HTTP calls with database
changes rolled back. Installing the MCP extra supplies the current test-client transport.

Alembic owns schema initialization. Migration `0001` is unchanged; `0002` adds the
platform and preserves/backfills legacy application data; `0003` adds reporting
indexes and append-only event enforcement. `0002` intentionally refuses a
schema-dropping downgrade; use reviewed forward migrations and normal backups.
Application startup never calls `create_all()`. Dependency versions are recorded
in `requirements-dev.lock` and `frontend/package-lock.json`.

## Scope and next integrations

Implemented: local records, explicit resume selection, deterministic duplicate
checks, application rules, manual drafting/approval, immutable audit events,
automation-run records and the working management UI.

Not implemented: authentication, Hermes installation/bots, model/DeepSeek calls,
Gmail sending, scraping/source adapters, browser/Cua automation, CAPTCHA bypass,
automatic applications or portal submissions. These remain separate future
integrations with credentials supplied through an external vault, human approval,
and authenticated API access. No Google credentials or Drive downloads are needed
for the current platform. There is no automatic email writer; the style guide
captures the distinct technical and product writing expectations.

Read [architecture](docs/architecture.md), [data model](docs/data-model.md),
[Hermes integration](docs/hermes-integration.md), [application workflow](docs/application-workflow.md)
and [email style](docs/email-style.md).


## Local Hermes MCP bridge

A separate stdio server now exposes 23 business tools through the existing API:
Hermes → MCP → FastAPI → PostgreSQL. No agent, scraper, email sender or browser
operator is implemented. The bridge does not access database credentials or ORM
models. Email approval requires user confirmation and never sends email.

For a fresh installation use `python -m pip install -r requirements-dev.lock -e '.[dev,mcp]'`.
With FastAPI running, verify it with `.venv/bin/python scripts/check_mcp.py`.
Register the server manually using [Hermes MCP setup](docs/hermes-mcp-setup.md)
and the [exact configuration](docs/examples/hermes-mcp.yaml). Your existing
`~/.hermes/config.yaml` is not modified automatically.
