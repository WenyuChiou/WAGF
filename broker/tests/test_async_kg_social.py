"""Tests for the domain-generic asynchronous knowledge-graph social engine."""
from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from broker.components.context.tiered import TieredContextBuilder
from broker.components.memory.engines.humancentric import HumanCentricMemoryEngine
from broker.components.memory.engines.window import WindowMemoryEngine
from broker.components.memory.origin_gate import MEMORY_LOG_NAME, install_origin_gate
from broker.components.social import (
    AsyncKnowledgeGraph,
    FilterRegistry,
    KnowledgeGraphSocialProvider,
    KnowledgeTriple,
)
from broker.components.social.follower_network import FollowerNetwork
from broker.components.social.graph import CustomGraph
from broker.core.run_integrity import GOVERNANCE_PHRASES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_agent(agent_id: str, agent_type: str = "consumer"):
    return SimpleNamespace(
        id=agent_id,
        name=agent_id,
        agent_type=agent_type,
        custom_attributes={},
        dynamic_state={},
        memory=[],
        memory_config={},
        get_available_skills=lambda: ["adopt_measure", "defer"],
    )


# ---------------------------------------------------------------------------
# 1. KnowledgeTriple validation & delayed visibility
# ---------------------------------------------------------------------------


class TestDelayedVisibilityAndTTL:
    """Asynchronous delivery_delay and ttl_periods semantics."""

    def test_available_period_property(self):
        triple = KnowledgeTriple(
            triple_id="t1",
            subject="A1",
            predicate="executed_action",
            obj="action_x",
            published_period=2,
            delivery_delay=3,
        )
        assert triple.available_period == 5

    def test_validation_rejects_invalid_fields(self):
        with pytest.raises(ValueError, match="visibility"):
            KnowledgeTriple("t", "A", "p", "o", visibility="unknown")
        with pytest.raises(ValueError, match="published_period"):
            KnowledgeTriple("t", "A", "p", "o", published_period=-1)
        with pytest.raises(ValueError, match="delivery_delay"):
            KnowledgeTriple("t", "A", "p", "o", delivery_delay=-1)
        with pytest.raises(ValueError, match="ttl_periods"):
            KnowledgeTriple("t", "A", "p", "o", ttl_periods=-1)
        with pytest.raises(ValueError, match="confidence"):
            KnowledgeTriple("t", "A", "p", "o", confidence=1.5)

    def test_delivery_delay_hides_at_t_and_reveals_at_t_plus_1(self):
        kg = AsyncKnowledgeGraph()
        kg.record_executed_action(
            agent_id="A1",
            agent_role="provider",
            action_name="adjust_rate",
            period=1,
            number_text="0.15",
            delivery_delay=1,
            visibility="global",
            outcome_text="rate updated",
        )

        # Invisible at period 1 (published=1, delay=1 -> available=2)
        assert kg.query_visible("C1", current_period=1) == []

        # Visible at period 2
        visible_p2 = kg.query_visible("C1", current_period=2)
        assert len(visible_p2) == 1
        assert visible_p2[0].subject == "A1"
        assert visible_p2[0].obj == "adjust_rate"
        assert visible_p2[0].value == pytest.approx(0.15)
        assert "rate updated" in visible_p2[0].text

    def test_ttl_expiration_after_available_period(self):
        kg = AsyncKnowledgeGraph()
        kg.assert_fact(
            subject="A1",
            predicate="announced",
            obj="program_open",
            author_id="A1",
            published_period=1,
            delivery_delay=1,
            ttl_periods=2,
            visibility="global",
        )

        # available_period = 2, ttl_periods = 2 -> visible at 2 and 3, expired at 4
        assert kg.query_visible("Obs", current_period=1) == []
        assert len(kg.query_visible("Obs", current_period=2)) == 1
        assert len(kg.query_visible("Obs", current_period=3)) == 1
        assert kg.query_visible("Obs", current_period=4) == []


# ---------------------------------------------------------------------------
# 2. Visibility scoping & deterministic ranking
# ---------------------------------------------------------------------------


class TestVisibilityScopingAndRanking:
    """Neighbor, follower, global, direct scopes and age-decayed ranking."""

    def test_neighbor_follower_global_direct_scopes(self):
        social_graph = CustomGraph(
            ["A1", "A2", "A3", "A4"],
            lambda _ids: [("A1", "A2")],
        )
        follower_net = FollowerNetwork()
        follower_net.add_edge("A3", "A2")  # A2 follows A3

        kg = AsyncKnowledgeGraph(
            social_graph=social_graph,
            follower_network=follower_net,
        )

        kg.assert_fact("A1", "did", "neighbor_act", author_id="A1", visibility="neighbors")
        kg.assert_fact("A4", "did", "non_neighbor_act", author_id="A4", visibility="neighbors")
        kg.assert_fact("A3", "did", "followed_act", author_id="A3", visibility="followers")
        kg.assert_fact("A4", "did", "unfollowed_act", author_id="A4", visibility="followers")
        kg.assert_fact("A4", "did", "global_act", author_id="A4", visibility="global")
        kg.assert_fact(
            "A4",
            "sent",
            "direct_msg_to_A2",
            author_id="A4",
            visibility="direct",
            target_ids=("A2",),
        )
        kg.assert_fact(
            "A4",
            "sent",
            "direct_msg_to_A1",
            author_id="A4",
            visibility="direct",
            target_ids=("A1",),
        )

        vis_a2 = {t.obj for t in kg.query_visible("A2", current_period=0, top_k=20)}
        assert vis_a2 == {"neighbor_act", "followed_act", "global_act", "direct_msg_to_A2"}

        vis_a1 = {t.obj for t in kg.query_visible("A1", current_period=0, top_k=20)}
        assert vis_a1 == {"global_act", "direct_msg_to_A1"}

    def test_include_self_and_predicate_subject_filters(self):
        kg = AsyncKnowledgeGraph()
        kg.assert_fact("A1", "executed_action", "act_1", author_id="A1", visibility="global")
        kg.assert_fact("A2", "state_update", "val_2", author_id="A2", visibility="global")

        assert len(kg.query_visible("A1", current_period=0, include_self=False)) == 1
        assert len(kg.query_visible("A1", current_period=0, include_self=True)) == 2
        by_pred = kg.query_visible(
            "A1", current_period=0, predicates=["executed_action"], include_self=True
        )
        assert [t.obj for t in by_pred] == ["act_1"]
        by_subj = kg.query_visible("A1", current_period=0, subjects="A2")
        assert [t.obj for t in by_subj] == ["val_2"]

    def test_deterministic_age_decayed_confidence_ranking(self):
        kg = AsyncKnowledgeGraph(half_life_periods=2.0)
        # Old high-confidence fact: available=0 -> at period 4, decay = 0.5**(4/2) = 0.25
        kg.assert_fact(
            "A1", "act", "old_fact",
            author_id="A1", published_period=0, confidence=1.0, visibility="global",
            triple_id="t_old",
        )
        # Recent moderate-confidence fact: available=4 -> decay = 1.0, score = 0.8
        kg.assert_fact(
            "A2", "act", "new_fact",
            author_id="A2", published_period=4, confidence=0.8, visibility="global",
            triple_id="t_new",
        )
        # Tied score with t_new: available=4, confidence=0.8 -> later insertion wins deterministically
        kg.assert_fact(
            "A3", "act", "newest_tied_fact",
            author_id="A3", published_period=4, confidence=0.8, visibility="global",
            triple_id="t_tied",
        )

        ranked = kg.query_visible("Obs", current_period=4, top_k=3)
        assert [t.triple_id for t in ranked] == ["t_tied", "t_new", "t_old"]


# ---------------------------------------------------------------------------
# 3. Invariant 7: No governance trace in social KG
# ---------------------------------------------------------------------------


class TestInvariant7NoGovernanceTrace:
    """strict_no_governance_trace rejects GOVERNANCE_PHRASES."""

    @pytest.mark.parametrize("phrase", GOVERNANCE_PHRASES)
    def test_assert_fact_rejects_governance_phrases(self, phrase):
        kg = AsyncKnowledgeGraph(strict_no_governance_trace=True)
        with pytest.raises(ValueError, match="Invariant 7"):
            kg.assert_fact(
                subject="A1",
                predicate="executed_action",
                obj="fallback",
                text=f"Action {phrase} during validation.",
                visibility="global",
            )

    def test_record_executed_action_rejects_governance_phrase_in_outcome(self):
        kg = AsyncKnowledgeGraph(strict_no_governance_trace=True)
        with pytest.raises(ValueError, match="Invariant 7"):
            kg.record_executed_action(
                agent_id="A1",
                agent_role="consumer",
                action_name="defer",
                period=1,
                outcome_text="Proposal to act was rejected by rule R1",
            )

    def test_metadata_governance_phrase_rejected(self):
        kg = AsyncKnowledgeGraph(strict_no_governance_trace=True)
        with pytest.raises(ValueError, match="Invariant 7"):
            kg.assert_fact(
                subject="A1",
                predicate="executed_action",
                obj="defer",
                text="A1 executed defer",
                visibility="global",
                metadata={"note": "default action applied"},
            )

    def test_strict_flag_false_allows_phrases(self):
        kg = AsyncKnowledgeGraph(strict_no_governance_trace=False)
        triple = kg.assert_fact(
            subject="A1",
            predicate="note",
            obj="test",
            text="proposal to act was rejected",
            visibility="global",
        )
        assert triple.text == "proposal to act was rejected"


# ---------------------------------------------------------------------------
# 4. Idempotent sync_to_memory with real OriginGate
# ---------------------------------------------------------------------------


class TestSyncToMemoryWithOriginGate:
    """sync_to_memory writes origin='social' through install_origin_gate idempotently."""

    def test_idempotent_sync_across_periods_with_origin_gate(self, tmp_path: Path):
        current_period = {"val": 1}
        engine = HumanCentricMemoryEngine()
        gate = install_origin_gate(engine, tmp_path, lambda: current_period["val"])
        gate.seeding = False

        kg = AsyncKnowledgeGraph()
        # Delayed fact: published 1, delay 1 -> available period 2 (inserted BEFORE period-1 fact)
        kg.record_executed_action(
            agent_id="A1",
            agent_role="regulator",
            action_name="update_policy",
            period=1,
            delivery_delay=1,
            visibility="global",
            outcome_text="new target active",
        )
        # Immediate fact at period 1
        kg.record_executed_action(
            agent_id="A2",
            agent_role="provider",
            action_name="publish_offer",
            period=1,
            delivery_delay=0,
            visibility="global",
            outcome_text="offer available",
        )

        # Period 1: delivers only A2's immediate fact
        n1 = kg.sync_to_memory("C1", 1, engine, max_items=5)
        assert n1 == 1

        # Calling again in period 1 is idempotent -> 0 new writes
        assert kg.sync_to_memory("C1", 1, engine, max_items=5) == 0

        # Advance to period 2: A1's delayed fact becomes available and is delivered once
        current_period["val"] = 2
        n2 = kg.sync_to_memory("C1", 2, engine, max_items=5)
        assert n2 == 1
        assert kg.sync_to_memory("C1", 2, engine, max_items=5) == 0

        assert gate.counts["social"] == 2
        log_path = tmp_path / MEMORY_LOG_NAME
        rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
        assert len(rows) == 2
        assert all(r["origin"] == "social" for r in rows)
        assert [r["source"] for r in rows] == ["community", "community"]
        assert all(r["emotion"] is None for r in rows)
        assert [r["period"] for r in rows] == [1, 2]

        snap = kg.snapshot()
        assert snap["triple_count"] == 2
        assert len(snap["delivered_by_observer"]["C1"]) == 2
        assert snap["delivery_cursor_period"]["C1"] == 2

    def test_double_provide_same_period_capped_at_max_items(self, tmp_path: Path):
        """Early cache context build + process_step build in one step must not double-sync."""
        current_period = {"val": 1}
        engine = WindowMemoryEngine(window_size=10)
        gate = install_origin_gate(engine, tmp_path, lambda: current_period["val"])
        gate.seeding = False

        social_graph = CustomGraph(["A1", "A2", "C1"], lambda _ids: [("A1", "C1"), ("A2", "C1")])
        kg = AsyncKnowledgeGraph(social_graph=social_graph)
        kg.assert_fact(
            subject="A1", predicate="action", obj="act_1",
            author_id="A1", published_period=1, visibility="neighbors",
        )
        kg.assert_fact(
            subject="A2", predicate="action", obj="act_2",
            author_id="A2", published_period=1, visibility="neighbors",
        )
        provider = KnowledgeGraphSocialProvider(
            kg=kg,
            period_getter=lambda: current_period["val"],
            memory_engine=engine,
            top_k=5,
            sync_max_items=1,
        )

        # Simulate ExperimentRunner early context build + SkillBrokerEngine build in same period
        provider.provide("C1", {}, {})
        provider.provide("C1", {}, {})
        assert gate.counts["social"] == 1

        # Next period delivers the remaining queued item with I1/I2 metadata
        current_period["val"] = 2
        provider.provide("C1", {}, {})
        assert gate.counts["social"] == 2
        rows = [
            json.loads(line)
            for line in (tmp_path / MEMORY_LOG_NAME).read_text(encoding="utf-8").splitlines()
        ]
        assert all(r["source"] == "neighbor" for r in rows)
        assert all(r["emotion"] is None for r in rows)

    def test_world_text_with_generic_proposal_to_allowed_under_strict_i7(self):
        """Ordinary world text like a municipal levee proposal must not false-positive I7."""
        kg = AsyncKnowledgeGraph(strict_no_governance_trace=True)
        triple = kg.assert_fact(
            subject="City",
            predicate="announcement",
            obj="levee_upgrade",
            text="The city's proposal to raise the levee passed.",
            author_id="gov_1",
            published_period=1,
            visibility="global",
        )
        assert "levee" in triple.text

    def test_two_hop_geographic_diffusion_and_move_edge_isolation(self):
        from broker.components.social.graph import SpatialNeighborhoodGraph

        positions = {
            "A1": (0.0, 0.0),
            "A2": (1.5, 0.0),
            "A3": (3.0, 0.0),
            "A4": (0.0, 1.5),
            "A5": (10.0, 1.5),
        }
        g = SpatialNeighborhoodGraph(
            list(positions.keys()), positions=positions, radius=1.5, fallback_k=0,
        )
        kg = AsyncKnowledgeGraph(social_graph=g, neighbor_hops=2)

        # Period 1 facts
        kg.assert_fact(
            subject="A1", predicate="event_note", obj="gap_1",
            text="A1 shortfall experience",
            author_id="A1", published_period=1, delivery_delay=1, visibility="neighbors",
        )
        kg.assert_fact(
            subject="A4", predicate="event_note", obj="old_a4",
            text="A4 pre-move fact",
            author_id="A4", published_period=1, delivery_delay=0, visibility="neighbors",
        )
        kg.assert_fact(
            subject="A5", predicate="event_note", obj="old_a5",
            text="A5 pre-move fact",
            author_id="A5", published_period=1, delivery_delay=0, visibility="neighbors",
        )

        # Period 2: 1-hop query to A2 sees only A1 (gap_1); 2-hop sees both gap_1 (1-hop) and old_a4 (2-hop via A1)
        assert [t.obj for t in kg.query_visible("A2", 2, hops=1)] == ["gap_1"]
        assert {t.obj for t in kg.query_visible("A2", 2)} == {"gap_1", "old_a4"}
        assert kg.query_visible("A3", 2) == []

        # End of period 2: A4 relocates next to A5
        move_diff = g.move("A4", (10.0, 0.0), period=2)
        assert move_diff["removed"] == ["A1"]
        assert move_diff["added"] == ["A5"]
        assert [e["op"] for e in g.edge_events] == ["remove", "add"]

        # Short move that keeps an existing edge must preserve its edge_start_period and emit no events
        g_stay = SpatialNeighborhoodGraph(
            ["B1", "B2", "B3"],
            positions={"B1": (0.0, 0.0), "B2": (1.0, 0.0), "B3": (5.0, 0.0)},
            radius=2.0,
            fallback_k=0,
        )
        assert g_stay.get_edge_start_period("B1", "B2") == 0
        stay_diff = g_stay.move("B1", (0.5, 0.0), period=3)
        assert stay_diff == {"removed": [], "added": [], "neighbors": ["B2"]}
        assert g_stay.get_edge_start_period("B1", "B2") == 0
        assert g_stay.edge_events == []

        # Period 3: A3 sees A1 at hop 2; A4 and A5 do NOT see each other's period-1 facts
        assert [t.obj for t in kg.query_visible("A3", 3)] == ["gap_1"]
        assert "old_a5" not in [t.obj for t in kg.query_visible("A4", 3)]
        assert "old_a4" not in [t.obj for t in kg.query_visible("A5", 3)]

        # New period-3 fact across (A4, A5) DOES propagate
        kg.assert_fact(
            subject="A4", predicate="event_note", obj="new_a4",
            text="A4 post-move action",
            author_id="A4", published_period=3, delivery_delay=0, visibility="neighbors",
        )
        assert [t.obj for t in kg.query_visible("A5", 3)] == ["new_a4"]


# ---------------------------------------------------------------------------
# 5. KnowledgeGraphSocialProvider + TieredContextBuilder integration
# ---------------------------------------------------------------------------


class TestKnowledgeGraphSocialProviderIntegration:
    """Integration with TieredContextBuilder and context formatting."""

    def test_provider_populates_context_and_tiered_prompt(self, tmp_path: Path):
        period_state = {"period": 2}
        social_graph = CustomGraph(["A1", "C1"], lambda _ids: [("A1", "C1")])
        kg = AsyncKnowledgeGraph(social_graph=social_graph)
        kg.record_executed_action(
            agent_id="A1",
            agent_role="provider",
            action_name="deploy_resource",
            period=1,
            number_text="0.5",
            delivery_delay=1,
            visibility="neighbors",
            outcome_text="capacity increased",
        )

        engine = HumanCentricMemoryEngine()
        gate = install_origin_gate(engine, tmp_path, lambda: period_state["period"])
        gate.seeding = False

        provider = kg.as_context_provider(
            lambda: period_state["period"],
            memory_engine=engine,
            top_k=5,
            context_key="social_gossip",
        )
        assert isinstance(provider, KnowledgeGraphSocialProvider)

        agents = {
            "A1": _build_agent("A1", "provider"),
            "C1": _build_agent("C1", "consumer"),
        }
        builder = TieredContextBuilder(
            agents=agents,
            memory_engine=engine,
            prompt_templates={
                "consumer": "Agent {agent_name}\nSocial:\n{social_gossip}\nActions:\n{options_text}",
            },
            extend_providers=[provider],
        )

        ctx = builder.build("C1")
        assert "deploy_resource" in ctx["social_gossip"]
        assert "capacity increased" in ctx["social_gossip"]
        assert gate.counts["social"] == 1

        prompt = builder.format_prompt(ctx)
        assert "deploy_resource" in prompt
        assert "capacity increased" in prompt

        # Second build in same period must not duplicate memory write
        builder.build("C1")
        assert gate.counts["social"] == 1


# ---------------------------------------------------------------------------
# 6. Genericity & untouched FilterRegistry regression guard
# ---------------------------------------------------------------------------


class TestGenericityAndCompatibility:
    """Verify domain genericity and untouched FilterRegistry compatibility."""

    def test_existing_filter_registry_preserved(self):
        assert "has_insurance" in FilterRegistry.names()
        fn = FilterRegistry.get("has_insurance")
        assert callable(fn)
        assert fn({"has_insurance": True}) is True
        assert fn({"has_insurance": False}) is False

    def test_assert_fact_accepts_knowledge_triple_and_custom_context_key(self):
        kg = AsyncKnowledgeGraph()
        triple = KnowledgeTriple(
            triple_id="custom-1",
            subject="R1",
            predicate="announced",
            obj="target_rate",
            value=0.2,
            author_id="R1",
            published_period=1,
            visibility="global",
        )
        assert kg.assert_fact(triple) is triple
        provider = kg.as_context_provider(lambda: 1, context_key="kg_summary")
        ctx = {}
        provider.provide("C1", {}, ctx)
        assert "R1 announced target_rate (0.2)" in ctx["kg_summary"]
        assert "local" not in ctx

    @pytest.mark.parametrize(
        "rel_path",
        [
            "broker/components/social/knowledge_graph.py",
            "broker/components/social/kg_provider.py",
        ],
    )
    def test_no_forbidden_imports_or_tier_literals(self, rel_path: str):
        repo_root = Path(__file__).resolve().parents[2]
        source = (repo_root / rel_path).read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden_prefixes = ("broker.domains.water", "examples.")
        forbidden_literals = {"OFFICIAL", "VERIFIED", "INFLUENCER", "PEER", "BOT"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(forbidden_prefixes)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert not mod.startswith(forbidden_prefixes)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert node.value not in forbidden_literals

    def test_provider_filters_sync_to_memory_by_predicates_and_subjects(self, tmp_path):
        kg = AsyncKnowledgeGraph()
        kg.assert_fact(
            subject="R1",
            predicate="policy_update",
            obj="rate_a",
            author_id="R1",
            published_period=1,
            visibility="global",
        )
        kg.assert_fact(
            subject="P1",
            predicate="capacity_update",
            obj="cap_b",
            author_id="P1",
            published_period=1,
            visibility="global",
        )
        engine = WindowMemoryEngine(window_size=5)
        gate = install_origin_gate(engine, tmp_path, period=lambda: 1)
        gate.seeding = False

        provider = KnowledgeGraphSocialProvider(
            kg=kg,
            period_getter=lambda: 1,
            memory_engine=engine,
            predicates=["policy_update"],
            subjects=["R1"],
        )
        ctx = {}
        provider.provide("C1", {}, ctx)

        assert "rate_a" in ctx["social_gossip"]
        assert "cap_b" not in ctx["social_gossip"]
        assert gate.counts["social"] == 1
        stored = engine.retrieve(SimpleNamespace(id="C1"), top_k=5)
        assert len(stored) == 1
        assert "rate_a" in stored[0]
        assert "cap_b" not in stored[0]
