import pandas as pd
from pathlib import Path

BASE_PATH = Path(r"H:\我的雲端硬碟\github\governed_broker_framework\examples\single_agent\results\JOH_FINAL\gemma3_4b\Group_C")
RUNS = ["Run_1", "Run_2", "Run_3"]

def calculate_rationality():
    total_approved = 0
    total_rejected = 0
    
    for run in RUNS:
        audit_path = BASE_PATH / run / "gemma3_4b_strict" / "household_governance_audit.csv"
        if not audit_path.exists():
            print(f"Warning: {audit_path} not found.")
            continue
            
        df = pd.read_csv(audit_path)
        counts = df['status'].value_counts()
        
        total_approved += counts.get('APPROVED', 0)
        total_rejected += counts.get('REJECTED', 0)
        
    print(f"Aggregated Group C Results:")
    print(f"Total Approved: {total_approved}")
    print(f"Total Rejected: {total_rejected}")
    
    if (total_approved + total_rejected) > 0:
        rs = total_approved / (total_approved + total_rejected)
        print(f"Rationality Score (RS): {rs:.4f}")
    else:
        print("No audit data found.")

if __name__ == "__main__":
    calculate_rationality()
