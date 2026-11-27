"""
Generic ``Post`` dataclass for social-media propagation channels.

Provides :class:`Post` — a domain-agnostic message envelope that
authors push into ``TieredEnvironment.social_feeds`` and that
:class:`~broker.components.context.providers.SocialMediaProvider` renders
into prompt content via the DomainPack's :meth:`PerceptionPack.verbalise_post`
hook. The ``tier_id: str`` field stays domain-owned via
:meth:`PerceptionPack.credibility_tiers` (see the AST gate in
``broker/tests/test_framework_invariants.py``).

Lifecycle + persistence
=======================
Posts are stored in ``TieredEnvironment.social_feeds: Dict[author_id, List[Post]]``.
The :class:`broker.components.events.exceptions.EventPersistence` enum determines
whether a Post survives period-boundary cleanup:

- ``EPHEMERAL`` — wiped at period boundary.
- ``STICKY_YEAR_DECAY`` — preserved across periods with weighted age decay
  (applied by :class:`~broker.components.context.providers.SocialMediaProvider`
  via :func:`age_weight`).
- ``STICKY_INDEFINITE`` — never wiped.

The DomainPack's :meth:`EventPack.event_persistence_policy` returns
the policy per ``event_type``.
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
    ``STICKY_YEAR_DECAY`` policy's default behaviour. Consumers such as
    :class:`~broker.components.context.providers.SocialMediaProvider` may
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
