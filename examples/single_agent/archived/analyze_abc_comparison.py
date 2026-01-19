"""
analyze_abc_comparison.py - Compare Groups A, B, C from simulation logs

This script analyzes the behavioral differences between:
- Group A: Baseline (no governance)
- Group B: Governed (with validation)
- Group C: Human-Centric (governed + memory + reflection)

Usage:
    python analyze_abc_comparison.py
"""

import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import numpy as np
from scipy import stats

# --- Configuration ---
RESULTS_DIR = "results/JOH_FINAL"
OUTPUT_DIR = "results/JOH_FINAL/plots"
# ---------------------

def load_all_simulation_logs(result_dir):
    """Load all simulation logs and tag with metadata."""
    data = []
    files = glob.glob(os.path.join(result_dir, "**", "simulation_log.csv"), recursive=True)
    files += glob.glob(os.path.join(result_dir, "**", "flood_adaptation_simulation_log.csv"), recursive=True)
    
    print(f"Found {len(files)} simulation log files.")
    
    for file_path in files:
        path_parts = Path(file_path).parts
        path_str = str(file_path).lower()
        
        model = "Unknown"
        if "gemma" in path_str:
            model = "gemma3_4b"
        elif "llama" in path_str:
            model = "llama3_2_3b"
            
        try:
            group = next((p for p in path_parts if "Group_" in p), "Unknown")
            run = next((p for p in path_parts if "Run_" in p), "Run_1")
        except Exception:
            group, run = "Unknown", "Run_1"
        
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

def calculate_adaptation_rate(df):
    """Calculate adaptation rate per group per year."""
    def check_adapted(row):
        # List of columns that might contain the decision
        cols = ['yearly_decision', 'adaptation', 'decision']
        for col in cols:
            val = row.get(col)
            if pd.notna(val) and str(val).strip() != "":
                s_val = str(val).strip().lower()
                if s_val not in ['none', 'nan', 'do_nothing', 'do nothing', 'not_applicable']:
                    return 1
        return 0
    
    df['adapted'] = df.apply(check_adapted, axis=1)
    
    # Group by Model, Group, Year
    year_col = 'year' if 'year' in df.columns else 'Year'
    
    summary = df.groupby(['Model', 'Group', year_col]).agg({
        'adapted': ['sum', 'count']
    }).reset_index()
    summary.columns = ['Model', 'Group', 'Year', 'Adaptations', 'TotalAgents']
    summary['AdaptationRate'] = summary['Adaptations'] / summary['TotalAgents']
    
    return summary

def calculate_cv_per_group(summary_df):
    """Calculate Coefficient of Variation of adaptation rate for each group."""
    results = []
    
    for (model, group), group_df in summary_df.groupby(['Model', 'Group']):
        rates = group_df['AdaptationRate'].values
        if len(rates) > 1:
            cv = np.std(rates) / np.mean(rates) if np.mean(rates) > 0 else 0
        else:
            cv = np.nan
        
        results.append({
            'Model': model,
            'Group': group,
            'MeanRate': np.mean(rates),
            'StdRate': np.std(rates),
            'CV': cv,
            'N_Years': len(rates)
        })
    
    return pd.DataFrame(results)

def plot_adaptation_trends(summary_df, output_dir):
    """Plot adaptation rate trends over simulation years."""
    os.makedirs(output_dir, exist_ok=True)
    
    for model in summary_df['Model'].unique():
        model_df = summary_df[summary_df['Model'] == model]
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        for group in sorted(model_df['Group'].unique()):
            group_df = model_df[model_df['Group'] == group]
            ax.plot(group_df['Year'], group_df['AdaptationRate'], 
                    marker='o', linewidth=2, markersize=6, label=group)
        
        ax.set_xlabel('Simulation Year', fontsize=12)
        ax.set_ylabel('Adaptation Rate', fontsize=12)
        ax.set_title(f'Adaptation Rate Over Time: {model}\n(Comparing Groups A, B, C)', 
                     fontsize=14, fontweight='bold')
        ax.legend(title='Group', loc='best')
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, 1)
        
        plt.tight_layout()
        output_path = os.path.join(output_dir, f"AdaptationTrend_{model}.png")
        plt.savefig(output_path, dpi=150)
        plt.close()
        print(f"Saved adaptation trend plot to {output_path}")

def plot_cv_comparison(cv_df, output_dir):
    """Plot CV comparison across groups (bar chart)."""
    os.makedirs(output_dir, exist_ok=True)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Pivot for grouped bar chart
    pivot = cv_df.pivot(index='Group', columns='Model', values='CV')
    pivot.plot(kind='bar', ax=ax, colormap='viridis', edgecolor='black')
    
    ax.set_xlabel('Group', fontsize=12)
    ax.set_ylabel('Coefficient of Variation (CV)', fontsize=12)
    ax.set_title('Behavioral Stability Comparison\n(Lower CV = More Consistent Behavior)', 
                 fontsize=14, fontweight='bold')
    ax.legend(title='Model')
    ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
    
    # Add value labels on bars
    for container in ax.containers:
        ax.bar_label(container, fmt='%.2f', padding=3)
    
    plt.tight_layout()
    output_path = os.path.join(output_dir, "CV_Comparison.png")
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"Saved CV comparison to {output_path}")

def perform_levene_test(df):
    """Perform Levene's test for equality of variances between groups."""
    results = []
    
    for model in df['Model'].unique():
        model_df = df[df['Model'] == model]
        groups = model_df['Group'].unique()
        
        if len(groups) < 2:
            continue
        
        # Get adaptation rates for each group
        group_data = {g: model_df[model_df['Group'] == g]['AdaptationRate'].values for g in groups}
        
        # Need at least 2 groups with data
        valid_groups = [g for g, v in group_data.items() if len(v) > 0]
        if len(valid_groups) < 2:
            continue
        
        try:
            stat, p_value = stats.levene(*[group_data[g] for g in valid_groups])
            results.append({
                'Model': model,
                'Groups': ', '.join(valid_groups),
                'Levene_Statistic': stat,
                'P_Value': p_value,
                'Significant': 'Yes' if p_value < 0.05 else 'No'
            })
        except Exception as e:
            print(f"Levene test error for {model}: {e}")
    
    return pd.DataFrame(results)

def main():
    print("=" * 60)
    print("ABC Group Comparison Analysis")
    print("=" * 60)
    
    print("\n1. Loading simulation logs...")
    df = load_all_simulation_logs(RESULTS_DIR)
    
    if df.empty:
        print("No simulation data found. Exiting.")
        return
    
    print(f"   Total entries: {len(df)}")
    print(f"   Models: {df['Model'].unique().tolist()}")
    print(f"   Groups: {df['Group'].unique().tolist()}")
    
    # Debug: Print sample decisions for each group
    for group in df['Group'].unique():
        sample = df[df['Group'] == group]
        if 'yearly_decision' in sample.columns:
            print(f"   Group {group} yearly_decision samples: {sample['yearly_decision'].unique()[:5]}")
        if 'decision' in sample.columns:
            print(f"   Group {group} decision samples: {sample['decision'].unique()[:5]}")
        if 'adaptation' in sample.columns:
            print(f"   Group {group} adaptation samples: {sample['adaptation'].unique()[:5]}")
    
    print("\n2. Calculating adaptation rates...")
    summary_df = calculate_adaptation_rate(df)
    print(summary_df.head(10))
    
    print("\n3. Calculating CV per group...")
    cv_df = calculate_cv_per_group(summary_df)
    print(cv_df.to_string(index=False))
    
    print("\n4. Performing Levene's test...")
    levene_df = perform_levene_test(summary_df)
    if not levene_df.empty:
        print(levene_df.to_string(index=False))
    else:
        print("   Not enough groups for Levene's test.")
    
    print("\n5. Generating plots...")
    plot_adaptation_trends(summary_df, OUTPUT_DIR)
    if not cv_df.empty and cv_df['CV'].notna().any():
        plot_cv_comparison(cv_df, OUTPUT_DIR)
    
    # Save summary to CSV
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    cv_df.to_csv(os.path.join(OUTPUT_DIR, "cv_summary.csv"), index=False)
    summary_df.to_csv(os.path.join(OUTPUT_DIR, "adaptation_summary.csv"), index=False)
    if not levene_df.empty:
        levene_df.to_csv(os.path.join(OUTPUT_DIR, "levene_test_results.csv"), index=False)
    
    print("\n6. Analysis complete!")
    print(f"   Plots saved to: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
