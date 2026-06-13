"""Phase 6W-A2 — gridded EventSource (GridProjector-backed per-agent intensity).

An ``EventSource`` whose ``draw_events`` carries BOTH a scalar summary of the period's
2D field (so aggregate consumers that read ``event.payload[var]`` keep working) AND the
field itself, and whose ``intensity_at`` is a cached per-agent ``GridProjector`` lookup.

The scalar ``BmiEventSource`` (bmi_source.py) is UNTOUCHED: a gridded coupling selects
THIS class by config, so the scalar event path — and every frozen scalar-coupled run —
stays byte-identical. Lives under ``broker.coupling`` (imported only on a flag-ON
coupled path), so it adds nothing to the frozen default import path.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import numpy as np

from .interfaces import Event
from .projection import GridProjector

_SUMMARY = {"max": np.max, "mean": np.mean, "min": np.min, "sum": np.sum}


class GridEventSource:
    """Wrap a field-producing model. ``field_fn(period) -> 2D array | None`` returns
    the period's field (``None`` / all-<=``event_threshold`` => no event for that
    period). The pre-built ``projector`` (its weights cached at construction) does the
    per-agent intensity lookup. Conforms structurally to ``broker.coupling.EventSource``
    (``draw_events`` / ``intensity_at`` / ``units``).
    """

    def __init__(
        self,
        field_fn: Callable[[int], Any],
        projector: GridProjector,
        unit: str,
        summary_reduce: str = "max",
        event_threshold: float = 0.0,
        field_key: str = "field",
    ) -> None:
        if summary_reduce not in _SUMMARY:
            raise ValueError(f"summary_reduce {summary_reduce!r} not in {tuple(_SUMMARY)}")
        self._field_fn = field_fn
        self._proj = projector
        self._unit = unit
        self._summary = summary_reduce
        self._threshold = float(event_threshold)
        self._field_key = field_key
        # caches the LAST projected field's per-agent result so intensity_at is a dict
        # lookup. Keyed on the field array's identity (NOT the period) so a same-period
        # double draw_events with a stateful field_fn never serves a stale projection
        # for an earlier event — that event carries its own field and re-projects.
        self._last_field_id: Optional[int] = None
        self._last_projected: Dict[str, float] = {}

    def draw_events(self, period: int) -> List[Event]:
        field = self._field_fn(int(period))
        if field is None:
            return []
        arr = np.asarray(field, dtype=float)
        scalar = float(_SUMMARY[self._summary](arr))
        if scalar <= self._threshold:
            return []
        self._last_field_id = id(arr)
        self._last_projected = self._proj.project(arr)   # weight-apply ONCE per period
        var = self._proj.grid_spec.var
        # payload carries BOTH a scalar summary under the var name (so aggregate
        # consumers reading payload[var] / payload["intensity"] keep working) AND the
        # field (so intensity_at can re-project on a cache miss).
        return [
            Event(
                event_id=f"{var}_t{period}",
                period=int(period),
                payload={var: scalar, "intensity": scalar, self._field_key: arr},
            )
        ]

    def intensity_at(self, agent_id: str, event: Event) -> float:
        """Per-agent projected value: a lookup into the cached projection when the
        event matches the cached period, else re-project the event's carried field."""
        field = event.payload.get(self._field_key)
        # Cache hit only when THIS event's field IS the last-projected array (identity),
        # so a stale projection from a later same-period draw_events is never served.
        if (
            field is not None
            and id(field) == self._last_field_id
            and agent_id in self._last_projected
        ):
            return float(self._last_projected[agent_id])
        if field is None:
            raise ValueError(
                f"GridEventSource.intensity_at: event {event.event_id} carries no "
                f"'{self._field_key}' field — cannot project (scalar-only payload?)."
            )
        return float(self._proj.project(field)[agent_id])

    def units(self) -> str:
        return self._unit

    def get_provenance(self) -> Dict[str, Any]:
        return {
            "source_class": type(self).__name__,
            "unit": self._unit,
            "summary_reduce": self._summary,
            "event_threshold": self._threshold,
            "projection": self._proj.get_provenance(),
        }


__all__ = ["GridEventSource"]
