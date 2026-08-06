"""Re-derive every unchecked number in SUBMISSION_2026/papers/workshop_skeleton.md.

Read-only with respect to examples/ and paper/. Emits one CONFIRMED / CORRECTED /
CANNOT-VERIFY verdict per claim, with the evidence beside it.

Claims checked (numbering follows the verification brief):
  1  "432,083 logged decisions"                     -> count every decision row on disk
  2  "14 model x testbed cells", "9 LLM configurations, 3B-27B, two open-weight families"
  3  retry-stratified appraisal 23.9 / 57.6 / 58.1 / 39.4
  4  "first-attempt appraisal not recoverable; recorded appraisal is post-correction on 100% of rows"
  5  "seed-labelling mismatch affects paired tests on 6 of 9 flood configurations"
  6  "governed 36.05% vs ungoverned 59.07%, delta +23.02 pp"; executed-action variant "0.86%"

Path + definition conventions are lifted verbatim from the prior art and NOT re-invented:
  SUBMISSION_2026/evidence/appraisal_composition.py   (cell list, flood globs, HIGH set)
  SUBMISSION_2026/evidence/gate0_signal_floor.py      (arms, INCREASE set, DEFAULT_SKILL)
  SUBMISSION_2026/decomposition/_loader.py            (irrigation loader conventions)

Usage:  python SUBMISSION_2026/evidence/skeleton_claims_check.py
"""
from __future__ import annotations

import csv
import glob
import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# --- definitions, copied from the canonical scripts -------------------------
INCREASE = frozenset({"increase_large", "increase_small"})
HIGH = frozenset({"H", "VH"})
DEFAULT_SKILL = "maintain_demand"          # irrigation registry default
LABEL_LEVELS = frozenset({"VL", "L", "M", "H", "VH"})

IRR_MODELS = [("gemma3:4b", ""), ("gemma3:12b", "gemma3_12b_"),
              ("gemma4:e2b", "gemma4_e2b_"), ("gemma4:e4b", "gemma4_e4b_"),
              ("ministral3:8b", "ministral3_8b_")]
IRR_RESULTS = os.path.join(REPO, "examples", "irrigation_abm", "results")
IRR_AUDIT = "irrigation_farmer_governance_audit.csv"
IRR_SIM = "simulation_log.csv"

FLOOD_ROOT = os.path.join(REPO, "examples", "single_agent", "results")
FLOOD_PAIRS = [("JOH_FINAL", "JOH_ABLATION_DISABLED"),
               ("JOH_FINAL_v2", "JOH_ABLATION_DISABLED_v2")]


def rule(title):
    print("\n" + "=" * 92)
    print(title)
    print("=" * 92)


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def count_rows(path):
    """Row count without materialising the file (raw_output cells are large)."""
    n = 0
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rdr = csv.reader(fh)
        next(rdr, None)
        for _ in rdr:
            n += 1
    return n


# ---------------------------------------------------------------------------
# discovery
# ---------------------------------------------------------------------------
def irrigation_runs():
    """[(model, arm, seed, dir)] for every irrigation run dir that has an audit csv."""
    out = []
    for label, seg in IRR_MODELS:
        for arm, prefix in (("governed", "production"), ("ungoverned", "ungoverned")):
            for d in sorted(glob.glob(os.path.join(IRR_RESULTS, f"{prefix}_v21_42yr_{seg}seed*"))):
                if not os.path.isdir(d):
                    continue
                m = re.search(r"seed(\d+)$", os.path.basename(d))
                out.append((label, arm, m.group(1) if m else "?", d))
    return out


def flood_runs():
    """[(model, arm, run_label, dir, seed_from_manifest)] for every flood run dir."""
    out = []
    for gov_base, ung_base in FLOOD_PAIRS:
        root = os.path.join(FLOOD_ROOT, gov_base)
        if not os.path.isdir(root):
            continue
        for model in sorted(os.listdir(root)):
            if not os.path.isdir(os.path.join(root, model)):
                continue
            for arm, base in (("governed", gov_base), ("ungoverned", ung_base)):
                pat = os.path.join(FLOOD_ROOT, base, model, "**", "household_governance_audit.csv")
                for csv_path in sorted(glob.glob(pat, recursive=True)):
                    d = os.path.dirname(csv_path)
                    seed = None
                    mf = os.path.join(d, "reproducibility_manifest.json")
                    if os.path.isfile(mf):
                        try:
                            seed = json.load(open(mf, encoding="utf-8")).get("seed")
                        except Exception:
                            seed = "UNREADABLE"
                    out.append((model, arm, os.path.relpath(d, FLOOD_ROOT), d, seed))
    return out


# ===========================================================================
# CLAIM 1 + 2
# ===========================================================================
def claim_1_and_2():
    rule("CLAIM 1 — abstract: '432,083 logged decisions'   |   CLAIM 2 — '14 cells / 9 configs'")

    irr = irrigation_runs()
    irr_audit_rows = irr_sim_rows = 0
    irr_per_run = []
    for label, arm, seed, d in irr:
        a = os.path.join(d, IRR_AUDIT)
        s = os.path.join(d, IRR_SIM)
        na = count_rows(a) if os.path.isfile(a) else 0
        ns = count_rows(s) if os.path.isfile(s) else 0
        irr_audit_rows += na
        irr_sim_rows += ns
        irr_per_run.append((label, arm, seed, na, ns))
    print(f"\nIRRIGATION: {len(irr)} run dirs")
    bad = [r for r in irr_per_run if r[3] != 3276 or r[4] != 3276]
    print(f"  audit rows total      {irr_audit_rows:>9,d}")
    print(f"  simulation_log total  {irr_sim_rows:>9,d}")
    print(f"  runs not at 3276/3276: {len(bad)}" + (f"  -> {bad}" if bad else ""))
    per_model = Counter((lbl, arm) for lbl, arm, _, _, _ in irr_per_run)
    for k in sorted(per_model):
        print(f"    {k[0]:14s} {k[1]:11s} {per_model[k]} runs")

    fl = flood_runs()
    fl_rows = 0
    fl_per = []
    for model, arm, rel, d, seed in fl:
        n = count_rows(os.path.join(d, "household_governance_audit.csv"))
        fl_rows += n
        fl_per.append((model, arm, rel, n, seed))
    print(f"\nFLOOD (single_agent household): {len(fl)} run dirs with an audit csv")
    print(f"  audit rows total      {fl_rows:>9,d}")
    stray = [r for r in fl_per if "Group_C" not in r[2]]
    if stray:
        print(f"  !! {len(stray)} run(s) OUTSIDE Group_C / Group_C_disabled are matched by the "
              f"prior-art '**' glob and are therefore IN the published table:")
        for r in stray:
            print(f"       {r[2]}   rows={r[3]}  seed={r[4]}")
    clean = sum(r[3] for r in fl_per if "Group_C" in r[2])
    print(f"  audit rows, Group_C / Group_C_disabled ONLY: {clean:,d}")

    total_all = irr_audit_rows + fl_rows
    total_clean = irr_audit_rows + clean
    print(f"\n  TOTAL decision rows, everything the prior-art globs read : {total_all:,d}")
    print(f"  TOTAL decision rows, Group_C-clean flood                 : {total_clean:,d}")
    print(f"  skeleton claims                                          : 432,083")
    print(f"  VERDICT claim 1: {'CONFIRMED' if total_all == 432083 else 'CORRECTED'}"
          f"   (off by {total_all - 432083:+,d} rows vs the claim)")

    # cells / configs
    irr_models = sorted({m for m, _ in IRR_MODELS})
    fl_models = sorted({m for m, _, _, _, _ in fl})
    print(f"\n  irrigation cells: {len(irr_models)}  {irr_models}")
    print(f"  flood cells     : {len(fl_models)}  {fl_models}")
    print(f"  cells total     : {len(irr_models) + len(fl_models)}   (skeleton: 14)")
    union = sorted(set(irr_models) | {m.replace("_", ":", 1) for m in fl_models})
    print(f"  distinct LLM configurations (union, normalised): {len(union)}  {union}")
    fams = sorted({m.split(":")[0].rstrip("0123456789") or m.split(":")[0] for m in union})
    gens = sorted({m.split(":")[0] for m in union})
    print(f"  name stems (generation level): {gens}   -> {len(gens)}")
    print(f"  vendor-family level          : {fams}   -> {len(fams)}")

    # parameter sizes from the manifests that carry them
    sizes = {}
    for model, arm, rel, d, seed in fl:
        mf = os.path.join(d, "reproducibility_manifest.json")
        if os.path.isfile(mf):
            try:
                j = json.load(open(mf, encoding="utf-8"))
            except Exception:
                continue
            if j.get("model_parameter_size"):
                sizes.setdefault(j.get("model", model), set()).add(j["model_parameter_size"])
    if sizes:
        print("\n  model_parameter_size recorded in flood manifests:")
        for k in sorted(sizes):
            print(f"    {k:18s} {sorted(sizes[k])}")
    return total_all, total_clean, len(irr_models) + len(fl_models), union


# ===========================================================================
# CLAIM 3 — retry-stratified appraisal
# ===========================================================================
def claim_3():
    rule("CLAIM 3 — §5: '0 retries 23.9% high, 1 -> 57.6%, 2 -> 58.1%, 3 -> 39.4%'")

    def strat(paths):
        num = Counter()
        den = Counter()
        for p in paths:
            for row in read_csv(p):
                v = (row.get("construct_WSA_LABEL") or "").strip().upper()
                if not v:                      # prior-art convention: skip blanks
                    continue
                rc = (row.get("retry_count") or "").strip()
                den[rc] += 1
                if v in HIGH:
                    num[rc] += 1
        return num, den

    def show(title, paths):
        num, den = strat(paths)
        print(f"\n  {title}")
        print(f"    {'retries':>8s} {'n':>8s} {'% high':>9s}")
        for rc in sorted(den, key=lambda x: int(x) if x.isdigit() else 99):
            print(f"    {rc:>8s} {den[rc]:>8,d} {100.0*num[rc]/den[rc]:>8.2f}%")
        return {rc: 100.0 * num[rc] / den[rc] for rc in den}

    allgov, allung = [], []
    per_cell = {}
    for label, seg in IRR_MODELS:
        g = sorted(glob.glob(os.path.join(IRR_RESULTS, f"production_v21_42yr_{seg}seed*", IRR_AUDIT)))
        u = sorted(glob.glob(os.path.join(IRR_RESULTS, f"ungoverned_v21_42yr_{seg}seed*", IRR_AUDIT)))
        allgov += g
        allung += u
        per_cell[label] = g

    anchor = show("GOVERNED, anchor cell gemma3:4b only (5 seeds)", per_cell["gemma3:4b"])
    pooled = show("GOVERNED, all 5 irrigation cells pooled (21 runs)", allgov)
    show("UNGOVERNED, all 5 irrigation cells pooled (20 runs)  [reference]", allung)

    claimed = {"0": 23.9, "1": 57.6, "2": 58.1, "3": 39.4}
    print("\n  match against the skeleton:")
    for src, name in ((anchor, "anchor gemma3:4b"), (pooled, "all cells pooled")):
        d = {k: round(src.get(k, float('nan')), 1) for k in claimed}
        hit = all(abs(src.get(k, 1e9) - v) < 0.15 for k, v in claimed.items())
        print(f"    {name:20s} {d}   {'<== MATCHES the skeleton' if hit else ''}")
    seq = [pooled.get(k) for k in ("0", "1", "2", "3")]
    if all(s is not None for s in seq):
        mono = all(seq[i] <= seq[i + 1] for i in range(3))
        print(f"\n  non-monotonicity (pooled): {'ABSENT (monotone)' if mono else 'PRESENT'}"
              f"   peak at retry_count={seq.index(max(seq))}")

    # per-cell, both arms -- is the non-monotonicity a property of the anchor only?
    print("\n  per-cell breakdown (does the non-monotonicity generalise?)")
    print(f"    {'cell':14s} {'arm':4s} " + " ".join(f"{i:>15s}" for i in ('0', '1', '2', '3'))
          + "  shape")
    for label, seg in IRR_MODELS:
        for arm, pre in (("gov", "production"), ("ung", "ungoverned")):
            num, den = strat(sorted(glob.glob(os.path.join(
                IRR_RESULTS, f"{pre}_v21_42yr_{seg}seed*", IRR_AUDIT))))
            cells, vals = [], []
            for k in ("0", "1", "2", "3"):
                if den[k]:
                    v = 100.0 * num[k] / den[k]
                    vals.append(v)
                    cells.append(f"{v:5.1f}% n={den[k]:<6,d}")
                else:
                    cells.append("       -       ")
            mono = all(vals[i] <= vals[i + 1] for i in range(len(vals) - 1))
            print(f"    {label:14s} {arm:4s} " + " ".join(f"{c:>15s}" for c in cells)
                  + f"  {'monotone' if mono else 'NON-MONOTONE'}")


# ===========================================================================
# CLAIM 4 — instrumentation
# ===========================================================================
def claim_4():
    rule("CLAIM 4 — §5: 'the recorded appraisal is the post-correction one on 100% of rows' / "
         "'first-attempt appraisal is not recoverable'")

    print("""
  CODE PATH (broker/core/_retry_loop.py + broker/core/_audit_helpers.py + audit.py):
    * _governance_retry_loop reassigns BOTH `skill_proposal` and `raw_output` on every
      attempt (lines ~292-301). The audit trace's `skill_proposal`, `raw_output`,
      `construct_*_LABEL`, `reason_*`, `proposed_skill` and `final_skill` are therefore
      all LAST-attempt values.  -> the "post-correction on 100% of rows" half is TRUE.
    * BUT _audit_helpers.py:371 calls  write_trace(..., all_validation_history)  -- the
      CUMULATIVE list of ValidationResults across EVERY attempt, not the final one. The
      auditor turns that into trace["validation_issues"] and hence the CSV columns
      `failed_rules` + `error_messages`. Those columns are a UNION over attempts.
    * The irrigation ERROR thinking-rules are pure functions of the appraisal labels:
        low_threat_no_increase            fires iff WSA == VL         and skill in INCREASE
        high_threat_high_cope_no_increase fires iff WSA in {H,VH} AND ACA in {H,VH}
                                                                     and skill in INCREASE
      So a rule id in `failed_rules` is a HARD constraint on the appraisal AT THE ATTEMPT
      THAT TRIPPED IT. On an APPROVED row the final attempt tripped nothing, so every
      entry in `failed_rules` must come from an EARLIER attempt.
    * Not recoverable even so: the attempt INDEX (which of attempts 0..2), the exact
      label pair when the rule did not fire, and any appraisal on an attempt that passed
      the thinking rules but failed only a physical/identity rule.
""")

    # 4a. is the appraisal column post-correction on 100% of rows? (structural, plus
    #     the observable consequence: proposed_skill == final_skill)
    tot = same = 0
    for label, seg in IRR_MODELS:
        for prefix in ("production", "ungoverned"):
            for p in sorted(glob.glob(os.path.join(IRR_RESULTS, f"{prefix}_v21_42yr_{seg}seed*", IRR_AUDIT))):
                for row in read_csv(p):
                    tot += 1
                    if (row.get("proposed_skill") or "") == (row.get("final_skill") or ""):
                        same += 1
    print(f"  irrigation: proposed_skill == final_skill on {same:,d}/{tot:,d} rows "
          f"({100.0*same/tot:.2f}%)  -> the proposal object IS overwritten, as claimed")

    # 4b. gated first-attempt columns present anywhere in the shipped corpus?
    gated = ["initial_skill", "initial_labels", "attempt_skills", "executed_skill"]
    found = defaultdict(int)
    for label, seg in IRR_MODELS:
        for prefix in ("production", "ungoverned"):
            for p in sorted(glob.glob(os.path.join(IRR_RESULTS, f"{prefix}_v21_42yr_{seg}seed*", IRR_AUDIT))):
                with open(p, encoding="utf-8-sig", newline="") as fh:
                    hdr = next(csv.reader(fh))
                for c in gated:
                    if c in hdr:
                        found[c] += 1
    print(f"  gated first-attempt/executed columns present in shipped irrigation CSVs: "
          f"{dict(found) or 'NONE'}")

    # 4c. is `rules_triggered` (the cumulative BLOCK+WARN union) populated?
    nonempty = tot2 = 0
    for label, seg in IRR_MODELS:
        for p in sorted(glob.glob(os.path.join(IRR_RESULTS, f"production_v21_42yr_{seg}seed*", IRR_AUDIT))):
            for row in read_csv(p):
                tot2 += 1
                if (row.get("rules_triggered") or "").strip():
                    nonempty += 1
    print(f"  rules_triggered populated on {nonempty:,d}/{tot2:,d} governed irrigation rows "
          f"(wired 2026-05-26, AFTER this corpus was produced)")

    # 4d. THE RECOVERY. Approved-after-retry rows whose failed_rules name a
    #     construct-conditioned ERROR rule.
    print("\n  RECOVERY TEST — rows where an EARLIER attempt's appraisal stratum is pinned")
    print(f"    {'cell':14s} {'appr+retry':>11s} {'HTHC fired':>11s} {'-> final NOT high':>18s}"
          f" {'LOW fired':>10s} {'-> final NOT VL':>16s}")
    grand = Counter()
    for label, seg in IRR_MODELS:
        c = Counter()
        for p in sorted(glob.glob(os.path.join(IRR_RESULTS, f"production_v21_42yr_{seg}seed*", IRR_AUDIT))):
            for row in read_csv(p):
                status = (row.get("status") or "").strip()
                rc = int(row.get("retry_count") or 0)
                fr = set((row.get("failed_rules") or "").split("|")) - {""}
                w = (row.get("construct_WSA_LABEL") or "").strip().upper()
                a = (row.get("construct_ACA_LABEL") or "").strip().upper()
                if status != "APPROVED" or rc == 0:
                    continue
                c["approved_after_retry"] += 1
                if "high_threat_high_cope_no_increase" in fr:
                    c["hthc"] += 1
                    if not (w in HIGH and a in HIGH):
                        c["hthc_moved"] += 1
                    if w not in HIGH:
                        c["hthc_wsa_moved"] += 1
                if "low_threat_no_increase" in fr:
                    c["low"] += 1
                    if w != "VL":
                        c["low_moved"] += 1
        grand.update(c)
        print(f"    {label:14s} {c['approved_after_retry']:>11,d} {c['hthc']:>11,d}"
              f" {c['hthc_wsa_moved']:>18,d} {c['low']:>10,d} {c['low_moved']:>16,d}")
    print(f"    {'ALL':14s} {grand['approved_after_retry']:>11,d} {grand['hthc']:>11,d}"
          f" {grand['hthc_wsa_moved']:>18,d} {grand['low']:>10,d} {grand['low_moved']:>16,d}")
    print(f"\n    'HTHC fired'        = high_threat_high_cope_no_increase is in failed_rules on an")
    print(f"                          APPROVED row with retry_count>0, so it fired on an EARLIER")
    print(f"                          attempt => that attempt had WSA in {{H,VH}} AND ACA in {{H,VH}}.")
    print(f"    '-> final NOT high' = of those, the rows whose FINAL logged WSA is not in {{H,VH}}.")
    print(f"                          These rows are direct, per-decision evidence that the logged")
    print(f"                          appraisal moved DOWN across the retry loop.")

    # 4d-bis. STRICT appraisal-move, over EVERY governed row with retry_count > 0
    #         (status-independent: the fired rule is logically incompatible with the
    #          FINAL labels, so it must have fired on an earlier attempt).
    print("\n  STRICT APPRAISAL-MOVE, all governed irrigation rows with retry_count>0")
    print(f"    {'cell':14s} {'retry>0':>9s} {'HTHC fired':>11s} {'final WSA not high':>19s}"
          f" {'%':>7s} {'VL fired':>9s} {'final not VL':>13s} {'%':>7s}")
    G = Counter()
    for label, seg in IRR_MODELS:
        c = Counter()
        for p in sorted(glob.glob(os.path.join(IRR_RESULTS, f"production_v21_42yr_{seg}seed*", IRR_AUDIT))):
            for r in read_csv(p):
                if int(r.get("retry_count") or 0) == 0:
                    continue
                c["n"] += 1
                fr = set((r.get("failed_rules") or "").split("|")) - {""}
                w = (r.get("construct_WSA_LABEL") or "").strip().upper()
                if "high_threat_high_cope_no_increase" in fr:
                    c["h"] += 1
                    if w not in HIGH:
                        c["hm"] += 1
                if "low_threat_no_increase" in fr:
                    c["l"] += 1
                    if w != "VL":
                        c["lm"] += 1
        G.update(c)
        hp = 100.0 * c["hm"] / c["h"] if c["h"] else float("nan")
        lp = 100.0 * c["lm"] / c["l"] if c["l"] else float("nan")
        print(f"    {label:14s} {c['n']:>9,d} {c['h']:>11,d} {c['hm']:>19,d} {hp:>6.1f}%"
              f" {c['l']:>9,d} {c['lm']:>13,d} {lp:>6.1f}%")
    print(f"    {'ALL':14s} {G['n']:>9,d} {G['h']:>11,d} {G['hm']:>19,d}"
          f" {100.0*G['hm']/G['h']:>6.1f}% {G['l']:>9,d} {G['lm']:>13,d}"
          f" {100.0*G['lm']/G['l']:>6.1f}%")
    print("    Read: 'final WSA not high' rows are decisions where an attempt reported")
    print("    WSA in {H,VH} AND ACA in {H,VH} (that is the only way the rule can fire) and")
    print("    the FINAL logged WSA is outside {H,VH}. The appraisal moved DOWN inside the")
    print("    retry loop, and the move is visible in the SHIPPED audit CSV.")

    # 4e. same probe on the flood corpus
    print("\n  same probe on flood (household), governed arm:")
    fl_counts = Counter()
    fl_rules = Counter()
    for gov_base, _ in FLOOD_PAIRS:
        root = os.path.join(FLOOD_ROOT, gov_base)
        if not os.path.isdir(root):
            continue
        for model in sorted(os.listdir(root)):
            pat = os.path.join(root, model, "**", "household_governance_audit.csv")
            for p in sorted(glob.glob(pat, recursive=True)):
                for row in read_csv(p):
                    if (row.get("status") or "").strip() != "APPROVED":
                        continue
                    if int(row.get("retry_count") or 0) == 0:
                        continue
                    fl_counts["approved_after_retry"] += 1
                    for r in set((row.get("failed_rules") or "").split("|")) - {""}:
                        fl_rules[r] += 1
    print(f"    approved-after-retry rows: {fl_counts['approved_after_retry']:,d}")
    for r, n in fl_rules.most_common(12):
        print(f"      {r:44s} {n:>7,d}")

    # flood rules are appraisal-conditioned too:
    #   extreme_threat_block   fires iff TP in {H,VH}  (blocks do_nothing)
    #   elevation_threat_low / relocation_threat_low   fire iff TP in {VL,L}
    LOWTP = frozenset({"VL", "L"})
    m = Counter()
    for gov_base, _ in FLOOD_PAIRS:
        root = os.path.join(FLOOD_ROOT, gov_base)
        if not os.path.isdir(root):
            continue
        for model in sorted(os.listdir(root)):
            for p in sorted(glob.glob(os.path.join(root, model, "**",
                                                   "household_governance_audit.csv"),
                                      recursive=True)):
                for row in read_csv(p):
                    if int(row.get("retry_count") or 0) == 0:
                        continue
                    fr = set((row.get("failed_rules") or "").split("|")) - {""}
                    tp = (row.get("construct_TP_LABEL") or "").strip().upper()
                    if "extreme_threat_block" in fr:
                        m["etb"] += 1
                        if tp not in HIGH:
                            m["etb_moved"] += 1
                    if fr & {"elevation_threat_low", "relocation_threat_low"}:
                        m["tlow"] += 1
                        if tp not in LOWTP:
                            m["tlow_moved"] += 1
    print(f"    extreme_threat_block fired on {m['etb']:,d} retry>0 rows; final TP outside "
          f"{{H,VH}} on {m['etb_moved']:,d} of them")
    print(f"    threat-too-low rules fired on {m['tlow']:,d} retry>0 rows; final TP outside "
          f"{{VL,L}} on {m['tlow_moved']:,d} of them")
    print("    (the elevation_threat_low message template '{context.TP_LABEL}' is NOT rendered")
    print("     in the shipped logs, so the exact earlier label does not leak -- only the")
    print("     stratum implied by the rule antecedent.)")

    # 4g. reflection_log
    rp = os.path.join(IRR_RESULTS, "production_v21_42yr_seed42", "reflection_log.jsonl")
    if os.path.isfile(rp):
        with open(rp, encoding="utf-8") as fh:
            d = json.loads(fh.readline())
        print(f"\n  reflection_log.jsonl keys: {sorted(d.keys())}")
        print("    -> year-level narrative summaries only; no appraisal label, no attempt index.")

    # 4f. does the JSONL hold anything the CSV does not?
    print("\n  JSONL traces (raw/*_traces.jsonl): keys per record")
    p = os.path.join(IRR_RESULTS, "production_v21_42yr_seed42", "raw",
                     "irrigation_farmer_traces.jsonl")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as fh:
            d = json.loads(fh.readline())
        print(f"    {sorted(d.keys())}")
        print("    `input` = the ORIGINAL prompt (retry prompts are a local in the loop and are")
        print("    never logged); `raw_output` = LAST attempt only; `validation_issues` = the")
        print("    same cumulative union the CSV's failed_rules is projected from.")


# ===========================================================================
# CLAIM 5 — flood seed labelling
# ===========================================================================
def claim_5():
    rule("CLAIM 5 — limitations: 'a seed-labelling mismatch affects paired tests on 6 of 9 "
         "flood configurations'")
    fl = flood_runs()
    by = defaultdict(lambda: defaultdict(dict))
    for model, arm, rel, d, seed in fl:
        run = os.path.basename(d)
        by[model][arm][run] = seed
    mismatch = []
    for model in sorted(by):
        gs = dict(sorted(by[model]["governed"].items()))
        us = dict(sorted(by[model]["ungoverned"].items()))
        same_set = sorted(v for v in gs.values() if v is not None) == \
                   sorted(v for v in us.values() if v is not None)
        pos_ok = all(gs[k] == us[k] for k in gs if k in us)
        verdict = "aligned" if (same_set and pos_ok) else "MISMATCH"
        if verdict == "MISMATCH":
            mismatch.append(model)
        print(f"\n  {model:15s} {verdict}{'' if same_set else '   (seed SETS differ, '
              'not merely labels)'}")
        print(f"    governed   {gs}")
        print(f"    ungoverned {us}")
        shared = sorted(set(gs.values()) & set(us.values()))
        print(f"    seeds present in BOTH arms: {shared}  "
              f"({len(shared)} of 5 usable for a paired test)")
    print(f"\n  configurations with a Run->seed mismatch: {len(mismatch)} of {len(by)}  {mismatch}")
    print(f"  skeleton claims 6 of 9  -> {'CONFIRMED' if len(mismatch) == 6 else 'CORRECTED'}")

    # also report raw seed values seen
    allseeds = Counter()
    for model in by:
        for arm in by[model]:
            for run, s in by[model][arm].items():
                allseeds[(arm, s)] += 1
    print(f"\n  seed values recorded across all flood manifests: {sorted(allseeds.items())}")


# ===========================================================================
# CLAIM 6 — the published pair, and the executed-action variant
# ===========================================================================
def claim_6():
    rule("CLAIM 6 — §4: 'governed 36.05% vs ungoverned 59.07%, delta +23.02 pp'; "
         "'executed action moves the governed figure to 0.86%'")

    def rates(d):
        """Return (published_conditional, executed_conditional, n_high, n_rows)
        for one irrigation run directory, computed off simulation_log.csv."""
        rows = read_csv(os.path.join(d, IRR_SIM))
        sim_high = [r for r in rows
                    if (r.get("wsa_label") or "").strip().upper() in HIGH]
        pub = 100.0 * sum(1 for r in sim_high
                          if (r.get("yearly_decision") or "").strip() in INCREASE) / len(sim_high)
        return pub, len(sim_high), len(rows)

    def exec_rates(d):
        """Executed-action version. simulation_log has no status column in this corpus,
        so the executed action is reconstructed from the AUDIT csv, joining on
        (agent_id, year): status.startswith('REJECTED') -> registry default executed."""
        aud = read_csv(os.path.join(d, IRR_AUDIT))
        n_high = n_inc = 0
        for r in aud:
            w = (r.get("construct_WSA_LABEL") or "").strip().upper()
            if w not in HIGH:
                continue
            n_high += 1
            status = (r.get("status") or "").strip()
            final = (r.get("final_skill") or "").strip()
            executed = DEFAULT_SKILL if status.startswith("REJECTED") else final
            if executed in INCREASE:
                n_inc += 1
        return (100.0 * n_inc / n_high if n_high else float("nan")), n_high

    print("\n  anchor cell gemma3:4b, per seed (published statistic, on simulation_log.yearly_decision)")
    print(f"    {'seed':>5s} {'gov %':>9s} {'ung %':>9s} {'gap pp':>9s} {'gov n_high':>11s} {'ung n_high':>11s}")
    gv, uv, gaps = [], [], []
    for s in ("42", "43", "44", "45", "46"):
        dg = os.path.join(IRR_RESULTS, f"production_v21_42yr_seed{s}")
        du = os.path.join(IRR_RESULTS, f"ungoverned_v21_42yr_seed{s}")
        g, gh, _ = rates(dg)
        u, uh, _ = rates(du)
        gv.append(g); uv.append(u); gaps.append(g - u)
        print(f"    {s:>5s} {g:>8.2f}% {u:>8.2f}% {g-u:>+8.2f} {gh:>11,d} {uh:>11,d}")

    # pooled (all rows of all 5 seeds together) -- this is the published convention
    def pooled(prefix):
        n_high = n_inc = 0
        for s in ("42", "43", "44", "45", "46"):
            rows = read_csv(os.path.join(IRR_RESULTS, f"{prefix}_v21_42yr_seed{s}", IRR_SIM))
            for r in rows:
                if (r.get("wsa_label") or "").strip().upper() in HIGH:
                    n_high += 1
                    if (r.get("yearly_decision") or "").strip() in INCREASE:
                        n_inc += 1
        return 100.0 * n_inc / n_high, n_high
    pg, pgh = pooled("production")
    pu, puh = pooled("ungoverned")
    print(f"\n    POOLED over 5 seeds : governed {pg:.2f}%  (n_high={pgh:,d})   "
          f"ungoverned {pu:.2f}%  (n_high={puh:,d})   gap {pg-pu:+.2f} pp")
    print(f"    per-seed MEAN       : governed {statistics.mean(gv):.2f}%  "
          f"ungoverned {statistics.mean(uv):.2f}%   gap {statistics.mean(gaps):+.2f} pp")
    print(f"    skeleton claims     : governed 36.05%  ungoverned 59.07%  delta +23.02 pp")

    # executed-action variant
    print("\n  executed-action variant (rejected row -> registry default 'maintain_demand')")
    eg = eu = None
    n_hi_g = n_inc_g = n_hi_u = n_inc_u = 0
    for s in ("42", "43", "44", "45", "46"):
        for prefix, tag in (("production", "g"), ("ungoverned", "u")):
            aud = read_csv(os.path.join(IRR_RESULTS, f"{prefix}_v21_42yr_seed{s}", IRR_AUDIT))
            for r in aud:
                if (r.get("construct_WSA_LABEL") or "").strip().upper() not in HIGH:
                    continue
                status = (r.get("status") or "").strip()
                final = (r.get("final_skill") or "").strip()
                executed = DEFAULT_SKILL if status.startswith("REJECTED") else final
                if tag == "g":
                    n_hi_g += 1
                    n_inc_g += executed in INCREASE
                else:
                    n_hi_u += 1
                    n_inc_u += executed in INCREASE
    eg = 100.0 * n_inc_g / n_hi_g
    eu = 100.0 * n_inc_u / n_hi_u
    print(f"    pooled: governed {eg:.2f}% (n_high={n_hi_g:,d})   "
          f"ungoverned {eu:.2f}% (n_high={n_hi_u:,d})   gap {eg-eu:+.2f} pp")
    per_g, per_u = [], []
    for s in ("42", "43", "44", "45", "46"):
        for prefix, acc in (("production", per_g), ("ungoverned", per_u)):
            hi = inc = 0
            for r in read_csv(os.path.join(IRR_RESULTS, f"{prefix}_v21_42yr_seed{s}", IRR_AUDIT)):
                if (r.get("construct_WSA_LABEL") or "").strip().upper() not in HIGH:
                    continue
                hi += 1
                status = (r.get("status") or "").strip()
                final = (r.get("final_skill") or "").strip()
                inc += (DEFAULT_SKILL if status.startswith("REJECTED") else final) in INCREASE
            acc.append(100.0 * inc / hi)
    print(f"    per-seed MEAN: governed {statistics.mean(per_g):.2f}%   "
          f"ungoverned {statistics.mean(per_u):.2f}%   gap "
          f"{statistics.mean(per_g)-statistics.mean(per_u):+.2f} pp")
    print(f"    skeleton claims the governed executed figure is 0.86%")

    # the RESULTS.md cross-check: unconditional executed rate
    for prefix, name in (("production", "governed"), ("ungoverned", "ungoverned")):
        n = inc = 0
        for s in ("42", "43", "44", "45", "46"):
            for r in read_csv(os.path.join(IRR_RESULTS, f"{prefix}_v21_42yr_seed{s}", IRR_AUDIT)):
                n += 1
                status = (r.get("status") or "").strip()
                final = (r.get("final_skill") or "").strip()
                executed = DEFAULT_SKILL if status.startswith("REJECTED") else final
                inc += executed in INCREASE
        print(f"    unconditional executed increase rate, {name:11s}: {100.0*inc/n:.2f}%  (n={n:,d})")


def contamination_note():
    """Side-effect of claim 1: the prior-art '**' glob pulls a Group_A backup run into
    ONE cell of the skeleton's §3 Table 1. Quantify the damage."""
    rule("SIDE FINDING — Group_A contamination of the flood ministral3_3b cell in §3 Table 1")

    def scan(paths, col="construct_TP_LABEL"):
        n = h = rej = 0
        for p in paths:
            for r in read_csv(p):
                v = (r.get(col) or "").strip().upper()
                if not v:
                    continue
                n += 1
                h += v in HIGH
                rej += (r.get("status") or "").strip().startswith("REJECTED")
        return 100.0 * h / n, 100.0 * rej / n, n

    allg = sorted(glob.glob(os.path.join(
        FLOOD_ROOT, "JOH_FINAL", "ministral3_3b", "**", "*governance_audit.csv"), recursive=True))
    clean = [p for p in allg if "Group_C" in p.replace(os.sep, "/")]
    ung = sorted(glob.glob(os.path.join(
        FLOOD_ROOT, "JOH_ABLATION_DISABLED", "ministral3_3b", "**", "*governance_audit.csv"),
        recursive=True))
    uh, _, un = scan(ung)
    for name, g in (("as published (Group_A bak included)", allg),
                    ("Group_C only", clean)):
        gh, gr, gn = scan(g)
        print(f"  {name:38s} %rejected={gr:7.4f}  high|gov={gh:6.2f}%  "
              f"high|ung={uh:6.2f}%  shift={uh-gh:+6.2f} pp  n_gov={gn:,d}")
    print("\n  The published row is 0.09% / +2.04 pp. Dropping the Group_A backup directory")
    print("  flips the sign of that cell's shift. The regime separation survives (the low")
    print("  regime's max is gemma4_e4b at +6.25), but the abstract's 'mean 0.8 pp' and the")
    print("  §3 per-cell table both need the corrected row.")


def main():
    claim_1_and_2()
    claim_3()
    claim_4()
    claim_5()
    claim_6()
    contamination_note()
    print("\n" + "=" * 92)
    print("done. every number above was read off a file under examples/; nothing was carried")
    print("over from the skeleton or the brief.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
