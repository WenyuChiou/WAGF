
import pandas as pd
import glob
from pathlib import Path

root = Path("examples/single_agent/results/JOH_FINAL")
logs = glob.glob(str(root / "**" / "simulation_log.csv"), recursive=True)

print("=== CHECKING FOR GHOSTS (NAN THREATS) ===")
for log in logs:
    try:
        print(f"Processing: {log}") # Debug
        df = pd.read_csv(log)
        df.columns = [c.lower() for c in df.columns]
        
        # Handle mixed column names
        dec_col = None
        if 'decision' in df.columns: dec_col = 'decision'
        elif 'yearly_decision' in df.columns: dec_col = 'yearly_decision'
        
        if dec_col:
            relocs = df[df[dec_col].astype(str).str.contains('relocate', case=False, na=False)]
            
            # Check for NaN threat
            # Sometimes empty strings or 'nan' string
            if 'threat_appraisal' in df.columns:
                ghosts = relocs[relocs['threat_appraisal'].astype(str).str.contains('nan|None|^$', case=False, regex=True)]
                
                if len(ghosts) > 0:
                    model_name = Path(log).parent.parent.parent.name
                    group_name = Path(log).parent.parent.name
                    print(f"\nModel: {model_name} | Group: {group_name}")
                    print(f"  Total Relocations: {len(relocs)}")
                    print(f"  Ghost Relocations: {len(ghosts)} ({len(ghosts)/len(relocs):.1%})")
            else:
                print(f"\nModel/Group: {Path(log).parent.parent.name}/{Path(log).parent.name} - MISSING THREAT COLUMN")
                
    except Exception as e:
        pass
