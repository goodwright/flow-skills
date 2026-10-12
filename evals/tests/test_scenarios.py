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
