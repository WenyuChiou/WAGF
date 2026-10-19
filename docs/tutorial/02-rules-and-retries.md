# 2. See a rule block a decision and retry

Use the flood output from [chapter 1](01-first-run.md). The existing skill output
schema requires `threat_appraisal` and `coping_appraisal`; the built-in mock
returns only `{"decision": 1}`. No new rule or scripted answer is needed.

Inspect the first household's audit:

```bash
python -c "import csv; from pathlib import Path; r=next(csv.DictReader(Path('.tmp/readme-flood/household_governance_audit.csv').open(encoding='utf-8-sig'))); print({k:r[k] for k in ('agent_id','initial_skill','retry_count','failed_rules','error_messages','executed_skill','execution_path')})"
```

Expected output:

```text
{'agent_id': 'Agent_1', 'initial_skill': 'buy_insurance', 'retry_count': '3', 'failed_rules': 'Unknown', 'error_messages': 'Response missing required fields: threat_appraisal, coping_appraisal', 'executed_skill': 'do_nothing', 'execution_path': 'rejected_default'}
```

The skill output-schema check blocks the missing fields. In these rows the
audit records the blocking message, but `failed_rules` and the per-attempt rule
IDs are `Unknown`; it does not retain a named study rule for this failure.
The console shows `Governance:Retry` attempts 1, 2 and 3;
the mock repeats its incomplete response, so it never supplies a corrected
decision. After the retries, the configured default `do_nothing` executes.
The [retry feedback guide](../guides/retry_feedback_guide.md) explains how the framework tells the agent why a proposal was returned and what it may do next.
This is a schema-blocking example, not evidence that an appraisal/action
consistency rule was exercised: the mock never states an appraisal.

The rule's required fields are defined in
[`agent_types.yaml`](../../examples/single_agent/agent_types.yaml), and skill
validation uses [`skill_registry.yaml`](../../examples/single_agent/skill_registry.yaml).
See the [governance guide](../guides/governance_layers.md) for adding study-specific
rules. This tutorial leaves the example's behaviour unchanged.

Next: [read proposals and executed actions separately](03-audit.md).
