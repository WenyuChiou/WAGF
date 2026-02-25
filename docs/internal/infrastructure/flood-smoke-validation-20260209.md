# Flood Smoke Validation Log (2026-02-09)

## Scope
- Objective: verify flood pipeline health before full Run_2/Run_3 main experiment.
- Paths used (temporary):
  - `verification_test/flood_smoke_groupA`
  - `verification_test/flood_smoke_groupB`
  - `verification_test/flood_smoke_groupC`

## Commands Executed
1. Group A baseline (legacy script)
- `python ref/LLMABMPMT-Final.py --model gemma3:4b --years 10 --agents 10 --output verification_test/flood_smoke_groupA --seed 4202 --agents-path examples/single_agent/agent_initial_profiles.csv --flood-years-path examples/single_agent/flood_years.csv`
- Note: `--years 2` is invalid for this script because it samples 3 flood years internally.

2. Group B governed strict/window
- `python examples/single_agent/run_flood.py --model gemma3:4b --years 2 --agents 10 --workers 1 --governance-mode strict --memory-engine window --window-size 5 --initial-agents examples/single_agent/agent_initial_profiles.csv --output verification_test/flood_smoke_groupB --seed 4202 --memory-seed 4202 --num-ctx 8192 --num-predict 1536`

3. Group C governed strict/humancentric + priority schema
- `python examples/single_agent/run_flood.py --model gemma3:4b --years 2 --agents 10 --workers 1 --governance-mode strict --memory-engine humancentric --window-size 5 --use-priority-schema --initial-agents examples/single_agent/agent_initial_profiles.csv --output verification_test/flood_smoke_groupC --seed 4202 --memory-seed 4202 --num-ctx 8192 --num-predict 1536`

## Verification Evidence
- Group A: `simulation_log.csv` exists, 1000 rows, years 1-10, `decision` non-null.
- Group B: `simulation_log.csv` exists, 200 rows, years 1-2, `yearly_decision` non-null.
  - `governance_summary.json`: interventions=9, retry_success=5.
- Group C: `simulation_log.csv` exists, 200 rows, years 1-2, `yearly_decision` non-null.
  - `governance_summary.json`: interventions=21, retry_success=11.

## Cleanup
- Removed temporary smoke artifacts before main run:
  - `verification_test/flood_smoke_groupA`
  - `verification_test/flood_smoke_groupB`
  - `verification_test/flood_smoke_groupC`
  - `example_llm_prompts.txt`

## Result
- Flood smoke test passed for all required execution paths (A/B/C).
- Main experiment can proceed with canonical script:
  - `examples/single_agent/run_wrr_v6_flood.ps1`
