"""
Empirical Benchmarks for Macro Plausibility Validation.

Compares LLM-ABM aggregate action rates against empirical data from
NFIP, Blue Acres, and flood adaptation literature.

This is a SEPARATE validation layer from BRC (which uses PMT framework
internal concordance). Empirical benchmarks test whether the emergent
aggregate behavior falls within plausible real-world ranges.

Usage:
    from paper3.analysis.empirical_benchmarks import compare_with_benchmarks

    df = load_audit_for_cv("paper3/results/seed_42/")
    report = compare_with_benchmarks(df)
    print(report.to_string())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Empirical benchmark definitions
# ---------------------------------------------------------------------------

@dataclass
class Benchmark:
    """A single empirical benchmark for aggregate behavior."""
    name: str
    metric: str
    rate_low: float
    rate_high: float
    source: str
    description: str = ""


# NJ / US flood adaptation literature benchmarks
FLOOD_BENCHMARKS: List[Benchmark] = [
    Benchmark(
        name="NFIP Insurance Uptake (SFHA)",
        metric="insurance_rate",
        rate_low=0.30,
        rate_high=0.50,
        source="Kousky (2017); FEMA NFIP statistics",
        description="Fraction of households in Special Flood Hazard Areas with active NFIP policies",
    ),
    Benchmark(
        name="Insurance Uptake (All Zones)",
        metric="insurance_rate_all",
        rate_low=0.15,
        rate_high=0.40,
        source="Kousky & Michel-Kerjan (2017); Gallagher (2014)",
        description="Fraction of all households (including moderate risk) with flood insurance",
    ),
    Benchmark(
        name="Elevation Adoption (Cumulative)",
        metric="elevation_rate",
        rate_low=0.03,
        rate_high=0.12,
        source="Haer et al. (2017); de Ruig et al. (2022)",
        description="Cumulative fraction of homeowners who elevate over a ~10yr horizon",
    ),
    Benchmark(
        name="Blue Acres Buyout Participation",
        metric="buyout_rate",
        rate_low=0.02,
        rate_high=0.15,
        source="NJ DEP Blue Acres Program reports; Greer & Brokopp Binder (2017)",
        description="Fraction accepting government buyout post-major-flood (highly variable by event)",
    ),
    Benchmark(
        name="Inaction Rate (Post-Flood)",
        metric="do_nothing_rate_postflood",
        rate_low=0.35,
        rate_high=0.65,
        source="Grothmann & Reusswig (2006); Bubeck et al. (2012)",
        description="Fraction of households taking no protective action after experiencing flooding",
    ),
    Benchmark(
        name="MG-NMG Adaptation Gap",
        metric="mg_adaptation_gap",
        rate_low=0.10,
        rate_high=0.30,
        source="Choi et al. (2024); Collins et al. (2018)",
        description="Difference in adaptation rates between non-marginalized and marginalized groups",
    ),
]


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------

def compute_aggregate_rates(
    df: pd.DataFrame,
    decision_col: str = "yearly_decision",
) -> Dict[str, float]:
    """Compute aggregate action rates from simulation trace.

    Parameters
    ----------
    df : DataFrame
        CVRunner-compatible DataFrame with yearly_decision, elevated,
        insured, mg_status columns.
    decision_col : str
        Column containing action decisions.

    Returns
    -------
    dict
        Aggregate rates keyed by benchmark metric names.
    """
    n_total = df["agent_id"].nunique()
    if n_total == 0:
        return {}

    # Last-year snapshot for cumulative metrics
    last_year = df["year"].max()
    last_df = df[df["year"] == last_year]

    rates: Dict[str, float] = {}

    # Insurance rate (from cumulative insured flag at last year)
    if "insured" in last_df.columns:
        rates["insurance_rate"] = last_df["insured"].mean()
        rates["insurance_rate_all"] = last_df["insured"].mean()

    # Elevation rate (cumulative at last year)
    if "elevated" in last_df.columns:
        owners = last_df[last_df["agent_type"] == "household_owner"]
        if len(owners) > 0:
            rates["elevation_rate"] = owners["elevated"].mean()
        else:
            rates["elevation_rate"] = last_df["elevated"].mean()

    # Buyout rate (cumulative relocated)
    if "relocated" in last_df.columns:
        rates["buyout_rate"] = last_df["relocated"].mean()

    # Do-nothing rate post-flood: fraction of agents who chose do_nothing
    # in years when they experienced flooding (flood_depth > 0)
    if "flood_depth_ft" in df.columns:
        flooded = df[df["flood_depth_ft"] > 0]
        if len(flooded) > 0:
            action = flooded[decision_col].str.lower()
            rates["do_nothing_rate_postflood"] = (action == "do_nothing").mean()
    else:
        # Approximate from overall do_nothing rate (less precise)
        action = df[decision_col].str.lower()
        rates["do_nothing_rate_postflood"] = (action == "do_nothing").mean()

    # MG-NMG adaptation gap
    if "mg_status" in last_df.columns:
        mg = last_df[last_df["mg_status"] == "MG"]
        nmg = last_df[last_df["mg_status"] == "NMG"]

        def _adapted(sub_df: pd.DataFrame) -> float:
            if len(sub_df) == 0:
                return 0.0
            adapted = (
                sub_df["elevated"].astype(bool)
                | sub_df.get("insured", pd.Series(False)).astype(bool)
                | sub_df.get("relocated", pd.Series(False)).astype(bool)
            )
            return adapted.mean()

        mg_rate = _adapted(mg)
        nmg_rate = _adapted(nmg)
        rates["mg_adaptation_gap"] = nmg_rate - mg_rate
        rates["mg_adaptation_rate"] = mg_rate
        rates["nmg_adaptation_rate"] = nmg_rate

    return rates


@dataclass
class BenchmarkComparison:
    """Result of comparing one observed rate against an empirical benchmark."""
    benchmark_name: str
    metric: str
    observed: float
    expected_low: float
    expected_high: float
    within_range: bool
    ratio_to_midpoint: float
    source: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "benchmark": self.benchmark_name,
            "metric": self.metric,
            "observed": round(self.observed, 4),
            "expected_range": f"[{self.expected_low:.2f}, {self.expected_high:.2f}]",
            "within_range": self.within_range,
            "ratio_to_midpoint": round(self.ratio_to_midpoint, 3),
            "source": self.source,
        }


@dataclass
class BenchmarkReport:
    """Complete benchmark comparison report."""
    comparisons: List[BenchmarkComparison] = field(default_factory=list)
    n_within_range: int = 0
    n_total: int = 0
    plausibility_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_benchmarks_evaluated": self.n_total,
            "n_within_range": self.n_within_range,
            "plausibility_score": round(self.plausibility_score, 3),
            "comparisons": [c.to_dict() for c in self.comparisons],
        }

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([c.to_dict() for c in self.comparisons])


def compare_with_benchmarks(
    df: pd.DataFrame,
    benchmarks: Optional[List[Benchmark]] = None,
    decision_col: str = "yearly_decision",
    tolerance: float = 0.5,
) -> BenchmarkReport:
    """Compare simulation output against empirical benchmarks.

    Parameters
    ----------
    df : DataFrame
        CVRunner-compatible simulation trace.
    benchmarks : list of Benchmark, optional
        Benchmarks to use. Default: FLOOD_BENCHMARKS.
    decision_col : str
        Decision column name.
    tolerance : float
        Tolerance factor for "within range" check.
        An observed rate within [low * (1-tol), high * (1+tol)] is acceptable.

    Returns
    -------
    BenchmarkReport
    """
    if benchmarks is None:
        benchmarks = FLOOD_BENCHMARKS

    rates = compute_aggregate_rates(df, decision_col=decision_col)
    report = BenchmarkReport()

    for bm in benchmarks:
        if bm.metric not in rates:
            continue

        observed = rates[bm.metric]
        midpoint = (bm.rate_low + bm.rate_high) / 2
        ratio = observed / midpoint if midpoint > 0 else 0.0

        # Within range check (with tolerance)
        low_bound = bm.rate_low * (1 - tolerance)
        high_bound = bm.rate_high * (1 + tolerance)
        within = low_bound <= observed <= high_bound

        comparison = BenchmarkComparison(
            benchmark_name=bm.name,
            metric=bm.metric,
            observed=observed,
            expected_low=bm.rate_low,
            expected_high=bm.rate_high,
            within_range=within,
            ratio_to_midpoint=ratio,
            source=bm.source,
        )
        report.comparisons.append(comparison)

    report.n_total = len(report.comparisons)
    report.n_within_range = sum(1 for c in report.comparisons if c.within_range)
    report.plausibility_score = (
        report.n_within_range / report.n_total if report.n_total > 0 else 0.0
    )

    return report
