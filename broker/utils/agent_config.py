"""
Agent Type Configuration Loader

Loads unified agent configuration from broker/agent_types.yaml.
Provides easy access to prompts, validation rules, and coherence rules.

Task-035: Added SDK UnifiedConfigLoader integration for experiment configs.
"""

import yaml
import os
import json
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field
from collections import defaultdict
from broker.utils.logging import setup_logger

if TYPE_CHECKING:
    from cognitive_governance.v1_prototype.config import (
        UnifiedConfigLoader,
        ExperimentConfig,
        MemoryConfig as SDKMemoryConfig,
    )

logger = setup_logger(__name__)


@dataclass
class ActionConfig:
    """Single action configuration."""
    id: str
    aliases: List[str]
    description: str
    requires: Optional[Dict[str, Any]] = None


@dataclass
class ValidationRule:
    """Single validation rule."""
    name: str
    param: str
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    max_delta: Optional[float] = None
    level: str = "WARNING"
    message: str = ""


@dataclass  
class CoherenceRule:
    """Construct coherence rule."""
    id: str = "unknown"
    construct: Optional[str] = None # Single construct (legacy)
    conditions: Optional[List[Dict[str, Any]]] = None # Multi-construct: [{'construct': 'TP', 'values': ['L']}]
    state_field: Optional[str] = None
    state_fields: Optional[List[str]] = None
    aggregation: str = "single"
    threshold: float = 0.5
    expected_levels: Optional[List[str]] = None
    trigger_phrases: Optional[List[str]] = None
    blocked_skills: Optional[List[str]] = None
    level: str = "ERROR" # ERROR (retry) or WARNING (log only)
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    # PR-6: what the rule's antecedent is ANCHORED IN.
    #   "self_report" — every condition reads a construct label the model wrote
    #                   in the same generation. Such a rule checks one JSON
    #                   object against itself.
    #   "world"       — at least one condition reads simulator/world state the
    #                   model cannot author (an env variable, a physical
    #                   precondition), so the rule can catch a self-report the
    #                   world contradicts.
    # Resolved by ``get_thinking_rules``: an explicit YAML ``grounding:`` wins;
    # otherwise it is inferred from the condition shapes. Default "self_report"
    # is the honest default — a rule is not world-grounded until it reads the
    # world.
    grounding: str = "self_report"


# ──────────────────────────────────────────────────────────────────────
# PR-6: rule GROUNDING — where a condition's antecedent comes from
# ──────────────────────────────────────────────────────────────────────
# A thinking rule reads either a construct LABEL the model just emitted
# (``construct:`` / ``field:`` with ``type: construct``) or a WORLD
# VARIABLE the model cannot author (``variable:``, or ``field:`` with
# ``type: expression | precondition | social``). Only the second kind can
# catch a self-report the simulated world contradicts.
#
# These two helpers are the SINGLE definition of that distinction. The
# config loader uses them to stamp ``CoherenceRule.grounding``; the
# validator uses ``world_condition_target`` to decide how to evaluate a
# condition. Keeping one definition is what stops the audit column and the
# enforcement path from disagreeing about which rules were world-grounded.

WORLD_CONDITION_TYPES: frozenset = frozenset({"expression", "precondition", "social"})

# Where a world variable may be looked up. ``auto`` is the documented
# precedence env_state -> agent state -> flattened context; the explicit
# scopes exist because the broker's validation context is built as
# ``{**agent_state, **env_context}`` and a name present in both silently
# resolves to the env copy. Writing ``scope:`` says which one you meant.
WORLD_CONDITION_SCOPES: frozenset = frozenset({"auto", "env", "state", "social", "context"})

# Top-level keys in an agent-types YAML that are NOT an agent type. Every
# scan that asks "what does each agent type declare?" has to skip these,
# and before PR-8 review finding C1 each scan carried its own copy of the
# list — one of which had none, so `has_non_default_deciders` read a
# `decider:` written under `shared:` (where nothing reads it) as a
# mixed-population run and switched the audit columns on for a corpus
# whose every row was an LLM row. Kept beside WORLD_CONDITION_SCOPES so
# the next scan finds it. Mirrors `RESERVED` in broker/tools/validate_prompt.
NON_AGENT_TOP_LEVEL_KEYS: frozenset = frozenset({
    "global_config", "shared", "metadata", "governance", "personas",
    "skill_magnitude",
})

# Warn-once keys for scope coercion (W5). ``world_condition_target`` runs per
# condition per rule per agent per step, so an unconditional warning would print
# at agents x years x rules x retries frequency and become noise nobody reads.
_WARNED_UNKNOWN_SCOPES: set = set()

# STRICTNESS OF ``is_true`` / ``is_false`` (documented here because this is where
# a rule author looks). Both operators test IDENTITY against Python's ``True`` /
# ``False`` singletons, not truthiness and not ``==``. A magnitude of ``1.0``,
# the string ``"true"``, and ``numpy.True_`` all fail an ``is_true`` condition.
#
# That is deliberate. ``1.0 == True`` is True in Python, so an ``==``-based flag
# test would start matching a magnitude that happens to equal 1, and the audit
# row would show the rule firing with nothing in it to explain why. The cost is
# that a simulator publishing a numpy boolean must convert it: write
# ``bool(value)`` in the environment adapter, or use
# ``operator: "==", value: true``, which coerces. There is no numpy import in
# ``broker/`` and adding one to accept ``numpy.bool_`` here would make the
# generic layer depend on a scientific stack it does not otherwise need.


def world_condition_target(cond: Any) -> Tuple[Optional[str], str]:
    """Return ``(variable_name, scope)`` for a world-state condition, else ``(None, "")``.

    Accepts the two shapes the repo already has in the wild:

    * ``{variable: hazard_index, scope: env, operator: ">", value: 0.4}``
    * ``{type: precondition, field: at_capacity, operator: "==", values: [true]}``

    A ``construct:``/``type: construct`` condition returns ``(None, "")`` —
    that is the self-report path and must keep its existing evaluation
    verbatim, or every frozen baseline moves.
    """
    if not isinstance(cond, dict):
        return None, ""
    name = cond.get("variable")
    if name:
        scope = str(cond.get("scope", "auto")).strip().lower()
        if scope not in WORLD_CONDITION_SCOPES:
            _warn_unknown_scope(str(name), cond.get("scope"), "auto")
            scope = "auto"
        return str(name), scope
    cond_type = str(cond.get("type", "") or "").strip().lower()
    if cond_type in WORLD_CONDITION_TYPES and cond.get("field"):
        raw_scope = cond.get("scope")
        scope = str(raw_scope if raw_scope is not None else "").strip().lower()
        if scope not in WORLD_CONDITION_SCOPES:
            fallback = "social" if cond_type == "social" else "auto"
            if scope:
                _warn_unknown_scope(str(cond.get("field")), raw_scope, fallback)
            scope = fallback
        return str(cond.get("field")), scope
    return None, ""


def _warn_unknown_scope(variable: str, raw_scope: Any, fallback: str) -> None:
    """W5: say out loud that a ``scope:`` was not recognised and was coerced.

    Coercing silently is the failure this warning removes: ``scope: environment``
    (a plausible typo for ``env``) became ``auto``, which searches env FIRST —
    so it worked, until the day the agent's own state carried the same name and
    the rule started reading the wrong plane with nothing anywhere saying the
    scope had never been honoured. Warn-once per (variable, scope).
    """
    key = (variable, str(raw_scope))
    if key in _WARNED_UNKNOWN_SCOPES:
        return
    _WARNED_UNKNOWN_SCOPES.add(key)
    logger.warning(
        "[Config] world condition on %r declares scope %r, which is not one of "
        "%s. Coerced to %r. A coerced scope still resolves a value, so the rule "
        "keeps firing — against whichever plane won, not the one you named.",
        variable, raw_scope, sorted(WORLD_CONDITION_SCOPES), fallback,
    )


def resolve_rule_grounding(rule: Dict[str, Any]) -> str:
    """Resolve a rule dict's grounding: explicit ``grounding:`` wins, else inferred.

    Inference is deliberately conservative: a rule counts as ``world`` only
    when at least one of its conditions actually reads a world variable. A
    rule that merely *mentions* the world in its ``message:`` stays
    ``self_report``, because prose is not an antecedent.

    An IDENTITY rule's top-level ``precondition:`` counts as a world antecedent
    (P1-f). Those rules test simulator state the model cannot author — this
    irreversible action has already been taken, the agent is already at its
    resource cap — and they always were world-grounded; nothing was stamping
    them, so every identity block was filed under ``rules_self_report`` and a
    count of self-report blocks silently included physical constraints.
    """
    declared = str(rule.get("grounding", "") or "").strip().lower()
    if declared in ("world", "self_report"):
        return declared
    if rule.get("precondition"):
        return "world"
    conditions = rule.get("conditions") or []
    if isinstance(conditions, list):
        for cond in conditions:
            name, _scope = world_condition_target(cond)
            if name:
                return "world"
    return "self_report"


def declared_governance_profiles(
    config: Dict[str, Any], agent_type: Optional[str] = None
) -> set:
    """Every governance-profile name a raw config dict declares.

    P1-e. Reads both shapes the loader reads: the top-level
    ``governance.<profile>.<agent_type>`` form and the per-agent-type
    ``<agent_type>.governance.<profile>`` form. ``global_config`` is skipped —
    it has a ``governance:`` block of its own holding settings, not profiles,
    and counting its keys would report ``max_retries`` as an available arm.

    Used by the runners to refuse a ``--governance-mode`` the config does not
    declare. Never raises; an unreadable config returns an empty set, and the
    caller decides what that means.
    """
    names: set = set()
    if not isinstance(config, dict):
        return names
    top = config.get("governance")
    if isinstance(top, dict):
        for profile, body in top.items():
            if not isinstance(body, dict):
                continue
            if agent_type is None or agent_type in body:
                names.add(str(profile))
    for key, body in config.items():
        if key == "global_config" or not isinstance(body, dict):
            continue
        if agent_type is not None and key != agent_type:
            continue
        gov = body.get("governance")
        if isinstance(gov, dict):
            names.update(str(p) for p in gov)
    return names


def assert_governance_profile_declared(
    cfg_data: Dict[str, Any], profile: Any, agent_type: Optional[str], config_path: Any
) -> None:
    """PR-6 review P1-e: refuse an undeclared ``--governance-mode``, loudly.

    ``get_thinking_rules`` falls back to the ``default`` profile when the
    requested one is not declared, and says nothing. For an interactive run that
    is forgiving; for a queued sweep it is the silent-wrong-data failure — a
    typo'd or stale arm name runs the WRONG RULE SET for hours and every
    artifact, including ``run_integrity.json``, looks healthy.

    ``default`` is always accepted: it is the fallback itself, and a config that
    declares no profiles at all legitimately resolves to it.

    N2: moved here from a byte-identical copy duplicated in
    ``examples/single_agent/run_flood.py`` and
    ``examples/irrigation_abm/run_experiment.py`` — both runners now call this
    one implementation instead of carrying their own that could drift apart.
    """
    requested = str(profile or "default").strip().lower()
    if requested == "default":
        return
    declared = {p.lower() for p in declared_governance_profiles(cfg_data, agent_type)}
    if requested in declared:
        return
    raise SystemExit(
        f"--governance-mode {profile!r} is not declared for agent_type "
        f"{agent_type!r} in {config_path}.\n"
        f"Declared profiles: {sorted(declared) or '(none)'}.\n"
        "Refusing to start: the config loader would fall back to the 'default' "
        "rule set silently, so the run would finish, look healthy, and answer a "
        "different question than the one you asked."
    )


def resolve_framework_aware_labels(config: Any = None) -> bool:
    """The ``validators.framework_aware_labels`` value, for callers holding no config.

    P1-b. ``build_domain_validators`` constructs a ``ThinkingValidator`` from a
    domain name alone — it never receives the ``AgentTypeConfig`` the
    ``AgentValidator`` was built from — so the flag reached one evaluator and not
    the other, and the two disagreed about missing constructs on the same
    decision. Pass a config when you have one; without it this reads the
    most-recently-loaded instance, which is the same object every production run
    path resolves (``ExperimentBuilder`` loads exactly one).

    Never raises, and coerces to a real ``bool``: a test double whose getter
    returns a truthy mock must not switch the flag on for the whole suite.
    """
    if config is None:
        config = getattr(AgentTypeConfig, "_instance", None)
    getter = getattr(config, "get_validators_framework_aware_labels", None)
    if not callable(getter):
        return False
    try:
        value = getter()
    except Exception as exc:  # noqa: BLE001 — a config read must not break dispatch
        logger.warning(
            "[Config] could not resolve validators.framework_aware_labels (%s: %s); "
            "treating as OFF for this validator. The AgentValidator resolves it "
            "from its own config, so a failure here can make the two evaluators "
            "disagree — check the startup parity log.",
            type(exc).__name__, exc,
        )
        return False
    return value if isinstance(value, bool) else False


class AgentTypeConfig:
    """
    Loader for agent type configurations.

    Usage:
        config = AgentTypeConfig.load()
        agent_cfg = config.get("my_agent_type")  # e.g., "household", "trader", etc.
        valid_actions = agent_cfg["actions"]
        rules = agent_cfg["validation_rules"]
    """
    
    _instance = None
    _instances: Dict[str, "AgentTypeConfig"] = {}
    _lock = threading.Lock()
    _config = {}

    @staticmethod
    def _resolve_yaml_path(yaml_path: Optional[str] = None) -> str:
        """Resolve config path deterministically for per-path cache keys."""
        if yaml_path is not None:
            return str(Path(yaml_path).resolve())

        cwd_path = (Path.cwd() / "agent_types.yaml").resolve()
        if cwd_path.exists():
            return str(cwd_path)

        # Fallback to package default
        return str((Path(__file__).parent / "agent_types.yaml").resolve())
    
    @classmethod
    def load(cls, yaml_path: Optional[str] = None, force_reload: bool = False) -> "AgentTypeConfig":
        """Load config from a path-aware cache to avoid cross-domain leakage."""
        resolved = cls._resolve_yaml_path(yaml_path)
        with cls._lock:
            if force_reload or resolved not in cls._instances:
                inst = cls()
                inst._load_yaml(resolved)
                cls._instances[resolved] = inst
            cls._instance = cls._instances[resolved]  # backward-compatible handle
            return cls._instance

    @classmethod
    def clear_cache(cls) -> None:
        """Clear all cached instances. Useful for test teardown."""
        with cls._lock:
            cls._instances.clear()
            cls._instance = None
    
    def _load_yaml(self, yaml_path: Optional[str] = None):
        """Load from YAML file."""
        yaml_path = self._resolve_yaml_path(yaml_path)
        # PR-8: answered once per loaded config and consulted per audit row.
        # Cleared here so a reload never answers from the previous file.
        self._non_default_deciders = None

        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
            self._yaml_path = str(yaml_path)
            # logger.info(f"Loaded configuration from {yaml_path}")
        except FileNotFoundError:
            logger.warning(
                f"[Config] Agent type configuration not found: {yaml_path}\n"
                f"  Tip: Ensure the file exists and the path is correct.\n"
                f"  Use: AgentTypeConfig.load('path/to/agent_types.yaml')"
            )
            self._config = {}
            self._yaml_path = None
        except yaml.YAMLError as e:
            mark = getattr(e, 'problem_mark', None)
            location = f" (line {mark.line + 1})" if mark else ""
            logger.warning(
                f"[Config] Invalid YAML in {yaml_path}{location}: {e}\n"
                f"  Tip: Check indentation, colons, and special characters."
            )
            self._config = {}
            self._yaml_path = None
        except Exception as e:
            logger.warning(f"[Config] Failed to load config from {yaml_path}: {e}")
            self._config = {}
            self._yaml_path = None
    
    def get_base_type(self, agent_type: str) -> str:
        """Map a specific agent type/subtype to a base type defined in config."""
        if agent_type in self._config:
            return agent_type
        
        # Suffix-based mapping (mg/nmg)
        base_type = agent_type.split('_')[0]
        if base_type in self._config:
            return base_type
            
        return agent_type

    def get(self, agent_type: str) -> Dict[str, Any]:
        """Get config for agent type."""
        base_type = self.get_base_type(agent_type)
        return self._config.get(base_type, {})
    
    def items(self):
        """Allow iteration over agent types."""
        return self._config.items()
    
    def keys(self):
        """Allow checking agent types."""
        return self._config.keys()
    
    def get_shared(self, key: str, default: Any = "") -> Any:
        """Get shared config value (e.g., rating_scale)."""
        shared = self._config.get("shared", {})
        return shared.get(key, default)
    
    def get_governance_retries(self, default: int = 3) -> int:
        """Get max retries for governance loop (Global > Shared > Default)."""
        # 1. Check Global Config
        global_gov = self._config.get("global_config", {}).get("governance", {})
        return global_gov.get("max_retries", self._config.get("shared", {}).get("governance", {}).get("max_retries", default))
    
    def get_governance_max_reports(self, default: int = 3) -> int:
        """Get max reports per retry (Global > Shared > Default)."""
        # 1. Check Global Config
        global_gov = self._config.get("global_config", {}).get("governance", {})
        return global_gov.get("max_reports_per_retry", self._config.get("shared", {}).get("governance", {}).get("max_reports_per_retry", default))

    def get_governance_physical_dispatch(self) -> Optional[Any]:
        """Registry-PHYSICAL dispatch selector for the simple ExperimentBuilder
        path: a domain string, an ``{agent_type: domain}`` mapping, or None.

        OPT-IN, default-OFF: frozen domains (flood / irrigation / vaccination /
        MA-flood / SA-flood) — which run their physical checks via
        ``custom_validators`` or intentionally leave them dormant — see no
        change in behavior or audit output.

        Two declared forms (Wave 3, review P1-2):

        * STRING form (single-domain runs)::

              governance:
                domain: cat_model
                dispatch_domain_physical: true

          Returns ``"cat_model"`` — ONE domain's checks for ALL agent types.
          Raises ValueError when the flag is truthy but ``domain`` is
          absent/blank (an explicitly-requested dispatch must never silently
          no-op; review P1-11).

        * MAPPING form (mixed-domain experiments)::

              governance:
                dispatch_domain_physical:
                  household: flood
                  operator: reservoir

          Returns the (lowercased) mapping — each proposal routes to its own
          agent type's domain in ``_run_validators``; agent types absent from
          the mapping get no registry dispatch. ``governance.domain`` is not
          required in this form. Empty/blank mapping values raise.

        Deliberately does NOT read the ``GOVERNANCE_DOMAIN`` env var: dispatch
        is config-declared only, so a stray env var cannot silently activate
        physical enforcement.
        """
        gov = self._config.get("global_config", {}).get("governance", {})
        flag = gov.get("dispatch_domain_physical", False)
        if not flag:
            return None
        if isinstance(flag, dict):
            mapping = {}
            for atype, dom in flag.items():
                dom_s = str(dom).strip().lower() if dom else ""
                if not dom_s:
                    raise ValueError(
                        "global_config.governance.dispatch_domain_physical mapping "
                        f"has an empty domain for agent_type {atype!r} — every "
                        "entry must name a registered domain."
                    )
                mapping[str(atype).strip()] = dom_s
            if not mapping:
                raise ValueError(
                    "global_config.governance.dispatch_domain_physical is an empty "
                    "mapping — declare {agent_type: domain} entries or remove it."
                )
            return mapping
        domain = gov.get("domain")
        resolved = (str(domain).strip().lower() or None) if domain else None
        if resolved is None:
            raise ValueError(
                "global_config.governance.dispatch_domain_physical is set but "
                "'domain' is absent/blank — the explicitly-requested PHYSICAL "
                "dispatch would silently never fire. Add 'domain: <your_domain>' "
                "next to the flag (see examples/cat_model/config/agent_types.yaml), "
                "or use the {agent_type: domain} mapping form."
            )
        return resolved

    def get_audit_executed_columns(self) -> bool:
        """F3 (2026-06-10 audit review): opt-in EXECUTED-stage audit columns.

        When ``global_config.audit.executed_skill_columns: true``, every trace
        carries top-level ``executed_skill`` + ``executed_via_fallback`` keys
        recording what the simulation engine ACTUALLY executed — on REJECTED,
        the registry default skill runs as fallback but the CSV's
        ``final_skill`` records the *blocked* proposal and
        ``fallback_activated`` stays False for plain REJECTED (only
        REJECTED_FALLBACK sets it). These two columns close that gap.
        (On the UNCERTAIN/parse-failure path the approval status is already
        REJECTED_FALLBACK, so ``fallback_activated`` and
        ``executed_via_fallback`` are both True — consistent by
        construction; the divergence these columns expose is plain-REJECTED
        only.)

        OPT-IN, default-OFF by byte-identity necessity: the CSV fieldnames are
        derived from row keys, so the flag-OFF default emits neither key and
        frozen-baseline reruns (v21 / paper-3 mock) stay byte-identical.
        Frozen datasets therefore retain the documented REJECTED-row semantics;
        enable this for ALL NEW domains.
        """
        block = self._config.get("global_config", {}).get("audit", {})
        if not isinstance(block, dict):
            return False
        return bool(block.get("executed_skill_columns", False))

    def get_audit_param_columns(self) -> bool:
        """Phase 6W-B6: opt-in PROPOSED-parameter audit columns (default-OFF).

        When ``global_config.audit.param_columns: true``, every trace whose
        SkillProposal carries multi-field setpoints emits one key-gated
        ``proposed_param_<name>`` column per declared setpoint (excluding the
        legacy magnitude scalars). These record the proposal-stage value, kept
        distinct from the commit-stage ``world_<name>`` columns so the
        proposed-vs-executed (EXECUTED-ONLY) distinction is preserved.

        OPT-IN, default-OFF by byte-identity necessity (CSV fieldnames derive
        from row keys): flag-OFF emits no key, and frozen domains carry no
        parameters anyway, so v21 / paper-3 mock reruns stay byte-identical.
        """
        block = self._config.get("global_config", {}).get("audit", {})
        if not isinstance(block, dict):
            return False
        return bool(block.get("param_columns", False))

    def get_audit_initial_proposal_columns(self) -> bool:
        """P0-1a (2026-07-29): opt-in FIRST-ATTEMPT proposal columns (default-OFF).

        When ``global_config.audit.initial_proposal_columns: true``, every
        trace carries three key-gated columns recording the agent's FIRST
        proposal, before any governance retry:

        - ``initial_skill``  -- the skill proposed on attempt 0 (``None`` if
          that attempt failed to parse).
        - ``initial_labels`` -- the attempt-0 construct labels (the
          ``*_LABEL`` entries of the proposal's reasoning), pipe-joined as
          ``KEY=VALUE`` pairs, so appraisal drift across retries is visible.
        - ``attempt_skills`` -- every attempt's skill in order, pipe-joined
          (``""`` marks an unparsable attempt).

        WHY THIS EXISTS. ``skill_proposal`` is REASSIGNED on each governance
        retry (``_retry_loop._governance_retry_loop``), so both the CSV's
        ``proposed_skill`` and the JSONL's ``skill_proposal`` record the LAST
        (post-retry) proposal. Measured over the shipped corpus,
        ``proposed_skill == final_skill`` on 100% of rows in all three
        reference domains despite heavy retrying, which makes any
        "governance changed the action" metric defined as
        proposed != final identically zero. These columns restore the
        proposal-stage truth that comparison needs; pair them with
        ``executed_skill_columns`` (F3) to measure initial -> executed.

        OPT-IN, default-OFF by byte-identity necessity, exactly as for
        ``executed_skill_columns`` and ``param_columns``: CSV fieldnames derive
        from row keys, so flag-OFF emits no key and frozen-baseline reruns
        (v21 / paper-3 mock) stay byte-identical. Enable for ALL NEW runs.
        """
        block = self._config.get("global_config", {}).get("audit", {})
        if not isinstance(block, dict):
            return False
        return bool(block.get("initial_proposal_columns", False))

    def get_audit_advise_columns(self) -> bool:
        """P0-1c: opt-in ADVISORY audit columns + per-decision LLM call counter.

        When ``global_config.audit.advise_columns: true`` every trace carries the
        advisory payload (``advise_mode``, ``advisory_fired``, ``advisory_llm_calls``,
        ``advisory_rules``, ``advisory_skill_before`` / ``_after``,
        ``advisory_changed_action``, ``advisory_parse_failed``,
        ``advisory_reports_shown``, ``advisory_prompt_chars``, ``post_advice_rules``)
        plus an ``llm_calls`` entry inside ``llm_stats``.

        ``llm_calls`` is the load-bearing one: sample-matching between the advise and
        placebo arms is the assumption the whole enforcement decomposition rests on,
        so it is MEASURED per decision rather than asserted in the Methods.

        OPT-IN, default-OFF by byte-identity necessity, exactly as for
        ``executed_skill_columns`` and ``initial_proposal_columns``.
        """
        block = self._config.get("global_config", {}).get("audit", {})
        if not isinstance(block, dict):
            return False
        return bool(block.get("advise_columns", False))

    def get_validators_framework_aware_labels(self) -> bool:
        """PR-6: opt-in FRAMEWORK-AWARE construct labels (default-OFF).

        ``AgentValidator.get_label`` normalises every construct label through a
        hardcoded five-level VL/L/M/H/VH alphabet and, on a miss, truncates to
        the first two characters. Registration is generic — a domain declares
        ``psychological_framework: financial`` and the frameworks registry
        supplies ``AGGRESSIVE -> A`` / ``CONSERVATIVE -> C`` — but ENFORCEMENT
        is not: those labels truncate to ``"AG"`` / ``"CO"``, match nothing, and
        every rule written against them silently never fires. A rule that never
        fires and a rule that never triggers look identical in the audit trail.

        With ``global_config.validators.framework_aware_labels: true`` the
        validator resolves labels against the agent type's OWN registered
        alphabet, and a construct the model did not report makes its rules
        NOT FIRE while recording a ``construct_missing`` WARNING — never a
        fabricated middle value.

        Default-OFF by byte-identity necessity: the truncation defect is load
        bearing for the frozen corpora, so it stays reproducible until a run
        opts out of it.
        """
        block = self._config.get("global_config", {}).get("validators", {})
        if not isinstance(block, dict):
            return False
        return bool(block.get("framework_aware_labels", False))

    def get_governance_advise_mode(self) -> str:
        """PR-6: the SOFT-RULE channel — ``off`` (default) / ``record`` / ``feedback``.

        WARNING-level rules are the framework's advisory layer, and until this
        flag they had no channel anywhere: they do not block (by design), they
        are not rendered into any prompt (``_retry_loop`` comprehends only
        ``v.errors``), and the audit CSV's ``warning_rules`` column records
        them without recording whether anything was done with them.

        * ``record``   — soft findings are written to the audit row
          (``advise_findings``) and NEVER reach the model. Zero extra LLM
          calls, so behaviour is provably unchanged and the column measures
          the rules' firing rate on its own.
        * ``feedback`` — soft findings are additionally rendered into ONE
          extra, non-blocking prompt; the proposal is still APPROVED, and
          ``advise_shown`` records that the model was told, so a reader can
          measure whether advice changed the next action.

        Distinct from ``global_config.governance.advise`` (P0-1c), which
        DEMOTES rules authored as ERROR into advisories for an experiment arm.
        This key governs rules already authored as WARNING.
        """
        gov = self._config.get("global_config", {}).get("governance", {})
        if not isinstance(gov, dict):
            return "off"
        mode = str(gov.get("advise_mode", "off")).strip().lower()
        if mode not in ("off", "record", "feedback"):
            raise ValueError(
                f"global_config.governance.advise_mode {mode!r} is not one of "
                "['feedback', 'off', 'record']. Silently reading it as 'off' "
                "would produce a run with no soft-rule record and no error "
                "anywhere saying the channel was requested."
            )
        return mode

    def get_governance_retry_feedback_mode(self) -> str:
        """Red-team objection 3 ablation: ``full`` (default) / ``placebo`` / ``silent``.

        Governs ONLY the text of the ENFORCE governance retry loop
        (``RetryMixin._governance_retry_loop`` in ``broker/core/_retry_loop.py``),
        which fires after a BINDING validator rejection. It answers a
        red-team objection that the framework's measured effect could just be
        "the model gets another attempt", not "the model was told a specific
        rule". Under ``placebo`` the validator still decides WHEN a proposal
        is rejected — same rules, same retry schedule, same
        ``on_retry_exhausted`` fallback — but the LLM-facing retry prompt
        carries a fixed, content-free sentence instead of the rule id,
        reason, and suggestion. Under ``silent`` the retry prompt is the
        ORIGINAL prompt, byte-for-byte, on every retry attempt -- no header,
        no closer, no rules block, no governance framing at all -- so the
        only thing that can differ between attempts is the LLM's own
        sampling. That is a strictly more content-free control than
        ``placebo``, which still keeps the "your previous answer was not
        accepted" framing. The audit trail is UNCHANGED in all three modes:
        ``failed_rules`` / ``error_messages`` are derived from the real
        ``ValidationResult`` objects, never from the (possibly placebo'd or
        silenced) retry prompt text.

        Distinct from ``global_config.governance.advise`` (P0-1c) and
        ``global_config.governance.advise_mode`` (PR-6): both of those govern
        the separate, NON-BLOCKING advisory channel (demoted or
        WARNING-authored rules, at most one extra call, never opens this
        retry loop). This key governs the BLOCKING retry loop only, and the
        two mechanisms share no config, no state, and no code path — reusing
        the advisory placebo machinery here would silently couple two
        independently-toggled experiment arms.

        OPT-IN via an explicit ``full``/``placebo``/``silent`` string; default
        ``full`` reproduces the shipped retry prompt byte-for-byte, so every
        frozen baseline (v21 / paper-3 mock) stays byte-identical without the
        operator doing anything.
        """
        gov = self._config.get("global_config", {}).get("governance", {})
        if not isinstance(gov, dict):
            return "full"
        mode = str(gov.get("retry_feedback_mode", "full")).strip().lower()
        if mode not in ("full", "placebo", "silent"):
            raise ValueError(
                f"global_config.governance.retry_feedback_mode {mode!r} is not "
                "one of ['full', 'placebo', 'silent']. Silently reading it as "
                "'full' would run a published corpus WITHOUT the content-free "
                "retry text an operator explicitly asked for, with nothing in "
                "the run saying the config was misread."
            )
        return mode

    def get_governance_feasible_set_feedback(self) -> bool:
        """``global_config.governance.feasible_set_feedback`` (default False).

        When True, every governance retry prompt that follows an ERROR
        verdict ends its reports block with one line naming the list of
        actions that pass every rule this step: the engine
        re-runs the validators over each skill the agent may choose, with
        the same reasoning labels, without logging those probe runs as rule
        hits (``RetryMixin._probe_feasible_skills``). The line sits outside
        ``max_reports_per_retry`` truncation. With this flag on, the trace
        gains a ``feasible_by_attempt`` column (one group per retry prompt
        that carried the line). Custom validators must tolerate being called
        as a dry run (the probes call them; only GovernanceAuditor logging is
        muted). The probe keeps the rejected proposal's magnitude/parameters,
        so a magnitude-dependent check can judge another skill by them. False
        reproduces the shipped retry prompt byte-for-byte.
        """
        gov = self._config.get("global_config", {}).get("governance", {})
        if not isinstance(gov, dict):
            return False
        return bool(gov.get("feasible_set_feedback", False))

    def has_world_grounded_rules(self) -> bool:
        """PR-6: True iff the ACTIVE governance profile declares a world-grounded rule.

        Used to switch the grounding audit columns on automatically for a
        profile that has something to report. A profile with only self-report
        rules gains no columns, which is what keeps every frozen baseline
        byte-identical without an operator having to remember a second flag.

        W6: MEMOISED per resolved profile. This is called once per audit ROW on
        the frozen default path, and each call re-parses every thinking rule of
        every agent type — a whole rule set rebuilt to answer a question whose
        answer cannot change while the profile does not. The cache key is the
        profile because the answer genuinely differs between `strict` and
        `grounded_v1`, and both are reachable from one cached config instance in
        a single process (the tests do exactly that). Value-preserving by
        construction: the cached value is whatever the uncached scan returned.
        """
        profile = os.environ.get("GOVERNANCE_PROFILE", "default").lower()
        cache = self.__dict__.setdefault("_world_grounded_cache", {})
        if profile in cache:
            return cache[profile]
        skip = {"global_config", "shared", "metadata", "governance"}
        answer = False
        for agent_type in self._config:
            if agent_type in skip or not isinstance(self._config.get(agent_type), dict):
                continue
            try:
                rules = self.get_thinking_rules(agent_type)
            except Exception:
                # A profile undeclared for THIS agent type is not a reason to
                # fail the audit-column decision; the rule accessors raise on
                # that separately and much louder.
                continue
            if any(getattr(r, "grounding", "self_report") == "world" for r in rules):
                answer = True
                break
        cache[profile] = answer
        return answer

    def get_audit_grounding_columns(self) -> bool:
        """PR-6: opt-in GROUNDING audit columns (``rules_world_grounded`` / ``rules_self_report``).

        ON when ``global_config.audit.grounding_columns: true`` OR when the
        active profile declares at least one world-grounded rule. The second
        clause is the important one: a reader of a grounded run must be able to
        tell which of the rules that fired read the world and which read the
        model's own labels, and that is not knowable from ``rules_triggered``,
        which lists ids only.
        """
        block = self._config.get("global_config", {}).get("audit", {})
        if isinstance(block, dict) and bool(block.get("grounding_columns", False)):
            return True
        return self.has_world_grounded_rules()

    def get_audit_decider_columns(self) -> bool:
        """PR-8: opt-in DECIDER audit columns (``decider`` / ``decider_path``).

        ON when ``global_config.audit.decider_columns: true`` OR when any
        agent type in this config declares a ``decider:`` other than the
        default ``llm``. The second clause is the one that matters: the
        moment a run holds a mixed population, every row has to say what
        produced it, or a rule-based row and a model row are
        indistinguishable in the CSV and the comparison the mixed run
        exists to support cannot be made.

        A config where every type is (or defaults to) ``llm`` emits
        neither key, so CSV fieldnames — derived from row keys — are
        unchanged and every frozen corpus reruns byte-identically.
        """
        block = self._config.get("global_config", {}).get("audit", {})
        if isinstance(block, dict) and bool(block.get("decider_columns", False)):
            return True
        return self.has_non_default_deciders()

    def _agent_type_blocks(self):
        """Yield ``(name, block)`` for every AGENT-TYPE block, only.

        C1: a ``decider:`` under ``shared:`` or ``global_config:`` is read
        by nothing. Counting one as a declaration switched the audit
        columns on for a run whose every row was an LLM row — a corpus
        that then carries a ``decider`` column saying ``llm`` on every
        row and a config that looks mixed. ``validate_prompt`` warns
        about the misplaced key; this makes sure it does not also
        silently change the CSV.
        """
        for name, block in (self._config or {}).items():
            if not isinstance(block, dict):
                continue
            if str(name) in NON_AGENT_TOP_LEVEL_KEYS:
                continue
            yield str(name), block

    def declared_decider_names(self) -> List[str]:
        """Every decider name the AGENT-TYPE blocks resolve to, sorted.

        A type that declares nothing contributes ``llm``, because that is
        what it will run and what its rows will say. This is the only
        thing that knows about an arm BEFORE the run: the per-decider
        census in ``run_integrity.json`` can count the arms that produced
        rows, and needs this to name the one that produced none.

        A malformed declaration is skipped rather than raised on — this
        is called to build a side artifact, and the run is about to fail
        much louder at decider resolution.
        """
        from broker.agents.deciders import DEFAULT_DECIDER_NAME
        names = set()
        for name, _block in self._agent_type_blocks():
            try:
                names.add(self.get_decider(name).name)
            except ValueError:
                names.add(DEFAULT_DECIDER_NAME)
        return sorted(names)

    def has_non_default_deciders(self) -> bool:
        """Does any agent type in this config declare a non-``llm`` decider?

        Scans the AGENT-TYPE blocks only (C1) — see
        :meth:`_agent_type_blocks` for why a ``decider:`` under
        ``shared:`` must not count.
        """
        from broker.agents.deciders import DEFAULT_DECIDER_NAME
        cached = getattr(self, "_non_default_deciders", None)
        if isinstance(cached, bool):
            return cached
        answer = False
        for name, block in self._agent_type_blocks():
            if "decider" not in block:
                continue
            try:
                spec = self.get_decider(name)
            except ValueError:
                # A malformed value is not a reason to answer "no columns":
                # the run is about to fail at resolution anyway, and
                # answering yes keeps the failure legible.
                answer = True
                break
            if spec.name != DEFAULT_DECIDER_NAME:
                answer = True
                break
        self._non_default_deciders = answer
        return answer

    def get_decider(self, agent_type: str):
        """Return this agent type's declared decider as a ``DeciderSpec``.

        ``decider:`` accepts a bare registered name or a
        ``{name, params}`` mapping::

            household_owner:
              decider: llm                      # the default; may be omitted
            household_renter:
              decider:
                name: rule_based
                params:
                  default_action: do_nothing
                  rules: [...]

        Absent means ``llm``, and the resolved callable is then the
        identical object ``ExperimentRunner.get_llm_invoke`` returns —
        so adding this key to the schema changed nothing for any config
        that does not use it.

        Raises ``ValueError`` on a malformed value rather than reading
        it as the default: a run that silently ignored a broken
        ``decider:`` would be an all-LLM run wearing a mixed-population
        config, and nothing in its artifacts would say so.
        """
        from broker.agents.deciders import parse_decider_spec
        cfg = self.get(agent_type)
        return parse_decider_spec(
            cfg.get("decider"), where=f"{agent_type}.decider"
        )

    def get_audit_corrected_status_columns(self) -> bool:
        """PR-3 (2026-09-01): opt-in CORRECTED status/truth columns (default-OFF).

        When ``global_config.audit.corrected_status_columns: true`` the audit
        plane stops reporting the *blocked proposal* as if it were the
        outcome, and starts reporting what the broker actually did:

        - ``executed_skill`` / ``executed_via_fallback`` — as for
          ``executed_skill_columns`` (F3); this flag implies them, so a run
          need not set both.
        - ``execution_path`` (NEW column) — one of ``approved`` /
          ``rejected_default`` / ``rejected_proposal`` / ``fallback`` /
          ``aborted`` / ``not_executed``. It names the remap rule that
          produced ``executed_skill``, so an analyst never has to re-derive
          it from ``status`` plus the domain's ``on_retry_exhausted`` policy.
        - ``fallback_activated`` — derived from the EXECUTED skill instead of
          the blocked one. Flag-OFF it reads ``approval_status ==
          "REJECTED_FALLBACK"``, which is False on a plain-``REJECTED`` row
          even though the registry default is exactly what ran.
        - ``rules_personal_hit`` / ``_social_`` / ``_thinking_`` /
          ``_semantic_`` — INFERRED from tier / validator name / rule id under
          ``AgentValidator`` (which sets ``metadata["tier"]``, never
          ``metadata["category"]``), instead of structurally zero. It is an
          inference, not a declaration: only the categories a producer's tier
          labels can express will ever populate, so a bucket reading zero can
          mean "no rule fired" OR "no tier label named this category". Rules
          whose category cannot be named — identity and other precondition
          rules among them — are NOT filed under a plausible bucket; they are
          counted as ``rules_uncategorised_total`` /
          ``rules_uncategorised_ids`` in ``run_integrity.json`` and logged
          once per run. Read those alongside the columns.
        - ``mem_top_emotion`` / ``mem_top_source`` — ``"unobserved"`` when the
          retrieved memory records carry no such key, instead of the
          ``"neutral"`` / ``"personal"`` literals that are indistinguishable
          in the CSV from a genuine unanimous mode.
        - one sentinel row per step that returned ``SkillOutcome.ABORTED``
          (unparsable output after retries), so per-agent-year row counts are
          conserved between arms instead of silently shrinking on the arm
          with more parse failures.

        OPT-IN, default-OFF by byte-identity necessity, exactly as for
        ``executed_skill_columns`` / ``initial_proposal_columns`` /
        ``advise_columns``: this flag both ADDS a column and CHANGES the
        values of four existing ones, so every published corpus must be able
        to reproduce byte-identically with it absent. Enable for ALL NEW runs.
        """
        block = self._config.get("global_config", {}).get("audit", {})
        if not isinstance(block, dict):
            return False
        return bool(block.get("corrected_status_columns", False))

    def get_parsing_strict_layers(self) -> bool:
        """PR-4 (2026-09-01): opt-in HARDENED parsing layers (default-OFF).

        When ``global_config.parsing.strict_layers: true``, ``UnifiedAdapter``
        stops treating a stray digit anywhere in the model's free text as a
        reasoned decision: every digit route that is not scoped to a decision
        line is disabled (each suppression recorded as a ``parsing_warnings``
        entry naming the candidate it rejected), the two decision-line digit
        routes survive re-anchored so the digit must BE the decision value
        rather than merely appear on the line, and a row an APPROVED proposal
        owes to the parser's own domain-default substitution is reported as
        ``decision_source == "default_substituted"`` instead of
        ``"llm_reasoned"``.

        Under ``parsing.strict_mode: true`` (the default) a suppressed row
        returns ``None`` and retries, ending ``REJECTED_FALLBACK`` or an
        ``ABORTED`` sentinel if every retry also fails. Under
        ``parsing.strict_mode: false`` a suppressed row falls through to
        ``parsing.default_skill`` instead, carrying the suppression warning.

        OPT-IN, default-OFF by byte-identity necessity, exactly as for the
        ``audit.*`` flags above: this changes ``parse_layer`` /
        ``parse_confidence`` / ``parsing_warnings`` values and the JSONL-only
        ``decision_source`` field on rows that would otherwise be
        digit-inferred, so every published corpus must reproduce
        byte-identically with it absent. Enable together with
        ``audit.corrected_status_columns`` — otherwise a step that now aborts
        instead of guessing writes no audit row at all, shrinking the
        denominator of whichever arm the model struggled with more.

        Full route-by-route behaviour, the ``strict_mode`` interaction, and
        the YAML surface: ``docs/references/yaml_configuration_reference.md``
        §2.1.7. Column semantics and the readiness-report counters
        (``parse_layer_digit_share`` / ``parse_layer_default_share``):
        ``docs/AUDIT_SCHEMA.md``.
        """
        block = self._config.get("global_config", {}).get("parsing", {})
        if not isinstance(block, dict):
            return False
        return bool(block.get("strict_layers", False))

    def get_coupling_context_contract(self) -> bool:
        """PR-9 coupling-retrofit (F1): opt-in fail-loud guard on a domain
        environment's per-agent CONTEXT handoff (default-OFF).

        When ``global_config.coupling.context_contract: true``, a domain
        environment that implements the pattern checks every physical-state
        field its ``get_agent_context()`` reads against a DECLARED
        ``CouplingContract`` before applying the legacy ``.get(key, 0)``
        default, and raises ``CouplingViolation`` naming any field that is
        genuinely absent instead of silently manufacturing a
        plausible-looking zero. The irrigation domain is the first consumer
        (fifteen fields — precipitation, lake_mead_level, water_right and
        twelve more; the full list is
        ``examples.irrigation_abm.irrigation_coupling.
        IRRIGATION_CONTEXT_FIELD_SOURCES``), which is why the key is named
        for the CONTEXT handoff and not for that domain.

        WHAT THE FLAG BUYS, precisely (review W3): at contract construction,
        direction + double-count (``CouplingContract.__post_init__``) and
        unit-declared + ``lo <= hi`` (``VarSpec.__post_init__``); at runtime,
        presence + finite numeric range + declared dtype, per field, per
        call. ``check_units()`` and ``check_cadence()`` are NOT called on
        this path and no unit CONVERSION is verified — a wrong-unit value
        inside the declared range passes.

        Distinct from the existing two-layer ``coupling.enable`` flag
        (``broker/coupling/flag.py``): that flag governs whether
        ``EnvironmentCouplingAdapter`` wraps ``sim_engine`` at all, a shape
        a per-agent ``get_agent_context()`` accessor does not fit (see the
        module docstring of ``irrigation_coupling.py``). This is a plain
        single-layer flag, same pattern as ``get_parsing_strict_layers``
        above — no DomainPack fallback, because a fail-loud guard opt-in
        has no meaningful non-YAML default beyond OFF.

        OPT-IN, default-OFF by byte-identity necessity: with the flag OFF
        the environment never constructs the contract or calls the guard,
        and every field defaults exactly as before, so v21 and every other
        frozen irrigation corpus reproduces byte-identically with this key
        absent. (Not "never imports ``broker.coupling``" — review W6: the
        provenance hook ``get_coupling_retrofit_metadata`` imports the
        contract module on EVERY run, flag or no flag, to report the field
        list. Importing it has no effect on behaviour; constructing the
        contract and running the guard are what the flag gates.)
        """
        block = self._config.get("global_config", {}).get("coupling", {})
        if not isinstance(block, dict):
            return False
        return bool(block.get("context_contract", False))

    def get_governance_on_retry_exhausted(self) -> str:
        """What executes when governance retries are exhausted: a MODEL-BUILDER choice.

        ``"default"`` (the default) — execute the registry ``default_skill``. This is
        the historical, hardcoded behaviour and stays bit-for-bit unchanged.

        ``"keep_proposal"`` — execute the agent's FINAL FAILED PROPOSAL instead.

        Why this is configurable rather than a framework constant: the two shipped
        water domains want opposite things. The flood study treats a persistent
        rule-violating choice as the observable it exists to measure, so overwriting
        it with a default destroys the datum. Irrigation is an enforced-allocation
        domain that would not converge if agents could keep taking water they were
        denied, so it wants the default.

        SCOPE. ``keep_proposal`` applies ONLY to ``SkillOutcome.REJECTED`` — a real
        proposal that failed validation. ``UNCERTAIN`` (the parser never produced a
        usable proposal) always uses the default: there is no agent choice to
        preserve, and executing a parser artefact is strictly worse.

        SAFETY, and read this before enabling it. ``keep_proposal`` executes an
        action that JUST FAILED VALIDATION, unvalidated. That directly trips the
        revisit trigger of accepted risk AR-1 in ``broker/INVARIANTS.md`` ("any
        domain configures a substantive, state- or world-mutating fallback"), whose
        safety argument was that every shipped default is a no-op. Enabling it is
        therefore a statement that, for THIS domain, the rules that can block are
        behavioural-theory rules whose violation is incoherent but possible — not
        world-affordance rules whose violation is impossible. A domain that mixes
        both must either keep the default policy or guarantee an independent
        execution-layer guard.

        It is REFUSED outright when the coupling layer is enabled (AR-2): a rejected
        proposal that reaches ``ControlSink.apply`` / ``commit_world_delta`` would
        commit a rule-violating value to a physical model with no governance at all,
        which is the one thing this framework claims it does not allow.
        """
        gov = self._config.get("global_config", {}).get("governance", {})
        if not isinstance(gov, dict):
            return "default"
        policy = str(gov.get("on_retry_exhausted", "default")).strip().lower()
        if policy not in {"default", "keep_proposal"}:
            raise ValueError(
                f"global_config.governance.on_retry_exhausted {policy!r} "
                "not in ['default', 'keep_proposal']"
            )
        if policy == "keep_proposal":
            coupling = self._config.get("global_config", {}).get("coupling", {})
            if isinstance(coupling, dict) and coupling.get("enable", False):
                raise ValueError(
                    "global_config.governance.on_retry_exhausted='keep_proposal' is "
                    "not permitted while global_config.coupling.enable is true. A "
                    "rejected proposal would reach the external model's ControlSink "
                    "ungoverned and commit a rule-violating value to the world "
                    "(broker/INVARIANTS.md accepted risk AR-2)."
                )
        return policy

    def get_governance_advise(self) -> Optional[Dict[str, Any]]:
        """P0-1c: the ADVISE arm spec, or None (default) meaning OFF.

        YAML surface, entire block absent by default::

            global_config:
              governance:
                advise:
                  mode: advise          # advise | placebo | resample | wrapper | off
                  rule_ids: [rule_a, rule_b]
                  placebo_text: "A governance rule was triggered by this decision."

        ``rule_ids`` is an explicit ALLOWLIST of rule ids whose blocking results are
        demoted to non-blocking advisories (see :mod:`broker.core._advise`). It fails
        CLOSED — an unlisted rule keeps blocking — and it is keyed on rule id rather
        than validator name so it also reaches domain custom validators.

        Validated eagerly and loudly, because a silently-misspelled arm config would
        produce a scientifically wrong run that still looks healthy:
        unknown mode, non-list / empty ``rule_ids``, and any id in
        :data:`broker.core._advise.ADVISE_DENY` all raise ValueError here.

        Default-OFF by byte-identity necessity: no block -> None -> empty allowlist
        -> ``demote()`` returns the same list object -> frozen baselines unchanged.
        """
        gov = self._config.get("global_config", {}).get("governance", {})
        if not isinstance(gov, dict):
            return None
        spec = gov.get("advise")
        if spec is None:
            return None
        if not isinstance(spec, dict):
            raise ValueError(
                f"global_config.governance.advise must be a mapping, got {type(spec).__name__}"
            )
        mode = str(spec.get("mode", "advise")).strip().lower()
        valid_modes = {"advise", "placebo", "resample", "wrapper", "off"}
        if mode not in valid_modes:
            raise ValueError(
                f"global_config.governance.advise.mode {mode!r} not in {sorted(valid_modes)}"
            )
        rule_ids = spec.get("rule_ids")
        if mode != "off":
            if not isinstance(rule_ids, list) or not rule_ids:
                raise ValueError(
                    "global_config.governance.advise.rule_ids must be a non-empty list "
                    f"when mode={mode!r}; got {rule_ids!r}"
                )
            from broker.core._advise import ADVISE_DENY
            denied = sorted(set(map(str, rule_ids)) & ADVISE_DENY)
            if denied:
                raise ValueError(
                    f"global_config.governance.advise.rule_ids may not contain {denied} "
                    "— these are hard feasibility gates that must always block."
                )
        return {
            "mode": mode,
            # mode="off" FORCES an empty allowlist. Without this, an arm authored as
            # the no-op control by flipping only `mode` while leaving `rule_ids`
            # populated would still demote those rules at _run_validators -- they
            # would stop blocking AND the advisory pass would never fire, so the
            # model would be told nothing. That is precisely the "WARNING has no
            # channel to the model" defect this whole feature exists to remove,
            # silently reintroduced inside the control arm.
            "rule_ids": [] if mode == "off" else [str(r) for r in (rule_ids or [])],
            "placebo_text": spec.get(
                "placebo_text", "A governance rule was triggered by this decision."
            ),
        }

    def get_governance_intervention_framing(self) -> str:
        """P0-1c: retry/advisory prompt framing — ``legacy`` (default) or ``neutral``.

        ``legacy`` reproduces the shipped retry prompt byte-for-byte and stays the
        default forever, so every published arm-C prompt is unchanged.

        ``neutral`` is opt-in and used by the NEW 7-arm runs. It replaces the
        "was BLOCKED" verb with a disposition-free one and suppresses the optional
        Suggestion line, so the text an agent sees is IDENTICAL in the advise,
        placebo and enforce arms — making the enforce-minus-advise contrast pure
        enforcement with zero wording delta.
        """
        gov = self._config.get("global_config", {}).get("governance", {})
        if not isinstance(gov, dict):
            return "legacy"
        framing = str(gov.get("intervention_framing", "legacy")).strip().lower()
        if framing not in {"legacy", "neutral"}:
            raise ValueError(
                f"global_config.governance.intervention_framing {framing!r} "
                "not in ['legacy', 'neutral']"
            )
        return framing

    def get_llm_retries(self, default: int = 2) -> int:
        """Get max retries for raw LLM invocation (Global > Shared > Default)."""
        # 1. Check Global Config
        global_llm = self._config.get("global_config", {}).get("llm", {})
        return global_llm.get("max_retries", self._config.get("shared", {}).get("llm", {}).get("max_retries", default))
    
    def get_reflection_config(self) -> dict:
        """Get reflection configuration (Global > Shared > Default).

        Documented top-level keys: ``interval``, ``batch_size``,
        ``importance_boost`` (the
        :class:`broker.components.cognitive.reflection.ReflectionEngine`
        ``insight_importance_boost`` kwarg), and Phase 6L-D
        (2026-05-23) ``base_importance`` (the
        :meth:`ReflectionEngine.compute_dynamic_importance` fallback
        when no DomainPack adapter supplies one).

        Documented sub-blocks:
        - ``triggers``: read by
          :meth:`ReflectionEngine.load_trigger_config`; carries
          ``crisis`` / ``periodic_interval`` / ``decision_types`` /
          ``institutional_threshold`` (default 0.05) / ``method`` /
          ``batch_size`` / ``importance_boost`` (default 0.85; this is
          ``ReflectionTriggerConfig.importance_boost``, distinct from
          the top-level ``importance_boost`` above).
        - ``persona_instruction``, ``questions`` — pre-existing
          reflection-prompt knobs; for reflection questions prefer
          :meth:`get_reflection_questions` (per-agent-type +
          DomainPack fallback).

        The merge copies the WHOLE ``reflection`` YAML block, so any
        documented or future key passes through automatically. Cognitive
        knobs stay YAML-only by user direction (Phase 6L plan) — no
        DomainPack hook for reflection.

        Note (Phase 6L-D): ``base_importance`` is surfaced in the
        defaults dict and pass-through-merged from YAML, but no
        production caller currently threads it into
        ``ReflectionEngine.compute_dynamic_importance(base_importance=...)``.
        End-to-end wiring is deferred — the accessor declares the
        interface so YAML edits do not silently no-op; the call-site
        update lands when a non-default value is genuinely needed.
        """
        defaults = {
            "interval": 1,
            "batch_size": 10,
            "importance_boost": 0.9,
            # Phase 6L-D (2026-05-23): surfaced so callers reading
            # ``get_reflection_config()`` know the key is recognised
            # and can override it via YAML. Matches the constructor
            # default of ``ReflectionEngine.compute_dynamic_importance``.
            "base_importance": 0.9,
        }
        
        # 1. Global Config
        global_refl = self._config.get("global_config", {}).get("reflection", {}) or {}
        
        # 2. Shared (Legacy Fallback)
        shared_refl = self._config.get("shared", {}).get("reflection", {}) or {}
        
        # Merge: Global > Shared > Default
        merged = defaults.copy()
        merged.update(shared_refl) # Apply legacy shared
        merged.update(global_refl) # Apply new global

        return merged

    def get_retrieval_config(self) -> dict:
        """Get skill-retrieval tuning (Global YAML > Shared YAML > DomainPack > Default).

        Returns dict with keys: ``top_n`` (int — candidate skills surfaced
        to the LLM) and ``min_score`` (float — relevance cutoff).

        Resolution order, lowest precedence first:
          1. Framework defaults (top_n=3, min_score=0.05) — byte-identical
             to the pre-6H hardcoded SkillRetriever construction.
          2. DomainPack ``retrieval_policy()`` — a pack ships its own
             defaults (Phase 6H v2 hook).
          3. Legacy ``shared.governance.retrieval``.
          4. ``global_config.governance.retrieval`` (most specific).
        """
        defaults = {"top_n": 3, "min_score": 0.05}

        # DomainPack-supplied policy (domain selector lives under
        # global_config.governance.domain).
        pack_policy: dict = {}
        domain = (
            self._config.get("global_config", {})
            .get("governance", {})
            .get("domain")
        )
        if domain:
            # Lazy import — keeps agent_config import-cycle-free.
            from broker.domains.registry import DomainPackRegistry
            pack_policy = (
                DomainPackRegistry.get_or_default(domain).retrieval_policy()
                or {}
            )

        global_ret = (
            self._config.get("global_config", {})
            .get("governance", {})
            .get("retrieval", {})
        ) or {}
        shared_ret = (
            self._config.get("shared", {})
            .get("governance", {})
            .get("retrieval", {})
        ) or {}

        merged = defaults.copy()
        merged.update(pack_policy)   # DomainPack over framework default
        merged.update(shared_ret)    # legacy shared over pack
        merged.update(global_ret)    # global YAML over all

        # Coerce + validate so a malformed config value fails here with a
        # clear message, not later as a TypeError deep inside SkillRetriever
        # (slice / comparison on a non-numeric top_n / min_score).
        try:
            merged["top_n"] = int(merged["top_n"])
            merged["min_score"] = float(merged["min_score"])
        except (TypeError, ValueError) as e:
            raise ValueError(
                "governance.retrieval: 'top_n' must be an int and "
                "'min_score' must be a float — got "
                f"top_n={merged.get('top_n')!r}, "
                f"min_score={merged.get('min_score')!r}"
            ) from e
        return merged

    def get_drift_config(self) -> dict:
        """Get population-drift-monitor tuning (Global YAML > Shared
        YAML > DomainPack > Default). Phase 6L-A (2026-05-22).

        Returns dict with keys: ``entropy_threshold`` /
        ``stagnation_threshold`` / ``collapse_threshold`` /
        ``jaccard_stagnation_threshold`` (floats) and
        ``history_window`` (int). Coercion happens here so a malformed
        YAML value fails with a clear message rather than a TypeError
        deep inside DriftDetector.

        Resolution order, lowest precedence first:
          1. Framework defaults (entropy=0.5, stagnation=0.6,
             collapse=0.9, jaccard_stagnation=0.8, history_window=5)
             — byte-identical to the pre-6L-A
             :class:`broker.components.analytics.drift.DriftDetector`
             constructor defaults.
          2. DomainPack ``drift_policy()`` — a pack ships its own
             defaults.
          3. Legacy ``shared.governance.drift``.
          4. ``global_config.governance.drift`` (most specific).

        Mirrors :meth:`get_retrieval_config` (Phase 6H Item 3 template).
        """
        defaults = {
            "entropy_threshold": 0.5,
            "stagnation_threshold": 0.6,
            "collapse_threshold": 0.9,
            "jaccard_stagnation_threshold": 0.8,
            "history_window": 5,
        }

        # DomainPack-supplied policy (domain selector under
        # global_config.governance.domain — same path as retrieval).
        pack_policy: dict = {}
        domain = (
            self._config.get("global_config", {})
            .get("governance", {})
            .get("domain")
        )
        if domain:
            # Lazy import — keeps agent_config import-cycle-free.
            from broker.domains.registry import DomainPackRegistry
            pack_policy = (
                DomainPackRegistry.get_or_default(domain).drift_policy()
                or {}
            )

        global_drift = (
            self._config.get("global_config", {})
            .get("governance", {})
            .get("drift", {})
        ) or {}
        shared_drift = (
            self._config.get("shared", {})
            .get("governance", {})
            .get("drift", {})
        ) or {}

        merged = defaults.copy()
        merged.update(pack_policy)    # DomainPack over framework default
        merged.update(shared_drift)   # legacy shared over pack
        merged.update(global_drift)   # global YAML over all

        # Coerce + validate so malformed config fails with a clear
        # message, not later as a TypeError inside DriftDetector.
        try:
            for k in (
                "entropy_threshold",
                "stagnation_threshold",
                "collapse_threshold",
                "jaccard_stagnation_threshold",
            ):
                merged[k] = float(merged[k])
            merged["history_window"] = int(merged["history_window"])
        except (TypeError, ValueError) as e:
            got = {k: merged.get(k) for k in defaults}
            raise ValueError(
                "governance.drift: all threshold keys must be float "
                f"and history_window must be int — got {got}"
            ) from e
        return merged

    def get_population_governance_config(self) -> dict:
        """Get population-governance threshold tuning (Global YAML >
        Shared YAML > DomainPack > Default). Phase 6L-B (2026-05-22).

        Returns dict with keys (all floats): ``echo_threshold``,
        ``entropy_threshold``, ``deadlock_threshold`` (the three
        :class:`broker.validators.governance.cross_agent_validator.CrossAgentValidator`
        knobs) and ``quorum_threshold`` (the
        :class:`broker.validators.agent.council.CouncilValidator`
        MAJORITY-mode quorum). Coercion happens here so a malformed
        YAML value fails with a clear message rather than a TypeError
        deep inside the validators.

        Resolution order, lowest precedence first:
          1. Framework defaults — byte-identical to the pre-6L-B
             ``CrossAgentValidator(...)`` and
             ``CouncilValidator(..., consensus_mode='MAJORITY')``
             constructor defaults.
          2. DomainPack ``population_governance_policy()``.
          3. Legacy ``shared.governance.population``.
          4. ``global_config.governance.population`` (most specific).

        Mirrors :meth:`get_retrieval_config` and
        :meth:`get_drift_config` (Phase 6H Item 3 template).
        """
        defaults = {
            "echo_threshold": 0.8,
            "entropy_threshold": 0.5,
            "deadlock_threshold": 0.5,
            "quorum_threshold": 0.5,
        }

        # DomainPack-supplied policy (domain selector under
        # global_config.governance.domain — same path as retrieval / drift).
        pack_policy: dict = {}
        domain = (
            self._config.get("global_config", {})
            .get("governance", {})
            .get("domain")
        )
        if domain:
            # Lazy import — keeps agent_config import-cycle-free.
            from broker.domains.registry import DomainPackRegistry
            pack_policy = (
                DomainPackRegistry.get_or_default(domain)
                .population_governance_policy()
                or {}
            )

        global_pop = (
            self._config.get("global_config", {})
            .get("governance", {})
            .get("population", {})
        ) or {}
        shared_pop = (
            self._config.get("shared", {})
            .get("governance", {})
            .get("population", {})
        ) or {}

        merged = defaults.copy()
        merged.update(pack_policy)   # DomainPack over framework default
        merged.update(shared_pop)    # legacy shared over pack
        merged.update(global_pop)    # global YAML over all

        # Coerce + validate so a malformed config value fails here with
        # a clear message, not later as a TypeError inside the
        # CrossAgentValidator / CouncilValidator comparisons.
        try:
            for k in defaults:
                merged[k] = float(merged[k])
        except (TypeError, ValueError) as e:
            got = {k: merged.get(k) for k in defaults}
            raise ValueError(
                "governance.population: every threshold must be a float "
                f"— got {got}"
            ) from e
        return merged

    def get_bridge_importance_config(self) -> dict:
        """Get MemoryBridge resolution-importance policy (Global YAML >
        Shared YAML > DomainPack > Default). Phase 6L-D (2026-05-23).

        Returns dict with keys (floats): ``approved`` (default 0.6) and
        ``denied`` (default 0.75). The ``denied >= approved`` asymmetry
        is the documented "denials more memorable" behavioural claim
        from ``MemoryBridge.store_resolution`` — domains should preserve
        it unless they have an explicit rationale to invert.

        Resolution order, lowest precedence first:
          1. Framework defaults (approved=0.6, denied=0.75) —
             byte-identical to the pre-6L-D
             ``MemoryBridge.store_resolution`` literals.
          2. DomainPack ``bridge_importance_policy()``.
          3. Legacy ``shared.governance.memory.resolution_importance_policy``.
          4. ``global_config.governance.memory.resolution_importance_policy``.

        Mirrors :meth:`get_retrieval_config` / :meth:`get_drift_config`
        / :meth:`get_population_governance_config` (Phase 6H Item 3
        template).
        """
        defaults = {"approved": 0.6, "denied": 0.75}

        # DomainPack-supplied policy.
        pack_policy: dict = {}
        domain = (
            self._config.get("global_config", {})
            .get("governance", {})
            .get("domain")
        )
        if domain:
            # Lazy import — keeps agent_config import-cycle-free.
            from broker.domains.registry import DomainPackRegistry
            pack_policy = (
                DomainPackRegistry.get_or_default(domain)
                .bridge_importance_policy()
                or {}
            )

        global_pol = (
            self._config.get("global_config", {})
            .get("governance", {})
            .get("memory", {})
            .get("resolution_importance_policy", {})
        ) or {}
        shared_pol = (
            self._config.get("shared", {})
            .get("governance", {})
            .get("memory", {})
            .get("resolution_importance_policy", {})
        ) or {}

        merged = defaults.copy()
        merged.update(pack_policy)   # DomainPack over framework default
        merged.update(shared_pol)    # legacy shared over pack
        merged.update(global_pol)    # global YAML over all

        # Coerce + validate so a malformed config value fails here
        # with a clear message, not later inside MemoryBridge.
        try:
            for k in defaults:
                merged[k] = float(merged[k])
        except (TypeError, ValueError) as e:
            got = {k: merged.get(k) for k in defaults}
            raise ValueError(
                "governance.memory.resolution_importance_policy: "
                f"every value must be a float — got {got}"
            ) from e
        # Asymmetry guard: the 'denied > approved' (denials more
        # memorable) split is the documented design rationale —
        # equal values are permitted but strict inversion requires
        # an explicit domain rationale. Catch the inversion at
        # config-load time with a clear message rather than silently
        # flipping the rationale at runtime.
        if merged["denied"] < merged["approved"]:
            raise ValueError(
                "governance.memory.resolution_importance_policy: "
                f"'denied' ({merged['denied']}) must be >= 'approved' "
                f"({merged['approved']}); inverting the 'denials more "
                "memorable' asymmetry requires an explicit domain "
                "rationale (see MemoryBridge.store_resolution)."
            )
        # Strip any YAML extras so downstream consumers see only the
        # two canonical keys.
        return {k: merged[k] for k in defaults}

    def get_reflection_questions(self, agent_type: str) -> List[str]:
        """Resolve reflection questions for an agent type (Phase 6H Item 4).

        A domain author customises reflection purely by editing
        ``agent_types.yaml`` — no DomainPack code required. Precedence,
        highest first:

          1. ``<agent_type>.reflection.questions`` — per-agent-type YAML
             (a multi-agent domain gives each agent type its own set).
          2. ``global_config.reflection.questions`` — domain-wide YAML.
          3. ``shared.reflection.questions`` — legacy domain-wide YAML.
          4. ``DomainPack.reflection_questions()`` — programmatic,
             domain-wide (for packaged domains).
          5. ``[]`` — caller applies the generic
             ``_DEFAULT_REFLECTION_QUESTIONS`` fallback.

        Returns an empty list when nothing is configured; the reflection
        prompt builders fall back to the domain-neutral default.

        Note: an explicit empty ``questions: []`` does NOT suppress
        reflection questions -- it is falsy, so resolution falls through
        to the next scope (ultimately the generic default). To use the
        generic default, omit the ``questions`` key entirely.
        """
        # 1. per-agent-type block
        block = self.get(agent_type) if agent_type else {}
        if isinstance(block, dict):
            per_type = (block.get("reflection", {}) or {}).get("questions")
            if per_type:
                return list(per_type)
        # 2-3. domain-wide YAML (global_config preferred, shared legacy)
        for scope in ("global_config", "shared"):
            q = (
                (self._config.get(scope, {}) or {})
                .get("reflection", {}) or {}
            ).get("questions")
            if q:
                return list(q)
        # 4. DomainPack hook (domain selector under global_config.governance)
        domain = (
            self._config.get("global_config", {})
            .get("governance", {})
            .get("domain")
        )
        if domain:
            # Lazy import — keeps agent_config import-cycle-free.
            from broker.domains.registry import DomainPackRegistry
            pack_q = DomainPackRegistry.get_or_default(domain).reflection_questions()
            if pack_q:
                return list(pack_q)
        # 5. nothing configured — caller applies the generic fallback
        return []

    def get_valid_actions(self, agent_type: str) -> List[str]:
        """Get all valid action IDs and aliases for agent type."""
        cfg = self.get(agent_type)
        # Check both top-level and nested parsing.actions
        actions = cfg.get("actions", cfg.get("parsing", {}).get("actions", []))
        valid = []
        for action in actions:
            valid.append(action["id"])
            valid.extend(action.get("aliases", []))
        return valid
    
    def get_action_alias_map(self, agent_type: str) -> Dict[str, str]:
        """Get a mapping from aliases (and canonical IDs) to canonical skill IDs."""
        cfg = self.get(agent_type)
        # Check both top-level and nested parsing.actions
        actions = cfg.get("actions", cfg.get("parsing", {}).get("actions", []))
        alias_map = {}
        for action in actions:
            canonical = action["id"]
            # Map canonical to itself
            alias_map[canonical.lower()] = canonical
            # Map all aliases to canonical
            for alias in action.get("aliases", []):
                alias_map[alias.lower()] = canonical
        return alias_map

    
    def get_validation_rules(self, agent_type: str) -> Dict[str, ValidationRule]:
        """Get validation rules as dict."""
        cfg = self.get(agent_type)
        rules = cfg.get("validation_rules", {})
        return {
            name: ValidationRule(
                name=name,
                param=rule.get("param", ""),
                min_val=rule.get("min"),
                max_val=rule.get("max"),
                max_delta=rule.get("max_delta"),
                level=rule.get("level", "WARNING"),
                message=rule.get("message", "")
            )
            for name, rule in rules.items()
        }
    
    def get_identity_rules(self, agent_type: str) -> List[CoherenceRule]:
        """Get identity/status rules."""
        cfg = self.get(agent_type)
        # Guarded too: this accessor runs on EVERY step, whereas the thinking-rule
        # accessor is skipped when a proposal's reasoning failed to parse. Guarding
        # only that one would leave an undeclared profile reachable for a whole run.
        profile = self._resolve_governance_profile(agent_type, cfg)

        # Task 015 fix: Look in both locations for governance rules
        # 1. Top-level governance section: governance.{profile}.{agent_type}.identity_rules
        # 2. Agent-type section: {agent_type}.governance.{profile}.identity_rules (legacy)
        top_level_gov = self._config.get("governance", {})
        rules = top_level_gov.get(profile, {}).get(agent_type, {}).get("identity_rules", [])

        # Fallback to agent-type embedded governance (legacy format)
        if not rules:
            gov = cfg.get("governance", {})
            rules = gov.get(profile, {}).get("identity_rules", cfg.get("identity_rules", {}))
        
        # DEBUG
        # print(f"DEBUG_CONFIG: Loading identity_rules for {agent_type} (Profile: {profile}). Found {len(rules)} entries.")
            
        if isinstance(rules, dict):
            rules_list = [{"id": k, **v} for k, v in rules.items()]
        else:
            rules_list = rules
            
        return [
            CoherenceRule(
                id=rule.get("id", "unknown"),
                construct=rule.get("construct", rule.get("id")),
                conditions=rule.get("conditions"),
                blocked_skills=rule.get("blocked_skills"),
                level=rule.get("level", "ERROR"),
                message=rule.get("message", ""),
                metadata={"precondition": rule.get("precondition")},
                # P1-f: identity rules read a physical precondition the model
                # cannot author, so `resolve_rule_grounding` reports them as
                # world-grounded. Unstamped, they defaulted to `self_report` and
                # every identity block landed in the wrong audit column.
                grounding=resolve_rule_grounding(rule),
            )
            for rule in rules_list
        ]

    def validate_schema(self, agent_type: str) -> List[str]:
        """
        Validate that the configuration for an agent type is consistent.
        Returns a list of error/warning messages.
        """
        issues = []
        cfg = self.get(agent_type)
        if not cfg:
            return [f"Agent type '{agent_type}' not found in config."]

        # 1. Check Profile
        profile = os.environ.get("GOVERNANCE_PROFILE", "default").lower()
        gov = cfg.get("governance", {})
        top_level_gov = self._config.get("governance", {})
        top_level_profile = top_level_gov.get(profile, {}) if profile != "default" else {}
        has_top_level = agent_type in top_level_profile
        if profile != "default" and profile not in gov and not has_top_level:
            issues.append(f"WARNING: Governance profile '{profile}' not found for '{agent_type}'. Falling back to default.")

        # 2. Check Thinking Rules vs Constructs
        config_parsing = self.get_parsing_config(agent_type)
        constructs = config_parsing.get("constructs", {})
        rules = self.get_thinking_rules(agent_type)
        for rule in rules:
            target_constructs = []
            # For legacy format: id IS the construct name if no explicit construct field
            c_field = rule.construct
            if c_field and not rule.conditions:
                target_constructs.append(c_field)
            
            if rule.conditions:
                for cond in rule.conditions:
                    if "construct" in cond:
                        target_constructs.append(cond["construct"])
            
            for c in target_constructs:
                if c not in constructs:
                    issues.append(f"ERROR: Thinking rule '{rule.id}' references unknown construct '{c}'.")

        return issues

    def get_governance_require_profile(self) -> bool:
        """P0-1c: opt-in fail-loud on an undeclared GOVERNANCE_PROFILE (default False).

        ``get_thinking_rules`` silently falls back to the ``default`` profile, and
        then to agent-type-level rules, when the requested profile is not declared.
        For ordinary runs that is forgiving; for an experiment sweep it is a trap —
        a typo'd arm name runs the WRONG RULE SET and the run still looks healthy,
        producing scientifically wrong data with no error anywhere.

        Set ``global_config.governance.require_profile: true`` in every arm config.
        Default-OFF so no frozen run changes behaviour.
        """
        gov = self._config.get("global_config", {}).get("governance", {})
        if not isinstance(gov, dict):
            return False
        return bool(gov.get("require_profile", False))

    def _resolve_governance_profile(self, agent_type: str, cfg: Dict[str, Any]) -> str:
        """Resolve GOVERNANCE_PROFILE, failing loudly on an undeclared name (opt-in).

        MUST be called by EVERY rule accessor, not just one. Both
        ``get_thinking_rules`` and ``get_identity_rules`` silently fall back to the
        ``default`` profile when the requested one is undeclared, and they are
        reached by different paths:

        * ``get_identity_rules`` runs UNCONDITIONALLY on every step (skill filtering
          and ``validate_identity``);
        * ``get_thinking_rules`` runs only ``if reasoning:`` — and ``reasoning`` is
          legitimately ``{}`` whenever a small local model's structured reasoning
          block fails to parse.

        So guarding only the thinking path leaves a real hole: a typo'd profile plus
        a parse-failure step completes the whole run on the wrong rule set with no
        error anywhere — the exact silent-wrong-data failure this guard exists to
        close. Centralised here so a future accessor cannot forget it.
        """
        profile = os.environ.get("GOVERNANCE_PROFILE", "default").lower()
        if profile == "default" or not self.get_governance_require_profile():
            return profile
        # Mirror the resolver's own lookup: the top-level form nests the agent_type
        # UNDER the profile, so a profile declared for another agent_type must not
        # count as declared for this one.
        top_level = self._config.get("governance", {}) or {}
        declared = {p for p, body in top_level.items()
                    if isinstance(body, dict) and agent_type in body}
        declared |= set(cfg.get("governance", {}) or {})
        if profile not in declared:
            raise ValueError(
                f"GOVERNANCE_PROFILE={profile!r} is not declared for agent_type "
                f"{agent_type!r} (declared: {sorted(declared)}). "
                "global_config.governance.require_profile is on, so this fails "
                "rather than silently falling back to the 'default' rule set."
            )
        return profile

    def get_thinking_rules(self, agent_type: str) -> List[CoherenceRule]:
        """Get cognitive/thinking rules."""
        cfg = self.get(agent_type)
        profile = self._resolve_governance_profile(agent_type, cfg)

        # Task 015 fix: Look in both locations for governance rules
        # 1. Top-level governance section: governance.{profile}.{agent_type}.thinking_rules
        # 2. Agent-type section: {agent_type}.governance.{profile}.thinking_rules (legacy)
        top_level_gov = self._config.get("governance", {})
        rules = top_level_gov.get(profile, {}).get(agent_type, {}).get("thinking_rules", [])

        # Fallback to agent-type embedded governance (legacy format)
        if not rules:
            gov = cfg.get("governance", {})
            rules_container = gov.get(profile, {}) if profile in gov else gov.get("default", {})
            rules = rules_container.get("thinking_rules", cfg.get("thinking_rules", cfg.get("coherence_rules", {})))
        
        # DEBUG
        # print(f"DEBUG_CONFIG: Loading thinking_rules for {agent_type} (Profile: {profile}). Found {len(rules)} entries.")
            
        if isinstance(rules, list):
            rules_list = rules
        else:
            rules_list = [{"id": k, **v} for k, v in rules.items()]
            
        coherence_rules = []
        for rule in rules_list:
            rule_id = rule.get("id", rule.get("construct", "unknown"))
            level = rule.get("level", "ERROR")
            if str(level).strip() not in ("ERROR", "WARNING"):
                # Warn ONCE per (rule, level): get_thinking_rules is called per
                # agent per step (no rule cache), so an unconditional warning
                # would spam logs at agents x years x retries frequency
                # (review batch-2 W2).
                warned = getattr(self, "_warned_rule_levels", None)
                if warned is None:
                    warned = set()
                    self._warned_rule_levels = warned
                if (rule_id, str(level)) not in warned:
                    warned.add((rule_id, str(level)))
                    logger.warning(
                        f"[Config] Rule {rule_id!r} has unknown enforcement "
                        f"level {level!r}; treated as non-blocking/WARNING by "
                        f"the exact-string comparisons; write ERROR or WARNING, "
                        f"uppercase."
                    )
            coherence_rules.append(
                CoherenceRule(
                    id=rule_id,
                    construct=rule.get("construct", rule.get("id") if "conditions" not in rule else None),
                    conditions=rule.get("conditions"),
                    expected_levels=rule.get("when_above", rule.get("when_true")),
                    blocked_skills=rule.get("blocked_skills"),
                    level=level,
                    message=rule.get("message", ""),
                    grounding=resolve_rule_grounding(rule),
                )
            )
        return coherence_rules

    def get_coherence_rules(self, agent_type: str) -> List[CoherenceRule]:
        """Legacy compatibility accessor."""
        return self.get_thinking_rules(agent_type)
    
    def get_constructs(self, agent_type: str) -> Dict[str, Dict]:
        """Get construct definitions."""
        cfg = self.get(agent_type)
        return cfg.get("constructs", {})
    
    def get_prompt_template(self, agent_type: str) -> str:
        """Get prompt template, supporting inline and file-based templates."""
        cfg = self.get(agent_type)

        template_file = cfg.get("prompt_template_file", "")
        if template_file:
            resolved = self._resolve_template_path(template_file)
            if resolved and resolved.exists():
                try:
                    return resolved.read_text(encoding="utf-8")
                except Exception as e:
                    logger.warning(f"Failed to read prompt file {resolved}: {e}")

        return cfg.get("prompt_template", "")

    def _resolve_template_path(self, relative_path: str) -> Optional[Path]:
        """Resolve a template file path relative to the YAML config location."""
        if not relative_path:
            return None

        p = Path(relative_path)
        if p.is_absolute():
            return p

        if hasattr(self, "_yaml_path") and self._yaml_path:
            yaml_dir = Path(self._yaml_path).parent
            return yaml_dir / relative_path

        return Path.cwd() / relative_path
    
    def get_parsing_config(self, agent_type: str) -> Dict[str, Any]:
        """Get parsing configuration for model adapter, falling back to default."""
        cfg = self.get(agent_type)
        parsing = cfg.get("parsing", {})
        
        # Merge with default if not presence
        default_parsing = self._config.get("default", {}).get("parsing", {})
        if not parsing:
            return default_parsing
            
        # Ensure constructs are inherited if missing
        if "constructs" not in parsing and "constructs" in default_parsing:
            parsing["constructs"] = default_parsing["constructs"]
            
        return parsing

    def get_memory_config(self, agent_type: str) -> Dict[str, Any]:
        """Get memory engine configuration (v1/v2/v3 supported), falling back to default."""
        cfg = self.get(agent_type)
        memory = cfg.get("memory", {}) or {}
        if not memory:
            return self._config.get("default", {}).get("memory", {}) or {}
        return memory

    def get_log_fields(self, agent_type: str) -> List[str]:
        """Get list of reasoning fields to highlight in logs, falling back to default."""
        cfg = self.get(agent_type)
        fields = cfg.get("log_fields", [])
        if not fields:
            return self._config.get("default", {}).get("log_fields", [])
        return fields

    def get_global_skills(self, agent_type: str) -> List[str]:
        """Get list of world-available skills (Phase 32) that are always presented."""
        parsing = self.get_parsing_config(agent_type)
        return parsing.get("global_skills", [])

    def get_full_disclosure_agent_types(self) -> List[str]:
        """Get list of agent types that bypass skill retrieval (Phase 33)."""
        types = []
        for atype, cfg in self._config.items():
            if cfg.get("parsing", {}).get("full_disclosure"):
                types.append(atype)
        return types


    def get_skill_map(self, agent_type: str, context: Dict[str, Any] = None) -> Dict[str, str]:
        """
        Get numeric skill map for an agent, optionally resolving variants based on context.
        
        Priority:
        1. dynamic_skill_map from context (for shuffled options)
        2. skill_variant-based map from YAML
        3. Smart resolution based on boolean context vars
        4. Default skill_map fallback
        """
        # 0. Check for dynamic_skill_map from context (highest priority - used for option shuffling)
        if context:
            # Check both top-level and nested in 'personal'
            dynamic_map = context.get("dynamic_skill_map") or context.get("personal", {}).get("dynamic_skill_map")
            if dynamic_map:
                return dynamic_map
        
        parsing = self.get_parsing_config(agent_type)
        if not parsing:
            return {}
            
        # 0. Check for dynamic_skill_map (Priority for transient mappings)
        dynamic = context.get("dynamic_skill_map") if context else None
        if dynamic:
            return dynamic

        # 1. Check for explicit skill_variant
        variant = context.get("skill_variant") if context else None
        if variant:
            v_key = f"skill_map_{variant}"
            if v_key in parsing:
                return parsing[v_key]
        
        # 2. Smart Resolution
        if context:
            for key, val in context.items():
                if isinstance(val, bool):
                    v_key = f"skill_map_{key}" if val else f"skill_map_non_{key}"
                    if v_key in parsing:
                        return parsing[v_key]
        
        # 3. Fallback
        return parsing.get("skill_map", {})

    def get_parameters(self, agent_type: str) -> Dict[str, Any]:
        """Get domain parameters for agent type."""
        cfg = self.get(agent_type)
        return cfg.get("parameters", {})

    def get_llm_params(self, agent_type: str) -> Dict[str, Any]:
        """Get LLM parameters (num_predict, num_ctx, etc.) for agent type."""
        cfg = self.get(agent_type)
        shared_llm = self._config.get("shared", {}).get("llm", {}) or {}
        global_llm = self._config.get("global_config", {}).get("llm", {}) or {}
        agent_llm = cfg.get("llm_params", {}) or {}
        merged = {}
        merged.update(shared_llm)
        merged.update(global_llm)
        merged.update(agent_llm)
        return merged

    def get_global_memory_config(self) -> Dict[str, Any]:
        """Get global memory config (Global > Shared > Default)."""
        defaults = {
            "window_size": 3,
            "consolidation_threshold": 0.6,
            "consolidation_probability": 0.7,
            "top_k_significant": 2,
            "decay_rate": 0.1
        }
        shared_mem = self._config.get("shared", {}).get("memory", {})
        global_mem = self._config.get("global_config", {}).get("memory", {})
        merged = defaults.copy()
        merged.update(shared_mem)
        merged.update(global_mem)
        return merged

    def get_sensory_cortex(self, agent_type: str = None) -> Optional[List[Dict]]:
        """Return sensory_cortex config if defined in global memory config."""
        memory_cfg = self._config.get("global_config", {}).get("memory", {})
        return memory_cfg.get("sensory_cortex", None)

    def get_response_format(self, agent_type: str) -> Dict[str, Any]:
        """Get response format configuration (delimiters, fields) with shared fallback."""
        cfg = self.get(agent_type)
        agent_fmt = cfg.get("response_format", {})
        shared_fmt = self._config.get("shared", {}).get("response_format", {})

        # Merge: agent-specific overrides shared
        if agent_fmt:
            return {**shared_fmt, **agent_fmt}
        return shared_fmt

    def get_numeric_fields(self, agent_type: str) -> List[Dict[str, Any]]:
        """
        Get all numeric field definitions from response_format.
        
        Returns a list of field configs that have type="numeric", each containing:
        - key: The field key (e.g., "magnitude_pct", "elevation_change")
        - min/max: Optional range constraints
        - unit: Optional unit (e.g., "%", "meters")
        - sign: Optional sign constraint ("positive_only", "negative_only", "both")
        
        This allows ModelAdapter to dynamically extract any numeric field,
        not just hardcoded "magnitude_pct".
        
        Returns:
            List of numeric field definitions, empty if none defined
        """
        response_fmt = self.get_response_format(agent_type)
        fields = response_fmt.get("fields", [])
        
        numeric_fields = []
        for field in fields:
            if field.get("type") == "numeric":
                numeric_fields.append({
                    "key": field.get("key"),
                    "min": field.get("min"),
                    "max": field.get("max"),
                    "unit": field.get("unit", ""),
                    "sign": field.get("sign", "positive_only"),
                    "required": field.get("required", False),
                })
        
        return numeric_fields

    def get_multi_skill_config(self, agent_type: str) -> Dict[str, Any]:
        """
        Get multi-skill configuration for an agent type.

        Returns the multi_skill config dict if enabled, empty dict otherwise.
        Multi-skill is intentionally bounded to a primary action plus one
        optional secondary action. Any larger requested value is capped at 2.
        Config lives under agent_type in agent_types.yaml:
            household:
              multi_skill:
                enabled: true
                max_skills: 2
                secondary_field: "secondary_decision"
                secondary_magnitude_field: "secondary_magnitude_pct"
        """
        cfg = self.get(agent_type)
        ms = cfg.get("multi_skill", {})
        if not ms.get("enabled", False):
            return {}
        normalized = dict(ms)
        normalized["max_skills"] = min(int(normalized.get("max_skills", 2)), 2)
        normalized.setdefault("execution_order", "sequential")
        normalized.setdefault("secondary_field", "secondary_decision")
        return normalized

    def get_multi_param_enabled(self, agent_type: str) -> bool:
        """Phase 6W-B2 (default-OFF): whether this agent_type opts into routing the
        full extracted numeric dict onto ``SkillProposal.parameters`` (multi-dimensional
        setpoints, e.g. a reservoir operator's {release, hydropower, flood_pool}).

        Frozen domains never declare it -> returns False -> ``parameters`` stays ``{}``
        -> JSONL/CSV byte-identical, regardless of how many numeric fields the
        agent_type declares (single_agent declares a secondary_magnitude_pct, so a
        count-based heuristic would be unsafe; an explicit opt-in is not). Config:
            <agent_type>:
              multi_param_action:
                enabled: true
        Accepts a bare bool too (``multi_param_action: true``).
        """
        cfg = self.get(agent_type)
        mp = cfg.get("multi_param_action", False)
        if isinstance(mp, bool):
            return mp
        if isinstance(mp, dict):
            return bool(mp.get("enabled", False))
        return False

    # =========================================================================
    # Task-041: Framework-Aware Rating Scale Support
    # =========================================================================

    def get_rating_scale(self, framework: str = "pmt") -> str:
        """
        Get rating scale template for framework.

        Priority:
        1. shared.rating_scales.{framework}.template (if defined)
        2. RatingScaleRegistry default
        3. shared.rating_scale (legacy fallback)

        Args:
            framework: Built-in or custom framework name

        Returns:
            Rating scale template string for prompt injection
        """
        from broker.interfaces.rating_scales import RatingScaleRegistry, FrameworkType

        # 1. Try framework-specific from YAML
        shared = self._config.get("shared", {})
        scales = shared.get("rating_scales", {})
        if framework.lower() in scales:
            template = scales[framework.lower()].get("template", "")
            if template:
                return template

        # 2. Use registry default or registered custom framework
        try:
            return RatingScaleRegistry.get_by_name(framework).template
        except KeyError:
            pass

        # 3. Legacy fallback
        legacy = shared.get("rating_scale", "")
        if legacy:
            return legacy

        # 4. Ultimate fallback to PMT
        return RatingScaleRegistry.get(FrameworkType.PMT).template

    def get_rating_scale_levels(self, framework: str = "pmt") -> List[str]:
        """
        Get valid rating levels for framework.

        Returns:
            List of valid levels, e.g., ["VL", "L", "M", "H", "VH"]
        """
        from broker.interfaces.rating_scales import RatingScaleRegistry, FrameworkType

        shared = self._config.get("shared", {})
        scales = shared.get("rating_scales", {})

        if framework.lower() in scales:
            levels = scales[framework.lower()].get("levels", [])
            if levels:
                return levels

        try:
            return RatingScaleRegistry.get_by_name(framework).levels
        except KeyError:
            # Domain-neutral generic 5-level Likert fallback (Phase 6J-A —
            # not a flood-PMT default).
            return ["VL", "L", "M", "H", "VH"]

    def get_framework_for_agent_type(self, agent_type: str) -> str:
        """
        Get psychological framework for agent type.

        Returns:
            Framework name: "pmt", "utility", "financial", or "generic"
        """
        cfg = self.get(agent_type)
        # TODO(Phase 6J-A part 2): flip this default to "generic" once the
        # flood example YAMLs declare `psychological_framework: pmt`
        # explicitly — until then an undeclared flood agent type must keep
        # resolving to PMT.
        return cfg.get("psychological_framework", "pmt")

    def get_rating_scale_for_agent_type(self, agent_type: str) -> str:
        """
        Get rating scale template for an agent type's framework.

        Convenience method that combines get_framework_for_agent_type
        and get_rating_scale.

        Args:
            agent_type: The agent type (e.g., "household", "government")

        Returns:
            Rating scale template string
        """
        framework = self.get_framework_for_agent_type(agent_type)
        return self.get_rating_scale(framework)

    @property
    def agent_types(self) -> List[str]:
        """List all available agent types."""
        return list(self._config.keys())

    # =========================================================================
    # Task-035: SDK UnifiedConfigLoader Integration
    # =========================================================================

    _sdk_loader: Optional["UnifiedConfigLoader"] = None
    _sdk_experiment_config: Optional["ExperimentConfig"] = None

    @classmethod
    def set_sdk_loader(cls, loader: "UnifiedConfigLoader"):
        """
        Set the SDK UnifiedConfigLoader for experiment config access.

        This allows using SDK-style configuration (YAML with validation)
        alongside the existing agent_types.yaml system.

        Args:
            loader: Instance of cognitive_governance.v1_prototype.config.UnifiedConfigLoader

        Example:
            >>> from cognitive_governance.v1_prototype.config import UnifiedConfigLoader
            >>> loader = UnifiedConfigLoader()
            >>> AgentTypeConfig.set_sdk_loader(loader)
        """
        cls._sdk_loader = loader

    @classmethod
    def load_sdk_experiment(cls, config_path: str) -> Optional["ExperimentConfig"]:
        """
        Load experiment configuration using SDK UnifiedConfigLoader.

        Args:
            config_path: Path to YAML experiment config file

        Returns:
            ExperimentConfig instance or None if SDK not available

        Example:
            >>> config = AgentTypeConfig.load_sdk_experiment("config/flood_study.yaml")
            >>> print(config.domain, config.agents)
        """
        if cls._sdk_loader is None:
            try:
                from cognitive_governance.v1_prototype.config import UnifiedConfigLoader
                cls._sdk_loader = UnifiedConfigLoader()
            except ImportError:
                logger.warning("SDK not available, cannot load experiment config")
                return None

        try:
            cls._sdk_experiment_config = cls._sdk_loader.load_experiment(config_path)
            logger.info(f"Loaded SDK experiment config: {cls._sdk_experiment_config.name}")
            return cls._sdk_experiment_config
        except Exception as e:
            logger.error(f"Failed to load SDK experiment config: {e}")
            return None

    def get_sdk_memory_config(self) -> Optional["SDKMemoryConfig"]:
        """
        Get SDK MemoryConfig from loaded experiment.

        Returns SDK-style MemoryConfig with validated fields, or None if
        no SDK experiment config is loaded.

        Returns:
            SDKMemoryConfig instance or None
        """
        if self._sdk_experiment_config is not None:
            return self._sdk_experiment_config.memory
        return None

    def get_sdk_reflection_config(self) -> Optional[Dict[str, Any]]:
        """
        Get SDK ReflectionConfig from loaded experiment.

        Returns:
            Dict with reflection settings or None
        """
        if self._sdk_experiment_config is not None:
            refl = self._sdk_experiment_config.reflection
            return {
                "enabled": refl.enabled,
                "interval": refl.interval,
                "auto_promote": refl.auto_promote,
                "promotion_threshold": refl.promotion_threshold,
                "max_memories_per_reflection": refl.max_memories_per_reflection,
            }
        return None

    def get_sdk_llm_config(self) -> Optional[Dict[str, Any]]:
        """
        Get SDK LLMConfig from loaded experiment.

        Returns:
            Dict with LLM settings or None
        """
        if self._sdk_experiment_config is not None:
            llm = self._sdk_experiment_config.llm
            return {
                "provider": llm.provider,
                "model": llm.model,
                "temperature": llm.temperature,
                "max_tokens": llm.max_tokens,
                "base_url": llm.base_url,
            }
        return None

    def get_memory_config_v2(self, agent_type: str) -> Dict[str, Any]:
        """
        Get memory config with SDK fallback.

        Priority:
        1. SDK experiment config (if loaded)
        2. Agent-type specific config from YAML
        3. Global memory config

        Args:
            agent_type: The agent type name

        Returns:
            Dict with memory configuration
        """
        # 1. Try SDK config first
        sdk_mem = self.get_sdk_memory_config()
        if sdk_mem is not None:
            return {
                "engine": sdk_mem.engine,
                "window_size": sdk_mem.window_size,
                "arousal_threshold": sdk_mem.arousal_threshold,
                "ema_alpha": sdk_mem.ema_alpha,
                "consolidation_threshold": sdk_mem.consolidation_threshold,
                "persistence": sdk_mem.persistence,
                "persistence_path": sdk_mem.persistence_path,
            }

        # 2. Fallback to existing logic
        return self.get_memory_config(agent_type)



# Re-export for backward compatibility (extracted to governance_auditor.py)
from broker.utils.governance_auditor import GovernanceAuditor  # noqa: F401, E402


# Convenience function
def load_agent_config(yaml_path: Optional[str] = None, force_reload: bool = False) -> AgentTypeConfig:
    """Load agent type configuration (path-aware cache, optional forced refresh)."""
    return AgentTypeConfig.load(yaml_path, force_reload=force_reload)
