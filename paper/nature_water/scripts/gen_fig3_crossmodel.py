#!/usr/bin/env python3
"""
Nature Water — Supplementary Figure: Cross-model governance effect (flood + irrigation).

EHE × IBR scatter plot with arrows showing governance effect per model.
Each model has two points: LLM (no validator) → Governed LLM.
Arrow direction: leftward (IBR↓) with minimal vertical shift (EHE≈).

Compares Governed LLM vs LLM (no validator) across:
  - Flood: 6 LLMs (Group_C vs Group_C_disabled)
  - Irrigation: Gemma-3 4B (v21 production vs ungoverned)

Data loaded dynamically from simulation_log.csv files.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path
from scipy import stats

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE = Path(__file__).resolve().parents[3]
SA = BASE / "examples" / "single_agent" / "results"
IRR = BASE / "examples" / "irrigation_abm" / "results"
OUT = BASE / "paper" / "nature_water" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

RUNS = [f'Run_{i}' for i in range(1, 6)]  # Run_1..Run_5; missing runs skipped at load time

# Models sorted by parameter count
MODEL_CONFIG = [
    ('gemma4_e2b',     'Gemma-4 e2b',   'Gemma-4'),
    ('ministral3_3b',  'Ministral 3B',  'Ministral'),
    ('gemma3_4b',      'Gemma-3 4B',    'Gemma-3'),
    ('gemma4_e4b',     'Gemma-4 e4b',   'Gemma-4'),
    ('ministral3_8b',  'Ministral 8B',  'Ministral'),
    ('gemma3_12b',     'Gemma-3 12B',   'Gemma-3'),
    ('ministral3_14b', 'Ministral 14B', 'Ministral'),
    ('gemma4_26b',     'Gemma-4 26B',   'Gemma-4'),
    ('gemma3_27b',     'Gemma-3 27B',   'Gemma-3'),
]

# ── Style ─────────────────────────────────────────────────────────────────────
BASE_FONT = 7.5
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica'],
    'font.size': BASE_FONT,
    'axes.labelsize': BASE_FONT,
    'axes.titlesize': BASE_FONT + 0.5,
    'xtick.labelsize': BASE_FONT - 0.5,
    'ytick.labelsize': BASE_FONT - 0.5,
    'legend.fontsize': BASE_FONT - 0.5,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'axes.spines.top': False,
    'axes.spines.right': False,
    'xtick.direction': 'out',
    'ytick.direction': 'out',
    'pdf.fonttype': 42,
    'ps.fonttype': 42,
})

GOV_COLOR   = '#0072B2'
DIS_COLOR   = '#D55E00'
SIG_COLOR   = '#0072B2'
NS_COLOR    = '#888888'
LINE_COLOR  = '#AAAAAA'


# ── Data loading ──────────────────────────────────────────────────────────────

def norm_action(d):
    d = str(d).strip().lower().replace(' ', '_')
    m = {'buy_insurance': 'buy_insurance', 'elevate_house': 'elevate_house',
         'relocate': 'relocate', 'do_nothing': 'do_nothing',
         'only_flood_insurance': 'buy_insurance', 'only_house_elevation': 'elevate_house',
         'both_flood_insurance_and_house_elevation': 'buy_insurance',
         'relocated': 'relocate', 'already_relocated': 'relocate'}
    return m.get(d, 'do_nothing')


def compute_run_metrics(df):
    """Compute EHE and IBR (excluding R5) for one run."""
    df = df[df['year'] <= 10].copy()
    if 'yearly_decision' in df.columns:
        df['action'] = df['yearly_decision'].apply(norm_action)
    elif 'decision' in df.columns:
        df['action'] = df['decision'].apply(norm_action)
    else:
        return None

    df['ta'] = df['threat_appraisal'].astype(str).str.strip().str.upper() if 'threat_appraisal' in df.columns else ''

    # EHE
    actions = ['do_nothing', 'buy_insurance', 'elevate_house', 'relocate']
    counts = df['action'].value_counts()
    total = counts.sum()
    h = sum(-(c / total) * np.log2(c / total) for a in actions if (c := counts.get(a, 0)) > 0)
    ehe = h / np.log2(4) if total > 0 else 0

    # IBR (excluding R5)
    n = len(df)
    r1 = ((df['ta'].isin(['H', 'VH'])) & (df['action'] == 'do_nothing')).sum()
    r3 = ((df['ta'].isin(['VL', 'L'])) & (df['action'] == 'relocate')).sum()
    r4 = ((df['ta'].isin(['VL', 'L'])) & (df['action'] == 'elevate_house')).sum()
    ibr = (r1 + r3 + r4) / n * 100 if n > 0 else 0

    return {'ehe': ehe, 'ibr': ibr}


def load_model_metrics(base_dir, model_key):
    """Load metrics for one model across 3 seeds."""
    results = []
    for run in RUNS:
        p = base_dir / model_key / 'Group_C' / run / 'simulation_log.csv'
        if not p.exists():
            p = base_dir / model_key / 'Group_C_disabled' / run / 'simulation_log.csv'
        if p.exists():
            df = pd.read_csv(p, encoding='utf-8-sig')
            m = compute_run_metrics(df)
            if m:
                results.append(m)
    return results


# ── Load all data ─────────────────────────────────────────────────────────────

def load_all():
    data = {}
    for model_key, model_label, family in MODEL_CONFIG:
        gov_dir = SA / 'JOH_FINAL' / model_key / 'Group_C'
        dis_dir = SA / 'JOH_ABLATION_DISABLED' / model_key / 'Group_C_disabled'

        gov_runs = []
        dis_runs = []
        for run in RUNS:
            gp = gov_dir / run / 'simulation_log.csv'
            dp = dis_dir / run / 'simulation_log.csv'
            if gp.exists():
                m = compute_run_metrics(pd.read_csv(gp, encoding='utf-8-sig'))
                if m:
                    gov_runs.append(m)
            if dp.exists():
                m = compute_run_metrics(pd.read_csv(dp, encoding='utf-8-sig'))
                if m:
                    dis_runs.append(m)

        data[model_key] = {
            'label': model_label,
            'family': family,
            'gov': gov_runs,
            'dis': dis_runs,
        }
        n_gov = len(gov_runs)
        n_dis = len(dis_runs)
        print(f"  {model_label}: {n_gov} gov, {n_dis} dis")

    return data


# ── Irrigation metrics ────────────────────────────────────────────────────────

def load_irrigation_metrics():
    """Load v21 irrigation governed/no-validator metrics."""
    result = {'gov': [], 'dis': []}
    for cond, prefix in [('gov', 'production_v21_42yr_seed'),
                          ('dis', 'ungoverned_v21_42yr_seed')]:
        for seed in [42, 43, 44, 45, 46]:
            p = IRR / f"{prefix}{seed}" / "simulation_log.csv"
            if not p.exists():
                continue
            df = pd.read_csv(p, encoding='utf-8')
            if len(df) < 3000:  # incomplete run
                continue
            # EHE (k=5 irrigation actions)
            counts = df['yearly_decision'].value_counts()
            probs = counts / counts.sum()
            H = sum(-p * np.log2(p) for p in probs if p > 0)
            ehe = H / np.log2(5)
            # IBR: high-WSA increase rate
            high_wsa = df[df['wsa_label'].isin(['H', 'VH'])]
            if len(high_wsa) > 0:
                ibr = high_wsa['yearly_decision'].isin(
                    ['increase_large', 'increase_small']
                ).sum() / len(high_wsa) * 100  # percentage
            else:
                ibr = 0.0
            result[cond].append({'seed': seed, 'ehe': ehe, 'ibr': ibr})
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Loading data...")
    data = load_all()

    n = len(MODEL_CONFIG)
    models = [mc[1] for mc in MODEL_CONFIG]
    families = [mc[2] for mc in MODEL_CONFIG]

    # Extract arrays
    gov_ehe = np.zeros(n)
    dis_ehe = np.zeros(n)
    gov_ibr = np.zeros(n)
    dis_ibr = np.zeros(n)

    for i, (model_key, _, _) in enumerate(MODEL_CONFIG):
        d = data[model_key]
        gov_ehe[i] = np.mean([r['ehe'] for r in d['gov']])
        dis_ehe[i] = np.mean([r['ehe'] for r in d['dis']])
        gov_ibr[i] = np.mean([r['ibr'] for r in d['gov']])
        dis_ibr[i] = np.mean([r['ibr'] for r in d['dis']])

    # Print summary
    print("\n── Cross-Model Summary ──")
    print(f"{'Model':<16} {'Gov EHE':>8} {'Dis EHE':>8} {'Gov IBR%':>9} {'Dis IBR%':>9}")
    for i in range(n):
        print(f"{models[i]:<16} {gov_ehe[i]:>8.3f} {dis_ehe[i]:>8.3f} {gov_ibr[i]:>8.1f} {dis_ibr[i]:>8.1f}")

    # ── Load irrigation ───────────────────────────────────────────────────
    print("\n--- Irrigation (Gemma-3 4B, v21) ---")
    irr = load_irrigation_metrics()
    irr_gov_ehe = np.mean([r['ehe'] for r in irr['gov']]) if irr['gov'] else np.nan
    irr_dis_ehe = np.mean([r['ehe'] for r in irr['dis']]) if irr['dis'] else np.nan
    irr_gov_ibr = np.mean([r['ibr'] for r in irr['gov']]) if irr['gov'] else np.nan
    irr_dis_ibr = np.mean([r['ibr'] for r in irr['dis']]) if irr['dis'] else np.nan
    has_irr = not (np.isnan(irr_gov_ehe) or np.isnan(irr_dis_ehe))

    if has_irr:
        print(f"  Governed:     EHE={irr_gov_ehe:.3f}, IBR={irr_gov_ibr:.1f}%")
        print(f"  No validator: EHE={irr_dis_ehe:.3f}, IBR={irr_dis_ibr:.1f}%")

    # ── Figure: broken-axis EHE × IBR scatter ──────────────────────────────
    # Left panel: flood-model cluster (IBR 0-10%)
    # Right panel: irrigation (IBR 35-45%)
    # Broken x-axis with "//" cut marks visually separates the two regimes
    # so flood-model labels do not collide and irrigation is not stranded in
    # the middle of a mostly-empty plot.
    fig, (ax_flood, ax_irr) = plt.subplots(
        1, 2, figsize=(6.0, 3.8),
        gridspec_kw={'width_ratios': [3.0, 1.6], 'wspace': 0.08},
        sharey=True,
    )

    # Marker styles per family
    FAMILY_MARKER = {'Gemma-3': 'o', 'Ministral': 's', 'Gemma-4': '^'}
    FAMILY_SIZE = {'Gemma-3': 55, 'Ministral': 55, 'Gemma-4': 60}

    # ---- Left panel: flood cross-model cluster ----
    for ax in (ax_flood,):
        # Arrows: no-validator → governed
        for i in range(n):
            ax.annotate('', xy=(gov_ibr[i], gov_ehe[i]),
                        xytext=(dis_ibr[i], dis_ehe[i]),
                        arrowprops=dict(arrowstyle='->', color='#888888',
                                        lw=0.8, shrinkA=3, shrinkB=3))
        # No-validator points (orange)
        for i in range(n):
            mk = FAMILY_MARKER[families[i]]
            ax.scatter(dis_ibr[i], dis_ehe[i], c=DIS_COLOR,
                       s=FAMILY_SIZE[families[i]], marker=mk,
                       edgecolors='white', linewidths=0.6, zorder=3)
        # Governed points (blue)
        for i in range(n):
            mk = FAMILY_MARKER[families[i]]
            ax.scatter(gov_ibr[i], gov_ehe[i], c=GOV_COLOR,
                       s=FAMILY_SIZE[families[i]], marker=mk,
                       edgecolors='white', linewidths=0.6, zorder=3)

    # Model labels with manual offsets to disambiguate the upper-left cluster
    PARAM_LABELS = [label for _, label, _ in MODEL_CONFIG]
    PARAM_LABELS = [lbl.split()[-1] if len(lbl) < 14 else lbl for lbl in PARAM_LABELS]

    # Offset table tuned to spread overlapping labels. Offsets in (dx, dy)
    # points; keys must match PARAM_LABELS values.
    LABEL_OFFSET = {
        '4B':  (7,  4),
        '3B':  (7, -8),
        '8B':  (7,  0),
        '12B': (7, -8),
        '14B': (7,  8),
        '27B': (7,  0),
        'e2b': (7,  6),
        'e4b': (7, -2),
        '26B': (7, -6),
    }
    for i in range(n):
        lbl = PARAM_LABELS[i]
        dx, dy = LABEL_OFFSET.get(lbl, (6, -2))
        ax_flood.annotate(lbl, (gov_ibr[i], gov_ehe[i]),
                          textcoords='offset points', xytext=(dx, dy),
                          fontsize=6, color='#333333', va='center',
                          fontweight='bold' if lbl in ('e2b', 'e4b', '26B') else 'normal')

    # ---- Right panel: irrigation ----
    if has_irr:
        ax_irr.annotate('', xy=(irr_gov_ibr, irr_gov_ehe),
                        xytext=(irr_dis_ibr, irr_dis_ehe),
                        arrowprops=dict(arrowstyle='->', color='#888888',
                                        lw=0.8, shrinkA=3, shrinkB=3))
        ax_irr.scatter(irr_dis_ibr, irr_dis_ehe, c=DIS_COLOR, s=70,
                       marker='D', edgecolors='white', linewidths=0.6, zorder=3)
        ax_irr.scatter(irr_gov_ibr, irr_gov_ehe, c=GOV_COLOR, s=70,
                       marker='D', edgecolors='white', linewidths=0.6, zorder=3)
        ax_irr.annotate('Gemma-3 4B', (irr_gov_ibr, irr_gov_ehe),
                        textcoords='offset points', xytext=(-30, -12),
                        fontsize=6, color='#333333', va='top',
                        fontstyle='italic')

    # ── Broken-axis visual cue ────────────────────────────────────────────
    # Hide inner spines so the break is obvious
    ax_flood.spines['right'].set_visible(False)
    ax_irr.spines['left'].set_visible(False)
    ax_irr.tick_params(axis='y', which='both', left=False, labelleft=False)

    # Diagonal // break markers at the seam. Using figure-relative coords
    # so the marker aspect ratio is correct regardless of subplot width.
    d_x, d_y = 0.006, 0.015
    kwargs = dict(transform=ax_flood.transAxes, color='k', clip_on=False, lw=0.8)
    # Left panel right edge: top and bottom corners
    ax_flood.plot((1 - d_x, 1 + d_x), (-d_y, +d_y), **kwargs)
    ax_flood.plot((1 - d_x, 1 + d_x), (1 - d_y, 1 + d_y), **kwargs)
    # Right panel left edge: top and bottom corners
    kwargs.update(transform=ax_irr.transAxes)
    ax_irr.plot((-d_x * 1.5, +d_x * 1.5), (-d_y, +d_y), **kwargs)
    ax_irr.plot((-d_x * 1.5, +d_x * 1.5), (1 - d_y, 1 + d_y), **kwargs)

    # Axis labels
    ax_flood.set_ylabel('Behavioural diversity (EHE)')
    fig.text(0.5, -0.01, 'Irrational behaviour rate, IBR (%)',
             ha='center', va='bottom', fontsize=BASE_FONT)

    # Axis limits — right panel now covers irrigation's full range
    # (governed 38.2, no-validator 61.1 with headroom)
    ax_flood.set_xlim(-0.6, 10.0)
    if has_irr:
        ax_irr.set_xlim(34, 66)
    all_ehe = list(dis_ehe) + list(gov_ehe) + ([irr_dis_ehe, irr_gov_ehe] if has_irr else [])
    ax_flood.set_ylim(min(all_ehe) - 0.05, max(all_ehe) + 0.06)

    # X-ticks
    ax_flood.set_xticks([0, 2, 4, 6, 8, 10])
    if has_irr:
        ax_irr.set_xticks([38, 50, 61])

    # ── Legend in a two-block layout: colour (condition) + shape (family) ──
    # Colour legend (condition)
    cond_handles = [
        plt.scatter([], [], c=GOV_COLOR, s=40, marker='o',
                    edgecolors='white', linewidths=0.6,
                    label='Governed LLM'),
        plt.scatter([], [], c=DIS_COLOR, s=40, marker='o',
                    edgecolors='white', linewidths=0.6,
                    label='LLM (no validator)'),
    ]
    shape_handles = [
        plt.scatter([], [], c='#888888', s=40, marker='o',
                    edgecolors='white', linewidths=0.6, label='Gemma-3 (flood)'),
        plt.scatter([], [], c='#888888', s=40, marker='^',
                    edgecolors='white', linewidths=0.6, label='Gemma-4 (flood)'),
        plt.scatter([], [], c='#888888', s=40, marker='s',
                    edgecolors='white', linewidths=0.6, label='Ministral (flood)'),
        plt.scatter([], [], c='#888888', s=40, marker='D',
                    edgecolors='white', linewidths=0.6, label='Irrigation'),
    ]

    # Stack both legends ABOVE the plot area: condition (colour) on the
    # top row, family/domain (shape) directly below it. Separating the two
    # legends keeps the colour-vs-shape semantics unambiguous without the
    # overlap that occurred when they shared the same y band.
    leg_cond = fig.legend(
        handles=cond_handles, loc='upper left',
        bbox_to_anchor=(0.10, 0.99),
        title='Condition (colour)', title_fontsize=6.5,
        frameon=True, framealpha=0.9, edgecolor='#cccccc',
        fontsize=6, markerscale=0.8, borderpad=0.3,
        ncol=2, columnspacing=0.8,
    )
    fig.legend(
        handles=shape_handles, loc='upper left',
        bbox_to_anchor=(0.45, 0.99),
        title='Family / domain (shape)', title_fontsize=6.5,
        frameon=True, framealpha=0.9, edgecolor='#cccccc',
        fontsize=6, markerscale=0.8, borderpad=0.3,
        ncol=4, columnspacing=0.6,
    )

    plt.subplots_adjust(bottom=0.14, top=0.82)

    # ── Save ──────────────────────────────────────────────────────────────
    for ext in ['png', 'pdf']:
        fpath = OUT / f'SFig_crossmodel_ehe_ibr.{ext}'
        fig.savefig(fpath, dpi=300, bbox_inches='tight', facecolor='white')
        print(f'\nSaved: {fpath}')
    plt.close(fig)


if __name__ == '__main__':
    main()
