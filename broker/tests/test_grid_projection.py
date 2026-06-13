"""Phase 6W-A1 — GridProjector unit + fail-loud tests (deterministic, no LLM/GPU).

Covers the convergent-pattern guarantees: cached weights, nearest/bilinear correctness,
and every fail-loud boundary (CRS, unit, extent, shape, unstructured/zonal hand-back).
See .research/wagf_coupling_IMPLEMENTATION_PLAN_2026-06-12.md (A1).
"""
import numpy as np
import pytest

from broker.coupling.interfaces import Event
from broker.coupling.grid_source import GridEventSource
from broker.coupling.projection import (
    AgentLocations,
    GridProjector,
    GridSpec,
    ProjectionError,
)


def _grid(crs="", unit="m"):
    # 3x3 grid, unit spacing, origin at cell (0,0) centre = (0,0)
    return GridSpec(shape=(3, 3), spacing=(1.0, 1.0), origin=(0.0, 0.0), crs=crs, var="intensity", unit=unit)


def _agents(crs=""):
    # (x, y) world coords -> fractional (row=y, col=x)
    return AgentLocations(coords={"A": (0.0, 0.0), "B": (2.0, 2.0), "C": (0.0, 1.0)}, crs=crs)


_FIELD = [[10.0, 11.0, 12.0],
          [20.0, 21.0, 22.0],
          [30.0, 31.0, 32.0]]


def test_nearest_recovers_cell_values():
    proj = GridProjector(_grid(), _agents(), method="nearest")
    out = proj.project(_FIELD)
    assert out["A"] == 10.0          # (x0,y0) -> row0,col0
    assert out["B"] == 32.0          # (x2,y2) -> row2,col2
    assert out["C"] == 20.0          # (x0,y1) -> row1,col0: confirms y->row, x->col


def test_bilinear_interpolates_between_cells():
    agents = AgentLocations(coords={"M": (0.5, 0.5)})  # x=0.5,y=0.5 -> frac (0.5,0.5)
    proj = GridProjector(_grid(), agents, method="bilinear")
    out = proj.project(_FIELD)
    # 4-corner mean of cells (0,0),(0,1),(1,0),(1,1) = (10+11+20+21)/4
    assert out["M"] == pytest.approx((10 + 11 + 20 + 21) / 4)


def test_weights_built_once_and_cached(monkeypatch):
    proj = GridProjector(_grid(), _agents(), method="nearest")
    calls = {"n": 0}
    orig = proj._build_weights
    monkeypatch.setattr(proj, "_build_weights", lambda: (calls.__setitem__("n", calls["n"] + 1) or orig()))
    proj.project(_FIELD); proj.project(_FIELD)
    assert calls["n"] == 0  # project() never rebuilds; weights cached at construction


def test_crs_mismatch_fails_loud():
    with pytest.raises(ProjectionError, match="CRS mismatch"):
        GridProjector(_grid(crs="EPSG:4326"), _agents(crs="EPSG:3857"), method="nearest")


def test_unit_mismatch_fails_loud():
    with pytest.raises(ProjectionError, match="unit mismatch"):
        GridProjector(_grid(unit="ft"), _agents(), method="nearest", source_units="m")


def test_agent_outside_grid_fails_loud():
    agents = AgentLocations(coords={"OOB": (99.0, 99.0)})
    with pytest.raises(ProjectionError, match="outside the grid extent"):
        GridProjector(_grid(), agents, method="nearest")


def test_field_shape_mismatch_fails_loud():
    proj = GridProjector(_grid(), _agents(), method="nearest")
    with pytest.raises(ProjectionError, match="field shape"):
        proj.project([[1.0, 2.0], [3.0, 4.0]])  # 2x2 != 3x3


def test_zonal_on_points_hands_back():
    with pytest.raises(ProjectionError, match="footprint"):
        GridProjector(_grid(), _agents(), method="zonal")


def test_unknown_method_fails_loud():
    with pytest.raises(ProjectionError, match="method"):
        GridProjector(_grid(), _agents(), method="cubic")


def test_provenance_carries_weight_hash():
    prov = GridProjector(_grid(crs="EPSG:5070"), _agents(crs="EPSG:5070"), method="nearest").get_provenance()
    assert prov["method"] == "nearest"
    assert prov["grid_crs"] == "EPSG:5070"
    assert len(prov["weight_sha256"]) == 16
    assert prov["n_agents"] == 3


def test_empty_agent_locations_fails_loud():
    with pytest.raises(ProjectionError, match="empty"):
        AgentLocations(coords={})


def test_coords_must_be_2_tuples():
    with pytest.raises(ProjectionError, match="2-tuple"):
        AgentLocations(coords={"A": (1.0, 2.0, 3.0)})


def test_crs_asymmetric_fails_loud():
    # one side declares a CRS, the other empty -> almost certainly a forgotten CRS
    with pytest.raises(ProjectionError, match="only one side"):
        GridProjector(_grid(crs="EPSG:4326"), _agents(crs=""), method="nearest")


def test_bilinear_1xN_grid():
    grid = GridSpec(shape=(1, 4), spacing=(1.0, 1.0), origin=(0.0, 0.0), crs="", var="intensity", unit="m")
    agents = AgentLocations(coords={"A": (2.0, 0.0)})  # x=2 -> col2, y=0 -> row0
    proj = GridProjector(grid, agents, method="bilinear")
    assert proj.project([[1.0, 2.0, 3.0, 4.0]])["A"] == pytest.approx(3.0)


def test_bilinear_far_corner():
    agents = AgentLocations(coords={"A": (2.0, 2.0)})  # far corner of the 3x3
    proj = GridProjector(_grid(), agents, method="bilinear")
    assert proj.project(_FIELD)["A"] == pytest.approx(32.0)  # weight lands on cell (2,2)


# --- A2: GridEventSource (gridded EventSource over a GridProjector) ---

def _field_fn(period):
    return _FIELD if period == 1 else None


def _src(**kw):
    proj = GridProjector(_grid(), _agents(), method="nearest")
    return GridEventSource(_field_fn, proj, unit="m", **kw)


def test_grid_source_emits_scalar_summary_and_field():
    # var != "intensity" so the var-keyed aggregate check is meaningful (not a tautology)
    grid = GridSpec(shape=(3, 3), spacing=(1.0, 1.0), origin=(0.0, 0.0), crs="", var="value", unit="m")
    proj = GridProjector(grid, _agents(), method="nearest")
    src = GridEventSource(_field_fn, proj, unit="m", summary_reduce="max")
    ev = src.draw_events(1)
    assert len(ev) == 1
    assert ev[0].payload["value"] == 32.0          # summary under the var name (aggregate consumer key)
    assert ev[0].payload["intensity"] == 32.0      # convenience alias
    assert "field" in ev[0].payload                # field carried for re-projection on a cache miss


def test_grid_source_intensity_varies_by_agent():
    src = _src()
    ev = src.draw_events(1)[0]
    assert src.intensity_at("A", ev) == 10.0   # cell (0,0)
    assert src.intensity_at("B", ev) == 32.0   # cell (2,2)
    assert src.intensity_at("C", ev) == 20.0   # cell (1,0)


def test_grid_source_no_event_when_field_none():
    assert _src().draw_events(2) == []          # field_fn returns None for period 2


def test_grid_source_no_event_below_threshold():
    proj = GridProjector(_grid(), _agents(), method="nearest")
    src = GridEventSource(lambda p: [[0.0] * 3] * 3, proj, unit="m", event_threshold=0.0)
    assert src.draw_events(1) == []             # max 0.0 <= threshold 0.0


def test_grid_source_intensity_at_cache_miss_reprojects():
    src = _src()
    ev2 = Event(event_id="x", period=99, payload={"field": _FIELD})  # not the cached period
    assert src.intensity_at("A", ev2) == 10.0   # re-projects from the carried field


def test_grid_source_scalar_only_payload_fails_loud():
    src = _src()
    ev = Event(event_id="x", period=99, payload={"intensity": 5.0})  # no field carried
    with pytest.raises(ValueError, match="cannot project"):
        src.intensity_at("A", ev)


def test_grid_source_units_and_provenance():
    src = _src()
    assert src.units() == "m"
    prov = src.get_provenance()
    assert prov["source_class"] == "GridEventSource"
    assert prov["projection"]["method"] == "nearest"


def test_grid_source_bad_summary_reduce_fails_loud():
    proj = GridProjector(_grid(), _agents(), method="nearest")
    with pytest.raises(ValueError, match="summary_reduce"):
        GridEventSource(_field_fn, proj, unit="m", summary_reduce="median")


def test_grid_source_same_period_double_draw_no_stale_cache():
    """Regression (code-review): two draw_events for the SAME period with a stateful
    field_fn — intensity_at on the FIRST event must reflect the FIRST field, not the
    later cached one (cache keyed on field identity, not period)."""
    f1 = [[1.0, 1.0, 1.0], [1.0, 1.0, 1.0], [1.0, 1.0, 1.0]]
    f2 = [[9.0, 9.0, 9.0], [9.0, 9.0, 9.0], [9.0, 9.0, 9.0]]
    calls = {"n": 0}

    def ff(period):
        calls["n"] += 1
        return f1 if calls["n"] == 1 else f2

    proj = GridProjector(_grid(), _agents(), method="nearest")
    src = GridEventSource(ff, proj, unit="m")
    ev1 = src.draw_events(5)[0]   # field f1 -> cached
    ev2 = src.draw_events(5)[0]   # same period, field f2 -> cache now f2
    assert src.intensity_at("A", ev1) == 1.0   # re-projects ev1's own field (NOT stale 9.0)
    assert src.intensity_at("A", ev2) == 9.0   # cache hit on the current field
