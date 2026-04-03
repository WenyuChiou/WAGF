"""
Flood IBR Decomposition by PMT Threat×Coping Quadrants
=======================================================
Nature Water — Insight B / R2: Structured non-compliance at institutional boundaries

Analyzes governed (Group B+C) and ungoverned (Group A) flood decisions
by PMT appraisal quadrants (TP × CP).
"""

import pandas as pd
import numpy as np
import os
import re
from collections import Counter

# ─── File paths ──────────────────────────────────────────────────────────
BASE = "C:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/single_agent/results/JOH_FINAL/gemma3_4b"

governed_files = []
for grp in ["Group_B", "Group_C"]:
    for run in ["Run_1", "Run_2", "Run_3"]:
        f = os.path.join(BASE, grp, run, "household_governance_audit.csv")
        if os.path.exists(f):
            governed_files.append((grp, run, f))

ungoverned_files = []
for run in ["Run_1", "Run_2", "Run_3"]:
    # Group A has simulation_log.csv, different format
    f = os.path.join(BASE, "Group_A", run, "simulation_log.csv")
    if os.path.exists(f):
        ungoverned_files.append(("Group_A", run, f))
    # Also check for governance audit just in case
    f2 = os.path.join(BASE, "Group_A", run, "household_governance_audit.csv")
    if os.path.exists(f2):
        ungoverned_files.append(("Group_A", run, f2))

print("=" * 80)
print("FLOOD IBR DECOMPOSITION BY PMT APPRAISAL QUADRANTS")
print("=" * 80)

# ─── Load governed data ─────────────────────────────────────────────────
print(f"\nGoverned files found: {len(governed_files)}")
for g, r, f in governed_files:
    print(f"  {g}/{r}: {os.path.basename(f)}")

gov_frames = []
for grp, run, fpath in governed_files:
    df = pd.read_csv(fpath, encoding="utf-8-sig")
    df["group"] = grp
    df["run"] = run
    gov_frames.append(df)

gov = pd.concat(gov_frames, ignore_index=True)
print(f"\nGoverned total rows: {len(gov)}")
print(f"  Columns available: {list(gov.columns[:20])}...")

# ─── Load ungoverned data ───────────────────────────────────────────────
print(f"\nUngoverned files found: {len(ungoverned_files)}")
for g, r, f in ungoverned_files:
    print(f"  {g}/{r}: {os.path.basename(f)}")

ungov_frames = []
for grp, run, fpath in ungoverned_files:
    df = pd.read_csv(fpath, encoding="utf-8-sig")
    df["group"] = grp
    df["run"] = run
    ungov_frames.append(df)

if ungov_frames:
    ungov = pd.concat(ungov_frames, ignore_index=True)
    print(f"Ungoverned total rows: {len(ungov)}")
    print(f"  Columns: {list(ungov.columns)}")
else:
    ungov = pd.DataFrame()
    print("No ungoverned data found.")

# ─── Skill name normalization ───────────────────────────────────────────
SKILL_MAP = {
    "do_nothing": "do_nothing",
    "do nothing": "do_nothing",
    "purchase_insurance": "insurance",
    "buy_insurance": "insurance",
    "buy insurance": "insurance",
    "insurance": "insurance",
    "only flood insurance": "insurance",
    "elevate_home": "elevation",
    "elevate_house": "elevation",
    "elevate home": "elevation",
    "elevation": "elevation",
    "only house elevation": "elevation",
    "both flood insurance and house elevation": "insurance+elevation",
    "relocate": "relocate",
    "relocation": "relocate",
    "already relocated": "relocate",
}

def normalize_skill(s):
    if pd.isna(s):
        return "unknown"
    s = str(s).strip().lower()
    return SKILL_MAP.get(s, s)

gov["proposed_norm"] = gov["proposed_skill"].apply(normalize_skill)
gov["final_norm"] = gov["final_skill"].apply(normalize_skill)

# For ungoverned: map decision column
if not ungov.empty:
    ungov["decision_norm"] = ungov["decision"].apply(normalize_skill)

# ─── Classify TP/CP for ungoverned (free-text → L/M/H) ─────────────────
# Group A doesn't have TP_LABEL/CP_LABEL — we need to infer from text
# or skip ungoverned from quadrant analysis

has_ungov_labels = False
if not ungov.empty and "construct_TP_LABEL" in ungov.columns:
    has_ungov_labels = True
elif not ungov.empty:
    # Attempt simple heuristic classification from free-text appraisals
    def classify_appraisal_text(text):
        """Heuristic: classify free-text appraisal to L/M/H"""
        if pd.isna(text):
            return "M"  # default
        text = str(text).lower()
        high_kw = ["high", "significant", "severe", "extreme", "major", "very concerned",
                    "imminent", "critical", "urgent", "devastating", "substantial"]
        low_kw = ["low", "minimal", "unlikely", "negligible", "no threat", "little",
                   "not concerned", "limited", "no significant", "hampered", "lack of confidence",
                   "skeptic"]

        h_score = sum(1 for kw in high_kw if kw in text)
        l_score = sum(1 for kw in low_kw if kw in text)

        if h_score > l_score:
            return "H"
        elif l_score > h_score:
            return "L"
        else:
            return "M"

    ungov["construct_TP_LABEL"] = ungov["threat_appraisal"].apply(classify_appraisal_text)
    ungov["construct_CP_LABEL"] = ungov["coping_appraisal"].apply(classify_appraisal_text)
    has_ungov_labels = True
    print("\n[INFO] Ungoverned TP/CP labels inferred from free-text using keyword heuristic.")
    print(f"  TP distribution: {ungov['construct_TP_LABEL'].value_counts().to_dict()}")
    print(f"  CP distribution: {ungov['construct_CP_LABEL'].value_counts().to_dict()}")

# ─── ANALYSIS 1: TP×CP Cross-Tab (Governed) ────────────────────────────
print("\n" + "=" * 80)
print("ANALYSIS 1: TP × CP CROSS-TAB — GOVERNED (Groups B+C pooled)")
print("=" * 80)

tp_order = ["L", "M", "H"]
cp_order = ["L", "M", "H"]
actions = ["do_nothing", "insurance", "elevation", "relocate", "insurance+elevation"]

# Clean labels
gov["tp"] = gov["construct_TP_LABEL"].str.strip().str.upper()
gov["cp"] = gov["construct_CP_LABEL"].str.strip().str.upper()

# Filter to valid labels
gov_valid = gov[gov["tp"].isin(tp_order) & gov["cp"].isin(tp_order)].copy()
print(f"\nValid governed rows (TP/CP in L,M,H): {len(gov_valid)} / {len(gov)}")

# Cross-tab counts
print("\n--- Cell Counts ---")
ct = pd.crosstab(gov_valid["tp"], gov_valid["cp"], margins=True)
ct = ct.reindex(index=tp_order + ["All"], columns=cp_order + ["All"], fill_value=0)
print(ct.to_string())

# Action distribution per cell
print("\n--- Action Distribution per TP×CP Cell (% of cell) ---")
print(f"{'TP':>3} {'CP':>3} {'N':>6} {'do_noth%':>9} {'insur%':>9} {'elev%':>9} {'reloc%':>9} {'rej_rate%':>10}")
print("-" * 70)

for tp in tp_order:
    for cp in cp_order:
        cell = gov_valid[(gov_valid["tp"] == tp) & (gov_valid["cp"] == cp)]
        n = len(cell)
        if n == 0:
            print(f"{tp:>3} {cp:>3} {n:>6}     ---       ---       ---       ---        ---")
            continue

        pcts = {}
        for a in actions:
            pcts[a] = 100 * (cell["proposed_norm"] == a).sum() / n

        rej = 100 * (cell["status"].str.upper() == "REJECTED").sum() / n

        print(f"{tp:>3} {cp:>3} {n:>6} {pcts['do_nothing']:>8.1f}% {pcts['insurance']:>8.1f}% {pcts['elevation']:>8.1f}% {pcts['relocate']:>8.1f}% {rej:>9.1f}%")

# ─── ANALYSIS 1b: TP×CP Cross-Tab (Ungoverned) ─────────────────────────
if has_ungov_labels and not ungov.empty:
    print("\n" + "=" * 80)
    print("ANALYSIS 1b: TP × CP CROSS-TAB — UNGOVERNED (Group A)")
    print("=" * 80)

    ungov["tp"] = ungov["construct_TP_LABEL"].str.strip().str.upper()
    ungov["cp"] = ungov["construct_CP_LABEL"].str.strip().str.upper()
    ungov_valid = ungov[ungov["tp"].isin(tp_order) & ungov["cp"].isin(tp_order)].copy()
    print(f"\nValid ungoverned rows: {len(ungov_valid)} / {len(ungov)}")

    ct_u = pd.crosstab(ungov_valid["tp"], ungov_valid["cp"], margins=True)
    ct_u = ct_u.reindex(index=tp_order + ["All"], columns=cp_order + ["All"], fill_value=0)
    print("\n--- Cell Counts ---")
    print(ct_u.to_string())

    print(f"\n{'TP':>3} {'CP':>3} {'N':>6} {'do_noth%':>9} {'insur%':>9} {'elev%':>9} {'reloc%':>9}")
    print("-" * 58)

    for tp in tp_order:
        for cp in cp_order:
            cell = ungov_valid[(ungov_valid["tp"] == tp) & (ungov_valid["cp"] == cp)]
            n = len(cell)
            if n == 0:
                print(f"{tp:>3} {cp:>3} {n:>6}     ---       ---       ---       ---")
                continue
            pcts = {}
            for a in actions:
                pcts[a] = 100 * (cell["decision_norm"] == a).sum() / n
            print(f"{tp:>3} {cp:>3} {n:>6} {pcts['do_nothing']:>8.1f}% {pcts['insurance']:>8.1f}% {pcts['elevation']:>8.1f}% {pcts['relocate']:>8.1f}%")

# ─── ANALYSIS 2: PMT-Inconsistent Cells ────────────────────────────────
print("\n" + "=" * 80)
print("ANALYSIS 2: PMT-INCONSISTENT BEHAVIOR")
print("=" * 80)

# High TP + High CP → should protect; what % do_nothing?
hh_gov = gov_valid[(gov_valid["tp"] == "H") & (gov_valid["cp"] == "H")]
hh_dn_gov = (hh_gov["proposed_norm"] == "do_nothing").sum()
print(f"\n[Governed] High TP + High CP: {len(hh_gov)} decisions")
print(f"  do_nothing: {hh_dn_gov} ({100*hh_dn_gov/max(len(hh_gov),1):.1f}%) — PMT-INCONSISTENT (should protect)")
for a in actions:
    c = (hh_gov["proposed_norm"] == a).sum()
    print(f"    {a}: {c} ({100*c/max(len(hh_gov),1):.1f}%)")

# High TP + Medium CP
hm_gov = gov_valid[(gov_valid["tp"] == "H") & (gov_valid["cp"] == "M")]
hm_dn_gov = (hm_gov["proposed_norm"] == "do_nothing").sum()
print(f"\n[Governed] High TP + Medium CP: {len(hm_gov)} decisions")
print(f"  do_nothing: {hm_dn_gov} ({100*hm_dn_gov/max(len(hm_gov),1):.1f}%)")

# Low TP → should do_nothing; what % choose costly action?
low_tp_gov = gov_valid[gov_valid["tp"] == "L"]
costly_gov = low_tp_gov["proposed_norm"].isin(["elevation", "relocate"]).sum()
print(f"\n[Governed] Low TP (any CP): {len(low_tp_gov)} decisions")
print(f"  Costly action (elevate/relocate): {costly_gov} ({100*costly_gov/max(len(low_tp_gov),1):.1f}%) — PMT-INCONSISTENT (low threat)")
for a in actions:
    c = (low_tp_gov["proposed_norm"] == a).sum()
    print(f"    {a}: {c} ({100*c/max(len(low_tp_gov),1):.1f}%)")

if has_ungov_labels and not ungov.empty:
    hh_ung = ungov_valid[(ungov_valid["tp"] == "H") & (ungov_valid["cp"] == "H")]
    hh_dn_ung = (hh_ung["decision_norm"] == "do_nothing").sum()
    print(f"\n[Ungoverned] High TP + High CP: {len(hh_ung)} decisions")
    print(f"  do_nothing: {hh_dn_ung} ({100*hh_dn_ung/max(len(hh_ung),1):.1f}%)")
    for a in actions:
        c = (hh_ung["decision_norm"] == a).sum()
        print(f"    {a}: {c} ({100*c/max(len(hh_ung),1):.1f}%)")

    low_tp_ung = ungov_valid[ungov_valid["tp"] == "L"]
    costly_ung = low_tp_ung["decision_norm"].isin(["elevation", "relocate"]).sum()
    print(f"\n[Ungoverned] Low TP (any CP): {len(low_tp_ung)} decisions")
    print(f"  Costly action (elevate/relocate): {costly_ung} ({100*costly_ung/max(len(low_tp_ung),1):.1f}%)")
    for a in actions:
        c = (low_tp_ung["decision_norm"] == a).sum()
        print(f"    {a}: {c} ({100*c/max(len(low_tp_ung),1):.1f}%)")

# ─── ANALYSIS 3: Reasoning Traces ──────────────────────────────────────
print("\n" + "=" * 80)
print("ANALYSIS 3: NON-COMPLIANCE REASONING TRACES (Governed)")
print("=" * 80)

# High TP + High CP choosing do_nothing
hh_dn_traces = gov_valid[
    (gov_valid["tp"] == "H") & (gov_valid["cp"] == "H") &
    (gov_valid["proposed_norm"] == "do_nothing")
]
print(f"\n--- High TP + High CP → do_nothing ({len(hh_dn_traces)} cases) ---")
sample_n = min(5, len(hh_dn_traces))
if sample_n > 0:
    sample = hh_dn_traces.sample(n=sample_n, random_state=42) if len(hh_dn_traces) > sample_n else hh_dn_traces
    for i, (_, row) in enumerate(sample.iterrows()):
        print(f"\n  Trace {i+1} [{row.get('group','?')}/{row.get('run','?')}, Agent={row.get('agent_id','?')}, Year={row.get('year','?')}]")
        reasoning = str(row.get("reason_reasoning", ""))[:300]
        tp_reason = str(row.get("reason_tp_reason", ""))[:200]
        cp_reason = str(row.get("reason_cp_reason", ""))[:200]
        print(f"    TP reason: {tp_reason}")
        print(f"    CP reason: {cp_reason}")
        print(f"    Reasoning: {reasoning}")
        print(f"    Status: {row.get('status', '?')}, Final: {row.get('final_norm', '?')}")
else:
    print("  [No cases found — agents in H/H mostly choose protective action]")

# Low TP choosing costly protection
lt_costly = gov_valid[
    (gov_valid["tp"] == "L") &
    (gov_valid["proposed_norm"].isin(["elevation", "relocate"]))
]
print(f"\n--- Low TP → costly action (elevate/relocate) ({len(lt_costly)} cases) ---")
sample_n = min(5, len(lt_costly))
if sample_n > 0:
    sample = lt_costly.sample(n=sample_n, random_state=42) if len(lt_costly) > sample_n else lt_costly
    for i, (_, row) in enumerate(sample.iterrows()):
        print(f"\n  Trace {i+1} [{row.get('group','?')}/{row.get('run','?')}, Agent={row.get('agent_id','?')}, Year={row.get('year','?')}]")
        reasoning = str(row.get("reason_reasoning", ""))[:300]
        tp_reason = str(row.get("reason_tp_reason", ""))[:200]
        cp_reason = str(row.get("reason_cp_reason", ""))[:200]
        print(f"    TP reason: {tp_reason}")
        print(f"    CP reason: {cp_reason}")
        print(f"    Reasoning: {reasoning}")
        print(f"    Status: {row.get('status', '?')}, Final: {row.get('final_norm', '?')}")
        if pd.notna(row.get("failed_rules", "")) and str(row.get("failed_rules", "")).strip():
            print(f"    Failed rules: {row['failed_rules']}")
else:
    print("  [No cases found]")

# ─── ANALYSIS 4: Full Action Distribution Heatmap Data ─────────────────
print("\n" + "=" * 80)
print("ANALYSIS 4: FULL 3×3 ACTION DISTRIBUTION (for heatmap)")
print("=" * 80)

print("\n--- GOVERNED: Proposed Action Distribution ---")
print(f"{'':>8}", end="")
for cp in cp_order:
    print(f"  CP={cp:>15}", end="")
print()

for tp in tp_order:
    print(f"TP={tp}", end="")
    for cp in cp_order:
        cell = gov_valid[(gov_valid["tp"] == tp) & (gov_valid["cp"] == cp)]
        n = len(cell)
        if n == 0:
            print(f"  {'(n=0)':>15}", end="")
        else:
            parts = []
            for a in actions:
                pct = 100 * (cell["proposed_norm"] == a).sum() / n
                if pct > 0:
                    abbr = {"do_nothing": "DN", "insurance": "Ins", "elevation": "Elv", "relocate": "Rel", "insurance+elevation": "I+E"}[a]
                    parts.append(f"{abbr}:{pct:.0f}")
            s = " ".join(parts)
            print(f"  {f'(n={n}) {s}':>15}", end="")
    print()

print("\n--- GOVERNED: Final (post-governance) Action Distribution ---")
for tp in tp_order:
    print(f"TP={tp}", end="")
    for cp in cp_order:
        cell = gov_valid[(gov_valid["tp"] == tp) & (gov_valid["cp"] == cp)]
        n = len(cell)
        if n == 0:
            print(f"  {'(n=0)':>15}", end="")
        else:
            parts = []
            for a in actions:
                pct = 100 * (cell["final_norm"] == a).sum() / n
                if pct > 0:
                    abbr = {"do_nothing": "DN", "insurance": "Ins", "elevation": "Elv", "relocate": "Rel", "insurance+elevation": "I+E"}[a]
                    parts.append(f"{abbr}:{pct:.0f}")
            s = " ".join(parts)
            print(f"  {f'(n={n}) {s}':>15}", end="")
    print()

if has_ungov_labels and not ungov.empty:
    print("\n--- UNGOVERNED: Action Distribution ---")
    for tp in tp_order:
        print(f"TP={tp}", end="")
        for cp in cp_order:
            cell = ungov_valid[(ungov_valid["tp"] == tp) & (ungov_valid["cp"] == cp)]
            n = len(cell)
            if n == 0:
                print(f"  {'(n=0)':>15}", end="")
            else:
                parts = []
                for a in actions:
                    pct = 100 * (cell["decision_norm"] == a).sum() / n
                    if pct > 0:
                        abbr = {"do_nothing": "DN", "insurance": "Ins", "elevation": "Elv", "relocate": "Rel", "insurance+elevation": "I+E"}[a]
                        parts.append(f"{abbr}:{pct:.0f}")
                s = " ".join(parts)
                print(f"  {f'(n={n}) {s}':>15}", end="")
        print()

# ─── ANALYSIS 5: Governance Rule Frequency ──────────────────────────────
print("\n" + "=" * 80)
print("ANALYSIS 5: GOVERNANCE RULE FIRING FREQUENCY")
print("=" * 80)

rejected = gov_valid[gov_valid["status"].str.upper() == "REJECTED"]
print(f"\nTotal rejections: {len(rejected)} / {len(gov_valid)} ({100*len(rejected)/len(gov_valid):.1f}%)")

# Parse failed_rules
all_rules = []
for fr in rejected["failed_rules"].dropna():
    fr_str = str(fr).strip()
    if fr_str:
        # Could be comma-separated or semicolon-separated
        for rule in re.split(r'[,;|]', fr_str):
            rule = rule.strip()
            if rule:
                all_rules.append(rule)

rule_counts = Counter(all_rules)
print(f"\nRule firing frequency (from {len(all_rules)} total rule firings):")
for rule, count in rule_counts.most_common(20):
    print(f"  {count:>5} ({100*count/len(all_rules):>5.1f}%)  {rule}")

# Also show which rules triggered (not just failed) from rules_triggered column
print("\n--- Rules Triggered (all decisions, not just rejections) ---")
all_triggered = []
for rt in gov_valid["rules_triggered"].dropna():
    rt_str = str(rt).strip()
    if rt_str:
        for rule in re.split(r'[,;|]', rt_str):
            rule = rule.strip()
            if rule:
                all_triggered.append(rule)

if all_triggered:
    trig_counts = Counter(all_triggered)
    print(f"Total rule triggers: {len(all_triggered)}")
    for rule, count in trig_counts.most_common(20):
        print(f"  {count:>5} ({100*count/len(all_triggered):>5.1f}%)  {rule}")
else:
    print("  [No rules_triggered data found]")

# ─── Rejection by TP×CP ─────────────────────────────────────────────────
print("\n--- Rejection Rate by TP × CP Cell ---")
print(f"{'TP':>3} {'CP':>3} {'Total':>6} {'Rejected':>9} {'Rate%':>7}")
print("-" * 35)
for tp in tp_order:
    for cp in cp_order:
        cell = gov_valid[(gov_valid["tp"] == tp) & (gov_valid["cp"] == cp)]
        n = len(cell)
        rej = (cell["status"].str.upper() == "REJECTED").sum()
        rate = 100 * rej / max(n, 1)
        print(f"{tp:>3} {cp:>3} {n:>6} {rej:>9} {rate:>6.1f}%")

# ─── What gets rejected in each cell? ───────────────────────────────────
print("\n--- What Gets Rejected per Cell ---")
for tp in tp_order:
    for cp in cp_order:
        cell_rej = gov_valid[(gov_valid["tp"] == tp) & (gov_valid["cp"] == cp) &
                            (gov_valid["status"].str.upper() == "REJECTED")]
        if len(cell_rej) == 0:
            continue
        proposed = cell_rej["proposed_norm"].value_counts()
        final = cell_rej["final_norm"].value_counts()
        print(f"\n  TP={tp}, CP={cp}: {len(cell_rej)} rejections")
        print(f"    Proposed: {proposed.to_dict()}")
        print(f"    Final:    {final.to_dict()}")

# ─── Summary stats ──────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"\nGoverned: {len(gov_valid)} valid decisions across {len(governed_files)} files")
print(f"  Groups: {gov_valid['group'].value_counts().to_dict()}")
print(f"  TP dist: {gov_valid['tp'].value_counts().to_dict()}")
print(f"  CP dist: {gov_valid['cp'].value_counts().to_dict()}")
print(f"  Proposed actions: {gov_valid['proposed_norm'].value_counts().to_dict()}")
print(f"  Final actions: {gov_valid['final_norm'].value_counts().to_dict()}")
print(f"  Overall rejection rate: {100*(gov_valid['status'].str.upper()=='REJECTED').sum()/len(gov_valid):.1f}%")

if has_ungov_labels and not ungov.empty:
    print(f"\nUngoverned: {len(ungov_valid)} valid decisions across {len(ungoverned_files)} files")
    print(f"  TP dist: {ungov_valid['tp'].value_counts().to_dict()}")
    print(f"  CP dist: {ungov_valid['cp'].value_counts().to_dict()}")
    print(f"  Actions: {ungov_valid['decision_norm'].value_counts().to_dict()}")

# ─── Governed vs Ungoverned comparison by key cells ─────────────────────
if has_ungov_labels and not ungov.empty:
    print("\n" + "=" * 80)
    print("GOVERNED vs UNGOVERNED COMPARISON (key cells)")
    print("=" * 80)

    for tp, cp, label in [("H", "H", "High-High (should protect)"),
                           ("H", "M", "High-Med"),
                           ("M", "M", "Med-Med"),
                           ("L", "L", "Low-Low (should do_nothing)"),
                           ("L", "M", "Low-Med"),
                           ("L", "H", "Low-High")]:
        g_cell = gov_valid[(gov_valid["tp"] == tp) & (gov_valid["cp"] == cp)]
        u_cell = ungov_valid[(ungov_valid["tp"] == tp) & (ungov_valid["cp"] == cp)]
        gn = len(g_cell)
        un = len(u_cell)

        print(f"\n  {label} (TP={tp}, CP={cp}):")
        print(f"    {'':>12} {'Gov(n={})'.format(gn):>15} {'Ungov(n={})'.format(un):>15}")
        for a in actions:
            g_pct = 100 * (g_cell["proposed_norm"] == a).sum() / max(gn, 1)
            u_pct = 100 * (u_cell["decision_norm"] == a).sum() / max(un, 1)
            print(f"    {a:>12} {g_pct:>14.1f}% {u_pct:>14.1f}%")
        if gn > 0:
            rej = 100 * (g_cell["status"].str.upper() == "REJECTED").sum() / gn
            print(f"    {'rej_rate':>12} {rej:>14.1f}%")

print("\n[DONE]")
