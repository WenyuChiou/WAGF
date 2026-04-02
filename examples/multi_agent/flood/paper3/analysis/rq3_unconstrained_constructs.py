"""
RQ3 Analysis: Unconstrained Construct Behavior Distributions
CP=M vs CP=H (no blocking rules), SP levels, PA levels
"""

import pandas as pd
import numpy as np
from scipy.stats import chi2_contingency
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

# Paths
BASE = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\multi_agent\flood\paper3")
RESULTS = BASE / "results" / "paper3_hybrid_v2"
PROFILES = BASE / "data" / "agent_initialization_complete.csv"
OUT_DIR = BASE / "analysis" / "tables"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SEEDS = ["seed_42", "seed_123", "seed_456"]
AGENT_TYPES = ["household_owner", "household_renter"]

# Load profiles for MG status
profiles = pd.read_csv(PROFILES)
profiles["mg_status"] = profiles["mg"].map({True: "MG", False: "NMG"})
agent_mg = profiles.set_index("agent_id")["mg_status"].to_dict()

# Load all audit data
frames = []
for seed in SEEDS:
    for atype in AGENT_TYPES:
        fpath = RESULTS / seed / "gemma3_4b_strict" / f"{atype}_governance_audit.csv"
        if fpath.exists():
            df = pd.read_csv(fpath)
            df["seed"] = seed
            df["agent_type"] = "owner" if "owner" in atype else "renter"
            frames.append(df)
        else:
            print(f"WARNING: Missing {fpath}")

data = pd.concat(frames, ignore_index=True)

# Compute executed action: APPROVED -> proposed_skill, REJECTED -> do_nothing
data["executed_action"] = data.apply(
    lambda r: r["proposed_skill"] if r["status"] == "APPROVED" else "do_nothing", axis=1
)

# Add MG status
data["mg_status"] = data["agent_id"].map(agent_mg)

# Rename construct columns for convenience
data.rename(columns={
    "construct_CP_LABEL": "CP",
    "construct_TP_LABEL": "TP",
    "construct_SP_LABEL": "SP",
    "construct_SC_LABEL": "SC",
    "construct_PA_LABEL": "PA",
}, inplace=True)

# Clean: drop rows with missing CP
print(f"Total rows: {len(data)}")
print(f"Rows with missing CP: {data['CP'].isna().sum()}")
print(f"Rows with empty CP: {(data['CP'] == '').sum()}")
data_clean = data[data["CP"].notna() & (data["CP"] != "")].copy()
print(f"Rows after cleaning: {len(data_clean)}")
print()

# CP distribution overview
print("=" * 80)
print("CP LABEL DISTRIBUTION (all data)")
print("=" * 80)
print(data_clean["CP"].value_counts().sort_index())
print()

# Helper functions
def action_distribution(df, group_col, agent_type_filter=None):
    """Compute action distribution percentages."""
    if agent_type_filter:
        df = df[df["agent_type"] == agent_type_filter]
    if len(df) == 0:
        return pd.DataFrame()
    ct = pd.crosstab(df[group_col], df["executed_action"], normalize="index") * 100
    counts = pd.crosstab(df[group_col], df["executed_action"])
    n_per_group = df.groupby(group_col).size()
    return ct, counts, n_per_group


def chi2_test(df, group_col, agent_type_filter=None):
    """Chi-squared test between groups."""
    if agent_type_filter:
        df = df[df["agent_type"] == agent_type_filter]
    ct = pd.crosstab(df[group_col], df["executed_action"])
    if ct.shape[0] < 2 or ct.shape[1] < 2:
        return None, None, None
    chi2, p, dof, _ = chi2_contingency(ct)
    return chi2, p, dof


def print_distribution(ct, counts, n_per_group, title):
    """Pretty print distribution table."""
    print(f"\n{'=' * 80}")
    print(title)
    print(f"{'=' * 80}")
    print(f"\nN per group:")
    for idx in n_per_group.index:
        print(f"  {idx}: N={n_per_group[idx]}")
    print(f"\nAction Distribution (%):")
    print(ct.round(1).to_string())
    print(f"\nAction Counts:")
    print(counts.to_string())


# Collect all results for CSV export
all_results = []


def record_result(section, group, agent_type, action, pct, count, n):
    all_results.append({
        "section": section,
        "group": group,
        "agent_type": agent_type,
        "action": action,
        "pct": round(pct, 2),
        "count": count,
        "N": n
    })


# =========================================================================
# (a) CP=M vs CP=H behavior distribution
# =========================================================================
print("\n" + "#" * 80)
print("# SECTION (a): CP=M vs CP=H Behavior Distribution")
print("#" * 80)

cp_mh = data_clean[data_clean["CP"].isin(["M", "H"])]

for atype in ["owner", "renter"]:
    ct, counts, n = action_distribution(cp_mh, "CP", atype)
    print_distribution(ct, counts, n, f"CP=M vs CP=H — {atype.upper()}")

    # Record for CSV
    for cp_val in ct.index:
        for action in ct.columns:
            record_result("a_CP_M_vs_H", f"CP={cp_val}", atype, action,
                          ct.loc[cp_val, action], counts.loc[cp_val, action], n[cp_val])

    chi2, p, dof = chi2_test(cp_mh, "CP", atype)
    if chi2 is not None:
        print(f"\n  Chi-squared test: chi2={chi2:.2f}, p={p:.4f}, dof={dof}")
        sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
        print(f"  Significance: {sig}")

# =========================================================================
# (b) CP=M vs CP=H x MG/NMG (4-way)
# =========================================================================
print("\n" + "#" * 80)
print("# SECTION (b): CP=M vs CP=H x MG/NMG (4-way)")
print("#" * 80)

cp_mh["cp_mg"] = cp_mh["CP"] + "_" + cp_mh["mg_status"].fillna("UNK")

for atype in ["owner", "renter"]:
    ct, counts, n = action_distribution(cp_mh, "cp_mg", atype)
    print_distribution(ct, counts, n, f"CP x MG — {atype.upper()}")

    for grp in ct.index:
        for action in ct.columns:
            record_result("b_CP_MG_4way", grp, atype, action,
                          ct.loc[grp, action], counts.loc[grp, action], n[grp])

    chi2, p, dof = chi2_test(cp_mh, "cp_mg", atype)
    if chi2 is not None:
        print(f"\n  Chi-squared test (4-way): chi2={chi2:.2f}, p={p:.4f}, dof={dof}")

# =========================================================================
# (c) All 5 CP levels
# =========================================================================
print("\n" + "#" * 80)
print("# SECTION (c): All 5 CP Levels — Full Gradient")
print("#" * 80)

cp_order = ["VL", "L", "M", "H", "VH"]
blocked_info = {
    "VL": "BLOCKED from elevation/buyout/relocate",
    "L": "BLOCKED from elevation/buyout/relocate",
    "M": "UNCONSTRAINED",
    "H": "UNCONSTRAINED",
    "VH": "VH+TP=VH blocks do_nothing"
}

for atype in ["owner", "renter"]:
    adf = data_clean[data_clean["agent_type"] == atype]
    ct = pd.crosstab(adf["CP"], adf["executed_action"], normalize="index") * 100
    counts = pd.crosstab(adf["CP"], adf["executed_action"])
    n_grp = adf.groupby("CP").size()

    # Reindex to ordered
    existing = [c for c in cp_order if c in ct.index]
    ct = ct.reindex(existing)
    counts = counts.reindex(existing)

    print(f"\n{'=' * 80}")
    print(f"All CP Levels — {atype.upper()}")
    print(f"{'=' * 80}")
    print(f"\nN per CP level:")
    for cp in existing:
        constraint = blocked_info.get(cp, "")
        print(f"  CP={cp}: N={n_grp.get(cp, 0):>5}  [{constraint}]")
    print(f"\nAction Distribution (%):")
    print(ct.round(1).to_string())
    print(f"\nAction Counts:")
    print(counts.to_string())

    for cp_val in existing:
        for action in ct.columns:
            record_result("c_all_CP", f"CP={cp_val}", atype, action,
                          ct.loc[cp_val, action], counts.loc[cp_val, action], n_grp.get(cp_val, 0))

# =========================================================================
# (d) CP=M vs CP=H controlling for TP
# =========================================================================
print("\n" + "#" * 80)
print("# SECTION (d): CP=M vs CP=H Controlling for TP Level")
print("#" * 80)

for tp_level in ["M", "H", "VH"]:
    subset = cp_mh[cp_mh["TP"] == tp_level]
    if len(subset) < 10:
        print(f"\n  TP={tp_level}: Too few observations (N={len(subset)}), skipping")
        continue

    for atype in ["owner", "renter"]:
        adf = subset[subset["agent_type"] == atype]
        if len(adf) < 5:
            print(f"\n  TP={tp_level}, {atype}: Too few (N={len(adf)}), skipping")
            continue

        ct = pd.crosstab(adf["CP"], adf["executed_action"], normalize="index") * 100
        counts = pd.crosstab(adf["CP"], adf["executed_action"])
        n_grp = adf.groupby("CP").size()

        print_distribution(ct, counts, n_grp,
                           f"CP=M vs CP=H | TP={tp_level} — {atype.upper()}")

        for cp_val in ct.index:
            for action in ct.columns:
                record_result(f"d_CP_control_TP={tp_level}", f"CP={cp_val}", atype, action,
                              ct.loc[cp_val, action], counts.loc[cp_val, action], n_grp[cp_val])

        chi2, p, dof = chi2_test(adf, "CP")
        if chi2 is not None:
            print(f"\n  Chi-squared: chi2={chi2:.2f}, p={p:.4f}, dof={dof}")
            sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
            print(f"  Significance: {sig}")

# =========================================================================
# (e) SP and PA distributions (unconstrained constructs)
# =========================================================================
print("\n" + "#" * 80)
print("# SECTION (e): SP Levels — No Blocking Rules")
print("#" * 80)

sp_order = ["VL", "L", "M", "H", "VH"]
for atype in ["owner", "renter"]:
    adf = data_clean[data_clean["agent_type"] == atype]
    adf_sp = adf[adf["SP"].notna() & (adf["SP"] != "")]
    ct = pd.crosstab(adf_sp["SP"], adf_sp["executed_action"], normalize="index") * 100
    counts = pd.crosstab(adf_sp["SP"], adf_sp["executed_action"])
    n_grp = adf_sp.groupby("SP").size()

    existing = [s for s in sp_order if s in ct.index]
    ct = ct.reindex(existing)
    counts = counts.reindex(existing)

    print(f"\n{'=' * 80}")
    print(f"SP Levels — {atype.upper()} (NO blocking rules for SP)")
    print(f"{'=' * 80}")
    print(f"\nN per SP level:")
    for sp in existing:
        print(f"  SP={sp}: N={n_grp.get(sp, 0):>5}")
    print(f"\nAction Distribution (%):")
    print(ct.round(1).to_string())
    print(f"\nAction Counts:")
    print(counts.to_string())

    for sp_val in existing:
        for action in ct.columns:
            record_result("e_SP_levels", f"SP={sp_val}", atype, action,
                          ct.loc[sp_val, action], counts.loc[sp_val, action], n_grp.get(sp_val, 0))

    # Chi-sq across all SP levels
    ct_raw = pd.crosstab(adf_sp["SP"], adf_sp["executed_action"])
    if ct_raw.shape[0] >= 2 and ct_raw.shape[1] >= 2:
        chi2, p, dof, _ = chi2_contingency(ct_raw)
        print(f"\n  Chi-squared (all SP levels): chi2={chi2:.2f}, p={p:.4f}, dof={dof}")
        sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
        print(f"  Significance: {sig}")

print("\n" + "#" * 80)
print("# SECTION (e cont): PA Levels — PA blocks buyout for H/VH only")
print("#" * 80)

pa_order = ["VL", "L", "M", "H", "VH"]
pa_blocked_info = {
    "VL": "unconstrained",
    "L": "unconstrained",
    "M": "unconstrained",
    "H": "BLOCKS buyout (high place attachment)",
    "VH": "BLOCKS buyout (very high place attachment)"
}

for atype in ["owner", "renter"]:
    adf = data_clean[data_clean["agent_type"] == atype]
    adf_pa = adf[adf["PA"].notna() & (adf["PA"] != "")]
    ct = pd.crosstab(adf_pa["PA"], adf_pa["executed_action"], normalize="index") * 100
    counts = pd.crosstab(adf_pa["PA"], adf_pa["executed_action"])
    n_grp = adf_pa.groupby("PA").size()

    existing = [p for p in pa_order if p in ct.index]
    ct = ct.reindex(existing)
    counts = counts.reindex(existing)

    print(f"\n{'=' * 80}")
    print(f"PA Levels — {atype.upper()}")
    print(f"{'=' * 80}")
    print(f"\nN per PA level:")
    for pa in existing:
        constraint = pa_blocked_info.get(pa, "")
        print(f"  PA={pa}: N={n_grp.get(pa, 0):>5}  [{constraint}]")
    print(f"\nAction Distribution (%):")
    print(ct.round(1).to_string())
    print(f"\nAction Counts:")
    print(counts.to_string())

    for pa_val in existing:
        for action in ct.columns:
            record_result("e_PA_levels", f"PA={pa_val}", atype, action,
                          ct.loc[pa_val, action], counts.loc[pa_val, action], n_grp.get(pa_val, 0))

    ct_raw = pd.crosstab(adf_pa["PA"], adf_pa["executed_action"])
    if ct_raw.shape[0] >= 2 and ct_raw.shape[1] >= 2:
        chi2, p, dof, _ = chi2_contingency(ct_raw)
        print(f"\n  Chi-squared (all PA levels): chi2={chi2:.2f}, p={p:.4f}, dof={dof}")
        sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
        print(f"  Significance: {sig}")

# =========================================================================
# Save CSV
# =========================================================================
results_df = pd.DataFrame(all_results)
out_path = OUT_DIR / "rq3_unconstrained_constructs.csv"
results_df.to_csv(out_path, index=False)
print(f"\n\nResults saved to: {out_path}")
print(f"Total rows in CSV: {len(results_df)}")
