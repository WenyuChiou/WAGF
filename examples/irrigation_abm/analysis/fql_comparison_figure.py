#!/usr/bin/env python3
"""
Generate 3-condition comparison figure for Nature Water paper.
LLM Governed vs LLM Ungoverned vs FQL Baseline.

EHE is shown ONLY for LLM conditions (Panel A, 2 bars).
FQL comparison uses water-system metrics only (Panels B-F).
FQL (Hung & Yang 2021) has a binary action space (increase/decrease);
computing EHE for it is not meaningful.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd
from pathlib import Path
from collections import Counter
import math

# ── Paths ──
MAIN_RESULTS = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\irrigation_abm\results")
FQL_RESULTS = Path(r"C:\Users\wenyu\Desktop\Lehigh\wagf-fql-baseline\examples\irrigation_abm\results\fql_raw")
OUT_DIR = Path(r"C:\Users\wenyu\Desktop\Lehigh\wagf-fql-baseline\examples\irrigation_abm\analysis\figures")
OUT_DIR.mkdir(parents=True, exist_ok=True)

seeds = [42, 43, 44]
DIRECTIONS = ["increase", "maintain", "decrease"]
H_MAX_DIR = math.log2(3)

def to_direction(s):
    s = s.lower().strip()
    if s.startswith("increase"): return "increase"
    elif s.startswith("decrease"): return "decrease"
    else: return "maintain"

def shannon_entropy(counts):
    total = sum(counts.values())
    if total == 0: return 0.0
    probs = np.array([v / total for v in counts.values()])
    probs = probs[probs > 0]
    return float(-np.sum(probs * np.log2(probs)))

# ── Load data ──
gov, ungov, fql = {}, {}, {}
for s in seeds:
    gov[s] = pd.read_csv(MAIN_RESULTS / f"production_v20_42yr_seed{s}" / "simulation_log.csv", encoding="utf-8")
    ungov[s] = pd.read_csv(MAIN_RESULTS / f"ungoverned_v20_42yr_seed{s}" / "simulation_log.csv", encoding="utf-8")
    fql[s] = pd.read_csv(FQL_RESULTS / f"seed{s}" / "simulation_log.csv", encoding="utf-8")

# ── Compute metrics per seed ──
def compute_metrics(sim_dict):
    results = {"ehe": [], "demand_ratio": [], "demand_mead_r": [],
               "shortage": [], "wsa_coherence": [], "mead_traj": [],
               "dir_dist": {"increase": [], "maintain": [], "decrease": []}}
    for s in seeds:
        df = sim_dict[s]
        # EHE (3-dir)
        dirs = df["yearly_decision"].str.lower().str.strip().map(to_direction)
        counts = Counter(dirs)
        results["ehe"].append(shannon_entropy(counts) / H_MAX_DIR)
        # Direction distribution
        total = len(df)
        for d in DIRECTIONS:
            results["dir_dist"][d].append((dirs == d).sum() / total * 100)
        # Demand ratio
        yearly = df.groupby("year").agg({"request": "sum", "water_right": "sum"})
        ratio = yearly["request"] / yearly["water_right"]
        results["demand_ratio"].append(ratio.mean())
        # Demand-Mead r
        yearly2 = df.groupby("year").agg({"request": "sum", "water_right": "sum", "lake_mead_level": "first"})
        r2 = yearly2["request"] / yearly2["water_right"]
        corr = np.corrcoef(yearly2["lake_mead_level"].values, r2.values)[0, 1]
        results["demand_mead_r"].append(corr)
        # Shortage years
        yearly3 = df.groupby("year").agg({"shortage_tier": "first"})
        results["shortage"].append(float((yearly3["shortage_tier"] > 0).sum()))
        # WSA coherence
        wsa = df["wsa_label"].fillna("").str.strip()
        skill = df["yearly_decision"].str.lower().str.strip()
        h_mask = wsa.isin(["H", "VH"])
        h_total = h_mask.sum()
        h_inc = (h_mask & skill.str.startswith("increase")).sum()
        results["wsa_coherence"].append((h_total - h_inc) / h_total if h_total > 0 else 1.0)
        # Mead trajectory
        mead_yearly = df.groupby("year")["lake_mead_level"].first()
        results["mead_traj"].append(mead_yearly)
    return results

m_gov = compute_metrics(gov)
m_ungov = compute_metrics(ungov)
m_fql = compute_metrics(fql)

# ── Colors ──
C_GOV = "#2166AC"      # blue
C_UNGOV = "#B2182B"    # red
C_FQL = "#4DAF4A"      # green
colors_3 = [C_GOV, C_UNGOV, C_FQL]
colors_2 = [C_GOV, C_UNGOV]
labels_3 = ["LLM Governed", "LLM Ungoverned", "FQL Baseline"]
labels_2 = ["LLM Governed", "LLM Ungoverned"]

# ══════════════════════════════════════════════════════════════════════════
# FIGURE
# ══════════════════════════════════════════════════════════════════════════
fig = plt.figure(figsize=(16, 12))
gs = gridspec.GridSpec(2, 3, hspace=0.35, wspace=0.35)

# ── Panel A: EHE — LLM only (2 bars) ──
ax_a = fig.add_subplot(gs[0, 0])
ehe_means = [np.mean(m_gov["ehe"]), np.mean(m_ungov["ehe"])]
ehe_stds = [np.std(m_gov["ehe"], ddof=1), np.std(m_ungov["ehe"], ddof=1)]
bars_a = ax_a.bar(range(2), ehe_means, yerr=ehe_stds, color=colors_2,
                  capsize=5, edgecolor='white', linewidth=0.5, width=0.6)
for bar, val in zip(bars_a, ehe_means):
    ax_a.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
              f"{val:.3f}", ha='center', va='bottom', fontweight='bold', fontsize=10)
ax_a.set_xticks(range(2))
ax_a.set_xticklabels(["LLM\nGoverned", "LLM\nUngoverned"], fontsize=9)
ax_a.set_ylabel("EHE (3-direction)")
ax_a.set_title("(a) Behavioral Diversity (LLM only)", fontweight='bold', fontsize=11)
ax_a.set_ylim(0, 1.05)
ax_a.annotate("FQL excluded:\nbinary action space\n(increase/decrease only)",
              xy=(0.98, 0.98), xycoords='axes fraction', ha='right', va='top',
              fontsize=7, fontstyle='italic', color='gray',
              bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow', alpha=0.8))

# ── Panel B: Water-system metrics (3 conditions) ──
ax_b = fig.add_subplot(gs[0, 1])
metrics_names = ["Demand\nRatio", "Demand-\nMead r", "WSA\nCoherence"]
metric_keys = ["demand_ratio", "demand_mead_r", "wsa_coherence"]
x = np.arange(len(metrics_names))
width = 0.25

for i, (m, c, lbl) in enumerate(zip([m_gov, m_ungov, m_fql], colors_3, labels_3)):
    means = [np.mean(m[k]) for k in metric_keys]
    stds = [np.std(m[k], ddof=1) for k in metric_keys]
    ax_b.bar(x + i * width, means, width, yerr=stds, color=c, label=lbl,
             capsize=3, edgecolor='white', linewidth=0.5)

ax_b.set_xticks(x + width)
ax_b.set_xticklabels(metrics_names, fontsize=9)
ax_b.set_ylabel("Value")
ax_b.set_title("(b) Water-System Metrics", fontweight='bold', fontsize=11)
ax_b.legend(fontsize=7, loc='upper right')
ax_b.set_ylim(0, 1.05)
ax_b.axhline(y=0, color='gray', linewidth=0.5)

# ── Panel C: Lake Mead trajectories ──
ax_c = fig.add_subplot(gs[0, 2])
years = np.arange(1, 43)
for m, c, lbl in zip([m_gov, m_ungov, m_fql], colors_3, labels_3):
    all_traj = np.array([t.values for t in m["mead_traj"]])
    mean_traj = all_traj.mean(axis=0)
    std_traj = all_traj.std(axis=0, ddof=1)
    ax_c.plot(years, mean_traj, color=c, label=lbl, linewidth=2)
    ax_c.fill_between(years, mean_traj - std_traj, mean_traj + std_traj, color=c, alpha=0.15)

ax_c.axhline(y=1050, color='red', linestyle='--', linewidth=1, alpha=0.6, label='Shortage threshold')
ax_c.axhline(y=1025, color='darkred', linestyle=':', linewidth=1, alpha=0.6, label='Dead pool risk')
ax_c.set_xlabel("Simulation Year")
ax_c.set_ylabel("Lake Mead Level (ft)")
ax_c.set_title("(c) Lake Mead Trajectories", fontweight='bold', fontsize=11)
ax_c.legend(fontsize=7, loc='lower left')
ax_c.set_xlim(1, 42)

# ── Panel D: Demand ratio trajectories ──
ax_d = fig.add_subplot(gs[1, 0])
for sim_dict, c, lbl_name in zip([gov, ungov, fql], colors_3, labels_3):
    all_ratio = []
    for s in seeds:
        df = sim_dict[s]
        yearly = df.groupby("year").agg({"request": "sum", "water_right": "sum"})
        ratio = yearly["request"] / yearly["water_right"]
        all_ratio.append(ratio.values)
    all_ratio = np.array(all_ratio)
    mean_r = all_ratio.mean(axis=0)
    std_r = all_ratio.std(axis=0, ddof=1)
    ax_d.plot(years, mean_r, color=c, label=lbl_name, linewidth=2)
    ax_d.fill_between(years, mean_r - std_r, mean_r + std_r, color=c, alpha=0.15)

ax_d.set_xlabel("Simulation Year")
ax_d.set_ylabel("Demand Ratio (request / water_right)")
ax_d.set_title("(d) Demand Ratio Over Time", fontweight='bold', fontsize=11)
ax_d.legend(fontsize=7, loc='upper right')
ax_d.set_xlim(1, 42)

# ── Panel E: Shortage years comparison ──
ax_e = fig.add_subplot(gs[1, 1])
shortage_means = [np.mean(m["shortage"]) for m in [m_gov, m_ungov, m_fql]]
shortage_stds = [np.std(m["shortage"], ddof=1) for m in [m_gov, m_ungov, m_fql]]
bars = ax_e.bar(range(3), shortage_means, yerr=shortage_stds, color=colors_3,
                capsize=5, edgecolor='white', linewidth=0.5)
for bar, val in zip(bars, shortage_means):
    ax_e.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
              f"{val:.1f}", ha='center', va='bottom', fontweight='bold', fontsize=11)
ax_e.set_xticks(range(3))
ax_e.set_xticklabels(["LLM\nGoverned", "LLM\nUngoverned", "FQL\nBaseline"], fontsize=9)
ax_e.set_ylabel("Shortage Years (out of 42)")
ax_e.set_title("(e) Shortage Years", fontweight='bold', fontsize=11)

# ── Panel F: Summary table ──
ax_f = fig.add_subplot(gs[1, 2])
ax_f.axis('off')
table_data = [
    ["EHE (3-dir)", f"{np.mean(m_gov['ehe']):.3f}", f"{np.mean(m_ungov['ehe']):.3f}", "N/A*"],
    ["Demand ratio", f"{np.mean(m_gov['demand_ratio']):.3f}", f"{np.mean(m_ungov['demand_ratio']):.3f}", f"{np.mean(m_fql['demand_ratio']):.3f}"],
    ["Demand-Mead r", f"{np.mean(m_gov['demand_mead_r']):.3f}", f"{np.mean(m_ungov['demand_mead_r']):.3f}", f"{np.mean(m_fql['demand_mead_r']):.3f}"],
    ["Shortage yrs", f"{np.mean(m_gov['shortage']):.1f}", f"{np.mean(m_ungov['shortage']):.1f}", f"{np.mean(m_fql['shortage']):.1f}"],
    ["WSA coherence", f"{np.mean(m_gov['wsa_coherence']):.3f}", f"{np.mean(m_ungov['wsa_coherence']):.3f}", f"{np.mean(m_fql['wsa_coherence']):.3f}"],
    ["Action space", "5 skills", "5 skills", "2 actions"],
    ["Reasoning", "Yes", "Yes", "No"],
]
col_labels = ["Metric", "LLM Gov", "LLM Ungov", "FQL"]
table = ax_f.table(cellText=table_data, colLabels=col_labels, loc='center',
                   cellLoc='center', colWidths=[0.3, 0.22, 0.22, 0.22])
table.auto_set_font_size(False)
table.set_fontsize(9)
table.scale(1, 1.4)

# Color header
for j in range(4):
    table[0, j].set_facecolor('#E0E0E0')
    table[0, j].set_text_props(fontweight='bold')
# Color columns
for i in range(1, len(table_data) + 1):
    table[i, 1].set_facecolor('#D4E6F1')
    table[i, 2].set_facecolor('#F5CBA7')
    table[i, 3].set_facecolor('#D5F5E3')

# Footnote for FQL EHE
ax_f.text(0.5, -0.02, "*FQL has binary action space (increase/decrease); EHE not applicable.",
          ha='center', va='top', fontsize=7, fontstyle='italic', color='gray',
          transform=ax_f.transAxes)

ax_f.set_title("(f) Summary", fontweight='bold', fontsize=11)

# ── Save ──
fig.suptitle("Three-Condition Comparison: LLM Governed vs Ungoverned vs FQL Baseline\n"
             "78 CRSS agents × 42 years × 3 seeds | Irrigation ABM",
             fontsize=13, fontweight='bold', y=0.98)

out_path = OUT_DIR / "fql_3condition_comparison.png"
fig.savefig(out_path, dpi=200, bbox_inches='tight', facecolor='white')
print(f"Saved: {out_path}")
plt.close()
