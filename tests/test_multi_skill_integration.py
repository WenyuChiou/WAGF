"""
Integration tests for Multi-Skill config toggle + model_adapter secondary parsing.

Tests real YAML config loading and secondary decision extraction
through the actual framework APIs.
"""
import pytest
import os
import tempfile
import yaml

from broker.utils.agent_config import AgentTypeConfig
from broker.components.response_format import ResponseFormatBuilder


# ── Fixture: temporary YAML with multi_skill enabled ──

ENABLED_YAML = {
    "shared": {
        "response_format": {
            "delimiter_start": "<<<DECISION_START>>>",
            "delimiter_end": "<<<DECISION_END>>>",
            "fields": [
                {"key": "reasoning", "type": "text", "required": True},
                {"key": "decision", "type": "choice", "required": True},
                {"key": "magnitude_pct", "type": "numeric", "min": 1, "max": 30, "unit": "%"},
                {"key": "secondary_decision", "type": "secondary_choice", "required": False},
                {"key": "secondary_magnitude_pct", "type": "numeric", "min": 1, "max": 30, "unit": "%", "required": False},
            ],
        }
    },
    "test_agent": {
        "description": "Test agent with multi_skill enabled",
        "multi_skill": {
            "enabled": True,
            "max_skills": 2,
            "execution_order": "sequential",
            "secondary_field": "secondary_decision",
            "secondary_magnitude_field": "secondary_magnitude_pct",
        },
        "parsing": {
            "skill_map": {"1": "skill_a", "2": "skill_b", "3": "skill_c"},
        },
    },
}

DISABLED_YAML = {
    "shared": {
        "response_format": {
            "delimiter_start": "<<<DECISION_START>>>",
            "delimiter_end": "<<<DECISION_END>>>",
            "fields": [
                {"key": "reasoning", "type": "text", "required": True},
                {"key": "decision", "type": "choice", "required": True},
            ],
        }
    },
    "test_agent": {
        "description": "Test agent with multi_skill disabled",
        "multi_skill": {
            "enabled": False,
        },
        "parsing": {
            "skill_map": {"1": "skill_a", "2": "skill_b", "3": "skill_c"},
        },
    },
}


@pytest.fixture
def enabled_config(tmp_path):
    """Load AgentTypeConfig with multi_skill enabled."""
    yaml_file = tmp_path / "agent_types.yaml"
    yaml_file.write_text(yaml.dump(ENABLED_YAML), encoding="utf-8")
    # Reset singleton for clean load
    AgentTypeConfig._instance = None
    cfg = AgentTypeConfig.load(str(yaml_file))
    yield cfg
    AgentTypeConfig._instance = None


@pytest.fixture
def disabled_config(tmp_path):
    """Load AgentTypeConfig with multi_skill disabled."""
    yaml_file = tmp_path / "agent_types.yaml"
    yaml_file.write_text(yaml.dump(DISABLED_YAML), encoding="utf-8")
    AgentTypeConfig._instance = None
    cfg = AgentTypeConfig.load(str(yaml_file))
    yield cfg
    AgentTypeConfig._instance = None


# ── get_multi_skill_config toggle ──

def test_get_multi_skill_config_enabled(enabled_config):
    """When enabled=true, returns full config dict."""
    ms = enabled_config.get_multi_skill_config("test_agent")
    assert ms["enabled"] is True
    assert ms["max_skills"] == 2
    assert ms["secondary_field"] == "secondary_decision"


def test_get_multi_skill_config_disabled(disabled_config):
    """When enabled=false, returns empty dict."""
    ms = disabled_config.get_multi_skill_config("test_agent")
    assert ms == {}


def test_get_multi_skill_config_missing(disabled_config):
    """When agent type has no multi_skill section, returns empty dict."""
    ms = disabled_config.get_multi_skill_config("nonexistent_agent")
    assert ms == {}


# ── ResponseFormatBuilder with multi_skill fields ──

def test_response_format_renders_secondary_fields(enabled_config):
    """When config has secondary_choice field, it renders in output."""
    agent_cfg = enabled_config.get("test_agent")
    shared_cfg = {"response_format": ENABLED_YAML["shared"]["response_format"]}
    rfb = ResponseFormatBuilder(agent_cfg, shared_config=shared_cfg)
    output = rfb.build(valid_choices_text="1, 2, 3")
    assert "secondary_decision" in output
    assert "OPTIONAL" in output
    assert "or 0 for none" in output


def test_response_format_omits_secondary_when_disabled(disabled_config):
    """When config has no secondary_choice field, output is unchanged."""
    agent_cfg = disabled_config.get("test_agent")
    shared_cfg = {"response_format": DISABLED_YAML["shared"]["response_format"]}
    rfb = ResponseFormatBuilder(agent_cfg, shared_config=shared_cfg)
    output = rfb.build(valid_choices_text="1, 2, 3")
    assert "secondary_decision" not in output


# ── Real YAML file loading (flood + irrigation) ──

def _load_domain_config(domain_dir):
    """Helper to load a real domain agent_types.yaml."""
    yaml_path = os.path.join(domain_dir, "agent_types.yaml")
    if not os.path.exists(yaml_path):
        pytest.skip(f"Domain config not found: {yaml_path}")
    AgentTypeConfig._instance = None
    cfg = AgentTypeConfig.load(yaml_path)
    return cfg


def test_flood_multi_skill_default_off():
    """Flood domain multi_skill should be disabled by default."""
    base = os.path.join(os.path.dirname(__file__), "..", "examples", "single_agent")
    cfg = _load_domain_config(base)
    ms = cfg.get_multi_skill_config("household")
    assert ms == {}, f"Expected empty dict (disabled), got: {ms}"
    AgentTypeConfig._instance = None


def test_irrigation_multi_skill_default_off():
    """Irrigation domain multi_skill should be disabled by default."""
    base = os.path.join(os.path.dirname(__file__), "..", "examples", "irrigation_abm", "config")
    cfg = _load_domain_config(base)
    ms = cfg.get_multi_skill_config("irrigation_farmer")
    assert ms == {}, f"Expected empty dict (disabled), got: {ms}"
    AgentTypeConfig._instance = None
