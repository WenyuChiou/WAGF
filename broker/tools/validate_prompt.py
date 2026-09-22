"""Static validator for agent prompt templates vs YAML config (Phase 6C-v4 G3).

Catches the 6 BLOCKERs surfaced by the vaccination_demo PoC (see
``.ai/vaccination_poc_findings_2026-05-10.md``) at config-time instead of
runtime. Examples:

* Prompt placeholder ``{response_format}`` referenced but YAML has no
  ``shared.response_format.fields`` block.
* Inline JSON example in the prompt uses key ``susceptibility_appraisal``
  but ``response_format.fields`` declares ``susceptibility_assessment``.
* ``response_format.fields[*].construct`` declared but ``parsing.constructs``
  missing the matching entry — parser cannot extract appraisal labels.
* ``actions:`` block missing — parser's ``get_valid_actions`` returns ``[]``
  and the LLM's skill choice is silently rejected.
* A governance profile declares thinking/identity rules constraining only a
  subset of available skills — the agent may converge on the unconstrained
  subset while governance silently looks effective elsewhere (harness-
  engineering flaw 5 — Requisite Variety). Warn when per-profile skill
  coverage is below 80%.

Usage::

    python -m broker.tools.validate_prompt \\
        examples/vaccination_demo/config/agent_types.yaml \\
        --agent-type individual

The CLI exits 0 if no issues, 1 if any ERROR-level issue, 2 if only WARN
issues are present. Issues are printed in ``severity: file:line message``
order so editors can navigate them.

Reference:
- ``docs/guides/HOW_TO_ADD_A_NEW_DOMAIN.md`` — full schema reference
- ``broker/components/context/builder.py:SafeFormatter`` — runtime behavior
  this CLI tries to anticipate

Added: 2026-05-10.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Phase 6R-B-3 (audit cluster E #16): the registry lookup happens at
# validate-time to union the CLI's base placeholder allowlist with
# domain-specific extensions. Module-level import because
# ``broker.domains.registry`` is a first-party broker module — if it
# ever can't be imported, the CLI was broken at startup, not here.
from broker.domains.registry import DomainPackRegistry

# Reviewer drift note (round 4, 2026-09): import the SAME tuple the
# runtime guard uses (broker/core/_skill_filtering.py) instead of
# retyping ("choice", "secondary_choice") here — a future third numeric
# field type would otherwise need remembering to update BOTH places.
from broker.core._skill_filtering import _NUMERIC_CHOICE_FIELD_TYPES


# ---------------------------------------------------------------------------
# Known broker-filled placeholders (auto-injected by TieredContextBuilder
# at runtime — see broker/components/context/tiered.py:format_prompt).
# Keeping this list current is a maintenance burden but the only way to
# distinguish "user-domain placeholder" (which YAML should declare) from
# "broker placeholder" (which is always filled). When adding a new
# template_vars[key] = ... in tiered.py, append the key here.
# ---------------------------------------------------------------------------
BROKER_FILLED_PLACEHOLDERS: Set[str] = {
    # Identity / system
    "system_prompt",
    "agent_id",
    "agent_name",
    "agent_type",
    "narrative_persona",
    "step",
    "year",
    # Memory / context blocks
    "memory",
    "relevant_memories",
    "personal_section",
    "local_section",
    "global_section",
    "institutional_section",
    "priority_section",
    "state",
    "perception",
    "objectives",
    "skills",
    "skills_text",
    # Options / choices
    "options_text",
    "valid_choices_text",
    "response_format",
    "rating_scale",
    # Social
    "social_gossip",
    "neighbor_action_summary",
    "global_news",
    # Phase 6R-B-3 (2026-05-26): the 3 water-domain placeholder names
    # (``insurance_cost_text`` / ``mg_barrier_text`` /
    # ``renewal_fatigue_text``) that previously lived here have moved to
    # ``FloodDomainPack.prompt_placeholder_extensions()``. The CLI
    # unions this base set with the registered DomainPack's extensions
    # at validate-time (see ``_resolve_domain_extensions`` below). This
    # closes the asymmetric coverage flagged by Phase 6Q-K-3 (Layer 3
    # audit finding #16).
}


# ---------------------------------------------------------------------------
# Domain-specific placeholder extensions (Phase 6R-B-3)
# ---------------------------------------------------------------------------

def _resolve_domain_extensions(cfg: Dict[str, Any]) -> Set[str]:
    """Return the placeholder extensions for the YAML's declared domain.

    Reads ``global_config.governance.domain`` from the agent-types YAML
    (e.g. ``"flood"``, ``"traffic"``, ``"irrigation"``). Looks the name
    up in :class:`DomainPackRegistry`; if registered, returns
    ``pack.prompt_placeholder_extensions()``. If absent (e.g. the
    relevant example package wasn't imported, or the YAML has no
    ``domain:`` field), returns ``set()`` — flood YAMLs will get a
    spurious WARN for the 3 water names UNLESS the user imports
    ``examples.governed_flood`` before invoking the CLI.

    Auto-importing every example package would couple the validator
    to the example tree (and bloat startup). Document the import
    convention instead: callers wanting flood-extension coverage
    invoke ``python -m examples.governed_flood`` first (which has
    the same registration side-effect), OR run the CLI from a
    Python module that has already imported the relevant example.
    """
    domain = (
        cfg.get("global_config", {})
        .get("governance", {})
        .get("domain")
    )
    if not domain:
        return set()
    pack = DomainPackRegistry.get(domain)
    if pack is None:
        # Pack not registered — likely the relevant example package
        # wasn't imported. Return empty set; the WARN that fires is
        # the correct behaviour ("you reference {insurance_cost_text}
        # but didn't import the FloodDomainPack").
        return set()
    try:
        ext = pack.prompt_placeholder_extensions()
    except Exception:
        # Defensive: a broken pack must not crash the validator.
        # Most likely real failures are AttributeError (pack missing
        # the method) and TypeError (method returns a non-iterable).
        # Phase 6Q-D-4 graceful-degradation pattern.
        return set()
    return set(ext) if ext else set()


@dataclass
class Issue:
    severity: str  # "ERROR" or "WARN"
    location: str  # short location hint (file, "yaml: <agent_type>", etc.)
    message: str

    def format(self) -> str:
        return f"{self.severity:5} {self.location}: {self.message}"


# ---------------------------------------------------------------------------
# Canonical global_config key registry (2026-06-09 architecture review P0-4)
# ---------------------------------------------------------------------------
# THE canonical list of recognized ``global_config`` keys. Every feature flag
# in this repo is read via ``dict.get(key, <default-OFF>)``, so a typo'd key
# (e.g. ``dispatch_domain_physcial``) silently resolves to feature-OFF with
# zero warnings — the worst failure class for a default-OFF flag system.
# This registry + ``check_global_config_keys`` is the config-time net.
#
# When ADDING a new global_config consumer anywhere in broker/, add its key
# here in the same commit. Keys ending in ``_system`` are domain blobs
# (vaccination_system / water_system convention) and are exempt.

KNOWN_GLOBAL_CONFIG_KEYS: Set[str] = {
    "llm",          # LLM sampling config (model, num_ctx, num_predict, ...)
    "memory",       # memory-engine tuning
    "reflection",   # reflection cadence/questions
    "governance",   # see KNOWN_GOVERNANCE_KEYS
    "social_feeds", # see KNOWN_SOCIAL_FEEDS_KEYS (two-layer flag, Phase 6T-E.B)
    "coupling",     # see KNOWN_COUPLING_KEYS (two-layer flag, Phase 6V)
    "audit",        # see KNOWN_AUDIT_KEYS (opt-in column flags, all default OFF)
    "parsing",      # see KNOWN_PARSING_KEYS (PR-4 hardened-parsing flag, default OFF)
    "validators",   # see KNOWN_VALIDATORS_KEYS (PR-6 label-resolution flag, default OFF)
}

KNOWN_GOVERNANCE_KEYS: Set[str] = {
    "max_retries",               # agent_config.get_governance_max_retries
    "max_reports_per_retry",     # agent_config.get_governance_max_reports
    "domain",                    # ValidatorRegistry / DomainPack resolution
    "dispatch_domain_physical",  # opt-in engine PHYSICAL dispatch (d1cf7c3)
    "shuffle_options",           # broker/core/_skill_filtering.py positional-bias mitigation
    "retrieval",                 # agent_config.get_retrieval_config
    "drift",                     # agent_config.get_drift_config
    "population",                # agent_config.get_population_governance_config
    # "policy_event_tiers" removed org-4 cleanup 2026-09 — the
    # DomainPack.policy_event_tiers() hook and its sole consumer
    # (AgentTypeConfig.get_policy_event_tiers_config) are both gone;
    # grep-confirmed no repo YAML sets this key, so dropping it from
    # the allowlist introduces no new "unknown key" WARN.
    # NOTE: governance.memory (bridge-importance / resolution_importance_policy
    # sub-block) is DISTINCT from the top-level global_config.memory block —
    # both are intentionally listed, one per level.
    "memory",                    # agent_config.get_bridge_importance_config
    # P0-1c/P0-1d arm-sweep keys. These were consumed before they were registered
    # here, so every config using them tripped a spurious "unknown key" WARN —
    # exactly the noise that trains operators to ignore this check.
    "advise",                    # agent_config.get_governance_advise
    "intervention_framing",      # agent_config.get_governance_intervention_framing
    "require_profile",           # agent_config.get_governance_require_profile
    "on_retry_exhausted",        # agent_config.get_governance_on_retry_exhausted
    # PR-6 soft-rule channel. Note it is `advise_mode`, NOT `advise` — the two
    # are different features (`advise` demotes ERROR rules for an experiment
    # arm; `advise_mode` governs rules already authored as WARNING) and writing
    # one where you meant the other is the mistake this entry exists to name.
    "advise_mode",               # agent_config.get_governance_advise_mode
    # Red-team objection 3 ablation (full | placebo, default full). Governs
    # ONLY the BLOCKING governance retry loop's LLM-facing text — distinct
    # from `advise` (demotes ERROR rules) and `advise_mode` (the WARNING
    # channel) above; writing one where you meant this one produces a run
    # with the wrong knob silently at its default.
    "retry_feedback_mode",       # agent_config.get_governance_retry_feedback_mode
}

KNOWN_SOCIAL_FEEDS_KEYS: Set[str] = {
    "enable",           # broker/components/social/feed_flag.py
    "top_k",            # run_unified_experiment social-feed knobs
    "half_life_years",
}

KNOWN_COUPLING_KEYS: Set[str] = {
    "enable",           # broker/coupling/flag.py
    "context_contract", # agent_config.get_coupling_context_contract (PR-9, F1)
}

# Every opt-in audit column flag, all default-OFF and all read through
# ``AgentTypeConfig``. Registered here because these flags fail CLOSED: a
# typo'd key resolves to its default, the run produces the UNCORRECTED columns,
# and nothing in the artifacts says the flag was ever requested — you find out
# when the analysis is already written. This check is the only config-time net.
KNOWN_AUDIT_KEYS: Set[str] = {
    "corrected_status_columns",  # agent_config.get_audit_corrected_status_columns (PR-3)
    "executed_skill_columns",    # agent_config.get_audit_executed_columns (F3)
    "initial_proposal_columns",  # agent_config.get_audit_initial_proposal_columns (P0-1a)
    "advise_columns",            # agent_config.get_audit_advise_columns (P0-1c)
    "param_columns",             # agent_config.get_audit_param_columns (6W-B6)
    "grounding_columns",         # agent_config.get_audit_grounding_columns (PR-6)
    "decider_columns",           # agent_config.get_audit_decider_columns (PR-8)
}

# PR-4: the single opt-in parsing-hardening flag, default-OFF, same fail-open
# rationale as KNOWN_AUDIT_KEYS — a typo'd key resolves to feature-OFF (the
# naked-digit layer keeps firing) with zero warnings anywhere else.
KNOWN_PARSING_KEYS: Set[str] = {
    "strict_layers",  # agent_config.get_parsing_strict_layers (PR-4)
}

# PR-6: validator-behaviour flags, default-OFF, same fail-closed rationale as
# KNOWN_AUDIT_KEYS — a typo'd key resolves to feature-OFF, the run keeps the
# hardcoded five-level label alphabet, and every rule written against another
# framework's labels silently never fires with nothing anywhere saying so.
KNOWN_VALIDATORS_KEYS: Set[str] = {
    "framework_aware_labels",  # agent_config.get_validators_framework_aware_labels
}


def _check_strict_layers_value(parsing_block: Dict[str, Any], loc: str) -> List[Issue]:
    """PR-4 (D8): ``strict_layers`` must be a real YAML bool.

    ``resolve_strict_layers_flag`` requires ``isinstance(value, bool)`` and
    resolves anything else OFF. That is the safe direction for byte identity
    and the wrong one for whoever wrote the key, and the quoted string
    ``"false"`` is the trap that costs the most: it is TRUTHY in Python, so a
    reader skimming the YAML reads it as off while a naive consumer would read
    it as on, and the resolver's answer (off, with one log line) matches
    neither reading reliably. Fail it here, at config time, where the fix is
    one character.
    """
    issues: List[Issue] = []
    if not isinstance(parsing_block, dict) or "strict_layers" not in parsing_block:
        return issues
    value = parsing_block["strict_layers"]
    if isinstance(value, bool):
        return issues
    hint = ""
    if isinstance(value, str) and value.strip().lower() in ("true", "false", "yes", "no", "on", "off"):
        # Lower-cased on purpose: the hint tells the reader what to type in
        # YAML, and Python's `True`/`False` repr is not valid YAML boolean
        # syntax — a hint that has to be translated before use is a hint that
        # gets copied wrong.
        meant = value.strip().lower() in ("true", "yes", "on")
        hint = (
            f" You almost certainly meant the bool: write "
            f"`strict_layers: {str(meant).lower()}` without quotes."
        )
    issues.append(Issue(
        "WARN", loc,
        f"strict_layers must be a bool, got {type(value).__name__} ({value!r}) — "
        f"the flag resolver rejects any non-bool and reads the feature OFF, so "
        f"the hardened parse layers will NOT run.{hint}",
    ))
    return issues


def _check_per_agent_strict_layers(cfg: Dict[str, Any]) -> List[Issue]:
    """PR-4 (D8): ``strict_layers`` under a per-agent ``parsing:`` block does nothing.

    ``strict_layers`` is read from ``global_config.parsing`` and nowhere else
    (``AgentTypeConfig.get_parsing_strict_layers``), while everything else a
    user writes under ``parsing:`` — ``strict_mode``, ``default_skill``,
    ``decision_keywords``, ``constructs`` — IS per-agent-type. Putting it
    beside them is the obvious mistake, and it is silent: the key is accepted,
    ignored, and the run behaves exactly as if the flag were never set.
    """
    message = (
        "'strict_layers' is read ONLY from global_config.parsing and is "
        "silently ignored here — this run's parse layers are NOT hardened. "
        "Move it to `global_config: {parsing: {strict_layers: true}}`. "
        "(Per-agent-type `parsing.strict_mode` is a different, genuinely "
        "per-agent key and stays where it is.)"
    )
    issues: List[Issue] = []
    for atype, block in cfg.items():
        if str(atype) in ("global_config", "shared", "governance") or not isinstance(block, dict):
            continue
        # A TOP-LEVEL `parsing:` block is the same mistake one level up, and
        # is just as silent — nothing reads it either.
        if str(atype) == "parsing":
            if "strict_layers" in block:
                issues.append(Issue("WARN", "yaml: parsing", message))
            continue
        parsing = block.get("parsing")
        if isinstance(parsing, dict) and "strict_layers" in parsing:
            issues.append(Issue("WARN", f"yaml: {atype}.parsing", message))
    return issues


def check_global_config_keys(cfg: Dict[str, Any]) -> List[Issue]:
    """Validate ``global_config`` against the canonical key registry.

    WARN on unrecognized keys (a typo'd flag key silently resolves to its
    default — usually feature-OFF — so the warning is the only net).
    ERROR when ``governance.dispatch_domain_physical`` is truthy but
    ``governance.domain`` is absent: the accessor returns None in that case
    and the explicitly-requested dispatch silently no-ops.
    """
    issues: List[Issue] = []
    # PR-4 (D8): runs BEFORE the global_config early-return on purpose — a YAML
    # that puts strict_layers under an agent type and has no global_config block
    # at all is the exact config this warning exists for.
    issues.extend(_check_per_agent_strict_layers(cfg))
    gc = cfg.get("global_config")
    if not isinstance(gc, dict):
        return issues

    loc = "yaml: global_config"
    for key in gc:
        if key in KNOWN_GLOBAL_CONFIG_KEYS or str(key).endswith("_system"):
            continue
        issues.append(Issue(
            "WARN", loc,
            f"unrecognized key '{key}' — no broker code reads it (typo'd "
            f"feature flags silently resolve default-OFF). Known keys: "
            f"{sorted(KNOWN_GLOBAL_CONFIG_KEYS)}; '<domain>_system' blobs are exempt.",
        ))

    def _check_block(name: str, known: Set[str]) -> Dict[str, Any]:
        block = gc.get(name)
        if block is not None and not isinstance(block, dict):
            # governance: true (scalar) would silently skip BOTH the sub-key
            # checks and the dispatch-without-domain ERROR — surface it.
            issues.append(Issue(
                "WARN", f"{loc}.{name}",
                f"expected a mapping, got {type(block).__name__} — the block "
                f"is ignored and none of its checks run.",
            ))
            return {}
        if not isinstance(block, dict):
            return {}
        for key in block:
            if key not in known:
                issues.append(Issue(
                    "WARN", f"{loc}.{name}",
                    f"unrecognized key '{key}' — known {name} keys: {sorted(known)}.",
                ))
        return block

    gov = _check_block("governance", KNOWN_GOVERNANCE_KEYS)
    _check_block("social_feeds", KNOWN_SOCIAL_FEEDS_KEYS)
    _check_block("coupling", KNOWN_COUPLING_KEYS)
    _check_block("audit", KNOWN_AUDIT_KEYS)
    _check_block("validators", KNOWN_VALIDATORS_KEYS)
    parsing_block = _check_block("parsing", KNOWN_PARSING_KEYS)
    issues.extend(_check_strict_layers_value(parsing_block, f"{loc}.parsing"))

    # PR-6: `advise_mode` must name a real mode. The config getter raises on a
    # bad value, but that happens at RUN time, after the operator has walked
    # away from a launched batch; catching it here costs one character to fix.
    if "advise_mode" in gov:
        _mode = str(gov.get("advise_mode")).strip().lower()
        if _mode not in ("off", "record", "feedback"):
            issues.append(Issue(
                "ERROR", f"{loc}.governance",
                f"advise_mode {gov.get('advise_mode')!r} is not one of "
                f"['feedback', 'off', 'record']. The soft-rule channel refuses "
                f"to start on an unknown mode rather than silently reading it off.",
            ))

    dispatch = gov.get("dispatch_domain_physical")
    if isinstance(dispatch, dict):
        # Mapping form ({agent_type: domain}, Wave 3 P1-2): self-contained —
        # governance.domain not required. Empty domain values are config bugs.
        for atype, dom in dispatch.items():
            if not (isinstance(dom, str) and dom.strip()):
                issues.append(Issue(
                    "ERROR", f"{loc}.governance",
                    f"dispatch_domain_physical mapping entry {atype!r} has an "
                    f"empty/non-string domain ({dom!r}) — the accessor raises on this.",
                ))
    elif dispatch and not gov.get("domain"):
        issues.append(Issue(
            "ERROR", f"{loc}.governance",
            "dispatch_domain_physical is set but 'domain' is absent — the "
            "dispatch accessor raises on this (an explicitly-requested "
            "PHYSICAL dispatch must never silently no-op). Add "
            "'domain: <your_domain>' next to the flag, or use the "
            "{agent_type: domain} mapping form.",
        ))
    return issues


# ---------------------------------------------------------------------------
# Rule-shape lint (G4, 2026-06-10 audit review — the 6N-E class killer)
# ---------------------------------------------------------------------------
# The thinking-rule loader (broker/utils/agent_config.py get_thinking_rules)
# consumes EXACTLY these keys; anything else loads silently and is IGNORED —
# the Phase 6N-E failure class (a rule the author believes in, evaluating
# never). Verified dead siblings found 2026-06-10: precondition (dropped by
# the loader), expected_values/levels (only when_above/when_true are read),
# state_field/state_fields/aggregation/threshold/trigger_phrases (CoherenceRule
# fields with no loader and no evaluator), string conditions.
_THINKING_RULE_CONSUMED_KEYS: Set[str] = {
    "id", "construct", "conditions", "when_above", "when_true",
    "blocked_skills", "level", "message",
    # PR-6: read by `resolve_rule_grounding` to stamp CoherenceRule.grounding,
    # which decides the `rules_world_grounded` / `rules_self_report` split.
    "grounding",
}
# Condition dicts: canonical short shape {construct, values}; the verbose
# 6N-E shape evaluates via the `field` fallback but `type`/`operator` are
# IGNORED (membership-in-values is the only semantic).
# `field` is consumed at EVALUATION time, not load time:
# broker/validators/agent/agent_validator.py:455
# (`cond.get("construct") or cond.get("field")`) — do not remove it from this
# set on a loader-only audit. NOTE these sets are thinking/coherence-rule
# specific; `identity_rules` has a DIFFERENT loader that reads `precondition`
# as live — extending this lint to identity_rules needs its own key set.
_CONDITION_CONSUMED_KEYS: Set[str] = {"construct", "values", "field"}

# PR-6: a WORLD condition consumes a DIFFERENT key set. `{variable, scope,
# operator, value|values}` are all live there
# (broker/utils/agent_config.py::world_condition_target,
# broker/validators/agent/agent_validator.py::_evaluate_world_condition), and
# `type` selects the verbose dataclass shape. Kept as a separate set rather than
# merged into the one above, because on a CONSTRUCT condition `operator` alone
# still has no semantics — that is the 6N-E finding this lint exists to report,
# and widening one set to accommodate the other would delete it.
_WORLD_CONDITION_CONSUMED_KEYS: Set[str] = {
    "variable", "scope", "operator", "value", "values", "type", "field",
}

# On a construct condition, `operator` + `value` TOGETHER select the numeric
# comparison branch (`if "operator" in cond and "value" in cond`), so the pair is
# live. `operator` on its own is not.
_CONSTRUCT_NUMERIC_KEYS: Set[str] = {"operator", "value"}


def _consumed_condition_keys(cond: Dict[str, Any]) -> Set[str]:
    """Which keys this particular condition shape actually consumes."""
    from broker.utils.agent_config import world_condition_target

    name, _scope = world_condition_target(cond)
    if name:
        return _WORLD_CONDITION_CONSUMED_KEYS
    if _CONSTRUCT_NUMERIC_KEYS <= set(cond):
        return _CONDITION_CONSUMED_KEYS | _CONSTRUCT_NUMERIC_KEYS
    return _CONDITION_CONSUMED_KEYS


def _iter_thinking_rule_blocks(cfg: Dict[str, Any]):
    """Yield ``(location, rules_list)`` for EVERY thinking-rule block in a config.

    Three shapes exist and all three are in production use:

    * ``<agent_type>.thinking_rules`` — the flat legacy form;
    * ``governance.<profile>.<agent_type>.thinking_rules`` — the top-level form;
    * ``<agent_type>.governance.<profile>.thinking_rules`` — the form BOTH
      shipped reference configs actually use, and the one
      :func:`check_rule_shapes` does not walk.

    Kept as one iterator so a new check cannot inherit that gap by copying the
    old walk.
    """
    for atype, block in (cfg or {}).items():
        if not isinstance(block, dict):
            continue
        if str(atype) == "governance":
            for profile, types in block.items():
                if not isinstance(types, dict):
                    continue
                for at, sub in types.items():
                    if isinstance(sub, dict):
                        yield (f"yaml: governance.{profile}.{at}.thinking_rules",
                               sub.get("thinking_rules"))
            continue
        if str(atype) == "global_config":
            continue
        yield (f"yaml: {atype}.thinking_rules", block.get("thinking_rules"))
        yield (f"yaml: {atype}.coherence_rules", block.get("coherence_rules"))
        gov = block.get("governance")
        if isinstance(gov, dict):
            for profile, sub in gov.items():
                if isinstance(sub, dict):
                    yield (f"yaml: {atype}.governance.{profile}.thinking_rules",
                           sub.get("thinking_rules"))


def _check_rule_table(
    atype: str, block: Dict[str, Any], spec, loc: str,
) -> List[Issue]:
    """PR-8 W5: a rule table's own shape, checked before the batch.

    Two BLOCKERs, neither visible until the run is finished.

    A table that will not parse at all — a bad ``scope:``, a rule with no
    ``action``, ``rule_based`` with no ``default_action`` — now raises at
    run start rather than mid-loop, but that is still one launch wasted.

    The second is the one nothing catches afterwards. When a proposal
    reports SOME constructs, ``_retry_loop`` requires every ``*_LABEL``
    in this agent type's ``parsing.constructs``, retries when one is
    missing, and a rule table answers the retry with the identical
    proposal — so the row exhausts its retries and lands ABORTED. Every
    row of that agent type. The CSV then holds an arm with the right
    ``decider`` column, a full row count, and no decisions in it.
    Reporting nothing at all is fine: the loop skips the check when a
    proposal's ``reasoning`` is empty.
    """
    issues: List[Issue] = []
    if spec.name not in ("rule_based", "hybrid"):
        return issues
    try:
        from broker.agents.deciders import build_rule_table
    except Exception:  # noqa: BLE001
        return issues
    try:
        table = build_rule_table(spec.params, where=f"{atype}.decider")
    except ValueError as exc:
        return [Issue("ERROR", loc, str(exc))]

    parsing = block.get("parsing")
    parsing = parsing if isinstance(parsing, dict) else {}
    constructs = parsing.get("constructs")
    constructs = constructs if isinstance(constructs, dict) else {}
    required = {k for k in constructs if "_LABEL" in str(k)}
    if not required:
        return issues
    shared_reasoning = spec.params.get("reasoning")
    shared_keys = set(shared_reasoning) if isinstance(shared_reasoning, dict) else set()
    for rule in table:
        declared = shared_keys | set(rule.reasoning)
        if not declared:
            continue  # reports nothing -> the retry check does not run
        missing = sorted(required - declared)
        if missing:
            issues.append(Issue(
                "ERROR", loc,
                f"rule '{rule.rule_id}' reports {sorted(declared)} but "
                f"'{atype}' requires {sorted(required)}. A PARTIAL report "
                f"makes the retry loop ask for {missing}; a rule table "
                f"answers the retry identically, so every row this rule "
                f"produces exhausts its retries and lands ABORTED. Declare "
                f"the missing label(s) here or in the decider's shared "
                f"`reasoning:`, or report none at all.",
            ))
    return issues


def check_decider_declarations(cfg: Dict[str, Any]) -> List[Issue]:
    """PR-8: every ``decider:`` must name a REGISTERED decider.

    Two failures, both silent without this check.

    An unregistered name is an ERROR. Nothing falls back to ``llm`` —
    ``DeciderRegistry.build`` raises — so the run dies at the first
    agent of that type, minutes into a batch, with a traceback rather
    than a config location. Catching it here costs one line to fix.

    ``decider:`` under a NON-AGENT top-level block (``global_config``,
    ``shared``, ``metadata``, ...) is a WARN, and it is the more
    dangerous of the two: it is read by nothing at all, the run starts
    fine, every agent silently uses the LLM default, and the resulting
    CSV is a correct all-LLM corpus wearing a mixed-population config's
    name. There is nothing in the artifacts to catch it afterwards.
    ``shared:`` is included (review C1) because it is the one people
    reach for — it is where the response format and the rating scale
    live, so it looks like the place a population-wide setting goes.

    A rule table's declared ``reasoning`` is checked too (review W5).
    A rule that reports SOME of an agent type's required ``*_LABEL``
    constructs and not all of them makes the retry loop ask for the
    missing ones — and a rule table answers the retry with the same
    proposal, so the row loops to ABORTED. Every row. Empty reasoning is
    fine: the loop skips the check entirely when a proposal reports no
    constructs at all.

    The registry is consulted AFTER the domain's own deciders are
    registered (via ``global_config.governance.domain``), so a domain
    that ships its own decider validates without the operator having to
    import anything by hand.
    """
    issues: List[Issue] = []
    try:
        from broker.agents.deciders import (
            DeciderRegistry, parse_decider_spec, register_domain_deciders,
        )
    except Exception as exc:  # noqa: BLE001 — never break the CLI over a lint
        return [Issue("WARN", "yaml", f"decider check skipped: {exc}")]

    from broker.utils.agent_config import NON_AGENT_TOP_LEVEL_KEYS

    gc = cfg.get("global_config")
    for reserved in sorted(NON_AGENT_TOP_LEVEL_KEYS):
        block = cfg.get(reserved)
        if isinstance(block, dict) and "decider" in block:
            issues.append(Issue(
                "WARN", f"yaml: {reserved}",
                "'decider' is a PER-AGENT-TYPE key and is read by nothing "
                f"under '{reserved}' — the run will start and every agent "
                "will use the default 'llm', producing an all-LLM corpus "
                "from a config that reads as mixed. Move it into the agent "
                "type block(s) it was meant for.",
            ))

    domain = None
    if isinstance(gc, dict):
        domain = (gc.get("governance") or {}).get("domain")
    # "Was any DomainPack loaded at all?" A CLI invocation that never
    # imported the example package has none, and every domain decider
    # would then look unregistered — see _resolve_domain_extensions for
    # the same import convention.
    pack_available = False
    try:
        from broker.domains.registry import DomainPackRegistry
        if domain:
            pack_available = DomainPackRegistry.get(domain) is not None
        else:
            pack_available = bool(DomainPackRegistry.domains())
    except Exception:  # noqa: BLE001
        pack_available = False
    try:
        register_domain_deciders(domain)
    except Exception as exc:  # noqa: BLE001
        pack_available = False
        issues.append(Issue(
            "WARN", "yaml: global_config.governance.domain",
            f"could not load domain '{domain}' deciders ({exc}).",
        ))

    for atype, block in cfg.items():
        if not isinstance(block, dict) or "decider" not in block:
            continue
        if str(atype) in NON_AGENT_TOP_LEVEL_KEYS:
            continue
        loc = f"yaml: {atype}.decider"
        try:
            spec = parse_decider_spec(block["decider"], where=str(atype))
        except ValueError as exc:
            issues.append(Issue("ERROR", loc, str(exc)))
            continue
        if DeciderRegistry.has(spec.name):
            issues.extend(_check_rule_table(str(atype), block, spec, loc))
            continue
        if not pack_available:
            # The pack import convention (see _resolve_domain_extensions)
            # means the CLI often runs without the domain's package
            # loaded. Calling a name it may well ship an ERROR would
            # train operators to ignore this check.
            issues.append(Issue(
                "WARN", loc,
                f"'{spec.name}' is not registered here, but no DomainPack "
                f"is imported in this process, so a decider a domain "
                f"ships would look exactly like this. Re-run after "
                f"`python -m examples.<your_example>` to check it for "
                f"real. Built-ins: {DeciderRegistry.names()}.",
            ))
            continue
        issues.append(Issue(
            "ERROR", loc,
            f"'{spec.name}' is not a registered decider — the run will "
            f"raise at this agent type's first decision. Registered: "
            f"{DeciderRegistry.names()}. A domain ships its own through "
            f"the DomainPack hook `decider_factories()`; if this is a "
            f"domain decider, check `global_config.governance.domain`.",
        ))
    return issues


def check_world_condition_scopes(cfg: Dict[str, Any]) -> List[Issue]:
    """W5: ERROR on a ``scope:`` the resolver does not recognise.

    An unrecognised scope is COERCED to ``auto`` at load time, and ``auto``
    searches env first — so ``scope: environment`` (a plausible typo) appears to
    work, and keeps appearing to work until the agent's own state carries the
    same variable name. Then the rule reads the wrong plane, with nothing in the
    run saying the scope was never honoured. The coercion warns once at runtime;
    this catches it before a batch is launched, which is when it is still one
    character to fix.
    """
    from broker.utils.agent_config import WORLD_CONDITION_SCOPES

    issues: List[Issue] = []
    for loc, rules in _iter_thinking_rule_blocks(cfg):
        if not isinstance(rules, list):
            continue
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            rid = rule.get("id", rule.get("construct", "?"))
            conds = rule.get("conditions")
            if not isinstance(conds, list):
                continue
            for cond in conds:
                if not isinstance(cond, dict) or "scope" not in cond:
                    continue
                scope = str(cond.get("scope") or "").strip().lower()
                if scope in WORLD_CONDITION_SCOPES:
                    continue
                issues.append(Issue(
                    "ERROR", loc,
                    f"rule {rid!r}: condition scope {cond.get('scope')!r} is not "
                    f"one of {sorted(WORLD_CONDITION_SCOPES)}. It is COERCED to "
                    f"'auto' at load time, which searches env then agent state "
                    f"then the flattened context — so the rule keeps firing, "
                    f"against whichever plane wins, not the one you named.",
                ))
    return issues


def check_rule_shapes(cfg: Dict[str, Any]) -> List[Issue]:
    """ERROR on accepted-but-ignored rule keys (silently-dead YAML).

    Scans ``thinking_rules`` / ``coherence_rules`` in agent-type blocks AND
    the top-level ``governance.<profile>.<agent_type>.thinking_rules`` form.
    Zero in-tree configs carry dead keys (scanned 2026-06-10), so ERROR
    severity is safe for the frozen regression net.
    """
    issues: List[Issue] = []

    def _lint_rules(rules: Any, loc: str) -> None:
        if not isinstance(rules, list):
            return
        for rule in rules:
            if not isinstance(rule, dict):
                issues.append(Issue(
                    "ERROR", loc,
                    f"rule entry is {type(rule).__name__}, not a mapping — "
                    f"string/scalar rules silently never evaluate.",
                ))
                continue
            rid = rule.get("id", rule.get("construct", "?"))
            extra = set(rule) - _THINKING_RULE_CONSUMED_KEYS
            if extra:
                issues.append(Issue(
                    "ERROR", loc,
                    f"rule {rid!r} carries key(s) the loader IGNORES "
                    f"{sorted(extra)} — the rule will not do what those keys "
                    f"promise (6N-E class). Consumed keys: "
                    f"{sorted(_THINKING_RULE_CONSUMED_KEYS)}.",
                ))
            conds = rule.get("conditions")
            if isinstance(conds, str):
                issues.append(Issue(
                    "ERROR", loc,
                    f"rule {rid!r}: conditions is a STRING — string conditions "
                    f"silently never trigger. Use a list of "
                    f"{{construct: X, values: [...]}} mappings.",
                ))
            elif isinstance(conds, list):
                for c in conds:
                    if not isinstance(c, dict):
                        continue
                    ce = set(c) - _consumed_condition_keys(c)
                    if ce:
                        issues.append(Issue(
                            "ERROR", loc,
                            f"rule {rid!r}: condition carries ignored key(s) "
                            f"{sorted(ce)} — e.g. 'operator' has NO semantics "
                            f"(matching is always membership-in-values). Use "
                            f"the canonical short shape "
                            f"{{construct: X, values: [...]}}.",
                        ))

    for atype, block in cfg.items():
        if not isinstance(block, dict):
            continue
        if str(atype) == "governance":
            # top-level governance.<profile>.<agent_type>.thinking_rules form
            for profile, types in block.items():
                if not isinstance(types, dict):
                    continue
                for at, sub in types.items():
                    if isinstance(sub, dict):
                        _lint_rules(sub.get("thinking_rules"),
                                    f"yaml: governance.{profile}.{at}.thinking_rules")
            continue
        _lint_rules(block.get("thinking_rules"), f"yaml: {atype}.thinking_rules")
        _lint_rules(block.get("coherence_rules"), f"yaml: {atype}.coherence_rules")

    return issues


# ---------------------------------------------------------------------------
# Placeholder extraction
# ---------------------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][\w]*)\}")
_DOUBLE_BRACE_RE = re.compile(r"\{\{[^{}]+\}\}")


def extract_placeholders(template: str) -> Set[str]:
    """Return the set of single-brace ``{placeholder}`` names in the template.

    Skips escaped double braces ``{{...}}`` (literal braces in inline JSON).
    """
    # Mask double-brace blocks first so they don't pollute extraction.
    masked = _DOUBLE_BRACE_RE.sub("", template)
    return set(_PLACEHOLDER_RE.findall(masked))


def collect_template_vars(value: Any) -> Set[str]:
    """Return YAML-declared lifecycle/context template variable names.

    Domains can declare ``template_vars`` as either a list of names or a
    mapping of name -> description/default. The validator treats those names as
    intentionally supplied by lifecycle hooks, context providers, or agent
    state rather than response_format fields.
    """
    if isinstance(value, list):
        return {v for v in value if isinstance(v, str)}
    if isinstance(value, dict):
        return {k for k in value if isinstance(k, str)}
    return set()


# ---------------------------------------------------------------------------
# Inline JSON key extraction (best-effort)
# ---------------------------------------------------------------------------

def extract_inline_json_keys(template: str) -> Set[str]:
    """Pull TOP-LEVEL JSON-object keys from inline JSON examples in the prompt.

    These are the keys an LLM is shown as the response shape; they MUST
    match ``response_format.fields[].key`` from the YAML or the parser will
    reject the response.

    Python ``str.format`` requires literal braces escaped as ``{{`` / ``}}``,
    so the prompt's JSON example is double-braced. We:
        1. Remove single-brace ``{placeholder}`` substitutions so they don't
           interfere with brace-depth tracking.
        2. Convert ``{{`` / ``}}`` → ``{`` / ``}`` (what the LLM actually sees
           after format substitution).
        3. Walk the result tracking JSON object depth, collecting only keys
           at depth 1 (= the outer response object), skipping nested
           ``{"label": ..., "reason": ...}`` sub-objects whose keys are
           intentionally not declared in YAML.
    """
    # 1. Strip {placeholder} substitutions
    masked = _PLACEHOLDER_RE.sub("", template)
    # 2. Render literal-brace escapes
    literal = masked.replace("{{", "{").replace("}}", "}")
    keys: Set[str] = set()
    depth = 0
    i = 0
    n = len(literal)
    while i < n:
        ch = literal[i]
        if ch == "{":
            depth += 1
            i += 1
            continue
        if ch == "}":
            depth -= 1
            i += 1
            continue
        if ch == '"' and depth == 1:
            end = literal.find('"', i + 1)
            if end < 0:
                break
            key_candidate = literal[i + 1:end]
            # Look ahead for ":" (with optional whitespace) — this
            # distinguishes a JSON key from a quoted value.
            j = end + 1
            while j < n and literal[j] in " \t\n":
                j += 1
            if j < n and literal[j] == ":" and re.fullmatch(
                r"[a-zA-Z_]\w*", key_candidate
            ):
                keys.add(key_candidate)
            i = end + 1
            continue
        i += 1
    return keys


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------

def load_yaml(path: Path) -> Dict[str, Any]:
    import yaml

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def resolve_prompt_path(yaml_path: Path, template_ref: str) -> Path:
    """Resolve a prompt_template_file reference.

    Two conventions coexist in the codebase:
      * vaccination_demo / new domains: path relative to YAML directory,
        e.g. ``prompts/individual.txt`` in
        ``examples/vaccination_demo/config/agent_types.yaml``.
      * irrigation / older flood: path relative to the EXAMPLE root, e.g.
        ``config/prompts/irrigation_farmer.txt`` in
        ``examples/irrigation_abm/config/agent_types.yaml`` (resolves to
        ``examples/irrigation_abm/config/prompts/...`` after walking up).

    We try yaml_dir first, then walk up the parent directory tree (max 4
    levels) looking for a match. Returns the first existing match, or the
    yaml_dir candidate if no match (so the caller can report the expected
    location).
    """
    template_path = Path(template_ref)
    if template_path.is_absolute():
        return template_path

    primary = (yaml_path.parent / template_ref).resolve()
    if primary.exists():
        return primary

    current = yaml_path.parent
    for _ in range(4):
        current = current.parent
        candidate = (current / template_ref).resolve()
        if candidate.exists():
            return candidate

    return primary


# ---------------------------------------------------------------------------
# Skill->rule coverage (Phase 6G flaw 5 — Requisite Variety)
# ---------------------------------------------------------------------------

COVERAGE_THRESHOLD = 0.80


def check_skill_rule_coverage(
    cfg: Dict[str, Any], agent_type: str
) -> List[Issue]:
    """Compute per-profile skill->rule coverage; warn on requisite-variety gaps.

    Closes harness-engineering flaw 5 (audit 2026-05-14): a DomainPack with
    N skills but rules constraining only M < N skills lets agents converge
    on the unconstrained subset while governance silently looks effective
    on the constrained subset. The check warns when an actively-deployed
    profile constrains fewer than ``COVERAGE_THRESHOLD`` (80%) of available
    skill ids via ``thinking_rules`` + ``identity_rules`` ``blocked_skills``
    lists. Profiles with zero rules (the disabled / no-governance baseline
    used as an ablation control) are intentionally skipped.

    Also flags ghost-skill references: ``blocked_skills`` entries pointing
    at skill ids absent from the actions list (typo / stale rule that will
    never fire at runtime).
    """
    issues: List[Issue] = []
    block = cfg.get(agent_type)
    if not isinstance(block, dict):
        return issues

    # Mirror the actions lookup in validate_agent_type so both top-level and
    # parsing.actions conventions are supported.
    actions = block.get("actions")
    if not actions:
        parsing_block = block.get("parsing", {})
        if isinstance(parsing_block, dict):
            actions = parsing_block.get("actions")
    if not isinstance(actions, list):
        return issues  # malformed actions already errored upstream

    skill_ids: Set[str] = set()
    for a in actions:
        if isinstance(a, dict) and isinstance(a.get("id"), str):
            skill_ids.add(a["id"])
    if not skill_ids:
        return issues

    governance = block.get("governance", {})
    if not isinstance(governance, dict):
        return issues

    for profile_name, profile in governance.items():
        if not isinstance(profile, dict):
            continue
        thinking = profile.get("thinking_rules") or []
        identity = profile.get("identity_rules") or []
        all_rules = (
            list(thinking) if isinstance(thinking, list) else []
        ) + (
            list(identity) if isinstance(identity, list) else []
        )
        if not all_rules:
            # Intentional disabled / baseline profile — skip coverage check
            continue

        constrained: Set[str] = set()
        for rule in all_rules:
            if not isinstance(rule, dict):
                continue
            blocked = rule.get("blocked_skills") or []
            if isinstance(blocked, list):
                for s in blocked:
                    if isinstance(s, str):
                        constrained.add(s)

        # Ghost-skill check: blocked_skills referencing ids not in actions
        ghost = sorted(constrained - skill_ids)
        if ghost:
            issues.append(Issue(
                "WARN",
                f"yaml: {agent_type}.governance.{profile_name}",
                f"rules reference skill id(s) not in actions list: {ghost}. "
                "Possible typo or stale rule — these blocks will never fire "
                "at runtime.",
            ))

        documented_unconstrained = profile.get("documented_unconstrained_skills") or []
        if not isinstance(documented_unconstrained, list):
            documented_unconstrained = []
        documented: Set[str] = {
            s for s in documented_unconstrained if isinstance(s, str)
        }
        documented_ghost = sorted(documented - skill_ids)
        if documented_ghost:
            issues.append(Issue(
                "WARN",
                f"yaml: {agent_type}.governance.{profile_name}",
                f"documented_unconstrained_skills reference skill id(s) "
                f"not in actions list: {documented_ghost}. Possible typo "
                "or stale documentation.",
            ))

        # Coverage check — skill_ids guaranteed non-empty by earlier guard
        enforceable_skill_ids = skill_ids - documented
        if not enforceable_skill_ids:
            continue
        covered = constrained & enforceable_skill_ids
        coverage = len(covered) / len(enforceable_skill_ids)
        if coverage < COVERAGE_THRESHOLD:
            uncovered = sorted(enforceable_skill_ids - constrained)
            issues.append(Issue(
                "WARN",
                f"yaml: {agent_type}.governance.{profile_name}",
                f"skill->rule coverage {coverage * 100:.0f}% (< "
                f"{int(COVERAGE_THRESHOLD * 100)}% requisite-variety "
                f"threshold); {len(uncovered)} skill(s) unconstrained by "
                f"any thinking_rule or identity_rule: {uncovered}. Agents "
                "may converge on the unconstrained subset while governance "
                "looks effective on the constrained subset. Add rules "
                "covering these skills or document the deliberate omission. "
                "(harness-engineering flaw 5 — Requisite Variety)",
            ))

    return issues


# ---------------------------------------------------------------------------
# Per-agent-type validation
# ---------------------------------------------------------------------------

def validate_agent_type(
    cfg: Dict[str, Any],
    agent_type: str,
    yaml_path: Path,
    domain_extensions: Optional[Set[str]] = None,
) -> List[Issue]:
    """Validate one agent type's prompt + YAML cross-references.

    Args:
        cfg: parsed YAML dict.
        agent_type: which top-level key to validate.
        yaml_path: path of the YAML (for error-message locations).
        domain_extensions: extra placeholder names accepted as broker-
            filled (in addition to ``BROKER_FILLED_PLACEHOLDERS``).
            Typically supplied by ``_resolve_domain_extensions`` from
            the YAML's ``global_config.governance.domain`` field +
            the registered DomainPack's
            ``prompt_placeholder_extensions()`` hook. Phase 6R-B-3.
    """
    if domain_extensions is None:
        domain_extensions = set()
    issues: List[Issue] = []
    block = cfg.get(agent_type)
    if not isinstance(block, dict):
        issues.append(Issue(
            "ERROR", f"yaml: {agent_type}",
            f"agent_type '{agent_type}' not found at YAML top level",
        ))
        return issues

    # ---- ACTIONS block (Finding 5 root cause A) --------------------------
    # Two valid locations exist in the wild:
    #   * top-of-block: vaccination_demo, irrigation_abm — block["actions"]
    #   * nested under parsing: multi_agent flood — block["parsing"]["actions"]
    actions = block.get("actions")
    actions_location = "actions"
    if not actions:
        parsing_block = block.get("parsing", {})
        if isinstance(parsing_block, dict):
            actions = parsing_block.get("actions")
            if actions:
                actions_location = "parsing.actions"
    if not actions:
        issues.append(Issue(
            "ERROR", f"yaml: {agent_type}.actions",
            "missing 'actions:' block — parser.get_valid_actions() will "
            "return [] and every LLM response will be rejected. Declare "
            "each skill with id + aliases. Allowed locations: "
            "agent_type.actions OR agent_type.parsing.actions.",
        ))
    elif not isinstance(actions, list):
        issues.append(Issue(
            "ERROR", f"yaml: {agent_type}.{actions_location}",
            f"actions must be a list, got {type(actions).__name__}",
        ))
    else:
        for i, a in enumerate(actions):
            if not isinstance(a, dict) or "id" not in a:
                issues.append(Issue(
                    "ERROR", f"yaml: {agent_type}.{actions_location}[{i}]",
                    "each action entry needs an 'id:' field",
                ))

    # ---- response_format -------------------------------------------------
    # Prefer agent-block-level response_format (overrides shared); fall back
    # to shared.response_format (vaccination_demo / irrigation pattern).
    shared = cfg.get("shared", {})
    response_format = block.get("response_format") or shared.get("response_format", {})
    fields = response_format.get("fields", []) if isinstance(response_format, dict) else []
    field_keys: Set[str] = set()
    construct_to_key: Dict[str, str] = {}
    for f in fields:
        if not isinstance(f, dict):
            continue
        key = f.get("key")
        if key:
            field_keys.add(key)
        construct = f.get("construct")
        if construct and key:
            construct_to_key[construct] = key

    if not fields:
        issues.append(Issue(
            "WARN", "yaml: shared.response_format.fields",
            "no response_format.fields declared — runtime will skip "
            "auto-injecting {response_format} into prompts",
        ))

    # ---- parsing.constructs vs response_format.fields[].construct ---------
    parsing = block.get("parsing", {})
    parsing_constructs = parsing.get("constructs", {}) if isinstance(parsing, dict) else {}
    missing_constructs = [
        c for c in construct_to_key if c not in parsing_constructs
    ]
    if missing_constructs:
        issues.append(Issue(
            "ERROR", f"yaml: {agent_type}.parsing.constructs",
            "response_format.fields declare construct labels "
            f"{missing_constructs} but parsing.constructs has no matching "
            "entries — the parser cannot extract appraisal labels and "
            "every response will fail required-fields check",
        ))

    # ---- prompt template -------------------------------------------------
    # Two equivalent forms: external file (prompt_template_file) or inline
    # string (prompt_template, used by older flood institutional agents).
    template_ref = block.get("prompt_template_file")
    inline_template = block.get("prompt_template")
    template: Optional[str] = None
    template_location = ""

    if template_ref:
        prompt_path = resolve_prompt_path(yaml_path, template_ref)
        if not prompt_path.exists():
            issues.append(Issue(
                "ERROR", str(prompt_path),
                "prompt_template_file does not exist (tried yaml_dir + "
                "up to 4 parent levels)",
            ))
            return issues
        template = prompt_path.read_text(encoding="utf-8")
        template_location = str(prompt_path)
    elif inline_template:
        template = inline_template
        template_location = f"yaml: {agent_type}.prompt_template (inline)"
    else:
        issues.append(Issue(
            "WARN", f"yaml: {agent_type}",
            "no 'prompt_template_file' or inline 'prompt_template' set — "
            "agent will use the broker default template",
        ))
        # Options-text parity BLOCKER, missing-template branch (2026-09,
        # hardened after silent-failure review — this WARN used to
        # `return` before the parity BLOCKER below ever ran). The broker
        # default template renders {skills}, not {options_text}
        # (BaseAgentContextBuilder.DEFAULT_PROMPT_TEMPLATE — the exact
        # vaccination_demo shape); TieredContextBuilder's own default DOES
        # carry {options_text}, but a static config check cannot know
        # which builder a given run will use, so it must not assume the
        # safe one. Fail closed: treat "no template at all" the same as
        # "template lacks the placeholder" for a multi-skill, non-
        # full_disclosure agent.
        n_actions_no_template = len(actions) if isinstance(actions, list) else 0
        full_disclosure_no_template = (
            bool(parsing.get("full_disclosure")) if isinstance(parsing, dict) else False
        )
        if n_actions_no_template > 1 and not full_disclosure_no_template:
            issues.append(Issue(
                "ERROR", f"yaml: {agent_type}",
                f"agent_type '{agent_type}' has {n_actions_no_template} eligible "
                f"skills, declares no 'prompt_template_file' or inline "
                f"'prompt_template', and 'parsing.full_disclosure' is not true. "
                f"The broker default template used in this case "
                f"(BaseAgentContextBuilder.DEFAULT_PROMPT_TEMPLATE) renders "
                f"'ACT:{{skills}}', NOT {{options_text}} — the exact "
                f"vaccination_demo bug shape. RAG skill retrieval can re-rank "
                f"the menu per call while the model answers against a stale "
                f"legend. Fix: add a prompt_template_file that renders "
                f"{{options_text}}, or set 'parsing.full_disclosure: true'.",
            ))
        return issues

    # ---- placeholder coverage -------------------------------------------
    placeholders = extract_placeholders(template)
    template_var_keys = (
        collect_template_vars(shared.get("template_vars"))
        | collect_template_vars(block.get("template_vars"))
    )
    # Phase 6R-B-3 (audit cluster E #16): union the base broker-filled
    # set with the DomainPack's domain-specific extensions (e.g.
    # FloodDomainPack.prompt_placeholder_extensions() supplies
    # ``insurance_cost_text`` etc.). Pre-fix these names lived in
    # BROKER_FILLED_PLACEHOLDERS directly, leaking flood-domain vocab
    # into generic CLI code.
    known_keys = (
        BROKER_FILLED_PLACEHOLDERS
        | domain_extensions
        | field_keys
        | template_var_keys
    )
    unknown = sorted(p for p in placeholders if p not in known_keys)
    if unknown:
        issues.append(Issue(
            "WARN", template_location,
            f"placeholders not in broker-filled or YAML-declared set: "
            f"{unknown}. At runtime SafeFormatter will silently render "
            f"these as '[N/A]'. Either add to response_format.fields or "
            f"ensure a domain lifecycle hook fills them via "
            f"template_vars.",
        ))

    # ---- options-text parity (2026-09 fix) --------------------------------
    # BLOCKER: an agent with >1 eligible skill whose prompt never renders
    # the live numbered list ({options_text}/{skills_text}) is vulnerable to
    # the vaccination_demo bug — RAG skill retrieval (or shuffle_options)
    # can re-rank the menu per call, and the model would then answer against
    # a stale/hardcoded legend (or the never-filled {skills} placeholder)
    # while the parser decodes the digit against the ACTUAL re-ranked
    # dynamic_skill_map (broker/core/_skill_filtering.py:_inject_options_text).
    # 'full_disclosure: true' is the one config-time escape hatch that keeps
    # the map pinned to registry (actions:) order, so a static legend built
    # from that order stays correct without {options_text}. See also the
    # matching runtime guard: SkillFilterMixin._assert_options_text_parity.
    n_actions = len(actions) if isinstance(actions, list) else 0
    full_disclosure = bool(parsing.get("full_disclosure")) if isinstance(parsing, dict) else False
    has_options_placeholder = "{options_text}" in template or "{skills_text}" in template
    # Name-based decision design (e.g. MA flood's government/insurance
    # institutional agents): every skill's literal id is hand-written into
    # the template's own static text (an options bullet list, an inline
    # JSON example asking for the literal name) instead of a broker-
    # rendered numbered list. The parser resolves such an answer by
    # NAME/alias match, not by re-ranked digit position, so order drift
    # carries no decode risk — PROVIDED nothing about this agent's shape
    # lets a digit sneak into the decode path anyway. Mirrors the runtime
    # guard's identical, hardened exemption
    # (SkillFilterMixin._is_name_based_and_safe), ALL required:
    #   1. every id matches ^[A-Za-z_]+$ — no digits in the id itself.
    #      unified_adapter.py Case 2 (`re.search(r'(\d+)', decision_val)`)
    #      extracts the FIRST digit ANYWHERE in the model's answer string
    #      and decodes POSITIONALLY if that digit is a dynamic_skill_map
    #      key, before ever trying name/alias resolution — a digit-bearing
    #      id could get silently mis-decoded via that digit even with
    #      every name spelled out in full.
    #   2. a whole-token regex per id (not a bare substring — "insurance"
    #      must not match inside "reinsurance_program").
    #   3. no {valid_choices_text} (unconditionally a digit-count string,
    #      independent of any declared type); no {response_format} WHILE
    #      the decision field is declared type: "choice" — ResponseFormat-
    #      Builder.build() is the ONLY code that turns "choice" into a
    #      numeric-ID instruction, and only inside the {response_format}
    #      block, so a declared "choice" the template never renders via
    #      {response_format} is inert (this is precisely MA flood's
    #      government/insurance shape — declared type: "choice", but the
    #      template hand-writes its own JSON and never references
    #      {response_format}, so the declaration can never actually
    #      render); no literal numbered-example decision value
    #      ("decision": 1 -style) or hand-written numbered option list
    #      (1. .../2. ...) either, catching a fully hand-rolled numeric
    #      prompt using no broker placeholder at all.
    action_ids = [
        a.get("id") for a in actions
        if isinstance(actions, list) and isinstance(a, dict) and a.get("id")
    ] if isinstance(actions, list) else []

    _name_like_id = re.compile(r"^[A-Za-z_]+$")
    _numbered_decision_example = re.compile(r'"decision"\s*:\s*"?\d')
    _numbered_option_list = re.compile(r"^\s*\d+\.\s", re.MULTILINE)

    def _spelled_out(aid: str) -> bool:
        if not _name_like_id.match(aid):
            return False
        pattern = rf"(?<![A-Za-z0-9_]){re.escape(aid)}(?![A-Za-z0-9_])"
        return re.search(pattern, template) is not None

    # Silent-failure hunter findings (2026-09), mirrored from
    # broker/core/_skill_filtering.py:resolve_decision_field_is_numeric_choice:
    # (NEW-1) "secondary_choice" also renders a numeric-ID instruction
    # (response_format.py's `elif ftype == "secondary_choice":` branch,
    # ~150-153) — not just "choice". (NEW-2) checking only fields whose
    # key is in a guessed decision_keywords set (defaulting to just
    # {"decision"}) can miss the real decision field: the parser's own
    # default keyword list is wider (unified_adapter.py:427,
    # ["decision", "choice", "action"]) and a YAML need not declare
    # decision_keywords explicitly to use it. Check ALL fields instead —
    # a numeric-choice field under any key is itself a live signal.
    decision_is_numeric_choice = any(
        isinstance(f, dict) and f.get("type") in _NUMERIC_CHOICE_FIELD_TYPES
        for f in fields
    )
    invites_digit = (
        "{valid_choices_text}" in template
        or ("{response_format}" in template and decision_is_numeric_choice)
        or bool(_numbered_decision_example.search(template))
        or len(_numbered_option_list.findall(template)) >= 2
    )
    is_name_based = (
        bool(action_ids) and all(_spelled_out(aid) for aid in action_ids) and not invites_digit
    )
    if n_actions > 1 and not full_disclosure and not has_options_placeholder and not is_name_based:
        issues.append(Issue(
            "ERROR", template_location,
            f"agent_type '{agent_type}' has {n_actions} eligible skills but "
            f"the prompt template renders neither {{options_text}} nor "
            f"{{skills_text}}, and 'parsing.full_disclosure' is not true. "
            f"RAG skill retrieval (or shuffle_options) can re-rank the menu "
            f"per call; the model then answers against a stale/hardcoded "
            f"legend while the parser decodes the digit against the actual "
            f"re-ranked map — this is the vaccination_demo bug (57-63% of "
            f"decisions decoded to the wrong skill from year 2 on, verified "
            f"on 3 runs). Fix: render {{options_text}} in the prompt "
            f"template, or set 'parsing.full_disclosure: true' to keep the "
            f"menu order stable.",
        ))

    # ---- inline JSON key sync (Finding 4) --------------------------------
    # Keys the parser looks for via parsing.decision_keywords are also
    # legitimate top-level JSON keys, even though they aren't in
    # response_format.fields (the decision is matched by parser pipeline,
    # not by required-fields check).
    decision_keywords = set(parsing.get("decision_keywords", []) or [])
    inline_keys = extract_inline_json_keys(template)
    if inline_keys and field_keys:
        only_in_prompt = inline_keys - field_keys - decision_keywords
        if only_in_prompt:
            issues.append(Issue(
                "ERROR", template_location,
                f"inline JSON example uses keys {sorted(only_in_prompt)} "
                f"not in YAML response_format.fields[].key "
                f"({sorted(field_keys)}) and not in "
                f"parsing.decision_keywords ({sorted(decision_keywords)}). "
                f"LLM will produce these keys but the parser will reject "
                f"them as 'missing required fields'.",
            ))

    # ---- Phase 6G flaw 5: skill->rule coverage (Requisite Variety) -------
    issues.extend(check_skill_rule_coverage(cfg, agent_type))

    return issues


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Static validator: agent prompt template vs YAML config.\n\n"
            "Phase 6R-B-3 (audit cluster E #16): the CLI's placeholder "
            "allowlist is the union of BROKER_FILLED_PLACEHOLDERS and "
            "the registered DomainPack's prompt_placeholder_extensions() "
            "hook. To validate a flood YAML (which references "
            "{insurance_cost_text} / {mg_barrier_text} / {renewal_fatigue_text}) "
            "without spurious WARNs, ensure FloodDomainPack is registered "
            "BEFORE invoking this CLI — e.g. run from a Python entry "
            "point that imports examples.governed_flood, or use "
            "`python -m examples.governed_flood validate_prompt ...`."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "yaml_file",
        type=Path,
        help="Path to agent_types.yaml",
    )
    parser.add_argument(
        "--agent-type",
        action="append",
        help=(
            "Agent type key to validate. Repeat for multiple. Default: "
            "every top-level key in the YAML that has 'agent_type' set."
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat WARN as ERROR (exit 1 on any issue)",
    )
    args = parser.parse_args(argv)

    if not args.yaml_file.exists():
        print(f"ERROR: YAML file not found: {args.yaml_file}", file=sys.stderr)
        return 1

    cfg = load_yaml(args.yaml_file)

    if args.agent_type:
        agent_types: List[str] = args.agent_type
    else:
        # Auto-discover: any top-level dict that looks like an agent-type
        # config block. Two conventions are seen in the wild:
        #   - vaccination_demo style: explicit `agent_type:` key inside
        #   - irrigation / flood style: the dict's KEY name is the agent
        #     type and the block has prompt_template_file / parsing / etc.
        AGENT_KEY_INDICATORS = (
            "agent_type",
            "prompt_template_file",
            "psychological_framework",
            "parsing",
        )
        RESERVED = {"global_config", "shared", "personas", "skill_magnitude",
                    "metadata",
                    # Top-level governance block (governance.strict.<agent_type>
                    # .thinking_rules) — never an agent type itself. Excluded so
                    # a future governance dict that happens to nest an
                    # AGENT_KEY_INDICATOR (e.g. parsing:) is not misclassified
                    # as an agent type (6T-F.3 was the first standalone config
                    # to carry a scanned top-level governance block).
                    "governance"}
        agent_types = [
            k for k, v in cfg.items()
            if isinstance(v, dict)
            and k not in RESERVED
            and any(ind in v for ind in AGENT_KEY_INDICATORS)
        ]
        if not agent_types:
            print(
                "ERROR: no agent_type blocks found in YAML. Each agent "
                "type block must contain at least one of: "
                f"{AGENT_KEY_INDICATORS}",
                file=sys.stderr,
            )
            return 1

    all_issues: List[Issue] = []
    # 2026-06-09: config-time unknown-key net (canonical registry above).
    all_issues.extend(check_global_config_keys(cfg))
    # 2026-06-10 (G4): silently-dead rule-shape lint (the 6N-E class).
    all_issues.extend(check_rule_shapes(cfg))
    # PR-6 (W5): world-condition `scope:` allowlist. An unrecognised scope is
    # coerced to `auto` at load time and the rule keeps firing against a plane
    # nobody named, so it has to be caught before the batch, not after.
    all_issues.extend(check_world_condition_scopes(cfg))
    # PR-8: every declared `decider:` must name a registered one, and the
    # key must be where something reads it.
    all_issues.extend(check_decider_declarations(cfg))
    # Phase 6R-B-3: resolve domain-specific placeholder extensions once
    # per CLI invocation. The hook is keyed on
    # ``global_config.governance.domain``.
    domain_extensions = _resolve_domain_extensions(cfg)
    for at in agent_types:
        all_issues.extend(
            validate_agent_type(
                cfg, at, args.yaml_file,
                domain_extensions=domain_extensions,
            )
        )

    if not all_issues:
        print(f"OK: {args.yaml_file} — {len(agent_types)} agent type(s) clean")
        return 0

    n_err = sum(1 for i in all_issues if i.severity == "ERROR")
    n_warn = sum(1 for i in all_issues if i.severity == "WARN")
    for issue in all_issues:
        print(issue.format())
    print(f"\n{n_err} error(s), {n_warn} warning(s)")

    if n_err > 0:
        return 1
    if args.strict and n_warn > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
