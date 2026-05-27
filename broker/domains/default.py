"""
DefaultDomainPack — no-op implementation of :class:`DomainPack`.

Returned by :func:`DomainPackRegistry.get_or_default` when no pack is
registered for the requested domain. Every method returns a benign
default so broker code can call into the pack unconditionally without
guarding for ``None``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from broker.interfaces.action_taxonomy import ActionTaxonomyEntry
from broker.domains.protocol import BuiltinCheck, EventHandler


class DefaultDomainPack:
    """Sentinel pack — every method is a safe no-op.

    Used when:
      - The experiment hasn't declared a ``domain`` (early bring-up of
        a new application).
      - The declared domain is unknown to the registry (typo or pack
        not yet imported).
      - A test exercises the pipeline with no domain wiring.

    Behavioural contract: calling any method MUST NOT mutate state.
    """

    name: str = "default"

    # ─── Reflection ───────────────────────────────────────────────

    def reflection_status_text(self, context: Any) -> Optional[str]:
        return None

    def reflection_questions(self) -> List[str]:
        return []

    def reflection_persona(self) -> Optional[str]:
        return None

    def reflection_trait_labels(self, context: Any) -> List[str]:
        return []

    # ─── Memory / importance / emotion ────────────────────────────

    def importance_profiles(self) -> Dict[str, float]:
        return {}

    def compute_importance(self, context: Any, base: float = 0.5) -> float:
        return base

    def classify_emotion(self, decision: str, context: Any) -> str:
        return "neutral"

    def emotional_keywords(self) -> Dict[str, str]:
        return {}

    def retrieval_weights(self) -> Dict[str, float]:
        # Equal weights — no domain-informed bias.
        return {"W_recency": 1.0 / 3, "W_importance": 1.0 / 3, "W_context": 1.0 / 3}

    # ─── Skills ────────────────────────────────────────────────────

    def skill_emotion_metadata(self, skill_name: str) -> Dict[str, Any]:
        return {}

    def extreme_actions(self) -> Set[str]:
        return set()

    # ─── Events ────────────────────────────────────────────────────

    def event_handlers(self) -> Dict[str, EventHandler]:
        return {}

    def agent_impact_handlers(self) -> Dict[str, EventHandler]:
        return {}

    # ─── Phase 6T-A (2026-05-27): dispatch + lifecycle defaults ──

    def event_type_to_domain(self, event_type: str) -> Optional[str]:
        """Phase 6T-A default: this pack OWNS ``event_type`` for ENV
        SYNC iff it appears in :meth:`event_handlers`. Returns
        ``self.name`` on ownership, ``None`` otherwise.

        Impact-only event types (in :meth:`agent_impact_handlers` but
        NOT :meth:`event_handlers`) are dispatched via the separate
        :meth:`MAEventManager.get_agent_impact` path and DO NOT count
        as env-sync ownership. Pack authors who deliberately register
        an event_type for impact-only aggregation MUST also list it
        in :meth:`silent_skip_event_types` so the env-sync dispatcher
        skips it instead of raising :class:`UnhandledEventError`.

        Rationale (Phase 6T-A code-review P1 catch, 2026-05-27): the
        pre-6T-A dispatcher silently skipped impact-only types
        (because they weren't in ``event_handlers``); the 6T-A
        explicit-opt-in contract requires the pack to declare
        intentional env-sync skip via :meth:`silent_skip_event_types`.
        Including impact handlers in the ownership check would
        regress to "claimed but no handler" → raise, which is wrong.

        Override in a pack to claim event_types the pack emits but
        doesn't directly handle (Phase 6T-E social-media observer
        pattern).
        """
        if event_type in self.event_handlers():
            return self.name
        return None

    def event_persistence_policy(self, event_type: str):
        """Phase 6T-A default: every event is ``EPHEMERAL``. Matches
        the pre-6T-A behaviour where ``MAEventManager.clear_year``
        discarded everything at the year boundary.

        Override in a pack to opt specific event_types into
        ``STICKY_YEAR_DECAY`` (Phase 6T-E social-media posts) or
        ``STICKY_INDEFINITE`` (Phase 6T-F influencer reputation, etc.).
        """
        from broker.components.events.exceptions import EventPersistence
        return EventPersistence.EPHEMERAL

    def silent_skip_event_types(self) -> Set[str]:
        """Phase 6T-A default: empty set — no event_types are
        legitimately unhandled. Override to acknowledge
        observational / metrics-only events the pack emits but does
        not act on.
        """
        return set()

    # ─── Memory policy (Phase 6K-A) ───────────────────────────────

    def action_taxonomy(self) -> Dict[str, ActionTaxonomyEntry]:
        """Phase 6O-B default — empty mapping (opt-out)."""
        return {}

    def memory_policy(self):  # -> Optional[MemoryPolicyBundle]
        return None

    # ─── Context provider hooks ────────────────────────────────────

    def mg_barrier_text(self, profile: Dict[str, Any]) -> str:
        return ""

    # ─── Validators ────────────────────────────────────────────────

    def builtin_checks(self) -> Dict[str, List[BuiltinCheck]]:
        return {}

    # ─── Memory templates ─────────────────────────────────────────

    def initial_memory_templates(self, profile: Dict[str, Any]) -> List[Any]:
        return []

    # ─── Perception (Phase 6H DomainPack v2) ──────────────────────

    def perception_descriptors(self) -> Dict[str, Any]:
        return {}

    def perception_field_policy(self) -> Dict[str, List[str]]:
        return {}

    def passthrough_agent_types(self) -> Set[str]:
        return set()

    # ─── Phase 6T-E (2026-05-27): social-media credibility defaults ─

    def credibility_tiers(self) -> List[str]:
        """Phase 6T-E default: empty list — pack doesn't ship a
        social-media channel. The Layer-3 SocialMediaProvider
        treats this as opt-out.
        """
        return []

    def credibility_weight(self, tier_id: str) -> float:
        """Phase 6T-E default: 1.0 for known tiers (those in
        :meth:`credibility_tiers`), 0.0 for unknown. Fail-closed
        so unknown / spoofed tier_ids are filtered out at sample
        time.
        """
        if tier_id in self.credibility_tiers():
            return 1.0
        return 0.0

    def verbalise_post(self, post: Any) -> str:
        """Phase 6T-E default: ``f"[{post.tier_id}] {post.text}"``
        debugging-grade rendering. Production packs override with
        domain-appropriate templates.
        """
        return f"[{getattr(post, 'tier_id', '')}] {getattr(post, 'text', '')}"

    def suppressed_tiers(self) -> Set[str]:
        """Phase 6T-E default: empty set — no tiers suppressed."""
        return set()

    def social_media_post_filter(self, agent: Any, post: Any) -> Optional[Any]:
        """Phase 6T-E default: returns the post unchanged. Packs
        with per-agent filtering (MG-distrust, echo-chamber,
        algorithmic ranking) override.
        """
        return post

    def prompt_placeholder_extensions(self) -> Set[str]:
        # Phase 6R-B-3 (audit cluster E #16): default contract — no
        # domain-specific placeholders. Generic domains rely on
        # ``BROKER_FILLED_PLACEHOLDERS`` alone.
        return set()

    def affordability_constraints(self) -> Dict[str, Any]:
        return {}

    # ─── Retrieval tuning (Phase 6H DomainPack v2) ────────────────

    def retrieval_policy(self) -> Dict[str, Any]:
        return {}

    # ─── Population drift monitoring (Phase 6L-A) ─────────────────

    def drift_policy(self) -> Dict[str, Any]:
        return {}

    # ─── Population-governance thresholds (Phase 6L-B) ────────────

    def population_governance_policy(self) -> Dict[str, Any]:
        return {}

    # ─── Policy event severity tiers (Phase 6L-C) ─────────────────

    def policy_event_tiers(self) -> Dict[str, float]:
        return {}

    # Phase 6Q-B (2026-05-26): the ``hazard_severity_thresholds``
    # default added in 6P-E was removed when ``HazardEventGenerator``
    # relocated to ``broker.domains.water.event_generators.hazard_per_agent``.

    # ─── Psychological framework (Phase 6Q-D) ─────────────────────

    def psychological_framework(self) -> str:
        """Default → blessed escape-hatch sentinel
        ``FRAMEWORK_ESCAPE_HATCH`` (``""``). ``ThinkingValidator``
        accepts this as an explicit no-metadata signal — generic
        5-level VL/L/M/H/VH ordering, empty construct registry.
        Domains with a registered psychometric framework override."""
        from broker.validators.governance.thinking_validator import (
            FRAMEWORK_ESCAPE_HATCH,
        )
        return FRAMEWORK_ESCAPE_HATCH

    def framework_for_agent_type(self, agent_type: Optional[str]) -> str:
        """Phase 6T-B default: delegate to :meth:`psychological_framework`.

        Packs without per-agent-type framework specialisation get the
        legacy domain-wide framework regardless of ``agent_type`` —
        preserving pre-6T-B behaviour for single-agent flood +
        irrigation + vaccination + any custom pack that hasn't opted
        into per-type framework selection.

        Multi-agent packs (FloodGovernanceMixin) override to return
        per-agent-type framework labels (household_owner → ``"pmt"``,
        government → ``"utility"``, insurance → ``"financial"``).
        ``agent_type=None`` MUST continue to return the domain-wide
        default so callers that don't plumb agent_type get the
        legacy value.
        """
        return self.psychological_framework()

    # ─── Profile loaders (Phase 6P-C) ─────────────────────────────

    def csv_loader_class(self) -> Optional[Any]:
        """Default → ``None`` → broker uses the generic ``CSVLoader``."""
        return None

    def synthetic_loader_class(self) -> Optional[Any]:
        """Default → ``None`` → broker uses the generic ``SyntheticLoader``."""
        return None

    # ─── Phase orchestration (Phase 6P-B) ─────────────────────────

    def phase_layout(self) -> Optional[List[Any]]:
        """Default → ``None`` so the orchestrator falls back to a
        generic 3-phase layout (CUSTOM → RESOLUTION → OBSERVATION)."""
        return None

    # ─── Phase 6T-C (2026-05-27): institutional lifecycle defaults ─

    def institutional_lifecycle_handlers(self) -> Dict[str, Any]:
        """Phase 6T-C default: empty dict — no per-agent-type lifecycle
        handlers registered. Multi-agent runners that consult this map
        fall back to their bespoke dispatch (e.g. the flood
        ``MultiAgentHooks`` class branches). Override in a pack to
        register :class:`InstitutionalLifecycleHandler` subclasses
        keyed by agent_type.
        """
        return {}

    def multi_agent_env_keys(self) -> Set[str]:
        """Phase 6T-C default: empty set — no domain-owned env keys
        declared. Multi-agent runners that consult this set get the
        pre-6T-C silent contract (env-key ownership is implicit).
        Override to codify the whitelist for a multi-agent domain.
        """
        return set()

    # ─── MemoryBridge resolution importance (Phase 6L-D) ──────────

    def bridge_importance_policy(self) -> Dict[str, float]:
        return {}
