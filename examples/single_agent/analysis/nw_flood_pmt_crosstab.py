"""
Flood PMT Cross-Tab Analysis — Corrected (5-level: VL, L, M, H, VH)
=====================================================================
Pools Group B (window memory) + Group C (HumanCentric memory) as "governed",
Group A as "ungoverned". Group A has free-text appraisals (no labels),
so we extract labels from the text or mark as UNKNOWN.

IMPORTANT: Uses ALL 5 PMT levels (VL, L, M, H, VH).
"""
import pandas as pd
import numpy as np
from pathlib import Path
from collections import Counter

# ── 0. PATHS & CONSTANTS ─────────────────────────────────────────────
BASE = Path(r"C:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/single_agent/results/JOH_FINAL/gemma3_4b")

gov_b_files = [BASE / f"Group_B/Run_{i}/household_governance_audit.csv" for i in range(1, 4)]
gov_c_files = [BASE / f"Group_C/Run_{i}/household_governance_audit.csv" for i in range(1, 4)]
ungov_files = [BASE / f"Group_A/Run_{i}/simulation_log.csv" for i in range(1, 4)]

LABELS_5 = ["VL", "L", "M", "H", "VH"]
SKILLS = ["do_nothing", "insurance", "elevate", "relocate"]

# Normalize all raw skill names to canonical 4
SKILL_MAP = {
    "do_nothing": "do_nothing",
    "purchase_insurance": "insurance",
    "buy_insurance": "insurance",
    "elevate_home": "elevate",
    "elevate_house": "elevate",
    "relocate": "relocate",
}

# Mapping from ungoverned decision text to canonical skill names
DECISION_MAP = {
    "do nothing": "do_nothing",
    "buy flood insurance": "insurance",
    "only flood insurance": "insurance",
    "only house elevation": "elevate",
    "house elevation": "elevate",
    "insurance and elevation": "elevate",
    "relocate": "relocate",
    "relocation": "relocate",
}


def normalize_skill(raw):
    """Map any raw skill string to canonical name."""
    if not isinstance(raw, str):
        return "do_nothing"
    r = raw.strip().lower()
    return SKILL_MAP.get(r, r)  # pass-through if not in map


def classify_appraisal_text(text):
    """Extract VL/L/M/H/VH from free-text appraisal."""
    if not isinstance(text, str) or text.strip() == "":
        return "UNKNOWN"
    t = text.lower()
    # Order matters: check "very high"/"very low" before "high"/"low"
    if any(k in t for k in ["very high", "extreme", "severe", "overwhelming"]):
        return "VH"
    if any(k in t for k in ["very low", "minimal", "negligible", "no real", "no significant"]):
        return "VL"
    if any(k in t for k in ["high", "significant", "serious", "strong", "substantial", "considerable"]):
        return "H"
    if any(k in t for k in ["low", "limited", "slight", "minor", "little"]):
        return "L"
    if any(k in t for k in ["moderate", "medium", "modest", "some", "reasonable", "uncertain",
                             "lingering", "persistent", "cautious"]):
        return "M"
    return "UNKNOWN"


def map_ungov_decision(text):
    """Map ungoverned decision text to canonical skill name."""
    if not isinstance(text, str):
        return "do_nothing"
    t = text.strip().lower()
    for key, val in DECISION_MAP.items():
        if key in t:
            return val
    return "do_nothing"


# ── 1. LOAD DATA ─────────────────────────────────────────────────────
def load_governed(files, group_label):
    frames = []
    for f in files:
        df = pd.read_csv(f, encoding="utf-8")
        df["group"] = group_label
        df["run"] = f.parent.name
        # TP/CP from construct columns
        df["TP"] = df["construct_TP_LABEL"].str.strip().str.upper()
        df["CP"] = df["construct_CP_LABEL"].str.strip().str.upper()
        # Fallback to reason columns
        mask_tp = ~df["TP"].isin(LABELS_5)
        mask_cp = ~df["CP"].isin(LABELS_5)
        if "reason_tp_label" in df.columns:
            df.loc[mask_tp, "TP"] = df.loc[mask_tp, "reason_tp_label"].str.strip().str.upper()
        if "reason_cp_label" in df.columns:
            df.loc[mask_cp, "CP"] = df.loc[mask_cp, "reason_cp_label"].str.strip().str.upper()
        # Normalize skills
        df["skill"] = df["final_skill"].apply(normalize_skill)
        df["proposed"] = df["proposed_skill"].apply(normalize_skill)
        df["is_rejected"] = (df["status"].str.strip().str.upper() == "REJECTED")
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def load_ungoverned(files):
    frames = []
    for f in files:
        df = pd.read_csv(f, encoding="utf-8")
        df["group"] = "A"
        df["run"] = f.parent.name
        df["TP"] = df["threat_appraisal"].apply(classify_appraisal_text)
        df["CP"] = df["coping_appraisal"].apply(classify_appraisal_text)
        df["skill"] = df["decision"].apply(map_ungov_decision)
        df["proposed"] = df["skill"]  # no governance, proposed=final
        df["is_rejected"] = False
        df["status"] = "APPROVED"
        df["failed_rules"] = ""
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


gov_b = load_governed(gov_b_files, "B")
gov_c = load_governed(gov_c_files, "C")
ungov = load_ungoverned(ungov_files)
gov_all = pd.concat([gov_b, gov_c], ignore_index=True)

print(f"Governed B rows: {len(gov_b)}")
print(f"Governed C rows: {len(gov_c)}")
print(f"Governed total:  {len(gov_all)}")
print(f"Ungoverned A rows: {len(ungov)}")

# Verify skill normalization
for lbl, dfc in [("Gov B", gov_b), ("Gov C", gov_c), ("Ungov A", ungov)]:
    print(f"  {lbl} skill values: {dict(dfc['skill'].value_counts())}")

# Check label coverage
for label, df_check in [("Gov", gov_all), ("Ungov", ungov)]:
    tp_valid = df_check["TP"].isin(LABELS_5).sum()
    cp_valid = df_check["CP"].isin(LABELS_5).sum()
    print(f"  {label}: TP valid={tp_valid}/{len(df_check)}, CP valid={cp_valid}/{len(df_check)}")
    print(f"    TP dist: {dict(df_check['TP'].value_counts())}")
    print(f"    CP dist: {dict(df_check['CP'].value_counts())}")


# ── 2. ANALYSIS FUNCTIONS ────────────────────────────────────────────
def skill_pct(cell):
    """Return dict of skill percentages for a cell."""
    sk = cell["skill"].value_counts(normalize=True) * 100
    return {s: sk.get(s, 0.0) for s in SKILLS}


def crosstab_5x5(df, label, labels=LABELS_5):
    """Print 5x5 TP x CP cross-tab with counts, action %, rejection rate."""
    mask = df["TP"].isin(labels) & df["CP"].isin(labels)
    d = df[mask].copy()
    n_dropped = len(df) - len(d)
    if n_dropped:
        print(f"  [{label}] Dropped {n_dropped} rows with invalid TP/CP labels")

    print(f"\n{'='*90}")
    print(f"  {label}: 5x5 TP x CP Cross-Tab  (N={len(d)})")
    print(f"{'='*90}")

    ct = pd.crosstab(d["TP"], d["CP"], margins=True)
    ct = ct.reindex(index=labels + ["All"], columns=labels + ["All"], fill_value=0)
    print(f"\n--- COUNTS ---")
    print(ct.to_string())

    print(f"\n--- ACTION DISTRIBUTION (%) & REJECTION RATE ---")
    header = f"{'TP':>3} x {'CP':<3} | {'N':>4} | {'do_noth':>7} {'insur':>7} {'elevat':>7} {'reloc':>7} | {'Rej%':>6}"
    print(header)
    print("-" * len(header))

    for tp in labels:
        for cp in labels:
            cell = d[(d["TP"] == tp) & (d["CP"] == cp)]
            n = len(cell)
            if n == 0:
                continue
            sp = skill_pct(cell)
            rej = cell["is_rejected"].mean() * 100
            print(f"  {tp:>2} x {cp:<2}  | {n:>4} | {sp['do_nothing']:>6.1f}% {sp['insurance']:>6.1f}% {sp['elevate']:>6.1f}% {sp['relocate']:>6.1f}% | {rej:>5.1f}%")

    # Marginal by TP
    print(f"\n--- MARGINAL BY TP ---")
    for tp in labels:
        cell = d[d["TP"] == tp]
        n = len(cell)
        if n == 0:
            continue
        sp = skill_pct(cell)
        rej = cell["is_rejected"].mean() * 100
        print(f"  TP={tp:>2} | {n:>4} | {sp['do_nothing']:>6.1f}% {sp['insurance']:>6.1f}% {sp['elevate']:>6.1f}% {sp['relocate']:>6.1f}% | {rej:>5.1f}%")

    # Marginal by CP
    print(f"\n--- MARGINAL BY CP ---")
    for cp in labels:
        cell = d[d["CP"] == cp]
        n = len(cell)
        if n == 0:
            continue
        sp = skill_pct(cell)
        rej = cell["is_rejected"].mean() * 100
        print(f"  CP={cp:>2} | {n:>4} | {sp['do_nothing']:>6.1f}% {sp['insurance']:>6.1f}% {sp['elevate']:>6.1f}% {sp['relocate']:>6.1f}% | {rej:>5.1f}%")

    # Overall
    sp = skill_pct(d)
    rej = d["is_rejected"].mean() * 100
    print(f"  TOTAL  | {len(d):>4} | {sp['do_nothing']:>6.1f}% {sp['insurance']:>6.1f}% {sp['elevate']:>6.1f}% {sp['relocate']:>6.1f}% | {rej:>5.1f}%")

    return d


def crosstab_3x3(df, label):
    """Condensed 3x3: VL+L -> Low, M -> Med, H+VH -> High."""
    d = df.copy()
    collapse = {"VL": "Low", "L": "Low", "M": "Med", "H": "High", "VH": "High"}
    d["TP3"] = d["TP"].map(collapse)
    d["CP3"] = d["CP"].map(collapse)
    mask = d["TP3"].notna() & d["CP3"].notna()
    d = d[mask]

    labels3 = ["Low", "Med", "High"]
    print(f"\n{'='*90}")
    print(f"  {label}: Condensed 3x3 TP x CP  (N={len(d)})")
    print(f"{'='*90}")

    ct = pd.crosstab(d["TP3"], d["CP3"], margins=True)
    ct = ct.reindex(index=labels3 + ["All"], columns=labels3 + ["All"], fill_value=0)
    print(f"\n--- COUNTS ---")
    print(ct.to_string())

    print(f"\n--- ACTION DISTRIBUTION (%) & REJECTION RATE ---")
    header = f"{'TP':>5} x {'CP':<5} | {'N':>4} | {'do_noth':>7} {'insur':>7} {'elevat':>7} {'reloc':>7} | {'Rej%':>6}"
    print(header)
    print("-" * len(header))

    for tp in labels3:
        for cp in labels3:
            cell = d[(d["TP3"] == tp) & (d["CP3"] == cp)]
            n = len(cell)
            if n == 0:
                continue
            sp = skill_pct(cell)
            rej = cell["is_rejected"].mean() * 100
            print(f"  {tp:>4} x {cp:<4}  | {n:>4} | {sp['do_nothing']:>6.1f}% {sp['insurance']:>6.1f}% {sp['elevate']:>6.1f}% {sp['relocate']:>6.1f}% | {rej:>5.1f}%")


def pmt_inconsistency(df, label):
    """PMT-inconsistent rates by quadrant."""
    mask = df["TP"].isin(LABELS_5) & df["CP"].isin(LABELS_5)
    d = df[mask].copy()

    print(f"\n{'='*90}")
    print(f"  {label}: PMT Inconsistency Analysis  (N={len(d)})")
    print(f"{'='*90}")

    costly = ["insurance", "elevate", "relocate"]

    # High-threat (H/VH) doing nothing
    ht = d[d["TP"].isin(["H", "VH"])]
    if len(ht) > 0:
        cnt = (ht["skill"] == "do_nothing").sum()
        print(f"  High-TP (H/VH) doing nothing:       {cnt:>4}/{len(ht):>4} = {cnt/len(ht)*100:>5.1f}%")

    # Low-threat (VL/L) doing costly action
    lt = d[d["TP"].isin(["VL", "L"])]
    if len(lt) > 0:
        cnt = lt["skill"].isin(costly).sum()
        print(f"  Low-TP  (VL/L) doing costly action:  {cnt:>4}/{len(lt):>4} = {cnt/len(lt)*100:>5.1f}%")

    # High-CP doing nothing
    hc = d[d["CP"].isin(["H", "VH"])]
    if len(hc) > 0:
        cnt = (hc["skill"] == "do_nothing").sum()
        print(f"  High-CP (H/VH) doing nothing:       {cnt:>4}/{len(hc):>4} = {cnt/len(hc)*100:>5.1f}%")

    # Low-CP doing costly action
    lc = d[d["CP"].isin(["VL", "L"])]
    if len(lc) > 0:
        cnt = lc["skill"].isin(costly).sum()
        print(f"  Low-CP  (VL/L) doing costly action:  {cnt:>4}/{len(lc):>4} = {cnt/len(lc)*100:>5.1f}%")

    # Combined: High-TP + High-CP but do_nothing
    hh = d[d["TP"].isin(["H", "VH"]) & d["CP"].isin(["H", "VH"])]
    if len(hh) > 0:
        cnt = (hh["skill"] == "do_nothing").sum()
        print(f"  High-TP & High-CP doing nothing:    {cnt:>4}/{len(hh):>4} = {cnt/len(hh)*100:>5.1f}%")

    # Combined: Low-TP + Low-CP but costly
    ll = d[d["TP"].isin(["VL", "L"]) & d["CP"].isin(["VL", "L"])]
    if len(ll) > 0:
        cnt = ll["skill"].isin(costly).sum()
        print(f"  Low-TP  & Low-CP  doing costly:     {cnt:>4}/{len(ll):>4} = {cnt/len(ll)*100:>5.1f}%")


def governance_rules(df, label):
    """Governance rule firing frequency."""
    rej = df[df["is_rejected"]].copy()
    print(f"\n{'='*90}")
    print(f"  {label}: Governance Rule Firing  (Total rejections: {len(rej)}/{len(df)} = {len(rej)/len(df)*100:.1f}%)")
    print(f"{'='*90}")

    if len(rej) == 0:
        print("  No rejections.")
        return

    # What did rejected proposals want to do?
    print(f"\n  Rejected proposed actions:")
    for s in SKILLS:
        cnt = (rej["proposed"] == s).sum()
        if cnt:
            print(f"    {s}: {cnt}")

    # Parse failed_rules  (separator may be | or ;)
    all_rules = []
    for rules_str in rej["failed_rules"].dropna():
        if isinstance(rules_str, str) and rules_str.strip():
            for sep in ["|", ";"]:
                if sep in rules_str:
                    parts = rules_str.split(sep)
                    break
            else:
                parts = [rules_str]
            for r in parts:
                r = r.strip()
                if r:
                    all_rules.append(r)

    if all_rules:
        rule_counts = Counter(all_rules)
        print(f"\n  {'Rule':<55} {'Count':>6} {'%':>7}")
        print(f"  {'-'*68}")
        for rule, cnt in rule_counts.most_common():
            print(f"  {rule:<55} {cnt:>6} {cnt/len(rej)*100:>6.1f}%")
    else:
        print("  (No rule names parsed from failed_rules column)")


def compare_groups(df_b, df_c):
    """Compare Group B vs C TP/CP distributions."""
    print(f"\n{'='*90}")
    print(f"  GROUP B (Window Memory) vs GROUP C (HumanCentric Memory)")
    print(f"{'='*90}")

    for construct, col in [("Threat Perception (TP)", "TP"), ("Coping Perception (CP)", "CP")]:
        print(f"\n  --- {construct} ---")
        b_dist = df_b[df_b[col].isin(LABELS_5)][col].value_counts().reindex(LABELS_5, fill_value=0)
        c_dist = df_c[df_c[col].isin(LABELS_5)][col].value_counts().reindex(LABELS_5, fill_value=0)
        b_pct = b_dist / b_dist.sum() * 100
        c_pct = c_dist / c_dist.sum() * 100

        print(f"  {'Label':>5} | {'B count':>8} {'B %':>7} | {'C count':>8} {'C %':>7}")
        print(f"  {'-'*50}")
        for lbl in LABELS_5:
            print(f"  {lbl:>5} | {b_dist[lbl]:>8} {b_pct[lbl]:>6.1f}% | {c_dist[lbl]:>8} {c_pct[lbl]:>6.1f}%")
        print(f"  {'Total':>5} | {b_dist.sum():>8}         | {c_dist.sum():>8}")

    # Action distribution
    print(f"\n  --- Action Distribution ---")
    for grp_label, grp_df in [("B", df_b), ("C", df_c)]:
        sp = skill_pct(grp_df)
        rej_rate = grp_df["is_rejected"].mean() * 100
        parts = "  ".join(f"{s}={sp[s]:.1f}%" for s in SKILLS)
        print(f"  Group {grp_label} (N={len(grp_df)}): {parts} | Rej={rej_rate:.1f}%")

    # Rejection rate by group
    print(f"\n  --- Rejection Detail ---")
    for grp_label, grp_df in [("B", df_b), ("C", df_c)]:
        rej = grp_df[grp_df["is_rejected"]]
        print(f"  Group {grp_label}: {len(rej)} rejections out of {len(grp_df)}")
        if len(rej) > 0:
            print(f"    Rejected proposed: {dict(rej['proposed'].value_counts())}")


# ── 3. RUN ALL ANALYSES ──────────────────────────────────────────────
print("\n" + "#" * 90)
print("#  FLOOD PMT CROSS-TAB ANALYSIS (5-level: VL, L, M, H, VH)")
print("#  All skill names normalized: do_nothing, insurance, elevate, relocate")
print("#" * 90)

# 1. 5x5 cross-tabs
crosstab_5x5(gov_all, "GOVERNED (B+C)")
crosstab_5x5(ungov, "UNGOVERNED (A)")

# 2. Condensed 3x3
crosstab_3x3(gov_all, "GOVERNED (B+C)")
crosstab_3x3(ungov, "UNGOVERNED (A)")

# 3. PMT inconsistency
pmt_inconsistency(gov_all, "GOVERNED (B+C)")
pmt_inconsistency(ungov, "UNGOVERNED (A)")

# 4. Governance rules
governance_rules(gov_all, "GOVERNED (B+C)")

# 5. B vs C comparison
compare_groups(gov_b, gov_c)

print("\n" + "#" * 90)
print("#  ANALYSIS COMPLETE")
print("#" * 90)
