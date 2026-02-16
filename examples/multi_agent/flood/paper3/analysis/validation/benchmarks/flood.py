"""
Flood ABM Empirical Benchmarks.

8 benchmark computations split from the original 141-line if/elif chain.
"""

from typing import Dict, List, Optional

import pandas as pd

from validation.benchmarks.registry import BenchmarkRegistry
from validation.io.trace_reader import _normalize_action, _extract_action

_registry = BenchmarkRegistry()


# =============================================================================
# Empirical Benchmark Definitions
# =============================================================================

EMPIRICAL_BENCHMARKS = {
    "insurance_rate_sfha": {
        "range": (0.30, 0.60),
        "weight": 1.0,
        "description": "Insurance uptake rate in SFHA zones",
    },
    "insurance_rate_all": {
        "range": (0.15, 0.55),
        "weight": 0.8,
        "description": "Overall insurance uptake rate",
    },
    "elevation_rate": {
        "range": (0.10, 0.35),
        "weight": 1.0,
        "description": "Cumulative elevation rate",
    },
    "buyout_rate": {
        "range": (0.05, 0.25),
        "weight": 0.8,
        "description": "Cumulative buyout/relocation rate",
    },
    "do_nothing_rate_postflood": {
        "range": (0.35, 0.65),
        "weight": 1.5,
        "description": "Inaction rate among recently flooded",
    },
    "mg_adaptation_gap": {
        "range": (0.05, 0.30),
        "weight": 2.0,
        "description": "Adaptation gap between MG and NMG (composite: any protective action)",
    },
    "renter_uninsured_rate": {
        "range": (0.15, 0.40),
        "weight": 1.0,
        "description": "Uninsured rate among renters in flood zones",
    },
    "insurance_lapse_rate": {
        "range": (0.15, 0.30),
        "weight": 1.0,
        "description": "Annual insurance lapse rate",
    },
}


# =============================================================================
# Column Helpers
# =============================================================================

def _get_insured_col(df: pd.DataFrame) -> Optional[str]:
    for col in ["final_has_insurance", "final_insured"]:
        if col in df.columns:
            return col
    return None


def _get_elevated_col(df: pd.DataFrame) -> Optional[str]:
    for col in ["final_elevated"]:
        if col in df.columns:
            return col
    return None


# =============================================================================
# Registered Benchmark Functions
# =============================================================================

@_registry.register("insurance_rate_sfha")
def _compute_insurance_rate_sfha(df, traces, **kwargs):
    ins_col = kwargs.get("ins_col") or _get_insured_col(df)
    high_risk = df[df["flood_zone"] == "HIGH"]
    if len(high_risk) == 0 or ins_col is None:
        return None
    if ins_col not in high_risk.columns:
        return None
    insured = high_risk[ins_col].fillna(False).astype(float).sum()
    return insured / len(high_risk)


@_registry.register("insurance_rate_all")
def _compute_insurance_rate_all(df, traces, **kwargs):
    ins_col = kwargs.get("ins_col") or _get_insured_col(df)
    if ins_col is None or ins_col not in df.columns:
        return None
    return df[ins_col].fillna(False).astype(float).mean()


@_registry.register("elevation_rate")
def _compute_elevation_rate(df, traces, **kwargs):
    elev_col = kwargs.get("elev_col") or _get_elevated_col(df)
    owners = df[df["tenure"] == "Owner"]
    if len(owners) == 0 or elev_col is None or elev_col not in owners.columns:
        return None
    return owners[elev_col].fillna(False).astype(float).mean()


@_registry.register("buyout_rate")
def _compute_buyout_rate(df, traces, **kwargs):
    if "final_bought_out" not in df.columns and "final_relocated" not in df.columns:
        return None
    buyout = df.get("final_bought_out", pd.Series([False]*len(df), index=df.index)).fillna(False)
    reloc = df.get("final_relocated", pd.Series([False]*len(df), index=df.index)).fillna(False)
    return (buyout.astype(bool) | reloc.astype(bool)).astype(float).mean()


@_registry.register("do_nothing_rate_postflood")
def _compute_do_nothing_rate_postflood(df, traces, **kwargs):
    flooded_traces = [t for t in traces if (
        t.get("flooded_this_year", False)
        or t.get("state_before", {}).get("flooded_this_year", False)
    )]
    if len(flooded_traces) == 0:
        return None

    def _effective_action(t: Dict) -> str:
        outcome = t.get("outcome", "")
        if outcome == "REJECTED":
            return "do_nothing"
        return _normalize_action(_extract_action(t))

    inaction = sum(1 for t in flooded_traces if _effective_action(t) == "do_nothing")
    return inaction / len(flooded_traces)


@_registry.register("mg_adaptation_gap")
def _compute_mg_adaptation_gap(df, traces, **kwargs):
    mg = df[df["mg"] == True].copy()
    nmg = df[df["mg"] == False].copy()
    if len(mg) == 0 or len(nmg) == 0:
        return None

    def _any_adaptation(sub_df):
        adapted = pd.Series(False, index=sub_df.index)
        for col in ["final_has_insurance", "final_insured",
                    "final_elevated", "final_bought_out",
                    "final_relocated"]:
            if col in sub_df.columns:
                adapted = adapted | sub_df[col].fillna(False).astype(bool)
        return adapted.astype(float).mean()

    mg_rate = _any_adaptation(mg)
    nmg_rate = _any_adaptation(nmg)
    return abs(nmg_rate - mg_rate)


@_registry.register("renter_uninsured_rate")
def _compute_renter_uninsured_rate(df, traces, **kwargs):
    ins_col = kwargs.get("ins_col") or _get_insured_col(df)
    renters_flood = df[(df["tenure"] == "Renter") & (df["flood_zone"] == "HIGH")]
    if len(renters_flood) == 0 or ins_col is None or ins_col not in renters_flood.columns:
        return None
    return 1.0 - renters_flood[ins_col].fillna(False).astype(float).mean()


@_registry.register("insurance_lapse_rate")
def _compute_insurance_lapse_rate(df, traces, **kwargs):
    agent_traces: Dict[str, list] = {}
    for trace in traces:
        aid = trace.get("agent_id", "")
        if not aid:
            continue
        trace_outcome = trace.get("outcome", "")
        if trace_outcome in ("REJECTED", "UNCERTAIN"):
            continue
        if not trace.get("validated", True):
            continue
        yr = trace.get("year", 0)
        action = _normalize_action(_extract_action(trace))
        agent_traces.setdefault(aid, []).append((yr, action))

    lapses = 0
    insured_periods = 0
    for aid, yearly in agent_traces.items():
        yearly.sort(key=lambda x: x[0])
        was_insured = False
        for yr, action in yearly:
            if was_insured:
                insured_periods += 1
                if action != "buy_insurance":
                    lapses += 1
            if action == "buy_insurance":
                was_insured = True

    return lapses / insured_periods if insured_periods > 0 else None


# =============================================================================
# Public dispatch (backward-compatible interface)
# =============================================================================

def _compute_benchmark(name: str, df: pd.DataFrame, traces: List[Dict]) -> Optional[float]:
    """Compute a specific benchmark value (backward-compatible wrapper)."""
    ins_col = _get_insured_col(df)
    elev_col = _get_elevated_col(df)
    return _registry.dispatch(name, df, traces, ins_col=ins_col, elev_col=elev_col)
