import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.stats import chi2_contingency

# Setup
BASE_DIR = Path("h:/我的雲端硬碟/github/governed_broker_framework/examples/single_agent")
OLD_DIR = BASE_DIR / "results_old"
WINDOW_DIR = BASE_DIR / "results_window_v2"
OUTPUT_DIR = BASE_DIR / "benchmark_analysis"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MODELS = [
    {"old": "Gemma_3_4B", "new": "gemma3_4b_strict", "label": "Gemma 3 (4B)"},
    {"old": "Llama_3.2_3B", "new": "llama3_2_3b_strict", "label": "Llama 3.2 (3B)"},
    {"old": "DeepSeek_R1_8B", "new": "deepseek_r1_8b_strict", "label": "DeepSeek R1 (8B)"},
    {"old": "GPT-OSS_20B", "new": "gpt_oss_latest_strict", "label": "GPT-OSS (20B)"}
]

STATE_ORDER = [
    "Do Nothing",
    "Only Flood Insurance",
    "Only House Elevation",
    "Both Flood Insurance and House Elevation",
    "Relocate"
]

def load_final_distribution(path, is_old=True):
    csv_file = "flood_adaptation_simulation_log.csv" if is_old else "simulation_log.csv"
    p = path / csv_file
    if not p.exists():
        return None
    df = pd.read_csv(p)
    # Get Year 10
    y10 = df[df['Year' if 'Year' in df.columns else 'year'] == 10]
    
    # Map column names if needed
    dec_col = 'Cumulative_State' if 'Cumulative_State' in y10.columns else ('decision' if 'decision' in y10.columns else 'cumulative_state')
    
    counts = y10[dec_col].value_counts().reindex(STATE_ORDER, fill_value=0)
    return counts

def run_stats():
    results = []
    fig, axes = plt.subplots(2, 4, figsize=(20, 10))
    
    for i, m in enumerate(MODELS):
        old_counts = load_final_distribution(OLD_DIR / m["old"], is_old=True)
        new_counts = load_final_distribution(WINDOW_DIR / m["new"], is_old=False)
        
        if old_counts is None or new_counts is None:
            print(f"Missing data for {m['label']}")
            continue
            
        # Chi-Square
        obs = np.array([old_counts.values, new_counts.values])
        # Add small epsilon to avoid zeros if necessary, but chi2 handles it usually
        chi2, p_val, dof, expected = chi2_contingency(obs + 0.001)
        
        results.append({
            "Model": m["label"],
            "Chi2": chi2,
            "P-Value": p_val,
            "Significant": p_val < 0.05
        })
        
        # Plotting
        ax_old = axes[0, i]
        ax_new = axes[1, i]
        
        old_counts.plot(kind='barh', ax=ax_old, color='skyblue')
        new_counts.plot(kind='barh', ax=ax_new, color='salmon')
        
        ax_old.set_title(f"{m['label']} (Old)")
        ax_new.set_title(f"{m['label']} (Window)")
        
        ax_old.set_xlabel("Agent Count")
        ax_new.set_xlabel("Agent Count")
        
        if i > 0:
            ax_old.set_yticklabels([])
            ax_new.set_yticklabels([])
            
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "old_vs_window_comparison_v3_2.png")
    
    stats_df = pd.DataFrame(results)
    stats_df.to_csv(OUTPUT_DIR / "chi_square_results.csv", index=False)
    print(stats_df)
    
    # Behavioral Audit Summary
    print("\nBehavioral Audit (High Threat Consistency):")
    for m in MODELS:
        audit_p = WINDOW_DIR / m["new"] / "audit_summary.json"
        if audit_p.exists():
            import json
            with open(audit_p, 'r') as f:
                audit = json.load(f)
            print(f"  {m['label']}: Validation Errors = {audit.get('validation_errors', 'N/A')}")
            
if __name__ == "__main__":
    run_stats()
