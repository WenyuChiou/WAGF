"""
Generate 4-panel (2x2) stacked bar chart showing cumulative behavioral
state distribution over 13 simulation years for MG/NMG x Owner/Renter.

Data: paper3_hybrid_v2 seed_42 gemma3_4b_strict traces.
"""

import json
import os
from collections import defaultdict
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# ── paths ──────────────────────────────────────────────────────────────
BASE = r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework"
RAW = os.path.join(
    BASE,
    "examples", "multi_agent", "flood", "paper3", "results",
    "paper3_hybrid_v2", "seed_42", "gemma3_4b_strict", "raw",
)
OUT_DIR = os.path.join(
    BASE, "examples", "multi_agent", "flood", "paper3", "analysis", "working"
)
os.makedirs(OUT_DIR, exist_ok=True)

OWNER_FILE = os.path.join(RAW, "household_owner_traces.jsonl")
RENTER_FILE = os.path.join(RAW, "household_renter_traces.jsonl")

# ── classification helpers ─────────────────────────────────────────────

def classify_owner(state_after):
    relocated = state_after.get("relocated", False)
    elevated = state_after.get("elevated", False)
    insured = state_after.get("has_insurance", False)
    if relocated:
        return "BT"
    if elevated and insured:
        return "FI+HE"
    if elevated:
        return "HE"
    if insured:
        return "FI"
    return "DN"


def classify_renter(state_after):
    relocated = state_after.get("relocated", False)
    insured = state_after.get("has_insurance", False)
    if relocated:
        return "RL"
    if insured:
        return "CI"
    return "DN"


# ── read traces ────────────────────────────────────────────────────────

# counts[cell][year][state] = count
# cell = (mg_bool, agent_type)  e.g. (True, "owner")
counts = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
severe_years = set()

def process_file(path, agent_kind):
    classify = classify_owner if agent_kind == "owner" else classify_renter
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            year = rec["year"]
            sa = rec["state_after"]
            sb = rec.get("state_before", sa)
            mg = sb.get("mg", False)
            state_label = classify(sa)
            cell = (mg, agent_kind)
            counts[cell][year][state_label] += 1
            # flood severity
            env = rec.get("environment_context", {})
            if env.get("flood_severity") == "SEVERE":
                severe_years.add(year)

process_file(OWNER_FILE, "owner")
process_file(RENTER_FILE, "renter")

years = list(range(1, 14))

# ── define state ordering & colours per agent type ─────────────────────
OWNER_STATES = ["DN", "FI", "HE", "FI+HE", "BT"]
RENTER_STATES = ["DN", "CI", "RL"]

COLORS = {
    "DN":    "steelblue",
    "FI":    "darkorange",
    "HE":    "seagreen",
    "FI+HE": "indianred",
    "BT":    "orchid",
    "CI":    "darkorange",
    "RL":    "orchid",
}

PANELS = [
    ((True,  "owner"),  "MG-Owner",  OWNER_STATES),
    ((False, "owner"),  "NMG-Owner", OWNER_STATES),
    ((True,  "renter"), "MG-Renter", RENTER_STATES),
    ((False, "renter"), "NMG-Renter", RENTER_STATES),
]

# ── plot ───────────────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(16, 10), sharey=True)
axes_flat = axes.flatten()

for idx, (cell_key, title, states) in enumerate(PANELS):
    ax = axes_flat[idx]
    data = counts[cell_key]

    # Build arrays: rows=states, cols=years (raw counts → percentages)
    raw = np.zeros((len(states), len(years)))
    for j, y in enumerate(years):
        for i, s in enumerate(states):
            raw[i, j] = data[y].get(s, 0)

    totals = raw.sum(axis=0)
    totals[totals == 0] = 1  # avoid /0
    pct = raw / totals * 100

    x = np.arange(len(years))
    width = 0.7
    bottom = np.zeros(len(years))

    for i, s in enumerate(states):
        ax.bar(x, pct[i], width, bottom=bottom, label=s,
               color=COLORS[s], edgecolor="white", linewidth=0.3)
        bottom += pct[i]

    # Severe flood markers
    for j, y in enumerate(years):
        if y in severe_years:
            ax.text(x[j], 103, "F", ha="center", va="bottom",
                    fontsize=9, fontweight="bold", color="red")

    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([str(y) for y in years], fontsize=9)
    ax.set_ylim(0, 110)
    ax.set_xlim(-0.5, len(years) - 0.5)

    if idx >= 2:
        ax.set_xlabel("Simulation year", fontsize=12)
    if idx % 2 == 0:
        ax.set_ylabel("Population share (%)", fontsize=12)

    # Legend in first panel only
    if idx == 0:
        ax.legend(loc="upper left", fontsize=9, framealpha=0.9)

    # Agent count annotation
    n_agents = int(totals[0])
    ax.text(0.97, 0.97, f"n={n_agents}", transform=ax.transAxes,
            ha="right", va="top", fontsize=10,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.8))

fig.suptitle(
    "Cumulative Behavioral State Distribution by Household Type (Seed 42)",
    fontsize=15, fontweight="bold", y=0.98,
)
plt.tight_layout(rect=[0, 0, 1, 0.95])

# ── save ───────────────────────────────────────────────────────────────
png_path = os.path.join(OUT_DIR, "fig_4cell_behavior_distribution.png")
pdf_path = os.path.join(OUT_DIR, "fig_4cell_behavior_distribution.pdf")
fig.savefig(png_path, dpi=300, bbox_inches="tight")
fig.savefig(pdf_path, bbox_inches="tight")
plt.close(fig)

print(f"Saved PNG: {png_path}")
print(f"Saved PDF: {pdf_path}")

# ── summary stats ──────────────────────────────────────────────────────
for cell_key, title, states in PANELS:
    data = counts[cell_key]
    total = sum(data[13].values()) if 13 in data else 0
    print(f"\n{title} (Year 13, n={total}):")
    for s in states:
        c = data[13].get(s, 0)
        pct_val = c / total * 100 if total else 0
        print(f"  {s}: {c} ({pct_val:.1f}%)")
