"""P0-1c: the ADVISE disposition — demotion predicate and intervention-report builder.

WHY THIS EXISTS
---------------
The framework ships exactly two validator dispositions, and neither can express
"tell the model about the rule, but do not block":

  ERROR    -> ValidationResult(valid=False, errors=[msg]). Opens the governance
              retry loop, which builds InterventionReports and re-prompts.
  WARNING  -> ValidationResult(valid=True, errors=[], warnings=[msg]). Executes
              anyway, and — verified at three independent points — has NO channel
              to the model at all:
                (a) the loop condition is `not all_valid` (_retry_loop.py:218)
                    and a WARNING sets valid=True, so the loop never opens;
                (b) reports are built inside `if v.errors:` (_retry_loop.py:224)
                    and a WARNING's errors list is empty by construction
                    (agent_validator.py:511);
                (c) the fallback branch (_retry_loop.py:245-247) also
                    comprehends only `v.errors`.

So the long-standing lab claim "WARNING rules produce ~0% behaviour change" is
ARCHITECTURALLY FORCED, not an empirical finding — it cannot be published as a
result. This module builds the missing third disposition so the
advice-versus-enforcement question becomes empirically answerable.

WHY DEMOTION RATHER THAN A NEW `level:` VALUE
---------------------------------------------
A per-rule `level: ADVISE` was designed and rejected. Every level decision in
AgentValidator is the exact-string ternary
``lv = ValidationLevel.ERROR if rule.level == "ERROR" else ValidationLevel.WARNING``
(agent_validator.py:254, :348, :501), so a third YAML value silently becomes
WARNING; and the result-construction sites at :259/:278/:300/:356 would emit
``valid=False`` with BOTH errors and warnings empty — a shape the codebase has
never produced, which opens the retry loop, builds zero reports, and burns three
content-free real-LLM calls before rejecting. Demoting the RESULT downstream of
the validators touches the level machinery zero times, and lets arms B, B' and C
read one byte-identical rule set so identical rule firing is a property of
construction rather than a claim in the Methods.

DEFAULT-OFF: with no ``global_config.governance.advise`` block the allowlist is
empty and :func:`demote` returns the *same list object*, so every frozen baseline
is bit-for-bit unchanged.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, FrozenSet, List, Optional

from ..interfaces.skill_types import InterventionReport, ValidationResult

# Rule ids that may NEVER be demoted, however the config is written. Affordability
# is a hard financial-feasibility gate carrying `deterministic: True`
# (agent_validator.py:190-211); demoting it would let an agent execute an action it
# cannot pay for and mutate world state on a false premise. Enforced twice: here at
# predicate time, and at config-parse time so a bad arm config fails loudly.
ADVISE_DENY: FrozenSet[str] = frozenset({
    # Financial feasibility. Carries `deterministic: True` and feeds EarlyExit.
    "affordability",
    # GENERIC ids assigned registry-wide, NOT per-skill: the engine stamps the SAME
    # rules_hit on every skill's physical-precondition and output-schema failure.
    # Advising either therefore switches that floor off for the ENTIRE registry, not
    # for one rule -- so a skill whose precondition asserts an irreversible state
    # change has not already happened could be re-executed, mutating the world into
    # a physically impossible configuration. These encode world affordances, never
    # behavioural theory, so they are never advisable.
    "precondition_violation",
    "output_schema_violation",
})

# Validator names that are structural floors, never theory. Belt-and-braces: these
# carry no rule_id (see the freeze comment at agent_validator.py:174-183) so the
# rules_hit guard below already excludes them.
_STRUCTURAL_VALIDATORS: FrozenSet[str] = frozenset({
    "AgentValidator:format",
    "AgentValidator:valid_decisions",
})


def is_advisable(v: Optional[ValidationResult], allow: FrozenSet[str]) -> bool:
    """True iff this blocking result is one the arm config asked to make advisory.

    Fails CLOSED: anything without an explicit ``metadata["rules_hit"][0]`` in
    ``allow`` keeps blocking. That is deliberate — an allowlist keyed on rule id
    reaches domain custom validators (whose names do not share the
    ``AgentValidator:thinking`` prefix) and cannot silently widen when a new
    validator family is added later.
    """
    if v is None or getattr(v, "valid", True):
        return False
    if (getattr(v, "validator_name", "") or "") in _STRUCTURAL_VALIDATORS:
        return False
    hits = (getattr(v, "metadata", None) or {}).get("rules_hit") or []
    if not hits or not hits[0]:
        return False
    rid = hits[0]
    if rid in ADVISE_DENY:
        return False
    return rid in allow


def demote(results: List[ValidationResult], allow: FrozenSet[str]) -> List[ValidationResult]:
    """Rewrite advised blocking results into non-blocking advisories.

    Returns the SAME list object when ``allow`` is empty — that object identity is
    the flag-OFF byte-identity guarantee, and a test pins it.

    Never mutates an input result. AgentValidator keeps long-lived references to
    the very objects it returns (``self.errors`` / ``self.warnings`` populated in
    ``_categorize_results``), so in-place edits would leak across decisions and
    across threads — ``process_step`` runs on a shared engine under a
    ThreadPoolExecutor.

    The rewritten copy carries ``metadata["disposition"] = "ADVISE"``, which is
    what the advisory pass keys on, plus ``advised_from_level`` so the audit trail
    still records that the rule was authored as ERROR.
    """
    if not allow:
        return results
    out: List[ValidationResult] = []
    for v in results:
        if not is_advisable(v, allow):
            out.append(v)
            continue
        meta: Dict[str, Any] = dict(getattr(v, "metadata", None) or {})
        meta["disposition"] = "ADVISE"
        meta["advised_from_level"] = meta.get("level", "ERROR")
        # The message moves errors -> warnings so `all_valid` stays True and the
        # governance retry loop is never opened by this rule, while the text
        # survives for the advisory prompt.
        out.append(replace(
            v,
            valid=True,
            errors=[],
            warnings=list(getattr(v, "warnings", None) or []) + list(getattr(v, "errors", None) or []),
            metadata=meta,
        ))
    return out


def render_intervention_prompt(
    adapter,
    original_prompt: str,
    reports: List[Any],
    *,
    max_reports: Optional[int] = None,
    framing: str = "legacy",
    include_reports: bool = True,
) -> "tuple[str, int]":
    """Render a retry/advisory prompt, tolerating adapters that predate P0-1c.

    ``ModelAdapter`` is a user-extensible seam — domains and tests supply their own
    subclasses — so requiring the new two-value ``format_intervention_prompt`` would
    break every existing custom adapter that implements only ``format_retry_prompt``.
    This shim keeps that contract:

    * adapter exposes ``format_intervention_prompt``  -> use it; accept either the
      ``(text, shown)`` tuple or a bare string (test doubles return the latter);
    * adapter exposes only ``format_retry_prompt``    -> use it, which can express
      the legacy framing only. Asking for a non-legacy framing on such an adapter
      is a configuration error and raises rather than silently rendering the
      wrong text into an experiment arm.
    """
    fn = getattr(adapter, "format_intervention_prompt", None)
    if callable(fn):
        res = fn(original_prompt, reports, max_reports=max_reports,
                 framing=framing, include_reports=include_reports)
        if isinstance(res, tuple) and len(res) == 2:
            return res
        return res, len(reports)
    if framing != "legacy" or not include_reports:
        raise ValueError(
            f"model adapter {type(adapter).__name__} does not implement "
            "format_intervention_prompt, so it cannot render "
            f"framing={framing!r}/include_reports={include_reports}. Upgrade the "
            "adapter before running a non-legacy experiment arm."
        )
    return adapter.format_retry_prompt(original_prompt, reports, max_reports=max_reports), len(reports)


def build_intervention_reports(
    validation_results: List[ValidationResult],
    skill_proposal,
    *,
    source: str = "errors",
    severity: Optional[str] = None,
) -> List[InterventionReport]:
    """Build the reports rendered into a retry / advisory prompt.

    ``source="errors"``     — the enforce path. Extracted verbatim from the inline
    block previously at ``_retry_loop.py:222-234``; semantics unchanged, including
    the ``"ERROR" if not v.valid else "WARNING"`` severity default.

    ``source="advisories"`` — the advise path. Iterates the ``warnings`` of results
    demoted by :func:`demote`, so an advisory prompt is built from exactly the
    rules the arm config advised on, and nothing else.
    """
    reports: List[InterventionReport] = []
    for v in validation_results:
        if not v:
            continue
        if source == "advisories":
            if (getattr(v, "metadata", None) or {}).get("disposition") != "ADVISE":
                continue
            messages = getattr(v, "warnings", None) or []
            sev = severity or "RULE"
        else:
            messages = getattr(v, "errors", None) or []
            sev = severity or ("ERROR" if not v.valid else "WARNING")
        meta = getattr(v, "metadata", None) or {}
        rule_id = (meta.get("rules_hit") or ["unknown_rule"])[0] if meta.get("rules_hit") else "unknown_rule"
        for message in messages:
            reports.append(InterventionReport(
                rule_id=rule_id,
                blocked_skill=skill_proposal.skill_name if skill_proposal else "unknown",
                violation_summary=message,
                suggested_correction=meta.get("suggestion"),
                severity=sev,
                domain_context=meta,
            ))
    return reports
