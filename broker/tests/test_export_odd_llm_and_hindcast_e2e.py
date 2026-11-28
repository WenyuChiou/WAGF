"""End-to-end 3-role historical flood hindcast test + ODD-LLM (Blocks A-E) export verification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from broker.calibration.hindcast_metrics import (
    aggregate_seed_metrics,
    evaluate_hindcast_series,
    split_hindcast_periods,
)
from broker.run import main as broker_run_main
from broker.tools.export_odd_llm import (
    SCHEMA_VERSION,
    build_odd_llm_report,
    main as export_odd_llm_main,
)


def _write_three_role_hindcast_case(case_dir: Path) -> tuple[Path, Path]:
    cfg_dir = case_dir / "config"
    prof_dir = case_dir / "profiles"
    sig_dir = case_dir / "signals"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    prof_dir.mkdir(parents=True, exist_ok=True)
    sig_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "__init__.py").write_text("", encoding="utf-8")

    households_csv = prof_dir / "households.csv"
    households_csv.write_text(
        "hh_id,zone,flood_depth_history,prior_experience\n"
        "H1,Floodplain_West,0.85,Experienced 1998 surge\n"
        "H2,Floodplain_Mid,0.65,Close watch after 1998\n"
        "H3,Floodplain_East,0.40,Edge of 100yr zone\n",
        encoding="utf-8",
    )

    exog_csv = sig_dir / "exogenous_floods.csv"
    exog_csv.write_text(
        "period,subject,predicate,obj,value,text,visibility,target_ids\n"
        "1,gauge_main,peak_stage_m,major_surge,4.9,Gauge reached 4.9m in period 1,global,\n"
        "2,gauge_main,peak_stage_m,moderate_wave,3.1,Gauge peaked at 3.1m in period 2,global,\n"
        "3,gauge_main,peak_stage_m,normal_flow,1.4,Gauge subsided to 1.4m in period 3,global,\n",
        encoding="utf-8",
    )

    (cfg_dir / "skill_registry.yaml").write_text(
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
                    "allow_multiple": True,
                },
                {
                    "skill_id": "elevate_home",
                    "description": "Elevate home above flood level",
                    "eligible_agent_types": ["household"],
                    "allow_multiple": True,
                },
                {
                    "skill_id": "set_subsidy",
                    "description": "Announce municipal mitigation subsidy",
                    "eligible_agent_types": ["government"],
                    "allow_multiple": True,
                },
                {
                    "skill_id": "update_premium",
                    "description": "Update flood risk premium schedule",
                    "eligible_agent_types": ["insurer"],
                    "allow_multiple": True,
                },
            ],
        }),
        encoding="utf-8",
    )

    hh_prompt = (
        "Year {current_year}. Household {agent_id} (zone={zone}).\n"
        "Neighbors & Social Signals:\n{social_gossip}\n"
        "Personal Memory:\n{memory}\n"
        "Available actions:\n{options_text}\n\n{response_format}"
    )
    inst_prompt = (
        "Year {current_year}. Institution {agent_id}.\n"
        "Available actions:\n{options_text}\n\n{response_format}"
    )

    cfg_path = cfg_dir / "agent_types.yaml"
    cfg_path.write_text(
        yaml.safe_dump({
            "shared": {
                "rating_scale": "VL | L | M | H | VH",
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
                "psychological_framework": "utility",
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
                "psychological_framework": "financial",
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
                "psychological_framework": "pmt",
                "prompt_template": hh_prompt,
                "actions": [
                    {"id": "buy_insurance", "description": "Buy flood insurance", "aliases": ["1", "buy_insurance"]},
                    {"id": "elevate_home", "description": "Elevate home", "aliases": ["2", "elevate_home"]},
                    {"id": "do_nothing", "description": "Hold position", "aliases": ["3", "do_nothing"]},
                ],
                "parsing": {
                    "skill_map": {"1": "buy_insurance", "2": "elevate_home", "3": "do_nothing"},
                    "default_skill": "do_nothing",
                },
                "governance": {
                    "default": {
                        "identity_rules": [
                            {
                                "id": "world_precondition_note",
                                "precondition": "untriggered_flag",
                                "blocked_skills": ["elevate_home"],
                                "level": "WARNING",
                                "grounding": "world",
                                "message": "Advisory world check",
                            }
                        ],
                    },
                },
                "memory": {"rejection_line_style": "executed"},
            },
            "global_config": {
                "memory": {
                    "engine_type": "humancentric",
                    "window_size": 5,
                    "top_k_significant": 2,
                    "reflection_slot": "separate",
                },
                "reflection": {
                    "enabled": True,
                    "interval": 1,
                },
                "governance": {
                    "appraisal_freeze": True,
                },
                "audit": {
                    "context_snapshot": True,
                    "initial_proposal_columns": True,
                    "attempt_columns": True,
                    "leakage_patterns": ["FUTURE_2099_POST_FLOOD"],
                },
                "run": {
                    "world": "hindcast_case:build_world",
                    "social": "hindcast_case:build_social",
                    "coordinator": "hindcast_case:build_coordinator",
                    "hooks": "hindcast_case:build_hooks",
                    "mock": "hindcast_case:build_mock",
                    "years": 3,
                    "seed": 17,
                    "phase_order": [["government"], ["insurer"], ["household"]],
                    "population": {
                        "government": {
                            "count": 1,
                            "attributes": {"budget_m": 25.0},
                            "initial_memories": ["Track basin mitigation spending"],
                        },
                        "insurer": {
                            "count": 1,
                            "attributes": {"solvency_ratio": 2.4},
                        },
                        "household": {
                            "table": "profiles/households.csv",
                            "id_col": "hh_id",
                            "columns": {"zone": "zone"},
                            "state_columns": {
                                "risk_score": {"col": "flood_depth_history", "raw_range": [0.0, 1.0]},
                            },
                            "memory_cols": ["prior_experience"],
                            "memory_template": "Household {agent_id} in {zone} registered risk {flood_depth_history}",
                        },
                    },
                },
            },
        }),
        encoding="utf-8",
    )

    (case_dir / "hindcast_case.py").write_text(
        dedent(r'''
            import json
            import re
            from broker.components.coordination.bridge import MultiActorLifecycleBridge
            from broker.components.coordination.messages import MessagePool
            from broker.components.social.fact_schedule import ExogenousFactSchedule
            from broker.components.social.graph import SpatialNeighborhoodGraph
            from broker.components.social.knowledge_graph import AsyncKnowledgeGraph
            from broker.interfaces.skill_types import ExecutionResult
            from broker.utils.llm_utils import LLMStats

            class BasinWorld:
                def __init__(self):
                    self.period = 0

                def advance_year(self):
                    self.period += 1
                    return {"current_year": self.period, "flood_stage_m": 4.9 if self.period == 1 else 2.0}

                def execute_skill(self, approved_skill):
                    return ExecutionResult(success=True, state_changes={})

            def _ensure_bundle(ctx):
                bundle = getattr(ctx, "extra_hindcast", None)
                if bundle is None:
                    positions = {"H1": (0.0, 0.0), "H2": (1.5, 0.0), "H3": (3.0, 0.0)}
                    graph = SpatialNeighborhoodGraph(
                        ["H1", "H2", "H3"], positions=positions, radius=1.5, fallback_k=0
                    )
                    kg = AsyncKnowledgeGraph(social_graph=graph, neighbor_hops=2)
                    schedule = ExogenousFactSchedule.from_csv(ctx.case_dir / "signals" / "exogenous_floods.csv")
                    bundle = {"graph": graph, "kg": kg, "schedule": schedule}
                    ctx.extra_hindcast = bundle
                return bundle

            def build_world(ctx):
                return BasinWorld()

            def build_social(ctx):
                return _ensure_bundle(ctx)["kg"]

            def build_coordinator(ctx):
                kg = _ensure_bundle(ctx)["kg"]
                pool = MessagePool()
                return MultiActorLifecycleBridge(
                    social_kg=kg,
                    message_pool=pool,
                    institutional_roles=("government", "insurer"),
                    default_ttl=2,
                    default_delivery_delay=1,
                )

            def build_hooks(ctx):
                bundle = _ensure_bundle(ctx)
                kg = bundle["kg"]
                graph = bundle["graph"]
                schedule = bundle["schedule"]
                sched_pre = schedule.as_pre_year_hook(kg)

                def on_pre_year(year, env, all_agents):
                    sched_pre(year, env, all_agents)

                def on_post_year(year, all_agents):
                    if year == 2:
                        # Buyout exit at end of period 2 -> inactive for period 3; must block H1->H2->H3 ghost relay.
                        all_agents["H2"].is_active = False
                        graph.deactivate_agent("H2", period=3)
                        kg.assert_fact(
                            subject="H1",
                            predicate="neighbor_signal",
                            obj="post_exit_shortfall",
                            value=1.0,
                            text="H1 observed period-2 relay signal through H2",
                            author_id="H1",
                            author_role="household",
                            published_period=2,
                            delivery_delay=1,
                            visibility="neighbors",
                        )

                return {"pre_year": on_pre_year, "post_year": on_post_year}

            def build_mock(ctx):
                def _pick(prompt, *needles):
                    for needle in needles:
                        for num, desc in re.findall(r"^\s*(\d+)\.\s*(.+)$", prompt, flags=re.MULTILINE):
                            if needle.lower() in desc.lower():
                                return num
                    raise AssertionError(f"Missing {needles!r} in prompt:\n{prompt}")

                def _reply(choice, reason):
                    return (
                        "<<<DECISION_START>>>"
                        + json.dumps({"decision": choice, "reason": reason})
                        + "<<<DECISION_END>>>",
                        LLMStats(success=True),
                    )

                def respond(prompt):
                    if "Household " in prompt:
                        if "Gauge reached 4.9m" in prompt or "period-2 relay signal" in prompt:
                            return _reply(
                                _pick(prompt, "Elevate home", "Take no protective"),
                                "Responding to hazard memory/signal",
                            )
                        return _reply(
                            _pick(prompt, "Purchase flood insurance", "Buy flood insurance", "Take no protective"),
                            "Routine flood insurance coverage",
                        )
                    if "government_1" in prompt:
                        return _reply(_pick(prompt, "Announce", "Take no protective"), "Subsidy adjustment")
                    if "insurer_1" in prompt:
                        return _reply(_pick(prompt, "Update flood risk", "Take no protective"), "Premium revision")
                    return (
                        "Reflection summary: households adapted across periods without future leakage.",
                        LLMStats(success=True),
                    )

                return {"government": respond, "insurer": respond, "household": respond}
        '''),
        encoding="utf-8",
    )
    return cfg_path, households_csv


def test_three_role_hindcast_pipeline_and_odd_llm_export(tmp_path: Path) -> None:
    case_dir = tmp_path / "hindcast_case"
    out_dir = tmp_path / "run_out"
    cfg_path, households_csv = _write_three_role_hindcast_case(case_dir)
    expected_hh_sha = hashlib.sha256(households_csv.read_bytes()).hexdigest()

    rc = broker_run_main([str(cfg_path), "--output", str(out_dir), "--strict-keys"])
    assert rc == 0

    # Check P0 + P1 + P2 run artifacts
    broker_run = json.loads((out_dir / "broker_run.json").read_text(encoding="utf-8"))
    integrity = json.loads((out_dir / "run_integrity.json").read_text(encoding="utf-8"))
    coord_snap = json.loads((out_dir / "coordination_snapshot.json").read_text(encoding="utf-8"))

    assert broker_run["population"] == {"government": 1, "insurer": 1, "household": 3}
    assert broker_run["population_sources"]["household"]["sha256"] == expected_hh_sha
    assert broker_run["population_sources"]["household"]["rows_loaded"] == 3
    assert integrity["inactive_agents_final"] == ["H2"]
    assert integrity["inactive_agents_final_count"] == 1
    assert integrity["leakage_scan"]["clean"] is True
    assert not (case_dir / "events.jsonl").exists()
    assert not (out_dir / "events.jsonl").exists()
    assert "social_graph" in coord_snap
    assert "coordinator" in coord_snap

    # P0 ghost-relay guard: H3 in year 3 must NOT receive H1's period-2 neighbor relay via exited H2
    hh_traces = []
    for line in (out_dir / "raw" / "household_traces.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if isinstance(rec, dict) and "_metadata" not in rec:
            hh_traces.append(rec)
    h3_year3 = [t for t in hh_traces if t.get("agent_id") == "H3" and t.get("year") == 3]
    assert len(h3_year3) == 1
    assert "period-2 relay signal through H2" not in h3_year3[0]["input"]

    # P2 continuous hindcast evaluation + seed aggregation
    import pandas as pd

    obs_series = [0.20, 0.55, 0.70]
    sim_series = [0.25, 0.50, 0.68]
    series_df = pd.DataFrame({"year": [1999, 2000, 2001], "obs": obs_series, "sim": sim_series})
    cal_df, val_df = split_hindcast_periods(series_df, 2000)
    cal_metrics = evaluate_hindcast_series(cal_df["obs"].tolist(), cal_df["sim"].tolist())
    full_metrics = evaluate_hindcast_series(obs_series, sim_series)
    seed_agg = aggregate_seed_metrics([full_metrics, {"kge": 0.85, "nse": 0.90, "rmse": 0.05, "mae": 0.04, "bias": 0.01}])

    hindcast_path = out_dir / "hindcast_verification.json"
    hindcast_path.write_text(
        json.dumps({
            "metrics": full_metrics,
            "calibration_split": cal_metrics,
            "validation_n": len(val_df),
            "seed_summary": seed_agg,
        }, indent=2),
        encoding="utf-8",
    )

    # Record pre-export hashes to assert read-only safety on run artifacts
    watched_files = [
        out_dir / "broker_run.json",
        out_dir / "run_integrity.json",
        out_dir / "reproducibility_manifest.json",
        out_dir / "memory_log.jsonl",
    ]
    before_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in watched_files}

    # P3: export ODD-LLM bundle via CLI
    assert export_odd_llm_main([str(out_dir)]) == 0
    for p in watched_files:
        assert hashlib.sha256(p.read_bytes()).hexdigest() == before_hashes[p.name]

    odd_json = json.loads((out_dir / "odd_llm.json").read_text(encoding="utf-8"))
    odd_md = (out_dir / "ODD_LLM.md").read_text(encoding="utf-8")

    assert odd_json["schema_version"] == SCHEMA_VERSION
    assert odd_json["run_id"] == broker_run["run_id"]

    block_a = odd_json["block_a_overview_and_entities"]
    assert set(block_a["agent_roles"]) == {"government", "insurer", "household"}
    assert block_a["population_sources"]["household"]["sha256"] == expected_hh_sha
    assert block_a["inactive_agents_final"] == ["H2"]

    block_b = odd_json["block_b_cognitive_and_psychological_design"]
    assert block_b["appraisal_freeze"] is True
    assert block_b["roles"]["government"]["psychological_framework"] == "utility"
    assert block_b["roles"]["insurer"]["psychological_framework"] == "financial"
    assert block_b["roles"]["household"]["psychological_framework"] == "pmt"
    assert block_b["roles"]["household"]["rule_grounding_counts"]["world"] >= 1
    assert block_b["dual_process_memory"]["engine_type"] == "humancentric"
    assert block_b["dual_process_memory"]["appraisal_drift_count"] == 0
    assert block_b["dual_process_memory"]["appraisal_relabeled_count"] == 0
    assert block_b["dual_process_memory"]["memory_writes_by_origin"]["seed"] >= 4
    assert block_b["dual_process_memory"]["reflection_log_rows"] > 0

    block_c = odd_json["block_c_llm_specification_and_prompt_contract"]
    assert block_c["model"] == "mock"
    assert len(block_c["roles"]["household"]["prompt_sha256"]) == 64
    assert "social_gossip" in block_c["roles"]["household"]["prompt_placeholders"]

    block_d = odd_json["block_d_governance_coupling_and_social_transmission"]
    assert block_d["invariant_7_isolation"]["governance_carryover_ok"] is True
    join_keys = block_d["coordination_and_social_kg"]["causal_join_keys"]
    assert join_keys["trace_rows_with_run_id"] > 0
    assert join_keys["memory_rows_with_memory_id"] > 0
    assert join_keys["memory_rows_with_triple_id"] > 0
    assert join_keys["reflection_rows_with_retrieved_memory_ids"] > 0

    block_e = odd_json["block_e_reproducibility_hindcast_and_integrity"]
    assert block_e["seed"] == 17
    assert block_e["integrity_ok"] is True
    assert block_e["leakage_scan"]["clean"] is True
    assert block_e["hindcast_verification"]["metrics"]["kge"] == pytest.approx(full_metrics["kge"])

    assert "## Block A" in odd_md
    assert "## Block B" in odd_md
    assert "## Block C" in odd_md
    assert "## Block D" in odd_md
    assert "## Block E" in odd_md
    assert "## Unobserved Fields" in odd_md


def test_export_odd_llm_sparse_run_and_error_guards(tmp_path: Path) -> None:
    missing_dir = tmp_path / "missing_run"
    assert export_odd_llm_main([str(missing_dir)]) == 2

    sparse_dir = tmp_path / "sparse_run"
    sparse_dir.mkdir()
    (sparse_dir / "broker_run.json").write_text(
        json.dumps({"model": "mock", "seed": 0, "population": {"custom_actor": 2}}),
        encoding="utf-8",
    )
    (sparse_dir / "run_integrity.json").write_text(
        json.dumps({"integrity_ok": False, "leakage_scan": {"clean": False, "flagged_trace_rows": 1}}),
        encoding="utf-8",
    )
    raw_dir = sparse_dir / "raw"
    raw_dir.mkdir()
    (raw_dir / "custom_actor_traces.jsonl").write_text(
        json.dumps({
            "agent_type": "custom_actor",
            "appraisal_drift": "X_LABEL:H>L",
            "appraisal_drifted": True,
            "appraisal_relabeled": True,
        }) + "\n",
        encoding="utf-8",
    )

    report = build_odd_llm_report(sparse_dir)
    # Never fabricates default "pmt" or fake git_commit for missing fields
    assert report["block_b_cognitive_and_psychological_design"]["appraisal_freeze"] is None
    assert "block_b_cognitive_and_psychological_design.appraisal_freeze" in report["unobserved_fields"]
    assert report["block_b_cognitive_and_psychological_design"]["dual_process_memory"]["appraisal_drift_count"] == 1
    assert report["block_b_cognitive_and_psychological_design"]["dual_process_memory"]["appraisal_relabeled_count"] == 1
    assert report["block_b_cognitive_and_psychological_design"]["roles"]["custom_actor"]["psychological_framework"] is None
    assert report["block_c_llm_specification_and_prompt_contract"]["roles"]["custom_actor"]["decider_type"] is None
    assert report["block_e_reproducibility_hindcast_and_integrity"]["seed"] == 0
    assert "block_b_cognitive_and_psychological_design.roles.custom_actor.psychological_framework" in report["unobserved_fields"]
    assert "block_e_reproducibility_hindcast_and_integrity.git_commit" in report["unobserved_fields"]
    assert "block_e_reproducibility_hindcast_and_integrity.hindcast_verification" in report["unobserved_fields"]
    assert report["block_e_reproducibility_hindcast_and_integrity"]["leakage_scan"]["clean"] is False


def test_export_odd_llm_manifest_digest_file_templates_and_resolved_llm_params(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    cfg_dir = case_dir / "config"
    prompts_dir = case_dir / "prompts"
    run_dir = tmp_path / "run_out"
    cfg_dir.mkdir(parents=True)
    prompts_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)

    prompt_file = prompts_dir / "op_prompt.txt"
    prompt_file.write_text("Period {current_year} unit {agent_id} state {level}\n", encoding="utf-8")
    expected_sha = hashlib.sha256(prompt_file.read_bytes()).hexdigest()

    cfg_payload = {
        "operator": {
            "prompt_template_file": "../prompts/op_prompt.txt",
            "llm_params": {"model": "qwen3:8b", "temperature": 0.25},
            "actions": [{"id": "hold", "description": "Hold"}],
        },
        "auditor": {
            "prompt_template": "Audit unit {agent_id} period {current_year}",
            "llm_params": {"temperature": 0.1},
            "actions": [{"id": "pass", "description": "Pass"}],
        },
        "global_config": {
            "llm": {"num_ctx": 4096, "top_p": 0.9},
        },
    }
    cfg_path = cfg_dir / "agent_types.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg_payload), encoding="utf-8")
    # Also simulate config_snapshot.yaml copied into run_dir (different parent dir than config/)
    (run_dir / "config_snapshot.yaml").write_text(yaml.safe_dump(cfg_payload), encoding="utf-8")

    (run_dir / "reproducibility_manifest.json").write_text(
        json.dumps({
            "model": "llama3.2:3b",
            "seed": 42,
            "git_commit": "abc1234",
            "agent_types_config": str(cfg_path),
            "model_digest": "sha256:abc123def456",
            "prompt_template_sha256": {"operator": expected_sha},
            "temperature": 0.25,
            "num_ctx": 8192,
            "llm_params_resolved": {
                "operator": {"model": "qwen3:8b", "temperature": 0.25, "num_ctx": 8192},
            },
        }),
        encoding="utf-8",
    )

    report = build_odd_llm_report(run_dir)
    block_c = report["block_c_llm_specification_and_prompt_contract"]

    assert block_c["model_digest"] == "sha256:abc123def456"
    assert block_c["llm_parameters_source"] == "manifest"
    assert block_c["llm_parameters"]["num_ctx"] == 8192

    op_role = block_c["roles"]["operator"]
    assert op_role["prompt_template_file"] == "../prompts/op_prompt.txt"
    assert op_role["prompt_sha256"] == expected_sha
    assert op_role["prompt_placeholders"] == ["agent_id", "current_year", "level"]
    assert op_role["llm_params"]["model"] == "qwen3:8b"
    assert op_role["llm_params_source"] == "manifest_resolved"
    assert "block_c_llm_specification_and_prompt_contract.roles.operator.prompt_template" not in report["unobserved_fields"]

    aud_role = block_c["roles"]["auditor"]
    assert aud_role["llm_params_source"] == "config_fallback"
    assert aud_role["llm_params"]["model"] == "llama3.2:3b"
    assert aud_role["llm_params"]["temperature"] == pytest.approx(0.1)
    assert aud_role["llm_params"]["num_ctx"] == 4096
