#!/usr/bin/env python3
"""
Comprehensive Flood Experiment Metrics Dashboard
=================================================
SAGE WRR Paper -- Gemma3-4B (JOH_FINAL) -- All evaluation metrics.

Produces a 4x2 panel dashboard (12 x 10 in, 300 DPI) with:
  Panel 1: Raw Entropy (H_norm) by group by year
  Panel 2: Corrected Entropy by group by year
  Panel 3: EBE (Effective Behavioral Entropy) by group by year
  Panel 4: Hallucination Rate (R_H) by group by year
  Panel 5: Action Distribution (stacked bars) aggregated by group
  Panel 6: Cumulative State Tracking (% elevated/insured/relocated over time)
  Panel 7: Trust Dynamics (trust_insurance & trust_neighbors over time)
  Panel 8: Governance Intervention Summary (bar chart)

Author: auto-generated for WRR SI dashboard
"""

import pathlib, json, warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from matplotlib.lines import Line2D

warnings.filterwarnings("ignore", category=FutureWarning)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE = pathlib.Path(__file__).resolve().parent
RESULTS = BASE.parents[1] / "results" / "JOH_FINAL" / "gemma3_4b"

entropy_csv   = BASE / "corrected_entropy_gemma3_4b.csv"
stats_csv     = BASE / "statistical_tests_results.csv"

sim_logs = {
    "Group_A": RESULTS / "Group_A" / "Run_1" / "simulation_log.csv",
    "Group_B": RESULTS / "Group_B" / "Run_1" / "simulation_log.csv",
    "Group_C": RESULTS / "Group_C" / "Run_1" / "simulation_log.csv",
}

gov_jsons = {
    "Group_B": RESULTS / "Group_B" / "Run_1" / "governance_summary.json",
    "Group_C": RESULTS / "Group_C" / "Run_1" / "governance_summary.json",
}

OUT_PNG = BASE / "flood_metrics_dashboard.png"
OUT_PDF = BASE / "flood_metrics_dashboard.pdf"

# ---------------------------------------------------------------------------
# Color palette  (Group A=coral/red, B=blue, C=teal)
# ---------------------------------------------------------------------------
COLORS = {
    "Group_A": "#E05555",   # coral-red
    "Group_B": "#3A7DDB",   # blue
    "Group_C": "#2AAA8A",   # teal
}
LABELS = {"Group_A": "Group A (No Gov.)",
           "Group_B": "Group B (Gov.)",
           "Group_C": "Group C (Gov.)"}

# Lighter shades for fill / CI bands
COLORS_LIGHT = {
    "Group_A": "#F5AAAA",
    "Group_B": "#A3C4F3",
    "Group_C": "#8FD9C4",
}

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
print("[1/6] Loading entropy / EBE data ...")
ent = pd.read_csv(entropy_csv)
years = sorted(ent["Year"].unique())

print("[2/6] Loading statistical tests ...")
stats = pd.read_csv(stats_csv)

print("[3/6] Loading simulation logs ...")
sim = {}
for grp, path in sim_logs.items():
    df = pd.read_csv(path)
    # Harmonise column names across Group A (different schema) vs B/C
    renames = {}
    if "decision" in df.columns and "yearly_decision" not in df.columns:
        renames["decision"] = "cumulative_state_raw"
    if "trust_in_insurance" in df.columns:
        renames["trust_in_insurance"] = "trust_insurance"
    if "trust_in_neighbors" in df.columns:
        renames["trust_in_neighbors"] = "trust_neighbors"
    if renames:
        df = df.rename(columns=renames)
    # Normalise yearly_decision (Group A has 'decision' col with mixed case)
    if "yearly_decision" not in df.columns:
        # Group A: use 'cumulative_state_raw' which is actually the per-year decision text
        df["yearly_decision"] = df["cumulative_state_raw"]
    sim[grp] = df

print("[4/6] Loading governance summaries ...")
gov = {}
for grp, path in gov_jsons.items():
    if path.exists():
        with open(path) as f:
            gov[grp] = json.load(f)

# ---------------------------------------------------------------------------
# Helper: normalise decision labels
# ---------------------------------------------------------------------------
def norm_decision(s):
    """Map raw decision strings to canonical labels."""
    s = str(s).strip().lower()
    mapping = {
        "do nothing": "DoNothing",
        "do_nothing": "DoNothing",
        "only house elevation": "Elevate",
        "elevate_house": "Elevate",
        "only flood insurance": "Insure",
        "buy_insurance": "Insure",
        "buy flood insurance": "Insure",
        "both house elevation and flood insurance": "Both",
        "elevate_and_insure": "Both",
        "both": "Both",
        "relocate": "Relocate",
        "relocate_out": "Relocate",
    }
    for key, val in mapping.items():
        if key in s:
            return val
    return "Other"

ACTION_ORDER = ["DoNothing", "Elevate", "Insure", "Both", "Relocate", "Other"]
ACTION_COLORS = {
    "DoNothing": "#BDBDBD",
    "Elevate":   "#F4A261",
    "Insure":    "#2A9D8F",
    "Both":      "#264653",
    "Relocate":  "#E76F51",
    "Other":     "#9E9E9E",
}

# ---------------------------------------------------------------------------
# Prepare per-group / per-year action counts from simulation logs
# ---------------------------------------------------------------------------
def get_action_counts(grp_df, grp_name):
    """Return DataFrame with columns [year, action, count]."""
    # Determine the decision column to use
    if "yearly_decision" in grp_df.columns:
        dec_col = "yearly_decision"
    elif "cumulative_state_raw" in grp_df.columns:
        dec_col = "cumulative_state_raw"
    else:
        dec_col = "decision"

    grp_df = grp_df.copy()
    grp_df["action"] = grp_df[dec_col].apply(norm_decision)
    counts = grp_df.groupby(["year", "action"]).size().reset_index(name="count")
    counts["group"] = grp_name
    return counts

all_action_counts = pd.concat(
    [get_action_counts(sim[g], g) for g in sim], ignore_index=True
)

# ---------------------------------------------------------------------------
# Prepare cumulative state tracking (% elevated / insured / relocated)
# ---------------------------------------------------------------------------
def get_state_pcts(grp_df, grp_name):
    """Return per-year percentage of agents elevated / insured / relocated."""
    rows = []
    for yr in sorted(grp_df["year"].unique()):
        sub = grp_df[grp_df["year"] == yr]
        n = len(sub)
        if n == 0:
            continue
        elevated_col = "elevated"
        insured_col = "has_insurance"
        relocated_col = "relocated"
        pct_elev = sub[elevated_col].apply(lambda x: str(x).strip().lower() == "true").mean() * 100
        pct_ins  = sub[insured_col].apply(lambda x: str(x).strip().lower() == "true").mean() * 100
        pct_rel  = sub[relocated_col].apply(lambda x: str(x).strip().lower() == "true").mean() * 100
        rows.append({"year": yr, "group": grp_name,
                      "pct_elevated": pct_elev, "pct_insured": pct_ins,
                      "pct_relocated": pct_rel})
    return pd.DataFrame(rows)

state_pcts = pd.concat([get_state_pcts(sim[g], g) for g in sim], ignore_index=True)

# ---------------------------------------------------------------------------
# Prepare trust dynamics
# ---------------------------------------------------------------------------
def get_trust(grp_df, grp_name):
    rows = []
    for yr in sorted(grp_df["year"].unique()):
        sub = grp_df[grp_df["year"] == yr]
        ti = pd.to_numeric(sub.get("trust_insurance", pd.Series(dtype=float)), errors="coerce")
        tn = pd.to_numeric(sub.get("trust_neighbors", pd.Series(dtype=float)), errors="coerce")
        rows.append({"year": yr, "group": grp_name,
                      "trust_insurance_mean": ti.mean(),
                      "trust_neighbors_mean": tn.mean()})
    return pd.DataFrame(rows)

trust_df = pd.concat([get_trust(sim[g], g) for g in sim], ignore_index=True)

# ===========================================================================
# BUILD THE FIGURE  (4 rows x 2 cols)
# ===========================================================================
print("[5/6] Building figure ...")
fig, axes = plt.subplots(4, 2, figsize=(12, 10.5),
                          gridspec_kw={"hspace": 0.42, "wspace": 0.28})

marker_kw = dict(linewidth=1.8, markersize=5, marker="o")

# ---- Panel (0,0): Raw Entropy H_norm ----------------------------------
ax = axes[0, 0]
for grp in ["Group_A", "Group_B", "Group_C"]:
    sub = ent[ent["Group"] == grp].sort_values("Year")
    ax.plot(sub["Year"], sub["Raw_H_norm"], color=COLORS[grp],
            label=LABELS[grp], **marker_kw)
ax.set_title("(a) Raw Normalised Entropy  $H_{\\mathrm{norm}}$", fontsize=10, fontweight="bold")
ax.set_ylabel("$H_{\\mathrm{norm}}$", fontsize=9)
ax.set_xlabel("Year", fontsize=9)
ax.set_xticks(years)
ax.set_ylim(-0.02, 1.02)
ax.legend(fontsize=7, loc="upper right", framealpha=0.8)
ax.grid(True, alpha=0.25)

# ---- Panel (0,1): Corrected Entropy -----------------------------------
ax = axes[0, 1]
for grp in ["Group_A", "Group_B", "Group_C"]:
    sub = ent[ent["Group"] == grp].sort_values("Year")
    ax.plot(sub["Year"], sub["Corrected_H_norm"], color=COLORS[grp],
            label=LABELS[grp], **marker_kw)
ax.axhline(0, color="grey", linewidth=0.6, linestyle="--")
ax.set_title("(b) Corrected Entropy  $H_{\\mathrm{corr}}$", fontsize=10, fontweight="bold")
ax.set_ylabel("$H_{\\mathrm{corr}}$", fontsize=9)
ax.set_xlabel("Year", fontsize=9)
ax.set_xticks(years)
ax.set_ylim(-0.1, 1.02)
ax.legend(fontsize=7, loc="upper right", framealpha=0.8)
ax.grid(True, alpha=0.25)

# ---- Panel (1,0): EBE -------------------------------------------------
ax = axes[1, 0]
for grp in ["Group_A", "Group_B", "Group_C"]:
    sub = ent[ent["Group"] == grp].sort_values("Year")
    ax.plot(sub["Year"], sub["EBE"], color=COLORS[grp],
            label=LABELS[grp], **marker_kw)
    # Shade fill to zero
    ax.fill_between(sub["Year"], 0, sub["EBE"],
                     color=COLORS_LIGHT[grp], alpha=0.25)
ax.set_title("(c) Effective Behavioral Entropy  $\\mathrm{EBE}$", fontsize=10, fontweight="bold")
ax.set_ylabel("EBE", fontsize=9)
ax.set_xlabel("Year", fontsize=9)
ax.set_xticks(years)
ax.set_ylim(-0.02, 1.02)
ax.legend(fontsize=7, loc="upper right", framealpha=0.8)
ax.grid(True, alpha=0.25)

# ---- Panel (1,1): Hallucination Rate -----------------------------------
ax = axes[1, 1]
for grp in ["Group_A", "Group_B", "Group_C"]:
    sub = ent[ent["Group"] == grp].sort_values("Year")
    ax.plot(sub["Year"], sub["Hallucination_Rate"], color=COLORS[grp],
            label=LABELS[grp], **marker_kw)
    ax.fill_between(sub["Year"], 0, sub["Hallucination_Rate"],
                     color=COLORS_LIGHT[grp], alpha=0.25)
# Add mean annotation from stats
for grp in ["Group_A", "Group_B", "Group_C"]:
    row = stats[(stats["comparison"] == grp) & (stats["metric"] == "Hallucination_Rate_mean")]
    if not row.empty:
        mean_val = row["statistic"].values[0]
        ax.axhline(mean_val, color=COLORS[grp], linewidth=0.9, linestyle=":",
                    alpha=0.6)
ax.set_title("(d) Hallucination Rate  $R_H$", fontsize=10, fontweight="bold")
ax.set_ylabel("$R_H$", fontsize=9)
ax.set_xlabel("Year", fontsize=9)
ax.set_xticks(years)
ax.set_ylim(-0.02, 0.52)
ax.legend(fontsize=7, loc="upper left", framealpha=0.8)
ax.grid(True, alpha=0.25)

# ---- Panel (2,0): Action Distribution (stacked bars) ------------------
ax = axes[2, 0]
grp_order = ["Group_A", "Group_B", "Group_C"]
bar_width = 0.25
x_pos = np.arange(len(grp_order))

# Aggregate across all years
agg = all_action_counts.groupby(["group", "action"])["count"].sum().reset_index()
totals = agg.groupby("group")["count"].sum()

# Build bottom stacks
bottoms = {g: 0.0 for g in grp_order}
for act in ACTION_ORDER:
    vals = []
    for g in grp_order:
        row = agg[(agg["group"] == g) & (agg["action"] == act)]
        pct = (row["count"].values[0] / totals[g] * 100) if len(row) > 0 else 0.0
        vals.append(pct)
    ax.bar(x_pos, vals, bar_width * 2.5, bottom=[bottoms[g] for g in grp_order],
           color=ACTION_COLORS.get(act, "#CCC"), label=act, edgecolor="white",
           linewidth=0.4)
    for i, g in enumerate(grp_order):
        bottoms[g] += vals[i]

ax.set_xticks(x_pos)
ax.set_xticklabels([LABELS[g] for g in grp_order], fontsize=7.5)
ax.set_ylabel("% of decisions", fontsize=9)
ax.set_title("(e) Action Distribution (All Years)", fontsize=10, fontweight="bold")
ax.legend(fontsize=6.5, loc="upper right", ncol=2, framealpha=0.8)
ax.set_ylim(0, 105)
ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
ax.grid(True, axis="y", alpha=0.25)

# ---- Panel (2,1): Cumulative State Tracking ----------------------------
ax = axes[2, 1]
line_styles = {"pct_elevated": "-", "pct_insured": "--", "pct_relocated": ":"}
state_labels = {"pct_elevated": "% Elevated", "pct_insured": "% Insured",
                "pct_relocated": "% Relocated"}

for grp in grp_order:
    sub = state_pcts[state_pcts["group"] == grp].sort_values("year")
    for metric, ls in line_styles.items():
        ax.plot(sub["year"], sub[metric], color=COLORS[grp],
                linestyle=ls, linewidth=1.5, marker="s" if ls == "-" else ("D" if ls == "--" else "^"),
                markersize=3.5)

# Custom legend: groups + metrics
legend_elements = []
for grp in grp_order:
    legend_elements.append(Line2D([0], [0], color=COLORS[grp], linewidth=2,
                                   label=LABELS[grp]))
legend_elements.append(Line2D([0], [0], color="grey", linestyle="-",
                               marker="s", markersize=4, label="Elevated"))
legend_elements.append(Line2D([0], [0], color="grey", linestyle="--",
                               marker="D", markersize=4, label="Insured"))
legend_elements.append(Line2D([0], [0], color="grey", linestyle=":",
                               marker="^", markersize=4, label="Relocated"))
ax.legend(handles=legend_elements, fontsize=6, loc="upper left", ncol=2, framealpha=0.8)
ax.set_title("(f) Cumulative State (% of Agents)", fontsize=10, fontweight="bold")
ax.set_ylabel("Percentage", fontsize=9)
ax.set_xlabel("Year", fontsize=9)
ax.set_xticks(years)
ax.set_ylim(-2, 102)
ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
ax.grid(True, alpha=0.25)

# ---- Panel (3,0): Trust Dynamics ----------------------------------------
ax = axes[3, 0]
for grp in grp_order:
    sub = trust_df[trust_df["group"] == grp].sort_values("year")
    ax.plot(sub["year"], sub["trust_insurance_mean"], color=COLORS[grp],
            linestyle="-", marker="o", markersize=4, linewidth=1.5)
    ax.plot(sub["year"], sub["trust_neighbors_mean"], color=COLORS[grp],
            linestyle="--", marker="s", markersize=4, linewidth=1.5)

legend_elements2 = []
for grp in grp_order:
    legend_elements2.append(Line2D([0], [0], color=COLORS[grp], linewidth=2,
                                    label=LABELS[grp]))
legend_elements2.append(Line2D([0], [0], color="grey", linestyle="-",
                                marker="o", markersize=4, label="Trust Insur."))
legend_elements2.append(Line2D([0], [0], color="grey", linestyle="--",
                                marker="s", markersize=4, label="Trust Neighb."))
ax.legend(handles=legend_elements2, fontsize=6, loc="best", ncol=2, framealpha=0.8)
ax.set_title("(g) Mean Trust Dynamics", fontsize=10, fontweight="bold")
ax.set_ylabel("Mean Trust Score", fontsize=9)
ax.set_xlabel("Year", fontsize=9)
ax.set_xticks(years)
ax.set_ylim(0, 0.72)
ax.grid(True, alpha=0.25)

# ---- Panel (3,1): Governance Interventions ----------------------------
ax = axes[3, 1]
groups_gov = ["Group_A", "Group_B", "Group_C"]
intervention_totals = []
retry_success = []
retry_exhausted = []
warnings_total = []
labels_gov = []

for grp in groups_gov:
    if grp in gov:
        g = gov[grp]
        intervention_totals.append(g["total_interventions"])
        retry_success.append(g["outcome_stats"]["retry_success"])
        retry_exhausted.append(g["outcome_stats"]["retry_exhausted"])
        warnings_total.append(g["warnings"]["total_warnings"])
    else:
        intervention_totals.append(0)
        retry_success.append(0)
        retry_exhausted.append(0)
        warnings_total.append(0)
    labels_gov.append(LABELS[grp])

x_g = np.arange(len(groups_gov))
w = 0.2

bars1 = ax.bar(x_g - 1.5*w, intervention_totals, w, color=[COLORS[g] for g in groups_gov],
               edgecolor="white", label="Total Interventions")
bars2 = ax.bar(x_g - 0.5*w, retry_success, w, color=[COLORS_LIGHT[g] for g in groups_gov],
               edgecolor="white", label="Retry Success")
bars3 = ax.bar(x_g + 0.5*w, retry_exhausted, w, color="#FF8A65",
               edgecolor="white", label="Retry Exhausted")
bars4 = ax.bar(x_g + 1.5*w, warnings_total, w, color="#FFD54F",
               edgecolor="white", label="Warnings")

# Value labels on bars
for bars in [bars1, bars2, bars3, bars4]:
    for bar in bars:
        h = bar.get_height()
        if h > 0:
            ax.text(bar.get_x() + bar.get_width()/2, h + 1.5, f"{int(h)}",
                    ha="center", va="bottom", fontsize=6.5, fontweight="bold")

ax.set_xticks(x_g)
ax.set_xticklabels(labels_gov, fontsize=7.5)
ax.set_title("(h) Governance Interventions Summary", fontsize=10, fontweight="bold")
ax.set_ylabel("Count", fontsize=9)
ax.legend(fontsize=6.5, loc="upper left", framealpha=0.8)
ax.grid(True, axis="y", alpha=0.25)
ax.set_ylim(0, max(intervention_totals + [10]) * 1.25)

# ---------------------------------------------------------------------------
# Global title & save
# ---------------------------------------------------------------------------
fig.suptitle("Flood ABM Evaluation Metrics Dashboard  --  Gemma3-4B  (gemma3_4b, JOH_FINAL)",
             fontsize=12, fontweight="bold", y=0.995)

print(f"[6/6] Saving -> {OUT_PNG}")
fig.savefig(OUT_PNG, dpi=300, bbox_inches="tight", facecolor="white")
fig.savefig(OUT_PDF, dpi=300, bbox_inches="tight", facecolor="white")
print(f"      Saved  -> {OUT_PDF}")
plt.close(fig)

# ===========================================================================
# Report available metrics summary
# ===========================================================================
print("\n" + "=" * 72)
print("METRICS AVAILABILITY REPORT")
print("=" * 72)

print("\n--- Entropy / EBE CSV (corrected_entropy_gemma3_4b.csv) ---")
print(f"  Columns : {list(ent.columns)}")
print(f"  Groups  : {sorted(ent['Group'].unique())}")
print(f"  Years   : {sorted(ent['Year'].unique())}")
print(f"  Rows    : {len(ent)}")

print("\n--- Simulation Logs ---")
for grp, df in sim.items():
    print(f"  {grp}: {len(df)} rows, {sorted(df['year'].unique())} years")
    print(f"    Columns: {list(df.columns)}")
    # Check which appraisals are populated
    if "threat_appraisal" in df.columns:
        non_na = df["threat_appraisal"].apply(lambda x: str(x).strip().lower() not in ["n/a", "nan", ""]).sum()
        print(f"    threat_appraisal populated: {non_na}/{len(df)}")
    if "coping_appraisal" in df.columns:
        non_na = df["coping_appraisal"].apply(lambda x: str(x).strip().lower() not in ["n/a", "nan", ""]).sum()
        print(f"    coping_appraisal populated: {non_na}/{len(df)}")

print("\n--- Governance Summary JSONs ---")
for grp in ["Group_A", "Group_B", "Group_C"]:
    if grp in gov:
        g = gov[grp]
        print(f"  {grp}: {g['total_interventions']} interventions, "
              f"rules={g['rule_frequency']}, "
              f"retry_success={g['outcome_stats']['retry_success']}, "
              f"warnings={g['warnings']['total_warnings']}")
    else:
        print(f"  {grp}: NO governance (baseline group)")

print("\n--- Statistical Tests (statistical_tests_results.csv) ---")
print(f"  Rows: {len(stats)}")
print(f"  Comparisons: {sorted(stats['comparison'].unique())}")
print(f"  Metrics tested: {sorted(stats['metric'].unique())}")

print("\n--- Action Distributions (from simulation logs) ---")
for grp in grp_order:
    sub = all_action_counts[all_action_counts["group"] == grp]
    total = sub["count"].sum()
    for act in ACTION_ORDER:
        c = sub[sub["action"] == act]["count"].sum()
        if c > 0:
            print(f"  {grp} | {act:12s}: {c:5d} ({c/total*100:5.1f}%)")

print("\n--- Trust Data (from simulation logs) ---")
for grp in grp_order:
    sub = trust_df[trust_df["group"] == grp]
    print(f"  {grp}: trust_insurance range [{sub['trust_insurance_mean'].min():.3f}, "
          f"{sub['trust_insurance_mean'].max():.3f}], "
          f"trust_neighbors range [{sub['trust_neighbors_mean'].min():.3f}, "
          f"{sub['trust_neighbors_mean'].max():.3f}]")

print("\n" + "=" * 72)
print("Dashboard saved to:")
print(f"  PNG: {OUT_PNG}")
print(f"  PDF: {OUT_PDF}")
print("=" * 72)
