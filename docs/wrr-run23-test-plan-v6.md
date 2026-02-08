# WRR Flood Multi-Run Test Plan (Run_2 / Run_3)

## Goal

Expand flood evidence from single-run to multi-seed while preserving parameter consistency and avoiding overwrite of existing `Run_1` outputs.

## Legacy Script Audit (single_agent)

Reviewed scripts under `examples/single_agent`:

- `run_flood_replicates.sh`
- `run_ministral_all.ps1`
- `run_ministral_8b14b_BC.ps1`
- `run_gemma3_experiment.ps1`
- `run_flood_BC_v7.ps1`
- `run_ministral_groupA_baseline.ps1`
- `run_missing_BC.sh`

### Risks Found

1. Most scripts hardcode output to `Run_1`.
- Running again can overwrite or mix prior artifacts.

2. Seed inconsistency across scripts.
- Some scripts use `seed=42`, others use `seed=401`.

3. Group C parameter drift exists in older scripts.
- Some include `--use-priority-schema`, some do not.

4. Baseline mismatch risk.
- `run_ministral_groupA_baseline.ps1` uses legacy `ref/LLMABMPMT-Final.py`, not `run_flood.py` pipeline.
- For WRR v6 reproducibility, avoid mixing baseline generator logic across runs unless explicitly declared.

5. Memory seed control is often omitted.
- `run_flood.py` defaults `--memory-seed 42`.
- If only `--seed` changes but memory seed remains fixed, stochastic independence is partial.

## Locked Test Matrix (Run_2 / Run_3)

- Models:
  - `gemma3:4b`, `gemma3:12b`, `gemma3:27b`
  - `ministral-3:3b`, `ministral-3:8b`, `ministral-3:14b`
- Groups:
  - A: `--governance-mode disabled --memory-engine window`
  - B: `--governance-mode strict --memory-engine window --window-size 5`
  - C: `--governance-mode strict --memory-engine humancentric --window-size 5 --use-priority-schema`
- Common parameters:
  - `--years 10 --agents 100 --workers 1`
  - `--num-ctx 8192 --num-predict 1536`
  - `--initial-agents examples/single_agent/agent_initial_profiles.csv`
- Seeds:
  - `Run_2`: `4202`
  - `Run_3`: `4203`
- Memory seed policy:
  - Set `--memory-seed` equal to `--seed` for each run.

## Output Convention (No Overwrite)

Use strict path template:

- `examples/single_agent/results/JOH_FINAL/<model_dir>/Group_A/Run_2`
- `examples/single_agent/results/JOH_FINAL/<model_dir>/Group_A/Run_3`
- `... Group_B/Run_2`, `... Group_B/Run_3`
- `... Group_C/Run_2`, `... Group_C/Run_3`

Do not remove existing `Run_1`.

## Execution Script

Use:

- `examples/single_agent/run_flood_runs23.ps1`

This script:
- keeps parameters fixed across models/groups,
- writes only to `Run_2` and `Run_3`,
- skips a run if `simulation_log.csv` already exists (safe resume).

## Post-Run Analysis Update

After Run_2/Run_3 complete, aggregate all runs (`Run_1..Run_3`) in a dedicated metrics script version (next step) and report:

- per-model/group mean กำ CI for `R_H`, `R_R`, `H_norm_k4`, `EHE_k4`
- group-level paired deltas vs Group A
- workload metrics (`retry_sum`) separately from decision-level rates
