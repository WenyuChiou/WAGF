#!/usr/bin/env python3
"""
CS Professor Meeting Demo — 3-condition: Rule-based PMT | WRR (Group_A) | WAGF (Group_C)

Same structure as gen_fig3_case2_flood.py but middle panel = Group_A (WRR) instead of
Group_C_disabled (no validator).

Layout (9 × 6):
  Top: 3 stacked-bar sub-panels (year 1-10, 5 protection states)
  Bottom: EHE line plot (3 conditions)

Data sources:
  - Rule-based PMT : results/rulebased/Run_{1,2,3}/simulation_log.csv
  - WRR (Group_A)  : results/JOH_FINAL/gemma3_4b/Group_A/Run_{1,2,3}/simulation_log.csv
  - WAGF (Group_C) : results/JOH_FINAL/gemma3_4b/Group_C/Run_{1,2,3}/simulation_log.csv

Output: paper/nature_water/professor_briefing/fig3a_demo_3conditions.png
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import warnings
warnings.filterwarnings('ignore')

from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
import matplotlib.ticker as ticker

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO = Path(__file__).resolve().parents[3]
SA_RESULTS = REPO / "examples" / "single_agent" / "results"

RULEBASED_DIR = SA_RESULTS / "rulebased"
WRR_DIR       = SA_RESULTS / "JOH_FINAL" / "gemma3_4b" / "Group_A"
WAGF_DIR      = SA_RESULTS / "JOH_FINAL" / "gemma3_4b" / "Group_C"

OUT_DIR = REPO / "paper" / "nature_water" / "professor_briefing"
OUT_DIR.mkdir(parents=True, exist_ok=True)
RUNS = ['Run_1', 'Run_2', 'Run_3']

# ── Style ─────────────────────────────────────────────────────────────────────
BASE_FONT = 8.5
plt.rcParams.update({
    'font.family': 'sans-serif', 'font.sans-serif': ['Arial'],
    'font.size': BASE_FONT, 'axes.labelsize': BASE_FONT,
    'axes.titlesize': BASE_FONT + 1, 'xtick.labelsize': BASE_FONT - 0.5,
    'ytick.labelsize': BASE_FONT - 0.5, 'legend.fontsize': BASE_FONT - 0.5,
    'figure.dpi': 200, 'savefig.dpi': 200, 'savefig.bbox': 'tight',
    'axes.spines.top': False, 'axes.spines.right': False,
    'pdf.fonttype': 42, 'ps.fonttype': 42,
})

PROT_STATES = ['No protection', 'Insurance only', 'Elevation only',
               'Insurance + Elevation', 'Relocated']
PROT_COLORS = {
    'No protection': '#0072B2', 'Insurance only': '#E69F00',
    'Elevation only': '#009E73', 'Insurance + Elevation': '#D55E00',
    'Relocated': '#CC79A7',
}
PROT_ABBREV = {
    'No protection': 'DN', 'Insurance only': 'FI',
    'Elevation only': 'HE', 'Insurance + Elevation': 'FI+HE',
    'Relocated': 'RL',
}

_STATE_MAP = {
    'Do Nothing': 'No protection',
    'Only Flood Insurance': 'Insurance only',
    'Only House Elevation': 'Elevation only',
    'Both Flood Insurance and House Elevation': 'Insurance + Elevation',
    'Relocate': 'Relocated', 'Already relocated': 'Relocated',
}

COND_COLORS = {'rulebased': '#666666', 'wrr': '#D55E00', 'wagf': '#0072B2'}
FLOOD_YEARS = [3, 4, 9]
LOG2_K = np.log2(4)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _as_bool(s):
    if s.dtype == bool: return s.fillna(False)
    return s.astype(str).str.strip().str.lower().isin({'true', '1', '1.0', 'yes'})

def _classify(row):
    rel = _as_bool(pd.Series([row['relocated']]))[0]
    ins = _as_bool(pd.Series([row['has_insurance']]))[0]
    elv = _as_bool(pd.Series([row['elevated']]))[0]
    if rel: return 'Relocated'
    if ins and elv: return 'Insurance + Elevation'
    if elv: return 'Elevation only'
    if ins: return 'Insurance only'
    return 'No protection'


def _load_rulebased_run(run):
    """Rule-based PMT: results/rulebased/Run_X/simulation_log.csv"""
    path = RULEBASED_DIR / run / "simulation_log.csv"
    if not path.exists():
        print(f"  MISSING: {path}")
        return pd.DataFrame()
    df = pd.read_csv(path, encoding='utf-8-sig')
    df = df[df['year'] <= 10].copy()
    # Rule-based has boolean columns
    df['prot_state'] = df.apply(_classify, axis=1)
    # Derive yearly_decision from boolean state
    def _rb_action(row):
        if _as_bool(pd.Series([row['relocated']]))[0]: return 'relocate'
        if _as_bool(pd.Series([row['elevated']]))[0]: return 'elevate_house'
        if _as_bool(pd.Series([row['has_insurance']]))[0]: return 'buy_insurance'
        return 'do_nothing'
    df['yearly_decision'] = df.apply(_rb_action, axis=1)
    print(f"  rulebased/{run}: {len(df)} rows")
    return df


def _load_wrr_run(run):
    """WRR Group_A: has 'decision' column with full-text, prose TA/CA."""
    path = WRR_DIR / run / "simulation_log.csv"
    if not path.exists():
        print(f"  MISSING: {path}")
        return pd.DataFrame()
    df = pd.read_csv(path, encoding='utf-8-sig')
    df = df[df['year'] <= 10].copy()
    # Map decision column
    if 'decision' in df.columns:
        df['prot_state'] = df['decision'].map(_STATE_MAP).fillna('No protection')
    else:
        df['prot_state'] = df.apply(_classify, axis=1)
    # Derive yearly_decision from boolean columns (Group_A TA is prose, not categorical)
    def _wrr_action(row):
        if _as_bool(pd.Series([row['relocated']]))[0]: return 'relocate'
        if _as_bool(pd.Series([row['elevated']]))[0]: return 'elevate_house'
        if _as_bool(pd.Series([row['has_insurance']]))[0]: return 'buy_insurance'
        return 'do_nothing'
    df['yearly_decision'] = df.apply(_wrr_action, axis=1)
    print(f"  WRR(Group_A)/{run}: {len(df)} rows")
    return df


def _load_wagf_run(run):
    """WAGF Group_C: has cumulative_state, yearly_decision, structured TA/CA."""
    path = WAGF_DIR / run / "simulation_log.csv"
    if not path.exists():
        print(f"  MISSING: {path}")
        return pd.DataFrame()
    df = pd.read_csv(path, encoding='utf-8-sig')
    df = df[df['year'] <= 10].copy()
    if 'cumulative_state' in df.columns:
        df['prot_state'] = df['cumulative_state'].map(_STATE_MAP).fillna('No protection')
    else:
        df['prot_state'] = df.apply(_classify, axis=1)
    if 'yearly_decision' not in df.columns:
        df['yearly_decision'] = 'do_nothing'
    # Normalize
    norm = {
        'do_nothing': 'do_nothing', 'buy_insurance': 'buy_insurance',
        'elevate_house': 'elevate_house', 'relocate': 'relocate',
    }
    df['yearly_decision'] = df['yearly_decision'].map(norm).fillna('do_nothing')
    print(f"  WAGF(Group_C)/{run}: {len(df)} rows")
    return df


def load_all():
    data = {'rulebased': [], 'wrr': [], 'wagf': []}
    for run in RUNS:
        df_rb = _load_rulebased_run(run)
        if not df_rb.empty: data['rulebased'].append(df_rb)
        df_wrr = _load_wrr_run(run)
        if not df_wrr.empty: data['wrr'].append(df_wrr)
        df_wagf = _load_wagf_run(run)
        if not df_wagf.empty: data['wagf'].append(df_wagf)
    for k, v in data.items():
        print(f"  {k}: {len(v)} runs")
    return data


# ── Stacked bars ──────────────────────────────────────────────────────────────

def _prot_counts(dfs):
    per_run = []
    for df in dfs:
        if df.empty: continue
        rel_yr = df[df['prot_state'] == 'Relocated'].groupby('agent_id')['year'].min()
        mask = pd.Series(True, index=df.index)
        for aid, ry in rel_yr.items():
            mask[(df['agent_id'] == aid) & (df['year'] > ry)] = False
        grp = df[mask].groupby(['year', 'prot_state']).size().unstack(fill_value=0)
        for s in PROT_STATES:
            if s not in grp.columns: grp[s] = 0
        per_run.append(grp[PROT_STATES])
    if not per_run:
        return pd.DataFrame(), pd.DataFrame()
    stacked = pd.concat(per_run)
    return stacked.groupby(level=0).mean(), stacked.groupby(level=0).std(ddof=0).fillna(0)

def draw_bars(axes, data):
    configs = [
        ('rulebased', 'Traditional ABM'),
        ('wrr',       'LLM agent (WRR)'),
        ('wagf',      'Governed LLM (WAGF)'),
    ]
    for i, (key, label) in enumerate(configs):
        ax = axes[i]
        mean_c, _ = _prot_counts(data[key])
        if mean_c.empty:
            ax.text(0.5, 0.5, 'No data', transform=ax.transAxes, ha='center', fontsize=8, color='#999')
            ax.set_title(label, fontweight='bold', fontsize=BASE_FONT, pad=3)
            continue
        years = mean_c.index.values
        x = np.arange(len(years))
        bottom = np.zeros(len(years))
        for state in PROT_STATES:
            vals = mean_c[state].values
            ax.bar(x, vals, bottom=bottom, width=0.75, color=PROT_COLORS[state],
                   edgecolor='white', linewidth=0.4, label=state, zorder=2)
            bottom += vals
        # Flood year shading
        for fy in FLOOD_YEARS:
            if fy in years:
                fx = np.where(years == fy)[0][0]
                ax.axvspan(fx - 0.4, fx + 0.4, color='#D32F2F', alpha=0.08, zorder=0)
                ax.text(fx, 103, 'F', fontsize=6, color='#D32F2F', ha='center',
                        fontweight='bold', va='bottom')

        ax.set_title(label, fontweight='bold', fontsize=BASE_FONT, pad=8)
        ax.set_xticks(x[::2]); ax.set_xticklabels(years[::2])
        ax.set_xlim(-0.5, len(years) - 0.5)
        ax.set_xlabel('Simulation year')
        if i == 0: ax.set_ylabel('Population count')
        else: ax.tick_params(labelleft=False)
        ax.set_ylim(0, 110); ax.yaxis.set_major_locator(ticker.MultipleLocator(20))

    handles = [mpatches.Patch(facecolor=PROT_COLORS[s], edgecolor='white',
               linewidth=0.4, label=s) for s in PROT_STATES]
    axes[1].legend(handles=handles, loc='lower right', fontsize=BASE_FONT - 1,
                   frameon=True, framealpha=0.9, facecolor='white', edgecolor='#CCC',
                   handlelength=0.8, handletextpad=0.3, labelspacing=0.15,
                   columnspacing=0.6, borderpad=0.3, ncol=2)


# ── EHE ───────────────────────────────────────────────────────────────────────

def _ehe(decisions):
    canonical = ['do_nothing', 'buy_insurance', 'elevate_house', 'relocate']
    counts = decisions.value_counts()
    total = counts.sum()
    if total == 0: return 0.0
    h = 0.0
    for a in canonical:
        c = counts.get(a, 0)
        if c > 0:
            p = c / total
            h -= p * np.log2(p)
    return h / LOG2_K

def _yearly_ehe(dfs):
    if not dfs:
        return np.arange(1, 11), np.zeros(10), np.zeros(10)
    per_run = []
    for df in dfs:
        vals = [_ehe(df[df['year'] == y]['yearly_decision']) for y in range(1, 11)]
        per_run.append(vals)
    arr = np.array(per_run)
    return np.arange(1, 11), arr.mean(0), arr.std(0) if arr.shape[0] > 1 else np.zeros(10)

def draw_ehe(ax, data):
    configs = [
        ('rulebased', 'Traditional ABM',       COND_COLORS['rulebased'], '--', '^'),
        ('wrr',       'LLM agent (WRR)',        COND_COLORS['wrr'],       '-.', 's'),
        ('wagf',      'Governed LLM (WAGF)',    COND_COLORS['wagf'],      '-',  'o'),
    ]
    for key, label, color, ls, marker in configs:
        years, means, stds = _yearly_ehe(data[key])
        if len(data[key]) > 1:
            for df in data[key]:
                _, rm, _ = _yearly_ehe([df])
                ax.plot(years, rm, color=color, alpha=0.15, lw=0.5, zorder=1)
        ax.plot(years, means, color=color, ls=ls, lw=1.5, marker=marker,
                markersize=4, zorder=3, label=label)
        if stds.max() > 0:
            ax.fill_between(years, means - stds, means + stds, color=color, alpha=0.12)

    for fy in FLOOD_YEARS:
        ax.axvline(fy, color='#AAA', ls=':', lw=0.6, alpha=0.6)
        ax.text(fy, 1.03, 'F', fontsize=6, color='#888', ha='center')

    ax.set_xlim(0.5, 10.5); ax.set_xticks(range(1, 11))
    ax.set_xlabel('Simulation year'); ax.set_ylabel('Behavioural entropy (EHE)')
    ax.set_ylim(0, 1.1); ax.yaxis.set_major_locator(ticker.MultipleLocator(0.2))
    ax.legend(fontsize=BASE_FONT - 1, frameon=False, loc='lower left', handlelength=1.2)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Loading data...")
    data = load_all()

    fig = plt.figure(figsize=(9, 3.5))
    gs = gridspec.GridSpec(1, 3,
                           left=0.08, right=0.96, top=0.88, bottom=0.12,
                           wspace=0.25)

    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1], sharey=ax1)
    ax3 = fig.add_subplot(gs[0, 2], sharey=ax1)
    draw_bars([ax1, ax2, ax3], data)

    # No main title

    out = OUT_DIR / "fig3a_demo_3conditions.png"
    fig.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    print(f"\nSaved: {out}")
    plt.close(fig)

    # Summary
    print("\n=== Summary ===")
    for name, key in [('Traditional ABM', 'rulebased'), ('LLM agent (WRR)', 'wrr'), ('Governed LLM (WAGF)', 'wagf')]:
        all_df = pd.concat(data[key], ignore_index=True) if data[key] else pd.DataFrame()
        if all_df.empty: continue
        n = len(all_df)
        print(f"\n  {name} (n={n}):")
        for s in PROT_STATES:
            c = (all_df['prot_state'] == s).sum()
            print(f"    {s:>25s}: {c:>5d} ({c/n*100:.1f}%)")
        ehe_vals = [_ehe(df['yearly_decision']) for df in data[key]]
        print(f"    Overall EHE: {np.mean(ehe_vals):.3f}")

if __name__ == '__main__':
    main()
