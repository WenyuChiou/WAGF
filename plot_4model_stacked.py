import pandas as pd
import matplotlib.pyplot as plt
import os
import glob

# Configuration
MODELS = {
    "Llama 3.2 3B": "results/hardened_benchmark/llama3.2_3b/simulation_log.csv",
    "Gemma 3 4B":   "results/hardened_benchmark/gemma3_4b/simulation_log.csv",
    "DeepSeek R1":  "results/hardened_benchmark/deepseek-r1_8b/simulation_log.csv", # path might vary, glob used below
    "GPT-OSS":      "results/hardened_benchmark/gpt-oss_latest/simulation_log.csv"
}

def get_data(csv_path):
    # Flexible path finding
    if not os.path.exists(csv_path):
        dir_name = os.path.dirname(csv_path)
        # Assuming format results/hardened_benchmark/MODEL_NAME/simulation_log.csv
        # If deeply nested:
        base_dir = "results/hardened_benchmark/"
        # extract model folder guess
        parts = csv_path.split('/')
        if len(parts) > 2:
            model_part = parts[2]
            candidates = glob.glob(f"results/hardened_benchmark/{model_part}*/**/simulation_log.csv", recursive=True)
            if candidates:
                csv_path = candidates[0]
            else:
                return None
    
    if not os.path.exists(csv_path):
        return None

    try:
        df = pd.read_csv(csv_path)
        if df.empty: return None
        return df
    except:
        return None

def plot_stacked_subplot(ax, df, title):
    # Logic from plot_results.py
    
    # Identify col 'decision'
    # Identify FIRST year relocated
    if 'decision' not in df.columns:
        ax.text(0.5, 0.5, "Invalid Data (No decision col)", ha='center', va='center')
        return

    relocated_first_year = df[df['decision'] == 'Relocate'].groupby('agent_id')['year'].min().reset_index()
    relocated_first_year.columns = ['agent_id', 'first_reloc_year']
    df = df.merge(relocated_first_year, on='agent_id', how='left')
    df = df[df['first_reloc_year'].isna() | (df['year'] <= df['first_reloc_year'])]
    
    pivot = df.pivot_table(index='year', columns='decision', aggfunc='size', fill_value=0)
    
    all_categories = [
        "Do Nothing",
        "Only Flood Insurance",
        "Only House Elevation",
        "Both Flood Insurance and House Elevation",
        "Relocate"
    ]
    categories = [c for c in all_categories if c in pivot.columns]
    
    # Colors
    # Blue, Orange, Green, Red, Purple
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    color_map = dict(zip(all_categories, colors))
    plot_colors = [color_map.get(c, "#333333") for c in categories]
    
    pivot[categories].plot(kind='bar', stacked=True, ax=ax, color=plot_colors, width=0.8, legend=False)
    
    ax.set_title(title, fontsize=12)
    ax.set_xlabel("Year")
    ax.set_ylabel("Agents")
    ax.grid(axis='y', linestyle='--', alpha=0.5)

def plot_4_stacked():
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    axes = axes.flatten()
    
    # Legend handles hack
    lines = []
    labels = []
    
    for i, (model, path) in enumerate(MODELS.items()):
        ax = axes[i]
        df = get_data(path)
        
        if df is not None:
            plot_stacked_subplot(ax, df, f"{model} (Error Mode)")
            # Grab handles for legend from the first valid plot
            if not lines:
                h, l = ax.get_legend_handles_labels()
                lines = h
                labels = l
        else:
            ax.text(0.5, 0.5, "Simulating... (Pending Data)", ha='center', va='center', fontsize=12, color='gray')
            ax.set_title(f"{model}", fontsize=12)
            ax.axis('off')
            ax.grid(False) # Ensure grid is off

    # Global Legend
    if lines:
        fig.legend(lines, labels, loc='upper center', bbox_to_anchor=(0.5, 1.02), ncol=5, title="Adaptation State")

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    output_file = "stacked_progression_4models.png"
    plt.savefig(output_file, dpi=300)
    print(f"Plot saved to {output_file}")

if __name__ == "__main__":
    plot_4_stacked()
