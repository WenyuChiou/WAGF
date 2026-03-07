#!/usr/bin/env python3
"""
CS Professor Meeting Demo — 3-condition flood comparison figure.

Layout (8 × 6 in):
  Top row:  3 stacked-bar sub-panels (year 1-10, 5 protection states)
            WRR version (Group_A) | Governed LLM (Group_B) | LLM no validator (Group_C_disabled)
  Bottom row: EHE line plot (3 conditions overlaid)

Data sources:
  - WRR version    : JOH_FINAL/gemma3_4b/Group_A/Run_{1,2,3}/simulation_log.csv
  - Governed LLM   : JOH_FINAL/gemma3_4b/Group_B/Run_{1,2,3}/simulation_log.csv  (preferred)
                      or JOH_FINAL/gemma3_4b/Group_C/Run_{1,2,3}/simulation_log.csv (fallback)
  - LLM no validator: JOH_ABLATION_DISABLED/gemma3_4b/Group_C_disabled/Run_{1,2,3}/simulation_log.csv

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

# ── Paths ──────────────────────────────────────────────────────────────────────
REPO = Path(__file__).resolve().parents[3]
SA_RESULTS = REPO / "examples" / "single_agent" / "results"

GROUP_A_DIR  = SA_RESULTS / "JOH_FINAL" / "gemma3_4b" / "Group_A"
GROUP_B_DIR  = SA_RESULTS / "JOH_FINAL" / "gemma3_4b" / "Group_B"
GROUP_C_DIR  = SA_RESULTS / "JOH_FINAL" / "gemma3_4b" / "Group_C"      # fallback for gov
DISABLED_DIR = SA_RESULTS / "JOH_ABLATION_DISABLED" / "gemma3_4b" / "Group_C_disabled"

OUT_DIR = REPO / "paper" / "nature_water" / "professor_briefing"
OUT_DIR.mkdir(parents=True, exist_ok=True)

RUNS = ['Run_1', 'Run_2', 'Run_3']

# ── Style ──────────────────────────────────────────────────────────────────────
BASE_FONT = 8.5
plt.rcParams.update({
    'font.family':        'sans-serif',
    'font.sans-serif':    ['Arial', 'Helvetica'],
    'font.size':          BASE_FONT,
    'axes.labelsize':     BASE_FONT,
    'axes.titlesize':     BASE_FONT + 1,
    'xtick.labelsize':    BASE_FONT - 0.5,
    'ytick.labelsize':    BASE_FONT - 0.5,
    'legend.fontsize':    BASE_FONT - 0.5,
    'figure.dpi':         200,
    'savefig.dpi':        200,
    'savefig.bbox':       'tight',
    'axes.spines.top':    False,
    'axes.spines.right':  False,
    'pdf.fonttype':       42,
    'ps.fonttype':        42,
})

# ── Protection state definitions ───────────────────────────────────────────────
PROT_STATES = [
    'No protection',
    'Insurance only',
    'Elevation only',
    'Insurance + Elevation',
    'Relocated',
]

PROT_COLORS = {
    'No protection':         '#0072B2',
    'Insurance only':        '#E69F00',
    'Elevation only':        '#009E73',
    'Insurance + Elevation': '#D55E00',
    'Relocated':             '#CC79A7',
}

PROT_ABBREV = {
    'No protection':         'DN',
    'Insurance only':        'FI',
    'Elevation only':        'HE',
    'Insurance + Elevation': 'FI+HE',
    'Relocated':             'RL',
}

# Map raw cumulative_state / decision strings to canonical PROT_STATES
_STATE_MAP = {
    'Do Nothing':                            'No protection',
    'Only Flood Insurance':                  'Insurance only',
    'Only House Elevation':                  'Elevation only',
    'Both Flood Insurance and House Elevation': 'Insurance + Elevation',
    'Relocate':                              'Relocated',
    'Already relocated':                     'Relocated',
}

# ── Condition colours ──────────────────────────────────────────────────────────
GOV_COLOR   = '#0072B2'
UNGOV_COLOR = '#D55E00'
WRR_COLOR   = '#666666'

# ── EHE constants ─────────────────────────────────────────────────────────────
FLOOD_ACTIONS_EHE = ['do_nothing', 'buy_insurance', 'elevate_house', 'relocate']
LOG2_K = np.log2(4)
FLOOD_YEARS = [3, 4, 9]


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _as_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series.fillna(False)
    s = series.astype(str).str.strip().str.lower()
    return s.isin({'true', '1', '1.0', 'yes'})


def _classify_state_from_cols(row) -> str:
    relocated     = _as_bool(pd.Series([row['relocated']]))[0]
    has_insurance = _as_bool(pd.Series([row['has_insurance']]))[0]
    elevated      = _as_bool(pd.Series([row['elevated']]))[0]
    if relocated:
        return 'Relocated'
    if has_insurance and elevated:
        return 'Insurance + Elevation'
    if elevated:
        return 'Elevation only'
    if has_insurance:
        return 'Insurance only'
    return 'No protection'


def _map_state_col(raw_series: pd.Series) -> pd.Series:
    return raw_series.map(_STATE_MAP).fillna('No protection')


def _normalise_decision(dec: str) -> str:
    d = str(dec).strip().lower().replace(' ', '_')
    mapping = {
        'do_nothing': 'do_nothing',
        'buy_insurance': 'buy_insurance',
        'only_flood_insurance': 'buy_insurance',
        'elevate_house': 'elevate_house',
        'only_house_elevation': 'elevate_house',
        'relocate': 'relocate',
        'relocated': 'relocate',
        'already_relocated': 'relocate',
        'both_flood_insurance_and_house_elevation': 'buy_insurance',
    }
    return mapping.get(d, 'do_nothing')


def _ehe_from_decisions(decisions: pd.Series) -> float:
    d = decisions.copy().str.strip().str.lower()
    d = d.replace({'relocate': 'relocate', 'relocated': 'relocate',
                   'buy_insurance': 'buy_insurance',
                   'only_flood_insurance': 'buy_insurance',
                   'elevate_house': 'elevate_house',
                   'only_house_elevation': 'elevate_house'})
    canonical = ['do_nothing', 'buy_insurance', 'elevate_house', 'relocate']
    counts = d.value_counts()
    total = counts.sum()
    if total == 0:
        return 0.0
    h = 0.0
    for act in canonical:
        c = counts.get(act, 0)
        if c > 0:
            p = c / total
            h -= p * np.log2(p)
    return h / LOG2_K


# ══════════════════════════════════════════════════════════════════════════════
# Data loading
# ══════════════════════════════════════════════════════════════════════════════

def _load_group_a_run(run: str) -> pd.DataFrame:
    """Load one Group_A (WRR) run. Uses 'decision' column for state mapping."""
    path = GROUP_A_DIR / run / "simulation_log.csv"
    if not path.exists():
        print(f"  WARNING: Missing {path}")
        return pd.DataFrame()
    df = pd.read_csv(path, encoding='utf-8-sig')
    if 'year' in df.columns:
        df = df[df['year'] <= 10].copy()

    # Map decision column to protection state
    if 'decision' in df.columns:
        df['prot_state'] = _map_state_col(df['decision'])
    else:
        df['prot_state'] = df.apply(_classify_state_from_cols, axis=1)

    # Derive yearly_decision for EHE from boolean state flags (Group_A has prose TA)
    def _wrr_action(row):
        rel = _as_bool(pd.Series([row['relocated']]))[0]
        ins = _as_bool(pd.Series([row['has_insurance']]))[0]
        elv = _as_bool(pd.Series([row['elevated']]))[0]
        if rel:
            return 'relocate'
        if elv and ins:
            return 'buy_insurance'
        if elv:
            return 'elevate_house'
        if ins:
            return 'buy_insurance'
        return 'do_nothing'

    df['yearly_decision'] = df.apply(_wrr_action, axis=1)
    print(f"  Group_A {run}: {len(df)} rows loaded")
    return df


def _load_llm_run_from_traces(base_dir: Path, run: str, max_year: int = 10) -> pd.DataFrame:
    """Fallback loader from household_traces.jsonl."""
    jsonl_path = base_dir / run / "raw" / "household_traces.jsonl"
    if not jsonl_path.exists():
        print(f"  WARNING: Missing {jsonl_path}")
        return pd.DataFrame()

    rows = []
    with open(jsonl_path, encoding='utf-8') as fh:
        for line in fh:
            t = json.loads(line)
            year = t.get('year', 0)
            if year > max_year:
                continue
            ap = t.get('approved_skill', {})
            action = ap.get('skill_name', 'do_nothing') if isinstance(ap, dict) else 'do_nothing'
            sa = t.get('state_after', t.get('state_before', {}))
            rows.append({
                'year': year,
                'agent_id': t.get('agent_id', ''),
                'yearly_decision': action,
                'elevated': sa.get('elevated', False),
                'has_insurance': sa.get('has_insurance', False),
                'relocated': sa.get('relocated', False),
            })

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df['prot_state'] = df.apply(_classify_state_from_cols, axis=1)
    print(f"  Loaded {len(df)} traces from {jsonl_path.name}")
    return df


def _load_llm_run(base_dir: Path, run: str) -> pd.DataFrame:
    """Load one LLM run. Prefers simulation_log.csv; falls back to traces."""
    path = base_dir / run / "simulation_log.csv"
    if not path.exists():
        return _load_llm_run_from_traces(base_dir, run, max_year=10)

    df = pd.read_csv(path, encoding='utf-8-sig')
    if 'year' in df.columns:
        df = df[df['year'] <= 10].copy()

    if 'cumulative_state' in df.columns:
        df['prot_state'] = _map_state_col(df['cumulative_state'])
    elif 'decision' in df.columns:
        df['prot_state'] = _map_state_col(df['decision'])
    else:
        df['prot_state'] = df.apply(_classify_state_from_cols, axis=1)

    if 'yearly_decision' not in df.columns:
        if 'decision' in df.columns:
            df['yearly_decision'] = df['decision'].str.lower().str.replace(' ', '_')
        else:
            df['yearly_decision'] = 'do_nothing'

    print(f"  {base_dir.name} {run}: {len(df)} rows loaded")
    return df


def load_all_runs() -> dict:
    """Return dict: 'wrr', 'gov', 'disabled' → list of DataFrames."""
    data = {'wrr': [], 'gov': [], 'disabled': []}

    # Determine governed directory (prefer Group_B, fallback Group_C)
    gov_dir = GROUP_B_DIR if GROUP_B_DIR.exists() else GROUP_C_DIR
    print(f"  Using governed dir: {gov_dir.name}")

    for run in RUNS:
        # WRR (Group_A)
        df_a = _load_group_a_run(run)
        if not df_a.empty:
            data['wrr'].append(df_a)

        # Governed LLM
        df_g = _load_llm_run(gov_dir, run)
        if not df_g.empty:
            data['gov'].append(df_g)

        # Disabled (no validator)
        df_d = _load_llm_run(DISABLED_DIR, run)
        if not df_d.empty:
            data['disabled'].append(df_d)

    for k, v in data.items():
        print(f"  {k}: {len(v)} runs loaded")
    return data


# ══════════════════════════════════════════════════════════════════════════════
# Stacked bars
# ══════════════════════════════════════════════════════════════════════════════

def _compute_prot_counts_per_year(dfs: list) -> tuple:
    per_run = []
    for df in dfs:
        if df.empty:
            continue
        relocated_year = (
            df[df['prot_state'] == 'Relocated']
            .groupby('agent_id')['year'].min()
        )
        keep_mask = pd.Series(True, index=df.index)
        for agent_id, rel_yr in relocated_year.items():
            drop = (df['agent_id'] == agent_id) & (df['year'] > rel_yr)
            keep_mask[drop] = False
        df_filtered = df[keep_mask]

        grp = (df_filtered.groupby(['year', 'prot_state']).size()
                 .unstack(fill_value=0))
        for s in PROT_STATES:
            if s not in grp.columns:
                grp[s] = 0
        grp = grp[PROT_STATES]
        per_run.append(grp)

    if not per_run:
        return pd.DataFrame(), pd.DataFrame()

    stacked = pd.concat(per_run, axis=0)
    mean_c = stacked.groupby(level=0).mean()
    std_c  = stacked.groupby(level=0).std(ddof=0).fillna(0.0)
    return mean_c, std_c


def draw_stacked_bars(axes, data: dict):
    sub_configs = [
        ('wrr',      'Traditional ABM',   WRR_COLOR),
        ('gov',      'Governed LLM\n(Group B)',   GOV_COLOR),
        ('disabled', 'LLM (no validator)\n(Group C disabled)', UNGOV_COLOR),
    ]

    for col_idx, (cond, sub_label, cond_color) in enumerate(sub_configs):
        ax = axes[col_idx]
        mean_c, std_c = _compute_prot_counts_per_year(data[cond])

        if mean_c.empty:
            ax.text(0.5, 0.5, 'No data', transform=ax.transAxes,
                    ha='center', va='center', fontsize=8, color='#999999')
            ax.set_title(sub_label, fontweight='bold', fontsize=BASE_FONT, pad=3)
            continue

        years = mean_c.index.values
        x     = np.arange(len(years))
        bar_w = 0.75
        bottom = np.zeros(len(years))

        for state in PROT_STATES:
            vals = mean_c[state].values
            ax.bar(x, vals, bottom=bottom, width=bar_w,
                   color=PROT_COLORS[state], edgecolor='white',
                   linewidth=0.4, label=state, zorder=2)
            bottom += vals

        ax.set_title(sub_label, fontweight='bold', fontsize=BASE_FONT, pad=3)
        ax.set_xticks(x[::2])
        ax.set_xticklabels(years[::2])
        ax.set_xlim(-0.5, len(years) - 0.5)
        ax.set_xlabel('Simulation year')

        if col_idx == 0:
            ax.set_ylabel('Population count')
        else:
            ax.tick_params(labelleft=False)

        ax.set_ylim(0, 105)
        ax.yaxis.set_major_locator(ticker.MultipleLocator(20))

    # Legend
    handles_leg = [
        mpatches.Patch(facecolor=PROT_COLORS[s], edgecolor='white',
                       linewidth=0.4, label=PROT_ABBREV[s])
        for s in PROT_STATES
    ]
    axes[1].legend(
        handles=handles_leg, loc='lower right',
        fontsize=BASE_FONT - 1, frameon=True, framealpha=0.9,
        facecolor='white', edgecolor='#CCCCCC',
        handlelength=0.6, handletextpad=0.2,
        labelspacing=0.1, columnspacing=0.5,
        borderpad=0.2, ncol=2,
    )


# ══════════════════════════════════════════════════════════════════════════════
# EHE line plot
# ══════════════════════════════════════════════════════════════════════════════

def _compute_yearly_ehe(dfs: list) -> tuple:
    if not dfs:
        return np.arange(1, 11), np.zeros(10), np.zeros(10)

    per_run = []
    for df in dfs:
        yearly_ehe = []
        for y in range(1, 11):
            yr = df[df['year'] == y]
            if len(yr) == 0:
                yearly_ehe.append(0.0)
                continue
            if 'yearly_decision' in yr.columns:
                dec = yr['yearly_decision']
            elif 'action' in yr.columns:
                dec = yr['action']
            else:
                yearly_ehe.append(0.0)
                continue
            yearly_ehe.append(_ehe_from_decisions(dec))
        per_run.append(yearly_ehe)

    arr = np.array(per_run)
    years = np.arange(1, 11)
    means = arr.mean(axis=0)
    stds = arr.std(axis=0) if arr.shape[0] > 1 else np.zeros(10)
    return years, means, stds


def draw_ehe_panel(ax, data: dict):
    conditions = [
        ('wrr',      'Traditional ABM',   WRR_COLOR,   '--', '^'),
        ('gov',      'Governed LLM (Group B)',   GOV_COLOR,    '-', 'o'),
        ('disabled', 'LLM no validator (C_dis)', UNGOV_COLOR,  '-', 's'),
    ]

    for cond_key, label, color, ls, marker in conditions:
        years, means, stds = _compute_yearly_ehe(data[cond_key])

        # Individual run traces
        if len(data[cond_key]) > 1:
            for df in data[cond_key]:
                _, run_m, _ = _compute_yearly_ehe([df])
                ax.plot(years, run_m, color=color, alpha=0.15, lw=0.5, zorder=1)

        ax.plot(years, means, color=color, ls=ls, lw=1.5, marker=marker,
                markersize=4, zorder=3, label=label)

        if stds.max() > 0:
            ax.fill_between(years, means - stds, means + stds,
                            color=color, alpha=0.12, zorder=1)

    # Flood markers
    for fy in FLOOD_YEARS:
        ax.axvline(fy, color='#AAAAAA', ls=':', lw=0.6, alpha=0.6, zorder=0)
        ax.text(fy, 1.03, 'F', fontsize=6, color='#888888', ha='center', va='bottom')

    ax.set_xlim(0.5, 10.5)
    ax.set_xticks(range(1, 11))
    ax.set_xlabel('Simulation year')
    ax.set_ylabel('Behavioural entropy (EHE)')
    ax.set_ylim(0, 1.1)
    ax.yaxis.set_major_locator(ticker.MultipleLocator(0.2))
    ax.legend(fontsize=BASE_FONT - 1, frameon=False,
              loc='lower left', handlelength=1.2)


# ══════════════════════════════════════════════════════════════════════════════
# Summary statistics
# ══════════════════════════════════════════════════════════════════════════════

def print_summary(data: dict):
    print("\n=== Protection State Summary ===")
    for cond_name, cond_key in [('Traditional ABM', 'wrr'),
                                 ('Governed LLM', 'gov'),
                                 ('LLM (no validator)', 'disabled')]:
        all_df = pd.concat(data[cond_key], ignore_index=True) if data[cond_key] else pd.DataFrame()
        if all_df.empty:
            print(f"  {cond_name}: No data.")
            continue
        total = len(all_df)
        print(f"\n  {cond_name} (n={total}):")
        for state in PROT_STATES:
            n = (all_df['prot_state'] == state).sum()
            print(f"    {state:>25s}: {n:>5d} ({n/total*100:.1f}%)")

    print("\n=== Overall EHE ===")
    for cond_name, cond_key in [('Traditional ABM', 'wrr'),
                                 ('Governed LLM', 'gov'),
                                 ('LLM (no validator)', 'disabled')]:
        ehe_vals = []
        for run_df in data[cond_key]:
            if run_df.empty:
                continue
            col = 'yearly_decision' if 'yearly_decision' in run_df.columns else 'decision'
            ehe_vals.append(_ehe_from_decisions(run_df[col]))
        vals = np.array(ehe_vals) if ehe_vals else np.array([0.0])
        print(f"  {cond_name}: mean EHE={vals.mean():.3f} (sd={vals.std():.3f})")


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def generate_figure():
    print("Loading data...")
    data = load_all_runs()

    fig = plt.figure(figsize=(9, 6))

    gs = gridspec.GridSpec(
        2, 3,
        height_ratios=[1.2, 1.0],
        left=0.08, right=0.96,
        top=0.93, bottom=0.08,
        hspace=0.38, wspace=0.25,
    )

    # Row 1: 3 stacked-bar sub-panels
    ax_a1 = fig.add_subplot(gs[0, 0])
    ax_a2 = fig.add_subplot(gs[0, 1], sharey=ax_a1)
    ax_a3 = fig.add_subplot(gs[0, 2], sharey=ax_a1)
    draw_stacked_bars([ax_a1, ax_a2, ax_a3], data)

    # Row 2: EHE line plot spanning all 3 columns
    ax_ehe = fig.add_subplot(gs[1, :])
    draw_ehe_panel(ax_ehe, data)

    # Panel labels
    fig.text(0.02, 0.95, 'a', fontsize=12, fontweight='bold')
    fig.text(0.02, 0.48, 'b', fontsize=12, fontweight='bold')

    # Title
    fig.suptitle('3-Condition Flood Comparison: Traditional ABM vs Governed LLM',
                 fontsize=10, fontweight='bold', y=0.99)

    # Save
    out_path = OUT_DIR / "fig3a_demo_3conditions.png"
    fig.savefig(out_path, dpi=200, bbox_inches='tight', facecolor='white')
    print(f"\nSaved: {out_path}")

    plt.close(fig)
    print_summary(data)


if __name__ == '__main__':
    generate_figure()
