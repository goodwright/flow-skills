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
