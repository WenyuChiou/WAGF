"""
Tests for governance rule system (B.2-B.4).

Tests the rule definitions and validators:
- GovernanceRule evaluation
- RuleCondition types
- Category validators (Personal, Social, Thinking, Physical)
- Rule breakdown tracking
"""
import pytest
from broker.governance import (
    GovernanceRule,
    RuleCondition,
    validate_all,
    get_rule_breakdown,
    PersonalValidator,
    SocialValidator,
    ThinkingValidator,
    PhysicalValidator,
)
from examples.governed_flood.validators.flood_validators import (
    FLOOD_PHYSICAL_CHECKS,
    FLOOD_SOCIAL_CHECKS,
)


class TestRuleCondition:
    """Test RuleCondition evaluation."""

    def test_construct_condition_in_operator(self):
        """Test construct condition with 'in' operator."""
        cond = RuleCondition(
            type="construct",
            field="TP_LABEL",
            operator="in",
            values=["H", "VH"]
        )
        context = {"reasoning": {"TP_LABEL": "H"}}
        assert cond.evaluate(context) is True

        context = {"reasoning": {"TP_LABEL": "L"}}
        assert cond.evaluate(context) is False

    def test_precondition_equality(self):
        """Test precondition with equality operator."""
        cond = RuleCondition(
            type="precondition",
            field="elevated",
            operator="==",
            values=[True]
        )
        context = {"state": {"elevated": True}}
        assert cond.evaluate(context) is True

        context = {"state": {"elevated": False}}
        assert cond.evaluate(context) is False

    def test_expression_comparison(self):
        """Test expression condition with comparison."""
        cond = RuleCondition(
            type="expression",
            field="savings",
            operator=">=",
            values=[50000]
        )
        context = {"state": {"savings": 60000}}
        assert cond.evaluate(context) is True

        context = {"state": {"savings": 30000}}
        assert cond.evaluate(context) is False

    def test_social_condition(self):
        """Test social context condition."""
        cond = RuleCondition(
            type="social",
            field="elevated_neighbor_pct",
            operator=">",
            values=[0.5]
        )
        context = {"social_context": {"elevated_neighbor_pct": 0.7}}
        assert cond.evaluate(context) is True


class TestGovernanceRule:
    """Test GovernanceRule evaluation."""

    def test_rule_blocks_specified_skill(self):
        """Rule should only trigger for blocked skills."""
        rule = GovernanceRule(
            id="test_rule",
            category="thinking",
            blocked_skills=["do_nothing"],
            construct="TP_LABEL",
            when_above=["VH"],
            message="VH threat requires action"
        )
        context = {"reasoning": {"TP_LABEL": "VH"}}

        # Should trigger for do_nothing
        assert rule.evaluate("do_nothing", context) is True

        # Should not trigger for other skills
        assert rule.evaluate("elevate_house", context) is False

    def test_rule_with_modern_conditions(self):
        """Test rule with multiple conditions (all must match)."""
        rule = GovernanceRule(
            id="high_tp_cp_action",
            category="thinking",
            conditions=[
                RuleCondition(type="construct", field="TP_LABEL", operator="in", values=["H", "VH"]),
                RuleCondition(type="construct", field="CP_LABEL", operator="in", values=["H", "VH"]),
            ],
            blocked_skills=["do_nothing"],
            message="High threat + high coping should lead to action"
        )

        # Both conditions met
        context = {"reasoning": {"TP_LABEL": "H", "CP_LABEL": "VH"}}
        assert rule.evaluate("do_nothing", context) is True

        # Only one condition met
        context = {"reasoning": {"TP_LABEL": "H", "CP_LABEL": "L"}}
        assert rule.evaluate("do_nothing", context) is False

    def test_rule_from_dict(self):
        """Test creating rule from YAML-style dictionary."""
        data = {
            "id": "extreme_threat_requires_action",
            "category": "thinking",
            "construct": "TP_LABEL",
            "when_above": ["VH"],
            "blocked_skills": ["do_nothing"],
            "level": "ERROR",
            "message": "Extreme threat requires adaptation action"
        }
        rule = GovernanceRule.from_dict(data)

        assert rule.id == "extreme_threat_requires_action"
        assert rule.category == "thinking"
        assert rule.construct == "TP_LABEL"
        assert rule.when_above == ["VH"]

    def test_label_normalization(self):
        """Test PMT label normalization."""
        rule = GovernanceRule(
            id="test",
            category="thinking",
            blocked_skills=["do_nothing"],
            construct="TP_LABEL",
            when_above=["VH"]
        )

        # Various VH representations
        for label in ["VH", "VERY HIGH", "Very_High", "veryhigh"]:
            context = {"reasoning": {"TP_LABEL": label}}
            assert rule.evaluate("do_nothing", context) is True


class TestPhysicalValidator:
    """Test PhysicalValidator for state preconditions (flood domain)."""

    def test_already_elevated_blocked(self):
        """Cannot elevate if already elevated."""
        validator = PhysicalValidator(builtin_checks=list(FLOOD_PHYSICAL_CHECKS))
        context = {"state": {"elevated": True}}

        results = validator.validate("elevate_house", [], context)
        assert len(results) > 0
        assert results[0].valid is False
        assert "already elevated" in results[0].errors[0]

    def test_already_relocated_blocked(self):
        """Cannot do meaningful actions after relocation."""
        validator = PhysicalValidator(builtin_checks=list(FLOOD_PHYSICAL_CHECKS))
        context = {"state": {"relocated": True}}

        results = validator.validate("relocate", [], context)
        assert len(results) > 0
        assert results[0].valid is False

    def test_renter_restriction(self):
        """Renters cannot elevate or buyout."""
        validator = PhysicalValidator(builtin_checks=list(FLOOD_PHYSICAL_CHECKS))
        context = {"state": {"tenure": "renter"}}

        results = validator.validate("elevate_house", [], context)
        assert len(results) > 0
        assert results[0].valid is False
        assert "Renters" in results[0].errors[0]

    def test_owner_can_elevate(self):
        """Owners can elevate if not already elevated."""
        validator = PhysicalValidator(builtin_checks=list(FLOOD_PHYSICAL_CHECKS))
        context = {"state": {"tenure": "Owner", "elevated": False}}

        results = validator.validate("elevate_house", [], context)
        assert len(results) == 0  # No blocking results


class TestThinkingValidator:
    """Test ThinkingValidator for PMT consistency."""

    def test_high_tp_cp_blocks_do_nothing(self):
        """High TP + High CP should not result in do_nothing."""
        validator = ThinkingValidator()
        context = {"reasoning": {"TP_LABEL": "H", "CP_LABEL": "VH"}}

        results = validator.validate("do_nothing", [], context)
        assert any(not r.valid for r in results)

    def test_vh_threat_requires_action(self):
        """VH threat should require protective action."""
        validator = ThinkingValidator()
        context = {"reasoning": {"TP_LABEL": "VH", "CP_LABEL": "M"}}

        results = validator.validate("do_nothing", [], context)
        assert any(not r.valid for r in results)

    def test_low_tp_blocks_extreme_action(self):
        """Low TP should not justify extreme measures."""
        validator = ThinkingValidator(extreme_actions={"relocate", "elevate_house"})
        context = {"reasoning": {"TP_LABEL": "L", "CP_LABEL": "M"}}

        results = validator.validate("relocate", [], context)
        assert any(not r.valid for r in results)


class TestSocialValidator:
    """Test SocialValidator - WARNING only."""

    def test_social_rules_never_block(self):
        """Social validator should only produce warnings, not errors."""
        validator = SocialValidator(builtin_checks=list(FLOOD_SOCIAL_CHECKS))
        context = {
            "reasoning": {},
            "state": {},
            "social_context": {"elevated_neighbor_pct": 0.8}
        }

        results = validator.validate("do_nothing", [], context)
        # All results should be valid (warnings only)
        assert all(r.valid for r in results)
        # Should have warnings
        assert any(len(r.warnings) > 0 for r in results)


class TestValidateAll:
    """Test combined validation across all categories."""

    def test_validate_all_combines_results(self):
        """validate_all should run all validators."""
        context = {
            "reasoning": {"TP_LABEL": "VH", "CP_LABEL": "H"},
            "state": {"elevated": False, "tenure": "Owner"},
            "social_context": {"elevated_neighbor_pct": 0.6}
        }

        results = validate_all("do_nothing", [], context)
        # Should have results from thinking validator at minimum
        assert len(results) > 0

    def test_rule_breakdown_counts_categories(self):
        """get_rule_breakdown should count hits per category."""
        from broker.interfaces.skill_types import ValidationResult

        results = [
            ValidationResult(valid=False, validator_name="ThinkingValidator",
                           errors=["Error 1"], metadata={"category": "thinking"}),
            ValidationResult(valid=False, validator_name="ThinkingValidator",
                           errors=["Error 2"], metadata={"category": "thinking"}),
            ValidationResult(valid=False, validator_name="PhysicalValidator",
                           errors=["Error 3"], metadata={"category": "physical"}),
            ValidationResult(valid=True, validator_name="SocialValidator",
                           warnings=["Warn 1"], metadata={"category": "social"}),
        ]

        breakdown = get_rule_breakdown(results)
        assert breakdown["thinking"] == 2
        assert breakdown["physical"] == 1
        assert breakdown["social"] == 1
        assert breakdown["personal"] == 0
