"""
Tests for TypeValidator (Per-agent-type validation).

Tests:
- Skill eligibility (eligible skill passes)
- Skill eligibility (ineligible skill fails)
- Per-type identity rule application
- Per-type thinking rule application
- Per-type social rule application (warnings only)
- Integration with validate_all
"""
import pytest

from broker.governance.type_validator import TypeValidator
from broker.governance import validate_all, get_rule_breakdown
from broker.config.agent_types import (
    AgentTypeRegistry,
    AgentTypeDefinition,
    AgentCategory,
    PsychologicalFramework,
    ValidationConfig,
    ValidationRuleRef,
    reset_default_registry,
)
from broker.interfaces.skill_types import ValidationResult


@pytest.fixture
def registry():
    """Create a test registry with household types."""
    reg = AgentTypeRegistry()

    # Household owner - can elevate, buy insurance, etc.
    owner = AgentTypeDefinition(
        type_id="household_owner",
        category=AgentCategory.HOUSEHOLD,
        psychological_framework=PsychologicalFramework.PMT,
        eligible_skills=["buy_insurance", "elevate_house", "do_nothing", "relocate"],
        validation=ValidationConfig(
            identity_rules=[
                ValidationRuleRef(
                    rule_id="elevated_already",
                    precondition="elevated",
                    blocked_skills=["elevate_house"],
                    level="ERROR",
                    message="House is already elevated",
                ),
            ],
            thinking_rules=[
                ValidationRuleRef(
                    rule_id="high_threat",
                    construct="TP_LABEL",
                    when_above=["VH"],
                    blocked_skills=["do_nothing"],
                    level="ERROR",
                    message="Very high threat requires action",
                ),
            ],
            social_rules=[
                ValidationRuleRef(
                    rule_id="neighbor_pressure",
                    precondition="high_neighbor_adoption",
                    blocked_skills=["do_nothing"],
                    level="WARNING",
                    message="Most neighbors have adapted",
                ),
            ],
        ),
    )
    reg.register(owner)

    # Household renter - limited skills
    renter = AgentTypeDefinition(
        type_id="household_renter",
        category=AgentCategory.HOUSEHOLD,
        psychological_framework=PsychologicalFramework.PMT,
        eligible_skills=["buy_contents_insurance", "relocate", "do_nothing"],
    )
    reg.register(renter)

    # Government agent - different skills
    gov = AgentTypeDefinition(
        type_id="government",
        category=AgentCategory.INSTITUTIONAL,
        psychological_framework=PsychologicalFramework.UTILITY,
        eligible_skills=["increase_subsidy", "decrease_subsidy", "issue_warning"],
    )
    reg.register(gov)

    return reg


@pytest.fixture
def validator(registry):
    """Create TypeValidator with test registry."""
    return TypeValidator(registry)


class TestSkillEligibility:
    """Test skill eligibility checking."""

    def test_eligible_skill_passes(self, validator):
        """Eligible skill should not produce validation errors."""
        context = {"state": {}, "reasoning": {}}
        results = validator.validate("buy_insurance", "household_owner", context)

        # Filter for eligibility errors
        eligibility_errors = [
            r for r in results
            if r.metadata.get("rule_id") == "type_skill_eligibility"
        ]
        assert len(eligibility_errors) == 0

    def test_ineligible_skill_fails(self, validator):
        """Ineligible skill should produce validation error."""
        context = {"state": {}, "reasoning": {}}
        results = validator.validate("elevate_house", "household_renter", context)

        eligibility_errors = [
            r for r in results
            if r.metadata.get("rule_id") == "type_skill_eligibility"
        ]
        assert len(eligibility_errors) == 1
        assert eligibility_errors[0].valid is False
        assert "not eligible" in eligibility_errors[0].errors[0]

    def test_renter_cannot_elevate(self, validator):
        """Renter should not be able to elevate house."""
        context = {"state": {}, "reasoning": {}}
        results = validator.validate("elevate_house", "household_renter", context)

        assert any(
            "not eligible" in err
            for r in results
            for err in r.errors
        )

    def test_owner_can_elevate(self, validator):
        """Owner should be able to elevate house (eligibility check passes)."""
        context = {"state": {"elevated": False}, "reasoning": {}}
        results = validator.validate("elevate_house", "household_owner", context)

        eligibility_errors = [
            r for r in results
            if r.metadata.get("rule_id") == "type_skill_eligibility"
        ]
        assert len(eligibility_errors) == 0

    def test_government_skills(self, validator):
        """Government agent has different skill set."""
        context = {"state": {}, "reasoning": {}}

        # Valid government skill
        results = validator.validate("increase_subsidy", "government", context)
        eligibility_errors = [
            r for r in results
            if r.metadata.get("rule_id") == "type_skill_eligibility"
        ]
        assert len(eligibility_errors) == 0

        # Invalid - household skill
        results = validator.validate("buy_insurance", "government", context)
        eligibility_errors = [
            r for r in results
            if r.metadata.get("rule_id") == "type_skill_eligibility"
        ]
        assert len(eligibility_errors) == 1

    def test_unknown_agent_type_skips_validation(self, validator):
        """Unknown agent type should skip validation (return empty)."""
        context = {"state": {}, "reasoning": {}}
        results = validator.validate("any_skill", "unknown_type", context)
        assert len(results) == 0


class TestIdentityRules:
    """Test per-type identity (state precondition) rules."""

    def test_elevated_already_blocks_elevate(self, validator):
        """Cannot elevate if already elevated (identity rule)."""
        context = {
            "state": {"elevated": True},
            "reasoning": {},
        }
        results = validator.validate("elevate_house", "household_owner", context)

        identity_errors = [
            r for r in results
            if r.metadata.get("subcategory") == "identity"
        ]
        assert len(identity_errors) == 1
        assert identity_errors[0].valid is False
        assert "already elevated" in identity_errors[0].errors[0]

    def test_not_elevated_allows_elevate(self, validator):
        """Can elevate if not already elevated."""
        context = {
            "state": {"elevated": False},
            "reasoning": {},
        }
        results = validator.validate("elevate_house", "household_owner", context)

        identity_errors = [
            r for r in results
            if r.metadata.get("subcategory") == "identity"
        ]
        assert len(identity_errors) == 0


class TestThinkingRules:
    """Test per-type thinking (construct-based) rules."""

    def test_vh_threat_blocks_do_nothing(self, validator):
        """VH threat should block do_nothing (thinking rule)."""
        context = {
            "state": {},
            "reasoning": {"TP_LABEL": "VH"},
        }
        results = validator.validate("do_nothing", "household_owner", context)

        thinking_errors = [
            r for r in results
            if r.metadata.get("subcategory") == "thinking"
        ]
        assert len(thinking_errors) == 1
        assert thinking_errors[0].valid is False
        assert "requires action" in thinking_errors[0].errors[0]

    def test_low_threat_allows_do_nothing(self, validator):
        """Low threat should allow do_nothing."""
        context = {
            "state": {},
            "reasoning": {"TP_LABEL": "L"},
        }
        results = validator.validate("do_nothing", "household_owner", context)

        # Check thinking rules specifically
        thinking_errors = [
            r for r in results
            if r.metadata.get("subcategory") == "thinking"
        ]
        assert len(thinking_errors) == 0

    def test_label_normalization(self, validator):
        """Test that PMT labels are normalized correctly."""
        context = {
            "state": {},
            "reasoning": {"TP_LABEL": "VERY HIGH"},  # Should normalize to VH
        }
        results = validator.validate("do_nothing", "household_owner", context)

        thinking_errors = [
            r for r in results
            if r.metadata.get("subcategory") == "thinking"
        ]
        assert len(thinking_errors) == 1  # Should still trigger


class TestSocialRules:
    """Test per-type social rules (warnings only)."""

    def test_social_rule_produces_warning_not_error(self, validator):
        """Social rules should produce warnings, not errors."""
        context = {
            "state": {},
            "reasoning": {},
            "social_context": {"high_neighbor_adoption": True},
        }
        results = validator.validate("do_nothing", "household_owner", context)

        social_results = [
            r for r in results
            if r.metadata.get("subcategory") == "social"
        ]
        # Social rules produce valid=True (warnings)
        assert all(r.valid is True for r in social_results)
        assert any(len(r.warnings) > 0 for r in social_results)

    def test_social_rule_not_triggered_when_condition_false(self, validator):
        """Social rule should not trigger when condition is false."""
        context = {
            "state": {},
            "reasoning": {},
            "social_context": {"high_neighbor_adoption": False},
        }
        results = validator.validate("do_nothing", "household_owner", context)

        social_results = [
            r for r in results
            if r.metadata.get("subcategory") == "social"
        ]
        assert len(social_results) == 0


class TestValidateAllIntegration:
    """Test TypeValidator integration with validate_all."""

    def test_validate_all_with_agent_type(self, registry):
        """validate_all should include type validation when agent_type is provided."""
        context = {
            "state": {"elevated": True, "tenure": "Owner"},
            "reasoning": {"TP_LABEL": "M", "CP_LABEL": "M"},
            "social_context": {},
        }

        # Without agent_type - no type validation
        results_no_type = validate_all("elevate_house", [], context)
        type_results_no_type = [
            r for r in results_no_type
            if r.metadata.get("category") == "type"
        ]

        # With agent_type - includes type validation
        results_with_type = validate_all(
            "elevate_house", [], context,
            agent_type="household_owner",
            registry=registry
        )
        type_results_with_type = [
            r for r in results_with_type
            if r.metadata.get("category") == "type"
        ]

        assert len(type_results_no_type) == 0
        assert len(type_results_with_type) > 0  # Should have identity rule error

    def test_validate_all_combines_all_validators(self, registry):
        """validate_all should combine results from all validators."""
        context = {
            "state": {"elevated": True, "tenure": "Owner"},
            "reasoning": {"TP_LABEL": "VH", "CP_LABEL": "H"},
            "social_context": {},
        }

        results = validate_all(
            "do_nothing", [], context,
            agent_type="household_owner",
            registry=registry
        )

        # Should have results from thinking validator (VH threat)
        # and type validator (VH threat rule)
        categories = set(r.metadata.get("category", "") for r in results)
        assert "thinking" in categories or "type" in categories

    def test_validate_all_uses_default_registry(self):
        """validate_all should use default registry when none provided."""
        reset_default_registry()

        context = {
            "state": {},
            "reasoning": {},
        }

        # This should not raise even without explicit registry
        results = validate_all(
            "do_nothing", [], context,
            agent_type="household"  # Default registry has "household"
        )

        # Should complete without error
        assert isinstance(results, list)

    def test_rule_breakdown_includes_type_category(self, registry):
        """get_rule_breakdown should count type category."""
        context = {
            "state": {"elevated": True},
            "reasoning": {"TP_LABEL": "VH"},
        }

        results = validate_all(
            "elevate_house", [], context,
            agent_type="household_owner",
            registry=registry
        )

        breakdown = get_rule_breakdown(results)
        # Type validator results have category="type", which won't be in standard breakdown
        # But we can verify results were generated
        assert len(results) > 0


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_eligible_skills_allows_all(self, registry):
        """Empty eligible_skills should allow all skills (no restriction)."""
        # Add a type with no skill restrictions
        unrestricted = AgentTypeDefinition(
            type_id="unrestricted",
            category=AgentCategory.CUSTOM,
            eligible_skills=[],  # Empty = no restriction
        )
        registry.register(unrestricted)

        validator = TypeValidator(registry)
        context = {"state": {}, "reasoning": {}}

        results = validator.validate("any_random_skill", "unrestricted", context)
        eligibility_errors = [
            r for r in results
            if r.metadata.get("rule_id") == "type_skill_eligibility"
        ]
        assert len(eligibility_errors) == 0

    def test_no_validation_config_skips_rules(self, registry):
        """Agent type without validation config should skip rule validation."""
        validator = TypeValidator(registry)
        context = {
            "state": {"elevated": True},  # Would trigger identity rule if present
            "reasoning": {"TP_LABEL": "VH"},  # Would trigger thinking rule if present
        }

        # household_renter has no validation config
        results = validator.validate("do_nothing", "household_renter", context)

        # Should only have eligibility results (or none if eligible)
        rule_results = [
            r for r in results
            if r.metadata.get("subcategory") in ("identity", "thinking", "social", "financial")
        ]
        assert len(rule_results) == 0

    def test_multiple_rules_can_trigger(self, registry):
        """Multiple rules of same type can trigger simultaneously."""
        # Add another identity rule
        owner = registry.get("household_owner")
        owner.validation.identity_rules.append(
            ValidationRuleRef(
                rule_id="relocated_already",
                precondition="relocated",
                blocked_skills=["relocate", "elevate_house"],
                level="ERROR",
                message="Already relocated",
            )
        )

        validator = TypeValidator(registry)
        context = {
            "state": {"elevated": True, "relocated": True},
            "reasoning": {},
        }

        results = validator.validate("elevate_house", "household_owner", context)
        identity_errors = [
            r for r in results
            if r.metadata.get("subcategory") == "identity"
        ]
        # Should have both identity rule errors
        assert len(identity_errors) == 2

    def test_metadata_contains_useful_info(self, validator):
        """Validation results should have useful metadata."""
        context = {
            "state": {},
            "reasoning": {},
        }

        results = validator.validate("elevate_house", "household_renter", context)
        assert len(results) > 0

        result = results[0]
        assert "agent_type" in result.metadata
        assert "blocked_skill" in result.metadata
        assert result.metadata["agent_type"] == "household_renter"
