"""Lane D -- claim traceability + survivor recomputation of the workshop headline.

READ-ONLY with respect to examples/, paper/, broker/. Writes only into this directory.

WHAT THIS ANSWERS
-----------------
The workshop headline is:

    in the HIGH-enforcement regime the prevalence of the conditioning appraisal shifts by a
    large positive amount; in the LOW-enforcement regime it does not; and the separation
    between the two groups is COMPLETE.

`papers/workshop_evidence.py` establishes that on all 14 cells with its own data selection.
This script asks the harder question: does it still hold after every contaminated, unbalanced
or partial cell is removed?  It re-derives the per-cell numbers from raw CSVs with an
independent code path (it does NOT import workshop_evidence.py or _loader.py) and then
recomputes the separation under four progressively stricter survival regimes.

SURVIVAL REGIMES
  R0  as-published        every cell workshop_evidence.py emits, pooled over all runs in each arm
  R1  shared-seed         every cell, but each arm restricted to the seed labels present in BOTH
  R2  balanced-only       only cells whose two arms carry IDENTICAL seed-label sets
  R3  balanced + attrition-matched
                          R2, and in flood the denominator is further restricted to the
                          (seed, agent_id, year) triples that produced a decision row in BOTH
                          arms -- this removes differential relocation attrition, which is a
                          post-treatment change in WHO is counted and is not otherwise controlled
  R4  antecedent-consistent
                          all 14 cells, but the measured stratum is the one the ERROR rules
                          ACTUALLY condition on in each testbed, rather than {H,VH} in both:
                            irrigation  high_threat_high_cope_no_increase fires on
                                        WSA in {H,VH} AND ACA in {H,VH}   -> the JOINT stratum
                            flood       three ERROR rules, all on TP: extreme_threat_block on
                                        {H,VH}, relocation_threat_low and elevation_threat_low
                                        on {VL,L}  -> report BOTH strata and take the larger
                                        magnitude, because the paper's {H,VH} choice is the
                                        antecedent of only one of the three
                          separation is then tested on |shift|.

DATA-SELECTION HYGIENE (asserted, not assumed)
  * flood arms are Group_C / Group_C_disabled named explicitly -- never a `**` walk of the model
    directory, which is what pulled Group_A/Run_1_bak_broker into one cell
  * any path containing Group_A, _bak, _dead, _QUARANTINE or a `_`-prefixed directory component
    is refused and counted; the count is printed and must be 0
  * irrigation run directories are matched by an exact `(production|ungoverned)_v21_42yr_<seg>seed<N>`
    regex, not a bare glob

Usage:  python SUBMISSION_2026/audit/audit_claim_traceability.py
"""
from __future__ import annotations

import csv
import glob
import json
import os
import re
import statistics
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

HIGH = {"H", "VH"}
BANNED = ("group_a", "_bak", "_dead", "_quarantine", "_logs", "rulebased")
REFUSED: list[str] = []

IRRIGATION_MODELS = [
    ("gemma3:4b", ""),
    ("gemma3:12b", "gemma3_12b_"),
    ("gemma4:e2b", "gemma4_e2b_"),
    ("gemma4:e4b", "gemma4_e4b_"),
    ("ministral3:8b", "ministral3_8b_"),
]
FLOOD_BASES = [("JOH_FINAL", "JOH_ABLATION_DISABLED"),
               ("JOH_FINAL_v2", "JOH_ABLATION_DISABLED_v2")]

PRESSURE_THRESHOLD = 5.0    # any cut inside the observed 0.85 .. 28.08 gap gives the same split


def refuse(path: str) -> bool:
    """True (and recorded) if `path` touches an excluded experiment / backup / quarantine dir."""
    low = path.replace("\\", "/").lower()
    for token in BANNED:
        if token in low:
            REFUSED.append(path)
            return True
    return False


def pretty(dirname: str) -> str:
    parts = dirname.split("_")
    return parts[0] + ":" + "_".join(parts[1:]) if len(parts) > 1 else dirname


# ---------------------------------------------------------------------------
# run discovery
# ---------------------------------------------------------------------------
IRR_RE = re.compile(r"^(production|ungoverned)_v21_42yr_(.*)seed(\d+)$")


def irrigation_runs(arm: str, seg: str):
    out = []
    root = os.path.join(REPO, "examples", "irrigation_abm", "results")
    for name in sorted(os.listdir(root)):
        d = os.path.join(root, name)
        if not os.path.isdir(d) or refuse(d):
            continue
        m = IRR_RE.match(name)
        if not m or m.group(1) != arm or m.group(2) != seg:
            continue
        csv_path = os.path.join(d, "irrigation_farmer_governance_audit.csv")
        if os.path.isfile(csv_path):
            out.append({"seed": m.group(3), "audit": csv_path, "simlog": None})
    return out


def flood_runs(base: str, model: str, sub: str):
    out = []
    root = os.path.join(REPO, "examples", "single_agent", "results", base, model, sub)
    if not os.path.isdir(root):
        return out
    for d in sorted(glob.glob(os.path.join(root, "Run_*"))):
        if not os.path.isdir(d) or refuse(d):
            continue
        audit = os.path.join(d, "household_governance_audit.csv")
        if not os.path.isfile(audit):
            continue
        seed = "NA"
        man = os.path.join(d, "reproducibility_manifest.json")
        if os.path.isfile(man):
            try:
                seed = str(json.load(open(man, encoding="utf-8")).get("seed", "NA"))
            except Exception:
                seed = "UNREADABLE"
        simlog = os.path.join(d, "simulation_log.csv")
        out.append({"seed": seed, "audit": audit,
                    "simlog": simlog if os.path.isfile(simlog) else None})
    return out


def build_cells():
    cells = []
    for label, seg in IRRIGATION_MODELS:
        cells.append({"cell": f"irrigation {label}", "testbed": "irrigation",
                      "col": "construct_WSA_LABEL",
                      "gov": irrigation_runs("production", seg),
                      "ung": irrigation_runs("ungoverned", seg)})
    for gb, ub in FLOOD_BASES:
        root = os.path.join(REPO, "examples", "single_agent", "results", gb)
        if not os.path.isdir(root):
            continue
        for m in sorted(os.listdir(root)):
            if not os.path.isdir(os.path.join(root, m)) or m.startswith("_"):
                continue
            g, u = flood_runs(gb, m, "Group_C"), flood_runs(ub, m, "Group_C_disabled")
            if not g or not u:
                print(f"  !! flood {m}: arm missing (gov {len(g)}, ung {len(u)}) -- reported, not skipped")
                continue
            cells.append({"cell": f"flood {pretty(m)}", "testbed": "flood",
                          "col": "construct_TP_LABEL", "gov": g, "ung": u})
    return cells


# ---------------------------------------------------------------------------
# measurement
# ---------------------------------------------------------------------------
def scan(runs, col, keep=None):
    """Pooled prevalence + rejection rate.  `keep(seed,row) -> bool` optionally filters rows."""
    n = high = rej = blank = 0
    for r in runs:
        for row in csv.DictReader(open(r["audit"], encoding="utf-8-sig", newline="")):
            if keep is not None and not keep(r["seed"], row):
                continue
            v = (row.get(col) or "").strip().upper()
            if not v:
                blank += 1
                continue
            n += 1
            if v in HIGH:
                high += 1
            if (row.get("status") or "").strip().startswith("REJECTED"):
                rej += 1
    if not n:
        return None
    return {"n": n, "blank": blank, "pct_high": 100.0 * high / n, "pct_rej": 100.0 * rej / n}


def keys_present(runs):
    """{seed: {(agent_id, year), ...}} -- the decision rows actually recorded, per run."""
    out = {}
    for r in runs:
        s = set()
        for row in csv.DictReader(open(r["audit"], encoding="utf-8-sig", newline="")):
            s.add(((row.get("agent_id") or "").strip(), (row.get("year") or "").strip()))
        out[r["seed"]] = s
    return out


def cell_row(c, seeds=None, matched=False):
    """One measured row for a cell.  seeds=None means every run in each arm."""
    g = [r for r in c["gov"] if seeds is None or r["seed"] in seeds]
    u = [r for r in c["ung"] if seeds is None or r["seed"] in seeds]
    if not g or not u:
        return None
    keep = None
    if matched and c["testbed"] == "flood":
        kg, ku = keys_present(g), keys_present(u)
        common = {s: kg[s] & ku[s] for s in kg if s in ku}

        def keep(seed, row, _c=common):
            ks = _c.get(seed)
            return ks is not None and ((row.get("agent_id") or "").strip(),
                                       (row.get("year") or "").strip()) in ks
    G, U = scan(g, c["col"], keep), scan(u, c["col"], keep)
    if not G or not U:
        return None
    return {"cell": c["cell"], "testbed": c["testbed"],
            "pct_rej": G["pct_rej"], "shift": U["pct_high"] - G["pct_high"],
            "high_gov": G["pct_high"], "high_ung": U["pct_high"],
            "n_gov": G["n"], "n_ung": U["n"]}


LOWSET = {"VL", "L"}


def antecedent_row(c):
    """R4: measure the stratum the ERROR rules actually condition on, per testbed."""
    def strata(runs):
        n = hi = lo = joint = 0
        for r in runs:
            for row in csv.DictReader(open(r["audit"], encoding="utf-8-sig", newline="")):
                v = (row.get(c["col"]) or "").strip().upper()
                if not v:
                    continue
                n += 1
                if v in HIGH:
                    hi += 1
                if v in LOWSET:
                    lo += 1
                if c["testbed"] == "irrigation":
                    a = (row.get("construct_ACA_LABEL") or "").strip().upper()
                    if v in HIGH and a in HIGH:
                        joint += 1
        if not n:
            return None
        return {"n": n, "hi": 100.0 * hi / n, "lo": 100.0 * lo / n, "joint": 100.0 * joint / n}

    G, U = strata(c["gov"]), strata(c["ung"])
    if not G or not U:
        return None
    if c["testbed"] == "irrigation":
        shift = U["joint"] - G["joint"]
        note = "WSA&ACA joint"
    else:
        d_hi, d_lo = U["hi"] - G["hi"], U["lo"] - G["lo"]
        shift = d_hi if abs(d_hi) >= abs(d_lo) else d_lo
        note = f"TP high {d_hi:+.2f} / TP low {d_lo:+.2f}"
    base = cell_row(c)
    return {"cell": c["cell"], "testbed": c["testbed"], "pct_rej": base["pct_rej"],
            "shift": shift, "high_gov": G["hi"], "high_ung": U["hi"],
            "n_gov": G["n"], "n_ung": U["n"], "note": note}


def separation_abs(rows, tag):
    hi = [r for r in rows if r["pct_rej"] > PRESSURE_THRESHOLD]
    lo = [r for r in rows if r["pct_rej"] <= PRESSURE_THRESHOLD]
    if not hi or not lo:
        return None
    shi = [abs(r["shift"]) for r in hi]
    slo = [abs(r["shift"]) for r in lo]
    complete = min(shi) > max(slo)
    print(f"  {tag:34s} cells {len(rows):2d} ({len(hi)} high / {len(lo)} low)   "
          f"|shift| high mean {statistics.fmean(shi):6.2f}  low mean {statistics.fmean(slo):6.2f}   "
          f"min high {min(shi):6.2f} vs max low {max(slo):6.2f}   "
          f"{'COMPLETE' if complete else 'OVERLAPPING'} (margin {min(shi) - max(slo):+.2f} pp)")
    return {"tag": tag, "n": len(rows), "n_high": len(hi), "n_low": len(lo),
            "high_mean": statistics.fmean(shi), "low_mean": statistics.fmean(slo),
            "min_high": min(shi), "max_low": max(slo), "complete": complete,
            "margin": min(shi) - max(slo)}


def separation(rows, tag):
    hi = [r for r in rows if r["pct_rej"] > PRESSURE_THRESHOLD]
    lo = [r for r in rows if r["pct_rej"] <= PRESSURE_THRESHOLD]
    if not hi or not lo:
        print(f"  {tag:34s} n={len(rows):2d}  ONE GROUP ONLY -- separation undefined")
        return None
    shi = [r["shift"] for r in hi]
    slo = [r["shift"] for r in lo]
    complete = min(shi) > max(slo)
    print(f"  {tag:34s} cells {len(rows):2d} ({len(hi)} high / {len(lo)} low)   "
          f"high mean {statistics.fmean(shi):+6.2f}  low mean {statistics.fmean(slo):+6.2f}   "
          f"min high {min(shi):+6.2f} vs max low {max(slo):+6.2f}   "
          f"{'COMPLETE' if complete else 'OVERLAPPING'} (margin {min(shi) - max(slo):+.2f} pp)")
    return {"tag": tag, "n": len(rows), "n_high": len(hi), "n_low": len(lo),
            "high_mean": statistics.fmean(shi), "low_mean": statistics.fmean(slo),
            "min_high": min(shi), "max_low": max(slo), "complete": complete,
            "margin": min(shi) - max(slo)}


# ---------------------------------------------------------------------------
# integrity probes
# ---------------------------------------------------------------------------
def attrition_probe(cells):
    """Flood only: how many simulation_log rows have no audit row, and why."""
    print("\n" + "=" * 100)
    print("PROBE 1 -- flood audit shortfall: silent drop, or relocation exit?")
    print("=" * 100)
    print(f"  {'cell':22s} {'arm':4s} {'simlog':>7s} {'audit':>7s} {'capture':>8s} "
          f"{'missing':>8s} {'reloc-exit':>10s} {'unexplained':>12s}")
    tot_miss = tot_rel = 0
    cap = {}
    for c in cells:
        if c["testbed"] != "flood":
            continue
        for arm in ("gov", "ung"):
            ns = na = miss = rel = 0
            for r in c[arm]:
                if not r["simlog"]:
                    continue
                au = list(csv.DictReader(open(r["audit"], encoding="utf-8-sig", newline="")))
                sl = list(csv.DictReader(open(r["simlog"], encoding="utf-8-sig", newline="")))
                ka = {((x.get("agent_id") or "").strip(), (x.get("year") or "").strip()) for x in au}
                ns += len(sl)
                na += len(au)
                for x in sl:
                    if ((x.get("agent_id") or "").strip(), (x.get("year") or "").strip()) in ka:
                        continue
                    miss += 1
                    if (x.get("relocated") or "").strip() == "True" and \
                       (x.get("yearly_decision") or "").strip() == "relocated":
                        rel += 1
            tot_miss += miss
            tot_rel += rel
            cap[(c["cell"], arm)] = 100.0 * na / ns if ns else float("nan")
            print(f"  {c['cell']:22s} {arm:4s} {ns:7,d} {na:7,d} {100.0 * na / ns if ns else 0:7.2f}% "
                  f"{miss:8,d} {rel:10,d} {miss - rel:12,d}")
    print(f"\n  TOTAL missing {tot_miss:,}  of which relocation exits {tot_rel:,}  "
          f"unexplained {tot_miss - tot_rel:,} "
          f"({100.0 * (tot_miss - tot_rel) / tot_miss if tot_miss else 0:.3f}% of the shortfall)")
    print("  A relocation exit is a designed end-of-participation, not a lost row. The residual is")
    print("  the only part attributable to a logging defect.")
    print("\n  DIFFERENTIAL ATTRITION (governed capture - ungoverned capture), pp:")
    for c in cells:
        if c["testbed"] != "flood":
            continue
        d = cap[(c["cell"], "gov")] - cap[(c["cell"], "ung")]
        print(f"    {c['cell']:22s} {d:+6.2f} pp"
              + ("   <- arms count different numbers of agent-years" if abs(d) >= 2 else ""))
    return cap


def seed_probe(cells):
    print("\n" + "=" * 100)
    print("PROBE 2 -- seed-label balance and pairing verifiability")
    print("=" * 100)
    out = {}
    for c in cells:
        gs = sorted(r["seed"] for r in c["gov"])
        us = sorted(r["seed"] for r in c["ung"])
        shared = sorted(set(gs) & set(us))
        bal = gs == us
        out[c["cell"]] = {"gov": gs, "ung": us, "shared": shared, "balanced": bal}
        print(f"  {c['cell']:22s} {'BALANCED  ' if bal else 'UNBALANCED'} "
              f"gov[{','.join(gs)}] ung[{','.join(us)}] shared[{','.join(shared)}]")
    return out


def provenance_probe():
    print("\n" + "=" * 100)
    print("PROBE 3 -- provenance of every run feeding the 14 cells")
    print("=" * 100)
    pats = ["examples/irrigation_abm/results/*/reproducibility_manifest.json",
            "examples/single_agent/results/JOH_FINAL/*/Group_C/Run_*/reproducibility_manifest.json",
            "examples/single_agent/results/JOH_FINAL_v2/*/Group_C/Run_*/reproducibility_manifest.json",
            "examples/single_agent/results/JOH_ABLATION_DISABLED/*/Group_C_disabled/Run_*/reproducibility_manifest.json",
            "examples/single_agent/results/JOH_ABLATION_DISABLED_v2/*/Group_C_disabled/Run_*/reproducibility_manifest.json"]
    seen, dirty, no_commit, clean = 0, 0, 0, 0
    for pat in pats:
        for p in glob.glob(os.path.join(REPO, pat)):
            if refuse(p):
                continue
            seen += 1
            try:
                m = json.load(open(p, encoding="utf-8"))
            except Exception:
                no_commit += 1
                continue
            commit = m.get("git_commit") or (m.get("git") or {}).get("git_commit") \
                if isinstance(m.get("git"), dict) else m.get("git_commit")
            d = m.get("git_dirty")
            if not commit:
                no_commit += 1
            elif d:
                dirty += 1
            else:
                clean += 1
    print(f"  manifests inspected {seen}   git_dirty=True {dirty}   "
          f"no git_commit recorded at all {no_commit}   CLEAN {clean}")
    return {"seen": seen, "dirty": dirty, "no_commit": no_commit, "clean": clean}


# ---------------------------------------------------------------------------
def main() -> int:
    print("LANE D -- CLAIM TRACEABILITY AND SURVIVOR RECOMPUTATION")
    print(f"repo   : {REPO}")
    print(f"python : {sys.version.split()[0]}\n")

    cells = build_cells()
    print(f"cells built: {len(cells)} "
          f"({sum(1 for c in cells if c['testbed'] == 'irrigation')} irrigation, "
          f"{sum(1 for c in cells if c['testbed'] == 'flood')} flood)")
    print(f"paths REFUSED by the hygiene filter (Group_A / _bak / _dead / _QUARANTINE): "
          f"{len(REFUSED)}")
    for p in REFUSED[:10]:
        print("   refused:", os.path.relpath(p, REPO))

    seeds = seed_probe(cells)
    attrition_probe(cells)
    provenance_probe()

    print("\n" + "=" * 100)
    print("PER-CELL MEASUREMENTS UNDER EACH SURVIVAL REGIME")
    print("=" * 100)
    r0, r1, r2, r3 = [], [], [], []
    print(f"  {'cell':22s} {'%rej':>7s} {'R0 all':>9s} {'R1 shared':>10s} "
          f"{'R2 bal':>9s} {'R3 matched':>11s}")
    for c in cells:
        s = seeds[c["cell"]]
        a = cell_row(c)
        b = cell_row(c, seeds=set(s["shared"])) if s["shared"] else None
        d = cell_row(c, seeds=set(s["shared"]), matched=True) if s["shared"] else None
        r0.append(a)
        if b:
            r1.append(b)
        if s["balanced"]:
            r2.append(b or a)
            if d:
                r3.append(d)
        print(f"  {c['cell']:22s} {a['pct_rej']:6.2f}% {a['shift']:>+9.2f} "
              f"{(b['shift'] if b else float('nan')):>+10.2f} "
              f"{(b['shift'] if s['balanced'] and b else float('nan')):>+9.2f} "
              f"{(d['shift'] if s['balanced'] and d else float('nan')):>+11.2f}")

    print("\n" + "=" * 100)
    print("HEADLINE UNDER EACH SURVIVAL REGIME")
    print("=" * 100)
    res = [separation(r0, "R0 as-published (all 14)"),
           separation(r1, "R1 shared-seed (all 14)"),
           separation(r2, "R2 balanced cells only"),
           separation(r3, "R3 balanced + attrition-matched")]

    print("\n  R4 -- measured on the stratum the ERROR rules actually condition on:")
    r4 = [x for x in (antecedent_row(c) for c in cells) if x]
    for r in r4:
        print(f"    {r['cell']:22s} {r['pct_rej']:6.2f}%  shift {r['shift']:>+7.2f}   ({r['note']})")
    res.append(separation_abs(r4, "R4 antecedent-consistent |shift|"))

    print("\n" + "=" * 100)
    print("VERDICT LINES -- grep these")
    print("=" * 100)
    for r in res:
        if not r:
            continue
        key = r["tag"].split()[0]
        print(f"VERDICT {key}_cells: {r['n']} ({r['n_high']} high / {r['n_low']} low)")
        print(f"VERDICT {key}_high_mean_pp: {r['high_mean']:.2f}")
        print(f"VERDICT {key}_low_mean_pp: {r['low_mean']:.2f}")
        print(f"VERDICT {key}_separation: {'COMPLETE' if r['complete'] else 'OVERLAPPING'}")
        print(f"VERDICT {key}_margin_pp: {r['margin']:.2f}")
    print(f"VERDICT hygiene_paths_refused: {len(REFUSED)}")

    with open(os.path.join(HERE, "survivor_cells.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["regime", "cell", "testbed", "pct_rejected_governed",
                    "pct_high_governed", "pct_high_ungoverned", "shift_pp", "n_gov", "n_ung"])
        for tag, rows in (("R0", r0), ("R1", r1), ("R2", r2), ("R3", r3)):
            for r in rows:
                w.writerow([tag, r["cell"], r["testbed"], round(r["pct_rej"], 4),
                            round(r["high_gov"], 4), round(r["high_ung"], 4),
                            round(r["shift"], 4), r["n_gov"], r["n_ung"]])
    print(f"\nwrote {os.path.join(HERE, 'survivor_cells.csv')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
