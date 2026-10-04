"""Pure matching tests and real MCP→HTTP→PostgreSQL tests with outer rollback."""

import asyncio
import importlib.util
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text

from app.schemas.domain import Rules
from app.schemas.lead_hunter import CandidateFacts, HunterContext, HunterParameters, ResearchJob
from app.services.lead_hunter import normalize_result
from app.services.lead_matching import assess
from backend.tests.test_mcp import call, connect
from backend.tests.test_mcp import http_api as http_api

NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def job(**changes):
    return ResearchJob.model_validate(
        {
            "company_name": "Research Fixture Inc.",
            "role_title": "Backend Engineer",
            "source": "company_portal",
            "job_url": "https://careers.example.com/jobs/fixture-1",
            "source_post_url": "https://careers.example.com/jobs/fixture-1?utm_source=board",
            "description": "Build Python backend systems and FastAPI services.",
            "location": "Bengaluru, India",
            "employment_type": "full time",
            "evidence_status": "page_read",
            "research": {
                "skills": ["Python", "FastAPI"],
                "minimum_experience_years": 0,
                "work_mode": "hybrid",
                "evidence_excerpt": "Backend Engineer. Python, FastAPI. Bengaluru. Fresh graduates welcome.",
            },
            **changes,
        }
    )


def context():
    return HunterContext(
        full_name="Test Candidate",
        current_role="SDE Intern",
        current_company="Example",
        location="Bengaluru",
        candidate=CandidateFacts(
            skills=["Python", "FastAPI"], project_areas=["backend"], provenance="Test fixture"
        ),
        active_resume_profiles={"technical": "Backend engineering", "product": "Product discovery"},
        rules=Rules(),
    )


def test_normalization_and_missing_optional_fields():
    original = job(company_name="  Example Inc.  ", source="Some New Board", job_url=None)
    normalized = normalize_result(original, NOW)
    assert normalized.source == "other"
    assert normalized.research.original_source == "Some New Board"
    assert normalized.research.source_urls == [original.source_post_url]
    assert normalized.research.retrieved_at == NOW
    assert normalized.posted_at is None
    assert normalized.research.salary_min is None
    assert normalized.recruiter_email is None
    assert original.research.retrieved_at is None


@pytest.mark.parametrize(
    "changes",
    [
        {"job_url": "not a URL"},
        {"job_url": "javascript:alert(1)"},
        {"job_url": "http://127.0.0.1/private"},
        {"job_url": "https://user:secret@example.com/job"},
        {"job_url": "https://example.com/job?access_token=secret"},
        {"job_url": None, "source_post_url": None},
        {"evidence_status": "unavailable"},
        {"canonical_job_url": "https://careers.example.com/1"},
        {"research": {}},
        {"company_name": "!!!"},
    ],
)
def test_invalid_evidence_is_not_a_job(changes):
    with pytest.raises(ValueError):
        normalize_result(job(**changes), NOW)


def test_transparent_score_and_resume_requires_more_than_title():
    result = assess(job(), HunterParameters(), context(), now=NOW)
    assert result.score == 100
    assert result.category == "Excellent"
    assert sum(result.breakdown.values()) == 100
    assert result.recommended_resume_type == "technical"
    unknown = job(description=None, research={"evidence_excerpt": "Backend engineer opening"})
    result = assess(unknown, HunterParameters(), context(), now=NOW)
    assert result.score == 45
    assert result.recommended_resume_type is None
    assert any("Experience eligibility" in w for w in result.warnings)
    # Asking for a technology never adds it to the candidate's known skills.
    result = assess(job(research={"skills": ["Rust"]}), HunterParameters(technologies=["Rust"]), context())
    assert result.breakdown["skills"] == 0


def test_experience_recency_exclusions_and_salary():
    result = assess(
        job(
            role_title="Senior Backend Engineer",
            posted_at=NOW - timedelta(days=4),
            research={
                "minimum_experience_years": 5,
                "salary_max": 100,
                "salary_currency": "INR",
                "salary_period": "year",
            },
        ),
        HunterParameters(recency_days=3, salary_min=200),
        context(),
        now=NOW,
    )
    assert result.score <= 39
    assert len(result.ineligible_reasons) == 4
    assert "Posting date unknown" in " ".join(
        assess(job(), HunterParameters(recency_days=3), context(), now=NOW).ineligible_reasons
    )
    ctx = context()
    ctx.rules.excluded_companies = ["Research Fixture"]
    assert assess(job(), HunterParameters(), ctx).ineligible_reasons
    ctx = context()
    ctx.candidate.experience_years = 1
    j = job(research={"minimum_experience_years": 2})
    assert "candidate experience" in " ".join(assess(j, HunterParameters(), ctx).ineligible_reasons)


def test_product_and_mixed_roles_do_not_blindly_select_resume():
    product = job(
        role_title="Product Manager", description="Own product discovery and stakeholder requirements."
    )
    result = assess(
        product, HunterParameters(role_keywords=["Product Manager"], experience_level="any"), context()
    )
    assert result.recommended_resume_type == "product"
    product.role_title = "Product Engineer"
    assert assess(product, HunterParameters(), context()).recommended_resume_type is None


def test_explicit_remote_request_needs_remote_evidence():
    missing = job(research={"skills": ["Python"], "minimum_experience_years": 0})
    result = assess(missing, HunterParameters(work_mode="remote"), context())
    assert "Work mode unknown" in " ".join(result.ineligible_reasons)
    assert result.score <= 39


def test_location_wording_does_not_create_cross_source_duplicates(http_api):
    async def run():
        async with connect(http_api) as mcp:
            original = job(
                company_name="Location " + uuid4().hex,
                job_url="https://careers.example.com/" + uuid4().hex,
                location="Bengaluru",
            )
            assert (await call(mcp, "ingest_lead_research", payload(original)))["created"] == 1
            alternative = original.model_copy(
                update={
                    "source": "linkedin",
                    "location": "Bengaluru, India",
                    "job_url": "https://linkedin.com/jobs/view/123",
                    "source_post_url": "https://linkedin.com/jobs/view/123",
                }
            )
            report = await call(mcp, "ingest_lead_research", payload(alternative))
            assert report["review_required"] == 1 and report["created"] == 0

    asyncio.run(run())


def payload(record=None, **options):
    return {"data": {"results": [(record or job()).model_dump(mode="json")], **options}}


def test_hunter_real_mcp_workflow_and_no_external_actions(http_api, monkeypatch):
    import smtplib
    import subprocess

    # The API workflow must never invoke a mail transport, browser or external process.
    def forbidden(*args, **kwargs):
        raise AssertionError("Lead Hunter attempted an external action")

    # stdio client needs subprocesses; only patch synchronous external-action entrypoints.
    monkeypatch.setattr(smtplib, "SMTP", forbidden)
    monkeypatch.setattr(smtplib, "SMTP_SSL", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)

    async def run():
        async with connect(http_api) as mcp:
            ctx = await call(mcp, "get_lead_hunter_context")
            assert set(ctx["active_resume_profiles"]) == {"technical", "product"}
            assert "email" not in ctx and "date_of_birth" not in ctx
            before = await call(mcp, "get_dashboard_summary")
            drafts = await call(mcp, "search_email_drafts", {"filters": {}})
            name = "Hunter " + uuid4().hex
            candidate = job(company_name=name, job_url="https://careers.example.com/" + uuid4().hex)
            first = await call(mcp, "ingest_lead_research", payload(candidate))
            assert first["created"] == 1
            item = first["items"][0]
            assert item["lead"]["status"] == "discovered"
            assert item["lead"]["research"]["score_breakdown"] == item["match"]["breakdown"]
            assert item["lead"]["research"]["salary_min"] is None
            lead_id = item["lead_id"]
            # Same job, another board; canonical URL was established from the original source.
            second = candidate.model_copy(
                update={
                    "source": "linkedin",
                    "job_url": "https://linkedin.com/jobs/view/123",
                    "source_post_url": "https://linkedin.com/posts/123",
                    "canonical_job_url": candidate.job_url,
                    "canonical_url_evidence": "Mock source links directly to the company career job.",
                }
            )
            duplicate = await call(mcp, "ingest_lead_research", payload(second))
            assert duplicate["existing"] == 1 and duplicate["created"] == 0
            assert duplicate["items"][0]["lead_id"] == lead_id
            repeated = await call(mcp, "ingest_lead_research", payload(candidate))
            assert repeated["existing"] == 1
            stored = await call(mcp, "get_job_lead", {"lead_id": lead_id})
            assert stored["source"] == "company_portal"  # Curated facts were not overwritten.
            assert (await call(mcp, "search_job_leads", {"filters": {"search": name}}))["total"] == 1
            after = await call(mcp, "get_dashboard_summary")
            assert after["total_leads"] == before["total_leads"] + 1
            assert after["total_applications"] == before["total_applications"]
            assert (await call(mcp, "search_email_drafts", {"filters": {}}))["total"] == drafts["total"]
            with httpx.Client(base_url=http_api, trust_env=False) as api:
                events = api.get(f"/leads/{lead_id}/events").json()["items"]
                assert {e["event_type"] for e in events} >= {
                    "lead_created",
                    "lead_matched",
                    "lead_research_observed",
                }
                assert any(
                    "https://linkedin.com/posts/123" in e["metadata"].get("source_urls", []) for e in events
                )
                audit = api.get("/automation-runs").json()["items"]
                assert any(r["id"] == first["run_id"] and r["status"] == "completed" for r in audit)

    asyncio.run(run())


def test_hunter_duplicate_cases_preview_filters_and_limits(http_api):
    async def run():
        async with connect(http_api) as mcp:
            name = "Duplicates " + uuid4().hex
            base = job(
                company_name=name,
                job_url="https://careers.example.com/" + uuid4().hex,
                recruiter_email="recruiter@example.com",
            )
            preview = await call(mcp, "ingest_lead_research", payload(base, dry_run=True))
            assert preview["items"][0]["outcome"] == "would_create" and preview["run_id"] is None
            assert (await call(mcp, "search_job_leads", {"filters": {"search": name}}))["total"] == 0
            await call(mcp, "ingest_lead_research", payload(base))
            # Tracking query and trailing slash normalize to the same job.
            tracking = base.model_copy(update={"job_url": base.job_url + "/?utm_campaign=test"})
            assert (await call(mcp, "ingest_lead_research", payload(tracking)))["existing"] == 1
            # Distinct job URL at the same company board is a legitimate separate opening.
            distinct = base.model_copy(update={"job_url": base.job_url + "-2"})
            assert (await call(mcp, "ingest_lead_research", payload(distinct)))["created"] == 1
            # Same recruiter and different role is allowed.
            role = base.model_copy(update={"role_title": "AI Engineer", "job_url": base.job_url + "-3"})
            assert (await call(mcp, "ingest_lead_research", payload(role)))["created"] == 1
            ambiguous = base.model_copy(
                update={
                    "source": "wellfound",
                    "job_url": "https://wellfound.com/jobs/123",
                    "source_post_url": "https://wellfound.com/jobs/123",
                }
            )
            assert (await call(mcp, "ingest_lead_research", payload(ambiguous)))["review_required"] == 1
            no_url = base.model_copy(
                update={"job_url": None, "source_post_url": "https://other.example.com/hiring"}
            )
            assert (await call(mcp, "ingest_lead_research", payload(no_url)))["review_required"] == 1
            invalid = base.model_copy(update={"job_url": "invalid"})
            recent = base.model_copy(update={"company_name": name + " New", "job_url": base.job_url + "new"})
            batch = {
                "results": [
                    invalid.model_dump(mode="json"),
                    recent.model_dump(mode="json"),
                    recent.model_copy(update={"job_url": base.job_url + "new2"}).model_dump(mode="json"),
                ],
                "parameters": {"max_leads": 1},
                "skipped_sources": ["Naukri: login required"],
            }
            report = await call(mcp, "ingest_lead_research", {"data": batch})
            assert report["created"] == 1 and report["skipped"] == 2
            assert report["skipped_sources"] == ["Naukri: login required"]

    asyncio.run(run())


def test_hunter_respects_existing_applications(http_api):
    async def run():
        async with connect(http_api) as mcp:
            candidate = job(
                company_name="Applied " + uuid4().hex, job_url="https://jobs.example.com/" + uuid4().hex
            )
            lead = (await call(mcp, "ingest_lead_research", payload(candidate)))["items"][0]["lead"]
            application = await call(
                mcp,
                "create_application",
                {
                    "data": {
                        "company_id": lead["company_id"],
                        "role_title": lead["role_title"],
                        "job_url": lead["job_url"],
                        "application_method": "portal",
                        "resume_type": "technical",
                    }
                },
            )
            before = await call(mcp, "get_application", {"application_id": application["id"]})
            report = await call(mcp, "ingest_lead_research", payload(candidate))
            assert report["items"][0]["matched_application_id"] == application["id"]
            assert report["created"] == 0
            assert await call(mcp, "get_application", {"application_id": application["id"]}) == before

    asyncio.run(run())


def test_hunter_shared_application_page_and_generic_lead_compatibility(http_api):
    async def run():
        async with connect(http_api) as mcp:
            base = job(
                company_name="Shared portal " + uuid4().hex,
                job_url="https://careers.example.com/" + uuid4().hex,
                application_url="https://careers.example.com/apply",
            )
            first = await call(mcp, "ingest_lead_research", payload(base))
            assert first["created"] == 1
            distinct = base.model_copy(update={"job_url": base.job_url + "-different"})
            assert (await call(mcp, "ingest_lead_research", payload(distinct)))["created"] == 1
            lead_id = first["items"][0]["lead_id"]
            await call(mcp, "update_job_lead", {"lead_id": lead_id, "changes": {"status": "shortlisted"}})
            assert (await call(mcp, "ingest_lead_research", payload(base)))["existing"] == 1
            assert (await call(mcp, "get_job_lead", {"lead_id": lead_id}))["status"] == "shortlisted"
            manual = await call(
                mcp,
                "create_job_lead",
                {
                    "data": {
                        "company_name": "Manual " + uuid4().hex,
                        "role_title": "Backend Engineer",
                        "job_url": base.job_url + "-manual",
                    }
                },
            )
            candidate = base.model_copy(
                update={
                    "company_name": manual["company"]["name"],
                    "job_url": manual["lead"]["job_url"],
                    "application_url": None,
                }
            )
            assert (await call(mcp, "ingest_lead_research", payload(candidate)))["existing"] == 1

    asyncio.run(run())


def test_hunter_source_filters_recency_and_invalid_sibling(http_api):
    async def run():
        async with connect(http_api) as mcp:
            base = job(
                company_name="Source " + uuid4().hex,
                source="New Public Board",
                job_url="https://jobs.example.com/" + uuid4().hex,
            )
            fresh = await call(mcp, "ingest_lead_research", payload(base, parameters={"recency_days": 3}))
            assert fresh["skipped"] == 1
            assert "Posting date unknown" in fresh["items"][0]["reason"]
            source_filter = await call(
                mcp, "ingest_lead_research", payload(base, parameters={"sources": ["linkedin"]})
            )
            assert source_filter["skipped"] == 1
            stored = await call(mcp, "ingest_lead_research", payload(base))
            assert stored["created"] == 1
            assert stored["items"][0]["lead"]["source"] == "other"
            assert stored["items"][0]["lead"]["research"]["original_source"] == "New Public Board"
            broken = base.model_copy(
                update={"recruiter_email": "not-email", "company_name": "Invalid contact " + uuid4().hex}
            )
            assert (await call(mcp, "ingest_lead_research", payload(broken)))["skipped"] == 1

    asyncio.run(run())


def test_bundled_mock_is_always_a_nonwriting_preview(http_api):
    import json

    async def run():
        data = json.loads(
            (
                Path(__file__).resolve().parents[2]
                / ".hermes/skills/lead-hunter/references/mock-research.json"
            ).read_text()
        )
        assert data["dry_run"] is True
        async with connect(http_api) as mcp:
            before = await call(mcp, "get_dashboard_summary")
            report = await call(mcp, "ingest_lead_research", {"data": data})
            assert report["created"] == 0 and report["run_id"] is None
            assert [i["outcome"] for i in report["items"]] == ["would_create", "review_required"]
            assert await call(mcp, "get_dashboard_summary") == before

    asyncio.run(run())


@pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="Set RUN_DB_TESTS=1")
def test_migration_roundtrip_in_rollback_only_schema():
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    from app.db.session import get_engine

    path = Path(__file__).resolve().parents[2] / "alembic/versions/0004_lead_research.py"
    spec = importlib.util.spec_from_file_location("migration_0004", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with get_engine().connect() as conn:
        transaction = conn.begin()
        try:
            schema = "test_hunter_" + uuid4().hex
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            conn.execute(
                text("CREATE TABLE job_leads (id uuid PRIMARY KEY, job_url text, application_url text)")
            )
            conn.execute(
                text("INSERT INTO job_leads VALUES (:id, :url, NULL)"),
                {"id": uuid4(), "url": "https://EXAMPLE.com/job/1/?utm_source=test"},
            )
            with Operations.context(MigrationContext.configure(conn)):
                migration.upgrade()
                assert conn.scalar(text("SELECT identity_urls FROM job_leads")) == [
                    "https://example.com/job/1"
                ]
                migration.downgrade()
                assert conn.scalar(text("SELECT count(*) FROM job_leads")) == 1
                migration.upgrade()
                assert conn.scalar(text("SELECT count(*) FROM job_leads")) == 1
        finally:
            transaction.rollback()
