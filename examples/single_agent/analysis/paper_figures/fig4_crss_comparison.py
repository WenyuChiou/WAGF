"""
Figure 4: SAGE-Governed Demand vs CRSS Baseline (Hung & Yang 2021 style)
Panel (a): Upper Basin aggregate demand
Panel (b): Lower Basin aggregate demand
Panel (c): Demand by behavioral cluster (% of initial)
"""
import pathlib, pandas as pd, numpy as np, matplotlib.pyplot as plt, re

ROOT = pathlib.Path(__file__).resolve().parents[4]
CRSS_DIR = ROOT / "ref" / "CRSS_DB" / "CRSS_DB"
WG_DIR = CRSS_DIR / "Within_Group_Div"
LB_DIR = CRSS_DIR / "LB_Baseline_DB"

# --- Pick best available simulation log ---
V5_LOG = ROOT / "examples" / "irrigation_abm" / "results" / "v5_rebalanced" / "simulation_log.csv"
V4_LOG = ROOT / "examples" / "irrigation_abm" / "results" / "production_4b_42yr_v4" / "simulation_log.csv"
SIM_LOG = V5_LOG if V5_LOG.exists() else V4_LOG

YEAR_OFFSET = 2018  # simulation year 1 = calendar year 2019

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

# ── 6. Plot ──
CLUSTER_LABELS = {
    "aggressive": "Aggressive",
    "forward_looking_conservative": "Forward-Looking\nConservative",
    "myopic_conservative": "Myopic\nConservative",
}
CLUSTER_COLORS = {
    "aggressive": "#d62728",
    "forward_looking_conservative": "#1f77b4",
    "myopic_conservative": "#2ca02c",
}

fig, axes = plt.subplots(3, 1, figsize=(8, 10), dpi=150)
fig.subplots_adjust(hspace=0.35)

# Panel (a): Upper Basin
ax = axes[0]
if not ub_compare.empty:
    ax.plot(ub_compare["calendar_year"], ub_compare["crss_demand"] / 1e6,
            color="#1a3a5c", linewidth=2.2, label="CRSS Baseline", zorder=3)
    ax.plot(ub_compare["calendar_year"], ub_compare["sage_demand"] / 1e6,
            color="#2196F3", linewidth=2.2, label="SAGE Governed", zorder=3)
    ax.fill_between(ub_compare["calendar_year"],
                    ub_compare["crss_demand"] / 1e6,
                    ub_compare["sage_demand"] / 1e6,
                    alpha=0.15, color="#2196F3")
ax.set_ylabel("Demand (million acre-ft/yr)", fontsize=10)
ax.set_title("(a) Upper Basin Aggregate Demand", fontsize=11, fontweight="bold", loc="left")
ax.legend(fontsize=9, framealpha=0.9)
ax.grid(True, alpha=0.3)
ax.set_xlim(2019, 2019 + max_years - 1)

# Panel (b): Lower Basin
ax = axes[1]
if not lb_compare.empty:
    ax.plot(lb_compare["calendar_year"], lb_compare["crss_demand"] / 1e6,
            color="#1a3a5c", linewidth=2.2, label="CRSS Baseline", zorder=3)
    ax.plot(lb_compare["calendar_year"], lb_compare["sage_demand"] / 1e6,
            color="#2196F3", linewidth=2.2, label="SAGE Governed", zorder=3)
    ax.fill_between(lb_compare["calendar_year"],
                    lb_compare["crss_demand"] / 1e6,
                    lb_compare["sage_demand"] / 1e6,
                    alpha=0.15, color="#2196F3")
ax.set_ylabel("Demand (million acre-ft/yr)", fontsize=10)
ax.set_title("(b) Lower Basin Aggregate Demand", fontsize=11, fontweight="bold", loc="left")
ax.legend(fontsize=9, framealpha=0.9)
ax.grid(True, alpha=0.3)
ax.set_xlim(2019, 2019 + max_years - 1)

# Panel (c): Cluster trajectories
ax = axes[2]
ax.axhline(100, color="gray", linestyle="--", linewidth=1.2, label="CRSS Baseline (100%)", zorder=1)
for cluster in ["aggressive", "forward_looking_conservative", "myopic_conservative"]:
    cdf = cluster_df[cluster_df["cluster"] == cluster]
    if cdf.empty:
        continue
    label = CLUSTER_LABELS.get(cluster, cluster)
    color = CLUSTER_COLORS.get(cluster, "gray")
    ax.plot(cdf["calendar_year"], cdf["pct_mean"], color=color, linewidth=2, label=label, zorder=3)
    ax.fill_between(cdf["calendar_year"],
                    cdf["pct_mean"] - cdf["pct_std"],
                    cdf["pct_mean"] + cdf["pct_std"],
                    alpha=0.12, color=color)
ax.set_ylabel("Demand (% of initial allocation)", fontsize=10)
ax.set_xlabel("Year", fontsize=10)
ax.set_title("(c) Demand by Behavioral Cluster", fontsize=11, fontweight="bold", loc="left")
ax.legend(fontsize=8, framealpha=0.9, ncol=2)
ax.grid(True, alpha=0.3)
ax.set_xlim(2019, 2019 + max_years - 1)

out_dir = pathlib.Path(__file__).parent
fig.savefig(out_dir / "fig4_crss_comparison.png", bbox_inches="tight", dpi=200)
plt.close()
print(f"\nSaved: {out_dir / 'fig4_crss_comparison.png'}")

# Summary statistics
if not ub_compare.empty:
    ub_delta = (ub_compare["sage_demand"].sum() - ub_compare["crss_demand"].sum()) / ub_compare["crss_demand"].sum() * 100
    print(f"UB total demand delta: {ub_delta:+.1f}% (SAGE vs CRSS)")
if not lb_compare.empty:
    lb_delta = (lb_compare["sage_demand"].sum() - lb_compare["crss_demand"].sum()) / lb_compare["crss_demand"].sum() * 100
    print(f"LB total demand delta: {lb_delta:+.1f}% (SAGE vs CRSS)")
