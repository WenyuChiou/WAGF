# WRR v6 Pre-Experiment Preflight Report

- Generated: 2026-02-09T00:36:31.282766+00:00

## Progress Update (2026-02-09)
- `research-engineer` skill:
  - `npx skills add https://github.com/wshobson/agents --skill research-engineer` could not find that exact skill name in the remote skill index.
  - Global fallback applied: copied local existing skill from `C:\Users\wenyu\.agents\skills\research-engineer` to `C:\Users\wenyu\.codex\skills\research-engineer`.
- Manuscript `paper/SAGE_WRR_Paper_v7.docx`:
  - Word readability repaired (namespace declaration recovery) and validated.
  - Corrupted symbol/text artifacts cleaned (no remaining private-use symbol paragraphs detected).
  - Validation status: `All validations PASSED!`
- Relevant commits:
  - `009f2c6` `paper: repair v7 docx namespace declarations for Word readability [agent: codex-gpt5]`
  - `6ebb905` `paper: clean corrupted symbols and normalize section prose in v7 [agent: codex-gpt5]`

## Flood Experiment Live Status (2026-02-09T12:54:25-05:00)
- Active process:
  - `python examples/single_agent/run_flood.py --model gemma3:27b ... --output examples/single_agent/results/JOH_FINAL/gemma3_27b/Group_B/Run_2 --seed 4202 --memory-seed 4202`
- Matrix completion:
  - `25/54` `simulation_log.csv` files present
  - `29/54` still missing
- Per-model completion snapshot:
  - `gemma3_4b`: A/B/C have `Run_1` and `Run_2`
  - `gemma3_12b`: A/B/C have `Run_1` and `Run_2`
  - `gemma3_27b`: `Group_A Run_1/Run_2`, `Group_B Run_1` (Run_2 in progress), `Group_C Run_1`
  - `ministral3_3b`: A/B/C have `Run_1` only
  - `ministral3_8b`: A/B/C have `Run_1` only
  - `ministral3_14b`: A/B/C have `Run_1` only

## 30-Min Refresh Template
- Purpose: refresh completion and active-run status every 30 minutes during long runs.

### Commands
```powershell
Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"

Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like '*examples/single_agent/run_flood.py*JOH_FINAL*' } |
  Select-Object ProcessId, CreationDate, CommandLine

python scripts/wrr_compute_metrics_v6.py
python scripts/wrr_render_results_md_v6.py
```

### Paste-Back Format
- Time:
- Active process:
- Completion (`simulation_log.csv`):
- Newly finished cells since last check:
- Current blocker (if any):

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
