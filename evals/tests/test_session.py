import json
import os
from pathlib import Path

import pytest

from flow_evals.session import ALLOWED_TOOLS, mcp_command, read_token, run_agent, skill_command

FAKE_CLAUDE = """#!/usr/bin/env python3
import json, os, sys
print(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd(), "cwd_entries": os.listdir("."),
                  "url": os.environ.get("FLOW_API_URL"), "token": os.environ.get("FLOW_API_TOKEN")}))
"""


@pytest.fixture
def fake_claude(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "claude"
    script.write_text(FAKE_CLAUDE)
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")


def _run(tmp_path: Path, token: str = "secret-token") -> dict:
    transcript = tmp_path / "runs" / "004-haiku.jsonl"
    command = skill_command("How much data?", "haiku", Path("plugins/flowbio").resolve())
    run_agent(command, "http://localhost:8019", token, transcript)
    return json.loads(transcript.read_text())


def test_runs_in_an_empty_temp_dir(tmp_path, fake_claude):
    seen = _run(tmp_path)
    assert seen["cwd_entries"] == []
    assert Path(seen["cwd"]) != Path.cwd()


def test_passes_isolation_and_allowlist_flags(tmp_path, fake_claude):
    argv = _run(tmp_path)["argv"]
    plugin_dir = str(Path("plugins/flowbio").resolve())
    assert argv[:2] == ["-p", "How much data?"]
    for flag, value in [("--plugin-dir", plugin_dir), ("--add-dir", plugin_dir), ("--model", "haiku"),
                        ("--output-format", "stream-json"), ("--setting-sources", "project")]:
        assert argv[argv.index(flag) + 1] == value
    assert {"--verbose", "--strict-mcp-config"} <= set(argv)
    assert argv[argv.index("--allowedTools") + 1:][:len(ALLOWED_TOOLS)] == ALLOWED_TOOLS


def test_lets_the_skill_load_and_grants_no_commands_itself(tmp_path, fake_claude):
    argv = _run(tmp_path)["argv"]
    allowed = argv[argv.index("--allowedTools") + 1:][:len(ALLOWED_TOOLS)]
    assert "Skill(flowbio:flow-assistant)" in allowed
    assert not [rule for rule in allowed if rule.startswith("Bash(")]


def test_token_reaches_the_child_env_but_not_its_argv(tmp_path, fake_claude):
    token = "secret-token"
    seen = _run(tmp_path, token)
    assert seen["token"] == token
    assert seen["url"] == "http://localhost:8019"
    assert token not in " ".join(seen["argv"])
    assert os.environ.get("FLOW_API_TOKEN") != token


def test_read_token_strips_whitespace(tmp_path):
    path = tmp_path / "token"
    path.write_text("abc\n")
    assert read_token(path) == "abc"


@pytest.mark.parametrize("content", [None, "", "\n"])
def test_read_token_stops_on_missing_or_empty_file(tmp_path, content):
    path = tmp_path / "token"
    if content is not None:
        path.write_text(content)
    with pytest.raises(SystemExit, match=str(path)):
        read_token(path)


def _mcp_argv(read_only: dict[str, bool]) -> list[str]:
    return mcp_command("How much data?", "haiku", "http://localhost:8019", read_only)[1:]


def test_mcp_mode_loads_only_flows_mcp_server_with_the_token_from_the_env():
    argv = _mcp_argv({"list_samples": True})
    config = json.loads(argv[argv.index("--mcp-config") + 1])
    assert config == {"mcpServers": {"flow": {"type": "http", "url": "http://localhost:8019/mcp",
                                              "headers": {"Authorization": "Bearer ${FLOW_API_TOKEN}"}}}}
    assert {"--strict-mcp-config", "--verbose"} <= set(argv)
    assert argv[argv.index("--setting-sources") + 1] == "project"
    assert not {"--plugin-dir", "--add-dir"} & set(argv)


def test_mcp_mode_pre_approves_flows_read_tools_but_not_its_writes():
    argv = _mcp_argv({"list_samples": True, "update_sample": False})
    assert argv[argv.index("--allowedTools") + 1:] == ["mcp__flow__list_samples"]


def test_mcp_mode_without_read_tools_pre_approves_nothing():
    assert "--allowedTools" not in _mcp_argv({"update_sample": False})
