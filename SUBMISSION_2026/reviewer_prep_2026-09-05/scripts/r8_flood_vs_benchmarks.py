"""R8 -- flood action shares for the three arms, checked against BOTH benchmark tables.

WHAT IT ANSWERS
  Two questions a reviewer asks together. First: how do the governed LLM, the
  no-validator LLM and the rule-based PMT baseline distribute their actions?
  Second: the repository ships TWO empirical-benchmark tables with the same metric
  names and DIFFERENT ranges -- which metrics do they disagree on, and is the count
  six or seven?

THE THREE ARMS
  governed / ungoverned   examples/single_agent/results/{JOH_FINAL,
                          JOH_ABLATION_DISABLED}/gemma3_4b/... , 5 runs each.
                          Action distribution from simulation_log `yearly_decision`
                          with `relocated` -> `relocate` (the published EHE basis).
  rulebased_pmt           examples/single_agent/results/rulebased/Run_1..3.
                          THIS ARM WRITES A DIFFERENT VOCABULARY: six cumulative
                          state labels ("Both Flood Insurance and House Elevation",
                          "Only Flood Insurance", "Do Nothing", "Only House
                          Elevation", "Already relocated", "Relocate"), not the four
                          yearly action types. Any four-way share for it therefore
                          depends on how the "Both" label is folded in, and there is
                          no fold that is obviously right. Three folds are computed
                          and reported side by side rather than one being chosen
                          silently. Note the published normalize_action() would send
                          "Both..." to do_nothing, because the label is absent from
                          its mapping and the function's tail defaults to do_nothing.

BENCHMARK TABLES -- read from file, diffed here
  A  examples/multi_agent/flood/paper3/analysis/empirical_benchmarks.py
     (FLOOD_BENCHMARKS, 8 Benchmark objects)
  B  examples/multi_agent/flood/paper3/analysis/validation/benchmarks/flood.py
     (EMPIRICAL_BENCHMARKS, 17 entries incl. institutional-trajectory ones)
  `python -m broker.calibration.benchmark_diff` does not exist on this branch, so
  the two tables are parsed and diffed here. Both are parsed from source text with a
  regex rather than imported, because importing A pulls in pandas and the paper3
  package path.

WHAT CAN AND CANNOT BE CHECKED AGAINST THEM
  The single-agent flood corpus carries agent-year state columns (elevated,
  has_insurance, relocated) and so supports insurance_rate_all, elevation_rate and
  buyout_rate. It carries no flood-event flag, no tenure, no flood_zone and no
  marginalised-group flag, so do_nothing_rate_postflood, insurance_rate_sfha,
  renter/rl_uninsured_rate, mg_adaptation_gap, insurance_lapse_rate and every
  institutional-trajectory benchmark are NOT AVAILABLE on this corpus and are
  written as such with the missing column named.

OUTPUT
  out/r8_flood_vs_benchmarks.csv   two blocks: `action_share` rows and
  `benchmark_check` rows (including the table-vs-table disagreement rows).

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r8_flood_vs_benchmarks.py
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import PrepError  # noqa: E402

MODEL = "gemma3_4b"
ARMS = {
    "governed": ("JOH_FINAL", "Group_C"),
    "ungoverned": ("JOH_ABLATION_DISABLED", "Group_C_disabled"),
}
RULEBASED = os.path.join(C.FLOOD_RESULTS, "rulebased")
P3 = os.path.join(C.REPO, "examples", "multi_agent", "flood", "paper3", "analysis")
TABLE_A = os.path.join(P3, "empirical_benchmarks.py")
TABLE_B = os.path.join(P3, "validation", "benchmarks", "flood.py")

#: The three folds of the rule-based "Both Flood Insurance and House Elevation"
#: label into the four yearly action types. None is privileged.
RB_FOLDS = {
    "both_to_do_nothing_published_normalize": "do_nothing",
    "both_to_elevate_house": "elevate_house",
    "both_to_buy_insurance": "buy_insurance",
}
RB_BASE = {
    "Only Flood Insurance": "buy_insurance",
    "Do Nothing": "do_nothing",
    "Only House Elevation": "elevate_house",
    "Already relocated": "relocate",
    "Relocate": "relocate",
}

#: metric-name synonyms between the two tables. Table A's "insurance_rate" is the
#: SFHA benchmark (its name and description say so) and table B calls the same thing
#: "insurance_rate_sfha". Table A's "rl_uninsured_rate" (repetitive-loss properties)
#: and table B's "renter_uninsured_rate" (renters) are DIFFERENT populations that
#: happen to carry the same range; they are reported as a name-only pair, not merged.
SYNONYM = {"insurance_rate": "insurance_rate_sfha"}
NAME_ONLY_PAIR = ("rl_uninsured_rate", "renter_uninsured_rate")


def parse_table_a(path):
    src = open(path, encoding="utf-8").read()
    blocks = re.findall(
        r'Benchmark\(\s*name="([^"]+)",\s*metric="([^"]+)",\s*rate_low=([\d.]+),'
        r'\s*rate_high=([\d.]+),', src)
    if not blocks:
        raise PrepError(f"could not parse any Benchmark(...) out of {path}")
    return {m: (float(lo), float(hi), name) for name, m, lo, hi in blocks}


def parse_table_b(path):
    src = open(path, encoding="utf-8").read()
    body = src.split("EMPIRICAL_BENCHMARKS = {", 1)[1]
    blocks = re.findall(r'"([a-z0-9_]+)":\s*\{\s*"range":\s*\(([-\d.]+),\s*([-\d.]+)\)',
                        body)
    if not blocks:
        raise PrepError(f"could not parse any range out of {path}")
    return {m: (float(lo), float(hi), m) for m, lo, hi in blocks}


def _shares(counts):
    t = sum(counts.values())
    return {k: v / t for k, v in counts.items()}, t


def main() -> int:
    C.banner("R8  flood action shares vs the two benchmark tables")
    rows = []

    # ---------- LLM arms ------------------------------------------------------
    finals = {}
    for arm, (root, group) in ARMS.items():
        per_run = []
        for run, (seed, rd) in C.flood_runs(root, MODEL, group).items():
            sim = C.read_csv(os.path.join(rd, C.FLOOD_SIM))
            C.require_cols(sim, ["yearly_decision", "year", "elevated",
                                 "has_insurance", "relocated"], f"{arm}/{run}")
            counts = {a: 0 for a in C.FLOOD_ACTION_ORDER}
            for r in sim:
                counts[C.flood_normalize_action(r.get("yearly_decision"))] += 1
            sh, t = _shares(counts)
            last = max(int(float(r["year"])) for r in sim)
            fin = [r for r in sim if int(float(r["year"])) == last]
            per_run.append({
                "run": run, "seed": seed, "n": t, "ehe": C.normalized_entropy(counts, 4),
                **{f"share_{k}": 100.0 * v for k, v in sh.items()},
                "elevation_rate": sum(1 for r in fin
                                      if str(r["elevated"]).strip().lower() == "true") / len(fin),
                "insurance_rate_all": sum(1 for r in fin
                                          if str(r["has_insurance"]).strip().lower() == "true") / len(fin),
                "buyout_rate": sum(1 for r in fin
                                   if str(r["relocated"]).strip().lower() == "true") / len(fin),
            })
        finals[arm] = per_run
        for k in ["ehe"] + [f"share_{a}" for a in C.FLOOD_ACTION_ORDER]:
            vals = [r[k] for r in per_run]
            rows.append({"block": "action_share", "arm": arm, "variant": "simulation_log",
                         "metric": k, "mean": C.mean(vals), "sd": C.sd(vals),
                         "n_runs": len(vals),
                         "per_run": " ".join(f"{v:.4f}" for v in vals),
                         "table": "", "range_low": "", "range_high": "",
                         "in_range": "", "note": ""})

    # ---------- rule-based PMT -----------------------------------------------
    if not os.path.isdir(RULEBASED):
        raise PrepError(f"missing rule-based arm at {RULEBASED}")
    rb_runs = sorted(d for d in os.listdir(RULEBASED)
                     if os.path.isdir(os.path.join(RULEBASED, d)))
    rb_final = []
    for fold_name, both_to in RB_FOLDS.items():
        per_run = []
        for run in rb_runs:
            sim = C.read_csv(os.path.join(RULEBASED, run, "simulation_log.csv"))
            C.require_cols(sim, ["decision", "year", "elevated", "has_insurance",
                                 "relocated"], f"rulebased/{run}")
            mapping = dict(RB_BASE)
            mapping["Both Flood Insurance and House Elevation"] = both_to
            counts = {a: 0 for a in C.FLOOD_ACTION_ORDER}
            for r in sim:
                lab = (r.get("decision") or "").strip()
                if lab not in mapping:
                    raise PrepError(f"rulebased/{run}: unmapped decision label {lab!r}")
                counts[mapping[lab]] += 1
            sh, t = _shares(counts)
            per_run.append({"ehe": C.normalized_entropy(counts, 4),
                            **{f"share_{k}": 100.0 * v for k, v in sh.items()}})
            if fold_name == "both_to_do_nothing_published_normalize":
                last = max(int(float(r["year"])) for r in sim)
                fin = [r for r in sim if int(float(r["year"])) == last]
                rb_final.append({
                    "elevation_rate": sum(1 for r in fin if str(r["elevated"]).strip().lower() == "true") / len(fin),
                    "insurance_rate_all": sum(1 for r in fin if str(r["has_insurance"]).strip().lower() == "true") / len(fin),
                    "buyout_rate": sum(1 for r in fin if str(r["relocated"]).strip().lower() == "true") / len(fin)})
        for k in ["ehe"] + [f"share_{a}" for a in C.FLOOD_ACTION_ORDER]:
            vals = [r[k] for r in per_run]
            rows.append({"block": "action_share", "arm": "rulebased_pmt",
                         "variant": fold_name, "metric": k,
                         "mean": C.mean(vals), "sd": C.sd(vals), "n_runs": len(vals),
                         "per_run": " ".join(f"{v:.4f}" for v in vals),
                         "table": "", "range_low": "", "range_high": "",
                         "in_range": "", "note": ""})

    # ---------- benchmark tables ---------------------------------------------
    A, B = parse_table_a(TABLE_A), parse_table_b(TABLE_B)
    print(f"  table A ({os.path.relpath(TABLE_A, C.REPO)}): {len(A)} metrics")
    print(f"  table B ({os.path.relpath(TABLE_B, C.REPO)}): {len(B)} metrics")

    computed = {
        "governed": {k: C.mean([r[k] for r in finals["governed"]])
                     for k in ("elevation_rate", "insurance_rate_all", "buyout_rate")},
        "ungoverned": {k: C.mean([r[k] for r in finals["ungoverned"]])
                       for k in ("elevation_rate", "insurance_rate_all", "buyout_rate")},
        "rulebased_pmt": {k: C.mean([r[k] for r in rb_final])
                          for k in ("elevation_rate", "insurance_rate_all", "buyout_rate")},
    }
    #: A computed value can sit outside a benchmark range because the model is wrong
    #: OR because the two numbers count different people. Elevation is the second
    #: case and the row must say so, or the comparison reads as a failed validation
    #: when it is a denominator mismatch.
    POPULATION_NOTE = {
        "elevation_rate": "corpus denominator = all agents (no tenure column); "
                          "benchmark A = homeowners over ~10 yr, benchmark B = "
                          "tenure==Owner; same cumulative construct, different "
                          "population",
    }
    NOT_AVAILABLE = {
        "insurance_rate_sfha": "no flood_zone column in the single-agent corpus",
        "insurance_rate": "no flood_zone column in the single-agent corpus",
        "do_nothing_rate_postflood": "no flooded_this_year column in the LLM simulation_log",
        "mg_adaptation_gap": "no marginalised-group flag in the single-agent corpus",
        "rl_uninsured_rate": "no repetitive-loss flag in the single-agent corpus",
        "renter_uninsured_rate": "no tenure column in the single-agent corpus",
        "insurance_lapse_rate": "requires per-agent trace outcome fields absent here",
    }
    for tname, tbl in (("A_empirical_benchmarks", A), ("B_validation_benchmarks", B)):
        for metric, (lo, hi, _) in sorted(tbl.items()):
            for arm, vals in computed.items():
                if metric in vals:
                    v = vals[metric]
                    rows.append({"block": "benchmark_check", "arm": arm, "variant": "",
                                 "metric": metric, "mean": v, "sd": float("nan"),
                                 "n_runs": len(finals.get(arm, rb_final)),
                                 "per_run": "", "table": tname, "range_low": lo,
                                 "range_high": hi,
                                 "in_range": "Y" if lo <= v <= hi else "N",
                                 "note": POPULATION_NOTE.get(metric, "")})
                else:
                    rows.append({"block": "benchmark_check", "arm": arm, "variant": "",
                                 "metric": metric, "mean": float("nan"),
                                 "sd": float("nan"), "n_runs": 0, "per_run": "",
                                 "table": tname, "range_low": lo, "range_high": hi,
                                 "in_range": "NOT AVAILABLE",
                                 "note": NOT_AVAILABLE.get(
                                     metric, "metric not computable from this corpus")})

    # ---------- table-vs-table disagreement -----------------------------------
    a_norm = {SYNONYM.get(k, k): v for k, v in A.items()}
    shared = sorted(set(a_norm) & set(B))
    disagree_shared = [m for m in shared if (a_norm[m][0], a_norm[m][1]) != (B[m][0], B[m][1])]
    a_only = sorted(set(a_norm) - set(B))
    b_only = sorted(set(B) - set(a_norm))
    for m in shared:
        rows.append({"block": "table_vs_table", "arm": "", "variant": "", "metric": m,
                     "mean": float("nan"), "sd": float("nan"), "n_runs": 0, "per_run": "",
                     "table": "A_vs_B",
                     "range_low": f"A={a_norm[m][0]}-{a_norm[m][1]}",
                     "range_high": f"B={B[m][0]}-{B[m][1]}",
                     "in_range": "DISAGREE" if m in disagree_shared else "AGREE",
                     "note": "shared metric name (after the insurance_rate ->"
                             " insurance_rate_sfha synonym)"})
    for m in a_only:
        rows.append({"block": "table_vs_table", "arm": "", "variant": "", "metric": m,
                     "mean": float("nan"), "sd": float("nan"), "n_runs": 0, "per_run": "",
                     "table": "A_only", "range_low": a_norm[m][0], "range_high": a_norm[m][1],
                     "in_range": "A ONLY", "note": "no counterpart name in table B"})

    C.write_csv("r8_flood_vs_benchmarks.csv",
                ["block", "arm", "variant", "metric", "mean", "sd", "n_runs", "per_run",
                 "table", "range_low", "range_high", "in_range", "note"], rows)

    print("\n  EHE (H/log2(4)) per arm, mean +/- sd over runs:")
    for r in rows:
        if r["block"] == "action_share" and r["metric"] == "ehe":
            print(f"    {r['arm']:14s} {r['variant']:38s} {r['mean']:.3f} +/- {r['sd']:.3f}")
    print("    published Extended Data Table 2: 0.861 / 0.815 / 0.583")

    print(f"\n  table A vs table B, shared metric names: {len(shared)}")
    print(f"    DISAGREE on range: {len(disagree_shared)} -> {disagree_shared}")
    print(f"    A only: {a_only}")
    print(f"    B only (institutional/trajectory + the renter metric): {len(b_only)}")
    print(f"\n  SETTLING THE COUNT: {len(disagree_shared)} shared metric names carry "
          f"different ranges.")
    print(f"    Add the name-only pair {NAME_ONLY_PAIR[0]} (table A) vs "
          f"{NAME_ONLY_PAIR[1]} (table B) -- same range, different population -- and "
          f"the count becomes {len(disagree_shared) + 1}.")
    print("    So both figures are defensible: the smaller one counts range "
          "disagreements on identical names; the larger one also counts the "
          "metric that exists in one table only under a different name.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
