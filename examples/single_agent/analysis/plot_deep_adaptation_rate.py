import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import re

def plot_deep_adaptation_rate_annual(base_dir):
    """
    Generates Hierarchical Adaptation plots.
    Weights: Relocate (5), Elevation (3), Insurance (1).
    WAI = (Sum of Weighted New Actions) / (Remaining Population).
    """
    results_root = Path(base_dir).resolve()
    print(f"Searching for simulation logs in: {results_root}")
    
    all_data = []
    composition_data = []
    
    log_files = list(results_root.rglob("simulation_log.csv"))
    
    for log_path in log_files:
        path_str = str(log_path)
        model_match = re.search(r'deepseek_r1_([\d_.]+b)', path_str, re.IGNORECASE)
        model_label = model_match.group(1).replace("_", ".") + "B" if model_match else "Unknown"
        
        group_label = "Unknown"
        if "Group_A" in path_str: group_label = "Group A"
        elif "Group_B" in path_str: group_label = "Group B"
        elif "Group_C" in path_str: group_label = "Group C"
        
        try:
            df = pd.read_csv(log_path)
            if df.empty: continue
            df.columns = [c.lower() for c in df.columns]
            dec_col = 'yearly_decision' if 'yearly_decision' in df.columns else ('decision' if 'decision' in df.columns else 'cumulative_state')
            
            total_agents = df[df['year'] == 0]['agent_id'].nunique()
            if total_agents == 0: total_agents = df['agent_id'].nunique()
            
            max_year = df['year'].max()
            
            # Track first-time events for weighting
            relocated_ids = set()
            elevated_ids = set()
            insured_ids = set()
            
            for year in range(max_year + 1):
                current_subset = df[df['year'] == year]
                curr_dec = current_subset[dec_col].astype(str).str.lower()
                
                # Relocation (Weight 5)
                # Filter 'already relocated' or 'relocated' as state
                is_reloc = curr_dec.str.contains('relocate', na=False) & ~curr_dec.str.contains('already', na=False)
                new_reloc_ids = set(current_subset[is_reloc]['agent_id'].unique()) - relocated_ids
                
                # Elevation (Weight 3)
                is_elev = curr_dec.str.contains('elevat', na=False) | curr_dec.str.contains('he', na=False)
                new_elev_ids = (set(current_subset[is_elev]['agent_id'].unique()) - elevated_ids) - relocated_ids
                
                # Insurance (Weight 1)
                is_ins = curr_dec.str.contains('insur', na=False) | curr_dec.str.contains('fi', na=False)
                new_ins_ids = ((set(current_subset[is_ins]['agent_id'].unique()) - insured_ids) - elevated_ids) - relocated_ids
                
                # Denominator: Active population (not yet relocated)
                remaining_count = total_agents - len(relocated_ids)
                if remaining_count <= 0: remaining_count = 1
                
                # Calculation
                wai_score = (len(new_reloc_ids) * 5 + len(new_elev_ids) * 3 + len(new_ins_ids) * 1) / remaining_count
                
                all_data.append({
                    "Model": model_label, "Group": group_label, "Year": year,
                    "WAI": wai_score, "Type": "WeightedIndex"
                })
                
                # Composition for stacked plot
                composition_data.append({"Model": model_label, "Group": group_label, "Year": year, "Action": "Relocation", "Count": len(new_reloc_ids)})
                composition_data.append({"Model": model_label, "Group": group_label, "Year": year, "Action": "Elevation", "Count": len(new_elev_ids)})
                composition_data.append({"Model": model_label, "Group": group_label, "Year": year, "Action": "Insurance", "Count": len(new_ins_ids)})
                
                # Update history
                relocated_ids.update(new_reloc_ids)
                elevated_ids.update(new_elev_ids)
                insured_ids.update(new_ins_ids)
                
        except Exception as e:
            print(f"Error: {e}")

    # Plotting
    plot_df = pd.DataFrame(all_data)
    sns.set_style("whitegrid")
    palette = {"Group A": "#e74c3c", "Group B": "#f1c40f", "Group C": "#2ecc71"}
    
    # 2x2 WAI Grid
    models = ["1.5bB", "8bB", "14bB", "32bB"]
    fig, axes = plt.subplots(2, 2, figsize=(16, 12), sharex=True, sharey=True)
    axes = axes.flatten()
    for i, m in enumerate(models):
        ax = axes[i]
        subset = plot_df[plot_df['Model'] == m]
        if subset.empty: continue
        sns.lineplot(data=subset, x="Year", y="WAI", hue="Group", palette=palette, linewidth=2.5, marker='o', ax=ax)
        ax.axvspan(3, 4, color='blue', alpha=0.1)
        ax.axvspan(9, 10, color='blue', alpha=0.1)
        ax.set_title(f"Adaptation Quality (WAI): {m}", fontweight='bold')
        if i >= 2: ax.set_xlabel("Year")
        if i % 2 == 0: ax.set_ylabel("Weighted Index (Commitment)")
        if i != 1: ax.get_legend().remove()
    
    plt.suptitle("Hierarchical Adaptation Benchmark: Weighted Commitment Index", fontsize=18, y=0.96)
    plt.savefig(results_root / "plot_adaptation_wai_2x2.png", dpi=300, bbox_inches='tight')
    
    # Stacked Composition (Example for 14B)
    comp_df = pd.DataFrame(composition_data)
    m14 = comp_df[(comp_df['Model'] == '14bB') & (comp_df['Group'] == 'Group A')]
    if not m14.empty:
        plt.figure(figsize=(10, 6))
        m14_pivot = m14.pivot(index='Year', columns='Action', values='Count')
        m14_pivot.plot(kind='bar', stacked=True, color=['#3498db', '#9b59b6', '#e67e22'], ax=plt.gca())
        plt.title("Action Composition: 14B Group A (Sensitive/Uncontrolled)")
        plt.ylabel("New Strategic Actions")
        plt.savefig(results_root / "plot_composition_14b_A.png", dpi=300)

if __name__ == "__main__":
    base = "C:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/single_agent/results/JOH_FINAL"
    plot_deep_adaptation_rate_annual(base)
