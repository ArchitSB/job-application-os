from uuid import UUID

from app.schemas.domain import ContactRead, Page
from backend.mcp.client import APIClient
from backend.mcp.contracts import BasicSearch
from backend.mcp.registration import READ


def register(server, api: APIClient):
    @server.tool(annotations=READ)
    async def search_contacts(filters: BasicSearch) -> Page[ContactRead]:
        """Search stored recruiter/founder/hiring contacts by name or email; no external contact discovery."""
        return await api.get("/contacts", Page[ContactRead], filters)

    @server.tool(annotations=READ)
    async def get_contact(contact_id: UUID) -> ContactRead:
        """Retrieve one stored contact and associated company ID. Does not contact the person."""
        return await api.get(f"/contacts/{contact_id}", ContactRead)
