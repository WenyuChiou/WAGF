# Next Task (2026-03-07)

## Repo Hygiene Follow-Up
- Decide whether `examples/multi_agent/flood/flowchart/` should stay as design support or move to archive/private working space
- Decide whether `examples/multi_agent/flood/input/census/` is required for reproducibility or should move to a data release package
- Review remaining untracked analysis files in `single_agent/`, `irrigation_abm/`, and `paper3/` before adding or archiving them
- Keep both `ref/CRSS_DB/` and `ref/RL-ABM-CRSS/` in the active repo workspace unless irrigation/FQL reference data is explicitly externalized

## In Progress ⏳

### Flood Extra Seeds (3→5 seeds)
- **Script**: `examples/single_agent/run_flood_extra_seeds.py --skip-existing`
- **Jobs**: 24 (6 models × 2 conditions × 2 seeds)
- **Seeds**: 45 (Run_4), 46 (Run_5)
- **Output**:
  - Governed → `JOH_FINAL/{model}/Group_C/Run_{4,5}/`
  - No validator → `JOH_ABLATION_DISABLED/{model}/Group_C_disabled/Run_{4,5}/`
- All 6 Ollama models confirmed available
- Script verified: Group_B→Group_C fix applied ✅

### After Extra Seeds Complete
1. Update EDT2 with 5-seed flood data (currently 3)
2. Regenerate Fig 3 (flood stacked bars) with 5 seeds
3. Regenerate Fig 4 (cross-model) with 5 seeds
4. Recompute SI Tables 1 & 2 (df=2→df=4, new CIs/p-values)
5. Update seed count in SI table notes ("3 seeds"→"5 seeds")
6. Regenerate v20 docx

## Remaining Tasks

### Cover Letter Update
- `cover_letter_v14.md` still has v20 numbers, "ungoverned", no-ceiling references
- Needs full rewrite with v21 framing + Group_C data

### Prof Yang Final Read
- Send updated docx for review
- Address any feedback

## Session BB Completed (2026-03-07)
- Group_B archived to `_archive_Group_B/` (6 models)
- SI Tables 1 & 2 updated with Group_C numbers
- SI Table 2 note: Ministral 14B ΔEHE significant (p=0.035)
- Results R3: removed contradictory "No model showed significant change"
- `run_flood_extra_seeds.py`: Group_B→Group_C fix
- v19 docx regenerated
- Full data inventory completed
- PROJECT_STATE.md updated

## Data Path Reference
```
# Irrigation v21 (COMPLETE)
examples/irrigation_abm/results/production_v21_42yr_seed{42-46}/
examples/irrigation_abm/results/ungoverned_v21_42yr_seed{42-46}/
examples/irrigation_abm/results/fql_raw/seed{42-51}/

# Flood (3 seeds done, Run_4/5 pending)
examples/single_agent/results/JOH_FINAL/{model}/Group_C/Run_{1-5}/
examples/single_agent/results/JOH_ABLATION_DISABLED/{model}/Group_C_disabled/Run_{1-5}/
examples/single_agent/results/rulebased/Run_{1-3}/

# ARCHIVED (DO NOT USE)
examples/single_agent/results/JOH_FINAL/_archive_Group_B/
```
## 2026-03-07 - ABM Generalization Program

- Goal: make WAGF easier for external ABM developers to adopt without making the core sound flood-only.
- Safety rule: use staged checkpoints; do not refactor core + examples simultaneously.
- Execution reference: `docs/plans/2026-03-07-abm-generalization-plan.md`
- Regression gate: `docs/checklists/abm_generalization_regression_gate.md`
- Immediate next step: decide whether to clean remaining archive/analysis references to `dual-appraisal`, or leave them as historical artifacts.
- New planning artifact:
  - `docs/plans/2026-03-07-release-readiness-audit.md`
  - `docs/plans/2026-03-07-repo-boundary-map.md`
  - `docs/plans/2026-03-07-water-sector-positioning-plan.md`
- Suggested continuation path:
  - paper-first hardening on naming, repo boundaries, and framework-facing docs
  - keep WAGF positioned as water-sector-first, with non-water use described only as a secondary extension path

## 2026-03-08 - Design Audit Follow-Up

- Use `docs/plans/2026-03-08-systematic-design-audit.md` as the current high-level architecture baseline.
- Highest-priority technical cleanup:
  - continue reducing runtime imports from `broker/` into `examples/`
  - split `examples/single_agent/README.md` into developer-facing and research-facing versions
  - add short config-surface READMEs for primary reference implementations
- Keep water-sector-first positioning intact while improving ABM developer onboarding.
- Phase 1 completed:
  - validator dispatch moved behind `broker/domains/water/validator_bundles.py`
  - `broker/interfaces/artifacts.py` no longer re-exports MA example artifacts via import
- Next decoupling candidates:
  - `broker/components/events/generators/hazard.py`
  - `broker/components/events/generators/impact.py`
