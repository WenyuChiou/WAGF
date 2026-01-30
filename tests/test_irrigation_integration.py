import json

from examples.multi_agent.irrigation_abm.run_experiment import _apply_skill, _parse_decision


def test_parse_decision_extracts_magnitude():
    payload = {
        "water_threat_appraisal": {"label": "H", "reason": ""},
        "water_coping_appraisal": {"label": "M", "reason": ""},
        "decision": "1",
        "magnitude": 15,
        "reasoning": "",
    }
    raw = "<<<DECISION_START>>>\n" + json.dumps(payload) + "\n<<<DECISION_END>>>"
    result = _parse_decision(raw)
    assert result["magnitude"] == 15
    assert result["skill"] == "increase_demand"


def test_apply_skill_uses_magnitude_percent():
    # 15% of 100k = 15k increase
    new_request = _apply_skill("increase_demand", 50_000, 100_000, magnitude_pct=15)
    assert new_request == 65_000
