
import os
import json
import pandas as pd
from collections import defaultdict

ROOT_DIR = r"results/JOH_FINAL"
REPORT_FILE = "analysis_report.md"
NUM_AGENTS = 100

def analyze():
    stats = defaultdict(lambda: defaultdict(int))
    run_counts = defaultdict(set)
    other_decisions = set()
    
    print(f"Scanning {ROOT_DIR}...")
    
    for root, dirs, files in os.walk(ROOT_DIR):
        if "household_traces.jsonl" in files:
            parts = os.path.normpath(root).split(os.sep)
            try:
                if "JOH_FINAL" in parts:
                    idx = parts.index("JOH_FINAL")
                    if idx + 2 < len(parts):
                        group = parts[idx + 2]
                        run = parts[idx + 3]
                    else:
                        continue
                else:
                    continue
            except:
                continue

            run_counts[group].add(run)
            path = os.path.join(root, "household_traces.jsonl")
            
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if not line.strip(): continue
                        try:
                            record = json.loads(line)
                            step = record.get('step_id')
                            if step is None: continue
                            
                            # Heuristic: Map global step to Year
                            year = step
                            if step > 100: # Assuming simple year ID is small
                                year = (step - 1) // NUM_AGENTS + 1
                            elif step > 10 and step <= 100:
                                # Ambiguous range if step_id is mixed. 
                                # But usually step_id 1..10 is Year. 
                                # If step_id 11..100, maybe it's Year 11..100?
                                year = step 
                            
                            # Extract Decision from nested structure
                            decision = "Unknown"
                            approved = record.get('approved_skill')
                            if isinstance(approved, dict):
                                decision = approved.get('skill_name', 'Unknown')
                            else:
                                # Fallback if key existed differently
                                decision = record.get('decision', 'Unknown')

                            # Normalize decision string
                            d_norm = str(decision).strip().lower()
                            
                            key = (group, year)
                            
                            if d_norm in ['do_nothing', 'do nothing']:
                                d_key = 'do_nothing'
                            elif d_norm in ['buy_insurance', 'buy insurance']:
                                d_key = 'buy_insurance'
                            elif d_norm in ['elevate_house', 'elevate house', 'elevate']:
                                d_key = 'elevate_house'
                            elif d_norm in ['relocate']:
                                d_key = 'relocate'
                            else:
                                d_key = 'Others'
                                other_decisions.add(str(decision))
                            
                            stats[key][d_key] += 1
                            stats[key]['Total'] += 1
                        except:
                            pass
            except:
                pass

    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write("# Interim Simulation Analysis Report (Behavior)\n\n")
        
        if other_decisions:
            f.write(f"**Unknown Decisions Found**: {', '.join(sorted(other_decisions))}\n\n")

        for group in sorted(run_counts.keys()):
            runs = sorted(run_counts[group])
            f.write(f"## Group: {group}\n")
            f.write(f"**Runs Found**: {len(runs)}\n\n")
            
            years = sorted(list(set(k[1] for k in stats.keys() if k[0] == group)))
            if not years:
                continue

            f.write("| Year | Total | Do Nothing | Buy Insurance | Elevate House | Relocate | Others |\n")
            f.write("|---|---|---|---|---|---|---|\n")
            
            for yr in years:
                d = stats[(group, yr)]
                total = d['Total']
                if total == 0: continue
                
                row = [str(yr), str(total)]
                for action in ['do_nothing', 'buy_insurance', 'elevate_house', 'relocate']:
                    count = d.get(action, 0)
                    pct = (count / total) * 100
                    row.append(f"{count} ({pct:.1f}%)")
                
                others = d.get('Others', 0)
                row.append(str(others))
                
                # Highlight if Year 1 EH > 0
                if yr == 1 and d.get('elevate_house', 0) > 0:
                    row.append("⚠️ EH DETECTED")
                
                f.write("| " + " | ".join(row) + " |\n")
            f.write("\n")
            
    print(f"Report written to {REPORT_FILE}")

if __name__ == "__main__":
    analyze()
