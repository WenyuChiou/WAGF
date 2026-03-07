"""
Nature Water — Figure 2c supplement: Pre- vs post-validation action distributions
(Governed proposed vs executed) alongside Ungoverned executed.

Key insight: The gap between governed proposed and executed distributions is SMALL,
showing governance shapes reasoning (agents propose diverse actions) rather than
filtering bad actions into diversity post-hoc.

Output:
  paper/nature_water/figures/Fig2c_prepost.png
  paper/nature_water/figures/Fig2c_prepost.pdf
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

# ── Paths ──
BASE    = Path(__file__).resolve().parents[3]
RESULTS = BASE / "examples" / "irrigation_abm" / "results"
OUT     = BASE / "paper" / "nature_water" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

SEEDS = [42, 43, 44]

# ── Actions ──
SKILLS = [
    'increase_large',
    'increase_small',
    'maintain_demand',
    'decrease_small',
    'decrease_large',
]
SKILL_LABELS = [
    'Increase large',
    'Increase small',
    'Maintain',
    'Decrease small',
    'Decrease large',
]

# ── Colors (Okabe-Ito) ──
GOV_COLOR   = '#0072B2'   # blue
UNGOV_COLOR = '#D55E00'   # vermillion

# Lighter shade for "Proposed" governed bars
GOV_LIGHT   = '#6DB8E8'   # lighter blue

# ── Nature Water style ──
plt.rcParams.update({
    'font.family':        'sans-serif',
    'font.sans-serif':    ['Arial', 'Helvetica'],
    'font.size':          7.5,
    'axes.labelsize':     8,
    'axes.titlesize':     9,
    'xtick.labelsize':    7,
    'ytick.labelsize':    7,
    'legend.fontsize':    7,
    'figure.dpi':         300,
    'savefig.dpi':        300,
    'savefig.bbox':       'tight',
    'axes.spines.top':    False,
    'axes.spines.right':  False,
    'xtick.direction':    'out',
    'ytick.direction':    'out',
})


# ══════════════════════════════════════════════════════════════
# DATA LOADING
# ══════════════════════════════════════════════════════════════

def load_governed_audit():
    """Load governed audit logs. Returns pooled DataFrame."""
    frames = []
    for seed in SEEDS:
        fpath = RESULTS / f"production_v20_42yr_seed{seed}" / "irrigation_farmer_governance_audit.csv"
        if fpath.exists():
            df = pd.read_csv(fpath, encoding='utf-8')
            df['seed'] = seed
            frames.append(df)
        else:
            print(f"  WARNING: Missing {fpath}")
    if not frames:
        raise FileNotFoundError("No governed audit logs found.")
    return pd.concat(frames, ignore_index=True)


def load_ungoverned_sim():
    """Load ungoverned simulation logs. Returns pooled DataFrame."""
    frames = []
    for seed in SEEDS:
        fpath = RESULTS / f"ungoverned_v20_42yr_seed{seed}" / "simulation_log.csv"
        if fpath.exists():
            df = pd.read_csv(fpath, encoding='utf-8')
            df['seed'] = seed
            frames.append(df)
        else:
            print(f"  WARNING: Missing {fpath}")
    if not frames:
        raise FileNotFoundError("No ungoverned simulation logs found.")
    return pd.concat(frames, ignore_index=True)


def compute_pct(series, skills=SKILLS):
    """Compute % share of each skill in a Series."""
    total = len(series)
    return {s: series.tolist().count(s) / total * 100 for s in skills}


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def generate_figure():
    print("Loading data...")
    gov_df    = load_governed_audit()
    ungov_df  = load_ungoverned_sim()

    print(f"  Governed audit rows   : {len(gov_df):,}")
    print(f"  Ungoverned sim rows   : {len(ungov_df):,}")

    # ── Compute distributions ──
    gov_proposed  = compute_pct(gov_df['proposed_skill'])
    gov_executed  = compute_pct(gov_df['final_skill'])
    ungov_exec    = compute_pct(ungov_df['yearly_decision'])

    # ── Print verification table ──
    print("\n--- Verification: Action percentages ---")
    print(f"{'Action':<20} {'Gov Proposed':>14} {'Gov Executed':>14} {'Diff':>8} {'Ungov':>10}")
    print("-" * 70)
    for s, lbl in zip(SKILLS, SKILL_LABELS):
        p  = gov_proposed[s]
        e  = gov_executed[s]
        u  = ungov_exec[s]
        diff = e - p
        print(f"{lbl:<20} {p:>13.1f}% {e:>13.1f}% {diff:>+7.1f}% {u:>9.1f}%")
    print()

    # ── Layout: grouped horizontal bars ──
    #
    # For each of 5 actions, we draw 3 bars vertically:
    #   Top    : Governed Proposed (lighter blue, hatched)
    #   Middle : Governed Executed (solid blue)
    #   Bottom : Ungoverned Executed (vermillion)
    #
    # Groups are separated by a small gap.

    n_actions  = len(SKILLS)
    bar_h      = 0.22          # individual bar height
    group_gap  = 0.10          # gap between the 3 bars within one action group
    group_pitch = 3 * bar_h + 2 * group_gap + 0.15   # vertical pitch between groups

    fig, ax = plt.subplots(figsize=(3.5, 3.0))

    # Y positions for each action group (0 = top, 4 = bottom)
    # We'll invert y-axis so action 0 appears at top.
    group_centers = np.arange(n_actions) * group_pitch

    for gi, (skill, label) in enumerate(zip(SKILLS, SKILL_LABELS)):
        yc = group_centers[gi]   # group center

        # Offsets within group (top → bottom before inversion)
        y_proposed = yc - (bar_h + group_gap)
        y_executed = yc
        y_ungov    = yc + (bar_h + group_gap)

        p_val = gov_proposed[skill]
        e_val = gov_executed[skill]
        u_val = ungov_exec[skill]

        # Governed Proposed — lighter blue, hatched
        ax.barh(y_proposed, p_val, height=bar_h,
                color=GOV_LIGHT, edgecolor=GOV_COLOR, linewidth=0.6,
                hatch='///', label='Governed (proposed)' if gi == 0 else None)

        # Governed Executed — solid blue
        ax.barh(y_executed, e_val, height=bar_h,
                color=GOV_COLOR, edgecolor=GOV_COLOR, linewidth=0.6,
                label='Governed (executed)' if gi == 0 else None)

        # Ungoverned Executed — vermillion
        ax.barh(y_ungov, u_val, height=bar_h,
                color=UNGOV_COLOR, edgecolor=UNGOV_COLOR, linewidth=0.6,
                label='Ungoverned' if gi == 0 else None)

        # Value labels (only if wide enough)
        for ypos, val in [(y_proposed, p_val), (y_executed, e_val), (y_ungov, u_val)]:
            if val >= 8:
                ax.text(val + 0.5, ypos, f'{val:.0f}%',
                        va='center', ha='left', fontsize=5.5, color='#333333')

    # ── Y-axis: action group labels at group center ──
    ax.set_yticks(group_centers)
    ax.set_yticklabels(SKILL_LABELS, fontsize=7)
    ax.invert_yaxis()

    # ── X-axis ──
    ax.set_xlabel('Action share (%)', fontsize=8)
    ax.set_xlim(0, 75)
    ax.set_xticks([0, 20, 40, 60])

    # ── Legend ──
    legend_patches = [
        mpatches.Patch(facecolor=GOV_LIGHT, edgecolor=GOV_COLOR,
                       hatch='///', label='Governed (proposed)'),
        mpatches.Patch(facecolor=GOV_COLOR, edgecolor=GOV_COLOR,
                       label='Governed (executed)'),
        mpatches.Patch(facecolor=UNGOV_COLOR, edgecolor=UNGOV_COLOR,
                       label='Ungoverned'),
    ]
    ax.legend(handles=legend_patches, loc='lower right', frameon=False,
              fontsize=6.5, handlelength=1.2, handleheight=0.9)

    # ── Panel label ──
    ax.text(-0.14, 1.04, '(c)', transform=ax.transAxes,
            fontsize=9, fontweight='bold', va='top')

    fig.tight_layout(pad=0.4)

    # ── Save ──
    for fmt in ['png', 'pdf']:
        outpath = OUT / f"Fig2c_prepost.{fmt}"
        fig.savefig(str(outpath), dpi=300)
        print(f"  Saved: {outpath}")

    plt.close(fig)


if __name__ == '__main__':
    generate_figure()
    print("\nDone.")
