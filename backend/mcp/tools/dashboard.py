from backend.mcp.client import APIClient
from backend.mcp.contracts import DashboardOutput
from backend.mcp.registration import READ


def register(server, api: APIClient):
    @server.tool(annotations=READ)
    async def get_dashboard_summary() -> DashboardOutput:
        """Read existing dashboard totals, this-week/month applications, waiting responses, interviews, rejections, offers and resume/source/method groupings."""
        return await api.get("/dashboard/summary", DashboardOutput)
