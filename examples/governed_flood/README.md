# Governed Flood Adaptation Experiment

Standalone example demonstrating **Group C (Full Cognitive Governance)** — the most complete configuration of the Governed Broker Framework for flood adaptation ABM.

## Three Pillars

| Pillar | Name | Configuration | Effect |
|--------|------|---------------|--------|
| 1 | **Strict Governance** | `governance_mode: strict` + PMT thinking/identity rules | Blocks cognitively inconsistent decisions |
| 2 | **Cognitive Memory** | `HumanCentricMemoryEngine` + `ReflectionEngine` | Emotional encoding + year-end consolidation |
| 3 | **Priority Schema** | `use_priority_schema: true` | Physical reality enters context before preferences |

## Recent Enhancements

| Feature | Description |
|---------|-------------|
| **Action-Outcome Feedback** | Agents see "Year N: You chose to [skill]" in memory, enabling reflection on past decisions. |
| **Configurable Reflection** | Reflection guidance questions now defined in `agent_types.yaml` (`global_config.reflection.questions`) instead of hardcoded. |
| **Reasoning-Before-Rating** | Response format places `reasoning` field first, improving autoregressive generation quality for appraisal labels. |

## Quick Start

```bash
# Full experiment (default: gemma3:4b, 10 years, 100 agents)
python run_experiment.py

# Smaller test run
python run_experiment.py --model gemma3:4b --years 2 --agents 10

# Custom model and output
python run_experiment.py --model gemma3:4b --years 10 --agents 100 --output results/my_run
```

## Governance Rules (v22, Strict Profile)

This demo uses the strict governance profile to block cognitively inconsistent actions and log warnings.

| Rule | Severity | Description |
|------|----------|-------------|
| `extreme_threat_block` | ERROR | TP in {H, VH} blocks `do_nothing` |
| `low_coping_block` | WARNING | CP in {VL, L} observes `elevate`/`relocate` |
| `relocation_threat_low` | ERROR | TP in {VL, L} blocks `relocate` |
| `elevation_threat_low` | ERROR | TP in {VL, L} blocks `elevate` |
| `elevation_block` | ERROR | Already-elevated agent cannot re-elevate |

## Output Files

```
results/
  simulation_log.csv               # Decision log (agents x years)
  household_governance_audit.csv    # Governance validation trace
  reflection_log.jsonl              # Year-end reflection insights
  reproducibility_manifest.json     # Seed, model, config snapshot
  config_snapshot.yaml              # Actual YAML used for this run
  governance_summary.json           # Validation statistics
  raw/
    household_traces.jsonl          # Full LLM interaction traces
```

### Output Interpretation Guide

| File | Description |
|------|-------------|
| `governance_summary.json` | `total_interventions` = ERROR blocks, `warnings.total_warnings` = WARNING observations, `retry_success` = agent corrected on retry |
| `household_governance_audit.csv` | Per-agent audit trail. Key columns: `failed_rules`, `warning_rules`, `warning_messages` |
| `audit_summary.json` | Parse quality: `validation_errors` (structural parse failures), `validation_warnings` (governance warnings) |
| `config_snapshot.yaml` | Full experiment config for reproducibility |

## Difference from `single_agent/run_flood.py`

| Aspect | `run_flood.py` (1048 lines) | `run_experiment.py` (~300 lines) |
|--------|----------------------------|----------------------------------|
| Purpose | Comparative experiment (Group A/B/C) | Showcase Group C only |
| Custom classes | FinalContextBuilder, DecisionFilteredMemoryEngine, FinalParityHook | None — uses broker API directly |
| Memory engine | Dynamic selection (window/importance/humancentric) | Fixed: HumanCentricMemoryEngine |
| Governance | Configurable (strict/relaxed/disabled) | Fixed: strict |
| Stress tests | 4 profiles (veteran/panic/goldfish/format) | None |
| Survey mode | Supported | Not included |

## CLI Arguments

| Flag | Default | Description |
|------|---------|-------------|
| `--model` | `gemma3:4b` | Ollama model name |
| `--years` | `10` | Simulation years |
| `--agents` | `100` | Number of household agents |
| `--workers` | `1` | Parallel LLM workers |
| `--seed` | random | Random seed for reproducibility |
| `--memory-seed` | `42` | Memory engine seed |
| `--window-size` | `5` | Memory window size |
| `--output` | `results/` | Output directory |
| `--num-ctx` | auto | Ollama context window override |
| `--num-predict` | auto | Ollama max tokens override |
