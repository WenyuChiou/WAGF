"""Phase 6O-A-1 — Terminal outcome classifier (domain-agnostic).

Classifies one audit trace row into one of 8 categories. Generic: reads
only the **existing** audit CSV / JSONL columns plus the optional
metadata contract defined in
`broker/interfaces/validation_metadata.py::ValidatorMetadata`. Contains
zero domain-specific strings — verified by the I5 token guard
(`TestDomainGenericity`).

Phase 6O-A-1 scope: classifier + tests only. Validators do NOT yet
populate `expected_terminal` / `feasible_actions` — that lands in
6O-A-2 as a per-validator update. Until 6O-A-2 ships, real audit data
will tend to classify as `unknown_terminal` when the data lacks the
new metadata keys; synthetic tests cover the full taxonomy.

Per the gap-matrix audit, this module is imported ONLY by new test
code in 6O-A-1, NOT by any existing experiment runtime path —
paper-1b byte-identical guarantee preserved.
"""
from __future__ import annotations

from typing import Any, Dict, Literal

TerminalCategory = Literal[
    "approved",
    "retry_recovered",
    "expected_hard_block",
    "recoverable_retry_failed",
    "no_feasible_action",
    "parser_failure",
    "execution_failure",
    "unknown_terminal",
]

#: All 8 categories, in human-meaningful order (success → recovery →
#: terminal-expected → terminal-recoverable → terminal-no-option → other).
TERMINAL_CATEGORIES: tuple[TerminalCategory, ...] = (
    "approved",
    "retry_recovered",
    "expected_hard_block",
    "recoverable_retry_failed",
    "no_feasible_action",
    "parser_failure",
    "execution_failure",
    "unknown_terminal",
)


def _as_int(value: Any, default: int = 0) -> int:
    """Tolerant int coerce — audit CSV reads can return strings."""
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _validation_issues(trace: Dict[str, Any]) -> list:
    """Extract validation_issues list from a trace row.

    JSONL traces carry `validation_issues` as a list of dicts. CSV rows
    flatten to `failed_rules` (pipe-separated) — when only CSV is
    available, validators' metadata cannot be inspected, so the
    classifier conservatively falls back to `unknown_terminal` for
    contested cases.
    """
    raw = trace.get("validation_issues")
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []


def _issue_meta(issue: Dict[str, Any]) -> Dict[str, Any]:
    """Pull the metadata sub-dict off a validation_issues entry."""
    meta = issue.get("metadata")
    return meta if isinstance(meta, dict) else {}


def classify_terminal(trace: Dict[str, Any]) -> TerminalCategory:
    """Classify one trace row's terminal outcome.

    Args:
        trace: A dict matching the JSONL trace shape (preferred) OR the
            audit CSV row shape (degrades gracefully). Recognised keys:
              - status: 'APPROVED' / 'REJECTED' / 'REJECTED_FALLBACK' /
                  'NO_FEASIBLE_ALTERNATIVE' / 'PARSE_FAILED' /
                  'EXECUTION_ERROR' (case-insensitive)
              - retry_count: int (or string from CSV)
              - format_retries: int
              - failed_rules: str (CSV pipe-separated) or
                  validation_issues: list (JSONL)
              - execution_error: bool/str truthy iff execution failed
                  after APPROVED.

    Returns:
        One of the 8 TerminalCategory literals.

    Decision rules (evaluated in priority order — first match wins):
      1. status APPROVED and retry_count == 0 → `approved`
      2. status APPROVED and retry_count > 0 → `retry_recovered`
      3. status APPROVED and execution_error truthy → `execution_failure`
      4. status contains 'PARSE' or final format_retries > 0 with
         non-APPROVED → `parser_failure`
      5. status contains 'NO_FEASIBLE' → `no_feasible_action`
      6. any validation_issue has metadata.expected_terminal == True
         → `expected_hard_block`
      7. retry_count > 0 AND any validation_issue has non-empty
         metadata.feasible_actions → `recoverable_retry_failed`
      8. fallback → `unknown_terminal`

    Note: rules 6+7 require JSONL trace input — CSV rows degrade to
    `unknown_terminal` for REJECTED outcomes lacking metadata. This
    is the **conservative** default; Phase 6O-A-2 will close the gap
    by having validators populate the new keys.
    """
    status = str(trace.get("status") or "").upper()
    retry_count = _as_int(trace.get("retry_count"))
    format_retries = _as_int(trace.get("format_retries"))
    execution_error = bool(trace.get("execution_error"))

    # Rule 3: APPROVED but execution failed
    if status == "APPROVED" and execution_error:
        return "execution_failure"

    # Rule 1+2: APPROVED paths
    if status == "APPROVED":
        return "retry_recovered" if retry_count > 0 else "approved"

    # Rule 4: parser failure
    if "PARSE" in status:
        return "parser_failure"
    if format_retries > 0:
        # APPROVED already returned above, so we know status != APPROVED here.
        return "parser_failure"

    # Rule 5: no feasible alternative path
    if "NO_FEASIBLE" in status:
        return "no_feasible_action"

    # Rules 6+7 need validation_issues metadata (JSONL)
    issues = _validation_issues(trace)
    if issues:
        if any(_issue_meta(i).get("expected_terminal") is True for i in issues):
            return "expected_hard_block"
        has_feasible = any(
            _issue_meta(i).get("feasible_actions") for i in issues
        )
        if has_feasible and retry_count > 0:
            return "recoverable_retry_failed"

    return "unknown_terminal"
