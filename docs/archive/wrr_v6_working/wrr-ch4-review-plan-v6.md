# WRR Section 4 Review and Rewrite Plan (WAGF v6)

## Scope

- Target: `paper/SAGE_WRR_Paper_v6.docx`, Section 4 (`Case Study 1: Flood Adaptation`)
- Goal: align result narration with Section 3 dual-metric logic (`R_H` vs `R_R`)
- Constraint: no fabricated statistics; preserve reported numeric results

## Independent Reviewer Concern

- Prior text used "hallucination" language that could be read as all ERROR rejections.
- After Section 3 split, Section 4 needed explicit consistency:
  - `R_H` = feasibility hallucination
  - `R_R` = rationality/coherence deviation
- EBE interpretation needed to remain tied to `R_H` only.

## Round 1 Landing (Applied to v6)

Applied in `paper/SAGE_WRR_Paper_v6.docx`:
- Renamed subsection `4.2` to:
  - `Feasibility Hallucination and Rationality Diagnostics`
- Updated detection paragraph to separate:
  - identity-rule infeasibility (`R_H`)
  - thinking-rule coherence failures (`R_R`)
- Kept reported flood statistics unchanged for `R_H`:
  - Group A: 20.84%
  - Group B: 0.58%
  - Group C: 2.80%
- Updated results interpretation:
  - EBE remains feasibility-adjusted (by `R_H`) and does not include `R_R`.
- Updated test paragraph wording to:
  - keep inferential stats on `R_H` and EBE
  - state `R_R` as complementary audit-based diagnostic

## Residual Check

- If `R_R` numeric summaries are later generated from audit traces, add them to SI or a compact table note to avoid asymmetry.

## Round 2 Focus Lock (Results: Rationality and Diversity)

Use one consistent metric package in Section 4:
- Rationality axis:
  - `R_H = n_id / n_active` (feasibility/identity violations)
  - `R_R = n_think / n_active` (thinking-rule deviations)
  - `Rationality pass = 1 - R_R`
- Diversity axis:
  - `H_norm` from final action distribution
  - `EHE = H_norm * (1 - R_H)`

Reviewer-safe counting note to include in Results text:
- Intervention and retry frequencies are governance workload metrics.
- They are not equivalent to unique violating decisions because retries can recur for a single decision.

Presentation lock under WRR Technical Note space limits:
1. Figure 2: `R_H`, `R_R`, and rationality pass by Group (A/B/C).
2. Figure 3: `H_norm` vs `EHE` by Group (A/B/C), same denominator window.
3. Table 1: compact group summary (`R_H`, `R_R`, pass, `H_norm`, `EHE`, retry workload).
4. Optional Table S1 (SI): full 18 model-group rows.
