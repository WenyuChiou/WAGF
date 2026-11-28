"""End-to-end integration tests for Track B: AsyncKnowledgeGraph + MultiActorLifecycleBridge + broker.run."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from textwrap import dedent
from uuid import uuid4

import pytest
import yaml

from broker.components.orchestration.sagas import SagaStatus
from broker.core.run_integrity import GOVERNANCE_PHRASES
from broker.run import main
from broker.tools import check_governance_carryover, check_run_integrity


def _write_yaml(path, data):
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _cleanup_case_modules(folder):
    for name in list(sys.modules):
        if name == folder.name or name.startswith(f"{folder.name}."):
            sys.modules.pop(name, None)


def _agent_block(prompt_template, actions, skill_map, *, extra=None):
    block = {
        "psychological_framework": "generic",
        "prompt_template": prompt_template,
        "actions": actions,
        "parsing": {"skill_map": skill_map, "default_skill": actions[0]["id"]},
        "response_format": {
            "delimiter_start": "<<<DECISION_START>>>",
            "delimiter_end": "<<<DECISION_END>>>",
            "fields": [{"key": "decision", "type": "choice", "required": True}],
        },
    }
    if extra:
        block.update(extra)
    return block


@pytest.fixture
def integrated_case(tmp_path, monkeypatch):
    """Create a self-contained 3-actor case wired with AsyncKnowledgeGraph and MultiActorLifecycleBridge."""
    folder = tmp_path / f"e2e_kg_{uuid4().hex}"
    config_path = folder / "config" / "agent_types.yaml"
    config_path.parent.mkdir(parents=True)
    (folder / "__init__.py").touch()

    _write_yaml(
        config_path.with_name("skill_registry.yaml"),
        {
            "default_skill": "hold",
            "skills": [
                {"skill_id": "hold", "description": "Hold current policy or behavior"},
                {
                    "skill_id": "adjust_incentive",
                    "description": "Adjust program incentive rate",
                    "eligible_agent_types": ["regulator"],
                },
                {
                    "skill_id": "expand_capacity",
                    "description": "Expand service capacity",
                    "eligible_agent_types": ["provider"],
                },
                {
                    "skill_id": "enroll_program",
                    "description": "Enroll in the program",
                    "eligible_agent_types": ["consumer"],
                },
                {
                    "skill_id": "restricted_action",
                    "description": "Restricted action blocked below tier 2",
                    "eligible_agent_types": ["consumer"],
                },
            ],
        },
    )

    (folder / "case_wiring.py").write_text(
        dedent(
            '''
            import json
            from broker.agents import AgentConfig, BaseAgent, Skill
            from broker.components.coordination import MultiActorLifecycleBridge
            from broker.components.coordination.coordinator import GameMaster
            from broker.components.coordination.messages import MessagePool
            from broker.components.orchestration.institutional_lifecycle import (
                InstitutionalLifecycleHandler,
            )
            from broker.components.orchestration.sagas import (
                SagaCoordinator,
                SagaDefinition,
                SagaStep,
            )
            from broker.components.social import AsyncKnowledgeGraph
            from broker.components.social.graph import SocialGraph
            from broker.interfaces.skill_types import ExecutionResult
            from broker.utils.llm_utils import LLMStats

            LAST_POOL = None
            LAST_GM = None
            LAST_SAGA = None
            LAST_KG = None
            PHASE_EXECUTION_LOG = []


            class World:
                year = 0

                def advance_step(self):
                    self.year += 1
                    return {"current_year": self.year, "incentive_rate": 0.1}

                def execute_skill(self, approved_skill):
                    return ExecutionResult(
                        success=True,
                        state_changes={"last_executed": approved_skill.skill_name},
                        action_context={"outcome_text": f"completed {approved_skill.skill_name}"},
                    )


            class RegulatorLifecycle(InstitutionalLifecycleHandler):
                def post_decision(self, agent, decision, year, env):
                    if decision == "adjust_incentive":
                        env["incentive_rate"] = 0.2 + 0.05 * year


            class ProviderLifecycle(InstitutionalLifecycleHandler):
                def post_decision(self, agent, decision, year, env):
                    if decision == "expand_capacity":
                        env["capacity_ready"] = True


            def build_world(ctx):
                return World()


            def build_agents(ctx):
                def _skill(sid):
                    return Skill(skill_id=sid, description=sid, affected_param=None, direction="none")

                cons_1 = BaseAgent(AgentConfig(
                    name="cons_1", agent_type="consumer", state_params=[],
                    objectives=[], constraints=[],
                    skills=[_skill("hold"), _skill("enroll_program"), _skill("restricted_action")],
                ))
                cons_1.dynamic_state["tier_level"] = 1
                return {
                    "reg_1": BaseAgent(AgentConfig(
                        name="reg_1", agent_type="regulator", state_params=[],
                        objectives=[], constraints=[],
                        skills=[_skill("hold"), _skill("adjust_incentive")],
                    )),
                    "prov_1": BaseAgent(AgentConfig(
                        name="prov_1", agent_type="provider", state_params=[],
                        objectives=[], constraints=[],
                        skills=[_skill("hold"), _skill("expand_capacity")],
                    )),
                    "cons_1": cons_1,
                }


            def build_social(ctx):
                global LAST_KG
                graph = SocialGraph(list(ctx.agents))
                graph.add_edge("prov_1", "cons_1")
                graph.add_edge("reg_1", "prov_1")
                LAST_KG = AsyncKnowledgeGraph(
                    social_graph=graph,
                    half_life_periods=2.0,
                    strict_no_governance_trace=True,
                )
                return LAST_KG


            def build_hooks(ctx):
                def post_step(agent, result):
                    PHASE_EXECUTION_LOG.append((getattr(ctx.world, "year", 0), agent.agent_type, agent.id))

                return {"post_step": post_step}


            def build_coordinator(ctx):
                global LAST_POOL, LAST_GM, LAST_SAGA
                graph = ctx.social.social_graph
                LAST_POOL = MessagePool(social_graph=graph)
                LAST_GM = GameMaster(message_pool=LAST_POOL)
                LAST_SAGA = SagaCoordinator()
                LAST_SAGA.register_saga(SagaDefinition(
                    name="rollout_workflow",
                    steps=[
                        SagaStep(
                            name="prepare",
                            execute=lambda c: {**c, "prepared": True},
                            compensate=lambda c: None,
                        ),
                        SagaStep(
                            name="finalize",
                            execute=lambda c: {**c, "finalized": True},
                            compensate=lambda c: None,
                        ),
                    ],
                ))
                LAST_SAGA.start_saga("rollout_workflow", {"origin": "test"}, step=1)
                return MultiActorLifecycleBridge(
                    handlers={"regulator": RegulatorLifecycle(), "provider": ProviderLifecycle()},
                    message_pool=LAST_POOL,
                    game_master=LAST_GM,
                    saga_coordinator=LAST_SAGA,
                    social_kg=ctx.social,
                    role_message_policy={
                        "regulator": {
                            "scope": "global",
                            "message_type": "policy_announcement",
                            "priority": 10,
                            "ttl": 1,
                            "visibility": "global",
                            "delivery_delay": 1,
                        },
                        "provider": {
                            "scope": "global",
                            "message_type": "service_update",
                            "priority": 5,
                            "ttl": 1,
                            "visibility": "neighbors",
                            "delivery_delay": 1,
                        },
                        "consumer": {
                            "scope": "neighbors",
                            "message_type": "peer_action",
                            "ttl": 1,
                            "visibility": "neighbors",
                            "delivery_delay": 1,
                        },
                    },
                )


            def build_mock(ctx):
                consumer_y2_calls = {"n": 0}

                def _reply(choice):
                    text = "<<<DECISION_START>>>" + json.dumps({"decision": choice}) + "<<<DECISION_END>>>"
                    return text, LLMStats(success=True)

                def consumer_invoke(prompt):
                    if getattr(ctx.world, "year", 1) == 1:
                        # Blocked on every attempt in Year 1 -> fallback default 'hold'
                        return _reply("3")
                    # Year 2: first attempt blocked by AgentValidator -> retry chooses '2' (enroll_program)
                    consumer_y2_calls["n"] += 1
                    if consumer_y2_calls["n"] == 1:
                        return _reply("3")
                    return _reply("2")

                return {
                    "regulator": lambda prompt: _reply("2"),
                    "provider": lambda prompt: _reply("2"),
                    "consumer": consumer_invoke,
                }
            '''
        ),
        encoding="utf-8",
    )

    data = {
        "global_config": {
            "reflection": {"enabled": True, "interval": 1, "importance_boost": 0.9,
                           "topic": "service conditions and your decisions"},
            "run": {
                "world": "case_wiring:build_world",
                "agents": "case_wiring:build_agents",
                "hooks": "case_wiring:build_hooks",
                "social": "case_wiring:build_social",
                "coordinator": "case_wiring:build_coordinator",
                "mock": "case_wiring:build_mock",
                "phase_order": [["regulator"], ["provider"], ["consumer"]],
                "years": 2,
            },
        },
        "regulator": _agent_block(
            "Memory:\n{memory}\nSocial:\n{social_gossip}\nAvailable actions\n{options_text}\n\n{response_format}",
            [{"id": "hold", "aliases": ["1"]}, {"id": "adjust_incentive", "aliases": ["2"]}],
            {"1": "hold", "2": "adjust_incentive"},
        ),
        "provider": _agent_block(
            "Memory:\n{memory}\nSocial:\n{social_gossip}\nAvailable actions\n{options_text}\n\n{response_format}",
            [{"id": "hold", "aliases": ["1"]}, {"id": "expand_capacity", "aliases": ["2"]}],
            {"1": "hold", "2": "expand_capacity"},
        ),
        "consumer": _agent_block(
            "Memory:\n{memory}\nSocial:\n{social_gossip}\nAvailable actions\n{options_text}\n\n{response_format}",
            [
                {"id": "hold", "aliases": ["1"]},
                {"id": "enroll_program", "aliases": ["2"]},
                {"id": "restricted_action", "aliases": ["3"]},
            ],
            {"1": "hold", "2": "enroll_program", "3": "restricted_action"},
            extra={
                "governance": {
                    "default": {
                        "thinking_rules": [
                            {
                                "id": "tier_restriction_rule",
                                "conditions": [{"expression": "tier_level < 2"}],
                                "blocked_skills": ["restricted_action"],
                                "level": "ERROR",
                                "message": "restricted_action requires tier_level >= 2",
                            }
                        ]
                    }
                }
            },
        ),
    }

    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setenv("GOVERNANCE_PROFILE", "default")
    yield config_path, data
    _cleanup_case_modules(folder)


def _traces(output, agent_type):
    path = output / "raw" / f"{agent_type}_traces.jsonl"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and "step_id" in json.loads(line)
    ]


def test_e2e_integrated_async_kg_multi_actor_and_invariant7(integrated_case, tmp_path):
    config, data = integrated_case
    _write_yaml(config, data)
    output = tmp_path / "integrated_run"

    assert main([str(config), "--model", "mock", "--output", str(output)]) == 0

    mod = sys.modules[f"{config.parents[1].name}.case_wiring"]

    # 1. Phase order respected in both years
    assert mod.PHASE_EXECUTION_LOG == [
        (1, "regulator", "reg_1"),
        (1, "provider", "prov_1"),
        (1, "consumer", "cons_1"),
        (2, "regulator", "reg_1"),
        (2, "provider", "prov_1"),
        (2, "consumer", "cons_1"),
    ]

    # 2. Delayed KG propagation (delivery_delay=1): Year 1 invisible, Year 2 visible
    cons_y1 = next(r for r in _traces(output, "consumer") if r["year"] == 1)
    cons_y2 = next(r for r in _traces(output, "consumer") if r["year"] == 2)
    assert "reg_1 (regulator) executed adjust_incentive" not in cons_y1["input"]
    assert "prov_1 (provider) executed expand_capacity" not in cons_y1["input"]
    assert "reg_1 (regulator) executed adjust_incentive" in cons_y2["input"]
    assert "prov_1 (provider) executed expand_capacity" in cons_y2["input"]

    # 3. MessagePool received executed-action publications & GameMaster recorded resolutions
    assert mod.LAST_POOL.summary()["total_messages"] > 0
    assert len(mod.LAST_GM.resolution_history) == 6
    assert mod.LAST_SAGA.get_status("saga_1") == SagaStatus.COMPLETED
    assert len(mod.LAST_SAGA.results) == 1

    # 4. OriginGate memory_log.jsonl has decision, reflection, and social entries with zero leakage
    mem_entries = [
        json.loads(line)
        for line in (output / "memory_log.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    origins = {e["origin"] for e in mem_entries}
    assert {"decision", "reflection", "social"}.issubset(origins)
    assert any(e["origin"] == "social" and e["period"] == 2 for e in mem_entries)
    assert not any(e["origin"] == "social" and e["period"] == 1 for e in mem_entries)

    for e in mem_entries:
        low = e["content"].lower()
        assert "restricted_action" not in low
        assert "tier_restriction_rule" not in low
        for phrase in GOVERNANCE_PHRASES:
            assert phrase not in low

    # 5. Reflection ran and recorded lessons
    refl_entries = [
        json.loads(line)
        for line in (output / "reflection_log.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(refl_entries) == 6  # 3 agents x 2 years

    # 6. run_integrity.json & check_run_integrity --strict CLI exit 0
    integrity = json.loads((output / "run_integrity.json").read_text(encoding="utf-8"))
    assert integrity["integrity_ok"] is True
    assert integrity["governance_carryover"]["ok"] is True

    repo_root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [sys.executable, "-m", "broker.tools.check_run_integrity", "--strict", str(output)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_e2e_integrated_twin_run_governance_carryover_passes(integrated_case, tmp_path):
    config, data = integrated_case
    _write_yaml(config, data)
    twin_out = tmp_path / "twin_check"

    report = check_governance_carryover.check(
        config, years=2, output=twin_out, require="both"
    )
    assert report["status"] == "pass", report
    assert report["run_a"]["default_rows"] >= 1
    assert report["run_a"]["approved_after_retry_rows"] >= 1
    assert report["differences"] == []

    # Also verify CLI invocation exits 0
    cli_out = tmp_path / "twin_cli"
    repo_root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "broker.tools.check_governance_carryover",
            str(config),
            "--years",
            "2",
            "--require",
            "both",
            "--output",
            str(cli_out),
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
