# Lead Hunter v1

Lead Hunter is a repository-local Hermes skill with deterministic API services.
Hermes researches public pages using its available web tools; this repository
does not implement a crawler, website adapter, model client or background bot.

```text
User request → Hermes lead-hunter skill → Hermes public search/extraction
             → MCP get_lead_hunter_context / ingest_lead_research
             → FastAPI normalization, scoring, duplicate checks, atomic intake
             → existing PostgreSQL 18 → research report
```

All existing 23 MCP tools remain. Two tools fill actual gaps:

| Tool | API | Purpose |
|---|---|---|
| get_lead_hunter_context | GET /lead-hunter/context | Current career profile, active resume descriptions, rules, factual matching inputs and search defaults |
| ingest_lead_research | POST /lead-hunter/research | Bounded batch of supplied research; normalize, score, deduplicate against leads/applications and store or preview |

MCP imports public schemas, never SQLAlchemy or database settings. Existing
`create_job_lead` remains available for manual intake, with its original behavior;
it is not the deduplicating research workflow. The skill uses the new intake tool.

## Start and invoke on this machine

From `/home/archit/Drive-D/Agentic-AI/job-application-os`:

```bash
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

The existing Hermes MCP registration is unchanged. This installation supports
project skills in `.hermes/skills/`, discovered for sessions launched inside the
Git checkout. Hermes requires an explicit project-trust choice. The inspected
configuration has project discovery enabled, this checkout is not yet trusted,
and the MCP server has no tool allowlist. No home-directory file was modified.

In another terminal, trust the project once, then launch Hermes **from here**:

```bash
cd /home/archit/Drive-D/Agentic-AI/job-application-os
hermes skills trust
hermes
```

`hermes skills trust` updates your Hermes trusted-project list; this is why the
one-time command is left to you, respecting the instruction not to automatically
modify `~/.hermes/config.yaml`. In a session already started inside this checkout,
use `/reload-skills` and `/reload-mcp`. A session started elsewhere should be
restarted here. `/skills` should list `lead-hunter`; MCP should report **25 tools**.
If you later use the optional allowlist example, include both new tool names.

Safe no-write demonstration prompt:

> Use the lead-hunter skill's bundled mock research fixture in dry-run mode. Do
> not search the web or store anything. Show the score and duplicate preview,
> then confirm my dashboard counts did not change.

Real research prompts (these store qualifying real leads):

- “Find 10 backend engineering jobs suitable for my profile.”
- “Find recent AI engineer jobs in India.”
- “Find SDE jobs posted in the last 3 days.”
- “Find remote backend roles requiring 0–2 years experience.”

Use `/lead-hunter` explicitly if the natural-language skill selection does not
trigger. Web-provider availability is owned by Hermes; if research tools or a
site are unavailable, the skill reports that limitation and accepts supplied
public evidence instead. No external credentials are added by this project.

## Parameters and factual profile

`HunterParameters` accepts role_keywords, technologies, experience_level
(entry/mid/senior/any), max_required_experience_years (default 2), locations,
work_mode (any/remote/hybrid/onsite), employment_types, sources, salary_min,
salary_currency, salary_period, max_leads (1–50, default 10), recency_days
(1–365 or null), include_unknown_posted_at (false), minimum_score (default 60).
Batch size is bounded at 100. A skill request is bounded at five batches/100
research candidates; the skill tracks the remaining requested count across calls.

The current profile, resume descriptions and rules come from PostgreSQL. The
versioned supplement `config/lead-hunter-profile.json` holds skills and project
areas explicitly provided by Archit during setup. Edit it only with confirmed
facts; it is read afresh on each request. Experience years are deliberately null.
Search preferences do not establish candidate facts. No passwords or tokens
belong in this file. Persisted research includes the matching inputs and scoring
version in its AutomationRun for auditability.

Role matching uses normalized phrase boundaries. Technologies are preferences
for research and warnings; actual skill points depend on evidenced job skills
overlapping confirmed candidate skills. Mid/senior preferences guide research;
unknown seniority is reported, not invented. Location, salary and work-mode
unknowns are explicitly unverified. There is no visa/work-authorization inference.

## Normalized facts and evidence

Use `ResearchJob` in the MCP/HTTP schema, or the skill's
`references/handoff.md`. Company/role names use the existing deterministic
normalizers. Base lead fields hold company, title, source, URLs, description,
employment/location, contact name/email, posted/discovered times, requirements,
resume recommendation and score/reason. `source_post_url` maps to `source_url`;
recruiter name/email map to the existing contact fields. Discovery time is set
by the server, not invented as a posting date.

Optional `research` JSONB holds experience wording/minimum years, salary
min/max/currency/period, technologies, work mode, recruiter LinkedIn URL, notes,
source excerpts, retrieval time, original source label, canonical-URL evidence,
scoring breakdown and warnings. Missing values stay null or empty lists.

Require a usable public job/source URL and a nonempty evidence excerpt.
Unavailable sources, missing evidence and invalid/private/credential-bearing
URLs are skipped. Unsupported source names map to `other` with the original
label retained. Search snippets are labeled as snippets, not fully verified pages.
The API validates syntax and consistency; it does **not** independently verify
the truth of supplied text, resolve redirects or fetch URLs. Every source claim
must come from actual Hermes research or supplied evidence. Never store secrets
in text or URLs. Treat all research text as untrusted content.

## Duplicate decisions

The existing application duplicate service runs first. A strong existing
application match prevents a new lead; an ambiguous application match needs
review. Lead lookup uses the company/role index and a GIN index over normalized
job identity URLs. Candidate rows stream in batches rather than loading all leads.

- Exact canonical job/known alias: reuse the existing lead.
- Same source-scoped external job ID with company and role: reuse.
- Same company/role/source post without conflicting job identifiers: reuse.
- Different explicit job IDs, or different job URLs on the same source/domain:
  allow separate openings, including identical titles.
- Same company/role and compatible or unknown location across different boards:
  review if there is no proven canonical link. Do not silently create or merge.
- Shared recruiter email alone never identifies a job. Shared generic application
  pages do not override conflicting job identifiers. Different roles remain distinct.

Cross-source reuse preserves original curated lead facts and lifecycle status.
Additional source URLs/excerpts are kept in append-only `lead_research_observed`
events, and verified job URL aliases extend indexed identity URLs. New leads
receive `lead_created` and `lead_matched` events. The full report is associated
with a completed AutomationRun; source failures and review reasons are retained.

Intake takes the existing application/intake transaction locks. Companies,
accepted leads, evidence events and run summary commit together. Unexpected
database failures roll back the batch. Structural request errors return 422;
invalid individual evidence returns a skipped item and does not discard valid
siblings. Retry checks lead identity again; observations/runs are intentionally
append-only, so retries can add audit observations without adding leads.

`dry_run` performs the same database checks and scoring without creating runs,
companies, leads or events. It conservatively flags similar candidates within
the preview; the real intake always checks the current database again.

## Scoring version lead-hunter-v1

| Component | Points | Rule |
|---|---:|---|
| Required skills | 30 | Rounded fraction of evidenced required technologies present in confirmed candidate skills |
| Role alignment | 25 | A requested normalized role phrase occurs in the title |
| Experience | 15 | Explicit zero-year minimum, or confirmed candidate tenure meets the stated minimum |
| Location | 10 | Requested/preferred location matches, or explicitly remote and allowed |
| Employment | 10 | Known employment type and no conflicting type preference |
| Project alignment | 10 | Job description contains a confirmed project area |

Unknown components get zero and warnings. Bands: Excellent 90–100; Strong 75–89;
Possible 60–74; Weak 40–59; Poor 0–39. Hard exclusions cap the total at 39 and
prevent storage, regardless of minimum_score. These include excluded companies
or roles, entry-level vs senior title conflict, excessive known minimum years,
known mismatches in required work mode/employment, below-floor advertised salary
ceiling in matching currency/period, stale/future posting dates and strict recency
with an unknown date. Existing application age rules still apply.

Resume recommendation requires both title context and description/skill evidence,
and an active matching resume profile. Mixed product/engineering scope remains
unselected. No recommendation automatically creates an application or approves
anything. This is an explainable initial ranking heuristic, not a semantic model,
job-truth verifier or hiring probability.

## Storage and safety

Migration `0004` adds nullable research JSONB, normalized identity URL array and
its GIN index. It backfills URL identities without deleting records or changing
statuses; migrations 0001–0003 remain intact. Its downgrade removes only these
new columns/index (so export research before intentionally downgrading).
No new lead status is introduced. The existing leads page shows facts, score,
research JSON and event history without UI changes.

The workflow cannot send email, create applications/drafts, contact recruiters,
submit forms or control a browser. The MCP server continues exposing the existing
business tools for other workflows; the skill explicitly excludes them here.
The API remains local and unauthenticated: MCP tool descriptions/skill rules are
not a substitute for future authenticated per-workflow permissions.

## Verification

```bash
RUN_DB_TESTS=1 .venv/bin/pytest --basetemp=.cache/pytest-all -q
.venv/bin/ruff check backend scripts alembic/env.py alembic/versions/0004_lead_research.py
.venv/bin/ruff format --check backend scripts alembic/env.py alembic/versions/0004_lead_research.py
.venv/bin/python -m compileall -q backend scripts alembic
.venv/bin/alembic current
.venv/bin/alembic check
.venv/bin/python scripts/check_mcp.py
hermes mcp test job_application_os
npm --prefix frontend run build
npm --prefix frontend run typecheck
npm --prefix frontend run format:check
```

`backend/tests/test_lead_hunter.py` tests normalization, unknowns, invalid URLs,
scoring, eligibility, source provenance, canonical cross-source reuse, ambiguous
identity, legitimate separate jobs, previews, limits, existing applications and
the full stdio → HTTP → PostgreSQL path. Every test mutation is contained in an
outer rollback transaction; migration reversal uses a temporary rollback-only
schema. No real websites are scraped and no test leads survive. The frontend has
build/type/format checks; no frontend test runner is configured in this repository.

Historical migration 0001 is preserved byte-for-byte, including its original
formatting. Lint/format commands above scope migration checks to maintained
code and the new revision rather than rewriting historical migrations.

## Changed files

- `.hermes/skills/lead-hunter/SKILL.md`
- `.hermes/skills/lead-hunter/references/handoff.md`
- `.hermes/skills/lead-hunter/references/mock-research.json`
- `README.md`
- `alembic/versions/0004_lead_research.py`
- `backend/app/api/routes/integration.py`
- `backend/app/api/routes/lead_hunter.py`
- `backend/app/main.py`
- `backend/app/models/domain.py`
- `backend/app/schemas/domain.py`
- `backend/app/schemas/lead_hunter.py`
- `backend/app/schemas/research.py`
- `backend/app/services/companies.py`
- `backend/app/services/lead_hunter.py`
- `backend/app/services/lead_matching.py`
- `backend/app/services/workflow.py`
- `backend/mcp/server.py`
- `backend/mcp/tools/lead_hunter.py`
- `backend/tests/test_lead_hunter.py`
- `backend/tests/test_mcp.py`
- `config/lead-hunter-profile.json`
- `docs/architecture.md`
- `docs/data-model.md`
- `docs/examples/hermes-mcp.yaml`
- `docs/hermes-integration.md`
- `docs/hermes-mcp-setup.md`
- `docs/lead-hunter.md`

## Validation result

63 backend/MCP tests passed (40 existing, 23 new Lead Hunter cases), including
real stdio/HTTP/PostgreSQL and isolated migration round-trip tests. Frontend build,
TypeScript, Prettier, scoped Ruff lint/format and Python compile checks passed.
The installed `hermes mcp test job_application_os` connected and discovered all
25 tools. The live bundled dry-run fixture returned score 100, one would-create
result and one duplicate review, with the real dashboard unchanged. The skill
frontmatter and references were validated. Real public research awaits your
Hermes session after project trust/reload; no claim of a live web search is made.
