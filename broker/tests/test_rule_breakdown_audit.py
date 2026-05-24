"""Phase 6N-D-3 regression test — `rule_breakdown` audit dict is populated.

Phase 6C W8 commit `4b20320` (May 10) wired `_safe_rule_breakdown` into
the audit trace at `broker/core/_audit_helpers.py:32-52` and computed
it via `broker/validators/governance/__init__.py::get_rule_breakdown`
at lines 95-110. Before that fix, the audit trace omitted
`rule_breakdown` entirely so the audit CSV's `rules_<category>_hit`
columns shipped as constant zeros.

Production audit CSVs generated BEFORE May 10 (notably irrigation v21
5-seed data dated April 25 — 3276 rows × 5 seeds = 16,380 rows with
`rules_<category>_hit` all 0 even though `failed_rules` had real rule
fires) cannot be retroactively fixed without re-running. The fix is
nevertheless live in current code, and these tests pin it to prevent
silent re-introduction of the all-zero bug.

Note: paper-1b IBR / EHE pipelines read `proposed_skill` /
`final_skill` / `status` / `wsa_label`, NOT these aggregate count
columns — so the pre-May-10 all-zero artefact has zero paper impact.
"""
from __future__ import annotations

import pytest

from broker.interfaces.skill_types import ValidationResult
from broker.validators.governance import get_rule_breakdown
from broker.core._audit_helpers import _safe_rule_breakdown


def _make_result(category: str, valid: bool = False) -> ValidationResult:
    """Synthetic ValidationResult carrying a category in metadata."""
    return ValidationResult(
        valid=valid,
        validator_name="TestValidator",
        errors=[] if valid else [f"{category} rule fired"],
        warnings=[],
        metadata={"category": category, "rule_id": f"test_{category}_rule"},
    )


def test_get_rule_breakdown_counts_thinking_fires():
    """A single thinking-category ValidationResult yields
    `thinking=1` in the breakdown dict."""
    results = [_make_result("thinking")]
    breakdown = get_rule_breakdown(results)
    assert breakdown == {
        "personal": 0,
        "social": 0,
        "thinking": 1,
        "physical": 0,
        "semantic": 0,
    }


def test_get_rule_breakdown_counts_mixed_categories():
    """Per-category increments work independently across rule fires."""
    results = [
        _make_result("thinking"),
        _make_result("thinking"),  # 2x thinking
        _make_result("physical"),  # 1x physical
        _make_result("personal"),  # 1x personal
    ]
    breakdown = get_rule_breakdown(results)
    assert breakdown["thinking"] == 2
    assert breakdown["physical"] == 1
    assert breakdown["personal"] == 1
    assert breakdown["social"] == 0
    assert breakdown["semantic"] == 0


def test_get_rule_breakdown_ignores_unknown_category():
    """A ValidationResult with an unknown category does NOT add a new
    key and does NOT crash — the breakdown dict has a fixed schema."""
    results = [_make_result("nonexistent_category")]
    breakdown = get_rule_breakdown(results)
    # All 5 known categories remain 0
    assert sum(breakdown.values()) == 0
    assert "nonexistent_category" not in breakdown


def test_safe_rule_breakdown_handles_flat_list():
    """`_safe_rule_breakdown` accepts a flat list of ValidationResults
    (the normal `all_validation_history` shape after Phase 6C-v3)."""
    results = [_make_result("thinking"), _make_result("physical")]
    breakdown = _safe_rule_breakdown(results)
    assert breakdown == {
        "personal": 0,
        "social": 0,
        "thinking": 1,
        "physical": 1,
        "semantic": 0,
    }


def test_safe_rule_breakdown_handles_nested_list_history():
    """`_safe_rule_breakdown` extends nested lists (the legacy retry-loop
    shape where each retry contributes a `List[ValidationResult]`)."""
    history = [
        [_make_result("thinking"), _make_result("physical")],  # retry 1
        [_make_result("thinking")],  # retry 2
    ]
    breakdown = _safe_rule_breakdown(history)
    assert breakdown["thinking"] == 2  # flattened across retries
    assert breakdown["physical"] == 1


def test_safe_rule_breakdown_handles_empty_history():
    """Empty / None history → all zeros, no crash."""
    assert _safe_rule_breakdown([])["thinking"] == 0
    assert _safe_rule_breakdown(None)["thinking"] == 0
