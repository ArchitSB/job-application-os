from uuid import UUID

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError

from app.schemas.domain import DraftCreate, DraftRead, Page
from backend.mcp.approval import confirm
from backend.mcp.client import APIClient
from backend.mcp.contracts import DraftSearch
from backend.mcp.registration import READ, WRITE


def register(server, api: APIClient):
    @server.tool(annotations=WRITE)
    async def create_email_draft(data: DraftCreate) -> DraftRead:
        """Save an unsent application email draft for review. Use the application's explicit resume and Archit's direct, personal, job-specific writing style; never invent experience. Does not approve or send email."""
        return await api.write("POST", "/email-drafts", DraftRead, data)

    @server.tool(annotations=READ)
    async def get_email_draft(draft_id: UUID) -> DraftRead:
        """Retrieve a draft's complete content and review/approval state. This does not access Gmail."""
        return await api.get(f"/email-drafts/{draft_id}", DraftRead)

    @server.tool(annotations=READ)
    async def search_email_drafts(filters: DraftSearch) -> Page[DraftRead]:
        """Search stored drafts by subject/recipient, status, resume type, dates and pagination."""
        return await api.get("/email-drafts", Page[DraftRead], filters)

    @server.tool(annotations=WRITE)
    async def approve_email_draft(draft_id: UUID, ctx: Context) -> DraftRead:
        """Mark a reviewed email draft as approved by the user, only after an MCP user-confirmation prompt. Show the exact content. Requires prior review in the UI; refuses changed content or missing consent. This does not send the email."""
        draft = await api.get(f"/email-drafts/{draft_id}", DraftRead)
        if draft.status == "approved":
            return draft
        if draft.status != "reviewed":
            raise ToolError("Draft must be marked reviewed in the local UI before it can be approved.")
        await confirm(
            ctx,
            f"Approve this reviewed draft? No email will be sent.\nDraft: {draft.id}\nRecipient: {draft.recipient_email}\nResume: {draft.resume_type}\nSubject: {draft.subject}\n\n{draft.body}",
        )
        return await api.write(
            "POST",
            f"/email-drafts/{draft_id}/approve",
            DraftRead,
            {"expected_updated_at": draft.updated_at.isoformat()},
            actor="user",
        )
