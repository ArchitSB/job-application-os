from backend.mcp.client import APIClient
from backend.mcp.contracts import ResumeList
from backend.mcp.registration import READ


def register(server, api: APIClient):
    @server.tool(annotations=READ)
    async def list_resume_profiles() -> ResumeList:
        """List technical and product resume metadata and configured public links. Select deliberately from full job responsibilities. Does not read local PDFs, download Drive files or expose credentials."""
        return ResumeList(profiles=await api.request("GET", "/resumes"))
