"""R5 -- irrigation: what the agent PROPOSED versus what the world EXECUTED.

WHAT IT ANSWERS
  The single most load-bearing disclosure in the package. The published irrigation
  headline (36.05 / 59.07) is computed on `yearly_decision`, which equals the audit's
  `proposed_skill` and `final_skill` row for row. It is NOT the action the simulation
  actually carried out: a REJECTED proposal runs the registry default
  `maintain_demand` instead. Recomputing the same statistic on that executed action
  gives 0.86 / 26.77 -- a different number, a different sign of gap, and a reviewer
  will find it.

THE THREE COLUMNS (all from irrigation_farmer_governance_audit.csv)
  proposal  `proposed_skill`  what the agent asked for.
  final     `final_skill`     what the audit writer recorded post-validator.
  executed  `maintain_demand` if status starts with REJECTED, else final_skill.
            Rule transcribed from reproduce_published.py:51-53; the default skill is
            _loader.DEFAULT_SKILL.

  The published statistic is the `proposal`/`final` one. `executed` is what ran.

WHAT IS COUNTED
  ibr_pct            conditional high-WSA increase rate (_loader.ibr's definition,
                     re-applied per action column, using the audit's own
                     construct_WSA_LABEL as the conditioning variable)
  increase_rate_pct  unconditional increase rate
  n_rejected         rows whose status starts with REJECTED
  n_proposal_ne_executed / n_proposal_ne_final   row-level disagreement counts
  n_proposal_blank   `proposed_skill` empty (a parse gap; 108 rows across the ten
                     released gemma3:4b runs, never folded into another bucket)

OUTPUT
  out/r5_irrigation_executed_vs_proposal.csv   per (arm, seed) plus MEAN/SD rows

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r5_irrigation_executed_vs_proposal.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import L, PrepError  # noqa: E402

EXPECT = {  # from reproduce_published.py's own diagnostic table
    ("governed", "proposal", "ibr_pct"): 36.05,
    ("ungoverned", "proposal", "ibr_pct"): 59.07,
    ("governed", "executed", "ibr_pct"): 0.86,
    ("ungoverned", "executed", "ibr_pct"): 26.77,
}
TOL = 0.05
LEVELS = {"proposal": C.irr_proposal, "final": C.irr_final, "executed": C.irr_executed}


def main() -> int:
    C.banner("R5  irrigation executed-vs-proposal")
    seeds = L.paired_seeds("")
    rows, agg = [], {}

    for arm in ("governed", "ungoverned"):
        for s in seeds:
            aud = L.load_audit(L.run_dir(arm, "", s))
            C.require_cols(aud, ["proposed_skill", "final_skill", "status",
                                 "construct_WSA_LABEL"], f"{arm} seed {s}")
            hi = [r for r in aud if C.irr_wsa_audit(r) in L.HIGH]
            if not hi:
                raise PrepError(f"{arm} seed {s}: no high-WSA rows -- empty IBR denominator")
            rec = {
                "arm": arm, "seed": s, "n_rows": len(aud),
                "n_high_wsa": len(hi),
                "n_rejected": sum(1 for r in aud
                                  if (r.get("status") or "").startswith("REJECTED")),
                "n_proposal_blank": sum(1 for r in aud if not C.irr_proposal(r)),
                "n_proposal_ne_final": sum(1 for r in aud
                                           if C.irr_proposal(r) != C.irr_final(r)),
                "n_proposal_ne_executed": sum(1 for r in aud
                                              if C.irr_proposal(r) != C.irr_executed(r)),
                "n_final_ne_executed": sum(1 for r in aud
                                           if C.irr_final(r) != C.irr_executed(r)),
            }
            for lvl, fn in LEVELS.items():
                rec[f"ibr_pct_{lvl}"] = 100.0 * sum(
                    1 for r in hi if fn(r) in L.INCREASE) / len(hi)
                rec[f"increase_rate_pct_{lvl}"] = 100.0 * sum(
                    1 for r in aud if fn(r) in L.INCREASE) / len(aud)
            rec["share_rows_proposal_ne_executed_pct"] = \
                100.0 * rec["n_proposal_ne_executed"] / len(aud)
            rows.append(rec)
            agg.setdefault(arm, []).append(rec)

    num_cols = [k for k in rows[0] if k not in ("arm", "seed")]
    for arm, rs in agg.items():
        for tag, fn in (("MEAN", C.mean), ("SD", C.sd)):
            rows.append({"arm": arm, "seed": tag,
                         **{k: fn([float(r[k]) for r in rs]) for k in num_cols}})

    C.write_csv("r5_irrigation_executed_vs_proposal.csv",
                ["arm", "seed"] + num_cols, rows)

    print(f"\n  {'arm':11s} {'level':9s} {'IBR %':>8s} {'increase rate %':>17s}")
    ok = True
    for arm in ("governed", "ungoverned"):
        for lvl in LEVELS:
            m = C.mean([r[f"ibr_pct_{lvl}"] for r in agg[arm]])
            mi = C.mean([r[f"increase_rate_pct_{lvl}"] for r in agg[arm]])
            tgt = EXPECT.get((arm, lvl, "ibr_pct"))
            note = ""
            if tgt is not None:
                hit = abs(m - tgt) <= TOL
                ok &= hit
                note = f"   expected {tgt}  {'MATCH' if hit else 'MISMATCH'}"
            print(f"  {arm:11s} {lvl:9s} {m:8.2f} {mi:17.2f}{note}")

    print("\n  row-level disagreement (mean over 5 seeds, out of 3276 rows/run):")
    for arm in ("governed", "ungoverned"):
        print(f"    {arm:11s} rejected {C.mean([r['n_rejected'] for r in agg[arm]]):7.1f}"
              f"   proposal!=executed {C.mean([r['n_proposal_ne_executed'] for r in agg[arm]]):7.1f}"
              f"  ({C.mean([r['share_rows_proposal_ne_executed_pct'] for r in agg[arm]]):5.2f} %)"
              f"   proposal!=final {C.mean([r['n_proposal_ne_final'] for r in agg[arm]]):5.1f}"
              f"   proposal blank {C.mean([r['n_proposal_blank'] for r in agg[arm]]):5.1f}")

    if not ok:
        raise PrepError("R5 did not reproduce reproduce_published.py's diagnostic table")
    print("\n  R5 reproduces reproduce_published.py's diagnostic row for all four cells.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
