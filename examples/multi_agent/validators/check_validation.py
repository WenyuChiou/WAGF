"""Analyze validation errors from audit log"""
import json

records = [json.loads(l) for l in open('examples/exp3_multi_agent/results/household_audit.jsonl', encoding='utf-8')]

# Find examples with SC parse failure
print("=== SC Parse Failure Examples ===")
count = 0
for r in records:
    if 'Failed to parse SC' in str(r.get('validation_errors', [])):
        if count < 5:
            print(f"Agent: {r['agent_id']}, Year: {r['year']}")
            print(f"SC level: {r['constructs']['SC']['level']}")
            sc_exp = r['constructs']['SC']['explanation']
            print(f"SC explanation: {sc_exp[:80] if sc_exp else 'None'}...")
            print("---")
            count += 1

print(f"\nTotal SC parse failures: {sum(1 for r in records if 'Failed to parse SC' in str(r.get('validation_errors', [])))}")

# Check actual validation rule triggers (not parse errors)
from collections import defaultdict
rule_triggers = defaultdict(int)

for r in records:
    for err in r.get('validation_errors', []):
        if err.startswith('R'):
            rule_id = err.split(':')[0]
            rule_triggers[rule_id] += 1

print("\n=== Actual Rule Triggers ===")
for rule_id, count in sorted(rule_triggers.items(), key=lambda x: -x[1]):
    print(f"{rule_id}: {count}")
