"""
Within-agent TP decay analysis broken down by agent type (owner/renter) and MG status.
4-cell comparison: MG-Owner, NMG-Owner, MG-Renter, NMG-Renter.
Pools across 3 seeds (42, 123, 456).
"""

import json
import warnings
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

warnings.filterwarnings("ignore")

# ── Paths ──
BASE = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\multi_agent\flood\paper3")
RESULTS = BASE / "results" / "paper3_hybrid_v2"
PROFILES = BASE / "data" / "agent_initialization_complete.csv"
SEEDS = [42, 123, 456]
OUTPUT_TABLE = BASE / "analysis" / "tables" / "rq1_tp_decay_by_group.csv"

TP_MAP = {"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5}


def load_profiles():
    df = pd.read_csv(PROFILES)
    return df[["agent_id", "mg", "tenure", "flood_zone"]].copy()


def load_audit_and_traces(seed):
    """Load audit CSVs and trace JSONLs for one seed, extract flood status per agent-year."""
    seed_dir = RESULTS / f"seed_{seed}" / "gemma3_4b_strict"

    # Load audit CSVs
    owner_audit = pd.read_csv(seed_dir / "household_owner_governance_audit.csv")
    owner_audit["agent_type"] = "Owner"
    renter_audit = pd.read_csv(seed_dir / "household_renter_governance_audit.csv")
    renter_audit["agent_type"] = "Renter"
    audit = pd.concat([owner_audit, renter_audit], ignore_index=True)
    audit["seed"] = seed

    # Extract TP numeric
    audit["tp_num"] = audit["construct_TP_LABEL"].map(TP_MAP)

    # Load traces to get flooded_this_year per agent-year
    flood_records = []
    for trace_file, atype in [
        (seed_dir / "raw" / "household_owner_traces.jsonl", "Owner"),
        (seed_dir / "raw" / "household_renter_traces.jsonl", "Renter"),
    ]:
        with open(trace_file, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                agent_id = rec.get("agent_id")
                year = rec.get("year")
                # Get flooded_this_year from state_before
                sb = rec.get("state_before", {})
                flooded = sb.get("flooded_this_year", False)
                flood_count = sb.get("flood_count", 0)
                flood_records.append({
                    "agent_id": agent_id,
                    "year": year,
                    "flooded_this_year": flooded,
                    "flood_count": flood_count,
                    "seed": seed,
                })

    flood_df = pd.DataFrame(flood_records)
    # De-duplicate (retries may produce multiple traces per agent-year)
    flood_df = flood_df.drop_duplicates(subset=["agent_id", "year", "seed"])

    return audit, flood_df


def build_combined():
    """Combine all seeds into one dataset with TP, flood status, agent metadata."""
    profiles = load_profiles()

    all_audit = []
    all_flood = []
    for seed in SEEDS:
        print(f"  Loading seed {seed}...")
        audit, flood_df = load_audit_and_traces(seed)
        all_audit.append(audit)
        all_flood.append(flood_df)

    audit = pd.concat(all_audit, ignore_index=True)
    flood = pd.concat(all_flood, ignore_index=True)

    # Merge flood status into audit
    audit = audit.merge(flood[["agent_id", "year", "seed", "flooded_this_year", "flood_count"]],
                        on=["agent_id", "year", "seed"], how="left")

    # Merge profiles (mg, tenure, flood_zone)
    audit = audit.merge(profiles[["agent_id", "mg", "flood_zone"]], on="agent_id", how="left")

    # Create cell label
    audit["mg_label"] = audit["mg"].map({True: "MG", False: "NMG"})
    audit["cell"] = audit["mg_label"] + "-" + audit["agent_type"]

    return audit


def find_flood_years_per_agent(df):
    """For each (agent_id, seed), find years where agent was flooded."""
    flooded = df[df["flooded_this_year"] == True]
    return flooded.groupby(["agent_id", "seed"])["year"].apply(list).to_dict()


def build_decay_windows(df, flood_years_dict, max_lag=3):
    """
    For each agent flood event, track TP at t=0, t+1, t+2, t+3.
    Only include if NO subsequent flood in [t+1, t+max_lag].
    """
    records = []
    # Index TP by (agent_id, seed, year)
    tp_index = df.set_index(["agent_id", "seed", "year"])["tp_num"].to_dict()
    action_index = df.set_index(["agent_id", "seed", "year"])["final_skill"].to_dict()
    cell_index = df.set_index(["agent_id", "seed", "year"])["cell"].to_dict()
    mg_index = df.set_index(["agent_id", "seed", "year"])["mg_label"].to_dict()
    zone_index = df.set_index(["agent_id", "seed", "year"])["flood_zone"].to_dict()
    type_index = df.set_index(["agent_id", "seed", "year"])["agent_type"].to_dict()

    max_year = int(df["year"].max())

    for (agent_id, seed), years in flood_years_dict.items():
        for flood_year in years:
            # Check no subsequent flood in window
            subsequent_floods = [y for y in years if flood_year < y <= flood_year + max_lag]
            if subsequent_floods:
                continue  # Skip — contaminated window

            # Also skip if window extends beyond data
            if flood_year + max_lag > max_year:
                continue

            key0 = (agent_id, seed, flood_year)
            tp0 = tp_index.get(key0)
            if pd.isna(tp0) if tp0 is not None else True:
                continue

            cell = cell_index.get(key0)
            mg = mg_index.get(key0)
            zone = zone_index.get(key0)
            atype = type_index.get(key0)
            action = action_index.get(key0)

            for lag in range(0, max_lag + 1):
                key = (agent_id, seed, flood_year + lag)
                tp = tp_index.get(key)
                records.append({
                    "agent_id": agent_id,
                    "seed": seed,
                    "flood_year": flood_year,
                    "lag": lag,
                    "tp": tp,
                    "cell": cell,
                    "mg_label": mg,
                    "agent_type": atype,
                    "flood_zone": zone,
                    "action_at_t0": action,
                })

    return pd.DataFrame(records)


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════
print("=" * 70)
print("WITHIN-AGENT TP DECAY BY 4-CELL (MG x TENURE)")
print("=" * 70)

print("\nLoading data...")
df = build_combined()
print(f"  Total audit rows: {len(df)}")
print(f"  Agents with valid TP: {df['tp_num'].notna().sum()}")
print(f"  Unique agents per seed: {df.groupby('seed')['agent_id'].nunique().to_dict()}")

# Find flood years per agent
flood_years_dict = find_flood_years_per_agent(df)
print(f"  Agents with at least 1 flood year: {len(flood_years_dict)}")

# Build decay windows
windows = build_decay_windows(df, flood_years_dict)
print(f"  Decay window records: {len(windows)}")
n_events = windows[windows["lag"] == 0].shape[0]
print(f"  Clean flood events (no subsequent flood in 3yr): {n_events}")

# ── ANALYSIS 1: TP Decay by 4 Cells ──
print("\n" + "=" * 70)
print("ANALYSIS 1: WITHIN-AGENT TP DECAY BY 4-CELL")
print("=" * 70)

cells = ["MG-Owner", "NMG-Owner", "MG-Renter", "NMG-Renter"]
summary_rows = []

for cell in cells:
    cw = windows[windows["cell"] == cell]
    row = {"Cell": cell}
    for lag in range(4):
        vals = cw[cw["lag"] == lag]["tp"].dropna()
        row[f"t+{lag}_mean"] = vals.mean()
        row[f"t+{lag}_std"] = vals.std()
        row[f"t+{lag}_N"] = len(vals)
    if row["t+0_mean"] and row["t+0_mean"] > 0:
        row["decay_pct"] = ((row["t+0_mean"] - row["t+3_mean"]) / row["t+0_mean"]) * 100
    else:
        row["decay_pct"] = np.nan
    summary_rows.append(row)

summary_df = pd.DataFrame(summary_rows)
print("\n  Mean TP at each lag (VL=1, L=2, M=3, H=4, VH=5):")
print("  " + "-" * 90)
print(f"  {'Cell':<14} {'t=0':>8} {'t+1':>8} {'t+2':>8} {'t+3':>8}  {'Decay%':>7}  {'N(t=0)':>7}")
print("  " + "-" * 90)
for _, r in summary_df.iterrows():
    print(f"  {r['Cell']:<14} {r['t+0_mean']:>8.3f} {r['t+1_mean']:>8.3f} {r['t+2_mean']:>8.3f} {r['t+3_mean']:>8.3f}  {r['decay_pct']:>6.1f}%  {int(r['t+0_N']):>7}")
print("  " + "-" * 90)

print("\n  N at each time point:")
for _, r in summary_df.iterrows():
    print(f"  {r['Cell']:<14}  N: t=0={int(r['t+0_N'])}, t+1={int(r['t+1_N'])}, t+2={int(r['t+2_N'])}, t+3={int(r['t+3_N'])}")

# ── ANALYSIS 2: Owner vs Renter ──
print("\n" + "=" * 70)
print("ANALYSIS 2: OWNER vs RENTER COMPARISON")
print("=" * 70)

for lag in range(4):
    owner_vals = windows[(windows["agent_type"] == "Owner") & (windows["lag"] == lag)]["tp"].dropna()
    renter_vals = windows[(windows["agent_type"] == "Renter") & (windows["lag"] == lag)]["tp"].dropna()
    print(f"  t+{lag}: Owner mean={owner_vals.mean():.3f} (N={len(owner_vals)}), "
          f"Renter mean={renter_vals.mean():.3f} (N={len(renter_vals)})")

# Mann-Whitney at t+2
owner_t2 = windows[(windows["agent_type"] == "Owner") & (windows["lag"] == 2)]["tp"].dropna()
renter_t2 = windows[(windows["agent_type"] == "Renter") & (windows["lag"] == 2)]["tp"].dropna()
if len(owner_t2) > 0 and len(renter_t2) > 0:
    u_stat, p_val = stats.mannwhitneyu(owner_t2, renter_t2, alternative="two-sided")
    print(f"\n  Mann-Whitney U at t+2: U={u_stat:.1f}, p={p_val:.4f}")
    print(f"  {'SIGNIFICANT' if p_val < 0.05 else 'NOT significant'} (alpha=0.05)")

# Owner vs Renter decay rates
owner_t0 = windows[(windows["agent_type"] == "Owner") & (windows["lag"] == 0)]["tp"].dropna().mean()
owner_t3 = windows[(windows["agent_type"] == "Owner") & (windows["lag"] == 3)]["tp"].dropna().mean()
renter_t0 = windows[(windows["agent_type"] == "Renter") & (windows["lag"] == 0)]["tp"].dropna().mean()
renter_t3 = windows[(windows["agent_type"] == "Renter") & (windows["lag"] == 3)]["tp"].dropna().mean()
print(f"\n  Owner total decay: {owner_t0:.3f} -> {owner_t3:.3f} ({(owner_t0-owner_t3)/owner_t0*100:.1f}%)")
print(f"  Renter total decay: {renter_t0:.3f} -> {renter_t3:.3f} ({(renter_t0-renter_t3)/renter_t0*100:.1f}%)")

# ── ANALYSIS 3: MG vs NMG ──
print("\n" + "=" * 70)
print("ANALYSIS 3: MG vs NMG COMPARISON")
print("=" * 70)

for lag in range(4):
    mg_vals = windows[(windows["mg_label"] == "MG") & (windows["lag"] == lag)]["tp"].dropna()
    nmg_vals = windows[(windows["mg_label"] == "NMG") & (windows["lag"] == lag)]["tp"].dropna()
    print(f"  t+{lag}: MG mean={mg_vals.mean():.3f} (N={len(mg_vals)}), "
          f"NMG mean={nmg_vals.mean():.3f} (N={len(nmg_vals)})")

mg_t2 = windows[(windows["mg_label"] == "MG") & (windows["lag"] == 2)]["tp"].dropna()
nmg_t2 = windows[(windows["mg_label"] == "NMG") & (windows["lag"] == 2)]["tp"].dropna()
if len(mg_t2) > 0 and len(nmg_t2) > 0:
    u_stat, p_val = stats.mannwhitneyu(mg_t2, nmg_t2, alternative="two-sided")
    print(f"\n  Mann-Whitney U at t+2: U={u_stat:.1f}, p={p_val:.4f}")
    print(f"  {'SIGNIFICANT' if p_val < 0.05 else 'NOT significant'} (alpha=0.05)")

mg_t0 = windows[(windows["mg_label"] == "MG") & (windows["lag"] == 0)]["tp"].dropna().mean()
mg_t3 = windows[(windows["mg_label"] == "MG") & (windows["lag"] == 3)]["tp"].dropna().mean()
nmg_t0 = windows[(windows["mg_label"] == "NMG") & (windows["lag"] == 0)]["tp"].dropna().mean()
nmg_t3 = windows[(windows["mg_label"] == "NMG") & (windows["lag"] == 3)]["tp"].dropna().mean()
print(f"\n  MG total decay: {mg_t0:.3f} -> {mg_t3:.3f} ({(mg_t0-mg_t3)/mg_t0*100:.1f}%)")
print(f"  NMG total decay: {nmg_t0:.3f} -> {nmg_t3:.3f} ({(nmg_t0-nmg_t3)/nmg_t0*100:.1f}%)")

# ── ANALYSIS 4: Flood Zone Effect ──
print("\n" + "=" * 70)
print("ANALYSIS 4: FLOOD ZONE EFFECT (HIGH vs LOW vs MEDIUM)")
print("=" * 70)

for zone in ["HIGH", "MEDIUM", "LOW"]:
    zw = windows[windows["flood_zone"] == zone]
    n_events_z = zw[zw["lag"] == 0].shape[0]
    if n_events_z == 0:
        print(f"  {zone}: No clean flood events")
        continue
    vals = []
    for lag in range(4):
        v = zw[zw["lag"] == lag]["tp"].dropna()
        vals.append(v.mean())
    decay = (vals[0] - vals[3]) / vals[0] * 100 if vals[0] > 0 else np.nan
    print(f"  {zone:<8} t=0={vals[0]:.3f}, t+1={vals[1]:.3f}, t+2={vals[2]:.3f}, t+3={vals[3]:.3f}  "
          f"Decay={decay:.1f}%  N={n_events_z}")

# HIGH vs LOW at t+2
high_t2 = windows[(windows["flood_zone"] == "HIGH") & (windows["lag"] == 2)]["tp"].dropna()
low_t2 = windows[(windows["flood_zone"] == "LOW") & (windows["lag"] == 2)]["tp"].dropna()
if len(high_t2) > 0 and len(low_t2) > 0:
    u_stat, p_val = stats.mannwhitneyu(high_t2, low_t2, alternative="two-sided")
    print(f"\n  HIGH vs LOW at t+2: U={u_stat:.1f}, p={p_val:.4f} ({'SIG' if p_val < 0.05 else 'NS'})")
else:
    print(f"\n  HIGH vs LOW at t+2: insufficient data (HIGH N={len(high_t2)}, LOW N={len(low_t2)})")

print("\n  NOTE: HIGH-zone agents flood more frequently, so 'clean' windows (no")
print("  subsequent flood in 3yr) are rarer. LOW-zone agents rarely flood at all,")
print("  so their sample may be small.")

# ── ANALYSIS 5: TP Copy-Paste Detection ──
print("\n" + "=" * 70)
print("ANALYSIS 5: TP COPY-PASTE / INERTIA DETECTION")
print("=" * 70)

# For each agent-seed, compute consecutive identical TP transitions
tp_series = df[["agent_id", "seed", "year", "tp_num", "flooded_this_year"]].dropna(subset=["tp_num"]).copy()
tp_series = tp_series.sort_values(["agent_id", "seed", "year"])

transitions = []
for (aid, s), grp in tp_series.groupby(["agent_id", "seed"]):
    grp = grp.sort_values("year")
    tps = grp["tp_num"].values
    years = grp["year"].values
    flooded = grp["flooded_this_year"].values
    for i in range(1, len(tps)):
        is_same = tps[i] == tps[i - 1]
        # Is this year post-flood? (previous year was a flood year)
        is_post_flood = flooded[i - 1] if i - 1 >= 0 else False
        transitions.append({
            "agent_id": aid,
            "seed": s,
            "year": years[i],
            "tp_same": is_same,
            "is_post_flood": is_post_flood,
        })

trans_df = pd.DataFrame(transitions)
total_trans = len(trans_df)
same_trans = trans_df["tp_same"].sum()
pct_same = same_trans / total_trans * 100

print(f"  Total year-to-year transitions: {total_trans}")
print(f"  Identical TP (t == t-1): {int(same_trans)} ({pct_same:.1f}%)")

# Break down by post-flood vs non-flood-adjacent
post_flood_trans = trans_df[trans_df["is_post_flood"] == True]
non_flood_trans = trans_df[trans_df["is_post_flood"] == False]

pf_same = post_flood_trans["tp_same"].sum() / len(post_flood_trans) * 100 if len(post_flood_trans) > 0 else 0
nf_same = non_flood_trans["tp_same"].sum() / len(non_flood_trans) * 100 if len(non_flood_trans) > 0 else 0

print(f"\n  Post-flood transitions (t+1 after flood year):")
print(f"    N={len(post_flood_trans)}, identical={pf_same:.1f}%")
print(f"  Non-flood-adjacent transitions:")
print(f"    N={len(non_flood_trans)}, identical={nf_same:.1f}%")

if pct_same > 90:
    print("\n  ** WARNING: >90% identical transitions suggests MODEL INERTIA,")
    print("     not genuine re-evaluation of threat perception. **")
elif pct_same > 70:
    print("\n  ** CAUTION: >70% identical transitions suggests moderate inertia. **")
else:
    print(f"\n  Inertia level: {'moderate' if pct_same > 50 else 'low'} ({pct_same:.1f}%)")

# Consecutive runs
print("\n  Consecutive identical TP runs (per agent-seed):")
run_lengths = []
for (aid, s), grp in tp_series.groupby(["agent_id", "seed"]):
    grp = grp.sort_values("year")
    tps = grp["tp_num"].values
    run = 1
    for i in range(1, len(tps)):
        if tps[i] == tps[i - 1]:
            run += 1
        else:
            run_lengths.append(run)
            run = 1
    run_lengths.append(run)

runs = pd.Series(run_lengths)
print(f"    Mean run length: {runs.mean():.2f}")
print(f"    Median run length: {runs.median():.1f}")
print(f"    Max run length: {runs.max()}")
print(f"    % runs >= 5 years: {(runs >= 5).sum() / len(runs) * 100:.1f}%")
print(f"    % runs == full 13 years: {(runs >= 13).sum() / len(runs) * 100:.1f}%")

# ── ANALYSIS 6: Action-Conditional TP Decay ──
print("\n" + "=" * 70)
print("ANALYSIS 6: ACTION-CONDITIONAL TP DECAY")
print("=" * 70)

# Protective actions at t=0
protective = ["buy_insurance", "elevate_house"]
passive = ["do_nothing"]

for label, action_list in [("Protective (insurance/elevation)", protective),
                           ("Do Nothing", passive)]:
    aw = windows[windows["action_at_t0"].isin(action_list)]
    n_ev = aw[aw["lag"] == 0].shape[0]
    if n_ev == 0:
        print(f"  {label}: No events")
        continue
    vals = []
    for lag in range(4):
        v = aw[aw["lag"] == lag]["tp"].dropna()
        vals.append((v.mean(), len(v)))
    decay = (vals[0][0] - vals[3][0]) / vals[0][0] * 100 if vals[0][0] > 0 else np.nan
    print(f"  {label}:")
    print(f"    t=0={vals[0][0]:.3f}(N={vals[0][1]}), t+1={vals[1][0]:.3f}(N={vals[1][1]}), "
          f"t+2={vals[2][0]:.3f}(N={vals[2][1]}), t+3={vals[3][0]:.3f}(N={vals[3][1]})")
    print(f"    3-year decay: {decay:.1f}%")

# Also check buyout
buyout_w = windows[windows["action_at_t0"] == "buyout_program"]
if len(buyout_w) > 0:
    n_ev = buyout_w[buyout_w["lag"] == 0].shape[0]
    vals = []
    for lag in range(4):
        v = buyout_w[buyout_w["lag"] == lag]["tp"].dropna()
        vals.append((v.mean(), len(v)))
    print(f"  Buyout at t=0:")
    print(f"    t=0={vals[0][0]:.3f}(N={vals[0][1]}), t+1={vals[1][0]:.3f}(N={vals[1][1]}), "
          f"t+2={vals[2][0]:.3f}(N={vals[2][1]}), t+3={vals[3][0]:.3f}(N={vals[3][1]})")

# Statistical test: protective vs do_nothing at t+2
prot_t2 = windows[(windows["action_at_t0"].isin(protective)) & (windows["lag"] == 2)]["tp"].dropna()
pass_t2 = windows[(windows["action_at_t0"].isin(passive)) & (windows["lag"] == 2)]["tp"].dropna()
if len(prot_t2) > 0 and len(pass_t2) > 0:
    u_stat, p_val = stats.mannwhitneyu(prot_t2, pass_t2, alternative="two-sided")
    print(f"\n  Protective vs Do-Nothing at t+2: U={u_stat:.1f}, p={p_val:.4f} ({'SIG' if p_val < 0.05 else 'NS'})")
    if prot_t2.mean() < pass_t2.mean():
        print("  -> Protective-action agents have LOWER TP at t+2 (risk compensation effect)")
    else:
        print("  -> Protective-action agents have HIGHER TP at t+2 (no risk compensation)")

# ── Save summary table ──
print("\n" + "=" * 70)
print("SAVING SUMMARY TABLE")
print("=" * 70)

# Build comprehensive output CSV
out_rows = []
for cell in cells:
    cw = windows[windows["cell"] == cell]
    for lag in range(4):
        vals = cw[cw["lag"] == lag]["tp"].dropna()
        out_rows.append({
            "cell": cell,
            "lag": lag,
            "mean_tp": vals.mean(),
            "std_tp": vals.std(),
            "n": len(vals),
        })

out_df = pd.DataFrame(out_rows)
out_df.to_csv(OUTPUT_TABLE, index=False)
print(f"  Saved to: {OUTPUT_TABLE}")

# Also print a pivot version
pivot = out_df.pivot(index="cell", columns="lag", values="mean_tp")
pivot.columns = [f"t+{c}" for c in pivot.columns]
print("\n  Pivot summary:")
print(pivot.to_string())

print("\n" + "=" * 70)
print("DONE")
print("=" * 70)
