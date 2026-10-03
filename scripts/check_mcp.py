"""Read-only stdio smoke check. Requires the local API, never modifies application data."""

import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def check() -> None:
    root = Path(__file__).resolve().parents[1]
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "backend.mcp.server"],
        cwd=str(root),
        env={"JOB_OS_API_URL": os.getenv("JOB_OS_API_URL", "http://127.0.0.1:8000")},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=20) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            print(f"MCP connected: {len(tools)} typed tools discovered.")
            for name in ("list_resume_profiles", "get_dashboard_summary"):
                result = await session.call_tool(name, {})
                if result.is_error:
                    raise RuntimeError(f"{name} failed: {result.content}")
                print(f"{name}: OK")
    print("Stdio server shut down cleanly. No records changed.")


if __name__ == "__main__":
    asyncio.run(check())
