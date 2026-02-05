"""Tests for CalibrationProtocol — three-stage calibration engine.

Validates:
    - CalibrationConfig creation and loading
    - PilotConfig, SensitivityConfig, FullConfig
    - AdjustmentRecommendation generation
    - Stage 1: Pilot iteration with mock simulate_fn
    - Stage 2: Sensitivity with mock invoke_fn
    - Stage 3: Full multi-seed validation
    - Overall verdict logic
    - Stage skipping when callbacks not provided
    - Report serialization
    - from_yaml / from_dict construction
"""

import json
import pytest
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

from broker.validators.calibration.calibration_protocol import (
    AdjustmentRecommendation,
    CalibrationConfig,
    CalibrationProtocol,
    CalibrationReport,
    CalibrationStage,
    FullConfig,
    PilotConfig,
    PilotIterationResult,
    SensitivityConfig,
    StageReport,
    StageVerdict,
)
from broker.validators.calibration.benchmark_registry import (
    Benchmark,
    BenchmarkCategory,
    BenchmarkRegistry,
)
from broker.validators.calibration.directional_validator import (
    DirectionalTest,
    DirectionalValidator,
    SwapTest,
)


# ---------------------------------------------------------------------------
# Mock simulation and metric functions
# ---------------------------------------------------------------------------

def mock_simulate_fn(
    n_agents: int = 25,
    n_years: int = 3,
    seed: int = 42,
    config_overrides: Optional[Dict] = None,
) -> pd.DataFrame:
    """Generate a mock simulation trace DataFrame."""
    rng = np.random.RandomState(seed)
    rows = []
    for year in range(1, n_years + 1):
        for agent_id in range(n_agents):
            action = rng.choice(
                ["buy_insurance", "elevate_house", "do_nothing", "buyout_program"],
                p=[0.35, 0.08, 0.50, 0.07],
            )
            rows.append({
                "agent_id": f"a_{agent_id:03d}",
                "year": year,
                "yearly_decision": action,
                "insured": action == "buy_insurance",
                "elevated": action == "elevate_house",
                "relocated": action == "buyout_program",
                "mg_status": "MG" if agent_id < n_agents // 2 else "NMG",
                "agent_type": "household_owner",
            })
    return pd.DataFrame(rows)


def mock_compute_metrics(df: pd.DataFrame) -> Dict[str, float]:
    """Compute mock metrics from simulation trace."""
    last_year = df["year"].max()
    last_df = df[df["year"] == last_year]
    n = len(last_df)
    if n == 0:
        return {}

    rates = {}
    rates["insurance_rate"] = last_df["insured"].mean()
    rates["elevation_rate"] = last_df["elevated"].mean()
    rates["do_nothing_rate_postflood"] = (
        (df["yearly_decision"] == "do_nothing").mean()
    )
    rates["buyout_rate"] = last_df["relocated"].mean()

    mg = last_df[last_df["mg_status"] == "MG"]
    nmg = last_df[last_df["mg_status"] == "NMG"]
    mg_adopted = (
        mg["insured"].astype(bool) | mg["elevated"].astype(bool)
    ).mean() if len(mg) > 0 else 0
    nmg_adopted = (
        nmg["insured"].astype(bool) | nmg["elevated"].astype(bool)
    ).mean() if len(nmg) > 0 else 0
    rates["mg_adaptation_gap"] = nmg_adopted - mg_adopted

    return rates


def mock_compute_metrics_perfect(df: pd.DataFrame) -> Dict[str, float]:
    """Return metrics that perfectly match all benchmarks."""
    return {
        "insurance_rate": 0.40,
        "elevation_rate": 0.07,
        "do_nothing_rate_postflood": 0.50,
        "mg_adaptation_gap": 0.20,
    }


def mock_invoke_llm(prompt: str) -> Tuple[str, bool]:
    """Mock LLM invoke for sensitivity tests."""
    # Return different responses based on prompt content
    if "6.0 ft" in prompt or "severe" in prompt:
        return json.dumps({"TP_LABEL": "VH", "decision": "buy_insurance"}), True
    elif "0.5 ft" in prompt or "minor" in prompt:
        return json.dumps({"TP_LABEL": "L", "decision": "do_nothing"}), True
    return json.dumps({"TP_LABEL": "M", "decision": "do_nothing"}), True


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_benchmarks():
    return [
        Benchmark(
            name="Insurance Uptake",
            metric="insurance_rate",
            rate_low=0.30,
            rate_high=0.50,
            source="Kousky (2017)",
        ),
        Benchmark(
            name="Elevation Rate",
            metric="elevation_rate",
            rate_low=0.03,
            rate_high=0.12,
            source="Haer et al. (2017)",
        ),
        Benchmark(
            name="Post-Flood Inaction",
            metric="do_nothing_rate_postflood",
            rate_low=0.35,
            rate_high=0.65,
            source="Grothmann (2006)",
            category=BenchmarkCategory.CONDITIONAL,
        ),
        Benchmark(
            name="MG-NMG Gap",
            metric="mg_adaptation_gap",
            rate_low=0.10,
            rate_high=0.30,
            source="Choi (2024)",
            category=BenchmarkCategory.DEMOGRAPHIC,
        ),
    ]


@pytest.fixture
def registry(sample_benchmarks):
    return BenchmarkRegistry(benchmarks=sample_benchmarks)


@pytest.fixture
def directional_tests():
    return [
        DirectionalTest(
            name="depth_tp",
            stimulus_field="depth",
            stimulus_values={"low": "0.5 ft minor", "high": "6.0 ft severe"},
            expected_response_field="TP_LABEL",
            expected_direction="increase",
            ordinal_map={"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5},
        ),
    ]


@pytest.fixture
def default_config():
    return CalibrationConfig(
        pilot=PilotConfig(n_agents=10, n_years=2, max_iterations=2),
        sensitivity=SensitivityConfig(replicates=5),
        full=FullConfig(n_agents=10, n_years=2, n_seeds=2),
    )


@pytest.fixture
def protocol(default_config, registry, directional_tests):
    validator = DirectionalValidator()
    validator.add_tests(directional_tests)
    validator.register_prompt_builder(
        lambda ctx, stim: f"Rate threat for: {stim}"
    )
    validator.register_parse_fn(
        lambda raw: json.loads(raw)
    )
    return CalibrationProtocol(
        config=default_config,
        registry=registry,
        directional_validator=validator,
    )


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class TestConfiguration:
    def test_pilot_config_defaults(self):
        cfg = PilotConfig()
        assert cfg.n_agents == 25
        assert cfg.epi_threshold == 0.50

    def test_pilot_config_from_dict(self):
        cfg = PilotConfig.from_dict({"n_agents": 50, "epi_threshold": 0.60})
        assert cfg.n_agents == 50
        assert cfg.epi_threshold == 0.60

    def test_sensitivity_config_defaults(self):
        cfg = SensitivityConfig()
        assert cfg.replicates == 10
        assert cfg.alpha == 0.05

    def test_full_config_defaults(self):
        cfg = FullConfig()
        assert cfg.n_agents == 400
        assert cfg.n_seeds == 10

    def test_calibration_config_from_dict(self):
        d = {
            "pilot": {"n_agents": 30},
            "sensitivity": {"replicates": 20},
            "full": {"n_seeds": 5},
            "framework": "utility",
            "tolerance": 0.2,
        }
        cfg = CalibrationConfig.from_dict(d)
        assert cfg.pilot.n_agents == 30
        assert cfg.sensitivity.replicates == 20
        assert cfg.full.n_seeds == 5
        assert cfg.framework == "utility"
        assert cfg.tolerance == 0.2

    def test_calibration_config_from_yaml(self, tmp_path):
        yaml_content = """
calibration:
  framework: pmt
  tolerance: 0.3
  pilot:
    n_agents: 25
    epi_threshold: 0.50
  sensitivity:
    replicates: 10
  full:
    n_agents: 400
    n_seeds: 10
"""
        yaml_path = tmp_path / "cal.yaml"
        yaml_path.write_text(yaml_content)

        cfg = CalibrationConfig.from_yaml(yaml_path)
        assert cfg.framework == "pmt"
        assert cfg.pilot.n_agents == 25
        assert cfg.full.n_seeds == 10


# ---------------------------------------------------------------------------
# Adjustment Recommendations
# ---------------------------------------------------------------------------

class TestAdjustmentRecommendation:
    def test_to_dict(self):
        adj = AdjustmentRecommendation(
            benchmark_name="Insurance",
            metric="insurance_rate",
            observed=0.10,
            expected_low=0.30,
            expected_high=0.50,
            deviation_direction="too_low",
            deviation_magnitude=0.11,
            suggestion="Increase insurance in prompts",
            priority=1,
        )
        d = adj.to_dict()
        assert d["deviation_direction"] == "too_low"
        assert d["priority"] == 1


# ---------------------------------------------------------------------------
# Stage 1: Pilot
# ---------------------------------------------------------------------------

class TestPilotStage:
    def test_pilot_passes_with_good_metrics(self, registry):
        """Pilot passes when metrics match benchmarks."""
        config = CalibrationConfig(
            pilot=PilotConfig(n_agents=10, n_years=2, max_iterations=3),
        )
        protocol = CalibrationProtocol(config=config, registry=registry)

        report = protocol.run(
            simulate_fn=mock_simulate_fn,
            compute_metrics_fn=mock_compute_metrics_perfect,
            stages=[CalibrationStage.PILOT],
        )

        assert report.pilot is not None
        assert report.pilot.verdict == StageVerdict.PASS
        assert report.pilot.summary["best_epi"] == pytest.approx(1.0)

    def test_pilot_generates_adjustments(self, registry):
        """Pilot generates adjustments when metrics are out of range."""
        # Use a registry with a benchmark that won't match
        tight_reg = BenchmarkRegistry(benchmarks=[
            Benchmark(
                name="Impossible",
                metric="insurance_rate",
                rate_low=0.95,
                rate_high=0.99,
                source="",
            ),
        ])
        config = CalibrationConfig(
            pilot=PilotConfig(n_agents=10, n_years=2, max_iterations=1),
        )
        protocol = CalibrationProtocol(config=config, registry=tight_reg)

        report = protocol.run(
            simulate_fn=mock_simulate_fn,
            compute_metrics_fn=mock_compute_metrics,
            stages=[CalibrationStage.PILOT],
        )

        assert report.pilot.verdict == StageVerdict.FAIL
        # Should have adjustment recommendations
        assert len(report.iterations) > 0
        assert len(report.iterations[0].adjustments) > 0

    def test_pilot_early_termination(self, registry):
        """Pilot stops early when EPI threshold met."""
        config = CalibrationConfig(
            pilot=PilotConfig(
                n_agents=10, n_years=2,
                max_iterations=5, epi_threshold=0.50,
            ),
        )
        protocol = CalibrationProtocol(config=config, registry=registry)

        report = protocol.run(
            simulate_fn=mock_simulate_fn,
            compute_metrics_fn=mock_compute_metrics_perfect,
            stages=[CalibrationStage.PILOT],
        )

        # Should stop at iteration 1 since metrics are perfect
        assert report.pilot.summary["iterations_used"] == 1


# ---------------------------------------------------------------------------
# Stage 2: Sensitivity
# ---------------------------------------------------------------------------

class TestSensitivityStage:
    def test_sensitivity_with_mock_llm(self, protocol):
        """Sensitivity test with mock LLM that responds correctly."""
        report = protocol.run(
            invoke_llm_fn=mock_invoke_llm,
            stages=[CalibrationStage.SENSITIVITY],
        )

        assert report.sensitivity is not None
        assert report.sensitivity.verdict in (
            StageVerdict.PASS, StageVerdict.FAIL
        )
        assert "pass_rate" in report.sensitivity.summary

    def test_sensitivity_skipped_without_llm(self, registry):
        """Sensitivity is skipped when no LLM function provided."""
        config = CalibrationConfig()
        protocol = CalibrationProtocol(config=config, registry=registry)

        report = protocol.run(
            simulate_fn=mock_simulate_fn,
            compute_metrics_fn=mock_compute_metrics,
            stages=[CalibrationStage.SENSITIVITY],
        )

        assert report.sensitivity.verdict == StageVerdict.SKIP


# ---------------------------------------------------------------------------
# Stage 3: Full
# ---------------------------------------------------------------------------

class TestFullStage:
    def test_full_validation_passes(self, registry):
        """Full validation passes with perfect metrics."""
        config = CalibrationConfig(
            full=FullConfig(n_agents=10, n_years=2, n_seeds=3),
        )
        protocol = CalibrationProtocol(config=config, registry=registry)

        report = protocol.run(
            simulate_fn=mock_simulate_fn,
            compute_metrics_fn=mock_compute_metrics_perfect,
            stages=[CalibrationStage.FULL],
        )

        assert report.full is not None
        assert report.full.verdict == StageVerdict.PASS
        assert report.full.summary["mean_epi"] == pytest.approx(1.0)
        assert report.full.summary["n_seeds"] == 3

    def test_full_validation_fails(self, registry):
        """Full validation fails with impossible benchmarks."""
        tight_reg = BenchmarkRegistry(benchmarks=[
            Benchmark(
                name="Impossible",
                metric="insurance_rate",
                rate_low=0.99,
                rate_high=1.00,
                source="",
            ),
        ])
        config = CalibrationConfig(
            full=FullConfig(n_agents=10, n_years=2, n_seeds=2),
        )
        protocol = CalibrationProtocol(config=config, registry=tight_reg)

        report = protocol.run(
            simulate_fn=mock_simulate_fn,
            compute_metrics_fn=mock_compute_metrics,
            stages=[CalibrationStage.FULL],
        )

        assert report.full.verdict == StageVerdict.FAIL

    def test_full_skipped_without_simulate(self, registry):
        config = CalibrationConfig()
        protocol = CalibrationProtocol(config=config, registry=registry)

        report = protocol.run(stages=[CalibrationStage.FULL])
        assert report.full.verdict == StageVerdict.SKIP


# ---------------------------------------------------------------------------
# Overall verdict
# ---------------------------------------------------------------------------

class TestOverallVerdict:
    def test_all_pass(self, protocol):
        report = protocol.run(
            simulate_fn=mock_simulate_fn,
            compute_metrics_fn=mock_compute_metrics_perfect,
            invoke_llm_fn=mock_invoke_llm,
        )
        # All stages ran — overall depends on actual results
        assert report.overall_verdict in (
            StageVerdict.PASS, StageVerdict.FAIL
        )

    def test_all_skip(self, registry):
        config = CalibrationConfig()
        protocol = CalibrationProtocol(config=config, registry=registry)

        report = protocol.run()  # no callbacks
        assert report.overall_verdict == StageVerdict.SKIP

    def test_partial_stages(self, protocol):
        """Run only pilot — overall follows pilot verdict."""
        report = protocol.run(
            simulate_fn=mock_simulate_fn,
            compute_metrics_fn=mock_compute_metrics_perfect,
            stages=[CalibrationStage.PILOT],
        )
        # Only pilot ran
        assert report.pilot.verdict == StageVerdict.PASS
        assert report.sensitivity is None
        assert report.full is None
        assert report.overall_verdict == StageVerdict.PASS


# ---------------------------------------------------------------------------
# from_yaml / from_dict
# ---------------------------------------------------------------------------

class TestConstruction:
    def test_from_dict(self):
        data = {
            "calibration": {
                "framework": "pmt",
                "tolerance": 0.3,
                "pilot": {"n_agents": 25},
                "benchmarks": [
                    {
                        "name": "Insurance",
                        "metric": "insurance_rate",
                        "rate_low": 0.30,
                        "rate_high": 0.50,
                        "source": "Test",
                    },
                ],
                "directional_tests": [
                    {
                        "name": "depth_tp",
                        "stimulus_field": "depth",
                        "stimulus_values": {"low": "1ft", "high": "6ft"},
                        "expected_response_field": "TP_LABEL",
                        "expected_direction": "increase",
                        "ordinal_map": {"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5},
                    },
                ],
                "swap_tests": [
                    {
                        "name": "income_swap",
                        "base_persona": {"income": "low"},
                        "swap_fields": {"income": "high"},
                    },
                ],
            },
        }
        protocol = CalibrationProtocol.from_dict(data)
        assert len(protocol._registry) == 1
        assert len(protocol._validator._directional_tests) == 1
        assert len(protocol._validator._swap_tests) == 1

    def test_from_yaml(self, tmp_path):
        yaml_content = """
calibration:
  framework: pmt
  tolerance: 0.3
  pilot:
    n_agents: 25
    epi_threshold: 0.50
  sensitivity:
    replicates: 10
  full:
    n_agents: 100
    n_seeds: 3
  benchmarks:
    - name: Insurance
      metric: insurance_rate
      rate_low: 0.30
      rate_high: 0.50
      source: "Test"
  directional_tests:
    - name: depth_tp
      stimulus_field: depth
      stimulus_values:
        low: "1ft"
        high: "6ft"
      expected_response_field: TP_LABEL
      expected_direction: increase
      ordinal_map:
        VL: 1
        L: 2
        M: 3
        H: 4
        VH: 5
"""
        yaml_path = tmp_path / "calibration.yaml"
        yaml_path.write_text(yaml_content)

        protocol = CalibrationProtocol.from_yaml(yaml_path)
        assert len(protocol._registry) == 1
        assert protocol._config.full.n_agents == 100


# ---------------------------------------------------------------------------
# Report serialization
# ---------------------------------------------------------------------------

class TestReportSerialization:
    def test_report_to_dict(self, protocol):
        report = protocol.run(
            simulate_fn=mock_simulate_fn,
            compute_metrics_fn=mock_compute_metrics_perfect,
            stages=[CalibrationStage.PILOT],
        )
        d = report.to_dict()
        assert "overall_verdict" in d
        assert "pilot" in d
        assert "metadata" in d

    def test_report_save_json(self, protocol, tmp_path):
        report = protocol.run(
            simulate_fn=mock_simulate_fn,
            compute_metrics_fn=mock_compute_metrics_perfect,
            stages=[CalibrationStage.PILOT],
        )
        json_path = tmp_path / "cal_report.json"
        report.save_json(json_path)

        loaded = json.loads(json_path.read_text())
        assert loaded["overall_verdict"] == "pass"
        assert "pilot" in loaded

    def test_pilot_iteration_to_dict(self):
        adj = AdjustmentRecommendation(
            benchmark_name="Test",
            metric="rate",
            observed=0.10,
            expected_low=0.30,
            expected_high=0.50,
            deviation_direction="too_low",
            deviation_magnitude=0.11,
            suggestion="Increase it",
        )
        iteration = PilotIterationResult(
            iteration=1,
            epi=0.50,
            n_benchmarks_evaluated=4,
            n_within_range=2,
            adjustments=[adj],
        )
        d = iteration.to_dict()
        assert d["iteration"] == 1
        assert len(d["adjustments"]) == 1

    def test_stage_report_to_dict(self):
        sr = StageReport(
            stage=CalibrationStage.PILOT,
            verdict=StageVerdict.PASS,
            summary={"epi": 0.80},
        )
        d = sr.to_dict()
        assert d["stage"] == "pilot"
        assert d["verdict"] == "pass"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_registry(self):
        """Protocol with no benchmarks — pilot should still run."""
        config = CalibrationConfig(
            pilot=PilotConfig(n_agents=5, n_years=1, max_iterations=1),
        )
        protocol = CalibrationProtocol(
            config=config,
            registry=BenchmarkRegistry(),
        )

        report = protocol.run(
            simulate_fn=mock_simulate_fn,
            compute_metrics_fn=mock_compute_metrics,
            stages=[CalibrationStage.PILOT],
        )
        # With 0 benchmarks, EPI = 0 → FAIL
        assert report.pilot.verdict == StageVerdict.FAIL

    def test_simulate_fn_returns_empty(self, registry):
        """Simulation returns empty DataFrame."""
        config = CalibrationConfig(
            pilot=PilotConfig(n_agents=0, n_years=0, max_iterations=1),
        )
        protocol = CalibrationProtocol(config=config, registry=registry)

        def empty_sim(**kwargs):
            return pd.DataFrame()

        def empty_metrics(df):
            return {}

        report = protocol.run(
            simulate_fn=empty_sim,
            compute_metrics_fn=empty_metrics,
            stages=[CalibrationStage.PILOT],
        )
        assert report.pilot.verdict == StageVerdict.FAIL
