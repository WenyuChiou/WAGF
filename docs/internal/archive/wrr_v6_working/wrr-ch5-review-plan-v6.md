# WRR Section 5 Review and Rewrite Plan (WAGF v6)

## Scope

- Target: `paper/SAGE_WRR_Paper_v6.docx`, Section 5 (`Case Study 2: Colorado River Irrigation`)
- Goal: align irrigation narrative with Section 3 metric taxonomy (`R_H` vs `R_R`)
- Constraint: preserve reported irrigation numbers; avoid introducing uncomputed statistics

## Independent Reviewer Concern

- Prior wording mixed feasibility hallucination and economic/rationality interpretation.
- After Section 3 split, Section 5 needed consistent cross-domain metric semantics:
  - `R_H`: infeasible proposals (identity feasibility failures)
  - `R_R`: coherence/rationality deviations (thinking-rule failures)

## Round 1 Landing (Applied to v6)

Applied in `paper/SAGE_WRR_Paper_v6.docx`:
- Tightened setup prose to emphasize architecture-invariant transfer:
  - broker architecture unchanged
  - domain adaptation via YAML artifacts
- Tightened result prose around request-diversion gap:
  - interpreted as institutional filtering through identity-rule feasibility constraints
- Preserved all reported numerical outcomes:
  - request/diversion deltas
  - interventions, retries, parsing failures
  - cluster behavior proportions
- Replaced single-term “economic hallucination” framing with metric-consistent split:
  - infeasible proposals -> `R_H`
  - feasible but incoherent behavior -> `R_R`

## Residual Check

- If irrigation-specific `R_H` and `R_R` aggregates are computed later, add a compact metric note/table for symmetry with flood case.
