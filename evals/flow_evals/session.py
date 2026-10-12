"""Runs one scenario's query through `claude -p` with only the plugin under test loaded."""

import os
import subprocess
import tempfile
from pathlib import Path

# The read allowlist the README recommends, so a write stalls on permission instead of running.
READ_ALLOWLIST = [
    "Bash(flowbio api get:*)",
    "Bash(uvx --from flowbio==0.12.0 flowbio api get:*)",
    "Bash(pipx run --spec flowbio==0.12.0 flowbio api get:*)",
    "Bash(jq:*)",
]
_TIMEOUT_SECONDS = 15 * 60


def read_token(path: Path) -> str:
    token = path.read_text().strip() if path.is_file() else ""
    if not token:
        raise SystemExit(f"No eval token in {path}. Run the flow-api eval seed to create it.")
    return token


def run_agent(query: str, model: str, plugin_dir: Path, api_url: str, token: str, transcript_path: Path) -> None:
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "FLOW_API_URL": api_url, "FLOW_API_TOKEN": token}
    with tempfile.TemporaryDirectory() as cwd, transcript_path.open("w") as transcript:
        try:
            subprocess.run(_agent_command(query, model, plugin_dir), cwd=cwd, env=env,
                           stdout=transcript, stderr=subprocess.STDOUT, timeout=_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            transcript.write(f"runner: agent timed out after {_TIMEOUT_SECONDS}s\n")


def _agent_command(query: str, model: str, plugin_dir: Path) -> list[str]:
    # The skill reads its own reference files; from an empty cwd those reads need --add-dir.
    return ["claude", "-p", query, "--plugin-dir", str(plugin_dir), "--add-dir", str(plugin_dir),
            "--model", model, "--output-format", "stream-json", "--verbose",
            "--setting-sources", "project", "--strict-mcp-config", "--allowedTools", *READ_ALLOWLIST]
