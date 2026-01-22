import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Paths
RESULTS_DIR = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL")
OUTPUT_DIR = Path(r"C:\Users\wenyu\.gemini\antigravity\brain\0eefc59d-202e-4d45-bd10-0806e60c7837")

MODELS = {
    'llama3_2_3b': 'Llama 3.2 (3B)',
    'gemma3_4b': 'Gemma 2 (9B)'
}

GROUPS = {
    'Group_A': 'Baseline (No Validator)',
    'Group_B': 'Gov Only (Validator)',
    'Group_C': 'Synergy (Validator + Mem)'
}

def load_trace_matrix(model_folder, group_folder):
    # Use Run 1 as representative
    log_path = RESULTS_DIR / model_folder / group_folder / "Run_1" / "simulation_log.csv"
    if not log_path.exists():
        return None
    
    df = pd.read_csv(log_path)
    # Standardize
    for col in ['elevated', 'relocated', 'has_insurance']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.lower() == 'true'
        else:
            df[col] = False
            
    decision_col = 'decision' if 'decision' in df.columns else 'yearly_decision'
    
    # State mapping: 0 (Risk), 1 (Protected), 2 (Relocated)
    trace_data = []
    agent_ids = sorted(df['agent_id'].unique())
    
    # We need to handle agents who are no longer in the CSV for a given year because they relocated
    for agent_id in agent_ids:
        agent_log = df[df['agent_id'] == agent_id].sort_values('year')
        row = []
        has_relocated = False
        for yr in range(1, 11):
            yr_data = agent_log[agent_log['year'] == yr]
            
            if has_relocated:
                row.append(2)
                continue
                
            if yr_data.empty:
                # If they were there before but not now, they must have relocated
                # (Assuming population doesn't increase)
                has_relocated = True
                row.append(2)
                continue
                
            is_relocated_flag = yr_data['relocated'].iloc[0]
            is_relocated_decision = (yr_data[decision_col].iloc[0] in ['Relocate', 'Already relocated']) if decision_col in yr_data.columns else False
            
            if is_relocated_flag or is_relocated_decision:
                has_relocated = True
                row.append(2)
            elif yr_data['elevated'].iloc[0] or yr_data['has_insurance'].iloc[0]:
                row.append(1)
            else:
                row.append(0)
        trace_data.append(row)
        
    return np.array(trace_data)

def plot_behavior_transition():
    # Colors: Yellow (Risk), Blue (Protected), Red (Relocated)
    cmap = sns.color_palette(["#FFD166", "#118AB2", "#EF476F"])
    
    fig, axes = plt.subplots(len(MODELS), len(GROUPS), figsize=(18, 12), sharex=True, sharey=True)
    
    for m_idx, (m_folder, m_label) in enumerate(MODELS.items()):
        for g_idx, (g_folder, g_label) in enumerate(GROUPS.items()):
            ax = axes[m_idx, g_idx]
            matrix = load_trace_matrix(m_folder, g_folder)
            
            if matrix is not None:
                sns.heatmap(matrix, cmap=cmap, cbar=False, ax=ax, xticklabels=range(1, 11))
            
            if m_idx == 0:
                ax.set_title(g_label, fontsize=16, fontweight='bold', pad=15)
            if g_idx == 0:
                ax.set_ylabel(f"{m_label}\n\nAgent ID", fontsize=16, fontweight='bold')
            
            ax.set_xlabel("Year" if m_idx == 1 else "")
    
    # Global Legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#FFD166', label='Stay & At Risk (Fragile)'),
        Patch(facecolor='#118AB2', label='Stay & Protected (Resilience)'),
        Patch(facecolor='#EF476F', label='Relocated (Exit/Collapse)')
    ]
    fig.legend(handles=legend_elements, loc='lower center', ncol=3, fontsize=14, frameon=False, bbox_to_anchor=(0.5, 0.02))
    
    plt.suptitle("Validator Impact: Behavioral Transition from Baseline to Synergy", fontsize=22, fontweight='bold', y=0.98)
    plt.tight_layout(rect=[0, 0.05, 1, 0.95])
    
    output_path = OUTPUT_DIR / "final_combined_trace_heatmap.png"
    plt.savefig(output_path, dpi=200)
    print(f"Combined heatmap saved to {output_path}")

if __name__ == "__main__":
    plot_behavior_transition()
