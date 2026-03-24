#!/usr/bin/env python3
"""
RQ2 Equity Figure: Publication-quality 2x2 figure emphasizing the equity channel.

Panel (a): Policy trajectory — Full (endogenous) vs Flat (fixed) subsidy + CRS
Panel (b): Affordability blocking by MG status — PRIMARY result
Panel (c): MG owner action distribution — Full vs Flat
Panel (d): NMG owner action distribution — Full vs Flat

Pools 3 seeds (42, 123, 456) for both Full and Flat conditions.
"""

import json
import os
import sys
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

warnings.filterwarnings("ignore", category=FutureWarning)

# ---------------------------------------------------------------------------
# Safe print for cp950 console
# ---------------------------------------------------------------------------
_orig_print = print
def safe_print(*args, **kwargs):
    try:
        _orig_print(*args, **kwargs)
    except (UnicodeEncodeError, UnicodeDecodeError):
        text = " ".join(str(a) for a in args)
        _orig_print(text.encode("ascii", errors="replace").decode(), **kwargs)

print = safe_print

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE = r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\multi_agent\flood"
SEEDS = [42, 123, 456]

FULL_DIR_TPL = os.path.join(BASE, "paper3", "results", "paper3_hybrid_v2",
                            "seed_{seed}", "gemma3_4b_strict")
FLAT_DIR_TPL = os.path.join(BASE, "paper3", "results", "paper3_ablation_flat_baseline",
                            "seed_{seed}", "gemma3_4b_strict")

PROFILES_PATH = os.path.join(BASE, "data", "agent_profiles_balanced.csv")

OUTPUT_DIR = os.path.join(BASE, "paper3", "results", "paper3_hybrid_v2", "analysis")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TABLES_DIR = os.path.join(BASE, "paper3", "analysis", "tables")
os.makedirs(TABLES_DIR, exist_ok=True)

OUTPUT_FIG = os.path.join(OUTPUT_DIR, "rq2_equity_figure.png")
OUTPUT_CSV = os.path.join(TABLES_DIR, "rq2_equity_summary.csv")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_jsonl(path):
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load_audit_csv(path):
    return pd.read_csv(path, encoding="utf-8-sig")


def load_profiles():
    df = pd.read_csv(PROFILES_PATH, encoding="utf-8")
    # MG lookup: agent_id -> bool
    return dict(zip(df["agent_id"], df["mg"]))


def extract_gov_policy(traces):
    """Extract subsidy trajectory from government traces."""
    skill_map = {
        "large_increase_subsidy": +5.0,
        "small_increase_subsidy": +2.5,
        "maintain_subsidy": 0.0,
        "small_decrease_subsidy": -2.5,
        "large_decrease_subsidy": -5.0,
    }
    years = sorted(set(t["year"] for t in traces))
    subsidy = 50.0  # start
    trajectory = {}
    for y in years:
        year_traces = [t for t in traces if t["year"] == y]
        if year_traces:
            t = year_traces[0]
            # Try skill_proposal first, then approved_skill
            skill_name = None
            if "skill_proposal" in t and t["skill_proposal"]:
                sp = t["skill_proposal"]
                if isinstance(sp, dict):
                    skill_name = sp.get("skill_name")
            if skill_name is None and "approved_skill" in t and t["approved_skill"]:
                ask = t["approved_skill"]
                if isinstance(ask, dict):
                    skill_name = ask.get("skill_name") or ask.get("mapping")
            if skill_name and skill_name in skill_map:
                subsidy += skill_map[skill_name]
            # Also check environment_context for actual subsidy_rate
            ec = t.get("environment_context", {})
            if ec and "subsidy_rate" in ec:
                subsidy = ec["subsidy_rate"] * 100.0
        trajectory[y] = subsidy
    return trajectory


def extract_ins_policy(traces):
    """Extract CRS discount trajectory from insurance traces."""
    skill_map = {
        "improve_crs": +5.0,
        "reduce_crs": -5.0,
        "maintain_crs": 0.0,
    }
    years = sorted(set(t["year"] for t in traces))
    crs = 15.0  # start
    trajectory = {}
    for y in years:
        year_traces = [t for t in traces if t["year"] == y]
        if year_traces:
            t = year_traces[0]
            skill_name = None
            if "skill_proposal" in t and t["skill_proposal"]:
                sp = t["skill_proposal"]
                if isinstance(sp, dict):
                    skill_name = sp.get("skill_name")
            if skill_name is None and "approved_skill" in t and t["approved_skill"]:
                ask = t["approved_skill"]
                if isinstance(ask, dict):
                    skill_name = ask.get("skill_name") or ask.get("mapping")
            if skill_name and skill_name in skill_map:
                crs += skill_map[skill_name]
            # Also check environment_context for actual crs_discount
            ec = t.get("environment_context", {})
            if ec and "crs_discount" in ec:
                crs = ec["crs_discount"] * 100.0
        trajectory[y] = crs
    return trajectory


def classify_action(proposed_skill, final_skill, status):
    """Map skills to action categories: FI, EH, BP, DN."""
    status_upper = str(status).strip().upper()
    if status_upper in ("APPROVED", "ACCEPTED"):
        skill = proposed_skill
    else:
        skill = "do_nothing"

    mapping = {
        "buy_insurance": "FI",
        "buy_flood_insurance": "FI",
        "flood_insurance": "FI",
        "purchase_insurance": "FI",
        "elevate_house": "EH",
        "buyout_program": "BP",
        "buyout": "BP",
        "accept_buyout": "BP",
        "do_nothing": "DN",
    }
    s_lower = str(skill).lower().strip()
    for k, v in mapping.items():
        if k in s_lower:
            return v
    return "DN"


def get_executed_action(row):
    """Get the EXECUTED action from audit row."""
    status = str(row.get("status", "")).strip().upper()
    proposed = str(row.get("proposed_skill", "")).strip()

    if status in ("APPROVED", "ACCEPTED"):
        skill = proposed
    else:
        skill = "do_nothing"  # REJECTED -> fallback

    mapping = {
        "buy_insurance": "FI",
        "buy_flood_insurance": "FI",
        "flood_insurance": "FI",
        "purchase_insurance": "FI",
        "elevate_house": "EH",
        "buyout_program": "BP",
        "buyout": "BP",
        "accept_buyout": "BP",
        "do_nothing": "DN",
    }
    s_lower = skill.lower()
    for k, v in mapping.items():
        if k in s_lower:
            return v
    return "DN"


def has_affordability_block(error_messages):
    """Check if rejection includes an affordability-related rule."""
    if pd.isna(error_messages) or not error_messages:
        return False
    msg = str(error_messages).upper()
    return "AFFORDABILITY" in msg


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
print("Loading agent profiles...")
mg_lookup = load_profiles()

# -- Panel (a): Policy trajectories (Full only - Flat is constant) ----------
print("Loading government and insurance traces for Full condition...")
all_gov_subsidy = {}  # year -> list of values across seeds
all_gov_crs = {}

for seed in SEEDS:
    full_dir = FULL_DIR_TPL.format(seed=seed)
    raw_dir = os.path.join(full_dir, "raw")

    gov_path = os.path.join(raw_dir, "government_traces.jsonl")
    ins_path = os.path.join(raw_dir, "insurance_traces.jsonl")

    if os.path.exists(gov_path):
        gov_traces = load_jsonl(gov_path)
        sub_traj = extract_gov_policy(gov_traces)
        for y, v in sub_traj.items():
            all_gov_subsidy.setdefault(y, []).append(v)

    if os.path.exists(ins_path):
        ins_traces = load_jsonl(ins_path)
        crs_traj = extract_ins_policy(ins_traces)
        for y, v in crs_traj.items():
            all_gov_crs.setdefault(y, []).append(v)

# Compute mean + std across seeds
years = sorted(all_gov_subsidy.keys())
subsidy_mean = [np.mean(all_gov_subsidy[y]) for y in years]
subsidy_std = [np.std(all_gov_subsidy[y]) for y in years]
crs_mean = [np.mean(all_gov_crs.get(y, [15.0])) for y in years]
crs_std = [np.std(all_gov_crs.get(y, [15.0])) for y in years]

# Flat baseline: constant 50% subsidy, 0% CRS
flat_subsidy = [50.0] * len(years)
flat_crs = [0.0] * len(years)

print(f"  Years: {years}")
print(f"  Full subsidy (mean): {[f'{v:.1f}' for v in subsidy_mean]}")
print(f"  Full CRS (mean):     {[f'{v:.1f}' for v in crs_mean]}")

# -- Panels (b)(c)(d): Audit data ------------------------------------------
print("\nLoading governance audit data (3 seeds x 2 conditions)...")

full_audits = []
flat_audits = []

for seed in SEEDS:
    # Full
    full_dir = FULL_DIR_TPL.format(seed=seed)
    audit_path = os.path.join(full_dir, "household_owner_governance_audit.csv")
    if os.path.exists(audit_path):
        df = load_audit_csv(audit_path)
        df["seed"] = seed
        df["condition"] = "Full"
        full_audits.append(df)
    else:
        print(f"  WARNING: Missing {audit_path}")

    # Flat
    flat_dir = FLAT_DIR_TPL.format(seed=seed)
    audit_path = os.path.join(flat_dir, "household_owner_governance_audit.csv")
    if os.path.exists(audit_path):
        df = load_audit_csv(audit_path)
        df["seed"] = seed
        df["condition"] = "Flat"
        flat_audits.append(df)
    else:
        print(f"  WARNING: Missing {audit_path}")

full_df = pd.concat(full_audits, ignore_index=True) if full_audits else pd.DataFrame()
flat_df = pd.concat(flat_audits, ignore_index=True) if flat_audits else pd.DataFrame()

print(f"  Full: {len(full_df)} rows, Flat: {len(flat_df)} rows")

# Add MG status
for df in [full_df, flat_df]:
    if not df.empty:
        df["mg"] = df["agent_id"].map(mg_lookup).fillna(False)
        df["mg_label"] = df["mg"].map({True: "MG", False: "NMG"})
        df["affordability_block"] = df["error_messages"].apply(has_affordability_block)
        df["executed_action"] = df.apply(get_executed_action, axis=1)

# -- Panel (b): Affordability blocking counts --------------------------------
print("\nComputing affordability blocking by MG status...")

def count_afford_blocks(df, condition_label):
    if df.empty:
        return pd.DataFrame()
    rejected = df[df["status"].str.upper() == "REJECTED"]
    afford = rejected[rejected["affordability_block"]]
    counts = afford.groupby("mg_label").size().reset_index(name="affordability_rejections")
    counts["condition"] = condition_label
    # total decisions per group
    total = df.groupby("mg_label").size().reset_index(name="total_decisions")
    counts = counts.merge(total, on="mg_label", how="left")
    counts["pct"] = (counts["affordability_rejections"] / counts["total_decisions"] * 100).round(1)
    return counts

full_blocks = count_afford_blocks(full_df, "Full")
flat_blocks = count_afford_blocks(flat_df, "Flat")
all_blocks = pd.concat([full_blocks, flat_blocks], ignore_index=True)

print("\nAffordability blocking summary:")
print(all_blocks.to_string(index=False))

# -- Panels (c)(d): Action distributions by MG status -----------------------
print("\nComputing action distributions...")

ACTION_ORDER = ["FI", "EH", "BP", "DN"]
ACTION_LABELS = {"FI": "Insurance", "EH": "Elevation", "BP": "Buyout", "DN": "Do Nothing"}


def action_dist(df, condition_label, mg_filter):
    if df.empty:
        return {}
    sub = df[df["mg"] == mg_filter]
    total = len(sub)
    if total == 0:
        return {a: 0.0 for a in ACTION_ORDER}
    counts = sub["executed_action"].value_counts()
    return {a: counts.get(a, 0) / total * 100.0 for a in ACTION_ORDER}


full_mg_dist = action_dist(full_df, "Full", True)
flat_mg_dist = action_dist(flat_df, "Flat", True)
full_nmg_dist = action_dist(full_df, "Full", False)
flat_nmg_dist = action_dist(flat_df, "Flat", False)

print(f"  Full MG:  {full_mg_dist}")
print(f"  Flat MG:  {flat_mg_dist}")
print(f"  Full NMG: {full_nmg_dist}")
print(f"  Flat NMG: {flat_nmg_dist}")

# ---------------------------------------------------------------------------
# Figure
# ---------------------------------------------------------------------------
print("\nGenerating figure...")

COLOR_FULL = "#2166AC"   # blue
COLOR_FLAT = "#762A83"   # purple
COLOR_FULL_LIGHT = "#92C5DE"
COLOR_FLAT_LIGHT = "#C2A5CF"

fig, axes = plt.subplots(2, 2, figsize=(12, 9))
fig.subplots_adjust(hspace=0.35, wspace=0.30, top=0.94, bottom=0.08,
                    left=0.08, right=0.95)

# Calendar year mapping
cal_years = [2010 + y for y in years]

# ==== Panel (a): Policy trajectory ====
ax_a = axes[0, 0]
ax_a2 = ax_a.twinx()

# Subsidy
l1, = ax_a.plot(cal_years, subsidy_mean, '-o', color=COLOR_FULL, lw=2, ms=4,
                label="Full: Subsidy", zorder=3)
ax_a.fill_between(cal_years,
                  [m - s for m, s in zip(subsidy_mean, subsidy_std)],
                  [m + s for m, s in zip(subsidy_mean, subsidy_std)],
                  alpha=0.15, color=COLOR_FULL)
l2, = ax_a.plot(cal_years, flat_subsidy, '--', color=COLOR_FLAT, lw=2,
                label="Flat: Subsidy (50%)")

# CRS
l3, = ax_a2.plot(cal_years, crs_mean, '-s', color=COLOR_FULL_LIGHT, lw=2, ms=4,
                 label="Full: CRS discount", zorder=2)
ax_a2.fill_between(cal_years,
                   [m - s for m, s in zip(crs_mean, crs_std)],
                   [m + s for m, s in zip(crs_mean, crs_std)],
                   alpha=0.15, color=COLOR_FULL_LIGHT)
l4, = ax_a2.plot(cal_years, flat_crs, '--', color=COLOR_FLAT_LIGHT, lw=2,
                 label="Flat: CRS (0%)")

ax_a.set_xlabel("Year", fontsize=10)
ax_a.set_ylabel("Subsidy Rate (%)", fontsize=10, color=COLOR_FULL)
ax_a2.set_ylabel("CRS Discount (%)", fontsize=10, color=COLOR_FULL_LIGHT)
ax_a.set_ylim(30, 80)
ax_a2.set_ylim(-5, 50)
ax_a.tick_params(axis='y', labelcolor=COLOR_FULL)
ax_a2.tick_params(axis='y', labelcolor=COLOR_FULL_LIGHT)
ax_a.set_title("(a) Institutional policy trajectories", fontsize=11, loc="left")

# Combined legend
lines = [l1, l2, l3, l4]
labels = [l.get_label() for l in lines]
ax_a.legend(lines, labels, fontsize=8, loc="upper left", framealpha=0.9)
ax_a.grid(True, alpha=0.3)

# ==== Panel (b): Affordability blocking — PRIMARY ====
ax_b = axes[0, 1]

groups = ["MG", "NMG"]
x_pos = np.arange(len(groups))
bar_width = 0.35

full_vals = []
flat_vals = []
full_pcts = []
flat_pcts = []

for g in groups:
    frow = all_blocks[(all_blocks["condition"] == "Full") & (all_blocks["mg_label"] == g)]
    full_vals.append(frow["affordability_rejections"].values[0] if len(frow) > 0 else 0)
    full_pcts.append(frow["pct"].values[0] if len(frow) > 0 else 0.0)

    frow2 = all_blocks[(all_blocks["condition"] == "Flat") & (all_blocks["mg_label"] == g)]
    flat_vals.append(frow2["affordability_rejections"].values[0] if len(frow2) > 0 else 0)
    flat_pcts.append(frow2["pct"].values[0] if len(frow2) > 0 else 0.0)

bars1 = ax_b.bar(x_pos - bar_width/2, full_vals, bar_width, color=COLOR_FULL,
                 label="Full (3-tier)", edgecolor="white", zorder=3)
bars2 = ax_b.bar(x_pos + bar_width/2, flat_vals, bar_width, color=COLOR_FLAT,
                 label="Flat (fixed)", edgecolor="white", zorder=3)

# Percentage labels on bars
for bar, pct in zip(bars1, full_pcts):
    h = bar.get_height()
    if h > 0:
        ax_b.text(bar.get_x() + bar.get_width()/2, h + max(full_vals + flat_vals)*0.02,
                  f"{pct:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold",
                  color=COLOR_FULL)

for bar, pct in zip(bars2, flat_pcts):
    h = bar.get_height()
    if h > 0:
        ax_b.text(bar.get_x() + bar.get_width()/2, h + max(full_vals + flat_vals)*0.02,
                  f"{pct:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold",
                  color=COLOR_FLAT)

# Count labels inside bars
for bar, val in zip(bars1, full_vals):
    if val > 0:
        ax_b.text(bar.get_x() + bar.get_width()/2, bar.get_height()/2,
                  f"n={val}", ha="center", va="center", fontsize=8, color="white")

for bar, val in zip(bars2, flat_vals):
    if val > 0:
        ax_b.text(bar.get_x() + bar.get_width()/2, bar.get_height()/2,
                  f"n={val}", ha="center", va="center", fontsize=8, color="white")

ax_b.set_xticks(x_pos)
ax_b.set_xticklabels(["Marginalized (MG)", "Non-Marginalized (NMG)"], fontsize=10)
ax_b.set_ylabel("Affordability Rejections\n(pooled, 3 seeds)", fontsize=10)
ax_b.set_title("(b) Affordability blocking by socioeconomic status", fontsize=11, loc="left")
ax_b.legend(fontsize=9, loc="upper right")
ax_b.grid(True, axis="y", alpha=0.3)
ax_b.set_axisbelow(True)


# ==== Panel (c): MG owner action distribution ====
ax_c = axes[1, 0]

x_pos_c = np.arange(len(ACTION_ORDER))
bar_w = 0.35

full_mg_vals = [full_mg_dist.get(a, 0) for a in ACTION_ORDER]
flat_mg_vals = [flat_mg_dist.get(a, 0) for a in ACTION_ORDER]

bars_c1 = ax_c.bar(x_pos_c - bar_w/2, full_mg_vals, bar_w, color=COLOR_FULL,
                   label="Full (3-tier)", edgecolor="white")
bars_c2 = ax_c.bar(x_pos_c + bar_w/2, flat_mg_vals, bar_w, color=COLOR_FLAT,
                   label="Flat (fixed)", edgecolor="white")

# Labels on bars
for bar, val in zip(bars_c1, full_mg_vals):
    if val > 2:
        ax_c.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                  f"{val:.1f}%", ha="center", va="bottom", fontsize=8, color=COLOR_FULL)
for bar, val in zip(bars_c2, flat_mg_vals):
    if val > 2:
        ax_c.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                  f"{val:.1f}%", ha="center", va="bottom", fontsize=8, color=COLOR_FLAT)

ax_c.set_xticks(x_pos_c)
ax_c.set_xticklabels([ACTION_LABELS[a] for a in ACTION_ORDER], fontsize=9)
ax_c.set_ylabel("Action Rate (%)", fontsize=10)
ax_c.set_title("(c) MG owner action distribution", fontsize=11, loc="left")
ax_c.legend(fontsize=9, loc="upper left")
ax_c.grid(True, axis="y", alpha=0.3)
ax_c.set_axisbelow(True)
ax_c.set_ylim(0, max(full_mg_vals + flat_mg_vals) * 1.25 + 5)

# ==== Panel (d): NMG owner action distribution ====
ax_d = axes[1, 1]

full_nmg_vals = [full_nmg_dist.get(a, 0) for a in ACTION_ORDER]
flat_nmg_vals = [flat_nmg_dist.get(a, 0) for a in ACTION_ORDER]

bars_d1 = ax_d.bar(x_pos_c - bar_w/2, full_nmg_vals, bar_w, color=COLOR_FULL,
                   label="Full (3-tier)", edgecolor="white")
bars_d2 = ax_d.bar(x_pos_c + bar_w/2, flat_nmg_vals, bar_w, color=COLOR_FLAT,
                   label="Flat (fixed)", edgecolor="white")

for bar, val in zip(bars_d1, full_nmg_vals):
    if val > 2:
        ax_d.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                  f"{val:.1f}%", ha="center", va="bottom", fontsize=8, color=COLOR_FULL)
for bar, val in zip(bars_d2, flat_nmg_vals):
    if val > 2:
        ax_d.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                  f"{val:.1f}%", ha="center", va="bottom", fontsize=8, color=COLOR_FLAT)

ax_d.set_xticks(x_pos_c)
ax_d.set_xticklabels([ACTION_LABELS[a] for a in ACTION_ORDER], fontsize=9)
ax_d.set_ylabel("Action Rate (%)", fontsize=10)
ax_d.set_title("(d) NMG owner action distribution", fontsize=11, loc="left")
ax_d.legend(fontsize=9, loc="upper left")
ax_d.grid(True, axis="y", alpha=0.3)
ax_d.set_axisbelow(True)
ax_d.set_ylim(0, max(full_nmg_vals + flat_nmg_vals) * 1.25 + 5)

# Save
fig.savefig(OUTPUT_FIG, dpi=300, bbox_inches="tight", facecolor="white")
print(f"\nFigure saved: {OUTPUT_FIG}")

# ---------------------------------------------------------------------------
# Summary CSV
# ---------------------------------------------------------------------------
print("\nBuilding summary table...")

rows = []
for condition, cond_df in [("Full", full_df), ("Flat", flat_df)]:
    if cond_df.empty:
        continue
    for mg_val, mg_label in [(True, "MG"), (False, "NMG")]:
        sub = cond_df[cond_df["mg"] == mg_val]
        total = len(sub)
        rejected_mask = sub["status"].str.upper() == "REJECTED"
        rejected = int(rejected_mask.sum())
        afford = int((rejected_mask & sub["affordability_block"]).sum())
        actions = sub["executed_action"].value_counts()
        row = {
            "condition": condition,
            "group": mg_label,
            "total_decisions": total,
            "total_rejections": rejected,
            "affordability_rejections": afford,
            "afford_pct": round(afford / total * 100, 2) if total > 0 else 0,
            "FI_pct": round(actions.get("FI", 0) / total * 100, 2) if total > 0 else 0,
            "EH_pct": round(actions.get("EH", 0) / total * 100, 2) if total > 0 else 0,
            "BP_pct": round(actions.get("BP", 0) / total * 100, 2) if total > 0 else 0,
            "DN_pct": round(actions.get("DN", 0) / total * 100, 2) if total > 0 else 0,
        }
        rows.append(row)

summary_df = pd.DataFrame(rows)
summary_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
print(f"Summary table saved: {OUTPUT_CSV}")
print("\n" + summary_df.to_string(index=False))

# Key finding
print("\n--- KEY FINDING ---")
if not all_blocks.empty:
    full_mg_block = all_blocks[(all_blocks["condition"] == "Full") & (all_blocks["mg_label"] == "MG")]
    flat_mg_block = all_blocks[(all_blocks["condition"] == "Flat") & (all_blocks["mg_label"] == "MG")]
    full_nmg_block = all_blocks[(all_blocks["condition"] == "Full") & (all_blocks["mg_label"] == "NMG")]

    if len(full_mg_block) > 0 and len(full_nmg_block) > 0:
        mg_n = full_mg_block["affordability_rejections"].values[0]
        nmg_n = full_nmg_block["affordability_rejections"].values[0] if len(full_nmg_block) > 0 else 0
        ratio = mg_n / nmg_n if nmg_n > 0 else float("inf")
        print(f"Full condition: MG affordability blocks = {mg_n}, NMG = {nmg_n} (ratio: {ratio:.1f}x)")

    if len(flat_mg_block) > 0:
        flat_mg_n = flat_mg_block["affordability_rejections"].values[0]
        flat_nmg_n = 0
        flat_nmg_row = all_blocks[(all_blocks["condition"] == "Flat") & (all_blocks["mg_label"] == "NMG")]
        if len(flat_nmg_row) > 0:
            flat_nmg_n = flat_nmg_row["affordability_rejections"].values[0]
        print(f"Flat condition: MG affordability blocks = {flat_mg_n}, NMG = {flat_nmg_n}")

print("\nDone.")
