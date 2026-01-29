
import json
from pathlib import Path

def debug_14b_v2_discrepancy():
    root = Path("examples/single_agent/results/JOH_FINAL")
    model = "deepseek_r1_14b"
    group = "Group_B"
    run_dir = root / model / group / "Run_1"
    jsonl_path = run_dir / "raw" / "household_traces.jsonl"
    
    print(f"Targeting: {jsonl_path}")
    
    interv_total, interv_success, intv_hallucination = 0, 0, 0
    intv_v1, intv_v2, intv_v3 = 0, 0, 0
    
    if jsonl_path.exists():
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    retry_active = data.get('retry_count', 0) > 0
                    failed_rules = str(data.get('failed_rules', '')).lower()
                    has_rules = failed_rules and failed_rules not in ['nan', 'none', '', '[]']
                    
                    if retry_active or has_rules:
                        parsed_error = str(data.get('parsing_warnings', '') or data.get('error_messages', '')).lower()
                        combined_error = parsed_error + " " + failed_rules
                        is_syntax = ('json' in parsed_error or 'parse' in parsed_error) and not has_rules
                        
                        if 'invalid label values' in combined_error or 'missing required constructs' in combined_error:
                            interv_total += 1
                            intv_hallucination += 1
                        elif not is_syntax:
                            interv_total += 1
                            interv_success += 1
                            if 'relocation_threat_low' in failed_rules: intv_v1 += 1
                            elif 'elevation_threat_low' in failed_rules: intv_v2 += 1
                            elif 'extreme_threat_block' in failed_rules or 'builtin_high_tp_cp_action' in failed_rules: intv_v3 += 1
                            else: intv_v1 += 1
                except: continue
        
        print("\n--- Summary Matching Master Report Logic ---")
        print(f"Total Intv: {interv_total}")
        print(f"Success Intv (S): {interv_success}")
        print(f"Hallucination (H): {intv_hallucination}")
        print(f"V1: {intv_v1}, V2: {intv_v2}, V3: {intv_v3}")

if __name__ == "__main__":
    debug_14b_v2_discrepancy()
