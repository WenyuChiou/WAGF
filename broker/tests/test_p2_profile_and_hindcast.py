"""Tests for PR 4 / P2: TabularProfileLoader, ExogenousFactSchedule, leakage_patterns, and hindcast metrics."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import pytest

from broker.agents import AgentConfig, BaseAgent, Skill
from broker.calibration.benchmark_registry import (
    Benchmark,
    BenchmarkCategory,
    BenchmarkRegistry,
)
from broker.calibration.calibration_protocol import (
    CalibrationConfig,
    CalibrationProtocol,
    CalibrationStage,
    FullConfig,
    PilotConfig,
)
from broker.calibration.hindcast_metrics import (
    aggregate_seed_metrics,
    compute_bias,
    compute_kge,
    compute_mae,
    compute_nse,
    compute_rmse,
    evaluate_hindcast_series,
    split_hindcast_periods,
)
from broker.components.social.fact_schedule import (
    ExogenousFactEntry,
    ExogenousFactSchedule,
)
from broker.components.social.knowledge_graph import AsyncKnowledgeGraph
from broker.core.run_integrity import scan_leakage_patterns
from broker.core.tabular_profile_loader import (
    TabularProfileLoader,
    append_seed_memories,
    apply_agent_attributes,
    read_tabular_dataframe,
)
from broker.run._entry import main as broker_run_main
from broker.tools.validate_prompt import KNOWN_AUDIT_KEYS
from broker.utils.agent_config import AgentTypeConfig


def _write_case_yaml(path: Path, extra_global: str = "", run_extra: str = "") -> None:
    path.write_text(
        f"""shared:
  rating_scale: |
    1=Very Low, 5=Very High

role_a:
  description: Role A agent
  prompt_template: |
    Agent {{agent_id}}
  response_format:
    fields:
      - key: decision
        type: choice
  actions:
    - id: hold
      description: Hold steady
role_b:
  description: Role B agent
  prompt_template: |
    Agent {{agent_id}}
  response_format:
    fields:
      - key: decision
        type: choice
  actions:
    - id: hold
      description: Hold steady
global_config:
  run:
{run_extra}
{extra_global}
""",
        encoding="utf-8",
    )


def _write_skill_registry(path: Path) -> None:
    path.write_text(
        """skills:
  - skill_id: hold
    description: Hold steady
    eligible_agent_types: ["*"]
default_skill: hold
""",
        encoding="utf-8",
    )


class TestTabularProfileLoader:
    """U6 unit tests for domain-agnostic tabular agent loading."""

    def test_load_csv_columns_state_and_memory_template(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "profiles.csv"
        csv_path.write_text(
            "unit_id,region,elevation_m,risk_score,prior_notes\n"
            "res_1,North,12.5,0.4,Experienced event A | Attended briefing\n"
            "res_2,South,8.0,0.8,Newcomer\n",
            encoding="utf-8",
        )
        expected_sha = hashlib.sha256(csv_path.read_bytes()).hexdigest()

        loader = TabularProfileLoader(
            id_col="unit_id",
            columns={"zone": "region", "elevation": "elevation_m"},
            state_columns={"risk": {"col": "risk_score", "raw_range": [0.0, 1.0]}},
            memory_cols=["prior_notes"],
            memory_template="Station {agent_id} located in {zone} at {elevation}m",
        )
        res = loader.load_agents(
            csv_path,
            agent_type="household",
            skills=[Skill(skill_id="hold", description="Hold", affected_param=None, direction="none")],
        )

        assert res.sha256 == expected_sha
        assert res.rows_loaded == 2
        assert list(res.agents.keys()) == ["res_1", "res_2"]

        a1 = res.agents["res_1"]
        assert a1.agent_type == "household"
        assert a1.custom_attributes["zone"] == "North"
        assert a1.fixed_attributes["elevation"] == pytest.approx(12.5)
        assert getattr(a1, "zone") == "North"
        assert a1.dynamic_state["risk"] == pytest.approx(0.4)
        assert a1.config.state_params[0].raw_range == (0.0, 1.0)
        assert len(a1.memory) == 3
        assert a1.memory[0]["metadata"]["origin"] == "seed"
        assert a1.memory[0]["content"] == "Experienced event A"
        assert a1.memory[-1]["content"] == "Station res_1 located in North at 12.5m"

    def test_apply_attributes_and_append_seed_memories_helpers(self) -> None:
        agent = BaseAgent(
            AgentConfig(
                name="u1",
                agent_type="role_a",
                state_params=[],
                objectives=[],
                constraints=[],
                skills=[],
            )
        )
        apply_agent_attributes(agent, {"sector": "East", "id": "ignored_reserved"})
        append_seed_memories(agent, ["First memory", "   ", "Second memory"])
        assert agent.custom_attributes["sector"] == "East"
        assert agent.id == "u1"
        assert [m["content"] for m in agent.memory] == ["First memory", "Second memory"]

    def test_limit_and_error_guards(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "dup.csv"
        csv_path.write_text(
            "unit_id,val\n"
            "a1,1\n"
            "a1,2\n",
            encoding="utf-8",
        )
        loader_lim = TabularProfileLoader(id_col="unit_id")
        res = loader_lim.load_agents(csv_path, agent_type="role_a", limit=1)
        assert list(res.agents.keys()) == ["a1"]

        with pytest.raises(ValueError, match="Duplicate agent_id"):
            loader_lim.load_agents(csv_path, agent_type="role_a")

        with pytest.raises(ValueError, match="missing column"):
            TabularProfileLoader(id_col="missing_col").load_agents(csv_path, agent_type="role_a")

        with pytest.raises(ValueError, match="Unsupported tabular profile format"):
            bad = tmp_path / "bad.json"
            bad.write_text("{}", encoding="utf-8")
            read_tabular_dataframe(bad)

    def test_preserves_numeric_and_zero_padded_identifiers_with_float_columns(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "numeric_ids.csv"
        csv_path.write_text(
            "unit_id,elevation_m\n"
            "00123,12.5\n"
            "00456,8.0\n",
            encoding="utf-8",
        )
        loader = TabularProfileLoader(id_col="unit_id", columns=["elevation_m"])
        res = loader.load_agents(csv_path, agent_type="role_a")
        assert list(res.agents.keys()) == ["00123", "00456"]
        assert res.agents["00123"].custom_attributes["elevation_m"] == pytest.approx(12.5)


class TestDeclarativePopulationRunner:
    """U6 integration tests for declarative run.population specs in broker.run."""

    def test_broker_run_tabular_inline_and_ablation_population(self, tmp_path: Path) -> None:
        case_dir = tmp_path / "case"
        cfg_dir = case_dir / "config"
        prof_dir = case_dir / "profiles"
        out_dir = tmp_path / "out"
        cfg_dir.mkdir(parents=True)
        prof_dir.mkdir(parents=True)

        (prof_dir / "role_a.csv").write_text(
            "pid,district,baseline_index,bg_note\n"
            "alpha_1,East,0.25,Prior event X\n"
            "alpha_2,West,0.75,No prior event\n",
            encoding="utf-8",
        )
        expected_sha = hashlib.sha256((prof_dir / "role_a.csv").read_bytes()).hexdigest()

        _write_skill_registry(cfg_dir / "skill_registry.yaml")
        cfg_path = cfg_dir / "agent_types.yaml"
        _write_case_yaml(
            cfg_path,
            run_extra="""    years: 1
    model: mock
    population:
      role_a:
        table: profiles/role_a.csv
        id_col: pid
        columns:
          - district
        state_columns:
          state_metric:
            col: baseline_index
            raw_range: [0.0, 1.0]
        memory_cols:
          - bg_note
        memory_template: "Unit {agent_id} operates in {district}"
      role_b:
        count: 1
        attributes:
          sector: Central
        initial_memories:
          - "Inline initial note for role_b"
""",
        )

        rc = broker_run_main(
            [
                str(cfg_path),
                "--output",
                str(out_dir),
                "--strict-keys",
            ]
        )
        assert rc == 0

        run_record = json.loads((out_dir / "broker_run.json").read_text(encoding="utf-8"))
        assert run_record["population"] == {"role_a": 2, "role_b": 1}
        assert run_record["agent_count"] == 3
        assert run_record["population_sources"]["role_a"]["table"] == "profiles/role_a.csv"
        assert run_record["population_sources"]["role_a"]["sha256"] == expected_sha
        assert run_record["population_sources"]["role_a"]["rows_loaded"] == 2

        mem_lines = [
            json.loads(line)
            for line in (out_dir / "memory_log.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        seed_lines = [row for row in mem_lines if row.get("origin") == "seed"]
        assert len(seed_lines) >= 5
        assert any("Prior event X" == row.get("content", "") for row in seed_lines)
        assert any("Unit alpha_1 operates in East" in row.get("content", "") for row in seed_lines)
        assert any("Inline initial note for role_b" in row.get("content", "") for row in seed_lines)

    def test_table_inline_attributes_available_and_override_for_memory_template(self, tmp_path: Path) -> None:
        case_dir = tmp_path / "case"
        cfg_dir = case_dir / "config"
        prof_dir = case_dir / "profiles"
        out_dir = tmp_path / "out"
        cfg_dir.mkdir(parents=True)
        prof_dir.mkdir(parents=True)
        (prof_dir / "role_a.csv").write_text(
            "pid,district\n"
            "00123,OldEast\n",
            encoding="utf-8",
        )
        _write_skill_registry(cfg_dir / "skill_registry.yaml")
        cfg_path = cfg_dir / "agent_types.yaml"
        _write_case_yaml(
            cfg_path,
            run_extra="""    years: 1
    model: mock
    population:
      role_a:
        table: profiles/role_a.csv
        id_col: pid
        columns:
          - district
        attributes:
          district: OverrideEast
          sector: CentralHub
        memory_template: "Unit {agent_id} at {sector} in {district}"
""",
        )
        assert broker_run_main([str(cfg_path), "--output", str(out_dir)]) == 0
        mem_lines = [
            json.loads(line)
            for line in (out_dir / "memory_log.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        seed_lines = [row for row in mem_lines if row.get("origin") == "seed"]
        assert any(
            row.get("agent_id") == "00123"
            and row.get("content") == "Unit 00123 at CentralHub in OverrideEast"
            for row in seed_lines
        )

    def test_broker_run_rejects_table_path_traversal_and_bad_specs(self, tmp_path: Path) -> None:
        outside = tmp_path / "secret.csv"
        outside.write_text("agent_id,x\nx1,1\n", encoding="utf-8")

        case_dir = tmp_path / "case"
        cfg_dir = case_dir / "config"
        cfg_dir.mkdir(parents=True)
        _write_skill_registry(cfg_dir / "skill_registry.yaml")
        cfg_path = cfg_dir / "agent_types.yaml"

        _write_case_yaml(
            cfg_path,
            run_extra="""    population:
      role_a:
        table: ../secret.csv
""",
        )
        assert broker_run_main([str(cfg_path), "--output", str(tmp_path / "out1")]) == 2

        _write_case_yaml(
            cfg_path,
            run_extra="""    population:
      role_a:
        count: 2
        attributes:
          - sector: S1
""",
        )
        assert broker_run_main([str(cfg_path), "--output", str(tmp_path / "out2")]) == 2


class TestExogenousFactSchedule:
    """U7 tests for thin ExogenousFactSchedule writing directly to AsyncKnowledgeGraph."""

    def test_csv_yaml_idempotent_apply_and_pre_year_hook(self, tmp_path: Path) -> None:
        entry = ExogenousFactEntry(period=1998, subject="gauge_1", predicate="baseline", obj="normal")
        assert entry.period == 1998

        csv_path = tmp_path / "signals.csv"
        csv_path.write_text(
            "period,subject,predicate,obj,value,text,visibility,target_ids\n"
            "1999,gauge_1,observed_level,alert,4.2,Level hit 4.2m,global,\n"
            "2001,gauge_1,advisory,evacuate,,Advisory issued,direct,a1|a2\n",
            encoding="utf-8",
        )
        sched = ExogenousFactSchedule.from_csv(csv_path)
        assert sched.periods == [1999, 2001]

        kg = AsyncKnowledgeGraph()
        hook = sched.as_pre_year_hook(kg)
        hook(1999, {}, {})
        hook(1999, {}, {})  # Idempotent repeat call must not double-insert
        assert sched.snapshot()["applied_triple_count"] == 1
        assert len(kg.query_visible("a1", current_period=1999)) == 1
        assert not (tmp_path / "events.jsonl").exists()

        hook(2001, {}, {})
        assert sched.snapshot()["applied_triple_count"] == 2
        assert len(kg.query_visible("a1", current_period=2001)) == 2
        assert len(kg.query_visible("a3", current_period=2001)) == 1  # Targeted advisory excluded

    def test_yaml_schedule_loads(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "facts.yaml"
        yaml_path.write_text(
            """facts:
  - period: 3
    subject: basin
    predicate: subsidy_rate
    obj: high
    value: 0.5
""",
            encoding="utf-8",
        )
        sched = ExogenousFactSchedule.from_yaml(yaml_path)
        kg = AsyncKnowledgeGraph()
        added = sched.apply_period(3, kg)
        assert len(added) == 1
        assert added[0].metadata.get("exogenous") is True


class TestLeakagePatternsAudit:
    """U8 tests for opt-in leakage_patterns validation and scanning."""

    def test_known_audit_key_and_invalid_regex_rejected(self, tmp_path: Path) -> None:
        assert "leakage_patterns" in KNOWN_AUDIT_KEYS
        cfg_path = tmp_path / "bad_regex.yaml"
        _write_case_yaml(
            cfg_path,
            extra_global="""  audit:
    leakage_patterns:
      - "[unclosed"
""",
        )
        with pytest.raises(ValueError, match="leakage_patterns"):
            AgentTypeConfig.load(str(cfg_path), force_reload=True)

    def test_scan_leakage_patterns_and_opt_in_default_off(self, tmp_path: Path) -> None:
        assert scan_leakage_patterns(tmp_path, [])["patterns_checked"] == []

        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        (raw_dir / "role_a_traces.jsonl").write_text(
            json.dumps({"raw_output": "Decision cites future 2012_post_event", "skill_proposal": {"reasoning": {}}})
            + "\n"
            + json.dumps({"raw_output": "Decision based on 1998 reading"})
            + "\n",
            encoding="utf-8",
        )
        (tmp_path / "reflection_log.jsonl").write_text(
            json.dumps({"summary": "No leak here"})
            + "\n"
            + json.dumps({"summary": "Mentioned 2012_post_event in summary"})
            + "\n",
            encoding="utf-8",
        )
        report = scan_leakage_patterns(tmp_path, [r"2012_post_event"])
        assert report["flagged_trace_rows"] == 1
        assert report["flagged_reflection_rows"] == 1
        assert report["matches_by_pattern"][r"2012_post_event"] == 2
        assert report["clean"] is False

    def test_experiment_runner_emits_leakage_scan_only_when_configured(self, tmp_path: Path) -> None:
        case_dir = tmp_path / "case"
        cfg_dir = case_dir / "config"
        cfg_dir.mkdir(parents=True)
        _write_skill_registry(cfg_dir / "skill_registry.yaml")

        cfg_no_leak = cfg_dir / "agent_types.yaml"
        _write_case_yaml(
            cfg_no_leak,
            run_extra="""    years: 1
    model: mock
    population:
      role_a: 1
""",
        )
        out_off = tmp_path / "out_off"
        assert broker_run_main([str(cfg_no_leak), "--output", str(out_off)]) == 0
        integrity_off = json.loads((out_off / "run_integrity.json").read_text(encoding="utf-8"))
        assert "leakage_scan" not in integrity_off

        cfg_with_leak = cfg_dir / "agent_types_leak.yaml"
        _write_case_yaml(
            cfg_with_leak,
            run_extra="""    years: 1
    model: mock
    population:
      role_a: 1
""",
            extra_global="""  audit:
    leakage_patterns:
      - "FORBIDDEN_FUTURE_TOKEN"
""",
        )
        out_on = tmp_path / "out_on"
        assert broker_run_main([str(cfg_with_leak), "--output", str(out_on), "--strict-keys"]) == 0
        integrity_on = json.loads((out_on / "run_integrity.json").read_text(encoding="utf-8"))
        assert "leakage_scan" in integrity_on
        assert integrity_on["leakage_scan"]["clean"] is True


class TestHindcastMetricsAndCalibrationProtocol:
    """U9 tests for continuous hindcast verification and multi-seed summaries."""

    def test_metrics_exact_and_edge_cases(self) -> None:
        obs = [1.0, 2.0, 3.0, 4.0]
        assert compute_kge(obs, obs) == pytest.approx(1.0)
        assert compute_nse(obs, obs) == pytest.approx(1.0)
        assert compute_rmse(obs, obs) == pytest.approx(0.0)
        assert compute_mae(obs, obs) == pytest.approx(0.0)
        assert compute_bias(obs, obs) == pytest.approx(0.0)

        sim = [2.0, 3.0, 4.0, 5.0]
        ev = evaluate_hindcast_series(obs, sim)
        assert ev["bias"] == pytest.approx(1.0)
        assert ev["mae"] == pytest.approx(1.0)
        assert ev["rmse"] == pytest.approx(1.0)
        assert ev["nse"] == pytest.approx(1.0 - (4.0 / 5.0))
        assert ev["n"] == pytest.approx(4.0)

        assert np.isnan(compute_kge([2.0, 2.0], [2.0, 2.0]))
        with pytest.raises(ValueError, match="lengths must match"):
            compute_rmse([1.0, 2.0], [1.0])

    def test_aggregate_seed_metrics_and_temporal_split(self) -> None:
        agg = aggregate_seed_metrics([{"kge": 0.4}, {"kge": 0.6}, {"kge": 0.8}])
        assert agg["kge"]["median"] == pytest.approx(0.6)
        assert agg["kge"]["iqr"] == pytest.approx(0.2)
        assert agg["kge"]["mean"] == pytest.approx(0.6)
        assert agg["kge"]["n_seeds"] == pytest.approx(3.0)

        df = pd.DataFrame({"year": [1998, 2000, 2005, 2010], "obs": [1, 2, 3, 4]})
        cal, holdout = split_hindcast_periods(df, 2002)
        assert cal["year"].tolist() == [1998, 2000]
        assert holdout["year"].tolist() == [2005, 2010]

    def test_benchmark_registry_round_digits_preserves_legacy_default(self) -> None:
        reg = BenchmarkRegistry()
        reg.register(
            Benchmark(
                name="Adopt",
                metric="m1",
                rate_low=0.3,
                rate_high=0.7,
                source="Synthetic test benchmark",
                category=BenchmarkCategory.AGGREGATE,
                weight=1.0,
            )
        )
        res_legacy = reg.compare({"m1": 0.555555}, tolerance=0.1)
        res_rounded = reg.compare({"m1": 0.555555}, tolerance=0.1, round_digits=3)
        assert res_legacy.formula_version == "legacy_epi_v1"
        assert res_legacy.comparisons[0].observed == pytest.approx(0.555555)
        assert res_rounded.comparisons[0].observed == 0.556
        assert res_rounded.formula_version.startswith("rounded_epi_r3_")

    def test_calibration_protocol_multi_seed_pilot_and_full_median_iqr(self) -> None:
        assert FullConfig().n_agents == 400
        assert FullConfig().n_years == 13
        assert FullConfig().n_seeds == 10

        seen_seeds: List[int] = []

        def _fake_sim(n_agents: int, n_years: int, seed: int) -> pd.DataFrame:
            seen_seeds.append(seed)
            return pd.DataFrame({"year": [1, 2], "adopt_rate": [0.4, 0.6]})

        def _fake_metrics(df: pd.DataFrame) -> Dict[str, float]:
            return {"adopt": float(df["adopt_rate"].mean())}

        reg = BenchmarkRegistry()
        reg.register(
            Benchmark(
                name="Adopt",
                metric="adopt",
                rate_low=0.3,
                rate_high=0.7,
                source="Synthetic test benchmark",
                category=BenchmarkCategory.AGGREGATE,
                weight=1.0,
            )
        )
        cfg = CalibrationConfig(
            pilot=PilotConfig(n_agents=4, n_years=2, n_seeds=3, epi_threshold=0.0, max_iterations=1),
            full=FullConfig(n_agents=4, n_years=2, n_seeds=3),
            framework="custom_cognitive",
        )
        proto = CalibrationProtocol(config=cfg, registry=reg)
        report = proto.run(
            simulate_fn=_fake_sim,
            compute_metrics_fn=_fake_metrics,
            stages=[CalibrationStage.PILOT, CalibrationStage.FULL],
        )
        # 3 seeds in pilot + 3 seeds in full = 6 calls
        assert len(seen_seeds) == 6
        assert report.pilot is not None
        assert report.full is not None
        assert report.full.summary["median_epi"] == pytest.approx(1.0)
        assert report.full.summary["iqr_epi"] == pytest.approx(0.0)
