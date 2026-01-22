
import json
import re
from pathlib import Path
from collections import defaultdict

# PMT Lexicon Definition (Hardcoded as per Methodology)
PMT_LEXICON = {
    "Severity": [
        "severe", "danger", "deadly", "catastrophe", "critical", "devastat", 
        "destroy", "loss", "damage", "threat", "crisis", "lethal", "fatal"
    ],
    "Vulnerability": [
        "risk", "likely", "prone", "exposed", "susceptible", "vulnerable", 
        "chance", "probability", "unsafe", "insecure", "weakness"
    ],
    "Response_Efficacy": [
        "effective", "protect", "prevent", "safe", "solution", "mitigate", 
        "reduce", "secure", "work", "useful", "benefit", "defend"
    ],
    "Cost": [
        "cost", "expensive", "afford", "price", "budget", "cheap", 
        "money", "fund", "financial", "fee", "pay", "spend"
    ]
}

def count_keywords(text):
    counts = defaultdict(int)
    text_lower = text.lower()
    for category, words in PMT_LEXICON.items():
        for word in words:
            # Simple substring check (robust for "devastating", "devastated")
            if word in text_lower:
                counts[category] += text_lower.count(word)
    return counts

def analyze_file(filepath):
    print(f"Analyzing: {filepath}")
    total_records = 0
    total_counts = defaultdict(int)
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                # Check different possible fields where reasoning might be stored
                input_prompt = data.get('input', '')
                output_content = data.get('output', '')
                
                # Combine input and output for full context analysis
                full_text = input_prompt + "\n" + output_content
                
                step_counts = count_keywords(full_text)
                for cat, count in step_counts.items():
                    total_counts[cat] += count
                
                total_records += 1
            except Exception as e:
                continue

    print("-" * 30)
    print(f"Total Records Analyzed: {total_records}")
    print("-" * 30)
    print("PMT Keyword Counts (Raw Frequency):")
    for cat in ["Severity", "Vulnerability", "Response_Efficacy", "Cost"]:
        avg = total_counts[cat] / total_records if total_records > 0 else 0
        print(f"{cat}: {total_counts[cat]} (Avg: {avg:.2f}/agent)")


if __name__ == "__main__":
    base_path = r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\BENCHMARK_2026\deepseek_r1_8b"
    path_a = f"{base_path}\\Group_A\\Run_1\\deepseek_r1_8b\\raw\\household_traces.jsonl"
    path_b = f"{base_path}\\Group_B\\Run_1\\deepseek_r1_8b_strict\\raw\\household_traces.jsonl"
    
    print("="*60)
    print("COMPARATIVE PMT ANALYSIS: GROUP A (Control) vs GROUP B (Governed)")
    print("="*60)

    print("\n>>> Analyzing GROUP A (Control)...")
    stats_a, count_a = analyze_file(path_a)

    print("\n>>> Analyzing GROUP B (Governed)...")
    stats_b, count_b = analyze_file(path_b)

    print("\n" + "="*60)
    print(f"{'CATEGORY':<20} | {'GROUP A (Avg)':<15} | {'GROUP B (Avg)':<15} | {'DELTA (%)':<10}")
    print("-" * 60)
    
    categories = ["Severity", "Vulnerability", "Response_Efficacy", "Cost"]
    for cat in categories:
        avg_a = stats_a[cat] / count_a if count_a > 0 else 0
        avg_b = stats_b[cat] / count_b if count_b > 0 else 0
        
        if avg_a > 0:
            delta = ((avg_b - avg_a) / avg_a) * 100
            diff_str = f"{delta:+.1f}%"
        else:
            diff_str = "N/A"
            
        print(f"{cat:<20} | {avg_a:<15.2f} | {avg_b:<15.2f} | {diff_str:<10}")
    print("="*60)
