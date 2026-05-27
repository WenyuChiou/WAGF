"""
Phase 6T-D tests for the FollowerNetwork primitive +
SocialGraphSpec follower_network extension.

Verifies:

- ``FollowerNetwork`` add/remove/query edge semantics
- Self-loop + empty-id + negative-weight rejection
- O(1) lookups in both directions (correctness, not throughput)
- Re-adding an edge updates weight in place
- ``year_boundary_decay`` no-op default + subclass override hook
- ``SocialGraphSpec(graph_type="follower_network")`` validates
- ``configure_social_graph_for_agent`` raises on follower_network
  (asymmetric — caller must query FollowerNetwork directly)
- Genericity invariant: the new module imports no domain code

Per the genericity audit at
``.research/social_media_genericity_audit.md``, 6T-D ships the
graph primitives WITHOUT credibility-tier vocabulary. The
``Post.credibility_tier`` enum + verbalisation templates are 6T-E
scope and MUST live in the DomainPack, not in broker/.

Plan: ``~/.claude/plans/swirling-knitting-lighthouse.md`` 6T-D.
"""
from __future__ import annotations

from typing import List

import pytest

from broker.components.social.config import (
    SocialGraphSpec,
    configure_social_graph_for_agent,
)
from broker.components.social.follower_network import FollowerNetwork


# ─────────────────────────────────────────────────────────────────────
# Class 1 — Edge mutation semantics
# ─────────────────────────────────────────────────────────────────────


class TestFollowerNetworkEdgeMutation:
    """add_edge / remove_edge / has_edge round-trip + idempotency."""

    def test_add_edge_records_both_directions(self):
        net = FollowerNetwork()
        net.add_edge("A", "B")
        assert net.has_edge("A", "B") is True
        assert "B" in net.get_followers("A")
        assert "A" in net.get_followed("B")

    def test_add_edge_default_weight_is_one(self):
        net = FollowerNetwork()
        net.add_edge("A", "B")
        assert net.get_edge_weight("A", "B") == 1.0

    def test_add_edge_with_custom_weight(self):
        net = FollowerNetwork()
        net.add_edge("A", "B", weight=2.5)
        assert net.get_edge_weight("A", "B") == 2.5

    def test_re_add_updates_weight_in_place(self):
        """Re-adding an existing edge updates the weight rather
        than duplicating the edge — useful for weight refresh
        without forcing a remove/add dance."""
        net = FollowerNetwork()
        net.add_edge("A", "B", weight=1.0)
        net.add_edge("A", "B", weight=3.0)
        assert net.edge_count() == 1
        assert net.get_edge_weight("A", "B") == 3.0

    def test_remove_edge_returns_true_when_existed(self):
        net = FollowerNetwork()
        net.add_edge("A", "B")
        assert net.remove_edge("A", "B") is True
        assert net.has_edge("A", "B") is False

    def test_remove_edge_idempotent_returns_false(self):
        """Removing a non-existent edge is not an error — returns
        False so callers can be loose about edge tracking."""
        net = FollowerNetwork()
        assert net.remove_edge("Unknown", "Other") is False

    def test_remove_edge_cleans_empty_index_entries(self):
        """After removing the last edge involving an agent, its
        keys disappear from both index dicts — keeps the internal
        state tidy + makes ``author_count`` / ``follower_count``
        accurate."""
        net = FollowerNetwork()
        net.add_edge("A", "B")
        net.remove_edge("A", "B")
        assert net.author_count() == 0
        assert net.follower_count() == 0


# ─────────────────────────────────────────────────────────────────────
# Class 2 — Input validation
# ─────────────────────────────────────────────────────────────────────


class TestFollowerNetworkInputValidation:
    """add_edge rejects pathological inputs explicitly."""

    def test_empty_author_id_rejected(self):
        net = FollowerNetwork()
        with pytest.raises(ValueError, match="non-empty"):
            net.add_edge("", "B")

    def test_empty_follower_id_rejected(self):
        net = FollowerNetwork()
        with pytest.raises(ValueError, match="non-empty"):
            net.add_edge("A", "")

    def test_self_loop_rejected(self):
        net = FollowerNetwork()
        with pytest.raises(ValueError, match="self-loop"):
            net.add_edge("A", "A")

    def test_negative_weight_rejected(self):
        net = FollowerNetwork()
        with pytest.raises(ValueError, match="weight"):
            net.add_edge("A", "B", weight=-1.0)

    def test_get_edge_weight_raises_keyerror_on_unknown(self):
        """KeyError-on-unknown is deliberate (NOT 0.0 default) so
        propagation calculations that thought the edge existed
        don't silently de-weight to zero."""
        net = FollowerNetwork()
        with pytest.raises(KeyError):
            net.get_edge_weight("ghost_author", "ghost_follower")


# ─────────────────────────────────────────────────────────────────────
# Class 3 — Asymmetric queries + scale
# ─────────────────────────────────────────────────────────────────────


class TestFollowerNetworkAsymmetricQueries:
    """The graph is directed — A→B does not imply B→A."""

    def test_directional_relationship(self):
        net = FollowerNetwork()
        net.add_edge("AUTH", "FAN_1")
        net.add_edge("AUTH", "FAN_2")
        # AUTH has 2 followers, FAN_1 has 0 followers
        assert sorted(net.get_followers("AUTH")) == ["FAN_1", "FAN_2"]
        assert net.get_followers("FAN_1") == []
        # FAN_1 follows AUTH; AUTH follows nobody
        assert net.get_followed("FAN_1") == ["AUTH"]
        assert net.get_followed("AUTH") == []

    def test_get_followers_returns_empty_for_unknown(self):
        net = FollowerNetwork()
        assert net.get_followers("nobody") == []
        assert net.get_followed("nobody") == []

    def test_scale_400_agents_with_power_law_followers(self):
        """Paper-3 scale (400 agents) — verifies the index dicts
        + weights dict survive a realistic-sized graph and queries
        are correct (not a performance benchmark)."""
        net = FollowerNetwork()
        # 5 "influencer" authors each followed by 80 households
        # → 400 directed edges total.
        for auth_idx in range(5):
            author = f"AUTH_{auth_idx}"
            for hh_idx in range(80):
                follower = f"HH_{auth_idx}_{hh_idx}"
                net.add_edge(author, follower, weight=1.0 + auth_idx * 0.1)

        assert net.edge_count() == 400
        assert net.author_count() == 5
        assert net.follower_count() == 400

        # Spot-check: AUTH_3's followers + the asymmetric weight.
        assert len(net.get_followers("AUTH_3")) == 80
        assert net.get_edge_weight("AUTH_3", "HH_3_42") == pytest.approx(1.3)

    def test_clear_removes_all_edges(self):
        net = FollowerNetwork()
        for i in range(10):
            net.add_edge(f"A_{i}", f"B_{i}")
        net.clear()
        assert net.edge_count() == 0
        assert net.author_count() == 0


# ─────────────────────────────────────────────────────────────────────
# Class 4 — Persistence + lifecycle hook
# ─────────────────────────────────────────────────────────────────────


class TestFollowerNetworkPersistence:
    """Follower relationships are STICKY (no clear_year wipe)
    unless a subclass overrides ``year_boundary_decay``."""

    def test_year_boundary_decay_default_noop(self):
        net = FollowerNetwork()
        net.add_edge("A", "B", weight=1.0)
        net.add_edge("A", "C", weight=1.0)
        net.year_boundary_decay(current_year=5)
        # Default impl is no-op — edges survive year boundary.
        assert net.edge_count() == 2
        assert net.has_edge("A", "B")

    def test_subclass_can_override_decay(self):
        """Operators implementing engagement-based unfollow rules
        subclass + override ``year_boundary_decay``."""

        class _DecayingNet(FollowerNetwork):
            def year_boundary_decay(self, current_year):
                # Halve every weight; remove edges that drop to 0.
                for (author, follower), weight in list(self._weights.items()):
                    new_weight = weight / 2
                    if new_weight < 0.1:
                        self.remove_edge(author, follower)
                    else:
                        self._weights[(author, follower)] = new_weight

        net = _DecayingNet()
        net.add_edge("A", "B", weight=1.0)
        net.add_edge("A", "C", weight=0.15)
        net.year_boundary_decay(current_year=1)

        assert net.get_edge_weight("A", "B") == 0.5
        assert net.has_edge("A", "C") is False  # 0.075 < 0.1 → dropped


# ─────────────────────────────────────────────────────────────────────
# Class 5 — SocialGraphSpec follower_network extension
# ─────────────────────────────────────────────────────────────────────


class TestSocialGraphSpecFollowerNetwork:
    """The new graph_type value validates + the dispatch
    function raises a clear error pointing callers to
    FollowerNetwork directly."""

    def test_follower_network_graph_type_validates(self):
        spec = SocialGraphSpec(graph_type="follower_network")
        assert spec.graph_type == "follower_network"

    def test_follower_seed_fn_and_weight_fn_optional(self):
        """Both new fields are optional; spec without them
        constructs cleanly."""
        spec = SocialGraphSpec(graph_type="follower_network")
        assert spec.follower_seed_fn is None
        assert spec.weight_fn is None

    def test_follower_seed_fn_callable_supported(self):
        """The seed callable is stored as-is for the runner to
        invoke at network-construction time."""

        def _seed(author_id, rng) -> List[str]:
            return [f"{author_id}_follower_{i}" for i in range(3)]

        spec = SocialGraphSpec(
            graph_type="follower_network",
            follower_seed_fn=_seed,
        )
        seeded = spec.follower_seed_fn("AUTH_X", None)
        assert seeded == ["AUTH_X_follower_0", "AUTH_X_follower_1", "AUTH_X_follower_2"]

    def test_weight_fn_callable_supported(self):
        spec = SocialGraphSpec(
            graph_type="follower_network",
            weight_fn=lambda a, f: 2.0 if a.startswith("AUTH_") else 1.0,
        )
        assert spec.weight_fn("AUTH_X", "HH_1") == 2.0
        assert spec.weight_fn("HH_1", "HH_2") == 1.0

    @pytest.fixture
    def _temp_follower_demo_spec(self):
        """Register a follower_network spec for one test, guaranteed
        cleanup even if the test is interrupted. Avoids polluting
        the global ``AGENT_SOCIAL_SPECS`` registry across tests."""
        from broker.components.social.config import (
            register_social_spec,
            AGENT_SOCIAL_SPECS,
        )
        register_social_spec(
            "follower_demo_agent",
            SocialGraphSpec(graph_type="follower_network"),
            overwrite=True,
        )
        try:
            yield "follower_demo_agent"
        finally:
            AGENT_SOCIAL_SPECS.pop("follower_demo_agent", None)

    def test_configure_social_graph_raises_on_follower_network(
        self, _temp_follower_demo_spec
    ):
        """The symmetric ``configure_social_graph_for_agent`` API
        can't express asymmetric follower relationships — it must
        raise instead of silently returning []."""

        class _Mock:
            agent_type = _temp_follower_demo_spec
            id = "X1"

        with pytest.raises(ValueError, match="follower_network"):
            configure_social_graph_for_agent(
                graph=object(),
                agent=_Mock(),
                all_agents={"X1": _Mock()},
            )


# ─────────────────────────────────────────────────────────────────────
# Class 6 — Genericity invariant
# ─────────────────────────────────────────────────────────────────────


class TestFollowerNetworkGenericity:
    """Per .research/social_media_genericity_audit.md, the new
    module + the SocialGraphSpec extensions MUST NOT carry
    domain-specific vocabulary (water/flood/household) or
    US-media-shaped tier literals
    (OFFICIAL/VERIFIED/INFLUENCER/PEER/BOT)."""

    def test_follower_network_module_has_no_forbidden_imports(self):
        """AST-scan the module source for forbidden import prefixes."""
        import ast
        from pathlib import Path

        import broker.components.social.follower_network as module
        source_path = Path(module.__file__)
        tree = ast.parse(source_path.read_text(encoding="utf-8"))

        forbidden_prefixes = (
            "broker.domains.water",
            "examples.",
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(forbidden_prefixes), (
                        f"follower_network imports forbidden module "
                        f"{alias.name!r}"
                    )
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert not mod.startswith(forbidden_prefixes), (
                    f"follower_network imports from forbidden module "
                    f"{mod!r}"
                )

    def test_follower_network_module_has_no_tier_literals(self):
        """AST-scan the module source for the US-media-shaped tier
        literals that Phase 6T-E might be tempted to bake in.
        These belong in the DomainPack per the audit doc."""
        import ast
        from pathlib import Path

        import broker.components.social.follower_network as module
        source_path = Path(module.__file__)
        tree = ast.parse(source_path.read_text(encoding="utf-8"))

        forbidden_literals = {
            "OFFICIAL", "VERIFIED", "INFLUENCER", "PEER", "BOT",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                # The literal must not appear as a code-level string
                # constant. Docstring mentions of the audit doc are
                # allowed (those contain explanatory references, not
                # active code).
                if node.value in forbidden_literals:
                    pytest.fail(
                        f"follower_network.py contains forbidden tier "
                        f"literal {node.value!r} — per "
                        f".research/social_media_genericity_audit.md, "
                        f"tier vocabulary belongs in the DomainPack."
                    )
