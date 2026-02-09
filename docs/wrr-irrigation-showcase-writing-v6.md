# WRR Irrigation Showcase Writing Plan (Reviewer-Style)

## Skill + Review Setup

- Installed global skill: `code-review-excellence` via:
  - `npx skills add https://github.com/wshobson/agents --skill code-review-excellence --yes --global`
- Review method used here follows that skill's checklist mindset (scope, correctness, evidence strength, claim-risk separation).

## Expert-Panel Consensus (simulated independent review lenses)

### Reviewer A (WRR Technical Note editor)

Primary concern:
- Keep one clear domain-transfer claim, avoid over-claiming full hydrologic equivalence.

Required writing shape:
- "Governance framework transferability" + "behavioral plausibility under domain constraints".
- Quantitative evidence must be compact and reproducible.

### Reviewer B (water systems modeler)

Primary concern:
- Distinguish policy-feasible behavior from physically/economically absurd behavior.
- Show system-level demand trajectory relation to CRSS baseline.

Required writing shape:
- Explain rule classes (identity/feasibility vs appraisal-thinking coherence).
- Include at least one trajectory comparison (request/diversion vs baseline) and one governance-outcome summary.

### Reviewer C (methods/statistics)

Primary concern:
- Denominator discipline and metric definitions.
- Separate governance workload from behavioral prevalence.

Required writing shape:
- Explicitly define: approved/rejected/retry, retry_count interpretation.
- If full 42-year logs are incomplete, mark as "intermediate run evidence" and avoid final-performance claims.

## Repository Reality Check (current irrigation artifacts)

Observed status:
- `examples/irrigation_abm/results/production_v19_42yr/raw/irrigation_farmer_traces.jsonl`
- `examples/irrigation_abm/results/production_v20_42yr/raw/irrigation_farmer_traces.jsonl`
- Full `simulation_log.csv` for these production folders is currently missing.
- `smoke_v20` has complete logs but is 20 agents x 15 years only.

Implication for writing:
- You can publish governance-behavior evidence from production traces now.
- You should delay strict CRSS demand-fit claims until full 42-year `simulation_log.csv` is regenerated/exported.

## What to Report Now (safe, evidence-backed)

### A. Governance behavior outcomes (from production traces)

Use per-decision rates with clear denominator = total trace rows.

`production_v19_42yr` (27xx-level production run):
- Rows: 2169
- Year coverage: 1-28 (28 years)
- Approved: 70.59%
- Rejected: 29.18%
- Rejected fallback: 0.23%
- Retry-success outcome share: 21.62%

`production_v20_42yr`:
- Rows: 2106
- Year coverage: 1-27 (27 years)
- Approved: 58.93%
- Rejected: 40.36%
- Rejected fallback: 0.71%
- Retry-success outcome share: 19.47%

### B. Rule-pressure profile (which constraints are doing work)

Top triggered rules:
- v19: `high_threat_high_cope_no_increase` (893), `curtailment_awareness` (651), `supply_gap_block_increase` (303)
- v20: `demand_ceiling_stabilizer` (923), `high_threat_high_cope_no_increase` (701), `curtailment_awareness` (177)

Interpretation sentence:
- Governance pressure shifts from appraisal inconsistency to hard allocation-cap stabilization in newer run, indicating rule set actively shapes feasible demand space.

### C. Behavioral diversity under governance

From approved-skill distribution (v20):
- 5-action entropy normalized by `log2(5)`: `H_norm = 0.7398`

Interpretation sentence:
- Despite high rejection pressure, decision diversity remains substantial (no collapse to single action).

## WRR Figure/Table Budget (for your 3-figure limit)

Recommended placement across paper:
1. Figure 1: WAGF architecture (already used globally).
2. Figure 2 (flood): rationality + effective diversity (`R_H`, `R_R`, `EHE`).
3. Figure 3 (irrigation): domain-transfer panel with:
- (a) governance outcome shares over years (approved/retry_success/rejected)
- (b) rule-trigger composition over years or top-rule stacked bars
- (c) optional demand trajectory vs CRSS only when full `simulation_log.csv` exists

Tables:
1. Main text table: flood group-level metrics (already defined in v6 docs).
2. Optional compact table for irrigation: v19 vs v20 (coverage, approval/rejection, retry burden, H_norm).

## Suggested Writing (directly usable)

### Results paragraph (irrigation, current data-safe version)

To test cross-domain transferability, we applied WAGF to a Colorado River irrigation ABM with 78 CRSS-derived agents. In current production traces, governance outcomes remain active throughout multi-decadal simulation years (v19: years 1-28; v20: years 1-27), with approval rates of 70.6% (v19) and 58.9% (v20), and corresponding rejection rates of 29.2% and 40.4%. Importantly, retry-mediated recovery remains common (retry-success outcomes: 21.6% in v19; 19.5% in v20), indicating that interventions are not purely terminal filters but corrective mechanisms that preserve agent execution continuity.

Rule-frequency diagnostics show that intervention burden is concentrated in hydrologically meaningful constraints, including high-threat/high-capacity demand-increase blocking and allocation-cap stabilization. In v20, the most frequent trigger is `demand_ceiling_stabilizer` (n=923), followed by `high_threat_high_cope_no_increase` (n=701), suggesting that governance increasingly enforces feasibility boundaries under chronic shortage conditions. At the same time, approved-action diversity remains high (v20 normalized entropy over five actions, `H_norm=0.7398`), supporting the claim that WAGF constrains implausible behaviors without collapsing the behavioral repertoire.

### Methods note (avoid reviewer attack)

Intervention counts are reported as governance workload indicators. Because one decision can induce multiple retry attempts, retry statistics are not interpreted as counts of unique violating agents.

## Mandatory next step before final submission claim

To state CRSS-alignment claims in definitive terms, regenerate or export full production `simulation_log.csv` (42-year complete), then report:
- yearly aggregate request/diversion vs CRSS baseline
- mean bias, MAPE, and trend correlation
- same governance outcome metrics on identical horizon

Without this step, phrase irrigation evidence as "transferability and governance efficacy" rather than "full trajectory fidelity".
