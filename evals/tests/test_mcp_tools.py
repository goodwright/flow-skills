import socket
import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn
from mcp import types
from mcp.server.lowlevel.server import Server

from flow_evals.mcp_tools import fetch_read_only, load_read_only, save_read_only

TOKEN = "eval-token"
TOOLS = [
    types.Tool(name="list_samples", input_schema={"type": "object"},
               annotations=types.ToolAnnotations(read_only_hint=True)),
    types.Tool(name="update_sample", input_schema={"type": "object"}),
]


async def _list_tools(ctx, params) -> types.ListToolsResult:
    return types.ListToolsResult(tools=TOOLS)


def _require_bearer(app):
    async def guarded(scope, receive, send):
        if scope["type"] == "http" and dict(scope["headers"]).get(b"authorization") != f"Bearer {TOKEN}".encode():
            await send({"type": "http.response.start", "status": 401, "headers": []})
            await send({"type": "http.response.body", "body": b""})
            return
        await app(scope, receive, send)
    return guarded


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _serve(server: Server) -> Iterator[str]:
    port = _free_port()
    app = _require_bearer(server.streamable_http_app(json_response=True, stateless_http=True))
    uvicorn_server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=uvicorn_server.run, daemon=True)
    thread.start()
    while not uvicorn_server.started:
        time.sleep(0.01)
    yield f"http://127.0.0.1:{port}"
    uvicorn_server.should_exit = True
    thread.join()


@pytest.fixture
def flow_server() -> Iterator[str]:
    yield from _serve(Server("flow", on_list_tools=_list_tools))


def test_marks_a_read_only_hinted_tool_read_only_and_an_unannotated_one_not(flow_server):
    assert fetch_read_only(f"{flow_server}/mcp", TOKEN) == {"list_samples": True, "update_sample": False}


async def _list_one_tool_per_page(ctx, params) -> types.ListToolsResult:
    page = int(params.cursor) if params and params.cursor else 0
    next_cursor = str(page + 1) if page + 1 < len(TOOLS) else None
    return types.ListToolsResult(tools=[TOOLS[page]], next_cursor=next_cursor)


@pytest.fixture
def paged_server() -> Iterator[str]:
    yield from _serve(Server("flow", on_list_tools=_list_one_tool_per_page))


def test_reads_every_page_of_the_tool_list(paged_server):
    assert fetch_read_only(f"{paged_server}/mcp", TOKEN) == {"list_samples": True, "update_sample": False}


@pytest.fixture
def toolless_server() -> Iterator[str]:
    yield from _serve(Server("flow"))


def test_a_server_that_lists_no_tools_has_none(toolless_server):
    assert fetch_read_only(f"{toolless_server}/mcp", TOKEN) == {}


def test_stops_when_the_server_refuses_the_token(flow_server):
    mcp_url = f"{flow_server}/mcp"
    with pytest.raises(SystemExit, match=f"{mcp_url}: Server returned an error response"):
        fetch_read_only(mcp_url, "rejected-token")


def test_stops_when_nothing_listens_at_the_url():
    mcp_url = f"http://127.0.0.1:{_free_port()}/mcp"
    with pytest.raises(SystemExit, match=f"{mcp_url}: All connection attempts failed"):
        fetch_read_only(mcp_url, TOKEN)


def test_a_saved_tool_list_loads_back_from_the_run_directory(tmp_path):
    read_only = {"list_samples": True, "update_sample": False}
    save_read_only(tmp_path, read_only)
    assert load_read_only(tmp_path) == read_only
    assert [p.name for p in tmp_path.iterdir()] == ["tools.json"]
