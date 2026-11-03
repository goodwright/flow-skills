"""Runs one scenario's query through `claude -p` with only the plugin, or only Flow's MCP server, loaded."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from flow_evals.mcp_tools import FLOW_MCP_SERVER, FLOW_TOOL_PREFIX

# The skill's own allowed-tools pre-approves its reads, so a write stalls on permission instead of
# running. Claude Code only loads a skill that grants itself tools in -p when a rule allows it.
ALLOWED_TOOLS = [
    "Skill(flowbio:flow-assistant)",
]
_TIMEOUT_SECONDS = 15 * 60


def read_token(path: Path) -> str:
    token = path.read_text().strip() if path.is_file() else ""
    if not token:
        raise SystemExit(f"No eval token in {path}. Run the flow-api eval seed to create it.")
    return token


def run_agent(command: list[str], api_url: str, token: str, transcript_path: Path) -> None:
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "FLOW_API_URL": api_url, "FLOW_API_TOKEN": token}
    with tempfile.TemporaryDirectory() as cwd, transcript_path.open("w") as transcript:
        try:
            subprocess.run(command, cwd=cwd, env=env,
                           stdout=transcript, stderr=subprocess.STDOUT, timeout=_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            transcript.write(f"runner: agent timed out after {_TIMEOUT_SECONDS}s\n")


def skill_command(query: str, model: str, plugin_dir: Path) -> list[str]:
    """The agent command for skill mode: only the plugin loaded, and only its skill allowed."""
    # The skill reads its own reference files; from an empty cwd those reads need --add-dir.
    return ["claude", "-p", query, "--plugin-dir", str(plugin_dir), "--add-dir", str(plugin_dir),
            *_common_flags(model), "--allowedTools", *ALLOWED_TOOLS]


def mcp_command(query: str, model: str, api_url: str, read_only: dict[str, bool]) -> list[str]:
    """The agent command for MCP mode: only Flow's MCP server loaded, and only its read tools allowed."""
    # Claude Code expands ${FLOW_API_TOKEN} from the agent's environment, keeping the token out of argv.
    server = {"type": "http", "url": f"{api_url}/mcp", "headers": {"Authorization": "Bearer ${FLOW_API_TOKEN}"}}
    read_tools = [f"{FLOW_TOOL_PREFIX}{name}" for name, is_read in read_only.items() if is_read]
    return ["claude", "-p", query, "--mcp-config", json.dumps({"mcpServers": {FLOW_MCP_SERVER: server}}),
            *_common_flags(model), *(["--allowedTools", *read_tools] if read_tools else [])]


def _common_flags(model: str) -> list[str]:
    return ["--model", model, "--output-format", "stream-json", "--verbose",
            "--setting-sources", "project", "--strict-mcp-config"]
