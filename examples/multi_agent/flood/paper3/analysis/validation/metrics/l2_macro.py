"""
L2 Macro Validation Metrics.

EPI (Empirical Plausibility Index) and 8 empirical benchmarks.
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import pandas as pd

from validation.theories.pmt import PMT_OWNER_RULES, PMT_RENTER_RULES
from validation.io.trace_reader import _normalize_action, _extract_action
from validation.io.state_inference import _extract_final_states_from_decisions
from validation.benchmarks.flood import (
    EMPIRICAL_BENCHMARKS as _FLOOD_BENCHMARKS,
    _compute_benchmark as _flood_compute_benchmark,
)


@dataclass
class L2Metrics:
    """L2 Macro validation metrics."""
    epi: float
    benchmark_results: Dict[str, Dict]
    benchmarks_in_range: int
    total_benchmarks: int
    supplementary: Optional[Dict] = None

    def passes_threshold(self) -> bool:
        return self.epi >= 0.60


def compute_l2_metrics(
    traces: List[Dict],
    agent_profiles: pd.DataFrame,
    benchmarks: Optional[Dict[str, Dict]] = None,
    benchmark_compute_fn: Optional[Callable] = None,
) -> L2Metrics:
    """Compute L2 macro-level validation metrics.

    Args:
        traces: List of decision trace dicts.
        agent_profiles: DataFrame with agent metadata.
        benchmarks: Dict of benchmark definitions {name: {range, weight, description}}.
            Defaults to flood EMPIRICAL_BENCHMARKS for backward compatibility.
        benchmark_compute_fn: Function(name, df, traces) -> Optional[float].
            Defaults to flood _compute_benchmark for backward compatibility.
    """
    if benchmarks is None:
        benchmarks = _FLOOD_BENCHMARKS
    if benchmark_compute_fn is None:
        benchmark_compute_fn = _flood_compute_benchmark
    # Check trace coverage
    traced_agents = set(t.get("agent_id", "") for t in traces)
    traced_agents.discard("")
    profile_agents = set(agent_profiles["agent_id"].astype(str))
    coverage = len(traced_agents & profile_agents) / len(profile_agents) if len(profile_agents) > 0 else 0
    if coverage < 0.90:
        print(f"  WARNING: Only {len(traced_agents & profile_agents)}/{len(profile_agents)} agents "
              f"have traces ({coverage:.1%} coverage). "
              f"Agents without traces are treated as having taken no action (fillna=False).")

    final_states = _extract_final_states_from_decisions(traces)

    if final_states:
        n_insured = sum(1 for s in final_states.values() if s.get("has_insurance"))
        n_elevated = sum(1 for s in final_states.values() if s.get("elevated"))
        n_buyout = sum(1 for s in final_states.values() if s.get("bought_out"))
        n_relocated = sum(1 for s in final_states.values() if s.get("relocated"))
        print(f"  Decision-based inference: {len(final_states)} agents")
        print(f"    Insured: {n_insured}, Elevated: {n_elevated}, "
              f"Bought out: {n_buyout}, Relocated: {n_relocated}")

    df = agent_profiles.copy()
    df["agent_id"] = df["agent_id"].astype(str)

    for agent_id, state in final_states.items():
        mask = df["agent_id"] == agent_id
        if mask.any():
            for key, value in state.items():
                df.loc[mask, f"final_{key}"] = value

    benchmark_results = {}
    in_range_count = 0
    total_weight = 0
    weighted_in_range = 0

    for name, config in benchmarks.items():
        value = benchmark_compute_fn(name, df, traces)
        low, high = config["range"]
        weight = config["weight"]

        rounded_value = round(value, 4) if value is not None else None
        is_in_range = low <= rounded_value <= high if rounded_value is not None else False

        benchmark_results[name] = {
            "value": rounded_value,
            "range": config["range"],
            "in_range": is_in_range,
            "weight": weight,
            "description": config["description"],
        }

        if value is not None:
            total_weight += weight
            if is_in_range:
                in_range_count += 1
                weighted_in_range += weight

    epi = weighted_in_range / total_weight if total_weight > 0 else 0.0

    supplementary = _compute_rejection_supplementary(traces, agent_profiles)

    return L2Metrics(
        epi=round(epi, 4),
        benchmark_results=benchmark_results,
        benchmarks_in_range=in_range_count,
        total_benchmarks=len(benchmarks),
        supplementary=supplementary,
    )


def _compute_rejection_supplementary(
    traces: List[Dict],
    agent_profiles: pd.DataFrame,
) -> Dict:
    """Compute REJECTED tracking metrics as supplementary L2 output."""
    mg_lookup = dict(zip(
        agent_profiles["agent_id"].astype(str),
        agent_profiles["mg"].astype(bool),
    ))

    rejected_mg = 0
    rejected_nmg = 0
    total_mg = 0
    total_nmg = 0

    for trace in traces:
        agent_id = str(trace.get("agent_id", ""))
        is_mg = mg_lookup.get(agent_id)
        if is_mg is None:
            continue

        outcome = trace.get("outcome", "")
        if is_mg:
            total_mg += 1
            if outcome == "REJECTED":
                rejected_mg += 1
        else:
            total_nmg += 1
            if outcome == "REJECTED":
                rejected_nmg += 1

    rejection_rate_mg = rejected_mg / total_mg if total_mg > 0 else 0.0
    rejection_rate_nmg = rejected_nmg / total_nmg if total_nmg > 0 else 0.0
    total_rejected = rejected_mg + rejected_nmg
    total_all = total_mg + total_nmg
    overall_rejection_rate = total_rejected / total_all if total_all > 0 else 0.0

    constrained_non_adaptation = 0
    for trace in traces:
        outcome = trace.get("outcome", "")
        if outcome == "REJECTED":
            proposed = _normalize_action(
                trace.get("skill_proposal", {}).get("skill_name", "do_nothing")
                if isinstance(trace.get("skill_proposal"), dict)
                else "do_nothing"
            )
            if proposed != "do_nothing":
                constrained_non_adaptation += 1

    constrained_rate = constrained_non_adaptation / total_all if total_all > 0 else 0.0

    return {
        "rejection_rate_overall": round(overall_rejection_rate, 4),
        "rejection_rate_mg": round(rejection_rate_mg, 4),
        "rejection_rate_nmg": round(rejection_rate_nmg, 4),
        "rejection_gap_mg_minus_nmg": round(rejection_rate_mg - rejection_rate_nmg, 4),
        "constrained_non_adaptation_rate": round(constrained_rate, 4),
        "total_rejected": total_rejected,
        "total_decisions": total_all,
    }
