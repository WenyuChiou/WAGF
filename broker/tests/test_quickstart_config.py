"""Regression tests for open-source Quickstart configuration health."""
from pathlib import Path

from broker.utils.agent_config import AgentTypeConfig


def test_quickstart_strict_profile_has_no_schema_errors(monkeypatch):
    """The Quickstart should run without governance schema ERROR diagnostics."""
    monkeypatch.setenv("GOVERNANCE_PROFILE", "strict")
    config_path = (
        Path(__file__).resolve().parents[2]
        / "examples"
        / "quickstart"
        / "agent_types.yaml"
    )

    config = AgentTypeConfig.load(str(config_path))
    issues = config.validate_schema("simple_agent")

    errors = [issue for issue in issues if issue.startswith("ERROR:")]
    assert errors == []
