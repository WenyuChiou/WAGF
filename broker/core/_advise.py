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
    feasible_line: Optional[str] = None,
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

    ``feasible_line`` (the feasible-set sentence, default None) is passed on
    only when set, so adapters and test doubles without that keyword keep
    working on every run that does not ask for it. An adapter exposing only
    ``format_retry_prompt`` gets it as one extra report after truncation.
    """
    fn = getattr(adapter, "format_intervention_prompt", None)
    if callable(fn):
        extra = {} if feasible_line is None else {"feasible_line": feasible_line}
        res = fn(original_prompt, reports, max_reports=max_reports,
                 framing=framing, include_reports=include_reports, **extra)
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
    if feasible_line is not None:
        shown = list(reports[:max_reports]) if max_reports else list(reports)
        return adapter.format_retry_prompt(original_prompt, shown + [feasible_line]), len(shown)
    return adapter.format_retry_prompt(original_prompt, reports, max_reports=max_reports), len(reports)


# Validator categories the soft channel can name, longest-prefix first so
# ``thinking_construct_missing`` resolves to ``thinking`` rather than to nothing.
# The prefix is what makes ``advise_findings`` readable: the same cell can carry a
# Tier-2 coherence finding, a social finding and a missing-construct finding, and
# without the category a reader cannot tell which layer produced which id.
_SOFT_FINDING_CATEGORIES = (
    "thinking", "identity", "social", "personal", "physical", "semantic",
)


def _soft_finding_category(v) -> str:
    """The validator category a soft finding came from, or ``"unknown"``.

    Reads ``metadata["category"]`` when the producer set one; otherwise infers
    from the validator name, which is either ``AgentValidator:<tier>_<level>``
    or a class name such as ``SocialValidator``. Never raises and never guesses
    past the table above — an unrecognised producer is reported as ``unknown``
    rather than filed under a plausible category, the same discipline
    ``_infer_category`` follows for the ``rules_*_hit`` buckets.
    """
    meta = getattr(v, "metadata", None) or {}
    declared = str(meta.get("category") or "").strip().lower()
    if declared:
        return declared
    name = str(getattr(v, "validator_name", "") or "").strip()
    tail = name.split(":", 1)[1] if ":" in name else name
    tail = tail.strip().lower()
    for known in _SOFT_FINDING_CATEGORIES:
        if tail.startswith(known):
            return known
    return "unknown"


def _soft_finding_labels(v) -> List[str]:
    """Category-prefixed ids for one soft finding, e.g. ``thinking:low_coping_block``.

    ``construct_missing`` is special-cased to ``construct_missing:<field>``: the
    rule id is the same string for every unreported construct, so without the
    field the cell would collapse two different findings into one id and a
    reader could not tell which construct was missing.
    """
    meta = getattr(v, "metadata", None) or {}
    hits = meta.get("rules_hit") or ([meta["rule_id"]] if meta.get("rule_id") else [])
    category = _soft_finding_category(v)
    out: List[str] = []
    for h in hits:
        if not h:
            continue
        rid = str(h)
        if rid in ("construct_missing", "world_variable_missing"):
            field = str(meta.get("field") or "").strip()
            out.append(f"{rid}:{field}" if field else rid)
        else:
            out.append(f"{category}:{rid}")
    return out


def _is_soft_finding(v) -> bool:
    """The shape test, WITHOUT the id requirement (C2 counts the id-less ones)."""
    if v is None or not getattr(v, "valid", True):
        return False
    meta = getattr(v, "metadata", None) or {}
    if meta.get("disposition") == "ADVISE":
        return False
    # Shadow mode already converted a BLOCKING result into an observe-only one
    # (``BaseValidator._to_shadow``), and it is recorded in its own
    # ``shadow_blocked`` column. Counting it again here would show a rule the
    # operator asked to observe as a soft finding, and under ``feedback`` would
    # feed a suppressed enforcement rule back to the model as advice — turning a
    # shadow arm into a quiet advice arm with nothing in the row saying so.
    if meta.get("shadow_blocked"):
        return False
    if not (getattr(v, "warnings", None) or []):
        return False
    return True


def collect_soft_findings(results: Optional[List[ValidationResult]]) -> List[ValidationResult]:
    """PR-6: the NON-BLOCKING WARNING findings of one validation pass.

    This is the framework's soft rule layer as it actually exists: results with
    ``valid=True`` and a non-empty ``warnings`` list, carrying a rule id. They
    never block, and before PR-6 they never reached the model either, so a
    WARNING rule could not change anything and could not be shown to have failed
    to — which is why the "WARNING rules produce ~0% behaviour change" claim was
    unpublishable rather than merely unsupported.

    Results already demoted by :func:`demote` are EXCLUDED. Those belong to the
    P0-1c arm machinery, which issues its own advisory call; counting them here
    too would show one finding to the model twice and double-count it in the
    audit row. Shadow-converted results are excluded for the same reason from
    the other direction — they are suppressed ENFORCEMENT, not advice.

    Results with NO rule id are also excluded, and counted separately by
    :func:`count_unidentified_soft_findings`. Including them produced a row with
    ``advise_shown=True`` and ``advise_findings=""``: an advisory call was made,
    the model was told something, and the audit row named nothing — the exact
    unreadable state the ``advise_shown`` column exists to prevent.
    """
    return [v for v in (results or []) if _is_soft_finding(v) and _soft_finding_labels(v)]


def count_unidentified_soft_findings(results: Optional[List[ValidationResult]]) -> int:
    """How many WARNING results carried no rule id, so could not be named.

    Recorded as ``soft_findings_unidentified`` under the soft channel. A non-zero
    count is the honest reading of a short ``advise_findings`` cell: warnings
    fired that this channel cannot name, not that nothing warned.
    """
    return sum(
        1 for v in (results or [])
        if _is_soft_finding(v) and not _soft_finding_labels(v)
    )


def soft_finding_ids(results: Optional[List[ValidationResult]]) -> List[str]:
    """Sorted, deduped category-prefixed ids — the ``advise_findings`` cell."""
    ids = set()
    for v in collect_soft_findings(results):
        ids.update(_soft_finding_labels(v))
    return sorted(ids)


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

    ``source="warnings"``   — PR-6's soft-rule path. Iterates the ``warnings`` of
    results that were AUTHORED as WARNING (never demoted), so the same renderer
    serves advice and enforcement and no wording can drift between them.
    """
    reports: List[InterventionReport] = []
    for v in validation_results:
        if not v:
            continue
        if source == "warnings":
            messages = getattr(v, "warnings", None) or []
            sev = severity or "ADVICE"
        elif source == "advisories":
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
