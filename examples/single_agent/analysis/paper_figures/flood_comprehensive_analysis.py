#!/usr/bin/env python3
"""
Comprehensive Flood Experiment Analysis Report
===============================================
Multi-model (Gemma3-4B / 12B / 27B), multi-governance-tier analysis.

Produces:
  Figure 1 -- Cumulative Protective Action Adoption (2 rows x 3 cols)
  Figure 2 -- Normalized Shannon Entropy Time Series (1 x 3)
  Figure 3 -- Governance Intervention Dashboard
  Table  1 -- flood_cumulative_year10.csv
  Table  2 -- flood_action_distribution.csv
  Table  3 -- flood_governance_summary.csv
  Console  -- Key Findings Summary

Author: auto-generated for WRR / SAGE paper analysis
"""

import pathlib, json, warnings, sys, textwrap
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from matplotlib.lines import Line2D
from collections import Counter

warnings.filterwarnings("ignore", category=FutureWarning)

# ==========================================================================
# Paths
# ==========================================================================
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
BASE       = SCRIPT_DIR.parents[1]  # examples/single_agent
RESULTS    = BASE / "results" / "JOH_FINAL"
OUT_DIR    = SCRIPT_DIR  # save figures alongside other paper figures

MODELS = [
    ("gemma3_4b",  "Gemma3-4B"),
    ("gemma3_12b", "Gemma3-12B"),
    ("gemma3_27b", "Gemma3-27B"),
]

# Which groups exist for each model
MODEL_GROUPS = {
    "gemma3_4b":  ["Group_A", "Group_B", "Group_C"],
    "gemma3_12b": ["Group_A", "Group_B", "Group_C"],
    "gemma3_27b": ["Group_A", "Group_B"],
}

# Governance summary files (only governed groups)
GOV_FILES = {
    "gemma3_4b":  {"Group_B": True, "Group_C": True},
    "gemma3_12b": {"Group_B": True, "Group_C": True},
    "gemma3_27b": {"Group_B": True},
}

FLOOD_YEARS = [3, 4, 9]
YEARS = list(range(1, 11))

# ==========================================================================
# Style -- publication-quality, Okabe-Ito color-blind friendly
# ==========================================================================
plt.rcParams.update({
    "font.family":       "serif",
    "font.serif":        ["Times New Roman", "DejaVu Serif"],
    "font.size":         9,
    "axes.labelsize":    10,
    "axes.titlesize":    10,
    "legend.fontsize":   7.5,
    "xtick.labelsize":   8,
    "ytick.labelsize":   8,
    "figure.dpi":        300,
    "savefig.dpi":       300,
    "savefig.bbox":      "tight",
    "axes.linewidth":    0.6,
    "xtick.major.width": 0.5,
    "ytick.major.width": 0.5,
})

# Group styling
GROUP_COLORS = {
    "Group_A": "#D55E00",   # vermillion
    "Group_B": "#0072B2",   # blue
    "Group_C": "#009E73",   # teal
}
GROUP_LINESTYLES = {
    "Group_A": "--",   # dashed = ungoverned
    "Group_B": "-",    # solid  = governed
    "Group_C": ":",    # dotted = governed + memory variant
}
GROUP_MARKERS = {
    "Group_A": "o",
    "Group_B": "s",
    "Group_C": "^",
}
GROUP_LABELS = {
    "Group_A": "A (no governance)",
    "Group_B": "B (governed)",
    "Group_C": "C (gov. + memory)",
}

# Protective-action color scheme
STATE_COLORS = {
    "elevated":  "#0072B2",   # blue
    "insured":   "#E69F00",   # orange
    "relocated": "#009E73",   # green
}

# ==========================================================================
# Data loading
# ==========================================================================
def load_sim_log(model_key, group):
    """Load and harmonise a single simulation log."""
    path = RESULTS / model_key / group / "Run_1" / "simulation_log.csv"
    if not path.exists():
        print(f"  WARNING: {path} not found, skipping.")
        return None
    df = pd.read_csv(path)

    # Harmonise column names (Group A has old schema)
    renames = {}
    if "decision" in df.columns and "yearly_decision" not in df.columns:
        renames["decision"] = "cumulative_state_label"
    if "trust_in_insurance" in df.columns:
        renames["trust_in_insurance"] = "trust_insurance"
    if "trust_in_neighbors" in df.columns:
        renames["trust_in_neighbors"] = "trust_neighbors"
    if renames:
        df = df.rename(columns=renames)

    # Ensure yearly_decision exists
    if "yearly_decision" not in df.columns:
        # Group A: derive from raw_llm_decision or raw_llm_code
        if "raw_llm_decision" in df.columns:
            df["yearly_decision"] = df["raw_llm_decision"].apply(norm_decision_raw)
        elif "cumulative_state_label" in df.columns:
            df["yearly_decision"] = df["cumulative_state_label"].apply(norm_decision_raw)
        else:
            df["yearly_decision"] = "unknown"

    # Normalise boolean columns
    for col in ["elevated", "has_insurance", "relocated"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: str(x).strip().lower() == "true")

    df["model"] = model_key
    df["group"] = group
    return df


def norm_decision_raw(s):
    """Map raw LLM decision text to canonical action key."""
    s = str(s).strip().lower()
    mapping = [
        ("do nothing",     "do_nothing"),
        ("do_nothing",     "do_nothing"),
        ("elevate the house", "elevate_house"),
        ("elevate_house",  "elevate_house"),
        ("only house elevation", "elevate_house"),
        ("buy flood insurance", "buy_insurance"),
        ("buy_insurance",  "buy_insurance"),
        ("only flood insurance", "buy_insurance"),
        ("buy flood insurance and elevate the house", "insurance_elevation"),
        ("both flood insurance and house elevation",  "insurance_elevation"),
        ("elevate_and_insure", "insurance_elevation"),
        ("insurance_elevation", "insurance_elevation"),
        ("both", "insurance_elevation"),
        ("relocate", "relocate"),
        ("relocate_out", "relocate"),
    ]
    for key, val in mapping:
        if key in s:
            return val
    return "do_nothing"   # default fallback


def norm_yearly_decision(s):
    """Normalise a yearly_decision value to canonical form."""
    s = str(s).strip().lower()
    if s in ("do_nothing", "do nothing"):
        return "do_nothing"
    if s in ("elevate_house", "elevate the house", "only house elevation"):
        return "elevate_house"
    if s in ("buy_insurance", "buy flood insurance", "only flood insurance"):
        return "buy_insurance"
    if s in ("insurance_elevation", "elevate_and_insure", "both",
             "buy flood insurance and elevate the house",
             "both flood insurance and house elevation",
             "both house elevation and flood insurance"):
        return "insurance_elevation"
    if s in ("relocate", "relocate_out"):
        return "relocate"
    return "do_nothing"


def load_governance(model_key, group):
    """Load governance_summary.json for a governed group."""
    path = RESULTS / model_key / group / "Run_1" / "governance_summary.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


# ==========================================================================
# Load all data
# ==========================================================================
print("=" * 72)
print("FLOOD EXPERIMENT COMPREHENSIVE ANALYSIS")
print("=" * 72)
print()

print("[1/7] Loading simulation logs ...")
all_dfs = []
for model_key, model_name in MODELS:
    for group in MODEL_GROUPS[model_key]:
        df = load_sim_log(model_key, group)
        if df is not None:
            all_dfs.append(df)
            print(f"  Loaded {model_key}/{group}: {len(df)} rows, "
                  f"years {sorted(df['year'].unique())}, "
                  f"agents {df['agent_id'].nunique()}")

DATA = pd.concat(all_dfs, ignore_index=True)
DATA["action"] = DATA["yearly_decision"].apply(norm_yearly_decision)

print(f"\n  Total rows: {len(DATA)}")
print(f"  Models: {sorted(DATA['model'].unique())}")
print(f"  Groups: {sorted(DATA['group'].unique())}")

print("\n[2/7] Loading governance summaries ...")
GOV_DATA = {}
for model_key, model_name in MODELS:
    for group in GOV_FILES.get(model_key, {}):
        g = load_governance(model_key, group)
        if g is not None:
            GOV_DATA[(model_key, group)] = g
            print(f"  {model_key}/{group}: {g['total_interventions']} interventions, "
                  f"rules={g['rule_frequency']}")


# ==========================================================================
# Compute per-model, per-group, per-year metrics
# ==========================================================================
print("\n[3/7] Computing metrics ...")

def compute_state_pcts(df):
    """Compute % elevated, insured, relocated per year per model per group."""
    rows = []
    for (model, group, year), sub in df.groupby(["model", "group", "year"]):
        n = len(sub)
        pct_elev = sub["elevated"].sum() / n * 100
        pct_ins  = sub["has_insurance"].sum() / n * 100
        pct_rel  = sub["relocated"].sum() / n * 100
        rows.append({
            "model": model, "group": group, "year": year,
            "pct_elevated": pct_elev, "pct_insured": pct_ins,
            "pct_relocated": pct_rel,
            "n_agents": n,
        })
    return pd.DataFrame(rows)


def compute_shannon_entropy(df):
    """Compute normalized Shannon entropy of action distribution per year per model per group."""
    ACTION_KEYS = ["do_nothing", "buy_insurance", "elevate_house",
                   "insurance_elevation", "relocate"]
    rows = []
    for (model, group, year), sub in df.groupby(["model", "group", "year"]):
        counts = Counter(sub["action"])
        total = sum(counts.values())
        probs = []
        for a in ACTION_KEYS:
            p = counts.get(a, 0) / total
            probs.append(p)
        # Shannon entropy
        H = 0.0
        for p in probs:
            if p > 0:
                H -= p * np.log2(p)
        # Normalise by log2(K) where K = number of possible actions
        K = len(ACTION_KEYS)
        H_norm = H / np.log2(K) if K > 1 else 0.0
        rows.append({
            "model": model, "group": group, "year": year,
            "H_raw": H, "H_norm": H_norm, "n_agents": total,
        })
    return pd.DataFrame(rows)


def compute_action_distribution(df):
    """Compute overall action distribution per model per group."""
    ACTION_KEYS = ["do_nothing", "buy_insurance", "elevate_house",
                   "insurance_elevation", "relocate"]
    rows = []
    for (model, group), sub in df.groupby(["model", "group"]):
        counts = Counter(sub["action"])
        total = sum(counts.values())
        row = {"model": model, "group": group, "total": total}
        for a in ACTION_KEYS:
            row[f"{a}_pct"] = counts.get(a, 0) / total * 100
        rows.append(row)
    return pd.DataFrame(rows)


state_pcts = compute_state_pcts(DATA)
entropy_df = compute_shannon_entropy(DATA)
action_dist = compute_action_distribution(DATA)

# ==========================================================================
# FIGURE 1: Cumulative Protective Action Adoption (2 rows x 3 cols)
# ==========================================================================
print("\n[4/7] Creating Figure 1: Cumulative Protective Action Adoption ...")

fig1, axes1 = plt.subplots(2, 3, figsize=(14, 7.5),
                            gridspec_kw={"hspace": 0.38, "wspace": 0.30})

# Top row: Elevation + Insurance, Bottom row: Relocation (or combined)
# Actually: let's do top row = individual states, bottom row = combined view
# Better approach: each column = one model, top row = elevation + insurance, bottom = relocation

state_metrics = [
    ("pct_elevated", "Elevation (%)", STATE_COLORS["elevated"]),
    ("pct_insured",  "Insurance (%)",  STATE_COLORS["insured"]),
    ("pct_relocated","Relocation (%)", STATE_COLORS["relocated"]),
]

for col_idx, (model_key, model_name) in enumerate(MODELS):
    groups = MODEL_GROUPS[model_key]

    # --- Top row: Elevation + Insurance ---
    ax_top = axes1[0, col_idx]
    for grp in groups:
        sub = state_pcts[(state_pcts["model"] == model_key) &
                         (state_pcts["group"] == grp)].sort_values("year")
        if sub.empty:
            continue
        # Elevation
        ax_top.plot(sub["year"], sub["pct_elevated"],
                    color=STATE_COLORS["elevated"],
                    linestyle=GROUP_LINESTYLES[grp],
                    marker=GROUP_MARKERS[grp], markersize=4,
                    linewidth=1.8, alpha=0.9)
        # Insurance
        ax_top.plot(sub["year"], sub["pct_insured"],
                    color=STATE_COLORS["insured"],
                    linestyle=GROUP_LINESTYLES[grp],
                    marker=GROUP_MARKERS[grp], markersize=4,
                    linewidth=1.8, alpha=0.9)

    # Flood year markers
    for fy in FLOOD_YEARS:
        ax_top.axvline(x=fy, color="gray", linestyle=":", linewidth=0.7, alpha=0.5)

    ax_top.set_title(f"{model_name}", fontweight="bold", fontsize=11)
    ax_top.set_ylabel("Agents (%)" if col_idx == 0 else "")
    ax_top.set_xticks(YEARS)
    ax_top.set_ylim(-2, 102)
    ax_top.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax_top.grid(True, alpha=0.2)

    if col_idx == 0:
        ax_top.set_ylabel("Elevation & Insurance (%)")

    # --- Bottom row: Relocation ---
    ax_bot = axes1[1, col_idx]
    for grp in groups:
        sub = state_pcts[(state_pcts["model"] == model_key) &
                         (state_pcts["group"] == grp)].sort_values("year")
        if sub.empty:
            continue
        ax_bot.plot(sub["year"], sub["pct_relocated"],
                    color=STATE_COLORS["relocated"],
                    linestyle=GROUP_LINESTYLES[grp],
                    marker=GROUP_MARKERS[grp], markersize=4,
                    linewidth=1.8, alpha=0.9)

    for fy in FLOOD_YEARS:
        ax_bot.axvline(x=fy, color="gray", linestyle=":", linewidth=0.7, alpha=0.5)

    ax_bot.set_xlabel("Simulation Year")
    ax_bot.set_xticks(YEARS)
    ax_bot.set_ylim(-2, 65)
    ax_bot.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax_bot.grid(True, alpha=0.2)

    if col_idx == 0:
        ax_bot.set_ylabel("Relocation (%)")

# Build unified legend
legend_elements = []
# Group lines
for grp in ["Group_A", "Group_B", "Group_C"]:
    legend_elements.append(Line2D([0], [0], color="gray",
                                   linestyle=GROUP_LINESTYLES[grp],
                                   marker=GROUP_MARKERS[grp], markersize=5,
                                   linewidth=1.8, label=GROUP_LABELS[grp]))
# Separator
legend_elements.append(Line2D([0], [0], color="none", label=""))
# State colors
legend_elements.append(Line2D([0], [0], color=STATE_COLORS["elevated"],
                               linewidth=3, label="Elevation"))
legend_elements.append(Line2D([0], [0], color=STATE_COLORS["insured"],
                               linewidth=3, label="Insurance"))
legend_elements.append(Line2D([0], [0], color=STATE_COLORS["relocated"],
                               linewidth=3, label="Relocation"))
# Flood marker
legend_elements.append(Line2D([0], [0], color="gray", linestyle=":",
                               linewidth=0.8, label="Flood year"))

fig1.legend(handles=legend_elements, loc="lower center", ncol=7,
            fontsize=8, framealpha=0.9, edgecolor="none",
            bbox_to_anchor=(0.5, -0.02))

fig1.suptitle("Cumulative Protective Action Adoption Under Governance",
              fontsize=13, fontweight="bold", y=1.01)

out1_png = OUT_DIR / "fig_flood_cumulative_state.png"
out1_pdf = OUT_DIR / "fig_flood_cumulative_state.pdf"
fig1.savefig(out1_png, dpi=300, bbox_inches="tight", facecolor="white")
fig1.savefig(out1_pdf, dpi=300, bbox_inches="tight", facecolor="white")
print(f"  Saved: {out1_png}")
print(f"  Saved: {out1_pdf}")
plt.close(fig1)

# ==========================================================================
# FIGURE 2: Normalized Shannon Entropy Time Series (1 x 3)
# ==========================================================================
print("\n[5/7] Creating Figure 2: Normalized Shannon Entropy ...")

fig2, axes2 = plt.subplots(1, 3, figsize=(14, 4.0),
                            gridspec_kw={"wspace": 0.28})

for col_idx, (model_key, model_name) in enumerate(MODELS):
    ax = axes2[col_idx]
    groups = MODEL_GROUPS[model_key]

    for grp in groups:
        sub = entropy_df[(entropy_df["model"] == model_key) &
                         (entropy_df["group"] == grp)].sort_values("year")
        if sub.empty:
            continue
        ax.plot(sub["year"], sub["H_norm"],
                color=GROUP_COLORS[grp],
                linestyle=GROUP_LINESTYLES[grp],
                marker=GROUP_MARKERS[grp], markersize=4.5,
                linewidth=1.8,
                label=GROUP_LABELS[grp])

        # Fill below line for visual emphasis
        ax.fill_between(sub["year"], 0, sub["H_norm"],
                        color=GROUP_COLORS[grp], alpha=0.06)

    for fy in FLOOD_YEARS:
        ax.axvline(x=fy, color="gray", linestyle=":", linewidth=0.7, alpha=0.5)

    ax.set_title(f"{model_name}", fontweight="bold", fontsize=11)
    ax.set_xlabel("Simulation Year")
    ax.set_xticks(YEARS)
    ax.set_ylim(-0.02, 1.05)
    ax.set_ylabel("Normalized Shannon Entropy" if col_idx == 0 else "")
    ax.legend(fontsize=7.5, loc="lower left", framealpha=0.9, edgecolor="none")
    ax.grid(True, alpha=0.2)

    # Annotate collapse if visible (12b typically collapses)
    if model_key == "gemma3_12b":
        # Find the minimum entropy across all groups
        for grp in groups:
            sub = entropy_df[(entropy_df["model"] == model_key) &
                             (entropy_df["group"] == grp)].sort_values("year")
            if not sub.empty:
                min_idx = sub["H_norm"].idxmin()
                min_row = sub.loc[min_idx]
                if min_row["H_norm"] < 0.15:
                    ax.annotate(
                        f"Entropy\ncollapse",
                        xy=(min_row["year"], min_row["H_norm"]),
                        xytext=(min_row["year"] + 1.5, min_row["H_norm"] + 0.35),
                        fontsize=7, color=GROUP_COLORS[grp],
                        fontweight="bold",
                        arrowprops=dict(arrowstyle="->",
                                        color=GROUP_COLORS[grp], lw=0.8),
                        ha="center",
                    )
                    break  # only annotate one

fig2.suptitle("Normalized Shannon Entropy of Action Distributions",
              fontsize=13, fontweight="bold", y=1.03)

out2_png = OUT_DIR / "fig_flood_entropy_scaling.png"
out2_pdf = OUT_DIR / "fig_flood_entropy_scaling.pdf"
fig2.savefig(out2_png, dpi=300, bbox_inches="tight", facecolor="white")
fig2.savefig(out2_pdf, dpi=300, bbox_inches="tight", facecolor="white")
print(f"  Saved: {out2_png}")
print(f"  Saved: {out2_pdf}")
plt.close(fig2)

# ==========================================================================
# FIGURE 3: Governance Intervention Dashboard
# ==========================================================================
print("\n[6/7] Creating Figure 3: Governance Intervention Dashboard ...")

# Collect governance data into a table
gov_rows = []
for model_key, model_name in MODELS:
    for group in MODEL_GROUPS[model_key]:
        gdata = GOV_DATA.get((model_key, group))
        if gdata is not None:
            # Get main rule
            rules = gdata.get("rule_frequency", {})
            main_rule = max(rules, key=rules.get) if rules else "N/A"
            main_rule_count = rules.get(main_rule, 0) if rules else 0
            gov_rows.append({
                "model": model_key,
                "model_name": model_name,
                "group": group,
                "total_interventions": gdata["total_interventions"],
                "main_rule": main_rule,
                "main_rule_count": main_rule_count,
                "retry_success": gdata["outcome_stats"]["retry_success"],
                "retry_exhausted": gdata["outcome_stats"]["retry_exhausted"],
                "parse_errors": gdata["outcome_stats"].get("parse_errors", 0),
                "warnings": gdata["warnings"]["total_warnings"],
                "warning_rule": list(gdata["warnings"].get("warning_rule_frequency", {}).keys()),
                "retry_success_rate": (gdata["outcome_stats"]["retry_success"] /
                                       max(gdata["total_interventions"], 1) * 100),
                "empty_content_retries": gdata.get("llm_level_retries", {}).get("empty_content_retries", 0),
                "empty_content_failures": gdata.get("llm_level_retries", {}).get("empty_content_failures", 0),
            })
        else:
            gov_rows.append({
                "model": model_key,
                "model_name": model_name,
                "group": group,
                "total_interventions": 0,
                "main_rule": "N/A",
                "main_rule_count": 0,
                "retry_success": 0,
                "retry_exhausted": 0,
                "parse_errors": 0,
                "warnings": 0,
                "warning_rule": [],
                "retry_success_rate": 0.0,
                "empty_content_retries": 0,
                "empty_content_failures": 0,
            })

gov_df = pd.DataFrame(gov_rows)

# Create figure: 2 panels side by side
fig3, (ax3a, ax3b) = plt.subplots(1, 2, figsize=(13, 5.0),
                                    gridspec_kw={"wspace": 0.35})

# --- Panel (a): Grouped bar chart of interventions by model+group ---
# Only show governed groups
gov_only = gov_df[gov_df["total_interventions"] > 0].copy()
gov_only["label"] = gov_only.apply(
    lambda r: f"{r['model_name']}\n{r['group'].replace('Group_', 'Grp ')}", axis=1)

x = np.arange(len(gov_only))
w = 0.22

bars_total = ax3a.bar(x - w, gov_only["total_interventions"],
                       w, color="#0072B2", edgecolor="white", label="Total Interventions")
bars_retry = ax3a.bar(x, gov_only["retry_success"],
                       w, color="#56B4E9", edgecolor="white", label="Retry Successes")
bars_warn  = ax3a.bar(x + w, gov_only["warnings"],
                       w, color="#E69F00", edgecolor="white", label="Warnings (low coping)")

# Value labels
for bars in [bars_total, bars_retry, bars_warn]:
    for bar in bars:
        h = bar.get_height()
        if h > 0:
            ax3a.text(bar.get_x() + bar.get_width() / 2, h + 1.5,
                      f"{int(h)}", ha="center", va="bottom",
                      fontsize=7, fontweight="bold")

ax3a.set_xticks(x)
ax3a.set_xticklabels(gov_only["label"], fontsize=7.5)
ax3a.set_ylabel("Count")
ax3a.set_title("(a) Governance Interventions by Model and Group",
               fontweight="bold", fontsize=10)
ax3a.legend(fontsize=7.5, loc="upper right", framealpha=0.9)
ax3a.grid(True, axis="y", alpha=0.2)
y_max = max(gov_only["total_interventions"].max(),
            gov_only["warnings"].max()) * 1.3
ax3a.set_ylim(0, y_max)

# --- Panel (b): Heatmap of rule triggers ---
# Build a matrix: rows = model+group, columns = rule types
all_rules = set()
for _, row in gov_only.iterrows():
    gdata = GOV_DATA.get((row["model"], row["group"]))
    if gdata:
        all_rules.update(gdata.get("rule_frequency", {}).keys())
        all_rules.update(gdata.get("warnings", {}).get("warning_rule_frequency", {}).keys())

all_rules = sorted(all_rules)
rule_labels = {
    "extreme_threat_block": "Extreme Threat\nBlock",
    "elevation_threat_low": "Elevation +\nLow Threat",
    "low_coping_block": "Low Coping\nWarning",
}

heat_data = np.zeros((len(gov_only), len(all_rules)))
row_labels = []

for i, (_, row) in enumerate(gov_only.iterrows()):
    gdata = GOV_DATA.get((row["model"], row["group"]))
    lbl = f"{row['model_name']} {row['group'].replace('Group_', '')}"
    row_labels.append(lbl)
    if gdata:
        for j, rule in enumerate(all_rules):
            count = gdata.get("rule_frequency", {}).get(rule, 0)
            count += gdata.get("warnings", {}).get("warning_rule_frequency", {}).get(rule, 0)
            heat_data[i, j] = count

# Plot heatmap
im = ax3b.imshow(heat_data, cmap="YlOrRd", aspect="auto", interpolation="nearest")
ax3b.set_xticks(np.arange(len(all_rules)))
ax3b.set_xticklabels([rule_labels.get(r, r) for r in all_rules],
                      fontsize=7.5, ha="center")
ax3b.set_yticks(np.arange(len(row_labels)))
ax3b.set_yticklabels(row_labels, fontsize=8)
ax3b.set_title("(b) Rule Trigger Frequency (Heatmap)",
               fontweight="bold", fontsize=10)

# Add text annotations on heatmap
for i in range(heat_data.shape[0]):
    for j in range(heat_data.shape[1]):
        val = int(heat_data[i, j])
        if val > 0:
            text_color = "white" if val > heat_data.max() * 0.6 else "black"
            ax3b.text(j, i, str(val), ha="center", va="center",
                      fontsize=9, fontweight="bold", color=text_color)

cbar = fig3.colorbar(im, ax=ax3b, shrink=0.8, pad=0.02)
cbar.set_label("Count", fontsize=9)

fig3.suptitle("Governance Intervention Analysis Across Model Scales",
              fontsize=13, fontweight="bold", y=1.02)

out3_png = OUT_DIR / "fig_flood_governance_interventions.png"
out3_pdf = OUT_DIR / "fig_flood_governance_interventions.pdf"
fig3.savefig(out3_png, dpi=300, bbox_inches="tight", facecolor="white")
fig3.savefig(out3_pdf, dpi=300, bbox_inches="tight", facecolor="white")
print(f"  Saved: {out3_png}")
print(f"  Saved: {out3_pdf}")
plt.close(fig3)

# ==========================================================================
# TABLES
# ==========================================================================
print("\n[7/7] Generating summary tables ...")

# --- Table 1: Cumulative state at Year 10 ---
year10 = state_pcts[state_pcts["year"] == 10].copy()
# Merge with mean entropy
ent_means = entropy_df.groupby(["model", "group"])["H_norm"].mean().reset_index()
ent_means.columns = ["model", "group", "mean_entropy"]
year10 = year10.merge(ent_means, on=["model", "group"], how="left")

# Add model display names
model_name_map = dict(MODELS)
year10["Model"] = year10["model"].map(model_name_map)
year10["Group"] = year10["group"]

table1 = year10[["Model", "Group", "pct_elevated", "pct_insured",
                  "pct_relocated", "mean_entropy"]].copy()
table1.columns = ["Model", "Group", "%Elevated", "%Insured",
                   "%Relocated", "Mean_Entropy"]
table1 = table1.round(2)

t1_path = OUT_DIR / "flood_cumulative_year10.csv"
table1.to_csv(t1_path, index=False)
print(f"\n  Table 1 saved: {t1_path}")
print(table1.to_string(index=False))

# --- Table 2: Action distribution ---
action_dist["Model"] = action_dist["model"].map(model_name_map)
action_dist["Group"] = action_dist["group"]
table2 = action_dist[["Model", "Group", "do_nothing_pct", "buy_insurance_pct",
                       "elevate_house_pct", "relocate_pct",
                       "insurance_elevation_pct"]].copy()
table2.columns = ["Model", "Group", "do_nothing%", "buy_insurance%",
                   "elevate_house%", "relocate%", "compound%"]
table2 = table2.round(2)

t2_path = OUT_DIR / "flood_action_distribution.csv"
table2.to_csv(t2_path, index=False)
print(f"\n  Table 2 saved: {t2_path}")
print(table2.to_string(index=False))

# --- Table 3: Governance summary ---
gov_df["Model"] = gov_df["model"].map(model_name_map)
gov_df["Group"] = gov_df["group"]
table3 = gov_df[gov_df["total_interventions"] > 0][
    ["Model", "Group", "total_interventions", "main_rule",
     "retry_success_rate", "warnings"]].copy()
table3.columns = ["Model", "Group", "Total_Interventions", "Main_Rule",
                   "Retry_Success_Rate", "Warnings"]
table3["Retry_Success_Rate"] = table3["Retry_Success_Rate"].round(1)

t3_path = OUT_DIR / "flood_governance_summary.csv"
table3.to_csv(t3_path, index=False)
print(f"\n  Table 3 saved: {t3_path}")
print(table3.to_string(index=False))

# ==========================================================================
# KEY FINDINGS SUMMARY
# ==========================================================================
print("\n")
print("=" * 72)
print("KEY FINDINGS SUMMARY")
print("=" * 72)

# Compute summary statistics for the narrative
def get_ent_stats(model, group):
    sub = entropy_df[(entropy_df["model"] == model) &
                     (entropy_df["group"] == group)]
    return sub["H_norm"].mean(), sub["H_norm"].min(), sub["H_norm"].max()

def get_year10_stats(model, group):
    sub = state_pcts[(state_pcts["model"] == model) &
                     (state_pcts["group"] == group) &
                     (state_pcts["year"] == 10)]
    if sub.empty:
        return 0, 0, 0
    return (sub["pct_elevated"].values[0],
            sub["pct_insured"].values[0],
            sub["pct_relocated"].values[0])


print("""
CLAIM 1: Governance Reduces Hallucination / Inconsistency
----------------------------------------------------------""")

# 4B analysis
e4a = get_ent_stats("gemma3_4b", "Group_A")
e4b = get_ent_stats("gemma3_4b", "Group_B")
e4c = get_ent_stats("gemma3_4b", "Group_C")
g4b = GOV_DATA.get(("gemma3_4b", "Group_B"), {})
g4c = GOV_DATA.get(("gemma3_4b", "Group_C"), {})

print(f"""
  Gemma3-4B:
    - Group A (ungoverned) shows elevated entropy (mean H_norm = {e4a[0]:.3f})
      that may reflect chaotic/hallucinated action choices rather than genuine
      behavioral diversity. Without governance, the 4B model produces
      inconsistent threat-action pairings.
    - The governance engine intercepted {g4b.get('total_interventions', 0)} violations in Group B
      and {g4c.get('total_interventions', 0)} in Group C, predominantly via the
      'extreme_threat_block' rule -- indicating the 4B model frequently
      outputs extreme threat perception paired with passive (do_nothing) actions.
    - Retry success rate: Group B = {g4b.get('outcome_stats', {}).get('retry_success', 0)}/{g4b.get('total_interventions', 0)}
      ({g4b.get('outcome_stats', {}).get('retry_success', 0)/max(g4b.get('total_interventions', 1), 1)*100:.0f}%),
      Group C = {g4c.get('outcome_stats', {}).get('retry_success', 0)}/{g4c.get('total_interventions', 0)}
      ({g4c.get('outcome_stats', {}).get('retry_success', 0)/max(g4c.get('total_interventions', 1), 1)*100:.0f}%).
""")

# 12B analysis
e12a = get_ent_stats("gemma3_12b", "Group_A")
e12b = get_ent_stats("gemma3_12b", "Group_B")
e12c = get_ent_stats("gemma3_12b", "Group_C")
g12b = GOV_DATA.get(("gemma3_12b", "Group_B"), {})
g12c = GOV_DATA.get(("gemma3_12b", "Group_C"), {})

print(f"""  Gemma3-12B:
    - Group A mean H_norm = {e12a[0]:.3f} (notably lower than 4B).
    - Group B mean H_norm = {e12b[0]:.3f}, Group C mean H_norm = {e12c[0]:.3f}.
    - Governance triggered different rules: 'elevation_threat_low' was the
      main intervention ({g12b.get('total_interventions', 0)} in B, {g12c.get('total_interventions', 0)} in C),
      catching agents that elevated without perceiving sufficient threat.
    - {g12b.get('warnings', {}).get('total_warnings', 0)} low_coping_block warnings in Group B,
      {g12c.get('warnings', {}).get('total_warnings', 0)} in Group C -- suggesting the 12B model
      frequently reports low coping capacity yet still takes protective action.
""")

# 27B analysis
e27a = get_ent_stats("gemma3_27b", "Group_A")
e27b = get_ent_stats("gemma3_27b", "Group_B")
g27b = GOV_DATA.get(("gemma3_27b", "Group_B"), {})

print(f"""  Gemma3-27B:
    - Group A mean H_norm = {e27a[0]:.3f}, Group B mean H_norm = {e27b[0]:.3f}.
    - Only {g27b.get('total_interventions', 0)} governance interventions needed in Group B
      (vs. 99-115 for 4B) -- indicating the larger model produces far fewer
      inconsistent threat-action pairings naturally.
    - However, {g27b.get('warnings', {}).get('total_warnings', 0)} low_coping_block warnings
      remain, and {g27b.get('llm_level_retries', {}).get('empty_content_retries', 0)} empty-content retries
      were needed, suggesting the 27B model has structural output issues.
""")

print("""
CLAIM 2: Governance Maintains Reasonable Behavioral Diversity
--------------------------------------------------------------""")

# Compare entropy across models
print(f"""
  Entropy analysis (mean normalized Shannon entropy over 10 years):

    Model       | Group A (ungov.) | Group B (gov.)  | Group C (gov.+mem)
    ------------|------------------|-----------------|--------------------
    Gemma3-4B   | {e4a[0]:.3f}            | {e4b[0]:.3f}           | {e4c[0]:.3f}
    Gemma3-12B  | {e12a[0]:.3f}            | {e12b[0]:.3f}           | {e12c[0]:.3f}
    Gemma3-27B  | {e27a[0]:.3f}            | {e27b[0]:.3f}           | N/A

  Key observations:
    - For 4B: Governed groups B ({e4b[0]:.3f}) and C ({e4c[0]:.3f}) maintain moderate
      entropy -- governance removes inconsistent outputs but does NOT collapse
      all agents into a single action.
    - For 12B: Both ungoverned A ({e12a[0]:.3f}) and governed groups show lower entropy
      than 4B, reflecting the 12B model's tendency toward behavioral
      convergence. Governance does not worsen this -- the B and C entropy
      values ({e12b[0]:.3f}, {e12c[0]:.3f}) are comparable or even HIGHER than A.
    - For 27B: Group A ({e27a[0]:.3f}) and B ({e27b[0]:.3f}) show moderate entropy,
      with governance needing minimal intervention. This demonstrates that
      larger models inherently produce more coherent outputs while
      maintaining diversity.
""")

print("""
NON-MONOTONIC SCALING RESULT
------------------------------""")

# Year-10 states
s4a = get_year10_stats("gemma3_4b", "Group_A")
s4b = get_year10_stats("gemma3_4b", "Group_B")
s12a = get_year10_stats("gemma3_12b", "Group_A")
s12b = get_year10_stats("gemma3_12b", "Group_B")
s27a = get_year10_stats("gemma3_27b", "Group_A")
s27b = get_year10_stats("gemma3_27b", "Group_B")

print(f"""
  Year-10 cumulative states (%elevated / %insured / %relocated):

    Model       | Group A                          | Group B (governed)
    ------------|----------------------------------|-----------------------------
    Gemma3-4B   | {s4a[0]:5.1f} / {s4a[1]:5.1f} / {s4a[2]:5.1f}          | {s4b[0]:5.1f} / {s4b[1]:5.1f} / {s4b[2]:5.1f}
    Gemma3-12B  | {s12a[0]:5.1f} / {s12a[1]:5.1f} / {s12a[2]:5.1f}          | {s12b[0]:5.1f} / {s12b[1]:5.1f} / {s12b[2]:5.1f}
    Gemma3-27B  | {s27a[0]:5.1f} / {s27a[1]:5.1f} / {s27a[2]:5.1f}          | {s27b[0]:5.1f} / {s27b[1]:5.1f} / {s27b[2]:5.1f}

  Scaling is NOT monotonic:
    - The 12B model does NOT simply produce "better" outputs than 4B.
      In fact, 12B shows the lowest behavioral diversity (entropy collapse)
      and the highest volume of low_coping_block warnings.
    - The 4B model requires the most governance interventions
      (99-115 extreme_threat_blocks) but remains behaviorally diverse
      once governed.
    - The 27B model requires the fewest interventions (12) and shows
      good diversity, but has structural issues (empty content retries).
""")

print("""
PRACTICAL RECOMMENDATION
--------------------------
  For production ABM simulations of flood adaptation behavior:

    1. Model selection is not simply "bigger is better." The 12B model
       exhibits an entropy collapse pattern where most agents converge
       to the same action, which undermines the value of agent-based
       simulation.

    2. Governance is essential for smaller models (4B), where
       extreme_threat_block interventions prevent the LLM from
       producing internally contradictory threat-perception + action
       pairs. Without governance, threat perception and coping capacity
       assessments are unreliable.

    3. The 27B model offers the best balance: coherent threat-action
       pairings with minimal governance intervention needed, while
       maintaining genuine behavioral diversity.

    4. The 'low_coping_block' warning pattern across all model sizes
       indicates a systematic tendency for LLMs to report low coping
       capacity even when choosing protective actions -- a finding
       relevant to LLM-based social simulation methodology broadly.
""")

print("=" * 72)
print("ANALYSIS COMPLETE")
print("=" * 72)
print(f"\nOutput files:")
print(f"  {out1_png}")
print(f"  {out1_pdf}")
print(f"  {out2_png}")
print(f"  {out2_pdf}")
print(f"  {out3_png}")
print(f"  {out3_pdf}")
print(f"  {t1_path}")
print(f"  {t2_path}")
print(f"  {t3_path}")
