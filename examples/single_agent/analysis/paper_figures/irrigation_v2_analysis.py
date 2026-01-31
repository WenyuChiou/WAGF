"""
SAGE Irrigation Experiment v4 -- Comprehensive Analysis
========================================================
Production run v4 (post-fix)  |  Gemma3 4B  |  78 Colorado River Basin districts
42 simulated years  |  3 behavioral clusters
Context pipeline fix: persona + memory now correctly injected.

6-panel figure:
  (A) Action distribution by year  (stacked area)
  (B) Governance outcomes & retry rate over time
  (C) Action distribution by cluster (grouped bars)
  (D) Demand trajectory by cluster (% of initial allocation)
  (E) WSA/ACA appraisal distribution over time
  (F) Behavioral diversity metrics (Shannon entropy + maintain_demand %)

Data sources:
  irrigation_farmer_traces.jsonl
  reflection_log.jsonl

Usage:
  python irrigation_v2_analysis.py
"""

import json
import sys
import math
from pathlib import Path
from collections import defaultdict, Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# ============================================================
# Paths
# ============================================================
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]
TRACE_FILE = (
    REPO_ROOT / "examples" / "irrigation_abm" / "results"
    / "production_4b_42yr_v4" / "raw" / "irrigation_farmer_traces.jsonl"
)
REFLECTION_FILE = (
    REPO_ROOT / "examples" / "irrigation_abm" / "results"
    / "production_4b_42yr_v4" / "reflection_log.jsonl"
)

# ============================================================
# Style -- AGU/WRR-compatible
# ============================================================
plt.rcParams.update({
    "font.family":       "serif",
    "font.serif":        ["Times New Roman", "DejaVu Serif"],
    "font.size":         8,
    "axes.labelsize":    9,
    "axes.titlesize":    9,
    "legend.fontsize":   6.5,
    "xtick.labelsize":   7,
    "ytick.labelsize":   7,
    "figure.dpi":        300,
    "savefig.dpi":       300,
    "savefig.bbox":      "tight",
    "axes.linewidth":    0.5,
    "xtick.major.width": 0.4,
    "ytick.major.width": 0.4,
})

# Okabe-Ito color-blind friendly palette
C_AGG  = "#D55E00"   # vermillion  -- Aggressive
C_FLC  = "#0072B2"   # blue        -- Forward-looking Conservative
C_MYO  = "#009E73"   # teal        -- Myopic Conservative
C_BASE = "#666666"   # dark gray   -- baseline

# Action colors
C_MAINTAIN   = "#56B4E9"  # sky blue
C_ADOPT_EFF  = "#E69F00"  # orange
C_REDUCE_ACR = "#CC79A7"  # reddish purple
C_DECREASE   = "#0072B2"  # blue
C_INCREASE   = "#D55E00"  # vermillion

ACTION_COLORS = {
    "maintain_demand":  C_MAINTAIN,
    "adopt_efficiency": C_ADOPT_EFF,
    "reduce_acreage":   C_REDUCE_ACR,
    "decrease_demand":  C_DECREASE,
    "increase_demand":  C_INCREASE,
}
ACTION_LABELS = {
    "maintain_demand":  "Maintain demand",
    "adopt_efficiency": "Adopt efficiency",
    "reduce_acreage":   "Reduce acreage",
    "decrease_demand":  "Decrease demand",
    "increase_demand":  "Increase demand",
}
ACTION_ORDER = ["maintain_demand", "adopt_efficiency", "reduce_acreage",
                "decrease_demand", "increase_demand"]

APPRAISAL_ORDER = ["VL", "L", "M", "H", "VH"]
APPRAISAL_COLORS = {
    "VL": "#2166ac",
    "L":  "#67a9cf",
    "M":  "#f7f7f7",
    "H":  "#ef8a62",
    "VH": "#b2182b",
}

SIM_START = 2019
CLUSTER_NAMES = {
    "aggressive": "Aggressive",
    "forward_looking_conservative": "Fwd-looking Cons.",
    "myopic_conservative": "Myopic Cons.",
}
CLUSTER_ORDER = ["aggressive", "forward_looking_conservative", "myopic_conservative"]
CLUSTER_COLORS = {
    "aggressive": C_AGG,
    "forward_looking_conservative": C_FLC,
    "myopic_conservative": C_MYO,
}

# ============================================================
# Data loading
# ============================================================

def load_traces():
    """Parse trace JSONL into structured records."""
    if not TRACE_FILE.exists():
        print(f"ERROR: {TRACE_FILE} not found"); sys.exit(1)

    records = []
    agent_meta = {}

    with open(TRACE_FILE, encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            aid = obj["agent_id"]
            year = obj["year"]
            sb = obj.get("state_before", {})
            sa = obj.get("state_after", {})
            sp = obj.get("skill_proposal", {})
            reasoning = sp.get("reasoning", {})

            if aid not in agent_meta:
                wr = sb.get("water_right", sa.get("water_right", 0))
                agent_meta[aid] = {
                    "cluster": sb.get("cluster", "unknown"),
                    "water_right": wr,
                    "initial_demand": wr * 0.80,
                }

            # Unified appraisal extraction (WTA/WCA -> WSA/ACA rename mid-run)
            wsa = reasoning.get("WSA_LABEL", reasoning.get("WTA_LABEL", None))
            aca = reasoning.get("ACA_LABEL", reasoning.get("WCA_LABEL", None))

            records.append({
                "agent_id": aid,
                "year": year,
                "cluster": agent_meta[aid]["cluster"],
                "water_right": agent_meta[aid]["water_right"],
                "initial_demand": agent_meta[aid]["initial_demand"],
                "request_after": sa.get("request", None),
                "action": sp.get("skill_name", "unknown"),
                "outcome": obj.get("outcome", "UNKNOWN"),
                "retry_count": obj.get("retry_count", 0),
                "format_retries": obj.get("format_retries", 0),
                "wsa_label": wsa,
                "aca_label": aca,
                "validation_issues": obj.get("validation_issues", []),
                "env_drought": obj.get("environment_context", {}).get("drought_index", None),
            })

    return records, agent_meta


def load_reflections():
    """Parse reflection log."""
    if not REFLECTION_FILE.exists():
        return []
    with open(REFLECTION_FILE, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


# ============================================================
# Analysis helpers
# ============================================================

def action_dist_by_year(records, max_year=None):
    """Returns {year -> {action -> count}}."""
    dist = defaultdict(Counter)
    for r in records:
        if max_year is None or r["year"] <= max_year:
            dist[r["year"]][r["action"]] += 1
    return dist


def governance_by_year(records, max_year=None):
    """Returns per-year governance stats."""
    stats = defaultdict(lambda: {"total": 0, "approved": 0, "retry_success": 0,
                                  "retries": 0, "retry_decisions": 0})
    for r in records:
        if max_year is None or r["year"] <= max_year:
            y = r["year"]
            stats[y]["total"] += 1
            if r["outcome"] == "APPROVED":
                stats[y]["approved"] += 1
            elif r["outcome"] == "RETRY_SUCCESS":
                stats[y]["retry_success"] += 1
            if r["retry_count"] > 0:
                stats[y]["retries"] += r["retry_count"]
                stats[y]["retry_decisions"] += 1
    return stats


def action_by_cluster(records, max_year=None):
    """Returns {cluster -> {action -> count}}."""
    dist = defaultdict(Counter)
    for r in records:
        if max_year is None or r["year"] <= max_year:
            dist[r["cluster"]][r["action"]] += 1
    return dist


def demand_trajectories(records, agent_meta, max_year=None):
    """Compute cluster-level demand trajectories as % of initial allocation."""
    agent_series = defaultdict(dict)
    for r in records:
        if max_year is None or r["year"] <= max_year:
            agent_series[r["agent_id"]][r["year"]] = r["request_after"]

    all_years = sorted(set(r["year"] for r in records if max_year is None or r["year"] <= max_year))

    result = {}
    for cluster in CLUSTER_ORDER:
        c_agents = [a for a, m in agent_meta.items() if m["cluster"] == cluster]
        n_agents = len(c_agents)

        years_list = [0]
        means = [100.0]
        stds = [0.0]
        ns = [n_agents]

        for yr in all_years:
            pcts = []
            for aid in c_agents:
                req = agent_series[aid].get(yr)
                init = agent_meta[aid]["initial_demand"]
                if req is not None and init > 0:
                    pcts.append(req / init * 100.0)

            if len(pcts) >= max(2, int(np.ceil(n_agents * 0.9))):
                years_list.append(yr)
                means.append(np.mean(pcts))
                stds.append(np.std(pcts, ddof=1) if len(pcts) > 1 else 0.0)
                ns.append(len(pcts))

        years_arr = np.array(years_list)
        mean_arr = np.array(means)
        std_arr = np.array(stds)
        n_arr = np.array(ns, dtype=float)
        se = std_arr / np.sqrt(np.maximum(n_arr, 1))

        result[cluster] = {
            "years": years_arr,
            "mean_pct": mean_arr,
            "std_pct": std_arr,
            "lo": mean_arr - 1.96 * se,
            "hi": mean_arr + 1.96 * se,
            "n_agents": n_agents,
        }
    return result


def appraisal_by_year(records, max_year=None):
    """Returns {year -> {label -> count}} for WSA and ACA."""
    wsa_dist = defaultdict(Counter)
    aca_dist = defaultdict(Counter)
    for r in records:
        if max_year is None or r["year"] <= max_year:
            y = r["year"]
            if r["wsa_label"] and r["wsa_label"] in APPRAISAL_ORDER:
                wsa_dist[y][r["wsa_label"]] += 1
            if r["aca_label"] and r["aca_label"] in APPRAISAL_ORDER:
                aca_dist[y][r["aca_label"]] += 1
    return wsa_dist, aca_dist


def shannon_entropy(counter):
    """Shannon entropy in bits for a Counter."""
    total = sum(counter.values())
    if total == 0:
        return 0.0
    h = 0.0
    for c in counter.values():
        if c > 0:
            p = c / total
            h -= p * math.log2(p)
    return h


# ============================================================
# Summary report
# ============================================================

def print_report(records, agent_meta, reflections):
    """Print comprehensive summary to stdout."""
    max_year = max(r["year"] for r in records)
    total = len(records)
    all_years = sorted(set(r["year"] for r in records))

    print("=" * 72)
    print("  SAGE Irrigation Experiment v4 -- Comprehensive Analysis Report")
    print("=" * 72)
    print(f"  Model: Gemma3 4B  |  Run: production_4b_42yr_v4 (post-fix)")
    print(f"  Districts: 78  |  Years analyzed: {len(all_years)} (of 42)")
    print(f"  Total decision records: {total}")
    print(f"  Reflection log entries: {len(reflections)}")
    print()

    # --- Cluster composition ---
    print("--- Cluster Composition ---")
    for c in CLUSTER_ORDER:
        n = sum(1 for a, m in agent_meta.items() if m["cluster"] == c)
        print(f"  {CLUSTER_NAMES[c]:25s}: {n:3d} agents")
    print()

    # --- Overall action distribution ---
    print(f"--- Overall Action Distribution (yr 1-{max_year}) ---")
    action_totals = Counter(r["action"] for r in records)
    for act in ACTION_ORDER:
        cnt = action_totals.get(act, 0)
        print(f"  {ACTION_LABELS.get(act, act):25s}: {cnt:5d} ({cnt/total*100:5.1f}%)")
    print()

    # --- Action by cluster ---
    print("--- Action Distribution by Cluster ---")
    abc = action_by_cluster(records, max_year)
    for c in CLUSTER_ORDER:
        ct = sum(abc[c].values())
        print(f"  {CLUSTER_NAMES[c]} ({ct} decisions):")
        for act in ACTION_ORDER:
            cnt = abc[c].get(act, 0)
            if cnt > 0:
                print(f"    {ACTION_LABELS.get(act, act):25s}: {cnt:5d} ({cnt/ct*100:5.1f}%)")
        print()

    # --- Decision distribution by year ---
    print("--- Decision Distribution by Year ---")
    adist = action_dist_by_year(records)
    for y in all_years:
        n = sum(adist[y].values())
        parts = []
        for act in ACTION_ORDER:
            cnt = adist[y].get(act, 0)
            if cnt > 0:
                parts.append(f"{act[:8]}={cnt}")
        print(f"  Year {y:2d} (n={n:2d}): {', '.join(parts)}")
    print()

    # --- Governance / hallucination ---
    print("--- Governance Analysis ---")
    gov = governance_by_year(records, max_year)
    total_approved = sum(gov[y]["approved"] for y in all_years)
    total_retry = sum(gov[y]["retry_success"] for y in all_years)
    total_retries = sum(gov[y]["retries"] for y in all_years)
    total_retry_decisions = sum(gov[y]["retry_decisions"] for y in all_years)
    print(f"  APPROVED (first attempt): {total_approved} ({total_approved/total*100:.1f}%)")
    print(f"  RETRY_SUCCESS:            {total_retry} ({total_retry/total*100:.1f}%)")
    print(f"  Decisions requiring retry: {total_retry_decisions} ({total_retry_decisions/total*100:.1f}%)")
    print(f"  Total retries consumed:   {total_retries}")
    print()

    # Retry rate trend
    print("  Retry rate by year:")
    for y in all_years:
        g = gov[y]
        rate = g["retry_decisions"] / g["total"] * 100 if g["total"] > 0 else 0
        bar = "#" * int(rate / 2)
        print(f"    Year {y:2d}: {g['retry_decisions']:2d}/{g['total']:2d} = {rate:5.1f}% {bar}")
    print()

    # Governance rule triggers
    rule_counts = Counter()
    for r in records:
        for vi in r["validation_issues"]:
            rule_counts[vi.get("rule_id", "unknown")] += 1
    print("  Governance rules triggered:")
    for rule, cnt in rule_counts.most_common():
        print(f"    {rule}: {cnt}")
    print()

    # --- Appraisal analysis ---
    print("--- Appraisal Distribution (WSA = Water Scarcity Assessment) ---")
    wsa_d, aca_d = appraisal_by_year(records, max_year)
    print("  WSA by year:")
    for y in all_years:
        parts = []
        n_total = sum(wsa_d[y].values())
        for lbl in APPRAISAL_ORDER:
            cnt = wsa_d[y].get(lbl, 0)
            if cnt > 0:
                parts.append(f"{lbl}={cnt}")
        print(f"    Year {y:2d} (n={n_total:2d}): {', '.join(parts) if parts else 'NO DATA'}")
    print()
    print("  ACA by year:")
    for y in all_years:
        parts = []
        n_total = sum(aca_d[y].values())
        for lbl in APPRAISAL_ORDER:
            cnt = aca_d[y].get(lbl, 0)
            if cnt > 0:
                parts.append(f"{lbl}={cnt}")
        print(f"    Year {y:2d} (n={n_total:2d}): {', '.join(parts) if parts else 'NO DATA'}")
    print()

    # --- Behavioral diversity ---
    print("--- Behavioral Diversity (Shannon Entropy) ---")
    print("  Max possible entropy = log2(5) = {:.3f} bits (5 actions)".format(
        math.log2(5)))
    for y in all_years:
        h = shannon_entropy(adist[y])
        n_actions = sum(1 for v in adist[y].values() if v > 0)
        print(f"  Year {y:2d}: H = {h:.3f} bits  ({n_actions} unique actions)")
    print()

    # --- Demand trajectory summary ---
    print("--- Demand Trajectory Summary ---")
    traj = demand_trajectories(records, agent_meta, max_year)
    for c in CLUSTER_ORDER:
        d = traj[c]
        final_idx = -1
        if len(d["mean_pct"]) > 1:
            yr1_pct = d["mean_pct"][1]
            final_pct = d["mean_pct"][final_idx]
            final_yr = d["years"][final_idx]
            print(f"  {CLUSTER_NAMES[c]:25s} (n={d['n_agents']:2d}):")
            print(f"    Year 1 demand:  {yr1_pct:.1f}% of initial")
            print(f"    Year {int(final_yr):2d} demand: {final_pct:.1f}% of initial")
            print(f"    Reduction:      {100 - final_pct:.1f}%")
            print(f"    Std at final:   {d['std_pct'][final_idx]:.1f}%")
    print()

    # --- Key findings ---
    print("=" * 72)
    print("  KEY FINDINGS")
    print("=" * 72)

    # 1. Action diversity
    action_totals_all = Counter(r["action"] for r in records)
    n_unique = sum(1 for v in action_totals_all.values() if v > 0)
    print(f"  1. Action diversity: {n_unique} of 5 actions used")
    for act in ACTION_ORDER:
        cnt = action_totals_all.get(act, 0)
        print(f"     {ACTION_LABELS.get(act, act):25s}: {cnt:5d} ({cnt/total*100:.1f}%)")
    print()

    # 2. Behavioral entropy trend
    mid_yr = max_year // 2
    late_yr = max(5, int(max_year * 0.75))
    early_actions = Counter(r["action"] for r in records if r["year"] <= 5)
    mid_actions = Counter(r["action"] for r in records if mid_yr - 2 <= r["year"] <= mid_yr + 2)
    late_actions = Counter(r["action"] for r in records if r["year"] >= late_yr)
    early_h = shannon_entropy(early_actions)
    mid_h = shannon_entropy(mid_actions)
    late_h = shannon_entropy(late_actions)
    print(f"  2. Behavioral diversity (Shannon entropy):")
    print(f"     Early (yr 1-5):    H = {early_h:.3f} bits")
    print(f"     Middle (yr ~{mid_yr}):  H = {mid_h:.3f} bits")
    print(f"     Late (yr {late_yr}+):   H = {late_h:.3f} bits")
    print()

    # 3. Governance activity
    print(f"  3. Governance interventions: {total_retry} of {total} decisions "
          f"({total_retry/total*100:.1f}%)")
    print()

    # 4. Cluster differentiation
    final_demands = {}
    for c in CLUSTER_ORDER:
        d = traj[c]
        final_demands[c] = d["mean_pct"][-1]
    spread = max(final_demands.values()) - min(final_demands.values())
    print(f"  4. Cluster differentiation at final year:")
    for c in CLUSTER_ORDER:
        print(f"     {CLUSTER_NAMES[c]:25s}: {final_demands[c]:.1f}%")
    print(f"     Spread: {spread:.1f} percentage points")
    if spread >= 10:
        print("     Good cluster differentiation — persona-driven divergence")
    else:
        print("     NOTE: Limited cluster differentiation")
    print()

    # 5. EBE (Effective Behavioral Entropy) per year
    max_possible_h = math.log2(5)
    print(f"  5. Effective Behavioral Entropy (EBE) by year:")
    print(f"     EBE = H_norm × (1 - R_H), max possible = 1.0")
    prev_h = None
    for y in all_years:
        h = shannon_entropy(adist[y])
        h_norm = h / max_possible_h if max_possible_h > 0 else 0
        if prev_h is not None:
            r_h = abs(h - prev_h) / max_possible_h if max_possible_h > 0 else 0
        else:
            r_h = 0.0
        ebe = h_norm * (1 - r_h)
        prev_h = h
        if y <= 5 or y % 5 == 0 or y == max_year:
            print(f"     Year {y:2d}: H_norm={h_norm:.3f}, R_H={r_h:.3f}, EBE={ebe:.3f}")
    print()

    # 6. Appraisal distribution
    wsa_counts = Counter()
    for y in all_years:
        for lbl, cnt in wsa_d[y].items():
            wsa_counts[lbl] += cnt
    wsa_total = sum(wsa_counts.values())
    print(f"  6. WSA appraisal distribution (n={wsa_total}):")
    for lbl in APPRAISAL_ORDER:
        cnt = wsa_counts.get(lbl, 0)
        pct = cnt / wsa_total * 100 if wsa_total > 0 else 0
        print(f"     {lbl:3s}: {cnt:5d} ({pct:.1f}%)")
    print()

    print("=" * 72)


# ============================================================
# 6-Panel Figure
# ============================================================

def make_figure(records, agent_meta, reflections):
    max_year = max(r["year"] for r in records)
    all_years = sorted(set(r["year"] for r in records))

    fig, axes = plt.subplots(2, 3, figsize=(10, 6.5), constrained_layout=True)
    panel_labels = ["A", "B", "C", "D", "E", "F"]

    for idx, ax in enumerate(axes.flat):
        ax.text(-0.08, 1.06, panel_labels[idx], transform=ax.transAxes,
                fontsize=11, fontweight="bold", va="top", ha="right")

    # ============================================================
    # Panel A: Action distribution by year (stacked area)
    # ============================================================
    ax = axes[0, 0]
    adist = action_dist_by_year(records, max_year)
    years = np.array(all_years)

    # Build stacked arrays for actions actually present
    present_actions = []
    for act in ACTION_ORDER:
        if any(adist[y].get(act, 0) > 0 for y in all_years):
            present_actions.append(act)

    stacks = []
    for act in present_actions:
        vals = [adist[y].get(act, 0) / sum(adist[y].values()) * 100
                for y in all_years]
        stacks.append(vals)

    stacks = np.array(stacks)
    colors = [ACTION_COLORS[a] for a in present_actions]
    labels = [ACTION_LABELS[a] for a in present_actions]

    ax.stackplot(years, stacks, colors=colors, labels=labels, alpha=0.85)
    ax.set_xlabel("Simulation Year")
    ax.set_ylabel("Action Share (%)")
    ax.set_title("Action Distribution by Year")
    ax.set_xlim(1, max_year)
    ax.set_ylim(0, 100)
    ax.legend(loc="center right", fontsize=5.5, framealpha=0.9)
    ax.grid(True, alpha=0.15, linewidth=0.3)

    # ============================================================
    # Panel B: Governance outcomes & retry rate
    # ============================================================
    ax = axes[0, 1]
    gov = governance_by_year(records, max_year)

    approved_pct = [gov[y]["approved"] / gov[y]["total"] * 100 for y in all_years]
    retry_pct = [gov[y]["retry_success"] / gov[y]["total"] * 100 for y in all_years]
    retry_rate = [gov[y]["retry_decisions"] / gov[y]["total"] * 100 for y in all_years]

    ax.bar(years, approved_pct, color="#56B4E9", alpha=0.8, label="APPROVED", width=0.8)
    ax.bar(years, retry_pct, bottom=approved_pct, color="#E69F00", alpha=0.8,
           label="RETRY_SUCCESS", width=0.8)

    ax2 = ax.twinx()
    ax2.plot(years, retry_rate, color="#D55E00", linewidth=1.2, marker="o",
             markersize=2.5, label="Retry rate (%)", zorder=5)
    ax2.set_ylabel("Retry Rate (%)", color="#D55E00", fontsize=8)
    ax2.tick_params(axis="y", labelcolor="#D55E00")
    ax2.set_ylim(0, 30)

    ax.set_xlabel("Simulation Year")
    ax.set_ylabel("Outcome Share (%)")
    ax.set_title("Governance Outcomes & Retries")
    ax.set_xlim(0.5, max_year + 0.5)
    ax.set_ylim(0, 105)

    # Combined legend
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc="lower right",
              fontsize=5.5, framealpha=0.9)
    ax.grid(True, alpha=0.15, linewidth=0.3)

    # ============================================================
    # Panel C: Action distribution by cluster (grouped bars)
    # ============================================================
    ax = axes[0, 2]
    abc = action_by_cluster(records, max_year)

    x = np.arange(len(CLUSTER_ORDER))
    bar_width = 0.15
    present_in_cluster = [a for a in ACTION_ORDER
                          if any(abc[c].get(a, 0) > 0 for c in CLUSTER_ORDER)]

    for i, act in enumerate(present_in_cluster):
        vals = []
        for c in CLUSTER_ORDER:
            total_c = sum(abc[c].values())
            vals.append(abc[c].get(act, 0) / total_c * 100 if total_c > 0 else 0)
        offset = (i - len(present_in_cluster) / 2 + 0.5) * bar_width
        ax.bar(x + offset, vals, bar_width, color=ACTION_COLORS[act],
               label=ACTION_LABELS[act], alpha=0.85)

    ax.set_xlabel("Cluster")
    ax.set_ylabel("Action Share (%)")
    ax.set_title("Actions by Cluster")
    ax.set_xticks(x)
    ax.set_xticklabels([CLUSTER_NAMES[c] for c in CLUSTER_ORDER],
                       fontsize=6, rotation=15, ha="right")
    ax.legend(fontsize=5.5, loc="upper right", framealpha=0.9)
    ax.grid(True, axis="y", alpha=0.15, linewidth=0.3)

    # ============================================================
    # Panel D: Demand trajectory by cluster
    # ============================================================
    ax = axes[1, 0]
    traj = demand_trajectories(records, agent_meta, max_year)

    # Baseline
    ax.axhline(100, color=C_BASE, linestyle="--", linewidth=0.8, alpha=0.5,
               label="Initial allocation")

    markers = {"aggressive": "o", "forward_looking_conservative": "s",
               "myopic_conservative": "^"}

    for c in CLUSTER_ORDER:
        d = traj[c]
        cal = SIM_START + d["years"]
        color = CLUSTER_COLORS[c]
        label = f"{CLUSTER_NAMES[c]} (n={d['n_agents']})"

        ax.fill_between(cal, d["lo"], d["hi"], color=color, alpha=0.10)
        ax.plot(cal, d["mean_pct"], color=color, linewidth=1.3, label=label)
        ax.plot(cal[1:], d["mean_pct"][1:], color=color, linewidth=0,
                marker=markers[c], markersize=2.5, markeredgewidth=0.3,
                markeredgecolor="white")

    ax.set_xlabel("Year")
    ax.set_ylabel("Demand (% of Initial)")
    ax.set_title("Water Demand Trajectories")
    ax.set_ylim(0, 115)
    ax.set_xlim(SIM_START - 0.5, SIM_START + max_year + 1)
    ax.legend(fontsize=5.5, loc="upper right", framealpha=0.9)
    ax.grid(True, alpha=0.15, linewidth=0.3)

    # Final value annotations
    for c in CLUSTER_ORDER:
        d = traj[c]
        final_yr = SIM_START + d["years"][-1]
        final_val = d["mean_pct"][-1]
        ax.annotate(f"{final_val:.0f}%", xy=(final_yr, final_val),
                    xytext=(final_yr + 0.5, final_val + 3),
                    fontsize=5.5, color=CLUSTER_COLORS[c], fontweight="bold")

    # ============================================================
    # Panel E: WSA & ACA appraisal distribution (stacked bars, two rows)
    # ============================================================
    ax = axes[1, 1]
    wsa_d, aca_d = appraisal_by_year(records, max_year)

    # Use WSA -- more variation in later years
    # Stacked bar for WSA
    bottoms = np.zeros(len(all_years))
    for lbl in APPRAISAL_ORDER:
        vals = []
        for y in all_years:
            total_y = sum(wsa_d[y].values())
            vals.append(wsa_d[y].get(lbl, 0) / total_y * 100 if total_y > 0 else 0)
        vals = np.array(vals)
        ax.bar(years, vals, bottom=bottoms, color=APPRAISAL_COLORS[lbl],
               label=f"WSA={lbl}", width=0.8, alpha=0.85,
               edgecolor="white", linewidth=0.2)
        bottoms += vals

    ax.set_xlabel("Simulation Year")
    ax.set_ylabel("WSA Distribution (%)")
    ax.set_title("Water Scarcity Appraisal (WSA)")
    ax.set_xlim(0.5, max_year + 0.5)
    ax.set_ylim(0, 105)
    ax.legend(fontsize=5.5, loc="lower right", framealpha=0.9, ncol=2)
    ax.grid(True, alpha=0.15, linewidth=0.3)

    # (v4: annotation removed -- post-fix data shows more variation)

    # ============================================================
    # Panel F: Behavioral diversity (Shannon entropy + maintain%)
    # ============================================================
    ax = axes[1, 2]
    adist = action_dist_by_year(records, max_year)

    entropies = [shannon_entropy(adist[y]) for y in all_years]
    maintain_pct = [adist[y].get("maintain_demand", 0) / sum(adist[y].values()) * 100
                    for y in all_years]

    max_h = math.log2(5)

    color_h = "#0072B2"
    color_m = "#D55E00"

    ax.plot(years, entropies, color=color_h, linewidth=1.3, marker="o",
            markersize=2.5, label="Shannon entropy (H)")
    ax.axhline(max_h, color=color_h, linestyle=":", linewidth=0.6, alpha=0.4)
    ax.set_ylabel("Shannon Entropy (bits)", color=color_h)
    ax.tick_params(axis="y", labelcolor=color_h)
    ax.set_ylim(0, max_h + 0.3)

    ax3 = ax.twinx()
    ax3.plot(years, maintain_pct, color=color_m, linewidth=1.3, marker="s",
             markersize=2.5, label="Maintain %")
    ax3.set_ylabel("Maintain-demand (%)", color=color_m, fontsize=8)
    ax3.tick_params(axis="y", labelcolor=color_m)
    ax3.set_ylim(0, 105)

    # (v4: mode-collapse zone removed -- post-fix data shows diversity)

    ax.set_xlabel("Simulation Year")
    ax.set_title("Behavioral Diversity")
    ax.set_xlim(0.5, max_year + 0.5)

    lines_a, labels_a = ax.get_legend_handles_labels()
    lines_b, labels_b = ax3.get_legend_handles_labels()
    ax.legend(lines_a + lines_b, labels_a + labels_b, loc="center right",
              fontsize=5.5, framealpha=0.9)
    ax.grid(True, alpha=0.15, linewidth=0.3)

    # ============================================================
    # Suptitle
    # ============================================================
    fig.suptitle(
        f"SAGE Irrigation Experiment v4 -- Gemma3 4B, 78 Districts, "
        f"{max_year}/42 Years (post-fix)",
        fontsize=10, fontweight="bold", y=1.02,
    )

    # ============================================================
    # Save
    # ============================================================
    out_png = SCRIPT_DIR / "irrigation_v2_analysis.png"
    out_pdf = SCRIPT_DIR / "irrigation_v2_analysis.pdf"

    fig.savefig(out_png, dpi=300)
    print(f"Saved: {out_png}")
    fig.savefig(out_pdf, dpi=300)
    print(f"Saved: {out_pdf}")
    plt.close()


# ============================================================
# Main
# ============================================================

def main():
    records, agent_meta = load_traces()
    reflections = load_reflections()

    print_report(records, agent_meta, reflections)
    make_figure(records, agent_meta, reflections)


if __name__ == "__main__":
    main()
