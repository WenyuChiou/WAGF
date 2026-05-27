"""
Phase 6T-D (2026-05-27): directed asymmetric author→follower graph
for social-media propagation channels.

Provides :class:`FollowerNetwork`, a generic primitive that the
Phase 6T-E social-media propagation channel + Phase 6T-F
influencer agent_type build on top of. The class itself has no
domain-specific knowledge — it stores ``(author, follower)`` edges
with optional float weights, and exposes O(1) ``get_followers /
get_followed`` queries.

Design rationale
================
Pre-6T-D the only social-graph primitives in broker were:

- :class:`SpatialNeighborhoodGraph` — symmetric proximity edges
- :class:`InteractionHub`'s in-memory neighbour list — undirected
- :func:`get_social_spec`-dispatched ``global / filtered_global /
  random`` modes — also symmetric

None of these capture the **asymmetric directed** "author publishes
to followers" relationship that social-media propagation requires:

- A government press office has 100k followers; the followers
  don't follow each other.
- An influencer's audience cares about THIS influencer; the
  influencer doesn't care about each individual follower.
- A bot account follows 10k accounts to manipulate engagement
  metrics; none follow back.

Phase 6T-D ships the primitive. The actual ``Post`` propagation
(weighted by author credibility + age decay) lives in Phase 6T-E
on top of this graph. The deliberate split: 6T-D's primitives are
generic + can be tested in isolation; 6T-E adds the semantic
overlay.

Persistence semantics
=====================
:class:`FollowerNetwork` is **sticky across simulation years** —
follower relationships persist until explicitly removed via
:meth:`remove_edge`. Pre-6T-D event-context dicts in
:class:`MAEventManager` wiped at every year boundary (the Phase
6T-A persistence policy split makes this explicit via the
``EventPersistence.EPHEMERAL`` default). Follower edges are
``STICKY_INDEFINITE`` by default — losing them at year boundary
would dissolve the network on every Jan 1, which contradicts
human follower-relationship behaviour.

Operators who want decaying follower relationships (e.g.
"unfollow if no engagement for N years") can subclass
:class:`FollowerNetwork` and override :meth:`year_boundary_decay`.

Genericity invariant
====================
This module lives in ``broker/components/social/`` so it MUST NOT
carry domain tokens. Verified by
``broker/tests/test_framework_invariants.py::TestDomainGenericity``
and by the genericity-audit AST scan in
``broker/tests/test_follower_network.py``. The genericity contract
is also documented in
``.research/social_media_genericity_audit.md`` —
``Post.credibility_tier`` and similar US-media-shaped enums do
NOT belong here; they belong on the DomainPack's PerceptionPack.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Set, Tuple


class FollowerNetwork:
    """Directed asymmetric author→follower graph with optional
    edge weights.

    Storage shape (chosen for O(1) lookups in either direction):

    - ``_followers_of[author_id]`` → ``Set[follower_id]``
    - ``_followed_by[follower_id]`` → ``Set[author_id]``
    - ``_weights[(author_id, follower_id)]`` → ``float``

    Both index dicts must stay in sync; the public mutators
    (:meth:`add_edge`, :meth:`remove_edge`) handle that. The
    network supports millions of edges efficiently — the Phase 6T
    paper-3 target is 400 agents × ~5 followed authors per agent =
    ~2000 edges, well within cache-friendly territory.

    Thread safety: NOT thread-safe. Phase 6T's multi-agent runner
    is single-threaded within a year boundary; concurrent edge
    mutation across threads is out of scope.
    """

    def __init__(self) -> None:
        self._followers_of: Dict[str, Set[str]] = {}
        self._followed_by: Dict[str, Set[str]] = {}
        self._weights: Dict[Tuple[str, str], float] = {}

    # ─────────────────────────────────────────────────────────────────
    # Mutators
    # ─────────────────────────────────────────────────────────────────

    def add_edge(
        self,
        author_id: str,
        follower_id: str,
        weight: float = 1.0,
    ) -> None:
        """Register that ``follower_id`` follows ``author_id`` with
        the given ``weight`` (default ``1.0``).

        Re-adding an existing edge updates the weight in place.
        Self-loops (``author_id == follower_id``) are rejected —
        an agent following itself is semantically meaningless for
        the propagation channel.

        Raises:
            ValueError: if ``author_id`` or ``follower_id`` is
                empty, or if they are equal, or if ``weight`` is
                negative.
        """
        if not author_id or not follower_id:
            raise ValueError(
                "FollowerNetwork.add_edge: both author_id and "
                "follower_id must be non-empty."
            )
        if author_id == follower_id:
            raise ValueError(
                f"FollowerNetwork.add_edge: self-loop rejected "
                f"({author_id!r} following itself is meaningless)."
            )
        if weight < 0:
            raise ValueError(
                f"FollowerNetwork.add_edge: weight must be >=0; "
                f"got {weight!r} for edge {author_id!r}→{follower_id!r}."
            )

        self._followers_of.setdefault(author_id, set()).add(follower_id)
        self._followed_by.setdefault(follower_id, set()).add(author_id)
        self._weights[(author_id, follower_id)] = float(weight)

    def remove_edge(self, author_id: str, follower_id: str) -> bool:
        """Remove the directed edge ``follower_id`` → ``author_id``.

        Returns ``True`` if the edge existed and was removed,
        ``False`` if no such edge was registered (this is not an
        error — idempotent removal is convenient when the caller
        doesn't track edges).
        """
        existed = (author_id, follower_id) in self._weights
        if not existed:
            return False

        del self._weights[(author_id, follower_id)]

        followers = self._followers_of.get(author_id)
        if followers is not None:
            followers.discard(follower_id)
            if not followers:
                del self._followers_of[author_id]

        followed = self._followed_by.get(follower_id)
        if followed is not None:
            followed.discard(author_id)
            if not followed:
                del self._followed_by[follower_id]

        return True

    def clear(self) -> None:
        """Remove every edge. Used by test teardown + experiment
        restart paths. Production code should NOT call this at
        year boundaries — follower relationships are sticky."""
        self._followers_of.clear()
        self._followed_by.clear()
        self._weights.clear()

    # ─────────────────────────────────────────────────────────────────
    # Queries
    # ─────────────────────────────────────────────────────────────────

    def get_followers(self, author_id: str) -> List[str]:
        """Return the list of follower IDs for ``author_id``.

        Returns an empty list (NOT ``None``) when the author has no
        followers or is unknown — callers can iterate
        unconditionally. Order is unspecified (the underlying
        storage is a set); callers requiring deterministic order
        should sort the returned list.
        """
        return list(self._followers_of.get(author_id, ()))

    def get_followed(self, follower_id: str) -> List[str]:
        """Return the list of authors that ``follower_id`` follows.

        Symmetric companion to :meth:`get_followers`. Returns empty
        list when the follower follows nobody or is unknown."""
        return list(self._followed_by.get(follower_id, ()))

    def get_edge_weight(self, author_id: str, follower_id: str) -> float:
        """Return the weight of the ``follower_id``→``author_id``
        edge.

        Raises ``KeyError`` if no such edge exists — caller must
        check :meth:`has_edge` first if uncertain. The KeyError-on-
        unknown contract is deliberate: a 0.0 default would silently
        deweight a propagation calculation that thought the edge
        existed, which would mask graph-construction bugs.
        """
        return self._weights[(author_id, follower_id)]

    def has_edge(self, author_id: str, follower_id: str) -> bool:
        """Idempotent membership check."""
        return (author_id, follower_id) in self._weights

    def edge_count(self) -> int:
        """Total number of directed edges in the network."""
        return len(self._weights)

    def author_count(self) -> int:
        """Number of distinct authors with ≥1 follower."""
        return len(self._followers_of)

    def follower_count(self) -> int:
        """Number of distinct follower agents."""
        return len(self._followed_by)

    def iter_edges(self) -> Iterable[Tuple[str, str, float]]:
        """Iterate over every edge as ``(author_id, follower_id,
        weight)`` tuples. Order unspecified."""
        for (author, follower), weight in self._weights.items():
            yield author, follower, weight

    # ─────────────────────────────────────────────────────────────────
    # Lifecycle hooks (subclassable)
    # ─────────────────────────────────────────────────────────────────

    def year_boundary_decay(self, current_year: int) -> None:
        """Hook called by future Phase 6T-E/F propagation code at
        year-boundary clear, AFTER ``EPHEMERAL`` event wipes. Default
        no-op (follower relationships are sticky by default).

        Subclasses MAY override to implement engagement-based
        unfollowing, time-decayed weights, or churn models. The
        base class is deliberately no-op so the simplest
        propagation channel (Phase 6T-E) doesn't need to opt out.
        """
        return None


__all__ = ["FollowerNetwork"]
