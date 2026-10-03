# Job Application OS

A personal job application system whose PostgreSQL database is the deterministic
source of truth. This first phase provides the database schema, migrations,
configuration, and FastAPI health endpoints.

## Architecture

- `backend/app/core`: Pydantic Settings; environment variables override the root `.env`.
- `backend/app/db`: SQLAlchemy 2.x declarative base, pooled engine, request sessions.
- `backend/app/models` and `schemas`: application storage and Pydantic contracts.
- `backend/app/api/routes` and `services`: health endpoints and database probe.
- `alembic`: versioned schema changes, including timestamp maintenance.
- `backend/tests`: isolated unit tests and opt-in PostgreSQL integration tests.

Python 3.12+ and locally installed PostgreSQL **18** are required. No Docker is used.
Run the following commands from the project root.

## Install and configure

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.lock -e '.[dev]'
cp .env.example .env  # first setup only; do not overwrite an existing .env
chmod 600 .env
```

Set `DATABASE_URL` in `.env` for your PostgreSQL database. It must use the
`postgresql+psycopg` driver. `APP_NAME` and `ENVIRONMENT` are optional.
Only `.env.example` belongs in version control; `.env` is ignored. The example
credentials are for private local development only.

## PostgreSQL setup

This project uses your existing local PostgreSQL 18 server on **localhost:5432**,
with storage managed by that server (`/var/lib/postgresql/18/main` on this machine).
Its database and login role are both named `job_application_os`, separate from
other projects' databases and roles. The application connects with its own role,
not the PostgreSQL superuser.

The project database, role, and `.env` are already configured. For a fresh setup,
configure `.env` and run:

```bash
python scripts/provision_database.py
```

The script prompts for the `postgres` administrator password without saving it.
It reads the project role's credentials from `.env`, creates only the project
role/database if absent, and does not alter existing roles or databases.
The PostgreSQL server must already be running; no project-local server start
command is needed for normal development.

The earlier workspace-local cluster on port 5433 is stopped and retained under
`.local/postgres` as an unused fallback. Its helper script remains available for
an explicitly selected isolated setup; do not start it for normal development.
To use that alternative on a fresh checkout, set `.env` to port 5433 and run
`bash scripts/local_postgres.sh init`, `bash scripts/local_postgres.sh start`,
and `python scripts/provision_database.py --workspace-local`.

## Migrate and run

```bash
source .venv/bin/activate
alembic upgrade head
uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/health/db
```

`/health` returns `{"status":"ok"}` without querying PostgreSQL. `/health/db`
executes `SELECT 1`, returning HTTP 200 when reachable and a sanitized HTTP 503
when unavailable. It checks connectivity, not migration readiness. API docs are
at `http://127.0.0.1:8000/docs`.

Alembic is the only schema initialization mechanism; application startup never
calls `create_all()`. For later schema changes, generate a revision with
`alembic revision --autogenerate -m "describe change"`, review it, then apply it.
Triggers and changes to controlled values require explicit migration review.

## Tests

```bash
pytest --basetemp=.local/pytest-tmp
RUN_DB_TESTS=1 pytest --basetemp=.local/pytest-tmp
alembic check
```

The default suite needs no running database. Opt-in database tests use the `.env`
database after migrations, verify PostgreSQL connectivity, indexes, constraints,
UUID/timestamp defaults and the update trigger. Test rows are rolled back.
`requirements-dev.lock` records the dependency versions verified for this setup.

## Current scope

The `applications` table stores job details, application method, resume type,
contacts, status, timestamps, draft email text and notes. Controlled values have
database CHECK constraints. Non-unique indexes support normalized company/role
lookups without blocking separate openings with similar titles. Normalized values
must currently be supplied explicitly; advanced duplicate detection is future work.
There are no application CRUD endpoints yet.

AI agents, job discovery/scraping, email automation, browser automation, platform
automation, and a frontend are **not implemented**. Hermes is neither installed
nor configured. It may later orchestrate work through this backend; critical job
leads, applications, statuses, duplicate decisions, resumes, contacts and history
must live in PostgreSQL rather than LLM memory. Only the applications table exists
in this phase; the other domain tables will be added through later migrations.
