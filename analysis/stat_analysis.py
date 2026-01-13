import pandas as pd
import numpy as np
from scipy.stats import chi2_contingency
import os

def load_and_map_baseline(path):
    df = pd.read_csv(path)
    # Mapping legacy strings to standard internal IDs
    mapping = {
        "Do Nothing": "do_nothing",
        "Only Flood Insurance": "buy_insurance",
        "Only House Elevation": "elevate_house",
        "Both Flood Insurance and House Elevation": "buy_insurance_and_elevate_house",
        "Relocate": "relocate",
        "Already relocated": "already_relocated"
    }
    df['mapped_decision'] = df['decision'].map(mapping)
    return df['mapped_decision'].fillna('unknown')

def load_and_map_new(path):
    df = pd.read_csv(path)
    # New log uses final_skill directly
    return df['final_skill'].fillna('unknown')

def perform_chi_square(group1, group2, label1, label2):
    # Get combined counts
    c1 = group1.value_counts()
    c2 = group2.value_counts()
    
    # Align categories
    all_categories = sorted(list(set(c1.index) | set(c2.index)))
    
    obs1 = [c1.get(cat, 0) for cat in all_categories]
    obs2 = [c2.get(cat, 0) for cat in all_categories]
    
    contingency = np.array([obs1, obs2])
    
    # Remove all-zero columns for Chi-square
    mask = contingency.sum(axis=0) > 0
    contingency = contingency[:, mask]
    
    chi2, p, dof, expected = chi2_contingency(contingency)
    
    print(f"\n--- Chi-square Test: {label1} vs {label2} ---")
    print(f"Categories: {[cat for i, cat in enumerate(all_categories) if mask[i]]}")
    print(f"Chi2: {chi2:.4f}, p-value: {p:.4g}")
    if p < 0.05:
        print("Result: Statistically SIGNIFICANT difference (p < 0.05)")
    else:
        print("Result: No statistically significant difference.")
    
    # Print percentages for context
    print(f"\nDistribution (%):")
    p1 = (c1 / len(group1) * 100).to_dict()
    p2 = (c2 / len(group2) * 100).to_dict()
    
    for cat in all_categories:
        v1 = p1.get(cat, 0)
        v2 = p2.get(cat, 0)
        delta = v2 - v1
        print(f"  {cat:35} | {label1}: {v1:5.1f}% | {label2}: {v2:5.1f}% | Delta: {delta:+5.1f}%")

if __name__ == "__main__":
    base_dir = r"h:\我的雲端硬碟\github\governed_broker_framework"
    
    # 1. Baseline
    baseline_path = os.path.join(base_dir, "ref", "flood_adaptation_simulation_log.csv")
    baseline_decisions = load_and_map_baseline(baseline_path)
    
    # 2. Llama 3.2 Window
    llama_window_path = os.path.join(base_dir, "examples", "single_agent", "results_window", "llama3_2_3b_strict", "household_governance_audit.csv")
    llama_window_decisions = load_and_map_new(llama_window_path)
    
    # 3. Llama 3.2 Importance
    llama_importance_path = os.path.join(base_dir, "examples", "single_agent", "results_importance", "llama3_2_3b_strict", "household_governance_audit.csv")
    if os.path.exists(llama_importance_path):
        llama_importance_decisions = load_and_map_new(llama_importance_path)
    else:
        llama_importance_decisions = None
        
    print(f"Llama 3.2 Statistical Analysis (Baseline n={len(baseline_decisions)}, Window n={len(llama_window_decisions)})")
    
    # Compare Baseline vs Window
    perform_chi_square(baseline_decisions, llama_window_decisions, "Legacy Baseline", "Llama 3.2 Window")
    
    # Compare Window vs Importance (if exists)
    if llama_importance_decisions is not None:
        perform_chi_square(llama_window_decisions, llama_importance_decisions, "Llama 3.2 Window", "Llama 3.2 Importance")
