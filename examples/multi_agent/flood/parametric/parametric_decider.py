"""Parametric household decision surface for the flood domain (no LLM).

``PARAMETRIC_CALIBRATION`` is the numeric knob set a household decision
rule needs: per-(zone, tenure) base adoption rates, PMT-style slopes,
eligibility gates, and cost constants. This module holds only that
surface plus the deterministic rate estimator built on top of it — the
full ``ParametricHouseholdDecider`` (per-agent TP/CP dynamics driven by
``environment.hazard`` / ``environment.tp_decay``, used inside the
multi-agent simulation loop) is a separate, heavier component. This
module is deliberately self-contained: no simulation or hazard-module
dependency, so :mod:`broker.calibration.optimize` can search
``PARAMETRIC_CALIBRATION`` in milliseconds without an LLM or a full
ABM run — see ``calibrate_parametric.py`` for the search itself.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

PARAMETRIC_CALIBRATION: Dict[str, Any] = {
    "base_rates": {
        "flood_prone_owner": 0.25,
        "flood_prone_renter": 0.08,
        "non_flood_prone_owner": 0.03,
        "non_flood_prone_renter": 0.01,
    },
    "slopes": {
        "threat": 2.0,
        "coping": 1.0,
        "cost": 1.5,
    },
    "anchors": {
        "tp0": 0.5,
        "cp0": 0.5,
    },
    "gates": {
        "elevate": {
            "min_flood_count": 2,
            "requires_not_elevated": True,
            "blocked_zones": ["LOW"],
        },
        "buyout": {
            "min_flood_count": 3,
            "blocked_zones": ["LOW"],
        },
        "relocate": {
            "min_flood_count": 1,
        },
    },
    "costs": {
        "default_effective_premium_rate": 0.008,
        "elevation_cost_usd": 80_000.0,
    },
}

OWNER_HIERARCHY = ("buy_insurance", "elevate_house", "buyout_program", "do_nothing")
RENTER_HIERARCHY = ("buy_contents_insurance", "relocate", "do_nothing")


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def _base_rate(calibration: Dict[str, Any], flood_prone: bool, tenure: str) -> float:
    key = f"{'flood_prone' if flood_prone else 'non_flood_prone'}_{tenure.lower()}"
    base_rates = calibration["base_rates"]
    if key not in base_rates:
        raise KeyError(
            f"no base_rate for key={key!r}; calibration['base_rates'] "
            f"has {sorted(base_rates)}"
        )
    return float(base_rates[key])


def aggregate_rates(
    calibration: Dict[str, Any],
    population: List[Dict[str, Any]],
) -> Dict[str, float]:
    """Estimate population-level aggregate action rates from a calibration dict.

    Deterministic closed-form expectation (no RNG, no per-year TP/CP
    dynamics) over a synthetic ``population`` of household descriptors
    — ``{"tenure": "Owner"|"Renter", "flood_zone": str, "flood_count": int}``.
    Each household's action probability at the calibrated anchor point
    (``tp = tp0``, ``cp = cp0``, so the threat/coping slope terms are
    zero) collapses to ``sigmoid(logit(base_rate) - cost_slope *
    cost_burden)`` — this is the same anchored-logistic shape
    ``ParametricHouseholdDecider.action_probability`` uses, evaluated at
    its own calibration anchor rather than a simulated agent's current
    TP/CP.

    Returns the subset of ``examples/multi_agent/flood/paper3/analysis/
    empirical_benchmarks.FLOOD_BENCHMARKS`` metrics this surface can
    speak to: ``insurance_rate``, ``insurance_rate_all``,
    ``elevation_rate``, ``buyout_rate``. Metrics this simplified surface
    has no opinion on (post-flood inaction, MG-NMG gap, repetitive-loss,
    lapse rate) are intentionally omitted — a missing, non-required
    metric is excluded from EPI rather than counted as a miss.

    ``insurance_rate`` and ``insurance_rate_all`` are two different
    populations, and must never be computed as one number under two
    names:

    * ``insurance_rate`` — uptake among **flood-prone households only**
      (``flood_zone != "LOW"``), matching the FLOOD_BENCHMARKS entry
      "NFIP Insurance Uptake (SFHA)", range [0.30, 0.50].
    * ``insurance_rate_all`` — uptake across **all zones**, matching
      "Insurance Uptake (All Zones)", range [0.15, 0.40].

    The base rate differs by zone, so the two numbers differ. Emitting
    one value for both (as this function did before the PR-7 review)
    makes them useless as an in-sample / held-out pair: fitting one
    lands exactly on the other, and the "out of sample" number measures
    nothing. ``broker.calibration.optimize.split_targets`` now refuses
    such a split outright when handed the observed values.
    """
    slopes = calibration["slopes"]
    costs = calibration["costs"]
    cost_slope = float(slopes["cost"])
    elevate_gate = calibration["gates"]["elevate"]
    buyout_gate = calibration["gates"]["buyout"]

    n_owners = 0
    n_all = 0
    n_prone = 0
    insured_sum = 0.0
    insured_prone_sum = 0.0
    elevated_sum = 0.0
    buyout_sum = 0.0

    for agent in population:
        tenure = agent["tenure"]
        zone = str(agent.get("flood_zone", "MEDIUM")).upper()
        flood_count = int(agent.get("flood_count", 0))
        flood_prone = zone != "LOW"
        n_all += 1

        base = _base_rate(calibration, flood_prone, tenure)
        # Insurance cost burden scales with the default premium rate;
        # at the calibration anchor (tp=tp0, cp=cp0) only the cost term
        # is non-zero, so p_insure = sigmoid(logit(base) - cost_slope * cost).
        premium_burden = float(costs["default_effective_premium_rate"]) * 5.0
        p_insure = _sigmoid(_logit(base) - cost_slope * premium_burden)
        insured_sum += p_insure
        if flood_prone:
            n_prone += 1
            insured_prone_sum += p_insure

        if tenure == "Owner":
            n_owners += 1
            eligible_elevate = (
                flood_count >= int(elevate_gate["min_flood_count"])
                and zone not in set(elevate_gate.get("blocked_zones", []))
            )
            if eligible_elevate:
                elevation_burden = float(costs["elevation_cost_usd"]) / 400_000.0
                p_elevate = _sigmoid(_logit(base) - cost_slope * elevation_burden)
                elevated_sum += p_elevate

            eligible_buyout = (
                flood_count >= int(buyout_gate["min_flood_count"])
                and zone not in set(buyout_gate.get("blocked_zones", []))
            )
            if eligible_buyout:
                buyout_sum += base * 0.5  # buyout is last-resort, damped

    if n_all == 0:
        return {}

    rates = {
        "insurance_rate_all": insured_sum / n_all,
        "buyout_rate": buyout_sum / n_all,
    }
    # Flood-prone-only uptake. Omitted rather than defaulted when the
    # population has no flood-prone households: this benchmark is not
    # required, so leaving it out excludes it from EPI, whereas a
    # stand-in number would be scored as if it had been measured.
    if n_prone > 0:
        rates["insurance_rate"] = insured_prone_sum / n_prone
    if n_owners > 0:
        rates["elevation_rate"] = elevated_sum / n_owners
    return rates


def _logit(probability: float) -> float:
    p = min(max(float(probability), 1e-9), 1.0 - 1e-9)
    return math.log(p / (1.0 - p))
