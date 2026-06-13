"""Phase 6W-A1 — generic grid -> per-agent projection operator.

Maps a 2D scalar field (a hazard-intensity / state surface produced by a hosted
numerical model) to per-agent values, so a gridded coupled model can feed
spatially-distributed agents without a hand-written per-domain projection. This
module is DOMAIN-VOCAB-FREE: the caller (under ``examples/<domain>/``) supplies the
grid metadata, the agent coordinates, the variable name, and the method.

Design (the convergent pattern across BMI/pymt, OpenMI, ESMF/NUOPC, OASIS-MCT,
Mesa-Geo, GEB, NetLogo-GIS):

  * the agent<->cell weight mapping is computed ONCE at construction (the ESMF/OASIS
    "precompute weights at init, reuse every tick" rule) and cached; ``project(field)``
    is then a cheap weighted lookup per period;
  * a bind-time CRS/unit mismatch fails LOUD — never silently interpolate across
    coordinate systems or units;
  * an out-of-extent agent, a wrong-shape field, an unstructured grid, and
    zonal-on-points all RAISE rather than guess. These are the honest boundaries the
    mature couplers also hand back to model code (sub-grid / within-cell
    decomposition and unstructured conservative remap are explicitly NOT built here).

Import-inert beyond the top-level numpy import (numpy is a core dependency). A
flag-OFF run never imports ``broker.coupling``, so this module never loads then.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

_METHODS = ("nearest", "bilinear", "zonal")


class ProjectionError(ValueError):
    """Bind-time / project-time projection failure (CRS, unit, shape, extent, kind)."""


@dataclass(frozen=True)
class GridSpec:
    """A uniform-rectilinear source grid (BMI's base tier).

    ``shape=(nrows, ncols)``; ``spacing=(dy, dx)``; ``origin=(y0, x0)`` is the world
    coordinate of cell ``(0, 0)``'s centre. ``var``/``unit`` let the bind gate
    cross-check the hosted source's declared units. Rectilinear (per-axis coordinate
    vectors) and unstructured grids are out of scope — a researcher supplies their
    own projection there, exactly as today.
    """

    shape: Tuple[int, int]
    spacing: Tuple[float, float]
    origin: Tuple[float, float]
    crs: str   # e.g. "EPSG:5070"; "" disables the CRS gate (toy / local coordinates)
    var: str   # the field variable name (provenance + event payload key)
    unit: str

    def __post_init__(self) -> None:
        if len(self.shape) != 2 or any(int(n) < 1 for n in self.shape):
            raise ProjectionError(f"GridSpec.shape must be 2 positive ints, got {self.shape!r}")
        if len(self.spacing) != 2 or any(float(s) <= 0.0 for s in self.spacing):
            raise ProjectionError(f"GridSpec.spacing must be 2 positive floats, got {self.spacing!r}")
        if not self.unit:
            raise ProjectionError("GridSpec: a numeric field must declare a non-empty unit")

    def hash_key(self) -> str:
        return hashlib.sha256(repr(self).encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class AgentLocations:
    """The destination element set (OpenMI ``IElementSet`` framing): the agents ARE
    the destination. Point coordinates ``(x, y)`` expressed in the grid's CRS."""

    coords: Dict[str, Tuple[float, float]]   # {agent_id: (x, y)}
    crs: str = ""

    def __post_init__(self) -> None:
        if not self.coords:
            raise ProjectionError("AgentLocations.coords is empty")
        bad = [k for k, v in self.coords.items() if len(v) != 2]
        if bad:
            raise ProjectionError(
                f"AgentLocations: coords must be (x, y) 2-tuples; wrong length for {bad[:5]}"
            )

    def hash_key(self) -> str:
        items = sorted((str(k), float(v[0]), float(v[1])) for k, v in self.coords.items())
        return hashlib.sha256(repr((items, self.crs)).encode("utf-8")).hexdigest()[:16]


class GridProjector:
    """Builds + CACHES the agent<->cell weight mapping ONCE at construction; then
    ``project(field_2d) -> {agent_id: value}`` is a weighted lookup per tick.

    ``method`` is a required modeling choice (never auto-picked): ``nearest`` (point
    sample), ``bilinear`` (smooth 4-corner), or ``zonal`` (areal — needs footprints,
    so it RAISES on point coords). ``source_units`` (the hosted source's
    ``units()``) is cross-checked against ``grid_spec.unit`` at bind time.
    """

    def __init__(
        self,
        grid_spec: GridSpec,
        agent_locations: AgentLocations,
        method: str = "nearest",
        source_units: Optional[str] = None,
    ) -> None:
        if method not in _METHODS:
            raise ProjectionError(f"projection method {method!r} not in {_METHODS}")
        if method == "zonal":
            # Fail at the top, before the weight build: areal (zonal) projection needs
            # agent footprint POLYGONS, undefined for point coords.
            raise ProjectionError(
                "method='zonal' needs agent footprint polygons, not point coords "
                "(an areal mean over a zone is undefined for a point); use nearest/bilinear."
            )
        # --- bind-time CRS fail-loud gate (no silent regrid; no asymmetric opt-out) ---
        gcrs, acrs = grid_spec.crs, agent_locations.crs
        if gcrs and acrs:
            if gcrs != acrs:
                raise ProjectionError(
                    f"CRS mismatch: grid {gcrs!r} != agents {acrs!r}; "
                    "reproject the agents before binding (no implicit transform)."
                )
        elif gcrs or acrs:
            # exactly one side declares a CRS -> almost certainly a forgotten CRS, not
            # an intentional opt-out. Refuse rather than silently project unchecked.
            raise ProjectionError(
                f"CRS declared on only one side (grid={gcrs!r}, agents={acrs!r}); "
                "declare both (matching) or set both to '' for local/toy coordinates."
            )
        # --- bind-time unit fail-loud gate ---
        if source_units is not None and source_units != grid_spec.unit:
            raise ProjectionError(
                f"unit mismatch: source units {source_units!r} != grid unit "
                f"{grid_spec.unit!r}; refusing to silently mix (e.g. m vs ft)."
            )
        self.grid_spec = grid_spec
        self.agent_locations = agent_locations
        self.method = method
        self._ids: Tuple[str, ...] = tuple(agent_locations.coords)
        self.cache_key = (grid_spec.hash_key(), agent_locations.hash_key(), method)
        self._idx, self._wts = self._build_weights()   # computed ONCE (bind time)

    def _frac(self, x: float, y: float) -> Tuple[float, float]:
        y0, x0 = self.grid_spec.origin
        dy, dx = self.grid_spec.spacing
        return (y - y0) / dy, (x - x0) / dx   # fractional (row, col)

    def _build_weights(self):
        nr, nc = self.grid_spec.shape
        idx: Dict[str, List[Tuple[int, int]]] = {}
        wts: Dict[str, List[float]] = {}
        oob: List[str] = []
        for aid in self._ids:
            x, y = self.agent_locations.coords[aid]
            fr, fc = self._frac(x, y)
            if fr < 0 or fr > nr - 1 or fc < 0 or fc > nc - 1:
                oob.append(aid)
                continue
            if self.method == "nearest":
                idx[aid] = [(int(round(fr)), int(round(fc)))]
                wts[aid] = [1.0]
            elif self.method == "bilinear":
                idx[aid], wts[aid] = self._bilinear_stencil(fr, fc, nr, nc)
            else:  # zonal
                raise ProjectionError(
                    "method='zonal' needs agent footprint polygons, not point coords "
                    "(an areal mean over a zone is undefined for a point); supply "
                    "footprints or use nearest/bilinear."
                )
        if oob:
            raise ProjectionError(
                f"{len(oob)} agent(s) fall outside the grid extent: {oob[:5]}"
                + (" ..." if len(oob) > 5 else "")
                + " — reproject or extend the grid; refusing to clamp silently."
            )
        return idx, wts

    @staticmethod
    def _bilinear_stencil(fr: float, fc: float, nr: int, nc: int):
        r0 = min(int(np.floor(fr)), nr - 2) if nr > 1 else 0
        c0 = min(int(np.floor(fc)), nc - 2) if nc > 1 else 0
        r1, c1 = min(r0 + 1, nr - 1), min(c0 + 1, nc - 1)
        tr, tc = fr - r0, fc - c0
        cells = [(r0, c0), (r0, c1), (r1, c0), (r1, c1)]
        weights = [(1 - tr) * (1 - tc), (1 - tr) * tc, tr * (1 - tc), tr * tc]
        return cells, weights

    def project(self, field_2d: Sequence[Sequence[float]]) -> Dict[str, float]:
        """Per-tick weighted lookup. ``field_2d`` must match ``grid_spec.shape``."""
        arr = np.asarray(field_2d, dtype=float)
        if arr.shape != tuple(self.grid_spec.shape):
            raise ProjectionError(
                f"field shape {arr.shape} != grid_spec.shape {tuple(self.grid_spec.shape)}"
            )
        out: Dict[str, float] = {}
        for aid in self._ids:
            out[aid] = float(
                sum(arr[r, c] * w for (r, c), w in zip(self._idx[aid], self._wts[aid]))
            )
        return out

    def get_provenance(self) -> Dict[str, object]:
        """World-side identity for the reproducibility manifest (mirrors the existing
        source ``get_provenance`` + a weight-mapping hash)."""
        # json.dumps (not repr) so the manifest hash is stable across Python versions.
        wrepr = json.dumps(
            [[aid, self._idx[aid], self._wts[aid]] for aid in self._ids], sort_keys=True
        )
        return {
            "projector_class": type(self).__name__,
            "method": self.method,
            "grid_shape": list(self.grid_spec.shape),
            "grid_spacing": list(self.grid_spec.spacing),
            "grid_origin": list(self.grid_spec.origin),
            "grid_crs": self.grid_spec.crs,
            "grid_unit": self.grid_spec.unit,
            "weight_sha256": hashlib.sha256(wrepr.encode("utf-8")).hexdigest()[:16],
            "n_agents": len(self._ids),
        }


__all__ = ["GridSpec", "AgentLocations", "GridProjector", "ProjectionError"]
