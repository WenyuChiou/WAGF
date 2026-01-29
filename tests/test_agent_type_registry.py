"""
Tests for Agent Type Registry (Task-040: SA/MA Unified Architecture).

Tests the AgentTypeRegistry, AgentTypeDefinition, and related types.
"""
import pytest
from pathlib import Path
import tempfile
import yaml

from broker.config.agent_types import (
    AgentTypeRegistry,
    AgentTypeDefinition,
    AgentCategory,
    PsychologicalFramework,
    ConstructDefinition,
    ResponseFormatSpec,
    ResponseFieldDefinition,
    ValidationConfig,
    ValidationRuleRef,
    MemoryConfigSpec,
    create_default_registry,
    get_default_registry,
    reset_default_registry,
    DEFAULT_PMT_CONSTRUCTS,
)


class TestConstructDefinition:
    """Test ConstructDefinition."""

    def test_create_construct(self):
        """Test basic construct creation."""
        construct = ConstructDefinition(
            name="Threat Perception",
            key="TP_LABEL",
            values=["VL", "L", "M", "H", "VH"],
            description="Perceived threat level",
            required=True,
        )
        assert construct.name == "Threat Perception"
        assert construct.key == "TP_LABEL"
        assert len(construct.values) == 5

    def test_validate_valid_value(self):
        """Test validation with valid value."""
        construct = ConstructDefinition(
            name="Test",
            key="TEST",
            values=["A", "B", "C"],
        )
        assert construct.validate("A") is True
        assert construct.validate("a") is True  # Case insensitive

    def test_validate_invalid_value(self):
        """Test validation with invalid value."""
        construct = ConstructDefinition(
            name="Test",
            key="TEST",
            values=["A", "B", "C"],
        )
        assert construct.validate("D") is False

    def test_validate_no_constraint(self):
        """Test validation with no value constraints."""
        construct = ConstructDefinition(name="Test", key="TEST")
        assert construct.validate("anything") is True


class TestResponseFormatSpec:
    """Test ResponseFormatSpec."""

    def test_from_dict(self):
        """Test creating ResponseFormatSpec from dictionary."""
        data = {
            "delimiter_start": "<<<START>>>",
            "delimiter_end": "<<<END>>>",
            "fields": [
                {"key": "threat", "type": "appraisal", "construct": "TP_LABEL"},
                {"key": "decision", "type": "choice", "required": True},
            ]
        }
        spec = ResponseFormatSpec.from_dict(data)
        assert spec.delimiter_start == "<<<START>>>"
        assert len(spec.fields) == 2
        assert spec.fields[0].construct == "TP_LABEL"


class TestAgentTypeDefinition:
    """Test AgentTypeDefinition."""

    def test_create_basic_definition(self):
        """Test basic definition creation."""
        defn = AgentTypeDefinition(
            type_id="test_agent",
            category=AgentCategory.HOUSEHOLD,
            psychological_framework=PsychologicalFramework.PMT,
            eligible_skills=["skill_a", "skill_b"],
        )
        assert defn.type_id == "test_agent"
        assert defn.category == AgentCategory.HOUSEHOLD
        assert defn.psychological_framework == PsychologicalFramework.PMT

    def test_from_dict_basic(self):
        """Test creating definition from dictionary."""
        data = {
            "type_id": "household_owner",
            "category": "household",
            "psychological_framework": "pmt",
            "eligible_skills": ["buy_insurance", "elevate_house"],
        }
        defn = AgentTypeDefinition.from_dict(data)
        assert defn.type_id == "household_owner"
        assert defn.category == AgentCategory.HOUSEHOLD
        assert "buy_insurance" in defn.eligible_skills

    def test_from_dict_with_constructs(self):
        """Test creating definition with constructs."""
        data = {
            "type_id": "test",
            "category": "household",
            "constructs": {
                "TP_LABEL": {
                    "name": "Threat Perception",
                    "values": ["L", "M", "H"],
                    "required": True,
                }
            }
        }
        defn = AgentTypeDefinition.from_dict(data)
        assert "TP_LABEL" in defn.constructs
        assert defn.constructs["TP_LABEL"].values == ["L", "M", "H"]

    def test_from_dict_with_validation(self):
        """Test creating definition with validation rules."""
        data = {
            "type_id": "test",
            "category": "household",
            "validation": {
                "identity_rules": [
                    {"id": "rule1", "precondition": "elevated", "blocked_skills": ["elevate_house"]}
                ],
                "thinking_rules": [
                    {"id": "rule2", "construct": "TP_LABEL", "when_above": ["VH"], "blocked_skills": ["do_nothing"]}
                ]
            }
        }
        defn = AgentTypeDefinition.from_dict(data)
        assert defn.validation is not None
        assert len(defn.validation.identity_rules) == 1
        assert len(defn.validation.thinking_rules) == 1

    def test_is_skill_eligible(self):
        """Test skill eligibility check."""
        defn = AgentTypeDefinition(
            type_id="test",
            category=AgentCategory.HOUSEHOLD,
            eligible_skills=["skill_a", "skill_b"],
        )
        assert defn.is_skill_eligible("skill_a") is True
        assert defn.is_skill_eligible("skill_c") is False

    def test_is_skill_eligible_no_restriction(self):
        """Test skill eligibility with no restrictions."""
        defn = AgentTypeDefinition(
            type_id="test",
            category=AgentCategory.HOUSEHOLD,
            eligible_skills=[],  # No restrictions
        )
        assert defn.is_skill_eligible("any_skill") is True

    def test_to_dict(self):
        """Test serialization to dictionary."""
        defn = AgentTypeDefinition(
            type_id="test",
            category=AgentCategory.HOUSEHOLD,
            psychological_framework=PsychologicalFramework.PMT,
            eligible_skills=["skill_a"],
            description="Test agent",
        )
        data = defn.to_dict()
        assert data["type_id"] == "test"
        assert data["category"] == "household"
        assert data["psychological_framework"] == "pmt"


class TestAgentTypeRegistry:
    """Test AgentTypeRegistry."""

    def test_register_and_get(self):
        """Test registering and retrieving types."""
        registry = AgentTypeRegistry()
        defn = AgentTypeDefinition(
            type_id="test_type",
            category=AgentCategory.HOUSEHOLD,
        )
        registry.register(defn)

        result = registry.get("test_type")
        assert result is not None
        assert result.type_id == "test_type"

    def test_register_duplicate_raises(self):
        """Test that registering duplicate raises error."""
        registry = AgentTypeRegistry()
        defn = AgentTypeDefinition(
            type_id="test_type",
            category=AgentCategory.HOUSEHOLD,
        )
        registry.register(defn)

        with pytest.raises(ValueError, match="already registered"):
            registry.register(defn)

    def test_register_empty_type_id_raises(self):
        """Test that empty type_id raises error."""
        registry = AgentTypeRegistry()
        defn = AgentTypeDefinition(
            type_id="",
            category=AgentCategory.HOUSEHOLD,
        )

        with pytest.raises(ValueError, match="non-empty"):
            registry.register(defn)

    def test_get_nonexistent_returns_none(self):
        """Test getting nonexistent type returns None."""
        registry = AgentTypeRegistry()
        assert registry.get("nonexistent") is None

    def test_get_by_category(self):
        """Test filtering by category."""
        registry = AgentTypeRegistry()
        registry.register(AgentTypeDefinition(
            type_id="household1",
            category=AgentCategory.HOUSEHOLD,
        ))
        registry.register(AgentTypeDefinition(
            type_id="gov1",
            category=AgentCategory.INSTITUTIONAL,
        ))

        households = registry.get_by_category(AgentCategory.HOUSEHOLD)
        assert len(households) == 1
        assert households[0].type_id == "household1"

    def test_get_by_framework(self):
        """Test filtering by psychological framework."""
        registry = AgentTypeRegistry()
        registry.register(AgentTypeDefinition(
            type_id="pmt_agent",
            category=AgentCategory.HOUSEHOLD,
            psychological_framework=PsychologicalFramework.PMT,
        ))
        registry.register(AgentTypeDefinition(
            type_id="utility_agent",
            category=AgentCategory.INSTITUTIONAL,
            psychological_framework=PsychologicalFramework.UTILITY,
        ))

        pmt_agents = registry.get_by_framework(PsychologicalFramework.PMT)
        assert len(pmt_agents) == 1
        assert pmt_agents[0].type_id == "pmt_agent"

    def test_get_eligible_skills(self):
        """Test getting eligible skills for type."""
        registry = AgentTypeRegistry()
        registry.register(AgentTypeDefinition(
            type_id="test",
            category=AgentCategory.HOUSEHOLD,
            eligible_skills=["skill_a", "skill_b"],
        ))

        skills = registry.get_eligible_skills("test")
        assert skills == ["skill_a", "skill_b"]

    def test_is_skill_eligible(self):
        """Test skill eligibility through registry."""
        registry = AgentTypeRegistry()
        registry.register(AgentTypeDefinition(
            type_id="test",
            category=AgentCategory.HOUSEHOLD,
            eligible_skills=["skill_a"],
        ))

        assert registry.is_skill_eligible("test", "skill_a") is True
        assert registry.is_skill_eligible("test", "skill_b") is False

    def test_list_types(self):
        """Test listing all type IDs."""
        registry = AgentTypeRegistry()
        registry.register(AgentTypeDefinition(type_id="type1", category=AgentCategory.HOUSEHOLD))
        registry.register(AgentTypeDefinition(type_id="type2", category=AgentCategory.HOUSEHOLD))

        types = registry.list_types()
        assert "type1" in types
        assert "type2" in types

    def test_has_type(self):
        """Test checking if type exists."""
        registry = AgentTypeRegistry()
        registry.register(AgentTypeDefinition(type_id="exists", category=AgentCategory.HOUSEHOLD))

        assert registry.has_type("exists") is True
        assert registry.has_type("not_exists") is False

    def test_clear(self):
        """Test clearing registry."""
        registry = AgentTypeRegistry()
        registry.register(AgentTypeDefinition(type_id="test", category=AgentCategory.HOUSEHOLD))
        assert len(registry) == 1

        registry.clear()
        assert len(registry) == 0

    def test_len_and_contains(self):
        """Test __len__ and __contains__."""
        registry = AgentTypeRegistry()
        registry.register(AgentTypeDefinition(type_id="test", category=AgentCategory.HOUSEHOLD))

        assert len(registry) == 1
        assert "test" in registry
        assert "other" not in registry


class TestRegistryInheritance:
    """Test agent type inheritance resolution."""

    def test_simple_inheritance(self):
        """Test simple parent-child inheritance."""
        registry = AgentTypeRegistry()

        # Parent type
        parent = AgentTypeDefinition(
            type_id="parent",
            category=AgentCategory.HOUSEHOLD,
            psychological_framework=PsychologicalFramework.PMT,
            eligible_skills=["skill_a", "skill_b"],
            context_template="parent_template.txt",
        )
        registry.register(parent)

        # Child type (inherits from parent)
        child = AgentTypeDefinition(
            type_id="child",
            category=AgentCategory.HOUSEHOLD,
            psychological_framework=PsychologicalFramework.PMT,
            parent="parent",
            eligible_skills=["skill_c"],  # Override
        )
        registry.register(child)

        resolved = registry.get("child")
        assert resolved is not None
        # Child should override eligible_skills
        assert resolved.eligible_skills == ["skill_c"]
        # Child should inherit context_template
        assert resolved.context_template == "parent_template.txt"

    def test_construct_merge(self):
        """Test that constructs are merged (child extends parent)."""
        registry = AgentTypeRegistry()

        parent = AgentTypeDefinition(
            type_id="parent",
            category=AgentCategory.HOUSEHOLD,
            constructs={
                "TP_LABEL": ConstructDefinition(name="TP", key="TP_LABEL", values=["L", "M", "H"]),
            },
        )
        registry.register(parent)

        child = AgentTypeDefinition(
            type_id="child",
            category=AgentCategory.HOUSEHOLD,
            parent="parent",
            constructs={
                "CP_LABEL": ConstructDefinition(name="CP", key="CP_LABEL", values=["L", "M", "H"]),
            },
        )
        registry.register(child)

        resolved = registry.get("child")
        # Should have both constructs
        assert "TP_LABEL" in resolved.constructs
        assert "CP_LABEL" in resolved.constructs


class TestRegistryYAMLLoading:
    """Test YAML loading functionality."""

    def test_load_from_yaml(self):
        """Test loading from YAML file."""
        yaml_content = """
agent_types:
  household_owner:
    type_id: household_owner
    category: household
    psychological_framework: pmt
    eligible_skills:
      - buy_insurance
      - elevate_house
    description: Test household owner
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            registry = AgentTypeRegistry()
            count = registry.load_from_yaml(Path(f.name))

            assert count == 1
            defn = registry.get("household_owner")
            assert defn is not None
            assert defn.category == AgentCategory.HOUSEHOLD

    def test_load_from_dict(self):
        """Test loading from dictionary."""
        data = {
            "agent_types": {
                "type1": {
                    "type_id": "type1",
                    "category": "household",
                    "eligible_skills": ["skill_a"],
                },
                "type2": {
                    "type_id": "type2",
                    "category": "institutional",
                    "psychological_framework": "utility",
                },
            }
        }

        registry = AgentTypeRegistry()
        count = registry.load_from_dict(data)

        assert count == 2
        assert registry.has_type("type1")
        assert registry.has_type("type2")

    def test_load_legacy_format(self):
        """Test loading legacy format (backward compatible)."""
        data = {
            "household": {
                "category": "household",
                "eligible_skills": ["skill_a"],
            },
            "global_config": {"memory": {}},  # Should be ignored
        }

        registry = AgentTypeRegistry()
        count = registry.load_from_dict(data)

        assert count == 1
        assert registry.has_type("household")

    def test_load_nonexistent_file_raises(self):
        """Test loading nonexistent file raises error."""
        registry = AgentTypeRegistry()

        with pytest.raises(FileNotFoundError):
            registry.load_from_yaml(Path("/nonexistent/path.yaml"))


class TestDefaultRegistry:
    """Test default registry functions."""

    def test_create_default_registry(self):
        """Test creating default registry."""
        registry = create_default_registry()

        assert len(registry) >= 1
        assert registry.has_type("household")

    def test_get_default_registry_singleton(self):
        """Test that get_default_registry returns singleton."""
        reset_default_registry()

        reg1 = get_default_registry()
        reg2 = get_default_registry()

        assert reg1 is reg2

    def test_reset_default_registry(self):
        """Test resetting default registry."""
        reg1 = get_default_registry()
        reset_default_registry()
        reg2 = get_default_registry()

        assert reg1 is not reg2

    def test_default_household_has_pmt(self):
        """Test default household uses PMT framework."""
        registry = create_default_registry()
        defn = registry.get("household")

        assert defn.psychological_framework == PsychologicalFramework.PMT


class TestMemoryConfigSpec:
    """Test MemoryConfigSpec."""

    def test_from_dict(self):
        """Test creating MemoryConfigSpec from dictionary."""
        data = {
            "engine": "unified",
            "surprise_strategy": "hybrid",
            "arousal_threshold": 0.6,
            "emotional_weights": {"direct_impact": 1.0},
        }
        config = MemoryConfigSpec.from_dict(data)

        assert config.engine == "unified"
        assert config.surprise_strategy == "hybrid"
        assert config.arousal_threshold == 0.6

    def test_defaults(self):
        """Test default values."""
        config = MemoryConfigSpec()

        assert config.engine == "unified"
        assert config.surprise_strategy == "ema"
        assert config.arousal_threshold == 0.5


class TestDefaultPMTConstructs:
    """Test default PMT constructs."""

    def test_default_pmt_constructs_exist(self):
        """Test that default PMT constructs are defined."""
        assert "TP_LABEL" in DEFAULT_PMT_CONSTRUCTS
        assert "CP_LABEL" in DEFAULT_PMT_CONSTRUCTS

    def test_pmt_construct_values(self):
        """Test PMT construct values."""
        tp = DEFAULT_PMT_CONSTRUCTS["TP_LABEL"]
        assert tp.values == ["VL", "L", "M", "H", "VH"]
        assert tp.required is True
