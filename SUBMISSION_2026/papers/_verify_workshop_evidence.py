"""ADVERSARIAL RE-DERIVATION of SUBMISSION_2026/papers/workshop_evidence.py.

Written to disagree. Nothing is imported from _loader.py or from workshop_evidence.py -- the
column names, the INCREASE/HIGH sets and the arm->directory mapping are re-typed from the brief,
and the counting is structured differently on purpose:

  * csv.reader + header-index lookup, not csv.DictReader  (so a duplicated header column, which
    the irrigation audit file has, cannot silently change which value is read)
  * per-seed accumulator dicts built in one pass, then reduced -- not a per-file rate function
  * every rate is computed on BOTH candidate denominators and both are printed, so a denominator
    choice can never hide inside a helper

It also runs five checks the original script does not:

  V4  is the "executed action" imputation (REJECTED -> maintain_demand) TRUE in the data?
      Tested against simulation_log.request year-over-year and magnitude_pct, which are the
      physical record of what the water request actually did.
  V5  enforcement pressure on the all-rows denominator vs the parsed-appraisal denominator.
  V6  regime separation re-tested on the paired-seed shift as well as the all-runs shift.
  V7  the flood seed labelling, read out of every reproducibility_manifest.json.
  V8  the corpus count, and a hunt for the skeleton's 432,083.

Usage:  python SUBMISSION_2026/papers/_verify_workshop_evidence.py
Read-only.
"""
from __future__ import annotations

import csv
import glob
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
IRR = os.path.join(REPO, "examples", "irrigation_abm", "results")
FLD = os.path.join(REPO, "examples", "single_agent", "results")

# Re-typed from the brief, deliberately not imported.
INCREASE_ACTIONS = ("increase_large", "increase_small")
HIGH_LABELS = ("H", "VH")

MODEL_PREFIX = {                 # display -> directory infix
    "gemma3:4b": "",
    "gemma3:12b": "gemma3_12b_",
    "gemma4:e2b": "gemma4_e2b_",
    "gemma4:e4b": "gemma4_e4b_",
    "ministral3:8b": "ministral3_8b_",
}
ARM_DIR = {"governed": "production", "ungoverned": "ungoverned"}

FLOOD_PAIRS = {"JOH_FINAL": "JOH_ABLATION_DISABLED",
               "JOH_FINAL_v2": "JOH_ABLATION_DISABLED_v2"}

FAIL = []


def note(ok: bool, msg: str) -> None:
    print(f"    [{'ok ' if ok else 'DIFF'}] {msg}")
    if not ok:
        FAIL.append(msg)


def read_indexed(path):
    """(header list, list of row lists). No dict -- index lookups only."""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    return rows[0], rows[1:]


def col(header, name):
    """FIRST index of `name`. csv.DictReader keeps the LAST; the irrigation audit header
    contains construct_completeness twice, so the two disagree in principle."""
    return header.index(name)


# ---------------------------------------------------------------------------
# V1/V2  anchor four headline numbers, per-seed then averaged
# ---------------------------------------------------------------------------
def anchor_rates(model_prefix):
    """{arm: {'cond': [...per seed], 'unc': [...], 'seeds': [...]}} from simulation_log.csv."""
    out = {}
    for arm, pre in ARM_DIR.items():
        per_seed = {}
        pat = os.path.join(IRR, f"{pre}_v21_42yr_{model_prefix}seed*")
        for d in sorted(glob.glob(pat)):
            seed = os.path.basename(d).rsplit("seed", 1)[1]
            hdr, rows = read_indexed(os.path.join(d, "simulation_log.csv"))
            i_act, i_wsa = col(hdr, "yearly_decision"), col(hdr, "wsa_label")
            n = inc = hi = hi_inc = 0
            for r in rows:
                n += 1
                is_inc = r[i_act].strip() in INCREASE_ACTIONS
                inc += is_inc
                if r[i_wsa].strip().upper() in HIGH_LABELS:
                    hi += 1
                    hi_inc += is_inc
            per_seed[seed] = (hi_inc, hi, inc, n)
        out[arm] = per_seed
    return out


def section_anchor():
    print("\nV1/V2  IRRIGATION conditional + unconditional, independent re-derivation")
    print("       (simulation_log.csv, yearly_decision x wsa_label, index-based reader)")
    expect = {  # what workshop_evidence.py printed, to be contradicted or confirmed
        "gemma3:4b": (36.05, 59.07, 40.90, 62.52),
        "gemma3:12b": (5.45, 16.89, 41.36, 41.52),
        "gemma4:e2b": (12.71, 31.65, 22.80, 38.05),
        "gemma4:e4b": (23.67, 41.08, 36.36, 44.87),
        "ministral3:8b": (2.69, 5.10, 52.01, 30.89),
    }
    print(f"    {'cell':14s} {'paired seeds':<16s} {'cond gov':>9s} {'cond ung':>9s} "
          f"{'unc gov':>9s} {'unc ung':>9s}   {'pooled cond gov':>16s}")
    for label, pre in MODEL_PREFIX.items():
        d = anchor_rates(pre)
        shared = sorted(set(d["governed"]) & set(d["ungoverned"]))
        vals = []
        pooled_gov = None
        for arm in ("governed", "ungoverned"):
            conds, uncs = [], []
            P = [0, 0, 0, 0]
            for s in shared:
                hi_inc, hi, inc, n = d[arm][s]
                conds.append(100.0 * hi_inc / hi)
                uncs.append(100.0 * inc / n)
                for j, v in enumerate((hi_inc, hi, inc, n)):
                    P[j] += v
            vals += [sum(conds) / len(conds), sum(uncs) / len(uncs)]
            if arm == "governed":
                pooled_gov = 100.0 * P[0] / P[1]
        cg, ug, cu, uu = vals[0], vals[2], vals[1], vals[3]
        print(f"    {label:14s} {','.join(shared):<16s} {cg:>8.2f}% {ug:>8.2f}% "
              f"{cu:>8.2f}% {uu:>8.2f}%   {pooled_gov:>15.2f}%")
        e = expect[label]
        for got, want, what in ((cg, e[0], "cond gov"), (ug, e[1], "cond ung"),
                                (cu, e[2], "unc gov"), (uu, e[3], "unc ung")):
            if abs(round(got, 2) - want) > 0.005:
                note(False, f"{label} {what}: workshop_evidence says {want}, I get {got:.4f}")
        if label == "gemma3:4b":
            note(abs(cg - 36.0521) < 0.001 and abs(ug - 59.0700) < 0.001
                 and abs(cu - 40.8974) < 0.001 and abs(uu - 62.5214) < 0.001,
                 f"ANCHOR raw {cg:.4f}/{ug:.4f}/{cu:.4f}/{uu:.4f} "
                 f"vs claimed 36.0521/59.0700/40.8974/62.5214")
            note(abs(pooled_gov - cg) > 0.1,
                 f"pooled ({pooled_gov:.4f}) differs from mean-of-seeds ({cg:.4f}) -- "
                 f"the convention IS load-bearing")


# ---------------------------------------------------------------------------
# V3  per-cell pressure and shift, both testbeds, both denominators
# ---------------------------------------------------------------------------
def scan_audit(paths, label_col):
    """(n_all, n_parsed, high_parsed, rej_all, rej_parsed)."""
    n_all = n_par = hi = rej_all = rej_par = 0
    for p in paths:
        hdr, rows = read_indexed(p)
        i_lab, i_st = col(hdr, label_col), col(hdr, "status")
        for r in rows:
            n_all += 1
            rejected = r[i_st].strip().startswith("REJECTED")
            rej_all += rejected
            if not r[i_lab].strip():
                continue
            n_par += 1
            rej_par += rejected
            hi += r[i_lab].strip().upper() in HIGH_LABELS
    return n_all, n_par, hi, rej_all, rej_par


def irr_audits(arm, pre):
    out = {}
    for d in sorted(glob.glob(os.path.join(IRR, f"{ARM_DIR[arm]}_v21_42yr_{pre}seed*"))):
        f = os.path.join(d, "irrigation_farmer_governance_audit.csv")
        if os.path.isfile(f):
            out[os.path.basename(d).rsplit("seed", 1)[1]] = f
    return out


def flood_audits(base, model, sub):
    out = {}
    for d in sorted(glob.glob(os.path.join(FLD, base, model, sub, "Run_*"))):
        hits = sorted(glob.glob(os.path.join(d, "*governance_audit.csv")))
        if not hits:
            continue
        man = os.path.join(d, "reproducibility_manifest.json")
        seed = "NA"
        if os.path.isfile(man):
            seed = str(json.load(open(man, encoding="utf-8")).get("seed", "NA"))
        out[seed] = hits[0]
    return out


def all_cells():
    cells = []
    for label, pre in MODEL_PREFIX.items():
        cells.append(("irrigation " + label, "irrigation", "construct_WSA_LABEL",
                      irr_audits("governed", pre), irr_audits("ungoverned", pre)))
    for gb, ub in FLOOD_PAIRS.items():
        for m in sorted(os.listdir(os.path.join(FLD, gb))):
            if not os.path.isdir(os.path.join(FLD, gb, m)) or m.startswith("_"):
                continue
            pretty = m.split("_")[0] + ":" + "_".join(m.split("_")[1:])
            cells.append(("flood " + pretty, "flood", "construct_TP_LABEL",
                          flood_audits(gb, m, "Group_C"),
                          flood_audits(ub, m, "Group_C_disabled")))
    return cells


def section_cells():
    print("\nV3/V5  PER-CELL pressure and shift -- and pressure on BOTH denominators")
    print("       claimed pressure/shift come from workshop_evidence.py's stdout table")
    claimed = {
        "irrigation ministral3:8b": (62.63, 32.97), "irrigation gemma4:e4b": (56.29, 43.38),
        "irrigation gemma3:12b": (49.52, 21.26), "irrigation gemma3:4b": (39.10, 45.50),
        "irrigation gemma4:e2b": (28.08, 47.53), "flood gemma3:4b": (0.85, -1.24),
        "flood gemma4:e4b": (0.47, 6.25), "flood gemma4:26b": (0.12, 2.92),
        "flood ministral3:3b": (0.11, -0.22), "flood ministral3:8b": (0.02, -3.69),
        "flood gemma3:12b": (0.02, -1.64), "flood gemma3:27b": (0.00, 1.22),
        "flood ministral3:14b": (0.00, 0.48), "flood gemma4:e2b": (0.00, 0.97),
    }
    print(f"    {'cell':24s} {'%rej parsed':>11s} {'%rej ALL':>9s} {'delta':>7s} "
          f"{'shift':>8s} {'shift paired':>13s}  balance")
    table = []
    for name, testbed, lab, gov, ung in all_cells():
        gA, gP, gH, gRa, gRp = scan_audit(list(gov.values()), lab)
        uA, uP, uH, uRa, uRp = scan_audit(list(ung.values()), lab)
        rej_par = 100.0 * gRp / gP
        rej_all = 100.0 * gRa / gA
        shift = 100.0 * uH / uP - 100.0 * gH / gP
        shared = sorted(set(gov) & set(ung))
        if shared:
            _, gP2, gH2, _, _ = scan_audit([gov[s] for s in shared], lab)
            _, uP2, uH2, _, _ = scan_audit([ung[s] for s in shared], lab)
            paired = 100.0 * uH2 / uP2 - 100.0 * gH2 / gP2
        else:
            paired = float("nan")
        bal = "BALANCED" if sorted(gov) == sorted(ung) else "UNBALANCED"
        print(f"    {name:24s} {rej_par:>10.2f}% {rej_all:>8.2f}% {rej_all - rej_par:>+7.2f} "
              f"{shift:>+8.2f} {paired:>+13.2f}  {bal}")
        table.append((name, testbed, rej_par, rej_all, shift, paired))
        if name in claimed:
            cr, cs = claimed[name]
            if abs(round(rej_par, 2) - cr) > 0.005:
                note(False, f"{name} %rejected: claimed {cr}, I get {rej_par:.4f}")
            if abs(round(shift, 2) - cs) > 0.005:
                note(False, f"{name} shift: claimed {cs}, I get {shift:.4f}")
    note(len(table) == 14, f"cell count = {len(table)} (claimed 14)")
    return table


# ---------------------------------------------------------------------------
# V4  is the executed-action imputation true in the data?
# ---------------------------------------------------------------------------
def section_executed():
    print("\nV4  DOES a REJECTED proposal actually leave the water request unmoved?")
    print("    (the 0.86% figure rests on imputing maintain_demand; audit final_skill does NOT")
    print("     record it -- final_skill still holds the rejected increase. Testing physically.)")
    bad = moved = flat = 0
    seen_status = {}
    for pre in MODEL_PREFIX.values():
        for d in sorted(glob.glob(os.path.join(IRR, f"production_v21_42yr_{pre}seed*"))):
            hdr_a, ra = read_indexed(os.path.join(d, "irrigation_farmer_governance_audit.csv"))
            ia, iy, ist, ifs = (col(hdr_a, "agent_id"), col(hdr_a, "year"),
                                col(hdr_a, "status"), col(hdr_a, "final_skill"))
            hdr_s, rs = read_indexed(os.path.join(d, "simulation_log.csv"))
            sa, sy, sreq, smag = (col(hdr_s, "agent_id"), col(hdr_s, "year"),
                                  col(hdr_s, "request"), col(hdr_s, "magnitude_pct"))
            req = {(r[sa], int(r[sy])): (float(r[sreq]), float(r[smag] or 0)) for r in rs}
            for r in ra:
                st = r[ist].strip()
                seen_status[st] = seen_status.get(st, 0) + 1
                if not st.startswith("REJECTED"):
                    continue
                k = (r[ia], int(r[iy]))
                prev = req.get((r[ia], int(r[iy]) - 1))
                cur = req.get(k)
                if cur is None:
                    continue
                if abs(cur[1]) > 1e-9:
                    bad += 1
                elif prev is not None:
                    if abs(cur[0] - prev[0]) > 1e-6:
                        moved += 1
                    else:
                        flat += 1
    print(f"    statuses seen across all 21 governed irrigation runs: {seen_status}")
    print(f"    REJECTED* rows whose request was UNCHANGED vs the prior year : {flat:,}")
    print(f"    REJECTED* rows whose request MOVED                          : {moved:,}")
    print(f"    REJECTED* rows with a non-zero magnitude_pct                : {bad:,}")
    note(moved == 0 and bad == 0,
         "imputation 'a rejected proposal never moved the water request' holds on every row"
         if moved == 0 and bad == 0 else
         f"imputation FAILS on {moved + bad} rows")


# ---------------------------------------------------------------------------
# V6  separation, on both the all-runs and the paired shift
# ---------------------------------------------------------------------------
def section_separation(table):
    print("\nV6  REGIME SEPARATION, retested")
    for which, idx in (("all runs", 4), ("paired seeds only", 5)):
        hi = [t for t in table if t[2] > 5.0]
        lo = [t for t in table if t[2] <= 5.0]
        shi = [t[idx] for t in hi]
        slo = [t[idx] for t in lo]
        margin = min(shi) - max(slo)
        print(f"    shift = {which:18s} high n={len(hi)} min {min(shi):+.2f} | "
              f"low n={len(lo)} max {max(slo):+.2f} | margin {margin:+.2f} pp -> "
              f"{'COMPLETE' if margin > 0 else 'OVERLAP'}")
        note(margin > 0, f"separation on {which} is complete (margin {margin:+.2f} pp)")
    hi = [t for t in table if t[2] > 5.0]
    lo = [t for t in table if t[2] <= 5.0]
    mh = sum(t[4] for t in hi) / len(hi)
    ml = sum(t[4] for t in lo) / len(lo)
    print(f"    mean shift: high {mh:+.2f} pp (claimed +38.13)   low {ml:+.2f} pp (claimed +0.56)")
    note(abs(round(mh, 2) - 38.13) < 0.005, f"high mean {mh:.4f}")
    note(abs(round(ml, 2) - 0.56) < 0.005, f"low mean {ml:.4f}")
    # pressure gap
    print(f"    pressure gap: max low {max(t[2] for t in lo):.2f}% .. "
          f"min high {min(t[2] for t in hi):.2f}%  (no cell inside)")


# ---------------------------------------------------------------------------
# V7  flood seed labelling, from the manifests
# ---------------------------------------------------------------------------
def section_seeds():
    print("\nV7  FLOOD seed labelling, read from every reproducibility_manifest.json")
    for gb, ub in FLOOD_PAIRS.items():
        for m in sorted(os.listdir(os.path.join(FLD, gb))):
            if not os.path.isdir(os.path.join(FLD, gb, m)) or m.startswith("_"):
                continue
            g = flood_audits(gb, m, "Group_C")
            u = flood_audits(ub, m, "Group_C_disabled")
            mark = "" if sorted(g) == sorted(u) else "   <- UNBALANCED"
            print(f"    {m:14s} gov {','.join(sorted(g, key=str)):<24s} "
                  f"ung {','.join(sorted(u, key=str)):<20s}{mark}")


# ---------------------------------------------------------------------------
# V8  corpus counting, and the hunt for 432,083
# ---------------------------------------------------------------------------
def section_corpus(table):
    print("\nV8  CORPUS SIZE -- the skeleton abstract claims 432,083 logged decisions")
    tot = 0
    for name, testbed, lab, gov, ung in all_cells():
        for f in list(gov.values()) + list(ung.values()):
            _, rows = read_indexed(f)
            tot += len(rows)
    print(f"    audit rows in the 14 cells (Group_C / Group_C_disabled only) : {tot:,}")
    note(tot == 216020, f"my count {tot:,} vs the script's CLAIM corpus_decision_rows: 216,020")
    # every audit csv anywhere under the two testbed trees
    wide = 0
    for pat in ("examples/irrigation_abm/results/**/*governance_audit.csv",
                "examples/single_agent/results/**/*governance_audit.csv"):
        for p in glob.glob(os.path.join(REPO, pat), recursive=True):
            _, rows = read_indexed(p)
            wide += len(rows)
    print(f"    EVERY *governance_audit.csv under both testbed trees          : {wide:,}")
    print(f"    2 x the 14-cell count                                         : {2 * tot:,}")
    note(tot == 216020 and wide != 432083,
         f"432,083 is not reproduced by either count (nearest: 2x = {2 * tot:,}, "
         f"off by {432083 - 2 * tot:+,})")


def main():
    print("INDEPENDENT RE-DERIVATION of workshop_evidence.py")
    print(f"repo   : {REPO}")
    print(f"python : {sys.version.split()[0]}")
    section_anchor()
    table = section_cells()
    section_executed()
    section_separation(table)
    section_seeds()
    section_corpus(table)
    print("\n" + "=" * 90)
    if FAIL:
        print(f"DISAGREEMENTS / FINDINGS: {len(FAIL)}")
        for f in FAIL:
            print("  * " + f)
    else:
        print("no disagreements")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
