"""
Figure 3: SAGE-Governed Demand vs CRSS Baseline (WRR Technical Note)
================================================================
Panel (a): Upper Basin aggregate demand (CRSS vs SAGE Request vs SAGE Diversion)
Panel (b): Lower Basin aggregate demand (CRSS vs SAGE Request vs SAGE Diversion)

Three-line comparison per basin:
  CRSS Baseline  — static projected demand (dark, dashed)
  SAGE Request   — adaptive agent demand after governance (medium, solid)
  SAGE Diversion — actual allocation after curtailment (light, solid)

Data: production_4b_42yr_v9 (v9: corrected mass balance + Powell constraint)
      Falls back to v7 then v6 if not yet available.
CRSS reference: ref/CRSS_DB/CRSS_DB/

AGU/WRR: 300 DPI, serif, Okabe-Ito palette, 7.0 x 4.0 inches
"""
import pathlib, sys, re
import matplotlib
matplotlib.use("Agg")
import pandas as pd, numpy as np, matplotlib.pyplot as plt
import matplotlib.ticker as mticker

ROOT = pathlib.Path(__file__).resolve().parents[4]
CRSS_DIR = ROOT / "ref" / "CRSS_DB" / "CRSS_DB"
WG_DIR = CRSS_DIR / "Within_Group_Div"
LB_DIR = CRSS_DIR / "LB_Baseline_DB"

# --- v9 simulation log (corrected mass balance), fallback chain v9 → v7 → v6 ---
SIM_LOG_V9 = ROOT / "examples" / "irrigation_abm" / "results" / "production_4b_42yr_v9" / "simulation_log.csv"
SIM_LOG_V7 = ROOT / "examples" / "irrigation_abm" / "results" / "production_4b_42yr_v7" / "simulation_log.csv"
SIM_LOG_V6 = ROOT / "examples" / "irrigation_abm" / "results" / "production_4b_42yr_v6" / "simulation_log.csv"
if SIM_LOG_V9.exists():
    SIM_LOG = SIM_LOG_V9
    print(f"Using v9 data: {SIM_LOG}")
elif SIM_LOG_V7.exists():
    SIM_LOG = SIM_LOG_V7
    print(f"v9 not ready, falling back to v7: {SIM_LOG}")
elif SIM_LOG_V6.exists():
    SIM_LOG = SIM_LOG_V6
    print(f"Falling back to v6: {SIM_LOG}")
else:
    print(f"ERROR: No simulation log found (v9/v7/v6).")
    sys.exit(1)

YEAR_OFFSET = 2018  # simulation year 1 = calendar year 2019

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

# ── 1. Load CRSS Upper Basin baseline (Annual_*_Div_req.csv) ──
STATE_GROUPS = ["AZ", "CO1", "CO2", "CO3", "NM", "UT1", "UT2", "UT3", "WY"]

crss_ub_frames = []
for sg in STATE_GROUPS:
    fp = WG_DIR / f"Annual_{sg}_Div_req.csv"
    if not fp.exists():
        continue
    df = pd.read_csv(fp)
    df["year"] = range(1, len(df) + 1)
    melted = df.melt(id_vars="year", var_name="agent_id", value_name="crss_demand")
    crss_ub_frames.append(melted)

crss_ub = pd.concat(crss_ub_frames, ignore_index=True)
print(f"CRSS UB baseline: {crss_ub['agent_id'].nunique()} agents, years 1-{crss_ub['year'].max()}")

# ── 2. Load CRSS Lower Basin baseline (LB_Baseline_DB/*_Div_req.txt) ──
def parse_lb_baseline(txt_path):
    """Parse RiverWare monthly txt -> annual sum."""
    lines = txt_path.read_text().splitlines()
    slot_name = None
    data_lines = []
    for line in lines:
        if line.startswith("# Series Slot:"):
            m = re.search(r"Series Slot:\s+([^:]+):([^.]+)\.", line)
            if m:
                slot_name = f"{m.group(1).strip()}_{m.group(2).strip()}"
        elif not line.startswith(("start_date", "end_date", "timestep", "units", "scale", "#")) and line.strip():
            try:
                data_lines.append(float(line.strip()))
            except ValueError:
                pass
    if not data_lines:
        return None, None
    n_years = len(data_lines) // 12
    annual = [sum(data_lines[i*12:(i+1)*12]) for i in range(n_years)]
    return slot_name, annual

def normalize_name(name):
    return re.sub(r'\s+', '', name)

lb_div_files = sorted(LB_DIR.glob("*_Div_req.txt"))
lb_slot_data = {}
for f in lb_div_files:
    slot_name, annual = parse_lb_baseline(f)
    if slot_name and annual:
        lb_slot_data[slot_name] = annual

# ── 3. Load simulation log ──
sim = pd.read_csv(SIM_LOG)
print(f"Simulation log: {sim['agent_id'].nunique()} agents, years 1-{sim['year'].max()}")

ub_agents = set(sim[sim["basin"] == "upper_basin"]["agent_id"].unique())
lb_agents = set(sim[sim["basin"] == "lower_basin"]["agent_id"].unique())

# ── 4. Match agents ──
crss_ub_agents = set(crss_ub["agent_id"].unique())
ub_matched = ub_agents & crss_ub_agents
print(f"UB matched: {len(ub_matched)}/{len(ub_agents)} simulation agents")

lb_match = {}
for sim_agent in lb_agents:
    norm = normalize_name(sim_agent)
    for slot_key, annual in lb_slot_data.items():
        parts = slot_key.split("_", 1)
        slot_part = normalize_name(parts[1]) if len(parts) == 2 else normalize_name(parts[0])
        if slot_part == norm:
            lb_match[sim_agent] = slot_key
            break

for sim_agent in lb_agents:
    if sim_agent not in lb_match:
        norm = normalize_name(sim_agent)
        for slot_key in lb_slot_data:
            if norm in normalize_name(slot_key):
                lb_match[sim_agent] = slot_key
                break

MANUAL_LB_MAP = {
    "CRIR AZ": "ColoradoRiverIndianReservation_CRIR AZ",
    "CRIR CA": "ColoradoRiverIndianReservation_CRIR CA",
    "Fort Mohave Ind Res AZ": "FtMohaveReservation_Fort Mohave Ind Res AZ",
    "Fort Mohave Ind Res CA": "FtMohaveReservation_Fort Mohave Ind Res CA",
    "Chemehuevi Ind Res": "ChemehueviReservation_Chemehuevi Ind Res",
    "Quechan Res Unit": "AllAmericanCanalYumaProj_Quechan Res Unit",
    "Bard Unit": "AllAmericanCanalYumaProj_Bard Unit",
}
for sim_agent, slot_key in MANUAL_LB_MAP.items():
    if sim_agent in lb_agents and sim_agent not in lb_match and slot_key in lb_slot_data:
        lb_match[sim_agent] = slot_key

print(f"LB matched: {len(lb_match)}/{len(lb_agents)} simulation agents")

# ── 5. Build comparison dataframes ──
max_years = min(42, sim["year"].max())

# UB: request + diversion
sim_ub_req = sim[sim["agent_id"].isin(ub_matched)].groupby("year")["request"].sum().reset_index()
sim_ub_req.columns = ["year", "sage_request"]
sim_ub_div = sim[sim["agent_id"].isin(ub_matched)].groupby("year")["diversion"].sum().reset_index()
sim_ub_div.columns = ["year", "sage_diversion"]

crss_ub_agg = crss_ub[crss_ub["agent_id"].isin(ub_matched)].groupby("year")["crss_demand"].sum().reset_index()

ub_compare = pd.merge(crss_ub_agg, sim_ub_req, on="year", how="inner")
ub_compare = pd.merge(ub_compare, sim_ub_div, on="year", how="inner")
ub_compare["calendar_year"] = ub_compare["year"] + YEAR_OFFSET

# LB: request + diversion
lb_crss_annual = {}
for sim_agent, slot_key in lb_match.items():
    annual = lb_slot_data[slot_key]
    for yr_idx, val in enumerate(annual[:max_years]):
        yr = yr_idx + 1
        lb_crss_annual.setdefault(yr, 0)
        lb_crss_annual[yr] += val

sim_lb_req = sim[sim["agent_id"].isin(lb_match.keys())].groupby("year")["request"].sum().reset_index()
sim_lb_req.columns = ["year", "sage_request"]
sim_lb_div = sim[sim["agent_id"].isin(lb_match.keys())].groupby("year")["diversion"].sum().reset_index()
sim_lb_div.columns = ["year", "sage_diversion"]

lb_compare = pd.DataFrame([
    {"year": yr, "crss_demand": val} for yr, val in sorted(lb_crss_annual.items())
])
lb_compare = pd.merge(lb_compare, sim_lb_req, on="year", how="inner")
lb_compare = pd.merge(lb_compare, sim_lb_div, on="year", how="inner")
lb_compare["calendar_year"] = lb_compare["year"] + YEAR_OFFSET

# ── 6. Color palette (matched to reference image style) ──
# Reference: CRSS = dark blue, ABM-No RL = gray, ABM-CRSS = light blue
C_CRSS = "#1B2838"       # dark navy (CRSS baseline)
C_SAGE_REQ = "#808080"   # gray (SAGE request / "No RL" analogue)
C_SAGE_DIV = "#4A90D9"   # light blue (SAGE diversion / "ABM-CRSS" analogue)

# ── 7. Plot (2-panel: UB + LB) ──
fig, axes = plt.subplots(2, 1, figsize=(7.0, 4.0), constrained_layout=True)

# --- Panel (a): Upper Basin ---
ax = axes[0]
if not ub_compare.empty:
    years = ub_compare["calendar_year"]
    ax.plot(years, ub_compare["crss_demand"] / 1e6,
            color=C_CRSS, lw=2.0, label="CRSS Baseline", zorder=3)
    ax.plot(years, ub_compare["sage_request"] / 1e6,
            color=C_SAGE_REQ, lw=1.5, label="SAGE Request (governed)", zorder=2)
    ax.plot(years, ub_compare["sage_diversion"] / 1e6,
            color=C_SAGE_DIV, lw=2.0, label="SAGE Diversion (curtailed)", zorder=3)
    # Shade between CRSS and SAGE diversion
    ax.fill_between(years,
                    ub_compare["crss_demand"] / 1e6,
                    ub_compare["sage_diversion"] / 1e6,
                    alpha=0.08, color=C_SAGE_DIV)
    # Annotate paper water gap
    mid_yr = 2040
    ub_crss_mid = ub_compare[ub_compare["calendar_year"] == mid_yr]["crss_demand"].values
    ub_sage_mid = ub_compare[ub_compare["calendar_year"] == mid_yr]["sage_request"].values
    if len(ub_crss_mid) > 0 and len(ub_sage_mid) > 0:
        gap_y = (ub_crss_mid[0] / 1e6 + ub_sage_mid[0] / 1e6) / 2
        ax.annotate("Paper water\nvs wet water\ngap (~1.8×)",
                    xy=(mid_yr, gap_y), fontsize=6.5, color="#888888",
                    fontstyle="italic", ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#cccccc", alpha=0.9))
ax.set_ylabel("Demand (million AF/yr)")
ax.set_title("(a) Upper Basin Aggregate Demand", fontweight="bold", loc="left", fontsize=10)
ax.legend(framealpha=0.9, edgecolor="none", fontsize=7.5)
ax.grid(True, alpha=0.2)
ax.set_xlim(2019, 2019 + max_years - 1)
for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)

# --- Panel (b): Lower Basin ---
ax = axes[1]
if not lb_compare.empty:
    years = lb_compare["calendar_year"]
    ax.plot(years, lb_compare["crss_demand"] / 1e6,
            color=C_CRSS, lw=2.0, label="CRSS Baseline", zorder=3)
    ax.plot(years, lb_compare["sage_request"] / 1e6,
            color=C_SAGE_REQ, lw=1.5, label="SAGE Request (governed)", zorder=2)
    ax.plot(years, lb_compare["sage_diversion"] / 1e6,
            color=C_SAGE_DIV, lw=2.0, label="SAGE Diversion (curtailed)", zorder=3)
    ax.fill_between(years,
                    lb_compare["crss_demand"] / 1e6,
                    lb_compare["sage_diversion"] / 1e6,
                    alpha=0.08, color=C_SAGE_DIV)
ax.set_ylabel("Demand (million AF/yr)")
ax.set_title("(b) Lower Basin Aggregate Demand", fontweight="bold", loc="left", fontsize=10)
ax.legend(framealpha=0.9, edgecolor="none", fontsize=7.5)
ax.grid(True, alpha=0.2)
ax.set_xlim(2019, 2019 + max_years - 1)
for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)

# Add x-label to bottom panel only
axes[1].set_xlabel("Calendar Year")

# ── Save ──
out_dir = pathlib.Path(__file__).parent
fig.savefig(out_dir / "fig4_crss_comparison.png")
fig.savefig(out_dir / "fig4_crss_comparison.pdf")
plt.close()
print(f"\nSaved: {out_dir / 'fig4_crss_comparison.png'}")
print(f"Saved: {out_dir / 'fig4_crss_comparison.pdf'}")

# ── Summary statistics ──
if not ub_compare.empty:
    ub_req_delta = (ub_compare["sage_request"].sum() - ub_compare["crss_demand"].sum()) / ub_compare["crss_demand"].sum() * 100
    ub_div_delta = (ub_compare["sage_diversion"].sum() - ub_compare["crss_demand"].sum()) / ub_compare["crss_demand"].sum() * 100
    print(f"\nUB: SAGE request vs CRSS: {ub_req_delta:+.1f}%")
    print(f"UB: SAGE diversion vs CRSS: {ub_div_delta:+.1f}%")
if not lb_compare.empty:
    lb_req_delta = (lb_compare["sage_request"].sum() - lb_compare["crss_demand"].sum()) / lb_compare["crss_demand"].sum() * 100
    lb_div_delta = (lb_compare["sage_diversion"].sum() - lb_compare["crss_demand"].sum()) / lb_compare["crss_demand"].sum() * 100
    print(f"LB: SAGE request vs CRSS: {lb_req_delta:+.1f}%")
    print(f"LB: SAGE diversion vs CRSS: {lb_div_delta:+.1f}%")

# Year-by-year summary
print(f"\n--- Year-by-Year Basin Totals (million AF) ---")
print(f"{'Year':>6} {'UB CRSS':>10} {'UB SAGE':>10} {'UB Div':>10} | {'LB CRSS':>10} {'LB SAGE':>10} {'LB Div':>10}")
for _, row in ub_compare.iterrows():
    yr = int(row["year"])
    lb_row = lb_compare[lb_compare["year"] == yr]
    if not lb_row.empty:
        lb_r = lb_row.iloc[0]
        print(f"{int(row['calendar_year']):>6} "
              f"{row['crss_demand']/1e6:>10.2f} {row['sage_request']/1e6:>10.2f} {row['sage_diversion']/1e6:>10.2f} | "
              f"{lb_r['crss_demand']/1e6:>10.2f} {lb_r['sage_request']/1e6:>10.2f} {lb_r['sage_diversion']/1e6:>10.2f}")
