#!/usr/bin/env python3
"""
Nature Water — Figure 3 (flood case study): 3-panel figure.

Layout (7.09 × 7.0 in, full Nature Water width):
  Top row:   (a) Cumulative protection state evolution — 3 side-by-side stacked
                 bar sub-panels: Rule-based | LLM (no validation) | Governed LLM
  Bottom row: (b) Initial vs final protection state comparison (grouped bars)
              (c) TA×CA pie matrices: LLM (no validation) vs Governed LLM

Data sources:
  - Rule-based PMT : examples/single_agent/results/rulebased/Run_{1,2,3}/simulation_log.csv
  - LLM (no validation): examples/single_agent/results/JOH_ABLATION_DISABLED/gemma3_4b/Group_C_disabled/Run_{1,2,3}/simulation_log.csv
  - Governed LLM   : examples/single_agent/results/JOH_FINAL/gemma3_4b/Group_C/Run_{1,2,3}/simulation_log.csv

Output: paper/nature_water/figures/Fig3_flood_case.{png,pdf}
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import warnings
warnings.filterwarnings('ignore')

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
import matplotlib.ticker as ticker
import matplotlib.colors as mcolors
from matplotlib.colorbar import ColorbarBase

# ── Paths ──────────────────────────────────────────────────────────────────────
REPO = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework")
SA_RESULTS = REPO / "examples" / "single_agent" / "results"

RULEBASED_DIR  = SA_RESULTS / "rulebased"
DISABLED_DIR   = SA_RESULTS / "JOH_ABLATION_DISABLED" / "gemma3_4b" / "Group_C_disabled"
GOV_DIR        = SA_RESULTS / "JOH_FINAL" / "gemma3_4b" / "Group_C"

OUT_DIR = REPO / "paper" / "nature_water" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Style ──────────────────────────────────────────────────────────────────────
BASE_FONT = 7.5
plt.rcParams.update({
    'font.family':        'sans-serif',
    'font.sans-serif':    ['Arial', 'Helvetica'],
    'font.size':          BASE_FONT,
    'axes.labelsize':     BASE_FONT,
    'axes.titlesize':     BASE_FONT + 0.5,
    'xtick.labelsize':    BASE_FONT - 0.5,
    'ytick.labelsize':    BASE_FONT - 0.5,
    'legend.fontsize':    BASE_FONT + 0.5,
    'figure.dpi':         300,
    'savefig.dpi':        300,
    'savefig.bbox':       'tight',
    'axes.spines.top':    False,
    'axes.spines.right':  False,
    'xtick.direction':    'out',
    'ytick.direction':    'out',
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
    'No protection':         '#0072B2',   # blue (matching reference)
    'Insurance only':        '#E69F00',   # amber/orange
    'Elevation only':        '#009E73',   # green
    'Insurance + Elevation': '#D55E00',   # vermillion/red
    'Relocated':             '#CC79A7',   # purple
}

PROT_HATCHES = {
    'No protection':         '',
    'Insurance only':        '///',
    'Elevation only':        '...',
    'Insurance + Elevation': 'xxx',
    'Relocated':             '\\\\\\',
}

# Abbreviations for compact legends/labels (full names in caption)
PROT_ABBREV = {
    'No protection':         'DN',
    'Insurance only':        'FI',
    'Elevation only':        'HE',
    'Insurance + Elevation': 'FI+HE',
    'Relocated':             'RL',
}

# Map from raw cumulative_state / decision strings to canonical PROT_STATES
_STATE_MAP = {
    'Do Nothing':                            'No protection',
    'Only Flood Insurance':                  'Insurance only',
    'Only House Elevation':                  'Elevation only',
    'Both Flood Insurance and House Elevation': 'Insurance + Elevation',
    'Relocate':                              'Relocated',
    'Already relocated':                     'Relocated',
}

# ── Appraisal level ordering ───────────────────────────────────────────────────
LEVEL_ORDER = ['VL', 'L', 'M', 'H', 'VH']

# ── Condition colours ──────────────────────────────────────────────────────────
GOV_COLOR   = '#0072B2'
UNGOV_COLOR = '#D55E00'
PMT_COLOR   = '#666666'

# ── EHE: flood actions (k = 4) ─────────────────────────────────────────────────
FLOOD_ACTIONS_EHE = ['do_nothing', 'buy_insurance', 'elevate_house', 'relocate']
# Normalisation constant: log2(4)
LOG2_K = np.log2(4)

RUNS = ['Run_1', 'Run_2', 'Run_3']


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _as_bool(series: pd.Series) -> pd.Series:
    """Convert various boolean representations to Python bool.

    Handles: True/False (native bool), 1/0 (int), 'true'/'false' (str),
    NaN → False.
    """
    if series.dtype == bool:
        return series.fillna(False)
    s = series.astype(str).str.strip().str.lower()
    return s.isin({'true', '1', '1.0', 'yes'})


def _classify_state_from_cols(row) -> str:
    """Derive canonical protection state from boolean columns."""
    relocated    = _as_bool(pd.Series([row['relocated']]))[0]
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
    """Map raw cumulative_state / decision strings to canonical PROT_STATES."""
    return raw_series.map(_STATE_MAP).fillna('No protection')


def _ehe_from_decisions(decisions: pd.Series) -> float:
    """Compute normalised Shannon entropy (EHE) from a flat array of decisions.

    Maps relocate/relocated variants, then computes entropy over FLOOD_ACTIONS_EHE.
    EHE = H / log2(k),  H = -Σ p log2 p.
    """
    # Normalise variant spellings
    d = decisions.copy().str.strip().str.lower()
    d = d.replace({'relocate': 'relocate', 'relocated': 'relocate',
                   'buy_insurance': 'buy_insurance',
                   'only_flood_insurance': 'buy_insurance',
                   'elevate_house': 'elevate_house',
                   'only_house_elevation': 'elevate_house'})
    # Use the 4 canonical actions
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

def _load_rulebased_run(run: str) -> pd.DataFrame:
    """Load one rulebased run; derive protection state from boolean columns."""
    path = RULEBASED_DIR / run / "simulation_log.csv"
    if not path.exists():
        print(f"  WARNING: Missing {path}")
        return pd.DataFrame()
    df = pd.read_csv(path, encoding='utf-8-sig')

    # Derive canonical prot_state from elevated / has_insurance / relocated
    df['prot_state'] = df.apply(_classify_state_from_cols, axis=1)

    # Derive yearly_decision for EHE from decision column (cumulative state proxy)
    # Rule-based stores per-year cumulative decision in 'decision'; derive action
    # from the transition (or map directly as best approximation)
    # The 'decision' column in rulebased represents the current cumulative state,
    # not the yearly action. We approximate EHE from the boolean state flags:
    # map Elevate→elevate_house, Insurance→buy_insurance, Both→buy_insurance,
    # Relocate→relocate, Do Nothing→do_nothing  (conservative proxy)
    def _rulebased_action(row):
        rel = _as_bool(pd.Series([row['relocated']]))[0]
        ins = _as_bool(pd.Series([row['has_insurance']]))[0]
        elv = _as_bool(pd.Series([row['elevated']]))[0]
        if rel:
            return 'relocate'
        if elv and ins:
            return 'buy_insurance'   # both — count as insurance (dominant)
        if elv:
            return 'elevate_house'
        if ins:
            return 'buy_insurance'
        return 'do_nothing'

    df['yearly_decision'] = df.apply(_rulebased_action, axis=1)
    return df


def _load_llm_run_grouped(base_dir: Path, run: str) -> pd.DataFrame:
    """Load one LLM run (Group_A or Group_B)."""
    path = base_dir / run / "simulation_log.csv"
    if not path.exists():
        print(f"  WARNING: Missing {path}")
        return pd.DataFrame()
    df = pd.read_csv(path, encoding='utf-8-sig')

    # Determine which column holds the cumulative state label
    if 'cumulative_state' in df.columns:
        df['prot_state'] = _map_state_col(df['cumulative_state'])
    elif 'decision' in df.columns:
        df['prot_state'] = _map_state_col(df['decision'])
    else:
        # Fallback: derive from boolean columns
        df['prot_state'] = df.apply(_classify_state_from_cols, axis=1)

    # Ensure yearly_decision exists for EHE
    if 'yearly_decision' not in df.columns:
        if 'decision' in df.columns:
            df['yearly_decision'] = df['decision'].str.lower().str.replace(' ', '_')
        else:
            df['yearly_decision'] = 'do_nothing'

    return df


def load_all_runs() -> dict:
    """Return dict with keys 'rulebased', 'disabled', 'gov'; each is list of DFs."""
    data = {'rulebased': [], 'disabled': [], 'gov': []}
    for run in RUNS:
        rb = _load_rulebased_run(run)
        if not rb.empty:
            data['rulebased'].append(rb)

        dis = _load_llm_run_grouped(DISABLED_DIR, run)
        if not dis.empty:
            data['disabled'].append(dis)

        gv = _load_llm_run_grouped(GOV_DIR, run)
        if not gv.empty:
            data['gov'].append(gv)

    for k, v in data.items():
        print(f"  {k}: {len(v)} runs loaded")
    return data


# ══════════════════════════════════════════════════════════════════════════════
# Panel (a): Stacked bar — protection state shares per year
# ══════════════════════════════════════════════════════════════════════════════

def _compute_prot_counts_per_year(dfs: list) -> tuple:
    """Return (mean_counts_df, std_counts_df) averaged across runs.

    mean_counts_df: index=year, columns=PROT_STATES, values = agent count.
    std_counts_df:  same shape.

    Relocated agents are excluded from subsequent years' counts:
    once an agent relocates, they are removed from all future year counts.
    The relocation year itself still shows the agent as 'Relocated'.
    """
    per_run = []
    for df in dfs:
        if df.empty:
            continue

        # Identify relocation year per agent: first year they appear as Relocated
        relocated_year = (
            df[df['prot_state'] == 'Relocated']
            .groupby('agent_id')['year']
            .min()
        )

        # Exclude agent-years AFTER relocation (keep the relocation year itself)
        keep_mask = pd.Series(True, index=df.index)
        for agent_id, rel_yr in relocated_year.items():
            drop = (df['agent_id'] == agent_id) & (df['year'] > rel_yr)
            keep_mask[drop] = False
        df_filtered = df[keep_mask]

        # Count per (year, prot_state) — absolute counts
        grp = (df_filtered.groupby(['year', 'prot_state']).size()
                 .unstack(fill_value=0))
        # Ensure all states present
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


def draw_panel_a(axes, data: dict):
    """Draw panel (a): 3 stacked bar sub-panels on provided axes.

    Y-axis = absolute agent count (decreasing as agents relocate).
    """
    sub_configs = [
        ('rulebased', 'Rule-based',            PMT_COLOR),
        ('disabled',  'LLM (no validation)',   UNGOV_COLOR),
        ('gov',       'Governed LLM',          GOV_COLOR),
    ]

    count_data = {}
    for cond, _, _ in sub_configs:
        mean_c, std_c = _compute_prot_counts_per_year(data[cond])
        count_data[cond] = (mean_c, std_c)

    for col_idx, (cond, sub_label, cond_color) in enumerate(sub_configs):
        ax = axes[col_idx]

        mean_c, std_c = count_data[cond]
        if mean_c.empty:
            ax.text(0.5, 0.5, 'No data', transform=ax.transAxes,
                    ha='center', va='center', fontsize=7, color='#999999')
            continue

        years = mean_c.index.values
        x     = np.arange(len(years))
        bar_w = 0.75
        bottom = np.zeros(len(years))

        for state in PROT_STATES:
            vals = mean_c[state].values

            bars = ax.bar(x, vals, bottom=bottom,
                          width=bar_w,
                          color=PROT_COLORS[state],
                          edgecolor='white',
                          linewidth=0.4,
                          label=state,
                          zorder=2)

            bottom += vals

        # Sub-panel title (bold, top center — matching Fig 2a style)
        ax.set_title(sub_label, fontweight='bold', fontsize=BASE_FONT, pad=3)

        # X axis
        ax.set_xticks(x[::2])
        ax.set_xticklabels(years[::2], fontsize=BASE_FONT - 1.0)
        ax.set_xlim(-0.5, len(years) - 0.5)
        ax.set_xlabel('Simulation year', fontsize=BASE_FONT - 0.5)

        if col_idx == 0:
            ax.set_ylabel('Population count', fontsize=BASE_FONT - 0.5)
        else:
            ax.tick_params(labelleft=False)

        ax.set_ylim(0, 105)
        ax.yaxis.set_major_locator(ticker.MultipleLocator(20))

    # Legend inside Ungoverned panel (axes[1]) — abbreviated, compact
    handles_leg = [
        mpatches.Patch(facecolor=PROT_COLORS[s], edgecolor='white',
                       linewidth=0.4, label=PROT_ABBREV[s])
        for s in PROT_STATES
    ]
    axes[1].legend(
        handles=handles_leg,
        loc='lower right',
        fontsize=BASE_FONT - 1,
        frameon=True, framealpha=0.9,
        facecolor='white', edgecolor='#CCCCCC',
        handlelength=0.6,
        handletextpad=0.2,
        labelspacing=0.1,
        columnspacing=0.5,
        borderpad=0.2,
        ncol=2,
    )

    # Panel label 'a' — added in generate_figure() for alignment

    return axes


# ══════════════════════════════════════════════════════════════════════════════
# Panel (c): Counterfactual governance violation rate (IBR)
# ══════════════════════════════════════════════════════════════════════════════

def _load_flood_gov_combined() -> pd.DataFrame:
    """Load and combine all 3 governed runs for pie matrix."""
    frames = []
    for run in RUNS:
        path = GOV_DIR / run / "simulation_log.csv"
        if not path.exists():
            print(f"  WARNING: Missing {path}")
            continue
        df = pd.read_csv(path, encoding='utf-8-sig')
        df['run'] = run
        frames.append(df)

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)

    # Canonical prot_state
    if 'cumulative_state' in df.columns:
        df['prot_state'] = _map_state_col(df['cumulative_state'])
    elif 'decision' in df.columns:
        df['prot_state'] = _map_state_col(df['decision'])
    else:
        df['prot_state'] = df.apply(_classify_state_from_cols, axis=1)

    # TA column
    df['ta_bin'] = df['threat_appraisal'].astype(str).str.strip()

    # CA column — try multiple names
    ca_col = None
    for col_name in ['coping_appraisal', 'coping_appraisal_label', 'construct_CP_LABEL']:
        if col_name in df.columns:
            ca_col = col_name
            break
    if ca_col is None:
        print("  WARNING: No coping appraisal column found. Columns available:")
        suspect = [c for c in df.columns
                   if any(kw in c.lower()
                          for kw in ['cop', 'ca', 'apprais', 'coping'])]
        print(f"    {suspect}")
        df['ca_bin'] = 'M'  # graceful fallback
    else:
        df['ca_bin'] = df[ca_col].astype(str).str.strip()

    df = df[df['ta_bin'].isin(LEVEL_ORDER)]
    df = df[df['ca_bin'].isin(LEVEL_ORDER)]
    df = df.dropna(subset=['ta_bin', 'ca_bin', 'prot_state'])

    # Normalise yearly_decision to canonical flood actions
    if 'yearly_decision' in df.columns:
        df['action'] = df['yearly_decision'].apply(_normalise_decision)
    else:
        df['action'] = 'do_nothing'

    return df


def _compute_ibr(dfs: list, dec_col: str) -> dict:
    """Compute counterfactual governance violation rate per rule.

    Applies all 5 governance rules from the 'strict' profile to the
    ungoverned data. Returns dict with per-rule violation counts and total n.

    Rules:
      R1 (extreme_threat_block): TP=H/VH + do_nothing         [ERROR]
      R3 (relocation_threat_low): TP=VL/L + relocate           [ERROR]
      R4 (elevation_threat_low): TP=VL/L + elevate_house       [ERROR]
      R5 (elevation_block): prev_year elevated + elevate_house  [ERROR]
    """
    per_run = []
    for df in dfs:
        df = df.copy()
        df['action'] = df[dec_col].apply(_normalise_decision)
        df['ta'] = df['threat_appraisal'].astype(str).str.strip()
        df['is_elevated'] = df['elevated'].astype(str).str.strip().str.lower().isin(
            {'true', '1', '1.0', 'yes'})
        df = df.sort_values(['agent_id', 'year'])
        df['prev_elevated'] = df.groupby('agent_id')['is_elevated'].shift(1)
        df['prev_elevated'] = df['prev_elevated'].fillna(False).astype(bool)

        n = len(df)
        r1 = ((df['ta'].isin(['H', 'VH'])) & (df['action'] == 'do_nothing')).sum()
        r3 = ((df['ta'].isin(['VL', 'L'])) & (df['action'] == 'relocate')).sum()
        r4 = ((df['ta'].isin(['VL', 'L'])) & (df['action'] == 'elevate_house')).sum()
        r5 = ((df['prev_elevated']) & (df['action'] == 'elevate_house')).sum()

        per_run.append({'n': n, 'R1': r1, 'R3': r3, 'R4': r4, 'R5': r5})

    if not per_run:
        return {'n': 0, 'R1': 0, 'R3': 0, 'R4': 0, 'R5': 0}

    # Average across runs
    result = {}
    total_n = sum(r['n'] for r in per_run)
    result['n'] = total_n / len(per_run)
    for key in ['R1', 'R3', 'R4', 'R5']:
        vals = [r[key] / r['n'] * 100 for r in per_run]
        result[key] = np.mean(vals)
        result[f'{key}_std'] = np.std(vals) if len(vals) > 1 else 0.0

    result['total'] = sum(result[k] for k in ['R1', 'R3', 'R4', 'R5'])
    return result


def _compute_cell_violations(df, ta, ca):
    """Compute violation COUNT for a single TA×CA cell.

    Rules (from strict governance profile):
      R1: TA=H/VH + do_nothing        (irrational inaction)
      R3: TA=VL/L + relocate           (overreaction)
      R4: TA=VL/L + elevate_house      (costly at low threat)
      R5: prev_elevated + elevate_house (hallucination / re-elevation)
    Returns: (violation_count, n)
    """
    cell = df[(df['ta_bin'] == ta) & (df['ca_bin'] == ca)]
    n = len(cell)
    if n == 0:
        return 0, 0

    v_r1 = cell['ta_bin'].isin(['H', 'VH']) & (cell['action'] == 'do_nothing')
    v_r3 = cell['ta_bin'].isin(['VL', 'L']) & (cell['action'] == 'relocate')
    v_r4 = cell['ta_bin'].isin(['VL', 'L']) & (cell['action'] == 'elevate_house')
    v_r5 = cell['prev_elevated'].astype(bool) & (cell['action'] == 'elevate_house')
    total_v = int((v_r1 | v_r3 | v_r4 | v_r5).sum())
    return total_v, n


def _prepare_pie_df(dfs, dec_col):
    """Prepare a combined DF with action, ta_bin, ca_bin, prev_elevated."""
    frames = []
    for df in dfs:
        df = df.copy()
        df['action'] = df[dec_col].apply(_normalise_decision)
        df['ta_bin'] = df['threat_appraisal'].astype(str).str.strip()
        # CA column
        for ca_col in ['coping_appraisal', 'coping_appraisal_label']:
            if ca_col in df.columns:
                df['ca_bin'] = df[ca_col].astype(str).str.strip()
                break
        else:
            df['ca_bin'] = 'M'
        # prev_elevated for R5
        df['is_elev'] = df['elevated'].astype(str).str.strip().str.lower().isin(
            {'true', '1', '1.0', 'yes'})
        df = df.sort_values(['agent_id', 'year'])
        df['prev_elevated'] = df.groupby('agent_id')['is_elev'].shift(1).fillna(False).astype(bool)
        df = df[df['ta_bin'].isin(LEVEL_ORDER) & df['ca_bin'].isin(LEVEL_ORDER)]
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def draw_single_pie_grid(fig, ax, df, title, title_color, show_ylabel=True,
                         show_legend=False, viol_cmap=None, viol_norm=None):
    """Draw a single 5×5 TA×CA pie matrix on the given axes.

    Background color = violation count (amber heatmap).
    Mini pie charts = action distribution per cell.
    """
    PIE_ACTIONS = ['do_nothing', 'buy_insurance', 'elevate_house', 'relocate']
    PIE_COLORS = ['#BBBBBB', '#0072B2', '#D55E00', '#CC79A7']
    PIE_LABELS = ['DN', 'FI', 'HE', 'RL']  # Do Nothing, Flood Insurance, House Elevation, Relocate

    ax.set_xlim(-0.5, 4.5)
    ax.set_ylim(-0.5, 4.5)
    ax.set_aspect('equal', adjustable='box')
    ax.set_xticks(range(5))
    ax.set_xticklabels(LEVEL_ORDER, fontsize=BASE_FONT)
    ax.set_yticks(range(5))
    if show_ylabel:
        ax.set_yticklabels(LEVEL_ORDER, fontsize=BASE_FONT)
        ax.set_ylabel('Threat appraisal (TA)', fontsize=BASE_FONT, labelpad=2)
    else:
        ax.set_yticklabels([])
    ax.set_xlabel('Coping appraisal (CA)', fontsize=BASE_FONT, labelpad=3)
    ax.set_title(title, fontsize=BASE_FONT + 0.5, fontweight='bold',
                 color=title_color, pad=6)

    for i, ta in enumerate(LEVEL_ORDER):
        for j, ca in enumerate(LEVEL_ORDER):
            viol_count, vn = _compute_cell_violations(df, ta, ca)

            # Background: violation count → color
            if vn >= 3:
                bg_color = viol_cmap(viol_norm(viol_count))
            else:
                bg_color = (0.97, 0.97, 0.97, 1.0)

            rect = plt.Rectangle((j - 0.5, i - 0.5), 1, 1,
                                 facecolor=bg_color,
                                 edgecolor='#DDDDDD', linewidth=0.4)
            ax.add_patch(rect)

            # Get action fractions for pie
            cell = df[(df['ta_bin'] == ta) & (df['ca_bin'] == ca)]
            n = len(cell)
            if n < 3:
                if n > 0:
                    ax.text(j, i, f'n={n}', ha='center', va='center',
                            fontsize=6, color='#BBBBBB')
                continue

            fracs = [(cell['action'] == a).sum() / n for a in PIE_ACTIONS]

            # Pie radius scaled by log(n) — larger for readability
            radius = 0.32 + 0.12 * min(np.log10(n) / 3.0, 1.0)

            start = 90.0
            for k, frac in enumerate(fracs):
                if frac <= 0:
                    continue
                end = start - frac * 360
                wedge = mpatches.Wedge(
                    (j, i), radius,
                    min(start, end), max(start, end),
                    facecolor=PIE_COLORS[k], edgecolor='white', linewidth=0.3)
                ax.add_patch(wedge)
                start = end

            # Violation count annotation (top-right corner)
            if viol_count > 0:
                ax.text(j + 0.40, i + 0.40, str(viol_count),
                        ha='right', va='top', fontsize=6.5,
                        color='#CC0000', fontweight='bold')

            # n label centered inside pie
            ax.text(j, i - 0.02, str(n), ha='center', va='center',
                    fontsize=6, color='white', fontweight='bold',
                    zorder=10,
                    bbox=dict(boxstyle='round,pad=0.1', facecolor='#00000055',
                              edgecolor='none'))

    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color('#CCCCCC')

    # Action legend inside grid — compact horizontal with abbreviations
    if show_legend:
        pie_handles = [mpatches.Patch(facecolor=PIE_COLORS[k], edgecolor='white',
                       linewidth=0.4, label=PIE_LABELS[k]) for k in range(4)]
        ax.legend(handles=pie_handles, loc='upper left', ncol=2,
                  fontsize=BASE_FONT - 0.5,
                  frameon=True, framealpha=0.9,
                  facecolor='white', edgecolor='#CCCCCC',
                  handlelength=0.6, handletextpad=0.2,
                  labelspacing=0.15, columnspacing=0.5,
                  borderpad=0.2)


# ══════════════════════════════════════════════════════════════════════════════
# Panel (b): Multi-layer flood protection trajectory
# ══════════════════════════════════════════════════════════════════════════════

FLOOD_YEARS = [3, 4, 9]


def _normalise_decision(dec: str) -> str:
    """Map various decision strings to canonical flood action."""
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


def _compute_multilayer_trajectory(dfs: list) -> tuple:
    """Compute % agents with multi-layer protection per year.

    Multi-layer = (insurance AND elevation) OR relocated.
    Returns: (years, means, stds) arrays.
    """
    if not dfs:
        return np.arange(1, 11), np.zeros(10), np.zeros(10)

    per_run = []
    for df in dfs:
        df = df.copy()
        df['elev'] = _as_bool(df['elevated'])
        df['ins'] = _as_bool(df['has_insurance'])
        df['reloc'] = _as_bool(df['relocated'])
        df['multi'] = (df['elev'] & df['ins']) | df['reloc']
        yearly = []
        for y in range(1, 11):
            yr = df[df['year'] == y]
            if len(yr) == 0:
                yearly.append(0.0)
            else:
                yearly.append(yr['multi'].sum() / len(yr) * 100)
        per_run.append(yearly)

    arr = np.array(per_run)
    years = np.arange(1, 11)
    means = arr.mean(axis=0)
    stds = arr.std(axis=0) if arr.shape[0] > 1 else np.zeros(10)
    return years, means, stds


def draw_panel_b(ax, data: dict):
    """Draw panel (b): multi-layer flood protection rate over time.

    Water insight: governance builds flood resilience through layered protection,
    not just single-measure adoption. Flood events (Y3, Y4, Y9) trigger jumps.
    """
    conditions = [
        ('rulebased', 'Rule-based',            PMT_COLOR,   '--'),
        ('disabled',  'LLM (no val.)',         UNGOV_COLOR,  '-'),
        ('gov',       'Governed',              GOV_COLOR,    '-'),
    ]

    for cond_key, label, color, ls in conditions:
        years, means, stds = _compute_multilayer_trajectory(data[cond_key])

        # Individual runs as thin lines (if multiple)
        if len(data[cond_key]) > 1:
            for df in data[cond_key]:
                _, run_m, _ = _compute_multilayer_trajectory([df])
                ax.plot(years, run_m, color=color, alpha=0.15, lw=0.6, zorder=1)

        # Mean line
        ax.plot(years, means, color=color, ls=ls, lw=1.2, marker='o',
                markersize=3, zorder=3, label=label)

        # Confidence band
        if stds.max() > 0:
            ax.fill_between(years, means - stds, means + stds,
                            color=color, alpha=0.12, zorder=1)

    # Flood event markers
    for fy in FLOOD_YEARS:
        ax.axvline(fy, color='#AAAAAA', ls=':', lw=0.6, alpha=0.6, zorder=0)
    # Single "F" label at top for flood markers
    ax.text(FLOOD_YEARS[0], ax.get_ylim()[1] if ax.get_ylim()[1] > 0 else 95,
            'F', fontsize=6, color='#888888', ha='center', va='bottom')
    ax.text(FLOOD_YEARS[1], 95, 'F', fontsize=6, color='#888888', ha='center', va='bottom')
    ax.text(FLOOD_YEARS[2], 95, 'F', fontsize=6, color='#888888', ha='center', va='bottom')

    ax.set_xlim(0.5, 10.5)
    ax.set_xticks(range(1, 11))
    ax.set_xticklabels(range(1, 11), fontsize=BASE_FONT - 1)
    ax.set_xlabel('Simulation year', fontsize=BASE_FONT - 0.5, labelpad=2)
    ax.set_ylabel('Multi-layer protection (%)', fontsize=BASE_FONT - 0.5, labelpad=2)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_locator(ticker.MultipleLocator(25))

    # Legend
    ax.legend(fontsize=BASE_FONT - 2.0, frameon=False,
              loc='center right', handlelength=1.2,
              handletextpad=0.3, labelspacing=0.2,
              borderpad=0.2)


# ══════════════════════════════════════════════════════════════════════════════
# Legends
# ══════════════════════════════════════════════════════════════════════════════

def _make_stacked_bar_legend_handles():
    handles = []
    for state in PROT_STATES:
        patch = mpatches.Patch(
            facecolor=PROT_COLORS[state],
            edgecolor='white',
            linewidth=0.4,
            label=state,
        )
        handles.append(patch)
    return handles


def _make_pie_legend_handles():
    handles = []
    for state in PROT_STATES:
        patch = mpatches.Patch(
            facecolor=PROT_COLORS[state],
            edgecolor='#888888',
            linewidth=0.3,
            label=state,
        )
        handles.append(patch)
    return handles


# ══════════════════════════════════════════════════════════════════════════════
# Main figure assembly
# ══════════════════════════════════════════════════════════════════════════════

def generate_figure():
    print("Loading data...")
    data = load_all_runs()

    # ── Figure: 2×3 layout ──────────────────────────────────────────────────
    # Row 1: a1, a2, a3  (stacked bars)
    # Row 2: b, c1, c2   (before/after bars, ungoverned pie, governed pie)
    fig = plt.figure(figsize=(7.09, 7.0))

    # Two-row outer grid
    gs_outer = gridspec.GridSpec(
        2, 1,
        height_ratios=[1.0, 1.5],
        left=0.07, right=0.97,
        top=0.95, bottom=0.06,
        hspace=0.32,
    )

    # Row 1: 3 equal-width columns for panel (a)
    gs_row1 = gridspec.GridSpecFromSubplotSpec(
        1, 3, subplot_spec=gs_outer[0],
        wspace=0.25,
    )

    # Row 2: b(wider) + c1 + c2
    gs_row2 = gridspec.GridSpecFromSubplotSpec(
        1, 3, subplot_spec=gs_outer[1],
        width_ratios=[1.15, 1.0, 1.0],
        wspace=0.30,
    )

    # ── Row 1: Panel (a) — 3 equal stacked bar sub-panels ──────────
    ax_a1 = fig.add_subplot(gs_row1[0, 0])
    ax_a2 = fig.add_subplot(gs_row1[0, 1], sharey=ax_a1)
    ax_a3 = fig.add_subplot(gs_row1[0, 2], sharey=ax_a1)
    draw_panel_a([ax_a1, ax_a2, ax_a3], data)

    # ── Row 2, col 0: Panel (b) — initial vs final protection state ──
    ax_b = fig.add_subplot(gs_row2[0, 0])
    draw_panel_b(ax_b, data)

    # ── Row 2, cols 1-2: Panel (c) — pie matrices ──────────
    # Prepare data (Run_1 only for comparable n=1000)
    df_dis = _prepare_pie_df(data['disabled'][:1], 'yearly_decision')
    df_gov = _prepare_pie_df(data['gov'][:1], 'yearly_decision')

    # Shared violation colormap
    max_viol = 1
    for df in [df_dis, df_gov]:
        for ta in LEVEL_ORDER:
            for ca in LEVEL_ORDER:
                vc, _ = _compute_cell_violations(df, ta, ca)
                max_viol = max(max_viol, vc)

    viol_cmap = mcolors.LinearSegmentedColormap.from_list(
        'viol', [(1, 1, 1), (1, 0.96, 0.85), (1, 0.85, 0.55), (0.95, 0.65, 0.15)],
        N=256)
    viol_norm = mcolors.Normalize(vmin=0, vmax=max_viol)

    ax_c1 = fig.add_subplot(gs_row2[0, 1])
    ax_c2 = fig.add_subplot(gs_row2[0, 2])

    draw_single_pie_grid(fig, ax_c1, df_dis, 'LLM (no validation)', UNGOV_COLOR,
                         show_ylabel=True, show_legend=True,
                         viol_cmap=viol_cmap, viol_norm=viol_norm)
    draw_single_pie_grid(fig, ax_c2, df_gov, 'Governed LLM', GOV_COLOR,
                         show_ylabel=False, show_legend=False,
                         viol_cmap=viol_cmap, viol_norm=viol_norm)

    # Colorbar next to governed grid
    pos_c2 = ax_c2.get_position()
    ax_cb = fig.add_axes([pos_c2.x1 + 0.005, pos_c2.y0 + pos_c2.height * 0.05,
                          0.008, pos_c2.height * 0.9])
    cb = ColorbarBase(ax_cb, cmap=viol_cmap, norm=viol_norm, orientation='vertical')
    cb.set_label('Violations', fontsize=BASE_FONT - 0.5, labelpad=2)
    cb.ax.tick_params(labelsize=BASE_FONT - 1)

    # ── Panel labels ──────────────────────────────────────────────────────
    label_x = 0.01
    fig.text(label_x, ax_a1.get_position().y1 + 0.01, 'a',
             fontsize=10, fontweight='bold', va='bottom')
    fig.text(label_x, ax_b.get_position().y1 + 0.01, 'b',
             fontsize=10, fontweight='bold', va='bottom')
    fig.text(ax_c1.get_position().x0 - 0.03, ax_c1.get_position().y1 + 0.01, 'c',
             fontsize=10, fontweight='bold', va='bottom')

    # ── Save ────────────────────────────────────────────────────────────────
    for fmt in ['png', 'pdf']:
        out = OUT_DIR / f"Fig3_flood_case.{fmt}"
        fig.savefig(out, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"  Saved: {out}")

    plt.close(fig)
    print("Done.")


# ══════════════════════════════════════════════════════════════════════════════
# Summary statistics (optional diagnostic)
# ══════════════════════════════════════════════════════════════════════════════

def print_summary_stats(data: dict):
    print("\n=== Protection State Summary ===")
    for cond_name, cond_key in [('Rule-based',            'rulebased'),
                                 ('LLM (no validation)',   'disabled'),
                                 ('Governed LLM',          'gov')]:
        print(f"\n  {cond_name}:")
        all_df = pd.concat(data[cond_key], ignore_index=True) if data[cond_key] else pd.DataFrame()
        if all_df.empty:
            print("    No data.")
            continue
        total = len(all_df)
        for state in PROT_STATES:
            n = (all_df['prot_state'] == state).sum()
            print(f"    {state:>25s}: {n:>5d} ({n/total*100:.1f}%)")

    print("\n=== EHE per Run ===")
    for cond_name, cond_key in [('Rule-based',            'rulebased'),
                                 ('LLM (no validation)',   'disabled'),
                                 ('Governed LLM',          'gov')]:
        ehe_vals = []
        for run_df in data[cond_key]:
            if run_df.empty:
                continue
            col = 'yearly_decision' if 'yearly_decision' in run_df.columns else 'decision'
            ehe_vals.append(_ehe_from_decisions(run_df[col]))
        vals = np.array(ehe_vals) if ehe_vals else np.array([0.0])
        print(f"  {cond_name}: {vals} → mean={vals.mean():.3f}, sd={vals.std():.3f}")


if __name__ == '__main__':
    generate_figure()
    data = load_all_runs()
    print_summary_stats(data)
