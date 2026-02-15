"""
Null-Model EPI Distribution — Random baseline for EPI significance testing.

Generates uniformly random action traces and computes the EPI distribution
via Monte Carlo simulation. Answers: "Could random agents pass EPI >= 0.60?"

Usage:
    from validation.metrics.null_model import compute_null_epi_distribution, epi_significance_test

    null = compute_null_epi_distribution(agent_profiles, n_simulations=1000)
    sig = epi_significance_test(observed_epi=0.78, null_distribution=null["samples"])
"""

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from validation.metrics.l2_macro import compute_l2_metrics


# Default action pools per agent type (flood ABM)
_FLOOD_OWNER_ACTIONS = ["do_nothing", "buy_insurance", "elevate", "buyout", "retrofit"]
_FLOOD_RENTER_ACTIONS = ["do_nothing", "buy_insurance", "relocate"]
_FLOOD_ACTION_POOLS = {"owner": _FLOOD_OWNER_ACTIONS, "renter": _FLOOD_RENTER_ACTIONS}


def generate_null_traces(
    agent_profiles: pd.DataFrame,
    n_years: int = 13,
    seed: int = 0,
    action_pools: Optional[Dict[str, List[str]]] = None,
) -> List[Dict]:
    """Generate uniformly random action traces for null model.

    Each agent picks a random action each year from their type's action pool.
    Traces include minimal structure for L2 metric computation.

    Args:
        agent_profiles: DataFrame with agent_id, tenure, flood_zone, mg columns.
        n_years: Number of simulation years.
        seed: Random seed for reproducibility.
        action_pools: Dict mapping agent type to action list.
            E.g., {"owner": ["do_nothing", "buy_insurance", ...], "renter": [...]}.
            Defaults to flood ABM action pools for backward compatibility.

    Returns:
        List of trace dicts compatible with compute_l2_metrics().
    """
    if action_pools is None:
        action_pools = _FLOOD_ACTION_POOLS

    rng = np.random.default_rng(seed)
    traces = []

    for _, row in agent_profiles.iterrows():
        agent_id = str(row["agent_id"])
        tenure = str(row.get("tenure", "Owner"))
        flood_zone = str(row.get("flood_zone", "LOW"))
        mg = bool(row.get("mg", False))

        is_owner = tenure.lower() == "owner"
        agent_type_key = "owner" if is_owner else "renter"
        action_pool = action_pools.get(agent_type_key, ["do_nothing"])

        for year in range(1, n_years + 1):
            action = action_pool[rng.integers(len(action_pool))]

            # Simulate flooding: ~20% chance per year for HIGH zone, ~5% for others
            if flood_zone == "HIGH":
                flooded = rng.random() < 0.20
            else:
                flooded = rng.random() < 0.05

            trace = {
                "agent_id": agent_id,
                "year": year,
                "approved_skill": {"skill_name": action},
                "outcome": "APPROVED",
                "validated": True,
                "flooded_this_year": flooded,
                "state_before": {
                    "flood_zone": flood_zone,
                    "tenure": tenure,
                    "mg": mg,
                    "flooded_this_year": flooded,
                },
            }
            traces.append(trace)

    return traces


def compute_null_epi_distribution(
    agent_profiles: pd.DataFrame,
    n_simulations: int = 1000,
    n_years: int = 13,
    seed: int = 0,
    action_pools: Optional[Dict[str, List[str]]] = None,
) -> Dict:
    """Monte Carlo null-model EPI distribution.

    Runs n_simulations of random agents and computes EPI for each,
    building a null distribution for significance testing.

    Args:
        agent_profiles: DataFrame with agent metadata.
        n_simulations: Number of Monte Carlo iterations.
        n_years: Years per simulation.
        seed: Base random seed.
        action_pools: Dict mapping agent type to action list.
            Defaults to flood ABM action pools.

    Returns:
        Dict with null_epi_mean, null_epi_std, null_epi_p05, null_epi_p95,
        null_epi_p99, samples (list), n_simulations.
    """
    samples = []

    for i in range(n_simulations):
        null_traces = generate_null_traces(agent_profiles, n_years, seed=seed + i,
                                           action_pools=action_pools)
        l2 = compute_l2_metrics(null_traces, agent_profiles)
        samples.append(l2.epi)

    samples_arr = np.array(samples)

    return {
        "null_epi_mean": round(float(samples_arr.mean()), 4),
        "null_epi_std": round(float(samples_arr.std()), 4),
        "null_epi_p05": round(float(np.percentile(samples_arr, 5)), 4),
        "null_epi_p50": round(float(np.percentile(samples_arr, 50)), 4),
        "null_epi_p95": round(float(np.percentile(samples_arr, 95)), 4),
        "null_epi_p99": round(float(np.percentile(samples_arr, 99)), 4),
        "samples": [round(float(s), 4) for s in samples],
        "n_simulations": n_simulations,
    }


def epi_significance_test(
    observed_epi: float,
    null_distribution: List[float],
) -> Dict:
    """Test if observed EPI significantly exceeds null model.

    Computes empirical p-value and z-score against the null distribution.

    Args:
        observed_epi: The observed EPI from actual experiment.
        null_distribution: List of EPI values from null model simulations.

    Returns:
        Dict with p_value, z_score, significant (bool at alpha=0.05).
    """
    null_arr = np.array(null_distribution)
    n = len(null_arr)

    if n == 0:
        return {"p_value": 1.0, "z_score": 0.0, "significant": False}

    # Empirical p-value: proportion of null >= observed
    p_value = float((null_arr >= observed_epi).sum() + 1) / (n + 1)

    # Z-score
    null_mean = float(null_arr.mean())
    null_std = float(null_arr.std())
    z_score = (observed_epi - null_mean) / null_std if null_std > 0 else 0.0

    return {
        "p_value": round(p_value, 6),
        "z_score": round(z_score, 4),
        "significant": p_value < 0.05,
        "observed_epi": round(observed_epi, 4),
        "null_mean": round(null_mean, 4),
        "null_std": round(null_std, 4),
    }
