"""
Fig 7: RQ3 Temporal Dynamics of Psychological Constructs
=========================================================
Analyzes SP and PA trajectories over 13 years by behavioral group,
event-aligned switching analysis, and divergence tests.
"""
import json
import os
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")

# ── Paths ──────────────────────────────────────────────────────────────
BASE = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework"
            r"\examples\multi_agent\flood\paper3\results\paper3_hybrid_v2")
SEEDS = [42, 123, 456]
MODEL = "gemma3_4b_strict"
AGENT_TYPES = ["household_owner", "household_renter"]
TABLE_OUT = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework"
                 r"\examples\multi_agent\flood\paper3\analysis\tables"
                 r"\rq3_temporal_trajectories.csv")
FIG_OUT = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework"
               r"\examples\multi_agent\flood\paper3\figures\main"
               r"\fig7_rq3_temporal_dynamics")

# ── Label map ──────────────────────────────────────────────────────────
LABEL_MAP = {"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5}
YEAR_MAP = {y: 2010 + y for y in range(1, 14)}  # year 1 -> 2011
INSURANCE_SKILLS = {"buy_insurance", "buy_contents_insurance"}

# ── Okabe-Ito colors ──────────────────────────────────────────────────
OI_ORANGE = "#E69F00"
OI_SKYBLUE = "#56B4E9"
OI_GREEN = "#009E73"
OI_VERMILLION = "#D55E00"
OI_BLUE = "#0072B2"
OI_PINK = "#CC79A7"
OI_YELLOW = "#F0E442"
OI_BLACK = "#000000"


# ======================================================================
# 1. Load and merge data
# ======================================================================
def load_audit_data():
    """Load governance audit CSVs for all seeds and agent types."""
    frames = []
    for seed in SEEDS:
        for atype in AGENT_TYPES:
            fpath = BASE / f"seed_{seed}" / MODEL / f"{atype}_governance_audit.csv"
            df = pd.read_csv(
                fpath,
                usecols=["agent_id", "year", "construct_SP_LABEL",
                          "construct_PA_LABEL", "proposed_skill", "status"],
                encoding="utf-8-sig",
            )
            df["seed"] = seed
            df["agent_type"] = atype
            df["uid"] = df["seed"].astype(str) + "_" + df["agent_id"]
            frames.append(df)
    return pd.concat(frames, ignore_index=True)


def load_flood_exposure():
    """Extract per-agent per-year flood status from JSONL traces."""
    records = []
    for seed in SEEDS:
        for atype in AGENT_TYPES:
            fpath = (BASE / f"seed_{seed}" / MODEL / "raw"
                     / f"{atype}_traces.jsonl")
            with open(fpath, encoding="utf-8") as f:
                for line in f:
                    trace = json.loads(line)
                    agent_id = trace.get("agent_id", "")
                    year = trace.get("year", 0)
                    flooded = False
                    sb = trace.get("state_before", {})
                    if sb.get("flooded_this_year", False):
                        flooded = True
                    uid = f"{seed}_{agent_id}"
                    records.append({"uid": uid, "year": year, "flooded": flooded})
    return pd.DataFrame(records)


print("Loading audit data...")
df = load_audit_data()
print(f"  Total rows: {len(df):,}, unique agents (uid): {df['uid'].nunique()}")

print("Loading flood exposure from traces...")
flood_df = load_flood_exposure()
print(f"  Flood records: {len(flood_df):,}")

# ── Derive executed action ─────────────────────────────────────────────
df["executed_action"] = np.where(
    df["status"] == "APPROVED", df["proposed_skill"], "do_nothing"
)

# ── Map construct labels to numeric ────────────────────────────────────
df["SP"] = df["construct_SP_LABEL"].map(LABEL_MAP)
df["PA"] = df["construct_PA_LABEL"].map(LABEL_MAP)

# ── Calendar year ──────────────────────────────────────────────────────
df["cal_year"] = df["year"].map(YEAR_MAP)

# ── Merge flood exposure ───────────────────────────────────────────────
flood_per_agent = (flood_df.groupby("uid")["flooded"]
                   .sum().reset_index().rename(columns={"flooded": "total_floods"}))
df = df.merge(flood_per_agent, on="uid", how="left")
df["total_floods"] = df["total_floods"].fillna(0).astype(int)


# ======================================================================
# 2. Classify agents by 13-year behavioral history
# ======================================================================
def classify_agents(df):
    agent_stats = df.groupby("uid").agg(
        insurance_years=("executed_action",
                         lambda x: x.isin(INSURANCE_SKILLS).sum()),
        donothing_years=("executed_action",
                         lambda x: (x == "do_nothing").sum()),
    ).reset_index()

    conditions = [
        agent_stats["insurance_years"] >= 7,
        agent_stats["donothing_years"] >= 9,
    ]
    choices = ["Persistent insurer", "Persistent non-actor"]
    agent_stats["group"] = np.select(conditions, choices, default="Switcher")
    return agent_stats[["uid", "group", "insurance_years", "donothing_years"]]


agent_groups = classify_agents(df)
df = df.merge(agent_groups, on="uid", how="left")

print("\n=== Agent Classification ===")
grp_counts = agent_groups["group"].value_counts()
for g, n in grp_counts.items():
    print(f"  {g}: N = {n}")
print(f"  Total: {agent_groups.shape[0]}")


# ======================================================================
# 3 & 4. SP and PA trajectories by behavioral group
# ======================================================================
def compute_trajectories(df, construct, groupcol="group"):
    """Compute mean + 95% CI per year per group."""
    rows = []
    for (grp, yr), sub in df.groupby([groupcol, "cal_year"]):
        vals = sub[construct].dropna()
        n = len(vals)
        if n == 0:
            continue
        mean = vals.mean()
        sem = vals.sem()
        ci95 = 1.96 * sem
        rows.append({
            "group": grp, "cal_year": yr, "construct": construct,
            "mean": mean, "sem": sem, "ci95_lo": mean - ci95,
            "ci95_hi": mean + ci95, "n": n
        })
    return pd.DataFrame(rows)


sp_traj = compute_trajectories(df, "SP")
pa_traj = compute_trajectories(df, "PA")

print("\n=== SP Trajectory by Group (mean per year) ===")
sp_pivot = sp_traj.pivot_table(index="cal_year", columns="group", values="mean")
print(sp_pivot.round(3).to_string())

print("\n=== PA Trajectory by Group (mean per year) ===")
pa_pivot = pa_traj.pivot_table(index="cal_year", columns="group", values="mean")
print(pa_pivot.round(3).to_string())


# ======================================================================
# 5. Event-aligned SP around insurance switch
# ======================================================================
def find_switches(df):
    """
    Find years where an agent switches TO or FROM insurance.
    Returns df with uid, switch_year, switch_type, and aligned SP values.
    """
    switch_records = []
    for uid, grp in df.groupby("uid"):
        grp = grp.sort_values("year")
        actions = grp.set_index("year")["executed_action"]
        sp_vals = grp.set_index("year")["SP"]

        for yr in range(2, 14):  # need at least year before
            prev = actions.get(yr - 1, None)
            curr = actions.get(yr, None)
            if prev is None or curr is None:
                continue

            prev_ins = prev in INSURANCE_SKILLS
            curr_ins = curr in INSURANCE_SKILLS

            if not prev_ins and curr_ins:
                stype = "Switch TO insurance"
            elif prev_ins and not curr_ins:
                stype = "Switch FROM insurance"
            else:
                continue

            # Collect SP at t-2..t+2 relative to switch year
            for offset in range(-2, 3):
                t = yr + offset
                sp = sp_vals.get(t, np.nan)
                switch_records.append({
                    "uid": uid, "switch_year": yr,
                    "switch_type": stype, "offset": offset, "SP": sp
                })
    return pd.DataFrame(switch_records)


switches = find_switches(df)
print("\n=== Switch Events ===")
if len(switches) > 0:
    sw_counts = switches.drop_duplicates(subset=["uid", "switch_year", "switch_type"])
    print(sw_counts["switch_type"].value_counts().to_string())
else:
    print("  No switch events found.")


def compute_event_aligned(switches):
    rows = []
    for (stype, offset), sub in switches.groupby(["switch_type", "offset"]):
        vals = sub["SP"].dropna()
        n = len(vals)
        if n == 0:
            continue
        mean = vals.mean()
        sem = vals.sem()
        ci95 = 1.96 * sem
        rows.append({
            "switch_type": stype, "offset": offset,
            "mean": mean, "sem": sem,
            "ci95_lo": mean - ci95, "ci95_hi": mean + ci95, "n": n
        })
    return pd.DataFrame(rows)


event_aligned = compute_event_aligned(switches)
print("\n=== Event-Aligned SP (mean at each offset) ===")
if len(event_aligned) > 0:
    ea_pivot = event_aligned.pivot_table(
        index="offset", columns="switch_type", values="mean")
    print(ea_pivot.round(3).to_string())


# ======================================================================
# 6. SP trajectory by flood exposure
# ======================================================================
df["flood_group"] = np.where(
    df["total_floods"] >= 4, "High flood (4+)",
    np.where(df["total_floods"] <= 1, "Low flood (0-1)", "Medium flood (2-3)")
)
sp_flood_traj = compute_trajectories(df, "SP", groupcol="flood_group")

print("\n=== SP by Flood Exposure ===")
flood_counts = df.drop_duplicates("uid").groupby("flood_group").size()
print(flood_counts.to_string())


# ======================================================================
# 7. Divergence test
# ======================================================================
def divergence_test(sp_traj):
    """Test if SP gap between persistent insurer and non-actor widens."""
    ins = sp_traj[sp_traj["group"] == "Persistent insurer"].set_index("cal_year")["mean"]
    non = sp_traj[sp_traj["group"] == "Persistent non-actor"].set_index("cal_year")["mean"]
    common_years = sorted(set(ins.index) & set(non.index))
    years = np.array(common_years)
    gaps = np.array([ins[y] - non[y] for y in common_years])
    slope, intercept, r, p, se = stats.linregress(years, gaps)
    return years, gaps, slope, intercept, r, p, se


years_div, gaps_div, slope, intercept, r_val, p_val, se_val = divergence_test(sp_traj)

print("\n=== Divergence Test: SP Gap (Insurer - Non-actor) ~ Year ===")
print(f"  Slope: {slope:.4f} (SE={se_val:.4f})")
print(f"  R^2: {r_val**2:.4f}")
print(f"  p-value: {p_val:.4f}")
if p_val < 0.05 and slope > 0:
    print("  Interpretation: Gap WIDENS significantly -> feedback amplifies differences")
elif p_val < 0.05 and slope < 0:
    print("  Interpretation: Gap NARROWS significantly -> convergence")
else:
    print("  Interpretation: No significant trend -> pure selection (parallel trajectories)")

for y, g in zip(years_div, gaps_div):
    print(f"  {int(y)}: gap = {g:.3f}")


# ======================================================================
# 8. Save table
# ======================================================================
# Combine all trajectory data
all_traj = pd.concat([
    sp_traj.assign(analysis="SP_by_behavior_group"),
    pa_traj.assign(analysis="PA_by_behavior_group"),
    sp_flood_traj.assign(analysis="SP_by_flood_exposure"),
], ignore_index=True)

if len(event_aligned) > 0:
    ea_out = event_aligned.rename(columns={"switch_type": "group", "offset": "cal_year"})
    ea_out["construct"] = "SP"
    ea_out["analysis"] = "event_aligned_switch"
    all_traj = pd.concat([all_traj, ea_out], ignore_index=True)

# Add divergence data
div_rows = []
for y, g in zip(years_div, gaps_div):
    div_rows.append({
        "group": "insurer_minus_nonactor", "cal_year": int(y),
        "construct": "SP_gap", "mean": g, "analysis": "divergence_test"
    })
div_df = pd.DataFrame(div_rows)
all_traj = pd.concat([all_traj, div_df], ignore_index=True)

all_traj.to_csv(TABLE_OUT, index=False)
print(f"\nTable saved to: {TABLE_OUT}")


# ======================================================================
# 9. Figure
# ======================================================================
fig, axes = plt.subplots(2, 2, figsize=(6.85, 5.5))
fig.subplots_adjust(hspace=0.38, wspace=0.32, top=0.94, bottom=0.10,
                    left=0.10, right=0.97)

GROUP_COLORS = {
    "Persistent insurer": OI_ORANGE,
    "Persistent non-actor": OI_SKYBLUE,
    "Switcher": OI_GREEN,
}
GROUP_ORDER = ["Persistent insurer", "Switcher", "Persistent non-actor"]
PANEL_LABELS = ["(a)", "(b)", "(c)", "(d)"]

# ── Panel (a): SP by behavioral group ─────────────────────────────────
ax = axes[0, 0]
for grp in GROUP_ORDER:
    sub = sp_traj[sp_traj["group"] == grp].sort_values("cal_year")
    if len(sub) == 0:
        continue
    ax.plot(sub["cal_year"], sub["mean"], "-o", color=GROUP_COLORS[grp],
            label=grp, markersize=3, linewidth=1.3)
    ax.fill_between(sub["cal_year"], sub["ci95_lo"], sub["ci95_hi"],
                    color=GROUP_COLORS[grp], alpha=0.15)
ax.set_xlabel("Year", fontsize=8)
ax.set_ylabel("Mean SP (1=VL, 5=VH)", fontsize=8)
ax.set_title("SP trajectory by behavioral group", fontsize=8.5, fontweight="bold")
ax.legend(fontsize=6.5, loc="best", framealpha=0.8)
ax.set_xlim(2011, 2023)
ax.xaxis.set_major_locator(mticker.MultipleLocator(2))
ax.tick_params(labelsize=7)
ax.text(0.02, 0.97, PANEL_LABELS[0], transform=ax.transAxes,
        fontsize=9, fontweight="bold", va="top")

# ── Panel (b): PA by behavioral group ─────────────────────────────────
ax = axes[0, 1]
for grp in GROUP_ORDER:
    sub = pa_traj[pa_traj["group"] == grp].sort_values("cal_year")
    if len(sub) == 0:
        continue
    ax.plot(sub["cal_year"], sub["mean"], "-o", color=GROUP_COLORS[grp],
            label=grp, markersize=3, linewidth=1.3)
    ax.fill_between(sub["cal_year"], sub["ci95_lo"], sub["ci95_hi"],
                    color=GROUP_COLORS[grp], alpha=0.15)
ax.set_xlabel("Year", fontsize=8)
ax.set_ylabel("Mean PA (1=VL, 5=VH)", fontsize=8)
ax.set_title("PA trajectory by behavioral group", fontsize=8.5, fontweight="bold")
ax.legend(fontsize=6.5, loc="best", framealpha=0.8)
ax.set_xlim(2011, 2023)
ax.xaxis.set_major_locator(mticker.MultipleLocator(2))
ax.tick_params(labelsize=7)
ax.text(0.02, 0.97, PANEL_LABELS[1], transform=ax.transAxes,
        fontsize=9, fontweight="bold", va="top")

# ── Panel (c): Event-aligned SP around switch ─────────────────────────
ax = axes[1, 0]
SWITCH_COLORS = {
    "Switch TO insurance": OI_VERMILLION,
    "Switch FROM insurance": OI_BLUE,
}
if len(event_aligned) > 0:
    for stype, color in SWITCH_COLORS.items():
        sub = event_aligned[event_aligned["switch_type"] == stype].sort_values("offset")
        if len(sub) == 0:
            continue
        ax.plot(sub["offset"], sub["mean"], "-o", color=color,
                label=stype, markersize=4, linewidth=1.3)
        ax.fill_between(sub["offset"], sub["ci95_lo"], sub["ci95_hi"],
                        color=color, alpha=0.15)
    ax.axvline(0, color="gray", linestyle="--", linewidth=0.8, alpha=0.6)
    ax.legend(fontsize=6.5, loc="best", framealpha=0.8)
ax.set_xlabel("Years relative to switch (t=0)", fontsize=8)
ax.set_ylabel("Mean SP", fontsize=8)
ax.set_title("SP around insurance switch events", fontsize=8.5, fontweight="bold")
ax.set_xlim(-2.5, 2.5)
ax.xaxis.set_major_locator(mticker.MultipleLocator(1))
ax.tick_params(labelsize=7)
ax.text(0.02, 0.97, PANEL_LABELS[2], transform=ax.transAxes,
        fontsize=9, fontweight="bold", va="top")

# ── Panel (d): Divergence test ─────────────────────────────────────────
ax = axes[1, 1]
ax.plot(years_div, gaps_div, "o-", color=OI_BLACK, markersize=4, linewidth=1.3,
        label="SP gap (insurer - non-actor)")
# Regression line
reg_line = intercept + slope * years_div
ax.plot(years_div, reg_line, "--", color=OI_VERMILLION, linewidth=1.2,
        label=f"OLS: slope={slope:.3f}, p={p_val:.3f}")
ax.axhline(0, color="gray", linestyle=":", linewidth=0.7, alpha=0.5)
ax.set_xlabel("Year", fontsize=8)
ax.set_ylabel("SP gap (insurer - non-actor)", fontsize=8)
ax.set_title("SP divergence test", fontsize=8.5, fontweight="bold")
ax.legend(fontsize=6.5, loc="best", framealpha=0.8)
ax.set_xlim(2011, 2023)
ax.xaxis.set_major_locator(mticker.MultipleLocator(2))
ax.tick_params(labelsize=7)
ax.text(0.02, 0.97, PANEL_LABELS[3], transform=ax.transAxes,
        fontsize=9, fontweight="bold", va="top")

# ── Save ───────────────────────────────────────────────────────────────
fig.savefig(str(FIG_OUT) + ".png", dpi=300, bbox_inches="tight")
fig.savefig(str(FIG_OUT) + ".pdf", bbox_inches="tight")
print(f"Figure saved to: {FIG_OUT}.png and .pdf")
plt.close()
print("\nDone.")
