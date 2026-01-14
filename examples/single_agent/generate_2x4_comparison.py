"""
Multi-Model 2x4 Comparison Chart Generator (Memory System Edition)

Generates a 2x4 grid showing adaptation states across 4 models and 2 memory engines:
- Row 1: 4 models with Window Memory
- Row 2: 4 models with Human-Centric Memory

Usage:
    python generate_2x4_comparison.py --results-row1 results_window --results-row2 results_humancentric
"""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import os

# Model configurations
MODELS = [
    {"name": "Gemma 3 (4B)", "folder": "gemma3_4b_strict"},
    {"name": "Llama 3.2 (3B)", "folder": "llama3_2_3b_strict"},
    {"name": "DeepSeek-R1 (8B)", "folder": "deepseek_r1_8b_strict"},
]

# Standard adaptation state colors
STATE_COLORS = {
    "Do Nothing": "#1f77b4",                              # Blue
    "Only Flood Insurance": "#ff7f0e",                    # Orange
    "Only House Elevation": "#2ca02c",                    # Green
    "Both Flood Insurance and House Elevation": "#d62728", # Red
    "Relocate": "#9467bd"                                 # Purple
}

STATE_ORDER = [
    "Do Nothing",
    "Only Flood Insurance",
    "Only House Elevation",
    "Both Flood Insurance and House Elevation",
    "Relocate"
]

def load_and_process(results_dir: Path, model_folder: str):
    """Load and process simulation log."""
    csv_path = results_dir / model_folder / "simulation_log.csv"
    
    # Try underscore variation if hyphenated folder not found
    if not csv_path.exists():
        alt_folder = model_folder.replace('-', '_')
        csv_path = results_dir / alt_folder / "simulation_log.csv"
    
    # Try hyphen variation if underscore folder not found
    if not csv_path.exists():
        alt_folder = model_folder.replace('_', '-')
        csv_path = results_dir / alt_folder / "simulation_log.csv"

    if not csv_path.exists():
        return pd.DataFrame()
    
    df = pd.read_csv(csv_path)
    if df.empty:
        return df
    
    dec_col = 'decision' if 'decision' in df.columns else 'cumulative_state'
    
    # Filter relocated agents after their first year
    relocations = df[df[dec_col] == 'Relocate'].groupby('agent_id')['year'].min().reset_index()
    relocations.columns = ['agent_id', 'first_reloc_year']
    df = df.merge(relocations, on='agent_id', how='left')
    df = df[df['first_reloc_year'].isna() | (df['year'] <= df['first_reloc_year'])]
    
    return df

def plot_stacked_bar(ax, df, title, show_ylabel=False):
    """Plot stacked bar chart."""
    if df.empty:
        ax.text(0.5, 0.5, "No Data", ha='center', va='center', fontsize=12)
        ax.set_title(title, fontsize=12, fontweight='bold')
        return

    dec_col = 'decision' if 'decision' in df.columns else 'cumulative_state'
    pivot = df.pivot_table(index='year', columns=dec_col, aggfunc='size', fill_value=0)
    
    categories = [c for c in STATE_ORDER if c in pivot.columns]
    plot_colors = [STATE_COLORS.get(c, "#333333") for c in categories]
    
    pivot[categories].plot(kind='bar', stacked=True, ax=ax, color=plot_colors, width=0.8, legend=False)
    
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel("Year", fontsize=9)
    if show_ylabel:
        ax.set_ylabel("Agents", fontsize=9)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    ax.tick_params(axis='both', which='major', labelsize=8)

def generate_2x3_memory_comparison(dir1: Path, dir2: Path, output_path: Path):
    """Generate the 2x3 comparison chart for two memory engines."""
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    
    # Row 1: Window Memory
    for i, model in enumerate(MODELS):
        df = load_and_process(dir1, model["folder"])
        plot_stacked_bar(axes[0, i], df, f"{model['name']}\n(Window)", show_ylabel=(i==0))
    
    # Row 2: Human-Centric Memory
    for i, model in enumerate(MODELS):
        df = load_and_process(dir2, model["folder"])
        plot_stacked_bar(axes[1, i], df, f"{model['name']}\n(Human-Centric)", show_ylabel=(i==0))
    
    # Legend
    handles = [plt.Rectangle((0,0),1,1, facecolor=STATE_COLORS[s]) for s in STATE_ORDER]
    fig.legend(handles, STATE_ORDER, loc='lower center', ncol=5, fontsize=11, 
               title="Adaptation State", title_fontsize=12, bbox_to_anchor=(0.5, 0.02))
    
    plt.suptitle("Memory Engine Impact Analysis: Window vs Human-Centric Retrieval (100 Agents, 10 Years)", 
                 fontsize=18, fontweight='bold', y=0.98)
    plt.tight_layout(rect=[0, 0.08, 1, 0.94])
    
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✅ Saved 2x3 memory comparison chart to: {output_path}")
    plt.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir1", type=str, default="results_window")
    parser.add_argument("--dir2", type=str, default="results_humancentric")
    parser.add_argument("--output", type=str, default="memory_system_comparison_2x3.png")
    args = parser.parse_args()
    
    generate_2x3_memory_comparison(Path(args.dir1), Path(args.dir2), Path(args.output))
