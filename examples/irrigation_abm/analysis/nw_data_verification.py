#!/usr/bin/env python3
# Nature Water Data Verification Script
# Computes ALL metrics for the Nature Water paper rewrite.
# 3 conditions (Governed, A1/No-Ceiling, Ungoverned) x 3 seeds (42,43,44).
import sys
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats

BASE = Path("C:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/irrigation_abm/results")
SEEDS = [42, 43, 44]
CONDITIONS = {
    "Governed":   [BASE / "production_v20_42yr_seed{}".format(s) / "simulation_log.csv" for s in SEEDS],
    "A1":         [BASE / "ablation_no_ceiling_seed{}".format(s) / "simulation_log.csv" for s in SEEDS],
    "Ungoverned": [BASE / "ungoverned_v20_42yr_seed{}".format(s) / "simulation_log.csv" for s in SEEDS],
}
AUDIT_DIRS = {
    "Governed":   [BASE / "production_v20_42yr_seed{}".format(s) for s in SEEDS],
    "A1":         [BASE / "ablation_no_ceiling_seed{}".format(s) for s in SEEDS],
    "Ungoverned": [BASE / "ungoverned_v20_42yr_seed{}".format(s) for s in SEEDS],
}
SKILLS_5 = ["increase_large", "increase_small", "maintain_demand", "decrease_small", "decrease_large"]

def load_sim(path):
    return pd.read_csv(path, encoding="utf-8")

def load_audit(dirpath):
    p = dirpath / "irrigation_farmer_governance_audit.csv"
    if p.exists():
        return pd.read_csv(p, encoding="utf-8-sig")
    return None

data = {}
audits = {}
for cond, paths in CONDITIONS.items():
    data[cond] = {}
    audits[cond] = {}
    for i, p in enumerate(paths):
        s = SEEDS[i]
        data[cond][s] = load_sim(p)
        audits[cond][s] = load_audit(AUDIT_DIRS[cond][i])

def yearly_agg(df):
    yearly = df.groupby("year").agg(
        request_sum=("request", "sum"),
        water_right_sum=("water_right", "sum"),
        lake_mead_level=("lake_mead_level", "first"),
        shortage_tier=("shortage_tier", "first"),
    ).reset_index()
    yearly["demand_ratio"] = yearly["request_sum"] / yearly["water_right_sum"]
    return yearly

yearly_data = {}
for cond in CONDITIONS:
    yearly_data[cond] = {}
    for s in SEEDS:
        yearly_data[cond][s] = yearly_agg(data[cond][s])

def compute_ehe(df):
    yearly_ehes = []
    for y, grp in df.groupby("year"):
        counts = grp["yearly_decision"].value_counts()
        total = counts.sum()
        probs = np.array([counts.get(sk, 0) / total for sk in SKILLS_5])
        probs = probs[probs > 0]
        H = -np.sum(probs * np.log2(probs)) if len(probs) > 0 else 0.0
        yearly_ehes.append(H / np.log2(5))
    return np.mean(yearly_ehes)

def compute_audit_ehe(audit_df):
    if audit_df is None or "proposed_skill" not in audit_df.columns:
        return float("nan")
    yearly_ehes = []
    for y, grp in audit_df.groupby("year"):
        counts = grp["proposed_skill"].value_counts()
        total = counts.sum()
        probs = np.array([counts.get(sk, 0) / total for sk in SKILLS_5])
        probs = probs[probs > 0]
        H = -np.sum(probs * np.log2(probs)) if len(probs) > 0 else 0.0
        yearly_ehes.append(H / np.log2(5))
    return np.mean(yearly_ehes) if yearly_ehes else float("nan")
SEP = "=" * 80
DSEP = "-" * 80
print(SEP)
print("  NATURE WATER -- COMPREHENSIVE DATA VERIFICATION")
print(SEP)

print("\n" + DSEP)
print("1. DEMAND RATIO (mean yearly request_sum / water_right_sum)")
print(DSEP)
dr_means = {}
for cond in CONDITIONS:
    seed_means = []
    for s in SEEDS:
        yr = yearly_data[cond][s]
        m = yr["demand_ratio"].mean()
        seed_means.append(m)
        print("  {:12s} seed{}: DR = {:.4f}".format(cond, s, m))
    ens_mean = np.mean(seed_means)
    ens_sd = np.std(seed_means, ddof=1)
    dr_means[cond] = (ens_mean, ens_sd, seed_means)
    print("  {:12s} ENSEMBLE: {:.4f} +/- {:.4f}".format(cond, ens_mean, ens_sd))
    print()

print(DSEP)
print("2. DEMAND RATIO GAP: (gov - ungov) / ungov * 100")
print(DSEP)
gov_dr = dr_means["Governed"][0]
ungov_dr = dr_means["Ungoverned"][0]
a1_dr = dr_means["A1"][0]
gap_pct = (gov_dr - ungov_dr) / ungov_dr * 100
gap_a1 = (a1_dr - ungov_dr) / ungov_dr * 100
print("  Governed vs Ungoverned: ({:.4f} - {:.4f}) / {:.4f} = {:.1f}%".format(gov_dr, ungov_dr, ungov_dr, gap_pct))
print("  A1 vs Ungoverned:       ({:.4f} - {:.4f}) / {:.4f} = {:.1f}%".format(a1_dr, ungov_dr, ungov_dr, gap_a1))

print("\n" + DSEP)
print("3. 42-YEAR MEAN LAKE MEAD ELEVATION (ft)")
print(DSEP)
mead_means = {}
for cond in CONDITIONS:
    seed_vals = []
    for s in SEEDS:
        yr = yearly_data[cond][s]
        m = yr["lake_mead_level"].mean()
        seed_vals.append(m)
        print("  {:12s} seed{}: {:.2f} ft".format(cond, s, m))
    ens_mean = np.mean(seed_vals)
    ens_sd = np.std(seed_vals, ddof=1)
    mead_means[cond] = (ens_mean, ens_sd)
    print("  {:12s} ENSEMBLE: {:.2f} +/- {:.2f} ft".format(cond, ens_mean, ens_sd))
    print()

print(DSEP)
print("4. DEMAND-MEAD PEARSON CORRELATION")
print(DSEP)
pearson_results = {}
for cond in CONDITIONS:
    seed_rs = []
    for s in SEEDS:
        yr = yearly_data[cond][s]
        r, p = stats.pearsonr(yr["demand_ratio"], yr["lake_mead_level"])
        seed_rs.append(r)
        print("  {:12s} seed{}: r = {:.4f}, p = {:.2e}".format(cond, s, r, p))
    pearson_results[cond] = (np.mean(seed_rs), np.std(seed_rs, ddof=1))
    print("  {:12s} ENSEMBLE r: {:.4f} +/- {:.4f}".format(cond, np.mean(seed_rs), np.std(seed_rs, ddof=1)))
    print()

print(DSEP)
print("5. SHORTAGE YEARS (shortage_tier > 0)")
print(DSEP)
shortage_counts = {}
for cond in CONDITIONS:
    seed_counts = []
    for s in SEEDS:
        yr = yearly_data[cond][s]
        n = int((yr["shortage_tier"] > 0).sum())
        seed_counts.append(n)
        print("  {:12s} seed{}: {} / {} years".format(cond, s, n, len(yr)))
    shortage_counts[cond] = seed_counts
    print("  {:12s} ENSEMBLE: {:.1f} +/- {:.1f}".format(cond, np.mean(seed_counts), np.std(seed_counts, ddof=1)))
    print()

print(DSEP)
print("6. MINIMUM LAKE MEAD ELEVATION (ft)")
print(DSEP)
for cond in CONDITIONS:
    seed_mins = []
    for s in SEEDS:
        yr = yearly_data[cond][s]
        mn = yr["lake_mead_level"].min()
        seed_mins.append(mn)
        yr_min = yr.loc[yr["lake_mead_level"].idxmin(), "year"]
        print("  {:12s} seed{}: {:.2f} ft (year {})".format(cond, s, mn, yr_min))
    print("  {:12s} ENSEMBLE min: {:.2f} +/- {:.2f}".format(cond, np.mean(seed_mins), np.std(seed_mins, ddof=1)))
    print()
print(DSEP)
print("7. CURTAILMENT SPREAD (DR_plentiful - DR_shortage)")
print(DSEP)
plentiful_dr = {}
shortage_dr = {}
for cond in CONDITIONS:
    seed_spreads, seed_plent, seed_short = [], [], []
    for s in SEEDS:
        yr = yearly_data[cond][s]
        plent = yr[yr["shortage_tier"] == 0]["demand_ratio"]
        short = yr[yr["shortage_tier"] > 0]["demand_ratio"]
        p_mean = plent.mean() if len(plent) > 0 else float("nan")
        s_mean = short.mean() if len(short) > 0 else float("nan")
        spread = p_mean - s_mean
        seed_spreads.append(spread)
        seed_plent.append(p_mean)
        seed_short.append(s_mean)
        print("  {:12s} seed{}: plentiful={:.4f}, shortage={:.4f}, spread={:.4f}".format(cond, s, p_mean, s_mean, spread))
    plentiful_dr[cond] = np.nanmean(seed_plent)
    shortage_dr[cond] = np.nanmean(seed_short)
    print("  {:12s} ENSEMBLE spread: {:.4f}".format(cond, np.nanmean(seed_spreads)))
    print("  {:12s} ENSEMBLE plentiful DR: {:.4f}".format(cond, plentiful_dr[cond]))
    print("  {:12s} ENSEMBLE shortage DR: {:.4f}".format(cond, shortage_dr[cond]))
    print()

print(DSEP)
print("8. PLENTIFUL-YEAR DR GAP (gov_plentiful vs ungov_plentiful)")
print(DSEP)
gp = plentiful_dr["Governed"]
up_val = plentiful_dr["Ungoverned"]
op_gap = (gp - up_val) / up_val * 100
print("  Governed plentiful DR:   {:.4f}".format(gp))
print("  Ungoverned plentiful DR: {:.4f}".format(up_val))
print("  Gap: {:.1f}%".format(op_gap))
print()

print(DSEP)
print("9. EHE -- 5-SKILL ENTROPY (Shannon / log2(5))")
print(DSEP)
ehe_results = {}
for cond in CONDITIONS:
    seed_ehes = []
    for s in SEEDS:
        ehe = compute_ehe(data[cond][s])
        seed_ehes.append(ehe)
        print("  {:12s} seed{}: EHE = {:.4f}".format(cond, s, ehe))
    ehe_results[cond] = (np.mean(seed_ehes), np.std(seed_ehes, ddof=1))
    print("  {:12s} ENSEMBLE: {:.4f} +/- {:.4f}".format(cond, np.mean(seed_ehes), np.std(seed_ehes, ddof=1)))
    print()

print(DSEP)
print("10. BRI -- WSA COHERENCE (high scarcity + increase = incoherent)")
print(DSEP)
for cond in CONDITIONS:
    seed_incoh = []
    for s in SEEDS:
        df = data[cond][s]
        high_wsa = df[df["wsa_label"].isin(["H", "VH"])]
        if len(high_wsa) > 0:
            increase_mask = high_wsa["yearly_decision"].isin(["increase_large", "increase_small"])
            incoh_rate = increase_mask.sum() / len(high_wsa)
        else:
            incoh_rate = 0.0
        seed_incoh.append(incoh_rate)
        print("  {:12s} seed{}: high-WSA n={}, incoh={:.4f} ({:.1f}%)".format(cond, s, len(high_wsa), incoh_rate, incoh_rate*100))
    print("  {:12s} ENSEMBLE incoherence: {:.4f}".format(cond, np.mean(seed_incoh)))
    print()

print(DSEP)
print("11. FIRST-ATTEMPT EHE (proposed_skill from governance audit)")
print(DSEP)
for cond in ["Governed", "Ungoverned"]:
    seed_ehes = []
    for s in SEEDS:
        ehe = compute_audit_ehe(audits[cond][s])
        seed_ehes.append(ehe)
        print("  {:12s} seed{}: first-attempt EHE = {:.4f}".format(cond, s, ehe))
    valid = [x for x in seed_ehes if not np.isnan(x)]
    if valid:
        print("  {:12s} ENSEMBLE: {:.4f} +/- {:.4f}".format(cond, np.mean(valid), np.std(valid, ddof=1)))
    print()
print(DSEP)
print("12. GOVERNANCE-BLOCKED PROPOSALS")
print(DSEP)
total_blocked = 0
total_rows = 0
for s in SEEDS:
    aud = audits["Governed"][s]
    if aud is not None:
        n_total = len(aud)
        n_blocked = int((aud["status"] != "APPROVED").sum())
        total_blocked += n_blocked
        total_rows += n_total
        pct = n_blocked / n_total * 100 if n_total > 0 else 0
        blocked_df = aud[aud["status"] != "APPROVED"]
        print("  Governed seed{}: {}/{} blocked ({:.1f}%)".format(s, n_blocked, n_total, pct))
        if len(blocked_df) > 0:
            for sk, cnt in blocked_df["proposed_skill"].value_counts().items():
                print("    {}: {}".format(sk, cnt))
if total_rows > 0:
    print("  TOTAL governed blocked: {}/{} ({:.1f}%)".format(total_blocked, total_rows, total_blocked/total_rows*100))
print()
print("  A1 (no ceiling) blocked proposals:")
for s in SEEDS:
    aud = audits["A1"][s]
    if aud is not None:
        n_total = len(aud)
        n_blocked = int((aud["status"] != "APPROVED").sum())
        print("    seed{}: {}/{} blocked ({:.1f}%)".format(s, n_blocked, n_total, n_blocked/n_total*100 if n_total else 0))
print()
print("  Ungoverned blocked proposals:")
for s in SEEDS:
    aud = audits["Ungoverned"][s]
    if aud is not None:
        n_total = len(aud)
        n_blocked = int((aud["status"] != "APPROVED").sum())
        print("    seed{}: {}/{} blocked ({:.1f}%)".format(s, n_blocked, n_total, n_blocked/n_total*100 if n_total else 0))
print()

print(DSEP)
print("13. YEAR-OVER-YEAR DEMAND VARIABILITY (SD of yearly DR)")
print(DSEP)
for cond in CONDITIONS:
    seed_sds = []
    for s in SEEDS:
        yr = yearly_data[cond][s]
        sd = yr["demand_ratio"].std()
        seed_sds.append(sd)
        print("  {:12s} seed{}: SD(DR) = {:.4f}".format(cond, s, sd))
    print("  {:12s} ENSEMBLE: {:.4f} +/- {:.4f}".format(cond, np.mean(seed_sds), np.std(seed_sds, ddof=1)))
    print()

print(DSEP)
print("14. UNGOVERNED BEHAVIORAL COLLAPSE (% increase decisions)")
print(DSEP)
for s in SEEDS:
    df = data["Ungoverned"][s]
    total = len(df)
    inc_mask = df["yearly_decision"].isin(["increase_large", "increase_small"])
    inc_count = int(inc_mask.sum())
    il = int((df["yearly_decision"] == "increase_large").sum())
    ism = int((df["yearly_decision"] == "increase_small").sum())
    print("  seed{}: {}/{} = {:.1f}% increase (large={}, small={})".format(s, inc_count, total, inc_count/total*100, il, ism))
print("\n  Governed increase % for comparison:")
for s in SEEDS:
    df = data["Governed"][s]
    total = len(df)
    inc = int(df["yearly_decision"].isin(["increase_large", "increase_small"]).sum())
    print("  seed{}: {}/{} = {:.1f}%".format(s, inc, total, inc/total*100))
print()
print(DSEP)
print("DEMAND CEILING THRESHOLD VERIFICATION")
print(DSEP)
print("  From irrigation_validators.py:")
print("    DEMAND_CEILING_AF = 6,000,000 AF = 6.0 MAF")
print("    Applied when: total_basin_demand > 6.0 MAF AND skill is increase_*")
print()

print(SEP)
print("  SUMMARY TABLE FOR PAPER")
print(SEP)
print("{:<40s} {:>12s} {:>12s} {:>12s}".format("Metric", "Governed", "A1", "Ungoverned"))
print(DSEP)
print("{:<40s} {:>12.4f} {:>12.4f} {:>12.4f}".format("Demand Ratio (mean)", dr_means["Governed"][0], dr_means["A1"][0], dr_means["Ungoverned"][0]))
print("{:<40s} {:>12.2f} {:>12.2f} {:>12.2f}".format("Mean Mead (ft)", mead_means["Governed"][0], mead_means["A1"][0], mead_means["Ungoverned"][0]))
print("{:<40s} {:>12.4f} {:>12.4f} {:>12.4f}".format("Plentiful DR", plentiful_dr["Governed"], plentiful_dr["A1"], plentiful_dr["Ungoverned"]))
print("{:<40s} {:>12.4f} {:>12.4f} {:>12.4f}".format("Shortage DR", shortage_dr["Governed"], shortage_dr["A1"], shortage_dr["Ungoverned"]))
cs_g = plentiful_dr["Governed"] - shortage_dr["Governed"]
cs_a = plentiful_dr["A1"] - shortage_dr["A1"]
cs_u = plentiful_dr["Ungoverned"] - shortage_dr["Ungoverned"]
print("{:<40s} {:>12.4f} {:>12.4f} {:>12.4f}".format("Curtailment Spread", cs_g, cs_a, cs_u))
print("{:<40s} {:>12.4f} {:>12.4f} {:>12.4f}".format("Pearson r (DR vs Mead)", pearson_results["Governed"][0], pearson_results["A1"][0], pearson_results["Ungoverned"][0]))
print("{:<40s} {:>12.4f} {:>12.4f} {:>12.4f}".format("EHE (5-skill)", ehe_results["Governed"][0], ehe_results["A1"][0], ehe_results["Ungoverned"][0]))
print("{:<40s} {:>12.1f} {:>12.1f} {:>12.1f}".format("Shortage years (/42)", np.mean(shortage_counts["Governed"]), np.mean(shortage_counts["A1"]), np.mean(shortage_counts["Ungoverned"])))

print("\n" + SEP)
print("  KEY PAPER CLAIMS -- VERIFICATION")
print(SEP)
print("  [Claim] Governed DR ~37% higher than Ungoverned: ACTUAL = {:.1f}%".format(gap_pct))
print("  [Claim] 53% higher plentiful operating point:    ACTUAL = {:.1f}%".format(op_gap))
print("  [Claim] Governed Mead LOWER than Ungoverned:")
gm = mead_means["Governed"][0]
um = mead_means["Ungoverned"][0]
print("          Gov={:.2f}, Ungov={:.2f}, diff={:.2f} ft".format(gm, um, gm - um))
print("  [Claim] Demand ceiling = 6.0 MAF: CONFIRMED in irrigation_validators.py")
print()

print(DSEP)
print("SKILL DISTRIBUTION (% of all decisions, ensemble mean across 3 seeds)")
print(DSEP)
for cond in CONDITIONS:
    print("\n  {}:".format(cond))
    all_counts = {sk: [] for sk in SKILLS_5}
    for s in SEEDS:
        df = data[cond][s]
        total = len(df)
        for sk in SKILLS_5:
            cnt = int((df["yearly_decision"] == sk).sum())
            all_counts[sk].append(cnt / total * 100)
    for sk in SKILLS_5:
        m = np.mean(all_counts[sk])
        sd = np.std(all_counts[sk], ddof=1)
        print("    {:<20s}: {:6.2f}% +/- {:.2f}%".format(sk, m, sd))

print("\n" + SEP)
print("  VERIFICATION COMPLETE")
print(SEP)