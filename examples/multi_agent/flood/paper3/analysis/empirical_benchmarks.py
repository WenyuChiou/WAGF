"""
Empirical Benchmarks for Macro Plausibility Validation.

Compares LLM-ABM aggregate action rates against empirical data from
NFIP, Blue Acres, and flood adaptation literature.

This is a SEPARATE validation layer from BRC (which uses PMT framework
internal concordance). Empirical benchmarks test whether the emergent
aggregate behavior falls within plausible real-world ranges.

Uses the generic :class:`BenchmarkRegistry` from
``broker.validators.calibration.benchmark_registry`` for benchmark
definition, comparison, and EPI computation.  This module provides the
**flood-domain benchmarks** and the **metric computation function**.

Usage:
    from paper3.analysis.empirical_benchmarks import compare_with_benchmarks

    df = load_audit_for_cv("paper3/results/seed_42/")
    report = compare_with_benchmarks(df)
    print(f"EPI = {report.plausibility_score:.3f}")
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from broker.validators.calibration.benchmark_registry import (
    Benchmark,
    BenchmarkCategory,
    BenchmarkComparison,
    BenchmarkRegistry,
    BenchmarkReport,
)


# ---------------------------------------------------------------------------
# Flood-domain empirical benchmark definitions
# ---------------------------------------------------------------------------

FLOOD_BENCHMARKS: List[Benchmark] = [
    Benchmark(
        name="NFIP Insurance Uptake (SFHA)",
        metric="insurance_rate",
        rate_low=0.30,
        rate_high=0.50,
        source="Kousky (2017); FEMA NFIP statistics",
        description="Fraction of households in Special Flood Hazard Areas with active NFIP policies",
        category=BenchmarkCategory.AGGREGATE,
        weight=1.0,
    ),
    Benchmark(
        name="Insurance Uptake (All Zones)",
        metric="insurance_rate_all",
        rate_low=0.15,
        rate_high=0.40,
        source="Kousky & Michel-Kerjan (2017); Gallagher (2014)",
        description="Fraction of all households (including moderate risk) with flood insurance",
        category=BenchmarkCategory.AGGREGATE,
        weight=0.8,
    ),
    Benchmark(
        name="Elevation Adoption (Cumulative)",
        metric="elevation_rate",
        rate_low=0.03,
        rate_high=0.12,
        source="Haer et al. (2017); de Ruig et al. (2022)",
        description="Cumulative fraction of homeowners who elevate over a ~10yr horizon",
        category=BenchmarkCategory.AGGREGATE,
        weight=1.0,
    ),
    Benchmark(
        name="Blue Acres Buyout Participation",
        metric="buyout_rate",
        rate_low=0.02,
        rate_high=0.15,
        source="NJ DEP Blue Acres Program reports; Greer & Brokopp Binder (2017)",
        description="Fraction accepting government buyout post-major-flood (highly variable by event)",
        category=BenchmarkCategory.AGGREGATE,
        weight=0.8,
    ),
    Benchmark(
        name="Inaction Rate (Post-Flood)",
        metric="do_nothing_rate_postflood",
        rate_low=0.35,
        rate_high=0.65,
        source="Grothmann & Reusswig (2006); Brody et al. (2017)",
        description="Fraction of households taking no protective action after experiencing flooding",
        category=BenchmarkCategory.CONDITIONAL,
        weight=1.5,
    ),
    Benchmark(
        name="MG-NMG Adaptation Gap",
        metric="mg_adaptation_gap",
        rate_low=0.10,
        rate_high=0.30,
        source="Choi et al. (2024); Collins et al. (2018)",
        description="Difference in adaptation rates between non-marginalized and marginalized groups",
        category=BenchmarkCategory.DEMOGRAPHIC,
        weight=2.0,
    ),
    Benchmark(
        name="Repetitive Loss Uninsured Rate",
        metric="rl_uninsured_rate",
        rate_low=0.15,
        rate_high=0.40,
        source="FEMA RL statistics; Kousky & Michel-Kerjan (2010)",
        description="Fraction of repetitive-loss properties without active NFIP coverage",
        category=BenchmarkCategory.CONDITIONAL,
        weight=1.0,
    ),
    Benchmark(
        name="Insurance Annual Lapse Rate",
        metric="insurance_lapse_rate",
        rate_low=0.05,
        rate_high=0.15,
        source="Gallagher (2014, AER); Michel-Kerjan et al. (2012)",
        description="Annual rate of NFIP policy non-renewal",
        category=BenchmarkCategory.TEMPORAL,
        weight=1.0,
    ),
]


def _get_flood_registry(
    benchmarks: Optional[List[Benchmark]] = None,
) -> BenchmarkRegistry:
    """Build a BenchmarkRegistry pre-loaded with flood benchmarks."""
    return BenchmarkRegistry(benchmarks=benchmarks or FLOOD_BENCHMARKS)


# ---------------------------------------------------------------------------
# Metric computation (domain-specific)
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

    # Repetitive loss uninsured rate
    # Agents flooded 2+ times who are NOT insured at last year
    if "insured" in last_df.columns and "flood_count" in df.columns:
        last_with_floods = last_df.merge(
            df.groupby("agent_id")["year"].count().rename("obs_count"),
            left_on="agent_id", right_index=True, how="left",
        )
        # Use flood_depth or decision history to count floods
        if "flood_depth_ft" in df.columns:
            flood_counts = df[df["flood_depth_ft"] > 0].groupby("agent_id").size()
            last_with_floods["n_floods"] = last_with_floods["agent_id"].map(flood_counts).fillna(0)
        else:
            last_with_floods["n_floods"] = 0

        rl_agents = last_with_floods[last_with_floods["n_floods"] >= 2]
        if len(rl_agents) > 0:
            rates["rl_uninsured_rate"] = (~rl_agents["insured"].astype(bool)).mean()

    # Insurance lapse rate (annual non-renewal)
    # Count agents who were insured in year N but not in year N+1
    if "insured" in df.columns and df["year"].nunique() > 1:
        years_sorted = sorted(df["year"].unique())
        lapse_events = 0
        insured_years = 0
        for i in range(len(years_sorted) - 1):
            y1 = df[df["year"] == years_sorted[i]]
            y2 = df[df["year"] == years_sorted[i + 1]]
            merged = y1[["agent_id", "insured"]].merge(
                y2[["agent_id", "insured"]], on="agent_id", suffixes=("_prev", "_next"),
            )
            was_insured = merged["insured_prev"].astype(bool)
            now_insured = merged["insured_next"].astype(bool)
            lapse_events += int((was_insured & ~now_insured).sum())
            insured_years += int(was_insured.sum())

        if insured_years > 0:
            rates["insurance_lapse_rate"] = lapse_events / insured_years

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


# ---------------------------------------------------------------------------
# Comparison (delegates to BenchmarkRegistry)
# ---------------------------------------------------------------------------

def compare_with_benchmarks(
    df: pd.DataFrame,
    benchmarks: Optional[List[Benchmark]] = None,
    decision_col: str = "yearly_decision",
    tolerance: float = 0.3,
) -> BenchmarkReport:
    """Compare simulation output against empirical benchmarks.

    Delegates to :class:`BenchmarkRegistry.compare` from the generic
    calibration engine.

    Parameters
    ----------
    df : DataFrame
        CVRunner-compatible simulation trace.
    benchmarks : list of Benchmark, optional
        Benchmarks to use. Default: FLOOD_BENCHMARKS.
    decision_col : str
        Decision column name.
    tolerance : float
        Tolerance factor for "within range" check (default 0.3 = 30%).
        An observed rate within [low * (1-tol), high * (1+tol)] is acceptable.

    Returns
    -------
    BenchmarkReport
    """
    registry = _get_flood_registry(benchmarks)
    rates = compute_aggregate_rates(df, decision_col=decision_col)
    return registry.compare(rates, tolerance=tolerance)


def compute_epi(
    df: pd.DataFrame,
    benchmarks: Optional[List[Benchmark]] = None,
    decision_col: str = "yearly_decision",
    tolerance: float = 0.3,
) -> float:
    """Compute Empirical Plausibility Index (EPI).

    EPI = weighted fraction of evaluated benchmarks where the simulated
    aggregate rate falls within the empirical range (with tolerance).

    Threshold: EPI >= 0.60 for L2 macro validation pass.

    Parameters
    ----------
    df : DataFrame
        CVRunner-compatible simulation trace.
    benchmarks : list of Benchmark, optional
        Defaults to FLOOD_BENCHMARKS.
    decision_col : str
        Decision column name.
    tolerance : float
        Tolerance factor for range check.

    Returns
    -------
    float
        EPI score in [0, 1].
    """
    report = compare_with_benchmarks(df, benchmarks, decision_col, tolerance)
    return report.plausibility_score
