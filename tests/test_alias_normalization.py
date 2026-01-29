"""
Regression test for alias normalization in parse_output().

Bug: self.alias_map was set at __init__ time and could be overwritten by
experiment.py with a trivial identity map, causing aliases like "FI", "HE",
"insurance" to pass through unnormalized. This led to 18.2% of decisions
being silently ignored in experiments.

Fix: parse_output() now dynamically loads alias_map per agent_type via
agent_config.get_action_alias_map(agent_type), matching the pattern already
used for valid_skills, parsing_cfg, and skill_map.
"""
import pytest
from pathlib import Path

from broker.utils.model_adapter import UnifiedAdapter


CONFIG_PATH = str(Path("examples/single_agent/agent_types.yaml"))


@pytest.fixture
def adapter():
    return UnifiedAdapter(agent_type="household", config_path=CONFIG_PATH)


@pytest.fixture
def base_context():
    return {"agent_id": "test_agent", "agent_type": "household"}


class TestAliasNormalizationJSON:
    """Test that aliases in JSON decision fields are normalized to canonical IDs."""

    def test_fi_alias_normalized_to_buy_insurance(self, adapter, base_context):
        """FI (short alias) should resolve to buy_insurance."""
        raw = '<<<DECISION_START>>>{"decision": "FI", "threat_appraisal": "H", "coping_appraisal": "M"}<<<DECISION_END>>>'
        result = adapter.parse_output(raw, base_context)
        assert result is not None
        assert result.skill_name == "buy_insurance"

    def test_insurance_alias_normalized(self, adapter, base_context):
        """'insurance' (text alias) should resolve to buy_insurance."""
        raw = '<<<DECISION_START>>>{"decision": "insurance", "threat_appraisal": "M", "coping_appraisal": "M"}<<<DECISION_END>>>'
        result = adapter.parse_output(raw, base_context)
        assert result is not None
        assert result.skill_name == "buy_insurance"

    def test_he_alias_normalized_to_elevate_house(self, adapter, base_context):
        """HE (short alias) should resolve to elevate_house."""
        raw = '<<<DECISION_START>>>{"decision": "HE", "threat_appraisal": "H", "coping_appraisal": "H"}<<<DECISION_END>>>'
        result = adapter.parse_output(raw, base_context)
        assert result is not None
        assert result.skill_name == "elevate_house"

    def test_elevation_alias_normalized(self, adapter, base_context):
        """'elevation' alias should resolve to elevate_house."""
        raw = '<<<DECISION_START>>>{"decision": "elevation", "threat_appraisal": "VH", "coping_appraisal": "H"}<<<DECISION_END>>>'
        result = adapter.parse_output(raw, base_context)
        assert result is not None
        assert result.skill_name == "elevate_house"

    def test_rl_alias_normalized_to_relocate(self, adapter, base_context):
        """RL (short alias) should resolve to relocate."""
        raw = '<<<DECISION_START>>>{"decision": "RL", "threat_appraisal": "VH", "coping_appraisal": "H"}<<<DECISION_END>>>'
        result = adapter.parse_output(raw, base_context)
        assert result is not None
        assert result.skill_name == "relocate"

    def test_dn_alias_normalized_to_do_nothing(self, adapter, base_context):
        """DN (short alias) should resolve to do_nothing."""
        raw = '<<<DECISION_START>>>{"decision": "DN", "threat_appraisal": "L", "coping_appraisal": "L"}<<<DECISION_END>>>'
        result = adapter.parse_output(raw, base_context)
        assert result is not None
        assert result.skill_name == "do_nothing"

    def test_nothing_alias_normalized(self, adapter, base_context):
        """'nothing' alias should resolve to do_nothing."""
        raw = '<<<DECISION_START>>>{"decision": "nothing", "threat_appraisal": "VL", "coping_appraisal": "L"}<<<DECISION_END>>>'
        result = adapter.parse_output(raw, base_context)
        assert result is not None
        assert result.skill_name == "do_nothing"


class TestAliasNormalizationNumeric:
    """Test that numeric decision IDs still work correctly."""

    def test_numeric_1_maps_to_buy_insurance(self, adapter, base_context):
        raw = '<<<DECISION_START>>>{"decision": 1, "threat_appraisal": "M", "coping_appraisal": "M"}<<<DECISION_END>>>'
        result = adapter.parse_output(raw, base_context)
        assert result is not None
        assert result.skill_name == "buy_insurance"

    def test_numeric_2_maps_to_elevate_house(self, adapter, base_context):
        raw = '<<<DECISION_START>>>{"decision": 2, "threat_appraisal": "H", "coping_appraisal": "H"}<<<DECISION_END>>>'
        result = adapter.parse_output(raw, base_context)
        assert result is not None
        assert result.skill_name == "elevate_house"

    def test_numeric_3_maps_to_relocate(self, adapter, base_context):
        raw = '<<<DECISION_START>>>{"decision": 3, "threat_appraisal": "VH", "coping_appraisal": "H"}<<<DECISION_END>>>'
        result = adapter.parse_output(raw, base_context)
        assert result is not None
        assert result.skill_name == "relocate"

    def test_numeric_4_maps_to_do_nothing(self, adapter, base_context):
        raw = '<<<DECISION_START>>>{"decision": 4, "threat_appraisal": "L", "coping_appraisal": "L"}<<<DECISION_END>>>'
        result = adapter.parse_output(raw, base_context)
        assert result is not None
        assert result.skill_name == "do_nothing"


class TestAliasMapIndependence:
    """Test that parse_output() alias resolution is independent of self.alias_map."""

    def test_alias_works_even_if_instance_map_is_empty(self, base_context):
        """Regression: even if self.alias_map is cleared, parse_output() should
        still normalize aliases because it loads alias_map dynamically."""
        adapter = UnifiedAdapter(agent_type="household", config_path=CONFIG_PATH)
        # Simulate the bug: experiment.py overwrites alias_map with trivial map
        adapter.alias_map = {"buy_insurance": "buy_insurance", "elevate_house": "elevate_house",
                             "relocate": "relocate", "do_nothing": "do_nothing"}

        raw = '<<<DECISION_START>>>{"decision": "FI", "threat_appraisal": "H", "coping_appraisal": "M"}<<<DECISION_END>>>'
        result = adapter.parse_output(raw, base_context)
        assert result is not None
        assert result.skill_name == "buy_insurance", (
            f"Expected 'buy_insurance' but got '{result.skill_name}'. "
            "parse_output() should load alias_map dynamically, not use self.alias_map."
        )

    def test_alias_works_even_if_instance_map_is_completely_empty(self, base_context):
        """Regression: even if self.alias_map is {}, parse_output() still normalizes."""
        adapter = UnifiedAdapter(agent_type="household", config_path=CONFIG_PATH)
        adapter.alias_map = {}  # Completely empty

        raw = '<<<DECISION_START>>>{"decision": "HE", "threat_appraisal": "VH", "coping_appraisal": "H"}<<<DECISION_END>>>'
        result = adapter.parse_output(raw, base_context)
        assert result is not None
        assert result.skill_name == "elevate_house"


class TestBracketedAliases:
    """Test that bracketed aliases like [FI], [HE] also normalize correctly."""

    def test_bracketed_fi(self, adapter, base_context):
        raw = '<<<DECISION_START>>>{"decision": "[FI]", "threat_appraisal": "H", "coping_appraisal": "M"}<<<DECISION_END>>>'
        result = adapter.parse_output(raw, base_context)
        assert result is not None
        assert result.skill_name == "buy_insurance"

    def test_bracketed_he(self, adapter, base_context):
        raw = '<<<DECISION_START>>>{"decision": "[HE]", "threat_appraisal": "H", "coping_appraisal": "H"}<<<DECISION_END>>>'
        result = adapter.parse_output(raw, base_context)
        assert result is not None
        assert result.skill_name == "elevate_house"


class TestDynamicParsingConfig:
    """Test that parse_output() uses dynamic parsing_cfg, not stale self.config."""

    def test_proximity_window_uses_dynamic_config(self, adapter, base_context):
        """Regression: proximity_window should come from parsing_cfg, not self.config."""
        adapter.config = {"proximity_window": 1, "normalization": {"FAKE": "VALUE"}}

        raw = "Decision 1. threat_appraisal " + ("x" * 10) + " H"
        result = adapter.parse_output(raw, base_context)

        assert result is not None
        assert result.skill_name == "buy_insurance"
        assert result.reasoning.get("TP_LABEL") == "H"
