"""
RQ3 Construct Dynamics: SP, PA, SC temporal and cross-sectional analysis.

Extracts Stakeholder Perception (SP), Place Attachment (PA), and Social Capital (SC)
dynamics from the flood ABM governance audit traces across 3 seeds.

Outputs (saved to tables/):
  - rq3_sp_pa_yearly.csv        : yearly construct means by group
  - rq3_construct_action_profiles.csv : action x construct means
  - rq3_construct_stats.csv     : statistical test results
"""

import os
import json
import warnings
import numpy as np
import pandas as pd
from scipy import stats
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning)

# ── Paths ──────────────────────────────────────────────────────────────
BASE = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\multi_agent\flood\paper3")
RESULTS = BASE / "results" / "paper3_hybrid_v2"
TABLES = BASE / "analysis" / "tables"
TABLES.mkdir(parents=True, exist_ok=True)

SEEDS = ["seed_42", "seed_123", "seed_456"]
AGENT_TYPES = ["household_owner", "household_renter"]
MODEL = "gemma3_4b_strict"

AGENT_INIT = BASE / "data" / "agent_initialization_complete.csv"

ORDINAL_MAP = {"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5}
CONSTRUCTS = ["TP", "CP", "SP", "SC", "PA"]
CONSTRUCT_COLS = {c: f"construct_{c}_LABEL" for c in CONSTRUCTS}

# ── 1. Load governance audit data ──────────────────────────────────────
def load_audit_data():
    """Load all seeds x agent types, return single DataFrame."""
    frames = []
    for seed in SEEDS:
        for atype in AGENT_TYPES:
            fpath = RESULTS / seed / MODEL / f"{atype}_governance_audit.csv"
            if not fpath.exists():
                print(f"  WARNING: missing {fpath}")
                continue
            df = pd.read_csv(fpath, low_memory=False)
            df["seed"] = seed
            df["agent_type"] = "owner" if "owner" in atype else "renter"
            frames.append(df)
    return pd.concat(frames, ignore_index=True)


def load_flood_counts():
    """Extract per-agent per-year flood_count from JSONL traces."""
    records = []
    for seed in SEEDS:
        for atype in AGENT_TYPES:
            fpath = RESULTS / seed / MODEL / "raw" / f"{atype}_traces.jsonl"
            if not fpath.exists():
                continue
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    sb = d.get("state_before", {})
                    if not isinstance(sb, dict):
                        continue
                    records.append({
                        "agent_id": d.get("agent_id", sb.get("id", "")),
                        "year": d.get("year"),
                        "seed": seed,
                        "flood_count": sb.get("flood_count", 0),
                    })
    if not records:
        return None
    return pd.DataFrame(records)


def load_agent_init():
    """Load agent initialization for MG status."""
    df = pd.read_csv(AGENT_INIT)
    # Normalize: keep agent_id, mg, tenure
    df = df[["agent_id", "mg", "tenure"]].copy()
    df["mg_label"] = df["mg"].map({True: "MG", False: "NMG", "True": "MG", "False": "NMG"})
    df["tenure_label"] = df["tenure"].str.strip()
    return df


# ── 2. Preprocessing ──────────────────────────────────────────────────
def preprocess(audit_df, init_df, flood_df):
    """Map ordinal labels, join MG status, add calendar year."""
    df = audit_df.copy()

    # Map ordinal constructs
    for c, col in CONSTRUCT_COLS.items():
        if col in df.columns:
            df[f"{c}_num"] = df[col].map(ORDINAL_MAP)

    # Calendar year: if year is 1-13, add 2010
    if df["year"].min() <= 13:
        df["calendar_year"] = df["year"].astype(int) + 2010
    else:
        df["calendar_year"] = df["year"].astype(int)

    # Join MG status
    df = df.merge(init_df[["agent_id", "mg_label", "tenure_label"]], on="agent_id", how="left")

    # 4-cell label
    df["cell"] = df["mg_label"].fillna("UNK") + "-" + df["agent_type"].str.capitalize()

    # Join flood counts if available
    if flood_df is not None:
        flood_df = flood_df.copy()
        flood_df["year"] = flood_df["year"].astype(int)
        df["year"] = df["year"].astype(int)
        df = df.merge(flood_df[["agent_id", "year", "seed", "flood_count"]],
                       on=["agent_id", "year", "seed"], how="left")
        df["flood_count"] = df["flood_count"].fillna(0).astype(int)
        df["flood_bin"] = pd.cut(df["flood_count"], bins=[-1, 0, 1, 2, 100],
                                  labels=["0", "1", "2", "3+"])
    else:
        df["flood_count"] = np.nan
        df["flood_bin"] = np.nan

    # Determine action column: use final_skill (executed), fall back to proposed_skill
    if "final_skill" in df.columns:
        df["action"] = df["final_skill"]
    elif "proposed_skill" in df.columns:
        df["action"] = df["proposed_skill"]
    else:
        df["action"] = "unknown"

    return df


# ── 3. Yearly means ───────────────────────────────────────────────────
def compute_yearly_means(df):
    """Compute yearly means for each construct by various groupings."""
    num_cols = [f"{c}_num" for c in CONSTRUCTS if f"{c}_num" in df.columns]
    rows = []

    # Define groupings
    groupings = {
        "Overall": df,
        "MG": df[df["mg_label"] == "MG"],
        "NMG": df[df["mg_label"] == "NMG"],
        "Owner": df[df["agent_type"] == "owner"],
        "Renter": df[df["agent_type"] == "renter"],
        "MG-Owner": df[df["cell"] == "MG-Owner"],
        "MG-Renter": df[df["cell"] == "MG-Renter"],
        "NMG-Owner": df[df["cell"] == "NMG-Owner"],
        "NMG-Renter": df[df["cell"] == "NMG-Renter"],
    }

    for group_name, gdf in groupings.items():
        if gdf.empty:
            continue
        yearly = gdf.groupby("calendar_year")[num_cols].mean()
        for year_val, row in yearly.iterrows():
            for col in num_cols:
                construct = col.replace("_num", "")
                rows.append({
                    "year": int(year_val),
                    "construct": construct,
                    "group": group_name,
                    "mean": round(row[col], 4) if pd.notna(row[col]) else np.nan,
                    "n": int(gdf[gdf["calendar_year"] == year_val][col].notna().sum()),
                })

    return pd.DataFrame(rows)


# ── 4. Construct by flood bin ──────────────────────────────────────────
def compute_flood_bin_means(df):
    """Mean SP, PA, SC by cumulative flood count bins."""
    if df["flood_bin"].isna().all():
        print("  No flood_count data available, skipping flood-bin analysis.")
        return None

    num_cols = ["SP_num", "PA_num", "SC_num"]
    existing = [c for c in num_cols if c in df.columns]
    result = df.groupby("flood_bin", observed=True)[existing].agg(["mean", "count"])
    print("\n=== Construct means by cumulative flood count ===")
    for col in existing:
        print(f"\n  {col.replace('_num','')}:")
        for fb in ["0", "1", "2", "3+"]:
            if fb in result.index:
                m = result.loc[fb, (col, "mean")]
                n = result.loc[fb, (col, "count")]
                print(f"    flood_bin={fb}: mean={m:.3f} (n={int(n)})")
    return result


# ── 5. Construct-action profiles ───────────────────────────────────────
def compute_action_profiles(df):
    """Mean construct values per action type."""
    num_cols = [f"{c}_num" for c in CONSTRUCTS if f"{c}_num" in df.columns]
    # Only rows with valid constructs
    valid = df.dropna(subset=num_cols, how="all")
    result = valid.groupby("action")[num_cols].agg(["mean", "count"])

    # Flatten for CSV
    rows = []
    for action in result.index:
        row = {"action": action}
        for col in num_cols:
            c = col.replace("_num", "")
            row[f"{c}_mean"] = round(result.loc[action, (col, "mean")], 4)
            row[f"{c}_n"] = int(result.loc[action, (col, "count")])
        rows.append(row)
    return pd.DataFrame(rows)


# ── 6. Statistical tests ──────────────────────────────────────────────
def compute_stats(df):
    """Spearman correlations and Mann-Whitney U tests."""
    results = []

    # Drop rows with missing numeric constructs
    for construct in ["SP", "PA"]:
        col = f"{construct}_num"
        if col not in df.columns:
            continue
        valid = df.dropna(subset=[col])
        if valid.empty:
            continue

        # Spearman: construct vs calendar_year (temporal trend)
        rho, pval = stats.spearmanr(valid["calendar_year"], valid[col])
        results.append({
            "test": f"Spearman_{construct}_vs_year",
            "statistic": round(rho, 4),
            "p_value": pval,
            "n": len(valid),
            "interpretation": f"{'Sig' if pval < 0.05 else 'NS'} temporal trend (rho={rho:.3f})",
        })

    # Mann-Whitney U: SP for insurance choosers vs do_nothing choosers
    insurance_actions = ["buy_insurance", "buy_contents_insurance"]
    sp_fi = df.loc[df["action"].isin(insurance_actions) & df["SP_num"].notna(), "SP_num"]
    sp_dn = df.loc[(df["action"] == "do_nothing") & df["SP_num"].notna(), "SP_num"]
    if len(sp_fi) > 0 and len(sp_dn) > 0:
        u, p = stats.mannwhitneyu(sp_fi, sp_dn, alternative="two-sided")
        results.append({
            "test": "MWU_SP_insurance_vs_donothing",
            "statistic": round(u, 1),
            "p_value": p,
            "n": len(sp_fi) + len(sp_dn),
            "interpretation": f"{'Sig' if p < 0.05 else 'NS'} SP diff (ins mean={sp_fi.mean():.2f}, dn mean={sp_dn.mean():.2f})",
        })

    # Mann-Whitney U: PA for relocate choosers vs do_nothing (renters only)
    renters = df[df["agent_type"] == "renter"]
    pa_rl = renters.loc[(renters["action"] == "relocate") & renters["PA_num"].notna(), "PA_num"]
    pa_dn_r = renters.loc[(renters["action"] == "do_nothing") & renters["PA_num"].notna(), "PA_num"]
    if len(pa_rl) > 0 and len(pa_dn_r) > 0:
        u, p = stats.mannwhitneyu(pa_rl, pa_dn_r, alternative="two-sided")
        results.append({
            "test": "MWU_PA_relocate_vs_donothing_renters",
            "statistic": round(u, 1),
            "p_value": p,
            "n": len(pa_rl) + len(pa_dn_r),
            "interpretation": f"{'Sig' if p < 0.05 else 'NS'} PA diff (rl mean={pa_rl.mean():.2f}, dn mean={pa_dn_r.mean():.2f})",
        })

    # Mann-Whitney U: SP for MG vs NMG
    sp_mg = df.loc[(df["mg_label"] == "MG") & df["SP_num"].notna(), "SP_num"]
    sp_nmg = df.loc[(df["mg_label"] == "NMG") & df["SP_num"].notna(), "SP_num"]
    if len(sp_mg) > 0 and len(sp_nmg) > 0:
        u, p = stats.mannwhitneyu(sp_mg, sp_nmg, alternative="two-sided")
        results.append({
            "test": "MWU_SP_MG_vs_NMG",
            "statistic": round(u, 1),
            "p_value": p,
            "n": len(sp_mg) + len(sp_nmg),
            "interpretation": f"{'Sig' if p < 0.05 else 'NS'} SP diff (MG mean={sp_mg.mean():.2f}, NMG mean={sp_nmg.mean():.2f})",
        })

    # Mann-Whitney U: PA for MG vs NMG
    pa_mg = df.loc[(df["mg_label"] == "MG") & df["PA_num"].notna(), "PA_num"]
    pa_nmg = df.loc[(df["mg_label"] == "NMG") & df["PA_num"].notna(), "PA_num"]
    if len(pa_mg) > 0 and len(pa_nmg) > 0:
        u, p = stats.mannwhitneyu(pa_mg, pa_nmg, alternative="two-sided")
        results.append({
            "test": "MWU_PA_MG_vs_NMG",
            "statistic": round(u, 1),
            "p_value": p,
            "n": len(pa_mg) + len(pa_nmg),
            "interpretation": f"{'Sig' if p < 0.05 else 'NS'} PA diff (MG mean={pa_mg.mean():.2f}, NMG mean={pa_nmg.mean():.2f})",
        })

    # Spearman: SP vs flood_count (dose-response)
    if "flood_count" in df.columns and df["flood_count"].notna().any():
        valid = df.dropna(subset=["SP_num", "flood_count"])
        if len(valid) > 10:
            rho, pval = stats.spearmanr(valid["flood_count"], valid["SP_num"])
            results.append({
                "test": "Spearman_SP_vs_flood_count",
                "statistic": round(rho, 4),
                "p_value": pval,
                "n": len(valid),
                "interpretation": f"{'Sig' if pval < 0.05 else 'NS'} flood-dose effect (rho={rho:.3f})",
            })
        valid2 = df.dropna(subset=["PA_num", "flood_count"])
        if len(valid2) > 10:
            rho, pval = stats.spearmanr(valid2["flood_count"], valid2["PA_num"])
            results.append({
                "test": "Spearman_PA_vs_flood_count",
                "statistic": round(rho, 4),
                "p_value": pval,
                "n": len(valid2),
                "interpretation": f"{'Sig' if pval < 0.05 else 'NS'} flood-dose effect (rho={rho:.3f})",
            })

    return pd.DataFrame(results)


# ── Main ───────────────────────────────────────────────────────────────
def main():
    print("=" * 70)
    print("RQ3 Construct Dynamics: SP, PA, SC Analysis")
    print("=" * 70)

    # Load data
    print("\n[1] Loading governance audit data...")
    audit_df = load_audit_data()
    print(f"    Total audit rows: {len(audit_df)}")
    print(f"    Seeds: {audit_df['seed'].unique().tolist()}")
    print(f"    Agent types: {audit_df['agent_type'].unique().tolist()}")

    print("\n[2] Loading agent initialization...")
    init_df = load_agent_init()
    print(f"    Agents: {len(init_df)}, MG: {(init_df['mg_label']=='MG').sum()}, NMG: {(init_df['mg_label']=='NMG').sum()}")

    print("\n[3] Loading flood counts from JSONL traces...")
    flood_df = load_flood_counts()
    if flood_df is not None:
        print(f"    Flood count records: {len(flood_df)}")
        print(f"    Max flood_count: {flood_df['flood_count'].max()}")
    else:
        print("    No flood count data found.")

    print("\n[4] Preprocessing...")
    df = preprocess(audit_df, init_df, flood_df)

    # Report construct coverage
    for c in CONSTRUCTS:
        col = f"{c}_num"
        if col in df.columns:
            n_valid = df[col].notna().sum()
            pct = 100 * n_valid / len(df)
            print(f"    {c}: {n_valid}/{len(df)} valid ({pct:.1f}%)")

    # Report action distribution
    print(f"\n    Action distribution:")
    for action, count in df["action"].value_counts().items():
        print(f"      {action}: {count} ({100*count/len(df):.1f}%)")

    # ── Yearly means ──
    print("\n[5] Computing yearly construct means...")
    yearly_df = compute_yearly_means(df)
    yearly_df.to_csv(TABLES / "rq3_sp_pa_yearly.csv", index=False)
    print(f"    Saved: {TABLES / 'rq3_sp_pa_yearly.csv'}")

    # Print summary: overall SP and PA by year
    print("\n=== Overall SP and PA by year ===")
    overall = yearly_df[yearly_df["group"] == "Overall"]
    for construct in ["SP", "PA", "SC"]:
        cdata = overall[overall["construct"] == construct].sort_values("year")
        if not cdata.empty:
            vals = cdata["mean"].values
            years = cdata["year"].values
            print(f"  {construct}: Y{years[0]}={vals[0]:.2f} -> Y{years[-1]}={vals[-1]:.2f}"
                  f"  (range {vals.min():.2f}-{vals.max():.2f})")

    # Print 4-cell summary for SP
    print("\n=== SP means by 4-cell (pooled across years) ===")
    for cell in ["MG-Owner", "MG-Renter", "NMG-Owner", "NMG-Renter"]:
        subset = df[df["cell"] == cell]
        sp_mean = subset["SP_num"].mean()
        pa_mean = subset["PA_num"].mean()
        n = subset["SP_num"].notna().sum()
        print(f"  {cell}: SP={sp_mean:.3f}, PA={pa_mean:.3f} (n={n})")

    # ── Flood bin analysis ──
    print("\n[6] Flood-bin construct analysis...")
    compute_flood_bin_means(df)

    # ── Action profiles ──
    print("\n[7] Computing construct-action profiles...")
    action_df = compute_action_profiles(df)
    action_df.to_csv(TABLES / "rq3_construct_action_profiles.csv", index=False)
    print(f"    Saved: {TABLES / 'rq3_construct_action_profiles.csv'}")

    print("\n=== Construct-Action Profiles ===")
    print(action_df.to_string(index=False))

    # ── Statistical tests ──
    print("\n[8] Running statistical tests...")
    stats_df = compute_stats(df)
    stats_df.to_csv(TABLES / "rq3_construct_stats.csv", index=False)
    print(f"    Saved: {TABLES / 'rq3_construct_stats.csv'}")

    print("\n=== Statistical Test Results ===")
    for _, row in stats_df.iterrows():
        sig = "***" if row["p_value"] < 0.001 else "**" if row["p_value"] < 0.01 else "*" if row["p_value"] < 0.05 else "ns"
        print(f"  {row['test']}: stat={row['statistic']}, p={row['p_value']:.4e}, n={row['n']} [{sig}]")
        print(f"    -> {row['interpretation']}")

    # ── Key findings summary ──
    print("\n" + "=" * 70)
    print("KEY FINDINGS SUMMARY")
    print("=" * 70)

    # SP temporal trend
    sp_trend = stats_df[stats_df["test"] == "Spearman_SP_vs_year"]
    if not sp_trend.empty:
        r = sp_trend.iloc[0]
        direction = "increasing" if r["statistic"] > 0 else "decreasing"
        print(f"\n1. SP temporal trend: {direction} (rho={r['statistic']:.3f}, p={r['p_value']:.2e})")

    # PA temporal trend
    pa_trend = stats_df[stats_df["test"] == "Spearman_PA_vs_year"]
    if not pa_trend.empty:
        r = pa_trend.iloc[0]
        direction = "increasing" if r["statistic"] > 0 else "decreasing"
        print(f"2. PA temporal trend: {direction} (rho={r['statistic']:.3f}, p={r['p_value']:.2e})")

    # MG vs NMG SP gap
    sp_gap = stats_df[stats_df["test"] == "MWU_SP_MG_vs_NMG"]
    if not sp_gap.empty:
        print(f"3. SP MG vs NMG: {sp_gap.iloc[0]['interpretation']}")

    # Insurance vs DN SP difference
    sp_ins = stats_df[stats_df["test"] == "MWU_SP_insurance_vs_donothing"]
    if not sp_ins.empty:
        print(f"4. SP insurance vs do_nothing: {sp_ins.iloc[0]['interpretation']}")

    # Relocate vs DN PA difference (renters)
    pa_rl = stats_df[stats_df["test"] == "MWU_PA_relocate_vs_donothing_renters"]
    if not pa_rl.empty:
        print(f"5. PA relocate vs do_nothing (renters): {pa_rl.iloc[0]['interpretation']}")

    # Flood-dose effects
    sp_flood = stats_df[stats_df["test"] == "Spearman_SP_vs_flood_count"]
    if not sp_flood.empty:
        print(f"6. SP flood-dose response: rho={sp_flood.iloc[0]['statistic']:.3f}, p={sp_flood.iloc[0]['p_value']:.2e}")

    pa_flood = stats_df[stats_df["test"] == "Spearman_PA_vs_flood_count"]
    if not pa_flood.empty:
        print(f"7. PA flood-dose response: rho={pa_flood.iloc[0]['statistic']:.3f}, p={pa_flood.iloc[0]['p_value']:.2e}")

    print("\nDone.")


if __name__ == "__main__":
    main()
