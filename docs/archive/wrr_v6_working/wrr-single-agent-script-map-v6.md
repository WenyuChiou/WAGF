# Single-Agent Flood Experiment Script Map (v6)

## Scope

This map summarizes the latest runnable scripts under `examples/single_agent` and clarifies:
- which config files are used,
- which parameters are fixed,
- output path conventions,
- whether each script is recommended for current WRR v6 workflow.

## Core Runner (Source of Truth)

### `examples/single_agent/run_flood.py`

Primary runtime entrypoint for flood experiments (used for Group B/C in WRR v6 A/B/C setup).

Config files used internally:
- Skill registry: `examples/single_agent/skill_registry.yaml`
- Agent/governance/memory/prompt config: `examples/single_agent/agent_types.yaml`
- Prompt template path (if configured): resolved from `agent_types.yaml`

Important CLI arguments:
- `--model`
- `--governance-mode` (`strict|relaxed|disabled`)
- `--memory-engine` (`window|humancentric|importance|hierarchical`)
- `--window-size`
- `--use-priority-schema` (optional switch; default off)
- `--seed`
- `--memory-seed`
- `--num-ctx`, `--num-predict`
- `--initial-agents`
- `--output`

Output behavior:
- If `--output` is provided, results write exactly there.
- If omitted, auto path is under `examples/single_agent/results/<model>_<governance_mode>/`.

## Group Setup Confirmation

For WRR A/B/C ablation, lock setup as:
- Group A: original baseline script `ref/LLMABMPMT-Final.py` (no priority schema path)
- Group B: `run_flood.py --governance-mode strict --memory-engine window --window-size 5`
- Group C: `run_flood.py --governance-mode strict --memory-engine humancentric --window-size 5 --use-priority-schema`

## Latest Script Inventory (run_* files)

Latest commit date per script (from git history):

- `examples/single_agent/run_wrr_v6_flood.ps1` (2026-02-08)
- `examples/single_agent/run_missing_BC.sh` (2026-02-03)
- `examples/single_agent/run_flood_BC_v7.ps1` (2026-02-01)
- `examples/single_agent/run_ministral_8b14b_BC.ps1` (2026-02-01)
- `examples/single_agent/run_ministral_groupA_baseline.ps1` (2026-02-01)
- `examples/single_agent/run_flood_replicates.sh` (2026-01-31)
- `examples/single_agent/run_gemma3_experiment.ps1` (2026-01-31)
- `examples/single_agent/run_ministral_all.ps1` (2026-01-31)
- `examples/single_agent/run_ministral_all.sh` (2026-01-31)
- `examples/single_agent/run_ministral_experiments.sh` (2026-01-31)
- `examples/single_agent/run_gemma27b_groupC.sh` (2026-01-31)

## Recommended Scripts for WRR v6 Now

### Recommended

1. `examples/single_agent/run_wrr_v6_flood.ps1`
- Purpose: Run seed replication for `Run_2` and `Run_3` without overwriting `Run_1`.
- Output paths:
  - `examples/single_agent/results/JOH_FINAL/<model_dir>/Group_A/Run_2`
  - `examples/single_agent/results/JOH_FINAL/<model_dir>/Group_A/Run_3`
  - and same for Group_B/Group_C.
- Safety:
  - skips execution if `simulation_log.csv` already exists.
- Group split:
  - A via `ref/LLMABMPMT-Final.py`
  - B/C via `run_flood.py`

2. Direct `run_flood.py` command lines (manual control)
- Best when debugging one model/group with explicit parameters.

### Use with Caution (Legacy/Targeted)

- `run_flood_BC_v7.ps1`
  - Hardcodes output to `Run_1`.
  - Group C currently omits `--use-priority-schema` in this script.
- `run_ministral_all.ps1`, `run_ministral_8b14b_BC.ps1`, `run_flood_replicates.sh`, `run_missing_BC.sh`
  - Useful historically, but most write to `Run_1` and can conflict with current archive layout.
- `run_ministral_groupA_baseline.ps1`
  - Uses `ref/LLMABMPMT-Final.py` for Group A baseline.
  - Keep only if this is your declared Group A definition (it now is).

## Path and Parameter Lock for Current Replication

Use these fixed values for Run_2/Run_3 consistency:
- `--years 10 --agents 100 --workers 1`
- `--num-ctx 8192 --num-predict 1536` (B/C)
- `--initial-agents examples/single_agent/agent_initial_profiles.csv`
- `--memory-seed` = same as `--seed` (B/C)
- Group A uses baseline flood years file:
  - `examples/single_agent/flood_years.csv`

Suggested seed plan:
- Run_2: seed `4202`
- Run_3: seed `4203`

## Practical Execution Order

1. Run `examples/single_agent/run_wrr_v6_flood.ps1`.
2. Verify each target folder has `simulation_log.csv`.
3. Recompute metrics after runs complete.
4. Update manuscript statistics to seed-aggregated values.
