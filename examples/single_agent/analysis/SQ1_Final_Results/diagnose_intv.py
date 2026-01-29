
import json
from pathlib import Path

def analyze(model, group):
    path = Path(f"c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/single_agent/results/JOH_FINAL/{model}/{group}/Run_1/raw/household_traces.jsonl")
    if not path.exists():
        path = Path(f"c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/single_agent/results/JOH_FINAL/{model}/{group}/Run_1/household_traces.jsonl")
        
    summary_path = Path(f"c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/single_agent/results/JOH_FINAL/{model}/{group}/Run_1/governance_summary.json")
    
    print(f"\n--- Analysis for {model} {group} ---")
    
    # 1. Summary Ground Truth
    if summary_path.exists():
        with open(summary_path, 'r') as f:
            s = json.load(f)
            print(f"Summary Rule Hits (S): {s.get('total_interventions')}")
    
    # 2. Trace Granularity
    steps_with_retry = 0
    total_retries = 0
    logic_only_steps = 0
    format_only_steps = 0
    
    retry_sum_with_rules = 0
    retry_sum_without_rules = 0
    
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    r = data.get('retry_count', 0)
                    if r > 0:
                        steps_with_retry += 1
                        total_retries += r
                        rules = data.get('failed_rules')
                        has_rules = rules and rules != '[]'
                        
                        if has_rules:
                            logic_only_steps += 1
                            retry_sum_with_rules += r
                        else:
                            format_only_steps += 1
                            retry_sum_without_rules += r
                except: continue
                        
    print(f"Steps with Retry (Total Events): {steps_with_retry}")
    print(f"Cumulative Retries in Traces: {total_retries}")
    print(f"Steps with Logic Rules (Thinking Blocks): {logic_only_steps}")
    print(f"Steps with Format Only (Hallucinations): {format_only_steps}")
    print(f"Retry Sum (Events with Rules): {retry_sum_with_rules}")
    print(f"Retry Sum (Events without Rules): {retry_sum_without_rules}")

analyze("deepseek_r1_1_5b", "Group_B")
analyze("deepseek_r1_1_5b", "Group_C")
analyze("deepseek_r1_14b", "Group_B")
