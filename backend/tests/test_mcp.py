"""Protocol tests use real stdio. Database integration runs behind the real HTTP API."""

import asyncio
import os
import socket
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp_types import ElicitResult

ROOT = Path(__file__).resolve().parents[2]
TOOLS = {
    "get_lead_hunter_context",
    "ingest_lead_research",
    "create_job_lead",
    "search_job_leads",
    "get_job_lead",
    "update_job_lead",
    "convert_lead_to_application",
    "check_application_duplicate",
    "create_application",
    "get_application",
    "search_applications",
    "update_application",
    "update_application_status",
    "record_application_event",
    "get_application_events",
    "create_email_draft",
    "get_email_draft",
    "search_email_drafts",
    "approve_email_draft",
    "list_resume_profiles",
    "get_dashboard_summary",
    "search_companies",
    "get_company",
    "search_contacts",
    "get_contact",
}


@asynccontextmanager
async def connect(url="http://127.0.0.1:9", elicitation=None):
    # Run from a different directory to prove packaging does not rely on the terminal's cwd.
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "backend.mcp.server"],
        cwd=str(ROOT / "frontend"),
        env={"JOB_OS_API_URL": url, "DATABASE_URL": "must-not-be-read", "PYTHONDONTWRITEBYTECODE": "1"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(
            read, write, read_timeout_seconds=15, elicitation_callback=elicitation
        ) as session:
            await session.initialize()
            yield session


async def call(session, name, arguments=None):
    result = await session.call_tool(name, arguments or {})
    assert not result.is_error, result
    assert result.structured_content is not None
    return result.structured_content


def test_stdio_start_discovery_and_closed_capabilities():
    async def run():
        async with connect() as session:
            tools = (await session.list_tools()).tools
            assert {t.name for t in tools} == TOOLS
            for tool in tools:
                assert tool.description and tool.input_schema and tool.output_schema
                assert tool.annotations.open_world_hint is False
                assert tool.annotations.destructive_hint is False
            assert (await session.list_resources()).resources == []
            assert (await session.list_prompts()).prompts == []
            failure = await session.call_tool("get_dashboard_summary", {})
            assert failure.is_error
            assert "API unavailable" in failure.content[0].text
            forbidden = await session.call_tool("execute_sql", {"query": "SELECT 1"})
            assert forbidden.is_error

    asyncio.run(run())


def test_client_confined_to_local_api_and_no_orm_import():
    import subprocess

    from backend.mcp.client import api_url

    for value in [
        "https://example.com",
        "http://example.com",
        "http://127.0.0.1@evil.com",
        "http://user:password@localhost:8000",
        "http://localhost:8000/path",
        "http://localhost:8000?token=hidden",
    ]:
        with pytest.raises(ValueError):
            api_url(value)
    assert api_url("http://localhost:8000") == "http://127.0.0.1:8000"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from backend.mcp.server import create_server; import sys; create_server(); assert 'sqlalchemy' not in sys.modules; assert 'app.core.config' not in sys.modules",
        ],
        cwd=ROOT / "frontend",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_client_refuses_redirects_and_sanitizes_failures():
    import httpx
    from mcp.server.mcpserver.exceptions import ToolError

    from backend.mcp.client import APIClient

    async def run():
        seen = []

        async def handler(request):
            seen.append(str(request.url))
            return httpx.Response(302, headers={"location": "https://external.example/secret"})

        api = APIClient(transport=httpx.MockTransport(handler))
        with pytest.raises(ToolError, match="redirect refused"):
            await api.request("GET", "/resumes")
        assert len(seen) == 1
        api = APIClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(500, text="secret database connection"))
        )
        with pytest.raises(ToolError) as e:
            await api.request("GET", "/resumes")
        assert "secret" not in str(e.value)

    asyncio.run(run())


@pytest.fixture
def http_api():
    if os.getenv("RUN_DB_TESTS") != "1":
        pytest.skip("Set RUN_DB_TESTS=1 for HTTP/PostgreSQL integration")
    import uvicorn
    from sqlalchemy.orm import Session

    from app.db.session import get_engine, get_session
    from app.main import create_app
    from app.services.seed import seed

    with get_engine().connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
        seed(session)
        app = create_app()
        app.dependency_overrides[get_session] = lambda: session
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(0.02)
            assert server.started, "Test API failed to start"
            yield f"http://127.0.0.1:{port}"
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            listener.close()
            session.close()
            transaction.rollback()
            assert not thread.is_alive()


def test_mcp_full_workflow_over_stdio_http_postgres(http_api):
    import httpx

    confirmations = []

    async def approve(ctx, params):
        confirmations.append(params.message)
        return ElicitResult(action="accept", content={"approve": True})

    async def run():
        async with connect(http_api, approve) as session:
            name = f"MCP Test {uuid4().hex}"
            intake = await call(
                session,
                "create_job_lead",
                {
                    "data": {
                        "company_name": name,
                        "role_title": "Backend Engineer",
                        "source": "other",
                        "job_url": "https://jobs.example.com/" + uuid4().hex,
                    }
                },
            )
            lead, company = intake["lead"], intake["company"]
            assert company["normalized_name"] and lead["normalized_role_title"] == "backend engineer"
            assert intake["duplicate"]["is_duplicate"] is False
            assert (await call(session, "search_job_leads", {"filters": {"search": name}}))["total"] == 1
            assert (await call(session, "get_job_lead", {"lead_id": lead["id"]}))["id"] == lead["id"]
            await call(
                session, "update_job_lead", {"lead_id": lead["id"], "changes": {"status": "shortlisted"}}
            )
            app = await call(
                session,
                "convert_lead_to_application",
                {"data": {"lead_id": lead["id"], "application_method": "email", "resume_type": "technical"}},
            )
            assert app["job_lead_id"] == lead["id"]
            assert (await call(session, "get_application", {"application_id": app["id"]}))["id"] == app["id"]
            assert (await call(session, "search_applications", {"filters": {"search": name}}))["total"] == 1
            duplicate = await call(
                session,
                "check_application_duplicate",
                {"data": {"company": name, "role_title": "Backend Engineer", "job_url": lead["job_url"]}},
            )
            assert duplicate["is_duplicate"] and duplicate["matched_application_id"] == app["id"]
            # Exact URL matching works even when a new/mistyped company name is supplied.
            cross_name = await call(
                session,
                "check_application_duplicate",
                {
                    "data": {
                        "company": "Unrecorded company",
                        "role_title": "Backend Engineer",
                        "job_url": lead["job_url"],
                    }
                },
            )
            assert cross_name["is_duplicate"]
            other = await call(
                session,
                "create_application",
                {
                    "data": {
                        "company_id": company["id"],
                        "role_title": "Product Manager",
                        "resume_type": "product",
                        "application_method": "portal",
                    }
                },
            )
            await call(
                session,
                "update_application",
                {"application_id": other["id"], "changes": {"notes": "Manual review needed"}},
            )
            await call(
                session,
                "update_application_status",
                {"data": {"application_id": other["id"], "status": "shortlisted"}},
            )
            ev = await call(
                session,
                "record_application_event",
                {
                    "application_id": app["id"],
                    "data": {
                        "event_type": "recruiter_replied",
                        "metadata": {"note": "Availability requested"},
                    },
                },
            )
            assert ev["actor"] == "hermes"
            assert (
                await call(session, "get_application_events", {"application_id": app["id"], "pagination": {}})
            )["total"] >= 2
            draft = await call(
                session,
                "create_email_draft",
                {
                    "data": {
                        "application_id": app["id"],
                        "recipient_email": "recruiter@example.com",
                        "subject": "Application for Backend Engineer | Archit Singh Baghel",
                        "body": "Hi, I am Archit. Let us discuss the backend role.",
                        "resume_type": "technical",
                    }
                },
            )
            assert draft["status"] == "draft" and draft["sent_at"] is None
            assert (await call(session, "get_email_draft", {"draft_id": draft["id"]}))["id"] == draft["id"]
            assert (
                await call(session, "search_email_drafts", {"filters": {"search": "recruiter@example.com"}})
            )["total"] >= 1
            # Human review remains a separate existing UI/API operation.
            async with httpx.AsyncClient(base_url=http_api, trust_env=False) as http:
                reviewed = await http.patch(f"/email-drafts/{draft['id']}", json={"status": "reviewed"})
                assert reviewed.status_code == 200
                contact = await http.post(
                    "/contacts",
                    json={"name": "Recruiter", "email": "hr@example.com", "company_id": company["id"]},
                )
                assert contact.status_code == 201
            approved = await call(session, "approve_email_draft", {"draft_id": draft["id"]})
            assert approved["status"] == "approved" and approved["sent_at"] is None
            assert len(confirmations) == 1 and draft["body"] in confirmations[0]
            assert (await call(session, "get_application", {"application_id": app["id"]}))[
                "status"
            ] != "applied"
            assert (await call(session, "list_resume_profiles"))["profiles"][0]["profile_type"] in {
                "technical",
                "product",
            }
            assert (await call(session, "get_dashboard_summary"))["total_applications"] >= 2
            assert (await call(session, "search_companies", {"filters": {"search": name}}))["items"][0][
                "id"
            ] == company["id"]
            assert (await call(session, "get_company", {"company_id": company["id"]}))["name"] == name
            assert (await call(session, "search_contacts", {"filters": {"search": "hr@example.com"}}))[
                "total"
            ] >= 1
            assert (await call(session, "get_contact", {"contact_id": contact.json()["id"]}))[
                "name"
            ] == "Recruiter"
            # Same normalized company is reused and does not create an accidental second company.
            repeated = await call(
                session,
                "create_job_lead",
                {"data": {"company_name": name + " Inc.", "role_title": "Another Role", "source": "email"}},
            )
            assert repeated["company"]["id"] == company["id"]

    asyncio.run(run())


@pytest.mark.parametrize("consent", ["decline", "cancel", "false", "unavailable", "changed"])
def test_approval_fails_closed(http_api, consent):
    import httpx

    async def run():
        async with httpx.AsyncClient(base_url=http_api, trust_env=False) as http:
            intake = (
                await http.post(
                    "/leads/intake", json={"company_name": f"Consent {uuid4().hex}", "role_title": "Engineer"}
                )
            ).json()
            app = (
                await http.post(
                    "/applications",
                    json={
                        "company_id": intake["company"]["id"],
                        "role_title": "Engineer",
                        "resume_type": "technical",
                        "application_method": "email",
                    },
                )
            ).json()
            draft = (
                await http.post(
                    "/email-drafts",
                    json={
                        "application_id": app["id"],
                        "recipient_email": "hr@example.com",
                        "subject": "Review me",
                        "body": "Original content",
                        "resume_type": "technical",
                    },
                )
            ).json()
            await http.patch(f"/email-drafts/{draft['id']}", json={"status": "reviewed"})

            async def respond(ctx, params):
                if consent == "changed":
                    await http.patch(f"/email-drafts/{draft['id']}", json={"body": "Different content"})
                    await http.patch(f"/email-drafts/{draft['id']}", json={"status": "reviewed"})
                    return ElicitResult(action="accept", content={"approve": True})
                if consent == "false":
                    return ElicitResult(action="accept", content={"approve": False})
                return ElicitResult(action=consent)

            async with connect(http_api, None if consent == "unavailable" else respond) as session:
                result = await session.call_tool("approve_email_draft", {"draft_id": draft["id"]})
                assert result.is_error
            stored = (await http.get(f"/email-drafts/{draft['id']}")).json()
            assert (
                stored["status"] == "reviewed" and stored["approved_at"] is None and stored["sent_at"] is None
            )

    asyncio.run(run())
