"""
Within-agent longitudinal TP decay analysis.

The existing rq3_tp_decay.csv is CROSS-SECTIONAL (groups all decisions by
years_since_flood). This could be confounded by agent selection: agents who
haven't flooded in 4+ years may be in LOW flood zones with naturally lower TP.

This script tracks individual agents THROUGH TIME after flood events to
measure true within-agent TP decay.

Data sources:
  - Governance audit CSV: agent_id, year, construct_TP_LABEL
  - JSONL traces: state_after.flooded_this_year (per-agent flood indicator)

Output: tables/rq1_tp_decay_within_agent.csv
"""

import json
import os
import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats

_PAPER3_OVERRIDE = os.environ.get("PAPER3_TRACE_DIR")
_PAPER3_OUTPUT_OVERRIDE = os.environ.get("PAPER3_OUTPUT_DIR")

# ── Config ──────────────────────────────────────────────────────────────
if _PAPER3_OVERRIDE:
    _TRACE_DIR = Path(os.path.normpath(_PAPER3_OVERRIDE))
    BASE = _TRACE_DIR.parent.parent
    SEEDS = [_TRACE_DIR.parent.name]
    MODEL = _TRACE_DIR.name
else:
    BASE = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework"
                r"\examples\multi_agent\flood\paper3\results\paper3_hybrid_v2")
    SEEDS = ["seed_42", "seed_123", "seed_456"]
    MODEL = "gemma3_4b_strict"
AGENT_TYPES = ["household_owner", "household_renter"]
TP_MAP = {"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5}
OUT_DIR = Path(os.path.normpath(_PAPER3_OUTPUT_OVERRIDE)) if _PAPER3_OUTPUT_OVERRIDE else BASE.parent.parent / "analysis" / "tables"
MAX_WINDOW = 4  # track t=0 through t+3 (4 time points)


# ── Step 1: Load audit CSV + JSONL flood data ──────────────────────────
def load_seed_data(seed: str) -> pd.DataFrame:
    """Load and merge audit CSV with JSONL flood flags for one seed."""
    frames = []
    for atype in AGENT_TYPES:
        # Audit CSV
        audit_path = BASE / seed / MODEL / f"{atype}_governance_audit.csv"
        if not audit_path.exists():
            print(f"  SKIP (no file): {audit_path}")
            continue
        df = pd.read_csv(audit_path, encoding="utf-8-sig",
                         usecols=["agent_id", "year", "construct_TP_LABEL"])
        df = df.rename(columns={"construct_TP_LABEL": "tp_label"})
        df["tp_num"] = df["tp_label"].map(TP_MAP)

        # JSONL traces → extract flooded_this_year per (agent_id, year)
        jsonl_path = BASE / seed / MODEL / "raw" / f"{atype}_traces.jsonl"
        flood_records = []
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                sa = rec.get("state_after", {})
                flood_records.append({
                    "agent_id": rec["agent_id"],
                    "year": rec["year"],
                    "flooded_this_year": sa.get("flooded_this_year", False),
                    "flood_zone": sa.get("flood_zone", ""),
                    "relocated": sa.get("relocated", False),
                })
        flood_df = pd.DataFrame(flood_records)
        # De-dup: take last trace per (agent_id, year) — retries may exist
        flood_df = flood_df.drop_duplicates(
            subset=["agent_id", "year"], keep="last"
        )

        df = df.merge(flood_df, on=["agent_id", "year"], how="left")
        df["seed"] = seed
        df["agent_type"] = atype
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


print("Loading data from 3 seeds...")
all_data = pd.concat([load_seed_data(s) for s in SEEDS], ignore_index=True)
print(f"  Total rows: {len(all_data):,}")
print(f"  Unique agents: {all_data.groupby(['seed','agent_id']).ngroups}")
print(f"  TP distribution: {all_data['tp_label'].value_counts().to_dict()}")
# Drop rows with missing TP
all_data = all_data.dropna(subset=["tp_num"])
# Exclude relocated agents (they exit the model)
all_data = all_data[all_data["relocated"] != True]
print(f"  After dropping NaN TP + relocated: {len(all_data):,} rows")

# ── Step 2: Identify flood events per agent ─────────────────────────────
def get_flood_years(agent_df: pd.DataFrame) -> list:
    """Return sorted list of years this agent was flooded."""
    return sorted(
        agent_df.loc[agent_df["flooded_this_year"] == True, "year"].tolist()
    )


# ── Analysis 1: Within-agent TP trajectory after flood (clean windows) ──
print("\n" + "=" * 70)
print("ANALYSIS 1: Within-agent TP trajectory after flood events")
print("         (clean windows — no subsequent flood in tracking period)")
print("=" * 70)

trajectories = []  # list of dicts: {flood_year, t, tp_num, agent_id, ...}

for (seed, agent_id), grp in all_data.groupby(["seed", "agent_id"]):
    grp = grp.sort_values("year")
    flood_years = get_flood_years(grp)
    tp_by_year = grp.set_index("year")["tp_num"].to_dict()

    for fy in flood_years:
        # Check if there's a clean window: no flood in [fy+1, fy+3]
        subsequent_floods = [y for y in flood_years if fy < y <= fy + MAX_WINDOW - 1]
        window_length = MAX_WINDOW
        if subsequent_floods:
            # Truncate window before next flood
            window_length = min(subsequent_floods) - fy
        if window_length < 2:
            continue  # Need at least t=0 and t+1

        for t in range(window_length):
            yr = fy + t
            if yr in tp_by_year:
                trajectories.append({
                    "seed": seed,
                    "agent_id": agent_id,
                    "flood_year": fy,
                    "t": t,
                    "year": yr,
                    "tp_num": tp_by_year[yr],
                    "clean_window": window_length,
                })

traj_df = pd.DataFrame(trajectories)
print(f"\n  Trajectory observations: {len(traj_df):,}")
print(f"  Unique flood events tracked: "
      f"{traj_df.groupby(['seed','agent_id','flood_year']).ngroups}")

# Mean TP at each t offset
within_agent_decay = traj_df.groupby("t").agg(
    n=("tp_num", "count"),
    mean_tp=("tp_num", "mean"),
    std_tp=("tp_num", "std"),
    median_tp=("tp_num", "median"),
).reset_index()
within_agent_decay["decay_pct"] = (
    (1 - within_agent_decay["mean_tp"] / within_agent_decay["mean_tp"].iloc[0]) * 100
).round(1)

print("\n  Within-agent TP decay (clean windows):")
print(within_agent_decay.to_string(index=False))

# ── Analysis 1b: Only agents with FULL 4-year clean windows ─────────────
print("\n--- Subset: only full 4-year clean windows ---")
full_window = traj_df[traj_df["clean_window"] >= MAX_WINDOW]
if len(full_window) > 0:
    full_decay = full_window.groupby("t").agg(
        n=("tp_num", "count"),
        mean_tp=("tp_num", "mean"),
        std_tp=("tp_num", "std"),
    ).reset_index()
    full_decay["decay_pct"] = (
        (1 - full_decay["mean_tp"] / full_decay["mean_tp"].iloc[0]) * 100
    ).round(1)
    print(full_decay.to_string(index=False))
else:
    print("  No agents with full 4-year clean windows.")

# ── Analysis 2: Paired comparison ───────────────────────────────────────
print("\n" + "=" * 70)
print("ANALYSIS 2: Paired within-agent comparison (flood year vs post-flood)")
print("=" * 70)

# For each (agent, flood_event), compute TP at t=0 and mean TP at t>0
paired_data = []
for (seed, agent_id, fy), subdf in traj_df.groupby(
    ["seed", "agent_id", "flood_year"]
):
    tp_at_flood = subdf.loc[subdf["t"] == 0, "tp_num"]
    tp_post = subdf.loc[subdf["t"] > 0, "tp_num"]
    if len(tp_at_flood) == 1 and len(tp_post) >= 1:
        paired_data.append({
            "seed": seed,
            "agent_id": agent_id,
            "flood_year": fy,
            "tp_at_flood": tp_at_flood.values[0],
            "tp_post_mean": tp_post.mean(),
            "tp_post_min": tp_post.min(),
            "n_post_years": len(tp_post),
        })

paired_df = pd.DataFrame(paired_data)
paired_df["tp_change"] = paired_df["tp_post_mean"] - paired_df["tp_at_flood"]

print(f"\n  Paired flood events: {len(paired_df)}")
print(f"  Mean TP at flood:  {paired_df['tp_at_flood'].mean():.3f}")
print(f"  Mean TP post-flood: {paired_df['tp_post_mean'].mean():.3f}")
print(f"  Mean change:       {paired_df['tp_change'].mean():.3f}")

# Direction of change
n_decay = (paired_df["tp_change"] < 0).sum()
n_same = (paired_df["tp_change"] == 0).sum()
n_increase = (paired_df["tp_change"] > 0).sum()
print(f"  Decay: {n_decay} ({n_decay/len(paired_df)*100:.1f}%)")
print(f"  Same:  {n_same} ({n_same/len(paired_df)*100:.1f}%)")
print(f"  Increase: {n_increase} ({n_increase/len(paired_df)*100:.1f}%)")

# Paired t-test
if len(paired_df) > 1:
    t_stat, p_val = stats.ttest_rel(
        paired_df["tp_at_flood"], paired_df["tp_post_mean"]
    )
    print(f"  Paired t-test: t={t_stat:.3f}, p={p_val:.4f}")

# Wilcoxon signed-rank test (non-parametric)
diffs = paired_df["tp_at_flood"] - paired_df["tp_post_mean"]
diffs_nonzero = diffs[diffs != 0]
if len(diffs_nonzero) > 10:
    w_stat, w_p = stats.wilcoxon(diffs_nonzero)
    print(f"  Wilcoxon signed-rank: W={w_stat:.1f}, p={w_p:.4f}")

# Monotonicity check
print("\n  --- Monotonicity of decay ---")
for t in range(1, MAX_WINDOW):
    subset = traj_df[traj_df["t"].isin([t - 1, t])]
    if len(subset) == 0:
        continue
    pivot = subset.pivot_table(
        values="tp_num", index=["seed", "agent_id", "flood_year"],
        columns="t", aggfunc="first"
    ).dropna()
    if t - 1 in pivot.columns and t in pivot.columns:
        diff = pivot[t] - pivot[t - 1]
        n_down = (diff < 0).sum()
        n_eq = (diff == 0).sum()
        n_up = (diff > 0).sum()
        n_tot = len(diff)
        print(f"  t={t-1}→t={t}: down={n_down}({n_down/n_tot*100:.0f}%), "
              f"same={n_eq}({n_eq/n_tot*100:.0f}%), "
              f"up={n_up}({n_up/n_tot*100:.0f}%) [n={n_tot}]")

# ── Analysis 3: Compare with cross-sectional ───────────────────────────
print("\n" + "=" * 70)
print("ANALYSIS 3: Within-agent vs cross-sectional comparison")
print("=" * 70)

# Cross-sectional reference from rq3_tp_decay.csv
cross_sectional = {0: 3.919, 1: 3.631, 2: 3.618, 3: 3.568}
# 4+ bucket maps to t=4 roughly
cross_sectional_4plus = 3.506

print(f"\n  {'t':>4s} | {'Within-agent':>14s} | {'Cross-sectional':>16s} | {'Difference':>12s}")
print("  " + "-" * 55)
for _, row in within_agent_decay.iterrows():
    t = int(row["t"])
    wa = row["mean_tp"]
    cs = cross_sectional.get(t, None)
    if cs is not None:
        diff = wa - cs
        print(f"  {t:4d} | {wa:14.3f} | {cs:16.3f} | {diff:12.3f}")
    else:
        print(f"  {t:4d} | {wa:14.3f} | {'N/A':>16s} |")

print("\n  Interpretation:")
if len(within_agent_decay) >= 2:
    wa_decay_total = within_agent_decay.iloc[0]["mean_tp"] - within_agent_decay.iloc[-1]["mean_tp"]
    cs_decay_total = cross_sectional[0] - cross_sectional_4plus
    print(f"    Within-agent total decay (t=0→t={int(within_agent_decay.iloc[-1]['t'])}): "
          f"{wa_decay_total:.3f}")
    print(f"    Cross-sectional total decay (0→4+): {cs_decay_total:.3f}")
    if abs(wa_decay_total) < abs(cs_decay_total):
        print("    → Cross-sectional OVERESTIMATES decay (selection bias likely)")
    else:
        print("    → Within-agent decay is STRONGER than cross-sectional")

# ── Analysis 4: LLM vs Traditional ABM decay rate ──────────────────────
print("\n" + "=" * 70)
print("ANALYSIS 4: LLM decay rate vs Traditional ABM formula")
print("           Traditional: TP' = TP × exp(-ln2 × w × Eff)")
print("=" * 70)

# Fit exponential decay: TP(t) = TP(0) * exp(-lambda * t)
if len(within_agent_decay) >= 2:
    t_vals = within_agent_decay["t"].values.astype(float)
    tp_vals = within_agent_decay["mean_tp"].values

    # Normalize: ratio = TP(t)/TP(0)
    tp0 = tp_vals[0]
    ratios = tp_vals / tp0

    # Log-linear fit: ln(ratio) = -lambda * t
    # Exclude t=0
    mask = t_vals > 0
    if mask.sum() >= 1:
        log_ratios = np.log(ratios[mask])
        t_fit = t_vals[mask]

        if len(t_fit) >= 2:
            slope, intercept, r_val, p_val, std_err = stats.linregress(
                t_fit, log_ratios
            )
            llm_lambda = -slope
        else:
            # Only one post-flood point
            llm_lambda = -log_ratios[0] / t_fit[0]
            r_val = 1.0

        print(f"\n  LLM exponential decay rate (lambda): {llm_lambda:.4f}")
        print(f"  LLM half-life: {np.log(2) / llm_lambda:.1f} years"
              if llm_lambda > 0 else "  No decay detected")
        if len(t_fit) >= 2:
            print(f"  R-squared: {r_val**2:.3f}")

        # Traditional ABM: typical w=0.5, Eff=0.3-0.5
        # TP' = TP * exp(-ln2 * w * Eff)
        # Per year: decay_factor = exp(-ln2 * w * Eff)
        # lambda_trad = ln2 * w * Eff
        print("\n  Traditional ABM comparison (TP' = TP × exp(-ln2 × w × Eff)):")
        for w, eff in [(0.3, 0.3), (0.5, 0.3), (0.5, 0.5), (0.7, 0.5)]:
            trad_lambda = np.log(2) * w * eff
            trad_4yr_decay = (1 - np.exp(-trad_lambda * 4)) * 100
            print(f"    w={w}, Eff={eff}: lambda={trad_lambda:.4f}, "
                  f"4yr decay={trad_4yr_decay:.1f}%")

        llm_4yr_decay = (1 - np.exp(-llm_lambda * 4)) * 100 if llm_lambda > 0 else 0
        print(f"\n  LLM 4yr decay: {llm_4yr_decay:.1f}%")
        print(f"  Traditional range: ~6% (conservative) to ~50% (aggressive)")

        # Equivalent w*Eff for LLM
        if llm_lambda > 0:
            equiv_weff = llm_lambda / np.log(2)
            print(f"  LLM equivalent w×Eff: {equiv_weff:.3f}")

# ── Analysis 5: Breakdown by flood zone ─────────────────────────────────
print("\n" + "=" * 70)
print("ANALYSIS 5: Within-agent decay by flood zone")
print("=" * 70)

if "flood_zone" in traj_df.columns:
    # Merge flood zone info
    zone_info = all_data[["seed", "agent_id", "year", "flood_zone"]].drop_duplicates()
    traj_with_zone = traj_df.merge(
        zone_info.rename(columns={"year": "year"}),
        on=["seed", "agent_id", "year"], how="left"
    )
    # Use flood_year's zone
    flood_zone_map = traj_with_zone[traj_with_zone["t"] == 0][
        ["seed", "agent_id", "flood_year", "flood_zone"]
    ].drop_duplicates()
    traj_with_zone = traj_with_zone.drop(columns=["flood_zone"]).merge(
        flood_zone_map, on=["seed", "agent_id", "flood_year"], how="left"
    )

    for zone in sorted(traj_with_zone["flood_zone"].dropna().unique()):
        z_df = traj_with_zone[traj_with_zone["flood_zone"] == zone]
        z_decay = z_df.groupby("t").agg(
            n=("tp_num", "count"),
            mean_tp=("tp_num", "mean"),
        ).reset_index()
        if len(z_decay) >= 2:
            z_decay["decay_pct"] = (
                (1 - z_decay["mean_tp"] / z_decay["mean_tp"].iloc[0]) * 100
            ).round(1)
            print(f"\n  {zone} zone:")
            print(z_decay.to_string(index=False))

# ── Analysis 6: TP transition matrix after flood ───────────────────────
print("\n" + "=" * 70)
print("ANALYSIS 6: TP transition matrix (t=0 → t+1)")
print("=" * 70)

t0_t1 = traj_df[traj_df["t"].isin([0, 1])].pivot_table(
    values="tp_num", index=["seed", "agent_id", "flood_year"],
    columns="t", aggfunc="first"
).dropna()
if len(t0_t1) > 0:
    t0_t1.columns = ["tp_t0", "tp_t1"]
    t0_t1 = t0_t1.reset_index()

    # Map back to labels
    inv_map = {v: k for k, v in TP_MAP.items()}
    t0_t1["label_t0"] = t0_t1["tp_t0"].map(inv_map)
    t0_t1["label_t1"] = t0_t1["tp_t1"].map(inv_map)

    trans = pd.crosstab(t0_t1["label_t0"], t0_t1["label_t1"], margins=True)
    print("\n  Transition counts (row=t0, col=t+1):")
    print(trans.to_string())

    trans_pct = pd.crosstab(
        t0_t1["label_t0"], t0_t1["label_t1"], normalize="index"
    ).round(3) * 100
    print("\n  Transition % (row-normalized):")
    print(trans_pct.to_string())


# ── Save output CSV ─────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SAVING OUTPUT")
print("=" * 70)

# Build comprehensive output table
out_rows = []

# Within-agent decay
for _, row in within_agent_decay.iterrows():
    out_rows.append({
        "analysis": "within_agent_all",
        "t": int(row["t"]),
        "n": int(row["n"]),
        "mean_tp": round(row["mean_tp"], 3),
        "std_tp": round(row["std_tp"], 3),
        "median_tp": round(row["median_tp"], 3),
        "decay_pct": round(row["decay_pct"], 1),
    })

# Full 4-year window only
if len(full_window) > 0:
    for _, row in full_decay.iterrows():
        out_rows.append({
            "analysis": "within_agent_full4yr",
            "t": int(row["t"]),
            "n": int(row["n"]),
            "mean_tp": round(row["mean_tp"], 3),
            "std_tp": round(row["std_tp"], 3),
            "decay_pct": round(row["decay_pct"], 1),
        })

# Cross-sectional reference
for t_val, cs_val in cross_sectional.items():
    out_rows.append({
        "analysis": "cross_sectional_ref",
        "t": t_val,
        "mean_tp": cs_val,
    })

out_df = pd.DataFrame(out_rows)
out_path = OUT_DIR / "rq1_tp_decay_within_agent.csv"
out_df.to_csv(out_path, index=False)
print(f"\n  Saved to: {out_path}")

# ── Summary ─────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"""
Key findings:
  1. Within-agent tracking: {traj_df.groupby(['seed','agent_id','flood_year']).ngroups}
     flood events tracked across {all_data.groupby(['seed','agent_id']).ngroups} agents (3 seeds)
  2. Mean TP at flood (t=0): {within_agent_decay.iloc[0]['mean_tp']:.3f}
  3. Mean TP at t+1:         {within_agent_decay.iloc[1]['mean_tp']:.3f}
  4. Paired comparison: {n_decay} decay, {n_same} same, {n_increase} increase
  5. LLM 4yr decay:    {llm_4yr_decay:.1f}% (equiv w×Eff={equiv_weff:.3f})
  6. Traditional ABM:   6-50% over 4 years (typical ~20-30%)
""")
