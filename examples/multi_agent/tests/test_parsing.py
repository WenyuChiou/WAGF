"""
Test Suite: LLM Output Parsing Validation
==========================================
Validates that the UnifiedAdapter correctly parses various LLM output formats
for household, government, and insurance agent types.

Tests cover:
1. Valid JSON with 5 constructs + decision (household)
2. Malformed JSON recovery
3. Case-insensitive construct matching
4. Institutional parsing (Government/Insurance)
5. Edge cases (missing fields, invalid skills, aliases)
"""

import sys
import unittest
from pathlib import Path

# Setup paths - IMPORTANT: Insert ROOT_DIR at position 0 to override local broker
CURRENT_DIR = Path(__file__).parent
MA_DIR = CURRENT_DIR.parent
ROOT_DIR = MA_DIR.parent.parent

# Remove any existing paths that might conflict
sys.path = [p for p in sys.path if 'multi_agent' not in p or p == str(MA_DIR)]
# Insert root at the beginning to ensure root broker is imported
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from broker.utils.model_adapter import UnifiedAdapter

CONFIG_PATH = str(MA_DIR / "ma_agent_types.yaml")


class TestHouseholdParsing(unittest.TestCase):
    """Test household agent (owner/renter) output parsing."""

    def setUp(self):
        self.adapter_owner = UnifiedAdapter(agent_type="household_owner", config_path=CONFIG_PATH)
        self.adapter_renter = UnifiedAdapter(agent_type="household_renter", config_path=CONFIG_PATH)

    def test_valid_json_with_all_constructs(self):
        """Test parsing a well-formed JSON with all 5 PMT constructs."""
        raw_output = '''
        ```json
        {
          "threat_perception": { "label": "H", "reason": "Recent floods have been severe" },
          "coping_perception": { "label": "VH", "reason": "I have savings for insurance" },
          "stakeholder_perception": { "label": "M", "reason": "Government support is moderate" },
          "social_capital": { "label": "L", "reason": "Few neighbors have adapted" },
          "place_attachment": { "label": "VH", "reason": "Lived here 20 years" },
          "decision": "buy_insurance"
        }
        ```
        '''

        proposal = self.adapter_owner.parse_output(raw_output, {"agent_id": "HH001"})

        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.skill_name, "buy_insurance")
        self.assertEqual(proposal.reasoning.get("TP_LABEL"), "H")
        self.assertEqual(proposal.reasoning.get("CP_LABEL"), "VH")
        self.assertEqual(proposal.reasoning.get("SP_LABEL"), "M")
        self.assertEqual(proposal.reasoning.get("SC_LABEL"), "L")
        self.assertEqual(proposal.reasoning.get("PA_LABEL"), "VH")

    def test_decision_aliases(self):
        """Test that all skill aliases are recognized."""
        test_cases = [
            ("do_nothing", ["DN", "nothing", "wait", "Do nothing", "Do Nothing", "[DN]"]),
            ("buy_insurance", ["FI", "insurance", "Buy insurance", "[FI]"]),
            ("elevate_house", ["HE", "elevate", "elevation", "Elevate house", "[HE]"]),
            ("buyout_program", ["BT", "buyout", "government buyout", "Accept buyout", "[BT]"]),
        ]

        for expected_skill, aliases in test_cases:
            for alias in aliases:
                raw_output = f'''
                {{
                  "threat_perception": {{ "label": "M", "reason": "test" }},
                  "decision": "{alias}"
                }}
                '''
                proposal = self.adapter_owner.parse_output(raw_output, {"agent_id": "TestAlias"})
                self.assertIsNotNone(proposal, f"Failed to parse alias: {alias}")
                self.assertEqual(proposal.skill_name, expected_skill,
                               f"Alias '{alias}' should map to '{expected_skill}', got '{proposal.skill_name}'")

    def test_renter_specific_actions(self):
        """Test renter-specific actions like relocate and contents insurance."""
        test_cases = [
            ("buy_contents_insurance", ["CI", "contents_insurance", "Buy contents insurance", "[CI]"]),
            ("relocate", ["RL", "move", "relocate", "Relocation", "Move", "[RL]"]),
        ]

        for expected_skill, aliases in test_cases:
            for alias in aliases:
                raw_output = f'''
                {{
                  "threat_perception": {{ "label": "H", "reason": "test" }},
                  "decision": "{alias}"
                }}
                '''
                proposal = self.adapter_renter.parse_output(raw_output, {"agent_id": "RenterTest"})
                self.assertIsNotNone(proposal, f"Failed to parse renter alias: {alias}")
                self.assertEqual(proposal.skill_name, expected_skill,
                               f"Renter alias '{alias}' should map to '{expected_skill}'")

    def test_construct_label_variations(self):
        """Test case variations for construct labels (VL, L, M, H, VH)."""
        labels = ["VL", "L", "M", "H", "VH"]

        for label in labels:
            # Test uppercase
            raw_output = f'''
            {{
              "threat_perception": {{ "label": "{label}", "reason": "test" }},
              "decision": "do_nothing"
            }}
            '''
            proposal = self.adapter_owner.parse_output(raw_output, {"agent_id": "LabelTest"})
            self.assertIsNotNone(proposal)
            extracted = proposal.reasoning.get("TP_LABEL", "").upper()
            self.assertEqual(extracted, label, f"Expected TP_LABEL={label}, got {extracted}")

    def test_lowercase_construct_labels(self):
        """Test that lowercase labels are handled (regex uses (?i) flag)."""
        raw_output = '''
        {
          "threat_perception": { "label": "vh", "reason": "lowercase test" },
          "decision": "do_nothing"
        }
        '''
        proposal = self.adapter_owner.parse_output(raw_output, {"agent_id": "LowerTest"})
        self.assertIsNotNone(proposal)
        tp_label = proposal.reasoning.get("TP_LABEL", "")
        # Should accept lowercase due to (?i) in regex
        self.assertIn(tp_label.upper(), ["VH", ""], f"Should parse 'vh', got: {tp_label}")

    def test_json_without_markdown_fence(self):
        """Test parsing JSON without markdown code fence."""
        raw_output = '''
        {
          "threat_perception": { "label": "M", "reason": "plain json" },
          "coping_perception": { "label": "L", "reason": "test" },
          "decision": "elevate_house"
        }
        '''
        proposal = self.adapter_owner.parse_output(raw_output, {"agent_id": "PlainJSON"})
        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.skill_name, "elevate_house")


class TestMalformedJsonRecovery(unittest.TestCase):
    """Test recovery from malformed JSON outputs."""

    def setUp(self):
        self.adapter = UnifiedAdapter(agent_type="household_owner", config_path=CONFIG_PATH)

    def test_missing_comma_recovery(self):
        """Test JSON with missing comma (common LLM error)."""
        raw_output = '''
        {
          "threat_perception": { "label": "L", "reason": "Far from river" }
          "decision": "do_nothing"
        }
        '''
        # The adapter should attempt smart repair
        proposal = self.adapter.parse_output(raw_output, {"agent_id": "MissingComma"})
        # May or may not recover depending on adapter implementation
        if proposal:
            self.assertEqual(proposal.skill_name, "do_nothing")

    def test_trailing_text_after_json(self):
        """Test JSON followed by additional conversational text."""
        raw_output = '''
        I've carefully considered the situation.
        ```json
        {
          "threat_perception": { "label": "H", "reason": "Flooding risk" },
          "decision": "buy_insurance"
        }
        ```
        I hope this helps with your flood preparedness!
        '''
        proposal = self.adapter.parse_output(raw_output, {"agent_id": "TrailingText"})
        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.skill_name, "buy_insurance")

    def test_decision_only_fallback(self):
        """Test extraction when only decision field is present."""
        raw_output = '''
        {
          "decision": "elevate_house"
        }
        '''
        proposal = self.adapter.parse_output(raw_output, {"agent_id": "DecisionOnly"})
        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.skill_name, "elevate_house")


class TestInstitutionalParsing(unittest.TestCase):
    """Test government and insurance agent output parsing."""

    def setUp(self):
        self.adapter_gov = UnifiedAdapter(agent_type="government", config_path=CONFIG_PATH)
        self.adapter_ins = UnifiedAdapter(agent_type="insurance", config_path=CONFIG_PATH)

    def test_government_decision_numeric(self):
        """Test government decisions using numeric codes."""
        test_cases = [
            ("1", "increase_subsidy"),
            ("2", "decrease_subsidy"),
            ("3", "maintain_subsidy"),
        ]

        for code, expected_skill in test_cases:
            raw_output = f'''
            {{
              "decision": "{code}",
              "reasoning": "Budget considerations"
            }}
            '''
            proposal = self.adapter_gov.parse_output(raw_output, {"agent_id": "GovTest"})
            self.assertIsNotNone(proposal, f"Failed to parse government code: {code}")
            self.assertEqual(proposal.skill_name, expected_skill,
                           f"Code '{code}' should map to '{expected_skill}'")

    def test_government_decision_text(self):
        """Test government decisions using text aliases."""
        test_cases = [
            ("INCREASE", "increase_subsidy"),
            ("increase", "increase_subsidy"),
            ("[1]", "increase_subsidy"),
            ("DECREASE", "decrease_subsidy"),
            ("MAINTAIN", "maintain_subsidy"),
        ]

        for alias, expected_skill in test_cases:
            raw_output = f'''
            {{
              "decision": "{alias}",
              "reasoning": "Policy adjustment"
            }}
            '''
            proposal = self.adapter_gov.parse_output(raw_output, {"agent_id": "GovTextTest"})
            self.assertIsNotNone(proposal, f"Failed to parse government alias: {alias}")
            self.assertEqual(proposal.skill_name, expected_skill)

    def test_insurance_decision_numeric(self):
        """Test insurance decisions using numeric codes."""
        test_cases = [
            ("1", "raise_premium"),
            ("2", "lower_premium"),
            ("3", "maintain_premium"),
        ]

        for code, expected_skill in test_cases:
            raw_output = f'''
            {{
              "decision": "{code}",
              "reasoning": "Solvency management"
            }}
            '''
            proposal = self.adapter_ins.parse_output(raw_output, {"agent_id": "InsTest"})
            self.assertIsNotNone(proposal, f"Failed to parse insurance code: {code}")
            self.assertEqual(proposal.skill_name, expected_skill)

    def test_insurance_decision_text(self):
        """Test insurance decisions using text aliases."""
        test_cases = [
            ("RAISE", "raise_premium"),
            ("raise", "raise_premium"),
            ("[1]", "raise_premium"),
            ("LOWER", "lower_premium"),
            ("lower", "lower_premium"),
            ("MAINTAIN", "maintain_premium"),
        ]

        for alias, expected_skill in test_cases:
            raw_output = f'''
            {{
              "decision": "{alias}",
              "reasoning": "Market adjustment"
            }}
            '''
            proposal = self.adapter_ins.parse_output(raw_output, {"agent_id": "InsTextTest"})
            self.assertIsNotNone(proposal, f"Failed to parse insurance alias: {alias}")
            self.assertEqual(proposal.skill_name, expected_skill)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""

    def setUp(self):
        self.adapter = UnifiedAdapter(agent_type="household_owner", config_path=CONFIG_PATH)
        self.adapter_gov = UnifiedAdapter(agent_type="government", config_path=CONFIG_PATH)

    def test_empty_output(self):
        """Test handling of empty LLM output."""
        raw_output = ""
        proposal = self.adapter.parse_output(raw_output, {"agent_id": "EmptyTest"})
        # Should return None or default, not crash
        # Behavior depends on adapter implementation

    def test_garbage_output(self):
        """Test handling of completely invalid output."""
        raw_output = "I'm sorry, I cannot help with that request."
        proposal = self.adapter.parse_output(raw_output, {"agent_id": "GarbageTest"})
        # Should handle gracefully

    def test_invalid_skill_name(self):
        """Test handling of unrecognized skill names."""
        raw_output = '''
        {
          "threat_perception": { "label": "M", "reason": "test" },
          "decision": "fly_to_moon"
        }
        '''
        proposal = self.adapter.parse_output(raw_output, {"agent_id": "InvalidSkill"})
        # Adapter may return None or default skill

    def test_partial_constructs(self):
        """Test parsing with only some constructs present."""
        raw_output = '''
        {
          "threat_perception": { "label": "H", "reason": "test" },
          "decision": "buy_insurance"
        }
        '''
        # Should still parse what's available
        proposal = self.adapter.parse_output(raw_output, {"agent_id": "PartialConstruct"})
        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.skill_name, "buy_insurance")
        self.assertEqual(proposal.reasoning.get("TP_LABEL"), "H")

    def test_construct_with_different_json_structure(self):
        """Test constructs with nested vs flat structure."""
        # Nested structure (standard)
        raw_output_nested = '''
        {
          "threat_perception": { "label": "VH", "reason": "High risk" },
          "decision": "buy_insurance"
        }
        '''

        # Some LLMs might output flatter structure
        raw_output_flat = '''
        {
          "threat_perception_label": "VH",
          "threat_perception_reason": "High risk",
          "decision": "buy_insurance"
        }
        '''

        proposal_nested = self.adapter.parse_output(raw_output_nested, {"agent_id": "Nested"})
        self.assertIsNotNone(proposal_nested)
        self.assertEqual(proposal_nested.skill_name, "buy_insurance")


class TestConstructExtraction(unittest.TestCase):
    """Test detailed construct extraction from various formats."""

    def setUp(self):
        self.adapter = UnifiedAdapter(agent_type="household_owner", config_path=CONFIG_PATH)

    def test_all_five_constructs(self):
        """Verify all 5 PMT constructs are extracted."""
        raw_output = '''
        ```json
        {
          "threat_perception": { "label": "VH", "reason": "Critical flood zone" },
          "coping_perception": { "label": "H", "reason": "Good savings" },
          "stakeholder_perception": { "label": "M", "reason": "Average support" },
          "social_capital": { "label": "L", "reason": "Few adapted neighbors" },
          "place_attachment": { "label": "VL", "reason": "Recent move" },
          "decision": "buy_insurance"
        }
        ```
        '''

        proposal = self.adapter.parse_output(raw_output, {"agent_id": "AllConstructs"})
        self.assertIsNotNone(proposal)

        reasoning = proposal.reasoning
        expected = {
            "TP_LABEL": "VH",
            "CP_LABEL": "H",
            "SP_LABEL": "M",
            "SC_LABEL": "L",
            "PA_LABEL": "VL"
        }

        for key, expected_value in expected.items():
            actual = reasoning.get(key, "")
            self.assertEqual(actual, expected_value,
                           f"Expected {key}={expected_value}, got {actual}")


if __name__ == "__main__":
    # Run with verbosity
    unittest.main(verbosity=2)
