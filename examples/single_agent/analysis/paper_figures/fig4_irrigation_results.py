"""
SAGE Paper -- Figure 4: Irrigation Demand Management Results
=============================================================
Colorado River Basin case study -- 78 irrigation districts, 42 years
(post-fix production run v4: persona + memory pipeline corrected).

Single-panel figure showing demand trajectories by behavioral cluster:
  - Aggressive (n=67)
  - Forward-looking Conservative (n=5)
  - Myopic Conservative (n=6)
  - Maintain-demand baseline (counterfactual: all agents hold initial demand)

Y-axis: demand as % of initial water right (year-0 = 80% utilization).
X-axis: simulation year (2019 + year offset).

Data source:
  examples/irrigation_abm/results/production_4b_42yr_v4/raw/
      irrigation_farmer_traces.jsonl

Cluster definitions from Hung & Yang (2021), mapped through:
  examples/irrigation_abm/config/agent_types.yaml

AGU/WRR figure requirements:
  - 300 DPI, serif font (Times New Roman / DejaVu Serif)
  - Color-blind friendly palette (Okabe-Ito)

Usage:
  python fig4_irrigation_results.py
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# ---------- paths ----------
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]  # governed_broker_framework/
TRACE_FILE = (
    REPO_ROOT
    / "examples" / "irrigation_abm" / "results"
    / "production_4b_42yr_v4" / "raw" / "irrigation_farmer_traces.jsonl"
)

# ---------- style (consistent with fig3) ----------
plt.rcParams.update({
    "font.family":       "serif",
    "font.serif":        ["Times New Roman", "DejaVu Serif"],
    "font.size":         9,
    "axes.labelsize":    10,
    "axes.titlesize":    10,
    "legend.fontsize":   7,
    "xtick.labelsize":   8,
    "ytick.labelsize":   8,
    "figure.dpi":        300,
    "savefig.dpi":       300,
    "savefig.bbox":      "tight",
    "axes.linewidth":    0.6,
    "xtick.major.width": 0.5,
    "ytick.major.width": 0.5,
})

# Okabe-Ito color-blind friendly palette
C_AGG  = "#D55E00"   # vermillion  -- Aggressive
C_FLC  = "#0072B2"   # blue        -- Forward-looking Conservative
C_MYO  = "#009E73"   # teal        -- Myopic Conservative
C_BASE = "#666666"   # dark gray   -- maintain_demand baseline

SIM_START = 2019     # simulation calendar start


# ================================================================
# Data loading
# ================================================================

def load_traces():
    """
    Parse the production JSONL trace file and return a list of dicts:
      {agent_id, year, cluster, water_right, request_after, skill}

    For year 1, request_before is absent; we infer the initial demand
    as 0.80 * water_right (the 80% utilization stated in the personas).
    """
    if not TRACE_FILE.exists():
        print(f"ERROR: Trace file not found:\n  {TRACE_FILE}")
        sys.exit(1)

    records = []
    agent_meta = {}  # agent_id -> {cluster, water_right, initial_demand}

    with open(TRACE_FILE, encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            aid = obj["agent_id"]
            year = obj["year"]
            sb = obj.get("state_before", {})
            sa = obj.get("state_after", {})
            skill = obj.get("approved_skill", {}).get("skill_name", "unknown")

            # Capture agent metadata on first encounter
            if aid not in agent_meta:
                wr = sb.get("water_right", sa.get("water_right", 0))
                agent_meta[aid] = {
                    "cluster": sb.get("cluster", sa.get("cluster", "unknown")),
                    "water_right": wr,
                    "initial_demand": wr * 0.80,
                }

            records.append({
                "agent_id": aid,
                "year": year,
                "cluster": agent_meta[aid]["cluster"],
                "water_right": agent_meta[aid]["water_right"],
                "initial_demand": agent_meta[aid]["initial_demand"],
                "request_after": sa.get("request", None),
                "skill": skill,
            })

    return records, agent_meta


def compute_cluster_trajectories(records, agent_meta):
    """
    For each cluster, compute:
      - mean demand as % of initial water-right per year
      - std for confidence bands
      - n (number of agents contributing)

    Returns dict[cluster] = {years, mean_pct, std_pct, lo_pct, hi_pct, n}
    """
    clusters = ["aggressive", "forward_looking_conservative", "myopic_conservative"]

    # Build per-agent time series: agent -> {year -> request_after}
    agent_series = defaultdict(dict)
    for r in records:
        agent_series[r["agent_id"]][r["year"]] = r["request_after"]

    all_years = sorted(set(r["year"] for r in records))

    # Insert a synthetic year-0 point at 100% for all clusters
    result = {}
    for cluster in clusters:
        cluster_agents = [aid for aid, m in agent_meta.items()
                          if m["cluster"] == cluster]
        n_agents = len(cluster_agents)

        # Year 0 = pre-simulation baseline (100% of initial demand)
        valid_years = [0]
        yearly_means = [100.0]
        yearly_stds = [0.0]
        yearly_ns = [n_agents]

        for yr in all_years:
            pcts = []
            for aid in cluster_agents:
                req = agent_series[aid].get(yr)
                if req is not None and agent_meta[aid]["initial_demand"] > 0:
                    pct = (req / agent_meta[aid]["initial_demand"]) * 100.0
                    pcts.append(pct)

            # Only include years where all (or nearly all) agents reported
            # This avoids biased means from partially-completed years
            if len(pcts) >= max(2, int(np.ceil(n_agents * 0.9))):
                valid_years.append(yr)
                yearly_means.append(np.mean(pcts))
                yearly_stds.append(np.std(pcts, ddof=1) if len(pcts) > 1 else 0.0)
                yearly_ns.append(len(pcts))

        years_arr = np.array(valid_years)
        mean_arr = np.array(yearly_means)
        std_arr = np.array(yearly_stds)
        n_arr = np.array(yearly_ns)

        # 95% CI approximation: mean +/- 1.96 * SE
        se_arr = std_arr / np.sqrt(np.maximum(n_arr, 1))
        lo = mean_arr - 1.96 * se_arr
        hi = mean_arr + 1.96 * se_arr

        result[cluster] = {
            "years": years_arr,
            "mean_pct": mean_arr,
            "std_pct": std_arr,
            "lo_pct": lo,
            "hi_pct": hi,
            "n": n_arr,
            "n_agents": n_agents,
        }

    return result


# ================================================================
# Figure
# ================================================================

def main():
    records, agent_meta = load_traces()
    traj = compute_cluster_trajectories(records, agent_meta)

    # Determine year range
    all_years = sorted(set(r["year"] for r in records))
    max_year = max(all_years)

    fig, ax = plt.subplots(figsize=(3.5, 3.5), constrained_layout=True)

    # ---- Maintain-demand baseline ----
    baseline_x = [SIM_START, SIM_START + max_year]
    ax.plot(
        baseline_x, [100.0, 100.0],
        color=C_BASE, linestyle="--", linewidth=1.0, alpha=0.6,
        label="Maintain-demand baseline", zorder=1,
    )

    # ---- Cluster trajectories ----
    cluster_config = [
        ("aggressive",
         C_AGG, "Aggressive (n={n})", "o", "-"),
        ("forward_looking_conservative",
         C_FLC, "Fwd-looking Cons. (n={n})", "s", "-"),
        ("myopic_conservative",
         C_MYO, "Myopic Cons. (n={n})", "^", "-"),
    ]

    for cluster, color, label_tmpl, marker, ls in cluster_config:
        d = traj[cluster]
        cal = SIM_START + d["years"]
        label = label_tmpl.format(n=d["n_agents"])

        # Confidence band (95% CI)
        ax.fill_between(
            cal, d["lo_pct"], d["hi_pct"],
            color=color, alpha=0.10, zorder=2,
        )

        # Mean line -- plot full line, then overlay markers for years 1+
        ax.plot(
            cal, d["mean_pct"],
            color=color, linewidth=1.5, linestyle=ls,
            label=label, zorder=3,
        )
        # Markers only on actual simulation years (skip synthetic year 0)
        ax.plot(
            cal[1:], d["mean_pct"][1:],
            color=color, linewidth=0, linestyle="none",
            marker=marker, markersize=2.8, markeredgewidth=0.4,
            markeredgecolor="white", zorder=4,
        )

    # ---- Drought severity context ----
    # Light shading to indicate the aridification scenario period
    ax.axvspan(SIM_START, SIM_START + max_year, color="#FFF3CD",
               alpha=0.15, zorder=0)

    # ---- Preliminary annotation ----
    # Use the actual number of complete years (max of valid years across clusters)
    n_complete = max(
        len(traj[c]["years"]) - 1  # subtract synthetic year 0
        for c in traj
    )
    ax.text(
        0.97, 0.03,
        f"Preliminary ({n_complete}/42 yr)",
        transform=ax.transAxes,
        fontsize=6, ha="right", va="bottom",
        color="gray", fontstyle="italic",
        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="lightgray",
                  alpha=0.9, lw=0.4),
    )

    # ---- Formatting ----
    # Use the last complete year (from trajectory data, not raw records)
    last_complete_yr = max(
        int(traj[c]["years"][-1]) for c in traj
    )
    ax.set_xlabel("Year")
    ax.set_ylabel("Water Demand (% of Initial Allocation)")
    ax.set_xlim(SIM_START - 0.3, SIM_START + last_complete_yr + 1.5)
    ax.set_ylim(0, 115)

    # X ticks every 4 years
    xtick_years = list(range(SIM_START, SIM_START + last_complete_yr + 1, 4))
    ax.set_xticks(xtick_years)
    ax.tick_params(axis="x", rotation=45)

    # Y ticks
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.yaxis.set_minor_locator(mticker.MultipleLocator(10))

    ax.legend(
        loc="upper right", framealpha=0.95, edgecolor="none",
        handlelength=1.6, borderpad=0.35, labelspacing=0.30,
        fontsize=6.5,
    )

    ax.grid(True, alpha=0.15, linewidth=0.4)
    ax.grid(True, which="minor", alpha=0.08, linewidth=0.3)

    # ---- Final-value annotations ----
    # Sort clusters by final value to avoid overlap
    final_vals = []
    for cluster, color, _, _, _ in cluster_config:
        d = traj[cluster]
        final_yr = SIM_START + d["years"][-1]
        final_val = d["mean_pct"][-1]
        final_vals.append((cluster, color, final_yr, final_val))

    final_vals.sort(key=lambda x: x[3], reverse=True)  # highest first

    # Place labels with spacing to avoid overlap
    prev_y = None
    min_gap = 4.0  # minimum gap in % units
    for cluster, color, final_yr, final_val in final_vals:
        label_y = final_val
        if prev_y is not None and abs(label_y - prev_y) < min_gap:
            label_y = prev_y - min_gap
        prev_y = label_y

        ax.annotate(
            f"{final_val:.0f}%",
            xy=(final_yr, final_val),
            xytext=(final_yr + 0.6, label_y),
            fontsize=6, color=color, fontweight="bold",
            ha="left", va="center",
            arrowprops=dict(arrowstyle="-", color=color, lw=0.4)
            if abs(label_y - final_val) > 1.5 else None,
        )

    # ---- Demand reduction annotation ----
    # Arrow showing overall reduction from baseline
    mid_yr = SIM_START + 12
    agg_mid = traj["aggressive"]["mean_pct"][12]  # year 12 index
    ax.annotate(
        "",
        xy=(mid_yr, agg_mid + 2),
        xytext=(mid_yr, 98),
        arrowprops=dict(
            arrowstyle="<->", color=C_BASE, lw=0.7,
            connectionstyle="arc3,rad=0",
        ),
    )
    ax.text(
        mid_yr + 0.3, (100 + agg_mid) / 2,
        "Demand\nreduction",
        fontsize=5.5, color=C_BASE, va="center", ha="left",
        fontstyle="italic",
    )

    # ==============================================================
    # Save
    # ==============================================================
    out_png = SCRIPT_DIR / "fig4_irrigation_results.png"
    out_pdf = SCRIPT_DIR / "fig4_irrigation_results.pdf"

    fig.savefig(out_png, dpi=300)
    print(f"Saved: {out_png}")

    fig.savefig(out_pdf, dpi=300)
    print(f"Saved: {out_pdf}")

    plt.close()

    # ------ Summary statistics ------
    print("\n--- Cluster Summary (Production Run) ---")
    for cluster in ["aggressive", "forward_looking_conservative",
                     "myopic_conservative"]:
        d = traj[cluster]
        # Skip year-0 synthetic point (index 0)
        print(f"  {cluster}:")
        print(f"    n_agents = {d['n_agents']}")
        print(f"    Year 1 mean demand  = {d['mean_pct'][1]:.1f}% of initial")
        print(f"    Final mean demand   = {d['mean_pct'][-1]:.1f}% of initial")
        print(f"    Overall reduction   = {100.0 - d['mean_pct'][-1]:.1f}%")
        print(f"    Years simulated     = {len(d['years']) - 1}")
        print()

    # Action frequency table
    print("--- Action Frequencies by Cluster ---")
    from collections import Counter
    for cluster in ["aggressive", "forward_looking_conservative",
                     "myopic_conservative"]:
        actions = Counter(
            r["skill"] for r in records if r["cluster"] == cluster
        )
        total = sum(actions.values())
        print(f"  {cluster} ({total} decisions):")
        for act, cnt in actions.most_common():
            print(f"    {act:25s} {cnt:5d} ({cnt/total*100:5.1f}%)")
        print()


if __name__ == "__main__":
    main()
