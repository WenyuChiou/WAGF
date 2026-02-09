# WRR v7 Intro Patch: Theory Examples + RH/RR Clarification

This note provides paste-ready text to align the manuscript with current v6 metrics and theory framing.

## 1) Suggested Intro Sentence Replacement

Replace the generic sentence:

`many ABMs encode behavior through predefined, theory-grounded rules and utility assumptions`

with:

`many water ABMs encode behavior through explicit behavioral theories and utility assumptions: flood adaptation models often operationalize Protection Motivation Theory (PMT) and related Protective Action Decision Model (PADM) constructs for appraisal-action logic, while irrigation-demand models commonly use utility- or risk-based formulations that can be interpreted through Prospect Theory under scarcity (Rogers, 1983; Lindell & Perry, 2012; Kahneman & Tversky, 1979; Hung & Yang, 2021).`

## 2) Suggested RH/RR Results Wording

Use this wording to avoid over-claims from legacy RH definitions:

`Under the current strict feasibility definition (identity/precondition contradictions), R_H is near zero across most runs, indicating strong containment of physical-state violations. The dominant residual error channel is coherence deviation (R_R), not feasibility leakage. In ungoverned Group A, R_R remains materially higher than governed settings, while governance (Groups B/C) compresses R_R to near-zero in most model-run cells.`

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
- This RH result is strict and conservative (mostly re-elevation/re-relocation state conflicts).
- Historical larger "hallucination" values mixed broader channels; do not directly compare without stating the metric definition.
