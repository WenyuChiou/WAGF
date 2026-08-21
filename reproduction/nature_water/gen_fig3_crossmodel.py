#!/usr/bin/env python3
"""
Nature Water — Supplementary Figure: Cross-model governance effect (flood + irrigation).

EHE × IBR scatter plot with arrows showing governance effect per model.
Each model has two points: Governed LLM (no validator) → Governed LLM.
Arrow direction: leftward (IBR↓) with minimal vertical shift (EHE≈).

Compares Governed LLM vs Governed LLM (no validator) across:
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
BASE = Path(__file__).resolve().parents[2]  # reproduction/nature_water/<file> -> repo root
SA = BASE / "examples" / "single_agent" / "results"
IRR = BASE / "examples" / "irrigation_abm" / "results"
OUT = BASE / "paper" / "nature_water" / "figures"
# The output directory is created at save time, not on import: these modules are
# imported by tests/test_nature_water_figure_helpers.py for their pure helper
# functions, and an import should not write to the filesystem.

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

import glob
sys.path.insert(0, str(BASE / "examples" / "single_agent" / "analysis"))
from compute_flood_metrics import process_llm_csv


def _flood_run_dirs(model_key, governed):
    """Run dirs, preferring the _v2 prompt-regime dataset (Gemma-4 models live
    in _v2; the rest in the base dirs), matching the cross-model table script."""
    roots = (['JOH_FINAL_v2', 'JOH_FINAL'] if governed
             else ['JOH_ABLATION_DISABLED_v2', 'JOH_ABLATION_DISABLED'])
    grp = 'Group_C' if governed else 'Group_C_disabled'
    for root in roots:
        rs = sorted(glob.glob(str(SA / root / model_key / grp / 'Run_*')))
        if rs:
            return rs
    return []


def flood_run_metrics(rundir):
    """Per-run EHE and conditional appraisal-action inconsistency for one flood
    run, computed exactly as in gen_tableS1_S6_crossmodel_unified.py:
      EXECUTED action = simulation_log yearly_decision (relocated-state rows
      dropped); threat label = audit reason_tp_label; denominator restricted to
      threat-relevant (non-medium) appraisals; numerator = R1 (high-threat
      do_nothing) + R3 (low-threat relocate) + R4 (low-threat elevate_house).
      EHE from process_llm_csv (the same routine the tables use)."""
    sl = pd.read_csv(rundir + '/simulation_log.csv', encoding='utf-8-sig')
    au = pd.read_csv(rundir + '/household_governance_audit.csv', encoding='utf-8-sig')
    m = sl.merge(au[['agent_id', 'year', 'reason_tp_label']],
                 on=['agent_id', 'year'], how='left')
    m = m[m['yearly_decision'].astype(str).str.lower() != 'relocated']
    ta = m['reason_tp_label'].astype(str).str.upper()
    dec = m['yearly_decision'].astype(str).str.lower()
    r1 = ((ta.isin(['H', 'VH'])) & (dec == 'do_nothing')).sum()
    r3 = ((ta.isin(['VL', 'L'])) & (dec == 'relocate')).sum()
    r4 = ((ta.isin(['VL', 'L'])) & (dec == 'elevate_house')).sum()
    den = int((ta.isin(['H', 'VH', 'VL', 'L'])).sum())
    if den == 0:
        return None
    aai = 100.0 * float(r1 + r3 + r4) / den
    ehe = process_llm_csv(rundir + '/simulation_log.csv')[0]
    return {'ehe': ehe, 'ibr': aai}


def load_all():
    data = {}
    for model_key, model_label, family in MODEL_CONFIG:
        gov_runs = [mm for r in _flood_run_dirs(model_key, True)
                    if (mm := flood_run_metrics(r)) is not None]
        dis_runs = [mm for r in _flood_run_dirs(model_key, False)
                    if (mm := flood_run_metrics(r)) is not None]
        data[model_key] = {'label': model_label, 'family': family,
                           'gov': gov_runs, 'dis': dis_runs}
        print(f"  {model_label}: {len(gov_runs)} gov, {len(dis_runs)} dis")
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
    fig.text(0.5, -0.01, 'Appraisal-action inconsistency (%)',
             ha='center', va='bottom', fontsize=BASE_FONT)

    # Axis limits — right panel now covers irrigation's full range
    # (governed 38.2, no-validator 61.1 with headroom)
    ax_flood.set_xlim(-0.6, 16.0)
    if has_irr:
        ax_irr.set_xlim(34, 66)
    all_ehe = list(dis_ehe) + list(gov_ehe) + ([irr_dis_ehe, irr_gov_ehe] if has_irr else [])
    ax_flood.set_ylim(min(all_ehe) - 0.05, max(all_ehe) + 0.06)

    # X-ticks
    ax_flood.set_xticks([0, 4, 8, 12, 16])
    if has_irr:
        ax_irr.set_xticks([36, 48, 60])

    # ── Legend in a two-block layout: colour (condition) + shape (family) ──
    # Colour legend (condition)
    cond_handles = [
        plt.scatter([], [], c=GOV_COLOR, s=40, marker='o',
                    edgecolors='white', linewidths=0.6,
                    label='Governed LLM'),
        plt.scatter([], [], c=DIS_COLOR, s=40, marker='o',
                    edgecolors='white', linewidths=0.6,
                    label='Governed LLM (no validator)'),
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
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ['png', 'pdf']:
        fpath = OUT / f'SFig_crossmodel_ehe_ibr.{ext}'
        fig.savefig(fpath, dpi=300, bbox_inches='tight', facecolor='white')
        print(f'\nSaved: {fpath}')
    plt.close(fig)


if __name__ == '__main__':
    main()
