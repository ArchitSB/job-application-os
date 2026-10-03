from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError

from backend.mcp.contracts import Confirmation


async def confirm(ctx: Context, message: str) -> None:
    """Ask the MCP client to obtain user consent; decline/unsupported fails closed."""
    try:
        result = await ctx.elicit(message=message, schema=Confirmation)
    except Exception:
        raise ToolError(
            "User confirmation is unavailable. Complete this approval in the local UI instead."
        ) from None
    if result.action != "accept" or result.data is None or result.data.approve is not True:
        raise ToolError("User did not approve. No change was made.")
