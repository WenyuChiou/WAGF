"""Reservoir operations continuous-control modules.

DECISION TIMING (hindcast-then-set): the runner advances the solver 12
monthly sub-steps under the LAST committed release target, then the operator
decides for the COMING year. The dead-pool projection therefore combines the
end-of-year storage just observed with NEXT year's inflow forecast
(``inflow_forecast_for_year(year + 1)``).

DESIGN arithmetic. Years 1-3 run under the default release fraction of 1.0 (all of demand)
(0.75 maf/month); year factors are (1.0, 0.7, 0.4, 0.4) — a two-year
drought tail:

* Year 1 factor 1.0, inflow 10.50 maf:
  month-end storage = [18.270, 18.737, 19.400, 19.756, 19.708, 19.361,
  18.818, 18.179, 17.648, 17.321, 17.198, 17.276]; spill=0.000,
  shortfall=0.000, mean release=0.750.
* Year 2 factor 0.7, inflow 7.35 maf:
  month-end storage = [17.193, 17.251, 17.449, 17.434, 17.140, 16.639,
  16.002, 15.302, 14.679, 14.202, 13.870, 13.682]; spill=0.000,
  shortfall=0.000, mean release=0.750.
* Year 3 factor 0.4, inflow 4.20 maf:
  month-end storage = [13.275, 12.952, 12.713, 12.355, 11.842, 11.213,
  10.511, 9.776, 9.088, 8.488, 7.973, 7.543]; spill=0.000,
  shortfall=0.000, mean release=0.750.

Per-decision what-if run (the contract's ``dead_pool_violation`` feasibility
bound: ``storage_unclamped >= 6.0`` at every month of the coming year, on a copy
of this model fed the forecast the operator saw):

* Decision 1 (S=17.276, F2=7.35):  1.0 passes.
* Decision 2 (S=13.682, F3=4.20):  1.0 passes.
* Decision 3 (S=7.543,  F4=4.20):  1.0 -> storage_unclamped 5.434 at month 6
  (2.102 at month 12) < 6.0 dead pool -> WALL fires (a release fraction of about 0.536
  or less passes); the scripted retry at 0.5 ends the year at 6.362 maf and is
  APPROVED — wall -> retry -> resolves.
* Year 4 then runs at the curtailed 0.375 maf/month and ends at
  6.362 maf, above dead pool.
* Decision 4 (S=6.362, F5=10.50 — the factor cycle wraps to wet):
  1.0 passes (recovery year).
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, Iterable, List

from broker.coupling import ContinuousBundle, CouplingViolation


INFLOW_PATTERN_MONTHLY = (
    1.2,
    1.4,
    1.6,
    1.3,
    0.9,
    0.6,
    0.4,
    0.3,
    0.4,
    0.6,
    0.8,
    1.0,
)
# Two-year drought tail (review C1 redesign): the wall must fire from a
# GENUINE forward forecast, so the drought continues into year 4 — at the
# year-3 decision the coming year's forecast (0.4 x 10.5 = 4.2 maf) is what
# makes a release fraction of 1.0 physically unsafe.
YEAR_FACTORS = (1.0, 0.7, 0.4, 0.4)


class ToyMassBalanceReservoir:
    """BMI-shaped monthly reservoir with one settable release target."""

    CAPACITY = 24.0
    DEAD_POOL = 6.0
    INITIAL_STORAGE = 18.0
    DEMAND_M = 0.75
    DEMAND_YEAR = DEMAND_M * 12.0
    EVAP_RATE = 0.01

    def __init__(
        self,
        *,
        storage0: float = INITIAL_STORAGE,
        release_target: float = DEMAND_M,
        year_factors: Iterable[float] = YEAR_FACTORS,
    ) -> None:
        self._storage = float(storage0)
        self._release_target = float(release_target)
        self._year_factors = tuple(float(x) for x in year_factors)
        self._t = 0
        self._spill = 0.0
        self._shortfall = 0.0
        self._release_actual = 0.0
        self._inflow = 0.0
        self._evaporation = 0.0
        self._last_available = self._storage
        self._storage_unclamped = self._storage
        # Used only on a projection copy (set_inflow_forecast): None = off.
        self._forecast_total: float | None = None
        self._forecast_until = 0

    def initialize(self, _config_file: str | None = None) -> None:
        self._storage = self.INITIAL_STORAGE
        self._release_target = self.DEMAND_M
        self._t = 0
        self._spill = 0.0
        self._shortfall = 0.0
        self._release_actual = 0.0
        self._inflow = 0.0
        self._evaporation = 0.0
        self._last_available = self._storage
        self._storage_unclamped = self._storage
        self._forecast_total = None
        self._forecast_until = 0

    @property
    def release_target(self) -> float:
        return self._release_target

    @property
    def last_available(self) -> float:
        return self._last_available

    def get_component_name(self) -> str:
        return "toy-mass-balance-reservoir"

    def _year_factor_for_index(self, year_index_zero_based: int) -> float:
        return self._year_factors[year_index_zero_based % len(self._year_factors)]

    def inflow_forecast_for_year(self, year: int) -> float:
        # Explicit modulo cycle (review S3): years beyond the factor tuple
        # wrap around loudly-by-convention instead of silently clamping to
        # the first year.
        factor = self._year_factor_for_index((int(year) - 1) % len(self._year_factors))
        return sum(INFLOW_PATTERN_MONTHLY) * factor

    def set_inflow_forecast(self, year_total: float) -> None:
        """Projection copies only: the next 12 months' inflow follows the
        forecast the agent saw (monthly = pattern share of ``year_total``), not
        the true inflow of that year. The live model never calls this."""
        self._forecast_total = float(year_total)
        self._forecast_until = self._t + 12

    def _current_inflow(self) -> float:
        month = self._t % 12
        if self._forecast_total is not None and self._t < self._forecast_until:
            return INFLOW_PATTERN_MONTHLY[month] * self._forecast_total / sum(
                INFLOW_PATTERN_MONTHLY
            )
        year = self._t // 12
        return INFLOW_PATTERN_MONTHLY[month] * self._year_factor_for_index(year)

    def _evap_loss(self, storage: float) -> float:
        return self.EVAP_RATE * storage

    def update(self) -> None:
        inflow_m = self._current_inflow()
        available = max(0.0, self._storage + inflow_m)
        release_applied = min(self._release_target, available)
        evap_loss = self._evap_loss(self._storage)
        next_storage = (
            self._storage
            + inflow_m
            - release_applied
            - evap_loss
        )
        spill = max(0.0, next_storage - self.CAPACITY)
        # Published for the feasibility bound: the storage this month asked
        # for, before the clamp to [0, CAPACITY] hides how far below dead pool
        # (or zero) the request would have taken the reservoir.
        self._storage_unclamped = next_storage
        self._storage = min(self.CAPACITY, max(0.0, next_storage))
        self._spill = spill
        self._shortfall = max(0.0, self.DEMAND_M - release_applied)
        self._release_actual = release_applied
        # Published for the contract's water-balance relation: this month's
        # inflow and the evaporation loss actually subtracted above.
        self._inflow = inflow_m
        self._evaporation = evap_loss
        self._last_available = available
        self._t += 1

    def get_value(self, name: str) -> List[float]:
        if name == "storage":
            return [self._storage]
        if name == "storage_unclamped":
            return [self._storage_unclamped]
        if name == "spill":
            return [self._spill]
        if name == "shortfall":
            return [self._shortfall]
        if name == "release_actual":
            return [self._release_actual]
        if name == "release_target":
            return [self._release_target]
        if name == "inflow":
            return [self._inflow]
        if name == "evaporation":
            return [self._evaporation]
        raise KeyError(name)

    def set_value(self, name: str, value) -> None:
        if name != "release_target":
            raise KeyError(f"{name!r} is not a settable reservoir input")
        if isinstance(value, (list, tuple)):
            raw = value[0]
        else:
            raw = value
        self._release_target = float(raw)

    def get_var_units(self, name: str) -> str:
        if name in {"storage", "storage_unclamped", "spill", "shortfall", "inflow", "evaporation"}:
            return "maf"
        if name in {"release_actual", "release_target"}:
            return "maf_per_month"
        raise KeyError(name)

    def get_current_time(self) -> float:
        return float(self._t)


class ToyLinearEvapReservoir(ToyMassBalanceReservoir):
    """Same BMI interface as ToyMassBalanceReservoir, fixed monthly evap."""

    FIXED_EVAP_M = 0.05

    def get_component_name(self) -> str:
        return "toy-linear-evap-reservoir"

    def _evap_loss(self, storage: float) -> float:
        return min(float(storage), self.FIXED_EVAP_M)


class ReservoirOpsBundle(ContinuousBundle):
    """Map the governed release fraction (0 to 1) onto the solver setpoint input."""

    def __post_init__(self) -> None:
        super().__post_init__()
        self._last_release_target = ToyMassBalanceReservoir.DEMAND_M

    def _release_target_for(self, approved_skill: Any) -> float:
        """The release target a skill asks for (no side effects)."""
        params = getattr(approved_skill, "parameters", None) or {}
        fraction = params.get("magnitude_pct")
        if fraction is None:
            return self._last_release_target
        return float(fraction) * ToyMassBalanceReservoir.DEMAND_M

    def inputs_for_skill(self, approved_skill: Any) -> Dict[str, float]:
        """magnitude_pct -> release_target; no magnitude -> the last target.
        Any other declared input passes through as in ContinuousBundle."""
        params = dict(getattr(approved_skill, "parameters", None) or {})
        params["release_target"] = self._release_target_for(approved_skill)
        return super().inputs_for_skill(replace(approved_skill, parameters=params))

    def apply_forecast(self, model_copy: Any, context: Dict[str, Any]) -> None:
        """Feed a projection copy the inflow forecast the operator saw."""
        env = context.get("env_state") if isinstance(context, dict) else None
        forecast = env.get("inflow_forecast_year") if isinstance(env, dict) else None
        if forecast is None and isinstance(context, dict):
            forecast = context.get("inflow_forecast_year")
        if forecast is None:
            raise CouplingViolation(
                "projection needs inflow_forecast_year in the validation context "
                "(the forecast the operator saw); it is absent, so the copy cannot "
                "be fed it. Check the runner's env wiring."
            )
        model_copy.set_inflow_forecast(forecast)

    def commit_world_delta(self, approved_skill: Any):
        params = dict(getattr(approved_skill, "parameters", None) or {})
        release_target = self._release_target_for(approved_skill)

        spec = self.contract.input_specs().get("release_target")
        if spec is not None:
            violation = spec.range_violation(release_target)
            if violation:
                raise CouplingViolation(
                    "input contract violations (derived setpoint): "
                    f"input {violation}"
                )

        params["release_target"] = release_target
        mapped_skill = replace(approved_skill, parameters=params)
        delta = super().commit_world_delta(mapped_skill)
        self._last_release_target = release_target
        return delta


__all__ = [
    "INFLOW_PATTERN_MONTHLY",
    "YEAR_FACTORS",
    "ReservoirOpsBundle",
    "ToyLinearEvapReservoir",
    "ToyMassBalanceReservoir",
]
