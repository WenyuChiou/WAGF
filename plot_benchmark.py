import pandas as pd
import matplotlib.pyplot as plt
import sys
from pathlib import Path
import os

# Configuration matching user's request
RESULTS_DIR = Path("results")
OUTPUT_DIR = Path("results/plots")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

COLOR_MAP = {
    "Do Nothing": "#1f77b4",        # Blue
    "Only Flood Insurance": "#ff7f0e", # Orange
    "Only House Elevation": "#2ca02c", # Green
    "Both Flood Insurance and House Elevation": "#d62728", # Red
    "Relocate": "#9467bd"           # Purple
}

ORDER = [
    "Do Nothing",
    "Only Flood Insurance",
    "Only House Elevation",
    "Both Flood Insurance and House Elevation",
    "Relocate"
]

def plot_model_results(model_dir):
    log_path = model_dir / "simulation_log.csv"
    if not log_path.exists():
        print(f"Skipping {model_dir.name} - No log found")
        return

    print(f"Plotting for {model_dir.name}...")
    df = pd.read_csv(log_path)
    
    # Check if 'decision' aligns with adaptation states or needs mapping
    # run_experiment.py logs 'decision' as "Relocate", "Only Flood Insurance", etc. directly
    # So we can use it directly.
    
    # Group by Year and Decision
    counts = df.groupby(['year', 'decision']).size().unstack(fill_value=0)
    
    # Reindex columns to ensure all states are present and ordered
    for state in ORDER:
        if state not in counts.columns:
            counts[state] = 0
    counts = counts[ORDER]
    
    # Rename columns for shorter legend
    SHORT_LABELS = {
        "Do Nothing": "Do Nothing",
        "Only Flood Insurance": "Insurance",
        "Only House Elevation": "Elevation",
        "Both Flood Insurance and House Elevation": "Ins + Elev",
        "Relocate": "Relocate"
    }
    counts.rename(columns=SHORT_LABELS, inplace=True)
    
    # Update color map to match new labels
    NEW_COLOR_MAP = {SHORT_LABELS[k]: v for k, v in COLOR_MAP.items()}
    
    # Plot
    fig, ax = plt.subplots(figsize=(10, 6))
    
    counts.plot(kind='bar', stacked=True, ax=ax, color=[NEW_COLOR_MAP.get(c, "#333333") for c in counts.columns], width=0.5)
    
    ax.set_title(f"Adaptation States by Year ({model_dir.name})")
    ax.set_xlabel("Year")
    ax.set_ylabel("Number of Agents")
    ax.set_ylim(0, 100) # Assuming 100 agents provided by user context
    ax.legend(title="Adaptation State", bbox_to_anchor=(1.05, 1), loc='upper left')
    
    plt.tight_layout()
    output_path = OUTPUT_DIR / f"stacked_bar_{model_dir.name}.png"
    plt.savefig(output_path, dpi=300)
    print(f"Saved plot to {output_path}")
    plt.close()

def main():
    if not RESULTS_DIR.exists():
        print(f"Results directory {RESULTS_DIR} not found.")
        return

    # Find all model subdirectories
    for item in RESULTS_DIR.iterdir():
        if item.is_dir() and item.name != "plots":
            plot_model_results(item)

if __name__ == "__main__":
    main()
