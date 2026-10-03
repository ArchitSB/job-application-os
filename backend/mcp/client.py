"""Fixed-origin HTTP boundary. Deliberately does not load the application's .env."""

import json
import os
from urllib.parse import urlsplit, urlunsplit

import httpx
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, ValidationError


def api_url(value: str) -> str:
    parts = urlsplit(value)
    if (
        parts.scheme != "http"
        or parts.hostname not in {"localhost", "127.0.0.1", "::1"}
        or parts.username
        or parts.password
        or parts.path not in {"", "/"}
        or parts.query
        or parts.fragment
    ):
        raise ValueError("JOB_OS_API_URL must be a credential-free loopback HTTP origin")
    # Avoid DNS/proxy redirection: localhost is pinned to the IPv4 loopback address.
    host = "[::1]" if parts.hostname == "::1" else "127.0.0.1"
    return urlunsplit(("http", f"{host}:{parts.port or 80}", "", "", ""))


class APIClient:
    def __init__(self, base_url: str | None = None, *, transport: httpx.AsyncBaseTransport | None = None):
        self.base_url = api_url(base_url or os.getenv("JOB_OS_API_URL", "http://127.0.0.1:8000"))
        self.transport = transport

    async def request(
        self,
        method: str,
        path: str,
        *,
        body: BaseModel | dict | None = None,
        params: BaseModel | dict | None = None,
        actor: str = "hermes",
    ) -> dict | list:
        if not path.startswith("/") or path.startswith("//") or "?" in path or "#" in path:
            raise ToolError("Invalid internal API path")
        if isinstance(body, BaseModel):
            body = body.model_dump(mode="json", exclude_unset=True)
        if isinstance(params, BaseModel):
            params = params.model_dump(mode="json", exclude_none=True)
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                transport=self.transport,
                timeout=15,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                response = await client.request(
                    method, path, json=body, params=params, headers={"X-Actor": actor}
                )
        except httpx.HTTPError:
            message = (
                "API unavailable. Start the local FastAPI backend and retry the read."
                if method == "GET"
                else "API connection failed or timed out; outcome may be uncertain. Read the record before retrying this write."
            )
            raise ToolError(message) from None
        if response.is_redirect:
            raise ToolError("API redirect refused; verify the local backend address")
        if response.status_code >= 500:
            raise ToolError(
                "Local API is unavailable. Check backend/database health; verify writes before retrying."
            )
        try:
            data = response.json()
        except ValueError:
            raise ToolError("Local API returned an unexpected non-JSON response") from None
        if response.is_error:
            # The API supplies sanitized business errors; never include HTTP headers or raw exceptions.
            error = data.get("error", {}) if isinstance(data, dict) else {}
            raise ToolError(json.dumps({"status": response.status_code, "error": error}))
        return data

    async def get(self, path: str, output, params=None):
        return self.validate(output, await self.request("GET", path, params=params))

    async def write(self, method: str, path: str, output, body, *, actor="hermes"):
        return self.validate(output, await self.request(method, path, body=body, actor=actor))

    @staticmethod
    def validate(output, data):
        try:
            return output.model_validate(data)
        except ValidationError:
            raise ToolError(
                "API response does not match the documented contract; check backend/bridge versions."
            ) from None
