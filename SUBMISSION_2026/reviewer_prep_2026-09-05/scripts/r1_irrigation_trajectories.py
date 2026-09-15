"""R1 -- per-year irrigation trajectories, governed vs no-validator (gemma3:4b v21, 5 seeds).

WHAT IT ANSWERS
  "Your headline is one number averaged over 42 years. Show me the year-by-year
   series, per seed, and show me that the effect is not one or two odd years."

DEFINITIONS -- all canonical, none invented
  ibr_pct            _loader.ibr, recomputed year by year: among rows whose
                     self-reported water-scarcity appraisal is H or VH, the share
                     whose action is increase_large/increase_small. Higher = worse.
  increase_rate_pct  _loader.increase_rate, unconditional over all rows of the year.
  ehe_yearly         normalised Shannon entropy H/log2(5) of the FIVE-skill action
                     distribution WITHIN ONE YEAR.
                     *** This is NOT the headline EHE. *** The headline EHE pools
                     every decision of the run once and takes entropy once
                     (irrigation ~0.687 governed / 0.848 no-validator). A per-year
                     entropy averaged over years is a DIFFERENT and smaller number
                     (the ~0.63-vs-0.86 trap recorded in project memory). It is
                     published here only as a trajectory shape, never as a headline.
                     r7 carries the pooled-once headline value.
  share_<skill>      action share of each of the five irrigation skills, that year.

ACTION LEVELS (every row of the output carries one)
  proposal   audit `proposed_skill` -- what the agent asked for, pre-validator.
  final      audit `final_skill`    -- what the audit writer recorded post-validator.
  executed   REJECTED* -> registry default `maintain_demand`, else final_skill.
             (reproduce_published.py:51-53)
  sim        simulation_log `yearly_decision` -- the column the published headline
             uses. Carried so the reader can see it coincides with `proposal`.

APPRAISAL COLUMN
  the `sim` level uses simulation_log `wsa_label`; the audit levels use the audit's
  own `construct_WSA_LABEL`. The two are separate views of the same decision and are
  not silently merged.

FQL
  `fql_raw` (validators ON, the Nature Water baseline arm) and `fql_nogov`
  (validators OFF, explicitly NOT paper data -- see
  examples/irrigation_abm/experiments/fql_nogov_2026-08.md) carry 10 seeds each and
  only a simulation_log, so they appear at the `sim` level only.

OUTPUT
  out/r1_irrigation_trajectories.csv   per (arm, seed, level, year)
  out/r1_irrigation_mead.csv           per (arm, seed, year) reservoir elevation,
                                       plus the across-seed mean +/- sd band.

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r1_irrigation_trajectories.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import L, PrepError  # noqa: E402

PREFIX = ""
FQL_ARMS = {
    "fql_validators_on": os.path.join(L.RESULTS, "fql_raw"),
    "fql_validators_off": os.path.join(L.RESULTS, "fql_nogov"),
}
SKILLS = C.IRR_SKILLS
#: MEASURED, not assumed: the FQL runner writes a THREE-action vocabulary
#: (increase_demand / decrease_demand / maintain_demand), not the five-skill LLM
#: registry. Its rows are therefore scored on their own vocabulary with k = 3, and
#: labelled level "sim_fql3" so an FQL entropy is never read against an LLM one.
#: Its `wsa_label` is likewise a fuzzy-state label emitted by the kernel, not an
#: agent self-report, so its ibr_pct is a structural analogue and not the same
#: measurement as the LLM IBR.
FQL_SKILLS = ["increase_demand", "maintain_demand", "decrease_demand"]
FQL_INCREASE = frozenset({"increase_demand"})
ALL_SHARE_COLS = SKILLS + [s for s in FQL_SKILLS if s not in SKILLS]
DEAD_POOL_FT = 895.0
SHORTAGE_FT = 1075.0     # FQL_BASELINE_NOTE_2026-08-06.md: "years whose mean
                         # elevation falls below 1,075 ft"


def _year(row) -> int:
    v = (row.get("year") or "").strip()
    if not v:
        raise PrepError("row with an empty `year`")
    return int(float(v))


def _per_year(rows, act_fn, high_fn, vocab=None, inc=None):
    """{year: metric dict} for one run at one action level.

    `vocab` is the legal action set (defaults to the five-skill LLM registry) and
    `inc` the subset counted as a demand increase. Any action outside `vocab` is
    counted in n_action_off_registry and EXCLUDED from the entropy base -- it is
    never folded into a bucket it does not belong to.
    """
    vocab = list(vocab or SKILLS)
    inc = inc if inc is not None else L.INCREASE
    by = {}
    for r in rows:
        by.setdefault(_year(r), []).append(r)
    out = {}
    for y, rs in sorted(by.items()):
        counts = {s: 0 for s in vocab}
        other = 0
        for r in rs:
            a = act_fn(r)
            if a in counts:
                counts[a] += 1
            else:
                other += 1
        # MEASURED on the released corpus: 108 audit rows across the ten gemma3:4b
        # runs (105 governed, 3 no-validator) carry an EMPTY `proposed_skill`.
        # `final_skill` and `yearly_decision` are never off-registry. Those rows are
        # counted in n_action_off_registry, kept in every rate denominator, and
        # excluded from the entropy base -- they are not folded into any bucket.
        if other == len(rs):
            raise PrepError(f"year {y}: every row is off-vocabulary {vocab}")
        den = [r for r in rs if high_fn(r)]
        num = sum(1 for r in den if act_fn(r) in inc)
        rec = {
            "n_rows": len(rs),
            "n_high": len(den),
            "n_action_off_registry": other,
            "ibr_pct": (100.0 * num / len(den)) if den else float("nan"),
            "increase_rate_pct": 100.0 * sum(1 for r in rs if act_fn(r) in inc) / len(rs),
            "ehe_yearly": C.normalized_entropy(counts, k=len(vocab)),
        }
        for s in ALL_SHARE_COLS:
            # a skill outside this run's vocabulary is NA, never 0 -- "the arm never
            # chose it" and "the arm cannot choose it" are different facts.
            rec[f"share_{s}"] = (100.0 * counts[s] / len(rs)) if s in counts else float("nan")
        out[y] = rec
    return out


def _mead_per_year(sim_rows):
    """{year: (mean elevation ft, n distinct values that year)}.

    lake_mead_level is a basin-level state replicated onto every agent row; if it
    is NOT constant within a year that is a data fact and is reported, not averaged
    away silently.
    """
    by = {}
    for r in sim_rows:
        v = (r.get("lake_mead_level") or "").strip()
        if not v:
            raise PrepError("simulation_log row with an empty lake_mead_level")
        by.setdefault(_year(r), []).append(float(v))
    return {y: (sum(vs) / len(vs), len(set(vs))) for y, vs in sorted(by.items())}


def main() -> int:
    C.banner("R1  irrigation per-year trajectories + Lake Mead bands")
    seeds = L.paired_seeds(PREFIX)
    print(f"LLM paired seeds: {seeds}")

    traj_rows, mead_rows = [], []

    # ---------------- LLM arms -------------------------------------------------
    for arm in ("governed", "ungoverned"):
        for s in seeds:
            d = L.run_dir(arm, PREFIX, s)
            sim = L.load_run(d)
            aud = L.load_audit(d)
            C.require_cols(sim, ["year", "yearly_decision", "wsa_label",
                                 "lake_mead_level"], f"{arm} seed {s} sim")
            C.require_cols(aud, ["year", "proposed_skill", "final_skill", "status",
                                 "construct_WSA_LABEL"], f"{arm} seed {s} audit")
            if len(sim) != L.EXPECTED_ROWS:
                raise PrepError(f"{arm} seed {s}: sim has {len(sim)} rows")

            levels = {
                "sim": (_per_year(sim, L.action, L.is_high)),
                "proposal": _per_year(aud, C.irr_proposal,
                                      lambda r: C.irr_wsa_audit(r) in L.HIGH),
                "final": _per_year(aud, C.irr_final,
                                   lambda r: C.irr_wsa_audit(r) in L.HIGH),
                "executed": _per_year(aud, C.irr_executed,
                                      lambda r: C.irr_wsa_audit(r) in L.HIGH),
            }
            for lvl, per in levels.items():
                for y, rec in per.items():
                    traj_rows.append({"arm": arm, "seed": s, "level": lvl, "year": y,
                                      **rec})

            for y, (mft, nuniq) in _mead_per_year(sim).items():
                mead_rows.append({"arm": arm, "seed": s, "year": y,
                                  "lake_mead_ft": mft,
                                  "n_distinct_values_in_year": nuniq})
        print(f"  {arm:11s} done ({len(seeds)} seeds)")

    # ---------------- FQL arms -------------------------------------------------
    for arm, root in FQL_ARMS.items():
        if not os.path.isdir(root):
            raise PrepError(f"missing FQL root {root}")
        sds = sorted(d for d in os.listdir(root)
                     if os.path.isdir(os.path.join(root, d)) and d.startswith("seed"))
        if not sds:
            raise PrepError(f"no seed dirs under {root}")
        for sd in sds:
            s = sd[len("seed"):]
            sim = C.read_csv(os.path.join(root, sd, "simulation_log.csv"))
            C.require_cols(sim, ["year", "yearly_decision", "wsa_label",
                                 "lake_mead_level"], f"{arm} {sd}")
            for y, rec in _per_year(sim, L.action, L.is_high,
                                    vocab=FQL_SKILLS, inc=FQL_INCREASE).items():
                traj_rows.append({"arm": arm, "seed": s, "level": "sim_fql3",
                                  "year": y, **rec})
            for y, (mft, nuniq) in _mead_per_year(sim).items():
                mead_rows.append({"arm": arm, "seed": s, "year": y,
                                  "lake_mead_ft": mft,
                                  "n_distinct_values_in_year": nuniq})
        print(f"  {arm:19s} done ({len(sds)} seeds: {','.join(x[4:] for x in sds)})")

    C.write_csv(
        "r1_irrigation_trajectories.csv",
        ["arm", "seed", "level", "year", "n_rows", "n_high", "n_action_off_registry",
         "ibr_pct", "increase_rate_pct", "ehe_yearly"]
        + [f"share_{s}" for s in ALL_SHARE_COLS],
        traj_rows)

    # band summary appended as arm-level rows with seed="MEAN"/"SD"
    band = {}
    for r in mead_rows:
        band.setdefault((r["arm"], r["year"]), []).append(r["lake_mead_ft"])
    for (arm, y), vs in sorted(band.items()):
        mead_rows.append({"arm": arm, "seed": "MEAN", "year": y,
                          "lake_mead_ft": C.mean(vs), "n_distinct_values_in_year": len(vs)})
        mead_rows.append({"arm": arm, "seed": "SD", "year": y,
                          "lake_mead_ft": C.sd(vs), "n_distinct_values_in_year": len(vs)})
    C.write_csv("r1_irrigation_mead.csv",
                ["arm", "seed", "year", "lake_mead_ft", "n_distinct_values_in_year"],
                mead_rows)

    # ---------------- console summary -----------------------------------------
    print("\n  Lake Mead, per arm (mean over years of the per-year across-agent mean;"
          "\n  min = smallest per-year mean; shortage years = per-year mean < 1075 ft):")
    print(f"    {'arm':20s} {'seeds':>5s} {'mean ft':>9s} {'min ft (mean+/-sd)':>22s} "
          f"{'shortage yr (mean+/-sd)':>24s} {'dead-pool seeds':>16s}")
    per_arm = {}
    for r in mead_rows:
        if r["seed"] in ("MEAN", "SD"):
            continue
        per_arm.setdefault(r["arm"], {}).setdefault(r["seed"], []).append(
            (r["year"], r["lake_mead_ft"]))
    for arm in ["governed", "ungoverned", "fql_validators_on", "fql_validators_off"]:
        d = per_arm[arm]
        mins, shorts, means, dead = [], [], [], 0
        for s, ys in d.items():
            vals = [v for _, v in sorted(ys)]
            mins.append(min(vals))
            shorts.append(sum(1 for v in vals if v < SHORTAGE_FT))
            means.append(C.mean(vals))
            dead += 1 if min(vals) <= DEAD_POOL_FT + 1e-9 else 0
        print(f"    {arm:20s} {len(d):>5d} {C.mean(means):9.1f} "
              f"{C.mean(mins):11.1f} +/- {C.sd(mins):5.1f} "
              f"{C.mean(shorts):14.1f} +/- {C.sd(shorts):4.1f} "
              f"{dead:>12d}/{len(d)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
