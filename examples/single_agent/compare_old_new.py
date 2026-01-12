"""
Old vs New Results Comparison Analysis

Compares the baseline system (old results) with the governed framework (new results).
"""

import pandas as pd
from pathlib import Path

OLD_RESULTS_DIR = Path("examples/single_agent/old results")
NEW_RESULTS_DIR = Path("examples/single_agent/results")

MODELS = [
    {"old_folder": "Gemma_3_4B", "new_folder": "gemma3_4b_strict", "name": "Gemma 3 (4B)"},
    {"old_folder": "Llama_3.2_3B", "new_folder": "llama3.2_3b_strict", "name": "Llama 3.2 (3B)"},
    {"old_folder": "DeepSeek_R1_8B", "new_folder": "deepseek-r1_8b_strict", "name": "DeepSeek-R1 (8B)"},
    {"old_folder": "GPT-OSS_20B", "new_folder": "gpt-oss_latest_strict", "name": "GPT-OSS (20B)"},
]

def load_old_log(folder: str) -> pd.DataFrame:
    """Load old baseline simulation log."""
    path = OLD_RESULTS_DIR / folder / "flood_adaptation_simulation_log.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)

def load_new_log(folder: str) -> pd.DataFrame:
    """Load new governed framework simulation log."""
    path = NEW_RESULTS_DIR / folder / "simulation_log.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)

def analyze_decision_distribution(df: pd.DataFrame, label: str) -> dict:
    """Analyze final year decision distribution."""
    if df.empty:
        return {"label": label, "total": 0, "distribution": {}}
    
    # Get final year data
    max_year = df['year'].max() if 'year' in df.columns else df['Year'].max() if 'Year' in df.columns else 10
    year_col = 'year' if 'year' in df.columns else 'Year'
    
    final_year = df[df[year_col] == max_year]
    
    # Determine decision column
    dec_col = None
    for col in ['cumulative_state', 'decision', 'Cumulative_State', 'Decision']:
        if col in final_year.columns:
            dec_col = col
            break
    
    if dec_col is None:
        return {"label": label, "total": len(final_year), "distribution": {}}
    
    dist = final_year[dec_col].value_counts().to_dict()
    return {
        "label": label,
        "total": len(final_year),
        "distribution": dist
    }

def main():
    print("=" * 70)
    print("OLD vs NEW Results Comparison Analysis")
    print("=" * 70)
    print()
    
    for model in MODELS:
        print(f"\n[MODEL] {model['name']}")
        print("-" * 50)
        
        # Load data
        old_df = load_old_log(model["old_folder"])
        new_df = load_new_log(model["new_folder"])
        
        old_analysis = analyze_decision_distribution(old_df, "Old (Baseline)")
        new_analysis = analyze_decision_distribution(new_df, "New (Governed)")
        
        # Compare
        if old_analysis["total"] == 0:
            print(f"  [!] Old results: NOT FOUND")
        else:
            print(f"  [OLD] Old results ({old_analysis['total']} agents):")
            for state, count in sorted(old_analysis["distribution"].items()):
                pct = count / old_analysis["total"] * 100
                print(f"      {state}: {count} ({pct:.1f}%)")
        
        if new_analysis["total"] == 0:
            print(f"  [!] New results: NOT FOUND")
        else:
            print(f"  [NEW] New results ({new_analysis['total']} agents):")
            for state, count in sorted(new_analysis["distribution"].items()):
                pct = count / new_analysis["total"] * 100
                print(f"      {state}: {count} ({pct:.1f}%)")
        
        # Delta
        if old_analysis["total"] > 0 and new_analysis["total"] > 0:
            print(f"  [DELTA] Key Changes:")
            all_states = set(old_analysis["distribution"].keys()) | set(new_analysis["distribution"].keys())
            for state in sorted(all_states):
                old_pct = old_analysis["distribution"].get(state, 0) / old_analysis["total"] * 100
                new_pct = new_analysis["distribution"].get(state, 0) / new_analysis["total"] * 100
                delta = new_pct - old_pct
                if abs(delta) > 5:  # Only show significant changes
                    arrow = "+" if delta > 0 else "-"
                    print(f"      {state}: {old_pct:.1f}% -> {new_pct:.1f}% ({arrow}{abs(delta):.1f}%)")
    
    print("\n" + "=" * 70)
    print("Analysis Complete")
    print("=" * 70)

if __name__ == "__main__":
    main()
