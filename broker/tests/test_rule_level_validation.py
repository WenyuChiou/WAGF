"""Regression coverage for load-time warnings on inert rule levels."""
from __future__ import annotations

import logging
import textwrap

import pytest

from broker.config.agent_types.base import ValidationRuleRef
from broker.governance.rule_types import GovernanceRule, RuleCondition
from broker.utils.agent_config import AgentTypeConfig
from broker.validators.governance.base_validator import BaseValidator


WARNING_FRAGMENT = (
    "treated as non-blocking/WARNING by the exact-string comparisons; "
    "write ERROR or WARNING, uppercase"
)


def _warning_messages(caplog):
    return [r.message for r in caplog.records if WARNING_FRAGMENT in r.message]


def _load_thinking_rule_level(tmp_path, level):
    yaml_path = tmp_path / f"agent_types_{level}.yaml"
    yaml_path.write_text(
        textwrap.dedent(
            f"""
            test_agent:
              thinking_rules:
                - id: lowercase_level_rule
                  construct: TEST_LABEL
                  when_above: [H]
                  blocked_skills: [act]
                  level: {level}
                  message: "test message"
            """
        ).lstrip(),
        encoding="utf-8",
    )
    cfg = AgentTypeConfig.load(str(yaml_path), force_reload=True)
    return cfg.get_thinking_rules("test_agent")[0].level


def _load_governance_rule_level(tmp_path, level):  # noqa: ARG001
    rule = GovernanceRule.from_dict(
        {
            "id": "lowercase_level_rule",
            "category": "thinking",
            "construct": "TEST_LABEL",
            "when_above": ["H"],
            "blocked_skills": ["act"],
            "level": level,
            "message": "test message",
        }
    )
    return rule.level


def _load_validation_ref_level(tmp_path, level):  # noqa: ARG001
    rule = ValidationRuleRef.from_dict(
        {
            "id": "lowercase_level_rule",
            "construct": "TEST_LABEL",
            "when_above": ["H"],
            "blocked_skills": ["act"],
            "level": level,
            "message": "test message",
        }
    )
    return rule.level


@pytest.mark.parametrize(
    "loader",
    [
        _load_thinking_rule_level,
        _load_governance_rule_level,
        _load_validation_ref_level,
    ],
)
def test_lowercase_rule_level_warns_and_preserves_raw_value(tmp_path, caplog, loader):
    caplog.set_level(logging.WARNING)

    level = loader(tmp_path, "error")

    assert level == "error"
    messages = _warning_messages(caplog)
    assert len(messages) == 1
    assert "lowercase_level_rule" in messages[0]
    assert "error" in messages[0]


@pytest.mark.parametrize(
    "loader",
    [
        _load_thinking_rule_level,
        _load_governance_rule_level,
        _load_validation_ref_level,
    ],
)
@pytest.mark.parametrize("level", ["ERROR", "WARNING"])
def test_canonical_rule_levels_load_silently(tmp_path, caplog, loader, level):
    caplog.set_level(logging.WARNING)

    loaded_level = loader(tmp_path, level)

    assert loaded_level == level
    assert _warning_messages(caplog) == []


class _ThinkingValidator(BaseValidator):
    @property
    def category(self) -> str:
        return "thinking"


def test_lowercase_error_level_does_not_block():
    rule = GovernanceRule(
        id="lowercase_error_nonblocking",
        category="thinking",
        conditions=[
            RuleCondition(
                type="construct",
                field="TEST_LABEL",
                operator="in",
                values=["H"],
            )
        ],
        blocked_skills=["act"],
        level="error",
        message="lowercase error fired",
    )

    results = _ThinkingValidator(builtin_checks=[]).validate(
        "act",
        [rule],
        {"reasoning": {"TEST_LABEL": "H"}},
    )

    assert len(results) == 1
    assert results[0].valid is True
    assert results[0].warnings == ["lowercase error fired"]
    assert results[0].errors == []
    assert results[0].metadata["level"] == "error"
