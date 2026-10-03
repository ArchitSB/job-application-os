from uuid import UUID

from app.schemas.domain import CompanyRead, Page
from backend.mcp.client import APIClient
from backend.mcp.contracts import BasicSearch
from backend.mcp.registration import READ


def register(server, api: APIClient):
    @server.tool(annotations=READ)
    async def search_companies(filters: BasicSearch) -> Page[CompanyRead]:
        """Find stored companies by name with pagination. Compare IDs/domains when similarly named companies exist; do not guess a merge."""
        return await api.get("/companies", Page[CompanyRead], filters)

    @server.tool(annotations=READ)
    async def get_company(company_id: UUID) -> CompanyRead:
        """Retrieve one company record, including normalized name, domain and public URLs."""
        return await api.get(f"/companies/{company_id}", CompanyRead)
