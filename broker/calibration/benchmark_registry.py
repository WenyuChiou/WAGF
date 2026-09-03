"""
Benchmark Registry — Domain-Agnostic Empirical Benchmark Engine.

Provides a generic framework for defining, registering, and comparing
simulation outputs against empirical benchmarks from literature or
survey data.  Part of the WAGF Calibration Protocol.

Moved from ``broker/domains/water/calibration/`` in PR-7 (2026-09) —
this module has no water-domain content, only caller-supplied benchmark
definitions.  The old import path still works via a re-export shim that
warns; see ``broker/domains/water/calibration/benchmark_registry.py``.

TWO EPI FORMULAS EXIST — read this before reporting a number
---------------------------------------------------------------
This registry's :meth:`BenchmarkRegistry.compare` computes what this
module calls ``legacy_epi``: a **tolerance-expanded** weighted pass
rate — the range checked is ``[low*(1-tolerance), high*(1+tolerance)]``
(default ``tolerance=0.3``), and ``observed`` is compared unrounded.

The formula that actually produced every published Paper 3 EPI number
is :func:`validation.metrics.l2_macro.compute_l2_metrics` under
``examples/multi_agent/flood/paper3/analysis/validation/`` — a
**hard-range** weighted pass rate (no tolerance expansion) with the
observed value **rounded to 4 decimal places** before the range check.
The two formulas can disagree on the same observations. See
``docs/guides/calibration_guide.md`` §"Two EPI formulas" for the exact
difference computed on a shared fixture, and use the ``formula_version``
field on every :class:`BenchmarkReport` to know which one you are
holding — never report an EPI number without it.

EPI IS A PASS RATE — report it, do not optimise against it
------------------------------------------------------------
``BenchmarkReport.plausibility_score`` counts how many benchmarks
landed inside their band, weighted.  Over five benchmarks it can take
five values, so ``1 - EPI`` is a staircase: flat almost everywhere,
with no information about which direction a parameter should move
until some metric crosses a bound.  A search handed that objective
reports whatever point it happened to start at.

Two continuous companions, for two different jobs:

``BenchmarkReport.band_distance``
    How far outside the band each observation sits, in band widths
    (``0.0`` inside), weight-averaged.  REPORT this — it says by how
    much a failing metric failed.  Do not search on it: it is flat
    across the entire interior of the bands, so a search reaching the
    band stops learning and returns its starting point.

``BenchmarkReport.midpoint_distance``
    Distance from the centre of each published range, in half-ranges
    (``1.0`` at a bound), weight-averaged.  SEARCH on this — it has a
    gradient everywhere.  Its zero point is a tie-break, not a truth
    claim: a benchmark states a range, and every point inside that
    range is equally supported by its source.  Returns ``float("nan")``
    — not ``0.0`` — when zero benchmarks were compared: ``0.0`` is this
    quantity's *best* value, and reporting it for an empty evaluation
    would read as "perfectly calibrated" instead of "nothing was
    measured".

Key classes:
    :class:`Benchmark` — single empirical benchmark definition
    :class:`BenchmarkCategory` — benchmark classification enum
    :class:`BenchmarkRegistry` — registry + comparison engine
    :class:`BenchmarkComparison` — single benchmark comparison result
    :class:`BenchmarkReport` — complete comparison report with EPI
        (``formula_version="legacy_epi_v1"`` on every report)

Usage::

    from broker.calibration.benchmark_registry import (
        BenchmarkRegistry, Benchmark, BenchmarkCategory,
    )

    registry = BenchmarkRegistry()
    registry.load_from_yaml("configs/calibration.yaml")
    # or register individually:
    registry.register(Benchmark(
        name="Insurance Uptake",
        metric="insurance_rate",
        rate_low=0.30, rate_high=0.50,
        source="Kousky (2017)",
    ))

    observed = {"insurance_rate": 0.42, "elevation_rate": 0.07}
    report = registry.compare(observed, tolerance=0.3)
    print(f"EPI = {report.plausibility_score:.3f}")

Design:
    - Domain-agnostic: all benchmark definitions come from callers
    - Weighted EPI: benchmarks can carry different weights
    - Category-level breakdown: aggregate, conditional, temporal, etc.
    - Tolerance-based range checking: observed within [low*(1-tol), high*(1+tol)]
    - Deviation direction and magnitude for calibration feedback

References:
    Windrum et al. (2007) — empirical validation of agent-based models
    Grimm et al. (2005) — pattern-oriented modelling
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BenchmarkCategory(str, Enum):
    """Classification of empirical benchmarks."""

    AGGREGATE = "aggregate"
    """Population-level rates (e.g., insurance uptake %)."""

    CONDITIONAL = "conditional"
    """Event-conditional rates (e.g., inaction rate post-flood)."""

    TEMPORAL = "temporal"
    """Time-series patterns (e.g., adoption curve shape)."""

    DEMOGRAPHIC = "demographic"
    """Group-difference patterns (e.g., MG-NMG gap)."""

    DISTRIBUTIONAL = "distributional"
    """Distribution shape features (e.g., skew, kurtosis)."""


# ---------------------------------------------------------------------------
# Benchmark dataclass
# ---------------------------------------------------------------------------

@dataclass
class Benchmark:
    """A single empirical benchmark for aggregate behavior.

    Parameters
    ----------
    name : str
        Human-readable benchmark name.
    metric : str
        Key matching the output of ``compute_metrics_fn``.
    rate_low : float
        Lower bound of empirical range.
    rate_high : float
        Upper bound of empirical range.
    source : str
        Literature citation.
    description : str
        Detailed description of what is measured.
    category : BenchmarkCategory
        Classification (aggregate, conditional, etc.).
    weight : float
        Weight in EPI computation (default 1.0).
    required : bool
        If True, absence of this metric in observed data is flagged.
    """

    name: str
    metric: str
    rate_low: float
    rate_high: float
    source: str
    description: str = ""
    category: BenchmarkCategory = BenchmarkCategory.AGGREGATE
    weight: float = 1.0
    required: bool = False

    def __post_init__(self) -> None:
        if self.rate_low > self.rate_high:
            raise ValueError(
                f"Benchmark '{self.name}': rate_low ({self.rate_low}) > "
                f"rate_high ({self.rate_high})"
            )
        if self.weight < 0:
            raise ValueError(
                f"Benchmark '{self.name}': weight must be non-negative"
            )

    @property
    def midpoint(self) -> float:
        """Midpoint of the empirical range."""
        return (self.rate_low + self.rate_high) / 2

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> Benchmark:
        """Construct from a dictionary (e.g., parsed from YAML)."""
        category = d.get("category", "aggregate")
        if isinstance(category, str):
            category = BenchmarkCategory(category)
        return cls(
            name=d["name"],
            metric=d["metric"],
            rate_low=float(d["rate_low"]),
            rate_high=float(d["rate_high"]),
            source=d.get("source", ""),
            description=d.get("description", ""),
            category=category,
            weight=float(d.get("weight", 1.0)),
            required=bool(d.get("required", False)),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "metric": self.metric,
            "rate_low": self.rate_low,
            "rate_high": self.rate_high,
            "source": self.source,
            "description": self.description,
            "category": self.category.value,
            "weight": self.weight,
            "required": self.required,
        }


# ---------------------------------------------------------------------------
# Comparison result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkComparison:
    """Result of comparing one observed rate against an empirical benchmark.

    ``expected_low`` / ``expected_high`` are the benchmark's own bounds.
    ``effective_low`` / ``effective_high`` are the bounds actually used
    for the pass/fail decision, i.e. widened by ``tolerance``; the two
    pairs differ whenever ``tolerance > 0``, and ``deviation_magnitude``
    is measured against the *effective* pair.
    """

    benchmark_name: str
    metric: str
    observed: float
    expected_low: float
    expected_high: float
    within_range: bool
    ratio_to_midpoint: float
    deviation_direction: str  # "too_high", "too_low", "ok"
    deviation_magnitude: float  # absolute deviation from nearest effective bound
    source: str
    category: str = ""
    weight: float = 1.0
    tolerance: float = 0.0
    effective_low: Optional[float] = None
    effective_high: Optional[float] = None

    def __post_init__(self) -> None:
        # Older callers construct comparisons without the effective
        # bounds; derive them from the raw bounds + tolerance so
        # band_distance always has a width to divide by.
        if self.effective_low is None:
            self.effective_low = self.expected_low * (1 - self.tolerance)
        if self.effective_high is None:
            self.effective_high = self.expected_high * (1 + self.tolerance)

    @property
    def band_width(self) -> float:
        """Width of the band the pass/fail decision actually used."""
        return float(self.effective_high) - float(self.effective_low)

    @property
    def band_distance(self) -> float:
        """How far outside the band the observation sits, in band widths.

        ``0.0`` inside the band; ``1.0`` means "one whole band width
        outside it".  Continuous *outside* the band, flat inside it —
        which makes it the right thing to REPORT ("is this plausible,
        and if not, by how much") and the wrong thing to SEARCH on: the
        whole interior is a plateau, so a search that reaches the band
        stops learning anything and returns wherever it happened to be.
        Use :attr:`midpoint_distance` for that.

        A zero-width band (``rate_low == rate_high`` and no tolerance)
        has no scale to normalise by, so the raw deviation is returned
        instead of dividing by zero.
        """
        width = self.band_width
        if width <= 0:
            return float(self.deviation_magnitude)
        return float(self.deviation_magnitude) / width

    @property
    def expected_midpoint(self) -> float:
        """Centre of the benchmark's own range (before any tolerance widening)."""
        return (float(self.expected_low) + float(self.expected_high)) / 2.0

    @property
    def midpoint_distance(self) -> float:
        """Distance from the benchmark's central value, in half-ranges.

        ``0.0`` at the centre of the published range, ``1.0`` at either
        published bound, above 1 outside it.  Independent of
        ``tolerance`` — the widening affects what counts as a pass, not
        where the literature's central estimate sits.

        This is the quantity to hand a parameter search.  It has a
        gradient everywhere, including inside the band, so the search
        keeps moving instead of stopping at the first parameters that
        clear the bound.

        Reading it needs one caveat, and it matters: a benchmark states
        a RANGE, so every point inside the range is equally supported by
        the source.  Driving this number to zero picks the most central
        of the acceptable points; it does not make the fit "more
        correct" than a point near a bound.  Report
        :attr:`band_distance` and the pass rate for the plausibility
        claim, and treat this as the tie-break that makes the search
        well-posed.
        """
        half_width = (float(self.expected_high) - float(self.expected_low)) / 2.0
        deviation = abs(float(self.observed) - self.expected_midpoint)
        if half_width <= 0:
            return deviation
        return deviation / half_width

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "benchmark": self.benchmark_name,
            "metric": self.metric,
            "observed": round(self.observed, 4),
            "expected_range": f"[{self.expected_low:.3f}, {self.expected_high:.3f}]",
            "within_range": self.within_range,
            "ratio_to_midpoint": round(self.ratio_to_midpoint, 3),
            "deviation_direction": self.deviation_direction,
            "deviation_magnitude": round(self.deviation_magnitude, 4),
            "source": self.source,
            "category": self.category,
            "weight": self.weight,
        }


@dataclass
class BenchmarkReport:
    """Complete benchmark comparison report with EPI.

    ``formula_version`` is always ``"legacy_epi_v1"`` — this registry's
    tolerance-expanded, unrounded formula.  It is NOT the formula that
    produced published Paper 3 numbers (see module docstring); carry
    this field alongside any EPI number you report so a reader can tell
    which formula produced it.

    ``plausibility_score`` (EPI) is a weighted PASS RATE: report it, do
    not optimise against it.  With five benchmarks it can take five
    values, so ``1 - EPI`` is flat almost everywhere and a search
    reading it has nothing to descend.  Use :attr:`band_distance` as
    the objective and keep the pass rate as the reported outcome.
    """

    comparisons: List[BenchmarkComparison] = field(default_factory=list)
    n_within_range: int = 0
    n_total: int = 0
    plausibility_score: float = 0.0
    by_category: Dict[str, float] = field(default_factory=dict)
    missing_metrics: List[str] = field(default_factory=list)
    formula_version: str = "legacy_epi_v1"
    tolerance: float = 0.0

    @property
    def band_distance(self) -> float:
        """Weight-averaged :attr:`BenchmarkComparison.band_distance`.

        ``0.0`` when every evaluated metric sits inside its band; above
        zero it says, in band widths, how far out the population is on
        average.  This is the number to REPORT next to the pass rate:
        it says by how much a failing metric failed.

        It is flat across the whole interior of the bands, so it is not
        a search objective — see :attr:`midpoint_distance`.

        ``0.0`` also when nothing evaluated — check ``n_total`` before
        reading a zero as "everything passed". This property stays
        ``0.0`` on an empty report deliberately: it is REPORTED, not
        searched, so an empty report reads as the plausibility claim
        "nothing failed" rather than as a loss a search could exploit
        by evaluating nothing. See :attr:`midpoint_distance` for the
        objective, which does not make that same choice.
        """
        total_weight = sum(c.weight for c in self.comparisons)
        if total_weight <= 0:
            return 0.0
        return sum(c.weight * c.band_distance for c in self.comparisons) / total_weight

    @property
    def midpoint_distance(self) -> float:
        """Weight-averaged :attr:`BenchmarkComparison.midpoint_distance`.

        The search objective: continuous everywhere, ``0.0`` only when
        every metric sits at the centre of its published range, ``1.0``
        when the average metric sits on a bound.  See the per-comparison
        docstring for what driving it to zero does and does not claim.

        Returns ``float("nan")`` when nothing was evaluated (zero
        comparisons, or every comparison carries zero weight) — NOT
        ``0.0``. ``0.0`` here is this objective's *best* possible value
        ("every scored metric sits at its band centre"); handing that
        back when nothing was scored would tell a search "nothing to
        improve" instead of "something is broken upstream" — exactly
        inverted from what an empty evaluation means. A caller that
        feeds this straight to
        :func:`~broker.calibration.optimize.optimize_parameters` gets
        the refusal already built for non-finite losses (see
        ``_evaluate`` there): a loud stop naming the parameters that
        produced an empty report, rather than a search that silently
        settles on having evaluated nothing. Use :attr:`band_distance`
        instead if you want a REPORTED quantity that stays ``0.0`` on
        an empty report.
        """
        total_weight = sum(c.weight for c in self.comparisons)
        if total_weight <= 0:
            return float("nan")
        return sum(
            c.weight * c.midpoint_distance for c in self.comparisons
        ) / total_weight

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "n_benchmarks_evaluated": self.n_total,
            "n_within_range": self.n_within_range,
            "plausibility_score": round(self.plausibility_score, 4),
            "by_category": {
                k: round(v, 4) for k, v in self.by_category.items()
            },
            "missing_metrics": self.missing_metrics,
            "comparisons": [c.to_dict() for c in self.comparisons],
            "formula_version": self.formula_version,
        }

    def save_json(self, path: Union[str, Path]) -> None:
        """Save report to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @property
    def out_of_range(self) -> List[BenchmarkComparison]:
        """Return comparisons that are outside the acceptable range."""
        return [c for c in self.comparisons if not c.within_range]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class BenchmarkRegistry:
    """Domain-agnostic benchmark registry and comparison engine.

    Holds a collection of :class:`Benchmark` definitions and provides
    methods to compare observed metric values against them, computing
    per-benchmark pass/fail and an overall Empirical Plausibility Index
    (EPI).

    Parameters
    ----------
    benchmarks : list of Benchmark, optional
        Initial benchmarks to register.
    """

    def __init__(
        self, benchmarks: Optional[List[Benchmark]] = None
    ) -> None:
        self._benchmarks: Dict[str, Benchmark] = {}
        if benchmarks:
            self.register_many(benchmarks)

    def register(self, benchmark: Benchmark) -> None:
        """Register a single benchmark.

        Parameters
        ----------
        benchmark : Benchmark
            Benchmark to register.  If a benchmark with the same metric
            already exists, it is overwritten with a warning.
        """
        if benchmark.metric in self._benchmarks:
            logger.warning(
                "Overwriting benchmark for metric '%s' (was: %s, now: %s)",
                benchmark.metric,
                self._benchmarks[benchmark.metric].name,
                benchmark.name,
            )
        self._benchmarks[benchmark.metric] = benchmark

    def register_many(self, benchmarks: List[Benchmark]) -> None:
        """Register multiple benchmarks at once."""
        for bm in benchmarks:
            self.register(bm)

    def load_from_yaml(self, path: Union[str, Path]) -> None:
        """Load benchmarks from a YAML file.

        Expects either:
        - Top-level ``benchmarks`` key containing a list of benchmark dicts
        - Top-level ``calibration.benchmarks`` key (nested under calibration)

        Parameters
        ----------
        path : str or Path
            Path to YAML file.
        """
        try:
            import yaml
        except ImportError:
            raise ImportError(
                "PyYAML is required for YAML loading: pip install pyyaml"
            )
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # Support nested calibration.benchmarks or top-level benchmarks
        bm_list = None
        if isinstance(data, dict):
            if "benchmarks" in data:
                bm_list = data["benchmarks"]
            elif "calibration" in data and isinstance(data["calibration"], dict):
                bm_list = data["calibration"].get("benchmarks", [])

        if not bm_list:
            logger.warning("No benchmarks found in %s", path)
            return

        for bm_dict in bm_list:
            self.register(Benchmark.from_dict(bm_dict))

        logger.info("Loaded %d benchmarks from %s", len(bm_list), path)

    def load_from_dict(self, data: Dict[str, Any]) -> None:
        """Load benchmarks from an already-parsed config dict.

        Supports same structure as :meth:`load_from_yaml`.
        """
        bm_list = None
        if "benchmarks" in data:
            bm_list = data["benchmarks"]
        elif "calibration" in data and isinstance(data["calibration"], dict):
            bm_list = data["calibration"].get("benchmarks", [])

        if not bm_list:
            return

        for bm_dict in bm_list:
            self.register(Benchmark.from_dict(bm_dict))

    @property
    def metrics(self) -> List[str]:
        """List of registered metric names."""
        return list(self._benchmarks.keys())

    @property
    def benchmarks(self) -> List[Benchmark]:
        """List of registered benchmarks."""
        return list(self._benchmarks.values())

    def __len__(self) -> int:
        return len(self._benchmarks)

    def __contains__(self, metric: str) -> bool:
        return metric in self._benchmarks

    def get(self, metric: str) -> Optional[Benchmark]:
        """Get benchmark by metric name."""
        return self._benchmarks.get(metric)

    # -------------------------------------------------------------------
    # Comparison
    # -------------------------------------------------------------------

    def compare(
        self,
        observed: Dict[str, float],
        tolerance: float = 0.3,
    ) -> BenchmarkReport:
        """Compare observed metrics against registered benchmarks.

        Parameters
        ----------
        observed : dict
            Mapping of metric name -> observed value.
        tolerance : float
            Tolerance factor for range checking.  An observed value
            within ``[low * (1 - tol), high * (1 + tol)]`` passes.

        Returns
        -------
        BenchmarkReport
            Full comparison report with EPI score.
        """
        comparisons: List[BenchmarkComparison] = []
        missing: List[str] = []

        for metric, bm in self._benchmarks.items():
            if metric not in observed:
                if bm.required:
                    missing.append(metric)
                continue

            obs = observed[metric]
            comp = self._compare_single(bm, obs, tolerance)
            comparisons.append(comp)

        # Compute overall EPI (weighted)
        total_weight = sum(c.weight for c in comparisons)
        if total_weight > 0:
            weighted_pass = sum(
                c.weight for c in comparisons if c.within_range
            )
            epi = weighted_pass / total_weight
        else:
            epi = 0.0

        # Per-category EPI
        by_category: Dict[str, float] = {}
        cat_groups: Dict[str, List[BenchmarkComparison]] = {}
        for c in comparisons:
            cat_groups.setdefault(c.category, []).append(c)
        for cat, group in cat_groups.items():
            cat_weight = sum(g.weight for g in group)
            if cat_weight > 0:
                cat_pass = sum(g.weight for g in group if g.within_range)
                by_category[cat] = cat_pass / cat_weight
            else:
                by_category[cat] = 0.0

        return BenchmarkReport(
            comparisons=comparisons,
            n_within_range=sum(1 for c in comparisons if c.within_range),
            n_total=len(comparisons),
            plausibility_score=epi,
            by_category=by_category,
            missing_metrics=missing,
            tolerance=tolerance,
        )

    def compute_epi(
        self,
        observed: Dict[str, float],
        tolerance: float = 0.3,
    ) -> float:
        """Compute weighted Empirical Plausibility Index.

        Convenience method — equivalent to
        ``self.compare(observed, tolerance).plausibility_score``.
        """
        return self.compare(observed, tolerance).plausibility_score

    # -------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------

    @staticmethod
    def _compare_single(
        bm: Benchmark,
        observed: float,
        tolerance: float,
    ) -> BenchmarkComparison:
        """Compare a single observed value against one benchmark."""
        low_bound = bm.rate_low * (1 - tolerance)
        high_bound = bm.rate_high * (1 + tolerance)
        within = low_bound <= observed <= high_bound

        midpoint = bm.midpoint
        ratio = observed / midpoint if midpoint > 0 else 0.0

        # Deviation direction and magnitude
        if observed < low_bound:
            direction = "too_low"
            magnitude = low_bound - observed
        elif observed > high_bound:
            direction = "too_high"
            magnitude = observed - high_bound
        else:
            direction = "ok"
            magnitude = 0.0

        return BenchmarkComparison(
            benchmark_name=bm.name,
            metric=bm.metric,
            observed=observed,
            expected_low=bm.rate_low,
            expected_high=bm.rate_high,
            within_range=within,
            ratio_to_midpoint=ratio,
            deviation_direction=direction,
            deviation_magnitude=magnitude,
            source=bm.source,
            category=bm.category.value,
            weight=bm.weight,
            tolerance=tolerance,
            effective_low=low_bound,
            effective_high=high_bound,
        )
