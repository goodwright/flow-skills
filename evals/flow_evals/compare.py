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
    failures = _coverage_failures(before, after)
    after_totals = model_totals(after)
    for model, b in model_totals(before).items():
        a = after_totals.get(model)
        if a is None:
            failures.append(f"{model}: missing from the after run")
            continue
        if _rate(a) < _rate(b):
            failures.append(f"{model}: pass rate fell from {b['passed']}/{b['total']} to {a['passed']}/{a['total']}")
        if a["tokens"] > b["tokens"]:
            failures.append(f"{model}: tokens rose from {b['tokens']} to {a['tokens']}")
    return failures


def _coverage_failures(before: list[dict], after: list[dict]) -> list[str]:
    """Totals only compare like with like when both runs hold the same, finished, scenario-model pairs."""
    before_keys = {(r["scenario"], r["model"]) for r in before}
    after_keys = {(r["scenario"], r["model"]) for r in after}
    failures = [f"{s} on {m}: only in the before run" for s, m in sorted(before_keys - after_keys)]
    failures += [f"{s} on {m}: only in the after run" for s, m in sorted(after_keys - before_keys)]
    failures += [f"{r['scenario']} on {r['model']}: did not finish in the after run"
                 for r in after if not r.get("completed", True)]
    return failures


def _rate(totals: dict) -> float:
    return totals["passed"] / totals["total"] if totals["total"] else 0.0


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
        before_pass = f"{b['passed']}/{b['total']}"
        after_pass = f"{a['passed']}/{a['total']}" if a else "-"
        after_tokens = a["input_tokens"] + a["output_tokens"] if a else "-"
        print(f"{b['scenario']:<32} {b['model']:<28} {before_pass:>7} {after_pass:>7} "
              f"{b['input_tokens'] + b['output_tokens']:>11} {after_tokens:>10}")

    failures = gate_failures(before, after)
    print("\n" + ("\n".join(failures) if failures else "gate: pass"))
    return 1 if failures else 0
