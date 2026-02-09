### S7. Behavioral Diagnostic Examples (Flood Case)

This section provides concrete examples for two diagnostic channels used in the manuscript:

1. **Feasibility / identity violations (`R_H`)**
2. **Rationality deviations (`R_R`)**

All examples below are trace-backed from `raw/household_traces.jsonl` in
`examples/single_agent/results/JOH_FINAL/*/Group_*/Run_*/raw/`.

#### S7.1 Why these examples are shown

- `R_H` and `R_R` are aggregate rates; reviewers often ask what the flagged events look like at decision level.
- These examples make the classification operational and auditable.
- The cases below are representative, not cherry-picked by prompt text.

#### S7.2 Decision-level examples (reasoning-log verified)

| Case ID | Category | Source | Agent-Year | Observed decision | Diagnostic interpretation |
|---|---|---|---|---|---|
| P1 | Physical/identity (`R_H`) | `ministral3_3b/Group_B/Run_1/raw/household_traces.jsonl` (line 446) | `Agent_73`, Year 5 | `skill_name=elevate_house`, `state_before.elevated=True`, `outcome=REJECTED`, `retry_count=3` | High-confidence physical violation attempt (re-elevation) blocked by identity and precondition checks. |
| P2 | Physical forensics (parser-intent mismatch) | same as P1 | `Agent_73`, Year 5 | free-text rationale mentions insurance-like action, but parsed skill is `elevate_house` | Indicates malformed/partially parsed output can map to an infeasible structural action; governance intercepts it before execution. |
| R1 | Irrational behavior (`R_R`) | `gemma3_12b/Group_B/Run_2/raw/household_traces.jsonl` (line 113) | `Agent_13`, Year 2 | `TP_LABEL=L`, `skill_name=elevate_house`, `outcome=REJECTED` | Low-threat costly structural action (`low_threat_costly_structural`), captured as coherence deviation. |
| R2 | Irrational behavior (`R_R`) | `gemma3_4b/Group_B/Run_1/raw/household_traces.jsonl` (e.g., line 231) | `Agent_31`, Year 3 | `TP_LABEL=H`, `skill_name=do_nothing`, `outcome=REJECTED` | High-threat inaction (`high_threat_inaction`), retained as bounded-rational residual under retry ceiling. |

#### S7.3 Relation to manuscript claims

- These examples support the interpretation that:
  - `R_H` captures **feasibility-state failures** (e.g., repeated structural action after completion).
  - `R_R` captures **coherence failures** between appraisal and action.
- Governed groups substantially suppress both channels at population scale, but do not force perfect rationality in every decision.
- Remaining outliers are expected under the study design (retry cap keeps a small tail of non-ideal behavior to avoid over-constraining human-like heterogeneity).
- In the current governed reasoning logs, only one high-confidence physical case is observed; this is consistent with strong containment, not evidence absence of checks.

#### S7.4 Reproducibility note

The examples were identified by replaying rule logic on trace rows and writing an auditable case table:
- `scripts/wrr_reasoning_log_audit_v6.py`
- `docs/wrr_reasoning_log_behavioral_cases_v6.csv`
- `docs/wrr_reasoning_log_behavioral_audit_v6.md`

- `R_H` (trace-level physical channel in governed flood traces): proposal conflicts with state preconditions, e.g., `skill_name=elevate_house` with `state_before.elevated=True`, or `skill_name=relocate` with `state_before.relocated=True`.
- `R_R`:
  - high threat + `do_nothing`,
  - low threat + `relocate`,
  - low threat + `elevate_house`.

Data-semantics note:
- `buy_insurance` is annual/renewable in this flood setup (`skill_registry.yaml`), so insurance repurchase is not classified as a physical impossibility.
- Group A `simulation_log.csv` uses cumulative-style `decision` labels; physical examples in this SI section are therefore grounded in governed trace logs (Group B/C) where step-level proposal and state are jointly available.
