import dataclasses
import json

import pytest

from flow_evals.checks import ItemResult
from flow_evals.run import format_table, grade, load_scenario, select_scenarios, summarise
from flow_evals.transcript import Transcript

EXPECTED = {"owned_count": 7}
TRANSCRIPT = Transcript(answer="7 files", commands=[], flow_paths=["/me", "/v2/data"], write_calls=[],
                        input_tokens=1000, output_tokens=200, turns=4, completed=True)


def _scenarios(tmp_path, names):
    for name in names:
        (tmp_path / f"{name}.json").write_text(json.dumps({"query": "q", "expected_behavior": []}))
    return tmp_path


def test_select_matches_globs_on_stem_in_order(tmp_path):
    folder = _scenarios(tmp_path, ["004-data-i-own", "019-deleted", "020-download", "001-samples"])
    assert [p.stem for p in select_scenarios(folder, ["004*", "02*"])] == ["004-data-i-own", "020-download"]


def test_select_stops_when_nothing_matches(tmp_path):
    with pytest.raises(SystemExit, match="999"):
        select_scenarios(_scenarios(tmp_path, ["004-data-i-own"]), ["999*"])


def test_load_stops_on_unknown_check_key(tmp_path):
    path = tmp_path / "004-x.json"
    path.write_text(json.dumps({"query": "q", "checks": {"answer_contains": ["nope"]}}))
    with pytest.raises(SystemExit, match="004-x.*nope"):
        load_scenario(path, EXPECTED)


def test_grade_runs_checks_then_rubric():
    scenario = {"checks": {"answer_contains": ["owned_count"]}, "expected_behavior": ["reads only"]}
    ask = lambda argv: json.dumps({"structured_output": {"items": [{"pass": False, "reason": "r"}]}})
    assert [(r.source, r.passed) for r in grade(scenario, EXPECTED, TRANSCRIPT, ask)] == [("check", True), ("rubric", False)]


def test_summarise_counts_passes_and_carries_metrics():
    results = [ItemResult("a", True, "check", ""), ItemResult("b", False, "rubric", "")]
    row = summarise("004", "haiku", results, TRANSCRIPT)
    assert (row["passed"], row["total"], row["pass_rate"]) == (1, 2, 0.5)
    assert (row["flow_calls"], row["flow_paths"]) == (2, TRANSCRIPT.flow_paths)
    assert (row["input_tokens"], row["output_tokens"], row["turns"]) == (1000, 200, 4)


def test_table_has_a_line_per_row():
    row = summarise("004", "haiku", [ItemResult("a", True, "check", "")], TRANSCRIPT)
    lines = format_table([row, {**row, "model": "opus"}]).splitlines()
    assert "scenario" in lines[0] and len(lines) == 4
    assert "004" in lines[2] and "1/1" in lines[2]


def test_grade_fails_every_item_of_a_run_that_never_finished_without_asking_the_grader():
    scenario = {"checks": {"answer_excludes": ["owned_count"], "no_write_calls": True},
                "expected_behavior": ["reads only"]}
    unfinished = dataclasses.replace(TRANSCRIPT, answer="", completed=False)

    def ask(argv):
        raise AssertionError("grader called for an unfinished run")
    results = grade(scenario, EXPECTED, unfinished, ask)
    assert [r.passed for r in results] == [False, False, False]
    assert all("no result" in r.reason for r in results)


def test_summarise_records_whether_the_run_finished():
    assert summarise("004", "haiku", [], TRANSCRIPT)["completed"] is True
