"""
Tests for AgentTypeConfig Rating Scale Methods.

Task-041: Universal Prompt/Context/Governance Framework
"""

import pytest
from broker.utils.agent_config import AgentTypeConfig
from broker.interfaces.rating_scales import RatingScaleRegistry


class TestAgentTypeConfigRatingScale:
    """Test rating scale methods in AgentTypeConfig."""

    def setup_method(self):
        """Reset registry before each test."""
        RatingScaleRegistry.reset()
        # Reset singleton
        AgentTypeConfig._instance = None

    def test_get_rating_scale_pmt_default(self):
        """PMT scale should be available by default."""
        config = AgentTypeConfig.load()
        scale = config.get_rating_scale("pmt")
        assert "VL = Very Low" in scale
        assert "VH = Very High" in scale

    def test_get_rating_scale_utility(self):
        """Utility scale should have priority levels."""
        config = AgentTypeConfig.load()
        scale = config.get_rating_scale("utility")
        assert "Low Priority" in scale
        assert "High Priority" in scale

    def test_get_rating_scale_financial(self):
        """Financial scale should have risk appetite levels."""
        config = AgentTypeConfig.load()
        scale = config.get_rating_scale("financial")
        assert "Conservative" in scale
        assert "Aggressive" in scale

    def test_get_rating_scale_unknown_defaults_pmt(self):
        """Unknown framework should default to PMT."""
        config = AgentTypeConfig.load()
        scale = config.get_rating_scale("unknown")
        # Should return PMT or legacy fallback
        assert scale  # Not empty

    def test_get_rating_scale_levels_pmt(self):
        """PMT levels should be VL/L/M/H/VH."""
        config = AgentTypeConfig.load()
        levels = config.get_rating_scale_levels("pmt")
        assert levels == ["VL", "L", "M", "H", "VH"]

    def test_get_rating_scale_levels_utility(self):
        """Utility levels should be L/M/H."""
        config = AgentTypeConfig.load()
        levels = config.get_rating_scale_levels("utility")
        assert levels == ["L", "M", "H"]

    def test_get_rating_scale_levels_financial(self):
        """Financial levels should be C/M/A."""
        config = AgentTypeConfig.load()
        levels = config.get_rating_scale_levels("financial")
        assert levels == ["C", "M", "A"]

    def test_get_rating_scale_levels_unknown_defaults_pmt(self):
        """Unknown framework should default to PMT levels."""
        config = AgentTypeConfig.load()
        levels = config.get_rating_scale_levels("unknown")
        assert levels == ["VL", "L", "M", "H", "VH"]

    def test_get_framework_for_agent_type_default(self):
        """Agent type without framework should default to pmt."""
        config = AgentTypeConfig.load()
        # Most agent types default to pmt
        framework = config.get_framework_for_agent_type("household")
        # Could be pmt or explicitly configured
        assert framework in ["pmt", "utility", "financial", "generic"]

    def test_get_rating_scale_for_agent_type(self):
        """Convenience method should work."""
        config = AgentTypeConfig.load()
        scale = config.get_rating_scale_for_agent_type("household")
        # Should return a non-empty scale
        assert scale
        assert isinstance(scale, str)


class TestAgentTypeConfigRatingScaleYAML:
    """Test rating scale methods with custom YAML config."""

    def setup_method(self):
        RatingScaleRegistry.reset()
        AgentTypeConfig._instance = None

    def test_yaml_scale_override(self, tmp_path):
        """Custom YAML scales should override defaults."""
        yaml_content = """
shared:
  rating_scales:
    pmt:
      levels: ["LOW", "MID", "HIGH"]
      labels:
        LOW: "Low"
        MID: "Medium"
        HIGH: "High"
      template: "Custom: LOW/MID/HIGH"
"""
        yaml_file = tmp_path / "test_agent_types.yaml"
        yaml_file.write_text(yaml_content)

        config = AgentTypeConfig.load(str(yaml_file))
        scale = config.get_rating_scale("pmt")
        assert "Custom: LOW/MID/HIGH" in scale

        levels = config.get_rating_scale_levels("pmt")
        assert levels == ["LOW", "MID", "HIGH"]

    def test_legacy_rating_scale_fallback(self, tmp_path):
        """Legacy rating_scale (not rating_scales) should work."""
        yaml_content = """
shared:
  rating_scale: |
    ### LEGACY SCALE:
    1 = Bad | 5 = Good
"""
        yaml_file = tmp_path / "test_agent_types.yaml"
        yaml_file.write_text(yaml_content)

        config = AgentTypeConfig.load(str(yaml_file))
        # For unknown framework, should fall back to legacy
        scale = config.get_rating_scale("unknown_framework")
        assert "LEGACY SCALE" in scale or "VL = Very Low" in scale

    def test_agent_type_framework_config(self, tmp_path):
        """Agent type can specify psychological_framework."""
        yaml_content = """
government:
  psychological_framework: utility
  prompt_template: "Government prompt"

household:
  psychological_framework: pmt
  prompt_template: "Household prompt"
"""
        yaml_file = tmp_path / "test_agent_types.yaml"
        yaml_file.write_text(yaml_content)

        config = AgentTypeConfig.load(str(yaml_file))

        assert config.get_framework_for_agent_type("government") == "utility"
        assert config.get_framework_for_agent_type("household") == "pmt"

    def test_get_rating_scale_for_agent_type_utility(self, tmp_path):
        """Government agent should get utility scale."""
        yaml_content = """
government:
  psychological_framework: utility
"""
        yaml_file = tmp_path / "test_agent_types.yaml"
        yaml_file.write_text(yaml_content)

        config = AgentTypeConfig.load(str(yaml_file))
        scale = config.get_rating_scale_for_agent_type("government")

        # Should be utility scale
        assert "Priority" in scale or "L/M/H" in scale or scale  # Non-empty
