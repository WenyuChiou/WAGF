# Phase 2 - first-run recipe

The first run is the reservoir demo, the same command the front-page
`README.md` gives. It uses the built-in mock, so it needs no Ollama and no
model download, and it takes a few seconds.

## Command

```bash
python -m broker.run examples/reservoir_control/config/reservoir_agent_types.yaml --model mock --years 4 --seed 42 --output .tmp/readme-reservoir
```

`--output` must be a new directory; the runner refuses to reuse a finished one.

## What the user should see

The run ends with a summary block:

```text
Block and repair in this run:
Year 3, agent OPERATOR:
  attempt 1  BLOCKED: set_release (requested release_target=0.75) breaks dead_pool_violation: storage_unclamped >= 6.0 does not hold; the model projects storage_unclamped=5.43401 at sub-step 6 of 12 (copy projection).
  attempt 2  APPROVED: set_release at 0.5 of demand
  executed   toy reservoir release target: 0.750 -> 0.375 maf/month
  effect     storage 7.543 maf at year 3, 6.362 maf at year 4 (dead pool 6.000 maf)
```

- The scripted operator asks for all of demand every year (magnitude 1.0, a
  fraction from 0 to 1). In year 3 the dead-pool rule blocks it, and the
  operator retries at 0.5 (half of demand), which is approved.
- `operator_governance_audit.csv`: four rows, all `APPROVED`; the year 3 row has
  `retry_count` 1 and `failed_rules` `dead_pool_violation`.
- `raw/operator_traces.jsonl`: the year 3 record keeps the block reason
  (`validation_issues`) and the executed change (`execution_result`).

The answers are scripted. Tell the user this shows the loop (rule, retry,
executed effect), not a result.

## Failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| No `Block and repair in this run:` block | the run was blocked nowhere, or crashed | read stdout for the first error; confirm the command used `--model mock --years 4` |
| `Output directory ... exists` style refusal | the output directory is from an earlier run | pick a new `--output` directory |
| Import error at start | WAGF is not installed in this Python | `python -m pip install -e ".[analysis]"`, then rerun |

## Optional second step

The two paper cases in the README (flood, then irrigation) use the same mock with
their own commands and fresh output directories. They end in the configured
default, because the mock never states the appraisals those cases require; that is
a wiring check, not a block-and-repair demonstration.
