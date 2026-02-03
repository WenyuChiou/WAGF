"""
Figure 4: SAGE Irrigation — Basin-Level Demand + Decision Composition
=====================================================================
(a) Upper Basin cluster demand trajectories (% of water right)
(b) Lower Basin cluster demand trajectories (% of water right)
(c) Upper Basin annual decision composition (stacked area)
(d) Lower Basin annual decision composition (stacked area)

Mirrors Hung & Yang (2021) Fig 8 regional separation.
Data: production_4b_42yr_v7 (simulation_log.csv)
AGU/WRR: 300 DPI, serif, Okabe-Ito palette
"""
import pathlib, sys
import matplotlib
matplotlib.use("Agg")
import pandas as pd, numpy as np, matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parents[4]
SIM_LOG = ROOT / "examples" / "irrigation_abm" / "results" / "production_4b_42yr_v7" / "simulation_log.csv"
if not SIM_LOG.exists():
    print(f"ERROR: {SIM_LOG} not found"); sys.exit(1)

SIM_START = 2019

# ── WRR Style ──
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 9,
    "axes.labelsize": 10,
    "axes.titlesize": 10,
    "legend.fontsize": 7,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.5,
    "ytick.major.width": 0.5,
})

# ── Okabe-Ito palette ──
CLUSTER_ORDER = ["aggressive", "forward_looking_conservative", "myopic_conservative"]
CLUSTER_NAMES = {
    "aggressive": "Aggressive",
    "forward_looking_conservative": "Fwd-Looking Cons.",
    "myopic_conservative": "Myopic Cons.",
}
CLUSTER_COLORS = {
    "aggressive": "#D55E00",
    "forward_looking_conservative": "#0072B2",
    "myopic_conservative": "#009E73",
}
CLUSTER_MARKERS = {"aggressive": "o", "forward_looking_conservative": "s", "myopic_conservative": "^"}

ACTION_ORDER = ["increase_demand", "maintain_demand", "decrease_demand", "reduce_acreage", "adopt_efficiency"]
ACTION_COLORS = {
    "increase_demand":  "#D55E00",
    "maintain_demand":  "#56B4E9",
    "decrease_demand":  "#0072B2",
    "reduce_acreage":   "#CC79A7",
    "adopt_efficiency": "#E69F00",
}
ACTION_LABELS = {
    "increase_demand":  "Increase",
    "maintain_demand":  "Maintain",
    "decrease_demand":  "Decrease",
    "reduce_acreage":   "Reduce acreage",
    "adopt_efficiency": "Adopt efficiency",
}

# ── Load ──
sim = pd.read_csv(SIM_LOG)
max_year = sim["year"].max()
all_years = sorted(sim["year"].unique())
cal_years = np.array([SIM_START + y - 1 for y in all_years])
print(f"Loaded: {sim['agent_id'].nunique()} agents, years 1-{max_year}")

# ── Helpers ──

def cluster_trajectories_pct_wr(basin_sim):
    """Compute mean demand as % of water_right per cluster."""
    results = {}
    for c in CLUSTER_ORDER:
        csim = basin_sim[basin_sim["cluster"] == c]
        agents = csim["agent_id"].unique()
        n = len(agents)
        if n == 0:
            continue

        years_out, means, lo95, hi95 = [], [], [], []
        for yr in all_years:
            yr_data = csim[csim["year"] == yr]
            if yr_data.empty:
                continue
            pcts = (yr_data["request"] / yr_data["water_right"] * 100).dropna().values
            if len(pcts) >= max(1, n // 2):
                m = pcts.mean()
                se = pcts.std(ddof=1) / np.sqrt(len(pcts)) if len(pcts) > 1 else 0
                years_out.append(yr)
                means.append(m)
                lo95.append(m - 1.96 * se)
                hi95.append(m + 1.96 * se)

        if years_out:
            results[c] = {
                "years": np.array(years_out),
                "mean": np.array(means),
                "lo": np.array(lo95),
                "hi": np.array(hi95),
                "n": n,
            }
    return results


def action_shares_by_year(basin_sim):
    """Compute action share (%) by year for a basin subset."""
    shares = {}
    for act in ACTION_ORDER:
        vals = []
        for yr in all_years:
            yr_data = basin_sim[basin_sim["year"] == yr]
            n_total = len(yr_data)
            n_act = len(yr_data[yr_data["yearly_decision"] == act])
            vals.append(n_act / n_total * 100 if n_total > 0 else 0)
        shares[act] = np.array(vals)
    return shares


def plot_trajectories(ax, traj, title):
    """Plot cluster demand trajectories on a given axes."""
    ax.axhline(100, color="#999999", ls="--", lw=0.7, alpha=0.5, label="Water right (100%)")

    for c in CLUSTER_ORDER:
        if c not in traj:
            continue
        d = traj[c]
        cy = SIM_START + d["years"] - 1
        color = CLUSTER_COLORS[c]
        n = d["n"]
        label = f"{CLUSTER_NAMES[c]} (n={n})"

        ax.fill_between(cy, d["lo"], d["hi"], color=color, alpha=0.12)
        ax.plot(cy, d["mean"], color=color, lw=1.8, label=label)
        # Markers every 5 years
        mask = (d["years"] % 5 == 1) | (d["years"] == d["years"][-1])
        ax.plot(cy[mask], d["mean"][mask], color=color, lw=0,
                marker=CLUSTER_MARKERS[c], ms=3.5, mew=0.3, mec="white")

        # Final annotation
        final_val = d["mean"][-1]
        final_yr = cy[-1]
        ax.annotate(f"{final_val:.0f}%", xy=(final_yr, final_val),
                    xytext=(5, 0), textcoords="offset points",
                    fontsize=6.5, color=color, fontweight="bold", va="center")

    ax.set_title(title, fontweight="bold", loc="left")
    ax.set_ylabel("Demand (% of Water Right)")
    ax.set_xlim(SIM_START, SIM_START + max_year - 1)
    ax.set_ylim(0, 130)
    ax.legend(loc="upper right", framealpha=0.9, edgecolor="none", fontsize=6)
    ax.grid(True, alpha=0.2)
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)


def plot_composition(ax, shares, title, n_agents):
    """Plot stacked area decision composition."""
    stacks = [shares[act] for act in ACTION_ORDER]
    colors = [ACTION_COLORS[act] for act in ACTION_ORDER]
    labels = [ACTION_LABELS[act] for act in ACTION_ORDER]

    ax.stackplot(cal_years, stacks, colors=colors, labels=labels, alpha=0.85)
    ax.set_title(title, fontweight="bold", loc="left")
    ax.set_ylabel("Decision Share (%)")
    ax.set_xlim(SIM_START, SIM_START + max_year - 1)
    ax.set_ylim(0, 100)
    ax.legend(loc="center right", framealpha=0.9, edgecolor="none", fontsize=5.5)
    ax.grid(True, alpha=0.2)
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)


# ── Split by basin ──
ub_sim = sim[sim["basin"] == "upper_basin"]
lb_sim = sim[sim["basin"] == "lower_basin"]
n_ub = ub_sim["agent_id"].nunique()
n_lb = lb_sim["agent_id"].nunique()

ub_traj = cluster_trajectories_pct_wr(ub_sim)
lb_traj = cluster_trajectories_pct_wr(lb_sim)
ub_shares = action_shares_by_year(ub_sim)
lb_shares = action_shares_by_year(lb_sim)

# ── 2×2 Figure ──
fig, axes = plt.subplots(2, 2, figsize=(7.5, 5.5), constrained_layout=True)

plot_trajectories(axes[0, 0], ub_traj,
                  f"(a) Upper Basin Demand by Cluster (n={n_ub})")
plot_trajectories(axes[0, 1], lb_traj,
                  f"(b) Lower Basin Demand by Cluster (n={n_lb})")
plot_composition(axes[1, 0], ub_shares,
                 f"(c) Upper Basin Decision Composition", n_ub)
plot_composition(axes[1, 1], lb_shares,
                 f"(d) Lower Basin Decision Composition", n_lb)

axes[1, 0].set_xlabel("Calendar Year")
axes[1, 1].set_xlabel("Calendar Year")

# ── Save ──
out_dir = pathlib.Path(__file__).parent
for ext in ["png", "pdf"]:
    fig.savefig(out_dir / f"fig4_irrigation_dual.{ext}")
    print(f"Saved: {out_dir / f'fig4_irrigation_dual.{ext}'}")
plt.close()

# ── Summary ──
print(f"\n--- Upper Basin (n={n_ub}) ---")
for c, d in ub_traj.items():
    print(f"  {CLUSTER_NAMES[c]:25s} (n={d['n']:2d}): Y1={d['mean'][0]:.1f}% -> Y42={d['mean'][-1]:.1f}% of WR")
print(f"\n--- Lower Basin (n={n_lb}) ---")
for c, d in lb_traj.items():
    print(f"  {CLUSTER_NAMES[c]:25s} (n={d['n']:2d}): Y1={d['mean'][0]:.1f}% -> Y42={d['mean'][-1]:.1f}% of WR")
