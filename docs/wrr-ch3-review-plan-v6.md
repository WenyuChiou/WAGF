# WRR Section 3 Review and Rewrite Plan (WAGF v6)

## Scope

- Target: `paper/SAGE_WRR_Paper_v6.docx`, Section 3 (`3. Metrics`)
- Goal: make metric definitions reviewer-safe, implementation-aligned, and notation-consistent
- Constraint: WRR Technical Note style (concise, reproducible, low rhetorical load)

## Reviewer Risks Identified

1. Definition ambiguity:
- "behavioral hallucination" needed explicit operational criterion tied to governance outcomes.

2. Notation drift:
- Entropy and hallucination symbols were mixed across lines (`RH`, `R_H`, formatting artifacts).

3. Reproducibility gap:
- Section needed explicit statement of what counts as hallucination (ERROR vs WARNING).

## Round 1 Landing (Applied to v6)

Applied in `paper/SAGE_WRR_Paper_v6.docx`:
- Reframed hallucination definition around feasible skill set:
  - proposal `a_t`
  - state-conditioned feasible set `A(s_(t-1))`
  - hallucination condition `a_t not in A(s_(t-1))`
- Added implementation-aligned operational rule:
  - ERROR-level validation rejection counts as hallucination
  - WARNING-level outcome does not count as hallucination
- Standardized equations:
  - `R_H = n_hall / n_total`
  - `EBE = H_norm * (1 - R_H)`, with `H_norm = H / log2(k)` and `H = -sum_i p_i log2(p_i)`
- Kept corrected-entropy policy explicit:
  - map hallucinated proposals to domain fallback skill
  - flood: `DoNothing`
  - irrigation: `maintain_demand`

## Residual Check for Next Round

- Verify that metric scripts and manuscript use the same `n_hall` counting convention in all tables/figures.
- Confirm notation rendering quality in final Word/PDF export (subscripts and minus signs).

## Round 2 Landing (Independent Reviewer Clarification)

Reviewer-style concern:
- The previous wording could be interpreted as "all ERROR rejections = hallucination,"
  which conflates feasibility infeasibility and rationality/coherence violations.

Applied update in `paper/SAGE_WRR_Paper_v6.docx`:
- Split error taxonomy into two rates:
  - `R_H = n_id / n_total` for feasibility hallucination (identity-rule ERROR)
  - `R_R = n_think / n_total` for rationality deviation (thinking-rule ERROR)
- Kept EBE coupled to feasibility hallucination burden only:
  - `EBE = H_norm * (1 - R_H)`
- Updated narrative to state explicitly:
  - infeasible behavior -> hallucination
  - feasible but incoherent behavior -> rationality deviation

Implication:
- Metrics now align with flood single-agent governance design (`identity_rules` vs `thinking_rules`).
