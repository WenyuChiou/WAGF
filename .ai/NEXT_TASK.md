# Next Task (2026-03-08)

## Introduction Status: DONE ✅
- `introduction_v10.md` revised (v19→v20), 3 rounds professor review PASS (8.8/10)
- NW reviewer + Prof Yang fixes applied
- Formatting + GPT words cleaned
- `NatureWater_MainText_v20.docx` compiled

## Experiment Data: FINAL ✅
- Irrigation v21: 5+5 seeds — DO NOT rerun
- Flood governed: 6 models × 5 seeds — DO NOT rerun
- Flood no-validator: 6 models × 3 seeds (gemma3_4b/ministral3_3b have 5) — DO NOT supplement
- FQL baseline: 10 seeds — DO NOT rerun

## Remaining Paper Tasks

### Cover Letter Update (OUTDATED)
- `cover_letter_v14.md` still has v20 numbers, "ungoverned", no-ceiling references
- Needs full rewrite with v21 framing + Group_C data

### Prof Yang Final Read
- Send updated v20 docx for review
- Address any feedback

### Fig 1 (Architecture Diagram)
- User will create manually

## Repo Hygiene (Low Priority)
- Decide on `examples/multi_agent/flood/flowchart/` and `input/census/`
- Review remaining untracked analysis files
- `hazard.py` / `impact.py` documentation-only vs runtime coupling check

## Paper3 MA Flood (Current Direction)
- Paper 3 RQ plan re-scoped around:
  - full-system inequality outcome
  - institutional feedback contribution
  - social information contribution
- Memory remains part of architecture but is **not** a primary ablation/RQ
- Use `si2_exogenous_institutions` and `si3*` social ablations as main mechanism contrasts
- Interpret the balanced population as 4 groups:
  - MG homeowner
  - MG renter
  - NMG homeowner
  - NMG renter
- Working RQs:
  1. flood adaptation inequalities across marginalized/non-marginalized homeowners and renters
  2. endogenous institutional feedback contribution
  3. social information contribution across homeowner/renter groups

## Data Path Reference
```
# Irrigation v21 (COMPLETE - FINAL)
examples/irrigation_abm/results/production_v21_42yr_seed{42-46}/
examples/irrigation_abm/results/ungoverned_v21_42yr_seed{42-46}/
examples/irrigation_abm/results/fql_raw/seed{42-51}/

# Flood (COMPLETE - FINAL)
examples/single_agent/results/JOH_FINAL/{model}/Group_C/Run_{1-5}/
examples/single_agent/results/JOH_ABLATION_DISABLED/{model}/Group_C_disabled/Run_{1-3}/ (4b/3b have Run_{1-5})
examples/single_agent/results/rulebased/Run_{1-3}/

# ARCHIVED (DO NOT USE)
examples/single_agent/results/JOH_FINAL/_archive_Group_B/
examples/irrigation_abm/results/_archive_v20/
```
