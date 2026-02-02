"""
C&V Runner — Three-Level Orchestrator.

Runs all three levels of the Calibration & Validation framework:

    Level 1 (MICRO):     MicroValidator  → CACR, EGS, TCS
    Level 2 (MACRO):     DistributionMatcher → KS, Wasserstein, chi2, PEBA
    Level 3 (COGNITIVE): PsychometricBattery → ICC, Cronbach, Fleiss

The runner can operate in two modes:
    1. Post-hoc mode: Analyze existing simulation trace CSVs (Levels 1-2)
    2. Active mode: Run psychometric probes via LLM (Level 3)

Usage:
    runner = CVRunner(
        trace_path="results/Group_B/Run_1/simulation_log.csv",
        framework="pmt",
    )
    report = runner.run_posthoc()  # Levels 1-2 only (no LLM calls)

Part of SAGE C&V Framework (feature/calibration-validation).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from broker.validators.calibration.micro_validator import (
    MicroValidator,
    MicroReport,
)
from broker.validators.calibration.distribution_matcher import (
    DistributionMatcher,
    MacroReport,
)
from broker.validators.calibration.temporal_coherence import (
    TemporalCoherenceValidator,
    TemporalReport,
)
from broker.validators.calibration.psychometric_battery import (
    PsychometricBattery,
    BatteryReport,
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
    macro: Optional[MacroReport] = None
    temporal: Optional[TemporalReport] = None
    rh_metrics: Dict[str, Any] = field(default_factory=dict)
    cognitive: Optional[BatteryReport] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"metadata": self.metadata}
        if self.micro:
            d["level1_micro"] = self.micro.to_dict()
        if self.temporal:
            d["level1_temporal"] = self.temporal.to_dict()
        if self.rh_metrics:
            d["level1_rh"] = {
                k: v for k, v in self.rh_metrics.items()
                if not isinstance(v, list) or len(v) < 100
            }
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
        if self.rh_metrics:
            s["R_H"] = round(self.rh_metrics.get("rh", 0), 3)
            s["EBE"] = round(self.rh_metrics.get("ebe", 0), 3)
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
        self._battery = PsychometricBattery()

        self._df: Optional[pd.DataFrame] = None

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
    ) -> CVReport:
        """Run post-hoc analysis (Levels 1-2, zero LLM calls).

        Parameters
        ----------
        df : DataFrame, optional
            Override loaded DataFrame.
        levels : list[int], optional
            Which levels to run (default: [1, 2]).

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

        if 1 in run_levels:
            report.micro = self.run_micro(data)
            report.temporal = self.run_temporal(data)
            report.rh_metrics = self.run_rh(data)

        if 2 in run_levels:
            report.macro = self.run_macro(data)

        return report

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
