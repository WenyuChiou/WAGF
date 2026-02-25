# WRR Section 6 Review and Rewrite Plan (WAGF v6)

## Scope

- Target: `paper/SAGE_WRR_Paper_v6.docx`, Section 6 (`Discussion`)
- Goal: enforce terminology consistency and claim boundaries after `R_H / R_R` split
- Constraint: keep technical-note tone and avoid over-claiming beyond reported evidence

## Independent Reviewer Concerns

1. Metric semantics drift:
- Discussion previously described EBE as generic hallucination correction, but Section 3 defines EBE against `R_H` (feasibility hallucination) specifically.

2. Diagnostic conflation:
- Rationality/coherence failures (`R_R`) and feasibility failures (`R_H`) need explicit separation in interpretation.

3. Claim strength:
- "prevents mode collapse" can read as absolute; better framed as evidence from current runs.

## Round 1 Landing (Applied to v6)

Applied in `paper/SAGE_WRR_Paper_v6.docx`:
- Reframed EBE paragraph to explicitly state:
  - EBE is feasibility-adjusted diversity (`R_H` channel)
  - Recommended reporting bundle: raw entropy + corrected entropy + `R_H`
- Reframed cross-model paragraph to avoid absolute language:
  - governance *suggests mitigation* in tested settings
  - emphasized joint reading of `R_H`/EBE with `R_R` audit traces
- Expanded limitations paragraph:
  - retained seed and sampling-parameter limits
  - added explicit limit that `R_R` is currently audit-level, not fully inferentially summarized across all case studies
  - retained warning-level non-blocking caveat

## Residual Check

- Ensure Conclusions section mirrors the same metric boundaries (`R_H` vs `R_R`) without reintroducing conflated "hallucination" claims.
