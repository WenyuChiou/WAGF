"""BmiEventSource — adapt a BMI-conformant numerical model to WAGF's EventSource.

The Basic Model Interface (BMI, CSDMS; JOSS 2020) is the adopted standard for
coupling numerical models in the earth/hydrologic sciences: each model exposes a
fixed verb set (initialize / update / get_value / set_value / get_var_units /
get_current_time / finalize) so a framework can drive ANY BMI-conformant model
uniformly. WAGF's source Protocols are a *superset* of that verb set, so a
standards-conformant solver is hosted by this ~thin wrapper — WAGF does not
re-implement BMI, it HOSTS a BMI component and adds the governed LLM decision
layer on top (the part BMI structurally cannot express).

This module is generic + domain-vocab-free: the value variable name + unit are
constructor parameters, so the SAME wrapper hosts any scalar-output solver — the
hosted model and its variable names are supplied by the caller under
``examples/<domain>/``.
"""
from __future__ import annotations

from typing import Any, List, Optional, Protocol, runtime_checkable

from .interfaces import Event


@runtime_checkable
class BmiComponent(Protocol):
    """The minimal BMI verb-set BmiEventSource calls. Any object exposing these
    (a real CSDMS/`bmipy.Bmi` model, an FMU shim, or a toy solver) qualifies —
    structural typing, no inheritance required."""

    def update(self) -> None: ...  # advance one model time step

    def get_value(self, name: str) -> Any: ...  # read an output variable

    def get_var_units(self, name: str) -> str: ...

    def get_current_time(self) -> float: ...


def _scalar(value: Any) -> float:
    """BMI get_value may return a numpy array / list / scalar. Reduce to a float
    (first element for a 1-element array) — never silently swallow a shape error."""
    if value is None:
        raise ValueError(
            "BmiEventSource: get_value returned None; a BMI model must return a "
            "numeric scalar or 1-element array, never None (a None here would "
            "otherwise crash float() with an opaque message)."
        )
    if hasattr(value, "__len__") and not isinstance(value, (str, bytes)):
        seq = list(value)
        if len(seq) != 1:
            raise ValueError(
                f"BmiEventSource expected a scalar from get_value, got length {len(seq)}; "
                "pass a per-agent value var or supply a reducer."
            )
        return float(seq[0])
    return float(value)


class BmiEventSource:
    """Wrap a BMI component as a WAGF EventSource. Each draw_events(period) calls
    bmi.update() once, reads the configured value variable, and emits a single
    Event when it exceeds ``event_threshold`` (>= a footprint occurred). Below the
    threshold (e.g. a no-flood year) it emits zero events — exactly the
    ``>=0 events per period`` EventSource contract.

    Satisfies broker.coupling.EventSource structurally.
    """

    def __init__(
        self,
        bmi: BmiComponent,
        value_var: str,
        unit: Optional[str] = None,
        event_threshold: float = 0.0,
    ):
        if not isinstance(bmi, BmiComponent):
            raise TypeError(
                "BmiEventSource requires a BMI-conformant component exposing the "
                "attributes update/get_value/get_var_units/get_current_time "
                "(runtime_checkable Protocol verifies attribute presence only, not "
                "callability — a non-callable attribute would pass here and fail later)"
            )
        self._bmi = bmi
        self._var = value_var
        self._unit = unit if unit is not None else bmi.get_var_units(value_var)
        self._threshold = float(event_threshold)
        # Opportunistic identity read (inc 3, review P0-3): BMI's own identity
        # verb feeds the reproducibility manifest when present. Not required —
        # minimal/toy/FMU shims without it stay valid.
        name_fn = getattr(bmi, "get_component_name", None)
        self._component_name = name_fn() if callable(name_fn) else None

    def draw_events(self, period: int) -> List[Event]:
        self._bmi.update()  # advance the hosted model one step (BMI verb)
        value = _scalar(self._bmi.get_value(self._var))
        if value <= self._threshold:
            return []
        return [Event(event_id=f"{self._var}_t{period}", period=int(period),
                      payload={self._var: value, "intensity": value})]

    def intensity_at(self, agent_id: str, event: Event) -> float:
        return float(event.payload.get(self._var, event.payload.get("intensity", 0.0)))

    def units(self) -> str:
        return self._unit

    def get_provenance(self) -> dict:
        """World-side identity for the reproducibility manifest (review P0-3)."""
        return {
            "source_class": type(self).__name__,
            "component_class": type(self._bmi).__name__,
            "component_name": self._component_name,
            "value_var": self._var,
            "unit": self._unit,
            "event_threshold": self._threshold,
        }


__all__ = ["BmiComponent", "BmiEventSource"]
