"""
Threat Perception (TP) Decay Module.

Implements FLOODABM TP dynamics with time-varying half-life decay.

Formulation:
    TP_t = (1 - mu_t) * TP_{t-1} + kappa * 1{r_t > theta} * r_t

Where:
    tau(t) = tau_inf - (tau_inf - tau_0) * exp(-k*t)  # Evolving half-life
    mu_t = ln(2) / tau(t) * (alpha * PA + beta * SC)  # Decay coefficient
    r_t = G_t / RCV_t                                  # Damage ratio
    1{r_t > theta} = Damage gate                       # Only gain TP if damage exceeds threshold
"""

from __future__ import annotations

import math
from typing import Dict, Optional

from examples.multi_agent.flood.environment.decay_models import (
    TAU_0,
    TAU_INF,
    K_DECAY,
    THETA,
    SHOCK_SCALE,
    ALPHA,
    BETA,
    MG_PARAMS,
    NMG_PARAMS,
)
from examples.multi_agent.flood.environment.tp_state import TPState, TPUpdateResult


class TPDecayEngine:
    """
    Manage threat perception decay per FLOODABM methodology.
    """

    def __init__(
        self,
        tau_0: float = TAU_0,
        tau_inf: float = TAU_INF,
        k: float = K_DECAY,
        theta: float = THETA,
        alpha: float = ALPHA,
        beta: float = BETA,
        use_mg_params: Optional[bool] = None,
    ):
        if use_mg_params is True:
            params = MG_PARAMS
            self.tau_0 = params["tau_0"]
            self.tau_inf = params["tau_inf"]
            self.k = params["k"]
            self.alpha = params["alpha"]
            self.beta = params["beta"]
        elif use_mg_params is False:
            params = NMG_PARAMS
            self.tau_0 = params["tau_0"]
            self.tau_inf = params["tau_inf"]
            self.k = params["k"]
            self.alpha = params["alpha"]
            self.beta = params["beta"]
        else:
            self.tau_0 = tau_0
            self.tau_inf = tau_inf
            self.k = k
            self.alpha = alpha
            self.beta = beta

        self.theta = theta

    def calculate_half_life(self, t: int) -> float:
        return self.tau_inf - (self.tau_inf - self.tau_0) * math.exp(-self.k * t)

    def calculate_decay_coefficient(
        self,
        t: int,
        pa: float,
        sc: float,
    ) -> float:
        tau_t = self.calculate_half_life(t)
        weighted_social = self.alpha * pa + self.beta * sc
        mu = (math.log(2) / tau_t) * weighted_social
        return min(1.0, max(0.0, mu))

    def update_tp(
        self,
        state: TPState,
        total_damage: float,
        total_rcv: float,
        kappa: float = 1.0,
    ) -> TPUpdateResult:
        damage_ratio = total_damage / total_rcv if total_rcv > 0 else 0
        damage_gate = damage_ratio > self.theta

        tau_t = self.calculate_half_life(state.year)
        mu_t = self.calculate_decay_coefficient(state.year, state.pa, state.sc)

        tp_after_decay = (1 - mu_t) * state.tp
        tp_gain = kappa * damage_ratio if damage_gate else 0

        tp_new = min(1.0, max(0.0, tp_after_decay + tp_gain))

        return TPUpdateResult(
            tp_new=round(tp_new, 4),
            tp_old=state.tp,
            tau_t=round(tau_t, 4),
            mu_t=round(mu_t, 4),
            damage_ratio=round(damage_ratio, 4),
            damage_gate=damage_gate,
            tp_decay=round(state.tp - tp_after_decay, 4),
            tp_gain=round(tp_gain, 4),
        )

    def simulate_trajectory(
        self,
        initial_tp: float,
        pa: float,
        sc: float,
        years: int,
        flood_years: Optional[Dict[int, float]] = None,
        total_rcv: float = 300_000,
    ) -> list[TPUpdateResult]:
        flood_years = flood_years or {}
        results = []
        current_tp = initial_tp

        for year in range(years):
            state = TPState(tp=current_tp, pa=pa, sc=sc, year=year)
            damage = flood_years.get(year, 0)

            result = self.update_tp(
                state=state,
                total_damage=damage,
                total_rcv=total_rcv,
            )
            results.append(result)
            current_tp = result.tp_new

        return results


def create_engine_for_group(is_mg: bool) -> TPDecayEngine:
    return TPDecayEngine(use_mg_params=is_mg)


def calculate_tp_update(
    current_tp: float,
    pa: float,
    sc: float,
    year: int,
    damage: float,
    rcv: float,
    is_mg: bool = False,
) -> float:
    engine = create_engine_for_group(is_mg)
    state = TPState(tp=current_tp, pa=pa, sc=sc, year=year, is_mg=is_mg)
    result = engine.update_tp(state, total_damage=damage, total_rcv=rcv)
    return result.tp_new
