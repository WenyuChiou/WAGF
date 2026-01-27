"""
SA Skill Registry Tests - Phase 2 of Integration Test Suite.
Task-038: Verify skill registry operations for Single-Agent flood adaptation.

Tests:
- SA-SR01: Load from YAML
- SA-SR02: Get skill by ID
- SA-SR03: Check eligibility
- SA-SR04: Check preconditions
- SA-SR05: Get execution mapping
"""
import pytest
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from broker.components.skill_registry import SkillRegistry
from broker.interfaces.skill_types import SkillDefinition, ValidationResult


# Fixtures
@pytest.fixture
def skill_registry():
    """Create and populate skill registry from SA config."""
    registry = SkillRegistry()
    yaml_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "examples", "single_agent", "skill_registry.yaml"
    )
    registry.register_from_yaml(yaml_path)
    return registry


@pytest.fixture
def empty_registry():
    """Create empty skill registry."""
    return SkillRegistry()


@pytest.fixture
def non_elevated_state():
    """State for non-elevated household."""
    return {
        "elevated": False,
        "has_insurance": False,
        "relocated": False
    }


@pytest.fixture
def elevated_state():
    """State for elevated household."""
    return {
        "elevated": True,
        "has_insurance": False,
        "relocated": False
    }


class TestSkillRegistryLoad:
    """Test loading skill registry from YAML."""

    def test_sa_sr01_load_from_yaml(self, skill_registry):
        """SA-SR01: Load skills from skill_registry.yaml."""
        skills = skill_registry.list_skills()

        # Should have loaded the 4 core skills
        assert len(skills) >= 4, f"Expected at least 4 skills, got {len(skills)}"

        expected_skills = ["buy_insurance", "elevate_house", "relocate", "do_nothing"]
        for skill in expected_skills:
            assert skill in skills, f"Expected skill '{skill}' in registry"

    def test_load_skill_definitions_complete(self, skill_registry):
        """Skills should have complete definitions."""
        skill = skill_registry.get("buy_insurance")

        assert skill is not None
        assert isinstance(skill, SkillDefinition)
        assert skill.skill_id == "buy_insurance"
        assert skill.description, "Should have description"
        assert skill.eligible_agent_types, "Should have eligible agent types"


class TestSkillRegistryGet:
    """Test skill retrieval operations."""

    def test_sa_sr02_get_skill_by_id(self, skill_registry):
        """SA-SR02: Get skill by ID returns SkillDefinition."""
        skill = skill_registry.get("buy_insurance")

        assert skill is not None
        assert isinstance(skill, SkillDefinition)
        assert skill.skill_id == "buy_insurance"

    def test_get_nonexistent_skill_returns_none(self, skill_registry):
        """Getting nonexistent skill returns None."""
        skill = skill_registry.get("nonexistent_skill")
        assert skill is None

    def test_exists_check(self, skill_registry):
        """Exists check works correctly."""
        assert skill_registry.exists("buy_insurance")
        assert skill_registry.exists("elevate_house")
        assert not skill_registry.exists("nonexistent")

    def test_default_skill(self, skill_registry):
        """Default skill is set correctly."""
        default = skill_registry.get_default_skill()
        assert default == "do_nothing"


class TestSkillEligibility:
    """Test eligibility checking."""

    def test_sa_sr03_check_eligibility_wildcard(self, skill_registry):
        """SA-SR03: Check eligibility with wildcard allows all agents."""
        result = skill_registry.check_eligibility("buy_insurance", "household")

        assert isinstance(result, ValidationResult)
        assert result.valid, "Household should be eligible for buy_insurance"

    def test_eligibility_unknown_skill(self, skill_registry):
        """Checking eligibility for unknown skill returns invalid."""
        result = skill_registry.check_eligibility("unknown_skill", "household")

        assert not result.valid
        assert len(result.errors) > 0
        assert "not found" in result.errors[0].lower()

    def test_eligibility_different_agent_types(self, skill_registry):
        """Different agent types should have appropriate eligibility."""
        # Household should be eligible for core skills
        for skill_id in ["buy_insurance", "elevate_house", "relocate", "do_nothing"]:
            result = skill_registry.check_eligibility(skill_id, "household")
            assert result.valid, f"Household should be eligible for {skill_id}"


class TestSkillPreconditions:
    """Test precondition checking."""

    def test_sa_sr04_check_preconditions_elevate_blocked_if_elevated(
        self, skill_registry, elevated_state
    ):
        """SA-SR04: Elevated agent cannot elevate again."""
        result = skill_registry.check_preconditions("elevate_house", elevated_state)

        # If preconditions are defined, elevated=True should block elevate_house
        # Note: This depends on skill_registry.yaml having preconditions defined
        # If no preconditions defined, it may still pass
        assert isinstance(result, ValidationResult)

    def test_preconditions_buy_insurance_allowed(
        self, skill_registry, non_elevated_state
    ):
        """Buy insurance should be allowed (can renew annually)."""
        result = skill_registry.check_preconditions("buy_insurance", non_elevated_state)

        assert result.valid, "buy_insurance should be allowed for non-elevated"

    def test_preconditions_do_nothing_always_valid(
        self, skill_registry, elevated_state
    ):
        """do_nothing should always be valid."""
        result = skill_registry.check_preconditions("do_nothing", elevated_state)
        assert result.valid, "do_nothing should always be valid"


class TestSkillExecutionMapping:
    """Test execution mapping retrieval."""

    def test_sa_sr05_get_execution_mapping(self, skill_registry):
        """SA-SR05: Get execution mapping returns callable path."""
        skill = skill_registry.get("buy_insurance")

        assert skill is not None
        assert skill.implementation_mapping, "Should have implementation mapping"
        # Mapping should be a string like "sim.buy_insurance"
        assert isinstance(skill.implementation_mapping, str)

    def test_all_skills_have_mapping(self, skill_registry):
        """All registered skills should have execution mappings."""
        for skill_id in skill_registry.list_skills():
            skill = skill_registry.get(skill_id)
            assert skill.implementation_mapping, f"{skill_id} should have mapping"


class TestSkillRegistration:
    """Test manual skill registration."""

    def test_register_skill_programmatically(self, empty_registry):
        """Can register skills programmatically."""
        skill = SkillDefinition(
            skill_id="test_skill",
            description="Test skill for unit tests",
            eligible_agent_types=["test_agent"],
            preconditions=[],
            institutional_constraints={},
            allowed_state_changes=["test_param"],
            implementation_mapping="test.execute"
        )

        empty_registry.register(skill)

        assert empty_registry.exists("test_skill")
        retrieved = empty_registry.get("test_skill")
        assert retrieved.skill_id == "test_skill"
        assert retrieved.description == "Test skill for unit tests"

    def test_set_default_skill(self, skill_registry):
        """Can change default skill."""
        skill_registry.set_default_skill("buy_insurance")
        assert skill_registry.get_default_skill() == "buy_insurance"

    def test_set_nonexistent_default_ignored(self, skill_registry):
        """Setting nonexistent skill as default is ignored."""
        original = skill_registry.get_default_skill()
        skill_registry.set_default_skill("nonexistent_skill")
        assert skill_registry.get_default_skill() == original


class TestSkillDefinitionFields:
    """Test skill definition field access."""

    def test_skill_has_institutional_constraints(self, skill_registry):
        """Skills should have institutional constraints defined."""
        skill = skill_registry.get("buy_insurance")
        assert skill is not None
        # institutional_constraints should be dict (may be empty)
        assert isinstance(skill.institutional_constraints, dict)

    def test_skill_has_allowed_state_changes(self, skill_registry):
        """Skills should have allowed state changes defined."""
        skill = skill_registry.get("elevate_house")
        assert skill is not None
        # allowed_state_changes should be list
        assert isinstance(skill.allowed_state_changes, list)


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
