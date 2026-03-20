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
    ('ministral3_3b',  'Ministral 3B',  'Ministral'),
    ('gemma3_4b',      'Gemma-3 4B',    'Gemma-3'),
    ('ministral3_8b',  'Ministral 8B',  'Ministral'),
    ('gemma3_12b',     'Gemma-3 12B',   'Gemma-3'),
    ('ministral3_14b', 'Ministral 14B', 'Ministral'),
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

    # ── Figure: EHE × IBR scatter with arrows ─────────────────────────────
    fig, ax = plt.subplots(figsize=(4.5, 3.8))

    # Marker styles per family
    FAMILY_MARKER = {'Gemma-3': 'o', 'Ministral': 's'}
    FAMILY_SIZE = {'Gemma-3': 55, 'Ministral': 55}

    # Draw arrows: no-validator → governed (orange → blue)
    for i in range(n):
        dx = gov_ibr[i] - dis_ibr[i]
        dy = gov_ehe[i] - dis_ehe[i]
        ax.annotate('', xy=(gov_ibr[i], gov_ehe[i]),
                    xytext=(dis_ibr[i], dis_ehe[i]),
                    arrowprops=dict(arrowstyle='->', color='#666666',
                                    lw=1.0, shrinkA=4, shrinkB=4))

    # Plot no-validator points (orange)
    for i in range(n):
        mk = FAMILY_MARKER[families[i]]
        ax.scatter(dis_ibr[i], dis_ehe[i], c=DIS_COLOR, s=FAMILY_SIZE[families[i]],
                   marker=mk, edgecolors='white', linewidths=0.6, zorder=3)

    # Plot governed points (blue)
    for i in range(n):
        mk = FAMILY_MARKER[families[i]]
        ax.scatter(gov_ibr[i], gov_ehe[i], c=GOV_COLOR, s=FAMILY_SIZE[families[i]],
                   marker=mk, edgecolors='white', linewidths=0.6, zorder=3)

    # Model labels (offset from governed point)
    PARAM_LABELS = ['3B', '4B', '8B', '12B', '14B', '27B']
    for i in range(n):
        ax.annotate(PARAM_LABELS[i], (gov_ibr[i], gov_ehe[i]),
                    textcoords='offset points', xytext=(6, -2),
                    fontsize=6, color='#444444', va='center')

    # Irrigation point (diamond markers)
    if has_irr:
        ax.annotate('', xy=(irr_gov_ibr, irr_gov_ehe),
                    xytext=(irr_dis_ibr, irr_dis_ehe),
                    arrowprops=dict(arrowstyle='->', color='#666666',
                                    lw=1.0, shrinkA=4, shrinkB=4))
        ax.scatter(irr_dis_ibr, irr_dis_ehe, c=DIS_COLOR, s=70,
                   marker='D', edgecolors='white', linewidths=0.6, zorder=3)
        ax.scatter(irr_gov_ibr, irr_gov_ehe, c=GOV_COLOR, s=70,
                   marker='D', edgecolors='white', linewidths=0.6, zorder=3)
        ax.annotate('Irrigation\n(Gemma-3 4B)', (irr_gov_ibr, irr_gov_ehe),
                    textcoords='offset points', xytext=(8, -6),
                    fontsize=6, color='#444444', va='top',
                    fontstyle='italic')

    # Legend entries
    ax.scatter([], [], c=GOV_COLOR, s=40, marker='o', edgecolors='white',
               linewidths=0.6, label='Governed LLM')
    ax.scatter([], [], c=DIS_COLOR, s=40, marker='o', edgecolors='white',
               linewidths=0.6, label='LLM (no validator)')
    ax.scatter([], [], c='#888888', s=40, marker='o', edgecolors='white',
               linewidths=0.6, label='Gemma-3 (flood)')
    ax.scatter([], [], c='#888888', s=40, marker='s', edgecolors='white',
               linewidths=0.6, label='Ministral (flood)')
    ax.scatter([], [], c='#888888', s=40, marker='D', edgecolors='white',
               linewidths=0.6, label='Irrigation')

    ax.legend(loc='upper right', frameon=True, framealpha=0.9,
              edgecolor='#cccccc', fontsize=6, markerscale=0.8)

    ax.set_xlabel('Irrational behaviour rate, IBR (%)')
    ax.set_ylabel('Behavioural diversity (EHE)')

    # Axis limits with padding
    all_ibr = list(dis_ibr) + list(gov_ibr) + ([irr_dis_ibr, irr_gov_ibr] if has_irr else [])
    all_ehe = list(dis_ehe) + list(gov_ehe) + ([irr_dis_ehe, irr_gov_ehe] if has_irr else [])
    ax.set_xlim(min(all_ibr) - 0.8, max(all_ibr) * 1.12)
    ax.set_ylim(min(all_ehe) - 0.05, max(all_ehe) + 0.06)

    plt.tight_layout()

    # ── Save ──────────────────────────────────────────────────────────────
    for ext in ['png', 'pdf']:
        fpath = OUT / f'SFig_crossmodel_ehe_ibr.{ext}'
        fig.savefig(fpath, dpi=300, bbox_inches='tight', facecolor='white')
        print(f'\nSaved: {fpath}')
    plt.close(fig)


if __name__ == '__main__':
    main()
