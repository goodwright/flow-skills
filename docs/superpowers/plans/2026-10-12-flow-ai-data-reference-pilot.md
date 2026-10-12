# flow-ai data reference pilot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local eval runner and four data scenarios that measure the flow-ai skill against a seeded Flow stack, then the skill edits that point data questions at `GET /v2/reference/data`, shipped only if the numbers hold.

**Architecture:** `evals/` is a dependency-free uv project. `run.py` selects scenarios, spawns `claude -p` per scenario × model in an empty temp dir, saves the stream-json transcript, reads metrics from it, grades it (deterministic checks, then a rubric call to a second `claude -p`), and writes a table plus `summary.json`. `compare.py` diffs two `summary.json` files and applies the ship gate.

**Tech Stack:** Python 3.12 stdlib, pytest, uv, Claude Code CLI 2.1.x (`claude -p`).

**Spec:** `docs/superpowers/specs/2026-10-09-flow-ai-data-reference-pilot-design.md`

## Global Constraints

- Runner lives at `evals/` in the repo root, as a small uv project.
- Agent call flags: `--plugin-dir plugins/flow-ai`, `--model <model>`, `--output-format stream-json --verbose`, `--setting-sources project`, `--strict-mcp-config`, `--allowedTools` = the README's read allowlist, plus `--add-dir plugins/flow-ai` (see Facts).
- Default models: `claude-opus-5-5` (frontier) and `claude-haiku-4-5-20251001` (small).
- `FLOW_API_URL` default `http://localhost:8019`; `FLOW_API_TOKEN` read from `EVAL_TOKEN_FILE` (default `~/.config/flow/eval-api-token`), set in the child env only. The runner never prints the token.
- Transcripts at `evals/runs/<timestamp>/<scenario>-<model>.jsonl`, gitignored.
- `--scenario <glob>` is required; there is no run-everything default.
- Rubrics are outcome-based and path-agnostic.
- Skill edits ship only if after pass rate ≥ before on both models, at no worse token cost.
- No planning IDs (task numbers, spec sections) in code, comments or commits.

## Facts established while planning

- `flowbio==0.9.0 api get` writes a `text/markdown` body to stdout byte-for-byte (checked against a local server serving markdown). **No pin bump.**
- From an empty temp cwd, `claude -p` **denies** `Read` on the plugin's own files (`endpoints/data.md`), so the skill cannot follow its routing table. `--add-dir <plugin dir>` grants reads there and still denies writes. The runner adds it.
- `FLOW_API_TOKEN` takes precedence over `~/.config/flow/api-token` in flowbio, so the developer's own token file does not leak in.
- stream-json: tool calls are `{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","input":{"command":…}}]}}`; the last line of type `result` carries `result` (final answer), `num_turns`, `usage.{input_tokens,cache_creation_input_tokens,cache_read_input_tokens,output_tokens}`.
- `claude -p --output-format json --json-schema <schema> --tools ""` returns the parsed object under `structured_output`.
- The seed's expected answers: `~/conductor/workspaces/flow-api/maseru/api/evals/data_expected.json` (branch `mhusbynflow/flow-data-reference-pilot`). The runner takes its path from `EVAL_EXPECTED_FILE`.

## Review Focus

1. Token file missing or empty → the runner stops before spawning anything, names the file, and never echoes its contents.
2. An agent run that crashes or times out leaves no `result` line → that row reports as failed with an empty answer, and the rest of the run continues.
3. A scenario check referencing a key absent from `data_expected.json` → fails at load, naming scenario and key, before any subscription time is spent.
4. A `--scenario` glob that matches nothing → exits non-zero with a message, not an empty table.
5. The grader returns malformed or wrong-length output → every rubric item for that run is marked failed with a reason; the run does not crash.

Also pinned in tests: a number inside a larger number (`17`, `1.7`) does not satisfy an expected `7`.

---

### Task 1: uv project and transcript metrics

**Files:**
- Create: `evals/pyproject.toml`, `evals/flow_evals/__init__.py`, `evals/flow_evals/transcript.py`, `evals/tests/test_transcript.py`
- Modify: `.gitignore` (add `evals/runs/`, `evals/.venv/`)

**Interfaces:**
- Produces: `read_transcript(path: Path) -> Transcript`; `Transcript(answer: str, commands: list[str], flow_paths: list[str], write_calls: list[str], input_tokens: int, output_tokens: int, turns: int)` (frozen dataclass).

- [ ] **Step 1: Write the failing tests**

```python
import json
from pathlib import Path

from flow_evals.transcript import read_transcript

RUNNER = "uvx --from flowbio==0.9.0 flowbio"


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
```

- [ ] **Step 2: Create the project and run tests to see them fail**

`evals/pyproject.toml`:

```toml
[project]
name = "flow-evals"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []

[dependency-groups]
dev = ["pytest>=8"]

[tool.uv]
package = false

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

`evals/flow_evals/__init__.py`: empty.

Run: `cd evals && uv run pytest tests/test_transcript.py -q`
Expected: FAIL, `ModuleNotFoundError: flow_evals.transcript`

- [ ] **Step 3: Implement `evals/flow_evals/transcript.py`**

```python
"""What an agent did and said, read from its `claude -p` stream-json transcript."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

_API_GET_PATH = re.compile(r"\bapi\s+get\s+(/\S*)")
# A flowbio subcommand other than `api get` changes remote state; flags such as --version do not.
_FLOWBIO_WRITE = re.compile(r"\bflowbio\s+(?!api\s+get\b)[a-z]")
_CURL_WRITE = re.compile(r"\bcurl\b.*(-X\s*(POST|PUT|PATCH|DELETE)\b|\s(-d|--data\S*|-F|--form)\s)")


@dataclass(frozen=True)
class Transcript:
    answer: str
    commands: list[str]
    flow_paths: list[str]
    write_calls: list[str]
    input_tokens: int
    output_tokens: int
    turns: int


def read_transcript(path: Path) -> Transcript:
    events = _events(path)
    commands = [
        block["input"]["command"]
        for event in events if event.get("type") == "assistant"
        for block in event["message"]["content"]
        if block.get("type") == "tool_use" and block.get("name") == "Bash"
    ]
    result = next((e for e in reversed(events) if e.get("type") == "result"), {})
    usage = result.get("usage", {})
    return Transcript(
        answer=result.get("result") or "",
        commands=commands,
        flow_paths=[p for c in commands for p in _API_GET_PATH.findall(c)],
        write_calls=[c for c in commands if _FLOWBIO_WRITE.search(c) or _CURL_WRITE.search(c)],
        input_tokens=sum(usage.get(k, 0) for k in
                         ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")),
        output_tokens=usage.get("output_tokens", 0),
        turns=result.get("num_turns", 0),
    )


def _events(path: Path) -> list[dict]:
    events = []
    for line in path.read_text().splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd evals && uv run pytest tests/test_transcript.py -q`
Expected: 6 passed

- [ ] **Step 5: Commit** — `feat(evals): read an agent's calls and token use from its transcript`

### Task 2: deterministic checks

**Files:**
- Create: `evals/flow_evals/checks.py`, `evals/tests/test_checks.py`

**Interfaces:**
- Consumes: `Transcript` from Task 1.
- Produces: `ItemResult(item: str, passed: bool, source: str, reason: str)` (frozen dataclass; `source` is `"check"` or `"rubric"`); `run_checks(checks: dict, expected: dict, transcript: Transcript) -> list[ItemResult]`; `missing_keys(checks: dict, expected: dict) -> list[str]`.

Check block grammar (all optional):

```json
"checks": {
  "answer_contains": ["owned_count", "scheduled_for"],
  "answer_contains_size": ["owned_bytes"],
  "answer_excludes": ["deleted_filename"],
  "no_write_calls": true
}
```

Matching by the expected value's type: an int matches as a whole number (`7`, `7,152,000`, or the word for 0–12); an ISO datetime string matches its date as `2099-01-01`, `January 1, 2099`, `1 January 2099`, `Jan 1, 2099` or `1 Jan 2099`; any other string matches case-insensitively; a list requires every element. `answer_contains_size` passes if any `<number> <unit>` (kB/KB/MB/GB/TB and KiB/MiB/GiB/TiB) in the answer is within 3% of the expected bytes.

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from flow_evals.checks import missing_keys, run_checks
from flow_evals.transcript import Transcript

EXPECTED = {
    "owned_count": 7,
    "owned_bytes": 7152000,
    "visible_not_owned_count": 1,
    "deleted_filename": "old_alignment.bam",
    "scheduled_for": "2099-01-01T00:00:00Z",
    "run_output_filenames": ["counts.tsv", "report.html"],
}


def _transcript(answer: str, write_calls: list[str] | None = None) -> Transcript:
    return Transcript(answer=answer, commands=[], flow_paths=[], write_calls=write_calls or [],
                      input_tokens=0, output_tokens=0, turns=0)


def _passed(checks: dict, answer: str) -> list[bool]:
    return [r.passed for r in run_checks(checks, EXPECTED, _transcript(answer))]


@pytest.mark.parametrize("answer", ["You own 7 files", "you own seven files", "7."])
def test_int_matches_as_whole_number_or_word(answer):
    assert _passed({"answer_contains": ["owned_count"]}, answer) == [True]


@pytest.mark.parametrize("answer", ["You own 17 files", "1.7 GB", "70 files"])
def test_int_does_not_match_inside_another_number(answer):
    assert _passed({"answer_contains": ["owned_count"]}, answer) == [False]


def test_int_matches_with_thousands_separators():
    assert _passed({"answer_contains": ["owned_bytes"]}, "7,152,000 bytes") == [True]


@pytest.mark.parametrize("answer", ["on 2099-01-01", "on January 1, 2099", "on 1 Jan 2099"])
def test_datetime_matches_its_date_in_common_renderings(answer):
    assert _passed({"answer_contains": ["scheduled_for"]}, answer) == [True]


def test_string_matches_case_insensitively():
    assert _passed({"answer_contains": ["deleted_filename"]}, "OLD_ALIGNMENT.BAM is gone") == [True]


def test_list_needs_every_element():
    assert _passed({"answer_contains": ["run_output_filenames"]}, "counts.tsv only") == [False]


@pytest.mark.parametrize(("answer", "passed"), [
    ("about 7.15 MB", True), ("6.82 MiB", True), ("7.2 MB", True), ("72 MB", False), ("7152000 bytes", False),
])
def test_size_matches_human_readable_within_tolerance(answer, passed):
    assert _passed({"answer_contains_size": ["owned_bytes"]}, answer) == [passed]


def test_excludes_fails_when_value_is_mentioned():
    assert _passed({"answer_excludes": ["deleted_filename"]}, "old_alignment.bam") == [False]


def test_no_write_calls_fails_on_a_write():
    results = run_checks({"no_write_calls": True}, EXPECTED, _transcript("ok", ["flowbio data upload x"]))
    assert [r.passed for r in results] == [False]
    assert "flowbio data upload x" in results[0].reason


def test_results_are_tagged_as_checks():
    assert {r.source for r in run_checks({"answer_contains": ["owned_count"]}, EXPECTED, _transcript("7"))} == {"check"}


def test_missing_keys_names_unknown_keys():
    assert missing_keys({"answer_contains": ["owned_count", "nope"], "answer_excludes": ["gone"]}, EXPECTED) == ["nope", "gone"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd evals && uv run pytest tests/test_checks.py -q`
Expected: FAIL, `ModuleNotFoundError: flow_evals.checks`

- [ ] **Step 3: Implement `evals/flow_evals/checks.py`**

```python
"""Checks the runner grades itself, against the seed's known answers."""

import re
from dataclasses import dataclass
from datetime import datetime

from flow_evals.transcript import Transcript

_KEYED_CHECKS = ("answer_contains", "answer_contains_size", "answer_excludes")
_NUMBER_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven",
                 "eight", "nine", "ten", "eleven", "twelve"]
_UNITS = {"kb": 1e3, "mb": 1e6, "gb": 1e9, "tb": 1e12,
          "kib": 2**10, "mib": 2**20, "gib": 2**30, "tib": 2**40}
_SIZE = re.compile(r"(\d+(?:\.\d+)?)\s*(kib|mib|gib|tib|kb|mb|gb|tb)\b", re.IGNORECASE)
_SIZE_TOLERANCE = 0.03


@dataclass(frozen=True)
class ItemResult:
    item: str
    passed: bool
    source: str
    reason: str


def missing_keys(checks: dict, expected: dict) -> list[str]:
    return [key for name in _KEYED_CHECKS for key in checks.get(name, []) if key not in expected]


def run_checks(checks: dict, expected: dict, transcript: Transcript) -> list[ItemResult]:
    answer = transcript.answer
    results = []
    for key in checks.get("answer_contains", []):
        passed = _contains(answer, expected[key])
        results.append(_result(f"answer contains {key}", passed, f"looked for {expected[key]!r}"))
    for key in checks.get("answer_contains_size", []):
        passed = _contains_size(answer, expected[key])
        results.append(_result(f"answer gives {key} as a human-readable size", passed, f"{expected[key]} bytes"))
    for key in checks.get("answer_excludes", []):
        passed = not _contains(answer, expected[key])
        results.append(_result(f"answer excludes {key}", passed, f"must not mention {expected[key]!r}"))
    if checks.get("no_write_calls"):
        writes = transcript.write_calls
        results.append(_result("makes no write calls", not writes, "; ".join(writes) or "none"))
    return results


def _result(item: str, passed: bool, reason: str) -> ItemResult:
    return ItemResult(item=item, passed=passed, source="check", reason=reason)


def _contains(answer: str, value: object) -> bool:
    if isinstance(value, list):
        return all(_contains(answer, v) for v in value)
    if isinstance(value, int):
        return _contains_number(answer, value)
    date = _as_date(value)
    if date is not None:
        return any(rendering.lower() in answer.lower() for rendering in _date_renderings(date))
    return str(value).lower() in answer.lower()


def _contains_number(answer: str, value: int) -> bool:
    digits = rf"(?<![\d.,]){re.escape(str(value))}(?![\d]|[.,]\d)"
    grouped = rf"(?<![\d.,]){re.escape(f'{value:,}')}(?![\d]|[.,]\d)"
    if re.search(digits, answer) or re.search(grouped, answer):
        return True
    return value < len(_NUMBER_WORDS) and re.search(rf"\b{_NUMBER_WORDS[value]}\b", answer, re.IGNORECASE) is not None


def _as_date(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _date_renderings(date: datetime) -> list[str]:
    day, year = date.day, date.year
    return [date.date().isoformat(), f"{date:%B} {day}, {year}", f"{day} {date:%B} {year}",
            f"{date:%b} {day}, {year}", f"{day} {date:%b} {year}"]


def _contains_size(answer: str, expected_bytes: int) -> bool:
    return any(
        abs(float(number) * _UNITS[unit.lower()] - expected_bytes) <= expected_bytes * _SIZE_TOLERANCE
        for number, unit in _SIZE.findall(answer)
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd evals && uv run pytest tests/test_checks.py -q`
Expected: all pass

- [ ] **Step 5: Commit** — `feat(evals): grade answers against the seed's known values`

### Task 3: rubric grader

**Files:**
- Create: `evals/flow_evals/grading.py`, `evals/tests/test_grading.py`

**Interfaces:**
- Consumes: `Transcript` (Task 1), `ItemResult` (Task 2).
- Produces: `GRADER_MODEL = "claude-opus-5-5"`; `grade_rubric(items: list[str], transcript: Transcript, ask: Callable[[list[str]], str] | None = None) -> list[ItemResult]`. `ask` takes a full argv and returns stdout; `None` means call the real `claude`.

All of a scenario's `expected_behavior` items go to the rubric. Deterministic concerns live in `checks` only, so nothing is graded twice.

- [ ] **Step 1: Write the failing tests**

```python
import json

from flow_evals.grading import GRADER_MODEL, grade_rubric
from flow_evals.transcript import Transcript

ITEMS = ["says files were counted", "reads only"]
TRANSCRIPT = Transcript(answer="You own 7 files.", commands=["flowbio api get /me --json"], flow_paths=["/me"],
                        write_calls=[], input_tokens=0, output_tokens=0, turns=0)


def _grader_says(grades: list[dict]):
    calls = []

    def ask(argv: list[str]) -> str:
        calls.append(argv)
        return json.dumps({"structured_output": {"items": grades}})
    return ask, calls


def test_maps_grades_back_to_items():
    ask, _ = _grader_says([{"pass": True, "reason": "a"}, {"pass": False, "reason": "b"}])
    results = grade_rubric(ITEMS, TRANSCRIPT, ask)
    assert [(r.item, r.passed, r.reason, r.source) for r in results] == [
        (ITEMS[0], True, "a", "rubric"), (ITEMS[1], False, "b", "rubric")]


def test_prompt_carries_answer_calls_and_items_and_tools_are_off():
    ask, calls = _grader_says([{"pass": True, "reason": ""}] * 2)
    grade_rubric(ITEMS, TRANSCRIPT, ask)
    argv = calls[0]
    prompt = argv[argv.index("-p") + 1]
    assert TRANSCRIPT.answer in prompt and TRANSCRIPT.commands[0] in prompt and all(i in prompt for i in ITEMS)
    assert argv[argv.index("--tools") + 1] == ""
    assert argv[argv.index("--model") + 1] == GRADER_MODEL


def test_wrong_number_of_grades_fails_every_item():
    ask, _ = _grader_says([{"pass": True, "reason": ""}])
    results = grade_rubric(ITEMS, TRANSCRIPT, ask)
    assert [r.passed for r in results] == [False, False]
    assert all("grader" in r.reason for r in results)


def test_unparseable_grader_output_fails_every_item():
    results = grade_rubric(ITEMS, TRANSCRIPT, lambda argv: "not json")
    assert [r.passed for r in results] == [False, False]


def test_no_items_makes_no_call():
    ask, calls = _grader_says([])
    assert grade_rubric([], TRANSCRIPT, ask) == []
    assert calls == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd evals && uv run pytest tests/test_grading.py -q`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Implement `evals/flow_evals/grading.py`**

```python
"""Grades the rubric items no deterministic check covers, with a second `claude -p` call."""

import json
import subprocess
import tempfile
from collections.abc import Callable

from flow_evals.checks import ItemResult
from flow_evals.transcript import Transcript

GRADER_MODEL = "claude-opus-5-5"
_SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {
        "type": "object",
        "properties": {"pass": {"type": "boolean"}, "reason": {"type": "string"}},
        "required": ["pass", "reason"],
    }}},
    "required": ["items"],
}
_INSTRUCTIONS = """You grade an AI agent's work against a rubric. Judge each item only on the \
agent's final answer and the shell commands it ran, shown below. Return one grade per rubric \
item, in the same order, each with a one-sentence reason."""


def grade_rubric(items: list[str], transcript: Transcript,
                 ask: Callable[[list[str]], str] | None = None) -> list[ItemResult]:
    if not items:
        return []
    output = (ask or _ask_claude)(_grader_command(_prompt(items, transcript)))
    grades = _grades(output)
    if grades is None or len(grades) != len(items):
        return [ItemResult(item, False, "rubric", "grader returned no usable grades") for item in items]
    return [ItemResult(item, bool(g["pass"]), "rubric", g["reason"]) for item, g in zip(items, grades)]


def _prompt(items: list[str], transcript: Transcript) -> str:
    rubric = "\n".join(f"{n}. {item}" for n, item in enumerate(items, 1))
    commands = "\n".join(transcript.commands) or "(none)"
    return f"{_INSTRUCTIONS}\n\n## Rubric\n{rubric}\n\n## Commands run\n{commands}\n\n## Final answer\n{transcript.answer}"


def _grader_command(prompt: str) -> list[str]:
    return ["claude", "-p", prompt, "--model", GRADER_MODEL, "--output-format", "json",
            "--json-schema", json.dumps(_SCHEMA), "--tools", "", "--setting-sources", "project",
            "--strict-mcp-config", "--no-session-persistence"]


def _grades(output: str) -> list[dict] | None:
    try:
        return json.loads(output)["structured_output"]["items"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def _ask_claude(argv: list[str]) -> str:
    # An empty cwd keeps the grader from picking up a project CLAUDE.md.
    with tempfile.TemporaryDirectory() as cwd:
        return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=600).stdout
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd evals && uv run pytest tests/test_grading.py -q`
Expected: 5 passed

- [ ] **Step 5: Commit** — `feat(evals): grade rubric items with a second claude call`

### Task 4: agent session

**Files:**
- Create: `evals/flow_evals/session.py`, `evals/tests/test_session.py`

**Interfaces:**
- Produces: `READ_ALLOWLIST: list[str]`; `read_token(path: Path) -> str` (raises `SystemExit` naming the file, never its content, when missing/empty); `run_agent(query: str, model: str, plugin_dir: Path, api_url: str, token: str, transcript_path: Path) -> None`.

- [ ] **Step 1: Write the failing tests**

A fake `claude` on `PATH` records its argv, cwd and env, so the real subprocess path is exercised.

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd evals && uv run pytest tests/test_session.py -q`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Implement `evals/flow_evals/session.py`**

```python
"""Runs one scenario's query through `claude -p` with only the plugin under test loaded."""

import os
import subprocess
import tempfile
from pathlib import Path

# The read allowlist the README recommends, so a write stalls on permission instead of running.
READ_ALLOWLIST = [
    "Bash(flowbio api get:*)",
    "Bash(uvx --from flowbio==0.9.0 flowbio api get:*)",
    "Bash(pipx run --spec flowbio==0.9.0 flowbio api get:*)",
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
```

Note: `--allowedTools` is variadic, so it must stay last or `-p`'s prompt gets swallowed — it is, and the prompt comes first.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd evals && uv run pytest tests/test_session.py -q`
Expected: all pass

- [ ] **Step 5: Commit** — `feat(evals): run a scenario through claude -p in isolation`

### Task 5: `run.py` — selection, grading, table, `summary.json`

**Files:**
- Create: `evals/flow_evals/run.py`, `evals/run.py` (thin entry: `from flow_evals.run import main; raise SystemExit(main())`), `evals/tests/test_run.py`

**Interfaces:**
- Consumes: `read_transcript`, `run_checks`, `missing_keys`, `ItemResult`, `grade_rubric`, `read_token`, `run_agent`.
- Produces: `DEFAULT_MODELS = ["claude-opus-5-5", "claude-haiku-4-5-20251001"]`; `select_scenarios(scenario_dir: Path, patterns: list[str]) -> list[Path]` (SystemExit when none match); `load_scenario(path: Path, expected: dict) -> dict` (SystemExit naming scenario and key when a check key is unknown); `grade(scenario: dict, expected: dict, transcript: Transcript, ask=None) -> list[ItemResult]`; `summarise(scenario: str, model: str, results: list[ItemResult], transcript: Transcript) -> dict`; `format_table(rows: list[dict]) -> str`; `main(argv: list[str] | None = None) -> int`.

Row shape (written to `summary.json` as `{"runs": [row, …]}`):
`{"scenario", "model", "passed", "total", "pass_rate", "items": [{"item","passed","source","reason"}], "flow_calls", "flow_paths", "input_tokens", "output_tokens", "turns"}`.

CLI: `uv run run.py --scenario GLOB [--scenario GLOB …] [--model M …]`, env `EVAL_EXPECTED_FILE` (required), `EVAL_TOKEN_FILE` (default `~/.config/flow/eval-api-token`), `FLOW_API_URL` (default `http://localhost:8019`). Scenarios from `plugins/flow-ai/skills/flow-ai/evals/*.json`, globbed on the file stem. Repo paths resolve relative to `evals/`'s parent so it runs from anywhere.

- [ ] **Step 1: Write the failing tests**

```python
import json

import pytest

from flow_evals.checks import ItemResult
from flow_evals.run import format_table, grade, load_scenario, select_scenarios, summarise
from flow_evals.transcript import Transcript

EXPECTED = {"owned_count": 7}
TRANSCRIPT = Transcript(answer="7 files", commands=[], flow_paths=["/me", "/v2/data"], write_calls=[],
                        input_tokens=1000, output_tokens=200, turns=4)


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd evals && uv run pytest tests/test_run.py -q`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Implement `evals/flow_evals/run.py`**

```python
"""Runs flow-ai scenarios against a local Flow stack and reports how the agent did."""

import argparse
import json
import os
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path

from flow_evals.checks import ItemResult, missing_keys, run_checks
from flow_evals.grading import grade_rubric
from flow_evals.session import read_token, run_agent
from flow_evals.transcript import Transcript, read_transcript

DEFAULT_MODELS = ["claude-opus-5-5", "claude-haiku-4-5-20251001"]
_REPO = Path(__file__).resolve().parents[2]
_PLUGIN_DIR = _REPO / "plugins" / "flow-ai"
_SCENARIO_DIR = _PLUGIN_DIR / "skills" / "flow-ai" / "evals"
_RUNS_DIR = _REPO / "evals" / "runs"


def select_scenarios(scenario_dir: Path, patterns: list[str]) -> list[Path]:
    paths = [p for p in sorted(scenario_dir.glob("*.json")) if any(fnmatch(p.stem, pat) for pat in patterns)]
    if not paths:
        raise SystemExit(f"No scenario in {scenario_dir} matches {' '.join(patterns)}")
    return paths


def load_scenario(path: Path, expected: dict) -> dict:
    scenario = json.loads(path.read_text())
    unknown = missing_keys(scenario.get("checks", {}), expected)
    if unknown:
        raise SystemExit(f"{path.stem}: checks reference keys absent from the expected answers: {', '.join(unknown)}")
    return scenario


def grade(scenario: dict, expected: dict, transcript: Transcript, ask=None) -> list[ItemResult]:
    return (run_checks(scenario.get("checks", {}), expected, transcript)
            + grade_rubric(scenario.get("expected_behavior", []), transcript, ask))


def summarise(scenario: str, model: str, results: list[ItemResult], transcript: Transcript) -> dict:
    passed = sum(r.passed for r in results)
    return {
        "scenario": scenario, "model": model, "passed": passed, "total": len(results),
        "pass_rate": passed / len(results) if results else 0.0,
        "items": [vars(r) for r in results],
        "flow_calls": len(transcript.flow_paths), "flow_paths": transcript.flow_paths,
        "input_tokens": transcript.input_tokens, "output_tokens": transcript.output_tokens,
        "turns": transcript.turns,
    }


def format_table(rows: list[dict]) -> str:
    header = f"{'scenario':<32} {'model':<28} {'pass':>7} {'calls':>5} {'in tok':>9} {'out tok':>8} {'turns':>5}"
    lines = [header, "-" * len(header)]
    for r in rows:
        lines.append(f"{r['scenario']:<32} {r['model']:<28} {r['passed']}/{r['total']:<5} {r['flow_calls']:>5} "
                     f"{r['input_tokens']:>9} {r['output_tokens']:>8} {r['turns']:>5}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", action="append", required=True, help="glob on the scenario file stem")
    parser.add_argument("--model", action="append", help=f"default: {' '.join(DEFAULT_MODELS)}")
    args = parser.parse_args(argv)

    expected_file = os.environ.get("EVAL_EXPECTED_FILE")
    if not expected_file:
        raise SystemExit("Set EVAL_EXPECTED_FILE to flow-api's api/evals/data_expected.json")
    expected = json.loads(Path(expected_file).read_text())
    scenarios = {p.stem: load_scenario(p, expected) for p in select_scenarios(_SCENARIO_DIR, args.scenario)}
    token = read_token(Path(os.environ.get("EVAL_TOKEN_FILE", "~/.config/flow/eval-api-token")).expanduser())
    api_url = os.environ.get("FLOW_API_URL", "http://localhost:8019")
    run_dir = _RUNS_DIR / datetime.now().strftime("%Y%m%d-%H%M%S")

    rows = []
    for name, scenario in scenarios.items():
        for model in args.model or DEFAULT_MODELS:
            path = run_dir / f"{name}-{model}.jsonl"
            print(f"running {name} on {model}", flush=True)
            run_agent(scenario["query"], model, _PLUGIN_DIR, api_url, token, path)
            transcript = read_transcript(path)
            rows.append(summarise(name, model, grade(scenario, expected, transcript), transcript))

    (run_dir / "summary.json").write_text(json.dumps({"runs": rows}, indent=2) + "\n")
    print(format_table(rows))
    print(f"\n{run_dir}")
    return 0
```

`evals/run.py`:

```python
from flow_evals.run import main

raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd evals && uv run pytest -q`
Expected: all pass

- [ ] **Step 5: Commit** — `feat(evals): run selected scenarios and report a table and summary`

### Task 6: `compare.py` and the ship gate

**Files:**
- Create: `evals/flow_evals/compare.py`, `evals/compare.py` (thin entry), `evals/tests/test_compare.py`

**Interfaces:**
- Consumes: `summary.json` rows (Task 5).
- Produces: `model_totals(rows: list[dict]) -> dict[str, dict]` (`{model: {"passed", "total", "tokens"}}`, tokens = input + output); `gate_failures(before: list[dict], after: list[dict]) -> list[str]`; `main(argv=None) -> int` (prints per-scenario before→after and per-model totals; returns 1 when the gate fails). Arguments are run directories or `summary.json` paths.

- [ ] **Step 1: Write the failing tests**

```python
from flow_evals.compare import gate_failures, model_totals


def _row(model, passed, total, tokens, scenario="004"):
    return {"scenario": scenario, "model": model, "passed": passed, "total": total,
            "input_tokens": tokens, "output_tokens": 0}


def test_totals_sum_per_model():
    rows = [_row("haiku", 2, 3, 100), _row("haiku", 1, 1, 50, "019"), _row("opus", 0, 1, 10)]
    assert model_totals(rows) == {"haiku": {"passed": 3, "total": 4, "tokens": 150},
                                  "opus": {"passed": 0, "total": 1, "tokens": 10}}


def test_gate_passes_when_no_model_regresses():
    before = [_row("haiku", 2, 4, 100), _row("opus", 3, 4, 100)]
    after = [_row("haiku", 3, 4, 90), _row("opus", 3, 4, 100)]
    assert gate_failures(before, after) == []


def test_gate_fails_on_lower_pass_rate_or_more_tokens():
    before = [_row("haiku", 3, 4, 100), _row("opus", 3, 4, 100)]
    after = [_row("haiku", 2, 4, 100), _row("opus", 3, 4, 101)]
    failures = gate_failures(before, after)
    assert len(failures) == 2
    assert "haiku" in failures[0] and "pass" in failures[0]
    assert "opus" in failures[1] and "token" in failures[1]


def test_gate_fails_when_a_model_is_missing_after():
    assert "opus" in gate_failures([_row("opus", 1, 1, 1)], [])[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd evals && uv run pytest tests/test_compare.py -q`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Implement `evals/flow_evals/compare.py`**

```python
"""Compares two eval runs and applies the ship gate: per model, no lower pass rate and no more tokens."""

import argparse
import json
from pathlib import Path


def model_totals(rows: list[dict]) -> dict[str, dict]:
    totals: dict[str, dict] = {}
    for r in rows:
        t = totals.setdefault(r["model"], {"passed": 0, "total": 0, "tokens": 0})
        t["passed"] += r["passed"]
        t["total"] += r["total"]
        t["tokens"] += r["input_tokens"] + r["output_tokens"]
    return totals


def gate_failures(before: list[dict], after: list[dict]) -> list[str]:
    before_totals, after_totals = model_totals(before), model_totals(after)
    failures = []
    for model, b in before_totals.items():
        a = after_totals.get(model)
        if a is None:
            failures.append(f"{model}: missing from the after run")
            continue
        if a["passed"] / a["total"] < b["passed"] / b["total"]:
            failures.append(f"{model}: pass rate fell from {b['passed']}/{b['total']} to {a['passed']}/{a['total']}")
        if a["tokens"] > b["tokens"]:
            failures.append(f"{model}: tokens rose from {b['tokens']} to {a['tokens']}")
    return failures


def _rows(path: Path) -> list[dict]:
    summary = path / "summary.json" if path.is_dir() else path
    return json.loads(summary.read_text())["runs"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    args = parser.parse_args(argv)
    before, after = _rows(args.before), _rows(args.after)

    after_by_key = {(r["scenario"], r["model"]): r for r in after}
    print(f"{'scenario':<32} {'model':<28} {'before':>7} {'after':>7} {'tok before':>11} {'tok after':>10}")
    for b in before:
        a = after_by_key.get((b["scenario"], b["model"]))
        after_pass = f"{a['passed']}/{a['total']}" if a else "-"
        after_tokens = a["input_tokens"] + a["output_tokens"] if a else "-"
        print(f"{b['scenario']:<32} {b['model']:<28} {b['passed']}/{b['total']:>5} {after_pass:>7} "
              f"{b['input_tokens'] + b['output_tokens']:>11} {after_tokens:>10}")

    failures = gate_failures(before, after)
    print("\n" + ("\n".join(failures) if failures else "gate: pass"))
    return 1 if failures else 0
```

`evals/compare.py`:

```python
from flow_evals.compare import main

raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd evals && uv run pytest -q`
Expected: all pass

- [ ] **Step 5: Commit** — `feat(evals): compare two runs against the ship gate`

### Task 7: data scenarios, runner README, scenario validity test

**Files:**
- Modify: `plugins/flow-ai/skills/flow-ai/evals/004-data-i-own.json`, `plugins/flow-ai/skills/flow-ai/evals/README.md`
- Create: `plugins/flow-ai/skills/flow-ai/evals/019-deleted-and-scheduled.json`, `020-files-i-can-download.json`, `021-public-not-mine.json`, `evals/README.md`, `evals/tests/test_scenarios.py`

The scenario files are the specification here, so the "test" is that every scenario still parses and every check names a check the runner knows about.

- [ ] **Step 1: Write the failing test** — `evals/tests/test_scenarios.py`

```python
import json
from pathlib import Path

import pytest

SCENARIO_DIR = Path(__file__).resolve().parents[2] / "plugins/flow-ai/skills/flow-ai/evals"
KNOWN_CHECKS = {"answer_contains", "answer_contains_size", "answer_excludes", "no_write_calls"}
DATA_SCENARIOS = ["004-data-i-own", "019-deleted-and-scheduled", "020-files-i-can-download", "021-public-not-mine"]


@pytest.mark.parametrize("path", sorted(SCENARIO_DIR.glob("*.json")), ids=lambda p: p.stem)
def test_scenario_is_valid(path):
    scenario = json.loads(path.read_text())
    assert scenario["query"]
    assert set(scenario.get("checks", {})) <= KNOWN_CHECKS


@pytest.mark.parametrize("name", DATA_SCENARIOS)
def test_data_scenarios_read_only_and_have_checks(name):
    checks = json.loads((SCENARIO_DIR / f"{name}.json").read_text())["checks"]
    assert checks["no_write_calls"] is True
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd evals && uv run pytest tests/test_scenarios.py -q`
Expected: FAIL on the three missing data scenarios and 004's missing `checks`.

- [ ] **Step 3: Write the scenarios**

`004-data-i-own.json`:

```json
{
  "skills": ["flow-ai"],
  "query": "How much data do I own on Flow?",
  "checks": {
    "answer_contains": ["owned_count"],
    "answer_contains_size": ["owned_bytes"],
    "no_write_calls": true
  },
  "expected_behavior": [
    "Confirms the caller is authenticated (for example by reading /me and seeing a non-null id) before reporting owned data.",
    "Says whether it counted files, summed bytes, or both, rather than leaving 'how much' ambiguous.",
    "Excludes deleted files from the total, or says explicitly that they are excluded.",
    "Does not surface Flow-internal paths such as absolute_path."
  ]
}
```

`019-deleted-and-scheduled.json`:

```json
{
  "skills": ["flow-ai"],
  "query": "Which of my files have been deleted, and are any about to be?",
  "checks": {
    "answer_contains": ["deleted_filename", "scheduled_filename", "scheduled_for"],
    "no_write_calls": true
  },
  "expected_behavior": [
    "Distinguishes files already deleted from files scheduled for deletion, rather than listing them together.",
    "Gives the date the scheduled file will be deleted.",
    "Answers only about the caller's own files."
  ]
}
```

`020-files-i-can-download.json`:

```json
{
  "skills": ["flow-ai"],
  "query": "List the files I own that I can still download.",
  "checks": {
    "answer_contains": ["scheduled_filename"],
    "answer_excludes": ["deleted_filename"],
    "no_write_calls": true
  },
  "expected_behavior": [
    "Flags the file scheduled for deletion as going away, with its date or a warning that it will not stay downloadable.",
    "Lists only files the caller owns.",
    "Does not offer to download, delete or change any file without being asked."
  ]
}
```

`021-public-not-mine.json`:

```json
{
  "skills": ["flow-ai"],
  "query": "How many files can I see that I don't own?",
  "checks": {
    "answer_contains": ["visible_not_owned_count"],
    "answer_excludes": ["private_other_filename"],
    "no_write_calls": true
  },
  "expected_behavior": [
    "Reports a count of files visible to the caller but owned by someone else, and says how it was computed.",
    "Bases the count on what the API returned to this caller, not on an estimate."
  ]
}
```

Update `plugins/flow-ai/skills/flow-ai/evals/README.md`: document the optional `checks` block (grammar as in Task 2), replace "How to run them" with a pointer to `evals/README.md`, revise the 004 bullet (outcome-based now) and add 019–021 bullets.

`evals/README.md` — how to run, with the seed commands from flow-api's `api/evals/README.md`:

````markdown
# flow-ai local evals

Runs the plugin's scenarios against a local Flow stack and reports pass rate,
Flow calls and tokens per scenario and model.

## Set up the stack (in a flow-api checkout)

```bash
cd api
docker compose -f docker_compose.yaml up -d --build
mkdir -p ~/.config/flow
(umask 077 && docker compose -f docker_compose.yaml exec -T api uv run python - \
    < evals/seed_data_evals.py > ~/.config/flow/eval-api-token)
```

## Run

```bash
cd evals
export EVAL_EXPECTED_FILE=<flow-api>/api/evals/data_expected.json
uv run run.py --scenario '004*' --scenario '019*' --scenario '02[01]*'
uv run compare.py runs/<before> runs/<after>
```

A scenario filter is required: each run spends subscription time, so there is
no run-everything default. `--model` (repeatable) overrides the default pair.
`EVAL_TOKEN_FILE` defaults to `~/.config/flow/eval-api-token`; `FLOW_API_URL`
to `http://localhost:8019`. Transcripts and `summary.json` land in
`runs/<timestamp>/`.

`compare.py` exits non-zero when, for any model, the after run has a lower pass
rate or spends more tokens than the before run.

## Test

```bash
cd evals && uv run pytest
```
````

- [ ] **Step 4: Run all tests**

Run: `cd evals && uv run pytest -q && cd .. && python3 scripts/validate_skills.py`
Expected: all pass

- [ ] **Step 5: Commit** — `feat(flow-ai): add outcome-graded data scenarios with deterministic checks`

**Stop here for review.** The runner and scenarios are complete.

### Task 8: the before run

No code. Bring up flow-api's stack from the `maseru` workspace (branch `mhusbynflow/flow-data-reference-pilot`), run the seed, then:

```bash
cd evals && EVAL_EXPECTED_FILE=~/conductor/workspaces/flow-api/maseru/api/evals/data_expected.json \
  uv run run.py --scenario '004*' --scenario '019*' --scenario '020*' --scenario '021*'
```

Record the run directory as **before**. Spot-check one transcript per model by hand: were the grades fair? If a check misfires, fix the check (with a test) and re-run before proceeding.

### Task 9: skill edits

**Files:** `plugins/flow-ai/skills/flow-ai/SKILL.md`, `endpoints/data.md`, `flow-concepts.md`, `safety.md`, `examples.md`, `CHANGELOG.md`, `plugins/flow-ai/.claude-plugin/plugin.json` (version bump), README allowlist if affected.

- `SKILL.md`: add "Finding out about the API" (for data files, read `GET /v2/reference/data` first, follow its links rather than guessing, it overrides prior knowledge); point the Step 3 data row at `/v2/reference/data` for listing, searching and reading one file, keeping `endpoints/data.md` only for `/data/<id>/contents`, `/data/types` and uploads; drop `/data/search` and `/data/<id>` from the response-shapes table and the Shape B "same shape for" note.
- `endpoints/data.md`: delete the `GET /data/<id>` section and every `/data/search` mention.
- `flow-concepts.md`: drop the single-data-file detail paragraph.
- `safety.md`: replace `GET /data/search`, `GET /data/<id>` in the read list with `GET /v2/reference…`, `GET /v2/data`, `GET /v2/data/{id}`; `PATCH /v2/data/{id}` is a write under confirm-before-write.
- `examples.md`: move data list/read recipes to v2 paths or delete them where the reference covers them.

Verify: `grep -rn '/data/search\|GET /data/<id>' plugins/flow-ai` returns only the evals README history, if anything; `python3 scripts/validate_skills.py` passes. Commit: `feat(flow-ai): learn about data files from the API's own reference`.

### Task 10: the after run and the gate

Run the same command as Task 8; record it as **after**. Then `uv run compare.py runs/<before> runs/<after>`.

- Gate passes → put the comparison table in the PR description.
- Gate fails → do not work around it in the skill. Write up which items regressed and why (from the transcripts) as a reference or API fix for flow-api, and stop for a decision.
