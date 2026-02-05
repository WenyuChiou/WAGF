"""
C&V Runner — Three-Level Orchestrator.

Runs all three levels of the Calibration & Validation framework:

    Level 1 (MICRO):     MicroValidator  → CACR, EGS, TCS
    Level 2 (MACRO):     DistributionMatcher → KS, Wasserstein, chi2, PEBA
    Level 3 (COGNITIVE): PsychometricBattery → ICC, Cronbach, Fleiss

The runner can operate in two modes:

    1. **Explicit mode** (original API): specify framework, columns, etc.
    2. **Auto-detect mode**: pass ``agent_types.yaml`` config and/or a
       DataFrame and the :class:`ValidationRouter` figures out which
       validators apply.

Usage (explicit)::

    runner = CVRunner(framework="pmt", group="B", start_year=2)
    report = runner.run_posthoc()

Usage (auto-detect)::

    runner = CVRunner.from_config(config=cfg, df=trace_df)
    plan = runner.plan           # inspect what will run
    report = runner.run_posthoc()

Part of SAGE C&V Framework (feature/calibration-validation).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

import pandas as pd

from broker.validators.calibration.micro_validator import (
    MicroValidator,
    MicroReport,
    BRCResult,
)
from broker.validators.calibration.distribution_matcher import (
    DistributionMatcher,
    MacroReport,
)
from broker.validators.calibration.temporal_coherence import (
    ActionStabilityValidator,
    TemporalCoherenceValidator,
    TemporalReport,
)
from broker.validators.calibration.psychometric_battery import (
    PsychometricBattery,
    BatteryReport,
)
from broker.validators.calibration.validation_router import (
    FeatureProfile,
    ValidationPlan,
    ValidationRouter,
    ValidatorType,
)
from broker.validators.calibration.benchmark_registry import (
    BenchmarkRegistry,
    BenchmarkReport,
)
from broker.validators.posthoc.unified_rh import compute_hallucination_rate


# ---------------------------------------------------------------------------
# Unified C&V Report
# ---------------------------------------------------------------------------

@dataclass
class CVReport:
    """Unified three-level C&V report.

    Attributes:
        micro: Level 1 micro validation report.
        macro: Level 2 macro calibration report.
        temporal: Temporal coherence report (part of Level 1).
        rh_metrics: R_H + EBE from unified_rh.py.
        cognitive: Level 3 psychometric battery report.
        metadata: Run metadata (group, model, seed, etc.).
    """
    micro: Optional[MicroReport] = None
    brc: Optional[BRCResult] = None
    macro: Optional[MacroReport] = None
    benchmark: Optional[BenchmarkReport] = None
    temporal: Optional[TemporalReport] = None
    action_stability: Optional[Dict[str, Any]] = None
    rh_metrics: Dict[str, Any] = field(default_factory=dict)
    cognitive: Optional[BatteryReport] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    validation_plan: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"metadata": self.metadata}
        if self.validation_plan:
            d["validation_plan"] = self.validation_plan
        if self.micro:
            d["level1_micro"] = self.micro.to_dict()
        if self.brc:
            d["level2_brc"] = self.brc.to_dict()
        if self.temporal:
            d["level1_temporal"] = self.temporal.to_dict()
        if self.action_stability:
            d["level1_action_stability"] = self.action_stability
        if self.rh_metrics:
            d["level1_rh"] = {
                k: v for k, v in self.rh_metrics.items()
                if not isinstance(v, list) or len(v) < 100
            }
        if self.benchmark:
            d["level2_benchmark"] = self.benchmark.to_dict()
        if self.macro:
            d["level2_macro"] = self.macro.to_dict()
        if self.cognitive:
            d["level3_cognitive"] = self.cognitive.to_dict()
        return d

    def save_json(self, path: str | Path) -> None:
        """Save report as JSON."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)

    @property
    def summary(self) -> Dict[str, Any]:
        """One-line summary metrics for comparison tables."""
        s: Dict[str, Any] = {}
        if self.micro:
            s["CACR"] = round(self.micro.cacr, 3)
            s["EGS"] = round(self.micro.egs, 3)
        if self.temporal:
            s["TCS"] = round(self.temporal.overall_tcs, 3)
        if self.brc:
            s["BRC"] = round(self.brc.brc, 3)
        if self.rh_metrics:
            s["R_H"] = round(self.rh_metrics.get("rh", 0), 3)
            s["EBE"] = round(self.rh_metrics.get("ebe", 0), 3)
        if self.benchmark:
            s["EPI"] = round(self.benchmark.plausibility_score, 3)
        if self.macro:
            s["echo_chamber"] = round(self.macro.echo_chamber_rate, 3)
        if self.cognitive and self.cognitive.overall_tp_icc:
            s["TP_ICC"] = round(self.cognitive.overall_tp_icc.icc_value, 3)
        s.update(self.metadata)
        return s


# ---------------------------------------------------------------------------
# C&V Runner
# ---------------------------------------------------------------------------

class CVRunner:
    """Three-level C&V orchestrator.

    Supports two construction modes:

    **Explicit mode** (original API) — caller specifies framework,
    column names, and group manually::

        runner = CVRunner(framework="pmt", ta_col="threat_appraisal", ...)

    **Auto-detect mode** — pass an ``agent_types.yaml`` config dict and
    the :class:`ValidationRouter` decision tree determines which
    validators are applicable::

        runner = CVRunner.from_config(config=cfg, df=trace_df)

    Parameters
    ----------
    trace_path : str or Path, optional
        Path to simulation_log.csv for post-hoc analysis.
    framework : str
        Psychological framework ("pmt", "utility", "financial").
    ta_col : str
        Threat/primary appraisal column name.
    ca_col : str
        Coping/secondary appraisal column name.
    decision_col : str
        Decision column name.
    reasoning_col : str
        Reasoning text column name.
    group : str
        Experiment group ("A", "B", "C").
    start_year : int
        First year to include in analysis.
    reference_data : dict, optional
        Empirical reference data for macro calibration.
    """

    def __init__(
        self,
        trace_path: Optional[str | Path] = None,
        framework: str = "pmt",
        ta_col: str = "threat_appraisal",
        ca_col: str = "coping_appraisal",
        decision_col: str = "yearly_decision",
        reasoning_col: str = "reasoning",
        group: str = "B",
        start_year: int = 2,
        reference_data: Optional[Dict[str, Any]] = None,
    ):
        self._trace_path = Path(trace_path) if trace_path else None
        self._framework = framework
        self._ta_col = ta_col
        self._ca_col = ca_col
        self._decision_col = decision_col
        self._reasoning_col = reasoning_col
        self._group = group
        self._start_year = start_year
        self._reference_data = reference_data

        # Initialize validators
        self._micro = MicroValidator(
            framework=framework,
            ta_col=ta_col,
            ca_col=ca_col,
            decision_col=decision_col,
        )
        self._macro = DistributionMatcher()
        self._temporal = TemporalCoherenceValidator()
        self._action_stability = ActionStabilityValidator(
            decision_col=decision_col,
        )
        self._battery = PsychometricBattery()

        self._df: Optional[pd.DataFrame] = None
        self._plan: Optional[ValidationPlan] = None
        self._profile: Optional[FeatureProfile] = None
        self._config: Optional[Dict[str, Any]] = None

    @classmethod
    def from_config(
        cls,
        config: Optional[Dict[str, Any]] = None,
        df: Optional[pd.DataFrame] = None,
        trace_path: Optional[str | Path] = None,
        group: str = "B",
        start_year: int = 2,
        reference_data: Optional[Dict[str, Any]] = None,
    ) -> CVRunner:
        """Create a CVRunner using automatic feature detection.

        The :class:`ValidationRouter` inspects the config and data to
        build a :class:`FeatureProfile`, then generates a
        :class:`ValidationPlan` selecting appropriate validators.

        Parameters
        ----------
        config : dict, optional
            Agent type configuration (from ``agent_types.yaml``).
        df : DataFrame, optional
            Pre-loaded simulation trace.
        trace_path : str or Path, optional
            Path to CSV (loaded lazily if df not provided).
        group : str
            Experiment group label.
        start_year : int
            First year to include.
        reference_data : dict, optional
            Empirical reference data for macro calibration.

        Returns
        -------
        CVRunner
        """
        profile = ValidationRouter.detect_features(
            config=config, df=df, reference_data=reference_data,
        )

        # Build runner with detected settings
        runner = cls(
            trace_path=trace_path,
            framework=profile.framework_name or "pmt",
            ta_col=profile.construct_cols.get(
                "TP_LABEL",
                profile.construct_cols.get("WSA_LABEL", "threat_appraisal"),
            ),
            ca_col=profile.construct_cols.get(
                "CP_LABEL",
                profile.construct_cols.get("ACA_LABEL", "coping_appraisal"),
            ),
            decision_col=profile.decision_col or "yearly_decision",
            reasoning_col=profile.reasoning_col or "reasoning",
            group=group,
            start_year=start_year,
            reference_data=reference_data,
        )

        runner._config = config
        runner._profile = profile
        runner._plan = ValidationRouter.plan(profile)
        if df is not None:
            runner._df = df

        return runner

    @property
    def plan(self) -> Optional[ValidationPlan]:
        """The auto-detected validation plan (None if explicit mode)."""
        return self._plan

    @property
    def profile(self) -> Optional[FeatureProfile]:
        """The detected feature profile (None if explicit mode)."""
        return self._profile

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def load_trace(self, path: Optional[str | Path] = None) -> pd.DataFrame:
        """Load simulation trace CSV.

        Parameters
        ----------
        path : str or Path, optional
            Override trace_path from constructor.

        Returns
        -------
        DataFrame
        """
        p = Path(path) if path else self._trace_path
        if p is None:
            raise ValueError("No trace path specified")
        if not p.exists():
            raise FileNotFoundError(f"Trace file not found: {p}")

        self._df = pd.read_csv(p)
        return self._df

    @property
    def df(self) -> pd.DataFrame:
        """Current loaded DataFrame."""
        if self._df is None:
            self.load_trace()
        return self._df

    # ------------------------------------------------------------------
    # Level 1: MICRO
    # ------------------------------------------------------------------

    def run_micro(self, df: Optional[pd.DataFrame] = None) -> MicroReport:
        """Run Level 1 micro validation (CACR + EGS)."""
        data = df if df is not None else self.df
        return self._micro.compute_full_report(
            data,
            reasoning_col=self._reasoning_col,
            start_year=self._start_year,
        )

    def run_temporal(self, df: Optional[pd.DataFrame] = None) -> TemporalReport:
        """Run temporal coherence analysis (TCS)."""
        data = df if df is not None else self.df
        return self._temporal.compute_tcs(data, start_year=self._start_year)

    def run_rh(self, df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Run unified R_H + EBE computation."""
        data = df if df is not None else self.df
        return compute_hallucination_rate(
            data,
            group=self._group,
            ta_col=self._ta_col,
            ca_col=self._ca_col,
            decision_col=self._decision_col,
            start_year=self._start_year,
        )

    def run_brc(
        self, df: Optional[pd.DataFrame] = None,
    ) -> BRCResult:
        """Run BRC (Behavioral Reference Concordance)."""
        data = df if df is not None else self.df
        return self._micro.compute_brc(
            data, start_year=self._start_year,
        )

    def run_action_stability(
        self, df: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """Run action stability analysis (construct-free temporal)."""
        data = df if df is not None else self.df
        return self._action_stability.compute(
            data, start_year=self._start_year,
        )

    # ------------------------------------------------------------------
    # Level 2: MACRO
    # ------------------------------------------------------------------

    def run_macro(self, df: Optional[pd.DataFrame] = None) -> MacroReport:
        """Run Level 2 macro calibration."""
        data = df if df is not None else self.df
        return self._macro.compute_full_report(
            data,
            reference_data=self._reference_data,
            decision_col=self._decision_col,
        )

    # ------------------------------------------------------------------
    # Combined post-hoc
    # ------------------------------------------------------------------

    def run_posthoc(
        self,
        df: Optional[pd.DataFrame] = None,
        levels: Optional[List[int]] = None,
        benchmark_registry: Optional[BenchmarkRegistry] = None,
        compute_metrics_fn: Optional[Any] = None,
    ) -> CVReport:
        """Run post-hoc analysis (Levels 1-2, zero LLM calls).

        When constructed via :meth:`from_config`, uses the
        :class:`ValidationPlan` to decide which validators to run.
        Otherwise falls back to explicit level selection.

        Parameters
        ----------
        df : DataFrame, optional
            Override loaded DataFrame.
        levels : list[int], optional
            Which levels to run (default: [1, 2]).
        benchmark_registry : BenchmarkRegistry, optional
            When provided, computes EPI by comparing observed metrics
            from ``compute_metrics_fn`` against registered benchmarks.
        compute_metrics_fn : callable, optional
            ``(df: DataFrame) -> Dict[str, float]``.  Required when
            ``benchmark_registry`` is given.

        Returns
        -------
        CVReport
        """
        data = df if df is not None else self.df
        run_levels = set(levels or [1, 2])

        report = CVReport(metadata={
            "group": self._group,
            "framework": self._framework,
            "start_year": self._start_year,
            "n_agents": data["agent_id"].nunique() if "agent_id" in data.columns else 0,
            "n_years": data["year"].nunique() if "year" in data.columns else 0,
        })

        # If auto-detect mode, attach the plan summary
        if self._plan:
            report.validation_plan = self._plan.summary()

        # Use plan-aware routing when available
        if self._plan and 1 in run_levels:
            self._run_level1_planned(data, report)
        elif 1 in run_levels:
            report.micro = self.run_micro(data)
            report.temporal = self.run_temporal(data)
            report.rh_metrics = self.run_rh(data)

        if self._plan and 2 in run_levels:
            self._run_level2_planned(data, report)
        elif 2 in run_levels:
            report.macro = self.run_macro(data)

        # Benchmark comparison (EPI) — when registry and metric fn provided
        if benchmark_registry is not None and compute_metrics_fn is not None:
            try:
                observed = compute_metrics_fn(data)
                report.benchmark = benchmark_registry.compare(observed)
            except (KeyError, ValueError, TypeError) as e:
                logger.debug("Benchmark computation skipped: %s", e)
            except Exception as e:
                logger.warning("Benchmark computation failed: %s", e)

        return report

    def _run_level1_planned(
        self,
        data: pd.DataFrame,
        report: CVReport,
    ) -> None:
        """Execute Level 1 validators according to the plan."""
        if not self._plan:
            return

        planned_types = {v.type for v in self._plan.level1_micro}

        # --- CORE: CACR (M1) ---
        if ValidatorType.CACR in planned_types:
            report.micro = self.run_micro(data)

        # --- CORE: RH (M2) ---
        if ValidatorType.RH in planned_types:
            try:
                report.rh_metrics = self.run_rh(data)
            except (KeyError, ValueError):
                # R_H requires specific columns (elevated, etc.) that
                # may not exist in all datasets
                pass

        # --- OPTIONAL: Temporal diagnostics ---
        if ValidatorType.TCS in planned_types:
            report.temporal = self.run_temporal(data)

        if ValidatorType.ACTION_STABILITY in planned_types:
            report.action_stability = self.run_action_stability(data)

    def _run_level2_planned(
        self,
        data: pd.DataFrame,
        report: CVReport,
    ) -> None:
        """Execute Level 2 validators according to the plan."""
        if not self._plan:
            return

        planned_types = {v.type for v in self._plan.level2_macro}

        # --- CORE: BRC (M3) ---
        if ValidatorType.BRC in planned_types:
            report.brc = self.run_brc(data)

        # --- OPTIONAL: Distribution matching ---
        if ValidatorType.DISTRIBUTION_MATCH in planned_types:
            report.macro = self.run_macro(data)

        # --- OPTIONAL: Benchmark EPI ---
        # Note: BENCHMARK execution in planned mode is handled in
        # run_posthoc() via the benchmark_registry parameter, not here.
        # The plan only flags that benchmarks are available.

    # ------------------------------------------------------------------
    # Batch comparison
    # ------------------------------------------------------------------

    @staticmethod
    def compare_groups(
        reports: Dict[str, CVReport],
    ) -> pd.DataFrame:
        """Compare C&V reports across experiment groups.

        Parameters
        ----------
        reports : dict
            {group_label: CVReport} for each group.

        Returns
        -------
        DataFrame
            Comparison table with one row per group.
        """
        rows = []
        for label, report in reports.items():
            row = report.summary
            row["group_label"] = label
            rows.append(row)

        return pd.DataFrame(rows)
