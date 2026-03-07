#!/usr/bin/env python3
"""
Nature Water — Figure 4: Cross-model governance effect (flood + irrigation).

Compares Governed LLM vs LLM (no validator) across:
  - Flood: 6 LLMs (Group_C vs Group_C_disabled)
  - Irrigation: Gemma-3 4B (v21 production vs ungoverned)

  (a) Paired dot plot — EHE by model
  (b) Forest plot — ΔEHE with 95% CI
  (c) Paired dot plot — IBR by model

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
    y_pos = np.arange(n)

    # Extract arrays
    gov_ehe = np.zeros(n)
    dis_ehe = np.zeros(n)
    gov_ibr = np.zeros(n)
    dis_ibr = np.zeros(n)
    gov_ibr_sd = np.zeros(n)
    dis_ibr_sd = np.zeros(n)
    delta_ehe = np.zeros(n)
    ci_lo = np.zeros(n)
    ci_hi = np.zeros(n)
    significant = np.zeros(n, dtype=bool)

    for i, (model_key, _, _) in enumerate(MODEL_CONFIG):
        d = data[model_key]
        g_ehe = [r['ehe'] for r in d['gov']]
        u_ehe = [r['ehe'] for r in d['dis']]
        g_ibr = [r['ibr'] for r in d['gov']]
        u_ibr = [r['ibr'] for r in d['dis']]

        gov_ehe[i] = np.mean(g_ehe)
        dis_ehe[i] = np.mean(u_ehe)
        gov_ibr[i] = np.mean(g_ibr)
        dis_ibr[i] = np.mean(u_ibr)
        gov_ibr_sd[i] = np.std(g_ibr, ddof=1) if len(g_ibr) > 1 else 0
        dis_ibr_sd[i] = np.std(u_ibr, ddof=1) if len(u_ibr) > 1 else 0

        # Delta EHE with paired t-test CI
        deltas = [g - u for g, u in zip(g_ehe, u_ehe)]
        delta_ehe[i] = np.mean(deltas)
        if len(deltas) >= 2:
            se = np.std(deltas, ddof=1) / np.sqrt(len(deltas))
            t_crit = stats.t.ppf(0.975, df=len(deltas) - 1)
            ci_lo[i] = delta_ehe[i] - t_crit * se
            ci_hi[i] = delta_ehe[i] + t_crit * se
            significant[i] = (ci_lo[i] > 0) or (ci_hi[i] < 0)
        else:
            ci_lo[i] = delta_ehe[i]
            ci_hi[i] = delta_ehe[i]

    # Print summary
    print("\n── Cross-Model Summary ──")
    print(f"{'Model':<16} {'Gov EHE':>8} {'Dis EHE':>8} {'ΔEHE':>8} {'CI':>16} {'Sig':>4} {'Gov IBR%':>9} {'Dis IBR%':>9}")
    for i in range(n):
        sig_str = '*' if significant[i] else ''
        print(f"{models[i]:<16} {gov_ehe[i]:>8.3f} {dis_ehe[i]:>8.3f} {delta_ehe[i]:>+8.3f} [{ci_lo[i]:>+.3f},{ci_hi[i]:>+.3f}] {sig_str:>4} {gov_ibr[i]:>8.1f} {dis_ibr[i]:>8.1f}")

    # Pooled effect (flood only)
    pooled_mean = np.mean(delta_ehe)
    pooled_se = np.std(delta_ehe, ddof=1) / np.sqrt(n)
    pooled_ci = [pooled_mean - 1.96 * pooled_se, pooled_mean + 1.96 * pooled_se]

    # ── Load irrigation ───────────────────────────────────────────────────
    print("\n--- Irrigation (Gemma-3 4B, v21) ---")
    irr = load_irrigation_metrics()
    irr_gov_ehe = np.mean([r['ehe'] for r in irr['gov']]) if irr['gov'] else np.nan
    irr_dis_ehe = np.mean([r['ehe'] for r in irr['dis']]) if irr['dis'] else np.nan
    irr_gov_ibr = np.mean([r['ibr'] for r in irr['gov']]) if irr['gov'] else np.nan
    irr_dis_ibr = np.mean([r['ibr'] for r in irr['dis']]) if irr['dis'] else np.nan
    irr_gov_ibr_sd = np.std([r['ibr'] for r in irr['gov']], ddof=1) if len(irr['gov']) > 1 else 0
    irr_dis_ibr_sd = np.std([r['ibr'] for r in irr['dis']], ddof=1) if len(irr['dis']) > 1 else 0
    has_irr = not (np.isnan(irr_gov_ehe) or np.isnan(irr_dis_ehe))

    if has_irr:
        g_ehe_irr = [r['ehe'] for r in irr['gov']]
        u_ehe_irr = [r['ehe'] for r in irr['dis']]
        # Pair by seed for delta computation (use min of available seeds)
        n_pairs = min(len(g_ehe_irr), len(u_ehe_irr))
        irr_deltas = [g_ehe_irr[i] - u_ehe_irr[i] for i in range(n_pairs)]
        irr_delta_ehe = np.mean(irr_deltas) if irr_deltas else 0
        if len(irr_deltas) >= 2:
            se = np.std(irr_deltas, ddof=1) / np.sqrt(len(irr_deltas))
            t_crit = stats.t.ppf(0.975, df=len(irr_deltas) - 1)
            irr_ci_lo = irr_delta_ehe - t_crit * se
            irr_ci_hi = irr_delta_ehe + t_crit * se
            irr_sig = (irr_ci_lo > 0) or (irr_ci_hi < 0)
        else:
            irr_ci_lo = irr_delta_ehe
            irr_ci_hi = irr_delta_ehe
            irr_sig = False
        print(f"  Governed:     {len(irr['gov'])} seeds, EHE={irr_gov_ehe:.3f}, IBR={irr_gov_ibr:.1f}%")
        print(f"  No validator: {len(irr['dis'])} seeds, EHE={irr_dis_ehe:.3f}, IBR={irr_dis_ibr:.1f}%")
        print(f"  ΔEHE={irr_delta_ehe:+.3f} [{irr_ci_lo:+.3f},{irr_ci_hi:+.3f}] {'*' if irr_sig else ''}")

    # ── Layout: flood rows + separator + irrigation row + pooled ──────────
    # y positions: 0..5 flood, gap, 7 irrigation, gap, 8.5 pooled
    y_irr = n + 1.0 if has_irr else n
    y_pooled = (y_irr + 1.3) if has_irr else (n + 0.8)

    # ── Figure ────────────────────────────────────────────────────────────────
    fig_h = 4.2 if has_irr else 3.5
    fig = plt.figure(figsize=(7.09, fig_h))
    gs = gridspec.GridSpec(1, 3, width_ratios=[1.3, 1, 1.1], wspace=0.35)

    # ── Panel (a): Paired dot plot — EHE ──────────────────────────────────
    ax_a = fig.add_subplot(gs[0])
    # Flood rows
    for i in range(n):
        ls = '-' if gov_ehe[i] >= dis_ehe[i] else '--'
        ax_a.plot([dis_ehe[i], gov_ehe[i]], [y_pos[i], y_pos[i]],
                  color=LINE_COLOR, linewidth=1.0, linestyle=ls, zorder=1)
    ax_a.scatter(dis_ehe, y_pos, c=DIS_COLOR, s=40, zorder=2,
                 edgecolors='white', linewidths=0.5, label='LLM (no validator)')
    ax_a.scatter(gov_ehe, y_pos, c=GOV_COLOR, s=40, zorder=2,
                 edgecolors='white', linewidths=0.5, label='Governed LLM')

    # Irrigation row
    if has_irr:
        ax_a.axhline(n + 0.4, color='#cccccc', linewidth=0.5, zorder=0)
        ls = '-' if irr_gov_ehe >= irr_dis_ehe else '--'
        ax_a.plot([irr_dis_ehe, irr_gov_ehe], [y_irr, y_irr],
                  color=LINE_COLOR, linewidth=1.0, linestyle=ls, zorder=1)
        ax_a.scatter(irr_dis_ehe, y_irr, c=DIS_COLOR, s=40, zorder=2,
                     edgecolors='white', linewidths=0.5, marker='D')
        ax_a.scatter(irr_gov_ehe, y_irr, c=GOV_COLOR, s=40, zorder=2,
                     edgecolors='white', linewidths=0.5, marker='D')

    all_labels = list(models) + (['Gemma-3 4B\n(irrigation)'] if has_irr else [])
    all_yticks = list(y_pos) + ([y_irr] if has_irr else [])
    ax_a.set_yticks(all_yticks)
    ax_a.set_yticklabels(all_labels)
    ax_a.set_xlabel('Behavioural\ndiversity (EHE)')
    ehe_all = list(dis_ehe) + list(gov_ehe) + ([irr_dis_ehe, irr_gov_ehe] if has_irr else [])
    ax_a.set_xlim(min(ehe_all) - 0.08, max(ehe_all) + 0.08)
    ax_a.invert_yaxis()

    # Family brackets (flood only)
    gemma_idx = [i for i, f in enumerate(families) if f == 'Gemma-3']
    minis_idx = [i for i, f in enumerate(families) if f == 'Ministral']
    bracket_x = ax_a.get_xlim()[1] - 0.01
    for idx_list, label in [(gemma_idx, 'Gemma-3'), (minis_idx, 'Ministral')]:
        y_min, y_max = min(idx_list), max(idx_list)
        ax_a.annotate('', xy=(bracket_x, y_min - 0.15), xytext=(bracket_x, y_max + 0.15),
                      arrowprops=dict(arrowstyle='-', color='#555555', lw=0.6),
                      annotation_clip=False)
        for y_end in [y_min - 0.15, y_max + 0.15]:
            ax_a.plot([bracket_x - 0.008, bracket_x], [y_end, y_end],
                      color='#555555', lw=0.6, clip_on=False)
        ax_a.text(bracket_x + 0.012, (y_min + y_max) / 2, label,
                  fontsize=6, va='center', rotation=270, color='#555555', clip_on=False)

    # Domain labels
    ax_a.text(-0.02, (y_pos[0] + y_pos[-1]) / 2, 'Flood',
              fontsize=6.5, fontweight='bold', va='center', ha='right',
              transform=ax_a.get_yaxis_transform(), color='#444444')

    ax_a.legend(loc='lower right', frameon=False, markerscale=0.8, fontsize=6)
    ax_a.text(-0.15, 1.05, 'a', transform=ax_a.transAxes,
              fontsize=9, fontweight='bold', va='top')

    # ── Panel (b): Forest plot — ΔEHE ─────────────────────────────────────
    ax_b = fig.add_subplot(gs[1])
    for i in range(n):
        color = SIG_COLOR if significant[i] else NS_COLOR
        ax_b.plot([ci_lo[i], ci_hi[i]], [y_pos[i], y_pos[i]],
                  color=color, linewidth=1.8, solid_capstyle='round', zorder=1)
        ax_b.scatter(delta_ehe[i], y_pos[i], c=color, s=40, zorder=2,
                     edgecolors='white', linewidths=0.5)
        ax_b.text(ci_hi[i] + 0.008, y_pos[i], f'{delta_ehe[i]:+.3f}',
                  fontsize=6, va='center', ha='left', color=color)

    # Irrigation row
    if has_irr:
        ax_b.axhline(n + 0.4, color='#cccccc', linewidth=0.5, zorder=0)
        irr_color = SIG_COLOR if irr_sig else NS_COLOR
        ax_b.plot([irr_ci_lo, irr_ci_hi], [y_irr, y_irr],
                  color=irr_color, linewidth=1.8, solid_capstyle='round', zorder=1)
        ax_b.scatter(irr_delta_ehe, y_irr, c=irr_color, s=40, zorder=2,
                     edgecolors='white', linewidths=0.5, marker='D')
        ax_b.text(irr_ci_hi + 0.008, y_irr, f'{irr_delta_ehe:+.3f}',
                  fontsize=6, va='center', ha='left', color=irr_color)

    # Pooled effect (flood only)
    ax_b.axhline(y_pooled - 0.5, color='#cccccc', linewidth=0.5, zorder=0)
    ax_b.plot([pooled_ci[0], pooled_ci[1]], [y_pooled, y_pooled],
              color='#222222', linewidth=1.8, solid_capstyle='round', zorder=1)
    ax_b.scatter(pooled_mean, y_pooled, marker='D', c='#222222', s=45, zorder=2,
                 edgecolors='white', linewidths=0.5)
    ax_b.text(pooled_ci[1] + 0.008, y_pooled, f'{pooled_mean:+.3f}',
              fontsize=6, va='center', ha='left', color='#222222')

    ax_b.axvline(0, color='#333333', linewidth=0.5, linestyle='--', zorder=0)
    b_yticks = list(y_pos) + ([y_irr] if has_irr else []) + [y_pooled]
    b_labels = [''] * n + ([''] if has_irr else []) + ['Flood\nmean']
    ax_b.set_yticks(b_yticks)
    ax_b.set_yticklabels(b_labels)
    ax_b.set_xlabel('\u0394 EHE\n(governed \u2212 no validator)')
    ax_b.set_ylim(-0.6, y_pooled + 0.6)
    ax_b.invert_yaxis()
    ax_b.text(-0.08, 1.05, 'b', transform=ax_b.transAxes,
              fontsize=9, fontweight='bold', va='top')

    # ── Panel (c): Paired dot plot — IBR ──────────────────────────────────
    ax_c = fig.add_subplot(gs[2])
    for i in range(n):
        ls = '-' if dis_ibr[i] >= gov_ibr[i] else '--'
        ax_c.plot([dis_ibr[i], gov_ibr[i]], [y_pos[i], y_pos[i]],
                  color=LINE_COLOR, linewidth=1.0, linestyle=ls, zorder=1)
    ax_c.errorbar(dis_ibr, y_pos, xerr=dis_ibr_sd, fmt='none',
                  ecolor=DIS_COLOR, elinewidth=0.8, capsize=3, capthick=0.6,
                  alpha=0.6, zorder=1)
    ax_c.errorbar(gov_ibr, y_pos, xerr=gov_ibr_sd, fmt='none',
                  ecolor=GOV_COLOR, elinewidth=0.8, capsize=3, capthick=0.6,
                  alpha=0.6, zorder=1)
    ax_c.scatter(dis_ibr, y_pos, c=DIS_COLOR, s=40, zorder=2,
                 edgecolors='white', linewidths=0.5)
    ax_c.scatter(gov_ibr, y_pos, c=GOV_COLOR, s=40, zorder=2,
                 edgecolors='white', linewidths=0.5)

    # Irrigation row
    if has_irr:
        ax_c.axhline(n + 0.4, color='#cccccc', linewidth=0.5, zorder=0)
        ls = '-' if irr_dis_ibr >= irr_gov_ibr else '--'
        ax_c.plot([irr_dis_ibr, irr_gov_ibr], [y_irr, y_irr],
                  color=LINE_COLOR, linewidth=1.0, linestyle=ls, zorder=1)
        ax_c.errorbar([irr_dis_ibr], [y_irr], xerr=[irr_dis_ibr_sd], fmt='none',
                      ecolor=DIS_COLOR, elinewidth=0.8, capsize=3, capthick=0.6, alpha=0.6)
        ax_c.errorbar([irr_gov_ibr], [y_irr], xerr=[irr_gov_ibr_sd], fmt='none',
                      ecolor=GOV_COLOR, elinewidth=0.8, capsize=3, capthick=0.6, alpha=0.6)
        ax_c.scatter(irr_dis_ibr, y_irr, c=DIS_COLOR, s=40, zorder=2,
                     edgecolors='white', linewidths=0.5, marker='D')
        ax_c.scatter(irr_gov_ibr, y_irr, c=GOV_COLOR, s=40, zorder=2,
                     edgecolors='white', linewidths=0.5, marker='D')

    short_names = ['3B', '4B', '8B', '12B', '14B', '27B'] + (['4B'] if has_irr else [])
    c_yticks = list(y_pos) + ([y_irr] if has_irr else [])
    ax_c.set_yticks(c_yticks)
    ax_c.set_yticklabels(short_names)
    ax_c.yaxis.tick_right()
    ax_c.set_xlabel('IBR (%)')
    ibr_max = max(list(dis_ibr) + ([irr_dis_ibr] if has_irr else []))
    ax_c.set_xlim(-0.5, ibr_max * 1.15)
    ax_c.invert_yaxis()
    ax_c.text(-0.08, 1.05, 'c', transform=ax_c.transAxes,
              fontsize=9, fontweight='bold', va='top')

    # ── Save ──────────────────────────────────────────────────────────────
    for ext in ['png', 'pdf']:
        fpath = OUT / f'Fig4_crossmodel.{ext}'
        fig.savefig(fpath, dpi=300, bbox_inches='tight', facecolor='white')
        print(f'\nSaved: {fpath}')
    plt.close(fig)


if __name__ == '__main__':
    main()
