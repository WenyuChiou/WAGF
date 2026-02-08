"""
WRR Technical Note — Irrigation ABM Figure (Single Figure, 2 Panels)
====================================================================
Panel (a): 42-year aggregate demand vs CRSS baseline
            - CRSS baseline (dashed) vs WAGF governed demand (solid) vs WAGF diversion (dotted)
            - Gray band: CRSS ±10% reference range
            - Inset text: Mean, CoV statistics

Panel (b): Governance outcome proportions (stacked area)
            - APPROVED (first attempt) / RETRY_SUCCESS / REJECTED
            - Shows learning curve: high rejection → stabilization

Data priority: production_v15_42yr > production_phase_c_42yr > v12_production_42yr_78agents
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
def _find_repo_root():
    p = pathlib.Path(__file__).resolve().parent
    for _ in range(10):
        if (p / ".git").exists():
            return p
        p = p.parent
    raise RuntimeError("Cannot find repo root (.git)")

ROOT = _find_repo_root()
RESULTS_BASE = ROOT / "examples" / "irrigation_abm" / "results"
CRSS_CSV = ROOT / "ref" / "CRSS_DB" / "CRSS_DB" / "annual_baseline_time_series.csv"
OUTPUT_DIR = pathlib.Path(__file__).parent

YEAR_OFFSET = 2018  # simulation year 1 = calendar year 2019

# ── Auto-detect best available dataset ──
CANDIDATES = [
    ("v15", RESULTS_BASE / "production_v15_42yr"),
    ("phase_c", RESULTS_BASE / "production_phase_c_42yr"),
    ("v12", RESULTS_BASE / "v12_production_42yr_78agents"),
]

sim_log_path = None
audit_path = None
dataset_label = None

for label, result_dir in CANDIDATES:
    sim_p = result_dir / "simulation_log.csv"
    audit_p = result_dir / "irrigation_farmer_governance_audit.csv"
    if sim_p.exists() and audit_p.exists():
        sim_log_path = sim_p
        audit_path = audit_p
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
audit = pd.read_csv(audit_path, encoding="utf-8-sig")
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

# ── 3. Governance outcome categorization ──
def categorize_outcome(row):
    if row["status"] == "APPROVED" and row["retry_count"] == 0:
        return "APPROVED"
    elif row["status"] == "APPROVED" and row["retry_count"] > 0:
        return "RETRY_SUCCESS"
    else:
        return "REJECTED"

audit["outcome_cat"] = audit.apply(categorize_outcome, axis=1)

gov_yearly = audit.groupby("year")["outcome_cat"].value_counts(normalize=True).unstack(fill_value=0)
# Ensure all columns exist
for col in ["APPROVED", "RETRY_SUCCESS", "REJECTED"]:
    if col not in gov_yearly.columns:
        gov_yearly[col] = 0.0
gov_yearly = gov_yearly[["APPROVED", "RETRY_SUCCESS", "REJECTED"]]
gov_yearly["calendar_year"] = gov_yearly.index + YEAR_OFFSET

# ── 4. Compute statistics ──
mean_demand = comp["request_maf"].mean()
mean_crss = comp["total_maf"].mean()
cov_demand = comp["request_maf"].std() / mean_demand * 100
ratio = mean_demand / mean_crss

# Approval rate in final 10 years
final_10 = gov_yearly.iloc[-10:]
mean_approved_final = final_10["APPROVED"].mean()
mean_rejected_y1_5 = gov_yearly.iloc[:5]["REJECTED"].mean()

print(f"\nStatistics:")
print(f"  WAGF Mean Demand: {mean_demand:.2f} MAF/yr ({ratio:.2f}x CRSS)")
print(f"  CRSS Mean: {mean_crss:.2f} MAF/yr")
print(f"  CoV: {cov_demand:.1f}%")
print(f"  Early rejection (Y1-5): {mean_rejected_y1_5:.0%}")
print(f"  Late approval (Y33-42): {mean_approved_final:.0%}")

# ── 5. Colors ──
# Okabe-Ito accessible palette
C_CRSS = "#332288"       # indigo — CRSS baseline
C_REQUEST = "#44AA99"    # teal — WAGF request
C_DIVERSION = "#88CCEE"  # light blue — WAGF diversion
C_APPROVED = "#44AA99"   # teal
C_RETRY = "#DDCC77"      # sand/gold
C_REJECTED = "#CC6677"   # rose

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

# Statistics inset
stats_text = (
    f"WAGF: {mean_demand:.2f} MAF/yr "
    f"({ratio:.2f}× CRSS)\n"
    f"CoV = {cov_demand:.1f}%"
)
ax_a.text(
    0.98, 0.05, stats_text, transform=ax_a.transAxes,
    fontsize=7.5, ha="right", va="bottom",
    bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="gray", alpha=0.9),
)

ax_a.set_ylabel("Aggregate Demand (million AF/yr)")
ax_a.set_title("(a) Annual Water Demand: WAGF vs CRSS Baseline", fontweight="bold", loc="left")
ax_a.legend(framealpha=0.9, edgecolor="none", fontsize=7.5, loc="upper right")
ax_a.grid(True, alpha=0.2, linewidth=0.4)
ax_a.set_xlim(years.min(), years.max())
ax_a.yaxis.set_major_locator(mticker.MultipleLocator(1))
for spine in ["top", "right"]:
    ax_a.spines[spine].set_visible(False)

# ── Panel (b): Governance Outcomes ──
cal_years = gov_yearly["calendar_year"].values

ax_b.stackplot(
    cal_years,
    gov_yearly["APPROVED"].values * 100,
    gov_yearly["RETRY_SUCCESS"].values * 100,
    gov_yearly["REJECTED"].values * 100,
    labels=["Approved", "Retry Success", "Rejected"],
    colors=[C_APPROVED, C_RETRY, C_REJECTED],
    alpha=0.85,
)

# Annotate key transition — require 3+ consecutive years ≥70% APPROVED
consecutive = 0
transition_year = None
for yr in gov_yearly.index:
    if gov_yearly.loc[yr, "APPROVED"] >= 0.70:
        consecutive += 1
        if consecutive >= 3:
            transition_year = (yr - 2) + YEAR_OFFSET  # first year of the 3-run
            break
    else:
        consecutive = 0

if transition_year is not None:
    ax_b.axvline(transition_year, color="gray", ls=":", lw=0.8, alpha=0.6)
    ax_b.text(
        transition_year + 0.5, 92,
        f"Governance\nstabilized",
        fontsize=7, color="gray", va="top",
    )

ax_b.set_xlabel("Calendar Year")
ax_b.set_ylabel("Agent Decisions (%)")
ax_b.set_title("(b) Governance Intervention Outcomes", fontweight="bold", loc="left")
ax_b.legend(framealpha=0.9, edgecolor="none", fontsize=7.5, loc="center right")
ax_b.set_xlim(years.min(), years.max())
ax_b.set_ylim(0, 100)
ax_b.yaxis.set_major_locator(mticker.MultipleLocator(25))
ax_b.grid(True, alpha=0.2, linewidth=0.4)
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

