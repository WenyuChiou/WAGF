"""
Tests for Framework-Aware Rating Scale System.

Task-041: Universal Prompt/Context/Governance Framework
"""

import pytest
from broker.interfaces.rating_scales import (
    FrameworkType,
    RatingScale,
    RatingScaleRegistry,
    get_scale_for_framework,
    validate_rating_value,
)


class TestFrameworkType:
    """Test FrameworkType enum."""

    def test_pmt_value(self):
        assert FrameworkType.PMT.value == "pmt"

    def test_utility_value(self):
        assert FrameworkType.UTILITY.value == "utility"

    def test_financial_value(self):
        assert FrameworkType.FINANCIAL.value == "financial"

    def test_generic_value(self):
        assert FrameworkType.GENERIC.value == "generic"

    def test_from_string(self):
        assert FrameworkType("pmt") == FrameworkType.PMT

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            FrameworkType("invalid")


class TestRatingScale:
    """Test RatingScale dataclass."""

    @pytest.fixture
    def pmt_scale(self):
        return RatingScale(
            framework=FrameworkType.PMT,
            levels=["VL", "L", "M", "H", "VH"],
            labels={
                "VL": "Very Low",
                "L": "Low",
                "M": "Medium",
                "H": "High",
                "VH": "Very High"
            },
            template="### RATING SCALE:\nVL = Very Low | L = Low | M = Medium | H = High | VH = Very High"
        )

    def test_format_labels_pmt(self, pmt_scale):
        assert pmt_scale.format_labels() == "VL/L/M/H/VH"

    def test_format_labels_utility(self):
        scale = RatingScale(
            framework=FrameworkType.UTILITY,
            levels=["L", "M", "H"],
            labels={},
            template=""
        )
        assert scale.format_labels() == "L/M/H"

    def test_validate_value_valid(self, pmt_scale):
        assert pmt_scale.validate_value("VH") is True
        assert pmt_scale.validate_value("L") is True
        assert pmt_scale.validate_value("M") is True

    def test_validate_value_case_insensitive(self, pmt_scale):
        assert pmt_scale.validate_value("vh") is True
        assert pmt_scale.validate_value("Vh") is True
        assert pmt_scale.validate_value("VH") is True

    def test_validate_value_invalid(self, pmt_scale):
        assert pmt_scale.validate_value("INVALID") is False
        assert pmt_scale.validate_value("X") is False
        assert pmt_scale.validate_value("") is False

    def test_get_label_description(self, pmt_scale):
        assert pmt_scale.get_label_description("VH") == "Very High"
        assert pmt_scale.get_label_description("L") == "Low"

    def test_get_label_description_case_insensitive(self, pmt_scale):
        assert pmt_scale.get_label_description("vh") == "Very High"

    def test_get_label_description_unknown(self, pmt_scale):
        assert pmt_scale.get_label_description("UNKNOWN") == "UNKNOWN"

    def test_get_level_index(self, pmt_scale):
        assert pmt_scale.get_level_index("VL") == 0
        assert pmt_scale.get_level_index("L") == 1
        assert pmt_scale.get_level_index("M") == 2
        assert pmt_scale.get_level_index("H") == 3
        assert pmt_scale.get_level_index("VH") == 4

    def test_get_level_index_case_insensitive(self, pmt_scale):
        assert pmt_scale.get_level_index("vh") == 4

    def test_get_level_index_invalid(self, pmt_scale):
        assert pmt_scale.get_level_index("INVALID") == -1

    def test_is_above_threshold(self, pmt_scale):
        assert pmt_scale.is_above_threshold("VH", "H") is True
        assert pmt_scale.is_above_threshold("H", "H") is True
        assert pmt_scale.is_above_threshold("M", "H") is False
        assert pmt_scale.is_above_threshold("VL", "VH") is False

    def test_is_above_threshold_invalid(self, pmt_scale):
        assert pmt_scale.is_above_threshold("INVALID", "H") is False
        assert pmt_scale.is_above_threshold("H", "INVALID") is False

    def test_numeric_range_none(self, pmt_scale):
        assert pmt_scale.numeric_range is None

    def test_numeric_range_utility(self):
        scale = RatingScale(
            framework=FrameworkType.UTILITY,
            levels=["L", "M", "H"],
            labels={},
            template="",
            numeric_range=(0.0, 1.0)
        )
        assert scale.numeric_range == (0.0, 1.0)


class TestRatingScaleRegistry:
    """Test RatingScaleRegistry."""

    def setup_method(self):
        """Reset registry before each test."""
        RatingScaleRegistry.reset()

    def test_get_pmt_scale(self):
        scale = RatingScaleRegistry.get(FrameworkType.PMT)
        assert scale.framework == FrameworkType.PMT
        assert scale.levels == ["VL", "L", "M", "H", "VH"]

    def test_get_utility_scale(self):
        scale = RatingScaleRegistry.get(FrameworkType.UTILITY)
        assert scale.framework == FrameworkType.UTILITY
        assert scale.levels == ["L", "M", "H"]
        assert scale.numeric_range == (0.0, 1.0)

    def test_get_financial_scale(self):
        scale = RatingScaleRegistry.get(FrameworkType.FINANCIAL)
        assert scale.framework == FrameworkType.FINANCIAL
        assert scale.levels == ["C", "M", "A"]

    def test_get_generic_defaults_to_pmt(self):
        scale = RatingScaleRegistry.get(FrameworkType.GENERIC)
        assert scale.levels == ["VL", "L", "M", "H", "VH"]

    def test_get_by_name_pmt(self):
        scale = RatingScaleRegistry.get_by_name("pmt")
        assert scale.framework == FrameworkType.PMT

    def test_get_by_name_case_insensitive(self):
        scale = RatingScaleRegistry.get_by_name("PMT")
        assert scale.framework == FrameworkType.PMT

        scale = RatingScaleRegistry.get_by_name("Utility")
        assert scale.framework == FrameworkType.UTILITY

    def test_get_by_name_invalid_defaults_pmt(self):
        scale = RatingScaleRegistry.get_by_name("unknown")
        assert scale.framework == FrameworkType.PMT

    def test_pmt_template_content(self):
        scale = RatingScaleRegistry.get(FrameworkType.PMT)
        assert "VL = Very Low" in scale.template
        assert "VH = Very High" in scale.template

    def test_utility_template_content(self):
        scale = RatingScaleRegistry.get(FrameworkType.UTILITY)
        assert "Low Priority" in scale.template
        assert "0.0-1.0" in scale.template

    def test_financial_template_content(self):
        scale = RatingScaleRegistry.get(FrameworkType.FINANCIAL)
        assert "Conservative" in scale.template
        assert "Aggressive" in scale.template

    def test_register_custom_scale(self):
        custom_scale = RatingScale(
            framework=FrameworkType.PMT,
            levels=["LOW", "MID", "HIGH"],
            labels={"LOW": "Low", "MID": "Medium", "HIGH": "High"},
            template="Custom template"
        )
        RatingScaleRegistry.register(custom_scale)

        scale = RatingScaleRegistry.get(FrameworkType.PMT)
        assert scale.levels == ["LOW", "MID", "HIGH"]

    def test_load_from_yaml(self):
        yaml_config = {
            "rating_scales": {
                "pmt": {
                    "levels": ["VERY_LOW", "LOW", "MEDIUM", "HIGH", "VERY_HIGH"],
                    "labels": {
                        "VERY_LOW": "Very Low",
                        "LOW": "Low",
                        "MEDIUM": "Medium",
                        "HIGH": "High",
                        "VERY_HIGH": "Very High"
                    },
                    "template": "Custom PMT template"
                }
            }
        }
        RatingScaleRegistry.load_from_yaml(yaml_config)

        scale = RatingScaleRegistry.get(FrameworkType.PMT)
        assert scale.levels == ["VERY_LOW", "LOW", "MEDIUM", "HIGH", "VERY_HIGH"]
        assert scale.template == "Custom PMT template"

    def test_load_from_yaml_with_numeric_range(self):
        yaml_config = {
            "rating_scales": {
                "utility": {
                    "levels": ["L", "M", "H"],
                    "labels": {},
                    "template": "",
                    "numeric_range": [0.0, 100.0]
                }
            }
        }
        RatingScaleRegistry.load_from_yaml(yaml_config)

        scale = RatingScaleRegistry.get(FrameworkType.UTILITY)
        assert scale.numeric_range == (0.0, 100.0)

    def test_load_from_yaml_unknown_framework_ignored(self):
        yaml_config = {
            "rating_scales": {
                "unknown_framework": {
                    "levels": ["A", "B", "C"],
                    "labels": {},
                    "template": ""
                }
            }
        }
        # Should not raise error
        RatingScaleRegistry.load_from_yaml(yaml_config)
        # PMT should still be default
        scale = RatingScaleRegistry.get(FrameworkType.PMT)
        assert scale.levels == ["VL", "L", "M", "H", "VH"]

    def test_get_all_frameworks(self):
        frameworks = RatingScaleRegistry.get_all_frameworks()
        assert FrameworkType.PMT in frameworks
        assert FrameworkType.UTILITY in frameworks
        assert FrameworkType.FINANCIAL in frameworks
        assert FrameworkType.GENERIC in frameworks

    def test_reset(self):
        # Register a custom scale
        custom_scale = RatingScale(
            framework=FrameworkType.PMT,
            levels=["A", "B"],
            labels={},
            template=""
        )
        RatingScaleRegistry.register(custom_scale)

        # Reset
        RatingScaleRegistry.reset()

        # Should be back to defaults
        scale = RatingScaleRegistry.get(FrameworkType.PMT)
        assert scale.levels == ["VL", "L", "M", "H", "VH"]


class TestConvenienceFunctions:
    """Test convenience functions."""

    def setup_method(self):
        RatingScaleRegistry.reset()

    def test_get_scale_for_framework(self):
        scale = get_scale_for_framework("pmt")
        assert scale.framework == FrameworkType.PMT

    def test_get_scale_for_framework_utility(self):
        scale = get_scale_for_framework("utility")
        assert scale.framework == FrameworkType.UTILITY

    def test_validate_rating_value_valid(self):
        assert validate_rating_value("VH", "pmt") is True
        assert validate_rating_value("H", "utility") is True
        assert validate_rating_value("C", "financial") is True

    def test_validate_rating_value_invalid(self):
        assert validate_rating_value("C", "pmt") is False  # C is financial
        assert validate_rating_value("VH", "utility") is False  # VH is PMT

    def test_validate_rating_value_case_insensitive(self):
        assert validate_rating_value("vh", "pmt") is True
        assert validate_rating_value("VH", "pmt") is True


class TestBackwardCompatibility:
    """Test backward compatibility with existing PMT-centric code."""

    def setup_method(self):
        RatingScaleRegistry.reset()

    def test_pmt_is_default(self):
        """PMT should be the default framework."""
        scale = RatingScaleRegistry.get_by_name("unknown")
        assert scale.format_labels() == "VL/L/M/H/VH"

    def test_pmt_levels_unchanged(self):
        """PMT levels should match existing hardcoded values."""
        scale = RatingScaleRegistry.get(FrameworkType.PMT)
        assert scale.levels == ["VL", "L", "M", "H", "VH"]

    def test_pmt_validation_works(self):
        """PMT validation should work as expected."""
        scale = RatingScaleRegistry.get(FrameworkType.PMT)
        for level in ["VL", "L", "M", "H", "VH"]:
            assert scale.validate_value(level) is True
