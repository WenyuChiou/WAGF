from __future__ import annotations

import json
from pathlib import Path

import pytest

from broker.components.governance.validator_registry import ValidatorRegistry
from broker.domains.water.validator_bundles import build_domain_validators
from broker.governance.rule_types import GovernanceRule
from broker.interfaces.skill_types import ValidationResult
from broker.validators.governance.base_validator import BaseValidator


class TriggerValidator(BaseValidator):
    @property
    def category(self) -> str:
        return "thinking"


def _trigger_rule() -> GovernanceRule:
    return GovernanceRule(
        id="shadow_rule",
        category="thinking",
        subcategory="unit",
        blocked_skills=["blocked_skill"],
        level="ERROR",
        message="blocked by test rule",
        precondition="blocked",
    )


def _trigger_context() -> dict:
    return {"state": {"blocked": True}, "reasoning": {}}


def test_active_mode_error_rule_remains_blocking():
    validator = TriggerValidator()

    results = validator.validate("blocked_skill", [_trigger_rule()], _trigger_context())

    assert len(results) == 1
    result = results[0]
    assert isinstance(result, ValidationResult)
    assert result.valid is False
    assert result.errors
    assert result.warnings == []
    assert "shadow_blocked" not in result.metadata


def test_shadow_mode_error_rule_becomes_non_blocking_warning():
    validator = TriggerValidator(mode="shadow")

    results = validator.validate("blocked_skill", [_trigger_rule()], _trigger_context())

    assert len(results) == 1
    result = results[0]
    assert result.valid is True
    assert result.errors == []
    assert result.warnings
    assert result.metadata["shadow_blocked"] == ["shadow_rule"]
    assert result.metadata["would_block_level"] == "ERROR"
    assert result.metadata["rule_id"] == "shadow_rule"
    assert result.metadata["rules_hit"] == ["shadow_rule"]


def test_set_mode_rejects_unknown_mode():
    validator = TriggerValidator()

    with pytest.raises(ValueError, match="active|shadow"):
        validator.set_mode("bogus")


def test_registry_mode_applies_when_domain_validators_are_built():
    def noop_check(skill_name, rules, context):
        return []

    saved_registry = {
        domain: {slot: list(checks) for slot, checks in slots.items()}
        for domain, slots in ValidatorRegistry._registry.items()
    }
    saved_modes = {
        domain: dict(slots)
        for domain, slots in ValidatorRegistry._modes.items()
    }
    saved_missing_warned = set(ValidatorRegistry._missing_warned)
    ValidatorRegistry.clear()
    try:
        ValidatorRegistry.register("shadow_domain", "physical", [noop_check])
        ValidatorRegistry.set_validator_mode("shadow_domain", "physical", "shadow")

        validators = build_domain_validators("shadow_domain")

        modes_by_category = {validator.category: validator.mode for validator in validators}
        assert modes_by_category["physical"] == "shadow"
        assert modes_by_category["personal"] == "active"
    finally:
        ValidatorRegistry._registry.clear()
        ValidatorRegistry._registry.update(saved_registry)
        ValidatorRegistry._modes.clear()
        ValidatorRegistry._modes.update(saved_modes)
        ValidatorRegistry._missing_warned.clear()
        ValidatorRegistry._missing_warned.update(saved_missing_warned)


def test_thinking_slot_is_shadowable():
    """Regression (code-review W4 CRITICAL): the 'thinking' slot must be a
    valid registry slot — build_domain_validators wires ThinkingValidator
    through _with_registered_mode(..., 'thinking'), so set_validator_mode
    for that slot must NOT raise.
    """
    saved_modes = {d: dict(s) for d, s in ValidatorRegistry._modes.items()}
    try:
        # Must not raise ValueError("slot must be one of ...").
        ValidatorRegistry.set_validator_mode("any_domain", "thinking", "shadow")
        assert ValidatorRegistry.get_validator_mode("any_domain", "thinking") == "shadow"
    finally:
        ValidatorRegistry._modes.clear()
        ValidatorRegistry._modes.update(saved_modes)


def test_replay_shadow_fallback_counts_recorded_validation_issues(tmp_path: Path):
    try:
        from broker.tools import replay_shadow
    except ImportError as exc:
        pytest.fail(f"replay_shadow module is missing: {exc}")

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    jsonl_path = raw_dir / "agent_traces.jsonl"
    traces = [
        {"step_id": 1, "validation_issues": [{"rule_id": "known_rule"}]},
        {"step_id": 2, "validation_issues": [{"rule_id": "known_rule"}]},
    ]
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for trace in traces:
            f.write(json.dumps(trace) + "\n")

    summary = replay_shadow.recover(tmp_path)

    assert summary["mode"] == "recorded-fire-rate"
    assert summary["trace_count"] == 2
    assert summary["rules"]["known_rule"]["fire_count"] == 2
    assert summary["rules"]["known_rule"]["fire_rate"] == 1.0
