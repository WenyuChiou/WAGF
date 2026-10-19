# 3. Read the audit record

The audit CSV has one row per household decision, with lists of attempts inside
each row. Read the compact fields after [chapter 1](01-first-run.md):

```bash
python -c "import csv; from pathlib import Path; rows=list(csv.DictReader(Path('.tmp/readme-flood/household_governance_audit.csv').open(encoding='utf-8-sig'))); print([{k:r[k] for k in ('agent_id','year','initial_skill','final_skill','executed_skill','execution_path','retry_count','attempt_skills','attempt_failed_rules')} for r in rows])"
```

Both households propose `buy_insurance`, use three governance retries, and
execute `do_nothing` with `execution_path=rejected_default`. Read
`executed_skill` to identify what changed the simulation. In these rejected rows,
`final_skill` still contains `buy_insurance`; it is not the executed default.
`attempt_skills` retains four attempted choices (initial plus three retries).
`attempt_failed_rules` is `Unknown|Unknown|Unknown|Unknown` here; read
`error_messages` for the actual missing-field reason. Empty `initial_labels` and
`final_labels` mean that
the mock supplied no appraisal, not a measured low threat or coping capacity.

Read the run-level integrity record too:

```bash
python -c "import json; from pathlib import Path; r=json.loads(Path('.tmp/readme-flood/run_integrity.json').read_text()); print({k:r[k] for k in ('audit_rows','expected_rows','audit_rows_missing_vs_configured_grid','reflection_log_entries','integrity_ok')})"
```

Expected output:

```text
{'audit_rows': 2, 'expected_rows': 2, 'audit_rows_missing_vs_configured_grid': 0, 'reflection_log_entries': 0, 'integrity_ok': False}
```

Coverage is complete for this two-household grid, but reflection integrity fails.
`governance_summary.json` uses older aggregate counters that do not describe this
schema-failure path reliably; use the decision rows and integrity record above.
Some optional cognitive columns also contain placeholders, as the console warns.
See the [audit schema](../AUDIT_SCHEMA.md) for field definitions.

Next: [two-way coupling with irrigation](04-water-model.md).
