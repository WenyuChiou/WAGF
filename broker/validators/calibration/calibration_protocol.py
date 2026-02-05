"""
Calibration Protocol — Three-Stage Domain-Agnostic Calibration Engine.

Provides a structured protocol for calibrating LLM-driven agent-based
models against empirical data.  Three stages:

    Stage 1 — PILOT: Small-N fast iteration with benchmark comparison.
        Generates AdjustmentRecommendation when metrics are out of range.

    Stage 2 — SENSITIVITY: Directional and swap tests verify the LLM
        responds correctly to stimulus changes.

    Stage 3 — FULL: Multi-seed population-level validation combining
        EPI (benchmark plausibility) with CVRunner post-hoc metrics.

Design principles:

    - **Domain-agnostic**: All calibration logic in broker/; domain
      benchmarks and metric functions provided by callers via callbacks.
    - **Callback-based**: ``simulate_fn``, ``compute_metrics_fn``, and
      ``invoke_llm_fn`` are caller-provided functions.
    - **Human-in-the-loop**: Protocol recommends adjustments but does
      NOT auto-modify prompts or configs.
    - **Integrates with CVRunner**: Extends existing validation pipeline.

Usage::

    from broker.validators.calibration.calibration_protocol import (
        CalibrationProtocol, CalibrationConfig,
    )

    protocol = CalibrationProtocol.from_yaml("configs/calibration.yaml")
    report = protocol.run(
        simulate_fn=my_simulation,
        compute_metrics_fn=compute_domain_metrics,
        invoke_llm_fn=my_llm_invoke,
    )
    report.save_json("calibration_report.json")

Part of SAGE Calibration Protocol.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import pandas as pd

from broker.validators.calibration.benchmark_registry import (
    BenchmarkRegistry,
    BenchmarkReport,
    Benchmark,
)
from broker.validators.calibration.directional_validator import (
    DirectionalValidator,
    DirectionalReport,
    DirectionalTest,
    SwapTest,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Callback protocols (type aliases)
# ---------------------------------------------------------------------------

SimulateFn = Callable[..., pd.DataFrame]
"""
(n_agents: int, n_years: int, seed: int,
 config_overrides: Optional[Dict] = None) -> DataFrame

Caller-provided simulation function.  Returns a trace DataFrame
compatible with CVRunner (agent_id, year, yearly_decision, etc.).
"""

ComputeMetricsFn = Callable[[pd.DataFrame], Dict[str, float]]
"""
(df: DataFrame) -> Dict[str, float]

Caller-provided function that extracts domain metrics from
a simulation trace.  Keys must match benchmark metric names.
"""

InvokeLLMFn = Callable[[str], Tuple[str, bool]]
"""
(prompt: str) -> (raw_output: str, success: bool)

Caller-provided LLM invocation function.
"""


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CalibrationStage(str, Enum):
    """Calibration protocol stages."""
    PILOT = "pilot"
    SENSITIVITY = "sensitivity"
    FULL = "full"


class StageVerdict(str, Enum):
    """Verdict for each calibration stage."""
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


# ---------------------------------------------------------------------------
# Configuration dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PilotConfig:
    """Configuration for Stage 1 pilot calibration."""
    n_agents: int = 25
    n_years: int = 3
    n_seeds: int = 1
    epi_threshold: float = 0.50
    max_iterations: int = 5

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> PilotConfig:
        return cls(
            n_agents=int(d.get("n_agents", 25)),
            n_years=int(d.get("n_years", 3)),
            n_seeds=int(d.get("n_seeds", 1)),
            epi_threshold=float(d.get("epi_threshold", 0.50)),
            max_iterations=int(d.get("max_iterations", 5)),
        )


@dataclass
class SensitivityConfig:
    """Configuration for Stage 2 directional sensitivity."""
    replicates: int = 10
    directional_pass_threshold: float = 0.75
    temperature: float = 0.7
    alpha: float = 0.05

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> SensitivityConfig:
        return cls(
            replicates=int(d.get("replicates", 10)),
            directional_pass_threshold=float(
                d.get("directional_pass_threshold", 0.75)
            ),
            temperature=float(d.get("temperature", 0.7)),
            alpha=float(d.get("alpha", 0.05)),
        )


@dataclass
class FullConfig:
    """Configuration for Stage 3 full validation."""
    n_agents: int = 400
    n_years: int = 13
    n_seeds: int = 10
    epi_threshold: float = 0.60
    cacr_threshold: float = 0.80
    icc_threshold: float = 0.60

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> FullConfig:
        return cls(
            n_agents=int(d.get("n_agents", 400)),
            n_years=int(d.get("n_years", 13)),
            n_seeds=int(d.get("n_seeds", 10)),
            epi_threshold=float(d.get("epi_threshold", 0.60)),
            cacr_threshold=float(d.get("cacr_threshold", 0.80)),
            icc_threshold=float(d.get("icc_threshold", 0.60)),
        )


@dataclass
class CalibrationConfig:
    """Complete calibration protocol configuration."""
    pilot: PilotConfig = field(default_factory=PilotConfig)
    sensitivity: SensitivityConfig = field(default_factory=SensitivityConfig)
    full: FullConfig = field(default_factory=FullConfig)
    decision_col: str = "yearly_decision"
    framework: str = "pmt"
    tolerance: float = 0.3

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> CalibrationConfig:
        """Build from a calibration config dict."""
        return cls(
            pilot=PilotConfig.from_dict(d.get("pilot", {})),
            sensitivity=SensitivityConfig.from_dict(d.get("sensitivity", {})),
            full=FullConfig.from_dict(d.get("full", {})),
            decision_col=d.get("decision_col", "yearly_decision"),
            framework=d.get("framework", "pmt"),
            tolerance=float(d.get("tolerance", 0.3)),
        )

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> CalibrationConfig:
        """Load from YAML file."""
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML required: pip install pyyaml")
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        cal = data.get("calibration", data)
        return cls.from_dict(cal)


# ---------------------------------------------------------------------------
# Adjustment Recommendation
# ---------------------------------------------------------------------------

@dataclass
class AdjustmentRecommendation:
    """Actionable recommendation for prompt/config adjustment.

    Generated when a benchmark is out of range.  Tells the user
    WHAT is wrong, by HOW MUCH, in WHICH direction, and SUGGESTS
    a specific adjustment strategy.
    """
    benchmark_name: str
    metric: str
    observed: float
    expected_low: float
    expected_high: float
    deviation_direction: str  # "too_high" or "too_low"
    deviation_magnitude: float
    suggestion: str
    priority: int = 1  # 1 = highest

    def to_dict(self) -> Dict[str, Any]:
        return {
            "benchmark": self.benchmark_name,
            "metric": self.metric,
            "observed": round(self.observed, 4),
            "expected_range": f"[{self.expected_low:.3f}, {self.expected_high:.3f}]",
            "deviation_direction": self.deviation_direction,
            "deviation_magnitude": round(self.deviation_magnitude, 4),
            "suggestion": self.suggestion,
            "priority": self.priority,
        }


# ---------------------------------------------------------------------------
# Stage-level reports
# ---------------------------------------------------------------------------

@dataclass
class PilotIterationResult:
    """Result of a single pilot iteration."""
    iteration: int
    epi: float
    n_benchmarks_evaluated: int
    n_within_range: int
    adjustments: List[AdjustmentRecommendation] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "epi": round(self.epi, 4),
            "n_benchmarks_evaluated": self.n_benchmarks_evaluated,
            "n_within_range": self.n_within_range,
            "adjustments": [a.to_dict() for a in self.adjustments],
        }


@dataclass
class StageReport:
    """Report for a single calibration stage."""
    stage: CalibrationStage
    verdict: StageVerdict
    summary: Dict[str, Any] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage.value,
            "verdict": self.verdict.value,
            "summary": self.summary,
            "details": self.details,
        }


@dataclass
class CalibrationReport:
    """Complete three-stage calibration report."""
    pilot: Optional[StageReport] = None
    sensitivity: Optional[StageReport] = None
    full: Optional[StageReport] = None
    iterations: List[PilotIterationResult] = field(default_factory=list)
    overall_verdict: StageVerdict = StageVerdict.SKIP
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "overall_verdict": self.overall_verdict.value,
            "metadata": self.metadata,
        }
        if self.pilot:
            d["pilot"] = self.pilot.to_dict()
        if self.sensitivity:
            d["sensitivity"] = self.sensitivity.to_dict()
        if self.full:
            d["full"] = self.full.to_dict()
        if self.iterations:
            d["pilot_iterations"] = [i.to_dict() for i in self.iterations]
        return d

    def save_json(self, path: Union[str, Path]) -> None:
        """Save report as JSON."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)


# ---------------------------------------------------------------------------
# Main Protocol
# ---------------------------------------------------------------------------

class CalibrationProtocol:
    """Three-stage domain-agnostic calibration engine.

    Parameters
    ----------
    config : CalibrationConfig
        Protocol configuration.
    registry : BenchmarkRegistry
        Benchmark definitions for EPI computation.
    directional_validator : DirectionalValidator, optional
        Pre-configured directional validator.  If None, Stage 2 is
        skipped unless ``invoke_llm_fn`` is provided with tests loaded
        from config.
    """

    def __init__(
        self,
        config: CalibrationConfig,
        registry: BenchmarkRegistry,
        directional_validator: Optional[DirectionalValidator] = None,
    ) -> None:
        self._config = config
        self._registry = registry
        self._validator = directional_validator

    @classmethod
    def from_yaml(cls, config_path: Union[str, Path]) -> CalibrationProtocol:
        """Build protocol from a YAML config file.

        The YAML should have a ``calibration`` key containing:
        - ``benchmarks``: list of benchmark definitions
        - ``directional_tests``: list of directional test specs
        - ``swap_tests``: list of swap test specs
        - ``pilot``, ``sensitivity``, ``full``: stage configs
        """
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML required: pip install pyyaml")

        config_path = Path(config_path)
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        cal_data = data.get("calibration", data)
        config = CalibrationConfig.from_dict(cal_data)

        # Build registry
        registry = BenchmarkRegistry()
        for bm in cal_data.get("benchmarks", []):
            registry.register(Benchmark.from_dict(bm))

        # Build directional validator
        validator = DirectionalValidator(alpha=config.sensitivity.alpha)
        for dt in cal_data.get("directional_tests", []):
            validator.add_test(DirectionalTest.from_dict(dt))
        for st in cal_data.get("swap_tests", []):
            validator.add_swap_test(SwapTest.from_dict(st))

        return cls(
            config=config,
            registry=registry,
            directional_validator=validator,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CalibrationProtocol:
        """Build protocol from a pre-parsed config dict."""
        cal_data = data.get("calibration", data)
        config = CalibrationConfig.from_dict(cal_data)

        registry = BenchmarkRegistry()
        for bm in cal_data.get("benchmarks", []):
            registry.register(Benchmark.from_dict(bm))

        validator = DirectionalValidator(alpha=config.sensitivity.alpha)
        for dt in cal_data.get("directional_tests", []):
            validator.add_test(DirectionalTest.from_dict(dt))
        for st in cal_data.get("swap_tests", []):
            validator.add_swap_test(SwapTest.from_dict(st))

        return cls(
            config=config,
            registry=registry,
            directional_validator=validator,
        )

    # -------------------------------------------------------------------
    # Main entry point
    # -------------------------------------------------------------------

    def run(
        self,
        simulate_fn: Optional[SimulateFn] = None,
        compute_metrics_fn: Optional[ComputeMetricsFn] = None,
        invoke_llm_fn: Optional[InvokeLLMFn] = None,
        stages: Optional[List[CalibrationStage]] = None,
    ) -> CalibrationReport:
        """Run the calibration protocol.

        Parameters
        ----------
        simulate_fn : callable, optional
            Simulation function (required for pilot and full stages).
        compute_metrics_fn : callable, optional
            Metric extraction function (required for pilot and full).
        invoke_llm_fn : callable, optional
            LLM invocation function (required for sensitivity stage).
        stages : list of CalibrationStage, optional
            Which stages to run.  Default: all applicable.

        Returns
        -------
        CalibrationReport
        """
        if stages is None:
            stages = list(CalibrationStage)

        report = CalibrationReport(
            metadata={
                "framework": self._config.framework,
                "decision_col": self._config.decision_col,
                "tolerance": self._config.tolerance,
                "n_benchmarks": len(self._registry),
            },
        )

        # Stage 1: Pilot
        if CalibrationStage.PILOT in stages:
            if simulate_fn and compute_metrics_fn:
                pilot_report, iterations = self._run_pilot(
                    simulate_fn, compute_metrics_fn,
                )
                report.pilot = pilot_report
                report.iterations = iterations
            else:
                report.pilot = StageReport(
                    stage=CalibrationStage.PILOT,
                    verdict=StageVerdict.SKIP,
                    summary={"reason": "simulate_fn or compute_metrics_fn not provided"},
                )

        # Stage 2: Sensitivity
        if CalibrationStage.SENSITIVITY in stages:
            if invoke_llm_fn and self._validator:
                sens_report = self._run_sensitivity(invoke_llm_fn)
                report.sensitivity = sens_report
            else:
                report.sensitivity = StageReport(
                    stage=CalibrationStage.SENSITIVITY,
                    verdict=StageVerdict.SKIP,
                    summary={"reason": "invoke_llm_fn or directional_validator not provided"},
                )

        # Stage 3: Full
        if CalibrationStage.FULL in stages:
            if simulate_fn and compute_metrics_fn:
                full_report = self._run_full(simulate_fn, compute_metrics_fn)
                report.full = full_report
            else:
                report.full = StageReport(
                    stage=CalibrationStage.FULL,
                    verdict=StageVerdict.SKIP,
                    summary={"reason": "simulate_fn or compute_metrics_fn not provided"},
                )

        # Overall verdict
        verdicts = []
        for stage_report in [report.pilot, report.sensitivity, report.full]:
            if stage_report and stage_report.verdict != StageVerdict.SKIP:
                verdicts.append(stage_report.verdict)

        if not verdicts:
            report.overall_verdict = StageVerdict.SKIP
        elif all(v == StageVerdict.PASS for v in verdicts):
            report.overall_verdict = StageVerdict.PASS
        else:
            report.overall_verdict = StageVerdict.FAIL

        return report

    # -------------------------------------------------------------------
    # Stage implementations
    # -------------------------------------------------------------------

    def _run_pilot(
        self,
        simulate_fn: SimulateFn,
        compute_metrics_fn: ComputeMetricsFn,
    ) -> Tuple[StageReport, List[PilotIterationResult]]:
        """Run Stage 1: Pilot calibration.

        Runs small-N simulations, compares against benchmarks,
        and generates adjustment recommendations.
        """
        cfg = self._config.pilot
        iterations: List[PilotIterationResult] = []
        best_epi = 0.0

        for i in range(1, cfg.max_iterations + 1):
            logger.info("Pilot iteration %d/%d", i, cfg.max_iterations)

            # Run simulation
            df = simulate_fn(
                n_agents=cfg.n_agents,
                n_years=cfg.n_years,
                seed=42 + i,
            )

            # Compute metrics
            observed = compute_metrics_fn(df)

            # Compare against benchmarks
            bench_report = self._registry.compare(
                observed, tolerance=self._config.tolerance,
            )

            # Generate adjustments
            adjustments = self._generate_adjustments(bench_report)

            iteration = PilotIterationResult(
                iteration=i,
                epi=bench_report.plausibility_score,
                n_benchmarks_evaluated=bench_report.n_total,
                n_within_range=bench_report.n_within_range,
                adjustments=adjustments,
            )
            iterations.append(iteration)
            best_epi = max(best_epi, bench_report.plausibility_score)

            logger.info(
                "  EPI = %.3f (%d/%d benchmarks within range)",
                bench_report.plausibility_score,
                bench_report.n_within_range,
                bench_report.n_total,
            )

            # Early termination if threshold met
            if bench_report.plausibility_score >= cfg.epi_threshold:
                logger.info("  Pilot PASS at iteration %d", i)
                break

        passed = best_epi >= cfg.epi_threshold
        return (
            StageReport(
                stage=CalibrationStage.PILOT,
                verdict=StageVerdict.PASS if passed else StageVerdict.FAIL,
                summary={
                    "best_epi": round(best_epi, 4),
                    "epi_threshold": cfg.epi_threshold,
                    "iterations_used": len(iterations),
                    "max_iterations": cfg.max_iterations,
                },
                details={
                    "iterations": [it.to_dict() for it in iterations],
                },
            ),
            iterations,
        )

    def _run_sensitivity(
        self,
        invoke_llm_fn: InvokeLLMFn,
    ) -> StageReport:
        """Run Stage 2: Directional sensitivity validation."""
        cfg = self._config.sensitivity

        if self._validator is None:
            return StageReport(
                stage=CalibrationStage.SENSITIVITY,
                verdict=StageVerdict.SKIP,
                summary={"reason": "No directional validator configured"},
            )

        dir_report = self._validator.run_all(
            invoke_fn=invoke_llm_fn,
            replicates=cfg.replicates,
            alpha=cfg.alpha,
        )

        passed = dir_report.pass_rate >= cfg.directional_pass_threshold

        return StageReport(
            stage=CalibrationStage.SENSITIVITY,
            verdict=StageVerdict.PASS if passed else StageVerdict.FAIL,
            summary={
                "pass_rate": round(dir_report.pass_rate, 4),
                "pass_threshold": cfg.directional_pass_threshold,
                "n_tests": dir_report.n_tests,
                "n_passed": dir_report.n_passed,
            },
            details=dir_report.to_dict(),
        )

    def _run_full(
        self,
        simulate_fn: SimulateFn,
        compute_metrics_fn: ComputeMetricsFn,
    ) -> StageReport:
        """Run Stage 3: Full multi-seed validation."""
        cfg = self._config.full
        seed_epis: List[float] = []
        seed_details: List[Dict[str, Any]] = []

        for seed_idx in range(cfg.n_seeds):
            seed = 42 + seed_idx * 111  # deterministic seed sequence

            logger.info(
                "Full validation seed %d/%d (seed=%d)",
                seed_idx + 1, cfg.n_seeds, seed,
            )

            df = simulate_fn(
                n_agents=cfg.n_agents,
                n_years=cfg.n_years,
                seed=seed,
            )

            observed = compute_metrics_fn(df)
            bench_report = self._registry.compare(
                observed, tolerance=self._config.tolerance,
            )

            seed_epis.append(bench_report.plausibility_score)
            seed_details.append({
                "seed": seed,
                "epi": round(bench_report.plausibility_score, 4),
                "n_within_range": bench_report.n_within_range,
                "n_total": bench_report.n_total,
            })

        # Aggregate
        import numpy as np

        mean_epi = float(np.mean(seed_epis)) if seed_epis else 0.0
        std_epi = float(np.std(seed_epis)) if seed_epis else 0.0
        passed = mean_epi >= cfg.epi_threshold

        return StageReport(
            stage=CalibrationStage.FULL,
            verdict=StageVerdict.PASS if passed else StageVerdict.FAIL,
            summary={
                "mean_epi": round(mean_epi, 4),
                "std_epi": round(std_epi, 4),
                "epi_threshold": cfg.epi_threshold,
                "n_seeds": cfg.n_seeds,
                "all_seeds_pass": all(
                    e >= cfg.epi_threshold for e in seed_epis
                ),
            },
            details={"seeds": seed_details},
        )

    # -------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------

    def _generate_adjustments(
        self, bench_report: BenchmarkReport,
    ) -> List[AdjustmentRecommendation]:
        """Generate actionable adjustment recommendations.

        Examines out-of-range benchmarks and suggests prompt/config
        adjustments sorted by deviation magnitude.
        """
        adjustments: List[AdjustmentRecommendation] = []

        for comp in bench_report.out_of_range:
            if comp.deviation_direction == "too_low":
                suggestion = (
                    f"The simulated {comp.metric} ({comp.observed:.3f}) is below "
                    f"the empirical range [{comp.expected_low:.3f}, "
                    f"{comp.expected_high:.3f}]. Consider: "
                    f"(1) adjusting agent prompts to increase this behavior, "
                    f"(2) reviewing governance rules that may be blocking it, "
                    f"(3) checking if financial costs in prompts are too high."
                )
            elif comp.deviation_direction == "too_high":
                suggestion = (
                    f"The simulated {comp.metric} ({comp.observed:.3f}) exceeds "
                    f"the empirical range [{comp.expected_low:.3f}, "
                    f"{comp.expected_high:.3f}]. Consider: "
                    f"(1) adding constraints or costs that reduce this behavior, "
                    f"(2) reviewing if governance rules are too permissive, "
                    f"(3) checking if prompts over-emphasize this action."
                )
            else:
                continue

            adjustments.append(AdjustmentRecommendation(
                benchmark_name=comp.benchmark_name,
                metric=comp.metric,
                observed=comp.observed,
                expected_low=comp.expected_low,
                expected_high=comp.expected_high,
                deviation_direction=comp.deviation_direction,
                deviation_magnitude=comp.deviation_magnitude,
                suggestion=suggestion,
                priority=1,
            ))

        # Sort by deviation magnitude (largest first)
        adjustments.sort(key=lambda a: a.deviation_magnitude, reverse=True)

        # Assign priorities
        for i, adj in enumerate(adjustments):
            adj.priority = i + 1

        return adjustments
