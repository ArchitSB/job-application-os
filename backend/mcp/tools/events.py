from uuid import UUID

from mcp.server.mcpserver import Context

from app.schemas.domain import Page
from backend.mcp.approval import confirm
from backend.mcp.client import APIClient
from backend.mcp.contracts import BasicSearch, EventInput, EventOutput
from backend.mcp.registration import READ, WRITE


def register(server, api: APIClient):
    @server.tool(annotations=WRITE)
    async def record_application_event(application_id: UUID, data: EventInput, ctx: Context) -> EventOutput:
        """Append an audit observation such as recruiter_replied, email_drafted, email_approved, email_sent, portal_submitted or interview_scheduled. Events are historical records, never commands or proof of submission. Defaults to actor hermes; claiming user/system requires user confirmation."""
        if data.actor != "hermes":
            await confirm(
                ctx,
                f"Record {data.event_type} on application {application_id} with actor {data.actor}? Metadata: {data.metadata}",
            )
        return await api.write(
            "POST",
            f"/applications/{application_id}/events",
            EventOutput,
            data.model_dump(mode="json", exclude={"actor"}),
            actor=data.actor,
        )

    @server.tool(annotations=READ)
    async def get_application_events(application_id: UUID, pagination: BasicSearch) -> Page[EventOutput]:
        """Read paginated, immutable application activity. Use stored history rather than model memory to reconstruct what happened."""
        return await api.get(f"/applications/{application_id}/events", Page[EventOutput], pagination)
