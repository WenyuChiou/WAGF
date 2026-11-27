"""End-to-end 3-year spatial KG mini-simulation verifying social experience
diffusion, dynamic relocation rewiring, institutional coordination, and Invariant 7.

Scenario run via ``python -m broker.run``:
- Geographic neighbor graph (``SpatialNeighborhoodGraph``):
  H1(0,0) -- H2(1.5,0) -- H3(3,0), plus H4(0,1.5) initially near H1 only,
  and H5(10,1.5) initially isolated.
- Institutional actors: ``gov_1`` (government) and ``ins_1`` (insurer).
- Year 1:
  - H1 proposes a restricted action, gets governance-blocked, retries to ``buy_insurance``.
  - Flood strikes in post_year; H1's insurance payout is insufficient, so the world
    publishes a neighbor-scoped ``claim_shortfall`` triple at period 1 (delay 1).
  - ``gov_1`` publishes a municipal announcement containing ``"proposal to raise the levee"``.
  - ``H4`` and ``H5`` emit pre-move neighbor facts at period 1 (delay 0).
- Year 2:
  - 1-hop neighbor H2 receives ``claim_shortfall`` into prompt & memory (``source="neighbor"``)
    and shifts its decision from ``buy_insurance`` to ``elevate_home``.
  - 2-hop neighbor H3 does NOT yet receive the 2-hop triple (effective arrival = 3).
  - At ``post_year(2)``, H4 relocates to (10.0, 0.0) via ``move("H4", (10.0, 0.0), period=2)``,
    breaking (H1, H4) and creating (H4, H5) with ``edge_start_period = 2``.
- Year 3:
  - 2-hop neighbor H3 receives ``claim_shortfall`` and shifts to ``elevate_home``.
  - Bidirectional pre-move isolation: H4 never sees H5's period-1 fact and H5 never sees
    H4's period-1 fact, while H4 retains pre-relocation memories synced in Year 1–2.
  - Post-move Year-3 facts DO propagate across the new (H4, H5) edge.
  - ``run_integrity.json`` and ``check_run_integrity --strict`` pass cleanly (Invariant 7).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import yaml

from broker.run import main


def _write_mini_case(case_dir: Path) -> Path:
    cfg_dir = case_dir / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "__init__.py").write_text("", encoding="utf-8")
    skill_reg = cfg_dir / "skill_registry.yaml"
    agent_cfg = cfg_dir / "agent_types.yaml"

    skill_reg.write_text(
        yaml.safe_dump({
            "default_skill": "do_nothing",
            "skills": [
                {
                    "skill_id": "do_nothing",
                    "description": "Take no protective action this year",
                    "eligible_agent_types": ["*"],
                },
                {
                    "skill_id": "buy_insurance",
                    "description": "Purchase flood insurance policy",
                    "eligible_agent_types": ["household"],
                },
                {
                    "skill_id": "elevate_home",
                    "description": "Elevate structure above base flood elevation",
                    "eligible_agent_types": ["household"],
                },
                {
                    "skill_id": "restricted_grant",
                    "description": "Emergency grant gated by household eligibility",
                    "eligible_agent_types": ["household"],
                },
                {
                    "skill_id": "set_subsidy",
                    "description": "Announce municipal mitigation policy",
                    "eligible_agent_types": ["government"],
                },
                {
                    "skill_id": "update_premium",
                    "description": "Adjust risk-based insurance pricing",
                    "eligible_agent_types": ["insurer"],
                },
            ],
        }),
        encoding="utf-8",
    )

    household_prompt = (
        "Year {current_year}. Agent {agent_id}.\n"
        "Neighbors & Social Reports:\n{social_gossip}\n"
        "Personal Memory:\n{memory}\n"
        "Available actions\n{options_text}\n\n{response_format}"
    )
    inst_prompt = (
        "Year {current_year}. Institution {agent_id}.\n"
        "Available actions\n{options_text}\n\n{response_format}"
    )

    agent_cfg.write_text(
        yaml.safe_dump({
            "global_config": {
                "memory": {
                    "engine_type": "window",
                    "window_size": 10,
                },
                "reflection": {"enabled": False},
                "run": {
                    "world": "hindcast_mini:build_world",
                    "agents": "hindcast_mini:build_agents",
                    "social": "hindcast_mini:build_social",
                    "hooks": "hindcast_mini:build_hooks",
                    "validators": "hindcast_mini:build_validators",
                    "mock": "hindcast_mini:build_mock",
                    "years": 3,
                    "phase_order": [["government"], ["insurer"], ["household"]],
                },
            },
            "shared": {
                "response_format": {
                    "delimiter_start": "<<<DECISION_START>>>",
                    "delimiter_end": "<<<DECISION_END>>>",
                    "fields": [
                        {"key": "decision", "type": "choice", "required": True},
                        {"key": "reason", "type": "text", "required": False},
                    ],
                },
            },
            "government": {
                "agent_type": "government",
                "psychological_framework": "generic",
                "prompt_template": inst_prompt,
                "actions": [
                    {"id": "set_subsidy", "description": "Announce subsidy", "aliases": ["1", "set_subsidy"]},
                    {"id": "do_nothing", "description": "Hold policy", "aliases": ["2", "do_nothing"]},
                ],
                "parsing": {"skill_map": {"1": "set_subsidy", "2": "do_nothing"}, "default_skill": "do_nothing"},
                "memory": {"rejection_line_style": "executed"},
            },
            "insurer": {
                "agent_type": "insurer",
                "psychological_framework": "generic",
                "prompt_template": inst_prompt,
                "actions": [
                    {"id": "update_premium", "description": "Update premium", "aliases": ["1", "update_premium"]},
                    {"id": "do_nothing", "description": "Hold rate", "aliases": ["2", "do_nothing"]},
                ],
                "parsing": {"skill_map": {"1": "update_premium", "2": "do_nothing"}, "default_skill": "do_nothing"},
                "memory": {"rejection_line_style": "executed"},
            },
            "household": {
                "agent_type": "household",
                "psychological_framework": "generic",
                "prompt_template": household_prompt,
                "actions": [
                    {"id": "restricted_grant", "description": "Claim restricted grant", "aliases": ["1", "restricted_grant"]},
                    {"id": "buy_insurance", "description": "Buy flood insurance", "aliases": ["2", "buy_insurance"]},
                    {"id": "elevate_home", "description": "Elevate home", "aliases": ["3", "elevate_home"]},
                    {"id": "do_nothing", "description": "Wait", "aliases": ["4", "do_nothing"]},
                ],
                "parsing": {
                    "skill_map": {
                        "1": "restricted_grant",
                        "2": "buy_insurance",
                        "3": "elevate_home",
                        "4": "do_nothing",
                    },
                    "default_skill": "do_nothing",
                },
                "memory": {"rejection_line_style": "executed"},
            },
        }),
        encoding="utf-8",
    )

    (case_dir / "hindcast_mini.py").write_text(
        dedent(r'''
            import json
            import re
            from broker.agents import AgentConfig, BaseAgent, Skill
            from broker.components.social.graph import SpatialNeighborhoodGraph
            from broker.components.social.knowledge_graph import AsyncKnowledgeGraph
            from broker.interfaces.skill_types import ExecutionResult, ValidationResult
            from broker.utils.llm_utils import LLMStats

            class MiniWorld:
                def __init__(self):
                    self.period = 0
                    self.relocation_log = []
                    self.decisions = []

                def advance_year(self):
                    self.period += 1
                    return {
                        "current_year": self.period,
                        "flood_depth_ft": 2.5 if self.period == 1 else 0.0,
                    }

                def execute_skill(self, approved_skill):
                    self.decisions.append((self.period, approved_skill.agent_id, approved_skill.skill_name))
                    return ExecutionResult(success=True, state_changes={})

            def _skill(sid):
                return Skill(skill_id=sid, description=sid, affected_param=None, direction="none")

            def build_world(ctx):
                return MiniWorld()

            def build_agents(ctx):
                hh_skills = [_skill("restricted_grant"), _skill("buy_insurance"), _skill("elevate_home"), _skill("do_nothing")]
                agents = {
                    "gov_1": BaseAgent(AgentConfig(
                        name="gov_1", agent_type="government", state_params=[], objectives=[], constraints=[],
                        skills=[_skill("set_subsidy"), _skill("do_nothing")],
                    )),
                    "ins_1": BaseAgent(AgentConfig(
                        name="ins_1", agent_type="insurer", state_params=[], objectives=[], constraints=[],
                        skills=[_skill("update_premium"), _skill("do_nothing")],
                    )),
                }
                for hid in ("H1", "H2", "H3", "H4", "H5"):
                    agents[hid] = BaseAgent(AgentConfig(
                        name=hid, agent_type="household", state_params=[], objectives=[], constraints=[],
                        skills=list(hh_skills),
                    ))
                return agents

            def build_social(ctx):
                positions = {
                    "H1": (0.0, 0.0),
                    "H2": (1.5, 0.0),
                    "H3": (3.0, 0.0),
                    "H4": (0.0, 1.5),
                    "H5": (10.0, 1.5),
                }
                graph = SpatialNeighborhoodGraph(
                    list(positions.keys()), positions=positions, radius=1.5, fallback_k=0,
                )
                kg = AsyncKnowledgeGraph(social_graph=graph, neighbor_hops=2)
                ctx.extra_social = {"graph": graph, "kg": kg}
                return kg

            def build_hooks(ctx):
                def on_post_year(year, all_agents):
                    kg = ctx.extra_social["kg"]
                    graph = ctx.extra_social["graph"]
                    if year == 1:
                        kg.assert_fact(
                            subject="gov_1",
                            predicate="policy_notice",
                            obj="levee_upgrade",
                            text="The city's proposal to raise the levee passed.",
                            author_id="gov_1",
                            author_role="government",
                            published_period=1,
                            delivery_delay=0,
                            visibility="global",
                        )
                        kg.assert_fact(
                            subject="H1",
                            predicate="claim_shortfall",
                            obj="payout_insufficient",
                            value=0.6,
                            text="H1 bought insurance but flood payout fell short of damage.",
                            author_id="H1",
                            author_role="household",
                            published_period=1,
                            delivery_delay=1,
                            visibility="neighbors",
                        )
                        kg.assert_fact(
                            subject="H4",
                            predicate="neighbor_note",
                            obj="pre_move_h4",
                            text="H4 stayed at old block in year 1.",
                            author_id="H4",
                            author_role="household",
                            published_period=1,
                            delivery_delay=0,
                            visibility="neighbors",
                        )
                        kg.assert_fact(
                            subject="H5",
                            predicate="neighbor_note",
                            obj="pre_move_h5",
                            text="H5 stayed at far block in year 1.",
                            author_id="H5",
                            author_role="household",
                            published_period=1,
                            delivery_delay=0,
                            visibility="neighbors",
                        )
                    elif year == 2:
                        move_res = graph.move("H4", (10.0, 0.0), period=2)
                        ctx.world.relocation_log.append(move_res)
                        kg.assert_fact(
                            subject="H4",
                            predicate="relocated_intro",
                            obj="new_block_arrival",
                            text="H4 moved onto the east block in year 3.",
                            author_id="H4",
                            author_role="household",
                            published_period=3,
                            delivery_delay=0,
                            visibility="neighbors",
                        )
                return {"post_year": on_post_year}

            def build_validators(ctx):
                def forbid_restricted_grant(proposal, context, registry):
                    if proposal.skill_name == "restricted_grant":
                        return ValidationResult(
                            valid=False,
                            validator_name="GrantEligibility",
                            errors=["restricted_grant requires verified buyout eligibility"],
                            metadata={"rule_id": "grant_eligibility_rule", "constraint_type": "hard"},
                        )
                    return ValidationResult(valid=True, validator_name="GrantEligibility", errors=[])
                return [forbid_restricted_grant]

            def build_mock(ctx):
                def _pick(prompt, needle):
                    needle_lower = needle.lower()
                    for num, desc in re.findall(r"^\s*(\d+)\.\s*(.+)$", prompt, flags=re.MULTILINE):
                        if needle_lower in desc.lower():
                            return num
                    raise AssertionError(f"Option {needle!r} not found in prompt:\n{prompt}")

                def _reply(choice, reason):
                    return (
                        "<<<DECISION_START>>>"
                        + json.dumps({"decision": choice, "reason": reason})
                        + "<<<DECISION_END>>>",
                        LLMStats(success=True),
                    )

                def respond(prompt):
                    if "grant_eligibility_rule" in prompt or "restricted_grant requires" in prompt:
                        return _reply(
                            _pick(prompt, "Purchase flood insurance"),
                            "Switching to flood insurance after eligibility block",
                        )
                    if "Agent H1." in prompt and "Year 1." in prompt:
                        return _reply(_pick(prompt, "Emergency grant"), "Trying emergency grant first")
                    if ("Agent H2." in prompt or "Agent H3." in prompt) and "payout fell short" in prompt:
                        return _reply(
                            _pick(prompt, "Elevate structure"),
                            "Peer insurance shortfall observed; elevating home",
                        )
                    if "Institution gov_1." in prompt:
                        return _reply(_pick(prompt, "Announce"), "Announce mitigation support")
                    if "Institution ins_1." in prompt:
                        return _reply(_pick(prompt, "Adjust"), "Reprice after hazard year")
                    return _reply(_pick(prompt, "Purchase flood insurance"), "Default insurance purchase")
                return {
                    "government": respond,
                    "insurer": respond,
                    "household": respond,
                }

            def save_summary(out_dir, ctx):
                pass
        '''),
        encoding="utf-8",
    )
    return agent_cfg


def test_e2e_kg_spatial_shortfall_two_hop_relocation_and_i7(tmp_path: Path):
    case_dir = tmp_path / "mini_hindcast"
    config_path = _write_mini_case(case_dir)
    out_dir = tmp_path / "results"

    rc = main([str(config_path), "--model", "mock", "--output", str(out_dir)])
    assert rc == 0

    raw_dir = out_dir / "raw"
    traces = {}
    for trace_path in raw_dir.glob("*_traces.jsonl"):
        for line in trace_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if "_metadata" in rec:
                continue
            traces[(rec["year"], rec["agent_id"])] = rec

    # H1 Year 1 blocked -> retried -> buy_insurance
    assert traces[(1, "H1")]["approved_skill"]["skill_name"] == "buy_insurance"
    assert traces[(1, "H1")]["retry_count"] == 1

    # 1-hop H2 sees shortfall in Year 2 -> switches to elevate_home; Year 1 did not see it
    assert traces[(1, "H2")]["approved_skill"]["skill_name"] == "buy_insurance"
    assert "payout fell short" in traces[(2, "H2")]["input"]
    assert traces[(2, "H2")]["approved_skill"]["skill_name"] == "elevate_home"

    # 2-hop H3: NOT visible in Year 2 (effective delay +1), visible in Year 3 -> switches
    assert "payout fell short" not in traces[(2, "H3")]["input"]
    assert traces[(2, "H3")]["approved_skill"]["skill_name"] == "buy_insurance"
    assert "payout fell short" in traces[(3, "H3")]["input"]
    assert traces[(3, "H3")]["approved_skill"]["skill_name"] == "elevate_home"

    # Bidirectional pre-move isolation between H4 and H5 after Year 2 move:
    assert "pre_move_h5" not in traces[(3, "H4")]["input"] and "far block" not in traces[(3, "H4")]["input"]
    assert "pre_move_h4" not in traces[(3, "H5")]["input"] and "old block" not in traces[(3, "H5")]["input"]
    # Post-move Year-3 neighbor triple DOES cross (H4, H5)
    assert "east block in year 3" in traces[(3, "H5")]["input"]

    # H4 keeps Year 1/2 pre-relocation memories in memory_log.jsonl
    mem_entries = [
        json.loads(line)
        for line in (out_dir / "memory_log.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    h4_pre_move_memories = [
        e for e in mem_entries
        if e["agent_id"] == "H4" and "payout fell short" in e["content"]
    ]
    assert len(h4_pre_move_memories) == 1
    assert h4_pre_move_memories[0]["source"] == "neighbor"
    assert h4_pre_move_memories[0]["emotion"] is None

    # No double-sync per period for any agent
    social_by_agent_period = {}
    for e in mem_entries:
        if e["origin"] == "social":
            key = (e["agent_id"], e["period"], e["content"])
            social_by_agent_period[key] = social_by_agent_period.get(key, 0) + 1
    assert social_by_agent_period and all(cnt == 1 for cnt in social_by_agent_period.values())

    # Invariant 7 strict integrity check passes (even with municipal "proposal to raise the levee")
    integrity = json.loads((out_dir / "run_integrity.json").read_text(encoding="utf-8"))
    assert integrity["integrity_ok"] is True
    assert integrity["governance_carryover"]["ok"] is True

    repo_root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [sys.executable, "-m", "broker.tools.check_run_integrity", "--strict", str(out_dir)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
