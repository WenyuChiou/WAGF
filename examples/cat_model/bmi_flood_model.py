"""ToyBmiFloodModel — a BMI-conformant flood-stage solver (Phase 6V increment 2).

A *real* (if tiny) numerical model, not a lookup table: it integrates a rainfall
forcing into flood stage with linear-reservoir drainage,

    S[t+1] = max(0, S[t] + R[t] - k * S[t]),   depth = S

and exposes the standard CSDMS Basic Model Interface verb set
(initialize / update / get_value / set_value / get_var_units / get_current_time /
get_time_step / finalize). It needs no `bmipy` install — it conforms to the BMI
*contract* (method names + semantics), which is all `broker.coupling.BmiEventSource`
duck-types against. Swapping a production `bmipy.Bmi` model (LISFLOOD-FP, a CSDMS
component, an FMU shim) in its place changes nothing upstream of the wrapper.

Output variable ``depth`` (ft) matches the key CatBundle.run_pipeline reads, so
``BmiEventSource(ToyBmiFloodModel(...), value_var="depth")`` is a drop-in for
FloodFootprintSource — the financial chain + governance are untouched.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

_OUTPUT = "depth"
_INPUT = "rainfall"


class ToyBmiFloodModel:
    """Linear-reservoir flood-stage model with the standard BMI verb set.

    Deterministic + seed-free: same rainfall schedule -> same depth series, so a
    coupling driven through BmiEventSource stays byte-reproducible.
    """

    def __init__(self, rainfall: Sequence[float], drainage_k: float = 0.4,
                 initial_stage: float = 0.0, dt: float = 1.0):
        if dt <= 0.0:
            raise ValueError(f"dt must be > 0 (got {dt}); update_until would loop forever")
        self._rain = [float(r) for r in rainfall]
        self._k = float(drainage_k)
        self._stage0 = float(initial_stage)
        self._dt = float(dt)
        self._stage = float(initial_stage)
        self._t = 0.0
        self._step = 0
        self._initialized = False

    # -- lifecycle -----------------------------------------------------------
    def initialize(self, config_file: Optional[str] = None) -> None:
        self._stage = self._stage0
        self._t = 0.0
        self._step = 0
        self._initialized = True

    def update(self) -> None:
        if not self._initialized:
            self.initialize()
        forcing = self._rain[self._step] if self._step < len(self._rain) else 0.0
        self._stage = max(0.0, self._stage + forcing - self._k * self._stage)
        self._step += 1
        self._t += self._dt

    def update_until(self, time: float) -> None:
        while self._t < float(time):
            self.update()

    def finalize(self) -> None:
        self._initialized = False

    # -- info ----------------------------------------------------------------
    def get_component_name(self) -> str:
        return "toy-linear-reservoir-flood-stage"

    def get_input_var_names(self) -> List[str]:
        return [_INPUT]

    def get_output_var_names(self) -> List[str]:
        return [_OUTPUT]

    # -- variable getters/setters -------------------------------------------
    def get_var_units(self, name: str) -> str:
        if name == _OUTPUT:
            return "ft"
        if name == _INPUT:
            return "ft"
        raise KeyError(f"unknown variable {name!r}")

    def get_var_type(self, name: str) -> str:
        return "float64"

    def get_value(self, name: str) -> List[float]:
        # BMI returns array-like; a 1-cell grid here (single insured location).
        if name == _OUTPUT:
            return [self._stage]
        if name == _INPUT:
            # step-1: the forcing that DROVE the current state (update() already
            # incremented _step), not the next step's forcing.
            idx = max(0, self._step - 1)
            return [self._rain[idx] if idx < len(self._rain) else 0.0]
        raise KeyError(f"unknown variable {name!r}")

    def set_value(self, name: str, value) -> None:
        """Override the remaining rainfall forcing (drives upstream coupling)."""
        if name != _INPUT:
            raise KeyError(f"{name!r} is not a settable input variable")
        seq = list(value) if hasattr(value, "__len__") else [float(value)]
        self._rain = self._rain[: self._step] + [float(v) for v in seq]

    # -- time ----------------------------------------------------------------
    def get_current_time(self) -> float:
        return self._t

    def get_start_time(self) -> float:
        return 0.0

    def get_end_time(self) -> float:
        return float(len(self._rain)) * self._dt

    def get_time_step(self) -> float:
        return self._dt

    def get_time_units(self) -> str:
        return "yr"


__all__ = ["ToyBmiFloodModel"]
