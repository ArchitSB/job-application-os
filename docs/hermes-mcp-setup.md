# Hermes MCP setup for this installation

## Implemented boundary

```text
Local Hermes Agent
  → stdio MCP server (backend.mcp.server)
    → HTTP FastAPI at 127.0.0.1:8000
      → existing PostgreSQL 18 at localhost:5432
```

The bridge uses the official **mcp==2.0.0** SDK (`MCPServer`), matching the SDK
installed with your Hermes. It uses neither the removed `mcp.server.fastmcp`
module nor the separate FastMCP framework. It is isolated from FastAPI and does
not start a database or web server.

The installed launcher is `/home/archit/.local/bin/hermes`, pointing to
`/home/archit/.hermes/hermes-agent/.hermes/bin/hermes`. Compatibility/configuration
was checked against these local installation sources:

- `~/.hermes/hermes-agent/website/docs/reference/mcp-config-reference.md`
- `~/.hermes/hermes-agent/website/docs/guides/use-mcp-with-hermes.md`
- `~/.hermes/hermes-agent/tools/mcp_tool_transport.py` (command/args/env/cwd and protocol negotiation)
- `~/.hermes/hermes-agent/tools/mcp_tool_common.py` (timeout configuration)
- Installed `mcp-2.0.0.dist-info/METADATA` and Hermes `pyproject.toml`.

No Hermes files, secrets, installation or configuration were modified.

## 1. Backend prerequisite

The bridge is already installed in this repository's virtual environment. Start
or restart FastAPI with the new API helper routes:

```bash
cd /home/archit/Drive-D/Agentic-AI/job-application-os
source .venv/bin/activate
uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

On a fresh checkout, install `python -m pip install -r requirements-dev.lock -e '.[dev,mcp]'`
and follow the existing README's database/migration setup. The original bridge required no migration; Lead Hunter adds migration `0004`.
Run `.venv/bin/alembic upgrade head` before starting the updated backend.

Run a read-only protocol check:

```bash
.venv/bin/python scripts/check_mcp.py
```

It launches a real stdio subprocess, discovers 25 tools, reads resume metadata and
the dashboard, then shuts down the child. It does not create application records.

## 2. Register with Hermes (manual)

Merge the `job_application_os` entry from [the complete configuration](examples/hermes-mcp.yaml)
into `~/.hermes/config.yaml` under its existing `mcp_servers` mapping. Preserve all
other settings and servers. The essential configuration is:

```yaml
mcp_servers:
  job_application_os:
    command: /home/archit/Drive-D/Agentic-AI/job-application-os/.venv/bin/python
    args: ["-m", "backend.mcp.server"]
    cwd: /home/archit/Drive-D/Agentic-AI/job-application-os
    env:
      JOB_OS_API_URL: http://127.0.0.1:8000
    enabled: true
    protocol: auto
    connect_timeout: 20
    timeout: 180
    supports_parallel_tool_calls: false
    trust: full
    elicitation:
      enabled: true
      timeout: 120
    tools:
      resources: false
      prompts: false
```

The complete configuration additionally allowlists the exact 25 tools, preventing
future server additions from being enabled silently. `trust: full` is appropriate
for this repository-owned bridge: ordinary record mutations do not ask for extra
Hermes transport approval. The email approval tool still requires its own human
confirmation. Set `trust: untrusted` if you additionally want Hermes to ask before
every write tool.

There are **no database passwords, API keys or OAuth tokens** in this entry.
`JOB_OS_API_URL` is the bridge's only configuration variable. It is read directly
from the environment, not `.env`; the app's DATABASE_URL is never read by the bridge.
The backend remains responsible for the database connection.

## 3. Load and verify

After saving the config, start a fresh Hermes session or use `/reload-mcp` in the
existing Hermes session. The installed CLI also supports:

```bash
hermes mcp test job_application_os
```

Hermes launches the subprocess itself. Do not run a second persistent MCP server
manually; stdio has no listening port. Directly running
`.venv/bin/python -m backend.mcp.server` waits for protocol messages, so it is not
an interactive shell. stdout is reserved for MCP; diagnostics use stderr.

Try: “Use Job Application OS to list my resume profiles and show my dashboard.”
Then inspect tool results before creating records. Hermes may prefix registered
tool names; the table below uses the server-native names.

## Tools and input shapes

Tools use typed Pydantic inputs and typed structured outputs. The MCP schema is
authoritative. Create/check tools take a `data` object; searches take `filters`;
patches take the UUID plus `changes`. Retrieval takes the resource UUID.

| Tool | Purpose / side effects |
|---|---|
| `get_lead_hunter_context` | Read current career profile, active resume descriptions, rules and confirmed matching facts; no credentials. |
| `ingest_lead_research` | Accept a `data` batch of source-supported results; normalize, score, deduplicate against leads/applications and store leads with audit history. dry_run writes nothing. No applications or drafts created. |
| `create_job_lead` | Capture a lead with `company_name`, role, source, description, location, URLs, posted date and contacts. Resolves/creates a company through the API in the lead transaction; returns lead, company and duplicate information. Optional company_id disambiguates existing names. |
| `search_job_leads` | Read paginated leads with text/status/source/resume/date filters. |
| `get_job_lead` | Retrieve one lead by lead_id. |
| `update_job_lead` | Patch stored facts or classification; API approval rules apply. |
| `convert_lead_to_application` | Supply lead_id, method and explicit resume_type. API performs duplicate-checked conversion and writes events atomically. |
| `check_application_duplicate` | Supply company name, role_title, URLs, contact email, source and external_job_id as available; returns is_duplicate/confidence/reason/matched_application_id plus signals. Uses the existing deterministic service. |
| `create_application` | Create a selected application's local record; no external submission. Requires company_id. |
| `get_application` | Retrieve one application. |
| `search_applications` | Read paginated application history with filters. |
| `update_application` | Patch allowed fields, with duplicate checks on identity changes and auditing. |
| `update_application_status` | Request an API-allowed transition; never submits an application. User-only approval/submission outcomes remain blocked for Hermes. |
| `record_application_event` | Append an observation and JSON metadata. Defaults to hermes; user/system labels require confirmation. Event names such as email_sent and portal_submitted are records, not actions. |
| `get_application_events` | Read immutable history using application_id and a pagination object. |
| `create_email_draft` | Save unsent content for review; no approval or sending. |
| `get_email_draft` | Read one draft. |
| `search_email_drafts` | Filter/paginate stored drafts. |
| `approve_email_draft` | Request user confirmation of the exact reviewed content, then approve that version only. Does not send email. |
| `list_resume_profiles` | Return technical/product metadata and public Drive links. No file reads/downloads. |
| `get_dashboard_summary` | Read existing totals, periods and groupings. |
| `search_companies` | Search/paginate stored companies. |
| `get_company` | Retrieve by company_id. |
| `search_contacts` | Search/paginate stored contacts. |
| `get_contact` | Retrieve by contact_id. |

Example native tool inputs:

```json
{"data":{"company_name":"Example Company","role_title":"Backend Engineer","source":"other","description":"User-supplied job description"}}
```

```json
{"data":{"company":"Example Company","role_title":"Backend Engineer","job_url":"https://example.com/jobs/123"}}
```

```json
{"filters":{"search":"Backend","status":"shortlisted","page":1,"page_size":25}}
```

Sources remain generic. Dates require timezone offsets; page_size is limited to
100. Resume choice is always explicit. No tool exposes a generic HTTP request,
SQL, shell, browser, Gmail, scraping or credential operation.

## Approval details

1. Save a draft through the tool or UI.
2. Review the draft in the existing UI and mark it reviewed.
3. Hermes calls `approve_email_draft` with draft_id.
4. Hermes's MCP elicitation surface shows recipient, subject, full body and resume.
5. Explicitly accept with `approve: true`; decline/cancel/unsupported confirmation
   produces no approval. There is no input parameter that lets the LLM claim consent.
6. The API locks the row and compares updated_at before using the existing draft
   approval service. A changed/re-reviewed draft must be shown again.
7. The API records email_approved and the existing draft-update event. sent_at is
   still null; the application is not marked applied.

Elicitation trusts the local MCP client to actually ask a human. This is not a
remote authentication mechanism. API access is local and unauthenticated as
before; authenticated identity and scoped service credentials remain future work.
Do not let another integration automatically synthesize elicitation responses.

## Troubleshooting and tests

- API unavailable: start the backend; verify `/health/db`. The stdio server can
  start/discover tools while the API is down; business calls return useful errors.
- 409 duplicate/policy conflict: inspect the API's reason. Do not let the model
  invent a duplicate override. User-only approvals remain in the UI or elicitation.
- Ambiguous company: use search_companies, inspect IDs/domains, and supply company_id.
- Approval unavailable: enable elicitation or approve in the local UI.
- Timeouts on writes: the outcome may be uncertain. Read existing records before
  retrying; the bridge never automatically retries writes.
- Loopback-only origin: external addresses, embedded credentials and redirects
  are refused; HTTP proxy environment variables are ignored.

```bash
RUN_DB_TESTS=1 .venv/bin/pytest --basetemp=.cache/pytest-mcp -q
.venv/bin/ruff check backend scripts alembic/env.py
.venv/bin/python -m compileall -q backend scripts
.venv/bin/alembic check
npm --prefix frontend run build
```

MCP tests use real stdio child processes and a real local HTTP API with all
PostgreSQL changes inside an outer rollback. They cover discovery, every exposed
tool, normalized intake, duplicates, approval acceptance/refusal/cancellation,
missing consent support, stale content, no ORM imports, fixed local origin and
no arbitrary/external-action tool surface.

## Lead Hunter workflow

The original 23 tools remain; `get_lead_hunter_context` reads current matching inputs,
and `ingest_lead_research` performs deterministic lead matching/deduplication/intake.
See [Lead Hunter setup, parameters and examples](lead-hunter.md). The repository
skill is `.hermes/skills/lead-hunter/SKILL.md`; launch Hermes from this checkout and
trust project skills once with `hermes skills trust`, then `/reload-skills` and
`/reload-mcp`. No existing Hermes configuration was changed automatically.
