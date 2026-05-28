from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from broker.config.schema import (
    AgentTypeConfig,
    AgentTypeSpecificConfig,
    load_agent_config,
)
from broker.validators.governance.thinking_validator import (
    FRAMEWORK_CONSTRUCTS,
    FRAMEWORK_LABEL_ORDERS,
    _LABEL_MAPPINGS,
    register_framework_metadata,
)


def _agent_config(framework: str = "pmt") -> dict:
    return {
        "description": "test agent",
        "psychological_framework": framework,
        "prompt_template_file": "prompts/test.txt",
    }


def test_vaccination_hbm_yaml_loads_under_non_water_slot():
    cfg = load_agent_config(Path("examples/vaccination_demo/config/agent_types.yaml"))

    assert cfg.individual.psychological_framework == "hbm"
    assert cfg.agent_types["individual"].psychological_framework == "hbm"


def test_legacy_agent_type_slot_warns_and_matches_new_shape():
    legacy = {"household": _agent_config("pmt")}
    new_shape = {"agent_types": {"household": _agent_config("pmt")}}

    with pytest.warns(
        DeprecationWarning,
        match="Top-level agent-type slot 'household' is deprecated",
    ) as caught:
        parsed_legacy = AgentTypeConfig.model_validate(legacy)

    parsed_new = AgentTypeConfig.model_validate(new_shape)

    assert len(caught) == 1
    assert parsed_legacy.model_dump() == parsed_new.model_dump()
    assert parsed_legacy.household.psychological_framework == "pmt"


def test_new_agent_types_shape_emits_no_legacy_warning():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        AgentTypeConfig.model_validate(
            {"agent_types": {"household": _agent_config("pmt")}}
        )

    assert not [
        warning
        for warning in caught
        if warning.category is DeprecationWarning
        and "Top-level agent-type slot" in str(warning.message)
    ]


def test_unregistered_framework_error_mentions_registry_and_import_hint():
    with pytest.raises(ValueError) as exc_info:
        AgentTypeSpecificConfig(psychological_framework="not_registered")

    message = str(exc_info.value)
    assert "framework 'not_registered' is not registered" in message
    assert "known frameworks:" in message
    assert "import the domain module before loading config" in message
    assert "value not in Literal" not in message


def test_agent_type_round_trip_dump_is_idempotent():
    with pytest.warns(
        DeprecationWarning,
        match="Top-level agent-type slot 'household' is deprecated",
    ):
        parsed = AgentTypeConfig.model_validate({"household": _agent_config("pmt")})

    dumped = parsed.model_dump()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        reparsed = AgentTypeConfig.model_validate(dumped)

    assert reparsed.model_dump() == dumped
    assert not [
        warning
        for warning in caught
        if warning.category is DeprecationWarning
        and "Top-level agent-type slot" in str(warning.message)
    ]


def test_custom_runtime_framework_registered_after_import_validates():
    name = "traffic_framework"
    register_framework_metadata(
        name,
        {"primary": "CONGESTION_LABEL", "secondary": "TRUST_LABEL", "all": []},
        {"L": 0, "M": 1, "H": 2},
        {"LOW": "L", "MEDIUM": "M", "HIGH": "H"},
    )
    try:
        cfg = AgentTypeConfig.model_validate(
            {"agent_types": {"commuter": _agent_config(name)}}
        )
        assert cfg.agent_types["commuter"].psychological_framework == name
    finally:
        FRAMEWORK_LABEL_ORDERS.pop(name, None)
        FRAMEWORK_CONSTRUCTS.pop(name, None)
        _LABEL_MAPPINGS.pop(name, None)


def test_legacy_slot_conflict_is_rejected():
    with pytest.raises(
        ValueError,
        match="Legacy slot 'household' conflicts with agent_types dict; remove one",
    ):
        AgentTypeConfig.model_validate(
            {
                "household": _agent_config("pmt"),
                "agent_types": {"household": _agent_config("pmt")},
            }
        )


EXAMPLE_CONFIG_PATHS = sorted(
    {
        *Path("examples").rglob("agent_types.yaml"),
        *Path("examples").glob("*/results/*/config_snapshot.yaml"),
    }
)


@pytest.mark.parametrize("config_path", EXAMPLE_CONFIG_PATHS, ids=str)
def test_example_agent_configs_and_snapshots_still_load(config_path: Path):
    load_agent_config(config_path)
