#!/usr/bin/env python3
"""
Cross-Seed Robustness Analysis for Paper 3 (hybrid_v2)
======================================================
Compares key metrics across 3 seeds (42, 123, 456) to establish reproducibility.

Outputs:
  1. Validation metrics comparison table (EPI, L1, L2 benchmarks)
  2. Decision distribution stability (action proportions per seed)
  3. RQ1: Traditional ABM vs LLM-ABM convergence/divergence consistency
  4. RQ2: Full (hybrid_v2) vs Ablation B (flat baseline) comparison stability
  5. RQ3: PMT dynamics (TP accumulation, CP ceiling, TP-CP gap, adaptation fatigue)
  6. Summary figures (multi-panel)
"""

import json
import csv
import os
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

warnings.filterwarnings("ignore", category=FutureWarning)


def safe_print(*args, **kwargs):
    """Windows cp950-safe print wrapper."""
    try:
        print(*args, **kwargs)  # noqa: safe_print-internal
    except UnicodeEncodeError:
        text = " ".join(str(a) for a in args)
        print(text.encode("ascii", errors="replace").decode("ascii"), **kwargs)  # noqa: safe_print-internal

# ============================================================
# PATHS
# ============================================================
BASE = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework")
FLOOD_DIR = BASE / "examples" / "multi_agent" / "flood"
HYBRID_DIR = FLOOD_DIR / "paper3" / "results" / "paper3_hybrid_v2"
ABLATION_DIR = FLOOD_DIR / "paper3" / "results" / "paper3_ablation_flat_baseline"
PROFILES_CSV = FLOOD_DIR / "data" / "agent_profiles_balanced.csv"
OUT_DIR = HYBRID_DIR / "analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SEEDS = [42, 123, 456]
OWNER_SKILLS = ["buy_insurance", "elevate_house", "buyout_program", "do_nothing"]
RENTER_SKILLS = ["buy_contents_insurance", "relocate", "do_nothing"]
ALL_SKILLS = OWNER_SKILLS + RENTER_SKILLS
PMT_MAP = {"VL": 0, "L": 1, "M": 2, "H": 3, "VH": 4}

# ============================================================
# DATA LOADING
# ============================================================

def load_profiles():
    """Load agent profiles."""
    profiles = {}
    with open(PROFILES_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            profiles[row["agent_id"]] = {
                "mg": row["mg"].strip().lower() == "true",
                "tenure": row["tenure"].strip(),
            }
    return profiles


def load_traces(seed, base_dir=None):
    """Load all household traces for a given seed.

    Args:
        seed: Seed number.
        base_dir: Base directory (defaults to HYBRID_DIR).
    """
    if base_dir is None:
        base_dir = HYBRID_DIR
    raw_dir = base_dir / f"seed_{seed}" / "gemma3_4b_strict" / "raw"
    traces = []
    for fname in ["household_owner_traces.jsonl", "household_renter_traces.jsonl"]:
        fpath = raw_dir / fname
        if not fpath.exists():
            safe_print(f"  WARNING: {fpath} not found")
            continue
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        traces.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return traces


def load_validation(seed, base_dir=None):
    """Load validation metrics for a given seed."""
    if base_dir is None:
        base_dir = HYBRID_DIR
    # Try multiple locations within the seed directory
    for subdir in ["validation", ""]:
        if subdir:
            vpath = base_dir / f"seed_{seed}" / subdir / "l2_macro_metrics.json"
        else:
            vpath = base_dir / f"seed_{seed}" / "l2_macro_metrics.json"
        if vpath.exists():
            with open(vpath, "r", encoding="utf-8") as f:
                return json.load(f)
    # Try inside gemma3_4b_strict
    vpath = base_dir / f"seed_{seed}" / "gemma3_4b_strict" / "l2_macro_metrics.json"
    if vpath.exists():
        with open(vpath, "r", encoding="utf-8") as f:
            return json.load(f)
    # Try global validation dir
    gpath = FLOOD_DIR / "paper3" / "results" / "validation" / "l2_macro_metrics.json"
    if gpath.exists():
        with open(gpath, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


# ============================================================
# ANALYSIS FUNCTIONS
# ============================================================

def _get_action(t):
    """Extract the final action from a trace record."""
    # Try approved_skill first (post-governance), then skill_proposal
    approved = t.get("approved_skill", {})
    if isinstance(approved, dict) and approved.get("skill_name"):
        return approved["skill_name"]
    sp = t.get("skill_proposal", {})
    if isinstance(sp, dict) and sp.get("skill_name"):
        return sp["skill_name"]
    return t.get("final_action", t.get("action", "unknown"))


def _get_reasoning(t):
    """Extract reasoning dict from a trace record."""
    sp = t.get("skill_proposal", {})
    if isinstance(sp, dict):
        return sp.get("reasoning", {})
    return t.get("reasoning", {})


def compute_decision_distribution(traces):
    """Compute per-year and overall action distributions."""
    year_actions = defaultdict(list)
    for t in traces:
        year = t.get("year", t.get("sim_year", 0))
        action = _get_action(t)
        if action and action != "unknown":
            year_actions[year].append(action)
    return year_actions


def compute_yearly_rates(traces, profiles):
    """Compute yearly insurance, elevation, do_nothing rates."""
    yearly = defaultdict(lambda: {"total": 0, "insurance": 0, "elevation": 0,
                                   "buyout": 0, "relocate": 0, "do_nothing": 0,
                                   "mg_adapt": 0, "mg_total": 0,
                                   "nmg_adapt": 0, "nmg_total": 0})
    for t in traces:
        year = t.get("year", t.get("sim_year", 0))
        action = _get_action(t)
        agent_id = t.get("agent_id", "")
        prof = profiles.get(agent_id, {})
        is_mg = prof.get("mg", False)

        yearly[year]["total"] += 1
        if "insurance" in action.lower():
            yearly[year]["insurance"] += 1
        if "elevat" in action.lower():
            yearly[year]["elevation"] += 1
        if "buyout" in action.lower():
            yearly[year]["buyout"] += 1
        if "relocat" in action.lower():
            yearly[year]["relocate"] += 1
        if action == "do_nothing":
            yearly[year]["do_nothing"] += 1

        # MG vs NMG adaptation
        is_adaptive = action != "do_nothing"
        if is_mg:
            yearly[year]["mg_total"] += 1
            if is_adaptive:
                yearly[year]["mg_adapt"] += 1
        else:
            yearly[year]["nmg_total"] += 1
            if is_adaptive:
                yearly[year]["nmg_adapt"] += 1

    return yearly


def compute_tp_by_year(traces):
    """Extract mean TP score per year."""
    year_tp = defaultdict(list)
    for t in traces:
        year = t.get("year", t.get("sim_year", 0))
        reasoning = _get_reasoning(t)
        tp = reasoning.get("TP_LABEL", reasoning.get("TP", ""))
        if tp in PMT_MAP:
            year_tp[year].append(PMT_MAP[tp])
    return {y: np.mean(vals) for y, vals in year_tp.items()}


def compute_entropy_by_year(traces):
    """Shannon entropy of decision distribution per year."""
    year_actions = compute_decision_distribution(traces)
    entropies = {}
    for year, actions in sorted(year_actions.items()):
        counts = Counter(actions)
        total = sum(counts.values())
        probs = [c / total for c in counts.values()]
        h = -sum(p * np.log2(p) for p in probs if p > 0)
        entropies[year] = h
    return entropies


def compute_rejection_rate(traces):
    """Compute governance rejection rate."""
    total = len(traces)
    rejected = sum(1 for t in traces if t.get("outcome") == "REJECTED")
    return rejected / total if total > 0 else 0


def compute_cp_by_year(traces):
    """Extract mean CP score per year."""
    year_cp = defaultdict(list)
    for t in traces:
        year = t.get("year", t.get("sim_year", 0))
        reasoning = _get_reasoning(t)
        cp = reasoning.get("CP_LABEL", reasoning.get("CP", ""))
        if cp in PMT_MAP:
            year_cp[year].append(PMT_MAP[cp])
    return {y: np.mean(vals) for y, vals in year_cp.items()}


def compute_tp_cp_gap_by_year(traces):
    """Compute mean (TP - CP) gap per year."""
    year_gaps = defaultdict(list)
    for t in traces:
        year = t.get("year", t.get("sim_year", 0))
        reasoning = _get_reasoning(t)
        tp = reasoning.get("TP_LABEL", reasoning.get("TP", ""))
        cp = reasoning.get("CP_LABEL", reasoning.get("CP", ""))
        if tp in PMT_MAP and cp in PMT_MAP:
            year_gaps[year].append(PMT_MAP[tp] - PMT_MAP[cp])
    return {y: np.mean(vals) for y, vals in year_gaps.items()}


def compute_adaptation_fatigue(traces):
    """Compute adaptation fatigue: do_nothing rate among agents who adapted before.

    Returns dict: year -> fatigue_rate (fraction of previously-adaptive agents
    choosing do_nothing this year).
    """
    # Track which agents have ever adapted (per year)
    agent_ever_adapted = set()
    year_agents = defaultdict(list)
    for t in traces:
        year = t.get("year", t.get("sim_year", 0))
        year_agents[year].append(t)

    fatigue_by_year = {}
    for year in sorted(year_agents.keys()):
        # Among agents who adapted in any previous year, how many do_nothing now?
        fatigue_candidates = 0
        fatigue_count = 0
        for t in year_agents[year]:
            agent_id = t.get("agent_id", "")
            action = _get_action(t)
            if agent_id in agent_ever_adapted:
                fatigue_candidates += 1
                if action == "do_nothing":
                    fatigue_count += 1
            # Update ever-adapted set
            if action != "do_nothing":
                agent_ever_adapted.add(agent_id)
        if fatigue_candidates > 0:
            fatigue_by_year[year] = fatigue_count / fatigue_candidates
    return fatigue_by_year


# ============================================================
# MAIN ANALYSIS
# ============================================================

safe_print("=" * 72)
safe_print("CROSS-SEED ROBUSTNESS ANALYSIS -- Paper 3 (hybrid_v2)")
safe_print("=" * 72)

profiles = load_profiles()
safe_print(f"Loaded {len(profiles)} agent profiles")

# Load all seeds (hybrid_v2 = full 3-tier)
all_traces = {}
all_validation = {}
for seed in SEEDS:
    safe_print(f"\nLoading seed_{seed} (hybrid_v2)...")
    all_traces[seed] = load_traces(seed)
    all_validation[seed] = load_validation(seed)
    safe_print(f"  Traces: {len(all_traces[seed])}")

# Load ablation B (flat baseline) traces
ablation_traces = {}
for seed in SEEDS:
    safe_print(f"\nLoading seed_{seed} (ablation_flat_baseline)...")
    ablation_traces[seed] = load_traces(seed, base_dir=ABLATION_DIR)
    safe_print(f"  Ablation traces: {len(ablation_traces[seed])}")

# ============================================================
# 1. VALIDATION METRICS COMPARISON
# ============================================================
safe_print("\n" + "=" * 72)
safe_print("[1] VALIDATION METRICS COMPARISON")
safe_print("=" * 72)

benchmark_names = []
benchmark_data = {}
for seed in SEEDS:
    v = all_validation[seed]
    if v:
        safe_print(f"\n  seed_{seed}: EPI={v['epi']:.4f} ({v['benchmarks_in_range']}/{v['total_benchmarks']} PASS)")
        for bname, bval in v["benchmark_results"].items():
            if bname not in benchmark_data:
                benchmark_data[bname] = []
                benchmark_names.append(bname)
            benchmark_data[bname].append(bval["value"])
            status = "PASS" if bval["in_range"] else "FAIL"
            safe_print(f"    {status} {bname}: {bval['value']:.3f} [{bval['range'][0]}-{bval['range'][1]}]")
    else:
        safe_print(f"\n  seed_{seed}: No validation data found")

safe_print("\n  Cross-seed summary (mean +/- SD):")
epi_values = [all_validation[s]["epi"] for s in SEEDS if all_validation[s]]
if epi_values:
    safe_print(f"    EPI: {np.mean(epi_values):.4f} +/- {np.std(epi_values):.4f}")
for bname in benchmark_names:
    vals = benchmark_data[bname]
    safe_print(f"    {bname}: {np.mean(vals):.3f} +/- {np.std(vals):.3f}")

# ============================================================
# 2. DECISION DISTRIBUTION STABILITY
# ============================================================
safe_print("\n" + "=" * 72)
safe_print("[2] DECISION DISTRIBUTION STABILITY")
safe_print("=" * 72)

seed_action_counts = {}
for seed in SEEDS:
    counts = Counter()
    for t in all_traces[seed]:
        action = _get_action(t)
        counts[action] += 1
    seed_action_counts[seed] = counts
    total = sum(counts.values())
    safe_print(f"\n  seed_{seed} (n={total}):")
    for action in sorted(counts.keys()):
        pct = counts[action] / total * 100
        safe_print(f"    {action}: {counts[action]} ({pct:.1f}%)")

# Cross-seed CoV for each action
safe_print("\n  Cross-seed coefficient of variation:")
all_actions = set()
for c in seed_action_counts.values():
    all_actions.update(c.keys())
for action in sorted(all_actions):
    vals = [seed_action_counts[s].get(action, 0) for s in SEEDS]
    mean_v = np.mean(vals)
    std_v = np.std(vals)
    cov = std_v / mean_v if mean_v > 0 else float("inf")
    safe_print(f"    {action}: mean={mean_v:.0f}, SD={std_v:.0f}, CoV={cov:.3f}")

# ============================================================
# 3. YEARLY RATE TRAJECTORIES
# ============================================================
safe_print("\n" + "=" * 72)
safe_print("[3] YEARLY RATE TRAJECTORIES")
safe_print("=" * 72)

seed_yearly = {}
for seed in SEEDS:
    seed_yearly[seed] = compute_yearly_rates(all_traces[seed], profiles)

years = sorted(set().union(*[seed_yearly[s].keys() for s in SEEDS]))

# ============================================================
# 4. RQ1: DECISION RATE CONSISTENCY (Traditional vs LLM-ABM context)
# ============================================================
safe_print("\n" + "=" * 72)
safe_print("[4] RQ1: DECISION RATE CONSISTENCY ACROSS SEEDS")
safe_print("    (Supports Traditional ABM vs LLM-ABM convergence/divergence)")
safe_print("=" * 72)

# Insurance, elevation, buyout, do_nothing yearly rates — cross-seed variability
for metric_name, metric_key in [("insurance", "insurance"), ("elevation", "elevation"),
                                 ("buyout", "buyout"), ("do_nothing", "do_nothing")]:
    seed_rates = {}
    for seed in SEEDS:
        ydata = seed_yearly[seed]
        yrs = sorted(ydata.keys())
        rates = [ydata[y][metric_key] / ydata[y]["total"] if ydata[y]["total"] > 0 else 0 for y in yrs]
        seed_rates[seed] = rates
    # Compute mean and SD across seeds per year
    rate_matrix = np.array([seed_rates[s] for s in SEEDS])
    mean_rate = np.mean(rate_matrix, axis=0)
    sd_rate = np.std(rate_matrix, axis=0)
    mean_cov = np.mean(sd_rate / (mean_rate + 1e-10))
    safe_print(f"  {metric_name}: mean CoV across years = {mean_cov:.3f}")

# ============================================================
# 5. RQ2: FULL vs ABLATION B (flat baseline) COMPARISON STABILITY
# ============================================================
safe_print("\n" + "=" * 72)
safe_print("[5] RQ2: FULL (hybrid_v2) vs ABLATION B (flat baseline)")
safe_print("=" * 72)

ablation_yearly = {}
for seed in SEEDS:
    ablation_yearly[seed] = compute_yearly_rates(ablation_traces[seed], profiles)

# Compare action distributions: Full vs Ablation per seed
for seed in SEEDS:
    full_counts = seed_action_counts[seed]
    abl_counts = Counter()
    for t in ablation_traces[seed]:
        action = _get_action(t)
        abl_counts[action] += 1
    full_total = sum(full_counts.values())
    abl_total = sum(abl_counts.values())
    safe_print(f"\n  seed_{seed}: Full(n={full_total}) vs Ablation(n={abl_total})")
    combined_actions = sorted(set(full_counts.keys()) | set(abl_counts.keys()))
    for action in combined_actions:
        f_pct = full_counts.get(action, 0) / full_total * 100 if full_total > 0 else 0
        a_pct = abl_counts.get(action, 0) / abl_total * 100 if abl_total > 0 else 0
        diff = f_pct - a_pct
        safe_print(f"    {action}: Full={f_pct:.1f}% Abl={a_pct:.1f}% (delta={diff:+.1f}%)")

# Cross-seed stability of Full-Ablation delta
safe_print("\n  Cross-seed stability of Full-Ablation delta:")
combined_all = sorted(set().union(*[set(seed_action_counts[s].keys()) for s in SEEDS],
                                    *[set(Counter(_get_action(t) for t in ablation_traces[s]).keys()) for s in SEEDS]))
for action in combined_all:
    deltas = []
    for seed in SEEDS:
        full_total = sum(seed_action_counts[seed].values())
        abl_counts = Counter(_get_action(t) for t in ablation_traces[seed])
        abl_total = sum(abl_counts.values())
        f_pct = seed_action_counts[seed].get(action, 0) / full_total * 100 if full_total > 0 else 0
        a_pct = abl_counts.get(action, 0) / abl_total * 100 if abl_total > 0 else 0
        deltas.append(f_pct - a_pct)
    safe_print(f"    {action}: mean delta={np.mean(deltas):+.1f}%, SD={np.std(deltas):.1f}%")

# ============================================================
# 6. RQ3: PMT DYNAMICS
# ============================================================
safe_print("\n" + "=" * 72)
safe_print("[6] RQ3: PMT DYNAMICS (TP accumulation, CP ceiling, TP-CP gap, adaptation fatigue)")
safe_print("=" * 72)

# 6a. TP trajectory
safe_print("\n  [6a] TP trajectory:")
seed_tp = {}
for seed in SEEDS:
    seed_tp[seed] = compute_tp_by_year(all_traces[seed])
    safe_print(f"  seed_{seed}: " + ", ".join(f"Y{y}={v:.2f}" for y, v in sorted(seed_tp[seed].items())))

# 6b. CP trajectory
safe_print("\n  [6b] CP trajectory:")
seed_cp = {}
for seed in SEEDS:
    seed_cp[seed] = compute_cp_by_year(all_traces[seed])
    safe_print(f"  seed_{seed}: " + ", ".join(f"Y{y}={v:.2f}" for y, v in sorted(seed_cp[seed].items())))

# 6c. TP-CP gap trajectory
safe_print("\n  [6c] TP-CP gap trajectory:")
seed_gap = {}
for seed in SEEDS:
    seed_gap[seed] = compute_tp_cp_gap_by_year(all_traces[seed])
    safe_print(f"  seed_{seed}: " + ", ".join(f"Y{y}={v:+.2f}" for y, v in sorted(seed_gap[seed].items())))

# 6d. Adaptation fatigue
safe_print("\n  [6d] Adaptation fatigue (do_nothing rate among previously-adaptive agents):")
seed_fatigue = {}
for seed in SEEDS:
    seed_fatigue[seed] = compute_adaptation_fatigue(all_traces[seed])
    vals = seed_fatigue[seed]
    if vals:
        safe_print(f"  seed_{seed}: " + ", ".join(f"Y{y}={v:.2f}" for y, v in sorted(vals.items())))
    else:
        safe_print(f"  seed_{seed}: no data")

# ============================================================
# 7. ENTROPY TRENDS & REJECTION RATES
# ============================================================
safe_print("\n" + "=" * 72)
safe_print("[7] ENTROPY TRENDS & REJECTION RATES")
safe_print("=" * 72)

seed_entropy = {}
for seed in SEEDS:
    seed_entropy[seed] = compute_entropy_by_year(all_traces[seed])
    vals = seed_entropy[seed]
    early = np.mean([vals.get(y, 0) for y in [1, 2, 3]])
    late = np.mean([vals.get(y, 0) for y in [11, 12, 13]])
    safe_print(f"  seed_{seed}: early(Y1-3)={early:.3f}, late(Y11-13)={late:.3f}, delta={late-early:+.3f}")

safe_print("\n  Governance rejection rates:")
for seed in SEEDS:
    rr = compute_rejection_rate(all_traces[seed])
    safe_print(f"  seed_{seed}: {rr:.1%}")

# ============================================================
# FIGURES
# ============================================================
safe_print("\n" + "=" * 72)
safe_print("[8] GENERATING FIGURES")
safe_print("=" * 72)

colors = {42: "#2196F3", 123: "#FF9800", 456: "#4CAF50"}
markers = {42: "o", 123: "s", 456: "^"}

# --- Figure 1: Multi-panel validation + trajectories ---
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle("Cross-Seed Robustness Analysis (3 seeds x 400 agents x 13yr)", fontsize=14, fontweight="bold")

# Panel A: EPI bar chart
ax = axes[0, 0]
epi_vals = [all_validation[s]["epi"] for s in SEEDS if all_validation[s]]
valid_seeds = [s for s in SEEDS if all_validation[s]]
if epi_vals:
    bars = ax.bar([f"Seed {s}" for s in valid_seeds], epi_vals,
                  color=[colors[s] for s in valid_seeds], alpha=0.8, edgecolor="black")
    ax.axhline(y=0.60, color="red", linestyle="--", linewidth=1.5, label="Threshold (0.60)")
    ax.axhline(y=np.mean(epi_vals), color="gray", linestyle=":", linewidth=1.5,
               label=f"Mean ({np.mean(epi_vals):.3f})")
    ax.set_ylabel("EPI Score")
    ax.set_title("(A) Empirical Plausibility Index")
    ax.legend(fontsize=9)
    ax.set_ylim(0, 1.0)
    for bar, val in zip(bars, epi_vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02, f"{val:.3f}",
                ha="center", va="bottom", fontweight="bold")
else:
    ax.set_title("(A) EPI — No validation data")

# Panel B: Insurance rate trajectories
ax = axes[0, 1]
for seed in SEEDS:
    ydata = seed_yearly[seed]
    yrs = sorted(ydata.keys())
    ins_rates = [ydata[y]["insurance"] / ydata[y]["total"] if ydata[y]["total"] > 0 else 0 for y in yrs]
    ax.plot(yrs, ins_rates, marker=markers[seed], color=colors[seed], label=f"Seed {seed}", linewidth=2, markersize=5)
ax.set_xlabel("Year")
ax.set_ylabel("Insurance Rate")
ax.set_title("(B) Insurance Uptake Trajectory")
ax.legend(fontsize=9)
ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))

# Panel C: TP trajectories
ax = axes[1, 0]
for seed in SEEDS:
    tp = seed_tp[seed]
    yrs = sorted(tp.keys())
    ax.plot(yrs, [tp[y] for y in yrs], marker=markers[seed], color=colors[seed],
            label=f"Seed {seed}", linewidth=2, markersize=5)
ax.set_xlabel("Year")
ax.set_ylabel("Mean TP Score")
ax.set_title("(C) Threat Perception Trajectory")
ax.legend(fontsize=9)

# Panel D: Entropy trajectories
ax = axes[1, 1]
for seed in SEEDS:
    ent = seed_entropy[seed]
    yrs = sorted(ent.keys())
    ax.plot(yrs, [ent[y] for y in yrs], marker=markers[seed], color=colors[seed],
            label=f"Seed {seed}", linewidth=2, markersize=5)
ax.set_xlabel("Year")
ax.set_ylabel("Shannon Entropy (bits)")
ax.set_title("(D) Decision Diversity Trajectory")
ax.legend(fontsize=9)

plt.tight_layout(rect=[0, 0, 1, 0.95])
fig_path = OUT_DIR / "cross_seed_robustness_multipanel.png"
plt.savefig(fig_path, dpi=200, bbox_inches="tight")
plt.close()
safe_print(f"  Saved: {fig_path}")

# --- Figure 2: Benchmark comparison heatmap ---
if benchmark_names and all_validation[SEEDS[0]]:
    fig, ax = plt.subplots(figsize=(12, 5))
    data_matrix = []
    row_labels = []
    for bname in benchmark_names:
        vals = benchmark_data[bname]
        data_matrix.append(vals)
        row_labels.append(bname)

    data_matrix = np.array(data_matrix)
    im = ax.imshow(data_matrix, aspect="auto", cmap="RdYlGn_r", vmin=0, vmax=1)

    ax.set_xticks(range(len(SEEDS)))
    ax.set_xticklabels([f"Seed {s}" for s in SEEDS])
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels(row_labels)

    # Add text annotations
    for i in range(len(row_labels)):
        v_obj = all_validation[SEEDS[0]]["benchmark_results"][row_labels[i]]
        lo, hi = v_obj["range"]
        for j in range(len(SEEDS)):
            val = data_matrix[i, j]
            in_range = lo <= val <= hi
            color = "green" if in_range else "red"
            ax.text(j, i, f"{val:.3f}", ha="center", va="center", fontsize=10,
                    fontweight="bold", color=color)

    # Add range annotations on the right
    for i, bname in enumerate(row_labels):
        v_obj = all_validation[SEEDS[0]]["benchmark_results"][bname]
        lo, hi = v_obj["range"]
        ax.text(len(SEEDS) + 0.2, i, f"[{lo}-{hi}]", ha="left", va="center", fontsize=9, color="gray")

    ax.set_title("L2 Benchmark Values Across Seeds (green=PASS, red=FAIL)", fontsize=13, fontweight="bold")
    plt.colorbar(im, ax=ax, label="Value", shrink=0.8)
    plt.tight_layout()
    fig_path = OUT_DIR / "cross_seed_benchmark_heatmap.png"
    plt.savefig(fig_path, dpi=200, bbox_inches="tight")
    plt.close()
    safe_print(f"  Saved: {fig_path}")

# --- Figure 3: Action distribution comparison ---
fig, ax = plt.subplots(figsize=(12, 6))
all_actions_sorted = sorted(all_actions)
x = np.arange(len(all_actions_sorted))
width = 0.25

for i, seed in enumerate(SEEDS):
    counts = seed_action_counts[seed]
    total = sum(counts.values())
    pcts = [counts.get(a, 0) / total * 100 for a in all_actions_sorted]
    ax.bar(x + i * width, pcts, width, label=f"Seed {seed}", color=colors[seed], alpha=0.8, edgecolor="black")

ax.set_xlabel("Action")
ax.set_ylabel("Percentage (%)")
ax.set_title("Decision Distribution Across Seeds (hybrid_v2)", fontsize=13, fontweight="bold")
ax.set_xticks(x + width)
ax.set_xticklabels(all_actions_sorted, rotation=30, ha="right")
ax.legend()
plt.tight_layout()
fig_path = OUT_DIR / "cross_seed_action_distribution.png"
plt.savefig(fig_path, dpi=200, bbox_inches="tight")
plt.close()
safe_print(f"  Saved: {fig_path}")

# --- Figure 4: RQ2 Full vs Ablation action distribution ---
fig, axes_rq2 = plt.subplots(1, len(SEEDS), figsize=(5 * len(SEEDS), 5), sharey=True)
if len(SEEDS) == 1:
    axes_rq2 = [axes_rq2]
for idx, seed in enumerate(SEEDS):
    ax = axes_rq2[idx]
    full_counts = seed_action_counts[seed]
    abl_counts = Counter(_get_action(t) for t in ablation_traces[seed])
    combined_actions_sorted = sorted(set(full_counts.keys()) | set(abl_counts.keys()))
    x2 = np.arange(len(combined_actions_sorted))
    w2 = 0.35
    full_total = sum(full_counts.values())
    abl_total = sum(abl_counts.values())
    f_pcts = [full_counts.get(a, 0) / full_total * 100 if full_total > 0 else 0 for a in combined_actions_sorted]
    a_pcts = [abl_counts.get(a, 0) / abl_total * 100 if abl_total > 0 else 0 for a in combined_actions_sorted]
    ax.bar(x2 - w2/2, f_pcts, w2, label="Full (3-tier)", color="#2196F3", alpha=0.8, edgecolor="black")
    ax.bar(x2 + w2/2, a_pcts, w2, label="Ablation B (flat)", color="#FF5722", alpha=0.8, edgecolor="black")
    ax.set_xlabel("Action")
    ax.set_title(f"Seed {seed}")
    ax.set_xticks(x2)
    ax.set_xticklabels(combined_actions_sorted, rotation=40, ha="right", fontsize=8)
    if idx == 0:
        ax.set_ylabel("Percentage (%)")
    ax.legend(fontsize=8)

fig.suptitle("RQ2: Full (hybrid_v2) vs Ablation B (flat baseline)", fontsize=13, fontweight="bold")
plt.tight_layout(rect=[0, 0, 1, 0.93])
fig_path = OUT_DIR / "cross_seed_rq2_full_vs_ablation.png"
plt.savefig(fig_path, dpi=200, bbox_inches="tight")
plt.close()
safe_print(f"  Saved: {fig_path}")

# --- Figure 5: RQ3 PMT dynamics (TP, CP, gap, fatigue) ---
fig, axes_pmt = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle("RQ3: PMT Dynamics Across Seeds", fontsize=14, fontweight="bold")

# Panel A: TP accumulation
ax = axes_pmt[0, 0]
for seed in SEEDS:
    tp = seed_tp[seed]
    yrs = sorted(tp.keys())
    ax.plot(yrs, [tp[y] for y in yrs], marker=markers[seed], color=colors[seed],
            label=f"Seed {seed}", linewidth=2, markersize=5)
ax.set_xlabel("Year")
ax.set_ylabel("Mean TP Score (0=VL, 4=VH)")
ax.set_title("(A) Threat Perception Accumulation")
ax.legend(fontsize=9)

# Panel B: CP ceiling
ax = axes_pmt[0, 1]
for seed in SEEDS:
    cp = seed_cp[seed]
    yrs = sorted(cp.keys())
    ax.plot(yrs, [cp[y] for y in yrs], marker=markers[seed], color=colors[seed],
            label=f"Seed {seed}", linewidth=2, markersize=5)
ax.set_xlabel("Year")
ax.set_ylabel("Mean CP Score (0=VL, 4=VH)")
ax.set_title("(B) Coping Perception Ceiling")
ax.legend(fontsize=9)

# Panel C: TP-CP gap
ax = axes_pmt[1, 0]
for seed in SEEDS:
    gap = seed_gap[seed]
    yrs = sorted(gap.keys())
    ax.plot(yrs, [gap[y] for y in yrs], marker=markers[seed], color=colors[seed],
            label=f"Seed {seed}", linewidth=2, markersize=5)
ax.axhline(y=0, color="gray", linestyle="--", alpha=0.5)
ax.set_xlabel("Year")
ax.set_ylabel("Mean TP - CP")
ax.set_title("(C) TP-CP Gap (+ = threat > coping)")
ax.legend(fontsize=9)

# Panel D: Adaptation fatigue
ax = axes_pmt[1, 1]
for seed in SEEDS:
    fat = seed_fatigue[seed]
    if fat:
        yrs = sorted(fat.keys())
        ax.plot(yrs, [fat[y] for y in yrs], marker=markers[seed], color=colors[seed],
                label=f"Seed {seed}", linewidth=2, markersize=5)
ax.set_xlabel("Year")
ax.set_ylabel("Fatigue Rate")
ax.set_title("(D) Adaptation Fatigue (do_nothing | prev adapted)")
ax.legend(fontsize=9)
ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))

plt.tight_layout(rect=[0, 0, 1, 0.95])
fig_path = OUT_DIR / "cross_seed_rq3_pmt_dynamics.png"
plt.savefig(fig_path, dpi=200, bbox_inches="tight")
plt.close()
safe_print(f"  Saved: {fig_path}")

# --- Figure 6: MG adaptation gap trajectory ---
fig, ax = plt.subplots(figsize=(10, 5))
for seed in SEEDS:
    ydata = seed_yearly[seed]
    yrs = sorted(ydata.keys())
    gaps = []
    for y in yrs:
        mg_rate = ydata[y]["mg_adapt"] / ydata[y]["mg_total"] if ydata[y]["mg_total"] > 0 else 0
        nmg_rate = ydata[y]["nmg_adapt"] / ydata[y]["nmg_total"] if ydata[y]["nmg_total"] > 0 else 0
        gaps.append(nmg_rate - mg_rate)  # positive = NMG adapts more
    ax.plot(yrs, gaps, marker=markers[seed], color=colors[seed], label=f"Seed {seed}", linewidth=2, markersize=5)

ax.axhline(y=0, color="gray", linestyle="--", alpha=0.5)
ax.fill_between(range(1, 14), [0.05]*13, [0.30]*13, alpha=0.1, color="green", label="Target range")
ax.set_xlabel("Year")
ax.set_ylabel("MG Adaptation Gap (NMG - MG rate)")
ax.set_title("MG Adaptation Gap Trajectory Across Seeds", fontsize=13, fontweight="bold")
ax.legend(fontsize=9)
plt.tight_layout()
fig_path = OUT_DIR / "cross_seed_mg_gap_trajectory.png"
plt.savefig(fig_path, dpi=200, bbox_inches="tight")
plt.close()
safe_print(f"  Saved: {fig_path}")

# ============================================================
# SUMMARY STATISTICS TABLE
# ============================================================
safe_print("\n" + "=" * 72)
safe_print("[9] SUMMARY TABLE")
safe_print("=" * 72)

summary_rows = []
# EPI
epi_vals = [all_validation[s]["epi"] for s in SEEDS if all_validation[s]]
if epi_vals:
    summary_rows.append(("EPI", np.mean(epi_vals), np.std(epi_vals), ">=0.60"))

# Benchmarks
for bname in benchmark_names:
    vals = benchmark_data[bname]
    v_obj = all_validation[SEEDS[0]]["benchmark_results"][bname]
    rng = f"{v_obj['range'][0]}-{v_obj['range'][1]}"
    summary_rows.append((bname, np.mean(vals), np.std(vals), rng))

# Rejection rate
rr_vals = [compute_rejection_rate(all_traces[s]) for s in SEEDS]
summary_rows.append(("rejection_rate", np.mean(rr_vals), np.std(rr_vals), "--"))

# Entropy early/late
for period, yr_range in [("entropy_early", [1,2,3]), ("entropy_late", [11,12,13])]:
    vals = []
    for seed in SEEDS:
        ent = seed_entropy[seed]
        vals.append(np.mean([ent.get(y, 0) for y in yr_range]))
    summary_rows.append((period, np.mean(vals), np.std(vals), "--"))

# TP early/late
for period, yr_range in [("tp_early", [1,2,3]), ("tp_late", [11,12,13])]:
    vals = []
    for seed in SEEDS:
        tp = seed_tp[seed]
        vals.append(np.mean([tp.get(y, 0) for y in yr_range]))
    summary_rows.append((period, np.mean(vals), np.std(vals), "--"))

# CP early/late
for period, yr_range in [("cp_early", [1,2,3]), ("cp_late", [11,12,13])]:
    vals = []
    for seed in SEEDS:
        cp = seed_cp[seed]
        vals.append(np.mean([cp.get(y, 0) for y in yr_range]))
    summary_rows.append((period, np.mean(vals), np.std(vals), "--"))

safe_print(f"\n  {'Metric':<25s} {'Mean':>8s} {'+/- SD':>8s} {'Target':>12s}")
safe_print("  " + "-" * 55)
for name, mean, sd, target in summary_rows:
    safe_print(f"  {name:<25s} {mean:>8.4f} {sd:>8.4f} {target:>12s}")

# Save summary as JSON
summary_json = {
    "experiment": "paper3_hybrid_v2",
    "ablation": "paper3_ablation_flat_baseline",
    "seeds": SEEDS,
    "n_agents": 400,
    "n_years": 13,
    "total_decisions_per_seed": 5200,
    "metrics": {name: {"mean": float(mean), "sd": float(sd), "target": target}
                for name, mean, sd, target in summary_rows},
    "per_seed_epi": {str(s): all_validation[s]["epi"] for s in SEEDS if all_validation[s]},
}
summary_path = OUT_DIR / "cross_seed_summary.json"
with open(summary_path, "w", encoding="utf-8") as f:
    json.dump(summary_json, f, indent=2)
safe_print(f"\n  Saved: {summary_path}")

safe_print("\n" + "=" * 72)
safe_print("CROSS-SEED ROBUSTNESS ANALYSIS COMPLETE")
safe_print(f"All outputs: {OUT_DIR}")
safe_print("=" * 72)
