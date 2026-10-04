from app.schemas.lead_hunter import HunterBatch, HunterContext, HunterReport
from backend.mcp.client import APIClient
from backend.mcp.registration import READ, WRITE


def register(server, api: APIClient):
    @server.tool(annotations=READ)
    async def get_lead_hunter_context() -> HunterContext:
        """Read current career profile, active resume descriptions, confirmed matching facts, application rules and search defaults before researching jobs. No credentials or personal form fields are returned. Use these facts, never invented experience."""
        return await api.get("/lead-hunter/context", HunterContext)

    @server.tool(annotations=WRITE)
    async def ingest_lead_research(data: HunterBatch) -> HunterReport:
        """Evaluate public job evidence supplied by Hermes research tools. Normalize, score, check existing leads AND applications, and store eligible new leads with audit history. Supply actual excerpts/URLs, mark inaccessible sources unavailable; never invent jobs. dry_run previews without writes. Ambiguous duplicates require review. Never creates applications, email drafts, approvals, emails or external submissions. Use instead of create_job_lead for Lead Hunter intake."""
        return await api.write("POST", "/lead-hunter/research", HunterReport, data)
