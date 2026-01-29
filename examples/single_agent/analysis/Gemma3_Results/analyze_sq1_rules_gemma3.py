
import json
import pandas as pd
from pathlib import Path

# --- CONFIGURATION ---
BASE_DIR = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL")
OUTPUT_DIR = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\analysis\Gemma3_Results")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

models = ["gemma3_1b", "gemma3_4b", "gemma3_12b", "gemma3_27b"]
groups = ["Group_A", "Group_B", "Group_C"]

def analyze_rule_interventions():
    records = []

    for model in models:
        for group in groups:
            run_dir = BASE_DIR / model / group / "Run_1"
            jsonl_path = run_dir / "raw" / "household_traces.jsonl"
            
            # Default counters
            v1_tot = 0 # Relocation blocks
            v2_tot = 0 # Elevation blocks
            v3_tot = 0 # Do Nothing blocks
            other_tot = 0
            
            # Also count raw violations for Group A (if they exist in traces even if not blocked? 
            # In Group A, traces might show what *would* have been blocked if using Audit mode, 
            # or just raw output. 
            # For parity with DeepSeek analysis, we usually look at 'failed_rules' in trace which 
            # governed agents populate. Native agents might not have this field or it's empty.)
            
            if not jsonl_path.exists():
                # print(f"Skipping {model} {group} (No traces)")
                continue

            print(f"Analyzing {model} {group}...")
            
            try:
                with open(jsonl_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                            # 'failed_rules' lists rules that triggered an intervention
                            failed_rules = str(data.get('failed_rules', '')).lower()
                            
                            if failed_rules and failed_rules not in ['nan', 'none', '', '[]']:
                                if 'relocation_threat_low' in failed_rules:
                                    v1_tot += 1
                                elif 'elevation_threat_low' in failed_rules:
                                    v2_tot += 1
                                elif 'extreme_threat_block' in failed_rules:
                                    v3_tot += 1
                                else:
                                    other_tot += 1
                        except: continue
            except Exception as e:
                print(f"Error reading {jsonl_path}: {e}")
                
            records.append({
                "Model": model,
                "Group": group,
                "V1_Tot": v1_tot,
                "V2_Tot": v2_tot,
                "V3_Tot": v3_tot,
                "Other_Tot": other_tot,
                "Total_Interventions": v1_tot + v2_tot + v3_tot + other_tot
            })

    if records:
        df = pd.DataFrame(records)
        output_file = OUTPUT_DIR / "sq1_gemma3_rules.csv"
        df.to_csv(output_file, index=False)
        print(f"Saved SQ1 Rule Analysis to {output_file}")
        print(df)
    else:
        print("No records found to analyze.")

if __name__ == "__main__":
    analyze_rule_interventions()
