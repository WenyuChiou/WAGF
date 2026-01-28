import pytest
from pathlib import Path

from broker.utils.model_adapter import UnifiedAdapter


def test_json_parse_confidence():
    config_path = Path("examples/single_agent/agent_types.yaml")
    adapter = UnifiedAdapter(agent_type="household", config_path=str(config_path))
    raw_output = '<<<DECISION_START>>>{"decision": 2, "threat_appraisal": "H", "coping_appraisal": "M"}<<<DECISION_END>>>'
    context = {"agent_id": "test", "agent_type": "household"}

    result = adapter.parse_output(raw_output, context)

    assert result is not None
    parse_meta = result.reasoning.get("_parse_metadata", {})
    assert parse_meta.get("parse_confidence", 0) >= 0.9
    assert parse_meta.get("parse_layer") == "json"


def test_construct_completeness():
    config_path = Path("examples/single_agent/agent_types.yaml")
    adapter = UnifiedAdapter(agent_type="household", config_path=str(config_path))
    raw_output = '<<<DECISION_START>>>{"decision": 2}<<<DECISION_END>>>'
    context = {"agent_id": "test", "agent_type": "household"}

    result = adapter.parse_output(raw_output, context)

    completeness = result.reasoning.get("_parse_metadata", {}).get("construct_completeness", 0)
    assert completeness < 1.0
