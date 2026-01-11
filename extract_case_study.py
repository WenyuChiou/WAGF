import json
import sys

def extract_case(log_path, year, decision_keyword):
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            entry = json.loads(line)
            if entry.get('year') == year and decision_keyword.lower() in str(entry.get('approved_skill', {})).lower():
                print(json.dumps(entry, indent=2))
                return

if __name__ == "__main__":
    extract_case("results_v4.2/llama_final/llama3.2_3b/household_audit.jsonl", 1, "relocate")
