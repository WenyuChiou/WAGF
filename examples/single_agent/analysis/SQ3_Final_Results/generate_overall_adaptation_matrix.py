
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import glob
import os
import re
import numpy as np
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================
# Resolve based on script location: analysis/SQ3_Final_Results/ -> ../../../results/JOH_FINAL
RESULTS_DIR = Path(__file__).parent.parent.parent / "results" / "JOH_FINAL"

# Filter to only DeepSeek series as requested
MODELS = ["deepseek_r1_1_5b", "deepseek_r1_8b", "deepseek_r1_14b", "deepseek_r1_32b"]
MODEL_LABELS = {
    "deepseek_r1_1_5b": "1.5B (DeepSeek)",
    "deepseek_r1_8b": "8B (DeepSeek)",
    "deepseek_r1_14b": "14B (DeepSeek)",
    "deepseek_r1_32b": "32B (DeepSeek)"
}
GROUPS = ["Group_A", "Group_B", "Group_C"]
GROUP_TITLES = {
    "Group_A": "Group A\n(Baseline)",
    "Group_B": "Group B\n(Govern + Window Mem)", 
    "Group_C": "Group C\n(Govern + Human Centric)"
}
FIGURE_OUTPUT = Path(__file__).parent # Absolute path to analysis/ folder

os.makedirs(FIGURE_OUTPUT, exist_ok=True)
sns.set_theme(style="whitegrid", context="paper", font_scale=1.1)
plt.rcParams['font.family'] = 'sans-serif'

# Categories & Colors (Matching plot_results.py / comparison_results.png)
CATEGORIES = [
    "Do Nothing",
    "Insurance",
    "Elevation",
    "Insurance + Elevation",
    "Relocate (Departing)"
]

# Matplotlib Tab10 Colors manually mapped
# 0: Blue, 1: Orange, 2: Green, 3: Red, 4: Purple
TAB10 = plt.get_cmap("tab10").colors
COLOR_MAP = {
    "Do Nothing": TAB10[0],       # Blue
    "Insurance": TAB10[1],        # Orange
    "Elevation": TAB10[2],        # Green
    "Insurance + Elevation": TAB10[3], # Red
    "Relocate (Departing)": TAB10[4]   # Purple
}

def clean_decision_detailed(state_str):
    """
    Map raw state string to one of the 5 categories.
    Prioritize Relocate > Both > Single > Do Nothing.
    """
    s = str(state_str).lower()
    
    if "relocate" in s:
        return "Relocate (Departing)"
    
    has_ins = "insurance" in s or "buy_insurance" in s
    has_ele = "elevation" in s or "elevate" in s or "elevate_house" in s
    
    # Check for "Both" usually explicit in cumulative_state
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
    """
    Returns counts for 5 categories for a specific year.
    """
    year_data = df[df['year'] == year]
    if year_data.empty: return [0]*5
    
    total = len(year_data)
    
    # 1. Map each agent's state
    # We use 'norm_raw' column created in load function
    states = year_data['norm_raw'].apply(clean_decision_detailed)
    
    counts = states.value_counts()
    
    # Ensure all categories present in correct order
    res = []
    for cat in CATEGORIES:
        res.append(counts.get(cat, 0))
        
    return res

def load_all_adaptation_data_detailed():
    data_map = {}
    
    for model in MODELS:
        for group in GROUPS:
            csv_path = f"{RESULTS_DIR}/{model}/{group}/Run_1/simulation_log.csv"
            
            if not os.path.exists(csv_path):
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
                
                # --- Population Attrition Logic (Match plot_results.py) ---
                # 1. Standardize state column for checking 'relocate'
                df['temp_state_check'] = df[state_col].astype(str).str.lower()
                
                # 2. Identify FIRST year each agent relocated
                reloc_rows = df[df['temp_state_check'].str.contains("relocate")]
                if not reloc_rows.empty:
                    first_reloc = reloc_rows.groupby('agent_id')['year'].min().reset_index()
                    first_reloc.columns = ['agent_id', 'first_reloc_year']
                    
                    # 3. Merge and Filter
                    df = df.merge(first_reloc, on='agent_id', how='left')
                    # Keep if never relocated OR current year <= first relocation year
                    df = df[df['first_reloc_year'].isna() | (df['year'] <= df['first_reloc_year'])]
                
                # 4. Now process year by year
                df['norm_raw'] = df[state_col].astype(str)
                
                years = range(1, 11)
                records = []
                for y in years:
                    counts = get_year_detailed_distribution(df, y)
                    records.append(counts)
                
                # DataFrame: Index=Year, Cols=Categories
                df_res = pd.DataFrame(records, columns=CATEGORIES, index=years)
                data_map[(model, group)] = df_res
                
            except Exception as e:
                print(f"Error parse {csv_path}: {e}")
                data_map[(model, group)] = None
                
    return data_map

def plot_dynamic_matrix_stacked_bar(data_map):
    # Swap axes as requested: Models as Columns, Groups as Rows
    # This ensures "xlabel" of the grid plots corresponds to model names implicitly
    nrows = len(GROUPS)
    ncols = len(MODELS)
    
    fig, axes = plt.subplots(nrows, ncols, figsize=(5*ncols, 4*nrows), sharex=True, sharey=True)
    
    for row_idx, group in enumerate(GROUPS):
        for col_idx, model in enumerate(MODELS):
            ax = axes[row_idx][col_idx]
            df = data_map.get((model, group))
            model_label = MODEL_LABELS[model]
            
            # Group Titles as Row Labels (Left Side)
            if col_idx == 0:
                ax.set_ylabel(GROUP_TITLES.get(group, group), fontsize=13, fontweight='bold', labelpad=15)
            
            # Model Labels as Column Titles (Top Row)
            if row_idx == 0:
                ax.set_title(model_label, fontsize=15, fontweight='bold')
            
            # FIX: Properly set x-axis limits and ticks for pandas bar plot (0-indexed positions)
            # This ensures Year 1 (pos 0) and Year 10 (pos 9) are fully visible
            ax.set_xlim(-0.5, 9.5)
            ax.set_xticks(range(0, 10))

            if df is not None and not df.empty:
                colors = [COLOR_MAP[c] for c in CATEGORIES]
                df.plot(kind='bar', stacked=True, color=colors, ax=ax, width=0.85, legend=False)
                
                ax.set_ylim(0, 105) 
                ax.grid(axis='y', linestyle='--', alpha=0.5)
            else:
                ax.text(0.5, 0.5, "Pending Data", 
                        ha='center', va='center', transform=ax.transAxes, color='gray', fontsize=12)
                ax.set_facecolor("#f9f9f9")

            # X Label (Year 1-10 labels)
            if row_idx == nrows - 1:
                ax.set_xlabel("Year")
                ax.set_xticklabels(range(1, 11), rotation=0)
            else:
                ax.set_xlabel("")
                ax.set_xticklabels([])

    # Legend
    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor=COLOR_MAP[c], label=c) for c in CATEGORIES]
    
    fig.legend(handles=legend_elements, loc='upper center', bbox_to_anchor=(0.5, 1.01), 
               ncol=5, fontsize=12, frameon=False, title="Adaptation State")

    plt.suptitle("Figure: Overall Adaptation Strategy Evolution (10 Years)", fontsize=22, fontweight='bold', y=1.05)
    plt.tight_layout()
    plt.savefig(f"{FIGURE_OUTPUT}/overall_adaptation_by_year.png", dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Generated {nrows}x{ncols} Adaptation Matrix (Stacked Bar).")

if __name__ == "__main__":
    print("Generating Overall Adaptation Matrix (Detailed - DeepSeek Only)...")
    data = load_all_adaptation_data_detailed()
    plot_dynamic_matrix_stacked_bar(data)
    print("Done.")
