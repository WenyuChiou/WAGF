"""Tests for P0 multi-period lifecycle exit, graph vacation, intra-period sync, and ablation guards."""

from __future__ import annotations

import json
import sys
from textwrap import dedent
from types import SimpleNamespace
from uuid import uuid4

import yaml

from broker.components.analytics.interaction import InteractionHub
from broker.components.coordination import MultiActorLifecycleBridge
from broker.components.coordination.messages import MessagePool
from broker.components.coordination.provider import MessagePoolProvider
from broker.components.orchestration.institutional_lifecycle import (
    InstitutionalLifecycleHandler,
)
from broker.components.social.graph import SocialGraph, SpatialNeighborhoodGraph
from broker.components.social.kg_provider import KnowledgeGraphSocialProvider
from broker.components.social.knowledge_graph import AsyncKnowledgeGraph
from broker.interfaces.event_generator import EventScope
from broker.interfaces.skill_types import ExecutionResult, SkillOutcome
from broker.run import main


def _write_yaml(path, data):
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def _cleanup_case_modules(folder):
    for name in list(sys.modules):
        if name == folder.name or name.startswith(f"{folder.name}."):
            sys.modules.pop(name, None)


def test_interaction_hub_filters_inactive_and_removed_neighbors():
    graph = SocialGraph(["A", "B", "C"])
    graph.add_edge("A", "B")
    graph.add_edge("A", "C")

    class Mem:
        def retrieve(self, agent, top_k=1):
            return [f"note from {agent.id}"]

    class Obs:
        def observe(self, observer, neighbor):
            return SimpleNamespace(
                visible_actions=[{"action": "act"}],
                gossip=f"gossip from {neighbor.id}",
                visible_attributes={"adopted": getattr(neighbor, "adopted", False)},
            )

    agents = {
        "A": SimpleNamespace(id="A", is_active=True, dynamic_state={}),
        "B": SimpleNamespace(
            id="B", is_active=False, adopted=True, dynamic_state={"last_decision": "exit"}
        ),
        # "C" deliberately removed from agents dict
    }

    # 1. Default exclude_inactive=False: missing "C" does not raise KeyError and is excluded,
    # while inactive "B" stays observable (e.g., physical traces on static graphs) until vacated.
    hub_default = InteractionHub(
        graph,
        memory_engine=Mem(),
        spatial_observables=["adopted"],
        visible_action_specs=[
            {"state_keys": ["adopted"], "action": "adopt", "description": "{nid} adopted"}
        ],
        social_observer=Obs(),
    )
    assert hub_default.get_spatial_context("A", agents) == {"neighbor_count": 1, "adopted_pct": 1.0}
    assert hub_default.get_visible_neighbor_actions("A", agents) == [
        {"neighbor_id": "B", "action": "adopt", "description": "B adopted"}
    ]

    # 2. Opt-in exclude_inactive=True: excludes BOTH missing "C" and is_active=False "B"
    hub = InteractionHub(
        graph,
        memory_engine=Mem(),
        spatial_observables=["adopted"],
        visible_action_specs=[
            {"state_keys": ["adopted"], "action": "adopt", "description": "{nid} adopted"}
        ],
        social_observer=Obs(),
        exclude_inactive=True,
    )

    assert hub.get_spatial_context("A", agents) == {}
    assert hub.get_visible_neighbor_actions("A", agents) == []
    assert hub.get_visible_neighbor_actions_v2("A", agents) == []
    assert hub.get_neighbor_action_summary("A", agents) == ""
    social = hub.get_social_context("A", agents)
    assert social == {"gossip": [], "visible_actions": [], "neighbor_count": 0}
    social_v2 = hub.get_social_context_v2("A", agents)
    assert social_v2 == {
        "gossip": [],
        "visible_actions": [],
        "neighbor_count": 0,
        "observable_attrs": {},
    }

    # 3. Vacating "B" on graph removes it from default hub too without exclude_inactive=True
    graph.vacate("B", period=2)
    assert hub_default.get_spatial_context("A", agents) == {}
    assert hub_default.get_visible_neighbor_actions("A", agents) == []

    # Add an active neighbor D and ensure denominator excludes inactive B & missing C
    graph.agent_ids.append("D")
    graph.graph["D"] = set()
    graph.add_edge("A", "D")
    agents["D"] = SimpleNamespace(
        id="D", is_active=True, adopted=True, dynamic_state={"last_decision": "hold"}
    )
    spatial = hub.get_spatial_context("A", agents)
    assert spatial == {"neighbor_count": 1, "adopted_pct": 1.0}
    assert hub.get_visible_neighbor_actions_v2("A", agents) == [
        {"action": "act", "neighbor_id": "D"}
    ]
    social_v2_d = hub.get_social_context_v2("A", agents)
    assert social_v2_d["neighbor_count"] == 1
    assert social_v2_d["gossip"] == ["Neighbor D mentioned: 'gossip from D'"]
    assert social_v2_d["observable_attrs"] == {"adopted": 1.0}


def test_spatial_graph_deactivate_agent_recomputes_fallback_and_excludes_from_stats():
    positions = {
        "A": (0.0, 0.0),
        "B": (1.0, 0.0),
        "C": (10.0, 0.0),
    }
    graph = SpatialNeighborhoodGraph(
        ["A", "B", "C"], positions=positions, radius=2.0, fallback_k=1
    )
    assert set(graph.get_neighbors("A")) == {"B"}

    res = graph.vacate("B", period=3)
    assert res == {"removed": ["A", "C"], "added": [], "neighbors": []}
    assert graph.is_active_agent("B") is False
    assert "B" not in graph.positions
    assert graph.get_neighbors("B") == []
    # Active A recomputes fallback_k=1 link to surviving active C at period=3
    assert graph.get_neighbors("A") == ["C"]
    assert graph.get_edge_start_period("A", "C") == 3
    stats = graph.get_spatial_stats()
    assert stats["active_agents"] == 2
    assert stats["inactive_agents"] == 1
    assert stats["isolated_agents"] == 0
    # Re-vacating or moving an inactive agent is a no-op
    assert graph.vacate("B", period=4) == {"removed": [], "added": [], "neighbors": []}
    assert graph.move("B", (2.0, 0.0), period=4) == {"removed": [], "added": [], "neighbors": []}


def test_async_kg_prevents_ghost_relay_and_skips_inactive_observer():
    graph = SocialGraph(["A", "B", "C"])
    graph.add_edge("A", "B")
    graph.add_edge("B", "C")
    kg = AsyncKnowledgeGraph(social_graph=graph, neighbor_hops=2)
    kg.assert_fact(
        subject="A",
        predicate="adopted_measure",
        obj="tier_1",
        text="A adopted tier_1.",
        author_id="A",
        published_period=1,
        delivery_delay=0,
        visibility="neighbors",
    )

    # While B is active, C sees A via 2-hop relay through B at period 2
    assert len(kg.query_visible("C", 2, hops=2)) == 1

    # Once B becomes inactive, B stops acting as an intermediate ghost relay
    agents = {
        "A": SimpleNamespace(id="A", is_active=True),
        "B": SimpleNamespace(id="B", is_active=False),
        "C": SimpleNamespace(id="C", is_active=True),
    }
    kg.sync_active_agents(agents)
    assert kg.query_visible("C", 2, hops=2) == []

    class DummyMem:
        def __init__(self):
            self.writes = []

        def add_memory(self, aid, text, metadata=None):
            self.writes.append((aid, text, metadata))

    mem = DummyMem()
    provider = KnowledgeGraphSocialProvider(kg, memory_engine=mem, top_k=5)
    ctx_b = {}
    provider.provide("B", agents, ctx_b, period=2)
    assert ctx_b["social_gossip"] == ""
    assert mem.writes == []


def test_message_pool_and_bridge_intra_period_location_and_exit_sync():
    pool = MessagePool()
    kg = AsyncKnowledgeGraph()

    class Phase1Handler(InstitutionalLifecycleHandler):
        def post_decision(self, agent, executed_skill, year, env):
            if agent.id == "p1":
                # p1 moves from region_a to region_b during Phase 1
                agent.region_id = "region_b"
            elif agent.id == "p2":
                # p2 exits permanently during Phase 1
                agent.is_active = False

    agents = {
        "p1": SimpleNamespace(id="p1", agent_type="participant", region_id="region_a", is_active=True),
        "p2": SimpleNamespace(id="p2", agent_type="participant", region_id="region_a", is_active=True),
        "reg_b": SimpleNamespace(id="reg_b", agent_type="regulator", region_id="region_b", is_active=True),
        "reg_a": SimpleNamespace(id="reg_a", agent_type="regulator", region_id="region_a", is_active=True),
    }
    bridge = MultiActorLifecycleBridge(
        handlers={"participant": Phase1Handler()},
        message_pool=pool,
        social_kg=kg,
        role_message_policy={
            "participant": {"scope": "regional"},
            "regulator": {"scope": "global"},
        },
        institutional_roles=("regulator",),
    )

    bridge.pre_year(1, {}, agents)

    # p1 acts -> relocates to region_b inside handler -> same-year regional msg reaches reg_b, NOT reg_a
    p1_res = SimpleNamespace(
        execution_result=ExecutionResult(success=True, state_changes={}),
        outcome=SkillOutcome.APPROVED,
        executed_skill="relocate",
        approved_skill=SimpleNamespace(skill_name="relocate", parameters={}),
        executed_via_fallback=False,
    )
    agents["p1"]._last_action_context = {"year": 1}
    bridge.post_step(agents["p1"], p1_res)

    assert len(pool.get_messages("reg_b")) == 1
    assert len(pool.get_messages("reg_a")) == 0
    # Inactive or missing observers receive nothing via provider
    pool_provider = MessagePoolProvider(pool)

    # p2 exits inside handler -> global broadcast later in same year must NOT reach p2
    p2_res = SimpleNamespace(
        execution_result=ExecutionResult(success=True, state_changes={}),
        outcome=SkillOutcome.APPROVED,
        executed_skill="exit_program",
        approved_skill=SimpleNamespace(skill_name="exit_program", parameters={}),
        executed_via_fallback=False,
    )
    agents["p2"]._last_action_context = {"year": 1}
    bridge.post_step(agents["p2"], p2_res)

    reg_res = SimpleNamespace(
        execution_result=ExecutionResult(success=True, state_changes={}),
        outcome=SkillOutcome.APPROVED,
        executed_skill="announce",
        approved_skill=SimpleNamespace(skill_name="announce", parameters={}),
        executed_via_fallback=False,
    )
    agents["reg_b"]._last_action_context = {"year": 1}
    bridge.post_step(agents["reg_b"], reg_res)

    assert all(m.sender_id != "reg_b" for m in pool.get_messages("p2"))
    ctx_p2 = {}
    pool_provider.provide("p2", agents, ctx_p2)
    assert ctx_p2["messages"] == []

    # Direct GLOBAL broadcast check on MessagePool
    msg_global = pool.broadcast("reg_b", "regulator", "Global notice", timestamp=1)
    assert msg_global.scope == EventScope.GLOBAL
    assert "p2" in pool._inactive_agents
    assert all(m.content != "Global notice" for m in pool.get_messages("p2"))


def test_broker_run_zero_count_population_scoping_and_early_exit_integrity(tmp_path, monkeypatch):
    folder = tmp_path / f"p0_case_{uuid4().hex}"
    cfg_dir = folder / "config"
    cfg_dir.mkdir(parents=True)
    (folder / "__init__.py").touch()

    _write_yaml(
        cfg_dir / "skill_registry.yaml",
        {
            "default_skill": "hold",
            "skills": [
                {"skill_id": "hold", "description": "Hold position", "eligible_agent_types": ["*"]},
                {"skill_id": "exit", "description": "Exit permanently", "eligible_agent_types": ["participant"]},
            ],
        },
    )

    (folder / "world.py").write_text(
        dedent('''
            from broker.interfaces.skill_types import ExecutionResult

            class World:
                year = 0

                def advance_step(self):
                    self.year += 1
                    return {"current_year": self.year}

                def execute_skill(self, approved_skill):
                    return ExecutionResult(success=True, state_changes={})

            def build(ctx):
                return World()

            def hooks(ctx):
                def post_step(agent, result):
                    if getattr(result, "executed_skill", None) == "exit":
                        agent.is_active = False
                return {"post_step": post_step}

            def mock(ctx):
                def respond(prompt):
                    return '{"decision": 2, "reason": "Exiting in year 1"}'
                return {"participant": respond, "regulator": respond}
        '''),
        encoding="utf-8",
    )

    cfg_path = cfg_dir / "agent_types.yaml"
    _write_yaml(
        cfg_path,
        {
            "global_config": {
                "run": {
                    "world": "world:build",
                    "hooks": "world:hooks",
                    "mock": "world:mock",
                    "population": {"regulator": 0, "participant": 2},
                    "phase_order": [["regulator"], ["participant"]],
                    "years": 3,
                },
                "reflection": {"enabled": True, "interval": 3, "topic": "your situation and your decisions"},
            },
            "regulator": {
                "psychological_framework": "generic",
                "decider": {
                    "name": "rule_based",
                    "params": {"default_action": "hold", "rules": []},
                },
                "prompt_template": "R {current_year}\n{memory}\n{options_text}\n{response_format}",
                "actions": [{"id": "hold", "aliases": ["1"]}],
                "parsing": {"skill_map": {"1": "hold"}, "default_skill": "hold"},
                "response_format": {
                    "delimiter_start": "<<<DECISION_START>>>",
                    "delimiter_end": "<<<DECISION_END>>>",
                    "fields": [{"key": "decision", "type": "choice", "required": True}],
                },
            },
            "participant": {
                "psychological_framework": "generic",
                "prompt_template": "P {current_year}\n{memory}\n{options_text}\n{response_format}",
                "actions": [{"id": "hold", "aliases": ["1"]}, {"id": "exit", "aliases": ["2"]}],
                "parsing": {"skill_map": {"1": "hold", "2": "exit"}, "default_skill": "hold"},
                "response_format": {
                    "delimiter_start": "<<<DECISION_START>>>",
                    "delimiter_end": "<<<DECISION_END>>>",
                    "fields": [{"key": "decision", "type": "choice", "required": True}],
                },
            },
        },
    )

    out_dir = tmp_path / "output"
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setenv("GOVERNANCE_PROFILE", "default")
    try:
        rc = main([str(cfg_path), "--model", "mock", "--output", str(out_dir)])
    finally:
        _cleanup_case_modules(folder)

    assert rc == 0
    integrity = json.loads((out_dir / "run_integrity.json").read_text(encoding="utf-8"))
    # 0-count regulator rule_based decider must NOT trigger false decider_arms_with_zero_rows
    assert integrity.get("decider_arms_with_zero_rows") == []
    # Both participants exited in year 1 before reflection interval=3 -> zero eligible turns, clean integrity
    assert integrity["inactive_agents_final_count"] == 2
    assert integrity["inactive_agents_final"] == ["participant_1", "participant_2"]
    assert integrity["reflection_eligible_turns"] == 0
    assert integrity["integrity_ok"] is True


def test_empty_memory_retrieval_with_due_active_agent_still_fails_reflection_integrity(
    tmp_path,
):
    from broker.components.memory.engine import WindowMemoryEngine
    from broker.core.run_integrity import record_run_integrity
    from broker.run._memory import ReflectionHook, ReflectionSettings

    cfg = SimpleNamespace(get_reflection_topic=lambda _t: "your situation and your decisions")
    hook = ReflectionHook(
        ReflectionSettings(enabled=True, interval=1),
        cfg,
        WindowMemoryEngine(window_size=3),
        "mock",
        tmp_path,
    )
    active_agent = SimpleNamespace(id="a1", agent_type="participant", is_active=True)
    # Active & due in year 1, but memory engine is empty -> eligible_turns=1, stored=0 -> mismatch
    hook(1, {"a1": active_agent})
    assert hook.eligible_turns == 1
    assert hook.counts["reflections_stored"] == 0
    audit = record_run_integrity(
        tmp_path,
        reflection_enabled=True,
        reflection_eligible_turns=hook.eligible_turns,
        verbose=False,
    )
    assert audit["reflection_eligible_turns"] == 1
    assert audit["integrity_ok"] is False
