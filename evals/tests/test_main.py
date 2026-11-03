import json
import os

import pytest

from flow_evals import compare, run

FAKE_CLAUDE = """#!/usr/bin/env python3
import json, os, sys
if "--json-schema" in sys.argv:
    print(json.dumps({"structured_output": {"items": [{"pass": True, "reason": "fine"}]}}))
else:
    with open(os.environ["TOKENS_SEEN"], "a") as seen:
        print(sys.argv[2], os.environ.get("FLOW_API_TOKEN"), sep="\\t", file=seen)
    print(json.dumps({"type": "result", "result": "You own 7 files.", "num_turns": 2,
                      "usage": {"input_tokens": 5, "output_tokens": 3}}))
"""
SCENARIO = {"query": "How many files do I own?", "checks": {"answer_contains": ["owned_count"]},
            "expected_behavior": ["reads only"]}
TOKEN = "secret-token"


@pytest.fixture
def stack(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "claude").write_text(FAKE_CLAUDE)
    (bin_dir / "claude").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    scenario_dir = tmp_path / "scenarios"
    scenario_dir.mkdir()
    (scenario_dir / "004-data-i-own.json").write_text(json.dumps(SCENARIO))
    monkeypatch.setattr(run, "_SCENARIO_DIR", scenario_dir)
    monkeypatch.setattr(run, "_RUNS_DIR", tmp_path / "runs")
    (tmp_path / "expected.json").write_text(json.dumps({"owned_count": 7}))
    (tmp_path / "token").write_text(TOKEN)
    monkeypatch.setenv("EVAL_EXPECTED_FILE", str(tmp_path / "expected.json"))
    monkeypatch.setenv("EVAL_TOKEN_FILE", str(tmp_path / "token"))
    monkeypatch.setenv("TOKENS_SEEN", str(tmp_path / "tokens-seen"))
    return tmp_path


def _summary(run_dir):
    return json.loads((run_dir / "summary.json").read_text())["runs"]


def test_main_runs_each_scenario_on_each_model_and_writes_a_summary(stack, capsys):
    assert run.main(["--scenario", "004*", "--model", "haiku", "--model", "opus"]) == 0
    run_dir, = (stack / "runs").iterdir()
    rows = _summary(run_dir)
    assert [(r["scenario"], r["model"], r["passed"], r["total"]) for r in rows] == [
        ("004-data-i-own", "haiku", 2, 2), ("004-data-i-own", "opus", 2, 2)]
    assert (run_dir / "004-data-i-own-haiku.jsonl").exists()
    assert TOKEN not in capsys.readouterr().out


def test_an_invalid_token_scenario_runs_with_a_token_flow_rejects(stack):
    rejected_query = "Show me the samples I own."
    (stack / "scenarios" / "018-auth.json").write_text(json.dumps({**SCENARIO, "query": rejected_query,
                                                                   "invalid_token": True}))
    run.main(["--scenario", "*", "--model", "haiku"])
    seen = dict(line.split("\t") for line in (stack / "tokens-seen").read_text().splitlines())
    assert seen[SCENARIO["query"]] == TOKEN
    assert seen[rejected_query] not in (TOKEN, "", "None")


def test_main_stops_without_the_expected_answers(stack, monkeypatch):
    monkeypatch.delenv("EVAL_EXPECTED_FILE")
    with pytest.raises(SystemExit, match="EVAL_EXPECTED_FILE"):
        run.main(["--scenario", "004*"])


def test_regrade_rewrites_the_summary_from_saved_transcripts(stack):
    run.main(["--scenario", "004*", "--model", "haiku"])
    run_dir, = (stack / "runs").iterdir()
    (stack / "expected.json").write_text(json.dumps({"owned_count": 8}))
    assert run.main(["--regrade", str(run_dir)]) == 0
    assert [(r["passed"], r["total"]) for r in _summary(run_dir)] == [(1, 2)]


def _write_summary(path, passed):
    path.mkdir()
    (path / "summary.json").write_text(json.dumps({"runs": [
        {"scenario": "004", "model": "haiku", "passed": passed, "total": 4,
         "input_tokens": 100, "output_tokens": 0, "completed": True}]}))
    return path


def test_compare_main_exits_zero_when_the_gate_passes(tmp_path, capsys):
    before, after = _write_summary(tmp_path / "a", 3), _write_summary(tmp_path / "b", 4)
    assert compare.main([str(before), str(after)]) == 0
    out = capsys.readouterr().out
    assert "3/4" in out and "4/4" in out and "gate: pass" in out


def test_compare_main_exits_one_and_says_why_when_the_gate_fails(tmp_path, capsys):
    before, after = _write_summary(tmp_path / "a", 4), _write_summary(tmp_path / "b", 3)
    assert compare.main([str(before), str(after)]) == 1
    assert "pass rate fell" in capsys.readouterr().out


READ_ONLY = {"list_samples": True, "update_sample": False}


@pytest.fixture
def flow_mcp(monkeypatch):
    fetched = []

    def fetch(mcp_url, token):
        fetched.append((mcp_url, token))
        return READ_ONLY
    monkeypatch.setattr(run, "fetch_read_only", fetch)
    return fetched


def test_mcp_mode_saves_the_servers_tools_and_records_the_mode(stack, flow_mcp, capsys):
    run.main(["--scenario", "004*", "--model", "haiku", "--mode", "mcp"])
    run_dir, = (stack / "runs").iterdir()
    assert flow_mcp == [("http://localhost:8019/mcp", TOKEN)]
    assert json.loads((run_dir / "tools.json").read_text()) == READ_ONLY
    assert json.loads((run_dir / "summary.json").read_text())["mode"] == "mcp"
    assert f"mcp mode, {run_dir}" in capsys.readouterr().out


def test_skill_mode_is_the_default_and_fetches_no_tools(stack, flow_mcp, capsys):
    run.main(["--scenario", "004*", "--model", "haiku"])
    run_dir, = (stack / "runs").iterdir()
    assert flow_mcp == []
    assert not (run_dir / "tools.json").exists()
    assert json.loads((run_dir / "summary.json").read_text())["mode"] == "skill"
    assert f"skill mode, {run_dir}" in capsys.readouterr().out


def _flow_tool_transcript(path, tool):
    events = [{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": tool, "input": {}}]}},
              {"type": "result", "result": "You own 7 files.", "num_turns": 2, "usage": {}}]
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")


@pytest.mark.parametrize(("tool", "writes"), [("mcp__flow__update_sample", True), ("mcp__flow__list_samples", False)])
def test_regrade_of_an_mcp_run_judges_writes_by_its_saved_tools(stack, flow_mcp, tool, writes):
    (stack / "scenarios" / "004-data-i-own.json").write_text(json.dumps({**SCENARIO, "checks": {"no_write_calls": True}}))
    run.main(["--scenario", "004*", "--model", "haiku", "--mode", "mcp"])
    run_dir, = (stack / "runs").iterdir()
    _flow_tool_transcript(run_dir / "004-data-i-own-haiku.jsonl", tool)
    run.main(["--regrade", str(run_dir)])
    row, = _summary(run_dir)
    assert row["items"][0]["passed"] is not writes


def test_regrade_drops_the_other_modes_items_by_the_runs_mode(stack, flow_mcp):
    skill_only = {"item": "reads via flow-cli", "only": "skill"}
    (stack / "scenarios" / "004-data-i-own.json").write_text(
        json.dumps({**SCENARIO, "expected_behavior": [skill_only, "reads only"]}))
    run.main(["--scenario", "004*", "--model", "haiku", "--mode", "mcp"])
    run_dir, = (stack / "runs").iterdir()
    run.main(["--regrade", str(run_dir)])
    assert [r["item"] for r in _summary(run_dir)[0]["items"]] == ["answer contains owned_count", "reads only"]


def test_regrade_of_a_run_without_a_mode_grades_it_as_skill_mode(stack):
    run.main(["--scenario", "004*", "--model", "haiku"])
    run_dir, = (stack / "runs").iterdir()
    summary = json.loads((run_dir / "summary.json").read_text())
    (run_dir / "summary.json").write_text(json.dumps({"runs": summary["runs"]}))
    assert run.main(["--regrade", str(run_dir)]) == 0
    assert json.loads((run_dir / "summary.json").read_text())["mode"] == "skill"
