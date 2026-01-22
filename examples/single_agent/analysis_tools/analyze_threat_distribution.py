import json
import os
import argparse
from collections import Counter

def analyze_traces(file_path):
    print(f"Analyzing: {file_path}")
    if not os.path.exists(file_path):
        print("File not found.")
        return

    tp_counts = Counter()
    decision_counts = Counter()
    action_threat_pairs = Counter()
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                # Extract decision and TP_LABEL
                # Depending on how the log is structured, these might be in different places.
                # Based on previous view_file, 'skill_proposal' has 'reasoning' which has 'TP_LABEL'.
                # And 'approved_skill' has 'skill_name'.
                
                skill_name = "unknown"
                tp_label = "unknown"
                
                if 'skill_proposal' in data:
                    prop = data['skill_proposal']
                    skill_name = prop.get('skill_name', 'unknown')
                    if 'reasoning' in prop and isinstance(prop['reasoning'], dict):
                        tp_label = prop['reasoning'].get('TP_LABEL', 'unknown')
                
                tp_counts[tp_label] += 1
                decision_counts[skill_name] += 1
                action_threat_pairs[(skill_name, tp_label)] += 1
                
            except json.JSONDecodeError:
                pass

    print("\n--- Threat Appraisal Distribution ---")
    for label, count in tp_counts.most_common():
        print(f"{label}: {count}")

    print("\n--- Decision Distribution ---")
    for skill, count in decision_counts.most_common():
        print(f"{skill}: {count}")

    print("\n--- Action + Threat Pairs (Top 20) ---")
    for (skill, tp), count in action_threat_pairs.most_common(20):
        print(f"{skill} + {tp}: {count}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("gemma_path", help="Path to Gemma traces")
    parser.add_argument("llama_path", help="Path to Llama traces")
    args = parser.parse_args()

    print("=== GEMMA RESULTS ===")
    analyze_traces(args.gemma_path)
    print("\n" + "="*30 + "\n")
    print("=== LLAMA RESULTS ===")
    analyze_traces(args.llama_path)
