# WRR Results Focus Plan (v6): Rationality and Diversity

## Scope

- Target section: flood results presentation in `paper/SAGE_WRR_Paper_v6.docx`
- Focus only: rationality and diversity
- Source-of-truth data files:
  - `docs/wrr_metrics_all_models_v6.csv`
  - `docs/wrr_metrics_group_summary_v6.csv`

## Definitions (Locked)

- `R_H = n_id / n_active`
  - decision-level feasibility/identity violation rate
- `R_R = n_think / n_active`
  - decision-level thinking-rule deviation rate
- `Rationality pass = 1 - R_R`
- `H_norm`
  - normalized Shannon entropy on final actions
- `EHE = H_norm * (1 - R_H)`

Counting rule:
- Intervention and retry counts are workload metrics.
- They are not equivalent to unique violating decisions because one decision may trigger multiple retries.

## Data Snapshot (Group Means Across 6 Models)

From `docs/wrr_metrics_group_summary_v6.csv`:

- Group A:
  - `R_H = 0.425`
  - `R_R = 0.094`
  - `Rationality pass = 0.906`
  - `H_norm(/4) = 0.583`
  - `EHE(/4) = 0.367`
- Group B:
  - `R_H ~ 0.000`
  - `R_R = 0.002`
  - `Rationality pass = 0.998`
  - `H_norm(/4) = 0.662`
  - `EHE(/4) = 0.662`
- Group C:
  - `R_H = 0.000`
  - `R_R = 0.004`
  - `Rationality pass = 0.996`
  - `H_norm(/4) = 0.656`
  - `EHE(/4) = 0.656`

Interpretation:
- Governance sharply reduces feasibility violations (`R_H`) and maintains high rationality pass.
- Effective diversity (`EHE`) is substantially higher in governed groups than ungoverned Group A.

## Figure and Table Layout (WRR Space-Constrained)

1. Figure 2: Rationality panel
- Bars or point-ranges by Group A/B/C for:
  - `R_H`
  - `R_R`
  - `Rationality pass`
- Optional overlay: model-level jitter points.

2. Figure 3: Diversity panel
- Side-by-side by Group A/B/C:
  - `H_norm(/4)`
  - `EHE(/4)`
- Purpose: show raw vs effective diversity gap in ungoverned setting.

3. Table 1 (main text)
- Compact group summary columns:
  - `R_H`, `R_R`, `Rationality pass`, `H_norm(/4)`, `EHE(/4)`, `retry_rows_mean`, `retry_sum_mean`

4. Table S1 (SI, optional)
- Full model x group values from `docs/wrr_metrics_all_models_v6.csv`.

## Ready-to-Paste Result Paragraph (Draft)

Across all six models, governance substantially improved decision-level feasibility and preserved action diversity. Group A showed higher feasibility violations (`R_H = 0.425`, group mean), whereas Groups B and C were near zero on `R_H`. Rationality deviations measured by thinking-rule inconsistency (`R_R`) remained low in governed settings (`R_R = 0.002` in Group B; `0.004` in Group C), corresponding to high rationality pass ratios (`1 - R_R > 0.99` for both groups). On diversity metrics, governed groups retained high normalized entropy (`H_norm(/4) = 0.662` for Group B; `0.656` for Group C) and therefore high effective heterogeneity (`EHE(/4)` matching `H_norm` due to near-zero `R_H`), while Group A showed a marked drop from raw diversity to effective diversity (`H_norm(/4) = 0.583` to `EHE(/4) = 0.367`).

Intervention and retry frequencies are reported as governance workload metrics, not as unique violation counts. Because retry attempts can recur for a single decision, workload frequency is not equivalent to decision-level violation prevalence.
