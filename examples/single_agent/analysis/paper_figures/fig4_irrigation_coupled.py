"""
Figure 4: Irrigation Case Study — Coupled Demand + Lake Mead Elevation
=====================================================================
Panel (a): Lake Mead elevation trajectory (v8 coupled vs CRSS static baseline)
Panel (b): Basin-level aggregate demand (UB + LB by cluster)
Panel (c): Annual decision composition (stacked area)

Comparable to Hung & Yang (2021) Fig 8 reservoir elevation plot.

Data: production_4b_42yr_v8 (mass balance coupling), fallback to v7
CRSS reference: ref/CRSS_DB/CRSS_DB/

AGU/WRR: 300 DPI, serif, Okabe-Ito palette, 7.0 x 5.5 inches
"""
import pathlib, sys
import matplotlib
matplotlib.use("Agg")
import pandas as pd, numpy as np, matplotlib.pyplot as plt
import matplotlib.ticker as mticker

ROOT = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
CRSS_DIR = ROOT / "ref" / "CRSS_DB" / "CRSS_DB"

# --- Data source: v8 (coupled) preferred, fallback to v7 ---
SIM_V8 = ROOT / "examples" / "irrigation_abm" / "results" / "production_4b_42yr_v8" / "simulation_log.csv"
SIM_V7 = ROOT / "examples" / "irrigation_abm" / "results" / "production_4b_42yr_v7" / "simulation_log.csv"
if SIM_V8.exists():
    SIM_LOG = SIM_V8
    VERSION = "v8"
    print(f"Using v8 data (coupled): {SIM_LOG}")
elif SIM_V7.exists():
    SIM_LOG = SIM_V7
    VERSION = "v7"
    print(f"v8 not ready, falling back to v7 (uncoupled): {SIM_LOG}")
else:
    print(f"ERROR: Neither v8 ({SIM_V8}) nor v7 ({SIM_V7}) found.")
    sys.exit(1)

YEAR_OFFSET = 2018  # simulation year 1 = calendar year 2019

# ── WRR Style ──
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 9,
    "axes.labelsize": 10,
    "axes.titlesize": 10,
    "legend.fontsize": 7.5,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.5,
    "ytick.major.width": 0.5,
})

# ── 1. Load simulation data ──
sim = pd.read_csv(SIM_LOG)
sim["calendar_year"] = sim["year"] + YEAR_OFFSET
max_year = sim["year"].max()
n_agents = sim["agent_id"].nunique()
print(f"Loaded: {n_agents} agents, {max_year} years, version={VERSION}")

# ── 2. Lake Mead elevation ──
has_mead_col = "lake_mead_level" in sim.columns

if has_mead_col:
    # v8 data has direct elevation logging (one value per year, same for all agents)
    mead_ts = sim.groupby("year")["lake_mead_level"].first().reset_index()
    mead_ts["calendar_year"] = mead_ts["year"] + YEAR_OFFSET
    print(f"Lake Mead elevation: Y1={mead_ts.iloc[0]['lake_mead_level']:.0f} ft, "
          f"Y{max_year}={mead_ts.iloc[-1]['lake_mead_level']:.0f} ft")
else:
    # v7: reconstruct from demand using mass balance post-hoc
    print("Reconstructing Lake Mead elevation from demand (no direct logging)...")
    from examples.irrigation_abm.irrigation_env import WaterSystemConfig
    cfg = WaterSystemConfig()

    # Elevation-storage lookup
    _S = np.array([2.0, 3.6, 5.8, 8.0, 9.5, 11.0, 13.0, 17.5, 23.3, 26.1])
    _E = np.array([895., 950., 1000., 1025., 1050., 1075., 1100., 1150., 1200., 1220.])

    # Load CRSS precipitation
    precip_path = CRSS_DIR / "HistoricalData" / "PrismWinterPrecip_ST_NOAA_Future.csv"
    if precip_path.exists():
        precip_df = pd.read_csv(precip_path, index_col=0) * 25.4
        ub_cols = ["WY", "UT1", "UT2", "UT3", "CO1", "CO2", "CO3"]
    else:
        precip_df = None

    storage = float(np.interp(cfg.mead_initial_elevation, _E, _S))
    mead_rows = []
    for yr in range(1, max_year + 1):
        cal_yr = yr + YEAR_OFFSET
        # Precipitation
        if precip_df is not None and cal_yr in precip_df.index:
            precip = float(precip_df.loc[cal_yr, ub_cols].mean())
        else:
            precip = cfg.precip_baseline_mm - 0.2 * yr

        nat_flow = cfg.natural_flow_base_maf * (precip / cfg.precip_baseline_mm)
        nat_flow = max(6.0, min(20.0, nat_flow))

        yr_data = sim[sim["year"] == yr]
        ub_div = yr_data[yr_data["basin"] == "upper_basin"]["diversion"].sum() / 1e6
        lb_div = yr_data[yr_data["basin"] == "lower_basin"]["diversion"].sum() / 1e6

        powell_rel = max(0, nat_flow - ub_div)
        inflow = powell_rel + cfg.lb_tributary_maf
        outflow = lb_div + cfg.mexico_treaty_maf + cfg.evaporation_maf + cfg.lb_municipal_maf
        storage = max(2.0, min(26.1, storage + inflow - outflow))
        elev = float(np.interp(storage, _S, _E))
        mead_rows.append({"year": yr, "calendar_year": cal_yr, "lake_mead_level": elev})

    mead_ts = pd.DataFrame(mead_rows)
    print(f"Reconstructed Mead: Y1={mead_rows[0]['lake_mead_level']:.0f} ft, "
          f"Y{max_year}={mead_rows[-1]['lake_mead_level']:.0f} ft")

# ── 3. Compute CRSS static baseline (constant initial demand) ──
# What would happen if agents never changed their demand from Year 1?
from examples.irrigation_abm.irrigation_env import WaterSystemConfig
cfg = WaterSystemConfig()
_S = np.array([2.0, 3.6, 5.8, 8.0, 9.5, 11.0, 13.0, 17.5, 23.3, 26.1])
_E = np.array([895., 950., 1000., 1025., 1050., 1075., 1100., 1150., 1200., 1220.])

precip_path = CRSS_DIR / "HistoricalData" / "PrismWinterPrecip_ST_NOAA_Future.csv"
if precip_path.exists():
    precip_df = pd.read_csv(precip_path, index_col=0) * 25.4
    ub_cols = ["WY", "UT1", "UT2", "UT3", "CO1", "CO2", "CO3"]
else:
    precip_df = None

# Year 1 diversions as static baseline
y1 = sim[sim["year"] == 1]
static_ub_div = y1[y1["basin"] == "upper_basin"]["diversion"].sum() / 1e6
static_lb_div = y1[y1["basin"] == "lower_basin"]["diversion"].sum() / 1e6

baseline_storage = float(np.interp(cfg.mead_initial_elevation, _E, _S))
baseline_rows = []
for yr in range(1, max_year + 1):
    cal_yr = yr + YEAR_OFFSET
    if precip_df is not None and cal_yr in precip_df.index:
        precip = float(precip_df.loc[cal_yr, ub_cols].mean())
    else:
        precip = cfg.precip_baseline_mm - 0.2 * yr
    nat_flow = cfg.natural_flow_base_maf * (precip / cfg.precip_baseline_mm)
    nat_flow = max(6.0, min(20.0, nat_flow))

    powell_rel = max(0, nat_flow - static_ub_div)
    inflow = powell_rel + cfg.lb_tributary_maf
    outflow = static_lb_div + cfg.mexico_treaty_maf + cfg.evaporation_maf + cfg.lb_municipal_maf
    baseline_storage = max(2.0, min(26.1, baseline_storage + inflow - outflow))
    elev = float(np.interp(baseline_storage, _S, _E))
    baseline_rows.append({"calendar_year": cal_yr, "lake_mead_level": elev})

baseline_ts = pd.DataFrame(baseline_rows)

# ── 4. Aggregate demand by cluster × basin ──
cluster_map = {"aggressive": "Aggressive", "forward_looking_conservative": "FLC",
               "myopic_conservative": "Myopic"}
sim["cluster_label"] = sim["cluster"].map(cluster_map).fillna(sim["cluster"])

# Basin-level aggregate demand by cluster
demand_by_cluster = sim.groupby(["calendar_year", "cluster_label"]).agg(
    total_request=("request", "sum"),
    total_diversion=("diversion", "sum")
).reset_index()

# ── 5. Decision composition ──
decisions = ["increase_demand", "decrease_demand", "maintain_demand",
             "adopt_efficiency", "reduce_acreage"]
decision_counts = sim.groupby(["calendar_year", "yearly_decision"]).size().unstack(fill_value=0)
for d in decisions:
    if d not in decision_counts.columns:
        decision_counts[d] = 0
decision_pct = decision_counts[decisions].div(decision_counts[decisions].sum(axis=1), axis=0) * 100

# ── 6. Shortage tier thresholds ──
TIER1_FT = cfg.mead_shortage_tier1  # 1075
TIER2_FT = cfg.mead_shortage_tier2  # 1050
TIER3_FT = cfg.mead_shortage_tier3  # 1025

# ── 7. Color palette ──
C_SAGE = "#0072B2"       # Blue — SAGE coupled
C_BASELINE = "#999999"   # Gray — static baseline
C_AGG = "#D55E00"        # Vermillion — Aggressive
C_FLC = "#009E73"        # Green — FLC
C_MYO = "#CC79A7"        # Pink — Myopic
C_DEC = {
    "increase_demand": "#D55E00",
    "maintain_demand": "#E69F00",
    "decrease_demand": "#009E73",
    "adopt_efficiency": "#0072B2",
    "reduce_acreage": "#CC79A7",
}

# ── 8. Plot (3-panel) ──
fig, axes = plt.subplots(3, 1, figsize=(7.0, 5.5), constrained_layout=True,
                         gridspec_kw={"height_ratios": [1.2, 1, 1]})

# --- Panel (a): Lake Mead Elevation ---
ax = axes[0]
years_bl = baseline_ts["calendar_year"]
ax.plot(years_bl, baseline_ts["lake_mead_level"],
        color=C_BASELINE, lw=1.5, ls="--", label="Static baseline (Y1 demand)", zorder=2)
ax.plot(mead_ts["calendar_year"], mead_ts["lake_mead_level"],
        color=C_SAGE, lw=2.0, label=f"SAGE coupled ({VERSION})", zorder=3)

# Shortage tier bands
ymin, ymax = 895, 1220
ax.axhspan(ymin, TIER3_FT, alpha=0.08, color="#D55E00", zorder=0)
ax.axhspan(TIER3_FT, TIER2_FT, alpha=0.05, color="#E69F00", zorder=0)
ax.axhspan(TIER2_FT, TIER1_FT, alpha=0.03, color="#E69F00", zorder=0)
ax.axhline(TIER1_FT, color="#888", lw=0.4, ls=":", zorder=1)
ax.axhline(TIER2_FT, color="#888", lw=0.4, ls=":", zorder=1)
ax.axhline(TIER3_FT, color="#888", lw=0.4, ls=":", zorder=1)
ax.text(2019.5, TIER1_FT + 2, "Tier 1", fontsize=6, color="#888", va="bottom")
ax.text(2019.5, TIER2_FT + 2, "Tier 2", fontsize=6, color="#888", va="bottom")
ax.text(2019.5, TIER3_FT + 2, "Tier 3", fontsize=6, color="#888", va="bottom")

ax.set_ylabel("Lake Mead Elevation (ft)")
ax.set_title("(a) Lake Mead Elevation", fontweight="bold", loc="left", fontsize=10)
ax.legend(loc="upper right", framealpha=0.9, edgecolor="none")
ax.set_ylim(ymin, ymax)
ax.set_xlim(2019, 2019 + max_year - 1)
ax.grid(True, alpha=0.15)
for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)

# --- Panel (b): Aggregate Demand by Cluster ---
ax = axes[1]
cluster_colors = {"Aggressive": C_AGG, "FLC": C_FLC, "Myopic": C_MYO}
for cl, grp in demand_by_cluster.groupby("cluster_label"):
    color = cluster_colors.get(cl, "#333")
    ax.plot(grp["calendar_year"], grp["total_diversion"] / 1e6,
            color=color, lw=1.8, label=cl, zorder=3)
    ax.plot(grp["calendar_year"], grp["total_request"] / 1e6,
            color=color, lw=0.8, ls=":", alpha=0.5, zorder=2)

ax.set_ylabel("Demand (million AF/yr)")
ax.set_title("(b) Aggregate Demand by Cluster (solid=diversion, dotted=request)",
             fontweight="bold", loc="left", fontsize=9)
ax.legend(loc="upper right", framealpha=0.9, edgecolor="none", ncol=3)
ax.set_xlim(2019, 2019 + max_year - 1)
ax.grid(True, alpha=0.15)
for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)

# --- Panel (c): Decision Composition ---
ax = axes[2]
years = decision_pct.index
bottom = np.zeros(len(years))
labels = {"increase_demand": "Increase", "maintain_demand": "Maintain",
          "decrease_demand": "Decrease", "adopt_efficiency": "Efficiency",
          "reduce_acreage": "Reduce acreage"}
for dec in decisions:
    vals = decision_pct[dec].values
    ax.fill_between(years, bottom, bottom + vals,
                    color=C_DEC[dec], alpha=0.75, label=labels[dec])
    bottom += vals

ax.set_ylabel("Share of Decisions (%)")
ax.set_xlabel("Calendar Year")
ax.set_title("(c) Annual Decision Composition", fontweight="bold", loc="left", fontsize=10)
ax.legend(loc="upper right", framealpha=0.9, edgecolor="none", ncol=3, fontsize=6.5)
ax.set_xlim(2019, 2019 + max_year - 1)
ax.set_ylim(0, 100)
ax.grid(True, alpha=0.15)
for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)

# ── Save ──
out_dir = pathlib.Path(__file__).parent
fig.savefig(out_dir / "fig4_irrigation_coupled.png")
fig.savefig(out_dir / "fig4_irrigation_coupled.pdf")
plt.close()
print(f"\nSaved: {out_dir / 'fig4_irrigation_coupled.png'}")
print(f"Saved: {out_dir / 'fig4_irrigation_coupled.pdf'}")

# ── Summary Statistics ──
print(f"\n--- Summary ({VERSION}) ---")
print(f"Agents: {n_agents}, Years: {max_year}")
if has_mead_col:
    y1_elev = mead_ts.iloc[0]["lake_mead_level"]
    yN_elev = mead_ts.iloc[-1]["lake_mead_level"]
    min_elev = mead_ts["lake_mead_level"].min()
    print(f"Mead elevation: {y1_elev:.0f} ft (Y1) → {yN_elev:.0f} ft (Y{max_year})")
    print(f"Mead minimum: {min_elev:.0f} ft (year {mead_ts.loc[mead_ts['lake_mead_level'].idxmin(), 'calendar_year']})")

total_req = sim.groupby("calendar_year")["request"].sum() / 1e6
total_div = sim.groupby("calendar_year")["diversion"].sum() / 1e6
print(f"Total request: {total_req.iloc[0]:.1f} MAF (Y1) → {total_req.iloc[-1]:.1f} MAF (Y{max_year})")
print(f"Total diversion: {total_div.iloc[0]:.1f} MAF (Y1) → {total_div.iloc[-1]:.1f} MAF (Y{max_year})")
