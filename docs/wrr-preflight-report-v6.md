# WRR v6 Pre-Experiment Preflight Report

- Generated: 2026-02-09T00:36:31.282766+00:00

## Flood Runner Checks
- `has_run2_seed_4202`: PASS
- `has_run3_seed_4203`: PASS
- `group_a_baseline_script`: PASS
- `group_c_priority_schema`: PASS
- `memory_seed_flag_present`: PASS

## Flood Output Matrix Status (JOH_FINAL)
- Existing `simulation_log.csv`: 18/54
- Missing examples (first 10):
  - `examples/single_agent/results/JOH_FINAL/gemma3_4b/Group_A/Run_2/simulation_log.csv`
  - `examples/single_agent/results/JOH_FINAL/gemma3_4b/Group_A/Run_3/simulation_log.csv`
  - `examples/single_agent/results/JOH_FINAL/gemma3_4b/Group_B/Run_2/simulation_log.csv`
  - `examples/single_agent/results/JOH_FINAL/gemma3_4b/Group_B/Run_3/simulation_log.csv`
  - `examples/single_agent/results/JOH_FINAL/gemma3_4b/Group_C/Run_2/simulation_log.csv`
  - `examples/single_agent/results/JOH_FINAL/gemma3_4b/Group_C/Run_3/simulation_log.csv`
  - `examples/single_agent/results/JOH_FINAL/gemma3_12b/Group_A/Run_2/simulation_log.csv`
  - `examples/single_agent/results/JOH_FINAL/gemma3_12b/Group_A/Run_3/simulation_log.csv`
  - `examples/single_agent/results/JOH_FINAL/gemma3_12b/Group_B/Run_2/simulation_log.csv`
  - `examples/single_agent/results/JOH_FINAL/gemma3_12b/Group_B/Run_3/simulation_log.csv`

## Irrigation Readiness
- `production_v19_42yr` trace: PASS
- `production_v20_42yr` trace: PASS
- `production_v19_42yr/simulation_log.csv`: MISSING
- `production_v20_42yr/simulation_log.csv`: MISSING

## Manuscript Structure Quick Checks (v6)
- Track changes enabled in settings: YES
- Line numbering enabled in settings: NO
- Figure placeholders in text: 3
- Remaining deletion marks (`w:delText`): 13

## Go/No-Go Gates
1. Flood Run_2/Run_3 matrix complete for all 6x3 model/group combinations.
2. Irrigation production full `simulation_log.csv` exported for v19/v20 (or one final selected production run).
3. Before submission: accept tracked changes and enable continuous line numbering in final manuscript file.