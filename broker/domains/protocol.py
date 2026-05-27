"""
DomainPack Protocol — single facade for all domain-specific behavior.

Phase 6C-v2 (2026-05-10): a new application domain (vaccination, traffic,
finance, etc.) implements this Protocol once and registers it via
``DomainPackRegistry.register("<name>", pack)``. Broker code queries the
pack via ``DomainPackRegistry.get_or_default(domain)`` and delegates
domain-specific decisions to the pack's methods.

TODO(6Q): Protocol width — after the Phase 6P batch this Protocol carries
~30 methods covering reflection, memory, events, validators, perception,
loaders, phase orchestration, and hazard config. Phase 6Q should split it
into composable sub-protocols by concern (e.g. ``ReflectionPack``,
``MemoryPack``, ``LoaderPack``, ``HazardPack``) so a domain author who only
needs reflection overrides isn't forced to read 30 method signatures.
Implementations stay backward-compat via either runtime_checkable
inheritance or a thin composition wrapper. Surfaced by Phase 6P-E
code-reviewer #5 (2026-05-25).

Design rationale
================
Before this layer, broker code had ``if agent_type == "household":``
gates and ``if event_type == "flood":`` chains hardcoded in 8+ hot-spot
sites. New domains either had to edit those branches (brittle) or
work around them with custom builders (incomplete). DomainPack
consolidates the dispatch surface so:

1. New domains implement only what they need (every method has a
   sensible default in :class:`DefaultDomainPack`).
2. Adding a domain is one class + one registration call. Zero edits
   under ``broker/``.
3. The five existing specific registries (Skill, Validator, Filter,
   MemoryEngine, Event) stay as concrete state stores; ``DomainPack``
   is the facade that wires them together.

Backward compatibility
======================
Water (irrigation + flood) is migrated to :class:`IrrigationDomainPack`
and :class:`FloodDomainPack` subclasses. Their behavior is byte-identical
to the pre-refactor hardcodes — verified by regression tests in
``tests/test_domain_pack_contract.py``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    Any, Callable, Dict, List, Optional, Protocol, Set, Tuple,
    runtime_checkable,
)


# ─────────────────────────────────────────────────────────────────────
# Type aliases (kept loose — concrete shapes are owned by their modules)
# ─────────────────────────────────────────────────────────────────────

EventHandler = Callable[[Any, Dict[str, Any]], None]
"""(event, state) -> None. Mutates ``state`` in place.

Reused for two distinct dispatch surfaces:
- :meth:`DomainPack.event_handlers` — ``state`` is the global environment
  dict; a handler overwrites env keys.
- :meth:`DomainPack.agent_impact_handlers` — ``state`` is a per-agent
  impact accumulator; a handler aggregates (max / sum), not overwrites.
"""

BuiltinCheck = Callable[..., List[Any]]
"""(skill_name, rules, context) -> List[ValidationResult]. Re-typed in
ValidatorRegistry; here we keep loose to avoid an import cycle."""


# ─────────────────────────────────────────────────────────────────────
# Memory policy bundle (Phase 6K-A 2026-05-22)
# ─────────────────────────────────────────────────────────────────────

@dataclass
class MemoryPolicyBundle:
    """Domain-specific memory-subsystem policy supplied by a
    :class:`DomainPack`. Consumed by:

    - :func:`broker.components.memory.policy_classifier.classify`
      (``category_rules`` overrides the generic default rule set).
    - :func:`broker.components.memory.initial_loader.load_initial_memories_from_json`
      (``external_event_whitelist`` controls which categories may keep
      ``MemoryContentType.EXTERNAL_EVENT`` at seed time; everything else
      downgrades to the loader's ``default_content_type``).
    - :class:`broker.components.memory.universal.UniversalCognitiveEngine`
      (``stimulus_key`` supplies the EMA surprise key when the caller
      did not pass one).

    ``category_rules`` values are :class:`MemoryContentType` members but
    typed as ``Any`` here to keep this protocol module decoupled from
    ``broker.components.memory`` (otherwise the import is circular —
    ``broker.components.memory.policy_classifier`` queries
    ``DomainPackRegistry`` for the bundle).
    """

    # Dict[str, MemoryContentType] — values are MemoryContentType members
    # at runtime; typed Any to avoid the circular import.
    category_rules: Dict[str, Any] = field(default_factory=dict)
    external_event_whitelist: Tuple[str, ...] = ()
    stimulus_key: Optional[str] = None
    # Optional override for the per-loader default; left None means
    # "use the loader's own argument default".
    default_content_type: Optional[Any] = None


# ─────────────────────────────────────────────────────────────────────
# Sub-protocols (Phase 6R-D-1, 2026-05-26)
# ─────────────────────────────────────────────────────────────────────
#
# The composite :class:`DomainPack` (defined below) inherits from these
# seven sub-protocols, each grouping a cohesive subset of the broker's
# domain-dispatch surface. The split exists for type-narrowing — broker
# subsystems can declare a parameter as ``ReflectionPack`` instead of
# the full ``DomainPack`` to make their contract explicit, and new
# domain authors can scan the relevant sub-protocol(s) instead of the
# 32-method composite.
#
# Each method declaration also lives in the ``DomainPack`` body below
# (with its full docstring) for IDE / class-inspection backward
# compatibility — Python's ``@runtime_checkable`` Protocol accepts
# duplicate declarations and uses the composite class's body as the
# authoritative source. The sub-protocols here carry only abbreviated
# docstrings citing the canonical DomainPack location.
#
# Phase 6R-D roadmap: 6R-D-1 (this commit) DEFINES the sub-protocols
# but does not yet narrow any broker consumer's type hints — every
# call site still uses ``DomainPack``. 6R-D-3 introduces typed
# accessors on ``DomainPackRegistry`` (``get_reflection_pack(domain)``
# etc.); 6R-D-4 migrates broker consumers to use the narrowed types
# at their relevant call sites.
# ─────────────────────────────────────────────────────────────────────


@runtime_checkable
class ReflectionPack(Protocol):
    """Reflection-prompt customisation hooks (4 methods).

    Consumed by ``broker/components/cognitive/reflection.py``. See the
    full method docstrings on ``DomainPack`` for semantics. Methods
    grouped: ``reflection_status_text``, ``reflection_questions``,
    ``reflection_persona``, ``reflection_trait_labels``.
    """
    def reflection_status_text(self, context: Any) -> Optional[str]: ...
    def reflection_questions(self) -> List[str]: ...
    def reflection_persona(self) -> Optional[str]: ...
    def reflection_trait_labels(self, context: Any) -> List[str]: ...


@runtime_checkable
class MemoryPack(Protocol):
    """Memory salience, emotion classification, retrieval tuning (6 methods).

    Consumed by ``broker/components/memory/`` (policy_classifier,
    initial_loader, universal). See ``DomainPack`` for full docstrings.
    Methods: ``importance_profiles``, ``compute_importance``,
    ``classify_emotion``, ``emotional_keywords``, ``retrieval_weights``,
    ``memory_policy``.
    """
    def importance_profiles(self) -> Dict[str, float]: ...
    def compute_importance(self, context: Any, base: float = 0.5) -> float: ...
    def classify_emotion(self, decision: str, context: Any) -> str: ...
    def emotional_keywords(self) -> Dict[str, str]: ...
    def retrieval_weights(self) -> Dict[str, float]: ...
    def memory_policy(self) -> Optional[MemoryPolicyBundle]: ...


@runtime_checkable
class SkillPack(Protocol):
    """Decision-semantic hooks: emotion / extremeness / affordability (4 methods).

    Consumed by ``broker/core/experiment_runner.py``,
    ``broker/validators/agent/agent_validator.py``, and analytics
    pipelines. See ``DomainPack`` for full docstrings. Methods:
    ``skill_emotion_metadata``, ``extreme_actions``,
    ``action_taxonomy``, ``affordability_constraints``.
    """
    def skill_emotion_metadata(self, skill_name: str) -> Dict[str, Any]: ...
    def extreme_actions(self) -> Set[str]: ...
    def action_taxonomy(self) -> Dict[str, "ActionTaxonomyEntry"]: ...
    def affordability_constraints(self) -> Dict[str, Any]: ...


@runtime_checkable
class EventPack(Protocol):
    """Multi-agent event handlers — global env + per-agent impact + dispatch / lifecycle (5 methods).

    Consumed by ``broker/components/events/ma_manager.py``. See
    ``DomainPack`` for full docstrings. Methods:
    ``event_handlers``, ``agent_impact_handlers``,
    ``event_type_to_domain``, ``event_persistence_policy``,
    ``silent_skip_event_types`` (last three added Phase 6T-A
    2026-05-27).
    """
    def event_handlers(self) -> Dict[str, EventHandler]: ...
    def agent_impact_handlers(self) -> Dict[str, EventHandler]: ...
    def event_type_to_domain(self, event_type: str) -> Optional[str]: ...
    def event_persistence_policy(self, event_type: str) -> Any: ...
    def silent_skip_event_types(self) -> Set[str]: ...


@runtime_checkable
class PerceptionPack(Protocol):
    """Numeric→qualitative verbalisation + per-agent-type policy + social-media tier vocabulary (8 methods).

    Consumed by ``broker/components/social/perception.py`` and by
    the Phase 6T-E social-media propagation channel. See
    ``DomainPack`` for full docstrings. Methods:
    ``perception_descriptors``, ``perception_field_policy``,
    ``passthrough_agent_types``, ``credibility_tiers`` (Phase 6T-E
    2026-05-27), ``credibility_weight`` (Phase 6T-E),
    ``verbalise_post`` (Phase 6T-E), ``suppressed_tiers``
    (Phase 6T-E), ``social_media_post_filter`` (Phase 6T-E).
    """
    def perception_descriptors(self) -> Dict[str, Any]: ...
    def perception_field_policy(self) -> Dict[str, List[str]]: ...
    def passthrough_agent_types(self) -> Set[str]: ...
    def credibility_tiers(self) -> List[str]: ...
    def credibility_weight(self, tier_id: str) -> float: ...
    def verbalise_post(self, post: Any) -> str: ...
    def suppressed_tiers(self) -> Set[str]: ...
    def social_media_post_filter(self, agent: Any, post: Any) -> Optional[Any]: ...


@runtime_checkable
class GovernancePack(Protocol):
    """Validator dispatch + policy thresholds + placeholder allowlist (9 methods).

    Consumed by ``broker/components/governance/*``,
    ``broker/validators/*``, and ``broker/tools/validate_prompt.py``.
    See ``DomainPack`` for full docstrings.

    Note (Phase 6R-D-1 open design): ``psychological_framework`` is
    grouped here because its sole consumer is the validator
    dispatcher, but semantically it's a framework-selector rather than
    a governance-policy tuner. A future Phase 6R-D refinement may
    split it into its own ``FrameworkPack``; see
    ``.research/domain_pack_protocol_reference.md`` for the deferred
    design decision.

    Methods: ``psychological_framework``,
    ``framework_for_agent_type`` (Phase 6T-B 2026-05-27),
    ``builtin_checks``, ``retrieval_policy``, ``drift_policy``,
    ``population_governance_policy``, ``policy_event_tiers``,
    ``bridge_importance_policy``, ``prompt_placeholder_extensions``.
    """
    def psychological_framework(self) -> str: ...
    def framework_for_agent_type(self, agent_type: Optional[str]) -> str: ...
    def builtin_checks(self) -> Dict[str, List[BuiltinCheck]]: ...
    def retrieval_policy(self) -> Dict[str, Any]: ...
    def drift_policy(self) -> Dict[str, Any]: ...
    def population_governance_policy(self) -> Dict[str, Any]: ...
    def policy_event_tiers(self) -> Dict[str, float]: ...
    def bridge_importance_policy(self) -> Dict[str, float]: ...
    def prompt_placeholder_extensions(self) -> Set[str]: ...


@runtime_checkable
class SetupPack(Protocol):
    """Agent initialisation + orchestration + per-agent narrative (7 methods).

    Consumed by ``broker/core/agent_initializer.py``,
    ``broker/components/orchestration/phases.py``, multi-agent
    runners, and per-agent context builders. See ``DomainPack`` for
    full docstrings. Methods: ``csv_loader_class``,
    ``synthetic_loader_class``, ``phase_layout``,
    ``initial_memory_templates``, ``mg_barrier_text``,
    ``institutional_lifecycle_handlers`` (Phase 6T-C 2026-05-27),
    ``multi_agent_env_keys`` (Phase 6T-C 2026-05-27).
    """
    def csv_loader_class(self) -> Optional[Any]: ...
    def synthetic_loader_class(self) -> Optional[Any]: ...
    def phase_layout(self) -> Optional[List[Any]]: ...
    def initial_memory_templates(self, profile: Dict[str, Any]) -> List[Any]: ...
    def mg_barrier_text(self, profile: Dict[str, Any]) -> str: ...
    def institutional_lifecycle_handlers(self) -> Dict[str, Any]: ...
    def multi_agent_env_keys(self) -> Set[str]: ...


# ─────────────────────────────────────────────────────────────────────
# Composite Protocol — DomainPack
# ─────────────────────────────────────────────────────────────────────

@runtime_checkable
class DomainPack(
    ReflectionPack,
    MemoryPack,
    SkillPack,
    EventPack,
    PerceptionPack,
    GovernancePack,
    SetupPack,
    Protocol,
):
    """Bundle of domain-specific behaviors queried by the broker pipeline.

    Every method has a no-op default in :class:`DefaultDomainPack`.
    Implementers override only what's relevant for their domain.

    Minimum new-domain surface (MUST override) — Phase 6Q-A (2026-05-26):
        1. ``name`` (class attribute) — domain identifier used as the
           registry key (e.g. ``"traffic"``).
        2. ``reflection_status_text(context)`` — without this the
           reflection prompt collapses to a generic identity line; the
           LLM has nothing domain-flavoured to reason from.
        3. ``importance_profiles()`` — without this every memory has
           the same baseline (0.5), so retrieval loses domain salience.

    Everything else has a safe no-op default in
    :class:`broker.domains.default.DefaultDomainPack` — override only
    the methods whose default is wrong for your domain. The 3-method
    minimum was previously documented only in the
    ``wagf-domain-builder`` skill checklist
    (`.claude/skills/wagf-domain-builder/references/edit_pass_checklist.md`);
    surfaced here so a new domain author reading the Protocol
    definition sees the contract immediately.

    Attributes
    ----------
    name : str
        Domain identifier matching the value passed to validators
        (e.g., ``"irrigation"``, ``"flood"``, ``"vaccination"``).
    """

    name: str

    # ─── Reflection ───────────────────────────────────────────────

    def reflection_status_text(self, context: Any) -> Optional[str]:
        """Per-agent narrative status block injected into the individual
        reflection prompt. Return ``None`` to skip — the prompt then
        contains only the generic identity line.

        Replaces the hardcoded flood block in
        ``broker/components/cognitive/reflection.py:301-313``.
        """
        ...

    def reflection_questions(self) -> List[str]:
        """Prompt questions for the reflection LLM call.

        Wired (Phase 6H Item 4) as step 4 of
        ``AgentTypeConfig.get_reflection_questions(agent_type)`` — its
        precedence is per-agent-type YAML → domain-wide YAML → this hook
        → a domain-neutral generic fallback. A packaged domain may return
        its questions here instead of declaring ``reflection.questions``
        in ``agent_types.yaml``; empty list → defer to YAML / the
        generic fallback."""
        ...

    def reflection_persona(self) -> Optional[str]:
        """Persona instruction prepended to reflection prompts (e.g.,
        "Speak in first person as a farmer..."). ``None`` → use YAML
        config or default."""
        ...

    def reflection_trait_labels(self, context: Any) -> List[str]:
        """Short trait labels (e.g. ``["repeat customer", "low balance"]``)
        for the compact batch reflection prompt — distinct from
        ``reflection_status_text``, which returns a full sentence for the
        individual prompt.

        Default ``[]`` → the batch prompt shows only the generic identity
        line. Replaces the hardcoded flood traits block in
        ``broker/components/cognitive/reflection.py`` (Phase 6H Item 9).
        """
        ...

    # ─── Memory / importance / emotion ────────────────────────────

    def importance_profiles(self) -> Dict[str, float]:
        """Named importance baselines (e.g.,
        ``{"first_shortage": 0.92, "drought_year": 0.95}``).
        Replaces the hardcoded flood profiles in
        ``broker/components/cognitive/reflection.py:96-98``."""
        ...

    def compute_importance(self, context: Any, base: float = 0.5) -> float:
        """Dynamic importance score for a memory derived from context."""
        ...

    def classify_emotion(self, decision: str, context: Any) -> str:
        """Emotion label for a memory anchored on a decision +
        environmental context (e.g., ``"critical"``, ``"major"``,
        ``"minor"``, ``"neutral"``)."""
        ...

    def emotional_keywords(self) -> Dict[str, str]:
        """Map of domain-specific event keywords → emotion labels."""
        ...

    def retrieval_weights(self) -> Dict[str, float]:
        """Weights summing to 1.0 over (recency, importance, context)
        for the memory retrieval scoring."""
        ...

    # ─── Skills ────────────────────────────────────────────────────

    def skill_emotion_metadata(self, skill_name: str) -> Dict[str, Any]:
        """Per-skill emotion + importance metadata for memory tagging.

        Replaces the hardcoded
        ``if skill_name in {"elevate_house", "relocate"}: ... elif
        "buy_insurance": ...`` chain in
        ``broker/core/experiment_runner.py:383-388``.

        Returns ``{}`` for skills that should use the base/default
        importance and the adapter's classify_emotion output.
        """
        ...

    def extreme_actions(self) -> Set[str]:
        """Set of skill names treated as 'extreme' by the thinking
        validator (e.g., one-way irreversible actions). Replaces the
        ``ThinkingValidator(extreme_actions=...)`` constructor kwarg
        currently set per-domain in ``validator_bundles.py``."""
        ...

    # ─── Events ────────────────────────────────────────────────────

    def event_handlers(self) -> Dict[str, EventHandler]:
        """Mapping of ``event_type → handler(event, env_state)``.

        Replaces the hardcoded ``if event.event_type == "flood": ...
        elif "no_flood": ... elif "subsidy_change": ...`` chain in
        ``broker/components/events/ma_manager.py:275-330``.

        New domains register their own event types (e.g., for
        vaccination: ``{"outbreak": ..., "vaccine_rollout": ...}``).
        """
        ...

    def agent_impact_handlers(self) -> Dict[str, EventHandler]:
        """Mapping of ``event_type → handler(event, impact_state)`` used to
        aggregate per-agent impact, consumed by
        ``MAEventManager.get_agent_impact()``.

        Distinct from :meth:`event_handlers` (which mutates the *global*
        environment state): these handlers aggregate the events that
        affect a single agent into a per-agent impact dict. A handler
        accumulates rather than overwrites — e.g. ``impact["damage"] =
        impact.get("damage", 0.0) + event.data["damage"]``.

        Replaces the hardcoded domain event-type chain in
        ``broker/components/events/ma_manager.py:get_agent_impact()``.
        Default empty ``{}`` → ``get_agent_impact`` returns ``{}``; a
        domain supplies its hazard / damage / payout handlers via its
        own pack (the water pack lives under ``broker/domains/water``).
        """
        ...

    # ─── Phase 6T-A (2026-05-27): dispatch + lifecycle hooks ─────

    def event_type_to_domain(self, event_type: str) -> Optional[str]:
        """Phase 6T-A: explicit ownership claim for ``MAEventManager``
        dispatch.

        Return this pack's :attr:`name` iff it OWNS ``event_type``,
        else ``None``. "Owns" defaults (in :class:`DefaultDomainPack`)
        to "appears in :meth:`event_handlers` or
        :meth:`agent_impact_handlers`" — the natural definition. Packs
        that emit observational events they don't directly handle
        (e.g. a flood pack emitting ``social_media_post`` events that
        a separate social-media pack handles in Phase 6T-E) can
        override to claim them.

        Pre-6T-A the dispatcher silently fell through to scan-all-packs
        when ``env.domain`` was unset, with no notion of who "owned"
        each event_type. The explicit ownership API makes the dispatch
        path deterministic + debuggable.
        """
        ...

    def event_persistence_policy(self, event_type: str) -> Any:
        """Phase 6T-A: lifecycle policy for an event of ``event_type``.

        Returns an :class:`EventPersistence` enum member (from
        ``broker.components.events.exceptions``). Typed ``Any`` here to
        keep this Protocol module decoupled from the concrete
        ``EventPersistence`` import (Protocol modules avoid hard imports
        from broker subpackages by convention).

        - ``EPHEMERAL`` — wiped at year boundary by
          ``MAEventManager.clear_ephemeral_events`` (pre-6T-A default
          behaviour).
        - ``STICKY_YEAR_DECAY`` — preserved across years with weighted
          age decay (consumed by Phase 6T-E social-media propagation).
        - ``STICKY_INDEFINITE`` — never wiped.

        Default in :class:`DefaultDomainPack`: ``EPHEMERAL`` for every
        event_type — matches pre-6T-A behaviour where ``clear_year``
        discarded everything.
        """
        ...

    def silent_skip_event_types(self) -> Set[str]:
        """Phase 6T-A: opt-in allowlist of event_types this pack
        acknowledges are intentionally unhandled.

        Events whose ``event_type`` appears in any registered pack's
        silent-skip allowlist do NOT raise :class:`UnhandledEventError`
        from the dispatcher — they're recorded as
        ``handlers_silently_skipped`` on
        :class:`EventDispatchMetrics` and the dispatch loop continues.

        Use this for legitimate observational / metrics-only events
        that domain code emits for downstream collectors but does not
        itself respond to (e.g. ``audit_only_post_emitted``,
        ``metrics_breadcrumb``). Do NOT use this as a workaround for
        forgotten handlers — that's exactly the silent-failure mode
        Phase 6T-A is closing.

        Default: empty set. The legacy pre-6T-A scan-all-silent-skip
        behaviour is now explicit per-pack opt-in.
        """
        ...

    # ─── Memory policy (Phase 6K-A) ───────────────────────────────

    def action_taxonomy(self) -> Dict[str, "ActionTaxonomyEntry"]:
        """Phase 6O-B: per-skill structural metadata.

        Domain packs may declare ``category`` / ``intensity`` /
        ``reversibility`` per skill so generic readiness reporters can
        compute action-coverage metrics without knowing skill names.

        Default returns empty dict — domains opting out are reported
        under ``unknown`` by the readiness layer. Implementations may
        either return a hardcoded mapping or call
        ``broker.interfaces.action_taxonomy.load_action_taxonomy_from_skill_registry``
        to read from the YAML they ship.
        """
        ...

    def memory_policy(self) -> Optional[MemoryPolicyBundle]:
        """Domain-specific memory-subsystem policy.

        Phase 6K-A (2026-05-22): one hook covers three previously-
        hardcoded flood literals in generic ``broker/components/memory/``:
        the ``policy_classifier._DEFAULT_RULES`` category map, the
        ``initial_loader`` EXTERNAL_EVENT whitelist, and the
        ``universal.py`` EMA ``stimulus_key`` fallback. Returning
        ``None`` (the default) means "use the generic, domain-neutral
        behaviour" — no category overrides, empty whitelist, no
        stimulus-key default (the cognitive engine requires the caller
        to pass one).
        """
        ...

    # ─── Context provider hooks ────────────────────────────────────

    def mg_barrier_text(self, profile: Dict[str, Any]) -> str:
        """Domain-specific narrative text for marginalised-group agents
        injected by ``FinancialCostProvider``. Default empty string —
        no MG-specific content. Replaces the hardcoded
        ``"Passaic River Basin"`` in
        ``broker/components/context/providers.py:708``.
        """
        ...

    # ─── Validators (already partially handled by ValidatorRegistry) ─

    def builtin_checks(self) -> Dict[str, List[BuiltinCheck]]:
        """Mapping of validator slot → list of builtin check functions.

        Slots: ``"physical"``, ``"personal"``, ``"social"``,
        ``"semantic"`` (``"thinking"`` uses ``extreme_actions()``
        instead).

        Default empty → falls back to ``ValidatorRegistry.get_checks(...)``
        registrations made by example packages directly (Phase 6B-1
        path remains valid).
        """
        ...

    def affordability_constraints(self) -> Dict[str, Any]:
        """Per-decision financial affordability cost models, keyed by
        decision/skill name. Each value is a dict
        ``{"base_cost": float, "income_multiplier": float,
        "default_subsidy_rate": float}``: the decision is affordable iff
        ``base_cost * (1 - subsidy_rate) <= income * income_multiplier``
        (``subsidy_rate`` is read from agent/env state, falling back to
        ``default_subsidy_rate``).

        Consumed by ``AgentValidator.validate_affordability()`` (Tier 0,
        opt-in via ``enable_financial_constraints``). Default ``{}`` →
        the affordability check is a no-op; a decision the domain does
        not list is unconstrained. Replaces the hardcoded flood
        elevation cost model (Phase 6H Item 6).
        """
        ...

    # ─── Memory templates (initial agent memories) ────────────────

    def initial_memory_templates(self, profile: Dict[str, Any]) -> List[Any]:
        """Domain-specific initial memories generated from an agent
        profile at experiment startup. Default empty list → no
        initial memories injected. Replaces flood-specific
        ``FloodMemoryTemplateProvider`` (Phase 6B-2)."""
        ...

    # ─── Perception (Phase 6H DomainPack v2) ──────────────────────

    def perception_descriptors(self) -> Dict[str, Any]:
        """Numeric→qualitative verbalization rules, keyed by the INPUT
        context field each transforms (e.g. ``{"depth_ft": <mapping>}``).
        Values are ``broker.interfaces.perception.DescriptorMapping``
        instances (kept loose as ``Any`` here to avoid an import cycle).

        The perception filter applies each as a pure table lookup — it
        never computes. A same-context ratio is expressed via the
        mapping's ``denominator_field``; a temporal change (e.g. a
        price rising/falling) is emitted as a context field by the
        domain environment and verbalized like any other field.

        Default ``{}`` → the filter verbalizes nothing (domain-neutral).
        Consumed by ``PerceptionFilterRegistry`` (Phase 6H Item 5 / 5b).
        """
        ...

    def perception_field_policy(self) -> Dict[str, List[str]]:
        """Field-name lists controlling what ``HouseholdPerceptionFilter``
        strips or aggregates. Recognised keys: ``"dollar_fields"``,
        ``"percentage_fields"``, ``"community_observable_fields"``,
        ``"neighbor_action_fields"``.

        Default ``{}`` → the filter strips nothing. A new domain opts in
        explicitly, which avoids the silent-data-loss risk when an
        unrelated domain's context happens to share a field name.
        """
        ...

    def passthrough_agent_types(self) -> Set[str]:
        """Agent types whose perception is RAW numbers, not verbalized —
        experts / institutions that legitimately reason with precise
        figures (e.g. a regulator, an insurer). Every other agent type
        verbalizes.

        Default ``set()`` → every agent type verbalizes. Verbalize is the
        safe default: verbalizing a precise perceiver only loses some
        precision, whereas passing raw numbers to a lay perceiver
        manufactures a super-perceiver artifact. The model builder
        declares the expert exceptions here (Phase 6H Item 5c).
        """
        ...

    def prompt_placeholder_extensions(self) -> Set[str]:
        """Domain-specific placeholder names that
        ``broker.tools.validate_prompt`` should treat as broker-filled
        (NOT warn about as unknown placeholders).

        Default ``set()`` — generic domains have no extensions; the base
        ``BROKER_FILLED_PLACEHOLDERS`` set in ``validate_prompt`` covers
        the universal placeholders (``{response_format}``, ``{memory}``,
        ``{narrative_persona}``, etc.).

        Per-domain providers or lifecycle hooks that inject extra
        placeholders at runtime register their names here. Examples:

        - ``FloodDomainPack.prompt_placeholder_extensions()`` returns
          ``{"insurance_cost_text", "mg_barrier_text",
          "renewal_fatigue_text"}`` — three flood-specific narrative
          placeholders injected by water-domain context providers.
        - A traffic domain that injects ``{congestion_advisory_text}``
          via a lifecycle hook returns ``{"congestion_advisory_text"}``.

        At validate-time the CLI unions ``BROKER_FILLED_PLACEHOLDERS``
        with the registered DomainPack's extensions before checking
        for unknown placeholders. Phase 6R-B-3 (audit cluster E #16) —
        proper fix for the asymmetric water-placeholder coverage
        documented by Phase 6Q-K-3 in ``validate_prompt.py:87-103``.
        """
        ...

    # ─── Phase 6T-E (2026-05-27): social-media credibility vocabulary ─

    def credibility_tiers(self) -> List[str]:
        """Phase 6T-E: ordered tier vocabulary for the domain's
        social-media propagation channel, highest-credibility first.

        Example values (per the genericity audit at
        ``.research/social_media_genericity_audit.md``):

        - flood (US-media-shaped): ``["official_authority",
          "verified_account", "influencer", "peer", "bot"]``
        - vaccination_ma (hypothetical): ``["cdc", "clinician",
          "health_influencer", "community_elder", "whatsapp_rumor"]``
        - traffic_ma (hypothetical): ``["transport_authority",
          "news_outlet", "commuter_forum", "waze_user",
          "unverified_tip"]``

        **Audit-locked design**: the tier vocabulary lives HERE
        (per-domain pack), NOT as a hardcoded enum in
        ``broker/components/social/post.py``. The
        ``Post.tier_id: str`` field carries an opaque tier
        identifier; broker code MUST NOT interpret it. Forbidden
        broker-side literals (enforced by the
        ``test_framework_invariants.py`` AST gate added in 6T-E):
        ``OFFICIAL`` / ``VERIFIED`` / ``INFLUENCER`` / ``PEER`` /
        ``BOT``.

        Default: empty list ``[]``. A pack that doesn't run a
        social-media channel returns the empty list and the Layer-3
        SocialMediaProvider treats the domain as opt-out.
        """
        ...

    def credibility_weight(self, tier_id: str) -> float:
        """Phase 6T-E: weight in ``[0.0, 1.0]`` for the perception
        filter's weighted sampling. Multiplied with
        :func:`broker.components.social.post.age_weight` and
        ``Post.engagement_score`` to compute the retrieval-side
        weight when sampling top-K posts for the household prompt.

        Default semantics in :class:`DefaultDomainPack`: ``1.0`` for
        known tiers (those in :meth:`credibility_tiers`), ``0.0``
        for unknown tiers (so unknown / spoofed tier_ids are
        filtered out — fail-closed). A pack overriding this method
        may declare a finer-grained credibility model
        (e.g. flood pack: official_authority=1.0,
        verified_account=0.85, influencer=0.6, peer=0.4, bot=0.05).

        The weight is consumed by the Phase 6T-E (deferred-commit)
        ``SocialMediaProvider``; this commit ships the contract.
        """
        ...

    def verbalise_post(self, post: Any) -> str:
        """Phase 6T-E: domain-specific natural-language rendering of
        a :class:`broker.components.social.post.Post` for the
        ``{social_media_feed}`` prompt placeholder.

        ``post`` is a :class:`Post` instance (typed ``Any`` here to
        avoid forcing every pack import the broker module). The
        return value is the prompt-ready string for that single
        post; the provider concatenates top-K calls into the
        placeholder body.

        **Audit-locked design**: verbalisation templates live HERE
        (per-domain pack), NOT in broker/. The flood domain's
        canonical mapping (from the audit doc) is:

        - ``official_authority`` → ``"The Department of Insurance
          announced: {post.text}"``
        - ``verified_account`` → ``"{Verified account} reported:
          {post.text}"``
        - ``influencer`` → ``"A popular voice in the community
          shared: {post.text}"``
        - ``peer`` → ``"Some posters in the community claim:
          {post.text}"``
        - ``bot`` → suppressed by default (see
          :meth:`suppressed_tiers`); configurable to show as ``"An
          unverified account claims: {post.text}"``

        Default in :class:`DefaultDomainPack`: ``f"[{post.tier_id}]
        {post.text}"`` — a debugging-grade rendering. Production
        packs override.
        """
        ...

    def suppressed_tiers(self) -> Set[str]:
        """Phase 6T-E: tier IDs whose posts the perception filter
        drops by default.

        Use case: the flood pack may suppress ``bot`` tier posts
        from being injected into the household prompt (the
        operator can override per-experiment by re-setting this in
        YAML). A vaccination_ma might suppress ``whatsapp_rumor``
        by default while keeping it in audit logs for downstream
        misinformation-tracking analysis.

        Default: ``set()`` — no tiers suppressed. Domains that ship
        social-media channels typically override.
        """
        ...

    def social_media_post_filter(self, agent: Any, post: Any) -> Optional[Any]:
        """Phase 6T-E: per-agent post filter hook.

        Returns the post (possibly transformed) or ``None`` to drop
        the post from this specific agent's feed. The Layer-3
        SocialMediaProvider (deferred-commit) calls this for every
        candidate post before adding it to the prompt feed.

        Use cases:

        - MG-distrust filter: an MG household may not see
          ``official_authority`` posts due to distrust of federal
          agencies. The pack overrides this to return ``None`` for
          ``(agent.is_mg, post.tier_id == "official_authority")``.
        - Echo-chamber filter: a follower of an influencer might
          have algorithmically-prioritised peer content; pack
          overrides to deweight non-followed authors.

        Default in :class:`DefaultDomainPack`: returns ``post``
        unchanged. Packs that want default-passthrough don't need
        to override.
        """
        ...

    # ─── Retrieval tuning (Phase 6H DomainPack v2) ────────────────

    def retrieval_policy(self) -> Dict[str, Any]:
        """Skill-retrieval tuning knobs. Recognised keys: ``"top_n"``
        (int — how many candidate skills to surface to the LLM) and
        ``"min_score"`` (float — relevance cutoff).

        Default ``{}`` → broker uses its framework defaults. A domain
        with many skills can widen ``top_n``; a domain with few can
        leave it. Also overridable via ``agent_types.yaml``
        ``governance.retrieval`` (Phase 6H Item 3).
        """
        ...

    # ─── Population drift monitoring (Phase 6L-A 2026-05-22) ──────

    def drift_policy(self) -> Dict[str, Any]:
        """Population-level drift-monitor thresholds. Recognised keys
        (all floats unless noted): ``entropy_threshold`` (Shannon-entropy
        bits below which a LOW_ENTROPY alert fires), ``stagnation_threshold``
        (fraction of agents whose recent decisions are jaccard-stagnant
        above which HIGH_STAGNATION fires), ``collapse_threshold``
        (dominant-action fraction above which MODE_COLLAPSE fires),
        ``jaccard_stagnation_threshold`` (per-agent jaccard above which
        the agent counts as stagnant), and ``history_window`` (int,
        recent-decision history length feeding the jaccard calc).

        Default ``{}`` → broker uses the
        :class:`broker.components.analytics.drift.DriftDetector`
        constructor defaults (entropy 0.5, stagnation 0.6, collapse 0.9,
        jaccard 0.8, history 5). Also overridable via
        ``agent_types.yaml`` ``governance.drift`` (Phase 6L-A).
        """
        ...

    # ─── Population-governance thresholds (Phase 6L-B 2026-05-22) ─

    def population_governance_policy(self) -> Dict[str, Any]:
        """Population-level governance thresholds bundled into one hook.
        Recognised keys (all floats):
        - ``echo_threshold`` — fraction above which a single skill being
          chosen by the cohort flags an echo-chamber alert (default
          0.8); consumed by
          :class:`broker.validators.governance.cross_agent_validator.CrossAgentValidator`.
        - ``entropy_threshold`` — Shannon entropy bits below which the
          population's decision diversity flags a low-entropy alert
          (default 0.5); also CrossAgentValidator.
        - ``deadlock_threshold`` — rejection rate above which the cohort
          flags a governance-deadlock alert (default 0.5);
          CrossAgentValidator.
        - ``quorum_threshold`` — fraction of sub-validators that must
          approve for the ``MAJORITY`` mode of
          :class:`broker.validators.agent.council.CouncilValidator` to
          approve (default 0.5; set 2/3 ≈ 0.667 for super-majority).

        Default ``{}`` → broker uses the class constructor defaults.
        Also overridable via ``agent_types.yaml``
        ``governance.population`` (Phase 6L-B).
        """
        ...

    # ─── Policy event severity tiers (Phase 6L-C 2026-05-23) ──────

    def policy_event_tiers(self) -> Dict[str, float]:
        """Severity-tier cutoffs consumed by
        :class:`broker.components.events.generators.policy.PolicyEventGenerator`
        when classifying a policy-change magnitude into
        ``EventSeverity.{SEVERE, MODERATE, MINOR, INFO}``.

        Recognised keys (all floats, lowercase severity names):
        ``severe`` / ``moderate`` / ``minor``. A ``|change_pct|`` at or
        above each threshold maps to that severity; below all three →
        INFO. Defaults preserve the pre-6L-C hardcoded
        0.20 / 0.10 / 0.05 cutoffs.

        Default ``{}`` → ``PolicyEventConfig`` constructor defaults
        apply. Also overridable via ``agent_types.yaml``
        ``governance.policy_event_tiers`` (Phase 6L-C).
        """
        ...

    # Phase 6P-E (2026-05-25) added a ``hazard_severity_thresholds``
    # hook here. Phase 6Q-B (2026-05-26) removed it — Phase 6P-E's
    # follow-up audit (5 parallel subagents) confirmed the
    # ``HazardEventGenerator`` had zero non-test production callers and
    # carried a flood-implicit payload schema (``depth_m`` / ``depth_ft``
    # / ``m → ft`` conversion / flood-shaped hazard_module API). The
    # generator was therefore relocated to
    # ``broker.domains.water.event_generators.hazard_per_agent`` instead
    # of being decoupled via this hook. The hook is gone; the move
    # automatically closes the hazard-event-payload genericity finding.

    # ─── Psychological framework (Phase 6Q-D 2026-05-26) ──────────

    def psychological_framework(self) -> str:
        """Framework identifier passed to ``ThinkingValidator(framework=...)``.

        Pre-6Q-D the validator silently defaulted to ``"pmt"``. The
        Phase 6P-E follow-up audit flagged this as a BLOCKER: any
        non-flood domain instantiating the validator without an
        explicit framework= silently inherited the PMT label ordering
        + PMT construct registry, even when the domain declared
        ``psychological_framework: hbm`` (or ``cognitive_appraisal``,
        etc.) in its YAML. The YAML field was dead config — no code
        path piped it into the validator constructor.

        This hook restores that wiring: ``build_domain_validators``
        reads it via ``DomainPackRegistry.get_or_default(domain)
        .psychological_framework()`` and passes it explicitly.

        Recognised values (must be pre-registered via
        :func:`broker.validators.governance.thinking_validator.register_framework_metadata`
        at import time): ``"pmt"`` (flood), ``"cognitive_appraisal"``
        (irrigation), ``"hbm"`` (vaccination), ``"utility"``,
        ``"financial"``. Returning ``""`` (empty string) is the
        escape hatch for domains without registered framework
        metadata — the validator then falls back to a generic 5-level
        VL/L/M/H/VH label ordering with no construct introspection.

        Phase 6T-B (2026-05-27): superseded for multi-agent domains by
        :meth:`framework_for_agent_type` — the new method enables
        per-agent-type framework selection (household → PMT,
        government → utility, insurance → financial). This method is
        kept as the domain-wide default that
        :meth:`framework_for_agent_type` delegates to when the caller
        provides no agent_type or the agent_type isn't recognised.

        Default ``""`` (no metadata) — overridden by every domain pack
        that ships a psychometric framework.
        """
        ...

    def framework_for_agent_type(self, agent_type: Optional[str]) -> str:
        """Phase 6T-B (2026-05-27): per-agent-type framework selector.

        Returns the framework identifier (same vocabulary as
        :meth:`psychological_framework`) that the dispatcher should
        pass to ``ThinkingValidator(framework=...)`` when validating a
        decision FROM an agent of this ``agent_type``. Enables
        institutional diversity in multi-agent domains — e.g. in the
        flood pack:

        - ``household_owner`` / ``household_renter`` → ``"pmt"``
          (Protection Motivation Theory; threat/coping appraisal)
        - ``nj_government`` / ``government`` → ``"utility"``
          (cost-benefit + budget pressure + equity)
        - ``fema_nfip`` / ``insurance`` → ``"financial"``
          (risk appetite + solvency + market share)

        Pre-6T-B every agent type in the flood domain was validated
        under PMT — institutionally inappropriate (a government
        budget decision is not a "threat appraisal"). Closes
        engineering-audit finding Y6.

        Backward compatibility: ``agent_type=None`` or an
        agent_type that the pack doesn't recognise must return the
        same value as :meth:`psychological_framework` — the legacy
        domain-wide default. The :class:`DefaultDomainPack`
        implementation delegates to ``psychological_framework()``
        unconditionally, so packs without per-agent-type overrides
        continue to behave as they did pre-6T-B. Paper-1b
        byte-identity protection: single-agent flood + irrigation
        runs that don't plumb agent_type through ``validate_all``
        continue to resolve via the legacy ``psychological_framework``
        path.

        Wiring: ``broker/components/governance/domain_validator_dispatch.py::build_domain_validators``
        accepts an optional ``agent_type`` and routes through this
        method. ``broker/validators/governance/__init__.py::validate_all``
        plumbs the existing ``agent_type`` parameter down to the
        dispatcher.
        """
        ...

    # ─── Profile loaders (Phase 6P-C 2026-05-25) ──────────────────

    def csv_loader_class(self) -> Optional[Any]:
        """Domain-specific CSV loader class — replaces the hardcoded
        ``if domain_name == "flood":`` branch in
        ``broker/core/agent_initializer.py::initialize_agents``.

        Return a subclass of ``broker.core.agent_initializer.CSVLoader``
        that knows how to populate domain-specific profile fields. The
        broker instantiates it with ``column_mappings=config.get(
        "column_mappings")``.

        Default ``None`` → the generic ``CSVLoader`` is used (loads
        common fields only; domain-specific extensions are ignored).
        Return type kept as ``Optional[Any]`` (not ``Type[CSVLoader]``)
        to avoid forcing every pack import ``broker.core.agent_initializer``.
        """
        ...

    def synthetic_loader_class(self) -> Optional[Any]:
        """Domain-specific synthetic-profile generator class —
        replaces the hardcoded ``if domain_name == "flood":`` branch
        for synthetic mode in ``initialize_agents``. Return a subclass
        of ``broker.core.agent_initializer.SyntheticLoader``; the
        broker instantiates it with ``seed=seed``. Default ``None`` →
        generic ``SyntheticLoader``."""
        ...

    # ─── Phase orchestration (Phase 6P-B 2026-05-25) ──────────────

    def phase_layout(self) -> Optional[List[Any]]:
        """Multi-agent phase execution layout (``List[PhaseConfig]``).

        Replaces the hardcoded ``if domain.lower() == "flood":`` branch
        in ``broker/components/orchestration/phases.py::from_domain``.
        Domains that need a custom phase split (institutional →
        household → resolution → observation, etc.) return their list
        here; domains with a single-phase pipeline return ``None`` and
        the orchestrator falls back to a generic 3-phase layout
        (CUSTOM → RESOLUTION → OBSERVATION).

        Return type kept as ``Optional[List[Any]]`` (not the concrete
        ``PhaseConfig`` class) to avoid forcing every pack import the
        ``broker.interfaces.coordination`` module — most packs return
        ``None`` and never touch the type.

        Default ``None`` (no-op) → generic layout. The flood pack
        overrides to return ``water_default_phases()``.
        """
        ...

    # ─── Phase 6T-C (2026-05-27): institutional lifecycle dispatch ─

    def institutional_lifecycle_handlers(self) -> Dict[str, Any]:
        """Phase 6T-C: per-agent-type lifecycle-handler dispatch table.

        Returns ``Dict[agent_type, InstitutionalLifecycleHandler]``
        (the value type is
        :class:`broker.components.orchestration.institutional_lifecycle.InstitutionalLifecycleHandler`
        but typed ``Any`` here to avoid forcing every pack import the
        broker module). The multi-agent runner consults this map to
        dispatch ``pre_year`` / ``post_decision`` / ``post_year``
        hooks per agent_type without growing a bespoke ``elif
        agent.agent_type == "X":`` chain in the lifecycle file.

        Pre-6T-C the flood ``MultiAgentHooks`` class baked agent-type
        branches into ``post_step`` (lines 547-665 of the bespoke
        ``examples/multi_agent/flood/orchestration/lifecycle_hooks.py``).
        Adding a new institutional agent_type required bloating that
        file with another branch. The hook opens the dispatch
        contract so Phase 6T-F's ``social_media_influencer`` (or any
        future institutional type) registers a handler instead.

        Default ``{}`` (no-op) → multi-agent runner gets no
        per-agent-type handlers and the legacy lifecycle file owns
        the entire dispatch surface. Closes engineering-audit R5+R6
        as an extension point; actual code-movement out of the
        bespoke flood file is deferred to Phase 6T-F when the second
        consumer materialises.
        """
        ...

    def multi_agent_env_keys(self) -> Set[str]:
        """Phase 6T-C: whitelist of env-dict keys this domain pack
        owns + injects when running multi-agent.

        Codifies the env-dict-whitelist convention previously
        implemented as an emergent pattern in each multi-agent
        lifecycle file (e.g. ``govt_budget_remaining``,
        ``crs_discount``, ``subsidy_rate`` for flood). The
        multi-agent runner can use this set to safely synchronise
        env state across phase boundaries without trampling keys
        owned by other domains.

        Default empty set — domains without multi-agent runs return
        ``set()`` (the pre-6T-C silent contract). The flood pack
        documents its multi-agent env keys here for the first time;
        future multi-agent domains add their own.
        """
        ...

    # ─── MemoryBridge resolution importance (Phase 6L-D 2026-05-23) ─

    def bridge_importance_policy(self) -> Dict[str, float]:
        """Per-domain override of the
        :class:`broker.components.memory.bridge.MemoryBridge` resolution
        importance values. Recognised keys (floats):
        ``approved`` (default 0.6) and ``denied`` (default 0.75; the
        higher value reflects the deliberate "denials more memorable"
        behavioural claim — see the inline comment in
        ``MemoryBridge.store_resolution``).

        Default ``{}`` → bridge constructor defaults apply. Also
        overridable via ``agent_types.yaml``
        ``governance.memory.resolution_importance_policy``
        (Phase 6L-D). Domains should preserve the
        ``denied >= approved`` asymmetry unless they have an explicit
        rationale to invert it.
        """
        ...
