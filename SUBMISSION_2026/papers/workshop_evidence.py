"""FROZEN NUMBERS for the 4-page workshop paper. One command, zero GPU, stdlib + optional matplotlib.

WHAT THIS SCRIPT PROVES
-----------------------
The paper makes one measurement claim: the standard conformance statistic for a governed LLM agent
is a CONDITIONAL rate whose denominator is a variable the agent itself authors, so sustained
enforcement moves the denominator and the reported gain is part behaviour, part composition.

This script regenerates every quantitative claim behind that sentence, from files on disk:

  A. PER-CELL TABLE   for each (testbed x model) cell: enforcement pressure (share of governed
     decisions terminally REJECTED), the prevalence of the rule's antecedent appraisal in each arm,
     the shift between arms, the seed set actually present in each arm, and a BALANCED flag.
     Cross-checked against the prior-art script SUBMISSION_2026/evidence/appraisal_composition.py
     (both its committed CSV and a live re-run of its exact convention). Differences are printed,
     never absorbed.

  B. REGIME SUMMARY   high-pressure vs low-pressure group means and ranges, plus an explicit test of
     whether the separation is COMPLETE (every high cell strictly above every low cell).

  C. CONDITIONAL vs UNCONDITIONAL  for all five irrigation cells: the published conditional rate per
     arm, the unconditional rate per arm (denominator fixed by design at 78 agents x 42 years), both
     gaps, and the share of the conditional gap that survives de-conditioning. Includes the
     executed-action recomputation, which is an order of magnitude away from the proposed-action one.

  D. FIGURE 1         scatter of enforcement pressure against appraisal shift, one point per cell,
     marker by testbed; PNG at 300 dpi plus the underlying points as CSV so the figure is auditable.

  E. CLAIM LINES      one `CLAIM <name>: <value>` line per paper number, greppable from one run.

WHAT IT DOES NOT PROVE, and the paper must say so: the table shows that composition MOVES. It does
not show WHY. Premise revision and selection both produce it, and the first-attempt appraisal is
overwritten on every retry, so this corpus cannot separate them.

CONVENTIONS, inherited verbatim from the canonical scripts and not re-invented here
  * irrigation INCREASE actions   {increase_large, increase_small}      (_loader.INCREASE)
  * HIGH appraisal                {H, VH}, stripped and uppercased      (_loader.HIGH)
  * irrigation appraisal column   construct_WSA_LABEL (audit) / wsa_label (simulation_log)
  * flood appraisal column        construct_TP_LABEL
  * enforcement pressure          status startswith "REJECTED" (covers REJECTED and
                                  REJECTED_FALLBACK, both terminal) in the GOVERNED arm only.
                                  The ungoverned arm's REJECTED rows are skill-precondition
                                  failures, not enforcement; they are printed as a diagnostic and
                                  never used as pressure.
  * rows whose appraisal cell is empty are excluded from the rate denominators, which is
    appraisal_composition.py's convention. The count of such rows is reported per cell.
  * published irrigation rates are the MEAN OF PER-SEED rates (verified: that is what reproduces
    36.05 / 59.07), not the pooled rate. Both are printed.

Usage:  python SUBMISSION_2026/papers/workshop_evidence.py
        (from the repo root; --no-fig skips the PNG)

Read-only with respect to examples/ and paper/. Writes only beside itself.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT_DIR = HERE

# Reuse the canonical irrigation loader rather than re-typing its definitions.
sys.path.insert(0, os.path.join(REPO, "SUBMISSION_2026", "decomposition"))
import _loader as L  # noqa: E402

HIGH = L.HIGH                      # {"H", "VH"}
INCREASE = L.INCREASE              # {"increase_large", "increase_small"}
DEFAULT_SKILL = L.DEFAULT_SKILL    # "maintain_demand"; executes when a proposal is rejected

PRIOR_ART_CSV = os.path.join(REPO, "SUBMISSION_2026", "evidence", "appraisal_composition.csv")

# The abstract in papers/workshop_skeleton.md claims this corpus size. Checked in section A.
SKELETON_CORPUS_CLAIM = 432083

# Anchor values the brief pre-commits to. Checked in section C; a mismatch is the headline.
ANCHOR_EXPECT = {
    "cond_gov": 36.05, "cond_ung": 59.07,
    "uncond_gov": 40.90, "uncond_ung": 62.52,
}
ANCHOR_TOL = 0.01


# ---------------------------------------------------------------------------
# Cell inventory
# ---------------------------------------------------------------------------
IRRIGATION_MODELS = [
    ("gemma3:4b", ""),
    ("gemma3:12b", "gemma3_12b_"),
    ("gemma4:e2b", "gemma4_e2b_"),
    ("gemma4:e4b", "gemma4_e4b_"),
    ("ministral3:8b", "ministral3_8b_"),
]

# (governed base dir, ungoverned base dir). Group_C vs Group_C_disabled is the clean ablation
# pair; Group_A is a DIFFERENT experiment (no structured prompts) and is excluded by name here.
FLOOD_BASES = [("JOH_FINAL", "JOH_ABLATION_DISABLED"),
               ("JOH_FINAL_v2", "JOH_ABLATION_DISABLED_v2")]
FLOOD_GOV_SUB = "Group_C"
FLOOD_UNG_SUB = "Group_C_disabled"


def _pretty_model(dirname: str) -> str:
    """gemma3_4b -> gemma3:4b ; gemma4_e2b -> gemma4:e2b ; ministral3_14b -> ministral3:14b"""
    parts = dirname.split("_")
    return parts[0] + ":" + "_".join(parts[1:]) if len(parts) > 1 else dirname


def irrigation_runs(arm_prefix: str, seg: str):
    """[(seed, audit_csv_path)] for one irrigation arm+model. Seed parsed from the dir name."""
    out = []
    pat = os.path.join(REPO, "examples", "irrigation_abm", "results",
                       f"{arm_prefix}_v21_42yr_{seg}seed*")
    for d in sorted(glob.glob(pat)):
        if not os.path.isdir(d):
            continue
        csv_path = os.path.join(d, "irrigation_farmer_governance_audit.csv")
        if not os.path.isfile(csv_path):
            continue
        m = re.search(r"seed(\d+)$", os.path.basename(d))
        out.append(((m.group(1) if m else "NA"), csv_path))
    return out


def flood_runs(base: str, model: str, sub: str):
    """[(seed, audit_csv_path)] for one flood arm+model. Seed read from reproducibility_manifest."""
    out = []
    root = os.path.join(REPO, "examples", "single_agent", "results", base, model, sub)
    for d in sorted(glob.glob(os.path.join(root, "Run_*"))):
        if not os.path.isdir(d):
            continue
        hits = sorted(glob.glob(os.path.join(d, "*governance_audit.csv")))
        if not hits:
            continue
        seed = "NA"
        man = os.path.join(d, "reproducibility_manifest.json")
        if os.path.isfile(man):
            try:
                seed = str(json.load(open(man, encoding="utf-8")).get("seed", "NA"))
            except Exception:
                seed = "UNREADABLE"
        out.append((seed, hits[0]))
    return out


def build_cells():
    """Every (testbed x model) cell with its two arms' run lists. Nothing is skipped silently."""
    cells = []
    for label, seg in IRRIGATION_MODELS:
        cells.append({
            "cell": f"irrigation {label}", "testbed": "irrigation", "model": label,
            "appraisal_col": "construct_WSA_LABEL",
            "gov": irrigation_runs("production", seg),
            "ung": irrigation_runs("ungoverned", seg),
        })
    for gb, ub in FLOOD_BASES:
        root = os.path.join(REPO, "examples", "single_agent", "results", gb)
        if not os.path.isdir(root):
            print(f"  !! missing flood base dir {root}")
            continue
        for m in sorted(os.listdir(root)):
            if not os.path.isdir(os.path.join(root, m)) or m.startswith("_"):
                continue
            g = flood_runs(gb, m, FLOOD_GOV_SUB)
            u = flood_runs(ub, m, FLOOD_UNG_SUB)
            if not g and not u:
                print(f"  !! flood {m}: no {FLOOD_GOV_SUB} or {FLOOD_UNG_SUB} runs; cell dropped")
                continue
            cells.append({
                "cell": f"flood {_pretty_model(m)}", "testbed": "flood", "model": _pretty_model(m),
                "appraisal_col": "construct_TP_LABEL", "dirname": m, "gov": g, "ung": u,
            })
    return cells


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------
def scan(paths, col):
    """Pooled counts over `paths`.

    Returns dict with:
      n_raw       every data row in the files
      n           rows whose appraisal cell is non-empty (the rate denominator)
      n_blank     n_raw - n, reported rather than hidden
      pct_high    100 * (appraisal in {H,VH}) / n
      pct_rej     100 * (status startswith REJECTED) / n
      rej_term / rej_fallback   the two terminal statuses, split out
    """
    n_raw = n = high = rej = rej_plain = rej_fb = 0
    for p in paths:
        with open(p, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                n_raw += 1
                value = (row.get(col) or "").strip().upper()
                if not value:
                    continue
                n += 1
                if value in HIGH:
                    high += 1
                status = (row.get("status") or "").strip()
                if status.startswith("REJECTED"):
                    rej += 1
                    if status == "REJECTED_FALLBACK":
                        rej_fb += 1
                    else:
                        rej_plain += 1
    if not n:
        return None
    return {"n_raw": n_raw, "n": n, "n_blank": n_raw - n,
            "pct_high": 100.0 * high / n, "pct_rej": 100.0 * rej / n,
            "rej_term": rej_plain, "rej_fallback": rej_fb}


def prior_art_scan(pattern, col):
    """appraisal_composition.py's EXACT convention: recursive glob over the whole base dir
    (which sweeps in Group_A backups), skip-empty rows, pooled. Reimplemented here only so the
    two scripts' numbers can be differenced rather than argued about."""
    n = high = rej = 0
    for path in glob.glob(os.path.join(REPO, pattern), recursive=True):
        with open(path, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                value = (row.get(col) or "").strip().upper()
                if not value:
                    continue
                n += 1
                if value in HIGH:
                    high += 1
                if (row.get("status") or "").strip().startswith("REJECTED"):
                    rej += 1
    if not n:
        return None
    return {"pct_high": 100.0 * high / n, "pct_rej": 100.0 * rej / n, "n": n}


def prior_art_patterns(cell):
    """The glob pair appraisal_composition.py uses for this cell, or None for irrigation
    (where the two scripts already agree by construction)."""
    if cell["testbed"] != "flood":
        return None
    for gb, ub in FLOOD_BASES:
        root = os.path.join(REPO, "examples", "single_agent", "results", gb, cell["dirname"])
        if os.path.isdir(root):
            return (f"examples/single_agent/results/{gb}/{cell['dirname']}/**/*governance_audit.csv",
                    f"examples/single_agent/results/{ub}/{cell['dirname']}/**/*governance_audit.csv")
    return None


def fmt_seeds(runs):
    return ",".join(s for s, _ in runs) if runs else "(none)"


# ---------------------------------------------------------------------------
# Section A -- per-cell table
# ---------------------------------------------------------------------------
def section_a(cells, claims):
    print("=" * 100)
    print("A. PER-CELL TABLE -- enforcement pressure and appraisal composition")
    print("=" * 100)
    print("enforcement pressure = % of GOVERNED decisions with a terminal REJECTED status.")
    print("shift = (ungoverned - governed) prevalence of the appraisal the rule conditions on.\n")

    rows = []
    for c in cells:
        g = scan([p for _, p in c["gov"]], c["appraisal_col"])
        u = scan([p for _, p in c["ung"]], c["appraisal_col"])
        if not g or not u:
            print(f"  !! {c['cell']}: no usable rows in "
                  f"{'governed' if not g else 'ungoverned'} arm -- REPORTED, NOT SKIPPED")
            continue
        gs, us = sorted(s for s, _ in c["gov"]), sorted(s for s, _ in c["ung"])
        rows.append({
            "cell": c["cell"], "testbed": c["testbed"], "model": c["model"],
            "appraisal_col": c["appraisal_col"],
            "pct_rejected_governed": g["pct_rej"], "pct_rejected_ungoverned": u["pct_rej"],
            "pct_high_governed": g["pct_high"], "pct_high_ungoverned": u["pct_high"],
            "shift_pp": u["pct_high"] - g["pct_high"],
            "n_governed": g["n"], "n_ungoverned": u["n"],
            "n_raw_governed": g["n_raw"], "n_raw_ungoverned": u["n_raw"],
            "blank_appraisal_governed": g["n_blank"], "blank_appraisal_ungoverned": u["n_blank"],
            "runs_governed": len(c["gov"]), "runs_ungoverned": len(c["ung"]),
            "seeds_governed": fmt_seeds(c["gov"]), "seeds_ungoverned": fmt_seeds(c["ung"]),
            "balanced": "BALANCED" if gs == us else "UNBALANCED",
            "_cellobj": c,
        })

    rows.sort(key=lambda r: -r["pct_rejected_governed"])

    hdr = (f"{'cell':24s} {'%rej gov':>9s} {'%rej ung':>9s} {'high|gov':>9s} {'high|ung':>9s} "
           f"{'shift pp':>9s} {'n gov':>7s} {'n ung':>7s}  {'balance':<11s} seeds gov | seeds ung")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r['cell']:24s} {r['pct_rejected_governed']:>8.2f}% {r['pct_rejected_ungoverned']:>8.2f}% "
              f"{r['pct_high_governed']:>8.2f}% {r['pct_high_ungoverned']:>8.2f}% "
              f"{r['shift_pp']:>+9.2f} {r['n_governed']:>7,d} {r['n_ungoverned']:>7,d}  "
              f"{r['balanced']:<11s} {r['seeds_governed']} | {r['seeds_ungoverned']}")

    n_irr = sum(1 for r in rows if r["testbed"] == "irrigation")
    n_fld = sum(1 for r in rows if r["testbed"] == "flood")
    print(f"\n  cells emitted: {len(rows)}  ({n_irr} irrigation, {n_fld} flood)")
    if (len(rows), n_irr, n_fld) != (14, 5, 9):
        print(f"  !! DISAGREEMENT with the skeleton, which lists 14 cells (5 irrigation, 9 flood)")
    else:
        print("  matches the skeleton's stated 14 cells (5 irrigation, 9 flood)")

    unbal = [r["cell"] for r in rows if r["balanced"] == "UNBALANCED"]
    print(f"  UNBALANCED cells ({len(unbal)}): {', '.join(unbal) if unbal else 'none'}")

    blanks_g = sum(r["blank_appraisal_governed"] for r in rows)
    blanks_u = sum(r["blank_appraisal_ungoverned"] for r in rows)
    n_total = sum(r["n_governed"] + r["n_ungoverned"] for r in rows)
    n_raw_total = sum(r["n_raw_governed"] + r["n_raw_ungoverned"] for r in rows)
    print(f"  rows with a blank appraisal cell, excluded from every rate: "
          f"{blanks_g:,} governed + {blanks_u:,} ungoverned")
    print(f"  CORPUS: {n_raw_total:,} logged decision rows in the 14 cells "
          f"({n_total:,} with a parsed appraisal)")
    if n_raw_total != SKELETON_CORPUS_CLAIM:
        print(f"  !! DISAGREEMENT: the skeleton abstract claims {SKELETON_CORPUS_CLAIM:,} logged "
              f"decisions; this run counts {n_raw_total:,}. See NUMBERS.md for the candidate "
              f"counts that were tried and none of which reproduce it.")

    claims["n_cells"] = len(rows)
    claims["n_cells_irrigation"] = n_irr
    claims["n_cells_flood"] = n_fld
    claims["corpus_decision_rows"] = n_raw_total
    claims["corpus_rows_with_appraisal"] = n_total
    claims["n_unbalanced_cells"] = len(unbal)

    # --- cross-check 1: the committed appraisal_composition.csv ------------------------------
    print("\n  CROSS-CHECK 1 vs the committed SUBMISSION_2026/evidence/appraisal_composition.csv")
    if not os.path.isfile(PRIOR_ART_CSV):
        print(f"    !! not found at {PRIOR_ART_CSV} -- cannot cross-check")
    else:
        prior = {}
        with open(PRIOR_ART_CSV, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                key = r["cell"].replace("_", ":", 1) if r["cell"].startswith("flood ") else r["cell"]
                # committed CSV writes flood models as gemma3_4b; normalise to gemma3:4b
                if r["cell"].startswith("flood "):
                    key = "flood " + _pretty_model(r["cell"].split(" ", 1)[1])
                prior[key] = r
        diffs = 0
        for r in rows:
            p = prior.get(r["cell"])
            if p is None:
                print(f"    {r['cell']:24s}  NOT IN the committed CSV")
                diffs += 1
                continue
            d_rej = r["pct_rejected_governed"] - float(p["pct_rejected_governed"])
            d_shift = r["shift_pp"] - float(p["shift_pp"])
            if abs(d_rej) > 0.005 or abs(d_shift) > 0.005:
                print(f"    {r['cell']:24s}  %rej {float(p['pct_rejected_governed']):7.4f} -> "
                      f"{r['pct_rejected_governed']:7.4f} ({d_rej:+.4f})   "
                      f"shift {float(p['shift_pp']):+8.4f} -> {r['shift_pp']:+8.4f} ({d_shift:+.4f})")
                diffs += 1
        extra = [k for k in prior if k not in {r["cell"] for r in rows}]
        for k in extra:
            print(f"    {k:24s}  IN the committed CSV but not emitted here")
        print(f"    cells differing from the committed CSV: {diffs} of {len(rows)}"
              + ("" if diffs else "  (exact agreement)"))
        claims["cells_differing_from_prior_art_csv"] = diffs

    # --- cross-check 2: prior-art glob convention, live -------------------------------------
    print("\n  CROSS-CHECK 2 vs a LIVE re-run of appraisal_composition.py's glob convention")
    print("    (its flood globs are `<base>/<model>/**/*governance_audit.csv`, which also match")
    print("     Group_A directories; this script restricts the flood arms to Group_C /")
    print("     Group_C_disabled, the clean ablation pair.)")
    live_diffs = 0
    for r in rows:
        pats = prior_art_patterns(r["_cellobj"])
        if not pats:
            continue
        pg = prior_art_scan(pats[0], r["appraisal_col"])
        pu = prior_art_scan(pats[1], r["appraisal_col"])
        if not pg or not pu:
            continue
        d_n = (pg["n"] - r["n_governed"], pu["n"] - r["n_ungoverned"])
        d_shift = (pu["pct_high"] - pg["pct_high"]) - r["shift_pp"]
        if d_n != (0, 0) or abs(d_shift) > 0.005:
            live_diffs += 1
            print(f"    {r['cell']:24s} prior-art pools {d_n[0]:+d} governed / {d_n[1]:+d} "
                  f"ungoverned extra rows; shift {d_shift:+.4f} pp, "
                  f"%rej {pg['pct_rej'] - r['pct_rejected_governed']:+.4f} pp")
    print(f"    flood cells where the two conventions differ: {live_diffs}"
          + ("  (none -- conventions agree)" if not live_diffs else ""))
    claims["flood_cells_contaminated_by_prior_art_glob"] = live_diffs

    # --- paired-seed recomputation ----------------------------------------------------------
    print("\n  PAIRED-SEED RECOMPUTATION (runs restricted to seeds present in BOTH arms)")
    print(f"    {'cell':24s} {'paired seeds':<22s} {'shift all':>10s} {'shift paired':>13s} {'delta':>8s}")
    for r in rows:
        c = r["_cellobj"]
        common = sorted(set(s for s, _ in c["gov"]) & set(s for s, _ in c["ung"]))
        if not common:
            print(f"    {r['cell']:24s} {'(no shared seed)':<22s} {r['shift_pp']:>+10.2f} "
                  f"{'n/a':>13s} {'n/a':>8s}")
            r["shift_pp_paired"] = float("nan")
            r["paired_seeds"] = ""
            continue
        g = scan([p for s, p in c["gov"] if s in common], c["appraisal_col"])
        u = scan([p for s, p in c["ung"] if s in common], c["appraisal_col"])
        sp = u["pct_high"] - g["pct_high"]
        r["shift_pp_paired"] = sp
        r["paired_seeds"] = ",".join(common)
        r["pct_rejected_governed_paired"] = g["pct_rej"]
        flag = "" if abs(sp - r["shift_pp"]) < 0.005 else "  <- moves"
        print(f"    {r['cell']:24s} {','.join(common):<22s} {r['shift_pp']:>+10.2f} "
              f"{sp:>+13.2f} {sp - r['shift_pp']:>+8.2f}{flag}")
    for r in rows:
        r.setdefault("shift_pp_paired", float("nan"))
        r.setdefault("paired_seeds", "")
        r.setdefault("pct_rejected_governed_paired", float("nan"))

    # write the table
    out_csv = os.path.join(OUT_DIR, "per_cell_table.csv")
    fields = [k for k in rows[0] if not k.startswith("_")]
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v)
                        for k, v in r.items() if k in fields})
    print(f"\n  wrote {out_csv}")
    return rows


# ---------------------------------------------------------------------------
# Section B -- regime summary
# ---------------------------------------------------------------------------
def section_b(rows, claims, threshold=5.0):
    print("\n" + "=" * 100)
    print(f"B. REGIME SUMMARY -- split at {threshold:.0f}% of governed decisions rejected")
    print("=" * 100)
    hi = [r for r in rows if r["pct_rejected_governed"] > threshold]
    lo = [r for r in rows if r["pct_rejected_governed"] <= threshold]
    for name, grp in (("HIGH", hi), ("LOW", lo)):
        if not grp:
            print(f"  {name}: empty")
            continue
        sh = [r["shift_pp"] for r in grp]
        pr = [r["pct_rejected_governed"] for r in grp]
        pos = sum(1 for x in sh if x > 0)
        print(f"  {name:4s} pressure  n={len(grp):2d}  "
              f"pressure {min(pr):.2f}% .. {max(pr):.2f}%   "
              f"shift mean {L.mean(sh):+.2f} pp   range {min(sh):+.2f} .. {max(sh):+.2f}   "
              f"positive {pos}/{len(grp)}")
        print(f"       testbeds: {sorted(set(r['testbed'] for r in grp))}")
        claims[f"{name.lower()}_n_cells"] = len(grp)
        claims[f"{name.lower()}_pressure_min_pct"] = round(min(pr), 2)
        claims[f"{name.lower()}_pressure_max_pct"] = round(max(pr), 2)
        claims[f"{name.lower()}_shift_mean_pp"] = round(L.mean(sh), 2)
        claims[f"{name.lower()}_shift_min_pp"] = round(min(sh), 2)
        claims[f"{name.lower()}_shift_max_pp"] = round(max(sh), 2)
        claims[f"{name.lower()}_shift_positive_count"] = f"{pos}/{len(grp)}"

    if hi and lo:
        shi = [r["shift_pp"] for r in hi]
        slo = [r["shift_pp"] for r in lo]
        complete = min(shi) > max(slo)
        print(f"\n  SEPARATION on appraisal shift: "
              f"{'COMPLETE' if complete else 'OVERLAPPING'} "
              f"(min high {min(shi):+.2f} vs max low {max(slo):+.2f}, "
              f"margin {min(shi) - max(slo):+.2f} pp)")
        pcomplete = min(r["pct_rejected_governed"] for r in hi) > \
            max(r["pct_rejected_governed"] for r in lo)
        print(f"  SEPARATION on enforcement pressure: "
              f"{'COMPLETE' if pcomplete else 'OVERLAPPING'} "
              f"(min high {min(r['pct_rejected_governed'] for r in hi):.2f}% vs "
              f"max low {max(r['pct_rejected_governed'] for r in lo):.2f}%)")
        # is the split identical to the testbed split?
        by_testbed = (all(r["testbed"] == "irrigation" for r in hi)
                      and all(r["testbed"] == "flood" for r in lo))
        print(f"  the pressure split is {'IDENTICAL to' if by_testbed else 'NOT identical to'} "
              f"the testbed split -- so 'regime' and 'testbed' are "
              f"{'confounded here and the paper must say so' if by_testbed else 'separable'}.")
        # monotonicity within the high group, which the skeleton forbids claiming
        order = sorted(hi, key=lambda r: r["pct_rejected_governed"])
        mono = all(order[i]["shift_pp"] <= order[i + 1]["shift_pp"] for i in range(len(order) - 1))
        print(f"  within the HIGH group the shift is {'MONOTONE' if mono else 'NON-MONOTONE'} "
              f"in pressure -- report a REGIME SEPARATION, not a dose-response.")
        claims["separation_shift"] = "COMPLETE" if complete else "OVERLAPPING"
        claims["separation_margin_pp"] = round(min(shi) - max(slo), 2)
        claims["separation_pressure"] = "COMPLETE" if pcomplete else "OVERLAPPING"
        claims["high_group_monotone"] = "yes" if mono else "no"

    # robustness of the threshold
    gap_lo = max(r["pct_rejected_governed"] for r in lo) if lo else float("nan")
    gap_hi = min(r["pct_rejected_governed"] for r in hi) if hi else float("nan")
    print(f"\n  the {threshold:.0f}% threshold is not load-bearing: the observed pressure gap runs "
          f"{gap_lo:.2f}% .. {gap_hi:.2f}% with no cell inside it.")
    return hi, lo


# ---------------------------------------------------------------------------
# Section C -- conditional vs unconditional, irrigation
# ---------------------------------------------------------------------------
def _executed(row):
    status = (row.get("status") or "").strip()
    if status.startswith("REJECTED"):
        return DEFAULT_SKILL
    return (row.get("final_skill") or "").strip()


def _executed_rates(path):
    """(conditional, unconditional) executed-action increase rates for one irrigation run."""
    num = den = inc = n = 0
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            n += 1
            ex = _executed(row)
            if ex in INCREASE:
                inc += 1
            if (row.get("construct_WSA_LABEL") or "").strip().upper() in HIGH:
                den += 1
                if ex in INCREASE:
                    num += 1
    return (100.0 * num / den if den else float("nan"),
            100.0 * inc / n if n else float("nan"))


def section_c(claims):
    print("\n" + "=" * 100)
    print("C. IRRIGATION -- conditional vs unconditional, all five cells")
    print("=" * 100)
    print("conditional   = executed increases / decisions whose SELF-REPORTED scarcity is H or VH")
    print("                (the published statistic; its denominator is post-treatment)")
    print("unconditional = increases / every decision (denominator fixed at 78 agents x 42 years)")
    print("action variable = simulation_log.yearly_decision, the last PROPOSED action.")
    print("Rates are the MEAN OF PER-SEED rates, on seeds present in BOTH arms.\n")

    hdr = (f"{'cell':16s} {'seeds':<14s} {'cond gov':>9s} {'cond ung':>9s} {'cond gap':>9s} "
           f"{'unc gov':>9s} {'unc ung':>9s} {'unc gap':>9s} {'survives':>9s}")
    print(hdr)
    print("-" * len(hdr))
    out = []
    for label, seg in IRRIGATION_MODELS:
        ps = L.paired_seeds(seg)
        all_g, all_u = L.seeds("governed", seg), L.seeds("ungoverned", seg)
        rec = {"cell": f"irrigation {label}", "paired_seeds": ",".join(ps),
               "balanced": "BALANCED" if all_g == all_u else "UNBALANCED"}
        for arm, key in (("governed", "gov"), ("ungoverned", "ung")):
            cond, unc = [], []
            for s in ps:
                rows = L.load_run(L.run_dir(arm, seg, s))
                cond.append(L.ibr(rows))
                unc.append(L.increase_rate(rows))
            rec[f"cond_{key}"] = L.mean(cond)
            rec[f"uncond_{key}"] = L.mean(unc)
        rec["cond_gap"] = rec["cond_gov"] - rec["cond_ung"]
        rec["uncond_gap"] = rec["uncond_gov"] - rec["uncond_ung"]
        rec["survival_ratio"] = (abs(rec["uncond_gap"]) / abs(rec["cond_gap"]) * 100.0
                                 if rec["cond_gap"] else float("nan"))
        rec["sign_flip"] = "YES" if rec["cond_gap"] * rec["uncond_gap"] < 0 else "no"
        out.append(rec)
        flag = "  <- SIGN FLIP" if rec["sign_flip"] == "YES" else ""
        print(f"{label:16s} {','.join(ps):<14s} {rec['cond_gov']:>8.2f}% {rec['cond_ung']:>8.2f}% "
              f"{rec['cond_gap']:>+9.2f} {rec['uncond_gov']:>8.2f}% {rec['uncond_ung']:>8.2f}% "
              f"{rec['uncond_gap']:>+9.2f} {rec['survival_ratio']:>8.1f}%{flag}")

    print("\n  'survives' = |unconditional gap| / |conditional gap|. Sign convention throughout:")
    print("  gap = governed - ungoverned, so NEGATIVE means governance lowered the rate.")

    # --- anchor gate ------------------------------------------------------------------------
    anchor = out[0]
    print(f"\n  ANCHOR GATE -- irrigation gemma3:4b must reproduce "
          f"conditional {ANCHOR_EXPECT['cond_gov']}/{ANCHOR_EXPECT['cond_ung']} and "
          f"unconditional {ANCHOR_EXPECT['uncond_gov']}/{ANCHOR_EXPECT['uncond_ung']}")
    checks = [("conditional governed", anchor["cond_gov"], ANCHOR_EXPECT["cond_gov"]),
              ("conditional ungoverned", anchor["cond_ung"], ANCHOR_EXPECT["cond_ung"]),
              ("unconditional governed", anchor["uncond_gov"], ANCHOR_EXPECT["uncond_gov"]),
              ("unconditional ungoverned", anchor["uncond_ung"], ANCHOR_EXPECT["uncond_ung"])]
    bad = []
    for name, got, want in checks:
        ok = abs(round(got, 2) - want) <= ANCHOR_TOL
        print(f"    {name:26s} got {got:8.4f}  expected {want:6.2f}  {'OK' if ok else 'MISMATCH'}")
        if not ok:
            bad.append(name)
    if bad:
        print("\n  !! HEADLINE: the anchor cell does NOT reproduce. Stop and read this before")
        print(f"     using any other number in this run. Failing: {', '.join(bad)}")
    else:
        print("    anchor reproduces exactly at 2 dp.")
    claims["anchor_gate"] = "PASS" if not bad else "FAIL: " + ", ".join(bad)

    # --- executed-action recomputation -------------------------------------------------------
    print("\n  EXECUTED-ACTION recomputation of the same statistic (a rejected proposal never")
    print("  moved the water request; the registry default 'maintain_demand' executed instead):")
    print(f"    {'cell':16s} {'exec cond gov':>13s} {'exec cond ung':>13s} {'exec unc gov':>13s} "
          f"{'exec unc ung':>13s}")
    for label, seg in IRRIGATION_MODELS:
        ps = L.paired_seeds(seg)
        vals = {}
        for arm_prefix, key in (("production", "gov"), ("ungoverned", "ung")):
            paths = [os.path.join(REPO, "examples", "irrigation_abm", "results",
                                  f"{arm_prefix}_v21_42yr_{seg}seed{s}",
                                  "irrigation_farmer_governance_audit.csv") for s in ps]
            r = [_executed_rates(p) for p in paths]
            vals[key] = (L.mean(x[0] for x in r), L.mean(x[1] for x in r))
        print(f"    {label:16s} {vals['gov'][0]:>12.2f}% {vals['ung'][0]:>12.2f}% "
              f"{vals['gov'][1]:>12.2f}% {vals['ung'][1]:>12.2f}%")
        if seg == "":
            claims["anchor_executed_conditional_governed_pct"] = round(vals["gov"][0], 2)
            claims["anchor_executed_conditional_ungoverned_pct"] = round(vals["ung"][0], 2)
    print("    Two defensible definitions of 'the action', an order of magnitude apart on the")
    print("    governed arm. The paper must say which it means.")

    # --- retry-stratified appraisal ----------------------------------------------------------
    print("\n  RETRY-STRATIFIED appraisal prevalence, anchor governed arm "
          "(consistent with BOTH mechanisms, decisive for neither):")
    strata = {}
    for s in L.paired_seeds(""):
        p = os.path.join(REPO, "examples", "irrigation_abm", "results",
                         f"production_v21_42yr_seed{s}", "irrigation_farmer_governance_audit.csv")
        with open(p, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                try:
                    k = int(float(row.get("retry_count") or 0))
                except (TypeError, ValueError):
                    k = -1
                v = (row.get("construct_WSA_LABEL") or "").strip().upper()
                d = strata.setdefault(k, [0, 0, 0])
                d[0] += 1                      # all rows
                if v:
                    d[1] += 1                  # parsed rows
                    if v in HIGH:
                        d[2] += 1
    print(f"    {'retries':>8s} {'rows':>8s} {'% high (parsed den.)':>21s} {'% high (all rows)':>19s}")
    retry_claim = []
    for k in sorted(strata):
        n_all, n_par, hi = strata[k]
        pp = 100.0 * hi / n_par if n_par else float("nan")
        pa = 100.0 * hi / n_all if n_all else float("nan")
        print(f"    {k:>8d} {n_all:>8,d} {pp:>20.2f}% {pa:>18.2f}%")
        retry_claim.append(f"{k}:{pp:.1f}")
    print("    The parsed-row denominator is the prior-art convention and is the one the")
    print("    skeleton quotes; the all-rows column differs only at 3 retries, where the")
    print("    unparseable rows live.")
    claims["retry_stratified_high_pct_parsed"] = " ".join(retry_claim)

    return out


# ---------------------------------------------------------------------------
# Section D -- Figure 1
# ---------------------------------------------------------------------------
FIG_CODE = '''
# --- Figure 1 drawing code (emitted so the figure is reproducible without matplotlib) ---
import csv, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
pts = list(csv.DictReader(open("fig1_data.csv", encoding="utf-8")))
fig, ax = plt.subplots(figsize=(5.2, 3.6), dpi=300)
style = {"irrigation": ("o", "#1f4e79"), "flood": ("^", "#c0504d")}
for testbed, (marker, colour) in style.items():
    xs = [float(p["pct_rejected"]) for p in pts if p["testbed"] == testbed]
    ys = [float(p["shift_pp"]) for p in pts if p["testbed"] == testbed]
    ax.scatter(xs, ys, marker=marker, s=46, c=colour, edgecolors="black",
               linewidths=0.5, label=testbed, zorder=3)
ax.axhline(0, color="grey", lw=0.7, zorder=1)
ax.set_xscale("symlog", linthresh=1.0)
ax.set_xlim(-0.04, 90)          # symlog would otherwise draw a meaningless negative decade
ax.set_xlabel("enforcement pressure (% of governed decisions rejected)")
ax.set_ylabel("appraisal shift, ungoverned - governed (pp)")
ax.legend(frameon=False, loc="upper left")
fig.tight_layout()
fig.savefig("fig1_regime_separation.png", dpi=300)
'''


def section_d(rows, claims, want_fig=True):
    print("\n" + "=" * 100)
    print("D. FIGURE 1 -- regime separation")
    print("=" * 100)
    data_csv = os.path.join(OUT_DIR, "fig1_data.csv")
    png = os.path.join(OUT_DIR, "fig1_regime_separation.png")
    fields = ["cell", "testbed", "model", "pct_rejected", "shift_pp", "shift_pp_paired",
              "n_governed", "n_ungoverned", "balanced"]
    with open(data_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({
                "cell": r["cell"], "testbed": r["testbed"], "model": r["model"],
                "pct_rejected": round(r["pct_rejected_governed"], 4),
                "shift_pp": round(r["shift_pp"], 4),
                "shift_pp_paired": ("" if r["shift_pp_paired"] != r["shift_pp_paired"]
                                    else round(r["shift_pp_paired"], 4)),
                "n_governed": r["n_governed"], "n_ungoverned": r["n_ungoverned"],
                "balanced": r["balanced"],
            })
    print(f"  wrote {data_csv}  ({len(rows)} points)")

    if not want_fig:
        print("  PNG skipped (--no-fig).")
        claims["figure1_png"] = "skipped"
        return

    try:
        import matplotlib  # noqa: F401
    except ImportError:
        print("  !! matplotlib is NOT installed. fig1_data.csv was still written.")
        print("  !! THE PNG WAS NOT PRODUCED. Run this, from this directory, once matplotlib exists:")
        print(FIG_CODE)
        claims["figure1_png"] = "NOT PRODUCED (matplotlib missing)"
        return

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(5.2, 3.6), dpi=300)
    style = {"irrigation": ("o", "#1f4e79"), "flood": ("^", "#c0504d")}
    for testbed, (marker, colour) in style.items():
        pts = [r for r in rows if r["testbed"] == testbed]
        ax.scatter([r["pct_rejected_governed"] for r in pts],
                   [r["shift_pp"] for r in pts],
                   marker=marker, s=46, c=colour, edgecolors="black", linewidths=0.5,
                   label=f"{testbed} (n={len(pts)})", zorder=3)
    ax.axhline(0, color="grey", lw=0.7, zorder=1)
    ax.set_xscale("symlog", linthresh=1.0)
    ax.set_xlim(-0.04, 200)     # symlog would otherwise draw a meaningless negative decade;
                                # the right margin is head-room for the point labels
    # Label only the points that are visually separable. The remaining low-pressure cells sit on
    # top of one another at x ~ 0 and are identified in fig1_data.csv, not by an unreadable label.
    unlabelled = 0
    for r in rows:
        if r["pct_rejected_governed"] >= 0.1:
            ax.annotate(r["model"], (r["pct_rejected_governed"], r["shift_pp"]),
                        textcoords="offset points", xytext=(6, -2), fontsize=5.5,
                        color="#333333", zorder=4)
        else:
            unlabelled += 1
    ax.set_xlabel("enforcement pressure (% of governed decisions rejected)")
    ax.set_ylabel("appraisal shift, ungoverned $-$ governed (pp)")
    ax.set_title("Enforcement pressure and the composition of the metric's denominator",
                 fontsize=8.5)
    ax.legend(frameon=False, loc="upper left", fontsize=8)
    ax.grid(alpha=0.25, lw=0.5)
    fig.tight_layout()
    fig.savefig(png, dpi=300)
    plt.close(fig)
    print(f"  wrote {png} at 300 dpi  (matplotlib {matplotlib.__version__})")
    print("  x axis is symlog with a linear threshold at 1% so the nine sub-1% flood cells")
    print("  remain visible; state that in the caption.")
    print(f"  {unlabelled} points below 0.1% pressure are drawn but not labelled (they overlap); "
          f"they are named in fig1_data.csv.")
    claims["figure1_png"] = os.path.basename(png)


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fig", action="store_true", help="skip the PNG, still write fig1_data.csv")
    args = ap.parse_args()

    print("WORKSHOP PAPER -- FROZEN NUMBERS")
    print(f"repo    : {REPO}")
    print(f"outputs : {OUT_DIR}")
    print(f"python  : {sys.version.split()[0]}\n")

    claims = {}
    cells = build_cells()
    rows = section_a(cells, claims)
    section_b(rows, claims)
    irr = section_c(claims)
    section_d(rows, claims, want_fig=not args.no_fig)

    # per-cell claim lines the paper quotes directly
    for r in rows:
        key = r["cell"].replace(" ", "_").replace(":", "")
        claims[f"cell_{key}_pct_rejected"] = round(r["pct_rejected_governed"], 2)
        claims[f"cell_{key}_shift_pp"] = round(r["shift_pp"], 2)
    for r in irr:
        key = r["cell"].replace(" ", "_").replace(":", "")
        claims[f"{key}_conditional_governed_pct"] = round(r["cond_gov"], 2)
        claims[f"{key}_conditional_ungoverned_pct"] = round(r["cond_ung"], 2)
        claims[f"{key}_conditional_gap_pp"] = round(r["cond_gap"], 2)
        claims[f"{key}_unconditional_governed_pct"] = round(r["uncond_gov"], 2)
        claims[f"{key}_unconditional_ungoverned_pct"] = round(r["uncond_ung"], 2)
        claims[f"{key}_unconditional_gap_pp"] = round(r["uncond_gap"], 2)
        claims[f"{key}_gap_survival_pct"] = round(r["survival_ratio"], 1)

    print("\n" + "=" * 100)
    print("E. CLAIM LINES -- grep these")
    print("=" * 100)
    for k in claims:
        print(f"CLAIM {k}: {claims[k]}")
    print(f"\nCLAIM claim_count: {len(claims)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
