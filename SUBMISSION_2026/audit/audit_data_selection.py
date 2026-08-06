"""Repeatable DATA-SELECTION audit for the WAGF corpus (READ-ONLY).

Purpose: for every data-selection expression used by a paper-feeding script, resolve
what it matches TODAY and flag contamination:
  * Group_A            -- a DIFFERENT experiment (no structured prompts), never a clean arm
  * *_bak* / _dead_*   -- backup or abandoned run directories
  * _QUARANTINE_*      -- runs withdrawn for a known data defect
  * v1 tree where v2 supersedes it
  * ASYMMETRY          -- governed arm and ungoverned arm drawn on different rules,
                          different seed sets, or different run counts

Writes NOTHING outside its own directory. Run from the repo root:

    python SUBMISSION_2026/audit/audit_data_selection.py [--csv out.csv]
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
IRR = "examples/irrigation_abm/results"
FLD = "examples/single_agent/results"

DIRTY_MARKERS = ("group_a", "_bak", "_dead", "_quarantine", "/_", "\\_")

# Every selection expression found in the repo that feeds a paper or a claim.
# (owner script, arm label, pattern relative to REPO, note)
PATTERNS = [
    # ---- SUBMISSION_2026 / evidence / appraisal_composition.py (post-fix) ----
    ("SUBMISSION_2026/evidence/appraisal_composition.py", "irr gov",
     IRR + "/production_v21_42yr_{SEG}seed*/irrigation_farmer_governance_audit.csv", "per-model SEG"),
    ("SUBMISSION_2026/evidence/appraisal_composition.py", "irr ung",
     IRR + "/ungoverned_v21_42yr_{SEG}seed*/irrigation_farmer_governance_audit.csv", "per-model SEG"),
    ("SUBMISSION_2026/evidence/appraisal_composition.py", "flood gov",
     FLD + "/JOH_FINAL/{M}/Group_C/**/*governance_audit.csv", "post-fix: Group_C named"),
    ("SUBMISSION_2026/evidence/appraisal_composition.py", "flood ung",
     FLD + "/JOH_ABLATION_DISABLED/{M}/Group_C_disabled/**/*governance_audit.csv", "post-fix"),
    # ---- AAMAS2027 copy: the UNFIXED original, still runnable ----
    ("AAMAS2027/experiments/appraisal_composition.py", "flood gov",
     FLD + "/JOH_FINAL/{M}/**/*governance_audit.csv", "PRE-fix copy still on disk"),
    ("AAMAS2027/experiments/appraisal_composition.py", "flood ung",
     FLD + "/JOH_ABLATION_DISABLED/{M}/**/*governance_audit.csv", "PRE-fix copy"),
    # ---- SUBMISSION_2026 / evidence / rederive_executed_levels.py ----
    ("SUBMISSION_2026/evidence/rederive_executed_levels.py", "flood strict",
     FLD + "/JOH_FINAL/**/*governance_audit.csv", "bare ** over the whole base dir"),
    ("SUBMISSION_2026/evidence/rederive_executed_levels.py", "flood strict v2",
     FLD + "/JOH_FINAL_v2/**/*governance_audit.csv", ""),
    ("SUBMISSION_2026/evidence/rederive_executed_levels.py", "flood disabled",
     FLD + "/JOH_ABLATION_DISABLED/**/*governance_audit.csv", ""),
    ("SUBMISSION_2026/evidence/rederive_executed_levels.py", "flood disabled v2",
     FLD + "/JOH_ABLATION_DISABLED_v2/**/*governance_audit.csv", ""),
    ("SUBMISSION_2026/evidence/rederive_executed_levels.py", "irr strict",
     IRR + "/production_v21_*/irrigation_farmer_governance_audit.csv", "all models pooled"),
    ("SUBMISSION_2026/evidence/rederive_executed_levels.py", "irr disabled",
     IRR + "/ungoverned_v21_*/irrigation_farmer_governance_audit.csv", "all models pooled"),
    # ---- SUBMISSION_2026 / evidence / skeleton_claims_check.py ----
    ("SUBMISSION_2026/evidence/skeleton_claims_check.py", "flood inventory gov",
     FLD + "/JOH_FINAL/{M}/**/household_governance_audit.csv", "flood_runs() + claim_4 probe"),
    ("SUBMISSION_2026/evidence/skeleton_claims_check.py", "flood inventory ung",
     FLD + "/JOH_ABLATION_DISABLED/{M}/**/household_governance_audit.csv", ""),
    # ---- SUBMISSION_2026 / papers / workshop_evidence.py (explicit, no **) ----
    ("SUBMISSION_2026/papers/workshop_evidence.py", "flood gov",
     FLD + "/JOH_FINAL/{M}/Group_C/Run_*", "explicit Group_C + Run_*"),
    ("SUBMISSION_2026/papers/workshop_evidence.py", "flood ung",
     FLD + "/JOH_ABLATION_DISABLED/{M}/Group_C_disabled/Run_*", ""),
    # ---- Nature Water figure/table scripts ----
    ("paper/nature_water/scripts/gen_fig3_crossmodel.py", "flood gov",
     FLD + "/JOH_FINAL/{M}/Group_C/Run_*", "v2-first fallback, per arm"),
    ("paper/nature_water/scripts/gen_fig3_crossmodel.py", "flood ung",
     FLD + "/JOH_ABLATION_DISABLED/{M}/Group_C_disabled/Run_*", ""),
    ("paper/nature_water/scripts/gen_si_cumulative_adaptation.py", "ungoverned series",
     FLD + "/JOH_FINAL/gemma3_4b/Group_A/Run_*/simulation_log.csv", "Group_A used AS the arm"),
    ("paper/nature_water/scripts/gen_si_cumulative_adaptation.py", "governed series",
     FLD + "/JOH_FINAL/gemma3_4b/Group_B/Run_*/simulation_log.csv", "Group_B no longer exists"),
    ("examples/single_agent/analysis/nw_flood_pmt_crosstab.py", "ungoverned",
     FLD + "/JOH_FINAL/gemma3_4b/Group_A/Run_*/simulation_log.csv", "Group_A used AS the arm"),
    ("examples/single_agent/analysis/nw_flood_ibr_decomposition.py", "ungoverned",
     FLD + "/JOH_FINAL/gemma3_4b/Group_A/Run_*/*.csv", "Group_A used AS the arm"),
]

SEGS = ["", "gemma3_12b_", "gemma4_e2b_", "gemma4_e4b_", "ministral3_8b_"]


def expand(pattern):
    """Expand {SEG} / {M} placeholders into the concrete patterns actually used."""
    if "{SEG}" in pattern:
        return [pattern.replace("{SEG}", s) for s in SEGS]
    if "{M}" in pattern:
        root = os.path.join(REPO, pattern.split("/{M}/")[0])
        if not os.path.isdir(root):
            return []
        models = sorted(m for m in os.listdir(root)
                        if os.path.isdir(os.path.join(root, m)))
        return [pattern.replace("{M}", m) for m in models]
    return [pattern]


def dirty(path):
    p = path.replace("\\", "/").lower()
    return [k for k in ("group_a", "_bak", "_dead", "_quarantine") if k in p]


def rows_in(path):
    if not path.lower().endswith(".csv") or not os.path.isfile(path):
        return 0
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rd = csv.reader(fh)
        next(rd, None)
        return sum(1 for _ in rd)


def seed_of(run_dir):
    m = os.path.join(run_dir, "reproducibility_manifest.json")
    if os.path.isfile(m):
        try:
            return str(json.load(open(m, encoding="utf-8")).get("seed", "NA"))
        except Exception:
            return "UNREADABLE"
    base = os.path.basename(run_dir)
    if "seed" in base:
        return base.split("seed")[-1]
    return "NA"


def commit_of(run_dir):
    m = os.path.join(run_dir, "reproducibility_manifest.json")
    if os.path.isfile(m):
        try:
            j = json.load(open(m, encoding="utf-8"))
            c = j.get("git_commit")
            return (c[:8] if c else "NONE") + ("+dirty" if j.get("git_dirty") else "")
        except Exception:
            return "UNREADABLE"
    return "NO-MANIFEST"


def audit_patterns(out_rows):
    print("=" * 110)
    print("1. PATTERN RESOLUTION -- what each selection expression matches today")
    print("=" * 110)
    for owner, arm, pat, note in PATTERNS:
        for concrete in expand(pat):
            hits = sorted(glob.glob(os.path.join(REPO, concrete), recursive=True))
            bad = [h for h in hits if dirty(h)]
            nrows = sum(rows_in(h) for h in hits)
            badrows = sum(rows_in(h) for h in bad)
            verdict = "CONTAMINATED" if bad else ("EMPTY" if not hits else "clean")
            out_rows.append({
                "script": owner, "arm": arm, "pattern": concrete,
                "n_matched": len(hits), "n_rows": nrows,
                "n_contaminating": len(bad), "contaminating_rows": badrows,
                "verdict": verdict, "note": note,
                "contaminating_paths": ";".join(os.path.relpath(b, REPO) for b in bad),
            })
            flag = {"CONTAMINATED": "!!", "EMPTY": "??", "clean": "  "}[verdict]
            print(f"{flag} {owner:58s} {arm:18s} n={len(hits):>3d} rows={nrows:>7,d} {verdict}")
            if len(hits) <= 0:
                print(f"     pattern matched NOTHING: {concrete}")
            for b in bad:
                print(f"     + {os.path.relpath(b, REPO)}  ({rows_in(b):,d} rows)")


def audit_arm_symmetry():
    print()
    print("=" * 110)
    print("2. ARM SYMMETRY -- seed sets, run counts and code commits, per cell")
    print("=" * 110)
    print(f"{'cell':26s} {'arm':4s} {'n':>2s}  {'seeds':<26s} {'commits'}")
    print("-" * 110)
    problems = []
    for seg, lab in zip(SEGS, ["gemma3_4b", "gemma3_12b", "gemma4_e2b",
                               "gemma4_e4b", "ministral3_8b"]):
        info = {}
        for arm, pre in (("gov", "production"), ("ung", "ungoverned")):
            ds = sorted(glob.glob(os.path.join(REPO, IRR, f"{pre}_v21_42yr_{seg}seed*")))
            info[arm] = (sorted(seed_of(d) for d in ds), [commit_of(d) for d in ds])
            print(f"{'irrigation ' + lab:26s} {arm:4s} {len(ds):>2d}  "
                  f"{','.join(info[arm][0]):<26s} {','.join(sorted(set(info[arm][1])))}")
        if info["gov"][0] != info["ung"][0]:
            problems.append(f"irrigation {lab}: seed sets differ "
                            f"{info['gov'][0]} vs {info['ung'][0]}")
        print()
    for gb, ub in (("JOH_FINAL", "JOH_ABLATION_DISABLED"),
                   ("JOH_FINAL_v2", "JOH_ABLATION_DISABLED_v2")):
        root = os.path.join(REPO, FLD, gb)
        if not os.path.isdir(root):
            continue
        for m in sorted(x for x in os.listdir(root)
                        if os.path.isdir(os.path.join(root, x)) and not x.startswith("_")):
            info = {}
            for arm, base, sub in (("gov", gb, "Group_C"),
                                   ("ung", ub, "Group_C_disabled")):
                ds = sorted(glob.glob(os.path.join(REPO, FLD, base, m, sub, "Run_*")))
                ds = [d for d in ds if os.path.isdir(d)]
                info[arm] = (sorted(seed_of(d) for d in ds), [commit_of(d) for d in ds])
                print(f"{'flood ' + m:26s} {arm:4s} {len(ds):>2d}  "
                      f"{','.join(info[arm][0]):<26s} {','.join(sorted(set(info[arm][1])))}")
            if info["gov"][0] != info["ung"][0]:
                problems.append(f"flood {m}: seed sets differ "
                                f"{info['gov'][0]} vs {info['ung'][0]}")
            if set(info["gov"][1]) != set(info["ung"][1]):
                problems.append(f"flood {m}: arms built at DIFFERENT commits "
                                f"{sorted(set(info['gov'][1]))} vs {sorted(set(info['ung'][1]))}")
            print()
    print("ASYMMETRIES FOUND:")
    for p in problems:
        print("  !! " + p)
    if not problems:
        print("  none")
    return problems


def audit_completeness():
    print()
    print("=" * 110)
    print("3. RUN COMPLETENESS -- is a short audit CSV attrition or a dropped trace?")
    print("=" * 110)
    print("flood: simulation_log.csv is the complete record (1000 rows = 100 agents x 10 yr).")
    print("The audit CSV is shorter because relocated agents stop deciding. The real test is")
    print("whether EVERY sim row carrying a real decision also has an audit row.")
    bad = missing_tot = na_tot = 0
    for p in sorted(glob.glob(os.path.join(REPO, FLD, "JOH_*", "*", "Group_C*",
                                           "Run_*", "household_governance_audit.csv"))):
        sim_p = p.replace("household_governance_audit.csv", "simulation_log.csv")
        if not os.path.isfile(sim_p):
            print(f"  !! no simulation_log next to {os.path.relpath(p, REPO)}")
            continue
        akey = {(r["agent_id"], r["year"])
                for r in csv.DictReader(open(p, encoding="utf-8-sig", newline=""))}
        missing, na = [], 0
        for r in csv.DictReader(open(sim_p, encoding="utf-8-sig", newline="")):
            dec = str(r.get("yearly_decision", "")).strip().lower()
            if dec in ("relocated", "already_relocated"):
                continue          # agent already gone; no decision was taken
            if dec in ("n/a", "na", "", "none"):
                na += 1           # decision failed to produce -- audit row legitimately absent
                continue
            if (r["agent_id"], r["year"]) not in akey:
                missing.append((r["agent_id"], r["year"]))
        na_tot += na
        if missing:
            bad += 1
            missing_tot += len(missing)
            print(f"  !! {len(missing):>3d} real decisions with NO audit row: "
                  f"{os.path.relpath(p, REPO)}")
        if na:
            print(f"  .. {na:>3d} 'n/a' decision(s) (no decision produced) in "
                  f"{os.path.relpath(sim_p, REPO)}")
    print(f"  SILENT DROPS (a real decision with no audit row): {missing_tot} across {bad} runs")
    print(f"  'n/a' agent-years (decision never produced; audit row correctly absent): {na_tot}")

    print("\nirrigation: expected 78 agents x 42 years = 3276 audit rows per run.")
    bad = 0
    for p in sorted(glob.glob(os.path.join(REPO, IRR, "*_v21_42yr_*seed*",
                                           "irrigation_farmer_governance_audit.csv"))):
        n = rows_in(p)
        if n != 3276:
            bad += 1
            print(f"  !! {n:,d} rows (expected 3,276): {os.path.relpath(p, REPO)}")
    print(f"  irrigation runs off the expected row count: {bad}")


def audit_provenance():
    print()
    print("=" * 110)
    print("4. PROVENANCE -- git_commit / git_dirty across every manifest in both testbeds")
    print("=" * 110)
    tot = clean = nocommit = dirty_n = 0
    commits = {}
    for root in (IRR, FLD):
        for p in glob.glob(os.path.join(REPO, root, "**",
                                        "reproducibility_manifest.json"), recursive=True):
            tot += 1
            try:
                j = json.load(open(p, encoding="utf-8"))
            except Exception:
                continue
            c = j.get("git_commit")
            if not c:
                nocommit += 1
                commits["NONE"] = commits.get("NONE", 0) + 1
                continue
            commits[c[:9]] = commits.get(c[:9], 0) + 1
            if j.get("git_dirty"):
                dirty_n += 1
            else:
                clean += 1
    print(f"  manifests: {tot}   no commit recorded: {nocommit}   "
          f"commit + dirty: {dirty_n}   commit + CLEAN: {clean}")
    print(f"  distinct code states represented: {len(commits)}")
    for k, v in sorted(commits.items(), key=lambda kv: -kv[1]):
        print(f"    {k:10s} {v:>4d} runs")


def audit_corpus_counts():
    print()
    print("=" * 110)
    print("5. CORPUS COUNTS -- what the two testbeds actually hold")
    print("=" * 110)
    for root in (FLD, IRR):
        files = glob.glob(os.path.join(REPO, root, "**", "*governance_audit.csv"),
                          recursive=True)
        rows = sum(rows_in(p) for p in files)
        sims = glob.glob(os.path.join(REPO, root, "**", "simulation_log.csv"),
                         recursive=True)
        simrows = sum(rows_in(p) for p in sims)
        print(f"  {root:38s} audit files {len(files):>4d}  audit rows {rows:>8,d}"
              f"   sim files {len(sims):>4d}  sim rows {simrows:>8,d}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=os.path.join(os.path.dirname(__file__),
                                                  "data_selection_audit.csv"))
    args = ap.parse_args()
    out_rows = []
    audit_patterns(out_rows)
    audit_arm_symmetry()
    audit_completeness()
    audit_provenance()
    audit_corpus_counts()
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out_rows[0]))
            w.writeheader()
            w.writerows(out_rows)
        print(f"\nwrote {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
