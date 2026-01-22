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

References:
- FLOODABM Supplementary Materials (Text S3, Table S4)
- Bubeck et al. (2023) SAGE: Panel data on TP persistence
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Optional


# =============================================================================
# FLOODABM CALIBRATED PARAMETERS (Table S4)
# =============================================================================
# These are calibrated separately for MG and NMG using hybrid grid search
# and bounded numerical optimization (RMSE + MAE minimization)

# Default parameters (use MG/NMG specific when available)
TAU_0 = 2.0       # tau_0: Initial half-life (years) - memory decays faster initially
TAU_INF = 8.0     # tau_inf: Asymptotic half-life (years) - long-term memory persistence
K_DECAY = 0.3     # k: Decay rate constant for half-life evolution

# TP Gain Parameters
THETA = 0.5       # theta: Damage ratio threshold for TP gain (50% damage)
SHOCK_SCALE = 0.3  # cs: Shock scaling factor (not used in current formula)

# Weighted decay coefficients
ALPHA = 0.4       # PA weight in decay formula
BETA = 0.6        # SC weight in decay formula

# MG-specific calibrated parameters (Table S4)
MG_PARAMS = {
    "alpha": 0.50,
    "beta": 0.21,
    "tau_0": 1.00,
    "tau_inf": 32.19,
    "k": 0.03,
}

# NMG-specific calibrated parameters (Table S4)
NMG_PARAMS = {
    "alpha": 0.22,
    "beta": 0.10,
    "tau_0": 2.72,
    "tau_inf": 50.10,
    "k": 0.01,
}


@dataclass
class TPState:
    """Threat perception state for a group or agent."""

    tp: float           # Current TP value [0, 1]
    pa: float           # Place attachment score [0, 1]
    sc: float           # Social capital score [0, 1]
    year: int           # Current simulation year
    is_mg: bool = False  # Whether this is a marginalized group

    def to_dict(self) -> dict:
        return {
            "tp": round(self.tp, 4),
            "pa": round(self.pa, 4),
            "sc": round(self.sc, 4),
            "year": self.year,
            "is_mg": self.is_mg,
        }


@dataclass
class TPUpdateResult:
    """Result of TP update calculation."""

    tp_new: float       # Updated TP value
    tp_old: float       # Previous TP value
    tau_t: float        # Current half-life
    mu_t: float         # Current decay coefficient
    damage_ratio: float  # Computed damage ratio
    damage_gate: bool   # Whether damage gate was triggered
    tp_decay: float     # TP lost to decay
    tp_gain: float      # TP gained from damage

    def to_dict(self) -> dict:
        return {
            "tp_new": round(self.tp_new, 4),
            "tp_old": round(self.tp_old, 4),
            "tau_t": round(self.tau_t, 4),
            "mu_t": round(self.mu_t, 4),
            "damage_ratio": round(self.damage_ratio, 4),
            "damage_gate": self.damage_gate,
            "tp_decay": round(self.tp_decay, 4),
            "tp_gain": round(self.tp_gain, 4),
        }


class TPDecayEngine:
    """
    Manage threat perception decay per FLOODABM methodology.

    Supports separate tracking for MG and NMG groups with calibrated parameters.

    The decay formula implements a "memory persistence" model where:
    1. TP decays over time (people forget flood risks)
    2. Decay rate depends on social factors (PA, SC)
    3. TP can increase when damage exceeds threshold
    4. Half-life evolves over time (longer persistence with repeated exposure)
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
        """
        Initialize the TP decay engine.

        Args:
            tau_0: Initial half-life in years
            tau_inf: Asymptotic half-life in years
            k: Decay rate constant
            theta: Damage ratio threshold for TP gain
            alpha: Weight for Place Attachment in decay
            beta: Weight for Social Capital in decay
            use_mg_params: If True, use MG calibrated params; if False, use NMG;
                          if None, use provided values
        """
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
        """
        Calculate evolving half-life tau(t).

        Formula:
            tau(t) = tau_inf - (tau_inf - tau_0) * exp(-k*t)

        As t -> infinity, tau(t) -> tau_inf (memory persists longer)
        At t = 0, tau(t) = tau_0 (initial rapid decay)

        Args:
            t: Time in years since simulation start

        Returns:
            Half-life in years
        """
        return self.tau_inf - (self.tau_inf - self.tau_0) * math.exp(-self.k * t)

    def calculate_decay_coefficient(
        self,
        t: int,
        pa: float,
        sc: float,
    ) -> float:
        """
        Calculate decay coefficient mu_t.

        Formula:
            mu_t = ln(2) / tau(t) * (alpha * PA + beta * SC)

        Higher PA and SC lead to faster decay (counterintuitive but reflects
        that strong community ties may lead to normalization of risk).

        Args:
            t: Time in years
            pa: Place attachment score [0, 1]
            sc: Social capital score [0, 1]

        Returns:
            Decay coefficient mu_t [0, 1]
        """
        tau_t = self.calculate_half_life(t)
        weighted_social = self.alpha * pa + self.beta * sc
        mu = (math.log(2) / tau_t) * weighted_social
        return min(1.0, max(0.0, mu))  # Clamp to valid range

    def update_tp(
        self,
        state: TPState,
        total_damage: float,
        total_rcv: float,
        kappa: float = 1.0,
    ) -> TPUpdateResult:
        """
        Update threat perception for next period.

        Formula:
            TP_t = (1 - mu_t) * TP_{t-1} + kappa * 1{r_t > theta} * r_t

        Where:
            - (1 - mu_t) * TP_{t-1} is the decay term
            - kappa * 1{r_t > theta} * r_t is the gain term (only when damaged)

        Args:
            state: Current TP state with tp, pa, sc, year
            total_damage: Total damage this year (G_t in dollars)
            total_rcv: Total replacement cost value (RCV_t in dollars)
            kappa: TP gain scaling factor (default 1.0)

        Returns:
            TPUpdateResult with new TP value and diagnostics
        """
        # Calculate damage ratio
        damage_ratio = total_damage / total_rcv if total_rcv > 0 else 0

        # Damage gate: only gain TP if damage exceeds threshold
        damage_gate = damage_ratio > self.theta

        # Calculate decay coefficient
        tau_t = self.calculate_half_life(state.year)
        mu_t = self.calculate_decay_coefficient(state.year, state.pa, state.sc)

        # Calculate decay and gain components
        tp_after_decay = (1 - mu_t) * state.tp
        tp_gain = kappa * damage_ratio if damage_gate else 0

        # Update TP (clamp to [0, 1])
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
        """
        Simulate TP trajectory over multiple years.

        Useful for visualization and validation against calibration targets.

        Args:
            initial_tp: Starting TP value
            pa: Place attachment (constant over time)
            sc: Social capital (constant over time)
            years: Number of years to simulate
            flood_years: Dict mapping year -> damage amount (None = no flood)
            total_rcv: Total RCV for damage ratio calculation

        Returns:
            List of TPUpdateResult for each year
        """
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
    """
    Factory function to create calibrated engine for MG or NMG.

    Args:
        is_mg: True for marginalized group, False for non-marginalized

    Returns:
        TPDecayEngine with calibrated parameters
    """
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
    """
    Convenience function for single TP update.

    Args:
        current_tp: Current threat perception [0, 1]
        pa: Place attachment [0, 1]
        sc: Social capital [0, 1]
        year: Current simulation year
        damage: Damage amount this year
        rcv: Total replacement cost value
        is_mg: Whether agent is marginalized group

    Returns:
        Updated TP value
    """
    engine = create_engine_for_group(is_mg)
    state = TPState(tp=current_tp, pa=pa, sc=sc, year=year, is_mg=is_mg)
    result = engine.update_tp(state, total_damage=damage, total_rcv=rcv)
    return result.tp_new
