"""End-to-end tests for P1 retrospective causal join keys and opt-in context snapshots."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from textwrap import dedent
from uuid import uuid4

import pytest
import yaml

from broker.components.memory.engines.humancentric import HumanCentricMemoryEngine
from broker.components.memory.origin_gate import install_origin_gate
from broker.run import main


def _write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


@pytest.fixture
def multi_actor_trace_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    folder = tmp_path / f"trace_case_{uuid4().hex}"
    config_path = folder / "config" / "agent_types.yaml"
    config_path.parent.mkdir(parents=True)
    (folder / "__init__.py").touch()

    (folder / "case_hooks.py").write_text(
        dedent(
            """
            from broker.agents import AgentConfig, BaseAgent, Skill
            from broker.components.coordination.bridge import MultiActorLifecycleBridge
            from broker.components.coordination.messages import MessagePool
            from broker.components.social.graph import SpatialNeighborhoodGraph
            from broker.components.social.knowledge_graph import AsyncKnowledgeGraph
            from broker.interfaces.skill_types import ExecutionResult
            from broker.utils.llm_utils import LLMStats

            class TraceWorld:
                year = 0
                def advance_step(self):
                    self.year += 1
                    return {"current_year": self.year, "hazard_active": self.year == 1}
                def execute_skill(self, approved_skill):
                    return ExecutionResult(
                        success=True,
                        state_changes={"last_action": approved_skill.skill_name},
                        action_context={"outcome_text": f"executed_{approved_skill.skill_name}"},
                    )

            def build_world(ctx):
                return TraceWorld()

            def build_agents(ctx):
                def _skills(aid_type):
                    if aid_type == "authority":
                        return [Skill("issue_advisory", "Issue advisory", None, "none")]
                    return [
                        Skill("keep_status", "Keep status", None, "none"),
                        Skill("mitigate", "Adopt mitigation", None, "none"),
                    ]

                agents = {}
                for atype, count in (ctx.population or {"authority": 1, "resident": 2}).items():
                    for idx in range(1, count + 1):
                        aid = f"{atype}_{idx}"
                        ag = BaseAgent(
                            AgentConfig(
                                name=aid,
                                agent_type=atype,
                                state_params=[],
                                objectives=[],
                                constraints=[],
                                skills=_skills(atype),
                            )
                        )
                        if atype == "resident":
                            ag.custom_attributes["zone"] = "north"
                            ag.memory = [f"Seed profile line for {aid}."]
                        agents[aid] = ag
                return agents

            def _ensure_state(ctx):
                if not hasattr(ctx, "_trace_state"):
                    resident_ids = [
                        aid for aid, ag in ctx.agents.items() if ag.agent_type == "resident"
                    ]
                    graph = SpatialNeighborhoodGraph(
                        resident_ids,
                        positions={aid: (i, 0) for i, aid in enumerate(resident_ids)},
                        radius=2.0,
                        fallback_k=1,
                    )
                    kg = AsyncKnowledgeGraph(social_graph=graph, neighbor_hops=2)
                    pool = MessagePool(social_graph=graph)
                    bridge = MultiActorLifecycleBridge(
                        message_pool=pool,
                        social_kg=kg,
                        institutional_roles=("authority",),
                        role_message_policy={
                            "authority": {"scope": "global", "delivery_delay": 0},
                            "resident": {"scope": "neighbors", "delivery_delay": 0},
                        },
                        default_delivery_delay=0,
                    )
                    ctx._trace_state = (graph, kg, pool, bridge)
                return ctx._trace_state

            def build_social(ctx):
                _, kg, _, _ = _ensure_state(ctx)
                return kg

            def build_coordinator(ctx):
                _, _, _, bridge = _ensure_state(ctx)
                return bridge

            def build_mock(ctx):
                def auth_invoke(prompt):
                    return '{"decision": 1}', LLMStats(success=True)

                def res_invoke(prompt):
                    if "mitigate" in prompt and "authority_1" in prompt:
                        return '{"decision": 2}', LLMStats(success=True)
                    return '{"decision": 1}', LLMStats(success=True)

                return {"authority": auth_invoke, "resident": res_invoke}
            """
        ),
        encoding="utf-8",
    )

    _write_yaml(
        config_path.with_name("skill_registry.yaml"),
        {
            "default_skill": "keep_status",
            "skills": [
                {"skill_id": "issue_advisory", "description": "Issue advisory", "eligible_agent_types": ["authority"]},
                {"skill_id": "keep_status", "description": "Keep status", "eligible_agent_types": ["resident"]},
                {"skill_id": "mitigate", "description": "Adopt mitigation", "eligible_agent_types": ["resident"]},
            ],
        },
    )

    data = {
        "global_config": {
            "run": {
                "world": "case_hooks:build_world",
                "agents": "case_hooks:build_agents",
                "social": "case_hooks:build_social",
                "coordinator": "case_hooks:build_coordinator",
                "mock": "case_hooks:build_mock",
                "population": {"authority": 1, "resident": 2},
                "phase_order": [["authority"], ["resident"]],
                "strict_keys": True,
            },
            "memory": {"engine_type": "humancentric", "deterministic_consolidation": True},
            "reflection": {"enabled": True, "interval": 1, "importance_boost": 0.9},
            "audit": {"context_snapshot": True},
        },
        "authority": {
            "psychological_framework": "none",
            "prompt_template": "Role: authority\n{options_text}\n\n{response_format}",
            "actions": [{"id": "issue_advisory", "aliases": ["1"]}],
            "parsing": {"skill_map": {"1": "issue_advisory"}, "default_skill": "issue_advisory"},
            "response_format": {
                "delimiter_start": "<<<DECISION_START>>>",
                "delimiter_end": "<<<DECISION_END>>>",
                "fields": [{"key": "decision", "type": "choice", "required": True}],
            },
        },
        "resident": {
            "psychological_framework": "generic",
            "prompt_template": "Social:\n{social_gossip}\nMemory:\n{memory}\n{options_text}\n\n{response_format}",
            "actions": [{"id": "keep_status", "aliases": ["1"]}, {"id": "mitigate", "aliases": ["2"]}],
            "parsing": {"skill_map": {"1": "keep_status", "2": "mitigate"}, "default_skill": "keep_status"},
            "response_format": {
                "delimiter_start": "<<<DECISION_START>>>",
                "delimiter_end": "<<<DECISION_END>>>",
                "fields": [{"key": "decision", "type": "choice", "required": True}],
            },
        },
    }
    _write_yaml(config_path, data)
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setenv("GOVERNANCE_PROFILE", "default")
    yield config_path, data
    for name in list(sys.modules):
        if name == folder.name or name.startswith(f"{folder.name}."):
            sys.modules.pop(name, None)


def test_retrospective_causal_join_keys_end_to_end(multi_actor_trace_case, tmp_path: Path):
    config_path, _ = multi_actor_trace_case
    output = tmp_path / "run_out"
    assert main([str(config_path), "--model", "mock", "--years", "2", "--output", str(output)]) == 0

    broker_run = json.loads((output / "broker_run.json").read_text(encoding="utf-8"))
    manifest = json.loads((output / "reproducibility_manifest.json").read_text(encoding="utf-8"))
    coord_snap = json.loads((output / "coordination_snapshot.json").read_text(encoding="utf-8"))
    mem_entries = [
        json.loads(line)
        for line in (output / "memory_log.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    refl_entries = [
        json.loads(line)
        for line in (output / "reflection_log.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    auth_traces = [
        json.loads(line)
        for line in (output / "raw" / "authority_traces.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    res_traces = [
        json.loads(line)
        for line in (output / "raw" / "resident_traces.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    auth_traces = [t for t in auth_traces if "step_id" in t]
    res_traces = [t for t in res_traces if "step_id" in t]

    run_id = broker_run["run_id"]
    assert isinstance(run_id, str) and run_id.startswith("run_")
    assert manifest["run_id"] == run_id
    assert coord_snap["run_id"] == run_id
    assert all(e["run_id"] == run_id for e in mem_entries)
    assert all(e["run_id"] == run_id for e in refl_entries)
    assert all(t["run_id"] == run_id for t in auth_traces + res_traces)

    # Sequential memory_id across all writes
    assert [e["memory_id"] for e in mem_entries] == [f"mem-{i}" for i in range(1, len(mem_entries) + 1)]
    mem_by_id = {e["memory_id"]: e for e in mem_entries}

    # Decision memories link cleanly to originating raw traces via source_step_id
    decision_mems = [e for e in mem_entries if e["origin"] == "decision"]
    all_step_ids = {t["step_id"] for t in auth_traces + res_traces}
    assert decision_mems
    assert all(e["source_step_id"] in all_step_ids for e in decision_mems)

    # Social KG audit in traces + social memories link back to author's source_step_id
    y2_res_traces = [t for t in res_traces if t["year"] == 2]
    assert y2_res_traces
    kg_triples_seen = y2_res_traces[0]["social_audit"]["kg_triples"]
    assert kg_triples_seen
    assert any(
        item["author_id"] == "authority_1"
        and item["effective_available_period"] <= 2
        and item["source_step_id"] in {t["step_id"] for t in auth_traces}
        for item in kg_triples_seen
    )

    social_mems = [e for e in mem_entries if e["origin"] == "social"]
    assert social_mems
    assert any(
        "triple_id" in e and "author_id" in e and "effective_available_period" in e and "source_step_id" in e
        for e in social_mems
    )

    # Reflection join keys: reflection_log <-> memory_log <-> raw trace memory_audit
    assert refl_entries
    assert all(e["reflection_id"].startswith("refl-") and e["retrieved_memory_ids"] for e in refl_entries)
    for r_entry in refl_entries:
        for mid in r_entry["retrieved_memory_ids"]:
            assert mid in mem_by_id
    refl_mems = [e for e in mem_entries if e["origin"] == "reflection"]
    assert {e["reflection_id"] for e in refl_mems} >= {e["reflection_id"] for e in refl_entries}

    # Audit memories carry memory_id/origin passthrough; context_snapshot stays JSONL-only
    assert all("context_snapshot" in t for t in res_traces)
    assert all(
        "memory_id" in m
        for t in y2_res_traces
        for m in t["memory_audit"]["memories"]
    )
    with (output / "resident_governance_audit.csv").open(encoding="utf-8-sig", newline="") as fh:
        headers = next(csv.reader(fh))
    assert "context_snapshot" not in headers

    # Coordination snapshot captures bridge & KG state
    assert coord_snap["coordinator"]["social_kg"]["triple_count"] >= 3
    assert coord_snap["coordinator"]["social_graph"]["num_agents"] == 2


def test_context_snapshot_off_and_no_coordination_snapshot_when_unused(
    multi_actor_trace_case, tmp_path: Path
):
    config_path, data = multi_actor_trace_case
    # Turn context_snapshot off and remove social/coordinator slots
    data["global_config"]["audit"]["context_snapshot"] = False
    data["global_config"]["run"] = {
        "world": "case_hooks:build_world",
        "mock": "case_hooks:build_mock",
        "population": {"resident": 1},
    }
    _write_yaml(config_path, data)
    output = tmp_path / "plain_out"
    assert main([str(config_path), "--model", "mock", "--years", "1", "--output", str(output)]) == 0
    assert not (output / "coordination_snapshot.json").exists()
    traces = [
        json.loads(line)
        for line in (output / "raw" / "resident_traces.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    decision_rows = [t for t in traces if "step_id" in t]
    assert decision_rows and all("context_snapshot" not in t for t in decision_rows)


def test_origin_gate_preserves_caller_metadata_and_seed_scoring(tmp_path: Path):
    engine = HumanCentricMemoryEngine(window_size=3, top_k_significant=1, seed=42)
    gate = install_origin_gate(engine, tmp_path, period=lambda: 1, run_id="run_test_1")

    # Bare string during seeding keeps emotion*source importance instead of metadata={} -> 0.5
    engine.add_memory("a1", "Year 0: suffered major damage.")
    stored = engine.working["a1"][0]
    assert stored["memory_id"] == "mem-1"
    assert stored["origin"] == "seed"
    assert stored["importance"] != 0.5

    # Caller dict is never mutated in place
    gate.seeding = False
    caller_meta = {"origin": "decision", "period": 1, "source_step_id": 7}
    engine.add_memory("a1", "Year 1: Action carried out: Wait.", metadata=caller_meta)
    assert set(caller_meta.keys()) == {"origin", "period", "source_step_id"}
    assert engine.working["a1"][1]["memory_id"] == "mem-2"

    log_rows = [
        json.loads(line)
        for line in (tmp_path / "memory_log.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert log_rows[0]["memory_id"] == "mem-1" and log_rows[0]["run_id"] == "run_test_1"
    assert log_rows[1]["memory_id"] == "mem-2" and log_rows[1]["source_step_id"] == 7


def test_origin_gate_stamps_bare_seed_memories_across_bounded_longterm_reordering(tmp_path: Path):
    engine = HumanCentricMemoryEngine(
        window_size=1,
        top_k_significant=2,
        max_working=1,
        max_longterm=2,
        deterministic_consolidation=True,
        seed=42,
    )
    install_origin_gate(engine, tmp_path, period=lambda: 0, run_id="run_bounded")

    # Sequence reproduces Codex P2: longterm capacity eviction sorts by importance,
    # so the newly consolidated dict may sit at index 0 rather than longterm[-1].
    for line in (
        "my critical failure and loss",
        "my success outcome",
        "my important decision today",
        "uneventful routine note",
    ):
        engine.add_memory("a1", line)

    for bucket in (engine.working["a1"], engine.longterm["a1"]):
        assert all("memory_id" in item and item.get("origin") == "seed" for item in bucket)

    ids_by_content = {
        row["content"]: row["memory_id"]
        for row in map(json.loads, (tmp_path / "memory_log.jsonl").read_text(encoding="utf-8").splitlines())
    }
    for item in engine.longterm["a1"]:
        assert item["memory_id"] == ids_by_content[item["content"]]
