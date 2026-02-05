"""
Benchmark Registry — Domain-Agnostic Empirical Benchmark Engine.

Provides a generic framework for defining, registering, and comparing
simulation outputs against empirical benchmarks from literature or
survey data.  Part of the SAGE Calibration Protocol.

Key classes:
    :class:`Benchmark` — single empirical benchmark definition
    :class:`BenchmarkCategory` — benchmark classification enum
    :class:`BenchmarkRegistry` — registry + comparison engine
    :class:`BenchmarkComparison` — single benchmark comparison result
    :class:`BenchmarkReport` — complete comparison report with EPI

Usage::

    from broker.validators.calibration.benchmark_registry import (
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
    """Result of comparing one observed rate against an empirical benchmark."""

    benchmark_name: str
    metric: str
    observed: float
    expected_low: float
    expected_high: float
    within_range: bool
    ratio_to_midpoint: float
    deviation_direction: str  # "too_high", "too_low", "ok"
    deviation_magnitude: float  # absolute deviation from nearest bound
    source: str
    category: str = ""
    weight: float = 1.0

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
    """Complete benchmark comparison report with EPI."""

    comparisons: List[BenchmarkComparison] = field(default_factory=list)
    n_within_range: int = 0
    n_total: int = 0
    plausibility_score: float = 0.0
    by_category: Dict[str, float] = field(default_factory=dict)
    missing_metrics: List[str] = field(default_factory=list)

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
        )
