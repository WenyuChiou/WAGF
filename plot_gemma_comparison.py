import pandas as pd
import matplotlib.pyplot as plt
import os
import glob
import numpy as np

# --- Configuration ---
# Actual paths for Old (Warning Mode) - existing
OLD_PATH = r"C:\Users\wenyu\OneDrive - Lehigh University\Desktop\Lehigh\NSF-project\ABM\LLM ABM\experiments\2_model_comparison\results\Gemma_3_4B\flood_adaptation_simulation_log.csv"

# Search paths for New (Error Mode)
NEW_BASE_DIR = "results"
NEW_PATTERNS = [
    "gemma_hardened/gemma3_4b/simulation_log.csv", 
    "hardened_benchmark/gemma3_4b/simulation_log.csv"
]

ALL_CATEGORIES = [
    "Do Nothing",
    "Only Flood Insurance",
    "Only House Elevation",
    "Both Flood Insurance and House Elevation",
    "Relocate"
]

# Matplotlib Colors
prop_cycle = plt.rcParams['axes.prop_cycle']
mpl_colors = prop_cycle.by_key()['color']
COLOR_MAP = {
    "Do Nothing": mpl_colors[0],       # Blue
    "Only Flood Insurance": mpl_colors[1], # Orange
    "Only House Elevation": mpl_colors[2], # Green
    "Both Flood Insurance and House Elevation": mpl_colors[3], # Red
    "Relocate": mpl_colors[4]          # Purple
}

def process_flow_data(df):
    """ Standard processing: Relocate counts once, then leaves. """
    if df is None or df.empty: return None
    
    # Normalize decision
    if 'decision' in df.columns:
        df['decision'] = df['decision'].astype(str).str.replace('nothing', 'Nothing', case=False)
    
    # Ensure year column is int
    df['year'] = df['year'].astype(int)
    
    # First Relocation
    relocated_first_year = df[df['decision'] == 'Relocate'].groupby('agent_id')['year'].min().reset_index()
    relocated_first_year.columns = ['agent_id', 'first_reloc_year']
    df = df.merge(relocated_first_year, on='agent_id', how='left')
    df = df[df['first_reloc_year'].isna() | (df['year'] <= df['first_reloc_year'])]
    
    pivot = df.pivot_table(index='year', columns='decision', aggfunc='size', fill_value=0)
    
    # Fill missing cols
    for c in ALL_CATEGORIES:
        if c not in pivot.columns:
            pivot[c] = 0
    
    # Ensure all years 1-10 are present if data exists
    if not pivot.empty:
        max_year = pivot.index.max()
        # If we have at least some data, try to show up to year 10 logic or max year
        target_max = max(10, max_year)
        full_years = range(1, target_max + 1)
        pivot = pivot.reindex(full_years, fill_value=0)
            
    return pivot[ALL_CATEGORIES]

def find_new_path():
    for pattern in NEW_PATTERNS:
        path = os.path.join(NEW_BASE_DIR, pattern)
        candidates = glob.glob(path, recursive=True)
        if candidates: return candidates[0]
    return None

def main():
    fig, axes = plt.subplots(1, 2, figsize=(16, 7), sharey=True)
    
    # --- Plot Old (Warning Mode) ---
    df_old = None
    if os.path.exists(OLD_PATH):
        df_old = pd.read_csv(OLD_PATH)
    
    pivot_old = process_flow_data(df_old)
    if pivot_old is not None:
        colors = [COLOR_MAP[c] for c in pivot_old.columns]
        pivot_old.plot(kind='bar', stacked=True, color=colors, ax=axes[0], legend=False, width=0.85)
        axes[0].set_title("Gemma 3 4B\n(Before: Warning Mode)", fontsize=14, fontweight='bold')
        axes[0].set_ylabel("Number of Agents", fontsize=12)
    else:
        axes[0].text(0.5, 0.5, "Old Data Not Found", ha='center')

    # --- Plot New (Error Mode) ---
    new_path = find_new_path()
    print(f"Using New Path: {new_path}")
    df_new = None
    if new_path and os.path.exists(new_path):
        df_new = pd.read_csv(new_path)
    
    pivot_new = process_flow_data(df_new)
    if pivot_new is not None:
        colors = [COLOR_MAP[c] for c in pivot_new.columns]
        pivot_new.plot(kind='bar', stacked=True, color=colors, ax=axes[1], legend=False, width=0.85)
        
        # Stats Annotation
        n_agents = len(df_new['agent_id'].unique())
        years_avail = df_new['year'].max()
        axes[1].text(0.02, 0.95, f"N={n_agents}, Years={years_avail}", transform=axes[1].transAxes, fontsize=10)
        
        axes[1].set_title("Gemma 3 4B\n(After: Error Mode)", fontsize=14, fontweight='bold')
    else:
        axes[1].text(0.5, 0.5, "Simulation In Progress...", ha='center', va='center', fontsize=12)
        axes[1].set_title("Gemma 3 4B\n(After: Error Mode)", fontsize=14, fontweight='bold')

    for ax in axes:
        ax.grid(axis='y', linestyle='--', alpha=0.4)
        ax.set_xlabel("Year", fontsize=12)
        
    # Legend
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(0.5, -0.05), ncol=5, fontsize=12)
    
    plt.suptitle("Impact of Governance Hardening: Gemma 3 4B", fontsize=18, fontweight='bold', y=1.02)
    plt.tight_layout()
    
    out_file = "gemma_comparison_final.png"
    plt.savefig(out_file, dpi=300, bbox_inches='tight')
    print(f"Saved {out_file}")

if __name__ == "__main__":
    main()
