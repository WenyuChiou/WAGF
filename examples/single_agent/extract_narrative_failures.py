import pandas as pd
from pathlib import Path
import json

BASE_MSG = "Starting Narrative Extraction..."
print(BASE_MSG)

ROOT = Path(r"H:\我的雲端硬碟\github\governed_broker_framework\examples\single_agent\results\JOH_FINAL\llama3_2_3b")
# Look for Group B first as they have governance enabled but no memory (most likely to error)
SEARCH_DIRS = [ROOT / "Group_B", ROOT / "Group_C"]

found_narratives = []

for group_dir in SEARCH_DIRS:
    if not group_dir.exists(): continue
    for run_dir in group_dir.iterdir():
        if "Run_" not in run_dir.name: continue
        
        # Find the strict folder inside
        for sub in run_dir.iterdir():
            if sub.is_dir() and "_strict" in sub.name:
                audit_csv = sub / "household_governance_audit.csv"
                if audit_csv.exists():
                    try:
                        df = pd.read_csv(audit_csv)
                        # Filter for blocks
                        blocked = df[df['status'] != 'APPROVED']
                        
                        for _, row in blocked.iterrows():
                            found_narratives.append({
                                "Group": group_dir.name,
                                "Run": run_dir.name,
                                "Year": row.get('year', 'N/A'),
                                "Agent": row.get('agent_id', 'N/A'),
                                "Action": row.get('action', 'N/A'),
                                "Error": row.get('error_msg', 'N/A'),
                                "Reasoning": str(row.get('agent_reasoning', ''))[:200] + "..." # Truncate
                            })
                            if len(found_narratives) > 5: break # Just need a few examples
                    except Exception as e:
                        print(f"Error reading {audit_csv}: {e}")
        if len(found_narratives) > 5: break

if not found_narratives:
    print("No interactions found (All Approved?). Checking logs for 'System 2 Correction' triggers if available.")
else:
    print(f"\nFound {len(found_narratives)} Interventions/Replacements:")
    for n in found_narratives:
        print(f"\n[Case: {n['Group']} / {n['Agent']} @ Year {n['Year']}]")
        print(f"  Attempted: {n['Action']}")
        print(f"  Blocked By: {n['Error']}")
        print(f"  Internal Monologue: \"{n['Reasoning']}\"")
