# Backend foundation decisions

FastAPI handles HTTP, services handle deterministic operations, and SQLAlchemy
maps data in PostgreSQL. Sessions close per request and require explicit commits
for future writes. Configuration is loaded from the root `.env` and may be
overridden by environment variables; connection strings are masked in settings
representations. Engine construction is lazy, with connection checks and bounded
connection/query timeouts.

Applications use database-generated UUIDs and timezone-aware timestamps. A
migration-managed trigger maintains `updated_at` even when records are modified
outside SQLAlchemy. Status, resume type and application method are strings with
database CHECK constraints; source is extensible text (for example linkedin,
telegram, naukri, wellfound, hnhiring, unstop, company_portal, email, or other).
Method and resume type are required; status defaults to `discovered`.

The composite company/role index also supports company-only lookups through its
leading column. A separate role index supports role-only lookups. Neither is
unique: equal normalized names are candidates for duplicate review, not proof
that two openings are identical. Normalization policy and duplicate decisions
remain future deterministic service work.

Alembic owns schema changes. No startup schema creation, agent logic, network
automation, or LLM history storage is part of this foundation. The current API
exposes only health checks and is intended to run on localhost for development.
