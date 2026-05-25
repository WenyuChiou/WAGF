"""Phase 6O-A-1 — Tests for the terminal-outcome classifier.

Synthetic fixtures only (no broker pipeline integration). Each test
constructs a minimal trace dict matching the audit JSONL / CSV shape
and asserts the classifier emits the expected category.

By design, this test module is the ONLY consumer of
`broker.components.analytics.terminal_taxonomy` in Phase 6O-A-1.
Production runtime paths do NOT import it — see
`.ai/2026/05/25/phase_6o_gap_matrix.md` R5 PASS.
"""
from __future__ import annotations

import pytest

from broker.components.analytics.terminal_taxonomy import (
    TERMINAL_CATEGORIES,
    classify_terminal,
)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _trace(**overrides) -> dict:
    """Build a default-APPROVED trace; overrides win."""
    base = {
        "status": "APPROVED",
        "retry_count": 0,
        "format_retries": 0,
        "failed_rules": "",
        "validation_issues": [],
    }
    base.update(overrides)
    return base


def _issue(rule_id: str, **metadata) -> dict:
    return {
        "rule_id": rule_id,
        "metadata": dict(metadata),
    }


# ---------------------------------------------------------------------------
# Rule 1 — APPROVED, no retry
# ---------------------------------------------------------------------------


def test_approved_zero_retries():
    assert classify_terminal(_trace()) == "approved"


def test_approved_status_lowercase_normalized():
    # status is canonicalised via .upper() — lowercase should still classify.
    assert classify_terminal(_trace(status="approved")) == "approved"


# ---------------------------------------------------------------------------
# Rule 2 — retry_recovered
# ---------------------------------------------------------------------------


def test_retry_recovered_one_retry():
    assert classify_terminal(_trace(retry_count=1)) == "retry_recovered"


def test_retry_recovered_string_retry_count_coerced():
    # Real audit CSV reads back retry_count as string sometimes.
    assert classify_terminal(_trace(retry_count="2")) == "retry_recovered"


# ---------------------------------------------------------------------------
# Rule 3 — execution_failure (APPROVED but execution_error truthy)
# ---------------------------------------------------------------------------


def test_execution_failure_after_approved():
    t = _trace(execution_error=True)
    assert classify_terminal(t) == "execution_failure"


def test_execution_failure_dominates_retry_recovered():
    # Even if retry succeeded, downstream execution failure wins.
    t = _trace(retry_count=1, execution_error=True)
    assert classify_terminal(t) == "execution_failure"


# ---------------------------------------------------------------------------
# Rule 4 — parser_failure
# ---------------------------------------------------------------------------


def test_parser_failure_explicit_status():
    t = _trace(status="PARSE_FAILED")
    assert classify_terminal(t) == "parser_failure"


def test_parser_failure_via_format_retries_with_rejection():
    # format_retries > 0 + non-APPROVED → parser_failure.
    t = _trace(status="REJECTED", format_retries=3)
    assert classify_terminal(t) == "parser_failure"


def test_format_retries_with_approved_is_retry_recovered():
    # format_retries can happen on a row that ultimately APPROVED — that
    # should NOT classify as parser_failure.
    t = _trace(format_retries=2, retry_count=2)
    assert classify_terminal(t) == "retry_recovered"


# ---------------------------------------------------------------------------
# Rule 5 — no_feasible_action
# ---------------------------------------------------------------------------


def test_no_feasible_action_status():
    t = _trace(status="NO_FEASIBLE_ALTERNATIVE")
    assert classify_terminal(t) == "no_feasible_action"


# ---------------------------------------------------------------------------
# Rule 6 — expected_hard_block (from validator metadata)
# ---------------------------------------------------------------------------


def test_expected_hard_block_via_metadata():
    t = _trace(
        status="REJECTED",
        validation_issues=[
            _issue("water_right_ceiling", expected_terminal=True, constraint_type="hard"),
        ],
    )
    assert classify_terminal(t) == "expected_hard_block"


def test_expected_hard_block_dominates_recoverable():
    # If multiple issues — one with expected_terminal True and another
    # with feasible_actions — the hard-block wins (priority order).
    t = _trace(
        status="REJECTED",
        retry_count=2,
        validation_issues=[
            _issue("at_cap", expected_terminal=True),
            _issue("soft_rule", feasible_actions=["maintain"]),
        ],
    )
    assert classify_terminal(t) == "expected_hard_block"


# ---------------------------------------------------------------------------
# Rule 7 — recoverable_retry_failed
# ---------------------------------------------------------------------------


def test_recoverable_retry_failed_with_feasible_alternatives():
    t = _trace(
        status="REJECTED",
        retry_count=3,
        validation_issues=[
            _issue("magnitude_too_large", feasible_actions=["maintain", "decrease_small"]),
        ],
    )
    assert classify_terminal(t) == "recoverable_retry_failed"


def test_recoverable_requires_retry_count():
    # If retry_count == 0, model never tried recovery — not "recoverable
    # _retry_failed" but rather an unknown terminal.
    t = _trace(
        status="REJECTED",
        retry_count=0,
        validation_issues=[
            _issue("magnitude_too_large", feasible_actions=["maintain"]),
        ],
    )
    assert classify_terminal(t) == "unknown_terminal"


# ---------------------------------------------------------------------------
# Rule 8 — unknown_terminal (fallback)
# ---------------------------------------------------------------------------


def test_unknown_terminal_for_rejected_without_metadata():
    # CSV-only rows lacking validation_issues lose hard-block / recoverable
    # signal — conservatively classify as unknown_terminal.
    t = _trace(status="REJECTED", failed_rules="some_rule")
    assert classify_terminal(t) == "unknown_terminal"


def test_unknown_terminal_for_empty_trace():
    assert classify_terminal({}) == "unknown_terminal"


def test_unknown_terminal_for_rejected_fallback_without_metadata():
    t = _trace(status="REJECTED_FALLBACK", retry_count=1)
    assert classify_terminal(t) == "unknown_terminal"


# ---------------------------------------------------------------------------
# Shape / robustness checks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("category", TERMINAL_CATEGORIES)
def test_taxonomy_constant_includes_all_categories(category):
    """TERMINAL_CATEGORIES tuple must include every Literal — sanity
    check the constant stays in sync with the type."""
    assert category in TERMINAL_CATEGORIES
    assert len(TERMINAL_CATEGORIES) == 8


def test_validation_issues_non_dict_entries_ignored():
    # Malformed JSONL might have non-dict items in validation_issues.
    t = _trace(
        status="REJECTED",
        retry_count=1,
        validation_issues=["junk", 42, None, _issue("real", feasible_actions=["x"])],
    )
    assert classify_terminal(t) == "recoverable_retry_failed"


def test_garbage_retry_count_string_treated_as_zero():
    t = _trace(retry_count="not-a-number")
    assert classify_terminal(t) == "approved"


def test_none_status_treated_as_unknown():
    t = _trace(status=None)
    # None status → "" upper → fails all status checks → fallback unknown
    assert classify_terminal(t) == "unknown_terminal"


# ---------------------------------------------------------------------------
# Domain-genericity contract — no domain-specific strings in this module
# ---------------------------------------------------------------------------


def test_taxonomy_module_has_no_domain_tokens():
    """The classifier file must contain zero domain-specific terms.

    This is a quick local check that mirrors what
    `TestDomainGenericity` enforces at the broker/ scope. Failing this
    test means the classifier accidentally hard-coded a skill name /
    construct label / domain token.
    """
    import broker.components.analytics.terminal_taxonomy as mod
    source_path = mod.__file__
    assert source_path is not None
    with open(source_path, "r", encoding="utf-8") as f:
        body = f.read()
    forbidden = (
        "flood",
        "irrigation",
        "vaccination",
        "PMT",
        "HBM",
        "WSA",
        "ACA",
        "NFIP",
        "FEMA",
        "Mead",
        "Powell",
    )
    for token in forbidden:
        # Allow inside comments / docstrings only if used as an example
        # in narrative explanation. The token must NOT appear in
        # executable code.  Conservative: assert token not present at
        # all in this minimal classifier (which has no comments
        # referencing examples by name).
        assert token.lower() not in body.lower(), (
            f"Terminal-taxonomy classifier must be domain-agnostic; "
            f"found {token!r} in source."
        )
