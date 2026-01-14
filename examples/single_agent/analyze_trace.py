import json
from pathlib import Path

traces_file = Path('results_modular/gemma3_4b_strict/raw/household_traces.jsonl')
traces = [json.loads(line) for line in traces_file.read_text(encoding='utf-8').splitlines()]

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
    print(f"  TP: {tp} | CP: {cp}")
    print(f"  Validation Errors: {issue_msgs}")
    print(f"  Model Reasoning: {text_reasoning[:300]}...") # Truncate for readability
    print("-" * 40)

print("\n=== ANALYSIS OF SUCCESSFUL RETRIES (How did they fix it?) ===")
for t in retry_success[:5]: # Show top 5
    agent = t['agent_id']
    approved = t.get('approved_skill', {}).get('skill_name')
    # original proposal is not stored in top-level trace, but might be in parsing_history if we logging it?
    # Actually validation_issues contains the history of failures.
    
    issues = t.get('validation_issues', [])
    initial_errors = [e for i in issues for e in i.get('errors', [])] # These are from the FAILED attempts
    
    print(f"[Agent {agent}] Final Outcome: {approved}")
    print(f"  Initial Errors: {initial_errors}")
    print("-" * 40)
