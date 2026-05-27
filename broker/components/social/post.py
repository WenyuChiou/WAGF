"""
Phase 6T-E (2026-05-27): generic Post dataclass for social-media
propagation channels.

Provides :class:`Post` — a domain-agnostic message envelope that
authors push into ``TieredEnvironment.social_feeds`` and that
followers' perception filters render into prompt content via
their DomainPack's :meth:`PerceptionPack.verbalise_post` hook.

Audit-locked design (see ``.research/social_media_genericity_audit.md``)
======================================================================
The :class:`Post` dataclass has a ``tier_id: str`` field — NOT a
broker-hardcoded credibility enum. The tier vocabulary
(e.g. ``official_authority / verified_account / influencer / peer
/ bot`` for flood; ``cdc / clinician / health_influencer /
community_elder / whatsapp_rumor`` for a future vaccination_ma
domain) is owned by the DomainPack via :meth:`PerceptionPack.credibility_tiers`.

This is the **third instance** of the broker/domain separation
pattern the audit traces:

1. Phase 6P-A: validator dispatch moved out of water namespace.
2. Phase 6P-E + 6Q-B: hazard event schema moved out of broker/.
3. **Phase 6T-E: tier vocabulary stays in DomainPack.**

Forbidden literals in this module + everywhere under broker/:
``OFFICIAL``, ``VERIFIED``, ``INFLUENCER``, ``PEER``, ``BOT`` —
these belong in ``examples/governed_flood/adapters/flood_perception.py``
(or wherever each domain documents its tier list). The AST gate
in ``broker/tests/test_framework_invariants.py`` enforces this.

Lifecycle + persistence
=======================
Posts are stored in ``TieredEnvironment.social_feeds: Dict[author_id, List[Post]]``
(field wiring lands when the Layer-3 SocialMediaProvider arrives,
not in this commit — see the deferred-work section of the Phase
6T-E CHANGELOG entry). The :class:`broker.components.events.exceptions.EventPersistence`
enum determines whether a Post survives the year-boundary clear:

- ``EPHEMERAL`` — wiped at year boundary (single-cycle propagation;
  unlikely for posts).
- ``STICKY_YEAR_DECAY`` — preserved across years with weighted
  age decay (the default for social-media posts; downstream
  retrieval applies :func:`age_weight` to discount older posts).
- ``STICKY_INDEFINITE`` — never wiped.

The DomainPack's :meth:`EventPack.event_persistence_policy` returns
the policy per ``event_type``. Posts emitted by an event handler
inherit that policy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Post:
    """Domain-agnostic social-media message envelope.

    Fields:

    - ``text`` — the post body. Pack's ``verbalise_post`` may wrap or
      annotate, but ``text`` is the canonical content.
    - ``author_id`` — the publishing agent's ID. The downstream
      :class:`broker.components.social.follower_network.FollowerNetwork`
      uses this to look up followers.
    - ``author_role`` — human-readable role label (e.g.
      ``"government"``, ``"insurance"``, ``"influencer"``). Distinct
      from ``tier_id``: role is what the author IS; tier is how
      credible they are perceived to be. The flood pack maps role →
      tier in :meth:`FloodPerceptionMixin.credibility_tiers` but
      other domains may decouple the two (e.g. a clinician role
      with verified vs unverified accounts at different credibility
      tiers).
    - ``event_year`` — sim-year the post was published. Used by
      :func:`age_weight` to compute time-decay weighting at
      retrieval.
    - ``event_type`` — the originating event type (e.g. ``"flood"``,
      ``"subsidy_change"``). Pack's
      :meth:`EventPack.event_persistence_policy` consults this for
      the lifecycle policy.
    - ``engagement_score`` — float in ``[0.0, +∞)``. Higher = more
      attention. Posts with engagement_score==0 are still valid;
      the retrieval-side weight calculation handles them.
    - ``tier_id`` — opaque string identifying the credibility tier
      within the owning pack's vocabulary. Broker code MUST NOT
      interpret this string; the DomainPack interprets via
      :meth:`PerceptionPack.credibility_weight` and
      :meth:`PerceptionPack.verbalise_post`.
    - ``metadata`` — optional dict for domain-extensible fields
      (e.g. hashtags, related event IDs, embedding vector). Broker
      treats it as opaque payload.
    """

    text: str
    author_id: str
    author_role: str
    event_year: int
    event_type: str
    engagement_score: float = 0.0
    tier_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate the bounded numeric fields.

        Rejecting bad values at construction time is cheaper than
        debugging an unexpected weight downstream. Empty text /
        author / role are NOT rejected — Phase 6T-E doesn't constrain
        their content (a domain may want empty-text posts as
        placeholder/silence signals).
        """
        if self.engagement_score < 0:
            raise ValueError(
                f"Post.engagement_score must be >=0; got "
                f"{self.engagement_score!r}."
            )
        if self.event_year < 0:
            raise ValueError(
                f"Post.event_year must be >=0; got {self.event_year!r}."
            )


def age_weight(
    post_year: int,
    current_year: int,
    half_life_years: float = 2.0,
) -> float:
    """Compute the exponential age-decay weight for a Post.

    Formula: ``weight = 0.5 ** (years_elapsed / half_life_years)``.
    At ``years_elapsed == half_life_years`` the weight is 0.5; at
    ``2 × half_life_years`` it's 0.25; etc.

    A future post (``current_year < post_year``) returns weight
    ``1.0`` — broker doesn't introduce time-travel semantics. In
    practice this branch only fires when the caller swaps argument
    order; the early return is defensive rather than meaningful.

    The default ``half_life_years=2.0`` matches the
    :class:`broker.components.events.exceptions.EventPersistence`
    ``STICKY_YEAR_DECAY`` policy's default behaviour. Downstream
    retrieval (Phase 6T-E SocialMediaProvider, future commit) may
    override per-event-type via the pack's persistence policy.

    The half-life choice is a research lever — domains studying
    short-term viral dynamics may set ``half_life_years=0.5``
    (8-month half-life), while domains studying institutional
    memory may set ``half_life_years=5.0``. This function is
    deliberately a free function (not a Post method) so a domain's
    custom decay (e.g. linear, or piecewise) can replace it
    without subclassing Post.
    """
    if current_year < post_year:
        return 1.0
    if half_life_years <= 0:
        raise ValueError(
            f"age_weight: half_life_years must be >0; got "
            f"{half_life_years!r}."
        )
    elapsed = current_year - post_year
    return 0.5 ** (elapsed / half_life_years)


__all__ = ["Post", "age_weight"]
