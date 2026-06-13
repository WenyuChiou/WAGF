"""Phase 6W-B7 — toy multi-setpoint reservoir solver for the multi-dim worked example.

A minimal BMI-conformant toy hosting THREE settable inputs (release_rate_cms /
hydropower_target_mw / flood_pool_pct) so the multi-dimensional-action chain
(propose 3 setpoints -> per-field bounds validate+retry -> commit -> proposed_param_*
+ world_* audit) can be exercised end-to-end on a plain ContinuousBundle (B5's
commit_world_delta applies each declared named setpoint directly — value_source=
'proposal' with matching names, so NO derive/override is needed, unlike the
single-magnitude reservoir_control). Physics are deliberately trivial.
"""
from __future__ import annotations

from typing import Any, List

_INPUTS = {
    "release_rate_cms": 400.0,
    "hydropower_target_mw": 800.0,
    "flood_pool_pct": 10.0,
}
_UNITS = {
    "release_rate_cms": "cms",
    "hydropower_target_mw": "MW",
    "flood_pool_pct": "pct",
    "storage": "maf",
}


class ToyMultiReservoir:
    """Three settable setpoint inputs + a storage observation. Toy mass balance."""

    CAPACITY = 1000.0
    DEAD_POOL = 50.0

    def __init__(self) -> None:
        self._storage = 500.0
        self._inputs = dict(_INPUTS)

    def initialize(self, _config_file: str | None = None) -> None:
        self._storage = 500.0
        self._inputs = dict(_INPUTS)

    def update(self) -> None:
        # trivial monthly step: release draws storage down, inflow refills a bit;
        # flood_pool_pct reserves headroom (caps storage). Not calibrated — toy.
        rel = self._inputs["release_rate_cms"]
        cap = self.CAPACITY * (1.0 - self._inputs["flood_pool_pct"] / 100.0)
        self._storage = max(self.DEAD_POOL, min(cap, self._storage - rel * 0.001 + 5.0))

    def get_value(self, name: str) -> List[float]:
        if name == "storage":
            return [self._storage]
        if name in self._inputs:
            return [self._inputs[name]]
        raise KeyError(f"{name!r} is not a readable variable")

    def set_value(self, name: str, value: Any) -> None:
        if name not in self._inputs:
            raise KeyError(f"{name!r} is not a settable reservoir input")
        v = value[0] if isinstance(value, (list, tuple)) else value
        self._inputs[name] = float(v)

    def get_var_units(self, name: str) -> str:
        return _UNITS.get(name, "")

    def get_current_time(self) -> float:
        return 0.0

    def get_component_name(self) -> str:
        return "ToyMultiReservoir(6W-B7 skeleton)"
