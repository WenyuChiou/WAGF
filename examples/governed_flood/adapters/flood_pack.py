"""
FloodDomainPack — concrete :class:`broker.domains.protocol.DomainPack`
implementation for the flood-risk household example.

Phase 6C-v2 (2026-05-10): wraps the existing :class:`FloodAdapter` with
the DomainPack facade and adds the methods previously hardcoded in
broker/ hot paths:

- ``reflection_status_text`` — replaces
  ``broker/components/cognitive/reflection.py:301-313`` (C3)
- ``skill_emotion_metadata`` — replaces
  ``broker/core/experiment_runner.py:383-388`` (W2)
- ``event_handlers`` — replaces
  ``broker/components/events/ma_manager.py:275-330`` chain (W5)
- ``mg_barrier_text`` — replaces the Passaic-specific text in
  ``broker/components/context/providers.py:704-712`` (C2)
- ``extreme_actions`` — replaces the kwarg in
  ``broker/domains/water/validator_bundles.py:87`` (C5 partial)

Phase 6R-D-5 (2026-05-26): the previously-monolithic ``FloodDomainPack``
class body splits into seven sub-pack mixins corresponding to the
seven Protocol sub-types defined in
``broker/domains/protocol.py`` (Phase 6R-D-1):

  FloodReflectionMixin  → ReflectionPack methods
  FloodMemoryMixin      → MemoryPack methods
  FloodSkillMixin       → SkillPack methods
  FloodEventMixin       → EventPack methods
  FloodPerceptionMixin  → PerceptionPack methods
  FloodGovernanceMixin  → GovernancePack methods
  FloodSetupMixin       → SetupPack methods

The composite ``FloodDomainPack`` inherits from all seven mixins +
``DefaultDomainPack`` (for any un-overridden no-op default). Public
surface — ``DomainPackRegistry.register("flood", FloodDomainPack())``
— is unchanged.

**Bug fix piggy-backed**: pre-Phase-6R-D-5, ``csv_loader_class`` and
``synthetic_loader_class`` were defined TWICE in the class body (once
at line 339/347 added by Phase 6R-C, and again at line 424/434
existing since Phase 6P-C). The earlier definitions were dead code
(overwritten by Python's class-dict semantics). The 6R-D-5 refactor
keeps only the Phase 6P-C definitions, now homed in
``FloodSetupMixin``.

Backward compatibility
======================
Every method produces byte-identical output to the pre-refactor
hardcoded site. Verified by ``tests/test_domain_pack_contract.py`` and
Phase 6R-D-5 mock-LLM ``broker.tools.compare_audit_csv`` smoke.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from broker.components.memory.content_types import MemoryContentType
from broker.domains.default import DefaultDomainPack
from broker.interfaces.action_taxonomy import (
    ActionTaxonomyEntry,
    load_action_taxonomy_from_skill_registry,
)
from broker.domains.protocol import BuiltinCheck, EventHandler, MemoryPolicyBundle

from examples.governed_flood.adapters.flood_adapter import FloodAdapter
from examples.governed_flood.adapters.flood_perception import (
    COMMUNITY_OBSERVABLE_FIELDS,
    DOLLAR_AMOUNT_FIELDS,
    NEIGHBOR_ACTION_FIELDS,
    PERCENTAGE_FIELDS,
    PERCEPTION_DESCRIPTORS,
)


# ─────────────────────────────────────────────────────────────────────
# Event handlers — extracted verbatim from
# broker/components/events/ma_manager.py:275-330
# ─────────────────────────────────────────────────────────────────────

def _handle_flood(event: Any, gs: Dict[str, Any]) -> None:
    gs["flood_occurred"] = event.data.get("occurred", True)
    gs["flood_depth_m"] = event.data.get("depth_m", 0)
    gs["flood_depth_ft"] = event.data.get("depth_ft", 0)


def _handle_no_flood(event: Any, gs: Dict[str, Any]) -> None:
    gs["flood_occurred"] = False
    gs["flood_depth_m"] = 0
    gs["flood_depth_ft"] = 0


def _handle_subsidy_change(event: Any, gs: Dict[str, Any]) -> None:
    gs["subsidy_rate"] = event.data.get("new_value", gs.get("subsidy_rate", 0.5))
    gs["govt_message"] = event.description


def _handle_premium_change(event: Any, gs: Dict[str, Any]) -> None:
    gs["premium_rate"] = event.data.get("new_value", gs.get("premium_rate", 0.02))
    gs["insurance_message"] = event.description


# ─────────────────────────────────────────────────────────────────────
# Per-agent impact handlers — extracted verbatim from the flood
# event-type chain in broker/components/events/ma_manager.py:get_agent_impact.
# These AGGREGATE into a per-agent impact dict (max for depth, sum for
# dollar amounts) rather than overwriting global env state.
# ─────────────────────────────────────────────────────────────────────

def _impact_flood(event: Any, impact: Dict[str, Any]) -> None:
    impact["flooded"] = True
    impact["depth_m"] = max(
        impact.get("depth_m", 0.0), event.data.get("depth_m", 0)
    )


def _impact_flood_damage(event: Any, impact: Dict[str, Any]) -> None:
    impact["damage_amount"] = (
        impact.get("damage_amount", 0.0) + event.data.get("damage_amount", 0)
    )
    impact["oop_cost"] = (
        impact.get("oop_cost", 0.0) + event.data.get("oop_cost", 0)
    )


def _impact_insurance_payout(event: Any, impact: Dict[str, Any]) -> None:
    impact["payout_amount"] = (
        impact.get("payout_amount", 0.0) + event.data.get("payout_amount", 0)
    )


# ─────────────────────────────────────────────────────────────────────
# Sub-pack mixins (Phase 6R-D-5, 2026-05-26)
# ─────────────────────────────────────────────────────────────────────
# Each mixin groups the FloodDomainPack overrides that satisfy a single
# Protocol sub-type defined in broker/domains/protocol.py. Composition
# below — ``FloodDomainPack(FloodReflectionMixin, FloodMemoryMixin, ...,
# DefaultDomainPack)`` — preserves the original 1-class registration
# contract while enabling type-narrowed isinstance checks per
# sub-protocol.
#
# The mixins reference ``self._inner`` (set in ``FloodDomainPack.__init__``
# to a ``FloodAdapter`` instance) and other ``self`` attributes via
# normal method binding — Python's MRO resolves correctly.
# ─────────────────────────────────────────────────────────────────────


class FloodReflectionMixin:
    """ReflectionPack methods — agent narrative for reflection prompts."""

    def reflection_status_text(self, context: Any) -> Optional[str]:
        """Flood status line for the individual reflection prompt.

        Summarises the agent's elevated / insured / flood_count /
        mg_status flags into ``"Current status: ..."``. Returns ``None``
        if no flag is set. The elevated/insured/flood_count values are
        read from ``context.custom_traits`` (Phase 6H Item 9 — the flood
        example populates them there; mg_status stays a generic field).
        """
        # Match the original gate: only emit for "household" agent_type.
        if getattr(context, "agent_type", None) != "household":
            return None

        traits = getattr(context, "custom_traits", None) or {}
        status_parts = []
        if traits.get("elevated", False):
            status_parts.append("your house is elevated")
        if traits.get("insured", False):
            status_parts.append("you have flood insurance")
        flood_count = traits.get("flood_count", 0)
        if flood_count > 0:
            status_parts.append(f"you've been flooded {flood_count} time(s)")
        if getattr(context, "mg_status", False):
            status_parts.append("you have limited resources")

        if not status_parts:
            return None
        return f"Current status: {', '.join(status_parts)}."

    def reflection_questions(self) -> List[str]:
        # Empty → AgentTypeConfig.get_reflection_questions() resolves from
        # agent_types.yaml reflection.questions, else the domain-neutral
        # _DEFAULT_REFLECTION_QUESTIONS fallback in reflection.py.
        return []

    def reflection_persona(self) -> Optional[str]:
        return None

    def reflection_trait_labels(self, context: Any) -> List[str]:
        """Short flood trait labels for the compact batch reflection
        prompt. ``flooded {n}x`` short form (distinct from the status-text
        ``flooded {n} time(s)`` long form). elevated/insured/flood_count
        are read from ``context.custom_traits`` (Phase 6H Item 9);
        mg_status stays a generic field."""
        traits = getattr(context, "custom_traits", None) or {}
        labels: List[str] = []
        if traits.get("elevated", False):
            labels.append("elevated")
        if traits.get("insured", False):
            labels.append("insured")
        flood_count = traits.get("flood_count", 0)
        if flood_count > 0:
            labels.append(f"flooded {flood_count}x")
        if getattr(context, "mg_status", False):
            labels.append("MG")
        return labels


class FloodMemoryMixin:
    """MemoryPack methods — importance / emotion / retrieval / policy
    delegation to the legacy FloodAdapter + flood-specific policy bundle."""

    def importance_profiles(self) -> Dict[str, float]:
        return dict(self._inner.importance_profiles)

    def compute_importance(self, context: Any, base: float = 0.9) -> float:
        return self._inner.compute_importance(context, base)

    def classify_emotion(self, decision: str, context: Any) -> str:
        return self._inner.classify_emotion(decision, context)

    def emotional_keywords(self) -> Dict[str, str]:
        return dict(self._inner.emotional_keywords)

    def retrieval_weights(self) -> Dict[str, float]:
        return dict(self._inner.retrieval_weights)

    def memory_policy(self) -> MemoryPolicyBundle:
        """Replaces three flood literals previously hardcoded in
        generic ``broker/components/memory/`` (Phase 6K-A 2026-05-22):
        the ``policy_classifier._DEFAULT_RULES`` flood category keys,
        the ``initial_loader`` EXTERNAL_EVENT whitelist, and the
        ``universal.py`` EMA ``stimulus_key`` fallback."""
        return MemoryPolicyBundle(
            category_rules={
                "flood_experience": MemoryContentType.EXTERNAL_EVENT,
                "flood_event": MemoryContentType.EXTERNAL_EVENT,
                "damage": MemoryContentType.EXTERNAL_EVENT,
                "insurance_claim": MemoryContentType.INITIAL_FACTUAL,
                "insurance_history": MemoryContentType.INITIAL_FACTUAL,
            },
            external_event_whitelist=(
                "flood_experience", "flood_event", "damage",
            ),
            stimulus_key="flood_depth_m",
        )


class FloodSkillMixin:
    """SkillPack methods — skill emotion / extremeness / taxonomy /
    affordability."""

    def skill_emotion_metadata(self, skill_name: str) -> Dict[str, Any]:
        """Reproduces ``experiment_runner.py:383-388`` flood skill→emotion
        mapping byte-identically (importance values 0.7 and 0.6 match
        the pre-refactor literals)."""
        if skill_name in {"elevate_house", "relocate"}:
            return {"emotion": "major", "importance": 0.7, "source": "personal"}
        if skill_name == "buy_insurance":
            return {"emotion": "positive", "importance": 0.6, "source": "personal"}
        # buyout_program and other flood skills fall through to the
        # broker's default "routine" tag (importance 0.1) — preserves
        # pre-refactor behaviour where only the 3 explicitly-named
        # skills got special tags.
        return {}

    def extreme_actions(self) -> Set[str]:
        """Replaces the explicit kwarg in ``validator_bundles.py:87``."""
        return {"relocate", "elevate_house"}

    def action_taxonomy(self) -> Dict[str, ActionTaxonomyEntry]:
        """Phase 6O-B — read taxonomy from single_agent skill_registry.yaml.

        Note: single-agent flood and governed_flood share the same skill
        set (buy_insurance / elevate_house / relocate / do_nothing); the
        canonical taxonomy declaration lives at
        examples/single_agent/skill_registry.yaml.
        """
        from pathlib import Path
        # examples/single_agent/skill_registry.yaml relative to this file
        yaml_path = (
            Path(__file__).resolve().parents[2]
            / "single_agent"
            / "skill_registry.yaml"
        )
        return load_action_taxonomy_from_skill_registry(yaml_path)

    def affordability_constraints(self) -> Dict[str, Any]:
        """Flood elevation cost model — replaces the hardcoded
        ``elevate_house`` rule in ``AgentValidator.validate_affordability()``
        (Phase 6H Item 6). $150k base, 50% subsidy default, affordable
        iff post-subsidy cost <= 3x annual income. Insurance
        affordability stays prompt-level guidance (not a hard gate)."""
        return {
            "elevate_house": {
                "base_cost": 150_000.0,
                "income_multiplier": 3.0,
                "default_subsidy_rate": 0.5,
            },
        }


class FloodEventMixin:
    """EventPack methods — global env mutation + per-agent impact
    aggregation for flood / no_flood / subsidy / premium / damage /
    payout events."""

    def event_handlers(self) -> Dict[str, EventHandler]:
        """Replaces the ``ma_manager.py:275-289`` if/elif chain."""
        return {
            "flood": _handle_flood,
            "no_flood": _handle_no_flood,
            "subsidy_change": _handle_subsidy_change,
            "premium_change": _handle_premium_change,
        }

    def agent_impact_handlers(self) -> Dict[str, EventHandler]:
        """Replaces the flood event-type chain in
        ``ma_manager.py:get_agent_impact()`` (Phase 6J-B)."""
        return {
            "flood": _impact_flood,
            "flood_damage": _impact_flood_damage,
            "insurance_payout": _impact_insurance_payout,
        }

    def silent_skip_event_types(self) -> Set[str]:
        """Phase 6T-A (2026-05-27): ``flood_damage`` and
        ``insurance_payout`` are deliberately impact-only — they
        appear in :meth:`agent_impact_handlers` but NOT in
        :meth:`event_handlers` (they aggregate per-agent damage /
        payout, not global env state). Pre-6T-A the env-sync
        dispatcher silently skipped them; the 6T-A explicit-opt-in
        contract requires this list to preserve that intentional
        skip and avoid :class:`UnhandledEventError`. Code-review P1
        catch — without this override the dispatcher raises on
        every flood_damage / insurance_payout fed to
        ``sync_to_environment``.
        """
        return {"flood_damage", "insurance_payout"}

    # ───────────────────────────────────────────────────────────────
    # Phase 6T-E.B (2026-05-28): post auto-emission
    # ───────────────────────────────────────────────────────────────
    #
    # The dispatcher at ``broker/components/events/ma_manager.py:
    # _sync_event_to_env`` calls ``emit_posts_for_event(event, env)``
    # AFTER the regular handler runs. Posts emitted here are appended
    # to ``env.social_feeds`` via ``env.add_post``. The
    # SocialMediaProvider (Phase 6T-E.B) reads ``env.social_feeds``
    # to inject ``{social_media_feed}`` into household prompts.
    #
    # Paper-3 byte-identity guard: this method early-returns when
    # ``env.global_state.get("_social_feeds_enabled")`` is False
    # (the default for paper-3 flood experiments). The flag is set
    # by the runner after consulting the two-layer resolver in
    # ``broker.components.social.feed_flag``.

    def emit_posts_for_event(self, event: Any, env: Any) -> List[Any]:
        """Phase 6T-E.B: emit Posts for a flood-domain event.

        Returns an empty list when the social-feeds flag is OFF
        (paper-3 default) — no behaviour change at the env level.
        When the flag is ON, emits 1-3 Posts per event, one per
        relevant author role, with ``metadata["canonical_event_id"]``
        set so Phase 6T-G cross-channel dedup can join them with
        OFFICIAL / GLOBAL channel emissions.

        Author roles + tier_ids:
          - ``government`` author → ``official_authority`` tier
          - ``insurance`` author  → ``verified_account`` tier
          - ``peer``       author → ``peer_post`` tier (generic
            household commentary; tier vocabulary lives in
            ``credibility_tiers()`` on this same pack).
        """
        gs = getattr(env, "global_state", {}) if env is not None else {}
        if not gs.get("_social_feeds_enabled"):
            return []

        from broker.components.social.post import Post

        # Per-event-type emission rules. Each tuple is
        # ``(author_id, author_role, tier_id, text)``.
        rules: Dict[str, List[tuple]] = {
            "flood": [
                ("nj_government", "government", "official_authority",
                 f"Flood advisory: {event.description}"),
                ("peer_residents", "peer", "peer_post",
                 f"Neighbors reporting flooding — depth around "
                 f"{event.data.get('depth_ft', 0)} ft."),
            ],
            "no_flood": [
                ("nj_government", "government", "official_authority",
                 "All-clear: no flooding this year."),
            ],
            "subsidy_change": [
                ("nj_government", "government", "official_authority",
                 event.description),
            ],
            "premium_change": [
                ("fema_nfip", "insurance", "verified_account",
                 event.description),
            ],
        }

        emissions = rules.get(event.event_type, [])
        if not emissions:
            return []

        # ``EnvironmentEvent`` itself has no ``year`` field — the
        # simulation year lives on ``env.global_state["year"]`` (the
        # MA runner sets it at the start of each year). Fall back to
        # 0 only when env is somehow missing the key.
        sim_year = int(gs.get("year", 0) or 0)
        canonical_id = (
            f"{event.event_type}:{sim_year}:"
            f"{event.data.get('location', 'global')}"
        )
        out: List[Any] = []
        for author_id, author_role, tier_id, text in emissions:
            try:
                post = Post(
                    text=text,
                    author_id=author_id,
                    author_role=author_role,
                    event_year=sim_year,
                    event_type=event.event_type,
                    engagement_score=0.0,
                    tier_id=tier_id,
                    metadata={"canonical_event_id": canonical_id},
                )
            except ValueError:
                # Defensive: Post.__post_init__ rejects negative
                # event_year / engagement_score. Skip silently —
                # the dispatcher's outer try/except will catch
                # anything else.
                continue
            out.append(post)
        return out


class FloodPerceptionMixin:
    """PerceptionPack methods — verbalisation rules + field stripping
    policy + passthrough institutional types."""

    def social_feeds_default_enabled(self) -> bool:
        """Phase 6T-E.B (2026-05-28): pack-level default = False.

        Paper-3 v21 5-seed gemma3:4b dataset was generated before
        social feeds existed; keeping this False guarantees byte-
        identity for any flood experiment that doesn't explicitly
        flip ``global_config.social_feeds.enable = true`` in YAML.
        """
        return False

    def perception_descriptors(self) -> Dict[str, Any]:
        """Numeric→qualitative verbalization rules for the household
        perception filter, keyed by INPUT context field (Phase 6H
        Item 5b). `PerceptionFilterRegistry` injects these."""
        return dict(PERCEPTION_DESCRIPTORS)

    def perception_field_policy(self) -> Dict[str, List[str]]:
        """Field-name lists controlling what QualitativePerceptionFilter
        strips / aggregates — replaces the former module-level flood
        constants in broker/components/social/perception.py."""
        return {
            "dollar_fields": list(DOLLAR_AMOUNT_FIELDS),
            "percentage_fields": list(PERCENTAGE_FIELDS),
            "community_observable_fields": list(COMMUNITY_OBSERVABLE_FIELDS),
            "neighbor_action_fields": list(NEIGHBOR_ACTION_FIELDS),
        }

    def passthrough_agent_types(self) -> Set[str]:
        """Government and insurance are institutional agents — they
        perceive raw numerical data (Phase 6H Item 5c). Households
        verbalize (the default).

        The MA-flood subtypes ``nj_government`` / ``fema_nfip`` are
        deliberately NOT listed: pre-6H they fell through to the
        verbalizing default, and MA flood (Paper 3) is frozen — keeping
        them off this set preserves byte-identical perception. List them
        here if a future MA-flood run wants institutional subtypes to
        see raw numbers."""
        return {"government", "insurance"}


class FloodGovernanceMixin:
    """GovernancePack methods — framework selector + validator bundle
    + placeholder allowlist extension."""

    def psychological_framework(self) -> str:
        """Phase 6Q-D (2026-05-26): PMT (Protection Motivation Theory)
        — the framework pre-registered by
        ``broker.domains.water.thinking_checks`` at import time.
        Matches the ``psychological_framework: pmt`` declaration in
        ``examples/governed_flood/config/agent_types.yaml`` (which
        pre-6Q-D was dead config — no code piped the YAML field into
        ``ThinkingValidator(framework=...)``).

        Phase 6T-B (2026-05-27): superseded for MA-flood by
        :meth:`framework_for_agent_type` — kept as the domain-wide
        default for backward compatibility (single-agent flood +
        callers that don't plumb agent_type through ``validate_all``)."""
        return "pmt"

    # Phase 6T-B (2026-05-27): per-agent-type framework table — closes
    # engineering-audit Y6. Households reason under PMT (threat /
    # coping appraisal); government reasons under utility (cost-benefit
    # + budget pressure + equity); insurance reasons under financial
    # (risk appetite + solvency + market share). All four framework
    # labels are pre-registered with their construct registries +
    # label orderings + label-text mappings via
    # ``broker.domains.water.thinking_checks.register_water_metadata``.
    _AGENT_TYPE_FRAMEWORK: Dict[str, str] = {
        "household_owner": "pmt",
        "household_renter": "pmt",
        "nj_government": "utility",
        "government": "utility",
        "fema_nfip": "financial",
        "insurance": "financial",
        # Phase 6T-F prep (2026-05-27): social_media_influencer
        # agent_type reasons under narrative_diffusion framework
        # (constructs: salience / virality / audience_fit /
        # narrative_consistency). The agent_type itself is not yet
        # in the MA-flood YAML — that's Phase 6T-F-implementation;
        # this entry is the interface contract so that wiring lands
        # cleanly when the implementation commit follows.
        "social_media_influencer": "narrative_diffusion",
    }

    def framework_for_agent_type(self, agent_type: Optional[str]) -> str:
        """Phase 6T-B (2026-05-27): per-agent-type framework selector
        for the multi-agent flood domain.

        Returns the appropriate framework label for the supplied
        ``agent_type``:

        - ``household_owner`` / ``household_renter`` → ``"pmt"``
        - ``nj_government`` / ``government`` → ``"utility"``
        - ``fema_nfip`` / ``insurance`` → ``"financial"``

        Unknown / ``None`` agent_type falls through to
        :meth:`psychological_framework` (``"pmt"``), preserving
        single-agent flood byte-identity for callers that don't plumb
        agent_type (e.g. ``examples/governed_flood/run_experiment.py``
        which only runs household_owner and lets the legacy domain-wide
        default apply).

        Each returned framework label is pre-registered with its
        construct registry + label ordering via
        ``broker.domains.water.thinking_checks.register_water_metadata``
        — the dispatcher's pre-construction framework-registry check
        (Phase 6Q-D-4) accepts all four values without downgrade.
        """
        if agent_type is None:
            return self.psychological_framework()
        normalised = agent_type.strip().lower()
        return self._AGENT_TYPE_FRAMEWORK.get(
            normalised,
            self.psychological_framework(),
        )

    # Phase 6T-F.1 (2026-05-29): NarrativeDiffusionFramework emits generic
    # expected-behavior verbs (``amplify`` / ``counter_narrative`` /
    # ``share`` / ``stay_silent`` — see
    # ``broker/validators/governance/frameworks/narrative_diffusion.py``).
    # This table maps those verbs to the flood-domain influencer's concrete
    # post-action skills (declared in the separate
    # ``examples/multi_agent/flood/config/skill_registry_influencer.yaml``).
    # It is the data half of the influencer interface contract — the
    # framework-binding half is :attr:`_AGENT_TYPE_FRAMEWORK` above.
    _NARRATIVE_DIFFUSION_SKILL_MAP: Dict[str, str] = {
        "amplify": "amplify_event",
        "counter_narrative": "post_counter_narrative",
        "share": "share_success_story",
        "stay_silent": "maintain_silence",
    }

    def narrative_diffusion_skill_map(self) -> Dict[str, str]:
        """Phase 6T-F.1: map ``NarrativeDiffusionFramework`` generic
        expected-behavior verbs to the flood influencer's concrete skill
        ids.

        Mirrors PMT's appraisal/verb -> concrete-skill indirection
        (``broker/domains/water/pmt.py:_DEFAULT_BEHAVIOR_MAP``) but for the
        narrative-diffusion channel. Returns a copy so callers cannot mutate
        the class-level table.

        Not yet consumed by any validator — this is the data half of the
        Phase 6T-F interface contract. The Phase 6T-F.3 narrative
        action-coherence check will read this map to resolve which concrete
        post-action a framework verb expects (and hence which to block).
        Adding it here, alongside :attr:`_AGENT_TYPE_FRAMEWORK`, keeps the
        framework binding and the verb->skill resolution co-located.
        """
        return dict(self._NARRATIVE_DIFFUSION_SKILL_MAP)

    def builtin_checks(self) -> Dict[str, List[BuiltinCheck]]:
        # Already registered via ValidatorRegistry at
        # examples/governed_flood/validators/__init__.py import time.
        return {}

    def prompt_placeholder_extensions(self) -> Set[str]:
        """Flood-domain narrative placeholders injected by water-domain
        context providers at runtime — ``validate_prompt`` must NOT warn
        about these for flood YAML even though they're not in the base
        ``BROKER_FILLED_PLACEHOLDERS`` set.

        Phase 6R-B-3 (audit cluster E #16): proper fix for the
        Phase 6Q-K-3 asymmetric coverage. Pre-fix, these 3 names lived
        in ``BROKER_FILLED_PLACEHOLDERS`` (a flood-domain leak in
        generic CLI code); now they're declared here in the
        flood-domain pack where they belong.

        - ``insurance_cost_text`` — quantitative cost disclosure
          (``InsuranceInfoProvider`` at
          ``broker/components/context/providers.py:524``).
        - ``mg_barrier_text`` — Passaic River Basin
          managerial-grant narrative (``FloodDomainPack.mg_barrier_text``).
        - ``renewal_fatigue_text`` — multi-year insurance lapse
          narrative.
        """
        return {
            "insurance_cost_text",
            "mg_barrier_text",
            "renewal_fatigue_text",
            # Phase 6T-E.B v0.5.1 (2026-05-28): {social_media_feed} is
            # injected by SocialMediaProvider (broker/components/context/
            # providers.py). When the social_feeds flag is OFF, the
            # placeholder resolves to "" — byte-identity preserved
            # because the household templates place {social_media_feed}
            # flush against {neighbor_action_summary} with no template-
            # side newlines.
            "social_media_feed",
        }


class FloodSetupMixin:
    """SetupPack methods — context narrative + agent initialisation
    classes + phase orchestration."""

    def mg_barrier_text(self, profile: Dict[str, Any]) -> str:
        """Reproduces the Passaic-specific text in ``providers.py:706-712``.

        The original site applies this only when (is_mg, flood_count==1,
        not flooded_this_year, not has_insurance). We keep that gating
        logic in providers.py and just return the text body here so the
        broker code can stay generic.
        """
        return (
            "- **Insurance Enrollment Context**: Among households with your "
            "income profile and community background in the Passaic River Basin "
            "who have experienced one prior flood, carrying NFIP flood insurance "
            "is uncommon — many face enrollment barriers including documentation "
            "requirements, upfront costs, and distrust of federal programs."
        )

    def initial_memory_templates(self, profile: Dict[str, Any]) -> List[Any]:
        # Provided via FloodMemoryTemplateProvider (Phase 6B-2);
        # broker.core.agent_initializer continues to use that path.
        return []

    def csv_loader_class(self) -> Any:
        """Phase 6P-C (2026-05-25): replaces the hardcoded
        ``if domain_name == "flood":`` branch in
        ``broker/core/agent_initializer.py::_resolve_csv_loader_class``.
        ``FloodCSVLoader`` populates the flood-specific profile fields
        (zone, depth, household_value, etc.) on top of the generic
        ``CSVLoader``.

        Phase 6R-D-5 (2026-05-26): de-duplicated. Pre-fix, this method
        was accidentally defined twice in the class body (once at
        line 339/347 added by Phase 6R-C, again at line 424/434
        existing since Phase 6P-C). Python class-dict semantics gave
        the LATER definition (Phase 6P-C version) precedence — but
        the dead code was confusing. The Phase 6P-C version is
        preserved here as the single source of truth.
        """
        from broker.domains.water.loaders import FloodCSVLoader
        return FloodCSVLoader

    def synthetic_loader_class(self) -> Any:
        """Phase 6P-C (2026-05-25): replaces the hardcoded
        ``if domain_name == "flood":`` branch in
        ``broker/core/agent_initializer.py::_resolve_synthetic_loader_class``.
        ``FloodSyntheticLoader`` generates flood-specific synthetic
        profiles with PRB-grid-aware zone assignment.

        Phase 6R-D-5 (2026-05-26): de-duplicated (see
        ``csv_loader_class`` docstring above).
        """
        from broker.domains.water.loaders import FloodSyntheticLoader
        return FloodSyntheticLoader

    def phase_layout(self) -> List[Any]:
        """Phase 6P-B (2026-05-25): replaces the hardcoded
        ``if domain.lower() == "flood":`` branch in
        ``broker/components/orchestration/phases.py::from_domain``.
        Returns the four-phase water MAS execution order
        (institutional → household → resolution → observation)."""
        from broker.domains.water.phase_layouts import water_default_phases
        return water_default_phases()

    # Phase 6P-E (2026-05-25) added a ``hazard_severity_thresholds``
    # override here returning the four flood water-depth thresholds.
    # Phase 6Q-B (2026-05-26) removed both the override AND the
    # underlying Protocol hook — ``HazardEventGenerator`` itself
    # relocated to ``broker.domains.water.event_generators.hazard_per_agent``,
    # so the thresholds now live alongside their consumer in the
    # water namespace (``HazardEventConfig.severity_thresholds``
    # default factory unchanged).


# ─────────────────────────────────────────────────────────────────────
# Composite — FloodDomainPack
# ─────────────────────────────────────────────────────────────────────
# Inherits from the seven sub-pack mixins (Phase 6R-D-5) plus
# ``DefaultDomainPack`` for any DomainPack method none of the mixins
# overrides. Python MRO: mixin overrides win over DefaultDomainPack
# no-op defaults; un-overridden methods fall through to
# DefaultDomainPack.
# ─────────────────────────────────────────────────────────────────────


class FloodDomainPack(
    FloodReflectionMixin,
    FloodMemoryMixin,
    FloodSkillMixin,
    FloodEventMixin,
    FloodPerceptionMixin,
    FloodGovernanceMixin,
    FloodSetupMixin,
    DefaultDomainPack,
):
    """DomainPack for the flood-risk household example — composite of
    the seven Phase 6R-D-5 sub-pack mixins.

    Public surface unchanged from Phase 6C-v2:
    ``DomainPackRegistry.register("flood", FloodDomainPack())``.
    Existing consumers calling ``pack.reflection_status_text(...)``,
    ``pack.event_handlers()``, etc. continue to work — Python MRO
    resolves each method to the relevant mixin.
    """

    name: str = "flood"

    def __init__(self) -> None:
        self._inner = FloodAdapter()
