"""Phase 6Q-D-3 (2026-05-26) — pin the `triggered_rules` producer.

Pre-6Q-D-3 the audit CSV column ``rules_triggered`` had a reader at
``broker/components/analytics/audit.py:353`` but no producer wrote
the trace key — the column was always empty regardless of how many
rules fired. Task-041 Phase 3 added the schema + reader without
finishing the wiring.

This test pins the new ``_safe_triggered_rules`` helper in
``broker/core/_audit_helpers.py`` so a future edit can't silently
revert the wiring.
"""
from __future__ import annotations

from broker.core._audit_helpers import _safe_triggered_rules
from broker.interfaces.skill_types import ValidationResult


def _make_result(valid, rule_id=None, rules_hit=None, category="thinking"):
    """Build a minimal ValidationResult for testing."""
    return ValidationResult(
        valid=valid,
        errors=[],
        warnings=[],
        validator_name="test_validator",
        metadata={
            "category": category,
            **({"rule_id": rule_id} if rule_id else {}),
            **({"rules_hit": rules_hit} if rules_hit else {}),
        },
    )


class TestSafeTriggeredRules:
    def test_empty_history_returns_empty_list(self):
        assert _safe_triggered_rules([]) == []
        assert _safe_triggered_rules(None) == []

    def test_single_rule_id_extracted(self):
        history = [[_make_result(valid=False, rule_id="high_threat_block_inaction")]]
        assert _safe_triggered_rules(history) == ["high_threat_block_inaction"]

    def test_rules_hit_list_extracted(self):
        history = [[_make_result(valid=False, rules_hit=["r1", "r2", "r3"])]]
        assert _safe_triggered_rules(history) == ["r1", "r2", "r3"]

    def test_block_and_warn_both_collected(self):
        # ValidationResult.valid distinguishes BLOCK (False) from WARN
        # (True with warnings), but `triggered_rules` collects either.
        history = [[
            _make_result(valid=False, rule_id="block_rule"),
            _make_result(valid=True, rule_id="warn_rule"),
        ]]
        assert _safe_triggered_rules(history) == ["block_rule", "warn_rule"]

    def test_dedup_across_history_entries(self):
        history = [
            [_make_result(valid=False, rule_id="rule_a")],
            [_make_result(valid=False, rule_id="rule_a")],  # same rule re-fires
            [_make_result(valid=False, rule_id="rule_b")],
        ]
        assert _safe_triggered_rules(history) == ["rule_a", "rule_b"]

    def test_sorted_output(self):
        history = [[
            _make_result(valid=False, rule_id="z_rule"),
            _make_result(valid=False, rule_id="a_rule"),
            _make_result(valid=False, rule_id="m_rule"),
        ]]
        assert _safe_triggered_rules(history) == ["a_rule", "m_rule", "z_rule"]

    def test_combined_rule_id_and_rules_hit(self):
        history = [[
            _make_result(valid=False, rule_id="primary", rules_hit=["sub_a", "sub_b"]),
        ]]
        assert _safe_triggered_rules(history) == ["primary", "sub_a", "sub_b"]

    def test_malformed_history_returns_empty_not_crash(self):
        # Phase 6Q-D-3 contract: the audit write path must NEVER
        # crash on a producer error. Graceful fallback to [].
        assert _safe_triggered_rules("not a list") == []
        assert _safe_triggered_rules([{"not": "a ValidationResult"}]) == []

    def test_no_rule_id_no_hits_returns_empty(self):
        # ValidationResults without rule_id or rules_hit metadata
        # (e.g. builtin checks that fire without a YAML rule) don't
        # contribute to the triggered list.
        history = [[_make_result(valid=False)]]
        assert _safe_triggered_rules(history) == []
