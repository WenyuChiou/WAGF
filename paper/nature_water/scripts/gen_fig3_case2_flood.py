#!/usr/bin/env python3
"""
Nature Water — Figure 3 (flood case study): 3-panel figure.

Layout (7.09 × 7.0 in, full Nature Water width):
  Top row:   (a) Cumulative protection state evolution — 3 side-by-side stacked
                 bar sub-panels: Rule-based | LLM (no validator) | Governed LLM
  Bottom row: (b) Initial vs final protection state comparison (grouped bars)
              (c) TA×CA pie matrices: LLM (no validator) vs Governed LLM

Data sources:
  - Rule-based PMT : examples/single_agent/results/rulebased/Run_{1,2,3}/simulation_log.csv
  - LLM (no validator): examples/single_agent/results/JOH_ABLATION_DISABLED/gemma3_4b/Group_C_disabled/Run_{1,2,3}/simulation_log.csv
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
REPO = Path(__file__).resolve().parents[3]
SA_RESULTS = REPO / "examples" / "single_agent" / "results"

# ── Model selection (overridable via FIG3_MODEL / FIG3_OUT env vars) ──────
# FIG3_MODEL   : directory name under JOH_FINAL/*/Group_C (e.g. gemma3_4b, gemma4_26b)
# FIG3_LABEL   : short pretty label used in figure caption-side text (optional)
# FIG3_OUT     : output basename WITHOUT extension (default Fig3_flood_case)
import os as _os
MODEL_KEY   = _os.environ.get("FIG3_MODEL", "gemma3_4b")
MODEL_LABEL = _os.environ.get("FIG3_LABEL", MODEL_KEY.replace("_", " "))
OUT_BASENAME = _os.environ.get("FIG3_OUT", "Fig3_flood_case")

RULEBASED_DIR  = SA_RESULTS / "rulebased"
DISABLED_DIR   = SA_RESULTS / "JOH_ABLATION_DISABLED" / MODEL_KEY / "Group_C_disabled"
GOV_DIR        = SA_RESULTS / "JOH_FINAL" / MODEL_KEY / "Group_C"

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

RUNS = [f'Run_{i}' for i in range(1, 6)]  # Run_1..Run_5; missing runs skipped at load time


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


def _load_llm_run_from_traces(base_dir: Path, run: str,
                               max_year: int = 10) -> pd.DataFrame:
    """Load one LLM run from household_traces.jsonl (fallback when CSV absent).

    Flattens nested fields:
      - approved_skill.skill_name → yearly_decision
      - skill_proposal.reasoning.TP_LABEL → threat_appraisal
      - skill_proposal.reasoning.CP_LABEL → coping_appraisal
      - state_after.{elevated, has_insurance, relocated} → boolean columns
    Filters to year <= max_year for cross-condition alignment.
    """
    import json as _json

    jsonl_path = base_dir / run / "raw" / "household_traces.jsonl"
    if not jsonl_path.exists():
        print(f"  WARNING: Missing {jsonl_path}")
        return pd.DataFrame()

    rows = []
    with open(jsonl_path, encoding='utf-8') as fh:
        for line in fh:
            t = _json.loads(line)
            year = t.get('year', 0)
            if year > max_year:
                continue

            # Extract action from approved_skill
            ap = t.get('approved_skill', {})
            if isinstance(ap, dict):
                action = ap.get('skill_name', 'do_nothing')
            else:
                action = str(ap) if ap else 'do_nothing'

            # Extract TP/CP from skill_proposal.reasoning
            sp = t.get('skill_proposal', {})
            reasoning = sp.get('reasoning', {}) if isinstance(sp, dict) else {}
            if isinstance(reasoning, dict):
                tp = str(reasoning.get('TP_LABEL', '')).strip().upper()
                cp = str(reasoning.get('CP_LABEL', '')).strip().upper()
            else:
                tp, cp = '', ''

            # State after action (for cumulative protection classification)
            sa = t.get('state_after', t.get('state_before', {}))
            elevated = sa.get('elevated', False)
            has_ins = sa.get('has_insurance', False)
            relocated = sa.get('relocated', False)

            rows.append({
                'year': year,
                'agent_id': t.get('agent_id', ''),
                'yearly_decision': action,
                'threat_appraisal': tp,
                'coping_appraisal': cp,
                'elevated': elevated,
                'has_insurance': has_ins,
                'relocated': relocated,
            })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df['prot_state'] = df.apply(_classify_state_from_cols, axis=1)
    print(f"    Loaded {len(df)} traces from {jsonl_path.name} (year≤{max_year})")
    return df


def _load_llm_run_grouped(base_dir: Path, run: str) -> pd.DataFrame:
    """Load one LLM run. Prefers simulation_log.csv; falls back to traces."""
    path = base_dir / run / "simulation_log.csv"
    if not path.exists():
        # Fallback: load from household_traces.jsonl
        return _load_llm_run_from_traces(base_dir, run, max_year=10)

    df = pd.read_csv(path, encoding='utf-8-sig')

    # Filter to year <= 10 for consistency
    if 'year' in df.columns:
        df = df[df['year'] <= 10].copy()

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
    sub_configs = get_panel_a_configs()

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

        for year_idx, year in enumerate(years):
            if year in get_flood_years():
                ax.axvspan(
                    x[year_idx] - 0.36,
                    x[year_idx] + 0.36,
                    color=get_flood_year_marker_style()["span_color"],
                    alpha=get_flood_year_marker_style()["span_alpha"],
                    zorder=1,
                )

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

        ax.set_ylim(*get_panel_a_ylim())
        ax.yaxis.set_major_locator(ticker.MultipleLocator(20))

        marker_style = get_flood_year_marker_style()
        for year_idx, year in enumerate(years):
            if year in get_flood_years():
                ax.text(
                    x[year_idx],
                    marker_style["y"],
                    marker_style["label"],
                    ha='center',
                    va='center',
                    fontsize=marker_style["fontsize"],
                    color=marker_style["color"],
                    fontweight=marker_style["fontweight"],
                    bbox=marker_style["bbox"],
                    zorder=5,
                )

    # Legend placed ABOVE the middle subplot (centered over the 3-subplot row).
    # Previously the legend sat inside axes[0] at 'upper right' and overlapped
    # the Year 1-3 bars of the Governed LLM subplot; moving it out of the
    # plotting area recovers that data region.
    handles_leg = [
        mpatches.Patch(facecolor=PROT_COLORS[s], edgecolor='white',
                       linewidth=0.4, label=PROT_ABBREV[s])
        for s in PROT_STATES
    ]
    axes[1].legend(
        handles=handles_leg,
        loc='lower center',
        bbox_to_anchor=(0.5, 1.12),
        fontsize=BASE_FONT - 1,
        frameon=True, framealpha=0.9,
        facecolor='white', edgecolor='#888888',
        handlelength=0.8,
        handletextpad=0.3,
        labelspacing=0.2,
        columnspacing=0.8,
        borderpad=0.3,
        ncol=5,
    )

    # Panel label 'a' — added in generate_figure() for alignment


def get_panel_a_configs():
    """Top-row order for Fig. 3.

    Keep governed on the left and ungoverned on the right.
    """
    return [
        ('gov',       'Governed LLM',        GOV_COLOR),
        ('rulebased', 'Rule-based',          PMT_COLOR),
        ('disabled',  'LLM (no validator)',  UNGOV_COLOR),
    ]


def get_panel_a_ylim():
    return (0, 110)


def get_flood_years():
    return [3, 4, 9]


def get_flood_year_spans():
    return [(2.5, 4.5), (8.5, 9.5)]


def get_flood_year_marker_style():
    return {
        'label': 'F',
        'y': 106,
        'fontsize': BASE_FONT - 0.2,
        'color': '#D94B4B',
        'fontweight': 'bold',
        'span_color': '#F5DADA',
        'span_alpha': 0.42,
        'bbox': {
            'boxstyle': 'round,pad=0.22,rounding_size=0.03',
            'facecolor': '#F9EFEF',
            'edgecolor': '#EBCACA',
            'linewidth': 0.8,
        },
    }


def get_panel_a_legend_config():
    return {
        'target_axis_index': 0,
        'loc': 'upper right',
    }


def get_violation_annotation_style():
    return {
        'ha': 'right',
        'va': 'top',
        'fontsize': 7.8,
        'color': '#B22222',
        'fontweight': 'bold',
        'bbox': {
            'boxstyle': 'round,pad=0.16',
            'facecolor': 'white',
            'edgecolor': '#B22222',
            'linewidth': 0.5,
        },
    }

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
    PIE_COLORS = ['#BDBDBD', '#4C78A8', '#F2B701', '#CC6677']
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
                ax.text(
                    j + 0.43, i + 0.43, str(viol_count),
                    **get_violation_annotation_style(),
                )

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
                  facecolor='white', edgecolor='black',
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


def _compute_yearly_ehe(dfs: list) -> tuple:
    """Compute per-year normalised Shannon entropy (EHE) from action distributions.

    Returns: (years, means, stds) arrays — one EHE value per simulation year.
    This captures *within-year behavioural diversity*, which is high for LLM agents
    (diverse reasoning → diverse actions) and low for rule-based agents
    (deterministic formula → uniform response).
    """
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
            # Get decision column
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


def _compute_action_props_and_se(dfs: list, action: str):
    """Return (mean_vals, se_vals) arrays of length 10 for one action."""
    per_run = []
    for df in dfs:
        if df.empty:
            continue
        # Need yearly_action column — derive if missing
        if 'yearly_action' not in df.columns:
            if 'yearly_decision' in df.columns:
                df = df.copy()
                df['yearly_action'] = df['yearly_decision'].apply(_normalise_decision)
            else:
                continue
        vals = []
        for yr in range(1, 11):
            yr_df = df[df['year'] == yr]
            total = len(yr_df)
            if total == 0:
                vals.append(0.0)
            else:
                vals.append((yr_df['yearly_action'] == action).sum() / total * 100)
        per_run.append(vals)
    if not per_run:
        return np.zeros(10), np.zeros(10)
    arr = np.array(per_run)
    mean = arr.mean(axis=0)
    se = arr.std(axis=0, ddof=1) / np.sqrt(len(per_run)) if len(per_run) > 1 else np.zeros(10)
    return mean, se


def _derive_yearly_action_rulebased(df: pd.DataFrame) -> pd.DataFrame:
    """Add yearly_action column to rulebased DF (transition-based)."""
    if 'yearly_action' in df.columns:
        return df
    df = df.copy()
    df_sorted = df.sort_values(['agent_id', 'year'])
    actions = []
    for _, agent_df in df_sorted.groupby('agent_id'):
        prev_ins, prev_elv, prev_rel = False, False, False
        for _, row in agent_df.iterrows():
            ins = _as_bool(pd.Series([row['has_insurance']]))[0]
            elv = _as_bool(pd.Series([row['elevated']]))[0]
            rel = _as_bool(pd.Series([row['relocated']]))[0]
            if rel and not prev_rel:
                actions.append('relocate')
            elif elv and not prev_elv:
                actions.append('elevate_house')
            elif ins and not prev_ins:
                actions.append('buy_insurance')
            else:
                actions.append('do_nothing')
            prev_ins, prev_elv, prev_rel = ins, elv, rel
    df_sorted['yearly_action'] = actions
    return df_sorted


def _derive_yearly_action_llm(df: pd.DataFrame) -> pd.DataFrame:
    """Add yearly_action column to LLM DF from yearly_decision."""
    if 'yearly_action' in df.columns:
        return df
    df = df.copy()
    if 'yearly_decision' in df.columns:
        df['yearly_action'] = df['yearly_decision'].apply(_normalise_decision)
    elif 'decision' in df.columns:
        df['yearly_action'] = df['decision'].apply(_normalise_decision)
    else:
        df['yearly_action'] = 'do_nothing'
    return df


def draw_panel_b(axes_b, data: dict):
    """Draw panel (b): 3×1 yearly adaptive action share sub-panels.

    Row i:   Insurance purchase rate (%)
    Row ii:  Elevation rate (%)
    Row iii: Relocation rate (%)

    Each sub-panel overlays 3 conditions with ±1 SE bands.
    Flood periods shaded.
    """
    from matplotlib.lines import Line2D

    # Condition config: key, label, color, marker, linestyle
    cond_config = [
        ('gov',       'Governed LLM',       GOV_COLOR,   'o',  '-'),
        ('disabled',  'LLM (no validator)', UNGOV_COLOR, 's',  '-'),
        ('rulebased', 'Traditional ABM',    PMT_COLOR,   '^',  '--'),
    ]

    # Row config: action_key, panel_label, ylabel
    row_config = [
        ('buy_insurance', 'i',   'Insurance (%)'),
        ('elevate_house', 'ii',  'Elevation (%)'),
        ('relocate',      'iii', 'Relocation (%)'),
    ]

    years = np.arange(1, 11)

    # Pre-process: add yearly_action to all DFs
    processed = {}
    for cond_key in ['rulebased', 'disabled', 'gov']:
        processed[cond_key] = []
        for df in data[cond_key]:
            if cond_key == 'rulebased':
                processed[cond_key].append(_derive_yearly_action_rulebased(df))
            else:
                processed[cond_key].append(_derive_yearly_action_llm(df))

    # Pre-compute all data
    all_data = {}
    for action_key, _, _ in row_config:
        all_data[action_key] = {}
        for cond_key, _, _, _, _ in cond_config:
            all_data[action_key][cond_key] = _compute_action_props_and_se(
                processed[cond_key], action_key)

    # Determine y-axis limits from data
    def get_ymax(action_key):
        max_val = 0
        for cond_key, _, _, _, _ in cond_config:
            mean, se = all_data[action_key][cond_key]
            max_val = max(max_val, np.max(mean + se))
        return max_val

    for row_idx, (action_key, panel_label, ylabel) in enumerate(row_config):
        ax = axes_b[row_idx]

        # Data-driven y-max
        raw_max = get_ymax(action_key)
        if raw_max <= 15:
            y_max = int(np.ceil(raw_max / 5) * 5) + 2
            yticks = np.arange(0, y_max + 1, 5)
        elif raw_max <= 30:
            y_max = int(np.ceil(raw_max / 10) * 10) + 5
            yticks = np.arange(0, y_max + 1, 10)
        else:
            y_max = int(np.ceil(raw_max / 10) * 10) + 5
            yticks = np.arange(0, y_max + 1, 20)

        # Flood event shading
        for fy_start, fy_end in get_flood_year_spans():
            ax.axvspan(fy_start, fy_end, color='#E8EEF4', alpha=0.8, zorder=0)

        # Horizontal gridlines
        ax.yaxis.grid(True, color='#E0E0E0', linewidth=0.4, zorder=0)
        ax.set_axisbelow(True)

        # Plot each condition
        for cond_key, cond_label, color, marker, ls in cond_config:
            mean, se = all_data[action_key][cond_key]
            ax.fill_between(years, np.maximum(mean - se, 0), mean + se,
                           color=color, alpha=0.10, zorder=1)
            ax.plot(years, mean, ls, color=color, linewidth=1.2, zorder=3)
            ax.plot(years, mean, marker, color=color, markersize=3,
                    markeredgecolor='white', markeredgewidth=0.3, zorder=4)

        # Y-axis
        ax.set_ylabel(ylabel, fontsize=BASE_FONT - 1, labelpad=3)
        ax.set_ylim(0, y_max)
        ax.set_yticks(yticks)

        # Panel label
        ax.text(0.02, 0.92, panel_label, transform=ax.transAxes,
                fontsize=BASE_FONT, fontweight='bold', va='top', ha='left')

        # Flood label on top sub-panel only
        if row_idx == 0:
            for mid, label in [(3.5, 'Flood\nY3\u20134'), (9.0, 'Flood\nY9')]:
                ax.text(mid, y_max * 0.95, label, fontsize=5, color='#666666',
                        ha='center', va='top', linespacing=0.9, zorder=5)

        ax.tick_params(length=2, pad=2)

        # X-axis only on bottom sub-panel
        if row_idx < 2:
            ax.set_xticklabels([])
        else:
            ax.set_xticks(years)
            ax.set_xticklabels([str(y) for y in years], fontsize=BASE_FONT - 1)
            ax.set_xlabel('Simulation year', fontsize=BASE_FONT - 0.5, labelpad=2)

    # Legend on top sub-panel
    legend_elements = [
        Line2D([0], [0], color=GOV_COLOR, marker='o', markersize=3.5,
               markeredgecolor='white', markeredgewidth=0.3,
               linewidth=1.2, label='Governed LLM'),
        Line2D([0], [0], color=UNGOV_COLOR, marker='s', markersize=3.5,
               markeredgecolor='white', markeredgewidth=0.3,
               linewidth=1.2, label='LLM (no validator)'),
        Line2D([0], [0], color=PMT_COLOR, marker='^', markersize=3.5,
               markeredgecolor='white', markeredgewidth=0.3,
               linewidth=1.2, linestyle='--', label='Traditional ABM'),
    ]
    axes_b[0].legend(handles=legend_elements, loc='upper center',
                     bbox_to_anchor=(0.5, 1.30), ncol=3, frameon=False,
                     fontsize=BASE_FONT - 1.5, handlelength=2.0,
                     columnspacing=1.0, handletextpad=0.4)


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

    # ── Figure: 2-row layout ─────────────────────────────────────────────
    # Row 1: (a) 3 stacked bar sub-panels — cumulative protection states
    # Row 2: (b) 2 TA×CA pie matrices — LLM (no validator) vs Governed LLM
    fig = plt.figure(figsize=(7.09, 6.0))

    gs_outer = gridspec.GridSpec(
        2, 1,
        height_ratios=[1.0, 1.3],
        left=0.07, right=0.96,
        top=0.96, bottom=0.06,
        hspace=0.30,
    )

    # Row 1: 3 equal-width columns for panel (a)
    gs_row1 = gridspec.GridSpecFromSubplotSpec(
        1, 3, subplot_spec=gs_outer[0],
        wspace=0.25,
    )

    # Row 2: 2 pie matrices side-by-side
    gs_row2 = gridspec.GridSpecFromSubplotSpec(
        1, 2, subplot_spec=gs_outer[1],
        wspace=0.20,
    )

    # ── Panel (a) — 3 stacked bar sub-panels ──────────────────────────
    ax_a1 = fig.add_subplot(gs_row1[0, 0])
    ax_a2 = fig.add_subplot(gs_row1[0, 1], sharey=ax_a1)
    ax_a3 = fig.add_subplot(gs_row1[0, 2], sharey=ax_a1)
    draw_panel_a([ax_a1, ax_a2, ax_a3], data)

    # ── Panel (b) — TA×CA pie matrices (aggregated across all seeds) ─
    df_dis = _prepare_pie_df(data['disabled'], 'yearly_decision')
    df_gov = _prepare_pie_df(data['gov'], 'yearly_decision')

    viol_cmap = mcolors.LinearSegmentedColormap.from_list(
        'viol', [(1, 1, 1), (1, 0.92, 0.78), (1, 0.72, 0.42),
                 (0.92, 0.45, 0.10), (0.75, 0.15, 0.05)],
        N=256)
    n_runs = max(len(data['disabled']), len(data['gov']), 1)
    VIOL_MAX = 100 * n_runs
    viol_norm = mcolors.Normalize(vmin=0, vmax=VIOL_MAX)

    ax_b1 = fig.add_subplot(gs_row2[0, 0])
    ax_b2 = fig.add_subplot(gs_row2[0, 1])

    draw_single_pie_grid(fig, ax_b1, df_dis, 'LLM (no validator)', UNGOV_COLOR,
                         show_ylabel=True, show_legend=True,
                         viol_cmap=viol_cmap, viol_norm=viol_norm)
    draw_single_pie_grid(fig, ax_b2, df_gov, 'Governed LLM', GOV_COLOR,
                         show_ylabel=False, show_legend=False,
                         viol_cmap=viol_cmap, viol_norm=viol_norm)

    # Shared colorbar
    pos_b2 = ax_b2.get_position()
    ax_cb = fig.add_axes([pos_b2.x1 + 0.005, pos_b2.y0 + pos_b2.height * 0.05,
                          0.008, pos_b2.height * 0.9])
    cb = ColorbarBase(ax_cb, cmap=viol_cmap, norm=viol_norm, orientation='vertical')
    cb.set_label('Violations', fontsize=BASE_FONT - 0.5, labelpad=2)
    cb.ax.tick_params(labelsize=BASE_FONT - 1)

    # ── Panel labels ──────────────────────────────────────────────────────
    label_x = 0.01
    fig.text(label_x, ax_a1.get_position().y1 + 0.01, 'a',
             fontsize=10, fontweight='bold', va='bottom')
    fig.text(label_x, ax_b1.get_position().y1 + 0.01, 'b',
             fontsize=10, fontweight='bold', va='bottom')

    # ── Save ────────────────────────────────────────────────────────────────
    for fmt in ['png', 'pdf']:
        out = OUT_DIR / f"{OUT_BASENAME}.{fmt}"
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
                                 ('LLM (no validator)',   'disabled'),
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
                                 ('LLM (no validator)',   'disabled'),
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
