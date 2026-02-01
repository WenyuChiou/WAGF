"""
Figure 4: SAGE-Governed Demand vs CRSS Baseline (WRR Technical Note)
================================================================
Panel (a): Upper Basin aggregate demand
Panel (b): Lower Basin aggregate demand
Panel (c): Demand by behavioral cluster (% of initial)

Data: production_4b_42yr_v6 (P0+P1 economic hallucination fix)
CRSS reference: ref/CRSS_DB/CRSS_DB/

AGU/WRR: 300 DPI, serif, Okabe-Ito palette, 7.0 x 8.5 inches
"""
import pathlib, sys, re
import matplotlib
matplotlib.use("Agg")
import pandas as pd, numpy as np, matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parents[4]
CRSS_DIR = ROOT / "ref" / "CRSS_DB" / "CRSS_DB"
WG_DIR = CRSS_DIR / "Within_Group_Div"
LB_DIR = CRSS_DIR / "LB_Baseline_DB"

# --- v6 simulation log (P0+P1 fix) ---
SIM_LOG = ROOT / "examples" / "irrigation_abm" / "results" / "production_4b_42yr_v6" / "simulation_log.csv"
if not SIM_LOG.exists():
    print(f"ERROR: {SIM_LOG} not found. Run v6 production first.")
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
UB_BASIN_MAP = {}  # agent_id -> state_group

crss_ub_frames = []
for sg in STATE_GROUPS:
    fp = WG_DIR / f"Annual_{sg}_Div_req.csv"
    if not fp.exists():
        continue
    df = pd.read_csv(fp)
    for col in df.columns:
        UB_BASIN_MAP[col] = sg
    df["year"] = range(1, len(df) + 1)
    melted = df.melt(id_vars="year", var_name="agent_id", value_name="crss_demand")
    crss_ub_frames.append(melted)

crss_ub = pd.concat(crss_ub_frames, ignore_index=True)
print(f"CRSS UB baseline: {crss_ub['agent_id'].nunique()} agents, years 1-{crss_ub['year'].max()}")

# ── 2. Load CRSS Lower Basin baseline (LB_Baseline_DB/*_Div_req.txt) ──
def parse_lb_baseline(txt_path):
    """Parse RiverWare monthly txt -> annual sum. Returns (slot_name, annual_df)."""
    lines = txt_path.read_text().splitlines()
    # Extract slot name from header comment (line 6 usually)
    slot_name = None
    data_lines = []
    for line in lines:
        if line.startswith("# Series Slot:"):
            # e.g. "# Series Slot: AgAboveRandlette:AgUteCurr.Diversion Requested ..."
            # Some slot names contain spaces (e.g. "CRIR AZ", "Bard Unit")
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
    # Monthly to annual: 12 months per year
    n_years = len(data_lines) // 12
    annual = [sum(data_lines[i*12:(i+1)*12]) for i in range(n_years)]
    return slot_name, annual

# Build mapping: simulation agent_id -> LB baseline file slot name
# LB agent IDs have spaces; filenames compress spaces away
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
print(f"  Using: {SIM_LOG.name} from {SIM_LOG.parent.name}")

# Detect basin from log
ub_agents = set(sim[sim["basin"] == "upper_basin"]["agent_id"].unique())
lb_agents = set(sim[sim["basin"] == "lower_basin"]["agent_id"].unique())

# ── 4. Match agents ──
# UB: direct name match with CRSS Annual files
crss_ub_agents = set(crss_ub["agent_id"].unique())
ub_matched = ub_agents & crss_ub_agents
print(f"UB matched: {len(ub_matched)}/{len(ub_agents)} simulation agents")

# LB: match via normalized name against lb_slot_data keys
# lb_slot_data keys are like "Group_Slot", sim agent_ids are "Slot" (with spaces)
# Build reverse lookup: normalized slot part -> full slot key
lb_match = {}
for sim_agent in lb_agents:
    norm = normalize_name(sim_agent)
    for slot_key, annual in lb_slot_data.items():
        # slot_key is "Group_Slot" -> check if Slot part matches
        parts = slot_key.split("_", 1)
        if len(parts) == 2:
            slot_part = normalize_name(parts[1])
        else:
            slot_part = normalize_name(parts[0])
        if slot_part == norm:
            lb_match[sim_agent] = slot_key
            break

# Fallback: match normalized sim agent anywhere in normalized slot_key
for sim_agent in lb_agents:
    if sim_agent not in lb_match:
        norm = normalize_name(sim_agent)
        for slot_key in lb_slot_data:
            if norm in normalize_name(slot_key):
                lb_match[sim_agent] = slot_key
                break

# Final fallback: manual mappings for known mismatches
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
if lb_agents - set(lb_match.keys()):
    print(f"  Unmatched LB: {lb_agents - set(lb_match.keys())}")

# ── 5. Build comparison dataframes ──
max_years = min(42, sim["year"].max())

# UB aggregate
sim_ub = sim[sim["agent_id"].isin(ub_matched)].groupby("year")["request"].sum().reset_index()
sim_ub.columns = ["year", "sage_demand"]

crss_ub_agg = crss_ub[crss_ub["agent_id"].isin(ub_matched)].groupby("year")["crss_demand"].sum().reset_index()

ub_compare = pd.merge(crss_ub_agg, sim_ub, on="year", how="inner")
ub_compare["calendar_year"] = ub_compare["year"] + YEAR_OFFSET

# LB aggregate
lb_crss_annual = {}
for sim_agent, slot_key in lb_match.items():
    annual = lb_slot_data[slot_key]
    for yr_idx, val in enumerate(annual[:max_years]):
        yr = yr_idx + 1
        lb_crss_annual.setdefault(yr, 0)
        lb_crss_annual[yr] += val

sim_lb = sim[sim["agent_id"].isin(lb_match.keys())].groupby("year")["request"].sum().reset_index()
sim_lb.columns = ["year", "sage_demand"]

lb_compare = pd.DataFrame([
    {"year": yr, "crss_demand": val} for yr, val in sorted(lb_crss_annual.items())
])
lb_compare = pd.merge(lb_compare, sim_lb, on="year", how="inner")
lb_compare["calendar_year"] = lb_compare["year"] + YEAR_OFFSET

# Cluster trajectories (% of initial)
cluster_data = []
for cluster in sim["cluster"].unique():
    csub = sim[sim["cluster"] == cluster].copy()
    # Get initial request per agent (year 1)
    init = csub[csub["year"] == 1].set_index("agent_id")["request"].to_dict()
    for yr in range(1, max_years + 1):
        yr_sub = csub[csub["year"] == yr]
        pcts = []
        for _, row in yr_sub.iterrows():
            base = init.get(row["agent_id"])
            if base and base > 0:
                pcts.append(row["request"] / base * 100)
        if pcts:
            cluster_data.append({
                "year": yr,
                "calendar_year": yr + YEAR_OFFSET,
                "cluster": cluster,
                "pct_mean": np.mean(pcts),
                "pct_std": np.std(pcts),
            })

cluster_df = pd.DataFrame(cluster_data)

# ── 6. Plot (WRR: Okabe-Ito, serif, 300 DPI) ──
# Okabe-Ito palette
C_AGG = "#D55E00"   # vermillion (aggressive)
C_FLC = "#0072B2"   # blue (forward-looking conservative)
C_MYO = "#009E73"   # teal (myopic conservative)
C_CRSS = "#555555"  # dark gray (CRSS baseline)
C_SAGE = "#0072B2"  # blue (SAGE governed)

CLUSTER_LABELS = {
    "aggressive": "Aggressive (n=67)",
    "forward_looking_conservative": "FLC (n=5)",
    "myopic_conservative": "Myopic (n=6)",
}
CLUSTER_COLORS = {
    "aggressive": C_AGG,
    "forward_looking_conservative": C_FLC,
    "myopic_conservative": C_MYO,
}
CLUSTER_MARKERS = {
    "aggressive": "o",
    "forward_looking_conservative": "s",
    "myopic_conservative": "^",
}

fig, axes = plt.subplots(3, 1, figsize=(7.0, 8.5), constrained_layout=True)

# Panel (a): Upper Basin
ax = axes[0]
if not ub_compare.empty:
    ax.plot(ub_compare["calendar_year"], ub_compare["crss_demand"] / 1e6,
            color=C_CRSS, lw=1.8, ls="--", label="CRSS Baseline", zorder=3)
    ax.plot(ub_compare["calendar_year"], ub_compare["sage_demand"] / 1e6,
            color=C_SAGE, lw=1.8, label="SAGE Governed (v6)", zorder=3)
    ax.fill_between(ub_compare["calendar_year"],
                    ub_compare["crss_demand"] / 1e6,
                    ub_compare["sage_demand"] / 1e6,
                    alpha=0.10, color=C_SAGE)
ax.set_ylabel("Demand (million AF/yr)")
ax.set_title("(a) Upper Basin Aggregate Demand", fontweight="bold", loc="left", fontsize=9)
ax.legend(framealpha=0.9, edgecolor="none")
ax.grid(True, alpha=0.2)
ax.set_xlim(2019, 2019 + max_years - 1)

# Panel (b): Lower Basin
ax = axes[1]
if not lb_compare.empty:
    ax.plot(lb_compare["calendar_year"], lb_compare["crss_demand"] / 1e6,
            color=C_CRSS, lw=1.8, ls="--", label="CRSS Baseline", zorder=3)
    ax.plot(lb_compare["calendar_year"], lb_compare["sage_demand"] / 1e6,
            color=C_SAGE, lw=1.8, label="SAGE Governed (v6)", zorder=3)
    ax.fill_between(lb_compare["calendar_year"],
                    lb_compare["crss_demand"] / 1e6,
                    lb_compare["sage_demand"] / 1e6,
                    alpha=0.10, color=C_SAGE)
ax.set_ylabel("Demand (million AF/yr)")
ax.set_title("(b) Lower Basin Aggregate Demand", fontweight="bold", loc="left", fontsize=9)
ax.legend(framealpha=0.9, edgecolor="none")
ax.grid(True, alpha=0.2)
ax.set_xlim(2019, 2019 + max_years - 1)

# Panel (c): Cluster trajectories
ax = axes[2]
ax.axhline(100, color="gray", ls="--", lw=0.8, alpha=0.5, label="Initial allocation (100%)", zorder=1)

# 10% floor line
ax.axhline(10, color=C_FLC, ls=":", lw=0.8, alpha=0.6, label="MIN_UTIL floor (10%)", zorder=1)

for cluster in ["aggressive", "forward_looking_conservative", "myopic_conservative"]:
    cdf = cluster_df[cluster_df["cluster"] == cluster]
    if cdf.empty:
        continue
    label = CLUSTER_LABELS.get(cluster, cluster)
    color = CLUSTER_COLORS.get(cluster, "gray")
    mkr = CLUSTER_MARKERS.get(cluster, "o")
    ax.plot(cdf["calendar_year"], cdf["pct_mean"], color=color, lw=1.8,
            marker=mkr, ms=3, markevery=3, label=label, zorder=3)
    ax.fill_between(cdf["calendar_year"],
                    cdf["pct_mean"] - cdf["pct_std"],
                    cdf["pct_mean"] + cdf["pct_std"],
                    alpha=0.10, color=color)

ax.set_ylabel("Demand (% of initial allocation)")
ax.set_xlabel("Calendar Year")
ax.set_title("(c) Demand by Behavioral Cluster", fontweight="bold", loc="left", fontsize=9)
ax.legend(framealpha=0.9, edgecolor="none", ncol=2, fontsize=7)
ax.grid(True, alpha=0.2)
ax.set_xlim(2019, 2019 + max_years - 1)
ax.set_ylim(-5, 130)

out_dir = pathlib.Path(__file__).parent
fig.savefig(out_dir / "fig4_crss_comparison.png")
fig.savefig(out_dir / "fig4_crss_comparison.pdf")
plt.close()
print(f"\nSaved: {out_dir / 'fig4_crss_comparison.png'}")
print(f"Saved: {out_dir / 'fig4_crss_comparison.pdf'}")

# Summary statistics
if not ub_compare.empty:
    ub_delta = (ub_compare["sage_demand"].sum() - ub_compare["crss_demand"].sum()) / ub_compare["crss_demand"].sum() * 100
    print(f"UB total demand delta: {ub_delta:+.1f}% (SAGE vs CRSS)")
if not lb_compare.empty:
    lb_delta = (lb_compare["sage_demand"].sum() - lb_compare["crss_demand"].sum()) / lb_compare["crss_demand"].sum() * 100
    print(f"LB total demand delta: {lb_delta:+.1f}% (SAGE vs CRSS)")

# Cluster final values
print("\n--- Cluster Demand at Year 42 (% of initial) ---")
for cluster in ["aggressive", "forward_looking_conservative", "myopic_conservative"]:
    cdf = cluster_df[cluster_df["cluster"] == cluster]
    if not cdf.empty:
        final = cdf[cdf["year"] == max_years]
        if not final.empty:
            print(f"  {cluster}: {final['pct_mean'].values[0]:.1f}% +/- {final['pct_std'].values[0]:.1f}%")
