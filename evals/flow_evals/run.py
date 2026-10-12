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
        score = f"{r['passed']}/{r['total']}"
        lines.append(f"{r['scenario']:<32} {r['model']:<28} {score:>7} {r['flow_calls']:>5} "
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
