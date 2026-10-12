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
                      input_tokens=0, output_tokens=0, turns=0, completed=True)


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


def test_excludes_list_fails_when_any_element_is_mentioned():
    assert _passed({"answer_excludes": ["run_output_filenames"]}, "only counts.tsv") == [False]
