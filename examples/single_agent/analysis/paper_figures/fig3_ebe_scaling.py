"""
Figure 3 -- Cross-Model EBE (Effective Behavioral Entropy) Scaling
WRR Technical Note: SAGE Framework

Computes EBE = H_norm * (1 - R_H) for each (model, group) combination:
  H_norm : normalized Shannon entropy over 5 canonical decision categories
  R_H    : hallucination rate (physically impossible / redundant actions)

Models : Gemma3 4B, Gemma3 12B, Gemma3 27B
Groups : A (unstructured), B (structured), C (structured + governance)
Note   : 27B / Group C data does not exist and is skipped.
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE = os.path.join(
    "c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework",
    "examples", "single_agent", "results", "JOH_FINAL",
)
OUT_DIR = os.path.join(
    "c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework",
    "examples", "single_agent", "analysis", "paper_figures",
)

MODELS = ["gemma3_4b", "gemma3_12b", "gemma3_27b"]
MODEL_LABELS = ["Gemma3 4B", "Gemma3 12B", "Gemma3 27B"]
GROUPS = ["Group_A", "Group_B", "Group_C"]
GROUP_LABELS = ["Group A", "Group B", "Group C"]

# 5 canonical categories for entropy
CANONICAL = ["Elevation", "Insurance", "Both", "DoNothing", "Relocate"]
N_CATS = len(CANONICAL)


# ---------------------------------------------------------------------------
# Decision normalisation helpers
# ---------------------------------------------------------------------------
def normalize_decision_group_a(raw: str) -> str:
    """Map Group-A raw_llm_decision text to canonical category."""
    if pd.isna(raw):
        return None
    raw_lower = raw.strip().lower()
    if "elevat" in raw_lower and "insur" in raw_lower:
        return "Both"
    if "elevat" in raw_lower:
        return "Elevation"
    if "insur" in raw_lower:
        return "Insurance"
    if "relocat" in raw_lower:
        return "Relocate"
    if "nothing" in raw_lower or "do_nothing" in raw_lower:
        return "DoNothing"
    return "DoNothing"  # fallback


def normalize_decision_group_bc(dec: str) -> str:
    """Map Group-B/C yearly_decision codes to canonical category."""
    if pd.isna(dec):
        return None
    dec_lower = dec.strip().lower()
    # 'relocated' is a STATUS marker, not an active decision -- skip
    if dec_lower == "relocated":
        return None
    if "elevat" in dec_lower and "insur" in dec_lower:
        return "Both"
    if "elevat" in dec_lower:
        return "Elevation"
    if "insur" in dec_lower:
        return "Insurance"
    if "relocat" in dec_lower:
        return "Relocate"
    if "nothing" in dec_lower:
        return "DoNothing"
    return "DoNothing"  # fallback


# ---------------------------------------------------------------------------
# Hallucination rate  R_H
# ---------------------------------------------------------------------------
def compute_hallucination_rate(df: pd.DataFrame, group: str) -> float:
    """
    Hallucination = choosing an action the agent has already permanently
    completed (elevate when already elevated, insure when already insured,
    relocate when already relocated).

    For Group A:  uses 'raw_llm_decision' column + state columns.
    For Group B/C: uses 'yearly_decision' column + state columns.

    The state columns (elevated, has_insurance, relocated) represent the
    agent's state at the END of the current year.  To determine prior state
    we look at the previous year's row.  For year 1 we infer the initial
    condition from the year-1 state and decision.
    """
    halluc = 0
    total = 0

    for agent_id in df["agent_id"].unique():
        agent = df[df["agent_id"] == agent_id].sort_values("year").reset_index(drop=True)

        for i in range(len(agent)):
            # ---- get the raw decision string ----
            if group == "Group_A":
                raw = str(agent.loc[i, "raw_llm_decision"]).strip().lower()
            else:
                raw = str(agent.loc[i, "yearly_decision"]).strip().lower()

            if raw == "nan" or raw == "relocated":
                continue
            total += 1

            # ---- determine prior-year state ----
            if i == 0:
                # Year 1: infer prior (initial) state.
                # If state is True but current decision is NOT that action,
                # the agent must have started with it (initial condition).
                elev_prior = (agent.loc[i, "elevated"] == True) and ("elevat" not in raw)
                ins_prior = (agent.loc[i, "has_insurance"] == True) and ("insur" not in raw)
                reloc_prior = (agent.loc[i, "relocated"] == True) and ("relocat" not in raw)
            else:
                elev_prior = agent.loc[i - 1, "elevated"] == True
                ins_prior = agent.loc[i - 1, "has_insurance"] == True
                reloc_prior = agent.loc[i - 1, "relocated"] == True

            # ---- check hallucination ----
            is_halluc = False
            if "elevat" in raw and elev_prior:
                is_halluc = True
            if "insur" in raw and ins_prior:
                is_halluc = True
            if "relocat" in raw and reloc_prior:
                is_halluc = True

            if is_halluc:
                halluc += 1

    return halluc / total if total > 0 else 0.0


# ---------------------------------------------------------------------------
# Normalised Shannon entropy  H_norm (averaged over years)
# ---------------------------------------------------------------------------
def compute_normalized_entropy(df: pd.DataFrame, group: str) -> float:
    """
    Per-year Shannon entropy over 5 canonical categories, normalised by
    log2(5), then averaged across all simulation years.
    """
    if group == "Group_A":
        df = df.copy()
        df["canon"] = df["raw_llm_decision"].apply(normalize_decision_group_a)
    else:
        df = df.copy()
        df["canon"] = df["yearly_decision"].apply(normalize_decision_group_bc)

    df = df.dropna(subset=["canon"])
    H_max = np.log2(N_CATS)

    yearly_H = []
    for year in sorted(df["year"].unique()):
        yr_df = df[df["year"] == year]
        counts = yr_df["canon"].value_counts()
        # Ensure all 5 categories are represented (some may be 0)
        probs = np.array([counts.get(c, 0) for c in CANONICAL], dtype=float)
        probs = probs / probs.sum()
        # Shannon entropy (only non-zero terms)
        nonzero = probs[probs > 0]
        H = -np.sum(nonzero * np.log2(nonzero))
        yearly_H.append(H / H_max)

    return float(np.mean(yearly_H))


# ---------------------------------------------------------------------------
# Main computation loop
# ---------------------------------------------------------------------------
results = {}  # (model, group) -> dict with R_H, H_norm, EBE

for model in MODELS:
    for group in GROUPS:
        csv_path = os.path.join(BASE, model, group, "Run_1", "simulation_log.csv")
        if not os.path.isfile(csv_path):
            print(f"  [skip] {model}/{group} -- file not found")
            continue

        df = pd.read_csv(csv_path)
        R_H = compute_hallucination_rate(df, group)
        H_norm = compute_normalized_entropy(df, group)
        EBE = H_norm * (1.0 - R_H)
        results[(model, group)] = {"R_H": R_H, "H_norm": H_norm, "EBE": EBE}

# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------
print("\n" + "=" * 72)
print(f"{'Model':<14} {'Group':<10} {'H_norm':>8} {'R_H':>8} {'EBE':>8}")
print("-" * 72)
for model, mlabel in zip(MODELS, MODEL_LABELS):
    for group, glabel in zip(GROUPS, GROUP_LABELS):
        key = (model, group)
        if key in results:
            r = results[key]
            print(f"{mlabel:<14} {glabel:<10} {r['H_norm']:8.4f} {r['R_H']:8.4f} {r['EBE']:8.4f}")
        else:
            print(f"{mlabel:<14} {glabel:<10} {'--':>8} {'--':>8} {'--':>8}")
print("=" * 72)

# ---------------------------------------------------------------------------
# Figure 3 -- Grouped bar chart
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(8, 4.5))

group_colors = {
    "Group_A": "#c0392b",    # red
    "Group_B": "#4682b4",    # steelblue
    "Group_C": "#1b2a49",    # darkblue
}

x = np.arange(len(MODELS))
bar_width = 0.22

for j, (group, glabel) in enumerate(zip(GROUPS, GROUP_LABELS)):
    ebe_vals = []
    for model in MODELS:
        key = (model, group)
        if key in results:
            ebe_vals.append(results[key]["EBE"])
        else:
            ebe_vals.append(np.nan)

    offsets = x + (j - 1) * bar_width
    bars = ax.bar(
        offsets,
        ebe_vals,
        width=bar_width,
        color=group_colors[group],
        edgecolor="white",
        linewidth=0.6,
        label=glabel,
        zorder=3,
    )

    # Value labels above bars
    for bar, val in zip(bars, ebe_vals):
        if not np.isnan(val):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.012,
                f"{val:.2f}",
                ha="center",
                va="bottom",
                fontsize=7.5,
                color="#333333",
            )

# ---- Non-monotonic scaling annotation (12B entropy collapse) ----
# Identify the 12B index
idx_12b = MODELS.index("gemma3_12b")

# Collect all EBE values at 12B to position the annotation
ebe_12b_vals = [
    results.get((MODELS[idx_12b], g), {}).get("EBE", 0) for g in GROUPS
]
max_ebe_12b = max(v for v in ebe_12b_vals if v is not None and not np.isnan(v))

# Also get the max at 4B for comparison
ebe_4b_vals = [
    results.get((MODELS[0], g), {}).get("EBE", 0) for g in GROUPS
]
max_ebe_4b = max(v for v in ebe_4b_vals if v is not None and not np.isnan(v))

# Place annotation
ann_x = x[idx_12b]
ann_y = max_ebe_12b + 0.07

ax.annotate(
    "12B entropy\ncollapse",
    xy=(ann_x, max_ebe_12b + 0.025),
    xytext=(ann_x + 0.55, ann_y + 0.06),
    fontsize=8.5,
    fontstyle="italic",
    color="#c0392b",
    ha="center",
    arrowprops=dict(
        arrowstyle="-|>",
        color="#c0392b",
        lw=1.2,
        connectionstyle="arc3,rad=-0.15",
    ),
)

# ---- Axes & labels ----
ax.set_xticks(x)
ax.set_xticklabels(MODEL_LABELS, fontsize=10)
ax.set_ylabel("Effective Behavioral Entropy (EBE)", fontsize=10.5)
ax.set_xlabel("Model", fontsize=10.5)
ax.set_ylim(0, 0.70)
ax.yaxis.set_major_locator(mticker.MultipleLocator(0.1))
ax.yaxis.set_minor_locator(mticker.MultipleLocator(0.05))

# Light grid
ax.grid(axis="y", linestyle="--", linewidth=0.4, alpha=0.5, zorder=0)
ax.set_axisbelow(True)

# Legend
ax.legend(
    loc="upper right",
    frameon=True,
    framealpha=0.9,
    edgecolor="#cccccc",
    fontsize=9,
)

# Spine cleanup
for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)

fig.tight_layout()

# ---- Save ----
out_path = os.path.join(OUT_DIR, "fig3_ebe_scaling.png")
fig.savefig(out_path, dpi=200, bbox_inches="tight")
print(f"\nFigure saved to {out_path}")
plt.close(fig)
