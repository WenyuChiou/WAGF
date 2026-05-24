"""Phase 6N-D-2 regression test — `RuleCondition._get_value_from_context`
defensive label normalisation.

Pre-fix `_get_value_from_context` returned `reasoning.get(self.field)`
raw — preserving whatever case the LLM emitted. Today the upstream
`unified_adapter.py` `.upper()` at line 474 already canonicalises
captures (Phase 6N-B), so this latent bug doesn't bite in production.
But any caller bypassing the unified adapter (test fixtures, direct
LLM-output injection, third-party tooling) would otherwise return raw
LLM case and silently miss `in ['H', 'VH']` comparisons.

Phase 6N-D-2 adds defensive `.upper().strip()` for string values in
the construct branch. These tests pin that contract.
"""
from __future__ import annotations

import pytest

from broker.governance.rule_types import RuleCondition


@pytest.mark.parametrize(
    "raw_value,expected_match",
    [
        ("H", True),       # canonical uppercase: matches
        ("h", True),       # lowercase: must match after normalization (the fix)
        (" H ", True),     # whitespace padding: must match after strip
        ("VH", True),
        ("vh", True),
        ("M", False),      # canonical but not in allow-list
        ("m", False),      # lowercase non-allowed: must stay non-match
        ("", False),       # empty: not a match
    ],
)
def test_construct_condition_normalizes_string_value(raw_value, expected_match):
    """Defensive normalisation: `_get_value_from_context` upper+strips
    string values for `construct`-type conditions."""
    cond = RuleCondition(
        type="construct",
        field="TEST_LABEL",
        operator="in",
        values=["H", "VH"],
    )
    context = {"reasoning": {"TEST_LABEL": raw_value}}

    assert cond.evaluate(context) is expected_match, (
        f"raw={raw_value!r}: evaluate returned wrong result. "
        f"Phase 6N-D-2 fix should normalise case+whitespace."
    )


def test_construct_condition_preserves_non_string_value():
    """Defensive normalisation must only apply to STRING values. Numbers
    or `None` pass through unchanged so existing operator semantics
    (`>`, `<`, etc.) keep working."""
    cond = RuleCondition(
        type="construct",
        field="TEST_SCORE",
        operator=">",
        values=[0.5],
    )
    # Numeric value — must NOT be touched by upper/strip
    context = {"reasoning": {"TEST_SCORE": 0.75}}
    assert cond.evaluate(context) is True


def test_construct_condition_handles_missing_field():
    """If the construct field is absent from reasoning, normalisation
    must NOT crash — returns None which then fails the comparison."""
    cond = RuleCondition(
        type="construct",
        field="MISSING_LABEL",
        operator="in",
        values=["H", "VH"],
    )
    context = {"reasoning": {}}
    # None should NOT match "in" against a list — no crash, no false-positive.
    assert cond.evaluate(context) is False
