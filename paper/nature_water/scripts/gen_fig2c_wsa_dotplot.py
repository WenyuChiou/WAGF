#!/usr/bin/env python3
"""
Nature Water Fig 2(c): WSA-Conditional Increase Rate Dot Plot.

Shows the fraction of decisions that are demand-increases at each WSA level,
for three conditions (Governed, No Ceiling, Ungoverned).
Demonstrates WHERE the demand-ceiling rule changes behaviour quality:
at high scarcity (H/VH), not at low scarcity.

Data: Gemma-3 4B, 78 agents × 42 years, 3 seeds each.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica'],
    'font.size': 7.5,
    'axes.labelsize': 8,
    'axes.titlesize': 9,
    'xtick.labelsize': 7,
    'ytick.labelsize': 7,
    'legend.fontsize': 6.5,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'axes.spines.top': False,
    'axes.spines.right': False,
    'xtick.direction': 'out',
    'ytick.direction': 'out',
})

# ── Paths ──
BASE = Path(__file__).resolve().parents[3]
RESULTS = BASE / "examples" / "irrigation_abm" / "results"
OUT = BASE / "paper" / "nature_water" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# ── Colors (Okabe-Ito) ──
GOV_COLOR   = '#0072B2'
UNGOV_COLOR = '#D55E00'
A1_COLOR    = '#009E73'

SEEDS = [42, 43, 44]
WSA_ORDER = ['VL', 'L', 'M', 'H', 'VH']
WSA_LABELS = ['Very Low', 'Low', 'Moderate', 'High', 'Very High']
INCREASE_ACTIONS = {'increase_large', 'increase_small'}

CONDITIONS = {
    'governed':   ('production_v20_42yr_seed{}', GOV_COLOR, 'o', 'Governed'),
    'a1':         ('ablation_no_ceiling_seed{}', A1_COLOR, 'D', 'No ceiling'),
    'ungoverned': ('ungoverned_v20_42yr_seed{}', UNGOV_COLOR, 's', 'Ungoverned'),
}


def compute_increase_rate_by_wsa(df):
    """Compute fraction of decisions that are increases, grouped by WSA level."""
    rates = {}
    for wsa in WSA_ORDER:
        subset = df[df['wsa_label'] == wsa]
        if len(subset) == 0:
            rates[wsa] = np.nan
        else:
            n_increase = subset['yearly_decision'].isin(INCREASE_ACTIONS).sum()
            rates[wsa] = n_increase / len(subset)
    return rates


def main():
    # ── Load data and compute per-seed increase rates ──
    all_rates = {}  # {condition: {wsa: [rate_seed1, rate_seed2, rate_seed3]}}
    all_counts = {}  # {condition: {wsa: [n_seed1, n_seed2, n_seed3]}}

    for cond, (pattern, color, marker, label) in CONDITIONS.items():
        all_rates[cond] = {w: [] for w in WSA_ORDER}
        all_counts[cond] = {w: [] for w in WSA_ORDER}
        for seed in SEEDS:
            fpath = RESULTS / pattern.format(seed) / "simulation_log.csv"
            if not fpath.exists():
                print(f"  WARNING: {fpath} not found")
                continue
            df = pd.read_csv(fpath, encoding='utf-8')
            rates = compute_increase_rate_by_wsa(df)
            for w in WSA_ORDER:
                all_rates[cond][w].append(rates[w])
                all_counts[cond][w].append(len(df[df['wsa_label'] == w]))

    # ── Print summary ──
    print("\n=== Increase Rate by WSA Level ===")
    for cond in CONDITIONS:
        print(f"\n{cond}:")
        for w in WSA_ORDER:
            vals = all_rates[cond][w]
            counts = all_counts[cond][w]
            if vals:
                print(f"  {w}: {np.mean(vals):.3f} (range {min(vals):.3f}-{max(vals):.3f}), "
                      f"n={int(np.mean(counts))}/seed")

    # ── Plot ──
    fig, ax = plt.subplots(figsize=(3.5, 2.8))

    x_positions = np.arange(len(WSA_ORDER))
    offsets = {'governed': -0.15, 'a1': 0.0, 'ungoverned': 0.15}

    for cond, (pattern, color, marker, label) in CONDITIONS.items():
        means = []
        mins = []
        maxs = []
        for w in WSA_ORDER:
            vals = all_rates[cond][w]
            if vals and not any(np.isnan(vals)):
                means.append(np.mean(vals))
                mins.append(min(vals))
                maxs.append(max(vals))
            else:
                means.append(np.nan)
                mins.append(np.nan)
                maxs.append(np.nan)

        means = np.array(means)
        mins = np.array(mins)
        maxs = np.array(maxs)
        x = x_positions + offsets[cond]

        # Min-max whiskers
        yerr_low = means - mins
        yerr_high = maxs - means
        ax.errorbar(x, means, yerr=[yerr_low, yerr_high],
                     fmt='none', ecolor=color, elinewidth=0.8,
                     capsize=2.5, capthick=0.8, zorder=3)

        # Markers
        ax.scatter(x, means, c=color, marker=marker, s=28, zorder=4,
                   edgecolors='white', linewidths=0.3, label=label)

    # ── Random baseline at 0.40 ──
    ax.axhline(y=0.40, color='#888888', ls='--', lw=0.6, alpha=0.6, zorder=1)
    ax.text(4.35, 0.41, 'Random\n(2/5)', fontsize=5.5, color='#888888',
            va='bottom', ha='left')

    # ── Shaded region for H/VH (where ceiling binds) ──
    ax.axvspan(2.5, 4.5, alpha=0.06, color='#D55E00', zorder=0)
    ax.text(3.5, 0.97, 'Ceiling rule binds', fontsize=5.5,
            ha='center', va='top', color='#666666', fontstyle='italic')

    # ── Annotation: governed vs no-ceiling gap at VH ──
    gov_vh = np.mean(all_rates['governed']['VH'])
    a1_vh = np.mean(all_rates['a1']['VH'])
    ungov_vh = np.mean(all_rates['ungoverned']['VH'])

    # Bracket between governed and no-ceiling at VH
    mid_y = (gov_vh + a1_vh) / 2
    delta_pp = (a1_vh - gov_vh) * 100
    if delta_pp > 0:
        ax.annotate(f'+{delta_pp:.0f}pp',
                    xy=(4.0, mid_y), fontsize=5.5, color='#333333',
                    ha='left', va='center')

    # ── Axes ──
    ax.set_xticks(x_positions)
    ax.set_xticklabels(WSA_LABELS, fontsize=7)
    ax.set_xlabel('Water shortage appraisal (agent self-report)', fontsize=8)
    ax.set_ylabel('Fraction choosing demand increase', fontsize=8)
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlim(-0.5, 4.8)

    # Panel label
    ax.text(-0.12, 1.05, '(c)', transform=ax.transAxes,
            fontsize=9, fontweight='bold', va='top')

    # Legend
    ax.legend(loc='upper left', frameon=False, fontsize=6.5,
              handletextpad=0.3, borderpad=0.3)

    plt.tight_layout()

    for ext in ['png', 'pdf']:
        out_path = OUT / f"Fig2c_wsa_dotplot.{ext}"
        fig.savefig(out_path, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"  Saved: {out_path}")

    plt.close()
    print("Done.")


if __name__ == '__main__':
    main()
