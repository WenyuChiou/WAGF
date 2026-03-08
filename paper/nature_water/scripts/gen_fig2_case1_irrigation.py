#!/usr/bin/env python3
"""
gen_fig2_case1_irrigation.py

Generate a 4-panel figure for the irrigation case study (Nature Water Fig 2).

Layout (GridSpec, 7.09 × 7.5 in):
  Top row:  (a) Governed vs Ungoverned stacked area + Mead   [wider]
            (b) Demand ratio vs Shortage years scatter        [narrower]
  Bottom row: (c) WSA × ACA pie matrix                       [left, large]
              (d) IBR × EHE scatter (rolling 5-yr)           [right]

Output: paper/nature_water/figures/Fig2_irrigation_case.{png,pdf}
"""

import sys
import warnings
import math
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
from matplotlib.colorbar import ColorbarBase
from matplotlib.patches import FancyArrowPatch
from matplotlib import rcParams

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO = Path(__file__).resolve().parents[3]
RESULTS = REPO / "examples" / "irrigation_abm" / "results"
OUT_DIR = REPO / "paper" / "nature_water" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Colours  (Okabe-Ito palette)
# ---------------------------------------------------------------------------
C_GOV   = "#0072B2"   # governed - blue
C_UNGOV = "#D55E00"   # ungoverned - vermillion
C_NOCEIL= "#009E73"   # no ceiling - teal
C_FQL   = "#666666"   # FQL - grey

ACTION_COLORS = {
    "increase_large":    "#D55E00",
    "increase_small":    "#E69F00",
    "maintain_demand":   "#DDDDDD",
    "decrease_small":    "#56B4E9",
    "decrease_large":    "#0072B2",
}
ACTION_HATCHES = {
    "increase_large":    "",
    "increase_small":    "",
    "maintain_demand":   "",
    "decrease_small":    "",
    "decrease_large":    "",
}
ACTION_ORDER = [
    "increase_large",
    "increase_small",
    "maintain_demand",
    "decrease_small",
    "decrease_large",
]
ACTION_LABELS = {
    "increase_large":    "Increase large",
    "increase_small":    "Increase small",
    "maintain_demand":   "Maintain demand",
    "decrease_small":    "Decrease small",
    "decrease_large":    "Decrease large",
}

# Original 5-action scheme (for pie matrix which uses proposed_skill from audit)
PIE_ACTION_ORDER = [
    "increase_large", "increase_small", "maintain_demand",
    "decrease_small", "decrease_large",
]
PIE_ACTION_COLORS = {
    "increase_large":  "#D55E00",
    "increase_small":  "#E69F00",
    "maintain_demand": "#DDDDDD",
    "decrease_small":  "#56B4E9",
    "decrease_large":  "#0072B2",
}
PIE_ACTION_LABELS = {
    "increase_large":  "Increase large",
    "increase_small":  "Increase small",
    "maintain_demand": "Maintain",
    "decrease_small":  "Decrease small",
    "decrease_large":  "Decrease large",
}

DROUGHT_THRESH = 1075.0   # ft  Tier-1 shortage line

# ---------------------------------------------------------------------------
# rcParams
# ---------------------------------------------------------------------------
rcParams.update({
    "font.family":      "Arial",
    "font.size":        7.5,
    "axes.titlesize":   7.5,
    "axes.labelsize":   7.5,
    "xtick.labelsize":  6.5,
    "ytick.labelsize":  6.5,
    "legend.fontsize":  7.5,
    "axes.spines.top":  False,
    "axes.spines.right":False,
    "xtick.direction":  "out",
    "ytick.direction":  "out",
    "pdf.fonttype":     42,
    "ps.fonttype":      42,
})

SEEDS = [42, 43, 44, 45, 46]
FQL_SEEDS = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def load_sim_logs(pattern_dir_fn, seeds=SEEDS):
    """Load and concatenate simulation_log.csv for given seeds.

    pattern_dir_fn: callable(seed) -> Path to directory
    Returns concatenated DataFrame with a 'seed' column, or None if all missing.
    """
    frames = []
    for s in seeds:
        p = pattern_dir_fn(s) / "simulation_log.csv"
        if not p.exists():
            print(f"  WARNING: missing {p}")
            continue
        df = pd.read_csv(p, encoding='utf-8')
        df['seed'] = s
        frames.append(df)
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


def load_audit_logs(pattern_dir_fn, seeds=SEEDS):
    """Load governance audit CSVs for given seeds.

    pattern_dir_fn: callable(seed) -> Path to directory
    Returns concatenated DataFrame with a 'seed' column, or None if all missing.
    """
    frames = []
    for s in seeds:
        p = pattern_dir_fn(s) / "irrigation_farmer_governance_audit.csv"
        if not p.exists():
            print(f"  WARNING: missing audit {p}")
            continue
        df = pd.read_csv(p, encoding='utf-8-sig')
        df['seed'] = s
        frames.append(df)
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


def correct_actions_with_audit(sim_df, audit_df):
    """Ensure yearly_decision uses the 5-action scheme.

    For REJECTED/REJECTED_FALLBACK rows, the simulation_log records the
    PROPOSED skill, but the executed action was maintain_demand (fallback).
    We overwrite these to maintain_demand so the stacked area shows what
    agents actually executed.

    Returns a copy of sim_df with corrected 'yearly_decision'.
    """
    if audit_df is None:
        return sim_df.copy()

    # Build rejection mask via merge
    rej = audit_df[audit_df['status'].isin(('REJECTED', 'REJECTED_FALLBACK'))][
        ['seed', 'agent_id', 'year']
    ].drop_duplicates()
    rej['_rejected'] = True

    corrected = sim_df.merge(rej, on=['seed', 'agent_id', 'year'], how='left')
    mask_rej = corrected['_rejected'].fillna(False).astype(bool)

    n_rejected = mask_rej.sum()
    total = len(corrected)

    # Rejected proposals -> maintain_demand (executed fallback)
    corrected.loc[mask_rej, 'yearly_decision'] = 'maintain_demand'

    corrected.drop(columns='_rejected', inplace=True)
    print(f"  Action correction: {n_rejected} rejected ({n_rejected/total*100:.1f}%) -> maintain_demand")
    return corrected


# ---------------------------------------------------------------------------
# Panel A helpers
# ---------------------------------------------------------------------------

def compute_stacked_area(df):
    """Compute mean action share per year averaged over agents and seeds.

    Returns DataFrame: index=year, columns=ACTION_ORDER, values=mean share.
    """
    # Fraction per (seed, year)
    counts = (
        df.groupby(['seed', 'year', 'yearly_decision'])
        .size()
        .reset_index(name='n')
    )
    total_per_sy = counts.groupby(['seed', 'year'])['n'].transform('sum')
    counts['share'] = counts['n'] / total_per_sy

    # Mean across seeds
    mean_share = (
        counts.groupby(['year', 'yearly_decision'])['share']
        .mean()
        .unstack(fill_value=0)
    )
    # Ensure all actions present and in order
    for a in ACTION_ORDER:
        if a not in mean_share.columns:
            mean_share[a] = 0.0
    return mean_share[ACTION_ORDER]


def compute_mean_mead(df):
    """Mean Lake Mead level per year, averaged across agents and seeds."""
    return (
        df.groupby(['seed', 'year'])['lake_mead_level']
        .mean()
        .groupby('year')
        .mean()
    )


def compute_mead_band(df):
    """Return (mean, std) of Lake Mead level per year across seeds."""
    per_seed_year = df.groupby(['seed', 'year'])['lake_mead_level'].mean()
    mean = per_seed_year.groupby('year').mean()
    std = per_seed_year.groupby('year').std()
    return mean, std


def get_drought_spans(mead_series, threshold=DROUGHT_THRESH):
    """Return list of (year_start, year_end) drought spans where Mead < threshold."""
    years = sorted(mead_series.index)
    spans = []
    in_drought = False
    start = None
    for y in years:
        if mead_series[y] < threshold:
            if not in_drought:
                in_drought = True
                start = y
        else:
            if in_drought:
                spans.append((start, y - 1))
                in_drought = False
    if in_drought:
        spans.append((start, years[-1]))
    return spans


def draw_stacked_panel(ax, ax2, share_df, mead_mean, fql_mead, title,
                       show_legend=False, show_ylabel_left=True,
                       show_ylabel_right=False, fql_mead_std=None,
                       llm_mead_std=None):
    """Draw one stacked-area sub-panel on ax (left y) and ax2 (right y: Mead)."""
    years = share_df.index.tolist()

    # Stacked area (with optional hatching for rejected-maintain)
    bottoms = np.zeros(len(years))
    for action in ACTION_ORDER:
        vals = share_df[action].values
        hatch = ACTION_HATCHES.get(action, "")
        ax.fill_between(years, bottoms, bottoms + vals,
                        facecolor=ACTION_COLORS[action], linewidth=0, alpha=0.9,
                        hatch=hatch, edgecolor='white' if not hatch else '#888888',
                        label=ACTION_LABELS[action])
        bottoms = bottoms + vals

    ax.set_xlim(1, max(years))
    ax.set_ylim(0, 1)
    ax.set_yticks([0, 0.25, 0.50, 0.75, 1.0])
    if show_ylabel_left:
        ax.set_ylabel("Action share (%)")
    # Display as percentage
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f'{v*100:.0f}'))
    ax.set_xlabel("Year")
    ax.set_title(title, fontweight='bold', pad=3)
    # Fix x-ticks: every 10 years
    ax.set_xticks([1, 10, 20, 30, 40])

    # Mead overlay on right axis
    ax2.plot(years, mead_mean.values, color='black', linewidth=1.2,
             zorder=5, label='LLM agent')
    if llm_mead_std is not None:
        ax2.fill_between(years,
                         mead_mean.values - llm_mead_std.values,
                         mead_mean.values + llm_mead_std.values,
                         color='black', alpha=0.10, zorder=3)
    if fql_mead is not None:
        ax2.plot(fql_mead.index, fql_mead.values, color=C_FQL,
                 linewidth=0.9, linestyle='--', zorder=4, label='Baseline (FQL)')
        if fql_mead_std is not None:
            ax2.fill_between(fql_mead.index,
                             fql_mead.values - fql_mead_std.values,
                             fql_mead.values + fql_mead_std.values,
                             color=C_FQL, alpha=0.15, zorder=3)
    ax2.axhline(DROUGHT_THRESH, color='#CC3333', linewidth=0.8,
                linestyle='--', zorder=6)
    ax2.set_ylim(880, 1240)
    ax2.set_ylabel("Water level (ft)" if show_ylabel_right else "", labelpad=4)
    ax2.tick_params(axis='y', which='both', direction='out')


# ---------------------------------------------------------------------------
# Panel B helpers
# ---------------------------------------------------------------------------

def compute_demand_ratio(df):
    """Demand ratio = total requested / total water_right, per (seed, year)."""
    agg = df.groupby(['seed', 'year']).agg(
        total_request=('request', 'sum'),
        total_wr=('water_right', 'sum')
    ).reset_index()
    agg['demand_ratio'] = agg['total_request'] / agg['total_wr']
    # Mean over years then per seed
    return agg.groupby('seed')['demand_ratio'].mean()


def compute_demand_maf(df):
    """Total water demand in MAF (million acre-feet), per seed (mean over years)."""
    agg = df.groupby(['seed', 'year']).agg(
        total_request=('request', 'sum'),
    ).reset_index()
    # request is in acre-feet; convert to MAF
    agg['demand_maf'] = agg['total_request'] / 1e6
    return agg.groupby('seed')['demand_maf'].mean()


def compute_shortage_years(df, threshold=DROUGHT_THRESH):
    """Count of years where mean Mead < threshold, per seed.

    Seeds with zero shortage years are included as 0 (not dropped).
    """
    all_seeds = df['seed'].unique()
    mead_per_sy = df.groupby(['seed', 'year'])['lake_mead_level'].mean()
    shortage_mask = mead_per_sy < threshold
    counts = (
        mead_per_sy[shortage_mask]
        .groupby('seed')
        .apply(lambda x: x.index.get_level_values('year').nunique())
    )
    return counts.reindex(all_seeds, fill_value=0)


# ---------------------------------------------------------------------------
# Panel C helpers
# ---------------------------------------------------------------------------

WSA_ORDER = ['VH', 'H', 'M', 'L', 'VL']   # top to bottom (rows)
ACA_ORDER = ['VL', 'L', 'M', 'H', 'VH']   # left to right (cols)


def compute_pie_matrix(audit_df):
    """Compute action count distributions for each (WSA, ACA) cell.

    Returns:
      - dict: (wsa, aca) -> dict(action -> count)
      - dict: (wsa, aca) -> total sample count
      - dict: (wsa, aca) -> violation count
    """
    data = {}
    total = {}
    violations = {}
    for wsa in WSA_ORDER:
        for aca in ACA_ORDER:
            mask = (
                (audit_df['construct_WSA_LABEL'] == wsa) &
                (audit_df['construct_ACA_LABEL'] == aca)
            )
            sub = audit_df[mask]
            counts = sub['proposed_skill'].value_counts()
            cell_counts = {a: int(counts.get(a, 0)) for a in PIE_ACTION_ORDER}
            data[(wsa, aca)] = cell_counts
            total[(wsa, aca)] = sum(cell_counts.values())
            violations[(wsa, aca)] = int((sub['status'] != 'APPROVED').sum())
    return data, total, violations


def get_irrigation_pie_panel_configs():
    return [
        {"key": "gov", "title": "Governed LLM", "title_color": C_GOV, "show_ylabel": True, "show_legend": False},
        {"key": "disabled", "title": "Governed LLM (no validator)", "title_color": C_UNGOV, "show_ylabel": False, "show_legend": False},
    ]


def get_irrigation_violation_annotation_style():
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


def get_irrigation_center_count_style():
    return {
        'ha': 'center',
        'va': 'center',
        'fontsize': 6.0,
        'color': 'white',
        'fontweight': 'bold',
        'bbox': {
            'boxstyle': 'round,pad=0.1',
            'facecolor': '#00000055',
            'edgecolor': 'none',
        },
    }


def get_irrigation_pie_text_layout():
    return {
        "aca_label_y": -0.055,
        "title_y": 1.01,
    }


def get_irrigation_violation_badge_layout():
    return {
        "use_figure_overlay": True,
        "x_ratio": 0.965,
        "y_ratio": 0.035,
    }


def get_irrigation_colorbar_config():
    return {
        "orientation": "vertical",
        "label": "Violations",
        "width": 0.008,
        "pad": 0.006,
        "height_ratio": 0.9,
        "y_offset_ratio": 0.05,
    }


def get_irrigation_action_legend_config():
    return {
        "use_figure_legend": True,
        "anchor_x": 0.53,
        "anchor_y": 0.165,
        "ncol": 2,
    }


def create_irrigation_violation_cmap():
    return mcolors.LinearSegmentedColormap.from_list(
        "irr_viols",
        ['#F7F7F7', '#F7D9A6', '#F3A65A', '#D95F02'],
    )


def draw_irrigation_pie_grid(
    fig,
    ax_bg,
    pie_data,
    pie_total,
    pie_violations,
    title,
    title_color,
    show_ylabel=True,
    show_legend=False,
    viol_cmap=None,
    viol_norm=None,
):
    ax_bg.set_axis_off()
    text_layout = get_irrigation_pie_text_layout()
    badge_layout = get_irrigation_violation_badge_layout()

    if pie_data is None:
        ax_bg.text(0.5, 0.5, "No audit data", ha='center', va='center',
                   transform=ax_bg.transAxes, fontsize=8)
        return

    bbox = ax_bg.get_position()

    n_rows = len(WSA_ORDER)
    n_cols = len(ACA_ORDER)

    left_margin = 0.11 if show_ylabel else 0.05
    right_margin = 0.01
    top_margin = 0.12
    bot_margin = 0.01

    cell_w = (1.0 - left_margin - right_margin) / n_cols
    cell_h = (1.0 - top_margin - bot_margin) / n_rows

    if viol_cmap is None:
        viol_cmap = create_irrigation_violation_cmap()
    if viol_norm is None:
        viol_max = max(pie_violations.values()) if pie_violations else 0
        viol_norm = mcolors.Normalize(vmin=0, vmax=max(1, viol_max))

    max_n = max(pie_total.values()) if pie_total else 1
    min_radius = 0.022
    max_radius = 0.040

    for ri, wsa in enumerate(WSA_ORDER):
        for ci, aca in enumerate(ACA_ORDER):
            n = pie_total.get((wsa, aca), 0)
            viol_count = pie_violations.get((wsa, aca), 0)

            cx_ax = left_margin + (ci + 0.5) * cell_w
            cy_ax = (1.0 - top_margin) - (ri + 0.5) * cell_h
            cy_ax_pie = cy_ax + cell_h * 0.06

            cell_bottom = (1.0 - top_margin) - (ri + 1) * cell_h
            cell_left = left_margin + ci * cell_w
            cell_top = (1.0 - top_margin) - ri * cell_h

            if n > 0:
                rect = plt.Rectangle(
                    (cell_left, cell_bottom), cell_w, cell_h,
                    facecolor=viol_cmap(viol_norm(viol_count)) if viol_count > 0 else '#F7F7F7',
                    edgecolor='none',
                    transform=ax_bg.transAxes,
                    zorder=-2,
                )
                ax_bg.add_patch(rect)

            if n == 0:
                ax_bg.text(cx_ax, cell_bottom, "n=0",
                           ha='center', va='bottom',
                           fontsize=6.0, color='#999999',
                           transform=ax_bg.transAxes)
                continue

            cx_fig = bbox.x0 + cx_ax * bbox.width
            cy_fig = bbox.y0 + cy_ax_pie * bbox.height
            r_frac = min_radius + (max_radius - min_radius) * math.sqrt(n / max_n)

            counts = pie_data[(wsa, aca)]
            sizes = [counts[a] for a in PIE_ACTION_ORDER]
            colors = [PIE_ACTION_COLORS[a] for a in PIE_ACTION_ORDER]
            sizes_nonzero = [(s, c) for s, c in zip(sizes, colors) if s > 0]
            if not sizes_nonzero:
                continue
            sz, cl = zip(*sizes_nonzero)

            pie_ax = fig.add_axes([cx_fig - r_frac, cy_fig - r_frac, 2 * r_frac, 2 * r_frac])
            pie_ax.pie(sz, colors=cl, startangle=90,
                       wedgeprops=dict(linewidth=0.3, edgecolor='white'))
            pie_ax.set_aspect('equal')
            pie_ax.text(
                0.5, 0.5, str(n),
                transform=pie_ax.transAxes,
                **get_irrigation_center_count_style(),
            )
            pie_ax.set_axis_off()

            if viol_count > 0:
                fig.text(
                    bbox.x0 + (cell_left + cell_w * badge_layout["x_ratio"]) * bbox.width,
                    bbox.y0 + (cell_top - cell_h * badge_layout["y_ratio"]) * bbox.height,
                    str(viol_count),
                    transform=fig.transFigure,
                    **get_irrigation_violation_annotation_style(),
                )

    for ci, aca in enumerate(ACA_ORDER):
        cx_ax = left_margin + (ci + 0.5) * cell_w
        ax_bg.text(cx_ax, 1.0 - top_margin + 0.02, aca,
                   ha='center', va='bottom', fontsize=8,
                   transform=ax_bg.transAxes)

    if show_ylabel:
        for ri, wsa in enumerate(WSA_ORDER):
            cy_ax = (1.0 - top_margin) - (ri + 0.5) * cell_h
            ax_bg.text(left_margin - 0.02, cy_ax, wsa,
                       ha='right', va='center', fontsize=8,
                       transform=ax_bg.transAxes)
        ax_bg.text(
            left_margin * 0.15,
            bot_margin + (1.0 - top_margin - bot_margin) / 2,
            "Water Shortage Appraisal (WSA)",
            ha='center', va='center', fontsize=8.5, fontweight='bold',
            rotation=90,
            transform=ax_bg.transAxes,
        )

    ax_bg.text(
        left_margin + (1.0 - left_margin - right_margin) / 2,
        text_layout["aca_label_y"],
        "Adaptive Capacity Appraisal (ACA)",
        ha='center', va='center', fontsize=8.5, fontweight='bold',
        transform=ax_bg.transAxes,
    )
    ax_bg.text(
        left_margin + (1.0 - left_margin - right_margin) / 2,
        text_layout["title_y"],
        title,
        ha='center', va='bottom', fontsize=8.5, fontweight='bold',
        color=title_color,
        transform=ax_bg.transAxes,
    )

    for ri in range(n_rows + 1):
        cy = (1.0 - top_margin) - ri * cell_h
        ax_bg.plot([left_margin, 1.0 - right_margin], [cy, cy],
                   color='#CCCCCC', linewidth=0.4,
                   transform=ax_bg.transAxes, zorder=0)
    for ci in range(n_cols + 1):
        cx = left_margin + ci * cell_w
        ax_bg.plot([cx, cx], [bot_margin, 1.0 - top_margin],
                   color='#CCCCCC', linewidth=0.4,
                   transform=ax_bg.transAxes, zorder=0)

# ---------------------------------------------------------------------------
# Panel D helpers
# ---------------------------------------------------------------------------

def compute_ehe_per_seed(df, n_actions=5):
    """Normalized Shannon entropy per seed (aggregate over all years).

    Uses the 5-action scheme. Returns DataFrame with columns: [seed, ehe]
    """
    tmp = df.copy()
    rows = []
    for seed, sdf in tmp.groupby('seed'):
        counts = sdf['yearly_decision'].value_counts()
        probs = counts / counts.sum()
        entropy = -sum(p * math.log2(p) for p in probs if p > 0)
        ehe = entropy / math.log2(n_actions)
        rows.append({'seed': seed, 'ehe': ehe})
    return pd.DataFrame(rows)


def compute_ibr_per_seed(df):
    """IBR = fraction of high-scarcity (WSA=H or VH) decisions that propose
    increase_large or increase_small. One value per seed.

    Uses corrected actions: rejected proposals become maintain_demand, so only
    APPROVED increases count as irrational.
    Returns DataFrame with columns: [seed, ibr]
    """
    tmp = df.copy()
    rows = []
    for seed, sdf in tmp.groupby('seed'):
        high_wsa = sdf[sdf['wsa_label'].isin(['H', 'VH'])]
        if len(high_wsa) == 0:
            ibr = 0.0
        else:
            irrational = high_wsa['yearly_decision'].isin(
                ['increase_large', 'increase_small']
            ).sum()
            ibr = irrational / len(high_wsa)
        rows.append({'seed': seed, 'ibr': ibr})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main figure builder
# ---------------------------------------------------------------------------

def build_figure():
    print("Loading data...")

    # --- Data directories (prefer v21 for governed, fall back to v20) ---
    def gov_dir_fn(s):
        v21 = RESULTS / f"production_v21_42yr_seed{s}"
        if (v21 / "simulation_log.csv").exists():
            print(f"  governed seed{s}: v21")
            return v21
        print(f"  governed seed{s}: v20 (fallback)")
        return RESULTS / f"production_v20_42yr_seed{s}"
    def ungov_dir_fn(s):
        v21 = RESULTS / f"ungoverned_v21_42yr_seed{s}"
        if (v21 / "simulation_log.csv").exists():
            print(f"  no-validator seed{s}: v21")
            return v21
        print(f"  no-validator seed{s}: v20 (fallback)")
        return RESULTS / f"ungoverned_v20_42yr_seed{s}"

    # --- Governed ---
    gov_df = load_sim_logs(gov_dir_fn)
    if gov_df is None:
        raise FileNotFoundError("No governed simulation logs found.")

    # --- LLM (no validator) ---
    ungov_df = load_sim_logs(ungov_dir_fn)
    if ungov_df is None:
        raise FileNotFoundError("No LLM (no validator) simulation logs found.")

    # --- FQL baseline ---
    fql_df = load_sim_logs(lambda s: RESULTS / "fql_raw" / f"seed{s}", seeds=FQL_SEEDS)

    # --- Audit traces (for action correction + pie matrix) ---
    gov_audit    = load_audit_logs(gov_dir_fn)
    ungov_audit  = load_audit_logs(ungov_dir_fn)

    # --- Correct yearly_decision: REJECTED -> maintain_demand ---
    print("Correcting actions using audit traces...")
    gov_df    = correct_actions_with_audit(gov_df, gov_audit)
    ungov_df  = correct_actions_with_audit(ungov_df, ungov_audit)

    # --- Map FQL actions to 6-action scheme for stacked area ---
    if fql_df is not None:
        fql_action_map = {
            'increase_demand': 'increase_large',
            'decrease_demand': 'decrease_large',
            'maintain_demand': 'maintain_demand',
        }
        fql_df['yearly_decision'] = fql_df['yearly_decision'].map(fql_action_map).fillna('maintain_demand')
        print(f"  FQL action mapping applied: {fql_df['yearly_decision'].value_counts().to_dict()}")

    print("Computing derived quantities...")

    # Stacked area - all 3 conditions
    gov_share   = compute_stacked_area(gov_df)
    ungov_share = compute_stacked_area(ungov_df)
    fql_share   = compute_stacked_area(fql_df) if fql_df is not None else None

    gov_mead   = compute_mean_mead(gov_df)
    ungov_mead = compute_mean_mead(ungov_df)
    fql_mead   = compute_mean_mead(fql_df) if fql_df is not None else None
    fql_mead_std = compute_mead_band(fql_df)[1] if fql_df is not None else None
    gov_mead_std   = compute_mead_band(gov_df)[1]
    ungov_mead_std = compute_mead_band(ungov_df)[1]

    # Bottom-row pie matrices use proposed_skill from single seed (seed 42)
    # for cleaner n values (78 agents x 42 years = 3,276 decisions)
    pie_gov_data = pie_gov_total = pie_gov_violations = None
    if gov_audit is not None:
        pie_audit_single = gov_audit[gov_audit['seed'] == 42]
        pie_gov_data, pie_gov_total, pie_gov_violations = compute_pie_matrix(pie_audit_single)
    pie_ungov_data = pie_ungov_total = pie_ungov_violations = None
    if ungov_audit is not None:
        pie_audit_single = ungov_audit[ungov_audit['seed'] == 42]
        pie_ungov_data, pie_ungov_total, pie_ungov_violations = compute_pie_matrix(pie_audit_single)


    # -----------------------------------------------------------------------
    # Figure layout - (a) full-width top, legend, then (b)(c)(d) each on own row
    # -----------------------------------------------------------------------
    print("Building figure...")
    fig = plt.figure(figsize=(7.09, 7.6))

    # Outer GridSpec: 3 rows
    #   row 0: panel (a) - 3 stacked area sub-panels (full width)
    #   row 1: legend strip
    #   row 2: panels (b) + (c) side by side
    outer = gridspec.GridSpec(
        3, 1, figure=fig,
        hspace=0.18,
        top=0.92, bottom=0.03, left=0.10, right=0.95,
        height_ratios=[0.80, 0.01, 1.05],
    )

    # Panel (a): 2 side-by-side stacked areas - Governed LLM | Governed LLM (no validator)
    # FQL baseline overlaid as dashed Mead line in both panels
    a_gs = gridspec.GridSpecFromSubplotSpec(
        1, 2, subplot_spec=outer[0],
        wspace=0.10,
    )

    ax_a_gov  = fig.add_subplot(a_gs[0])
    ax_a_gov2 = ax_a_gov.twinx()
    ax_a_nv   = fig.add_subplot(a_gs[1], sharey=ax_a_gov)
    ax_a_nv2  = ax_a_nv.twinx()

    # Row 2: (b) scatter + (c) pie matrix side by side
    bc_gs = gridspec.GridSpecFromSubplotSpec(
        1, 2, subplot_spec=outer[2],
        wspace=0.10,
        width_ratios=[1.0, 1.0],
    )

    ax_b1 = fig.add_subplot(bc_gs[0])
    ax_b2 = fig.add_subplot(bc_gs[1])

    # -----------------------------------------------------------------------
    # Panel (a) - 3 stacked area sub-panels
    # -----------------------------------------------------------------------
    draw_stacked_panel(
        ax_a_gov, ax_a_gov2,
        gov_share, gov_mead, fql_mead,
        title="Governed LLM",
        show_ylabel_left=True,
        show_ylabel_right=False,
        fql_mead_std=fql_mead_std,
        llm_mead_std=gov_mead_std,
    )
    draw_stacked_panel(
        ax_a_nv, ax_a_nv2,
        ungov_share, ungov_mead, fql_mead,
        title="Governed LLM (no validator)",
        show_ylabel_left=False,
        show_ylabel_right=True,
        fql_mead_std=fql_mead_std,
        llm_mead_std=ungov_mead_std,
    )
    ax_a_nv.tick_params(labelleft=False)
    ax_a_nv.set_ylabel("")

    # Twin axis cleanup
    for tw in [ax_a_gov2, ax_a_nv2]:
        tw.spines['top'].set_visible(False)
    # Only show Mead y-axis label + ticks on rightmost panel
    ax_a_gov2.tick_params(labelright=False)

    # Shared action legend inside no-validator panel (bottom area)
    action_handles = []
    for a in ACTION_ORDER:
        hatch = ACTION_HATCHES.get(a, "")
        action_handles.append(
            mpatches.Patch(facecolor=ACTION_COLORS[a], label=ACTION_LABELS[a],
                           hatch=hatch,
                           edgecolor='#888888' if hatch else 'white',
                           linewidth=0.4)
        )
    mead_handle  = plt.Line2D([0], [0], color='black', linewidth=1.2, label='LLM agent')
    fql_handle   = plt.Line2D([0], [0], color=C_FQL,  linewidth=0.9, linestyle='--', label='Baseline (FQL)')
    tier1_handle = plt.Line2D([0], [0], color='#CC3333', linewidth=0.8, linestyle='--', label='Tier 1 (1,075 ft)')

    all_handles = action_handles + [mead_handle, fql_handle, tier1_handle]
    # Place legend above panel (a) using the figure-level legend
    fig.legend(
        handles=all_handles,
        loc='upper center',
        bbox_to_anchor=(0.52, 1.00),
        ncol=4,
        fontsize=6.0,
        frameon=True,
        framealpha=0.90,
        facecolor='white',
        edgecolor='#CCCCCC',
        handlelength=0.9,
        handletextpad=0.3,
        columnspacing=0.5,
        borderpad=0.3,
    )
    # Hide the dedicated legend strip row (still exists in gridspec but empty)
    ax_leg = fig.add_subplot(outer[1])
    ax_leg.axis('off')

    pie_panels = {
        "gov": (pie_gov_data, pie_gov_total, pie_gov_violations),
        "disabled": (pie_ungov_data, pie_ungov_total, pie_ungov_violations),
    }
    all_violation_counts = []
    for _, _, pviol in pie_panels.values():
        if pviol:
            all_violation_counts.extend(pviol.values())
    viol_cmap = create_irrigation_violation_cmap()
    viol_norm = mcolors.Normalize(vmin=0, vmax=max(1, max(all_violation_counts) if all_violation_counts else 0))
    for ax, cfg in zip([ax_b1, ax_b2], get_irrigation_pie_panel_configs()):
        pdata, ptotal, pviol = pie_panels[cfg["key"]]
        draw_irrigation_pie_grid(
            fig, ax, pdata, ptotal, pviol,
            title=cfg["title"],
            title_color=cfg["title_color"],
            show_ylabel=cfg["show_ylabel"],
            show_legend=cfg["show_legend"],
            viol_cmap=viol_cmap,
            viol_norm=viol_norm,
        )

    pos_b2 = ax_b2.get_position()
    cb_cfg = get_irrigation_colorbar_config()
    ax_cb = fig.add_axes([
        pos_b2.x1 + cb_cfg["pad"],
        pos_b2.y0 + pos_b2.height * cb_cfg["y_offset_ratio"],
        cb_cfg["width"],
        pos_b2.height * cb_cfg["height_ratio"],
    ])
    cb = ColorbarBase(ax_cb, cmap=viol_cmap, norm=viol_norm, orientation=cb_cfg["orientation"])
    cb.set_label(cb_cfg["label"], fontsize=7.0, labelpad=2)
    cb.ax.tick_params(labelsize=6.5)

    legend_cfg = get_irrigation_action_legend_config()
    pie_legend_handles = [
        mpatches.Patch(facecolor=PIE_ACTION_COLORS[a], label=PIE_ACTION_LABELS[a])
        for a in PIE_ACTION_ORDER
    ]
    fig.legend(
        handles=pie_legend_handles,
        loc='upper center',
        bbox_to_anchor=(legend_cfg["anchor_x"], legend_cfg["anchor_y"]),
        ncol=legend_cfg["ncol"],
        fontsize=6.5,
        frameon=False,
        handlelength=0.9,
        handletextpad=0.3,
        columnspacing=0.5,
        labelspacing=0.25,
    )

    label_kw = dict(fontsize=8, fontweight='bold', va='top', ha='left',
                    transform=fig.transFigure)
    bbox_a = ax_a_gov.get_position()
    fig.text(bbox_a.x0 - 0.06, bbox_a.y1 + 0.01, 'a', **label_kw)
    bbox_b = ax_b1.get_position()
    fig.text(bbox_b.x0 - 0.04, bbox_b.y1 + 0.01, 'b', **label_kw)

    for ext in ('png', 'pdf'):
        out_path = OUT_DIR / f"Fig2_irrigation_case.{ext}"
        fig.savefig(str(out_path), dpi=300, bbox_inches='tight')
        print(f"Saved: {out_path}")

    plt.close(fig)
    print("Done.")
    return


if __name__ == "__main__":
    build_figure()
