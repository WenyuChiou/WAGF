
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import os
import numpy as np

# Setup
RESULTS_DIR = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL")
OUTPUT_DIR = Path(r"C:\Users\wenyu\.gemini\antigravity\brain\0eefc59d-202e-4d45-bd10-0806e60c7837")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)
plt.rcParams.update({'figure.dpi': 300})

MODELS = {
    'llama3_2_3b': 'Llama 3.2 3B',
    'gemma3_4b': 'Gemma 3 4B'
}

GROUPS = {
    'Group_A': 'Group A (Baseline)',
    'Group_B': 'Group B (Gov)',
    'Group_C': 'Group C (Mem)'
}

GROUP_PALETTE = {
    'Group A (Baseline)': '#7f7f7f', # Gray
    'Group B (Gov)': '#d62728',      # Red
    'Group C (Mem)': '#2ca02c'       # Green
}

BEHAVIOR_COLORS = {
    'Relocated': '#EF476F',        # Red (Cumulative Exit)
    'Action: Protect': '#06D6A0',  # Bright Green (This year's adaptation)
    'Stay & Protected': '#118AB2', # Teal (Already adapted state)
    'Stay & At Risk': '#FFD166'    # Yellow (Passive/At Risk)
}

def load_behavior_data():
    all_rows = []
    
    for model_folder, model_label in MODELS.items():
        base_path = RESULTS_DIR / model_folder
        if not base_path.exists(): continue

        for group_folder, group_label in GROUPS.items():
            search_path = base_path / group_folder
            if not search_path.exists(): continue

            found_files = list(search_path.rglob("simulation_log.csv"))
            for f in found_files:
                try:
                    df = pd.read_csv(f)
                    # Standardize booleans
                    for col in ['elevated', 'relocated', 'has_insurance']:
                        if col in df.columns:
                            if df[col].dtype == object:
                                df[col] = df[col].astype(str).str.lower() == 'true'
                            else:
                                df[col] = df[col].astype(bool)
                        else:
                            df[col] = False
                    
                    decision_col = 'decision' if 'decision' in df.columns else 'yearly_decision'
                    
                    for year in range(1, 11):
                        yr_df = df[df['year'] == year]
                        if yr_df.empty: continue
                        
                        # Identify decision column
                        decision_col = 'decision' if 'decision' in yr_df.columns else ('decision_made' if 'decision_made' in yr_df.columns else None)
                        
                        # HYBRID CATEGORIES:
                        # 1. Relocated (Cumulative)
                        is_relocated = (yr_df['relocated'] == True) | (yr_df[decision_col] == 'Already relocated') if decision_col else (yr_df['relocated'] == True)
                        
                        # 2. Action: Protect (New decision this year)
                        protect_decisions = ['Only Flood Insurance', 'Only House Elevation', 'Both Flood Insurance and House Elevation']
                        is_new_protect = yr_df[decision_col].isin(protect_decisions) if decision_col else pd.Series([False]*len(yr_df))
                        
                        # 3. Already Protected (State stayed, not a new decision)
                        is_already_protected = (yr_df['elevated'] | yr_df['has_insurance']) & (~is_new_protect) & (~is_relocated)
                        
                        # 4. Passive (Stay & At Risk)
                        is_passive = (~is_relocated) & (~is_new_protect) & (~is_already_protected)
                        
                        all_rows.append({
                            'Model': model_label,
                            'Group': group_label,
                            'Year': year,
                            'Relocated': is_relocated.mean(),
                            'Action: Protect': is_new_protect.mean(),
                            'Stay & Protected': is_already_protected.mean(),
                            'Stay & At Risk': is_passive.mean(),
                            'RunID': f.parent.name
                        })
                except Exception as e:
                    print(f"Error processing {f}: {e}")
                    
    return pd.DataFrame(all_rows)

def plot_behavior_matrix(df):
    """Creates a 2x3 matrix of stacked bar charts for direct ABC comparison.
    Aggregates data across all runs to show mean behavior with error bars (Std Dev).
    """
    models = df['Model'].unique()
    groups = ['Group A (Baseline)', 'Group B (Gov)', 'Group C (Mem)']
    
    fig, axes = plt.subplots(len(models), len(groups), figsize=(18, 10), sharex=True, sharey=True)
    
    categories = list(BEHAVIOR_COLORS.keys())
    colors = [BEHAVIOR_COLORS[c] for c in categories]

    for i, model in enumerate(models):
        for j, group in enumerate(groups):
            ax = axes[i, j]
            subset = df[(df['Model'] == model) & (df['Group'] == group)]
            if subset.empty: continue
            
            # Aggregate across runs (calculate mean and std for each year and category)
            # subset contains columns: Year, Relocated, Stay & Protected, Stay & At Risk, RunID
            agg_mean = subset.groupby('Year')[categories].mean()
            agg_std = subset.groupby('Year')[categories].std().fillna(0)
            
            years = agg_mean.index
            bottom = np.zeros(len(years))
            
            for k, cat in enumerate(categories):
                means = agg_mean[cat].values
                stds = agg_std[cat].values
                
                # Draw the bar
                ax.bar(years, means, bottom=bottom, color=colors[k], width=0.8, label=cat if (i==0 and j==0) else "")
                
                # Draw small error bars on the top boundary of each segment
                # (Representing the variance of where that specific boundary falls)
                ax.errorbar(years, bottom + means, yerr=stds, fmt='none', ecolor='black', 
                            capsize=3, elinewidth=1, alpha=0.6)
                
                bottom += means
            
            if i == 0: ax.set_title(group, fontsize=14, fontweight='bold', pad=10)
            if j == 0: ax.set_ylabel(model, fontsize=14, fontweight='bold')
            ax.set_ylim(0, 1.05)
            ax.grid(axis='y', linestyle='--', alpha=0.3)
            
    # Add a single legend
    handles, labels = axes[0,0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 1.05), ncol=3, fontsize=12)
    
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    save_path = OUTPUT_DIR / "behavior_evolution_matrix.png"
    plt.savefig(save_path, bbox_inches='tight', dpi=150)
    print(f"Saved {save_path}")

def load_friction_data():
    all_chunks = []
    
    for model_folder, model_label in MODELS.items():
        base_path = RESULTS_DIR / model_folder
        if not base_path.exists(): continue
        
        # Add Group A (Zero) explicitly for all 10 runs
        for run_id in range(1, 11):
            a_rows = []
            for yr in range(1, 11):
                a_rows.append({
                    'Year': yr, 
                    'Interventions': 0, 
                    'Group': GROUPS['Group_A'], 
                    'Model': model_label, 
                    'RunID': f"Run_{run_id}"
                })
            all_chunks.append(pd.DataFrame(a_rows))

        for group_folder, group_label in {'Group_B': GROUPS['Group_B'], 'Group_C': GROUPS['Group_C']}.items():
            search_path = base_path / group_folder
            if not search_path.exists(): continue
            
            found_files = list(search_path.rglob("household_governance_audit.csv"))
            for f in found_files:
                try:
                    df = pd.read_csv(f)
                    if df.empty: continue
                    
                    if 'step_id' in df.columns:
                        df['Year'] = ((df['step_id'] - 1) // 100) + 1
                    else:
                        df['Year'] = (df.index // 100) + 1
                    
                    df['Year'] = df['Year'].astype(int).clip(1, 10)
                    
                    # Count retries as the measure of friction/intervention
                    if 'retry_count' not in df.columns:
                        df['retry_count'] = 1 # Fallback
                        
                    # Aggregate by year within THIS run
                    retries = df.groupby('Year', observed=False)['retry_count'].sum().reset_index(name='Interventions')
                    retries['Group'] = group_label
                    retries['Model'] = model_label
                    retries['RunID'] = f.parent.name
                    all_chunks.append(retries)
                except Exception as e:
                    print(f"Friction Error {f}: {e}")
                
    if not all_chunks: return pd.DataFrame()
    final_df = pd.concat(all_chunks, ignore_index=True)
    final_df['Year'] = final_df['Year'].astype(int)
    final_df['Interventions'] = final_df['Interventions'].astype(float)
    return final_df

def plot_final_governance(df):
    plt.figure(figsize=(14, 7))
    # Using pointplot to clearly show mean and CI across 10 runs
    g = sns.catplot(
        data=df, x="Year", y="Interventions", hue="Group", col="Model",
        kind="point", palette=GROUP_PALETTE, height=5, aspect=1.4,
        errorbar=('ci', 95), capsize=.1, sharey=True, markers=["o", "s", "D"]
    )
    g.set_axis_labels("Simulation Year", "Total Interventions (Framework Buffering)")
    g.set_titles("{col_name}")
    plt.subplots_adjust(top=0.85)
    g.fig.suptitle('Governance Interventions: Framing Decision Boundaries', fontsize=18, fontweight='bold')
    save_path = OUTPUT_DIR / "final_governance_comparison.png"
    plt.savefig(save_path, bbox_inches='tight')
    print(f"Saved {save_path}")

if __name__ == "__main__":
    print("Loading Behavioral Data...")
    beh_df = load_behavior_data()
    if not beh_df.empty:
        plot_behavior_matrix(beh_df)
    
    print("Loading Governance Data...")
    gov_df = load_friction_data()
    if not gov_df.empty:
        plot_final_governance(gov_df)
    
    print("Execution Finished.")
