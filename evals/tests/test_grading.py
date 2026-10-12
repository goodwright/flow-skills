import json
import subprocess

from flow_evals.grading import GRADER_MODEL, grade_rubric
from flow_evals.transcript import Transcript

ITEMS = ["says files were counted", "reads only"]
TRANSCRIPT = Transcript(answer="You own 7 files.", commands=["flowbio api get /me --json"], flow_paths=["/me"],
                        write_calls=[], input_tokens=0, output_tokens=0, turns=0, completed=True)


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


def test_grader_timeout_fails_every_item():
    def ask(argv: list[str]) -> str:
        raise subprocess.TimeoutExpired(argv, 600)
    results = grade_rubric(ITEMS, TRANSCRIPT, ask)
    assert [r.passed for r in results] == [False, False]
    assert all("grader" in r.reason for r in results)
