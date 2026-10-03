from uuid import UUID

from app.schemas.domain import ApplicationCreate, ApplicationPatch, DuplicateResult, Page
from app.schemas.integration import DuplicateByCompany
from backend.mcp.client import APIClient
from backend.mcp.contracts import ApplicationOutput, ApplicationSearch, StatusUpdate
from backend.mcp.registration import READ, WRITE


def register(server, api: APIClient):
    @server.tool(annotations=READ)
    async def check_application_duplicate(data: DuplicateByCompany) -> DuplicateResult:
        """Check whether a job opportunity has already been applied to using the API's deterministic duplicate service. Always call before creating an application from a newly discovered job. Company is a name; optional company_id resolves ambiguity. No LLM duplicate decision."""
        return await api.write("POST", "/applications/check-duplicate-by-name", DuplicateResult, data)

    @server.tool(annotations=WRITE)
    async def create_application(data: ApplicationCreate) -> ApplicationOutput:
        """Create an application record after selecting a job and an explicit resume. API duplicate checks and policy apply. This does not submit an application externally or grant human approval."""
        return await api.write("POST", "/applications", ApplicationOutput, data)

    @server.tool(annotations=READ)
    async def get_application(application_id: UUID) -> ApplicationOutput:
        """Read one application's stored facts, selected resume, status and application dates."""
        return await api.get(f"/applications/{application_id}", ApplicationOutput)

    @server.tool(annotations=READ)
    async def search_applications(filters: ApplicationSearch) -> Page[ApplicationOutput]:
        """Search application history with text, status, source, method, resume, dates and pagination. Date filters apply to record creation time."""
        return await api.get("/applications", Page[ApplicationOutput], filters)

    @server.tool(annotations=WRITE)
    async def update_application(application_id: UUID, changes: ApplicationPatch) -> ApplicationOutput:
        """Update application facts via the API; identity changes repeat duplicate checks and all changes are audited as Hermes. User-only approval/submission transitions remain blocked."""
        return await api.write("PATCH", f"/applications/{application_id}", ApplicationOutput, changes)

    @server.tool(annotations=WRITE)
    async def update_application_status(data: StatusUpdate) -> ApplicationOutput:
        """Record an allowed application status transition, with optional notes/date. Does not submit jobs or send emails. The API enforces human-only approval and submission outcomes."""
        return await api.write(
            "PATCH",
            f"/applications/{data.application_id}",
            ApplicationOutput,
            data.model_dump(mode="json", exclude={"application_id"}, exclude_unset=True),
        )
