import json
import sys
import argparse
from pathlib import Path

def analyze_trace_file(file_path):
    path = Path(file_path)
    if not path.exists():
        print(f"Error: File not found at {path}")
        return

    print(f"Analyzing: {path}")
    try:
        traces = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    except Exception as e:
        print(f"Error reading trace file: {e}")
        return

    # Find failed (UNCERTAIN) and RECOVERED (RETRY_SUCCESS) traces
    failed = [t for t in traces if t.get('outcome') == 'UNCERTAIN']
    retry_success = [t for t in traces if t.get('outcome') == 'RETRY_SUCCESS']

    print(f"Total traces: {len(traces)}")
    print(f"UNCERTAIN (Fallout): {len(failed)}")
    print(f"RETRY_SUCCESS (Recovered): {len(retry_success)}")
    print("-" * 60)

    print("=== ANALYSIS OF FALLOUT CASES (Why did they fail?) ===")
    for t in failed[:10]: # Show top 10
        agent = t['agent_id']
        sp = t.get('skill_proposal', {})
        skill_name = sp.get('skill_name')
        reasoning = sp.get('reasoning', {})
        tp = reasoning.get('TP_LABEL')
        cp = reasoning.get('CP_LABEL')
        
        # Extract nested reasons if available (Gemma format)
        ta_reason = reasoning.get('threat_appraisal', {}).get('reason', '') if isinstance(reasoning.get('threat_appraisal'), dict) else ''
        ca_reason = reasoning.get('coping_appraisal', {}).get('reason', '') if isinstance(reasoning.get('coping_appraisal'), dict) else ''
        
        text_reasoning = f"Threat Reason: {ta_reason}\nCoping Reason: {ca_reason}"
        if not ta_reason and not ca_reason:
             text_reasoning = reasoning.get('Reasoning', "No reasoning text found")
        
        issues = t.get('validation_issues', [])
        issue_msgs = [e for i in issues for e in i.get('errors', [])]
        
        print(f"[Agent {agent}] Proposed: {skill_name}")
        print(f"  Ratings: TP={tp} | CP={cp}")
        print(f"  Validation Errors: {issue_msgs}")
        print(f"  Model Reasoning: {str(text_reasoning)[:300]}...") # Truncate for readability
        print("-" * 40)

    print("\n=== ANALYSIS OF SUCCESSFUL RETRIES (Logic Correction) ===")
    for t in retry_success[:15]: # Show top 15
        agent = t['agent_id']
        approved = t.get('approved_skill', {}).get('skill_name')
        
        # In recovered traces, 'skill_proposal' is the FINAL successful one. 
        # But 'validation_issues' contains the history of failures.
        # We need to manually reconstruct what they *tried* to do.
        
        issues = t.get('validation_issues', [])
        initial_errors = [e for i in issues for e in i.get('errors', [])]
        
        # Try to find the original bad decision from the error message if possible
        # e.g. "Logic Block: elevate_house flagged by thinking rules"
        original_intent = "Unknown"
        for err in initial_errors:
            if "Logic Block:" in err:
                original_intent = err.split("Logic Block:")[1].split("flagged")[0].strip()
                break
        
        # Since we don't store the full *rejected* reasoning in the final trace object (to save space),
        # we can only show the error that caught it.
        # However, knowing they tried 'original_intent' but got blocked is key.
        
        print(f"[Agent {agent}] Correction: {original_intent} -> {approved}")
        print(f"  Trigger: {initial_errors}")
        print("-" * 40)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze trace logs for anomalies")
    parser.add_argument("file", nargs="?", help="Path to household_traces.jsonl")
    args = parser.parse_args()

    if args.file:
        analyze_trace_file(args.file)
    else:
        # Auto-detect latest trace in results_window if no file provided
        base_dir = Path("examples/single_agent/results_window")
        if base_dir.exists():
            traces = list(base_dir.rglob("household_traces.jsonl"))
            if traces:
                # Get the most recently modified file
                latest_trace = max(traces, key=lambda p: p.stat().st_mtime)
                analyze_trace_file(latest_trace)
            else:
                 print("No trace files found in default location.")
        else:
            print("Usage: python analyze_trace.py <path_to_jsonl>")
