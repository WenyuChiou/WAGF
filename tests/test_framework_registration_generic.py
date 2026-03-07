import textwrap

from broker.interfaces.rating_scales import RatingScale, RatingScaleRegistry
from broker.utils.agent_config import AgentTypeConfig
from broker.validators.governance.thinking_validator import (
    ThinkingValidator,
    register_framework_metadata,
)


def setup_function():
    RatingScaleRegistry.reset()
    AgentTypeConfig.clear_cache()


def test_custom_framework_scale_can_be_loaded_from_yaml(tmp_path):
    yaml_content = textwrap.dedent(
        """
        shared:
          rating_scales:
            risk_capacity:
              levels: ["LOW", "MID", "HIGH"]
              labels:
                LOW: "Low"
                MID: "Medium"
                HIGH: "High"
              template: "Custom risk-capacity scale"

        analyst:
          psychological_framework: risk_capacity
        """
    )
    yaml_file = tmp_path / "agent_types.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")

    config = AgentTypeConfig.load(str(yaml_file))

    assert config.get_framework_for_agent_type("analyst") == "risk_capacity"
    assert config.get_rating_scale("risk_capacity") == "Custom risk-capacity scale"
    assert config.get_rating_scale_levels("risk_capacity") == ["LOW", "MID", "HIGH"]


def test_custom_framework_metadata_and_scale_work_with_thinking_validator():
    register_framework_metadata(
        name="risk_capacity",
        constructs={
            "primary": "RISK_LABEL",
            "secondary": "CAPACITY_LABEL",
            "all": ["RISK_LABEL", "CAPACITY_LABEL"],
        },
        label_order={"LOW": 0, "MID": 1, "HIGH": 2},
        label_mappings={"VERY HIGH": "HIGH", "MEDIUM": "MID", "LOW": "LOW"},
    )
    RatingScaleRegistry.register(
        RatingScale(
            framework="risk_capacity",
            levels=["LOW", "MID", "HIGH"],
            labels={"LOW": "Low", "MID": "Medium", "HIGH": "High"},
            template="Custom risk-capacity scale",
        )
    )

    validator = ThinkingValidator(framework="risk_capacity")

    assert validator._normalize_label("VERY HIGH", "risk_capacity") == "HIGH"
    assert validator.get_valid_levels("risk_capacity") == ["LOW", "MID", "HIGH"]
    assert validator.validate_label_value("MID", "risk_capacity") is True
