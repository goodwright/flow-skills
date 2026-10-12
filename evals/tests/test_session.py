import json
import os
from pathlib import Path

import pytest

from flow_evals.session import READ_ALLOWLIST, read_token, run_agent

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
    run_agent("How much data?", "haiku", Path("plugins/flow-ai").resolve(), "http://localhost:8019", token, transcript)
    return json.loads(transcript.read_text())


def test_runs_in_an_empty_temp_dir(tmp_path, fake_claude):
    seen = _run(tmp_path)
    assert seen["cwd_entries"] == []
    assert Path(seen["cwd"]) != Path.cwd()


def test_passes_isolation_and_allowlist_flags(tmp_path, fake_claude):
    argv = _run(tmp_path)["argv"]
    plugin_dir = str(Path("plugins/flow-ai").resolve())
    assert argv[:2] == ["-p", "How much data?"]
    for flag, value in [("--plugin-dir", plugin_dir), ("--add-dir", plugin_dir), ("--model", "haiku"),
                        ("--output-format", "stream-json"), ("--setting-sources", "project")]:
        assert argv[argv.index(flag) + 1] == value
    assert {"--verbose", "--strict-mcp-config"} <= set(argv)
    assert argv[argv.index("--allowedTools") + 1:][:len(READ_ALLOWLIST)] == READ_ALLOWLIST


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
