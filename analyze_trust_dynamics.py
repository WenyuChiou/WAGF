import pandas as pd
import sys

LOG_FILE = "simulation_log_interim.csv"

def analyze_logs():
    try:
        df = pd.read_csv(LOG_FILE)
        print(f"--- Log Analysis: {LOG_FILE} ---")
        print(f"Total Rows: {len(df)}")
        print(f"Agents: {df['agent_id'].nunique()}")
        print(f"Years: {df['year'].unique()}")
        
        # 1. Trust Score Evolution
        print("\n--- Average Trust Scores by Year ---")
        trust_stats = df.groupby('year')[['trust_insurance', 'trust_neighbors']].agg(['mean', 'std'])
        print(trust_stats)
        
        # 2. Decision Diversity by Year
        print("\n--- Decision Counts by Year ---")
        decisions = df.groupby(['year', 'cumulative_state']).size().unstack(fill_value=0)
        print(decisions)
        
        # 3. Check for Static "0.5" Trust (Bug Indicator)
        exact_05 = df[(df['trust_insurance'] == 0.5) & (df['year'] > 1)]
        if len(exact_05) > 0:
            print(f"\n[WARNING] Found {len(exact_05)} rows in Year > 1 with exactly 0.5 trust (Possible Reset Bug).")
        else:
            print("\n[SUCCESS] No rows in Year > 1 have exactly 0.5 trust. Variance confirmed.")

        # 4. Check for Trust "Drafting" (Is it moving?)
        # Compare Year 1 vs Year 10 Distribution
        y1_trust = df[df['year'] == 1]['trust_insurance'].mean()
        y10_trust = df[df['year'] == df['year'].max()]['trust_insurance'].mean()
        print(f"\nTrust Drift: Year 1 ({y1_trust:.3f}) -> Year {df['year'].max()} ({y10_trust:.3f})")

    except Exception as e:
        print(f"Error reading log: {e}")

if __name__ == "__main__":
    analyze_logs()
