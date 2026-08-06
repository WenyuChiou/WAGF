"""The workshop paper's whole evidence base, in one command. Zero GPU.

CLAIM UNDER TEST
Enforcing a behavioural-theory norm on an LLM agent changes the SELF-REPORTED STATE the norm
conditions on, not only the action. Because the standard conformance statistic is conditional on
exactly that state, it conditions on a post-treatment variable.

WHAT THIS SCRIPT COMPUTES, per (testbed x model) cell:
  * enforcement pressure = share of decisions that exhaust retries and are recorded REJECTED
  * appraisal shift      = (ungoverned - governed) prevalence of the appraisal value the rule
                           conditions on (irrigation: WSA in {H,VH}; flood: TP in {H,VH})

EXPECTED SHAPE (verified 2026-07-29, corrected 2026-07-30): the two testbeds separate completely.
Irrigation binds tightly (28-63% rejected) and shifts +21..+48 pp; flood binds loosely
(0-0.85% rejected) and does not shift (-3.7..+6.3 pp, 5 of 9 cells positive, mean +0.56).

WHAT THE MECHANISM IS -- corrected 2026-07-30, and the earlier reading here was WRONG.
This docstring previously said the corpus could not distinguish "premise revision" (the agent
restates its appraisal so the norm stops applying) from "selection", and that flood was a natural
control for loose rule binding. Both statements have since been falsified by this corpus:

  * Year 1, where the two arms' worlds are provably identical (exogeneity_check.py reports
    year1_exact_equal_rate = 1.0, first disagreement at year 2), the shift is ~0 -- even though
    68-88% of governed year-1 decisions had already exhausted their retry budget.
  * On decisions the agent was NEVER retried on -- no validator ever said anything to it -- the
    shift is LARGER, not smaller: +49.1 pp against +40.4 pp pooled, in 5 of 5 irrigation cells.
    Premise revision cannot produce a shift where nothing was said to the agent.
  * The shift tracks the reservoir, not enforcement: the governed arm ends 102 ft higher on Lake
    Mead and 1.84 shortage tiers lower.

So the appraisal moves mainly because the intervention CHANGED THE WORLD and the agent reported the
changed world accurately. That is a stronger result than premise revision, because it needs no
assumption that the agent games the rule: even a perfectly honest agent breaks the statistic.

Flood is NOT a "low enforcement pressure" control. It was built as a cross-theory portability
demonstration, and run_flood.py:285-291 sets the flood event from a schedule or an i.i.d. draw with
no agent action entering, so it has no action->environment feedback channel at all. Its null is
consistent with the mechanism above rather than evidence about rule binding. The identifying
evidence is WITHIN irrigation (the year-1 and never-retried strata), which needs no cross-testbed
comparison -- useful, because enforcement regime is perfectly confounded with testbed identity here.

Usage:  python SUBMISSION_2026/evidence/appraisal_composition.py [--csv out.csv]
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import statistics

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HIGH = {"H", "VH"}

# (label, appraisal column, governed glob, ungoverned glob)
CELLS = []
for _label, _seg in [("gemma3:4b", ""), ("gemma3:12b", "gemma3_12b_"),
                     ("gemma4:e2b", "gemma4_e2b_"), ("gemma4:e4b", "gemma4_e4b_"),
                     ("ministral3:8b", "ministral3_8b_")]:
    CELLS.append((
        f"irrigation {_label}", "construct_WSA_LABEL",
        f"examples/irrigation_abm/results/production_v21_42yr_{_seg}seed*/irrigation_farmer_governance_audit.csv",
        f"examples/irrigation_abm/results/ungoverned_v21_42yr_{_seg}seed*/irrigation_farmer_governance_audit.csv",
    ))
for _gb, _ub in [("JOH_FINAL", "JOH_ABLATION_DISABLED"),
                 ("JOH_FINAL_v2", "JOH_ABLATION_DISABLED_v2")]:
    _root = os.path.join(REPO, "examples/single_agent/results", _gb)
    # Skip non-model entries: the tree also holds `_logs/`, README.md and loose
    # analysis scripts alongside the per-model directories.
    _models = ([m for m in sorted(os.listdir(_root))
                if os.path.isdir(os.path.join(_root, m)) and not m.startswith("_")]
               if os.path.isdir(_root) else [])
    for _m in _models:
        # Group_C / Group_C_disabled ONLY, named explicitly rather than reached by `**`.
        # Every model directory also carries a Group_A sibling, which is a DIFFERENT
        # experiment (no structured prompts) and is not a clean ablation of Group_C.
        # A bare `<model>/**` glob pulled `ministral3_3b/Group_A/Run_1_bak_broker/`
        # -- 903 rows from a backup of that other experiment -- into the governed arm,
        # which flipped the sign of that cell's appraisal shift (+2.04 -> -0.22 pp).
        # It was the only such file in the corpus, so exactly one cell was affected.
        CELLS.append((
            f"flood {_m}", "construct_TP_LABEL",
            f"examples/single_agent/results/{_gb}/{_m}/Group_C/**/*governance_audit.csv",
            f"examples/single_agent/results/{_ub}/{_m}/Group_C_disabled/**/*governance_audit.csv",
        ))


def scan(pattern: str, col: str):
    """Return (pct_high_appraisal, pct_rejected, n_rows) over every run matching `pattern`."""
    n = high = rejected = 0
    for path in glob.glob(os.path.join(REPO, pattern), recursive=True):
        with open(path, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                value = (row.get(col) or "").strip().upper()
                if not value:
                    continue          # rows without an appraisal cannot enter either rate
                n += 1
                if value in HIGH:
                    high += 1
                if (row.get("status") or "").strip().startswith("REJECTED"):
                    rejected += 1
    if not n:
        return None
    return 100.0 * high / n, 100.0 * rejected / n, n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=None, help="also write the per-cell table here")
    args = ap.parse_args()

    out = []
    for label, col, gov_pat, ung_pat in CELLS:
        g = scan(gov_pat, col)
        u = scan(ung_pat, col)
        if not g or not u:
            print(f"  (skipped {label}: missing runs)")
            continue
        out.append({
            "cell": label,
            "appraisal_col": col,
            "pct_rejected_governed": round(g[1], 4),
            "pct_high_governed": round(g[0], 4),
            "pct_high_ungoverned": round(u[0], 4),
            "shift_pp": round(u[0] - g[0], 4),
            "n_governed": g[2],
            "n_ungoverned": u[2],
        })

    out.sort(key=lambda r: -r["pct_rejected_governed"])
    print(f"\n{'cell':26s} {'enforcement':>12s} {'high|gov':>9s} {'high|ungov':>11s} {'shift pp':>9s}")
    print(f"{'':26s} {'(% rejected)':>12s} {'':>9s} {'':>11s} {'':>9s}")
    print("-" * 72)
    for r in out:
        print(f"{r['cell']:26s} {r['pct_rejected_governed']:>11.2f}% "
              f"{r['pct_high_governed']:>8.2f}% {r['pct_high_ungoverned']:>10.2f}% "
              f"{r['shift_pp']:>+8.2f}")

    hi = [r["shift_pp"] for r in out if r["pct_rejected_governed"] > 5]
    lo = [r["shift_pp"] for r in out if r["pct_rejected_governed"] <= 5]
    print()
    if hi:
        print(f"  HIGH enforcement (>5% rejected), n={len(hi):2d}: "
              f"mean {statistics.mean(hi):+.2f} pp   range {min(hi):+.2f} .. {max(hi):+.2f}")
    if lo:
        print(f"  LOW  enforcement (<=5% rejected), n={len(lo):2d}: "
              f"mean {statistics.mean(lo):+.2f} pp   range {min(lo):+.2f} .. {max(lo):+.2f}")
    if hi and lo:
        sep = min(hi) > max(lo)
        print(f"\n  Separation between regimes: {'COMPLETE' if sep else 'OVERLAPPING'} "
              f"(min high {min(hi):+.2f} vs max low {max(lo):+.2f})")
        print("  NOTE: report this as a REGIME SEPARATION, not a dose-response --")
        print("  the ordering within the high-enforcement group is NOT monotone.")

    if args.csv and out:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out[0]))
            w.writeheader()
            w.writerows(out)
        print(f"\nwrote {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
