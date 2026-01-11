import pandas as pd
import os

def analyze_shift(csv_path):
    if not os.path.exists(csv_path):
        print("Log not found.")
        return
    
    df = pd.read_csv(csv_path)
    
    # Analyze by Year
    years = [2, 3, 4, 5]
    print(f"{'Year':<5} | {'Flood':<6} | {'Avg TP':<10} | {'Do Nothing %':<12} | {'Retry %':<10}")
    print("-" * 55)
    
    for y in range(1, 11):
        # We need to map step_id to year. 100 agents per year.
        # Year 1: 1-100, Year 2: 101-200, etc.
        start = (y-1) * 100 + 1
        end = y * 100
        
        mask = (df['step_id'] >= start) & (df['step_id'] <= end)
        year_data = df[mask]
        
        if len(year_data) == 0: continue
        
        dn_count = len(year_data[year_data['approved_skill'] == 'do_nothing'])
        retry_count = len(year_data[year_data['outcome'] == 'RETRY_SUCCESS'])
        
        # Threat labels count
        tp_high = len(year_data[year_data['TP_LABEL'] == 'High'])
        
        print(f"{y:<5} | {y in [3,4,9]:<6} | {tp_high:<10} | {dn_count/len(year_data)*100:<12.1f} | {retry_count/len(year_data)*100:<10.1f}")

    print("\n[Validation Issues in Year 3/4]")
    critical_years_mask = (df['step_id'] >= 201) & (df['step_id'] <= 400)
    samples = df[critical_years_mask & (df['outcome'] == 'RETRY_SUCCESS')].head(5)
    for _, row in samples.iterrows():
        print(f"Agent {row['agent_id']} (Step {row['step_id']}):")
        print(f"  Reasoning: TP={row['TP_LABEL']}, CP={row['CP_LABEL']}")
        print(f"  Issues: {row['issues']}")
        print(f"  Final Decision: {row['approved_skill']}")
        print("-" * 20)

if __name__ == "__main__":
    analyze_shift("results/gemma3_4b/household_audit.csv")
