"""R4 -- flood headline IBR, every published variant computed side by side.

WHAT IT ANSWERS
  Five different flood IBR pairs circulate in the drafts and the ledgers:
  0.87/7.41, 1.60/14.22, 2.51/22.56, 0.9/8.5, 0.87/8.53. A reviewer who finds two
  of them will ask which definition each belongs to. This script builds the full
  grid and says which published pair lands on which cell -- and which lands on none.

THE GRID  (3 conditionings x 3 action levels x 2 aggregations = 18 cells per arm)
  conditioning
    unconditional   denominator = every audit row. THIS is the canonical published
                    definition (gemma4_nw_crossmodel_analysis.py:compute_ibr_components,
                    where `total = len(work)`).
    tp_not_medium   denominator = rows whose threat appraisal is VL, L, H or VH.
                    Medium-threat cells carry no inconsistency rule, so dropping
                    them raises the rate without changing the numerator.
    tp_high         denominator = rows whose threat appraisal is H or VH. Note the
                    numerator collapses to R1 alone here: R3 and R4 require a LOW
                    appraisal and cannot occur inside a high-appraisal denominator.
  action level      proposal (proposed_skill) / final (final_skill) / executed
                    (REJECTED* -> do_nothing)
  aggregation       per_run_then_mean (each run a unit, then the unweighted mean --
                    what a per-seed table reports) versus pooled (one rate over the
                    concatenated rows -- decision-weighted). They differ whenever
                    runs have unequal audit lengths, which these do (857 to 984).

  Numerator is always R1 + R3 + R4, R5 excluded per Extended Data Table 2.

OUTPUT
  out/r4_flood_headline_variants.csv   one row per (arm, conditioning, level,
  aggregation) with the per-seed values alongside, plus a `matches_published`
  column naming any published pair the cell reproduces.

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r4_flood_headline_variants.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402

MODEL = "gemma3_4b"
ARMS = {
    "governed": ("JOH_FINAL", "Group_C"),
    "ungoverned": ("JOH_ABLATION_DISABLED", "Group_C_disabled"),
}
LEVELS = {"proposal": C.flood_proposal, "final": C.flood_final, "executed": C.flood_executed}
COND = {
    "unconditional": lambda tp: True,
    "tp_not_medium": lambda tp: tp in ("VL", "L", "H", "VH"),
    "tp_high": lambda tp: tp in ("H", "VH"),
}
#: (label, governed, ungoverned, tolerance in pp). Sources named in the README.
PUBLISHED = [
    ("0.87 / 7.41", 0.87, 7.41, 0.05),
    ("1.60 / 14.22 (SI)", 1.60, 14.22, 0.05),
    ("2.51 / 22.56", 2.51, 22.56, 0.05),
    ("0.9 / 8.5 (EDT2, 1 dp)", 0.9, 8.5, 0.05),
    ("0.87 / 8.53", 0.87, 8.53, 0.05),
]


#: The published Extended Data Table 2 pair 0.9 / 8.5 (and the ledger's 0.87 / 8.53)
#: does NOT come from the live no-validator corpus. It comes from the corpus as it
#: stood before 2026-05-30, when no-validator Run_1..Run_3 were moved to
#: _QUARANTINE_reflection_missing_2026-05-30/ for the documented reflection-OFF
#: defect and re-run. Reconstructing that historical arm -- quarantined Run_1..3
#: plus live Run_4..5 -- is what makes 8.53 +/- 1.08 appear, so this script builds
#: it explicitly as a THIRD arm rather than leaving the published pair unexplained.
QUARANTINE = os.path.join(C.FLOOD_RESULTS,
                          "_QUARANTINE_reflection_missing_2026-05-30", MODEL)
ARMS_ALL = dict(ARMS)
ARMS_ALL["ungoverned_as_published_pre_quarantine"] = None


def _rows(arm):
    out = []
    if arm == "ungoverned_as_published_pre_quarantine":
        live = C.flood_runs(*(("JOH_ABLATION_DISABLED", MODEL, "Group_C_disabled")))
        for run in ("Run_1", "Run_2", "Run_3"):
            rd = os.path.join(QUARANTINE, run)
            if not os.path.isdir(rd):
                raise C.PrepError(f"missing quarantined run {rd}")
            out.append((run, C.flood_seed_of(rd),
                        C.read_csv(os.path.join(rd, C.FLOOD_AUDIT))))
        for run in ("Run_4", "Run_5"):
            seed, rd = live[run]
            out.append((run, seed, C.read_csv(os.path.join(rd, C.FLOOD_AUDIT))))
        return out
    root, group = ARMS[arm]
    for run, (seed, rd) in C.flood_runs(root, MODEL, group).items():
        aud = C.read_csv(os.path.join(rd, C.FLOOD_AUDIT))
        C.require_cols(aud, ["proposed_skill", "final_skill", "status",
                             "construct_TP_LABEL"], f"{arm}/{run}")
        out.append((run, seed, aud))
    return out


def main() -> int:
    C.banner("R4  flood headline IBR variants (gemma3_4b)")
    per_arm = {a: _rows(a) for a in ARMS_ALL}
    grid, out_rows = {}, []

    for arm, runs in per_arm.items():
        for cname, cfn in COND.items():
            for lname, lfn in LEVELS.items():
                per_seed, pooled_rows = [], []
                seedmap = {}
                for run, seed, aud in runs:
                    sel = [r for r in aud
                           if cfn(C.flood_normalize_tp(r.get("construct_TP_LABEL")))]
                    if not sel:
                        raise C.PrepError(
                            f"{arm}/{run}/{cname}: empty denominator -- refusing to score")
                    v = C.flood_ibr_components(sel, lfn)["ibr_pct"]
                    per_seed.append(v)
                    seedmap[f"{run}:{seed}"] = v
                    pooled_rows += sel
                pooled = C.flood_ibr_components(pooled_rows, lfn)["ibr_pct"]
                for agg, val in (("per_run_then_mean", C.mean(per_seed)),
                                 ("pooled", pooled)):
                    grid[(arm, cname, lname, agg)] = (val, per_seed, seedmap)

    for (arm, cname, lname, agg), (val, per_seed, seedmap) in sorted(grid.items()):
        rec = {"arm": arm, "conditioning": cname, "level": lname, "aggregation": agg,
               "ibr_pct": val, "sd_over_runs": C.sd(per_seed) if agg == "per_run_then_mean"
               else float("nan")}
        for k, v in seedmap.items():
            rec[f"run_{k.split(':')[0].replace('Run_', '')}_seed{k.split(':')[1]}"] = v
        out_rows.append(rec)

    # match published pairs to cells
    print(f"\n  {'published pair':26s} -> matching cell(s)")
    matched = {}
    for label, pg, pu, tol in PUBLISHED:
        hits = []
        for (arm, c, l, a) in grid:
            if arm != "governed":
                continue
            gv = grid[("governed", c, l, a)][0]
            for uarm in ("ungoverned", "ungoverned_as_published_pre_quarantine"):
                uv = grid[(uarm, c, l, a)][0]
                if abs(gv - pg) <= tol and abs(uv - pu) <= tol:
                    hits.append(f"{c}/{l}/{a}  [no-val arm: {uarm}]")
        matched[label] = hits
        print(f"  {label:26s} -> {hits if hits else 'NO CELL MATCHES'}")

    # attach to csv
    lab_by_cell = {}
    for label, hits in matched.items():
        for h in hits:
            lab_by_cell.setdefault(h.split("  [")[0],
                                   {}).setdefault(h.split("arm: ")[1].rstrip("]"),
                                                  []).append(label)
    for rec in out_rows:
        key = f"{rec['conditioning']}/{rec['level']}/{rec['aggregation']}"
        by_arm = lab_by_cell.get(key, {})
        labs = by_arm.get("ungoverned", []) if rec["arm"] in ("governed", "ungoverned")             else by_arm.get("ungoverned_as_published_pre_quarantine", [])
        if rec["arm"] == "governed":
            labs = sorted({x for v in by_arm.values() for x in v})
        rec["matches_published"] = "; ".join(labs)

    fields = ["arm", "conditioning", "level", "aggregation", "ibr_pct", "sd_over_runs",
              "matches_published"]
    extra = sorted({k for r in out_rows for k in r} - set(fields))
    C.write_csv("r4_flood_headline_variants.csv", fields + extra, out_rows)

    print("\n  the grid (%). gov = governed | noval = LIVE no-validator corpus |"
          "\n  noval_pub = the pre-quarantine no-validator arm the paper published")
    print(f"    {'conditioning':15s} {'level':9s} {'aggregation':18s} {'gov':>7s} "
          f"{'noval':>8s} {'noval_pub':>10s}")
    for c in COND:
        for l in LEVELS:
            for a in ("per_run_then_mean", "pooled"):
                print(f"    {c:15s} {l:9s} {a:18s} "
                      f"{grid[('governed', c, l, a)][0]:7.2f} "
                      f"{grid[('ungoverned', c, l, a)][0]:8.2f} "
                      f"{grid[('ungoverned_as_published_pre_quarantine', c, l, a)][0]:10.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
