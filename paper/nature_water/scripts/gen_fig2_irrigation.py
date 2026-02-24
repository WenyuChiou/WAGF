"""
Nature Water — Figure 2: Irrigation domain results (4-panel)
  (a) Lake Mead elevation time series
  (b) Demand ratio time series (4 conditions incl. FQL)
  (c) Skill distribution stacked bars (4 conditions)
  (d) Strategy diversity vs demand-Mead coupling scatter (12 points)
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy import stats
from pathlib import Path

# ── Paths ──
BASE = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework")
RESULTS = BASE / "examples" / "irrigation_abm" / "results"
OUT = BASE / "paper" / "nature_water" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# ── Style (Nature Water) ──
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica'],
    'font.size': 7.5,
    'axes.labelsize': 8,
    'axes.titlesize': 9,
    'xtick.labelsize': 7,
    'ytick.labelsize': 7,
    'legend.fontsize': 7,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'axes.spines.top': False,
    'axes.spines.right': False,
    'xtick.direction': 'out',
    'ytick.direction': 'out',
})

# Colors — Okabe-Ito palette (colorblind-safe)
GOV_COLOR   = '#0072B2'   # Okabe-Ito blue
UNGOV_COLOR = '#D55E00'   # Okabe-Ito vermillion
A1_COLOR    = '#009E73'   # Okabe-Ito bluish green
FQL_COLOR   = '#666666'   # grey

SEEDS = [42, 43, 44]

# Skills for LLM conditions (5-action space)
LLM_SKILLS = ['increase_large', 'increase_small', 'maintain_demand',
              'decrease_small', 'decrease_large']
LLM_SKILL_LABELS = ['Increase large', 'Increase small', 'Maintain',
                     'Decrease small', 'Decrease large']
SKILL_COLORS = ['#D55E00', '#E69F00', '#F0E442', '#56B4E9', '#0072B2']

# FQL raw actions (2-action space)
FQL_RAW_SKILLS = ['increase_demand', 'decrease_demand']

# ══════════════════════════════════════════════════════════════
# DATA LOADING
# ══════════════════════════════════════════════════════════════

def load_all_data():
    """Load all simulation logs for governed, ungoverned, A1, and FQL."""
    data = {'governed': [], 'ungoverned': [], 'a1': [], 'fql': []}
    path_map = {
        'governed':   ('production_v20_42yr_seed{}', SEEDS),
        'ungoverned': ('ungoverned_v20_42yr_seed{}', SEEDS),
        'a1':         ('ablation_no_ceiling_seed{}', SEEDS),
    }
    for cond, (pattern, seeds) in path_map.items():
        for seed in seeds:
            fpath = RESULTS / pattern.format(seed) / "simulation_log.csv"
            if fpath.exists():
                df = pd.read_csv(fpath, encoding='utf-8')
                data[cond].append(df)
            else:
                print(f"  WARNING: Missing {fpath}")

    # FQL
    for seed in SEEDS:
        fpath = RESULTS / "fql_raw" / f"seed{seed}" / "simulation_log.csv"
        if fpath.exists():
            df = pd.read_csv(fpath, encoding='utf-8')
            data['fql'].append(df)
        else:
            print(f"  WARNING: Missing {fpath}")

    for cond in data:
        print(f"  {cond}: {len(data[cond])} seeds loaded")
    return data


def compute_yearly_aggregates(data):
    """Compute per-year Mead elevation and demand ratio across seeds."""
    results = {}
    for cond in ['governed', 'ungoverned', 'a1', 'fql']:
        if not data[cond]:
            continue
        yearly_mead = []
        yearly_demand = []
        for df in data[cond]:
            by_year = df.groupby('year').agg({
                'lake_mead_level': 'first',
                'request': 'sum',
                'water_right': 'sum',
            }).reset_index()
            by_year['demand_ratio'] = by_year['request'] / by_year['water_right']
            yearly_mead.append(by_year['lake_mead_level'].values)
            yearly_demand.append(by_year['demand_ratio'].values)

        n_years = min(len(m) for m in yearly_mead)
        mead_arr = np.array([m[:n_years] for m in yearly_mead])
        demand_arr = np.array([d[:n_years] for d in yearly_demand])

        results[cond] = {
            'years': np.arange(1, n_years + 1),
            'mead_mean': mead_arr.mean(axis=0),
            'mead_std': mead_arr.std(axis=0),
            'demand_mean': demand_arr.mean(axis=0),
            'demand_std': demand_arr.std(axis=0),
            'mead_per_seed': mead_arr,
            'demand_per_seed': demand_arr,
        }
    return results


def compute_skill_distributions(data):
    """Compute action share (%) per condition.
    For FQL: use fql_raw_skill (2-action) and also yearly_decision (post-validator).
    """
    results = {}
    # LLM conditions: 5-action space
    for cond in ['governed', 'ungoverned', 'a1']:
        if not data[cond]:
            continue
        all_decisions = []
        for df in data[cond]:
            all_decisions.extend(df['yearly_decision'].tolist())
        total = len(all_decisions)
        freqs = {s: all_decisions.count(s) / total * 100 for s in LLM_SKILLS}
        results[cond] = freqs

    # FQL: yearly_decision includes validator-blocked maintain_demand
    # We show the post-validator distribution for fair comparison
    if data['fql']:
        all_decisions = []
        for df in data['fql']:
            all_decisions.extend(df['yearly_decision'].tolist())
        total = len(all_decisions)
        # Map FQL skills to LLM skill slots
        fql_to_llm = {
            'increase_demand': 'increase_large',  # FQL has no small/large distinction
            'decrease_demand': 'decrease_large',
            'maintain_demand': 'maintain_demand',
        }
        freqs = {s: 0 for s in LLM_SKILLS}
        for d in all_decisions:
            mapped = fql_to_llm.get(d, d)
            if mapped in freqs:
                freqs[mapped] += 1
        freqs = {s: v / total * 100 for s, v in freqs.items()}
        results['fql'] = freqs

    return results


def compute_ehe_per_seed(data):
    """Compute strategy diversity per seed per condition.
    LLM: 5-action space, EHE = H/log2(5)
    FQL: use fql_raw_skill (2-action), EHE = H/log2(2)
    """
    results = {}
    k_llm = len(LLM_SKILLS)

    for cond in ['governed', 'ungoverned', 'a1']:
        if not data[cond]:
            continue
        ehes = []
        for df in data[cond]:
            decisions = df['yearly_decision'].tolist()
            total = len(decisions)
            freqs = [decisions.count(s) / total for s in LLM_SKILLS]
            freqs = [f for f in freqs if f > 0]
            h = -sum(f * np.log2(f) for f in freqs)
            ehe = h / np.log2(k_llm)
            ehes.append(ehe)
        results[cond] = ehes

    # FQL: 2-action raw space
    if data['fql']:
        ehes = []
        k_fql = len(FQL_RAW_SKILLS)
        for df in data['fql']:
            decisions = df['fql_raw_skill'].tolist()
            total = len(decisions)
            freqs = [decisions.count(s) / total for s in FQL_RAW_SKILLS]
            freqs = [f for f in freqs if f > 0]
            h = -sum(f * np.log2(f) for f in freqs)
            ehe = h / np.log2(k_fql)
            ehes.append(ehe)
        results['fql'] = ehes

    return results


def compute_demand_mead_correlation(ts):
    """Compute Pearson r between yearly demand ratio and Mead per seed."""
    results = {}
    for cond in ['governed', 'ungoverned', 'a1', 'fql']:
        if cond not in ts:
            continue
        rs = []
        n_seeds = ts[cond]['mead_per_seed'].shape[0]
        for s in range(n_seeds):
            mead = ts[cond]['mead_per_seed'][s]
            demand = ts[cond]['demand_per_seed'][s]
            r, _ = stats.pearsonr(demand, mead)
            rs.append(r)
        results[cond] = rs
    return results


# ══════════════════════════════════════════════════════════════
# FIGURE 2: 4-panel irrigation
# ══════════════════════════════════════════════════════════════

def generate_figure():
    print("Loading data...")
    data = load_all_data()
    for cond in ['governed', 'ungoverned', 'a1']:
        if not data[cond]:
            print(f"  ERROR: No {cond} data found. Aborting.")
            return

    print("Computing aggregates...")
    ts = compute_yearly_aggregates(data)
    skill_dist = compute_skill_distributions(data)
    ehes = compute_ehe_per_seed(data)
    corrs = compute_demand_mead_correlation(ts)

    # Print summary
    for cond in ['governed', 'ungoverned', 'a1', 'fql']:
        if cond in ehes and cond in corrs:
            print(f"  {cond}: SD = {np.mean(ehes[cond]):.3f} +/- {np.std(ehes[cond]):.3f}, "
                  f"r = {np.mean(corrs[cond]):.3f} +/- {np.std(corrs[cond]):.3f}")

    # ── Figure setup ──
    fig = plt.figure(figsize=(7.09, 5.8))
    gs = gridspec.GridSpec(2, 2, hspace=0.42, wspace=0.38,
                           left=0.08, right=0.97, top=0.95, bottom=0.07)

    # Condition definitions for line plots
    line_conds = [
        ('governed',   GOV_COLOR,   'Governed',         '-',  1.0),
        ('ungoverned', UNGOV_COLOR, 'Ungoverned',       '--', 1.0),
        ('a1',         A1_COLOR,    'A1 (no ceiling)',  '-.', 1.0),
    ]
    line_conds_with_fql = line_conds + [
        ('fql',        FQL_COLOR,   'FQL baseline',     ':',  0.9),
    ]

    # ── Panel (a): Mead elevation ──
    ax_a = fig.add_subplot(gs[0, 0])
    for cond, color, label, ls, lw in line_conds:
        if cond not in ts:
            continue
        yrs = ts[cond]['years']
        ax_a.plot(yrs, ts[cond]['mead_mean'], color=color, linewidth=lw,
                  linestyle=ls, label=label)
        ax_a.fill_between(yrs,
                          ts[cond]['mead_mean'] - ts[cond]['mead_std'],
                          ts[cond]['mead_mean'] + ts[cond]['mead_std'],
                          alpha=0.15, color=color)

    # Shortage tier thresholds
    for elev, tier_label in [(1075, 'Tier 1'), (1050, 'Tier 2'), (1025, 'Tier 3')]:
        ax_a.axhline(y=elev, color='gray', linestyle='--', linewidth=0.7, alpha=0.6)
        ax_a.text(2, elev + 3, tier_label, fontsize=6, color='gray',
                  ha='left', va='bottom')

    ax_a.set_ylabel('Lake Mead elevation (ft)')
    ax_a.set_xlabel('Simulation year')
    ax_a.set_xlim(1, 42)
    ax_a.set_ylim(940, 1260)
    ax_a.legend(loc='lower left', frameon=False, fontsize=6.5)
    ax_a.text(-0.12, 1.05, 'a', transform=ax_a.transAxes,
              fontsize=8, fontweight='bold', va='top')

    # ── Panel (b): Demand ratio ──
    ax_b = fig.add_subplot(gs[0, 1])
    for cond, color, label, ls, lw in line_conds_with_fql:
        if cond not in ts:
            continue
        yrs = ts[cond]['years']
        ax_b.plot(yrs, ts[cond]['demand_mean'], color=color, linewidth=lw,
                  linestyle=ls, label=label)
        ax_b.fill_between(yrs,
                          ts[cond]['demand_mean'] - ts[cond]['demand_std'],
                          ts[cond]['demand_mean'] + ts[cond]['demand_std'],
                          alpha=0.15, color=color)

    ax_b.set_ylabel('Basin demand ratio')
    ax_b.set_xlabel('Simulation year')
    ax_b.set_xlim(1, 42)
    ax_b.legend(loc='upper left', frameon=False, fontsize=6.5)
    ax_b.text(-0.12, 1.05, 'b', transform=ax_b.transAxes,
              fontsize=8, fontweight='bold', va='top')

    # ── Panel (c): Skill distribution stacked bars ──
    ax_c = fig.add_subplot(gs[1, 0])

    bar_conds = [
        ('governed',   'Governed'),
        ('a1',         'A1'),
        ('ungoverned', 'Ungoverned'),
        ('fql',        'FQL'),
    ]

    y_positions = np.arange(len(bar_conds))
    bar_height = 0.55

    for idx, (cond, cond_label) in enumerate(bar_conds):
        if cond not in skill_dist:
            continue
        left = 0
        for si, (sk, sl, sc) in enumerate(zip(LLM_SKILLS, LLM_SKILL_LABELS, SKILL_COLORS)):
            val = skill_dist[cond].get(sk, 0)
            bar = ax_c.barh(idx, val, left=left, color=sc, height=bar_height,
                            label=sl if idx == 0 else None)
            if val > 6:
                ax_c.text(left + val / 2, idx, f'{val:.0f}%',
                          ha='center', va='center', fontsize=6.5, color='black')
            left += val

    ax_c.set_yticks(y_positions)
    ax_c.set_yticklabels([l for _, l in bar_conds], fontsize=7)
    ax_c.set_xlabel('Action share (%)')
    ax_c.set_xlim(0, 105)
    ax_c.set_xticks([0, 50, 100])
    ax_c.legend(loc='upper right', fontsize=6, ncol=1,
                title='Action', title_fontsize=7, frameon=False)
    ax_c.invert_yaxis()
    ax_c.text(-0.12, 1.05, 'c', transform=ax_c.transAxes,
              fontsize=8, fontweight='bold', va='top')

    # ── Panel (d): EHE vs demand-Mead scatter ──
    ax_d = fig.add_subplot(gs[1, 1])

    scatter_conds = [
        ('governed',   GOV_COLOR,   'Governed',        'o'),   # circle
        ('ungoverned', UNGOV_COLOR, 'Ungoverned',      's'),   # square
        ('a1',         A1_COLOR,    'A1 (no ceiling)',  'D'),   # diamond
        ('fql',        FQL_COLOR,   'FQL baseline',    '^'),   # triangle
    ]

    for cond, color, label, marker in scatter_conds:
        if cond not in ehes or cond not in corrs:
            continue
        ehe_vals = ehes[cond]
        r_vals = corrs[cond]
        ax_d.scatter(r_vals, ehe_vals, color=color, s=65, marker=marker,
                     zorder=5, edgecolors='white', linewidth=0.5, label=label)

        # Annotate condition mean
        mean_r = np.mean(r_vals)
        mean_ehe = np.mean(ehe_vals)

        # Offset annotations to avoid overlap
        offsets = {
            'governed':   (12, -16),
            'ungoverned': (12, 12),
            'a1':         (-15, 10),
            'fql':        (-8, -14),
        }
        ox, oy = offsets.get(cond, (8, -4))
        disp_label = label
        if cond == 'fql':
            disp_label = 'FQL\n(2-action)'
        ax_d.annotate(disp_label,
                      xy=(mean_r, mean_ehe), fontsize=6, color=color,
                      textcoords='offset points', xytext=(ox, oy),
                      fontweight='bold',
                      arrowprops=dict(arrowstyle='-', color=color, alpha=0.4, lw=0.5))

    ax_d.set_xlabel('Demand\u2013Mead correlation (Pearson $r$)')
    ax_d.set_ylabel('Strategy diversity')
    ax_d.axvline(x=0, color='grey', ls=':', lw=0.4, alpha=0.3)
    ax_d.text(-0.12, 1.05, 'd', transform=ax_d.transAxes,
              fontsize=8, fontweight='bold', va='top')

    # Quadrant labels
    ax_d.text(0.02, 0.98, 'Arbitrary\ndiversity',
              transform=ax_d.transAxes, fontsize=6, color='gray',
              va='top', ha='left', fontstyle='italic')
    ax_d.text(0.98, 0.98, 'Adaptive\ndiversity',
              transform=ax_d.transAxes, fontsize=6, color='gray',
              va='top', ha='right', fontstyle='italic')

    # Save
    for fmt in ['png', 'pdf']:
        outpath = OUT / f"Fig2_irrigation.{fmt}"
        fig.savefig(outpath, dpi=300)
        print(f"  Saved: {outpath}")
    plt.close(fig)


if __name__ == '__main__':
    generate_figure()
    print("\nDone.")
