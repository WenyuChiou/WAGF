import pandas as pd
import os
import collections
import numpy as np

OLD_LOG = r"H:\我的雲端硬碟\github\governed_broker_framework\examples\single_agent\old_results\Gemma_3_4B\flood_adaptation_simulation_log.csv"
NEW_LOG = "simulation_log_interim.csv"

def calculate_entropy(decisions):
    if not decisions: return 0.0
    counts = collections.Counter(decisions)
    total = sum(counts.values())
    probs = [c/total for c in counts.values()]
    return -sum(p * np.log2(p) for p in probs)

def analyze_log(path, label):
    print(f"\n--- Analyzing {label} ---")
    if not os.path.exists(path):
        print("File not found.")
        return

    try:
        df = pd.read_csv(path)
        print(f"Columns: {list(df.columns)}")
        
        # Normalize column names
        if "decision" in df.columns: decision_col = "decision"
        elif "yearly_decision" in df.columns: decision_col = "yearly_decision"
        else: decision_col = "cumulative_state" # Fallback
        
        print(f"Using Decision Column: {decision_col}")

        # Diversity by Year
        print("\nDecision Entropy (Diversity) by Year:")
        for year in sorted(df['year'].unique()):
            yearly_data = df[df['year'] == year]
            decisions = yearly_data[decision_col].tolist()
            entropy = calculate_entropy(decisions)
            top_decisions = collections.Counter(decisions).most_common(3)
            print(f"Year {year}: Entropy={entropy:.3f} | Top: {top_decisions}")

        # Memory Analysis for Agent_5 (Sample)
        print("\nMemory Sample (Agent_5):")
        agent_5 = df[df['agent_id'] == 'Agent_5'].sort_values('year')
        for _, row in agent_5.iterrows():
            year = row['year']
            mem = row['memory']
            # Check if year 3 flood is in memory
            has_y3_flood = "Year 3:" in str(mem) and ("flooded" in str(mem).lower() or "damage" in str(mem).lower())
            print(f"Year {year} Memory Length: {len(str(mem))} | Has Y3 Record: {'Year 3' in str(mem)}")
            if year in [5, 8]:
                print(f"  -> Content: {mem}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_log(OLD_LOG, "BASELINE (Old Results)")
    analyze_log(NEW_LOG, "FRAMEWORK (New Results)")
