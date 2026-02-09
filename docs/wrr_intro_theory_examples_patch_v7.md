# WRR v7 Intro Patch: Rationalization + Diversity First

This note provides paste-ready text to align the manuscript with current v6 metrics and theory framing.

## 1) Suggested Intro Sentence Replacement

Replace the generic sentence:

`many ABMs encode behavior through predefined, theory-grounded rules and utility assumptions`

with:

`many water ABMs encode behavior through explicit behavioral theories and utility assumptions: flood adaptation models often operationalize Protection Motivation Theory (PMT) and related Protective Action Decision Model (PADM) constructs for appraisal-action logic, while irrigation-demand models commonly use utility- or risk-based formulations that can be interpreted through Prospect Theory under scarcity (Rogers, 1983; Lindell & Perry, 2012; Kahneman & Tversky, 1979; Hung & Yang, 2021).`

## 2) Suggested Main-Claim Wording

Use this wording to center the narrative on rationalization and diversity:

`The primary governance effect is behavioral rationalization with diversity retention. Across model-group runs, WAGF strongly reduces coherence deviations (R_R) relative to ungoverned baselines while maintaining effective behavioral diversity (EHE). Feasibility contradictions (R_H) are tracked as a safety diagnostic and remain near zero under the strict identity/precondition definition.`

Optional transferability sentence:

`The irrigation case is used as transferability evidence that the same governance runtime can preserve rationalized behavior under different domain theory slots and institutional constraints.`

## 3) Current Numeric Snapshot (from `docs/wrr_metrics_all_models_v6.csv`)

- Group A:
  - `R_H mean = 0.0000`
  - `R_R mean = 0.0441` (4.41%)
- Group B:
  - `R_H mean = 0.000182` (0.0182%)
  - `R_R mean = 0.002272` (0.2272%)
- Group C:
  - `R_H mean = 0.0000`
  - `R_R mean = 0.003494` (0.3494%)

Important interpretation:
- `R_H` in this table is strict and conservative (state-contradiction channel).
- The central performance axis is `R_R` reduction + `EHE` retention.
- If older drafts used broader "hallucination" definitions, explicitly note the metric re-definition before comparing values.
