"""
Governance Validators - Rule evaluation by category.

STATUS: this five-category stack (reached through ``validate_all`` /
``build_domain_validators`` below) is available architecture, not the
production default. As of v0.6.0 it has no non-test production call
sites: production experiment construction
(``broker/core/experiment_builder.py``) wires a single
``AgentValidator`` instance (``broker/validators/agent/agent_validator.py``),
whose own ``validate_thinking`` / ``_validate_internal`` methods run the
YAML rule engine (``identity_rules`` / ``thinking_rules`` / ...) directly —
they never call into ``PersonalValidator`` / ``SocialValidator`` /
``PhysicalValidator`` / ``SemanticGroundingValidator`` /
``ThinkingValidator`` below. The one exception is the opt-in, default-OFF
``domain_physical_dispatch`` path in ``skill_broker_engine.py``, which
calls ``PhysicalValidator`` directly (not through ``validate_all``) and
only when a run explicitly sets
``global_config.governance.dispatch_domain_physical``.

Validators:
- PersonalValidator: Financial + Cognitive constraints
- SocialValidator: Neighbor influence + Community norms (WARNING only)
- ThinkingValidator: construct-action coherence
- PhysicalValidator: State preconditions + Immutability
- SemanticGroundingValidator: Reasoning grounding + Factual consistency
- TypeValidator: Per-agent-type validation (skill eligibility, type rules)

Domain-specific builtin checks are injected by domain adapters. The generic
governance entrypoint should not import example packages directly.
"""
import os
import threading
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from broker.interfaces.skill_types import ValidationResult
from broker.validators.governance.base_validator import BaseValidator, BuiltinCheck
from broker.validators.governance.personal_validator import PersonalValidator
from broker.validators.governance.social_validator import SocialValidator
from broker.validators.governance.thinking_validator import ThinkingValidator
from broker.validators.governance.physical_validator import PhysicalValidator
from broker.validators.governance.semantic_validator import SemanticGroundingValidator
from broker.governance.type_validator import TypeValidator

# Phase 6T-F prep (2026-05-27): auto-register the generic-framework
# metadata (utility / financial / narrative_diffusion) at module
# import time. Closes a Phase-6P-A-class leak — previously utility +
# financial lived in broker/domains/water/thinking_checks.py even
# though their construct vocabulary is genuinely cross-domain. Now
# they're available to ANY domain pack without needing to import
# from the water namespace.
from . import frameworks  # noqa: F401

if TYPE_CHECKING:
    from broker.governance.rule_types import GovernanceRule

__all__ = [
    "BaseValidator",
    "BuiltinCheck",
    "PersonalValidator",
    "SocialValidator",
    "ThinkingValidator",
    "PhysicalValidator",
    "SemanticGroundingValidator",
    "TypeValidator",
    "validate_all",
    "get_rule_breakdown",
    "get_uncategorised_rules",
    "reset_uncategorised_rules",
]


def validate_all(
    skill_name: str,
    rules: List["GovernanceRule"],
    context: Dict[str, Any],
    agent_type: Optional[str] = None,
    registry: Optional["AgentTypeRegistry"] = None,
    domain: Optional[str] = None,
    config: Optional[object] = None,
) -> List[ValidationResult]:
    """
    Run all validators against a skill proposal.

    Not on the default production path — see the module STATUS note above.
    Production runs validate through ``AgentValidator`` instead.

    Args:
        skill_name: Proposed skill name
        rules: List of all governance rules
        context: Dictionary with reasoning, state, social_context
        agent_type: Optional agent type ID for per-type validation.
        registry: Optional AgentTypeRegistry instance for type validation.
        domain: Domain identifier controlling built-in checks.
        config: Optional ``AgentTypeConfig`` (or duck-typed equivalent) to
            resolve ``validators.framework_aware_labels`` from. P2 (PR-6
            review): without this, ``build_domain_validators`` below resolves
            the flag against ``AgentTypeConfig._instance`` — the most
            recently loaded config PROCESS-WIDE — every time it runs. A
            mid-run ``load_agent_config(other_path)`` on an unrelated path
            (``broker/components/context/tiered.py``,
            ``broker/components/response_format.py``) flips that global, so
            the SAME rule on the SAME decision could silently start reading a
            different flag value than the ``AgentValidator`` it is meant to
            agree with. Pass the caller's own config to pin it; ``None``
            preserves the old (global-singleton) resolution for callers that
            have no config object of their own.

    Returns:
        Combined list of ValidationResult from all validators
    """
    from broker.governance.rule_types import GovernanceRule as _GovernanceRule

    if rules and not isinstance(rules[0], _GovernanceRule):
        raise TypeError("rules must be GovernanceRule instances")

    resolved_domain = (domain or "").strip().lower() or (
        str(context.get("domain", "")).strip().lower()
        or str(context.get("env_state", {}).get("domain", "")).strip().lower()
        or str(context.get("agent_state", {}).get("env_state", {}).get("domain", "")).strip().lower()
        or str(os.environ.get("GOVERNANCE_DOMAIN", "")).strip().lower()
        or None
    )

    # Phase 6P-A (2026-05-25): runtime cross-namespace coupling closed.
    # The dispatcher now lives at a generic address —
    # `broker.components.governance.domain_validator_dispatch` — and its
    # body has been registry-driven since Phase 6C-v2. The function-local
    # import is preserved to keep `validate_all`'s module-load surface
    # narrow (no eager import of all validator subclasses).
    from broker.components.governance.domain_validator_dispatch import (
        build_domain_validators,
    )

    # Phase 6T-B (2026-05-27): plumb agent_type to the dispatcher so
    # GovernancePack.framework_for_agent_type can route household
    # decisions to PMT, government to utility, insurance to financial.
    # Pre-6T-B the agent_type was accepted by validate_all but dropped
    # before the dispatcher call — closing engineering-audit Y6.
    #
    # P2 (PR-6 review): also plumb `config` through, for the same reason —
    # `build_domain_validators` resolves `framework_aware_labels` from
    # `config` when given one, and from the process-global
    # `AgentTypeConfig._instance` otherwise. Dropping it here the same way
    # `agent_type` used to be dropped pre-6T-B would leave every caller that
    # DOES hold a config at the mercy of whichever config a concurrent
    # `load_agent_config(other_path)` call loaded last.
    validators = build_domain_validators(
        resolved_domain, agent_type=agent_type, config=config)

    all_results = []
    for validator in validators:
        results = validator.validate(skill_name, rules, context)
        all_results.extend(results)

    if agent_type:
        type_validator = TypeValidator(registry)
        type_results = type_validator.validate(skill_name, agent_type, context)
        all_results.extend(type_results)

    return all_results


_BREAKDOWN_CATEGORIES = ("personal", "social", "thinking", "physical", "semantic")

# Words that identify a category when the producing validator never set
# ``metadata["category"]``. Checked against the tier label, the validator name
# and the rule name/id, in that order of trust.
#
# PR-3 review item P1c: "identity" was mapped here to "personal" and that was
# WRONG. A domain's identity rules are typically PRECONDITION tests — has this
# action already been taken, is the agent still in the active set — not
# statements about who the agent is or what they can afford. Filing them under
# personal produced a confident number pointing at the wrong governance layer.
# They now fall through to `uncategorised` below, which is reported by name
# instead of being absorbed. (Worked example, in the domain that motivated
# this: docs/AUDIT_SCHEMA.md, "The rules_*_hit caveat".)
#
# The emission site is deliberately NOT changed: giving AgentValidator an
# explicit ``metadata["category"]`` would alter ``rules_*_hit`` with the flag
# OFF and break byte identity of every frozen corpus. Inference here is the
# only place this can be fixed without touching flag-OFF CSV values.
_CATEGORY_ALIASES = (
    ("afford", "personal"),
    ("financ", "personal"),
    ("budget", "personal"),
)

#: Rule ids whose category could not be determined, accumulated for the life of
#: the process and reported ONCE per run (by ``record_run_integrity``) rather
#: than per row. This is a side-artifact channel only: it is never a CSV column,
#: so it cannot move a byte of any audit CSV under either flag setting.
#:
#: C1 (round-2 review): the tally is kept ONLY on the inference path
#: (``allow_metadata_fallback=True``, i.e. a run with
#: ``audit.corrected_status_columns`` ON). With the flag OFF every
#: ``AgentValidator`` result is uncategorised by construction — that is the
#: documented defect, not news about this run — so tallying it there produced a
#: process-global number that grew on the byte-identity-locked path and told the
#: reader nothing. ``reset_uncategorised_rules`` is called from
#: ``SkillBrokerEngine.__init__`` so back-to-back runs in one process (a seed
#: sweep in a single interpreter) do not inherit the previous run's ids.
_UNCATEGORISED_RULE_IDS: set = set()
_UNCATEGORISED_TOTAL = 0

#: The tally is read-modify-written from ``get_rule_breakdown``, which runs
#: inside the audit trace build — and that runs under ``ThreadPoolExecutor``
#: whenever ``workers > 1``. A bare ``+=`` on a module global is the same
#: lost-update class the F6 fix closed in ``audit.py`` (the summary counters
#: mutated outside the writer's lock), so the update is held under a lock.
_UNCATEGORISED_LOCK = threading.Lock()


def _rule_identity(metadata: Dict[str, Any], validator_name: str) -> str:
    """The most specific name available for an uncounted rule."""
    for key in ("rule_id", "rule"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return str(validator_name or "").strip() or "(unnamed)"


def note_uncategorised_rules(count: int, rule_ids) -> None:
    """Record rules that reached no breakdown bucket. Never raises.

    Held under ``_UNCATEGORISED_LOCK``: the caller runs per audit row, and audit
    rows are built concurrently when a run sets ``workers > 1``. Without the
    lock two threads read the same total and both write back the same +1, so the
    reported number drifts BELOW the truth — an undercount in the one field that
    exists to say "the buckets are lying to you".
    """
    global _UNCATEGORISED_TOTAL
    with _UNCATEGORISED_LOCK:
        _UNCATEGORISED_TOTAL += int(count)
        _UNCATEGORISED_RULE_IDS.update(rule_ids)


def get_uncategorised_rules() -> Dict[str, Any]:
    """Process-wide uncategorised-rule tally, for ``run_integrity.json``.

    Returns ``rules_uncategorised_total`` (how many validator results were not
    counted into any of the five buckets) and ``rules_uncategorised_ids`` (which
    rules they were). A non-zero total is the honest reading of an all-zero
    ``rules_*_hit`` row: the rules fired, and the breakdown could not name their
    category — not that nothing happened.

    Populated only on runs with ``audit.corrected_status_columns`` ON. With the
    flag OFF the total is 0 — not because nothing was uncategorised, but because
    with no inference running EVERYTHING is, which the known-limitation table in
    ``docs/AUDIT_SCHEMA.md`` already states once for all such runs.
    """
    with _UNCATEGORISED_LOCK:
        return {
            "rules_uncategorised_total": _UNCATEGORISED_TOTAL,
            "rules_uncategorised_ids": sorted(_UNCATEGORISED_RULE_IDS),
        }


def reset_uncategorised_rules() -> None:
    """Clear the tally.

    Called by ``SkillBrokerEngine.__init__`` (so a second run in the same
    interpreter starts from zero rather than inheriting the first run's ids)
    and by tests.
    """
    global _UNCATEGORISED_TOTAL
    with _UNCATEGORISED_LOCK:
        _UNCATEGORISED_TOTAL = 0
        _UNCATEGORISED_RULE_IDS.clear()


def _infer_category(metadata: Dict[str, Any], validator_name: str) -> str:
    """Best-effort category for a result whose producer set no ``category``.

    Returns "" when nothing matches — an uncategorised result is NOT counted
    into an arbitrary bucket. ``AgentValidator:format`` (a schema breach) and
    the flood identity/precondition rules land here on purpose: neither is one
    of the five governance categories, and guessing a bucket for them is how
    the number stops meaning anything.
    """
    if metadata.get("exception_used") is True:
        return ""
    for text in (
        str(metadata.get("tier", "")),
        str(validator_name or ""),
        str(metadata.get("rule", "")),
        str(metadata.get("rule_id", "")),
    ):
        lowered = text.lower()
        if not lowered:
            continue
        for bucket in _BREAKDOWN_CATEGORIES:
            if bucket in lowered:
                return bucket
        for alias, bucket in _CATEGORY_ALIASES:
            if alias in lowered:
                return bucket
    return ""


def get_rule_breakdown(
    results: List[ValidationResult],
    *,
    allow_metadata_fallback: bool = False,
) -> Dict[str, int]:
    """Get rule hit counts by category for audit logging.

    ``metadata["category"]`` is set by ``BaseValidator`` subclasses
    (PersonalValidator / SocialValidator / ...), which the DEFAULT production
    path never reaches: production wires a single ``AgentValidator``, whose
    result metadata carries ``level`` / ``tier`` / ``rule`` / ``rule_id`` /
    ``rules_hit`` and no ``category`` at all. So under the default config the
    lookup below matches nothing and every ``rules_*_hit`` column is
    structurally zero, however many rules fired.

    ``allow_metadata_fallback=True`` (reached only from a run with
    ``global_config.audit.corrected_status_columns`` ON) INFERS the category
    from ``tier`` / validator name / rule id when ``category`` is absent. It is
    an inference, not a declaration: only categories a producer's tier labels
    can express will ever populate, and rules whose category cannot be named —
    identity / precondition rules among them — are counted as uncategorised
    (see ``get_uncategorised_rules``) rather than filed under a plausible
    bucket. An explicit ``category`` always wins, so validators that set it keep
    their exact previous behaviour and flag-OFF runs are untouched.

    The returned dict is the FIVE breakdown buckets and nothing else: its keys
    become ``rules_*_hit`` CSV columns, so an extra key here would add a column.
    """
    breakdown = {name: 0 for name in _BREAKDOWN_CATEGORIES}
    uncounted: List[str] = []

    for result in results:
        # S1: read ``result.metadata`` directly, as before PR-3. The
        # ``getattr(..., None) or {}`` form was the one behaviour change on the
        # flag-OFF path in this PR; a producer that emits a metadata-less
        # result should raise into _safe_rule_breakdown's warning, not be
        # silently absorbed.
        metadata = result.metadata
        if metadata.get("exception_used") is True:
            continue
        category = metadata.get("category", "")
        if category not in breakdown and allow_metadata_fallback:
            category = _infer_category(
                metadata, getattr(result, "validator_name", "")
            )
        if category in breakdown:
            breakdown[category] += 1
        elif allow_metadata_fallback:
            # C1: tallied ONLY on the inference path. With the fallback OFF
            # every AgentValidator result lands here by construction — that is
            # the documented structural-zero defect, not a finding about this
            # run — so counting it there filled `rules_uncategorised_*` with a
            # number that was 100% of the results on every flag-OFF run and
            # meant nothing. Here it answers a real question: the inference ran
            # and still could not name these rules' category.
            uncounted.append(
                _rule_identity(metadata, getattr(result, "validator_name", ""))
            )

    if uncounted:
        note_uncategorised_rules(len(uncounted), uncounted)

    return breakdown
