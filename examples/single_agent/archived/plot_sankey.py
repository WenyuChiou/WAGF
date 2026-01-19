"""
plot_sankey.py - Cognition-to-Action Flow Visualization

This script merges reflection logs (what agents think) with simulation logs 
(what agents do) to create a Sankey diagram showing the flow from 
cognitive themes to behavioral outcomes.

Usage:
    python plot_sankey.py
"""

import json
import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# Optional: plotly for interactive Sankey (if available)
try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False
    print("Warning: plotly not installed. Will use matplotlib fallback.")

# --- Configuration ---
RESULTS_DIR = "results/JOH_FINAL"
OUTPUT_DIR = "results/JOH_FINAL/plots"

# Keyword categories (same as visualize_reflection.py)
KEYWORDS = {
    "Risk Awareness": ["risk", "danger", "threat", "unsafe", "vulnerable", "fear", "scared", "severity", "frequency", "trend", "damage", "impact", "disaster", "flood"],
    "Protective Action": ["insurance", "levee", "elevation", "elevat", "protect", "defend", "safety", "mitigate", "proactive", "preparedness", "opportunity", "investigate", "grant", "feasibility", "measure", "strategy"],
    "Financial Concern": ["cost", "expensive", "money", "budget", "afford", "price", "loss", "financial", "claim", "delay", "tax", "economic", "recovery"],
    "Social Influence": ["neighbor", "community", "others", "friend", "group", "observe", "influence", "uptake", "adoption", "hesitant", "peer"],
    "Relocation": ["move", "leave", "relocate", "away", "migration", "exit", "displacement"]
}

# Priority order for dominant theme selection (to resolve ties)
THEME_PRIORITY = ["Protective Action", "Risk Awareness", "Financial Concern", "Social Influence", "Relocation"]
# ---------------------

def load_reflection_logs(result_dir):
    """Load reflection logs and determine dominant theme per agent per year."""
    data = []
    # 1. Search for dedicated reflection logs
    files = glob.glob(os.path.join(result_dir, "**", "reflection_log.jsonl"), recursive=True)
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
                    year = entry.get("year_created", entry.get("year", 0))
                    agent_id = entry.get("agent_id", "Unknown")
                    
                    # Determine themes present in this reflection
                    themes_found = []
                    for category, words in KEYWORDS.items():
                        if any(word in summary for word in words):
                            themes_found.append(category)
                    
                    if summary:
                        data.append({
                            "Model": model, "Group": group, "Run": run,
                            "AgentID": agent_id, "Year": year, "Summary": summary,
                            "Themes": themes_found
                        })
                except Exception:
                    continue

    # 2. Search for simulation logs (fallback)
    sim_files = glob.glob(os.path.join(result_dir, "**", "simulation_log.csv"), recursive=True)
    sim_files += glob.glob(os.path.join(result_dir, "**", "flood_adaptation_simulation_log.csv"), recursive=True)
    
    loaded_runs = set([(d['Model'], d['Group'], d['Run']) for d in data])
    
    for file_path in sim_files:
        path_parts = Path(file_path).parts
        path_str = str(file_path).lower()
        
        model = "Unknown"
        if "gemma" in path_str: model = "gemma3_4b"
        elif "llama" in path_str: model = "llama3_2_3b"
            
        try:
            group = next((p for p in path_parts if "Group_" in p), "Unknown")
            run = next((p for p in path_parts if "Run_" in p), "Run_1")
        except:
            group, run = "Unknown", "Run_1"
            
        if (model, group, run) in loaded_runs:
            continue
            
        try:
            df = pd.read_csv(file_path)
            appraisal_cols = [c for c in ['threat_appraisal', 'coping_appraisal'] if c in df.columns]
            if not appraisal_cols:
                continue
            
            for _, row in df.iterrows():
                summary = " ".join([str(row[c]) for c in appraisal_cols if pd.notna(row[c])]).lower()
                year = row.get('year', row.get('Year', 0))
                agent_id = row.get('agent_id', row.get('AgentID', 'Unknown'))
                
                themes_found = []
                for category, words in KEYWORDS.items():
                    if any(word in summary for word in words):
                        themes_found.append(category)

                if summary:
                    data.append({
                        "Model": model, "Group": group, "Run": run,
                        "AgentID": agent_id, "Year": year, "Summary": summary,
                        "Themes": themes_found
                    })
        except Exception:
            continue
            
    return pd.DataFrame(data)

def load_simulation_logs(result_dir):
    """Load simulation logs to get agent actions."""
    data = []
    files = glob.glob(os.path.join(result_dir, "**", "simulation_log.csv"), recursive=True)
    files += glob.glob(os.path.join(result_dir, "**", "flood_adaptation_simulation_log.csv"), recursive=True)
    
    for file_path in files:
        path_parts = Path(file_path).parts
        try:
            group = next((p for p in path_parts if "Group_" in p), "Unknown")
            run = next((p for p in path_parts if "Run_" in p), "Run_1")
            model = next((p for p in path_parts if "gemma" in p or "llama" in p), "Unknown")
        except:
            group, run, model = "Unknown", "Unknown", "Unknown"
        
        try:
            df = pd.read_csv(file_path)
            df['Model'] = model
            df['Group'] = group
            df['Run'] = run
            data.append(df)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
    
    if data:
        return pd.concat(data, ignore_index=True)
    return pd.DataFrame()

def get_dominant_theme(themes_list):
    """Given a list of themes across reflections, return the most frequent one."""
    if not themes_list:
        return "No Reflection"
    
    # Flatten the list of lists
    all_themes = [t for themes in themes_list for t in themes]
    if not all_themes:
        return "No Clear Theme"
    
    # Count occurrences
    from collections import Counter
    counts = Counter(all_themes)
    
    # Find max count
    max_count = max(counts.values())
    
    # If tie, use priority order
    for theme in THEME_PRIORITY:
        if counts.get(theme, 0) == max_count:
            return theme
    
    return counts.most_common(1)[0][0]

def determine_action(row):
    """Determine the action taken by an agent in a given year."""
    # Check for relocation first
    if pd.notna(row.get('relocated')) and row.get('relocated') == True:
        return "Relocated"
    
    # Check for adaptations
    adaptation_cols = ['adaptation', 'yearly_decision', 'decision']
    adaptation = ""
    for col in adaptation_cols:
        if col in row and pd.notna(row[col]):
            adaptation = str(row[col]).lower()
            break
    
    if 'insurance' in adaptation:
        return "Purchased Insurance"
    elif 'elevat' in adaptation:
        return "Elevated House"
    elif 'levee' in adaptation:
        return "Built Levee"
    elif adaptation and adaptation not in ['none', 'nan', '']:
        return "Other Adaptation"
    else:
        return "No Action"

def create_sankey_data(reflection_df, simulation_df):
    """Merge reflection and simulation data to create Sankey flow data."""
    # Aggregate reflections by agent/year to get dominant theme
    if reflection_df.empty:
        print("No reflection data available for Sankey.")
        return None
    
    # Group reflections by (Model, Group, Run, AgentID, Year)
    reflection_agg = reflection_df.groupby(['Model', 'Group', 'Run', 'AgentID', 'Year']).agg({
        'Themes': list
    }).reset_index()
    
    reflection_agg['DominantTheme'] = reflection_agg['Themes'].apply(get_dominant_theme)
    
    # Merge with simulation data
    # Need to match on Agent ID and Year
    if 'agent_id' in simulation_df.columns:
        simulation_df = simulation_df.rename(columns={'agent_id': 'AgentID'})
    if 'year' in simulation_df.columns:
        simulation_df = simulation_df.rename(columns={'year': 'Year'})
    
    # Determine action for each row in simulation
    simulation_df['Action'] = simulation_df.apply(determine_action, axis=1)
    
    # Merge
    merged = pd.merge(
        reflection_agg[['Model', 'Group', 'Run', 'AgentID', 'Year', 'DominantTheme']],
        simulation_df[['Model', 'Group', 'Run', 'AgentID', 'Year', 'Action']],
        on=['Model', 'Group', 'Run', 'AgentID', 'Year'],
        how='inner'
    )
    
    if merged.empty:
        print("No matching data between reflections and simulations.")
        return None
    
    # Create flow counts: (Theme -> Action)
    flow_counts = merged.groupby(['DominantTheme', 'Action']).size().reset_index(name='Count')
    
    return flow_counts

def plot_sankey_matplotlib(flow_df, output_path):
    """Create a simple Sankey-like visualization using matplotlib."""
    from matplotlib.sankey import Sankey
    
    # For matplotlib Sankey, we need a simpler approach
    # Let's create a stacked bar chart as an alternative
    
    pivot = flow_df.pivot_table(index='DominantTheme', columns='Action', values='Count', fill_value=0)
    
    fig, ax = plt.subplots(figsize=(14, 8))
    pivot.plot(kind='barh', stacked=True, ax=ax, colormap='viridis')
    
    ax.set_xlabel('Number of Agent-Year Instances', fontsize=12)
    ax.set_ylabel('Dominant Cognitive Theme', fontsize=12)
    ax.set_title('Cognition → Action Flow\n(What Agents Think vs What They Do)', fontsize=14, fontweight='bold')
    ax.legend(title='Action Taken', bbox_to_anchor=(1.02, 1), loc='upper left')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved flow chart to {output_path}")

def plot_sankey_plotly(flow_df, output_path):
    """Create an interactive Sankey diagram using Plotly."""
    # Create node labels
    themes = flow_df['DominantTheme'].unique().tolist()
    actions = flow_df['Action'].unique().tolist()
    
    all_labels = themes + actions
    label_to_idx = {label: i for i, label in enumerate(all_labels)}
    
    # Create links
    sources = [label_to_idx[t] for t in flow_df['DominantTheme']]
    targets = [label_to_idx[a] for a in flow_df['Action']]
    values = flow_df['Count'].tolist()
    
    # Color mapping
    theme_colors = {
        "Risk Awareness": "rgba(255, 99, 71, 0.8)",      # Tomato
        "Protective Action": "rgba(60, 179, 113, 0.8)", # Medium Sea Green
        "Financial Concern": "rgba(255, 215, 0, 0.8)",  # Gold
        "Social Influence": "rgba(100, 149, 237, 0.8)", # Cornflower Blue
        "Relocation": "rgba(148, 103, 189, 0.8)",       # Purple
        "No Reflection": "rgba(128, 128, 128, 0.8)",    # Gray
        "No Clear Theme": "rgba(192, 192, 192, 0.8)"    # Silver
    }
    
    link_colors = [theme_colors.get(t, "rgba(180, 180, 180, 0.5)") for t in flow_df['DominantTheme']]
    
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=all_labels,
            color=["#1f77b4"] * len(themes) + ["#2ca02c"] * len(actions)
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            color=link_colors
        )
    )])
    
    fig.update_layout(
        title_text="Cognition → Action Flow (Sankey Diagram)",
        font_size=12
    )
    
    # Save as HTML (interactive) and PNG (static)
    html_path = output_path.replace('.png', '.html')
    fig.write_html(html_path)
    print(f"Saved interactive Sankey to {html_path}")
    
    try:
        fig.write_image(output_path)
        print(f"Saved static Sankey to {output_path}")
    except Exception as e:
        print(f"Could not save static image (kaleido may be required): {e}")

def main():
    print("Loading reflection logs...")
    reflection_df = load_reflection_logs(RESULTS_DIR)
    print(f"Loaded {len(reflection_df)} reflection entries.")
    
    print("Loading simulation logs...")
    simulation_df = load_simulation_logs(RESULTS_DIR)
    print(f"Loaded {len(simulation_df)} simulation entries.")
    
    print("Creating Sankey flow data...")
    flow_df = create_sankey_data(reflection_df, simulation_df)
    
    if flow_df is None or flow_df.empty:
        print("Cannot create Sankey: no matching data.")
        return
    
    print(f"Flow data summary:\n{flow_df}")
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, "Cognition_Action_Sankey.png")
    
    if HAS_PLOTLY:
        plot_sankey_plotly(flow_df, output_path)
    else:
        plot_sankey_matplotlib(flow_df, output_path)
    
    print("Done.")

if __name__ == "__main__":
    main()
