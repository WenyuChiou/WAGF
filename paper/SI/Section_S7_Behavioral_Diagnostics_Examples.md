### S7. Behavioral Diagnostic Examples (Flood Case)

This section documents decision-level examples for the two diagnostic channels used in the manuscript:

1. **Feasibility hallucination (`R_H`)**: identity/precondition contradiction.
2. **Rationality deviation (`R_R`)**: thinking-rule coherence contradiction.

All cases are trace-backed from `raw/household_traces.jsonl` under:
`examples/single_agent/results/JOH_FINAL/*/Group_*/Run_*/raw/`.

#### S7.1 Why this section is needed

- `R_H` and `R_R` are population-level rates; this section shows what flagged rows look like at decision level.
- The purpose is auditability: each case includes file path, line, state, proposed skill, and validator outcome.
- The examples are selected from governed traces (Group B/C), where proposal and state are logged in the same row.

#### S7.2 Verified decision-level examples

| Case ID | Category | Source | Agent-Year | Observed decision | Interpretation |
|---|---|---|---|---|---|
| H1 | Feasibility hallucination (`R_H`) | `examples/single_agent/results/JOH_FINAL/ministral3_3b/Group_B/Run_1/raw/household_traces.jsonl` (line 446) | `Agent_73`, Year 5 | `skill_name=elevate_house`, `state_before.elevated=True`, `outcome=REJECTED`, `retry_count=3`; issue includes `Precondition failed: 'not elevated'` | State-incompatible re-elevation proposal. Counted in the feasibility channel. |
| R1 | Rationality deviation (`R_R`) | `examples/single_agent/results/JOH_FINAL/gemma3_12b/Group_B/Run_2/raw/household_traces.jsonl` (line 113) | `Agent_13`, Year 2 | `skill_name=elevate_house`, `outcome=REJECTED`, `retry_count=3`; issue `rule_id=elevation_threat_low` | Low-threat costly structural action; coherence violation under thinking rules. |
| R2 | Rationality deviation (`R_R`) | `examples/single_agent/results/JOH_FINAL/gemma3_4b/Group_B/Run_1/raw/household_traces.jsonl` (line 231) | `Agent_31`, Year 3 | `skill_name=do_nothing`, `outcome=REJECTED`, `retry_count=3`; issue `rule_id=extreme_threat_block` | High-threat inaction after bounded retries; retained residual non-ideal behavior. |

#### S7.3 Additional note on non-physical output failures

- Some rows also show output-schema failures (for example, `Response missing required fields: reasoning`).
- These are governance/audit diagnostics but are **not** counted as feasibility hallucination by the strict manuscript definition.
- The strict split used in this paper is:
  - `R_H`: identity/precondition contradiction.
  - `R_R`: thinking-rule contradiction.

#### S7.4 Relation to manuscript claims

- These examples support the manuscript claim that governance reduces state-incompatible and incoherent outputs but does not enforce perfect rationality.
- Residual `R_R` is expected by design because retries are capped; after cap, some boundedly irrational actions remain observable.
- In this flood dataset, `R_H` events are sparse in governed groups, which is consistent with strong containment by identity/precondition checks.

#### S7.5 Reproducibility

- Case extraction snapshot: `docs/wrr_s7_examples_v9.json`.
- `buy_insurance` is renewable in this setup (`examples/single_agent/skill_registry.yaml`), so repeated insurance purchase is not classified as physical impossibility.
- Group A `simulation_log.csv` uses cumulative decision labels; this SI section therefore uses governed trace rows where proposal, rule result, and state are directly aligned.
