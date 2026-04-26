# Phase 2 — smoke test recipe

The two scripts at `examples/quickstart/` form the canonical WAGF
smoke test. Both are short (~5 agents × 2 years) and produce
`simulation_log.csv` in their respective output directories.

## Commands

```bash
# Without governance — pure LLM, no broker validation
python examples/quickstart/01_barebone.py

# With governance — full broker pipeline
python examples/quickstart/02_governance.py
```

Each script auto-creates `examples/quickstart/results/<timestamp>/`.

## What the user should see

### `01_barebone.py` output (no governance)

- Prints per-year action distribution.
- Typical pattern: agents propose `increase_demand` even under
  shortage (irrational behaviour, no validator to block).
- Writes `simulation_log.csv`, `governance_audit.csv` (if scaffolded),
  and `raw/*.jsonl`.

### `02_governance.py` output (with governance)

- Prints per-year action distribution + per-rule rejection counts.
- Typical pattern: increase rate halves under high-shortage
  appraisals; rejected proposals retry as `maintain` or `decrease`.
- Writes the same artefacts plus a richer
  `irrigation_farmer_governance_audit.csv` with `failed_rules`,
  `retry_count`, `construct_*` columns.

## Diff to highlight

After both scripts run, compute the increase-rate diff:

```python
import pandas as pd
df_barebone = pd.read_csv("examples/quickstart/results/<bare>/simulation_log.csv")
df_gov      = pd.read_csv("examples/quickstart/results/<gov>/simulation_log.csv")

inc_bare = (df_barebone["yearly_decision"].str.startswith("increase")).mean()
inc_gov  = (df_gov["yearly_decision"].str.startswith("increase")).mean()

print(f"Increase rate without governance: {inc_bare:.1%}")
print(f"Increase rate with governance:    {inc_gov:.1%}")
print(f"Reduction:                        {(inc_bare - inc_gov) * 100:.1f} pp")
```

A reduction of ≥ 10 pp confirms the broker pipeline is working. A
zero or negative reduction is a smoke-test failure → debug before
advancing.

## Failure modes

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `connection refused localhost:11434` | Ollama daemon not running | `ollama serve` or open Ollama app |
| `model not found: gemma3:4b` | model not pulled | `ollama pull gemma3:4b` |
| `TypeError: expected str instance, dict found` | broker memory pipeline mismatch (should not happen post-2026-04-25; if it does, your repo checkout is stale) | `git pull` or `git checkout main` |
| Empty `simulation_log.csv` | Python script crashed mid-run | Inspect stdout; check `examples/quickstart/results/<dir>/raw/*.jsonl` for the last decision before the crash |
| `0 pp reduction` between barebone and governance | broker pipeline did not engage | Confirm `02_governance.py` actually loads the governance config; check the logged `governance_profile` field |

See `references/troubleshooting.md` for fuller diagnostics.

## What this phase does NOT verify

- Statistical reproducibility (use `abm-reproducibility-checker`).
- Cross-model behaviour (use `wagf-experiment-designer`).
- Memory / reflection module health (use the audit-trace analyser if
  suspicious).

This is a minimal "broker pipeline runs end-to-end" check.
