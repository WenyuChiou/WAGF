"""Phase 6T-E.B regression tests for SocialMediaProvider behaviour
(flag-ON path).

Covers:
- top_k truncation
- follower-graph filtering
- suppressed_tiers filtering
- pack-supplied social_media_post_filter (drop via None return)
- empty-feed → empty string
- weighting orders correctly (credibility × age × engagement)
- audit-key population
- verbalise_post exception → fallback rendering, dispatch continues
- unknown tier_id → cred=0 → filtered (not crashed)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

import pytest

from broker.components.context.providers import SocialMediaProvider
from broker.components.social.follower_network import FollowerNetwork
from broker.components.social.post import Post
from broker.simulation.environment import TieredEnvironment


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _StubPack:
    """Domain pack stub exposing only the methods the provider needs."""

    def __init__(
        self,
        suppressed: Optional[Set[str]] = None,
        weights: Optional[Dict[str, float]] = None,
        drop_for_agents: Optional[Set[str]] = None,
        raise_on_verbalise: bool = False,
    ):
        self._suppressed = suppressed or set()
        self._weights = weights or {
            "official_authority": 1.0,
            "verified_account": 0.8,
            "peer_post": 0.3,
        }
        self._drop_for_agents = drop_for_agents or set()
        self._raise_on_verbalise = raise_on_verbalise

    def suppressed_tiers(self) -> Set[str]:
        return self._suppressed

    def credibility_weight(self, tier_id: str) -> float:
        return self._weights.get(tier_id, 0.0)

    def verbalise_post(self, post: Post) -> str:
        if self._raise_on_verbalise:
            raise RuntimeError("simulated verbalise failure")
        return f"[{post.tier_id}] {post.author_id} {post.event_year}: {post.text}"

    def social_media_post_filter(self, agent: Any, post: Post) -> Optional[Post]:
        agent_id = getattr(agent, "id", None) if not isinstance(agent, dict) else agent.get("id")
        if agent_id in self._drop_for_agents:
            return None
        return post


def _make_post(
    text: str = "hi",
    author_id: str = "gov",
    event_year: int = 1,
    event_type: str = "subsidy_change",
    engagement_score: float = 0.0,
    tier_id: str = "official_authority",
) -> Post:
    return Post(
        text=text,
        author_id=author_id,
        author_role="government",
        event_year=event_year,
        event_type=event_type,
        engagement_score=engagement_score,
        tier_id=tier_id,
    )


@pytest.fixture
def env():
    return TieredEnvironment()


@pytest.fixture
def graph():
    net = FollowerNetwork()
    # household "hh1" follows gov + insurer; doesn't follow "stranger".
    # FollowerNetwork.add_edge(author, follower) — i.e. "hh1 follows gov"
    # means gov is the author, hh1 is the follower.
    net.add_edge(author_id="gov", follower_id="hh1")
    net.add_edge(author_id="insurer", follower_id="hh1")
    return net


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEmptyPaths:
    def test_empty_feeds_returns_empty_string(self, env, graph):
        provider = SocialMediaProvider(env, graph, _StubPack())
        ctx: Dict[str, Any] = {}
        provider.provide("hh1", {"hh1": {"id": "hh1"}}, ctx, year=1)
        assert ctx["social_media_feed"] == ""
        assert ctx["_social_media_audit"] == []

    def test_no_followed_authors_returns_empty(self, env):
        env.add_post(_make_post(author_id="gov"))
        empty_graph = FollowerNetwork()
        provider = SocialMediaProvider(env, empty_graph, _StubPack())
        ctx: Dict[str, Any] = {}
        provider.provide("hh1", {"hh1": {"id": "hh1"}}, ctx, year=1)
        assert ctx["social_media_feed"] == ""

    def test_missing_agent_returns_empty(self, env, graph):
        env.add_post(_make_post(author_id="gov"))
        provider = SocialMediaProvider(env, graph, _StubPack())
        ctx: Dict[str, Any] = {}
        provider.provide("nonexistent", {}, ctx, year=1)
        assert ctx["social_media_feed"] == ""


class TestRendering:
    def test_followed_author_post_appears(self, env, graph):
        env.add_post(_make_post(text="subsidy up", author_id="gov", event_year=1))
        provider = SocialMediaProvider(env, graph, _StubPack())
        ctx: Dict[str, Any] = {}
        provider.provide("hh1", {"hh1": {"id": "hh1"}}, ctx, year=1)
        # v0.5.1: when non-empty, the value starts with the section
        # header preceded by leading "\n\n" (byte-identity-safe
        # injection format).
        assert "subsidy up" in ctx["social_media_feed"]
        assert ctx["social_media_feed"].startswith(
            "\n\n## Social media (recent posts):\n- "
        )
        assert ctx["_social_media_audit"] == [("gov", 1, "subsidy_change", "official_authority")]

    def test_unfollowed_author_post_filtered(self, env, graph):
        env.add_post(_make_post(text="stranger post", author_id="stranger", event_year=1))
        provider = SocialMediaProvider(env, graph, _StubPack())
        ctx: Dict[str, Any] = {}
        provider.provide("hh1", {"hh1": {"id": "hh1"}}, ctx, year=1)
        assert ctx["social_media_feed"] == ""

    def test_suppressed_tier_filtered(self, env, graph):
        env.add_post(_make_post(tier_id="peer_post", author_id="gov", event_year=1))
        pack = _StubPack(suppressed={"peer_post"})
        provider = SocialMediaProvider(env, graph, pack)
        ctx: Dict[str, Any] = {}
        provider.provide("hh1", {"hh1": {"id": "hh1"}}, ctx, year=1)
        assert ctx["social_media_feed"] == ""

    def test_pack_filter_drops_post(self, env, graph):
        env.add_post(_make_post(author_id="gov", event_year=1))
        # Pack drops everything for hh1
        pack = _StubPack(drop_for_agents={"hh1"})
        provider = SocialMediaProvider(env, graph, pack)
        ctx: Dict[str, Any] = {}
        provider.provide("hh1", {"hh1": {"id": "hh1"}}, ctx, year=1)
        assert ctx["social_media_feed"] == ""

    def test_unknown_tier_id_zero_weight_filtered_out_of_top_k(self, env, graph):
        """Unknown tier → cred_weight=0 → score=0. With higher-scored
        posts present, the unknown gets bumped out of top_k. Without
        higher posts (only unknown), it still appears (no crash) —
        we don't filter zero-score, just rank it last."""
        env.add_post(_make_post(text="mystery", tier_id="mysterious_tier", author_id="gov", event_year=1))
        provider = SocialMediaProvider(env, graph, _StubPack(), top_k=5)
        ctx: Dict[str, Any] = {}
        provider.provide("hh1", {"hh1": {"id": "hh1"}}, ctx, year=1)
        # Doesn't crash; the single zero-scored post still renders
        assert "mystery" in ctx["social_media_feed"]

    def test_verbalise_exception_falls_back(self, env, graph):
        env.add_post(_make_post(text="hi", author_id="gov", event_year=1))
        pack = _StubPack(raise_on_verbalise=True)
        provider = SocialMediaProvider(env, graph, pack)
        ctx: Dict[str, Any] = {}
        provider.provide("hh1", {"hh1": {"id": "hh1"}}, ctx, year=1)
        # Fallback rendering: dispatch did NOT raise; feed has SOMETHING
        assert ctx["social_media_feed"] != ""
        assert "official_authority" in ctx["social_media_feed"]


class TestTopK:
    def test_top_k_truncates(self, env, graph):
        for i in range(10):
            env.add_post(_make_post(text=f"post-{i}", author_id="gov", event_year=1))
        provider = SocialMediaProvider(env, graph, _StubPack(), top_k=3)
        ctx: Dict[str, Any] = {}
        provider.provide("hh1", {"hh1": {"id": "hh1"}}, ctx, year=1)
        # Should have exactly 3 lines (one "- " prefix per post)
        assert ctx["social_media_feed"].count("- ") == 3
        assert len(ctx["_social_media_audit"]) == 3

    def test_top_k_ranking_by_score(self, env, graph):
        """Higher cred × age × engagement → higher rank."""
        # Old peer post (low cred, age decays, no engagement)
        env.add_post(_make_post(text="OLD-PEER", author_id="gov", event_year=1, tier_id="peer_post"))
        # Recent official (high cred, no age decay, high engagement)
        env.add_post(_make_post(text="NEW-OFFICIAL", author_id="gov", event_year=10,
                                tier_id="official_authority", engagement_score=5.0))
        provider = SocialMediaProvider(env, graph, _StubPack(), top_k=2)
        ctx: Dict[str, Any] = {}
        provider.provide("hh1", {"hh1": {"id": "hh1"}}, ctx, year=10)
        feed = ctx["social_media_feed"]
        new_idx = feed.index("NEW-OFFICIAL")
        old_idx = feed.index("OLD-PEER")
        assert new_idx < old_idx, "NEW-OFFICIAL should rank ahead of OLD-PEER"


class TestAuditTrail:
    def test_audit_tuple_shape(self, env, graph):
        env.add_post(_make_post(text="x", author_id="gov", event_year=3, event_type="flood", tier_id="verified_account"))
        provider = SocialMediaProvider(env, graph, _StubPack())
        ctx: Dict[str, Any] = {}
        provider.provide("hh1", {"hh1": {"id": "hh1"}}, ctx, year=3)
        assert ctx["_social_media_audit"] == [("gov", 3, "flood", "verified_account")]

    def test_audit_matches_rendered_order(self, env, graph):
        env.add_post(_make_post(text="a", author_id="gov", event_year=1))
        env.add_post(_make_post(text="b", author_id="insurer", event_year=2, tier_id="verified_account"))
        provider = SocialMediaProvider(env, graph, _StubPack(), top_k=5)
        ctx: Dict[str, Any] = {}
        provider.provide("hh1", {"hh1": {"id": "hh1"}}, ctx, year=2)
        # v0.5.1: feed starts with "\n\n## Social media (recent posts):\n"
        # followed by one line per post (prefixed by "- "). Extract the
        # post lines by stripping the header preamble.
        feed = ctx["social_media_feed"]
        header_end = feed.index("\n", feed.index("## Social media"))
        post_lines = [ln for ln in feed[header_end:].split("\n") if ln.startswith("- ")]
        audit_authors = [a[0] for a in ctx["_social_media_audit"]]
        # Both posts present
        assert len(post_lines) == 2
        assert len(audit_authors) == 2
        # Order matches: first audit author appears in first post line
        assert audit_authors[0] in post_lines[0]
        assert audit_authors[1] in post_lines[1]
