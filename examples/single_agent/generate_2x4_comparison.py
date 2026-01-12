"""
Multi-Model 2x4 Comparison Chart Generator

Generates a 2x4 grid showing adaptation states across 4 models:
- Row 1: 4 individual model stacked bar charts
- Row 2: (Optional future extension) 4 cumulative progression charts

Usage:
    python generate_2x4_comparison.py
"""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# Model configurations with display names and folder names
MODELS = [
    {"name": "Gemma 3 (4B)", "folder": "gemma3_4b_strict"},
    {"name": "Llama 3.2 (3B)", "folder": "llama3.2_3b_strict"},
    {"name": "DeepSeek-R1 (8B)", "folder": "deepseek-r1_8b_strict"},
    {"name": "GPT-OSS (Latest)", "folder": "gpt-oss_latest_strict"},
]

# Standard adaptation state colors (matching baseline)
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


def load_model_data(results_dir: Path, model_folder: str) -> pd.DataFrame:
    """Load simulation log for a specific model."""
    csv_path = results_dir / model_folder / "simulation_log.csv"
    if not csv_path.exists():
        print(f"⚠️ Missing: {csv_path}")
        return pd.DataFrame()
    return pd.read_csv(csv_path)


def process_for_chart(df: pd.DataFrame) -> pd.DataFrame:
    """Process dataframe: filter relocated agents after their first year."""
    if df.empty:
        return df
    
    dec_col = 'decision' if 'decision' in df.columns else 'cumulative_state'
    
    # Find first relocation year per agent
    relocations = df[df[dec_col] == 'Relocate'].groupby('agent_id')['year'].min()
    relocations = relocations.reset_index()
    relocations.columns = ['agent_id', 'first_reloc_year']
    
    # Merge and filter
    df = df.merge(relocations, on='agent_id', how='left')
    df = df[df['first_reloc_year'].isna() | (df['year'] <= df['first_reloc_year'])]
    
    return df


def plot_model_chart(ax, df: pd.DataFrame, model_name: str):
    """Plot stacked bar chart for a single model on given axes."""
    if df.empty:
        ax.text(0.5, 0.5, f"{model_name}\n(No Data)", ha='center', va='center', fontsize=12)
        ax.set_title(model_name, fontsize=14, fontweight='bold')
        return
    
    dec_col = 'decision' if 'decision' in df.columns else 'cumulative_state'
    
    # Pivot table
    pivot = df.pivot_table(index='year', columns=dec_col, aggfunc='size', fill_value=0)
    
    # Ensure consistent ordering
    categories = [c for c in STATE_ORDER if c in pivot.columns]
    plot_colors = [STATE_COLORS.get(c, "#333333") for c in categories]
    
    # Stacked bar plot
    pivot[categories].plot(kind='bar', stacked=True, ax=ax, color=plot_colors, width=0.8, legend=False)
    
    ax.set_title(model_name, fontsize=14, fontweight='bold')
    ax.set_xlabel("Year", fontsize=10)
    ax.set_ylabel("Number of Agents", fontsize=10)
    ax.grid(axis='y', linestyle='--', alpha=0.5)


def generate_2x4_chart(results_dir: Path, output_path: Path):
    """Generate the 2x4 comparison chart."""
    
    # Create figure with 2 rows, 4 columns (currently using row 1 for all 4 models)
    fig, axes = plt.subplots(2, 4, figsize=(20, 10))
    
    # Top row: 4 model stacked bar charts
    for i, model_config in enumerate(MODELS):
        df = load_model_data(results_dir, model_config["folder"])
        df = process_for_chart(df)
        plot_model_chart(axes[0, i], df, model_config["name"])
    
    # Bottom row: Currently placeholder (can add cumulative progression later)
    for i in range(4):
        axes[1, i].axis('off')
        axes[1, i].text(0.5, 0.5, "(Reserved for future visualization)", 
                        ha='center', va='center', fontsize=10, color='gray')
    
    # Create unified legend
    handles = [plt.Rectangle((0,0),1,1, facecolor=STATE_COLORS[s]) for s in STATE_ORDER]
    fig.legend(handles, STATE_ORDER, loc='lower center', ncol=5, fontsize=11, 
               title="Adaptation State", title_fontsize=12, bbox_to_anchor=(0.5, 0.02))
    
    plt.suptitle("Multi-Model Flood Adaptation Comparison (100 Agents, 10 Years)", 
                 fontsize=18, fontweight='bold', y=0.98)
    plt.tight_layout(rect=[0, 0.08, 1, 0.96])
    
    # Save
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✅ Saved 2x4 comparison chart to: {output_path}")
    plt.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate 2x4 comparison chart.")
    parser.add_argument("--results", type=str, help="Directory containing model results folders.")
    parser.add_argument("--output", type=str, help="Output PNG file path.")
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    results_dir = Path(args.results).resolve() if args.results else script_dir / "results"
    
    # Generate unique output name based on results folder if not provided
    if args.output:
        output_path = Path(args.output).resolve()
    else:
        suffix = results_dir.name if results_dir.name != "results" else "window"
        output_path = script_dir / f"multi_model_comparison_2x4_{suffix}.png"
    
    print("=" * 60)
    print(f"Generating 2x4 Comparison Chart")
    print(f"Results Source: {results_dir}")
    print(f"Output Path: {output_path}")
    print("=" * 60)
    
    # Check which models have data
    print("\nModel data status:")
    for model in MODELS:
        csv_path = results_dir / model["folder"] / "simulation_log.csv"
        status = "✅" if csv_path.exists() else "❌"
        print(f"  {status} {model['name']}: {model['folder']}")
    
    # Generate chart
    generate_2x4_chart(results_dir, output_path)
