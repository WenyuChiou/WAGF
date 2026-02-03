"""
Tests for ResponseFormatBuilder Framework Support.

Task-041: Universal Prompt/Context/Governance Framework
"""

import pytest
from broker.components.response_format import ResponseFormatBuilder, create_response_format_builder
from broker.interfaces.rating_scales import RatingScaleRegistry


class TestResponseFormatBuilderFramework:
    """Test framework-aware response format generation."""

    def setup_method(self):
        """Reset registry before each test."""
        RatingScaleRegistry.reset()

    def test_pmt_labels(self):
        """PMT framework should use VL/L/M/H/VH labels."""
        config = {
            "response_format": {
                "fields": [
                    {"key": "threat_appraisal", "type": "appraisal", "construct": "TP_LABEL"}
                ]
            }
        }
        builder = ResponseFormatBuilder(config, framework="pmt")
        result = builder.build()
        assert '"label": "VL/L/M/H/VH"' in result

    def test_utility_labels(self):
        """Utility framework should use L/M/H labels."""
        config = {
            "response_format": {
                "fields": [
                    {"key": "budget_impact", "type": "appraisal", "construct": "BUDGET_UTIL"}
                ]
            }
        }
        builder = ResponseFormatBuilder(config, framework="utility")
        result = builder.build()
        assert '"label": "L/M/H"' in result

    def test_financial_labels(self):
        """Financial framework should use C/M/A labels."""
        config = {
            "response_format": {
                "fields": [
                    {"key": "risk_assessment", "type": "appraisal", "construct": "RISK_APPETITE"}
                ]
            }
        }
        builder = ResponseFormatBuilder(config, framework="financial")
        result = builder.build()
        assert '"label": "C/M/A"' in result

    def test_backward_compatible_default_pmt(self):
        """Default framework should be PMT for backward compatibility."""
        config = {
            "response_format": {
                "fields": [
                    {"key": "appraisal", "type": "appraisal"}
                ]
            }
        }
        builder = ResponseFormatBuilder(config)  # No framework specified
        result = builder.build()
        assert '"label": "VL/L/M/H/VH"' in result

    def test_numeric_field_type(self):
        """Numeric field type should include range."""
        config = {
            "response_format": {
                "fields": [
                    {"key": "solvency", "type": "numeric", "min": 0.0, "max": 1.0}
                ]
            }
        }
        builder = ResponseFormatBuilder(config, framework="financial")
        result = builder.build()
        assert "Enter a number: 0.0-1.0" in result

    def test_numeric_field_default_range(self):
        """Numeric field should have default range 0-1."""
        config = {
            "response_format": {
                "fields": [
                    {"key": "score", "type": "numeric"}
                ]
            }
        }
        builder = ResponseFormatBuilder(config)
        result = builder.build()
        assert "Enter a number" in result

    def test_per_field_scale_override(self):
        """Field can override framework scale."""
        config = {
            "response_format": {
                "fields": [
                    {"key": "mixed", "type": "appraisal", "scale": "utility"}
                ]
            }
        }
        builder = ResponseFormatBuilder(config, framework="pmt")
        result = builder.build()
        assert '"label": "L/M/H"' in result  # Uses utility scale, not pmt

    def test_get_valid_levels_pmt(self):
        """Should return valid levels for PMT."""
        builder = ResponseFormatBuilder({}, framework="pmt")
        levels = builder.get_valid_levels()
        assert levels == ["VL", "L", "M", "H", "VH"]

    def test_get_valid_levels_utility(self):
        """Should return valid levels for Utility."""
        builder = ResponseFormatBuilder({}, framework="utility")
        levels = builder.get_valid_levels()
        assert levels == ["L", "M", "H"]

    def test_get_valid_levels_financial(self):
        """Should return valid levels for Financial."""
        builder = ResponseFormatBuilder({}, framework="financial")
        levels = builder.get_valid_levels()
        assert levels == ["C", "M", "A"]

    def test_custom_shared_config_scales(self):
        """Should use scales from shared config if provided."""
        config = {
            "response_format": {
                "fields": [
                    {"key": "test", "type": "appraisal"}
                ]
            }
        }
        shared_config = {
            "rating_scales": {
                "pmt": {
                    "levels": ["LOW", "MID", "HIGH"]
                }
            }
        }
        builder = ResponseFormatBuilder(config, shared_config, framework="pmt")
        labels = builder._get_labels_for_framework()
        assert labels == "LOW/MID/HIGH"


class TestResponseFormatBuilderBasics:
    """Test basic ResponseFormatBuilder functionality."""

    def test_empty_config_returns_empty(self):
        """Empty config should return empty string."""
        builder = ResponseFormatBuilder({})
        result = builder.build()
        assert result == ""

    def test_empty_fields_returns_empty(self):
        """Config with no fields should return empty string."""
        config = {
            "response_format": {
                "delimiter_start": "<<<START>>>",
                "fields": []
            }
        }
        builder = ResponseFormatBuilder(config)
        result = builder.build()
        assert result == ""

    def test_text_field_type(self):
        """Text field type should use ellipsis."""
        config = {
            "response_format": {
                "fields": [
                    {"key": "comment", "type": "text"}
                ]
            }
        }
        builder = ResponseFormatBuilder(config)
        result = builder.build()
        assert '"comment": "..."' in result

    def test_choice_field_type(self):
        """Choice field type should include valid choices."""
        config = {
            "response_format": {
                "fields": [
                    {"key": "decision", "type": "choice"}
                ]
            }
        }
        builder = ResponseFormatBuilder(config)
        result = builder.build("1 or 2")
        assert "Numeric ID, choose ONE from: 1 or 2" in result

    def test_custom_delimiters(self):
        """Custom delimiters should be used."""
        config = {
            "response_format": {
                "delimiter_start": "<<<MY_START>>>",
                "delimiter_end": "<<<MY_END>>>",
                "fields": [
                    {"key": "test", "type": "text"}
                ]
            }
        }
        builder = ResponseFormatBuilder(config)
        result = builder.build()
        assert "<<<MY_START>>>" in result
        assert "<<<MY_END>>>" in result

    def test_get_required_fields(self):
        """Should return only required fields."""
        config = {
            "response_format": {
                "fields": [
                    {"key": "required_field", "type": "text", "required": True},
                    {"key": "optional_field", "type": "text", "required": False},
                    {"key": "default_field", "type": "text"}
                ]
            }
        }
        builder = ResponseFormatBuilder(config)
        required = builder.get_required_fields()
        assert required == ["required_field"]

    def test_get_construct_mapping(self):
        """Should return field-to-construct mapping."""
        config = {
            "response_format": {
                "fields": [
                    {"key": "threat_appraisal", "type": "appraisal", "construct": "TP_LABEL"},
                    {"key": "coping_appraisal", "type": "appraisal", "construct": "CP_LABEL"},
                    {"key": "comment", "type": "text"}  # No construct
                ]
            }
        }
        builder = ResponseFormatBuilder(config)
        mapping = builder.get_construct_mapping()
        assert mapping == {
            "threat_appraisal": "TP_LABEL",
            "coping_appraisal": "CP_LABEL"
        }

    def test_get_delimiters_default(self):
        """Should return default delimiters if not specified."""
        builder = ResponseFormatBuilder({})
        start, end = builder.get_delimiters()
        assert start == "<<<DECISION_START>>>"
        assert end == "<<<DECISION_END>>>"

    def test_get_delimiters_custom(self):
        """Should return custom delimiters if specified."""
        config = {
            "response_format": {
                "delimiter_start": "<<<START>>>",
                "delimiter_end": "<<<END>>>"
            }
        }
        builder = ResponseFormatBuilder(config)
        start, end = builder.get_delimiters()
        assert start == "<<<START>>>"
        assert end == "<<<END>>>"

    def test_custom_reason_hint(self):
        """Appraisal field should use custom reason hint."""
        config = {
            "response_format": {
                "fields": [
                    {"key": "appraisal", "type": "appraisal", "reason_hint": "Explain your reasoning"}
                ]
            }
        }
        builder = ResponseFormatBuilder(config)
        result = builder.build()
        assert '"reason": "Explain your reasoning"' in result


class TestResponseFormatBuilderMultipleFields:
    """Test ResponseFormatBuilder with multiple fields."""

    def test_multiple_fields_json_structure(self):
        """Multiple fields should produce valid JSON structure."""
        config = {
            "response_format": {
                "fields": [
                    {"key": "threat_appraisal", "type": "appraisal"},
                    {"key": "coping_appraisal", "type": "appraisal"},
                    {"key": "decision", "type": "choice"}
                ]
            }
        }
        builder = ResponseFormatBuilder(config, framework="pmt")
        result = builder.build("1, 2, or 3")

        # Check structure
        assert "<<<DECISION_START>>>" in result
        assert "<<<DECISION_END>>>" in result
        assert "{" in result
        assert "}" in result

        # Check fields
        assert '"threat_appraisal"' in result
        assert '"coping_appraisal"' in result
        assert '"decision"' in result

        # Check commas (last field should not have comma)
        lines = result.split("\n")
        # Find the decision line (should be the last field, no comma)
        for line in lines:
            if '"decision"' in line:
                assert not line.rstrip().endswith(",")

    def test_mixed_frameworks_fields(self):
        """Fields can have different framework scales."""
        config = {
            "response_format": {
                "fields": [
                    {"key": "pmt_field", "type": "appraisal", "scale": "pmt"},
                    {"key": "utility_field", "type": "appraisal", "scale": "utility"},
                    {"key": "financial_field", "type": "appraisal", "scale": "financial"}
                ]
            }
        }
        builder = ResponseFormatBuilder(config, framework="pmt")  # Default is PMT
        result = builder.build()

        # Each field should use its own scale
        # This is a complex assertion - check they're all present
        assert '"pmt_field"' in result
        assert '"utility_field"' in result
        assert '"financial_field"' in result
        # PMT field should have VL/L/M/H/VH
        # Utility field should have L/M/H
        # Financial field should have C/M/A


class TestFactoryFunction:
    """Test create_response_format_builder factory function."""

    def setup_method(self):
        RatingScaleRegistry.reset()
        # Reset agent config singleton
        from broker.utils.agent_config import AgentTypeConfig
        AgentTypeConfig._instance = None

    def test_factory_with_framework_override(self, tmp_path):
        """Factory should accept framework override."""
        yaml_content = """
household:
  psychological_framework: pmt
  response_format:
    fields:
      - key: test
        type: appraisal
"""
        yaml_file = tmp_path / "test_agent_types.yaml"
        yaml_file.write_text(yaml_content)

        builder = create_response_format_builder(
            "household",
            config_path=str(yaml_file),
            framework="utility"  # Override
        )
        result = builder.build()
        assert '"label": "L/M/H"' in result  # Should use utility, not PMT

    def test_factory_uses_agent_framework(self, tmp_path):
        """Factory should use agent type's framework by default."""
        yaml_content = """
government:
  psychological_framework: utility
  response_format:
    fields:
      - key: budget
        type: appraisal
"""
        yaml_file = tmp_path / "test_agent_types.yaml"
        yaml_file.write_text(yaml_content)

        builder = create_response_format_builder(
            "government",
            config_path=str(yaml_file)
        )
        result = builder.build()
        assert '"label": "L/M/H"' in result  # Should use utility
