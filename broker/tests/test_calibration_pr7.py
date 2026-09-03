"""PR-7 calibration/optimize consolidation — regression + pin tests.

Covers:
    - the three broker/domains/water/calibration/* shims warn, resolve
      to the exact same objects as broker.calibration.*, and re-export
      every public name the moved modules expose
    - formula_version is present on every BenchmarkReport, and on the
      paper3 L2Metrics result
    - the two EPI formulas (generic legacy_epi vs paper3's
      compute_l2_metrics, the one that actually runs) differ on a
      pinned 5-metric fixture by a documented amount
    - the two benchmark TABLES disagree on five metric ranges and two
      metric names — enumerated by broker.calibration.benchmark_diff so
      the disagreement cannot go quiet
    - optimize_parameters converges on a 2-param quadratic toy in
      <= 50 evals, both methods
    - the honesty contract on OptimizeResult: converged /
      termination_reason / x0 / search_moved / max_evals, and the
      refusal of a non-finite loss
    - an ImportError raised by the caller's objective is NOT relabelled
      "scipy is missing" and does not silently re-run the search
    - the non-prompt-key refusal
    - split_targets determinism, and its refusal of a split whose
      held-out value is bit-identical to an in-sample value
    - aggregate_rates computes flood-prone-only and all-zone insurance
      uptake as two different numbers
    - the parametric first-workload example runs end-to-end
    - no water tokens in broker/calibration/ (delegated to the
      existing framework-invariants scan; asserted here too so this
      file fails loudly if that guard is ever skipped)
"""

from __future__ import annotations

import importlib
import json
import math
import subprocess
import sys
import types
import warnings
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FLOOD_DIR = REPO_ROOT / "examples" / "multi_agent" / "flood"
PAPER3_ANALYSIS_DIR = FLOOD_DIR / "paper3" / "analysis"


# ---------------------------------------------------------------------------
# Shim regression
# ---------------------------------------------------------------------------

class TestShims:
    """broker/domains/water/calibration/{benchmark_registry,
    calibration_protocol, directional_validator} are re-export shims —
    same objects as broker.calibration.*, DeprecationWarning on import."""

    @pytest.mark.parametrize("submodule", [
        "benchmark_registry", "calibration_protocol", "directional_validator",
    ])
    def test_shim_warns_on_import(self, submodule):
        # A shim module's warnings.warn() call runs at import time, once
        # per process — importlib.import_module() on an already-cached
        # module is a no-op and replays nothing. In the full suite, other
        # test modules (tests/test_calibration_protocol.py etc.) import
        # these shims before this file runs, so re-importing must force
        # a fresh execution via reload(), not rely on first-import.
        mod_path = f"broker.domains.water.calibration.{submodule}"
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            if mod_path in sys.modules:
                importlib.reload(sys.modules[mod_path])
            else:
                importlib.import_module(mod_path)
            own_warnings = [
                w for w in caught
                if w.category is DeprecationWarning and submodule in str(w.message)
            ]
        assert own_warnings, f"{mod_path} did not emit its own DeprecationWarning"
        assert "broker.calibration" in str(own_warnings[0].message)

    def test_shim_objects_are_identical(self):
        import broker.calibration.benchmark_registry as new_br
        import broker.domains.water.calibration.benchmark_registry as old_br
        import broker.calibration.calibration_protocol as new_cp
        import broker.domains.water.calibration.calibration_protocol as old_cp
        import broker.calibration.directional_validator as new_dv
        import broker.domains.water.calibration.directional_validator as old_dv

        assert old_br.BenchmarkRegistry is new_br.BenchmarkRegistry
        assert old_br.Benchmark is new_br.Benchmark
        assert old_cp.CalibrationProtocol is new_cp.CalibrationProtocol
        assert old_cp.PilotConfig is new_cp.PilotConfig
        assert old_dv.DirectionalValidator is new_dv.DirectionalValidator
        assert old_dv.chi_squared_test is new_dv.chi_squared_test

    def test_package_import_does_not_itself_warn_for_moved_modules(self):
        """`import broker.domains.water.calibration` (the package) pulls
        the moved symbols from broker.calibration directly, so it must
        not itself emit the *moved-module* shim warnings (a separate,
        pre-existing PMTFramework shim warning from micro_validator.py
        is out of scope here and is filtered out)."""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            import broker.domains.water.calibration  # noqa: F401
            moved_module_warnings = [
                w for w in caught
                if w.category is DeprecationWarning
                and any(name in str(w.message) for name in (
                    "calibration.benchmark_registry is deprecated",
                    "calibration.calibration_protocol is deprecated",
                    "calibration.directional_validator is deprecated",
                ))
            ]
        assert not moved_module_warnings, (
            f"importing the water calibration package should not trigger "
            f"the moved-submodule shims: {moved_module_warnings}"
        )

    # Names a module holds only because it imported stdlib/typing
    # plumbing. Not part of anything's public API, so a shim need not
    # carry them. Everything else public in the moved module MUST be
    # reachable from the shim — the old import path used to reach it.
    _PLUMBING = {
        "annotations", "Any", "Callable", "Dict", "Iterable", "List",
        "Mapping", "Optional", "Sequence", "Tuple", "Union", "Enum",
        "dataclass", "field", "Path", "Counter", "logger",
    }

    @staticmethod
    def _public_names(module) -> set:
        return {
            name for name in dir(module)
            if not name.startswith("_")
            and not isinstance(getattr(module, name), types.ModuleType)
        }

    @pytest.mark.parametrize("submodule", [
        "benchmark_registry", "calibration_protocol", "directional_validator",
    ])
    def test_shim_reexports_every_public_name(self, submodule):
        """A re-export shim must be import-compatible with what it replaced.

        Before the move, ``from broker.domains.water.calibration.
        calibration_protocol import BenchmarkRegistry`` worked — it was
        in that module's namespace. Re-exporting only the headline
        classes turns such an import into an ImportError at some
        caller's next run, which is exactly the breakage a shim exists
        to prevent. Compare the two namespaces name by name.
        """
        new = importlib.import_module(f"broker.calibration.{submodule}")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            shim = importlib.import_module(
                f"broker.domains.water.calibration.{submodule}"
            )

        expected = self._public_names(new) - self._PLUMBING
        missing = sorted(expected - self._public_names(shim))
        assert not missing, (
            f"broker/domains/water/calibration/{submodule}.py does not "
            f"re-export {missing} — these were importable from the old "
            f"path before the PR-7 move"
        )
        for name in sorted(expected):
            assert getattr(shim, name) is getattr(new, name), (
                f"{submodule}.{name} is a different object on the shim; "
                f"isinstance checks across the two paths would fail"
            )
        # __all__ has to agree with what is actually re-exported, or
        # `from ... import *` silently drops names the test just passed.
        assert expected <= set(shim.__all__), (
            f"{submodule} shim __all__ is missing "
            f"{sorted(expected - set(shim.__all__))}"
        )


# ---------------------------------------------------------------------------
# formula_version
# ---------------------------------------------------------------------------

class TestFormulaVersion:
    def test_formula_version_on_every_report(self):
        from broker.calibration.benchmark_registry import Benchmark, BenchmarkRegistry

        registry = BenchmarkRegistry(benchmarks=[
            Benchmark(name="x", metric="x", rate_low=0.1, rate_high=0.5, source="fixture"),
        ])
        report = registry.compare({"x": 0.3})
        assert report.formula_version == "legacy_epi_v1"
        assert report.to_dict()["formula_version"] == "legacy_epi_v1"

        empty_report = registry.compare({})
        assert empty_report.formula_version == "legacy_epi_v1"

    def test_paper3_l2_metrics_names_its_formula(self):
        """The formula that produced every published EPI must say so.

        ``asdict(L2Metrics)`` is what lands in ``validation_report.json``,
        so the saved artifact carries the version string rather than
        leaving a reader to infer it from the file's directory.
        """
        sys.path.insert(0, str(PAPER3_ANALYSIS_DIR))
        from dataclasses import asdict

        from validation.metrics.l2_macro import (
            FORMULA_VERSION, L2Metrics, compute_l2_metrics,
        )

        assert FORMULA_VERSION == "paper3_l2_hard_range_v1"
        assert L2Metrics(
            epi=0.0, benchmark_results={}, benchmarks_in_range=0,
            total_benchmarks=0,
        ).formula_version == FORMULA_VERSION

        profiles = pd.DataFrame({"agent_id": ["A0"], "mg": [False]})
        result = compute_l2_metrics(
            [], profiles, benchmarks={}, benchmark_compute_fn=lambda *a: None,
        )
        assert asdict(result)["formula_version"] == FORMULA_VERSION
        # And it is NOT the generic registry's formula — the whole point
        # of the field is that these two are different numbers.
        from broker.calibration.benchmark_registry import BenchmarkReport

        assert BenchmarkReport().formula_version != FORMULA_VERSION


# ---------------------------------------------------------------------------
# hunter P1: midpoint_distance on an empty report must not read as "best"
# ---------------------------------------------------------------------------

class TestEmptyReportDistances:
    """Before this fix, ``BenchmarkReport.midpoint_distance`` returned
    ``0.0`` — the objective's BEST possible value — when zero benchmarks
    were evaluated (``total_weight <= 0``). Fed to
    ``optimize_parameters``, that told the search "nothing to improve"
    instead of "something upstream is broken": the exact inversion of
    an empty evaluation. ``band_distance`` keeps returning ``0.0`` on
    empty — it is a REPORTED number, not a search objective, so ``0.0``
    there reads as the plausibility claim "nothing failed", which is
    the correct (if easy to misread) thing to report; check ``n_total``
    before trusting it.
    """

    def test_midpoint_distance_is_nan_not_zero_on_empty_registry(self):
        from broker.calibration.benchmark_registry import BenchmarkRegistry

        registry = BenchmarkRegistry()  # zero benchmarks registered
        report = registry.compare({})
        assert report.n_total == 0

        # Falsification: on the code as it stood before this fix, this
        # exact call returned 0.0 — the best possible loss — for zero
        # benchmarks evaluated. `math.isnan` is what proves the fix;
        # `!= 0.0` alone would not, since NaN also fails `== 0.0`.
        assert math.isnan(report.midpoint_distance), (
            f"expected NaN for an empty report, got {report.midpoint_distance!r} "
            f"— if this is 0.0, the pre-fix silent-best-loss bug is back"
        )
        # band_distance is unchanged: still 0.0, but it is a REPORTED
        # quantity (see its docstring), and n_total says to check it.
        assert report.band_distance == 0.0
        assert report.n_total == 0

    def test_optimize_parameters_refuses_the_nan_loudly(self):
        """A NaN loss cannot be compared, so optimize_parameters must
        raise at the evaluation site (see broker.calibration.optimize
        `_evaluate`) rather than silently reporting a 'best' point that
        was never actually measured."""
        from broker.calibration.benchmark_registry import BenchmarkRegistry
        from broker.calibration.optimize import optimize_parameters

        registry = BenchmarkRegistry()  # zero benchmarks -> empty report

        def objective(params):
            return registry.compare({}).midpoint_distance

        with pytest.raises(ValueError, match="non-finite"):
            optimize_parameters(
                objective, {"x": (0.0, 1.0)}, method="grid", max_evals=5,
            )

    def test_a_real_benchmark_that_is_never_observed_also_yields_nan(self):
        """Not just a registry with zero benchmarks REGISTERED — the
        same empty-report path is reached whenever every registered
        benchmark's metric is absent from `observed`."""
        from broker.calibration.benchmark_registry import Benchmark, BenchmarkRegistry

        registry = BenchmarkRegistry(benchmarks=[
            Benchmark(name="x", metric="x", rate_low=0.1, rate_high=0.5, source="fixture"),
        ])
        report = registry.compare({"some_other_metric": 0.9})
        assert report.n_total == 0
        assert math.isnan(report.midpoint_distance)


# ---------------------------------------------------------------------------
# Two EPI formulas, pinned on a shared 5-metric fixture
# ---------------------------------------------------------------------------

# Same five metrics, same observed values, same (range, weight) definitions
# — pulled from paper3's EMPIRICAL_BENCHMARKS so the ONLY variable between
# the two computations below is the aggregation formula itself (hard range
# + rounding vs tolerance-expanded + unrounded), not a benchmark-constant
# difference (a separate, also-real ambiguity documented in
# docs/guides/calibration_guide.md).
_FIXTURE_OBSERVED = {
    "insurance_rate_all": 0.42,
    "elevation_rate": 0.07,
    "buyout_rate": 0.03,
    "do_nothing_rate_postflood": 0.55,
    "mg_adaptation_gap": 0.12,
}


def _paper3_epi(fixture: dict) -> float:
    sys.path.insert(0, str(PAPER3_ANALYSIS_DIR))
    from validation.metrics.l2_macro import compute_l2_metrics
    from validation.benchmarks.flood import EMPIRICAL_BENCHMARKS

    sub_benchmarks = {k: EMPIRICAL_BENCHMARKS[k] for k in fixture}
    profiles = pd.DataFrame({"agent_id": [f"A{i}" for i in range(5)], "mg": [False] * 5})

    def fn(name, df, traces):
        return fixture[name]

    l2 = compute_l2_metrics([], profiles, benchmarks=sub_benchmarks, benchmark_compute_fn=fn)
    return l2.epi


def _generic_epi(fixture: dict) -> float:
    sys.path.insert(0, str(PAPER3_ANALYSIS_DIR))
    from validation.benchmarks.flood import EMPIRICAL_BENCHMARKS
    from broker.calibration.benchmark_registry import Benchmark, BenchmarkRegistry

    sub_benchmarks = {k: EMPIRICAL_BENCHMARKS[k] for k in fixture}
    registry = BenchmarkRegistry(benchmarks=[
        Benchmark(
            name=k, metric=k, rate_low=cfg["range"][0], rate_high=cfg["range"][1],
            source="fixture", weight=cfg["weight"],
        )
        for k, cfg in sub_benchmarks.items()
    ])
    return registry.compare(fixture, tolerance=0.3).plausibility_score


class TestTwoEpiFormulas:
    def test_pinned_on_shared_fixture(self):
        paper3_epi = _paper3_epi(_FIXTURE_OBSERVED)
        generic_epi = _generic_epi(_FIXTURE_OBSERVED)

        # Pinned 2026-09-02 on this exact fixture (see docs/guides/
        # calibration_guide.md "Two EPI formulas" for the full table).
        assert paper3_epi == pytest.approx(0.7049, abs=1e-4), (
            f"paper3 compute_l2_metrics EPI drifted: got {paper3_epi}"
        )
        assert generic_epi == pytest.approx(0.8689, abs=1e-4), (
            f"generic legacy_epi drifted: got {generic_epi}"
        )
        # The formulas must actually disagree here (elevation_rate=0.07
        # sits inside the tolerance-expanded band [0.07, 0.455] but
        # outside the hard band [0.10, 0.35]) — this is the whole point
        # of the pin, not an incidental rounding wobble.
        assert abs(generic_epi - paper3_epi) > 0.1


# ---------------------------------------------------------------------------
# The two benchmark TABLES (separate from the two formulas)
# ---------------------------------------------------------------------------

class TestBenchmarkTablesDisagree:
    """Two tables in this repo define ranges for the same metric names
    and do not agree. That is a human decision to resolve — nobody is
    reconciling it here — but it must not be able to go quiet, because
    "the observed value is inside the empirical range" then means two
    different things depending on which table the code reached for."""

    # Names that mean the same thing, spelled differently in the two
    # tables. Declared here rather than guessed by the diff helper:
    # deciding that two metric names are synonyms is domain knowledge.
    _ALIASES = {
        "insurance_rate": "insurance_rate_sfha",
        "rl_uninsured_rate": "renter_uninsured_rate",
    }

    def _tables(self):
        sys.path.insert(0, str(REPO_ROOT))
        sys.path.insert(0, str(FLOOD_DIR))
        sys.path.insert(0, str(PAPER3_ANALYSIS_DIR))
        from validation.benchmarks.flood import EMPIRICAL_BENCHMARKS
        from paper3.analysis.empirical_benchmarks import FLOOD_BENCHMARKS

        # Only the metrics FLOOD_BENCHMARKS also defines — the paper3
        # table additionally carries institutional-trajectory
        # benchmarks that have no counterpart, and listing those as
        # "only in one table" would bury the real disagreements.
        shared = {
            name: cfg for name, cfg in EMPIRICAL_BENCHMARKS.items()
            if name in {
                self._ALIASES.get(b.metric, b.metric) for b in FLOOD_BENCHMARKS
            }
        }
        return FLOOD_BENCHMARKS, shared

    def _diff(self, aliases=True):
        from broker.calibration.benchmark_diff import diff_benchmark_tables

        left, right = self._tables()
        return diff_benchmark_tables(
            left=left, right=right,
            left_name="FLOOD_BENCHMARKS", right_name="EMPIRICAL_BENCHMARKS",
            aliases=self._ALIASES if aliases else None,
        )

    # Pinned 2026-09-03. FLOOD_BENCHMARKS range vs EMPIRICAL_BENCHMARKS
    # range, on the metrics both tables define.
    _EXPECTED_RANGE_DISAGREEMENTS = {
        "insurance_rate_sfha": ((0.30, 0.50), (0.30, 0.60)),
        "insurance_rate_all": ((0.15, 0.40), (0.15, 0.55)),
        "elevation_rate": ((0.03, 0.12), (0.10, 0.35)),
        "buyout_rate": ((0.02, 0.15), (0.05, 0.25)),
        "mg_adaptation_gap": ((0.10, 0.30), (0.05, 0.30)),
        "insurance_lapse_rate": ((0.05, 0.15), (0.15, 0.30)),
    }

    def test_six_ranges_disagree(self):
        diff = self._diff()
        found = {
            d.metric: (d.left.as_range, d.right.as_range)
            for d in diff.range_disagreements
        }
        assert found == self._EXPECTED_RANGE_DISAGREEMENTS, (
            f"the benchmark-range disagreements changed:\n{diff.to_markdown()}"
        )
        # Everything else the two tables share must actually agree, or
        # this pin is hiding a new one.
        assert set(diff.agreements) == {
            "do_nothing_rate_postflood", "renter_uninsured_rate",
        }
        assert diff.weight_disagreements == []

    def test_the_two_name_mismatches_need_an_alias_to_match_at_all(self):
        """`insurance_rate` vs `insurance_rate_sfha` and
        `rl_uninsured_rate` vs `renter_uninsured_rate` are the same
        quantity under two names. Without the alias map they look like
        four separate metrics, two per table."""
        diff = self._diff()
        assert diff.aliases_applied == self._ALIASES

        naive = self._diff(aliases=False)
        unmatched = {d.metric for d in naive.only_in_one}
        assert unmatched == {
            "insurance_rate", "insurance_rate_sfha",
            "rl_uninsured_rate", "renter_uninsured_rate",
        }

    def test_a_disagreement_never_renders_as_nothing(self):
        diff = self._diff()
        rendered = diff.to_markdown()
        assert "_(none)_" not in rendered
        for d in diff.range_disagreements:
            assert f"`{d.metric}`" in rendered

    def test_identical_tables_report_no_disagreement(self):
        from broker.calibration.benchmark_diff import diff_benchmark_tables

        table = {"m": {"range": (0.1, 0.2), "weight": 1.0}}
        diff = diff_benchmark_tables(table, dict(table))
        assert diff.disagreements == []
        assert diff.agreements == ["m"]

    def test_weight_only_disagreement_is_its_own_kind(self):
        from broker.calibration.benchmark_diff import diff_benchmark_tables

        diff = diff_benchmark_tables(
            {"m": {"range": (0.1, 0.2), "weight": 1.0}},
            {"m": {"range": (0.1, 0.2), "weight": 2.0}},
        )
        assert [d.kind for d in diff.disagreements] == ["weight"]

    def test_unreadable_entry_raises_rather_than_being_skipped(self):
        from broker.calibration.benchmark_diff import normalize_table

        with pytest.raises(ValueError, match="range"):
            normalize_table({"m": {"weight": 1.0}})

    # -- code-reviewer #5: three silent-drop collision shapes ----------

    def test_duplicate_metric_name_in_a_dict_shaped_table_raises(self):
        """Two keys that collapse to the same string after `str()`
        conversion would otherwise silently keep only the last one."""
        from broker.calibration.benchmark_diff import normalize_table

        with pytest.raises(ValueError, match="duplicate metric name"):
            normalize_table({
                1: {"range": (0.1, 0.2), "weight": 1.0},
                "1": {"range": (0.3, 0.4), "weight": 1.0},
            })

    def test_duplicate_metric_name_in_a_list_shaped_table_raises(self):
        """Two Benchmark objects sharing a `.metric` — the shape a
        hand-built or concatenated benchmark list can end up in."""
        from broker.calibration.benchmark_diff import normalize_table
        from broker.calibration.benchmark_registry import Benchmark

        table = [
            Benchmark(name="A", metric="m", rate_low=0.1, rate_high=0.2, source="x"),
            Benchmark(name="B", metric="m", rate_low=0.3, rate_high=0.4, source="y"),
        ]
        with pytest.raises(ValueError, match="duplicate metric name"):
            normalize_table(table)

    def test_alias_target_colliding_with_an_existing_left_metric_raises(self):
        """`a` aliases to `x`, and the left table also independently
        defines `x` in its own right — the alias would silently
        overwrite (or be overwritten by) the unaliased entry."""
        from broker.calibration.benchmark_diff import diff_benchmark_tables

        left = {
            "a": {"range": (0.1, 0.2), "weight": 1.0},
            "x": {"range": (0.5, 0.6), "weight": 1.0},
        }
        right = {"x": {"range": (0.1, 0.2), "weight": 1.0}}
        with pytest.raises(ValueError, match="alias collision"):
            diff_benchmark_tables(left=left, right=right, aliases={"a": "x"})

    def test_two_left_metrics_aliasing_to_one_target_raises(self):
        """`a` and `b` both alias to `x` — nothing named `x` exists in
        the left table on its own, but the two aliases collide with
        each other."""
        from broker.calibration.benchmark_diff import diff_benchmark_tables

        left = {
            "a": {"range": (0.1, 0.2), "weight": 1.0},
            "b": {"range": (0.3, 0.4), "weight": 1.0},
        }
        right = {"x": {"range": (0.1, 0.2), "weight": 1.0}}
        with pytest.raises(ValueError, match="alias collision"):
            diff_benchmark_tables(left=left, right=right, aliases={"a": "x", "b": "x"})

    # -- code-reviewer #5: `python -m broker.calibration.benchmark_diff` --

    def test_main_prints_the_rendered_table_and_returns_zero(self, tmp_path, capsys):
        from broker.calibration.benchmark_diff import main

        left_mod = tmp_path / "left_table.py"
        right_mod = tmp_path / "right_table.py"
        left_mod.write_text(
            'TABLE = {"m": {"range": (0.1, 0.3), "weight": 1.0}}\n', encoding="utf-8",
        )
        right_mod.write_text(
            'TABLE = {"m": {"range": (0.2, 0.4), "weight": 1.0}}\n', encoding="utf-8",
        )
        if str(tmp_path) not in sys.path:
            sys.path.insert(0, str(tmp_path))

        rc = main([
            "--left", "left_table:TABLE", "--right", "right_table:TABLE",
            "--left-name", "L", "--right-name", "R",
        ])
        out, err = capsys.readouterr()
        assert rc == 0, out + err
        assert "`m`" in out
        assert "range" in out
        assert "disagreement(s)" in out

    def test_main_surfaces_a_collision_as_an_error_not_a_traceback(self, tmp_path, capsys):
        from broker.calibration.benchmark_diff import main

        left_mod = tmp_path / "dup_left_table.py"
        left_mod.write_text(
            '''
from broker.calibration.benchmark_registry import Benchmark
TABLE = [
    Benchmark(name="A", metric="m", rate_low=0.1, rate_high=0.2, source="x"),
    Benchmark(name="B", metric="m", rate_low=0.3, rate_high=0.4, source="y"),
]
''',
            encoding="utf-8",
        )
        right_mod = tmp_path / "dup_right_table.py"
        right_mod.write_text(
            'TABLE = {"m": {"range": (0.1, 0.2), "weight": 1.0}}\n', encoding="utf-8",
        )
        if str(tmp_path) not in sys.path:
            sys.path.insert(0, str(tmp_path))

        rc = main([
            "--left", "dup_left_table:TABLE", "--right", "dup_right_table:TABLE",
        ])
        out, err = capsys.readouterr()
        assert rc == 2, out + err
        assert "duplicate metric name" in err


# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------

def _quadratic(params):
    return (params["x"] - 3.0) ** 2 + (params["y"] + 1.0) ** 2


class TestOptimizer:
    @pytest.mark.parametrize("method", ["nelder-mead", "grid"])
    def test_converges_on_2param_quadratic_within_50_evals(self, method):
        from broker.calibration.optimize import optimize_parameters

        space = {"x": (-5.0, 5.0), "y": (-5.0, 5.0)}
        result = optimize_parameters(_quadratic, space, method=method, max_evals=50, seed=42)

        assert result.n_evals <= 50
        # nelder-mead should land very close to (3, -1); grid, evenly
        # spaced over a 10-unit range at ~7 levels/dim, is coarser but
        # must still land far closer than the unoptimised center (loss
        # 10.0 at x=y=0).
        threshold = 0.01 if method == "nelder-mead" else 1.0
        assert result.best_loss < threshold, (
            f"{method} did not converge: best_loss={result.best_loss}, "
            f"best_params={result.best_params}"
        )
        assert result.method.startswith(method if method == "grid" else "nelder-mead")

    def test_pure_python_fallback_converges(self):
        from broker.calibration.optimize import _coordinate_descent_fallback

        space = {"x": (-5.0, 5.0), "y": (-5.0, 5.0)}
        outcome = _coordinate_descent_fallback(
            _quadratic, space, max_evals=50, seed=42,
        )
        assert outcome.n_evals <= 50
        assert outcome.best_loss < 0.05, (
            f"fallback did not converge: loss={outcome.best_loss}, "
            f"params={outcome.best_params}"
        )

    def test_held_out_is_reported(self):
        from broker.calibration.optimize import optimize_parameters

        space = {"x": (-5.0, 5.0), "y": (-5.0, 5.0)}

        def held_out(params):
            return abs(params["x"] - 3.0)

        result = optimize_parameters(
            _quadratic, space, method="nelder-mead", max_evals=50, seed=42,
            held_out_objective=held_out,
        )
        assert result.held_out_distance is not None
        assert result.in_sample_distance == result.best_loss

    def test_prompt_key_rejected(self):
        from broker.calibration.optimize import optimize_parameters

        with pytest.raises(ValueError, match="non-prompt"):
            optimize_parameters(
                lambda p: 0.0,
                {"prompt_templates.household": (0.0, 1.0)},
                method="grid", max_evals=5,
            )

    @pytest.mark.parametrize("bad_key", [
        "system_message.tone", "persona_text.mg", "household.prompt_path",
    ])
    def test_other_prompt_shaped_keys_rejected(self, bad_key):
        from broker.calibration.optimize import optimize_parameters

        with pytest.raises(ValueError):
            optimize_parameters(lambda p: 0.0, {bad_key: (0.0, 1.0)}, method="grid", max_evals=5)


# ---------------------------------------------------------------------------
# The honesty contract on OptimizeResult
# ---------------------------------------------------------------------------

class TestResultTellsTheTruthAboutItself:
    """A result that does not say whether the search moved, converged,
    or ran out of budget can describe a no-op as a calibration. PR-7
    review found exactly that: params_after was the bounds midpoint on
    all four parameters because the loss was already 0 at x0 and the
    search never accepted a move, while `converged` (False) was not
    serialised at all."""

    def test_flat_objective_reports_no_movement_and_warns(self):
        from broker.calibration.optimize import optimize_parameters

        result = optimize_parameters(
            lambda params: 0.0, {"x": (0.0, 1.0), "y": (0.0, 1.0)},
            method="nelder-mead", max_evals=30, seed=42,
        )
        assert result.search_moved is False
        assert result.warning == "search never left its starting point"
        assert result.best_params == result.x0
        assert result.to_dict()["warning"] == "search never left its starting point"
        assert result.to_dict()["search_moved"] is False

    def test_real_search_reports_movement(self):
        from broker.calibration.optimize import optimize_parameters

        result = optimize_parameters(
            _quadratic, {"x": (-5.0, 5.0), "y": (-5.0, 5.0)},
            method="nelder-mead", max_evals=200, seed=42,
        )
        assert result.search_moved is True
        assert result.warning is None
        assert "warning" not in result.to_dict()

    def test_budget_and_reason_are_serialised(self):
        from broker.calibration.optimize import optimize_parameters

        result = optimize_parameters(
            _quadratic, {"x": (-5.0, 5.0), "y": (-5.0, 5.0)},
            method="grid", max_evals=25, seed=42,
        )
        payload = result.to_dict()
        assert payload["max_evals"] == 25
        assert payload["n_evals"] == result.n_evals
        assert payload["termination_reason"], "no termination reason recorded"
        assert set(payload["x0"]) == {"x", "y"}

    def test_grid_convergence_means_the_whole_grid_ran(self):
        """`converged = n_evals <= max_evals` was tautologically True.
        Grid convergence has to mean the grid was actually enumerated."""
        from broker.calibration.optimize import optimize_parameters

        space = {"x": (-5.0, 5.0), "y": (-5.0, 5.0), "z": (-5.0, 5.0)}

        full = optimize_parameters(
            lambda p: sum(v * v for v in p.values()), space,
            method="grid", max_evals=27, seed=42,
        )
        assert full.converged is True
        assert "full grid enumerated" in full.termination_reason

        truncated = optimize_parameters(
            lambda p: sum(v * v for v in p.values()), space,
            method="grid", max_evals=3, seed=42,
        )
        assert truncated.converged is False
        assert "max_evals before full grid" in truncated.termination_reason
        # The dimensions the budget never let it vary must be named —
        # itertools.product varies the last axis fastest, so a truncated
        # grid can have looked at exactly one value of the first ones.
        assert "dimensions never fully varied" in truncated.termination_reason
        assert "'x'" in truncated.termination_reason

    def test_fallback_convergence_means_the_step_shrank(self):
        from broker.calibration.optimize import _coordinate_descent_fallback

        space = {"x": (-5.0, 5.0), "y": (-5.0, 5.0)}
        starved = _coordinate_descent_fallback(_quadratic, space, max_evals=4, seed=42)
        assert starved.converged is False
        assert "max_evals exhausted" in starved.termination_reason

        settled = _coordinate_descent_fallback(_quadratic, space, max_evals=5000, seed=42)
        assert settled.converged is True
        assert "step size shrank" in settled.termination_reason

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    @pytest.mark.parametrize("method", ["nelder-mead", "grid"])
    def test_non_finite_loss_is_refused(self, bad, method):
        """A NaN loses every `<` comparison, so a search that tolerates
        it reports a 'best' point it never measured, with converged
        True and a bare NaN in the JSON."""
        from broker.calibration.optimize import optimize_parameters

        with pytest.raises(ValueError, match="non-finite"):
            optimize_parameters(
                lambda p: bad, {"x": (0.0, 1.0)},
                method=method, max_evals=10, seed=42,
            )

    def test_non_finite_held_out_is_refused(self):
        from broker.calibration.optimize import optimize_parameters

        with pytest.raises(ValueError, match="non-finite"):
            optimize_parameters(
                _quadratic, {"x": (-5.0, 5.0), "y": (-5.0, 5.0)},
                method="grid", max_evals=9, seed=42,
                held_out_objective=lambda p: float("nan"),
            )

    def test_best_loss_is_always_finite(self):
        from broker.calibration.optimize import optimize_parameters

        result = optimize_parameters(
            _quadratic, {"x": (-5.0, 5.0), "y": (-5.0, 5.0)},
            method="nelder-mead", max_evals=100, seed=42,
        )
        assert math.isfinite(result.best_loss)


class TestScipyProbeIsSeparateFromTheSearch:
    """`try: <whole search> except ImportError:` relabels an
    ImportError raised inside the caller's objective as 'scipy not
    available' and silently re-runs the entire search under a different
    method — the report then names a method that did not produce its
    numbers."""

    def test_objective_import_error_propagates(self):
        pytest.importorskip("scipy.optimize")
        from broker.calibration.optimize import optimize_parameters

        calls = {"n": 0}

        def objective(params):
            calls["n"] += 1
            if calls["n"] == 2:
                raise ImportError("a module the objective needs is missing")
            return sum(v * v for v in params.values())

        with pytest.raises(ImportError, match="a module the objective needs"):
            optimize_parameters(
                objective, {"x": (-5.0, 5.0), "y": (-5.0, 5.0)},
                method="nelder-mead", max_evals=50, seed=42,
            )
        # It must NOT have restarted the search under the fallback: a
        # re-run would push the call count far past where it raised.
        assert calls["n"] == 2, (
            f"objective was called {calls['n']} times — the search "
            f"restarted after the ImportError instead of propagating it"
        )

    def test_public_api_works_without_scipy(self, monkeypatch):
        """The pure-python path is the one an install without the
        `analysis` extra takes; it must reach the same public API."""
        import builtins

        import broker.calibration.optimize as opt

        real_import = builtins.__import__

        def _no_scipy(name, *args, **kwargs):
            if name == "scipy" or name.startswith("scipy."):
                raise ImportError("scipy is not installed (simulated)")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _no_scipy)
        assert opt._scipy_available() is False

        result = opt.optimize_parameters(
            _quadratic, {"x": (-5.0, 5.0), "y": (-5.0, 5.0)},
            method="nelder-mead", max_evals=200, seed=42,
        )
        assert result.method == "nelder-mead (pure-python fallback)"
        assert result.best_loss < 0.05
        assert result.search_moved is True
        assert result.termination_reason


class TestUnflattenCollisions:
    def test_value_then_branch_collision_raises(self):
        from broker.calibration.optimize import unflatten_dict

        with pytest.raises(ValueError, match="already a leaf value"):
            unflatten_dict({"a": 1.0, "a.b": 2.0})

    def test_branch_then_value_collision_raises(self):
        from broker.calibration.optimize import unflatten_dict

        with pytest.raises(ValueError, match="collides"):
            unflatten_dict({"a.b": 2.0, "a": 1.0})

    def test_round_trip_without_collisions(self):
        from broker.calibration.optimize import flatten_dict, unflatten_dict

        nested = {"base_rates": {"owner": 0.25, "renter": 0.08}, "slope": 2.0}
        assert unflatten_dict(flatten_dict(nested)) == nested


class TestSplitTargets:
    def test_deterministic_under_seed(self):
        from broker.calibration.optimize import split_targets

        targets = {"a": 0.1, "b": 0.2, "c": 0.3, "d": 0.4}
        s1 = split_targets(targets, holdout_fraction=0.25, seed=42)
        s2 = split_targets(targets, holdout_fraction=0.25, seed=42)
        assert s1.in_sample == s2.in_sample
        assert s1.held_out == s2.held_out

    def test_both_sides_nonempty_with_enough_targets(self):
        from broker.calibration.optimize import split_targets

        targets = {"a": 0.1, "b": 0.2, "c": 0.3, "d": 0.4}
        split = split_targets(targets, holdout_fraction=0.25, seed=42)
        assert split.in_sample
        assert split.held_out
        assert set(split.in_sample) | set(split.held_out) == set(targets)
        assert not (set(split.in_sample) & set(split.held_out))
        # hunter P2-1: no `observed=` means the check that actually
        # catches an aliased estimator never ran, so this must NOT read
        # as "passed" — that would claim a check that never happened.
        assert split.held_out_disjoint_check == "not_checked (observed not supplied)"
        assert split.to_dict()["held_out_disjoint_check"] == (
            "not_checked (observed not supplied)"
        )

    def test_identical_target_values_across_the_split_warn_but_do_not_raise(self, caplog):
        """code-reviewer #1: two DIFFERENT metrics CAN legitimately
        publish the same number by coincidence — FLOOD_BENCHMARKS ships
        `insurance_rate_all` and `rl_uninsured_rate` at the same
        published midpoint (0.275). A target-side collision alone is
        not proof of an aliased estimator, so it only warns; it is the
        OBSERVED-side collision (next test) that still raises."""
        import logging

        from broker.calibration.optimize import split_targets

        targets = {"a": 0.1, "b": 0.2, "c": 0.3, "twin": 0.3}
        caplog.set_level(logging.WARNING, logger="broker.calibration.optimize")
        split = split_targets(targets, holdout_fraction=0.25, seed=42)  # does not raise
        assert set(split.held_out) == {"c"}
        assert split.held_out_disjoint_check == "not_checked (observed not supplied)"
        assert any(
            "TARGET values collide" in rec.message for rec in caplog.records
        ), "the target-side collision must still be logged, just not raised"

    def test_target_side_collision_with_observed_supplied_names_the_collision(self, caplog):
        """When `observed=` IS supplied and the model's own values are
        disjoint, the collision is recorded on the split rather than
        just logged and dropped — a reader of the JSON should not have
        to re-derive it from the raw benchmark table."""
        import logging

        from broker.calibration.optimize import split_targets

        targets = {"a": 0.1, "b": 0.2, "c": 0.3, "twin": 0.3}
        observed = {"a": 0.11, "b": 0.22, "c": 0.31, "twin": 0.29}
        assert len(set(observed.values())) == len(observed)  # disjoint on the model side

        caplog.set_level(logging.WARNING, logger="broker.calibration.optimize")
        split = split_targets(
            targets, holdout_fraction=0.25, seed=42, observed=observed,
        )
        assert set(split.held_out) == {"c"}
        assert "target-side collision" in split.held_out_disjoint_check
        assert "c" in split.held_out_disjoint_check
        assert "twin" in split.held_out_disjoint_check
        assert "observed-side disjoint" in split.held_out_disjoint_check

    def test_flood_benchmarks_midpoint_collision_no_longer_raises(self):
        """Regression for the code-reviewer #1 finding on the real
        production table: FLOOD_BENCHMARKS' `insurance_rate_all` and
        `rl_uninsured_rate` both publish midpoint 0.275. Before this
        fix, `split_targets` raised ValueError for seeds 2 and 3 on
        exactly this pair (falsified against the pre-fix code, which
        called `_assert_values_disjoint` unconditionally on the target
        side)."""
        sys.path.insert(0, str(FLOOD_DIR))
        from paper3.analysis.empirical_benchmarks import FLOOD_BENCHMARKS

        from broker.calibration.optimize import split_targets

        targets = {b.metric: b.midpoint for b in FLOOD_BENCHMARKS}
        assert targets["insurance_rate_all"] == targets["rl_uninsured_rate"] == 0.275

        for seed in (2, 3):
            split = split_targets(targets, holdout_fraction=0.25, seed=seed)
            names = {"insurance_rate_all", "rl_uninsured_rate"}
            # The two colliding metrics land on opposite sides of the
            # split at these seeds -- that is what used to raise.
            assert names & set(split.held_out)
            assert names & set(split.in_sample)
            assert split.held_out_disjoint_check == "not_checked (observed not supplied)"

    def test_identical_observed_values_across_the_split_are_refused(self):
        """The aliasing that matters usually lives in the model, not
        the targets: one estimator assigned to two metric names. The
        targets look fine; the observations give it away."""
        from broker.calibration.optimize import split_targets

        targets = {"a": 0.1, "b": 0.2, "c": 0.3, "d": 0.4}
        split = split_targets(targets, holdout_fraction=0.25, seed=42)
        held_key = sorted(split.held_out)[0]
        kept_key = sorted(split.in_sample)[0]

        aliased = {"a": 0.11, "b": 0.22, "c": 0.33, "d": 0.44}
        aliased[held_key] = aliased[kept_key]  # one estimator, two names
        with pytest.raises(ValueError, match="observed"):
            split_targets(
                targets, holdout_fraction=0.25, seed=42, observed=aliased,
            )

    def test_observed_check_is_recorded_when_it_ran(self):
        from broker.calibration.optimize import split_targets

        targets = {"a": 0.1, "b": 0.2, "c": 0.3, "d": 0.4}
        observed = {"a": 0.11, "b": 0.22, "c": 0.33, "d": 0.44}
        split = split_targets(
            targets, holdout_fraction=0.25, seed=42, observed=observed,
        )
        assert split.disjoint_check_used_observed is True
        assert split.to_dict()["disjoint_check_used_observed"] is True

        without = split_targets(targets, holdout_fraction=0.25, seed=42)
        assert without.disjoint_check_used_observed is False


# ---------------------------------------------------------------------------
# Parametric first-workload example
# ---------------------------------------------------------------------------

def _flood_population():
    """Two flood-prone and two safe households, one owner each side."""
    return [
        {"tenure": "Owner", "flood_zone": "HIGH", "flood_count": 3},
        {"tenure": "Renter", "flood_zone": "MEDIUM", "flood_count": 2},
        {"tenure": "Owner", "flood_zone": "LOW", "flood_count": 0},
        {"tenure": "Renter", "flood_zone": "LOW", "flood_count": 0},
    ]


class TestAggregateRates:
    """`insurance_rate` (flood-prone households only) and
    `insurance_rate_all` (every zone) were emitted as the same float,
    which is what made them useless as an in-sample/held-out pair."""

    def _decider(self):
        sys.path.insert(0, str(REPO_ROOT))
        sys.path.insert(0, str(FLOOD_DIR))
        import parametric.parametric_decider as decider

        return decider

    def test_prone_only_and_all_zone_rates_differ(self):
        decider = self._decider()
        rates = decider.aggregate_rates(
            decider.PARAMETRIC_CALIBRATION, _flood_population(),
        )
        assert "insurance_rate" in rates
        assert "insurance_rate_all" in rates
        assert rates["insurance_rate"] != rates["insurance_rate_all"], (
            "flood-prone-only uptake is being emitted as the all-zone "
            "number again — the two metrics are one number under two names"
        )
        # The shipped base rates are far higher in flood-prone zones, so
        # the prone-only rate has to be the larger of the two.
        assert rates["insurance_rate"] > rates["insurance_rate_all"]

    def test_prone_rate_is_computed_over_prone_households_only(self):
        decider = self._decider()
        population = _flood_population()
        prone_only = [a for a in population if a["flood_zone"] != "LOW"]

        full = decider.aggregate_rates(decider.PARAMETRIC_CALIBRATION, population)
        subset = decider.aggregate_rates(decider.PARAMETRIC_CALIBRATION, prone_only)
        assert full["insurance_rate"] == pytest.approx(
            subset["insurance_rate_all"], abs=1e-12,
        )

    def test_prone_rate_is_omitted_rather_than_defaulted(self):
        """A benchmark with no population behind it must be absent, not
        zero — an absent non-required metric drops out of EPI, whereas a
        stand-in 0.0 is scored as a measurement that failed."""
        decider = self._decider()
        safe_only = [a for a in _flood_population() if a["flood_zone"] == "LOW"]
        rates = decider.aggregate_rates(decider.PARAMETRIC_CALIBRATION, safe_only)
        assert "insurance_rate" not in rates
        assert "insurance_rate_all" in rates

    def test_base_rate_heterogeneity_moves_the_rates(self):
        decider = self._decider()
        import copy

        raised = copy.deepcopy(decider.PARAMETRIC_CALIBRATION)
        raised["base_rates"]["flood_prone_owner"] = 0.8
        base = decider.aggregate_rates(
            decider.PARAMETRIC_CALIBRATION, _flood_population(),
        )
        moved = decider.aggregate_rates(raised, _flood_population())
        assert moved["insurance_rate"] > base["insurance_rate"]


class TestBuildObjectiveGuardsEmptyReport:
    """hunter P1, applied to the one place in this repo that actually
    calls `optimize_parameters` against a midpoint-distance objective:
    `_build_objective` must fail loudly, naming the registry/observed
    mismatch, before a NaN loss ever reaches the optimizer."""

    def _module(self):
        sys.path.insert(0, str(REPO_ROOT))
        sys.path.insert(0, str(FLOOD_DIR))
        import parametric.calibrate_parametric as example

        return example

    def test_empty_registry_raises_with_the_metric_names(self):
        example = self._module()
        from broker.calibration.benchmark_registry import BenchmarkRegistry

        empty_registry = BenchmarkRegistry()  # matches no metric at all
        objective = example._build_objective(empty_registry, _flood_population())

        with pytest.raises(AssertionError, match="zero benchmarks scored"):
            objective({})


class TestParametricExample:
    def test_runs_end_to_end_and_improves_in_sample(self, tmp_path):
        sys.path.insert(0, str(REPO_ROOT))
        sys.path.insert(0, str(FLOOD_DIR))
        from parametric.calibrate_parametric import DEFAULT_MAX_EVALS, run

        payload = run(tmp_path, seed=42)

        out_path = tmp_path / "calibration_result.json"
        assert out_path.exists()
        on_disk = json.loads(out_path.read_text(encoding="utf-8"))
        assert on_disk == payload

        before = payload["in_sample_midpoint_distance_before"]
        after = payload["in_sample_midpoint_distance_after"]
        assert after < before, (
            "optimizer did not improve on the shipped "
            "PARAMETRIC_CALIBRATION defaults"
        )
        # Held-out must be REPORTED (not None) — the requirement is that
        # a number exists to look at, not that it improved.
        assert payload["held_out_midpoint_distance_before"] is not None
        assert payload["held_out_midpoint_distance_after"] is not None
        assert payload["formula_version"] == "legacy_epi_v1"
        assert payload["n_evals"] <= DEFAULT_MAX_EVALS
        assert payload["max_evals"] == DEFAULT_MAX_EVALS

    def test_result_says_whether_the_search_moved(self, tmp_path):
        """The pre-review run reported `params_after` == the bounds
        midpoint on all four parameters with no way to tell from the
        JSON. Now the file has to say."""
        sys.path.insert(0, str(REPO_ROOT))
        sys.path.insert(0, str(FLOOD_DIR))
        from parametric.calibrate_parametric import run

        payload = run(tmp_path, seed=42)

        assert payload["search_moved"] is True
        assert payload["params_after"]["base_rates"] != payload["x0"]["base_rates"]
        assert "warning" not in payload
        assert payload["converged"] is True
        assert payload["termination_reason"]

    def test_calibration_result_reports_both_generic_warnings(self, tmp_path):
        """code-reviewer #3 + hunter P2-3: both caveats must land IN the
        JSON next to `params_after`, generalising the single
        `OptimizeResult.warning` into a `warnings` list — not be left
        for a reader to re-derive from `in_sample_metrics` / `space` /
        the per-metric `benchmarks` table by hand. The shipped default
        run (seed 42) actually triggers both: 3 in-sample metrics vs.
        4 base-rate parameters, and the held-out metric
        (`insurance_rate`) finishes outside its own published range."""
        sys.path.insert(0, str(REPO_ROOT))
        sys.path.insert(0, str(FLOOD_DIR))
        from parametric.calibrate_parametric import run

        payload = run(tmp_path, seed=42)

        assert "warnings" in payload
        assert isinstance(payload["warnings"], list)
        joined = " | ".join(payload["warnings"])

        n_in = len(payload["in_sample_metrics"])
        n_params = len(payload["x0"]["base_rates"])
        assert n_in < n_params, "fixture assumption changed -- update this test"
        assert f"n_metrics_in_sample ({n_in}) < n_parameters ({n_params})" in joined
        assert "does not identify the parameters" in joined

        assert "held-out midpoint distance > 1.0" in joined
        assert "insurance_rate" in joined
        assert "OUTSIDE its published range" in joined

    def test_result_carries_the_provenance_a_reader_needs(self, tmp_path):
        sys.path.insert(0, str(REPO_ROOT))
        sys.path.insert(0, str(FLOOD_DIR))
        from parametric.calibrate_parametric import run

        payload = run(tmp_path, seed=42)

        assert payload["benchmark_source"].endswith("FLOOD_BENCHMARKS")
        assert payload["tolerance"] == 0.3
        assert payload["held_out_disjoint_check"] == "passed"
        assert payload["disjoint_check_used_observed"] is True
        assert payload["n_benchmarks_evaluated_in_sample"] >= 1
        assert payload["n_within_range_in_sample_after"] >= 0
        # The pass rate is reported but never optimised against.
        assert 0.0 <= payload["epi_pass_rate_in_sample_after"] <= 1.0
        # Per-metric table: band, observed, deviation, per benchmark.
        assert payload["benchmarks"]
        for row in payload["benchmarks"]:
            assert {"metric", "rate_low", "rate_high", "weight", "tolerance",
                    "band_low", "band_high", "observed_after",
                    "band_distance_after", "midpoint_distance_after",
                    "split"} <= set(row)
        metrics = {row["metric"] for row in payload["benchmarks"]}
        assert metrics == set(payload["in_sample_metrics"]) | set(
            payload["held_out_metrics"]
        )

    def test_held_out_metric_is_not_a_copy_of_an_in_sample_one(self, tmp_path):
        """The point of the split. With `insurance_rate` aliased to
        `insurance_rate_all`, the held-out number was the in-sample
        number wearing a different name."""
        sys.path.insert(0, str(REPO_ROOT))
        sys.path.insert(0, str(FLOOD_DIR))
        from parametric.calibrate_parametric import run

        payload = run(tmp_path, seed=42)
        observed = {
            row["metric"]: row["observed_after"] for row in payload["benchmarks"]
        }
        in_sample = [observed[m] for m in payload["in_sample_metrics"]]
        held_out = [observed[m] for m in payload["held_out_metrics"]]
        assert held_out
        for value in held_out:
            assert value not in in_sample, (
                "a held-out metric's observed value is bit-identical to an "
                "in-sample one"
            )


# ---------------------------------------------------------------------------
# CLI: a plausibility number never gets written without naming its formula
# ---------------------------------------------------------------------------

_EPI_OBJECTIVE_SRC = '''
from broker.calibration.benchmark_registry import Benchmark, BenchmarkRegistry

_REG = BenchmarkRegistry(benchmarks=[
    Benchmark(name="A", metric="m", rate_low=0.2, rate_high=0.4, source="fixture"),
])


def objective(params):
    return _REG.compare({"m": params["x"]}, tolerance=0.3).midpoint_distance
'''

_TAGGED_OBJECTIVE_SRC = 'FORMULA_VERSION = "legacy_epi_v1"\n' + _EPI_OBJECTIVE_SRC

_PLAIN_OBJECTIVE_SRC = '''
def objective(params):
    return (params["x"] - 0.3) ** 2
'''


def _run_calibrate_cli(tmp_path, source, module_name, extra_args, out_name):
    """Out-of-process: spawns `python -m broker.tools.calibrate`.

    Kept for exactly one test — the one that checks the `python -m`
    entry path itself actually works (module resolution, argv parsing
    at the process boundary, stderr on a real process). The other three
    CLI-formula-version tests exercise the same `main()` logic
    in-process via :func:`_call_calibrate_cli_inprocess` — a subprocess
    per test bought nothing beyond what calling `main()` directly
    already proves for those three.
    """
    (tmp_path / f"{module_name}.py").write_text(source, encoding="utf-8")
    import os

    env = dict(os.environ)
    env["PYTHONPATH"] = str(tmp_path)
    env["PYTHONHASHSEED"] = "0"
    out_dir = tmp_path / out_name
    proc = subprocess.run(
        [sys.executable, "-m", "broker.tools.calibrate",
         "--objective-module", f"{module_name}:objective",
         "--space", '{"x":[0.0,1.0]}',
         "--method", "grid", "--max-evals", "9",
         "--out", str(out_dir), *extra_args],
        cwd=str(REPO_ROOT), capture_output=True, text=True, env=env,
    )
    return proc, out_dir / "optimize_result.json"


def _call_calibrate_cli_inprocess(tmp_path, source, module_name, extra_args, out_name):
    """In-process: writes the objective module, puts `tmp_path` on
    `sys.path`, and calls `broker.tools.calibrate.main(argv)` directly
    — same code path `_run_calibrate_cli` drives via subprocess, minus
    the process-spawn cost. `module_name` must be unique across callers
    in this test session (each becomes a real `sys.modules` entry)."""
    (tmp_path / f"{module_name}.py").write_text(source, encoding="utf-8")
    if str(tmp_path) not in sys.path:
        sys.path.insert(0, str(tmp_path))

    from broker.tools.calibrate import main as calibrate_main

    out_dir = tmp_path / out_name
    argv = [
        "--objective-module", f"{module_name}:objective",
        "--space", '{"x":[0.0,1.0]}',
        "--method", "grid", "--max-evals", "9",
        "--out", str(out_dir), *extra_args,
    ]
    rc = calibrate_main(argv)
    return rc, out_dir / "optimize_result.json"


class TestCalibrateCliFormulaVersion:
    def test_untagged_plausibility_objective_is_refused(self, tmp_path):
        """The one test kept on the subprocess path — see
        `_run_calibrate_cli`'s docstring for why."""
        proc, out_file = _run_calibrate_cli(
            tmp_path, _EPI_OBJECTIVE_SRC, "epi_obj", [], "a",
        )
        assert proc.returncode == 2, proc.stdout + proc.stderr
        assert "names no formula version" in proc.stderr
        assert not out_file.exists(), (
            "a result with an unnameable EPI convention was written anyway"
        )

    def test_flag_supplies_the_version(self, tmp_path, capsys):
        rc, out_file = _call_calibrate_cli_inprocess(
            tmp_path, _EPI_OBJECTIVE_SRC, "epi_obj2",
            ["--formula-version", "legacy_epi_v1"], "b",
        )
        out, err = capsys.readouterr()
        assert rc == 0, out + err
        assert json.loads(out_file.read_text(encoding="utf-8"))[
            "formula_version"] == "legacy_epi_v1"

    def test_module_constant_supplies_the_version(self, tmp_path, capsys):
        rc, out_file = _call_calibrate_cli_inprocess(
            tmp_path, _TAGGED_OBJECTIVE_SRC, "epi_obj3", [], "c",
        )
        out, err = capsys.readouterr()
        assert rc == 0, out + err
        assert json.loads(out_file.read_text(encoding="utf-8"))[
            "formula_version"] == "legacy_epi_v1"

    def test_plain_objective_needs_no_version(self, tmp_path, capsys):
        """An objective with no benchmark machinery in it is not an EPI
        under either convention, so there is nothing to name."""
        rc, out_file = _call_calibrate_cli_inprocess(
            tmp_path, _PLAIN_OBJECTIVE_SRC, "plain_obj", [], "d",
        )
        out, err = capsys.readouterr()
        assert rc == 0, out + err
        assert json.loads(out_file.read_text(encoding="utf-8"))[
            "formula_version"] is None

    def test_the_shipped_example_module_is_tagged(self):
        """The worked example has to model the contract it documents."""
        sys.path.insert(0, str(REPO_ROOT))
        sys.path.insert(0, str(FLOOD_DIR))
        import parametric.calibrate_parametric as example

        from broker.tools.calibrate import _looks_plausibility_derived

        assert _looks_plausibility_derived(example) is True
        assert example.FORMULA_VERSION == "legacy_epi_v1"


# ---------------------------------------------------------------------------
# No water tokens (belt-and-suspenders on top of test_framework_invariants)
# ---------------------------------------------------------------------------

class TestNoWaterTokensInCalibrationPackage:
    def test_invariants_suite_passes_for_calibration(self):
        result = subprocess.run(
            [sys.executable, "-m", "pytest",
             "broker/tests/test_framework_invariants.py::TestDomainGenericity",
             "-q"],  # no --timeout: pytest-timeout is not a CI dependency
            cwd=str(REPO_ROOT), capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"TestDomainGenericity failed after the PR-7 move:\n{result.stdout}\n{result.stderr}"
        )
