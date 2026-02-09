"""
WRR Technical Note — Irrigation ABM Figure (Single Figure, 2 Panels)
====================================================================
Panel (a): 42-year aggregate demand vs CRSS baseline
            - CRSS baseline (dashed) vs WAGF governed demand (solid) vs WAGF diversion (dotted)
            - Gray band: CRSS ±10% reference range

Panel (b): Lake Mead elevation with DCP shortage tier bands
            - Tier 0/1/2/3 background bands at 1075/1050/1025 ft thresholds
            - Shows bidirectional coupling: agent demand → reservoir → shortage → curtailment

Data priority: production_v20_42yr > production_v15_42yr > production_phase_c_42yr
CRSS reference: ref/CRSS_DB/CRSS_DB/annual_baseline_time_series.csv

Style: WRR 300 DPI, serif (Times New Roman), 7.0 x 5.5 inches
"""
import pathlib
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

# ── Paths ──
ROOT = pathlib.Path(__file__).resolve().parents[3]
RESULTS_BASE = ROOT / "examples" / "irrigation_abm" / "results"
CRSS_CSV = ROOT / "ref" / "CRSS_DB" / "CRSS_DB" / "annual_baseline_time_series.csv"
OUTPUT_DIR = pathlib.Path(__file__).parent

YEAR_OFFSET = 2018  # simulation year 1 = calendar year 2019

# ── Auto-detect best available dataset ──
CANDIDATES = [
    ("v20", RESULTS_BASE / "production_v20_42yr"),
    ("v18", RESULTS_BASE / "production_v18_42yr"),
    ("v15", RESULTS_BASE / "production_v15_42yr"),
    ("phase_c", RESULTS_BASE / "production_phase_c_42yr"),
    ("v12", RESULTS_BASE / "v12_production_42yr_78agents"),
]

sim_log_path = None
dataset_label = None

for label, result_dir in CANDIDATES:
    sim_p = result_dir / "simulation_log.csv"
    if sim_p.exists():
        sim_log_path = sim_p
        dataset_label = label
        print(f"[OK] Using dataset: {label} ({result_dir.name})")
        break

if sim_log_path is None:
    print("ERROR: No complete simulation results found.")
    sys.exit(1)

# ── WRR Style ──
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 9,
    "axes.labelsize": 10,
    "axes.titlesize": 10,
    "legend.fontsize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.5,
    "ytick.major.width": 0.5,
})

# ── 1. Load Data ──
sim = pd.read_csv(sim_log_path, encoding="utf-8")
crss = pd.read_csv(CRSS_CSV)

n_agents = sim["agent_id"].nunique()
max_year = sim["year"].max()
print(f"Agents: {n_agents}, Years: 1-{max_year}")

# ── 2. Aggregate yearly demand ──
yearly = sim.groupby("year").agg(
    request_af=("request", "sum"),
    diversion_af=("diversion", "sum"),
).reset_index()
yearly["request_maf"] = yearly["request_af"] / 1e6
yearly["diversion_maf"] = yearly["diversion_af"] / 1e6
yearly["calendar_year"] = yearly["year"] + YEAR_OFFSET

# CRSS baseline (UB + LB total)
crss["total_maf"] = (crss["ub_baseline_af"] + crss["lb_baseline_af"]) / 1e6
crss_merged = crss[crss["year"] <= max_year][["year", "calendar_year", "total_maf"]].copy()

# Merge
comp = pd.merge(yearly, crss_merged, on="year", suffixes=("", "_crss"))
comp["calendar_year"] = comp["year"] + YEAR_OFFSET

# ── 3. Lake Mead elevation per year (from simulation log) ──
mead_yearly = sim.groupby("year").agg(
    lake_mead_ft=("lake_mead_level", "first"),
    shortage_tier=("shortage_tier", "first"),
).reset_index()
mead_yearly["calendar_year"] = mead_yearly["year"] + YEAR_OFFSET

# ── 4. Compute statistics ──
mean_demand = comp["request_maf"].mean()
mean_crss = comp["total_maf"].mean()
cov_demand = comp["request_maf"].std() / mean_demand * 100
ratio = mean_demand / mean_crss

# Shortage tier summary
n_tier0 = (mead_yearly["shortage_tier"] == 0).sum()
n_tier1 = (mead_yearly["shortage_tier"] == 1).sum()
n_tier2 = (mead_yearly["shortage_tier"] == 2).sum()
n_tier3 = (mead_yearly["shortage_tier"] == 3).sum()

print(f"\nStatistics:")
print(f"  WAGF Mean Demand: {mean_demand:.2f} MAF/yr ({ratio:.2f}x CRSS)")
print(f"  CRSS Mean: {mean_crss:.2f} MAF/yr")
print(f"  CoV: {cov_demand:.1f}%")
print(f"  Shortage tiers: T0={n_tier0}, T1={n_tier1}, T2={n_tier2}, T3={n_tier3}")
print(f"  Mead range: {mead_yearly['lake_mead_ft'].min():.0f}-{mead_yearly['lake_mead_ft'].max():.0f} ft")

# ── 5. Colors ──
# Okabe-Ito accessible palette
C_CRSS = "#332288"       # indigo — CRSS baseline
C_REQUEST = "#44AA99"    # teal — WAGF request
C_DIVERSION = "#88CCEE"  # light blue — WAGF diversion

# ── 6. Create Figure ──
fig, (ax_a, ax_b) = plt.subplots(
    2, 1, figsize=(7.0, 5.5),
    gridspec_kw={"height_ratios": [1.3, 1]},
    constrained_layout=True,
)

# ── Panel (a): Demand vs CRSS ──
years = comp["calendar_year"]

# CRSS ±10% reference band
ax_a.fill_between(
    years, comp["total_maf"] * 0.90, comp["total_maf"] * 1.10,
    alpha=0.12, color=C_CRSS, label="CRSS ±10% range", zorder=1,
)

# CRSS baseline
ax_a.plot(
    years, comp["total_maf"],
    color=C_CRSS, lw=2.0, linestyle="--", alpha=0.7,
    label="CRSS Baseline", zorder=3,
)

# WAGF Request (governed demand)
ax_a.plot(
    years, comp["request_maf"],
    color=C_REQUEST, lw=2.0, label="WAGF Request", zorder=4,
)

# WAGF Diversion (actual after curtailment)
ax_a.plot(
    years, comp["diversion_maf"],
    color=C_DIVERSION, lw=1.5, linestyle=":",
    label="WAGF Diversion", zorder=2, alpha=0.8,
)

ax_a.set_ylabel("Aggregate Demand (million AF/yr)")
ax_a.set_title("(a) Annual Water Demand: WAGF vs CRSS Baseline",
               fontweight="bold", loc="left", fontsize=10)
# Legend: horizontal, lower-right to avoid overlapping data
ax_a.set_ylim(3.0, 7.0)
ax_a.legend(
    framealpha=0.95, edgecolor="none", fontsize=7,
    loc="lower right", bbox_to_anchor=(0.99, 0.01),
    borderpad=0.4, handlelength=1.5, ncol=2,
)
ax_a.grid(True, alpha=0.15, linewidth=0.4)
ax_a.set_xlim(years.min(), years.max())
ax_a.yaxis.set_major_locator(mticker.MultipleLocator(1))
for spine in ["top", "right"]:
    ax_a.spines[spine].set_visible(False)

# ── Panel (b): Lake Mead Elevation with Shortage Tier Bands ──
mcal = mead_yearly["calendar_year"]
melev = mead_yearly["lake_mead_ft"]

# Tier background bands (DCP thresholds)
ax_b.axhspan(1075, 1220, alpha=0.08, color="#2E7D32", label="Tier 0 (0%)")
ax_b.axhspan(1050, 1075, alpha=0.12, color="#DDCC77", label="Tier 1 (5%)")
ax_b.axhspan(1025, 1050, alpha=0.15, color="#CC6677", label="Tier 2 (10%)")
ax_b.axhspan(950, 1025, alpha=0.18, color="#882255", label="Tier 3 (20%)")

# Tier threshold dashed lines
for thresh in [1075, 1050, 1025]:
    ax_b.axhline(thresh, color="#888888", ls="--", lw=0.5, alpha=0.5)

# Elevation trajectory
ax_b.plot(mcal, melev, color=C_CRSS, lw=2.0, zorder=5)

ax_b.set_xlabel("Calendar Year")
ax_b.set_ylabel("Lake Mead Elevation (ft)")
ax_b.set_title("(b) Lake Mead Elevation and Shortage Tiers",
               fontweight="bold", loc="left", fontsize=10)
ax_b.legend(
    framealpha=0.95, edgecolor="none", fontsize=7,
    loc="lower right", bbox_to_anchor=(0.99, 0.01),
    borderpad=0.4, handlelength=1.5, ncol=2,
)
ax_b.set_xlim(years.min(), years.max())
ax_b.set_ylim(980, 1200)
ax_b.yaxis.set_major_locator(mticker.MultipleLocator(25))
ax_b.grid(True, alpha=0.15, linewidth=0.4)
for spine in ["top", "right"]:
    ax_b.spines[spine].set_visible(False)

# ── Save ──
out_png = OUTPUT_DIR / "fig_wrr_irrigation.png"
out_pdf = OUTPUT_DIR / "fig_wrr_irrigation.pdf"
fig.savefig(out_png)
fig.savefig(out_pdf)
plt.close()

print(f"\n[OK] Saved: {out_png}")
print(f"[OK] Saved: {out_pdf}")
print(f"Dataset: {dataset_label} | Agents: {n_agents} | Years: {max_year}")
