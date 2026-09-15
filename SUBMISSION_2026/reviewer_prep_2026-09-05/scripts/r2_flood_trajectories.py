"""R2 -- per-year flood single-agent trajectories, Group_C vs Group_C_disabled.

WHAT IT ANSWERS
  The flood twin of R1: year-by-year IBR, entropy and action shares for the
  household flood-adaptation testbed (Gemma-3 4B, 100 agents x 10 years).

DEFINITIONS -- transcribed from the canonical published implementation
  examples/single_agent/analysis/gemma4_nw_crossmodel_analysis.py
  ibr_pct      (R1 + R3 + R4) / total * 100, R5 (re-elevation) TRACKED AND EXCLUDED
               per Extended Data Table 2.
                 R1 = threat appraisal in {H,VH} AND action == do_nothing
                 R3 = threat appraisal in {VL,L} AND action == relocate
                 R4 = threat appraisal in {VL,L} AND action == elevate_house
               The denominator is EVERY audit row of the year -- unconditional.
  ehe_yearly   H/log2(4) over the four-action distribution WITHIN ONE YEAR.
               *** Not the headline EHE. *** The published 0.861 / 0.815 pools the
               whole run once. r7 carries the pooled-once value.
  share_*      four-action shares, same normalisation map as the published script
               (`relocated` -> `relocate`).

ACTION LEVELS
  proposal   audit `proposed_skill`, normalised.
  final      audit `final_skill`, normalised. THIS is what the published flood
             numbers use (summarize_pooled_metrics maps final_skill).
  executed   REJECTED* -> household registry default `do_nothing`, else final_skill.

CORPUS CAVEAT -- read before pairing anything
  The v1 flood cells are NOT seed-matched. Governed Run_1..Run_5 carry seeds
  {42, 4202, 4203, 45, 46}; the no-validator arm carries {42, 43, 44, 45, 46}.
  Only THREE seeds (42, 45, 46) exist in both arms. The published cross-model
  script pairs by RUN INDEX (Run_1 with Run_1), not by seed. Both pairings are
  emitted here and the difference is reported rather than resolved silently.
  simulation_log.csv is 1000 rows in every run; household_governance_audit.csv is
  shorter, because an agent that has already relocated makes no further decision.

OUTPUT
  out/r2_flood_trajectories.csv   per (arm, run, seed, level, year)

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r2_flood_trajectories.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import PrepError  # noqa: E402

MODEL = "gemma3_4b"
ARMS = {
    "governed": ("JOH_FINAL", "Group_C"),
    "ungoverned": ("JOH_ABLATION_DISABLED", "Group_C_disabled"),
}
LEVELS = {"proposal": C.flood_proposal, "final": C.flood_final, "executed": C.flood_executed}


def _year(row) -> int:
    v = (row.get("year") or "").strip()
    if not v:
        raise PrepError("audit row with an empty `year`")
    return int(float(v))


def main() -> int:
    C.banner("R2  flood single-agent per-year trajectories (gemma3_4b)")
    rows_out = []
    seen = {}

    for arm, (root, group) in ARMS.items():
        runs = C.flood_runs(root, MODEL, group)
        seen[arm] = {r: s for r, (s, _) in runs.items()}
        print(f"  {arm:11s} {root}/{MODEL}/{group}")
        for run, (seed, rd) in runs.items():
            aud = C.read_csv(os.path.join(rd, C.FLOOD_AUDIT))
            sim = C.read_csv(os.path.join(rd, C.FLOOD_SIM))
            C.require_cols(aud, ["year", "proposed_skill", "final_skill", "status",
                                 "construct_TP_LABEL"], f"{arm}/{run} audit")
            unmapped = sum(1 for r in aud
                           if C.flood_action_is_unmapped(r.get("final_skill")))
            print(f"    {run} seed {seed:>5s}  audit {len(aud):>4d}  sim {len(sim):>4d}"
                  f"  final_skill silently coerced to do_nothing: {unmapped}")

            by = {}
            for r in aud:
                by.setdefault(_year(r), []).append(r)
            for lvl, fn in LEVELS.items():
                for y, rs in sorted(by.items()):
                    comp = C.flood_ibr_components(rs, fn)
                    counts = {a: 0 for a in C.FLOOD_ACTION_ORDER}
                    for r in rs:
                        counts[fn(r)] += 1
                    tp = {t: 0 for t in C.FLOOD_TP_ORDER + ["UNK"]}
                    for r in rs:
                        tp[C.flood_normalize_tp(r.get("construct_TP_LABEL"))] += 1
                    n_high = tp["H"] + tp["VH"]
                    rec = {
                        "arm": arm, "run": run, "seed": seed, "level": lvl, "year": y,
                        "n_audit_rows": len(rs),
                        "n_tp_high": n_high,
                        "n_tp_unk": tp["UNK"],
                        "R1": comp["R1"], "R3": comp["R3"], "R4": comp["R4"],
                        "ibr_pct": comp["ibr_pct"],
                        "ehe_yearly": C.normalized_entropy(counts, k=4),
                    }
                    for a in C.FLOOD_ACTION_ORDER:
                        rec[f"share_{a}"] = 100.0 * counts[a] / len(rs)
                    rows_out.append(rec)

    C.write_csv(
        "r2_flood_trajectories.csv",
        ["arm", "run", "seed", "level", "year", "n_audit_rows", "n_tp_high", "n_tp_unk",
         "R1", "R3", "R4", "ibr_pct", "ehe_yearly"]
        + [f"share_{a}" for a in C.FLOOD_ACTION_ORDER],
        rows_out)

    g, u = seen["governed"], seen["ungoverned"]
    shared = sorted(set(g.values()) & set(u.values()))
    print(f"\n  governed   run->seed: {g}")
    print(f"  ungoverned run->seed: {u}")
    print(f"  seeds present in BOTH arms: {shared}  (n={len(shared)}, NOT 5)")
    print("  -> a seed-matched paired test on this cell has df=2, not df=4."
          "\n     The published pairing is by run index, which pairs governed seed 4202"
          "\n     with no-validator seed 43 and governed 4203 with 44.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
