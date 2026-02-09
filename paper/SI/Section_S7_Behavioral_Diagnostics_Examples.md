### S7. Behavioral Diagnostic Examples (Flood Case)

This section provides concrete examples for two diagnostic channels used in the manuscript:

1. **Feasibility / identity violations (`R_H`)**
2. **Rationality deviations (`R_R`)**

All examples are directly taken from `simulation_log.csv` in `examples/single_agent/results/JOH_FINAL`.

#### S7.1 Why these examples are shown

- `R_H` and `R_R` are aggregate rates; reviewers often ask what the flagged events look like at decision level.
- These examples make the classification operational and auditable.
- The cases below are representative, not cherry-picked by prompt text.

#### S7.2 Decision-level examples

| Case ID | Category | Source | Agent-Year | Observed decision | Diagnostic interpretation |
|---|---|---|---|---|---|
| P1 | Physical/identity (`R_H`) | `gemma3_12b/Group_A/Run_1/simulation_log.csv` | `Agent_1`, Year 4 | `Both Flood Insurance and House Elevation` with `elevated=True` | Re-elevation attempt after elevation already completed (identity-state inconsistency). |
| P2 | Physical/identity (`R_H`) | `ministral3_3b/Group_B/Run_1/simulation_log.csv` | `Agent_73`, Year 5 | `yearly_decision=elevate_house`, `elevated=True`, `retry_count=3` | A rare leaked feasibility violation in governed mode after retry budget exhaustion. |
| R1 | Irrational behavior (`R_R`) | `gemma3_12b/Group_A/Run_1/simulation_log.csv` | `Agent_43`, Year 3 | `Do Nothing` while threat text implies high threat | High-threat inaction rule violation (`high_threat_inaction`). |
| R2 | Irrational behavior (`R_R`) | `gemma3_4b/Group_C/Run_1/simulation_log.csv` | `Agent_14`, Year 9 | `yearly_decision=do_nothing`, `threat_appraisal=H`, `retry_count=3` | Residual high-threat inaction in governed mode; consistent with bounded rationality and retry ceiling design. |

#### S7.3 Relation to manuscript claims

- These examples support the interpretation that:
  - `R_H` captures **feasibility-state failures** (e.g., repeated structural action after completion).
  - `R_R` captures **coherence failures** between appraisal and action.
- Governed groups substantially suppress both channels at population scale, but do not force perfect rationality in every decision.
- Remaining outliers are expected under the study design (retry cap keeps a small tail of non-ideal behavior to avoid over-constraining human-like heterogeneity).

#### S7.4 Reproducibility note

The examples were identified by replaying the same decision-level rules used in `scripts/wrr_compute_metrics_v6.py`:

- `R_H`: `previous_elevated=True` and action in `{elevation, both}`.
- `R_R`:
  - high threat + `do_nothing`,
  - low threat + `relocate`,
  - low threat + `{elevation, both}`.

