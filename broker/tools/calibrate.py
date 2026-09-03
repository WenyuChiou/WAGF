"""Run a numeric parameter search against a caller-supplied objective.

Usage
-----
    python -m broker.tools.calibrate \\
        --objective-module examples.my_domain.calib:objective \\
        --space '{"base_rates.owner": [0.0, 1.0], "base_rates.renter": [0.0, 1.0]}' \\
        --method nelder-mead --max-evals 50 --out results/calibration/

    python -m broker.tools.calibrate \\
        --objective-module examples.my_domain.calib:objective \\
        --held-out-objective-module examples.my_domain.calib:held_out_objective \\
        --space configs/calibration_space.json \\
        --formula-version legacy_epi_v1 \\
        --method grid --max-evals 64 --seed 7 --out results/calibration/

Thin wrapper around :func:`broker.calibration.optimize.optimize_parameters`
— all the actual search logic (scipy Nelder-Mead / pure-python fallback
/ grid, the non-prompt-key refusal, held-out reporting) lives there.
This CLI's only job is: import the objective(s) the caller names,
parse the space, run the search, write ``optimize_result.json``.

What this is NOT for
---------------------
This searches NUMERIC parameters only — the space is refused if any
key looks like a prompt or template path (see
``broker.calibration.optimize`` module docstring for why). It does not
run a simulation itself; ``--objective-module`` must point at a
function that already knows how to turn parameters into a loss
(typically: simulate, compute rates, compare against benchmarks,
return a distance). See
``examples/multi_agent/flood/parametric/calibrate_parametric.py`` for
a complete worked example.

Naming the formula
-------------------
More than one implementation in this repo computes something called
"EPI", and they disagree on the same observations (see
``docs/guides/calibration_guide.md``). A written result that does not
say which one produced it cannot be compared with anything, so this
CLI refuses to write one:

* an objective module may export ``FORMULA_VERSION = "..."`` and the
  CLI reads it — this is the intended path;
* ``--formula-version`` overrides it from the command line;
* if neither is present AND the objective looks plausibility-derived
  (its module exports ``EPI_DERIVED = True``, or holds names imported
  from ``broker.calibration.benchmark_registry``), the run stops with
  an error instead of writing an untraceable number.

An objective with no benchmark machinery in it — a plain distance to
targets, say — needs no formula version and is written as usual.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Callable, Dict, Optional, Tuple

from broker.calibration.optimize import ObjectiveFn, optimize_parameters


def _load_callable(spec: str) -> Callable:
    """Import ``module.path:attr`` and return the attribute."""
    target, _ = _load_callable_and_module(spec)
    return target


def _load_callable_and_module(spec: str) -> Tuple[Callable, ModuleType]:
    """Import ``module.path:attr``; return the attribute and its module."""
    if ":" not in spec:
        raise ValueError(
            f"expected 'module.path:attr', got {spec!r} (missing ':')"
        )
    module_path, attr = spec.split(":", 1)
    module = importlib.import_module(module_path)
    if not hasattr(module, attr):
        raise AttributeError(f"{module_path!r} has no attribute {attr!r}")
    target = getattr(module, attr)
    if not callable(target):
        raise TypeError(f"{spec!r} is not callable")
    return target, module


def _looks_plausibility_derived(module: ModuleType) -> bool:
    """Does this objective module compute a benchmark plausibility score?

    Two signals, both explicit: the module opts in with
    ``EPI_DERIVED = True``, or it holds a name that came from
    ``broker.calibration.benchmark_registry`` (the registry class, a
    report, a benchmark — anything that implies a band-and-pass-rate
    formula is involved). Either way the number it returns depends on
    which EPI convention was used, so the result must say which.
    """
    if getattr(module, "EPI_DERIVED", False):
        return True
    from broker.calibration import benchmark_registry as _registry_module

    for value in vars(module).values():
        if value is _registry_module:
            return True
        if getattr(value, "__module__", None) == _registry_module.__name__:
            return True
    return False


def _load_space(spec: str) -> Dict[str, Tuple[float, float]]:
    """Parse ``--space`` as either a path to a JSON file or an inline
    JSON string, both mapping ``name -> [low, high]``."""
    path = Path(spec)
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
    else:
        raw = json.loads(spec)
    if not isinstance(raw, dict):
        raise ValueError("--space must decode to a JSON object of name -> [low, high]")
    space: Dict[str, Tuple[float, float]] = {}
    for name, bounds in raw.items():
        if not (isinstance(bounds, (list, tuple)) and len(bounds) == 2):
            raise ValueError(f"--space entry {name!r} must be a [low, high] pair, got {bounds!r}")
        space[name] = (float(bounds[0]), float(bounds[1]))
    return space


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--objective-module", required=True,
        help="'module.path:attr' — a Dict[str,float] -> float callable, lower is better.",
    )
    parser.add_argument(
        "--held-out-objective-module", default=None,
        help="Optional 'module.path:attr' evaluated once on the best in-sample "
             "params after the search converges; never used to select params.",
    )
    parser.add_argument(
        "--space", required=True,
        help="Path to a JSON file, or an inline JSON string, mapping "
             "param name -> [low, high]. Numeric-only: a key that looks "
             "like a prompt/template path is refused.",
    )
    parser.add_argument("--method", choices=["nelder-mead", "grid"], default="nelder-mead")
    parser.add_argument("--max-evals", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--formula-version", default=None,
        help="Names the plausibility formula the objective uses, e.g. "
             "'legacy_epi_v1'. Overrides the objective module's "
             "FORMULA_VERSION. Required (from either source) when the "
             "objective is plausibility-derived — see this module's "
             "docstring.",
    )
    parser.add_argument("--out", type=Path, required=True, help="Directory to write optimize_result.json into.")
    return parser


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        objective, objective_module = _load_callable_and_module(args.objective_module)
    except (ValueError, ImportError, AttributeError, TypeError) as exc:
        print(f"ERROR: could not load --objective-module {args.objective_module!r}: {exc}", file=sys.stderr)
        return 2

    formula_version = args.formula_version or getattr(
        objective_module, "FORMULA_VERSION", None,
    )
    if formula_version is None and _looks_plausibility_derived(objective_module):
        print(
            f"ERROR: {args.objective_module!r} looks plausibility-derived "
            f"(it uses broker.calibration.benchmark_registry, or sets "
            f"EPI_DERIVED) but names no formula version. More than one "
            f"implementation in this repo computes an 'EPI' and they "
            f"disagree on the same observations, so a written result "
            f"without one cannot be compared with anything. Export "
            f"FORMULA_VERSION from the objective module, or pass "
            f"--formula-version.",
            file=sys.stderr,
        )
        return 2

    held_out_objective: Optional[ObjectiveFn] = None
    if args.held_out_objective_module:
        try:
            held_out_objective = _load_callable(args.held_out_objective_module)
        except (ValueError, ImportError, AttributeError, TypeError) as exc:
            print(f"ERROR: could not load --held-out-objective-module "
                  f"{args.held_out_objective_module!r}: {exc}", file=sys.stderr)
            return 2

    try:
        space = _load_space(args.space)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: could not parse --space: {exc}", file=sys.stderr)
        return 2

    try:
        result = optimize_parameters(
            objective=objective, space=space, method=args.method,
            max_evals=args.max_evals, seed=args.seed,
            held_out_objective=held_out_objective,
            formula_version=formula_version,
        )
    except ValueError as exc:
        # Includes the non-prompt-key refusal and the non-finite-loss
        # refusal — surfaced as a normal CLI error, not a traceback.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    out_path = args.out / "optimize_result.json"
    payload = result.to_dict()
    payload["objective_module"] = args.objective_module
    payload["held_out_objective_module"] = args.held_out_objective_module
    payload["space"] = {k: list(v) for k, v in space.items()}
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"method: {result.method}  n_evals: {result.n_evals}/{result.max_evals}  "
          f"converged: {result.converged}")
    print(f"termination: {result.termination_reason}")
    print(f"best_loss (in-sample): {result.best_loss:.6f}")
    if result.held_out_distance is not None:
        print(f"held-out distance: {result.held_out_distance:.6f}")
    print(f"formula_version: {result.formula_version}")
    print(f"x0: {result.x0}")
    print(f"best_params: {result.best_params}")
    print(f"search_moved: {result.search_moved}")
    if result.warning is not None:
        print(f"WARNING: {result.warning} — best_params is x0, so this run "
              f"searched but calibrated nothing.")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
