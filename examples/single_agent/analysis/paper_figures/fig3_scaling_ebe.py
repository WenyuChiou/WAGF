"""
SAGE Paper — Figure 3: Cross-Model Scaling of Behavioral Entropy
=================================================================
Shows mean normalised Shannon entropy vs model size for DeepSeek R1 and
Gemma 3 families, grouped by governance treatment (A/B/C).

Key message:
  - Without governance (Group A): entropy varies wildly across model sizes,
    with frequent mode collapse (DeepSeek 8b -> Elevation, Gemma 12b -> Both).
  - With governance (B/C): entropy stays in a healthy range regardless of
    model size, preventing mode collapse.

Reads:
  SQ2_Final_Results/yearly_entropy_audited.csv  (DeepSeek R1: 1.5b-32b)
  SQ2_Final_Results/gemma3_entropy_audited.csv  (Gemma 3: 4b-27b)

Usage:
  python fig3_scaling_ebe.py
"""

import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

# ---------- paths ----------
SCRIPT_DIR = Path(__file__).resolve().parent
SQ2 = SCRIPT_DIR.parents[0] / "SQ2_Final_Results"

# ---------- style ----------
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 9,
    "axes.labelsize": 10,
    "axes.titlesize": 10,
    "legend.fontsize": 7.5,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})

# Okabe-Ito palette
C_A = "#D55E00"   # vermillion
C_B = "#0072B2"   # blue
C_C = "#009E73"   # teal

# Model parameters (billions)
MODEL_SIZES = {
    "deepseek_r1_1_5b": 1.5,
    "deepseek_r1_8b": 8,
    "deepseek_r1_14b": 14,
    "deepseek_r1_32b": 32,
    "gemma3_4b": 4,
    "gemma3_12b": 12,
    "gemma3_27b": 27,
}

MODEL_FAMILY = {
    "deepseek_r1_1_5b": "DeepSeek R1",
    "deepseek_r1_8b": "DeepSeek R1",
    "deepseek_r1_14b": "DeepSeek R1",
    "deepseek_r1_32b": "DeepSeek R1",
    "gemma3_4b": "Gemma 3",
    "gemma3_12b": "Gemma 3",
    "gemma3_27b": "Gemma 3",
}


def load_data():
    """Load and merge DeepSeek + Gemma entropy data."""
    ds_path = SQ2 / "yearly_entropy_audited.csv"
    gm_path = SQ2 / "gemma3_entropy_audited.csv"

    frames = []
    if ds_path.exists():
        frames.append(pd.read_csv(ds_path))
    else:
        print(f"WARNING: {ds_path} not found")

    if gm_path.exists():
        frames.append(pd.read_csv(gm_path))
    else:
        print(f"WARNING: {gm_path} not found")

    if not frames:
        print("No data found. Exiting.")
        sys.exit(1)

    df = pd.concat(frames, ignore_index=True)
    df["Size_B"] = df["Model"].map(MODEL_SIZES)
    df["Family"] = df["Model"].map(MODEL_FAMILY)
    return df


def compute_mean_entropy(df):
    """Compute mean H_norm per model × group (years 2-10 to exclude startup)."""
    # Use years 2-10 to get converged behavior, not initial conditions
    df_conv = df[df["Year"] >= 2].copy()
    summary = (
        df_conv.groupby(["Model", "Group"])
        .agg(
            Mean_H_norm=("Shannon_Entropy_Norm", "mean"),
            Std_H_norm=("Shannon_Entropy_Norm", "std"),
            Size_B=("Size_B", "first"),
            Family=("Family", "first"),
        )
        .reset_index()
    )
    return summary


def main():
    df = load_data()
    summary = compute_mean_entropy(df)

    fig, ax = plt.subplots(figsize=(4.5, 3.2), constrained_layout=True)

    # Plot each group × family combination
    group_cfg = {
        "Group_A": {"color": C_A, "label": "A (ungoverned)", "zorder": 3},
        "Group_B": {"color": C_B, "label": "B (governance + window)", "zorder": 4},
        "Group_C": {"color": C_C, "label": "C (governance + memory)", "zorder": 5},
    }

    family_markers = {
        "DeepSeek R1": {"marker": "o", "size": 50},
        "Gemma 3": {"marker": "D", "size": 40},
    }

    # Plot data points
    for group, gcfg in group_cfg.items():
        g = summary[summary["Group"] == group]
        if g.empty:
            continue

        for family, fmcfg in family_markers.items():
            gf = g[g["Family"] == family]
            if gf.empty:
                continue

            label = f"{gcfg['label']}" if family == "DeepSeek R1" else None
            ax.scatter(
                gf["Size_B"], gf["Mean_H_norm"],
                c=gcfg["color"],
                marker=fmcfg["marker"],
                s=fmcfg["size"],
                edgecolors="white",
                linewidths=0.5,
                zorder=gcfg["zorder"],
                label=label,
            )
            # Error bars
            ax.errorbar(
                gf["Size_B"], gf["Mean_H_norm"],
                yerr=gf["Std_H_norm"],
                fmt="none",
                ecolor=gcfg["color"],
                elinewidth=0.7,
                capsize=2,
                alpha=0.5,
                zorder=2,
            )

    # --- Annotations for mode collapse ---
    # DeepSeek R1 8B Group A: mode collapse to Elevation
    ds8b_a = summary[(summary["Model"] == "deepseek_r1_8b") & (summary["Group"] == "Group_A")]
    if not ds8b_a.empty:
        ax.annotate(
            "Elevation\nlock-in",
            xy=(8, ds8b_a["Mean_H_norm"].values[0]),
            xytext=(12, 0.08),
            fontsize=6.5, color=C_A, ha="center",
            arrowprops=dict(arrowstyle="->", color=C_A, lw=0.7),
        )

    # Gemma 12B Group A: mode collapse to Both
    gm12_a = summary[(summary["Model"] == "gemma3_12b") & (summary["Group"] == "Group_A")]
    if not gm12_a.empty:
        ax.annotate(
            "Both\nlock-in",
            xy=(12, gm12_a["Mean_H_norm"].values[0]),
            xytext=(18, 0.15),
            fontsize=6.5, color=C_A, ha="center",
            arrowprops=dict(arrowstyle="->", color=C_A, lw=0.7),
        )

    # DeepSeek 1.5B Group A: agent loss / collapse
    ds15_a = summary[(summary["Model"] == "deepseek_r1_1_5b") & (summary["Group"] == "Group_A")]
    if not ds15_a.empty:
        ax.annotate(
            "Agent\nloss",
            xy=(1.5, ds15_a["Mean_H_norm"].values[0]),
            xytext=(2.5, 0.65),
            fontsize=6.5, color=C_A, ha="center",
            arrowprops=dict(arrowstyle="->", color=C_A, lw=0.7),
        )

    # --- Family marker legend ---
    ax.scatter([], [], marker="o", c="gray", s=50, edgecolors="white",
               linewidths=0.5, label="DeepSeek R1")
    ax.scatter([], [], marker="D", c="gray", s=40, edgecolors="white",
               linewidths=0.5, label="Gemma 3")

    ax.set_xscale("log")
    ax.set_xlabel("Model Size (billion parameters)")
    ax.set_ylabel("Mean H$_{norm}$ (years 2–10)")
    ax.set_xlim(1, 40)
    ax.set_ylim(-0.02, 1.0)

    # Custom x-ticks — offset 12/14 labels to avoid overlap
    ax.set_xticks([1.5, 4, 8, 12, 14, 27, 32])
    ax.set_xticklabels(["1.5", "4", "8", "12", "14", "27", "32"],
                        fontsize=7)
    ax.xaxis.set_minor_formatter(mticker.NullFormatter())
    # Nudge 12B and 14B ticks to avoid overlap
    for tick in ax.xaxis.get_major_ticks():
        tick.label1.set_horizontalalignment("center")

    ax.legend(loc="upper right", framealpha=0.9, edgecolor="none", ncol=2)
    ax.grid(True, alpha=0.2)

    # Governance zone annotation
    ax.axhspan(0.3, 0.8, alpha=0.06, color=C_B, zorder=0)
    ax.text(1.15, 0.55, "Governed\nrange", fontsize=7, color=C_B,
            ha="left", va="center", style="italic", alpha=0.7)

    # ======== Save ========
    out_png = SCRIPT_DIR / "fig3_scaling_ebe.png"
    fig.savefig(out_png, dpi=300)
    print(f"Saved: {out_png}")

    out_pdf = SCRIPT_DIR / "fig3_scaling_ebe.pdf"
    fig.savefig(out_pdf)
    print(f"Saved: {out_pdf}")

    plt.close()

    # Print summary table
    print("\n--- Cross-Model Mean H_norm (years 2-10) ---")
    pivot = summary.pivot_table(
        index="Model", columns="Group", values="Mean_H_norm", aggfunc="first"
    )
    pivot["Size_B"] = pivot.index.map(MODEL_SIZES)
    pivot = pivot.sort_values("Size_B")
    print(pivot.to_string(float_format="{:.3f}".format))


if __name__ == "__main__":
    main()
