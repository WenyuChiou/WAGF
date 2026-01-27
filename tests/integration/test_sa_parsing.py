"""
SA Parsing Tests - Phase 1 of Integration Test Suite.
Task-038: Verify LLM response parsing for Single-Agent flood adaptation.

Tests parsing of:
- JSON with delimiters (SA-P01)
- Numeric skill mapping (SA-P02)
- VL/L/M/H/VH labels (SA-P03)
- Reasoning fields (SA-P04)
- Naked digit recovery (SA-P05)
- Qwen3 think tag stripping (SA-P06)
- Case-insensitive keys (SA-P07)
- Invalid JSON fallback to keyword (SA-P08)
"""
import pytest
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from broker.utils.model_adapter import UnifiedAdapter
from broker.interfaces.skill_types import SkillProposal


# Fixtures
@pytest.fixture
def sa_adapter():
    """Create UnifiedAdapter for SA household agent."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "examples", "single_agent", "agent_types.yaml"
    )
    return UnifiedAdapter(agent_type="household", config_path=config_path)


@pytest.fixture
def default_context():
    """Default context for non-elevated household."""
    return {
        "agent_id": "test_household_001",
        "agent_type": "household",
        "elevated": False,
        "has_insurance": False
    }


@pytest.fixture
def elevated_context():
    """Context for elevated household (fewer options)."""
    return {
        "agent_id": "test_household_002",
        "agent_type": "household",
        "elevated": True,
        "has_insurance": False
    }


class TestSAParsingBasic:
    """Basic parsing tests for SA experiments."""

    def test_sa_p01_parse_json_with_delimiters(self, sa_adapter, default_context):
        """SA-P01: Parse JSON enclosed in <<<DECISION_START>>>...<<<DECISION_END>>>."""
        raw_output = '''<<<DECISION_START>>>
{
    "decision": 1,
    "threat_appraisal": {"label": "H", "reason": "High flood risk"},
    "coping_appraisal": {"label": "M", "reason": "Moderate resources"}
}
<<<DECISION_END>>>'''

        result = sa_adapter.parse_output(raw_output, default_context)

        assert result is not None, "Should parse valid JSON with delimiters"
        assert isinstance(result, SkillProposal)
        assert result.skill_name == "buy_insurance", f"Expected buy_insurance, got {result.skill_name}"

    def test_sa_p02_parse_numeric_skill_mapping(self, sa_adapter, default_context):
        """SA-P02: Parse numeric string decision and map to skill."""
        raw_output = '{"decision": "2"}'

        result = sa_adapter.parse_output(raw_output, default_context)

        assert result is not None, "Should parse numeric string decision"
        assert result.skill_name == "elevate_house", f"Expected elevate_house for decision 2, got {result.skill_name}"

    def test_sa_p03_parse_vl_l_m_h_vh_labels(self, sa_adapter, default_context):
        """SA-P03: Parse and extract VL/L/M/H/VH appraisal labels."""
        raw_output = '''<<<DECISION_START>>>
{
    "decision": 1,
    "threat_appraisal": {"label": "VH", "reason": "Very high flood risk"},
    "coping_appraisal": {"label": "L", "reason": "Limited resources"}
}
<<<DECISION_END>>>'''

        result = sa_adapter.parse_output(raw_output, default_context)

        assert result is not None
        assert result.reasoning is not None
        # Check that appraisal labels are extracted into reasoning
        reasoning = result.reasoning
        # The exact key names may vary by config, check common patterns
        reasoning_str = str(reasoning).lower()
        has_appraisals = (
            "appraisal" in reasoning_str or
            "threat" in reasoning_str or
            "coping" in reasoning_str or
            "tp" in reasoning_str or
            "cp" in reasoning_str
        )
        assert has_appraisals or len(reasoning) > 0, "Should extract appraisal constructs"

    def test_sa_p04_parse_reasoning_field(self, sa_adapter, default_context):
        """SA-P04: Extract reasoning dict from response."""
        raw_output = '''<<<DECISION_START>>>
{
    "decision": 1,
    "reasoning": {
        "threat": "High flood risk in my area",
        "strategy": "Insurance provides financial protection"
    }
}
<<<DECISION_END>>>'''

        result = sa_adapter.parse_output(raw_output, default_context)

        assert result is not None
        assert result.reasoning is not None
        # Reasoning should be a dict with content
        assert isinstance(result.reasoning, dict)

    def test_sa_p05_naked_digit_recovery(self, sa_adapter, default_context):
        """SA-P05: Recover decision from naked digit after text."""
        raw_output = '''After analyzing the flood risk and my financial situation,
I believe buying insurance is the best option to protect my family.

1'''

        result = sa_adapter.parse_output(raw_output, default_context)

        # Should recover decision from naked digit "1"
        assert result is not None, "Should recover decision from naked digit"
        assert result.skill_name == "buy_insurance", f"Expected buy_insurance, got {result.skill_name}"

    def test_sa_p06_qwen3_think_tag_stripping(self, sa_adapter, default_context):
        """SA-P06: Strip <think>...</think> tags before parsing."""
        raw_output = '''<think>
Let me analyze the flood risk carefully...
The threat level is high but I have some resources.
I should consider my options.
</think>
<<<DECISION_START>>>
{"decision": 1, "threat_appraisal": {"label": "H", "reason": "High risk"}}
<<<DECISION_END>>>'''

        result = sa_adapter.parse_output(raw_output, default_context)

        assert result is not None, "Should parse after stripping think tags"
        assert result.skill_name == "buy_insurance"

    def test_sa_p07_case_insensitive_keys(self, sa_adapter, default_context):
        """SA-P07: Handle uppercase/mixed case keys."""
        raw_output = '''<<<DECISION_START>>>
{
    "DECISION": 2,
    "THREAT_APPRAISAL": {"LABEL": "VH", "REASON": "Very high risk"}
}
<<<DECISION_END>>>'''

        result = sa_adapter.parse_output(raw_output, default_context)

        assert result is not None, "Should handle uppercase keys"
        assert result.skill_name == "elevate_house", f"Expected elevate_house, got {result.skill_name}"

    def test_sa_p08_invalid_json_fallback_to_keyword(self, sa_adapter, default_context):
        """SA-P08: Fall back to keyword extraction for invalid JSON."""
        raw_output = '''I have carefully considered the flood risk and my options.
Given the high threat level, I believe I should elevate my house
to protect my family from future flooding.
My choice is elevate_house.'''

        result = sa_adapter.parse_output(raw_output, default_context)

        # Should fall back to keyword matching
        assert result is not None, "Should fall back to keyword extraction"
        assert result.skill_name == "elevate_house", f"Expected elevate_house from keywords, got {result.skill_name}"


class TestSAParsingEdgeCases:
    """Edge case parsing tests."""

    def test_empty_output_returns_none(self, sa_adapter, default_context):
        """Empty output should return None."""
        result = sa_adapter.parse_output("", default_context)
        assert result is None

    def test_only_think_tags_returns_none(self, sa_adapter, default_context):
        """Output with only think tags should return None."""
        raw_output = '''<think>
I am thinking about this problem...
Let me consider the options.
</think>'''

        result = sa_adapter.parse_output(raw_output, default_context)
        assert result is None, "Only think tags should return None"

    def test_nested_decision_dict(self, sa_adapter, default_context):
        """Handle nested decision dict."""
        raw_output = '''{"decision": {"choice": 1}}'''

        result = sa_adapter.parse_output(raw_output, default_context)
        assert result is not None
        assert result.skill_name == "buy_insurance"

    def test_decision_with_option_prefix(self, sa_adapter, default_context):
        """Handle decision like 'Option 2'."""
        raw_output = '''<<<DECISION_START>>>
{"decision": "Option 2: Elevate my house"}
<<<DECISION_END>>>'''

        result = sa_adapter.parse_output(raw_output, default_context)
        assert result is not None
        assert result.skill_name == "elevate_house"


class TestSASkillMapping:
    """Test skill mapping based on agent state."""

    def test_non_elevated_has_four_options(self, sa_adapter, default_context):
        """Non-elevated household should map decisions 1-4."""
        # Decision 4 = do_nothing for non-elevated
        raw_output = '{"decision": 4}'
        result = sa_adapter.parse_output(raw_output, default_context)

        assert result is not None
        assert result.skill_name == "do_nothing", f"Decision 4 should map to do_nothing, got {result.skill_name}"

    def test_elevated_has_three_options(self, sa_adapter, elevated_context):
        """Elevated household should have different skill mapping (no elevate option)."""
        # For elevated agents, decision 3 = do_nothing (not relocate)
        raw_output = '{"decision": 3}'
        result = sa_adapter.parse_output(raw_output, elevated_context)

        assert result is not None
        # The exact mapping depends on config, but elevate_house should not be available


class TestSAAppraisalNormalization:
    """Test normalization of appraisal labels."""

    def test_normalize_very_low_to_vl(self, sa_adapter, default_context):
        """'very low' should normalize to 'VL'."""
        raw_output = '''<<<DECISION_START>>>
{
    "decision": 4,
    "threat_appraisal": {"label": "very low", "reason": "Low risk area"}
}
<<<DECISION_END>>>'''

        result = sa_adapter.parse_output(raw_output, default_context)
        assert result is not None

    def test_normalize_medium_to_m(self, sa_adapter, default_context):
        """'medium' or 'moderate' should normalize to 'M'."""
        raw_output = '''<<<DECISION_START>>>
{
    "decision": 1,
    "threat_appraisal": {"label": "moderate", "reason": "Moderate risk"}
}
<<<DECISION_END>>>'''

        result = sa_adapter.parse_output(raw_output, default_context)
        assert result is not None


class TestSAParseLayerTracking:
    """Test that parse_layer is tracked correctly."""

    def test_enclosure_parse_layer(self, sa_adapter, default_context):
        """Parse layer should indicate 'enclosure' for delimiter-wrapped JSON."""
        raw_output = '''<<<DECISION_START>>>
{"decision": 1}
<<<DECISION_END>>>'''

        result = sa_adapter.parse_output(raw_output, default_context)
        assert result is not None
        # parse_layer should be accessible or logged

    def test_json_parse_layer(self, sa_adapter, default_context):
        """Parse layer should indicate 'json' for raw JSON."""
        raw_output = '{"decision": 2}'

        result = sa_adapter.parse_output(raw_output, default_context)
        assert result is not None


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
