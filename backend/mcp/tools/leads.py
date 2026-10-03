from uuid import UUID

from app.schemas.domain import ApplicationCreate, LeadPatch, LeadRead, Page
from app.schemas.integration import LeadIntake, LeadIntakeResult
from backend.mcp.client import APIClient
from backend.mcp.contracts import ApplicationOutput, ConvertLead, LeadSearch
from backend.mcp.registration import READ, WRITE


def register(server, api: APIClient):
    @server.tool(annotations=WRITE)
    async def create_job_lead(data: LeadIntake) -> LeadIntakeResult:
        """Capture a discovered job, resolving or creating its company by normalized name. Ambiguous companies require company_id. Returns the lead, normalized names and deterministic duplicate information. Does not apply externally."""
        return await api.write("POST", "/leads/intake", LeadIntakeResult, data)

    @server.tool(annotations=READ)
    async def search_job_leads(filters: LeadSearch) -> Page[LeadRead]:
        """Search stored job leads using text, status, source, resume, timezone-aware dates and bounded pagination. Does not discover or scrape jobs."""
        return await api.get("/leads", Page[LeadRead], filters)

    @server.tool(annotations=READ)
    async def get_job_lead(lead_id: UUID) -> LeadRead:
        """Retrieve one stored job lead, including its source, description and optional fit assessment."""
        return await api.get(f"/leads/{lead_id}", LeadRead)

    @server.tool(annotations=WRITE)
    async def update_job_lead(lead_id: UUID, changes: LeadPatch) -> LeadRead:
        """Update lead facts, classification or review status through existing application rules. Do not invent experience or choose resumes solely from keywords. Cannot grant user approval."""
        return await api.write("PATCH", f"/leads/{lead_id}", LeadRead, changes)

    @server.tool(annotations=WRITE)
    async def convert_lead_to_application(data: ConvertLead) -> ApplicationOutput:
        """Create an application from an existing lead after selection. Supply an explicit resume and method. The API checks duplicates and atomically converts the lead and records events. Nothing is submitted externally."""
        lead = await api.get(f"/leads/{data.lead_id}", LeadRead)
        application = ApplicationCreate(
            company_id=lead.company_id,
            job_lead_id=lead.id,
            role_title=lead.role_title,
            application_method=data.application_method,
            resume_type=data.resume_type,
            source=lead.source,
            notes=data.notes,
        )
        return await api.write("POST", "/applications", ApplicationOutput, application)
