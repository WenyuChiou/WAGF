"""
Tests for Config Schema Validation.

Task-041: Universal Prompt/Context/Governance Framework
"""

import pytest
from pathlib import Path

from broker.config.schema import (
    load_agent_config,
    MemoryConfig,
    RatingScaleConfig,
    RatingScalesConfig,
    SharedConfig,
    AgentTypeSpecificConfig,
    validate_rating_scales,
)


def test_valid_config_loads_sa():
    config = load_agent_config(Path("examples/single_agent/agent_types.yaml"))
    assert config.global_config.memory.window_size == 5


def test_valid_config_loads_ma():
    config = load_agent_config(Path("examples/multi_agent/flood/config/agents/agent_types.yaml"))
    assert config.global_config.memory.window_size == 5


def test_invalid_engine_type_raises():
    with pytest.raises(ValueError):
        MemoryConfig(engine_type="invalid")


def test_all_memory_engine_types():
    for engine in ["window", "importance", "humancentric", "hierarchical", "universal", "unified"]:
        config = MemoryConfig(engine_type=engine)
        assert config.engine_type == engine


class TestRatingScaleConfig:
    """Test RatingScaleConfig Pydantic model."""

    def test_valid_pmt_scale(self):
        """Valid PMT scale should parse correctly."""
        config = RatingScaleConfig(
            levels=["VL", "L", "M", "H", "VH"],
            labels={
                "VL": "Very Low",
                "L": "Low",
                "M": "Medium",
                "H": "High",
                "VH": "Very High"
            },
            template="### RATING SCALE:\nVL = Very Low | VH = Very High"
        )
        assert config.levels == ["VL", "L", "M", "H", "VH"]
        assert config.labels["VH"] == "Very High"

    def test_valid_utility_scale_with_numeric_range(self):
        """Utility scale with numeric_range should parse correctly."""
        config = RatingScaleConfig(
            levels=["L", "M", "H"],
            labels={"L": "Low Priority", "M": "Medium Priority", "H": "High Priority"},
            numeric_range=[0.0, 1.0]
        )
        assert config.numeric_range == [0.0, 1.0]

    def test_invalid_numeric_range_length(self):
        """numeric_range with wrong length should fail."""
        with pytest.raises(ValueError, match="exactly 2 values"):
            RatingScaleConfig(
                levels=["L", "M", "H"],
                numeric_range=[0.0, 0.5, 1.0]  # 3 values
            )

    def test_invalid_numeric_range_order(self):
        """numeric_range with min >= max should fail."""
        with pytest.raises(ValueError, match="less than"):
            RatingScaleConfig(
                levels=["L", "M", "H"],
                numeric_range=[1.0, 0.0]  # Reversed
            )

    def test_minimum_levels_required(self):
        """levels must have at least 2 items."""
        with pytest.raises(ValueError):
            RatingScaleConfig(levels=["L"])  # Only 1 level


class TestRatingScalesConfig:
    """Test RatingScalesConfig container."""

    def test_all_frameworks_optional(self):
        """All framework scales are optional."""
        config = RatingScalesConfig()
        assert config.pmt is None
        assert config.utility is None
        assert config.financial is None

    def test_mixed_frameworks(self):
        """Can define some frameworks but not others."""
        config = RatingScalesConfig(
            pmt=RatingScaleConfig(levels=["VL", "L", "M", "H", "VH"]),
            utility=RatingScaleConfig(levels=["L", "M", "H"], numeric_range=[0.0, 1.0])
        )
        assert config.pmt is not None
        assert config.utility is not None
        assert config.financial is None


class TestSharedConfig:
    """Test SharedConfig model."""

    def test_legacy_rating_scale(self):
        """Legacy rating_scale field should work."""
        config = SharedConfig(
            rating_scale="### RATING SCALE:\nVL = Very Low | VH = Very High"
        )
        assert "RATING SCALE" in config.rating_scale

    def test_new_rating_scales(self):
        """New rating_scales field should work."""
        config = SharedConfig(
            rating_scales=RatingScalesConfig(
                pmt=RatingScaleConfig(levels=["VL", "L", "M", "H", "VH"])
            )
        )
        assert config.rating_scales.pmt.levels == ["VL", "L", "M", "H", "VH"]

    def test_both_legacy_and_new(self):
        """Can have both legacy and new rating_scales."""
        config = SharedConfig(
            rating_scale="Legacy template",
            rating_scales=RatingScalesConfig(
                pmt=RatingScaleConfig(levels=["VL", "L", "M", "H", "VH"])
            )
        )
        assert config.rating_scale == "Legacy template"
        assert config.rating_scales.pmt is not None


class TestAgentTypeSpecificConfig:
    """Test AgentTypeSpecificConfig model."""

    def test_default_framework_is_pmt(self):
        """Default psychological_framework should be pmt."""
        config = AgentTypeSpecificConfig()
        assert config.psychological_framework == "pmt"

    def test_valid_frameworks(self):
        """All valid frameworks should parse correctly."""
        for framework in ["pmt", "utility", "financial", "generic"]:
            config = AgentTypeSpecificConfig(psychological_framework=framework)
            assert config.psychological_framework == framework

    def test_invalid_framework_raises(self):
        """Invalid framework should raise error."""
        with pytest.raises(ValueError):
            AgentTypeSpecificConfig(psychological_framework="invalid")


class TestValidateRatingScales:
    """Test validate_rating_scales function."""

    def test_empty_config_valid(self):
        """Empty config should be valid."""
        errors = validate_rating_scales({})
        assert errors == []

    def test_none_config_valid(self):
        """None config should be valid."""
        errors = validate_rating_scales(None)
        assert errors == []

    def test_valid_pmt_config(self):
        """Valid PMT config should have no errors."""
        config = {
            "pmt": {
                "levels": ["VL", "L", "M", "H", "VH"],
                "labels": {
                    "VL": "Very Low",
                    "L": "Low",
                    "M": "Medium",
                    "H": "High",
                    "VH": "Very High"
                }
            }
        }
        errors = validate_rating_scales(config)
        assert errors == []

    def test_missing_levels_error(self):
        """Missing levels should produce error."""
        config = {
            "pmt": {
                "labels": {"VL": "Very Low"}
            }
        }
        errors = validate_rating_scales(config)
        assert any("levels is required" in e for e in errors)

    def test_insufficient_levels_error(self):
        """Less than 2 levels should produce error."""
        config = {
            "pmt": {
                "levels": ["L"]
            }
        }
        errors = validate_rating_scales(config)
        assert any("at least 2" in e for e in errors)

    def test_missing_label_warning(self):
        """Labels missing for a level should produce error."""
        config = {
            "pmt": {
                "levels": ["VL", "L", "M"],
                "labels": {"VL": "Very Low", "L": "Low"}  # Missing M
            }
        }
        errors = validate_rating_scales(config)
        assert any("missing key 'M'" in e for e in errors)

    def test_invalid_numeric_range_length(self):
        """Invalid numeric_range length should produce error."""
        config = {
            "utility": {
                "levels": ["L", "M", "H"],
                "numeric_range": [0.0]  # Only 1 value
            }
        }
        errors = validate_rating_scales(config)
        assert any("[min, max]" in e for e in errors)

    def test_invalid_numeric_range_order(self):
        """Invalid numeric_range order should produce error."""
        config = {
            "utility": {
                "levels": ["L", "M", "H"],
                "numeric_range": [1.0, 0.0]  # min > max
            }
        }
        errors = validate_rating_scales(config)
        assert any("min must be < max" in e for e in errors)
