import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Paths
RESULTS_DIR = Path(__file__).resolve().parents[3] / "results" / "JOH_FINAL"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "reports" / "figures"

MODELS = {
    'llama3_2_3b': 'Llama 3.2 (3B)',
    'gemma3_4b': 'Gemma 2 (9B)'
}

# 4 Options Logic
def generate_group_c_visualizations():
    for model_folder, model_label in MODELS.items():
        # Using Run 1 as a representative for Trace Heatmap and Calendar
        log_path = RESULTS_DIR / model_folder / "Group_C" / "Run_1" / "simulation_log.csv"
        if not log_path.exists():
            print(f"File not found: {log_path}")
            continue
        
        df = pd.read_csv(log_path)
        # Standardize
        for col in ['elevated', 'relocated', 'has_insurance']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.lower() == 'true'
            else:
                df[col] = False
        
        decision_col = 'decision' if 'decision' in df.columns else 'yearly_decision'
        
        # --- OPTION 1: Trace Heatmap ---
        # Matrix: Agent ID (Rows) x Year (Cols)
        # Values: 0 (Risk), 1 (Protected), 2 (Relocated)
        trace_data = []
        for agent_id in df['agent_id'].unique():
            agent_log = df[df['agent_id'] == agent_id].sort_values('year')
            row = []
            for yr in range(1, 11):
                yr_data = agent_log[agent_log['year'] == yr]
                if yr_data.empty:
                    # Look for 'Already relocated' in previous years or use state
                    # If they are gone, value = 2
                    row.append(2 if any(agent_log[agent_log['year'] < yr]['relocated']) else 0)
                    continue
                
                if yr_data['relocated'].iloc[0] or (decision_col in yr_data and yr_data[decision_col].iloc[0] == 'Already relocated'):
                    val = 2
                elif yr_data['elevated'].iloc[0] or yr_data['has_insurance'].iloc[0]:
                    val = 1
                else:
                    val = 0
                row.append(val)
            trace_data.append(row)
        
        trace_matrix = np.array(trace_data)
        
        plt.figure(figsize=(10, 8))
        cmap = sns.color_palette(["#FFD166", "#118AB2", "#EF476F"]) # Yellow, Teal, Red
        sns.heatmap(trace_matrix, cmap=cmap, cbar=False, xticklabels=range(1, 11))
        plt.title(f"{model_label} - Group C: Trace Heatmap (Agent Lifecycle)", fontsize=14)
        plt.xlabel("Year")
        plt.ylabel("Agent ID")
        # Custom legend
        from matplotlib.patches import Patch
        legend_elements = [Patch(facecolor='#FFD166', label='At Risk'),
                           Patch(facecolor='#118AB2', label='Protected'),
                           Patch(facecolor='#EF476F', label='Relocated')]
        plt.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1.2, 1))
        plt.tight_layout()
        plt.savefig(OUTPUT_DIR / f"group_c_option1_{model_folder}.png", dpi=200)
        plt.close()

        # --- OPTION 2: Flow Ribbon (Stacked Area) ---
        # Cumulative stats for the 100 agents
        years = range(1, 11)
        area_data = {
            'Relocated': [],
            'Protected': [],
            'At Risk': []
        }
        for yr in years:
            yr_df = df[df['year'] == yr]
            # Since some might be missing if relocated, we count them as relocated
            total_agents = 100
            relocated = yr_df['relocated'].sum() + (total_agents - len(yr_df))
            protected = (yr_df['elevated'] | yr_df['has_insurance']).sum()
            at_risk = total_agents - relocated - protected
            
            area_data['Relocated'].append(relocated/total_agents)
            area_data['Protected'].append(protected/total_agents)
            area_data['At Risk'].append(at_risk/total_agents)
            
        plt.figure(figsize=(10, 6))
        plt.stackplot(years, area_data['Relocated'], area_data['Protected'], area_data['At Risk'],
                      labels=['Relocated', 'Protected', 'At Risk'],
                      colors=['#EF476F', '#118AB2', '#FFD166'], alpha=0.8)
        plt.title(f"{model_label} - Group C: Population Flow Ribbon", fontsize=14)
        plt.xlabel("Year")
        plt.ylabel("Population Fraction")
        plt.legend(loc='lower left')
        plt.savefig(OUTPUT_DIR / f"group_c_option2_{model_folder}.png", dpi=200)
        plt.close()

        # --- OPTION 3: Survival & Adaptation Curves ---
        plt.figure(figsize=(10, 6))
        stay_rate = [1 - r for r in area_data['Relocated']]
        prot_rate = [p for p in area_data['Protected']]
        
        plt.plot(years, stay_rate, label='Community Survival (Stayed)', color='#EF476F', linewidth=3, marker='o')
        plt.plot(years, prot_rate, label='Adaptation Level (Protected)', color='#06D6A0', linewidth=3, marker='s')
        plt.fill_between(years, prot_rate, stay_rate, color='grey', alpha=0.1, label='Vulnerability Gap')
        
        plt.title(f"{model_label} - Group C: Survival & Adaptation Curves", fontsize=14)
        plt.xlabel("Year")
        plt.ylabel("Percentage (%)")
        plt.ylim(0, 1.1)
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.legend()
        plt.savefig(OUTPUT_DIR / f"group_c_option3_{model_folder}.png", dpi=200)
        plt.close()

        # --- OPTION 4: Behavioral Calendar (Simplified as a grid) ---
        plt.figure(figsize=(12, 4))
        # We aggregate daily/yearly actions into a matrix
        # Let's show "Action Intensity" heatmap (Sum of actions per year)
        # Actually, let's just make a smaller version of the heatmap but with actions highlighted
        action_matrix = []
        for yr in years:
            yr_df = df[df['year'] == yr]
            action_count = yr_df[decision_col].isin(['Only Flood Insurance', 'Only House Elevation', 'Both Flood Insurance and House Elevation']).sum()
            action_matrix.append(action_count)
        
        plt.bar(years, action_matrix, color='#06D6A0')
        plt.title(f"{model_label} - Group C: Yearly Adaptation Action Frequency", fontsize=14)
        plt.xlabel("Year")
        plt.ylabel("Number of Actions Taken")
        plt.savefig(OUTPUT_DIR / f"group_c_option4_{model_folder}.png", dpi=200)
        plt.close()

if __name__ == "__main__":
    generate_group_c_visualizations()
    print("Prototypes generated in Brain directory.")
