"""Phase 6T-F.2 (2026-05-29): social_media_influencer lifecycle handler.

The SECOND concrete consumer of the Phase 6T-C
:class:`~broker.components.orchestration.institutional_lifecycle.InstitutionalLifecycleHandler`
extension point (government / insurance still run through the bespoke flood
``MultiAgentHooks`` class — see that ABC's module docstring for why the
extraction was deferred until a second consumer existed). This handler
turns an influencer's accepted post-action decision into a
:class:`~broker.components.social.post.Post` appended to the environment's
``social_feeds`` via ``env.add_post``.

Scope (6T-F.2): ``decision -> Post -> env.add_post`` plus the influencer's
execution-phase placement (:data:`INFLUENCER_PHASE_ORDER` /
:func:`insert_influencer_phase`). The ERROR-level narrative
action-coherence validators are 6T-F.3; the FollowerNetwork seeding +
end-to-end mock smoke that makes these posts visible to households is
6T-F.4.

Domain placement: this is flood-DOMAIN code (flood-flavoured post text +
the flood ``"influencer"`` credibility tier), so it correctly lives in the
example tree, not under ``broker/``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from broker.components.orchestration.institutional_lifecycle import (
    InstitutionalLifecycleHandler,
)


# Map each post-action skill to the Post body the influencer publishes.
# ``maintain_silence`` is intentionally absent — it produces no Post.
# Keys MUST match the skill ids in
# ``examples/multi_agent/flood/config/skill_registry_influencer.yaml`` and
# the verb->skill map VALUES in
# ``FloodGovernanceMixin.narrative_diffusion_skill_map``.
_POST_TEMPLATES: Dict[str, str] = {
    "amplify_event": (
        "Flood risk is real and rising this season — do not wait for the "
        "next event to think about protecting your home."
    ),
    "post_counter_narrative": (
        "Setting the record straight on some misleading flood claims going "
        "around: check your actual zone and the real cost of insurance "
        "before you decide it cannot happen to you."
    ),
    "share_success_story": (
        "A neighbour who elevated last year rode out the flood with almost "
        "no damage — adaptation works when you plan ahead."
    ),
}

# The influencer's author_role + credibility tier in the flood domain's
# tier vocabulary (broker/components/social/post.py lists ``influencer``
# among the flood tiers). 6T-F.4 wires the flood pack's
# credibility_tiers()/verbalise_post() to recognise this tier when
# rendering household feeds.
INFLUENCER_AUTHOR_ROLE = "influencer"
INFLUENCER_TIER_ID = "influencer"

# The no-post action (kept as a named constant for callers/tests).
SILENCE_SKILL = "maintain_silence"


def _agent_id(agent: Any) -> str:
    """Best-effort agent identifier, tolerant of the runner's agent type."""
    for attr in ("agent_id", "id", "name"):
        val = getattr(agent, attr, None)
        if isinstance(val, str) and val:
            return val
    return "social_media_influencer"


def _reasoning(agent: Any) -> str:
    """Return the influencer's free-text reasoning if the runner stashed it
    on the agent (so the published post carries the model's own words);
    empty string when unavailable.

    Best-effort enrichment only — NOT load-bearing. The exact
    ``dynamic_state`` slot is finalised when 6T-F.4 wires the runner; this
    reads the common candidates and falls back to the template alone.
    """
    state = getattr(agent, "dynamic_state", None)
    if isinstance(state, dict):
        for key in ("reasoning", "last_reasoning", "decision_reasoning"):
            val = state.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return ""


class InfluencerLifecycleHandler(InstitutionalLifecycleHandler):
    """Turns an accepted influencer post-action into a social-feed Post.

    Only :meth:`post_decision` is overridden — the influencer has no
    start-of-year or end-of-year side effects in 6T-F.2.
    """

    def post_decision(
        self,
        agent: Any,
        decision: str,
        year: int,
        env: Any,
    ) -> None:
        """Publish the influencer's chosen post to ``env.social_feeds``.

        ``decision`` is the EXECUTED skill (post-governance, per the
        EXECUTED-ONLY rule). ``maintain_silence`` (or any skill not in
        :data:`_POST_TEMPLATES`) emits nothing. Everything else builds a
        :class:`Post` and appends it via ``env.add_post``. If ``env`` does
        not expose a callable ``add_post`` (e.g. a runner that has not yet
        wired the TieredEnvironment — that wiring is 6T-F.4), this is a
        no-op rather than a crash.
        """
        template = _POST_TEMPLATES.get(decision)
        if template is None:
            # maintain_silence or an unmapped skill — publish nothing.
            return None

        add_post = getattr(env, "add_post", None)
        if not callable(add_post):
            return None

        reasoning = _reasoning(agent)
        text = f"{template} {reasoning}".strip() if reasoning else template

        from broker.components.social.post import Post

        post = Post(
            text=text,
            author_id=_agent_id(agent),
            author_role=INFLUENCER_AUTHOR_ROLE,
            event_year=int(year),
            event_type=decision,
            engagement_score=0.0,
            tier_id=INFLUENCER_TIER_ID,
            metadata={"narrative_action": decision},
        )
        add_post(post)
        return None


# ── Execution-phase placement ────────────────────────────────────────
#
# The influencer is an active decider that must run AFTER the institutional
# agents set policy (so it can react to this year's subsidy/premium) and
# BEFORE households decide (so its posts are already in env.social_feeds
# when the household SocialMediaProvider builds their prompts). This is the
# dependency contract for 6T-F.2; 6T-F.4 feeds it to
# ``ExperimentBuilder.with_phase_order``.
INFLUENCER_PHASE_ORDER: List[List[str]] = [
    ["government"],
    ["insurance"],
    ["social_media_influencer"],
    ["household_owner", "household_renter"],
]


def insert_influencer_phase(
    base_order: List[List[str]],
    *,
    influencer_type: str = "social_media_influencer",
    household_types: Optional[List[str]] = None,
) -> List[List[str]]:
    """Return ``base_order`` with the influencer phase inserted directly
    before the first phase that contains a household agent_type, preserving
    every other phase and its order.

    Used by 6T-F.4 to slot the influencer into an existing flood phase
    order without hard-coding the full list. Invariant guaranteed: the
    influencer decides after any institutional phase that precedes the
    households and before the households themselves.
    """
    # Idempotency guard: if the influencer phase is already present (a
    # re-entrant call, or a hand-built order that already slots it), return
    # a copy unchanged so the influencer never fires twice per year.
    if any(influencer_type in phase for phase in base_order):
        return [list(phase) for phase in base_order]

    households = set(household_types or ["household_owner", "household_renter"])
    out: List[List[str]] = []
    inserted = False
    for phase in base_order:
        if not inserted and any(a in households for a in phase):
            out.append([influencer_type])
            inserted = True
        out.append(list(phase))
    if not inserted:
        # No household phase found — append the influencer last so it still
        # appears exactly once.
        out.append([influencer_type])
    return out


__all__ = [
    "InfluencerLifecycleHandler",
    "INFLUENCER_PHASE_ORDER",
    "insert_influencer_phase",
    "INFLUENCER_AUTHOR_ROLE",
    "INFLUENCER_TIER_ID",
    "SILENCE_SKILL",
]
