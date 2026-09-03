"""PR-7 first calibration-optimizer workload: no LLM, no ABM run, < 1 second.

Searches ``PARAMETRIC_CALIBRATION["base_rates"]`` (four numbers — the
per flood-zone x tenure marginal adoption rate) against
``examples/multi_agent/flood/paper3/analysis/empirical_benchmarks.FLOOD_BENCHMARKS``
using :func:`broker.calibration.optimize.optimize_parameters`. The
"simulation" is :func:`parametric_decider.aggregate_rates` — a
closed-form expectation over a small synthetic household population,
not a multi-year ABM run, so this is deliberately a fast smoke-level
demonstration of the optimizer + held-out-reporting machinery, not a
recalibration of the real Paper 3 parametric decider.

Three numbers, and what each "0.0" means
-----------------------------------------
The **objective** is a weighted mean *midpoint* distance: for each
benchmark, how far the simulated rate sits from the centre of the
published range, measured in half-ranges (``1.0`` = on a published
bound). It is continuous everywhere, so the search always has a
direction to move in.

It is deliberately NOT ``1 - EPI``. EPI is a weighted pass rate over a
handful of benchmarks, so ``1 - EPI`` takes a handful of values and is
flat everywhere in between: a search reading it gets no signal until
some metric crosses a bound, and reports whatever point it started at.
That is exactly what this script did before the PR-7 review — it
printed "distance 0.615 -> 0.0" while returning the untouched midpoint
of every bound.

Nor is it the band distance (0 inside the band, growing outside). That
one is honest about what a benchmark claims, but it is flat across the
whole band interior — and the starting point of this search already
sits inside every band, so a search reading it also returns its
starting point. Measured, not assumed: with the band distance as
objective this run ends ``search_moved: false``.

So read the three reported quantities differently:

* ``*_midpoint_distance`` (the objective) — 0.0 would mean every metric
  sits at the centre of its published range. Being closer to the centre
  is NOT better-supported by the source: a benchmark states a range,
  and every point inside it is equally consistent with the citation.
  The centre is a tie-break that makes the search well-posed, nothing
  more.
* ``*_band_distance = 0.0`` — every evaluated metric is inside its
  (tolerance-widened) band. This is the plausibility statement. It does
  not say the fit is tight.
* ``epi_pass_rate_* = 1.0`` — the same statement as a weighted pass
  rate. Reported, never optimised against.

The band checks use ``tolerance=0.3``, so the band checked for e.g.
[0.30, 0.50] is [0.21, 0.65] — 44 percentage points wide. A number
inside a window that wide is "not implausible", which is a much weaker
claim than "calibrated".

Usage::

    python examples/multi_agent/flood/parametric/calibrate_parametric.py [--out DIR]

Writes ``calibration_result.json`` to ``--out`` (default: this file's
directory).
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _find_project_root(marker: str = "pyproject.toml") -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / marker).exists():
            return parent
    raise RuntimeError(f"could not locate project root (no {marker} found)")


_PROJECT_ROOT = _find_project_root()
_FLOOD_DIR = Path(__file__).resolve().parents[1]  # examples/multi_agent/flood
for _p in (str(_PROJECT_ROOT), str(_FLOOD_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from broker.calibration.benchmark_registry import (  # noqa: E402
    BenchmarkRegistry,
    BenchmarkReport,
)
from broker.calibration.optimize import (  # noqa: E402
    OptimizeResult,
    optimize_parameters,
    split_targets,
)
from paper3.analysis.empirical_benchmarks import FLOOD_BENCHMARKS  # noqa: E402
from parametric.parametric_decider import (  # noqa: E402
    PARAMETRIC_CALIBRATION,
    aggregate_rates,
)

# Which benchmark table this run used. Two tables in this repo define
# ranges for overlapping metric names and disagree on five of them (see
# docs/guides/calibration_guide.md and broker.calibration.benchmark_diff);
# a plausibility number that does not name its table is not checkable.
BENCHMARK_SOURCE = "examples.multi_agent.flood.paper3.analysis.empirical_benchmarks.FLOOD_BENCHMARKS"

# Band-check tolerance. Both the objective and the reported pass rate
# use the widened band, so this belongs in the output next to them.
TOLERANCE = 0.3

OBJECTIVE_KIND = "weighted_mean_midpoint_distance"
OBJECTIVE_DEFINITION = (
    "per benchmark: |observed - (rate_low + rate_high)/2| divided by "
    "(rate_high - rate_low)/2, so 0 at the centre of the published range "
    "and 1 on either published bound; then the benchmark-weighted mean "
    "across benchmarks. Tolerance-independent. Chosen over the band "
    "distance (0 inside the widened band) because that one is flat "
    "across the band interior, and this search starts inside every "
    "band — with it as objective the search does not move at all."
)

# The band/tolerance convention shared by the objective and the pass
# rate. Read by broker.tools.calibrate when this module is used as a
# --objective-module, so a written result can never be detached from
# the formula that produced it.
FORMULA_VERSION = "legacy_epi_v1"
EPI_DERIVED = True

# The metrics `aggregate_rates` can actually speak to (see its
# docstring) — the calibration surface is limited to base_rates, so we
# only search benchmarks this surface influences.
_SPEAKABLE_METRICS = {"insurance_rate", "insurance_rate_all", "elevation_rate", "buyout_rate"}


def _synthetic_population(seed: int = 42, n: int = 240) -> List[Dict[str, Any]]:
    """Deterministic synthetic household population spanning the four
    (flood-prone x tenure) groups in roughly realistic proportions."""
    import random

    rng = random.Random(seed)
    zones_prone = ["HIGH", "MEDIUM"]
    zones_safe = ["LOW"]
    population: List[Dict[str, Any]] = []
    for i in range(n):
        tenure = "Owner" if rng.random() < 0.65 else "Renter"
        flood_prone = rng.random() < 0.5
        zone = rng.choice(zones_prone) if flood_prone else rng.choice(zones_safe)
        # Flood count correlated with proneness so the elevate/buyout
        # gates (min_flood_count 2 / 3) actually admit some agents.
        flood_count = rng.choices([0, 1, 2, 3, 4], weights=[3, 3, 2, 1, 1] if flood_prone else [8, 1, 1, 0, 0])[0]
        population.append({"tenure": tenure, "flood_zone": zone, "flood_count": flood_count})
    return population


def _make_registry(metric_names: set) -> BenchmarkRegistry:
    benchmarks = [b for b in FLOOD_BENCHMARKS if b.metric in metric_names]
    return BenchmarkRegistry(benchmarks=benchmarks)


def _observed_for(
    population: List[Dict[str, Any]],
    flat_base_rates: Dict[str, float],
) -> Dict[str, float]:
    calibration = copy.deepcopy(PARAMETRIC_CALIBRATION)
    calibration["base_rates"].update(flat_base_rates)
    return aggregate_rates(calibration, population)


def _report_for(
    registry: BenchmarkRegistry,
    population: List[Dict[str, Any]],
    flat_base_rates: Dict[str, float],
) -> Tuple[Dict[str, float], BenchmarkReport]:
    observed = _observed_for(population, flat_base_rates)
    return observed, registry.compare(observed, tolerance=TOLERANCE)


def _build_objective(registry: BenchmarkRegistry, population: List[Dict[str, Any]]):
    """Continuous distance to the benchmark centres — see the module docstring."""

    def objective(flat_base_rates: Dict[str, float]) -> float:
        observed, report = _report_for(registry, population, flat_base_rates)
        # BenchmarkReport.midpoint_distance is NaN, not 0.0, when zero
        # benchmarks were scored (see that property's docstring) — NaN
        # is non-finite, so optimize_parameters._evaluate would already
        # raise on it. This assert fires first and names WHY: the
        # registry's metric names have stopped matching what
        # aggregate_rates actually produced.
        assert report.n_total > 0, (
            f"midpoint_distance objective evaluated with zero benchmarks "
            f"scored: registry defines {sorted(registry.metrics)} but "
            f"observed only has {sorted(observed)}. Fix the registry / "
            f"metric-name mismatch rather than letting this run silently "
            f"report a NaN loss."
        )
        return report.midpoint_distance

    return objective


def _metric_rows(
    registry: BenchmarkRegistry,
    population: List[Dict[str, Any]],
    params_before: Dict[str, float],
    params_after: Dict[str, float],
    split_label: str,
) -> List[Dict[str, Any]]:
    """Per-metric (band, observed, deviation) table for one side of the split."""
    _, report_before = _report_for(registry, population, params_before)
    _, report_after = _report_for(registry, population, params_after)
    before_by_metric = {c.metric: c for c in report_before.comparisons}

    rows: List[Dict[str, Any]] = []
    for comp in sorted(report_after.comparisons, key=lambda c: c.metric):
        prev = before_by_metric.get(comp.metric)
        rows.append({
            "metric": comp.metric,
            "split": split_label,
            "benchmark": comp.benchmark_name,
            "rate_low": comp.expected_low,
            "rate_high": comp.expected_high,
            "weight": comp.weight,
            "tolerance": comp.tolerance,
            "band_low": round(float(comp.effective_low), 6),
            "band_high": round(float(comp.effective_high), 6),
            "band_midpoint": round(comp.expected_midpoint, 6),
            "observed_before": round(prev.observed, 6) if prev else None,
            "observed_after": round(comp.observed, 6),
            "midpoint_distance_before": (
                round(prev.midpoint_distance, 6) if prev else None
            ),
            "midpoint_distance_after": round(comp.midpoint_distance, 6),
            "band_distance_before": round(prev.band_distance, 6) if prev else None,
            "band_distance_after": round(comp.band_distance, 6),
            "within_band_before": prev.within_range if prev else None,
            "within_band_after": comp.within_range,
        })
    return rows


DEFAULT_MAX_EVALS = 400
"""Enough budget for scipy's Nelder-Mead to converge on 4 parameters.

The previous default, 40, exhausted ``maxfev`` first and reported
``converged: False`` — a partially-run search whose parameters are hard
to read as anything.  253 evaluations of this closed-form surface take
about 0.05 s, so there is no reason to stop early.
"""


def run(
    out_dir: Path,
    seed: int = 42,
    max_evals: int = DEFAULT_MAX_EVALS,
) -> Dict[str, Any]:
    started = time.monotonic()
    population = _synthetic_population(seed=seed)

    targets = {
        b.metric: b.midpoint for b in FLOOD_BENCHMARKS
        if b.metric in _SPEAKABLE_METRICS
    }
    default_flat = dict(PARAMETRIC_CALIBRATION["base_rates"])
    observed_at_defaults = _observed_for(population, default_flat)

    # `observed=` makes the split refuse a held-out metric whose model
    # output is bit-identical to an in-sample one — the aliasing this
    # script shipped with before the PR-7 review.
    split = split_targets(
        targets, holdout_fraction=0.25, seed=seed, observed=observed_at_defaults,
    )

    in_sample_registry = _make_registry(set(split.in_sample))
    held_out_registry = _make_registry(set(split.held_out))

    in_sample_objective = _build_objective(in_sample_registry, population)
    held_out_objective = _build_objective(held_out_registry, population)

    _, before_in_report = _report_for(in_sample_registry, population, default_flat)
    _, before_held_report = _report_for(held_out_registry, population, default_flat)
    before_in_sample = before_in_report.midpoint_distance
    before_held_out = (
        before_held_report.midpoint_distance if split.held_out else None
    )

    space = {name: (0.001, 0.9) for name in PARAMETRIC_CALIBRATION["base_rates"]}

    result: OptimizeResult = optimize_parameters(
        objective=in_sample_objective,
        space=space,
        method="nelder-mead",
        max_evals=max_evals,
        seed=seed,
        held_out_objective=held_out_objective if split.held_out else None,
        formula_version=FORMULA_VERSION,
    )

    best_params = dict(result.best_params)
    _, after_in_report = _report_for(in_sample_registry, population, best_params)
    _, after_held_report = _report_for(held_out_registry, population, best_params)

    elapsed = time.monotonic() - started

    benchmark_rows = (
        _metric_rows(in_sample_registry, population, default_flat, best_params, "in_sample")
        + _metric_rows(held_out_registry, population, default_flat, best_params, "held_out")
    )

    # Caveats that belong IN the result JSON next to params_after, not
    # left for a reader to re-derive from the other fields. Generalises
    # OptimizeResult.warning (the search's own "did I move" caveat,
    # which optimize_parameters already knows how to compute) into a
    # list this script can also append to, because the two conditions
    # below are things only THIS script's objective knows — how many
    # metrics fed the search vs. how many parameters it searched, and
    # per-metric held-out fit.
    warnings: List[str] = []
    if result.warning is not None:
        warnings.append(result.warning)
    n_metrics_in_sample = len(split.in_sample)
    n_parameters = len(space)
    if n_metrics_in_sample < n_parameters:
        warnings.append(
            f"n_metrics_in_sample ({n_metrics_in_sample}) < n_parameters "
            f"({n_parameters}): the objective does not identify the "
            f"parameters; params_after is one satisfying combination, "
            f"not an estimate"
        )
    held_out_outside_published_range = sorted(
        c.metric for c in after_held_report.comparisons
        if c.midpoint_distance > 1.0
    )
    if held_out_outside_published_range:
        warnings.append(
            f"held-out midpoint distance > 1.0: at least one held-out "
            f"metric is OUTSIDE its published range (inside only the "
            f"tolerance-widened band): {held_out_outside_published_range}"
        )

    payload: Dict[str, Any] = {
        "params_before": {"base_rates": default_flat},
        "params_after": {"base_rates": {k: round(v, 6) for k, v in best_params.items()}},
        "warnings": warnings,
        "x0": {"base_rates": {k: round(v, 6) for k, v in result.x0.items()}},
        "search_moved": result.search_moved,
        "converged": result.converged,
        "termination_reason": result.termination_reason,
        "n_evals": result.n_evals,
        "max_evals": result.max_evals,
        "method": result.method,
        "seed": seed,
        "objective": {
            "kind": OBJECTIVE_KIND,
            "definition": OBJECTIVE_DEFINITION,
            "tolerance": TOLERANCE,
            "note": (
                "0.0 means every evaluated metric sits at the centre of "
                "its published range; see band_distance for inside-band"
            ),
        },
        "benchmark_source": BENCHMARK_SOURCE,
        "tolerance": TOLERANCE,
        "in_sample_metrics": sorted(split.in_sample),
        "held_out_metrics": sorted(split.held_out),
        "held_out_disjoint_check": split.held_out_disjoint_check,
        "disjoint_check_used_observed": split.disjoint_check_used_observed,
        # The objective the search minimised.
        "in_sample_midpoint_distance_before": round(before_in_sample, 6),
        "in_sample_midpoint_distance_after": round(result.in_sample_distance, 6),
        "held_out_midpoint_distance_before": (
            round(before_held_out, 6) if before_held_out is not None else None
        ),
        "held_out_midpoint_distance_after": (
            round(result.held_out_distance, 6)
            if result.held_out_distance is not None else None
        ),
        # The plausibility statement: how far outside the widened band.
        "in_sample_band_distance_before": round(before_in_report.band_distance, 6),
        "in_sample_band_distance_after": round(after_in_report.band_distance, 6),
        "held_out_band_distance_before": round(before_held_report.band_distance, 6),
        "held_out_band_distance_after": round(after_held_report.band_distance, 6),
        "epi_pass_rate_in_sample_before": round(before_in_report.plausibility_score, 6),
        "epi_pass_rate_in_sample_after": round(after_in_report.plausibility_score, 6),
        "epi_pass_rate_held_out_before": round(before_held_report.plausibility_score, 6),
        "epi_pass_rate_held_out_after": round(after_held_report.plausibility_score, 6),
        "n_benchmarks_evaluated_in_sample": after_in_report.n_total,
        "n_within_range_in_sample_after": after_in_report.n_within_range,
        "n_benchmarks_evaluated_held_out": after_held_report.n_total,
        "n_within_range_held_out_after": after_held_report.n_within_range,
        "benchmarks": benchmark_rows,
        "formula_version": after_in_report.formula_version,
        "elapsed_seconds": round(elapsed, 3),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "calibration_result.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=Path(__file__).resolve().parent,
        help="Directory to write calibration_result.json into (default: this file's directory).",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-evals", type=int, default=DEFAULT_MAX_EVALS)
    args = parser.parse_args()

    payload = run(args.out, seed=args.seed, max_evals=args.max_evals)

    print(f"wrote {args.out / 'calibration_result.json'}")
    print(f"  benchmark table: {payload['benchmark_source']}")
    print(f"  objective: {payload['objective']['kind']} (tolerance={payload['tolerance']})")
    print(f"  method: {payload['method']}  n_evals: {payload['n_evals']}/{payload['max_evals']}  "
          f"elapsed: {payload['elapsed_seconds']}s")
    print(f"  converged: {payload['converged']}  ({payload['termination_reason']})")
    print(f"  search_moved: {payload['search_moved']}")
    print(f"  in-sample  midpoint distance (objective): "
          f"{payload['in_sample_midpoint_distance_before']} -> "
          f"{payload['in_sample_midpoint_distance_after']}")
    print(f"  held-out   midpoint distance (objective): "
          f"{payload['held_out_midpoint_distance_before']} -> "
          f"{payload['held_out_midpoint_distance_after']}")
    print(f"  in-sample  band distance (reported): "
          f"{payload['in_sample_band_distance_before']} -> "
          f"{payload['in_sample_band_distance_after']}")
    print(f"  held-out   band distance (reported): "
          f"{payload['held_out_band_distance_before']} -> "
          f"{payload['held_out_band_distance_after']}")
    print(f"  in-sample  EPI pass rate: {payload['epi_pass_rate_in_sample_before']} -> "
          f"{payload['epi_pass_rate_in_sample_after']} "
          f"({payload['n_within_range_in_sample_after']}/"
          f"{payload['n_benchmarks_evaluated_in_sample']} within band)")
    print(f"  held-out   EPI pass rate: {payload['epi_pass_rate_held_out_before']} -> "
          f"{payload['epi_pass_rate_held_out_after']} "
          f"({payload['n_within_range_held_out_after']}/"
          f"{payload['n_benchmarks_evaluated_held_out']} within band)")
    print(f"  formula_version: {payload['formula_version']}")
    print("  per-metric:")
    for row in payload["benchmarks"]:
        print(f"    [{row['split']:>9}] {row['metric']:<20} "
              f"published [{row['rate_low']:.3f}, {row['rate_high']:.3f}] "
              f"band [{row['band_low']:.4f}, {row['band_high']:.4f}] "
              f"observed {row['observed_before']:.4f} -> {row['observed_after']:.4f} "
              f"midpoint_dist {row['midpoint_distance_before']:.4f} -> "
              f"{row['midpoint_distance_after']:.4f}  "
              f"band_dist {row['band_distance_before']:.4f} -> "
              f"{row['band_distance_after']:.4f}")
    if payload["warnings"]:
        print("  WARNINGS:")
        for w in payload["warnings"]:
            print(f"    - {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
