#!/usr/bin/env python3
"""
DEPRECATED: thin wrapper around ``run_experiment.py --governance-mode disabled``.

This script used to duplicate run_experiment.py's whole pipeline (profiles,
environment, memory engine, context builder, lifecycle hooks) with
``governance="disabled"`` and ``custom_validators=[]`` hardcoded at the
builder call. That duplication is what let the two scripts silently drift:
run_experiment.py's builder always passed
``with_custom_validators([irrigation_governance_validator])`` regardless of
governance_mode, so a hypothetical ``run_experiment.py --governance-mode
disabled`` would have kept irrigation's physical/social/behavioral checks
(water right cap, drought severity, demand floor/ceiling, ...) running as a
SECOND, independent governance layer -- not the zero-validator ablation this
file's own builder call produced. run_experiment.py's builder now branches
on governance_mode itself (``custom_validators = [] if
args.governance_mode == "disabled" else [irrigation_governance_validator]``),
so there is exactly one implementation of "ungoverned" left, and this file
just forwards to it.

This wrapper is kept ONLY so existing docs, batch scripts
(run_gemma4_e4b_batch.bat, run_gemma12b_batch.bat, run_ensemble.bat, ...) and
tests (examples/irrigation_abm/tests/test_coupling.py's
``_run_ungoverned``) that invoke ``run_ungoverned_experiment.py`` by name
keep working unchanged. New work should call
``run_experiment.py --governance-mode disabled`` directly.

Historical CLI defaults are preserved so an invocation that relied on them
(model=gemma3:4b, years=42, and, when ``--output`` is omitted, the
``results/ungoverned_v20_42yr_seed{seed}`` directory name) behaves exactly
as before.

broker/tests/test_coupling_retrofit_pr9.py::TestFlagReachesEveryIrrigationRunner
pins that this file actually delegates to run_experiment.py's main() (rather
than reimplementing coupling-context-contract wiring here) via
test_ungoverned_forwards_to_run_experiment_main, and separately pins that
run_experiment.py itself still calls get_coupling_context_contract() and
constructs IrrigationEnvironment(..., coupling_contract_active=
coupling_contract_active).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from examples.irrigation_abm.run_experiment import main as _run_experiment_main

THIS_DIR = Path(__file__).parent


def _parse_legacy_args(argv):
    """Parse this script's historical flags (a subset of run_experiment.py's)."""
    p = argparse.ArgumentParser(
        description="DEPRECATED wrapper: forwards to "
                     "run_experiment.py --governance-mode disabled."
    )
    p.add_argument("--model", default="gemma3:4b")
    p.add_argument("--thinking-mode", choices=["auto", "disabled", "enabled"],
                   default=None, help="Forwarded to run_experiment.py")
    p.add_argument("--years", type=int, default=42)
    p.add_argument("--agents", type=int, default=5, help="Synthetic agents (ignored with --real)")
    p.add_argument("--real", action="store_true", help="Use real 78-agent CRSS data")
    p.add_argument("--paper-water-margin", type=float, default=0.4,
                   help="Forwarded to run_experiment.py --paper-water-margin "
                        "(see there for the full description). Only affects --real.")
    p.add_argument("--cluster-method", type=str, default="hy2021",
                   choices=["hy2021", "legacy_centroid"],
                   help="Forwarded to run_experiment.py --cluster-method "
                        "(see there for the full description). Only affects --real.")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--memory-seed", type=int, default=42)
    p.add_argument("--window-size", type=int, default=5)
    p.add_argument("--output", type=str, default=None)
    p.add_argument("--num-ctx", type=int, default=None)
    p.add_argument("--num-predict", type=int, default=None)
    p.add_argument("--coupling", action="store_true",
                   help="Enable the v0.6 coupling layer (see run_experiment.py --coupling "
                        "for the full description).")
    return p.parse_args(argv)


def _build_forwarding_argv(args) -> list:
    """Translate this script's parsed (legacy) args into run_experiment.py's CLI."""
    seed = args.seed if args.seed is not None else 42

    # Historical default output directory (used by run_ensemble.bat, which
    # omits --output): anchored at this file's own directory, exactly as
    # the pre-wrapper script anchored it at `base / "results"`.
    output = args.output or str(THIS_DIR / "results" / f"ungoverned_v20_42yr_seed{seed}")

    forwarded = [
        "--model", args.model,
        "--years", str(args.years),
        "--agents", str(args.agents),
        "--workers", str(args.workers),
        "--seed", str(seed),
        "--memory-seed", str(args.memory_seed),
        "--window-size", str(args.window_size),
        "--output", output,
        # New flags (2026-09-28), forwarded unconditionally with the same
        # defaults run_experiment.py itself uses -- a historical invocation
        # that never mentioned either flag behaves exactly as before.
        "--paper-water-margin", str(args.paper_water_margin),
        "--cluster-method", args.cluster_method,
        # The one behavioral pin: ungoverned means governance_mode=disabled,
        # which run_experiment.py's builder now maps to BOTH empty YAML
        # rules AND custom_validators=[] (see module docstring above).
        "--governance-mode", "disabled",
    ]
    if args.real:
        forwarded.append("--real")
    if args.coupling:
        forwarded.append("--coupling")
    if args.num_ctx is not None:
        forwarded += ["--num-ctx", str(args.num_ctx)]
    if args.num_predict is not None:
        forwarded += ["--num-predict", str(args.num_predict)]
    if args.thinking_mode is not None:
        forwarded += ["--thinking-mode", args.thinking_mode]
    return forwarded


def main():
    print(
        "[Deprecated] run_ungoverned_experiment.py now forwards to "
        "run_experiment.py --governance-mode disabled; call that directly "
        "in new work."
    )
    args = _parse_legacy_args(sys.argv[1:])
    forwarded_argv = _build_forwarding_argv(args)
    sys.argv = [sys.argv[0]] + forwarded_argv
    _run_experiment_main()


if __name__ == "__main__":
    main()
