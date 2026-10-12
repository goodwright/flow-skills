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
