import json
from pathlib import Path

import pytest

from flow_evals.transcript import read_transcript

RUNNER = "flow-cli"


def _bash(command: str) -> dict:
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": command}}]}}


def _result(answer: str) -> dict:
    return {"type": "result", "result": answer, "num_turns": 3, "usage": {
        "input_tokens": 10, "cache_creation_input_tokens": 100,
        "cache_read_input_tokens": 1000, "output_tokens": 50}}


def _write(tmp_path: Path, events: list[dict]) -> Path:
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    return path


def test_reads_answer_tokens_and_turns(tmp_path):
    answer = "You own 7 files."
    transcript = read_transcript(_write(tmp_path, [_result(answer)]))
    assert transcript.answer == answer
    assert transcript.input_tokens == 1110
    assert transcript.output_tokens == 50
    assert transcript.turns == 3


def test_lists_flow_paths_in_call_order(tmp_path):
    events = [
        _bash(f"{RUNNER} api get /me --json | jq -r '.id'"),
        _bash(f"( {RUNNER} api get /v2/reference/data; {RUNNER} api get /v2/data --param count=100 --json )"),
        _result("x"),
    ]
    assert read_transcript(_write(tmp_path, events)).flow_paths == ["/me", "/v2/reference/data", "/v2/data"]


def test_flags_flowbio_commands_other_than_api_get_as_writes(tmp_path):
    upload = f"{RUNNER} data upload /tmp/x.tsv --json"
    events = [_bash(f"{RUNNER} api get /me --json"), _bash(upload), _bash("flowbio --version"), _result("x")]
    assert read_transcript(_write(tmp_path, events)).write_calls == [upload]


def test_flags_flow_cli_commands_other_than_api_get_as_writes(tmp_path):
    run = "printf '%s' '{}' | flow-cli api post /pipelines/versions/1/run --body - --json"
    events = [_bash("flow-cli api get /me --json | jq -r '.id'"), _bash(run), _result("x")]
    transcript = read_transcript(_write(tmp_path, events))
    assert transcript.write_calls == [run]
    assert transcript.flow_paths == ["/me"]


def test_flags_mutating_curl_as_write(tmp_path):
    patch = "curl -X PATCH http://localhost:8019/v2/data/1 -d '{}'"
    events = [_bash("curl -s http://localhost:8019/me"), _bash(patch), _result("x")]
    assert read_transcript(_write(tmp_path, events)).write_calls == [patch]


def test_run_without_result_line_has_empty_answer(tmp_path):
    transcript = read_transcript(_write(tmp_path, [_bash(f"{RUNNER} api get /me --json")]))
    assert transcript.answer == ""
    assert transcript.flow_paths == ["/me"]
    assert transcript.turns == 0


def test_ignores_non_json_lines(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text("Error: boom\n" + json.dumps(_result("ok")) + "\n")
    assert read_transcript(path).answer == "ok"


def test_flags_the_skills_multi_line_pipeline_run_as_write(tmp_path):
    run = ('curl -sS --fail-with-body \\\n  -H "Authorization: Bearer $(< ~/.config/flow/api-token)" \\\n'
           '  -H "Content-Type: application/json" \\\n  -X POST "$FLOW_API_URL/pipelines/versions/7/run" \\\n'
           "  --data '{\"params\": {}}'")
    assert read_transcript(_write(tmp_path, [_bash(run), _result("x")])).write_calls == [run]


@pytest.mark.parametrize("command", [
    "curl --request DELETE http://localhost:8019/v2/data/1",
    "curl -d@body.json http://localhost:8019/v2/data/1",
    "curl --json '{}' http://localhost:8019/v2/data/1",
    "uvx --from flowbio==0.14.1 flowbio \\\n  data upload /tmp/x.tsv --json",
])
def test_flags_other_write_shapes(tmp_path, command):
    assert read_transcript(_write(tmp_path, [_bash(command), _result("x")])).write_calls == [command]


def test_run_with_a_result_line_is_completed(tmp_path):
    assert read_transcript(_write(tmp_path, [_result("ok")])).completed is True


def test_run_without_result_line_is_not_completed(tmp_path):
    assert read_transcript(_write(tmp_path, [_bash("jq .")])).completed is False
