"""Phase 6N-D-1 regression test — `_validate_yaml_rules` respects `rule.level`.

Before this fix, `ThinkingValidator._validate_yaml_rules` hardcoded
`valid=False` regardless of whether the YAML rule declared
`level: ERROR` or `level: WARNING`. So any WARNING rule with
`blocked_skills` silently block-and-retried like ERROR — a real
behaviour leak that vaccination_demo worked around in L3-1C by
stripping `blocked_skills` from WARNING rules (commit `64899b8`).
Irrigation + governed_flood had not worked around it and so 9+
WARNING+blocked_skills rules in those domains were silently blocking.

These tests would FAIL on pre-Phase-6N-D-1 code (the ERROR test passes
on pre-fix code too because `valid=False` is the correct ERROR
behaviour; the WARNING test FAILS on pre-fix because it returns
`valid=False` when the test asserts `valid=True`).
"""
from __future__ import annotations

import pytest

# Phase 6Q-G (2026-05-26): broker.domains auto-discovery removed.
# This test exercises ThinkingValidator(framework="pmt") — PMT
# registers at broker.domains.water import time.
import broker.domains.water  # noqa: F401 — registers PMT framework

from broker.governance.rule_types import GovernanceRule, RuleCondition
from broker.validators.governance.thinking_validator import ThinkingValidator


def _make_rule(level: str, blocked_skills: list[str]) -> GovernanceRule:
    """Synthetic multi-condition rule that triggers on TEST_LABEL ∈ {H, VH}."""
    return GovernanceRule(
        id=f"test_{level.lower()}_rule",
        category="thinking",
        conditions=[
            RuleCondition(
                type="construct",
                field="TEST_LABEL",
                operator="in",
                values=["H", "VH"],
            ),
        ],
        blocked_skills=blocked_skills,
        level=level,
        message=f"Test {level} rule fired",
    )


@pytest.fixture
def fired_context() -> dict:
    """Context that triggers the synthetic rule (TEST_LABEL='H')."""
    return {"reasoning": {"TEST_LABEL": "H"}, "framework": "pmt"}


def test_warning_rule_with_blocked_skills_does_not_reject(fired_context):
    """A WARNING-level rule with `blocked_skills` should fire but NOT
    set `valid=False`. The rule message goes to `warnings[]`, not
    `errors[]`. Pre-fix code hardcoded `valid=False` and pushed the
    message to `errors[]` — this test failed on that code."""
    validator = ThinkingValidator(framework="pmt")
    rule = _make_rule(level="WARNING", blocked_skills=["test_skill"])

    results = validator._validate_yaml_rules(
        skill_name="test_skill",
        rules=[rule],
        context=fired_context,
        framework="pmt",
    )

    assert len(results) == 1
    r = results[0]
    assert r.valid is True, (
        f"WARNING rule must NOT set valid=False (Phase 6N-D-1 fix). "
        f"Got valid={r.valid}"
    )
    assert r.warnings == ["Test WARNING rule fired"], (
        f"WARNING message must go to warnings[]. Got warnings={r.warnings}"
    )
    assert r.errors == [], (
        f"WARNING message must NOT go to errors[]. Got errors={r.errors}"
    )
    assert r.metadata.get("level") == "WARNING", (
        f"metadata must record the level for audit traceability. "
        f"Got metadata={r.metadata}"
    )


def test_error_rule_with_blocked_skills_does_reject(fired_context):
    """ERROR-level rules retain their previous behaviour: rule fires,
    `valid=False`, message in `errors[]`."""
    validator = ThinkingValidator(framework="pmt")
    rule = _make_rule(level="ERROR", blocked_skills=["test_skill"])

    results = validator._validate_yaml_rules(
        skill_name="test_skill",
        rules=[rule],
        context=fired_context,
        framework="pmt",
    )

    assert len(results) == 1
    r = results[0]
    assert r.valid is False
    assert r.errors == ["Test ERROR rule fired"]
    assert r.warnings == []
    assert r.metadata.get("level") == "ERROR"


def test_rule_default_level_is_error(fired_context):
    """If the YAML omits `level:`, the rule defaults to ERROR (per
    GovernanceRule schema). Confirms the fix's `getattr(rule, 'level',
    'ERROR')` fallback matches the dataclass default."""
    validator = ThinkingValidator(framework="pmt")
    rule = GovernanceRule(
        id="test_default_level",
        category="thinking",
        conditions=[
            RuleCondition(
                type="construct",
                field="TEST_LABEL",
                operator="in",
                values=["H", "VH"],
            ),
        ],
        blocked_skills=["test_skill"],
        # level omitted — defaults to "ERROR"
        message="Default-level rule fired",
    )

    results = validator._validate_yaml_rules(
        skill_name="test_skill",
        rules=[rule],
        context=fired_context,
        framework="pmt",
    )

    assert len(results) == 1
    assert results[0].valid is False
    assert results[0].errors == ["Default-level rule fired"]
