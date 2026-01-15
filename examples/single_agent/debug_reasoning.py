import json
from pathlib import Path

path = Path("examples/single_agent/results_window/llama3_2_3b_strict/raw/household_traces.jsonl")

def inspect():
    if not path.exists():
        print("JSONL not found.")
        return

    print("--- Inspecting Year 5 vs 6 Reasoning ---")
    agents_of_interest = {} # agent_id -> {5: trace, 6: trace}

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                t = json.loads(line)
                # Infer year from step_id if agents=100
                year = (t['step_id'] - 1) // 100 + 1
                if year in [5, 6]:
                    aid = t['agent_id']
                    if aid not in agents_of_interest:
                        agents_of_interest[aid] = {}
                    agents_of_interest[aid][year] = t
            except:
                continue

    # Find agents who have both Y5 and Y6 and same decision
    count = 0
    for aid, years in agents_of_interest.items():
        if 5 in years and 6 in years:
            d5 = years[5].get('approved_skill',{}).get('skill_name')
            d6 = years[6].get('approved_skill',{}).get('skill_name')
            if d5 == d6 == 'do_nothing':
                count += 1
                if count <= 3:
                    print(f"\nAgent: {aid}")
                    for y in [5, 6]:
                        reasoning = years[y].get('skill_proposal', {}).get('reasoning', {})
                        tp = reasoning.get('TP_THOUGHTS', '') if isinstance(reasoning, dict) else str(reasoning)
                        cp = reasoning.get('CP_THOUGHTS', '') if isinstance(reasoning, dict) else ''
                        print(f"  Year {y}: Decision={d5}")
                        print(f"    Threat: {tp[:300]}...")
                        print(f"    Coping: {cp[:300]}...")
                if count >= 3: break

if __name__ == "__main__":
    inspect()
