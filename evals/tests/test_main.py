import json
import os

import pytest

from flow_evals import compare, run

FAKE_CLAUDE = """#!/usr/bin/env python3
import json, sys
if "--json-schema" in sys.argv:
    print(json.dumps({"structured_output": {"items": [{"pass": True, "reason": "fine"}]}}))
else:
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
