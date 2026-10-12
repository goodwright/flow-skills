from flow_evals.compare import gate_failures, model_totals


def _row(model, passed, total, tokens, scenario="004", completed=True):
    return {"scenario": scenario, "model": model, "passed": passed, "total": total,
            "input_tokens": tokens, "output_tokens": 0, "completed": completed}


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


def test_gate_fails_when_the_runs_cover_different_scenarios():
    before = [_row("haiku", 1, 2, 100), _row("haiku", 1, 2, 100, "019")]
    after = [_row("haiku", 2, 2, 50)]
    assert any("019" in f for f in gate_failures(before, after))


def test_gate_fails_on_an_unfinished_after_run():
    before = [_row("haiku", 0, 2, 100)]
    after = [_row("haiku", 0, 2, 0, completed=False)]
    assert any("did not finish" in f for f in gate_failures(before, after))


def test_gate_tolerates_a_model_with_no_items():
    assert gate_failures([_row("haiku", 0, 0, 10)], [_row("haiku", 0, 0, 10)]) == []
