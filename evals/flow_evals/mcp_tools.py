"""Which of Flow's MCP tools the server marks read-only, fetched before an MCP-mode run."""

import asyncio

import httpx2
from mcp import types
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError

FLOW_MCP_SERVER = "flow"
# Claude Code names an MCP tool mcp__<server>__<tool>.
FLOW_TOOL_PREFIX = f"mcp__{FLOW_MCP_SERVER}__"


def fetch_read_only(mcp_url: str, token: str) -> dict[str, bool]:
    """Maps each tool Flow's MCP server lists to whether it marks the tool read-only.

    Exits when the server can't be reached or refuses the token, before any agent spends time on it.
    """
    try:
        return asyncio.run(_fetch_read_only(mcp_url, token))
    except* (MCPError, httpx2.HTTPError) as group:
        failure = _first_leaf(group)
    raise SystemExit(f"Could not list Flow's MCP tools at {mcp_url}: {failure}")


def _first_leaf(error: BaseException) -> BaseException:
    # The SDK's task groups nest the real cause a level or more deep.
    while isinstance(error, BaseExceptionGroup):
        error = error.exceptions[0]
    return error


async def _fetch_read_only(mcp_url: str, token: str) -> dict[str, bool]:
    async with (
        httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"}) as http_client,
        # The server keeps no sessions, so there is none to end.
        streamable_http_client(mcp_url, http_client=http_client, terminate_on_close=False) as (read, write),
        ClientSession(read, write) as session,
    ):
        initialized = await session.initialize()
        tools, cursor = [], None
        if initialized.capabilities.tools is None:
            return {}
        while True:
            page = await session.list_tools(params=types.PaginatedRequestParams(cursor=cursor) if cursor else None)
            tools += page.tools
            if not (cursor := page.next_cursor):
                break
    return {tool.name: bool(tool.annotations and tool.annotations.read_only_hint) for tool in tools}
