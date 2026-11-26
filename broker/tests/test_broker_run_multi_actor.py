"""Tests for MultiActorLifecycleBridge and opt-in social/coordinator broker.run slots."""

from __future__ import annotations

import json
import sys
from textwrap import dedent
from types import SimpleNamespace
from uuid import uuid4

import pytest
import yaml

from broker.components.analytics.interaction import InteractionHub
from broker.components.context.providers import ContextProvider
from broker.components.coordination import MultiActorLifecycleBridge
from broker.components.coordination.coordinator import GameMaster
from broker.components.coordination.messages import MessagePool
from broker.components.coordination.provider import MessagePoolProvider
from broker.components.orchestration.institutional_lifecycle import (
    InstitutionalLifecycleHandler,
)
from broker.components.orchestration.sagas import (
    SagaCoordinator,
    SagaDefinition,
    SagaStatus,
    SagaStep,
)
from broker.components.social.graph import SocialGraph
from broker.core.run_integrity import GOVERNANCE_PHRASES
from broker.interfaces.skill_types import (
    ApprovedSkill,
    ExecutionResult,
    SkillBrokerResult,
    SkillOutcome,
    SkillProposal,
)
from broker.run import _entry, main
from broker.tools import check_run_integrity


def _write_yaml(path, data):
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def _cleanup_case_modules(folder):
    for name in list(sys.modules):
        if name == folder.name or name.startswith(f"{folder.name}."):
            sys.modules.pop(name, None)


def _agent_block(prompt_template, actions, skill_map):
    return {
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


@pytest.fixture
def multi_actor_case(tmp_path, monkeypatch):
    """Build a domain-generic 3-agent-type case (regulator, provider, consumer)."""
    folder = tmp_path / f"ma_case_{uuid4().hex}"
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
                    "skill_id": "blocked_action",
                    "description": "Restricted action blocked by validator",
                    "eligible_agent_types": ["consumer"],
                },
            ],
        },
    )

    (folder / "case_hooks.py").write_text(
        dedent(
            '''
            import json
            from broker.agents import AgentConfig, BaseAgent, Skill
            from broker.components.coordination import MultiActorLifecycleBridge
            from broker.components.coordination.coordinator import GameMaster
            from broker.components.coordination.messages import MessagePool
            from broker.components.coordination.provider import MessagePoolProvider
            from broker.components.orchestration.institutional_lifecycle import (
                InstitutionalLifecycleHandler,
            )
            from broker.components.orchestration.sagas import (
                SagaCoordinator,
                SagaDefinition,
                SagaStatus,
                SagaStep,
            )
            from broker.components.social.graph import SocialGraph
            from broker.interfaces.skill_types import ExecutionResult, ValidationResult
            from broker.utils.llm_utils import LLMStats

            PHASE_LOG = []
            EXTRA_HOOK_CALLS = []
            KG_RECORDS = []
            REFLECTION_SEEN_ENV = []
            SAGA_INSTANCE = None
            POOL_INSTANCE = None
            GM_INSTANCE = None


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


            class RegulatorHandler(InstitutionalLifecycleHandler):
                def pre_year(self, agent, year, env):
                    env.setdefault("pre_year_roles", []).append((year, agent.agent_type))

                def post_decision(self, agent, decision, year, env):
                    if decision == "adjust_incentive":
                        env["incentive_rate"] = 0.25 + 0.05 * year

                def post_year(self, agent, year, env):
                    env["settled_year"] = year
                    REFLECTION_SEEN_ENV.append((year, env.get("incentive_rate")))


            class ProviderHandler(InstitutionalLifecycleHandler):
                def post_decision(self, agent, decision, year, env):
                    if decision == "expand_capacity":
                        env["capacity_expanded"] = True


            class DuckSocialKG:
                def __init__(self, graph):
                    self.graph = graph
                    self.records = KG_RECORDS
                    self._synced = set()

                def record_executed_action(
                    self,
                    agent_id,
                    agent_role,
                    action_name,
                    period,
                    *,
                    number_text="",
                    delivery_delay=1,
                    visibility="neighbors",
                    outcome_text="",
                ):
                    self.records.append(
                        {
                            "agent_id": agent_id,
                            "agent_role": agent_role,
                            "action_name": action_name,
                            "period": period,
                            "number_text": number_text,
                            "delivery_delay": delivery_delay,
                            "visibility": visibility,
                            "outcome_text": outcome_text,
                        }
                    )

                def as_context_provider(self, period_getter, *, memory_engine=None):
                    kg = self

                    class _DuckKGProvider:
                        def provide(self, agent_id, agents, context, **kwargs):
                            current = period_getter()
                            lines = [
                                f"KG notice: {rec['agent_id']} ({rec['agent_role']}) ran {rec['action_name']} at period {rec['period']}"
                                for rec in kg.records
                                if rec["period"] + rec["delivery_delay"] <= current
                                and rec["agent_id"] != agent_id
                            ]
                            if lines:
                                local = context.setdefault("local", {})
                                social = local.setdefault("social", [])
                                social.extend(lines)
                                context["kg_social_digest"] = " | ".join(lines)
                            if memory_engine is not None:
                                for idx, rec in enumerate(kg.records):
                                    key = (agent_id, idx)
                                    if (
                                        key not in kg._synced
                                        and rec["period"] + rec["delivery_delay"] <= current
                                        and rec["agent_id"] != agent_id
                                    ):
                                        kg._synced.add(key)
                                        memory_engine.add_memory(
                                            agent_id,
                                            f"Period {rec['period']}: peer {rec['agent_id']} executed {rec['action_name']}.",
                                            {
                                                "origin": "social",
                                                "period": current,
                                                "importance": 0.4,
                                                "emotion": "neutral",
                                                "source": "social",
                                            },
                                        )

                    return _DuckKGProvider()


            def build_world(ctx):
                return World()


            def build_agents(ctx):
                def _skill(sid):
                    return Skill(skill_id=sid, description=sid, affected_param=None, direction="none")

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
                    "cons_1": BaseAgent(AgentConfig(
                        name="cons_1", agent_type="consumer", state_params=[],
                        objectives=[], constraints=[],
                        skills=[_skill("hold"), _skill("enroll_program"), _skill("blocked_action")],
                    )),
                }


            def build_social_pool(ctx):
                global POOL_INSTANCE
                graph = SocialGraph(list(ctx.agents))
                graph.add_edge("prov_1", "cons_1")
                POOL_INSTANCE = MessagePool(social_graph=graph)
                return MessagePoolProvider(POOL_INSTANCE, max_messages=10)


            def build_social_kg(ctx):
                graph = SocialGraph(list(ctx.agents))
                graph.add_edge("prov_1", "cons_1")
                return DuckSocialKG(graph)


            def build_hooks(ctx):
                def pre_year(year, env, agents):
                    EXTRA_HOOK_CALLS.append(("pre_year", year))

                def post_step(agent, result):
                    PHASE_LOG.append((getattr(ctx.world, "year", 0), agent.agent_type, agent.id))

                def post_year(year, agents):
                    EXTRA_HOOK_CALLS.append(("post_year", year))

                def after_run(output_dir):
                    EXTRA_HOOK_CALLS.append(("after_run", str(output_dir)))

                return {
                    "pre_year": pre_year,
                    "post_step": post_step,
                    "post_year": post_year,
                    "after_run": after_run,
                }


            def build_coordinator(ctx):
                global SAGA_INSTANCE, GM_INSTANCE
                saga = SagaCoordinator()
                saga.register_saga(SagaDefinition(
                    name="program_rollout",
                    steps=[
                        SagaStep(
                            name="allocate",
                            execute=lambda c: {**c, "allocated": True},
                            compensate=lambda c: None,
                        ),
                        SagaStep(
                            name="activate",
                            execute=lambda c: {**c, "activated": True},
                            compensate=lambda c: None,
                        ),
                    ],
                ))
                saga.start_saga("program_rollout", {"stage": "init"}, step=1)
                SAGA_INSTANCE = saga

                pool = POOL_INSTANCE
                if pool is None:
                    pool = MessagePool()
                GM_INSTANCE = GameMaster(message_pool=pool)

                social_kg = ctx.social if hasattr(ctx.social, "record_executed_action") else None
                return MultiActorLifecycleBridge(
                    handlers={"regulator": RegulatorHandler(), "provider": ProviderHandler()},
                    message_pool=pool,
                    game_master=GM_INSTANCE,
                    saga_coordinator=saga,
                    social_kg=social_kg,
                    role_message_policy={
                        "regulator": {
                            "scope": "global",
                            "message_type": "policy_announcement",
                            "priority": 10,
                            "ttl": 1,
                            "delivery_delay": 1,
                        },
                        "provider": {
                            "scope": "global",
                            "message_type": "service_update",
                            "priority": 5,
                            "ttl": 1,
                            "delivery_delay": 1,
                        },
                        "consumer": {
                            "scope": "neighbors",
                            "message_type": "peer_action",
                            "ttl": 1,
                            "delivery_delay": 1,
                        },
                    },
                )


            def block_restricted(proposal, context, registry):
                if proposal.skill_name != "blocked_action":
                    return []
                return [
                    ValidationResult(
                        valid=False,
                        validator_name="restricted_rule",
                        errors=["blocked_action is prohibited"],
                        metadata={"rule_id": "restricted_rule", "level": "ERROR"},
                    )
                ]


            def build_validators(ctx):
                return (block_restricted,)


            def build_mock(ctx):
                def _respond(choice):
                    text = "<<<DECISION_START>>>" + json.dumps({"decision": choice}) + "<<<DECISION_END>>>"
                    return text, LLMStats(success=True)

                return {
                    "regulator": lambda prompt: _respond("2"),
                    "provider": lambda prompt: _respond("2"),
                    "consumer": lambda prompt: _respond("3" if "Year 1:" in prompt else "2"),
                }
            '''
        ),
        encoding="utf-8",
    )

    data = {
        "global_config": {
            "reflection": {"enabled": True, "interval": 1, "importance_boost": 0.9},
            "run": {
                "world": "case_hooks:build_world",
                "agents": "case_hooks:build_agents",
                "hooks": "case_hooks:build_hooks",
                "social": "case_hooks:build_social_pool",
                "coordinator": "case_hooks:build_coordinator",
                "mock": "case_hooks:build_mock",
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
            "Memory:\n{memory}\nSocial:\n{social_gossip}\nKG:\n{kg_social_digest}\nAvailable actions\n{options_text}\n\n{response_format}",
            [
                {"id": "hold", "aliases": ["1"]},
                {"id": "enroll_program", "aliases": ["2"]},
                {"id": "blocked_action", "aliases": ["3"]},
            ],
            {"1": "hold", "2": "enroll_program", "3": "blocked_action"},
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


def test_multi_actor_e2e_with_message_pool_saga_reflection_and_invariant7(multi_actor_case, tmp_path):
    config, data = multi_actor_case
    data["global_config"]["run"]["validators"] = "case_hooks:build_validators"
    _write_yaml(config, data)
    output = tmp_path / "out_pool"

    assert main([str(config), "--model", "mock", "--output", str(output)]) == 0

    mod = sys.modules[f"{config.parents[1].name}.case_hooks"]

    # 1. Phase execution order: regulator -> provider -> consumer each year
    assert mod.PHASE_LOG == [
        (1, "regulator", "reg_1"),
        (1, "provider", "prov_1"),
        (1, "consumer", "cons_1"),
        (2, "regulator", "reg_1"),
        (2, "provider", "prov_1"),
        (2, "consumer", "cons_1"),
    ]

    # 2. Inner hooks preserved (not overwritten by coordinator bridge)
    assert ("pre_year", 1) in mod.EXTRA_HOOK_CALLS
    assert ("post_year", 1) in mod.EXTRA_HOOK_CALLS
    assert ("pre_year", 2) in mod.EXTRA_HOOK_CALLS
    assert ("post_year", 2) in mod.EXTRA_HOOK_CALLS
    assert ("after_run", str(output)) in mod.EXTRA_HOOK_CALLS

    # 3. MessagePool delivery into downstream prompts (same period across phases)
    prov_y1 = next(r for r in _traces(output, "provider") if r["year"] == 1)
    cons_y1 = next(r for r in _traces(output, "consumer") if r["year"] == 1)
    assert "reg_1 (regulator) executed adjust incentive" in prov_y1["input"]
    assert "reg_1 (regulator) executed adjust incentive" in cons_y1["input"]
    assert "prov_1 (provider) executed expand capacity" in cons_y1["input"]

    # 4. SagaCoordinator completed across the 2 years
    assert mod.SAGA_INSTANCE.get_status("saga_1") == SagaStatus.COMPLETED
    assert len(mod.SAGA_INSTANCE.results) == 1
    assert mod.SAGA_INSTANCE.results[0].completed_steps == ["allocate", "activate"]

    # 5. GameMaster recorded executed resolutions
    assert len(mod.GM_INSTANCE.resolution_history) == 6

    # 6. OriginGate memory_log.jsonl + Invariant 7 clean (rejected proposal never leaked)
    mem_log = [
        json.loads(line)
        for line in (output / "memory_log.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert mem_log
    assert all(entry["origin"] in ("decision", "reflection", "social", "world", "seed") for entry in mem_log)
    for entry in mem_log:
        low = entry["content"].lower()
        assert "blocked_action" not in low
        assert "restricted_rule" not in low
        for phrase in GOVERNANCE_PHRASES:
            assert phrase not in low

    for msg in mod.POOL_INSTANCE._messages:
        low = msg.content.lower()
        assert "blocked_action" not in low
        assert "restricted_rule" not in low
        for phrase in GOVERNANCE_PHRASES:
            assert phrase not in low

    # 7. Reflection ran AFTER settled post_year
    assert len(mod.REFLECTION_SEEN_ENV) == 2
    assert (output / "reflection_log.jsonl").is_file()

    # 8. run_integrity.json & check_run_integrity CLI
    integrity = json.loads((output / "run_integrity.json").read_text(encoding="utf-8"))
    assert integrity["integrity_ok"] is True
    assert integrity["governance_carryover"]["ok"] is True
    with pytest.raises(SystemExit) as exc_info:
        check_run_integrity.main([str(output)])
    assert exc_info.value.code == 0

    # 9. broker_run.json records social and coordinator slots
    run_record = json.loads((output / "broker_run.json").read_text(encoding="utf-8"))
    assert run_record["slots"]["social"] == "case_hooks:build_social_pool"
    assert run_record["slots"]["coordinator"] == "case_hooks:build_coordinator"
    assert run_record["phase_order"] == [["regulator"], ["provider"], ["consumer"]]


def test_multi_actor_e2e_with_duck_typed_social_kg_as_context_provider(multi_actor_case, tmp_path):
    config, data = multi_actor_case
    data["global_config"]["run"]["social"] = "case_hooks:build_social_kg"
    data["global_config"]["run"]["years"] = 2
    _write_yaml(config, data)
    output = tmp_path / "out_kg"

    assert main([str(config), "--model", "mock", "--output", str(output)]) == 0

    mod = sys.modules[f"{config.parents[1].name}.case_hooks"]

    # social_kg.record_executed_action received executed actions for all 3 roles x 2 years
    assert len(mod.KG_RECORDS) == 6
    assert {r["agent_role"] for r in mod.KG_RECORDS} == {"regulator", "provider", "consumer"}

    # Delayed KG records from period 1 (delivery_delay=1) arrive in period 2 downstream prompts
    cons_y1 = next(r for r in _traces(output, "consumer") if r["year"] == 1)
    cons_y2 = next(r for r in _traces(output, "consumer") if r["year"] == 2)
    assert "KG notice:" not in cons_y1["input"]
    assert "KG notice: reg_1 (regulator) ran adjust_incentive at period 1" in cons_y2["input"]

    # Social memories tagged origin="social" logged by OriginGate
    mem_log = [
        json.loads(line)
        for line in (output / "memory_log.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(entry["origin"] == "social" for entry in mem_log)

    integrity = json.loads((output / "run_integrity.json").read_text(encoding="utf-8"))
    assert integrity["integrity_ok"] is True
    assert integrity["governance_carryover"]["ok"] is True


def test_unknown_phase_order_agent_type_raises_run_error(multi_actor_case, tmp_path, capsys):
    config, data = multi_actor_case
    data["global_config"]["run"]["phase_order"] = [["regulator"], ["typo_role"], ["consumer"]]
    _write_yaml(config, data)

    with pytest.raises(_entry.RunError, match="typo_role"):
        _entry.prepare([str(config), "--output", str(tmp_path / "out_err")])

    assert main([str(config), "--output", str(tmp_path / "out_cli_err")]) == 2
    assert "typo_role" in capsys.readouterr().err


@pytest.mark.parametrize("slot_name", ["social", "coordinator"])
def test_invalid_social_or_coordinator_slot_return_raises_slot_error(
    multi_actor_case, tmp_path, slot_name
):
    config, data = multi_actor_case
    folder = config.parents[1]
    (folder / "bad_slot.py").write_text("def bad(ctx):\n    return 12345\n", encoding="utf-8")
    data["global_config"]["run"][slot_name] = "bad_slot:bad"
    _write_yaml(config, data)

    with pytest.raises(_entry.SlotError):
        _entry.prepare([str(config), "--output", str(tmp_path / f"bad_{slot_name}")])


def test_social_slot_supports_sequence_and_interaction_hub_and_coordinator_mapping(
    multi_actor_case, tmp_path
):
    config, data = multi_actor_case
    folder = config.parents[1]
    (folder / "alt_slots.py").write_text(
        dedent(
            '''
            from broker.components.analytics.interaction import InteractionHub
            from broker.components.context.providers import ContextProvider
            from broker.components.social.graph import SocialGraph


            class TagProvider(ContextProvider):
                def __init__(self, key, val):
                    self.key = key
                    self.val = val

                def provide(self, agent_id, agents, context, **kwargs):
                    context[self.key] = self.val


            def seq_social(ctx):
                return [TagProvider("tag_a", "alpha"), TagProvider("tag_b", "beta")]


            def hub_social(ctx):
                g = SocialGraph(list(ctx.agents))
                return InteractionHub(graph=g)


            def mapping_coord(ctx):
                seen = []

                def post_year(year, agents):
                    seen.append(year)

                return {"post_year": post_year}
            '''
        ),
        encoding="utf-8",
    )

    data["global_config"]["run"]["social"] = "alt_slots:seq_social"
    data["global_config"]["run"]["coordinator"] = "alt_slots:mapping_coord"
    _write_yaml(config, data)
    prep_seq = _entry.prepare([str(config), "--output", str(tmp_path / "prep_seq")])
    built_ctx = prep_seq.runner.broker.context_builder.build("cons_1")
    assert built_ctx["tag_a"] == "alpha" and built_ctx["tag_b"] == "beta"
    assert isinstance(prep_seq.ctx.coordinator, dict)

    data["global_config"]["run"]["social"] = "alt_slots:hub_social"
    _write_yaml(config, data)
    prep_hub = _entry.prepare([str(config), "--output", str(tmp_path / "prep_hub")])
    assert isinstance(prep_hub.ctx.social, InteractionHub)
    assert prep_hub.runner.broker.context_builder.hub is prep_hub.ctx.social


def test_bridge_unit_chaining_invariant7_and_role_policy():
    graph = SocialGraph(["reg_1", "cons_1", "cons_2", "cons_3"])
    graph.add_edge("cons_1", "cons_2")

    pool = MessagePool(social_graph=graph)
    kg_calls = []

    class _KG:
        def record_executed_action(
            self,
            agent_id,
            agent_role,
            action_name,
            period,
            *,
            number_text="",
            delivery_delay=1,
            visibility="neighbors",
            outcome_text="",
        ):
            kg_calls.append((agent_id, agent_role, action_name, period, visibility, delivery_delay))

    saga = SagaCoordinator()
    saga.register_saga(
        SagaDefinition(
            name="s1",
            steps=[SagaStep(name="only", execute=lambda c: {**c, "done": True}, compensate=lambda c: None)],
        )
    )
    saga_id = saga.start_saga("s1", {}, step=1)

    events = []

    class _Handler(InstitutionalLifecycleHandler):
        def pre_year(self, agent, year, env):
            events.append(("handler_pre", agent.id, year))

        def post_decision(self, agent, decision, year, env):
            events.append(("handler_decision", agent.id, decision, year))

        def post_year(self, agent, year, env):
            events.append(("handler_post", agent.id, year))

    bridge = MultiActorLifecycleBridge(
        handlers={"regulator": _Handler()},
        message_pool=pool,
        saga_coordinator=saga,
        social_kg=_KG(),
    )

    inner_events = []
    hooks = bridge.as_hooks(
        {
            "pre_year": lambda y, env, agents: inner_events.append(("inner_pre", y)),
            "post_step": lambda ag, res: inner_events.append(("inner_step", ag.id)),
            "post_year": lambda y, agents: inner_events.append(("inner_post", y)),
            "after_run": lambda out: inner_events.append(("after", out)),
        }
    )
    assert set(hooks) == {"pre_year", "post_step", "post_year", "after_run"}

    agents = {
        "reg_1": SimpleNamespace(id="reg_1", agent_type="regulator"),
        "cons_1": SimpleNamespace(id="cons_1", agent_type="consumer"),
        "cons_2": SimpleNamespace(id="cons_2", agent_type="consumer"),
        "cons_3": SimpleNamespace(id="cons_3", agent_type="consumer"),
    }
    env = {}
    hooks["pre_year"](1, env, agents)

    # Rejected proposal where fallback executed -> emits ONLY executed fallback ("hold")
    rejected_with_fallback = SkillBrokerResult(
        outcome=SkillOutcome.REJECTED,
        skill_proposal=SkillProposal(skill_name="forbidden_skill", agent_id="cons_1", reasoning={}),
        approved_skill=ApprovedSkill(
            skill_name="forbidden_skill", agent_id="cons_1", approval_status="REJECTED"
        ),
        execution_result=ExecutionResult(success=True),
        executed_skill="hold",
        executed_via_fallback=True,
    )
    hooks["post_step"](agents["cons_1"], rejected_with_fallback)

    # Aborted step -> emits nothing
    aborted = SkillBrokerResult(
        outcome=SkillOutcome.ABORTED,
        skill_proposal=None,
        approved_skill=None,
        execution_result=None,
    )
    hooks["post_step"](agents["reg_1"], aborted)

    # Approved regulator action -> broadcasts globally
    approved_reg = SkillBrokerResult(
        outcome=SkillOutcome.APPROVED,
        skill_proposal=SkillProposal(skill_name="adjust_incentive", agent_id="reg_1", reasoning={}),
        approved_skill=ApprovedSkill(
            skill_name="adjust_incentive",
            agent_id="reg_1",
            approval_status="APPROVED",
            parameters={"magnitude_pct": 0.4},
        ),
        execution_result=ExecutionResult(success=True),
        executed_skill="adjust_incentive",
    )
    hooks["post_step"](agents["reg_1"], approved_reg)

    hooks["post_year"](1, agents)

    # Neighbor-only scope for consumer cons_1 -> cons_2 received it, cons_3 did not
    cons2_msgs = [m.content for m in pool.get_messages("cons_2")]
    cons3_msgs = [m.content for m in pool.get_messages("cons_3")]
    assert any("cons_1 (consumer) executed hold" in c for c in cons2_msgs)
    assert not any("cons_1" in c for c in cons3_msgs)
    assert not any("forbidden_skill" in c for c in cons2_msgs)

    # Regulator broadcast reached cons_3
    assert any("reg_1 (regulator) executed adjust incentive (number 0.4)" in c for c in cons3_msgs)

    # KG got only executed actions (never aborted, never forbidden_skill)
    assert kg_calls == [
        ("cons_1", "consumer", "hold", 1, "neighbors", 1),
        ("reg_1", "regulator", "adjust_incentive", 1, "global", 1),
    ]
    assert saga.get_status(saga_id) == SagaStatus.COMPLETED
    assert ("inner_pre", 1) in inner_events
    assert ("inner_step", "cons_1") in inner_events
    assert ("inner_post", 1) in inner_events
    assert ("handler_decision", "reg_1", "adjust_incentive", 1) in events


def test_bridge_keep_proposal_preserves_number_and_empty_recipient_types_do_not_broadcast():
    graph = SocialGraph(["prov_1", "cons_1", "cons_2"])
    graph.add_edge("prov_1", "cons_1")
    pool = MessagePool(social_graph=graph)
    kg_calls = []

    class _KG:
        def record_executed_action(
            self,
            agent_id,
            agent_role,
            action_name,
            period,
            *,
            number_text="",
            delivery_delay=1,
            visibility="neighbors",
            outcome_text="",
        ):
            kg_calls.append((agent_id, action_name, number_text))

    bridge = MultiActorLifecycleBridge(
        message_pool=pool,
        social_kg=_KG(),
        role_message_policy={
            "provider": {"scope": "global", "recipient_types": ["regulator"]},
            "consumer": {"scope": "neighbors", "recipient_types": ["regulator"]},
        },
    )
    agents = {
        "prov_1": SimpleNamespace(id="prov_1", agent_type="provider"),
        "cons_1": SimpleNamespace(id="cons_1", agent_type="consumer"),
        "cons_2": SimpleNamespace(id="cons_2", agent_type="consumer"),
    }
    bridge.pre_year(1, {}, agents)

    # Rejected proposal executed as-is (keep_proposal: executed_via_fallback=False)
    # must preserve executed parameters (matching ExperimentRunner._apply_state_changes).
    kept_result = SkillBrokerResult(
        outcome=SkillOutcome.REJECTED,
        skill_proposal=SkillProposal(
            skill_name="expand_capacity", agent_id="prov_1", reasoning={}, magnitude_pct=0.6
        ),
        approved_skill=ApprovedSkill(
            skill_name="expand_capacity",
            agent_id="prov_1",
            approval_status="REJECTED",
            parameters={"magnitude_pct": 0.6},
        ),
        execution_result=ExecutionResult(success=True),
        executed_skill="expand_capacity",
        executed_via_fallback=False,
    )
    bridge.post_step(agents["prov_1"], kept_result)
    assert kg_calls[-1] == ("prov_1", "expand_capacity", "number 0.6")

    # Empty recipient_types match (no regulator in agents) must NOT broadcast to cons_1/cons_2.
    assert pool.get_messages("cons_1") == []
    assert pool.get_messages("cons_2") == []

    # Neighbor filter with empty match must NOT broadcast either.
    bridge.post_step(agents["cons_1"], kept_result)
    assert pool.get_messages("prov_1") == []
    assert pool.get_messages("cons_2") == []
