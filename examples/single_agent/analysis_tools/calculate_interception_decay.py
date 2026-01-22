import pandas as pd
import os
from pathlib import Path
from collections import defaultdict

def analyze_decay_csv():
    # Initialize counts for interception and total proposals per group and year
    counts = {
        "Group_B": defaultdict(lambda: {'total': 0, 'intercepted': 0}),
        "Group_C": defaultdict(lambda: {'total': 0, 'intercepted': 0})
    }

    base_dir = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL\gemma3_4b")
    
    for group in ["Group_B", "Group_C"]:
        group_path = base_dir / group
        if not group_path.exists(): 
            continue
        
        runs = sorted(list(group_path.glob("Run_*")))
        print(f"Processing {group}: {len(runs)} runs")
        
        for run in runs:
            audit_files = list(run.rglob("household_governance_audit.csv"))
            if not audit_files: continue
            
            audit_path = audit_files[0]
            
            try:
                df = pd.read_csv(audit_path)
                
                # Infer year from step_id if year column is empty or NA
                if 'year' not in df.columns or df['year'].isnull().all():
                    if 'step_id' in df.columns:
                        # step_id 1-100 is Year 1, 101-200 is Year 2
                        df['year'] = ((df['step_id'] - 1) // 100) + 1
                    else:
                        print(f"    DEBUG: No year or step_id column in {audit_path}")
                        continue
                
                df['is_intercepted'] = (
                    (df['validated'] == False) | 
                    (df['retry_count'] > 0) | 
                    (df['proposed_skill'] != df['final_skill']) |
                    (df['status'] != 'APPROVED')
                )
                
                # Aggregate by year
                yearly = df.groupby('year').agg(
                    total=('agent_id', 'count'),
                    intercepted=('is_intercepted', 'sum')
                ).to_dict('index')
                
                for year, data in yearly.items():
                    year_val = int(year)
                    if year_val > 10: continue
                    counts[group][year_val]['total'] += data['total']
                    counts[group][year_val]['intercepted'] += data['intercepted']
                    
            except Exception as e:
                print(f"    ERROR processing {audit_path}: {e}")

    print("\nInterception Decay Analysis (Interventions per Year)")
    print(f"{'Year':<5} | {'Group B (%)':<15} | {'Group C (%)':<15}")
    print("-" * 40)
    for y in range(1, 11):
        rate_b = 0.0
        if counts['Group_B'][y]['total'] > 0:
            rate_b = (counts['Group_B'][y]['intercepted'] / counts['Group_B'][y]['total']) * 100
            
        rate_c = 0.0
        if counts['Group_C'][y]['total'] > 0:
            rate_c = (counts['Group_C'][y]['intercepted'] / counts['Group_C'][y]['total']) * 100
            
        print(f"{y:<5} | {rate_b:<15.2f} | {rate_c:<15.2f}")
    
    # Show raw totals
    total_b = sum(counts['Group_B'][y]['intercepted'] for y in range(1, 11))
    total_c = sum(counts['Group_C'][y]['intercepted'] for y in range(1, 11))
    
    total_steps_b = sum(counts['Group_B'][y]['total'] for y in range(1, 11))
    total_steps_c = sum(counts['Group_C'][y]['total'] for y in range(1, 11))
    
    print(f"\nTotal Interventions: Group B = {total_b} ({total_steps_b} steps), Group C = {total_c} ({total_steps_c} steps)")

if __name__ == "__main__":
    analyze_decay_csv()
