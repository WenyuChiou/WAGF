"""
Generate Overall Adaptation Matrix for SI - All 6 Models × 3 Groups
For WRR Paper Supporting Information

Models: gemma3 (4b, 12b, 27b) + ministral3 (3b, 8b, 14b)
Groups: A (Baseline), B (Govern+Window), C (Govern+Human Centric)
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = REPO_ROOT / "examples" / "single_agent" / "results" / "JOH_FINAL"
OUTPUT_DIR = REPO_ROOT / "paper"

# All 6 models
MODELS = ["gemma3_4b", "gemma3_12b", "gemma3_27b", "ministral3_3b", "ministral3_8b", "ministral3_14b"]
MODEL_LABELS = {
    "gemma3_4b": "Gemma3\n4B",
    "gemma3_12b": "Gemma3\n12B",
    "gemma3_27b": "Gemma3\n27B",
    "ministral3_3b": "Ministral3\n3B",
    "ministral3_8b": "Ministral3\n8B",
    "ministral3_14b": "Ministral3\n14B",
}

GROUPS = ["Group_A", "Group_B", "Group_C"]
GROUP_TITLES = {
    "Group_A": "Group A\n(Ungoverned)",
    "Group_B": "Group B\n(SAGE + Window Mem)",
    "Group_C": "Group C\n(SAGE + Human Centric)"
}

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Categories & Colors
CATEGORIES = [
    "Do Nothing",
    "Insurance",
    "Elevation",
    "Insurance + Elevation",
    "Relocate (Departing)"
]

TAB10 = plt.get_cmap("tab10").colors
COLOR_MAP = {
    "Do Nothing": TAB10[0],       # Blue
    "Insurance": TAB10[1],        # Orange
    "Elevation": TAB10[2],        # Green
    "Insurance + Elevation": TAB10[3], # Red
    "Relocate (Departing)": TAB10[4]   # Purple
}

def clean_decision_detailed(state_str):
    """Map raw state string to one of the 5 categories."""
    s = str(state_str).lower()

    if "relocate" in s:
        return "Relocate (Departing)"

    has_ins = "insurance" in s or "buy_insurance" in s
    has_ele = "elevation" in s or "elevate" in s or "elevate_house" in s

    if "both" in s and "insurance" in s and "elevation" in s:
        return "Insurance + Elevation"

    if has_ins and has_ele:
        return "Insurance + Elevation"
    elif has_ins:
        return "Insurance"
    elif has_ele:
        return "Elevation"

    return "Do Nothing"

def get_year_detailed_distribution(df, year):
    """Returns counts for 5 categories for a specific year."""
    year_data = df[df['year'] == year]
    if year_data.empty:
        return [0]*5

    states = year_data['norm_raw'].apply(clean_decision_detailed)
    counts = states.value_counts()

    res = []
    for cat in CATEGORIES:
        res.append(counts.get(cat, 0))
    return res

def load_all_adaptation_data_detailed():
    """Load adaptation data for all models and groups."""
    data_map = {}

    for model in MODELS:
        for group in GROUPS:
            csv_path = RESULTS_DIR / model / group / "Run_1" / "simulation_log.csv"

            if not csv_path.exists():
                print(f"  [SKIP] Not found: {csv_path}")
                data_map[(model, group)] = None
                continue

            try:
                df = pd.read_csv(csv_path)

                # Determine state column
                if 'cumulative_state' in df.columns:
                    state_col = 'cumulative_state'
                elif 'decision' in df.columns:
                    state_col = 'decision'
                else:
                    data_map[(model, group)] = None
                    continue

                # Population Attrition Logic
                df['temp_state_check'] = df[state_col].astype(str).str.lower()

                reloc_rows = df[df['temp_state_check'].str.contains("relocate")]
                if not reloc_rows.empty:
                    first_reloc = reloc_rows.groupby('agent_id')['year'].min().reset_index()
                    first_reloc.columns = ['agent_id', 'first_reloc_year']
                    df = df.merge(first_reloc, on='agent_id', how='left')
                    df = df[df['first_reloc_year'].isna() | (df['year'] <= df['first_reloc_year'])]

                df['norm_raw'] = df[state_col].astype(str)

                years = range(1, 11)
                records = []
                for y in years:
                    counts = get_year_detailed_distribution(df, y)
                    records.append(counts)

                df_res = pd.DataFrame(records, columns=CATEGORIES, index=years)
                data_map[(model, group)] = df_res
                print(f"  [OK] Loaded: {model}/{group}")

            except Exception as e:
                print(f"  [ERROR] {csv_path}: {e}")
                data_map[(model, group)] = None

    return data_map

def plot_adaptation_matrix_6x3(data_map):
    """Create 3 rows (groups) × 6 columns (models) adaptation matrix."""
    nrows = len(GROUPS)  # 3
    ncols = len(MODELS)  # 6

    sns.set_theme(style="whitegrid", context="paper", font_scale=1.0)
    plt.rcParams['font.family'] = 'serif'
    plt.rcParams['font.serif'] = ['Times New Roman'] + plt.rcParams['font.serif']

    fig, axes = plt.subplots(nrows, ncols, figsize=(3.5*ncols, 3.5*nrows), sharex=True, sharey=True)

    group_ann = ['(a)', '(b)', '(c)']

    for row_idx, group in enumerate(GROUPS):
        for col_idx, model in enumerate(MODELS):
            ax = axes[row_idx][col_idx]
            df = data_map.get((model, group))
            model_label = MODEL_LABELS[model]

            # Row labels (left side)
            if col_idx == 0:
                ax.text(-0.45, 1.1, group_ann[row_idx], transform=ax.transAxes,
                        fontsize=20, fontweight='bold', va='top', ha='right', family='serif')
                ax.set_ylabel(GROUP_TITLES.get(group, group), fontsize=12, fontweight='bold',
                             labelpad=15, family='serif')

            # Column labels (top)
            if row_idx == 0:
                ax.set_title(model_label, fontsize=14, fontweight='bold', pad=15, family='serif')

            ax.set_xlim(-0.5, 9.5)
            ax.set_xticks(range(0, 10))

            if df is not None and not df.empty:
                colors = [COLOR_MAP[c] for c in CATEGORIES]
                df.plot(kind='bar', stacked=True, color=colors, ax=ax, width=0.85, legend=False)
                ax.set_ylim(0, 105)
                ax.tick_params(axis='y', labelsize=10)
                ax.grid(axis='y', linestyle='--', alpha=0.5)
            else:
                ax.set_facecolor("#f5f5f5")
                ax.text(0.5, 0.5, "No Data", transform=ax.transAxes,
                       ha='center', va='center', fontsize=12, color='gray')
                ax.set_xticks([])
                ax.set_yticks([])

            # X axis labels (bottom row only)
            if row_idx == nrows - 1:
                ax.set_xlabel("Year", fontsize=12, fontweight='bold', family='serif')
                ax.set_xticks(range(10))
                ax.set_xticklabels(range(1, 11), rotation=0, size=10, family='serif')
            else:
                ax.set_xlabel("")
                ax.set_xticks(range(10))
                ax.set_xticklabels([])

    # Legend
    ABBR_LABELS = {
        "Do Nothing": "DN (Do Nothing)",
        "Insurance": "FI (Flood Insurance)",
        "Elevation": "HE (House Elevation)",
        "Insurance + Elevation": "HE + FI (Both)",
        "Relocate (Departing)": "RL (Relocate)"
    }

    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor=COLOR_MAP[c], label=ABBR_LABELS[c]) for c in CATEGORIES]

    # Place legend in top-left subplot
    leg_ax = axes[0][0]
    leg = leg_ax.legend(handles=legend_elements, loc='upper right', fontsize=8, frameon=True,
                        title="Adaptation State", borderpad=0.3, labelspacing=0.1)
    plt.setp(leg.get_title(), fontsize=9, fontweight='bold', family='serif')

    plt.tight_layout(rect=[0, 0, 1, 0.98])

    output_path = OUTPUT_DIR / "SI_Figure_Adaptation_Matrix_6x3.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"\nSaved: {output_path}")
    return output_path

def plot_adaptation_matrix_by_family(data_map):
    """Create separate plots for each model family (Gemma3 and Ministral3)."""

    families = {
        "gemma3": ["gemma3_4b", "gemma3_12b", "gemma3_27b"],
        "ministral3": ["ministral3_3b", "ministral3_8b", "ministral3_14b"]
    }

    for family_name, models in families.items():
        nrows = len(GROUPS)  # 3
        ncols = len(models)  # 3

        sns.set_theme(style="whitegrid", context="paper", font_scale=1.1)
        plt.rcParams['font.family'] = 'serif'
        plt.rcParams['font.serif'] = ['Times New Roman'] + plt.rcParams['font.serif']

        fig, axes = plt.subplots(nrows, ncols, figsize=(5*ncols, 4*nrows), sharex=True, sharey=True)

        group_ann = ['(a)', '(b)', '(c)']

        for row_idx, group in enumerate(GROUPS):
            for col_idx, model in enumerate(models):
                ax = axes[row_idx][col_idx]
                df = data_map.get((model, group))
                model_label = MODEL_LABELS[model]

                if col_idx == 0:
                    ax.text(-0.35, 1.1, group_ann[row_idx], transform=ax.transAxes,
                            fontsize=24, fontweight='bold', va='top', ha='right', family='serif')
                    ax.set_ylabel(GROUP_TITLES.get(group, group), fontsize=16, fontweight='bold',
                                 labelpad=18, family='serif')

                if row_idx == 0:
                    ax.set_title(model_label, fontsize=18, fontweight='bold', pad=20, family='serif')

                ax.set_xlim(-0.5, 9.5)
                ax.set_xticks(range(0, 10))

                if df is not None and not df.empty:
                    colors = [COLOR_MAP[c] for c in CATEGORIES]
                    df.plot(kind='bar', stacked=True, color=colors, ax=ax, width=0.85, legend=False)
                    ax.set_ylim(0, 105)
                    ax.tick_params(axis='y', labelsize=12)
                    ax.grid(axis='y', linestyle='--', alpha=0.5)
                else:
                    ax.set_facecolor("#f5f5f5")
                    ax.text(0.5, 0.5, "No Data", transform=ax.transAxes,
                           ha='center', va='center', fontsize=14, color='gray')
                    ax.set_xticks([])
                    ax.set_yticks([])

                if row_idx == nrows - 1:
                    ax.set_xlabel("Year", fontsize=16, fontweight='bold', family='serif')
                    ax.set_xticks(range(10))
                    ax.set_xticklabels(range(1, 11), rotation=0, size=12, family='serif')
                else:
                    ax.set_xlabel("")
                    ax.set_xticks(range(10))
                    ax.set_xticklabels([])

        # Legend
        ABBR_LABELS = {
            "Do Nothing": "DN",
            "Insurance": "FI",
            "Elevation": "HE",
            "Insurance + Elevation": "HE + FI",
            "Relocate (Departing)": "RL"
        }

        from matplotlib.patches import Patch
        legend_elements = [Patch(facecolor=COLOR_MAP[c], label=ABBR_LABELS[c]) for c in CATEGORIES]

        leg_ax = axes[0][0]
        leg = leg_ax.legend(handles=legend_elements, loc='upper right', fontsize=11, frameon=True,
                            title="State", borderpad=0.4, labelspacing=0.15)
        plt.setp(leg.get_title(), fontsize=12, fontweight='bold', family='serif')

        plt.tight_layout(rect=[0, 0, 1, 0.98])

        output_path = OUTPUT_DIR / f"SI_Figure_Adaptation_{family_name.capitalize()}_3x3.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"Saved: {output_path}")

if __name__ == "__main__":
    print("=" * 60)
    print("Generating SI Adaptation Matrices (All 6 Models × 3 Groups)")
    print("=" * 60)

    print("\nLoading data...")
    data = load_all_adaptation_data_detailed()

    print("\n" + "=" * 60)
    print("Generating plots...")
    print("=" * 60)

    # Generate combined 6×3 matrix
    print("\n1. Creating 6×3 combined matrix...")
    plot_adaptation_matrix_6x3(data)

    # Generate separate plots by model family
    print("\n2. Creating separate family matrices (3×3 each)...")
    plot_adaptation_matrix_by_family(data)

    print("\n" + "=" * 60)
    print("Done! All figures saved to paper/ directory.")
    print("=" * 60)
