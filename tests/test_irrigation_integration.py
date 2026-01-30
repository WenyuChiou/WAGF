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


def test_build_regret_feedback_formats_shortfall():
    from examples.multi_agent.irrigation_abm.irrigation_personas import (
        build_regret_feedback,
    )

    text = build_regret_feedback(
        year=2025,
        request=120_000,
        diversion=90_000,
        drought_index=0.72,
        preceding_factor=0,
    )
    assert "Year 2025" in text
    assert "requested 120000" in text.replace(",", "")
    assert "received 90000" in text.replace(",", "")
    assert "shortfall" in text.lower()
    assert "drought index" in text.lower()
