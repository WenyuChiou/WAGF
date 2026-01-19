import json
import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
from pathlib import Path
import matplotlib
matplotlib.rcParams['font.family'] = 'DejaVu Sans'
matplotlib.rcParams['font.size'] = 11

# --- Configuration ---
RESULTS_DIR = "results/JOH_FINAL"
OUTPUT_DIR = "results/JOH_FINAL/plots"
KEYWORDS = {
    "Risk Awareness": ["risk", "danger", "threat", "unsafe", "vulnerable", "fear", "scared", "severity", "frequency", "trend", "damage", "impact", "disaster", "flood"],
    "Protective Action": ["insurance", "levee", "elevation", "elevat", "protect", "defend", "safety", "mitigate", "proactive", "preparedness", "opportunity", "investigate", "grant", "feasibility", "measure", "strategy"],
    "Financial Concern": ["cost", "expensive", "money", "budget", "afford", "price", "loss", "financial", "claim", "delay", "tax", "economic", "recovery"],
    "Social Influence": ["neighbor", "community", "others", "friend", "group", "observe", "influence", "uptake", "adoption", "hesitant", "peer"],
    "Relocation": ["move", "leave", "relocate", "away", "migration", "exit", "displacement"]
}
# Number of agents per simulation run (for normalization)
AGENTS_PER_RUN = 100
# ---------------------

def load_reflection_logs(result_dir):
    """Recursively find and load all reflection_log.jsonl files."""
    data = []
    # 1. Search for all jsonl files (dedicated reflection logs)
    files = glob.glob(os.path.join(result_dir, "**", "reflection_log.jsonl"), recursive=True)
    print(f"Found {len(files)} dedicated reflection logs.")
    
    for file_path in files:
        path_parts = Path(file_path).parts
        path_str = str(file_path).lower()
        
        model = "Unknown"
        if "gemma" in path_str: model = "gemma3_4b"
        elif "llama" in path_str: model = "llama3_2_3b"
        elif "deepseek" in path_str: model = "deepseek_r1_8b"
        elif "gpt_oss" in path_str: model = "gpt_oss_20b"
            
        try:
            group = next((p for p in path_parts if "Group_" in p), "Unknown")
            run = next((p for p in path_parts if "Run_" in p), "Run_1")
        except:
            group, run = "Unknown", "Run_1"

        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    summary = entry.get("summary", "").lower()
                    year = entry.get("year_created", 0)
                    agent_id = entry.get("agent_id", "Unknown")
                    
                    data.append({
                        "Model": model, "Group": group, "Run": run,
                        "AgentID": agent_id, "Year": year, "Summary": summary
                    })
                except Exception as e:
                    continue

    # 2. Search for simulation logs (fallback for Group A or missing reflections)
    sim_files = glob.glob(os.path.join(result_dir, "**", "simulation_log.csv"), recursive=True)
    sim_files += glob.glob(os.path.join(result_dir, "**", "flood_adaptation_simulation_log.csv"), recursive=True)
    print(f"Checking {len(sim_files)} simulation logs for fallback cognitive data...")
    
    loaded_runs = set([(d['Model'], d['Group'], d['Run']) for d in data])
    
    for file_path in sim_files:
        path_parts = Path(file_path).parts
        path_str = str(file_path).lower()
        
        model = "Unknown"
        if "gemma" in path_str: model = "gemma3_4b"
        elif "llama" in path_str: model = "llama3_2_3b"
        elif "deepseek" in path_str: model = "deepseek_r1_8b"
        elif "gpt_oss" in path_str: model = "gpt_oss_20b"
            
        try:
            group = next((p for p in path_parts if "Group_" in p), "Unknown")
            run = next((p for p in path_parts if "Run_" in p), "Run_1")
        except:
            group, run = "Unknown", "Run_1"
            
        # Only load if we haven't already loaded reflections for this run
        if (model, group, run) in loaded_runs:
            continue
            
        try:
            df = pd.read_csv(file_path)
            # Use threat_appraisal and coping_appraisal if available
            appraisal_cols = [c for c in ['threat_appraisal', 'coping_appraisal'] if c in df.columns]
            if not appraisal_cols:
                continue
                
            for _, row in df.iterrows():
                summary = " ".join([str(row[c]) for c in appraisal_cols if pd.notna(row[c])]).lower()
                year = row.get('year', row.get('Year', 0))
                agent_id = row.get('agent_id', row.get('AgentID', 'Unknown'))
                
                if summary:
                    data.append({
                        "Model": model, "Group": group, "Run": run,
                        "AgentID": agent_id, "Year": year, "Summary": summary
                    })
        except Exception as e:
            print(f"Error loading fallback data from {file_path}: {e}")
    
    return pd.DataFrame(data)

def calculate_keyword_frequencies(df):
    """Calculate the frequency of each keyword category per year/group."""
    rows = []
    
    # Process each row in the dataframe
    for _, row in df.iterrows():
        summary = row['Summary']
        for category, words in KEYWORDS.items():
            # Check if any word in the category appears in the summary
            count = sum(1 for word in words if word in summary)
            if count > 0:
                rows.append({
                    "Group": row['Group'],
                    "Year": row['Year'],
                    "Category": category,
                    "Count": 1 # Binary presence per reflection, or use 'count' for intensity
                })
    
    freq_df = pd.DataFrame(rows)
    # Group by Group, Year, Category and sum counts
    if not freq_df.empty:
        summary_df = freq_df.groupby(["Group", "Year", "Category"]).sum().reset_index()
        return summary_df
    else:
        return pd.DataFrame(columns=["Group", "Year", "Category", "Count"])

def plot_cognitive_heatmap(df, raw_df, output_dir):
    """Generate normalized heatmap plots for each group."""
    if df.empty:
        print("No reflection data found to plot.")
        return

    os.makedirs(output_dir, exist_ok=True)
    groups = df['Group'].unique()
    
    for group in groups:
        group_df = df[df['Group'] == group]
        group_raw_df = raw_df[raw_df['Group'] == group]
        
        # Calculate normalization factor: unique runs * agents per run
        n_runs = group_raw_df['Run'].nunique()
        normalization_factor = max(n_runs * AGENTS_PER_RUN, 1)  # Avoid division by zero
        
        # Pivot: Rows=Category, Cols=Year, Values=Count
        pivot_table = group_df.pivot_table(index="Category", columns="Year", values="Count", fill_value=0)
        
        # Normalize: Count per agent (across all runs)
        pivot_normalized = pivot_table / normalization_factor
        
        # Create figure with improved aesthetics
        fig, ax = plt.subplots(figsize=(12, 7))
        
        # Use rocket_r colormap for modern, publication-quality appearance
        heatmap = sns.heatmap(
            pivot_normalized, 
            annot=True, 
            fmt=".2f",  # Two decimal places for normalized values
            cmap="rocket_r",  # Reversed rocket: light background, dark values
            linewidths=0.8,
            linecolor='white',
            cbar_kws={'label': 'Mentions per Agent', 'shrink': 0.8},
            ax=ax
        )
        
        # Improve title and labels
        ax.set_title(
            f"Evolution of Cognitive Focus: {group}\n(Normalized Frequency per Agent, n={n_runs} runs)",
            fontsize=14, fontweight='bold', pad=20
        )
        ax.set_ylabel("Cognitive Theme", fontsize=12)
        ax.set_xlabel("Simulation Year", fontsize=12)
        
        # Rotate y-axis labels for better readability
        plt.yticks(rotation=0)
        plt.xticks(rotation=0)
        
        plt.tight_layout()
        
        output_path = os.path.join(output_dir, f"Cognitive_Heatmap_{group}.png")
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"Generated heatmap for {group}: {output_path} (normalized by {n_runs} runs)")

def main():
    print("Loading reflection logs...")
    df = load_reflection_logs(RESULTS_DIR)
    
    if df.empty:
        print("No data found. Ensure simulations have finished and reflection_log.jsonl exists.")
        return
        
    print(f"Loaded {len(df)} reflection entries.")
    print(f"Unique Groups: {df['Group'].unique()}")
    print(f"Unique Models: {df['Model'].unique()}")
    
    print("Analyzing keyword frequencies...")
    freq_df = calculate_keyword_frequencies(df)
    
    print("Generating plots...")
    plot_cognitive_heatmap(freq_df, df, OUTPUT_DIR)
    print("Done.")

if __name__ == "__main__":
    main()
