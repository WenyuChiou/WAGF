"""
Figure 3: Cross-Model EBE Scaling (WRR Technical Note)
=======================================================
Computes EBE = H_norm * (1 - R_H) for each (model, group) combination.

Two model families side-by-side:
  Left panel : Gemma3 (4B, 12B, 27B) — Google
  Right panel: Ministral (3B, 8B, 14B) — Mistral

Skips missing data gracefully (e.g. 27B Group C, Ministral 8B/14B).

AGU/WRR: 300 DPI, serif, Okabe-Ito palette.
"""

import os, sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import numpy as np
import pandas as pd
pd.set_option('future.no_silent_downcasting', True)
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# PostHocValidator for unified R_H
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from broker.validators.posthoc import KeywordClassifier, ThinkingRulePostHoc
from broker.validators.posthoc.unified_rh import _compute_physical_hallucinations

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
BASE = SCRIPT_DIR.parents[1] / "results" / "JOH_FINAL"
OUT_DIR = SCRIPT_DIR

GEMMA_MODELS = ["gemma3_4b", "gemma3_12b", "gemma3_27b"]
GEMMA_LABELS = ["4B", "12B", "27B"]
MINISTRAL_MODELS = ["ministral3_3b", "ministral3_8b", "ministral3_14b"]
MINISTRAL_LABELS = ["3B", "8B", "14B"]

GROUPS = ["Group_A", "Group_B", "Group_C"]
GROUP_LABELS = ["A: Ungoverned", "B: Gov. + Window", "C: Gov. + HumanCentric"]

# 5 canonical categories for entropy
CANONICAL = ["Elevation", "Insurance", "Both", "DoNothing", "Relocate"]
N_CATS = len(CANONICAL)

# WRR style
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 9, "axes.labelsize": 10, "axes.titlesize": 10,
    "legend.fontsize": 7.5, "xtick.labelsize": 8, "ytick.labelsize": 8,
    "figure.dpi": 300, "savefig.dpi": 300, "savefig.bbox": "tight",
    "axes.linewidth": 0.6,
})

# Okabe-Ito
C_A = "#D55E00"  # vermillion
C_B = "#0072B2"  # blue
C_C = "#009E73"  # teal
GROUP_COLORS = {"Group_A": C_A, "Group_B": C_B, "Group_C": C_C}


# ---------------------------------------------------------------------------
# Decision normalisation helpers
# ---------------------------------------------------------------------------
def normalize_decision(raw: str) -> str:
    """Map raw decision text to canonical category."""
    if pd.isna(raw):
        return None
    s = raw.strip().lower()
    if s == "relocated":
        return None  # status marker, not an active decision
    if "elevat" in s and "insur" in s:
        return "Both"
    if "elevat" in s:
        return "Elevation"
    if "insur" in s:
        return "Insurance"
    if "relocat" in s:
        return "Relocate"
    if "nothing" in s or "do_nothing" in s:
        return "DoNothing"
    return "DoNothing"


def get_decision_column(df, group, model):
    """Determine which column holds the decision string.

    Group A baselines (all models) use LLMABMPMT-Final.py which produces
    'raw_llm_decision'.  Groups B/C use run_flood.py which produces
    'yearly_decision'.
    """
    if "raw_llm_decision" in df.columns and group == "Group_A":
        return "raw_llm_decision"
    return "yearly_decision"


# ---------------------------------------------------------------------------
# Hallucination rate  R_H
# ---------------------------------------------------------------------------
def compute_hallucination_rate(df: pd.DataFrame, dec_col: str, group: str = "B") -> float:
    """R_H = (physical + thinking) / N_active, using PostHocValidator.

    Insurance renewal excluded. Thinking violations (V1/V2/V3) included.
    """
    classifier = KeywordClassifier()
    rule_checker = ThinkingRulePostHoc()

    df = df.sort_values(["agent_id", "year"]).copy()
    ta_col = "threat_appraisal" if "threat_appraisal" in df.columns else None
    ca_col = "coping_appraisal" if "coping_appraisal" in df.columns else None
    if ta_col and ca_col:
        df = classifier.classify_dataframe(df, ta_col, ca_col)
    else:
        df["ta_level"] = "M"
        df["ca_level"] = "M"

    # Physical hallucinations
    phys_mask = _compute_physical_hallucinations(df)

    # Active mask
    df["prev_relocated"] = (
        df.groupby("agent_id")["relocated"].shift(1).fillna(False).infer_objects(copy=False)
    )
    active_mask = ~df["prev_relocated"] & (df["year"] >= 2)
    df_active = df[active_mask]
    n_active = len(df_active)
    if n_active == 0:
        return 0.0

    n_phys = int(phys_mask.reindex(df_active.index, fill_value=False).sum())

    # Thinking violations
    think_results = rule_checker.apply(
        df_active, group=group, decision_col=dec_col, ta_level_col="ta_level"
    )
    n_think = rule_checker.total_violations(think_results)

    return (n_phys + n_think) / n_active if n_active > 0 else 0.0


def compute_normalized_entropy(df: pd.DataFrame, dec_col: str) -> float:
    """Per-year H_norm over 5 canonical categories, averaged across years."""
    df = df.copy()
    df["canon"] = df[dec_col].apply(normalize_decision)
    df = df.dropna(subset=["canon"])
    H_max = np.log2(N_CATS)
    yearly_H = []
    for year in sorted(df["year"].unique()):
        yr_df = df[df["year"] == year]
        counts = yr_df["canon"].value_counts()
        probs = np.array([counts.get(c, 0) for c in CANONICAL], dtype=float)
        probs = probs / probs.sum()
        nonzero = probs[probs > 0]
        H = -np.sum(nonzero * np.log2(nonzero))
        yearly_H.append(H / H_max)
    return float(np.mean(yearly_H))


# ---------------------------------------------------------------------------
# Main computation loop
# ---------------------------------------------------------------------------
ALL_MODELS = GEMMA_MODELS + MINISTRAL_MODELS
results = {}

for model in ALL_MODELS:
    for group in GROUPS:
        csv_path = BASE / model / group / "Run_1" / "simulation_log.csv"
        if not csv_path.is_file():
            print(f"  [skip] {model}/{group}")
            continue
        df = pd.read_csv(csv_path, encoding="utf-8-sig")
        dec_col = get_decision_column(df, group, model)
        group_letter = group.replace("Group_", "")
        R_H = compute_hallucination_rate(df, dec_col, group=group_letter)
        H_norm = compute_normalized_entropy(df, dec_col)
        EBE = H_norm * (1.0 - R_H)
        results[(model, group)] = {"R_H": R_H, "H_norm": H_norm, "EBE": EBE}

# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------
all_labels = GEMMA_LABELS + MINISTRAL_LABELS
print("\n" + "=" * 72)
print(f"{'Model':<20} {'Group':<24} {'H_norm':>8} {'R_H':>8} {'EBE':>8}")
print("-" * 72)
for model, mlabel in zip(ALL_MODELS, ["Gemma3 " + l for l in GEMMA_LABELS] + ["Ministral " + l for l in MINISTRAL_LABELS]):
    for group, glabel in zip(GROUPS, GROUP_LABELS):
        key = (model, group)
        if key in results:
            r = results[key]
            print(f"{mlabel:<20} {glabel:<24} {r['H_norm']:8.4f} {r['R_H']:8.4f} {r['EBE']:8.4f}")
        else:
            print(f"{mlabel:<20} {glabel:<24} {'--':>8} {'--':>8} {'--':>8}")
print("=" * 72)

# ---------------------------------------------------------------------------
# Figure 3 -- Two-panel grouped bar chart
# ---------------------------------------------------------------------------
# Determine which families have data
gemma_available = [m for m in GEMMA_MODELS if any((m, g) in results for g in GROUPS)]
ministral_available = [m for m in MINISTRAL_MODELS if any((m, g) in results for g in GROUPS)]
has_ministral = len(ministral_available) > 0

if has_ministral:
    fig, (ax_g, ax_m) = plt.subplots(1, 2, figsize=(7.0, 3.5),
                                      constrained_layout=True,
                                      gridspec_kw={"width_ratios": [len(gemma_available), max(len(ministral_available), 1)]})
else:
    fig, ax_g = plt.subplots(figsize=(5.0, 3.5), constrained_layout=True)

def plot_family(ax, models, labels, title):
    x = np.arange(len(models))
    bar_width = 0.22
    for j, (group, glabel) in enumerate(zip(GROUPS, GROUP_LABELS)):
        ebe_vals = []
        for model in models:
            key = (model, group)
            if key in results:
                ebe_vals.append(results[key]["EBE"])
            else:
                ebe_vals.append(np.nan)
        offsets = x + (j - 1) * bar_width
        bars = ax.bar(offsets, ebe_vals, width=bar_width,
                      color=GROUP_COLORS[group], edgecolor="white", lw=0.6,
                      label=glabel, zorder=3)
        for bar, val in zip(bars, ebe_vals):
            if not np.isnan(val):
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.012,
                        f"{val:.2f}", ha="center", va="bottom",
                        fontsize=6.5, color="#333333")

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_title(title, fontweight="bold", loc="left", fontsize=9)
    ax.set_ylim(0, 0.70)
    ax.yaxis.set_major_locator(mticker.MultipleLocator(0.1))
    ax.grid(axis="y", ls="--", lw=0.4, alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)

# Panel (a): Gemma
gemma_labels_avail = [GEMMA_LABELS[GEMMA_MODELS.index(m)] for m in gemma_available]
plot_family(ax_g, gemma_available, gemma_labels_avail, "(a) Gemma3 (Google)")
ax_g.set_ylabel("Effective Behavioral Entropy (EBE)")
ax_g.legend(framealpha=0.9, edgecolor="none", fontsize=7)

# 12B collapse annotation
if "gemma3_12b" in gemma_available:
    idx_12b = gemma_available.index("gemma3_12b")
    ebe_12b = [results.get(("gemma3_12b", g), {}).get("EBE", 0) for g in GROUPS]
    max_12b = max(v for v in ebe_12b if v and not np.isnan(v))
    ax_g.annotate("12B entropy\ncollapse", xy=(idx_12b, max_12b + 0.02),
                  xytext=(idx_12b + 0.6, max_12b + 0.10),
                  fontsize=7, fontstyle="italic", color=C_A, ha="center",
                  arrowprops=dict(arrowstyle="->", color=C_A, lw=0.8))

# Panel (b): Ministral
if has_ministral:
    ministral_labels_avail = [MINISTRAL_LABELS[MINISTRAL_MODELS.index(m)] for m in ministral_available]
    plot_family(ax_m, ministral_available, ministral_labels_avail, "(b) Ministral (Mistral)")
    if len(ministral_available) < 3:
        ax_m.text(0.95, 0.95, f"{3 - len(ministral_available)} sizes\npending",
                  transform=ax_m.transAxes, ha="right", va="top",
                  fontsize=7, fontstyle="italic", color="#888888")

# ---- Save ----
out_png = OUT_DIR / "fig3_ebe_scaling.png"
out_pdf = OUT_DIR / "fig3_ebe_scaling.pdf"
fig.savefig(out_png)
fig.savefig(out_pdf)
print(f"\nSaved: {out_png}")
print(f"Saved: {out_pdf}")
plt.close(fig)
