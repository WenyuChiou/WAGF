
import json

file_path = "examples/single_agent/results/JOH_FINAL/deepseek_r1_1_5b/Group_B/Run_1/raw/household_traces.jsonl"

print(f"Searching: {file_path}")

target_agent = "Agent_6"
target_year = 2 # Based on previous finding

with open(file_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
            # Generalized Ghost Hunt
            reasoning = data.get('skill_proposal', {}).get('reasoning', {})
            ta = (reasoning.get('TP_LABEL') or reasoning.get('threat_appraisal', {}).get('label'))
            
            # Check if TA is missing/null but Decision is Relocate
            skill = data.get('skill_proposal', {}).get('skill_name', '').lower()
            
            if 'relocate' in skill and not ta:
                print(f"\n=== FOUND GHOST TRACE: {data.get('agent_id')} Y{data.get('year')} ===")
                print("Decided:", skill)
                print("Reasoning Object:", json.dumps(reasoning, indent=2))
                print("\n--- RAW LLM OUTPUT ---")
                print(str(data.get('raw_output'))[:1000]) # Trucate to avoid massive output
                break

        except: continue
