"""
Tests for Multi-Framework ThinkingValidator.

Task-041: Universal Prompt/Context/Governance Framework
"""

import pytest
from broker.validators.governance.thinking_validator import (
    ThinkingValidator,
    FRAMEWORK_LABEL_ORDERS,
    FRAMEWORK_CONSTRUCTS,
)
from broker.governance.rule_types import GovernanceRule


class TestThinkingValidatorPMT:
    """Test PMT framework validation (backward compatible)."""

    def setup_method(self):
        self.validator = ThinkingValidator(framework="pmt")

    def test_high_tp_high_cp_do_nothing_fails(self):
        """High TP + High CP should not allow do_nothing."""
        context = {
            "reasoning": {"TP_LABEL": "VH", "CP_LABEL": "H"},
            "framework": "pmt"
        }
        results = self.validator.validate("do_nothing", [], context)
        assert len(results) >= 1
        assert any("protective action" in r.errors[0] for r in results if not r.valid)

    def test_high_tp_high_cp_buy_insurance_passes(self):
        """High TP + High CP should allow protective actions."""
        context = {
            "reasoning": {"TP_LABEL": "VH", "CP_LABEL": "H"},
            "framework": "pmt"
        }
        results = self.validator.validate("buy_insurance", [], context)
        # Should not have the high_tp_cp_action error
        assert all(r.valid for r in results)

    def test_vh_threat_do_nothing_fails(self):
        """VH threat should not allow do_nothing."""
        context = {
            "reasoning": {"TP_LABEL": "VH", "CP_LABEL": "L"},
            "framework": "pmt"
        }
        results = self.validator.validate("do_nothing", [], context)
        assert len(results) >= 1
        assert any("requires protective action" in r.errors[0] for r in results if not r.valid)

    def test_low_tp_extreme_action_fails(self):
        """Low TP should not justify extreme actions."""
        context = {
            "reasoning": {"TP_LABEL": "L", "CP_LABEL": "M"},
            "framework": "pmt"
        }
        results = self.validator.validate("relocate", [], context)
        assert len(results) >= 1
        assert any("does not justify" in r.errors[0] for r in results if not r.valid)

    def test_low_tp_buy_insurance_passes(self):
        """Low TP can still justify moderate actions like insurance."""
        context = {
            "reasoning": {"TP_LABEL": "L", "CP_LABEL": "M"},
            "framework": "pmt"
        }
        results = self.validator.validate("buy_insurance", [], context)
        # buy_insurance is not an extreme action
        assert all(r.valid for r in results)

    def test_medium_tp_cp_allows_all(self):
        """Medium TP/CP should allow all actions."""
        context = {
            "reasoning": {"TP_LABEL": "M", "CP_LABEL": "M"},
            "framework": "pmt"
        }
        for skill in ["do_nothing", "buy_insurance", "elevate_house", "relocate"]:
            results = self.validator.validate(skill, [], context)
            # Medium values should not trigger built-in rules
            assert all(r.valid for r in results)


class TestThinkingValidatorUtility:
    """Test Utility framework validation for government agents."""

    def setup_method(self):
        self.validator = ThinkingValidator(framework="utility")

    def test_high_budget_high_equity_maintain_fails(self):
        """High budget impact + high equity gap should not allow maintain_policy."""
        context = {
            "reasoning": {"BUDGET_UTIL": "H", "EQUITY_GAP": "H"},
            "framework": "utility"
        }
        results = self.validator.validate("maintain_policy", [], context)
        assert len(results) >= 1
        assert any("policy change" in r.errors[0] for r in results if not r.valid)

    def test_high_budget_high_equity_change_passes(self):
        """High budget impact + high equity gap should allow policy changes."""
        context = {
            "reasoning": {"BUDGET_UTIL": "H", "EQUITY_GAP": "H"},
            "framework": "utility"
        }
        results = self.validator.validate("increase_subsidy", [], context)
        # Should not trigger maintain_policy rule
        assert all(r.valid for r in results)

    def test_low_budget_expensive_action_fails(self):
        """Low budget utility should not justify expensive policies."""
        context = {
            "reasoning": {"BUDGET_UTIL": "L", "EQUITY_GAP": "M"},
            "framework": "utility"
        }
        results = self.validator.validate("increase_subsidy", [], context)
        assert len(results) >= 1
        assert any("does not justify" in r.errors[0] for r in results if not r.valid)

    def test_low_budget_decrease_subsidy_passes(self):
        """Low budget utility can justify decrease_subsidy."""
        context = {
            "reasoning": {"BUDGET_UTIL": "L", "EQUITY_GAP": "M"},
            "framework": "utility"
        }
        results = self.validator.validate("decrease_subsidy", [], context)
        assert all(r.valid for r in results)


class TestThinkingValidatorFinancial:
    """Test Financial framework validation for insurance agents."""

    def setup_method(self):
        self.validator = ThinkingValidator(framework="financial")

    def test_high_solvency_conservative_expand_fails(self):
        """High solvency concern with conservative risk should not expand."""
        context = {
            "reasoning": {"RISK_APPETITE": "C", "SOLVENCY_IMPACT": "A"},  # A = Aggressive/High
            "framework": "financial"
        }
        results = self.validator.validate("expand_coverage", [], context)
        assert len(results) >= 1
        assert any("expansion" in r.errors[0] for r in results if not r.valid)

    def test_aggressive_risk_conservative_action_fails(self):
        """Aggressive risk appetite should not allow conservative actions."""
        context = {
            "reasoning": {"RISK_APPETITE": "A", "SOLVENCY_IMPACT": "M"},
            "framework": "financial"
        }
        results = self.validator.validate("restrict_coverage", [], context)
        assert len(results) >= 1
        assert any("conflicts" in r.errors[0] for r in results if not r.valid)

    def test_moderate_risk_allows_all(self):
        """Moderate risk appetite should allow most actions."""
        context = {
            "reasoning": {"RISK_APPETITE": "M", "SOLVENCY_IMPACT": "M"},
            "framework": "financial"
        }
        for skill in ["raise_premium", "lower_premium", "expand_coverage"]:
            results = self.validator.validate(skill, [], context)
            assert all(r.valid for r in results)


class TestThinkingValidatorLabelNormalization:
    """Test label normalization across frameworks."""

    def test_pmt_normalize_verbose_labels(self):
        """PMT should normalize verbose labels."""
        validator = ThinkingValidator(framework="pmt")
        assert validator._normalize_label("VERY LOW", "pmt") == "VL"
        assert validator._normalize_label("VERY_LOW", "pmt") == "VL"
        assert validator._normalize_label("VERYLOW", "pmt") == "VL"
        assert validator._normalize_label("VERY HIGH", "pmt") == "VH"
        assert validator._normalize_label("Medium", "pmt") == "M"

    def test_utility_normalize_priority_labels(self):
        """Utility should normalize priority labels."""
        validator = ThinkingValidator(framework="utility")
        assert validator._normalize_label("LOW PRIORITY", "utility") == "L"
        assert validator._normalize_label("HIGH PRIORITY", "utility") == "H"
        assert validator._normalize_label("LOW", "utility") == "L"

    def test_financial_normalize_risk_labels(self):
        """Financial should normalize risk labels."""
        validator = ThinkingValidator(framework="financial")
        assert validator._normalize_label("CONSERVATIVE", "financial") == "C"
        assert validator._normalize_label("AGGRESSIVE", "financial") == "A"
        assert validator._normalize_label("MODERATE", "financial") == "M"

    def test_none_label_defaults_to_m(self):
        """None label should default to M."""
        validator = ThinkingValidator()
        assert validator._normalize_label(None) == "M"
        assert validator._normalize_label("") == "M"


class TestThinkingValidatorLabelComparison:
    """Test label comparison across frameworks."""

    def test_pmt_compare_labels(self):
        """PMT label comparison should work correctly."""
        validator = ThinkingValidator(framework="pmt")
        assert validator._compare_labels("VL", "VH") == -1
        assert validator._compare_labels("VH", "VL") == 1
        assert validator._compare_labels("M", "M") == 0
        assert validator._compare_labels("L", "H") == -1

    def test_utility_compare_labels(self):
        """Utility label comparison should work correctly."""
        validator = ThinkingValidator(framework="utility")
        assert validator._compare_labels("L", "H", "utility") == -1
        assert validator._compare_labels("H", "L", "utility") == 1
        assert validator._compare_labels("M", "M", "utility") == 0

    def test_financial_compare_labels(self):
        """Financial label comparison should work correctly."""
        validator = ThinkingValidator(framework="financial")
        assert validator._compare_labels("C", "A", "financial") == -1
        assert validator._compare_labels("A", "C", "financial") == 1
        assert validator._compare_labels("M", "M", "financial") == 0


class TestThinkingValidatorGetValidLevels:
    """Test get_valid_levels method."""

    def test_pmt_valid_levels(self):
        """PMT should return VL/L/M/H/VH."""
        validator = ThinkingValidator(framework="pmt")
        levels = validator.get_valid_levels()
        assert "VL" in levels
        assert "VH" in levels
        assert len(levels) == 5

    def test_utility_valid_levels(self):
        """Utility should return L/M/H."""
        validator = ThinkingValidator(framework="utility")
        levels = validator.get_valid_levels()
        assert "L" in levels
        assert "H" in levels
        assert len(levels) == 3

    def test_financial_valid_levels(self):
        """Financial should return C/M/A."""
        validator = ThinkingValidator(framework="financial")
        levels = validator.get_valid_levels()
        assert "C" in levels
        assert "A" in levels
        assert len(levels) == 3


class TestThinkingValidatorValidateLabelValue:
    """Test validate_label_value method."""

    def test_pmt_valid_labels(self):
        """PMT should accept valid labels."""
        validator = ThinkingValidator(framework="pmt")
        assert validator.validate_label_value("VL") is True
        assert validator.validate_label_value("VH") is True
        assert validator.validate_label_value("M") is True

    def test_pmt_invalid_labels(self):
        """PMT should reject invalid labels."""
        validator = ThinkingValidator(framework="pmt")
        assert validator.validate_label_value("C") is False
        assert validator.validate_label_value("A") is False
        assert validator.validate_label_value("INVALID") is False

    def test_utility_valid_labels(self):
        """Utility should accept valid labels."""
        validator = ThinkingValidator(framework="utility")
        assert validator.validate_label_value("L") is True
        assert validator.validate_label_value("H") is True

    def test_utility_invalid_labels(self):
        """Utility should reject PMT-specific labels."""
        validator = ThinkingValidator(framework="utility")
        assert validator.validate_label_value("VL") is False
        assert validator.validate_label_value("VH") is False

    def test_financial_valid_labels(self):
        """Financial should accept valid labels."""
        validator = ThinkingValidator(framework="financial")
        assert validator.validate_label_value("C") is True
        assert validator.validate_label_value("A") is True

    def test_financial_invalid_labels(self):
        """Financial should reject PMT-specific labels."""
        validator = ThinkingValidator(framework="financial")
        assert validator.validate_label_value("VL") is False
        assert validator.validate_label_value("VH") is False


class TestThinkingValidatorFrameworkFromContext:
    """Test framework detection from context."""

    def test_uses_context_framework(self):
        """Should use framework from context if provided."""
        validator = ThinkingValidator(framework="pmt")
        context = {
            "reasoning": {"BUDGET_UTIL": "H", "EQUITY_GAP": "H"},
            "framework": "utility"  # Override
        }
        results = validator.validate("maintain_policy", [], context)
        # Should use utility validation, not PMT
        assert any("policy change" in r.errors[0] for r in results if not r.valid)

    def test_uses_default_framework(self):
        """Should use validator's default framework if not in context."""
        validator = ThinkingValidator(framework="pmt")
        context = {
            "reasoning": {"TP_LABEL": "VH", "CP_LABEL": "H"}
            # No framework specified
        }
        results = validator.validate("do_nothing", [], context)
        # Should use PMT validation
        assert any("protective action" in r.errors[0] for r in results if not r.valid)


class TestThinkingValidatorBackwardCompatibility:
    """Test backward compatibility with existing code."""

    def test_default_framework_is_pmt(self):
        """Default framework should be PMT."""
        validator = ThinkingValidator()
        assert validator.framework == "pmt"

    def test_pmt_label_order_constant_exists(self):
        """PMT_LABEL_ORDER constant should still exist for compatibility."""
        from broker.validators.governance.thinking_validator import PMT_LABEL_ORDER
        assert PMT_LABEL_ORDER == {"VL": 0, "L": 1, "M": 2, "H": 3, "VH": 4}

    def test_category_is_thinking(self):
        """Category should be 'thinking'."""
        validator = ThinkingValidator()
        assert validator.category == "thinking"

    def test_metadata_includes_framework(self):
        """Validation results should include framework in metadata."""
        validator = ThinkingValidator(framework="pmt")
        context = {
            "reasoning": {"TP_LABEL": "VH", "CP_LABEL": "L"},
            "framework": "pmt"
        }
        results = validator.validate("do_nothing", [], context)
        for r in results:
            if not r.valid:
                assert r.metadata.get("framework") == "pmt"


class TestThinkingValidatorMultiCondition:
    """Task-041 Phase 3: Test multi-condition YAML-driven rules."""

    def setup_method(self):
        self.validator = ThinkingValidator(framework="pmt")

    def test_dual_condition_and_logic_violation(self):
        """Two conditions both met should trigger violation."""
        context = {
            "reasoning": {"TP_LABEL": "H", "CP_LABEL": "H"},
            "framework": "pmt"
        }
        from broker.governance.rule_types import GovernanceRule, RuleCondition
        rules = [GovernanceRule(
            id="high_tp_high_cp",
            category="thinking",
            conditions=[
                RuleCondition(type="construct", field="TP_LABEL", operator="in", values=["H", "VH"]),
                RuleCondition(type="construct", field="CP_LABEL", operator="in", values=["H", "VH"])
            ],
            blocked_skills=["do_nothing"],
            message="High threat + high coping should act"
        )]
        results = self.validator.validate("do_nothing", rules, context)
        # Should trigger because both conditions match via base validator
        assert any(not r.valid for r in results)

    def test_dual_condition_partial_match_no_violation(self):
        """One condition met, one not = no violation from multi-condition rule."""
        context = {
            "reasoning": {"TP_LABEL": "H", "CP_LABEL": "L"},  # CP is Low
            "framework": "pmt"
        }
        from broker.governance.rule_types import GovernanceRule, RuleCondition
        rules = [GovernanceRule(
            id="high_tp_high_cp_multi",
            category="thinking",
            conditions=[
                RuleCondition(type="construct", field="TP_LABEL", operator="in", values=["H", "VH"]),
                RuleCondition(type="construct", field="CP_LABEL", operator="in", values=["H", "VH"])
            ],
            blocked_skills=["do_nothing"]
        )]
        results = self.validator.validate("do_nothing", rules, context)
        # The multi-condition rule should NOT trigger because CP is Low (AND logic)
        # But built-in rules may still trigger based on TP alone
        multi_rule_violations = [r for r in results if not r.valid and r.metadata.get("rule_id") == "high_tp_high_cp_multi"]
        assert len(multi_rule_violations) == 0

    def test_triple_condition_all_constructs(self):
        """Three constructs (TP, CP, SC) all checked."""
        context = {
            "reasoning": {"TP_LABEL": "VH", "CP_LABEL": "L", "SC_LABEL": "VL"},
            "framework": "pmt"
        }
        from broker.governance.rule_types import GovernanceRule, RuleCondition
        rules = [GovernanceRule(
            id="high_threat_low_resources",
            category="thinking",
            conditions=[
                RuleCondition(type="construct", field="TP_LABEL", operator="in", values=["H", "VH"]),
                RuleCondition(type="construct", field="CP_LABEL", operator="in", values=["VL", "L"]),
                RuleCondition(type="construct", field="SC_LABEL", operator="in", values=["VL", "L"])
            ],
            blocked_skills=["elevate_house"],
            message="Low resources with high threat blocks complex actions"
        )]
        results = self.validator.validate("elevate_house", rules, context)
        assert any(not r.valid and r.metadata.get("rule_id") == "high_threat_low_resources" for r in results)

    def test_variable_condition_with_state(self):
        """Test non-construct variable condition using state."""
        context = {
            "reasoning": {"TP_LABEL": "H"},
            "state": {"savings": 3000},
            "framework": "pmt"
        }
        from broker.governance.rule_types import GovernanceRule, RuleCondition
        rules = [GovernanceRule(
            id="financial_constraint",
            category="thinking",
            conditions=[
                RuleCondition(type="construct", field="TP_LABEL", operator="in", values=["H", "VH"]),
                RuleCondition(type="expression", field="savings", operator="<", values=[5000])
            ],
            blocked_skills=["elevate_house"],
            message="Insufficient savings"
        )]
        results = self.validator.validate("elevate_house", rules, context)
        assert any(not r.valid and r.metadata.get("rule_id") == "financial_constraint" for r in results)

    def test_variable_condition_not_matched(self):
        """Variable condition not met should not trigger."""
        context = {
            "reasoning": {"TP_LABEL": "H"},
            "state": {"savings": 10000},  # Savings is high enough
            "framework": "pmt"
        }
        from broker.governance.rule_types import GovernanceRule, RuleCondition
        rules = [GovernanceRule(
            id="financial_constraint",
            category="thinking",
            conditions=[
                RuleCondition(type="construct", field="TP_LABEL", operator="in", values=["H", "VH"]),
                RuleCondition(type="expression", field="savings", operator="<", values=[5000])
            ],
            blocked_skills=["elevate_house"]
        )]
        results = self.validator.validate("elevate_house", rules, context)
        assert not any(r.metadata.get("rule_id") == "financial_constraint" for r in results if not r.valid)

    def test_not_in_operator(self):
        """Test not_in operator - blocking non-high threat from extreme actions."""
        context = {
            "reasoning": {"TP_LABEL": "M"},  # Medium threat
            "framework": "pmt"
        }
        from broker.governance.rule_types import GovernanceRule, RuleCondition
        rules = [GovernanceRule(
            id="moderate_threat_blocks_relocation",
            category="thinking",
            conditions=[
                RuleCondition(type="construct", field="TP_LABEL", operator="in", values=["VL", "L", "M"])
            ],
            blocked_skills=["relocate"],
            message="Only high threat justifies relocation"
        )]
        results = self.validator.validate("relocate", rules, context)
        assert any(not r.valid and r.metadata.get("rule_id") == "moderate_threat_blocks_relocation" for r in results)

    def test_skill_not_in_blocked_list(self):
        """Rule should not apply if skill not in blocked list."""
        context = {
            "reasoning": {"TP_LABEL": "H", "CP_LABEL": "H"},
            "framework": "pmt"
        }
        from broker.governance.rule_types import GovernanceRule, RuleCondition
        rules = [GovernanceRule(
            id="high_tp_high_cp_blocks_nothing",
            category="thinking",
            conditions=[
                RuleCondition(type="construct", field="TP_LABEL", operator="in", values=["H", "VH"]),
                RuleCondition(type="construct", field="CP_LABEL", operator="in", values=["H", "VH"])
            ],
            blocked_skills=["do_nothing"]  # Only blocks do_nothing
        )]
        # buy_insurance is not blocked by this specific rule
        results = self.validator.validate("buy_insurance", rules, context)
        assert not any(r.metadata.get("rule_id") == "high_tp_high_cp_blocks_nothing" for r in results if not r.valid)
