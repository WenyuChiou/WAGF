import json
import csv
from pathlib import Path

def fix_csv(results_dir):
    results_dir = Path(results_dir)
    jsonl_path = results_dir / "raw" / "household_traces.jsonl"
    csv_path = results_dir / "household_governance_audit.csv"
    
    if not jsonl_path.exists():
        print(f"JSONL not found at {jsonl_path}")
        return

    print(f"Processing {results_dir.name}...")
    
    # 1. Read all traces to get all possible keys
    traces = []
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                traces.append(json.loads(line))
            except:
                continue
    
    if not traces:
        print("No traces found.")
        return

    # 2. Build flat rows (same logic as audit_writer.py)
    flat_rows = []
    for t in traces:
        row = {
            "step_id": t.get("step_id"),
            "year": t.get("year"),
            "timestamp": t.get("timestamp"),
            "agent_id": t.get("agent_id"),
            "status": t.get("approved_skill", {}).get("status", "UNKNOWN"),
            "retry_count": t.get("retry_count", 0),
            "validated": t.get("validated", True),
            "llm_retries": t.get("llm_retries", 0),
            "llm_success": t.get("llm_success", True)
        }
        
        skill_prop = t.get("skill_proposal", {})
        row["proposed_skill"] = skill_prop.get("skill_name")
        row["final_skill"] = t.get("approved_skill", {}).get("skill_name")
        
        reasoning = skill_prop.get("reasoning", {})
        if isinstance(reasoning, dict):
            for k, v in reasoning.items():
                row[f"reason_{k.lower()}"] = v
        
        issues = t.get("validation_issues", [])
        if issues:
            row["failed_rules"] = "|".join([str(i.get('rule_id', 'Unknown')) for i in issues])
        else:
            row["failed_rules"] = ""
            
        flat_rows.append(row)

    # 3. Write CSV
    if flat_rows:
        priority_keys = ["step_id", "year", "agent_id", "proposed_skill", "final_skill", "status", "retry_count", "validated", "failed_rules"]
        all_keys = list(flat_rows[0].keys())
        fieldnames = priority_keys + [k for k in all_keys if k not in priority_keys]
        
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(flat_rows)
        print(f"Successfully updated {csv_path}")

if __name__ == "__main__":
    # Fix Llama and Gemma Window results
    fix_csv("examples/single_agent/results_window/llama3_2_3b_strict")
    fix_csv("examples/single_agent/results_window/gemma3_4b_strict")
