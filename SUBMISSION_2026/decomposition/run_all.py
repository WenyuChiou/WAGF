"""run_all -- ONE-COMMAND RUNNER for the post-treatment-conditioning decomposition.

ESTIMAND: this file estimates nothing. It is a harness. It executes the estimator
scripts of this campaign in dependency order, streams their output, and reports which
succeeded and which failed. Every number the campaign reports is produced by the
scripts listed in ORDER below, never by this file.

WHY THE ORDER IS THIS ORDER
  0. corpus prerequisites  -- _loader self-test, seed_inventory, reproduce_published,
     linkage_check. These establish that the corpus loads identically for everyone,
     that the seed sets are what we think they are, that the published 36.05 / 59.07
     headline reproduces from raw files, and what `yearly_decision` actually means.
     If any of these fail, nothing downstream is interpretable.
  1. exogeneity_check      -- the EMPIRICAL answer to "which environment columns are
     treatment-invariant, hence legal to condition on". e2 / e3 / e4 all condition on
     environment variables, so this must run BEFORE them, and its verdict governs
     which strata are admissible. NOTE: this script lives in ../evidence/, not in
     this directory, and writes its CSVs there. That is its own directory, not a
     stray write.
  2. e1 .. e6              -- the estimators, cheapest and least assumption-laden
     first: e1 unconditional total effect, e2 environment-stratified, e3 Kitagawa /
     Oaxaca-Blinder decomposition, e4 worst-case partial-identification bounds,
     e5 year-1 clean-slate, e6 flood placebo / negative control.
  3. _verify_e1 .. _verify_e6 -- the independent adversarial re-derivations. They are
     run LAST because a re-derivation is only meaningful once the thing it re-derives
     has run.

FAILURE SEMANTICS
  Every sub-script is invoked with check=False, so one failure never hides the others.
  Failures are aggregated and re-reported at the end. The process exits 1 if ANY
  sub-script exited non-zero, 0 only if all of them exited 0. No shell=True anywhere;
  arguments are passed as a list.

USAGE (from the repo root):
    python SUBMISSION_2026/decomposition/run_all.py            # everything, in order
    python SUBMISSION_2026/decomposition/run_all.py --core     # exogeneity + e1..e6 only
    python SUBMISSION_2026/decomposition/run_all.py --list     # print the plan, run nothing
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

HERE = os.path.abspath(os.path.dirname(__file__))
CAMPAIGN = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(CAMPAIGN, ".."))
EVIDENCE = os.path.join(CAMPAIGN, "evidence")

# (group, label, absolute script path)
ORDER = [
    ("prereq", "_loader (self-test)", os.path.join(HERE, "_loader.py")),
    ("prereq", "seed_inventory", os.path.join(HERE, "seed_inventory.py")),
    ("prereq", "reproduce_published", os.path.join(HERE, "reproduce_published.py")),
    ("prereq", "linkage_check", os.path.join(HERE, "linkage_check.py")),
    ("core", "exogeneity_check", os.path.join(EVIDENCE, "exogeneity_check.py")),
    ("core", "e1_total_effect", os.path.join(HERE, "e1_total_effect.py")),
    ("core", "e2_stratified", os.path.join(HERE, "e2_stratified.py")),
    ("core", "e3_decomposition", os.path.join(HERE, "e3_decomposition.py")),
    ("core", "e4_bounds", os.path.join(HERE, "e4_bounds.py")),
    ("core", "e5_year1", os.path.join(HERE, "e5_year1.py")),
    ("core", "e6_flood_placebo", os.path.join(HERE, "e6_flood_placebo.py")),
    ("verify", "_verify_e1_total_effect", os.path.join(HERE, "_verify_e1_total_effect.py")),
    ("verify", "_verify_e2_stratified", os.path.join(HERE, "_verify_e2_stratified.py")),
    ("verify", "_verify_e3_decomposition", os.path.join(HERE, "_verify_e3_decomposition.py")),
    ("verify", "_verify_e4_bounds", os.path.join(HERE, "_verify_e4_bounds.py")),
    ("verify", "_verify_e5_year1", os.path.join(HERE, "_verify_e5_year1.py")),
    ("verify", "_verify_e6_flood_placebo", os.path.join(HERE, "_verify_e6_flood_placebo.py")),
]

BANNER = "=" * 100


def selected(core_only: bool):
    if core_only:
        return [row for row in ORDER if row[0] == "core"]
    return list(ORDER)


def main() -> int:
    ap = argparse.ArgumentParser(description="run every estimator in this campaign, in order")
    ap.add_argument("--core", action="store_true",
                    help="run only exogeneity_check + e1..e6 (skip prereqs and verifiers)")
    ap.add_argument("--list", action="store_true", help="print the plan and exit 0")
    args = ap.parse_args()

    plan = selected(args.core)

    if args.list:
        print("plan (executed top to bottom):")
        for i, (group, label, path) in enumerate(plan, 1):
            print(f"  {i:2d}. [{group:6s}] {label:28s} {os.path.relpath(path, REPO)}")
        return 0

    missing = [p for _, _, p in plan if not os.path.isfile(p)]
    if missing:
        print("REFUSING TO START -- these scripts are missing:", file=sys.stderr)
        for p in missing:
            print(f"  {p}", file=sys.stderr)
        return 1

    print(BANNER)
    print("RUN_ALL -- post-treatment-conditioning decomposition")
    print(BANNER)
    print(f"repo root   : {REPO}")
    print(f"interpreter : {sys.executable}")
    print(f"scripts     : {len(plan)}")
    print("sign convention reminder: every gap printed downstream is GOVERNED minus")
    print("UNGOVERNED; negative means governance LOWERED the rate.")
    print()

    results = []  # (label, returncode, seconds)
    t_all = time.time()

    for i, (group, label, path) in enumerate(plan, 1):
        print()
        print(BANNER)
        print(f"[{i}/{len(plan)}]  {label}   ({group})")
        print(f"          {os.path.relpath(path, REPO)}")
        print(BANNER)
        sys.stdout.flush()
        t0 = time.time()
        proc = subprocess.run([sys.executable, path], cwd=REPO, check=False)
        dt = time.time() - t0
        results.append((label, proc.returncode, dt))
        print(f"\n-- {label}: exit={proc.returncode}  ({dt:.1f}s)")
        sys.stdout.flush()

    total = time.time() - t_all
    ok = [r for r in results if r[1] == 0]
    bad = [r for r in results if r[1] != 0]

    print()
    print(BANNER)
    print("SUMMARY")
    print(BANNER)
    for label, rc, dt in results:
        print(f"  {'PASS' if rc == 0 else 'FAIL':4s}  exit={rc:<4d} {dt:6.1f}s  {label}")
    print()
    print(f"  {len(ok)}/{len(results)} succeeded in {total:.1f}s total")
    if bad:
        print()
        print("  FAILED:")
        for label, rc, _ in bad:
            print(f"    {label}  (exit {rc})")
        print()
        print("  Nothing here was patched to make it pass. Read the failing script's own")
        print("  output above; a silently-repaired estimator is worse than a reported failure.")
        return 1

    print("  All scripts exited 0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
