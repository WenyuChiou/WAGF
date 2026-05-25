"""Phase 6O-A-1 — TypedDict contract for ValidationResult.metadata.

`ValidationResult.metadata` (defined at `broker/interfaces/skill_types.py:84`)
is a free-form `Dict[str, Any]` by design — every validator may attach
domain-specific context to its result without changing the framework
contract. This file formalises the SUBSET of keys that downstream
broker code may rely on, so contributors writing new validators know
which keys to populate for full feature support.

All fields are **optional** (`TypedDict total=False`). Missing keys are
treated as "feature not available for this rule" by consumers:

- The terminal-outcome classifier (`broker.components.analytics.terminal_taxonomy`)
  returns `unknown_terminal` when `expected_terminal` / `feasible_actions`
  are absent.
- The audit CSV writer (`broker.components.analytics.audit`) never reads
  the metadata dict directly — see Phase 6O-A subagent audit
  (`.ai/2026/05/25/phase_6o_gap_matrix.md` R1 PASS) — so adding new
  keys is byte-identical to paper-1b output.

The contract documents **existing** keys (already populated by current
validators since Phase 6N-D-1) plus **new** keys introduced by Phase
6O-A-1 for future validator-side population in 6O-A-2.
"""
from __future__ import annotations

from typing import List, Literal, TypedDict

# ---------------------------------------------------------------------------
# Existing keys — populated by current validators
# ---------------------------------------------------------------------------

#: Rule severity propagation. ERROR rules block-and-retry; WARNING rules
#: log-only by default (Phase 6N-D-1 closed the silent-block bug at
#: `broker/validators/governance/thinking_validator.py:329-355`).
SeverityLevel = Literal["ERROR", "WARNING"]

#: Validator category — broader than a specific rule_id, used by audit
#: bookkeeping and the terminal-outcome classifier.
ValidatorCategory = Literal[
    "physical",
    "institutional",
    "behavioral",
    "semantic",
    "format",
    "personal",
    "social",
    "thinking",
    "other",
]

#: Constraint severity classification — populated by Phase 6O-A-2 validators.
#: `hard` = physical / legal impossibility (water-right ceiling, recent-dose
#: cooldown); `soft` = preference / norm (peer-pressure WARNING); `diagnostic`
#: = informational only, never blocks.
ConstraintType = Literal["hard", "soft", "diagnostic"]


# ---------------------------------------------------------------------------
# The full contract
# ---------------------------------------------------------------------------


class ValidatorMetadata(TypedDict, total=False):
    """Optional structured fields inside `ValidationResult.metadata`.

    Validators MAY populate any subset of these keys. Consumers MUST
    treat missing keys as "feature unavailable" — never raise.

    See `.ai/2026/05/25/phase_6o_gap_matrix.md` for the Phase 6O-A
    derivation and `feedback_confirm_experiments_run_after_broker_change`
    memory for the byte-identical paper-1b guarantee that motivated the
    additive-only approach.
    """

    # --- existing (already in production audit traces) ---

    rule_id: str
    """The rule that fired. Stable across validator invocations."""

    category: ValidatorCategory
    """Validator family this rule belongs to."""

    level: SeverityLevel
    """Severity propagation — see `Phase 6N-D-1` closure."""

    # --- new in Phase 6O-A-1 (contract only; validator population in 6O-A-2) ---

    feasible_actions: List[str]
    """Skill IDs that would PASS this validator instead of the blocked
    one. Empty list means no alternative passes (caller should expect
    a terminal outcome). Consumed by retry-prompt formatting (Phase
    6O-A-2) and the terminal-outcome classifier."""

    recovery_hint: str
    """Short, human-readable instruction for retry-prompt formatting.
    Example: 'Consider a smaller magnitude tier (max 5%).' Free-form,
    bounded to ~120 chars in style guide."""

    expected_terminal: bool
    """Domain-pack assertion: a rejection from this rule reflects a
    valid physical/institutional impossibility, NOT a model failure.
    Used by the terminal-outcome classifier to distinguish
    `expected_hard_block` from `recoverable_retry_failed`. Default
    treats absence as `False` so the framework is conservative —
    domains must opt IN to hard-block classification."""

    constraint_type: ConstraintType
    """Constraint severity (see `ConstraintType` above)."""
