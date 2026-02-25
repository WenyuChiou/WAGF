# WRR v7 Expert Review (Round 4)

Scope: independent reviewer-style assessment of current manuscript text (based on `paper/verify_v7/word/document.xml`) against the updated project narrative (`rationalization + diversity retention`, with hallucination as risk context and identity/physical rules as module constraints).

## Major Findings (Must Fix Before Submission)

1. **Critical inconsistency: core results text still claims high Group A `R_H` (20.84%)**
- Evidence:
  - `paper/verify_v7/word/document.xml:1061`
  - `paper/verify_v7/word/document.xml:1918`
- Issue:
  - Current metric table (`docs/wrr_metrics_all_models_v6.csv`) uses strict `R_H` (identity/precondition contradictions), where Group A is currently 0 in available runs.
  - This creates a direct contradiction between manuscript claims and reproducible analysis outputs.
- Required action:
  - Replace absolute high-`R_H` claims with metric-definition-aware wording.
  - State that the dominant residual channel is `R_R` (coherence deviation), while strict `R_H` is near zero.

2. **Critical inconsistency: abstract and table captions still center “hallucination reduction” as primary contribution**
- Evidence:
  - `paper/verify_v7/word/document.xml:198`
  - `paper/verify_v7/word/document.xml:371`
- Issue:
  - The current project framing has shifted to behavioral rationalization + diversity retention.
  - Existing abstract/caption language over-anchors to hallucination percentages that no longer match strict `R_H`.
- Required action:
  - Reframe contribution as:
    - primary: `R_R` reduction + `EHE` retention,
    - secondary: hallucination risk management via identity/physical rule constraints.

3. **Methods inconsistency: equations use `n_total` denominator while analysis pipeline uses active-decision denominator**
- Evidence:
  - `paper/verify_v7/word/document.xml:958`
  - `paper/verify_v7/word/document.xml:967`
  - implementation: `scripts/wrr_compute_metrics_v6.py` (`R_H = n_id / n_active`, `R_R = n_think / n_active`)
- Issue:
  - Denominator mismatch (`n_total` vs `n_active`) undermines reproducibility.
- Required action:
  - Align equations and text with `n_active` definition from `docs/wrr-metric-calculation-spec-v6.md`.

4. **Theory framing too generic in introduction; lacks concrete ABM examples tied to water domains**
- Evidence:
  - `paper/verify_v7/word/document.xml:241`
- Issue:
  - “theory-grounded rules and utility assumptions” is correct but abstract; reviewers will ask “which theory in which water context?”
- Required action:
  - Add concrete examples:
    - flood ABM: PMT + PADM-style appraisal/stakeholder logic,
    - irrigation ABM: utility/risk framing interpretable via Prospect Theory under scarcity.

## Medium Findings (Should Fix)

1. **Mixed terminology across sections (“economic hallucination” vs “rationality deviation”)**
- Evidence:
  - `paper/verify_v7/word/document.xml:251`
- Risk:
  - Category drift and reviewer confusion about what counts toward `R_H` vs `R_R`.
- Action:
  - Keep “hallucination” for feasibility/identity contradictions.
  - Keep “rationality deviation” for thinking/coherence failures.

2. **SI and main text need explicit bridge sentence on parser-intent mismatch**
- Evidence:
  - SI now captures this in `paper/SI/Section_S7_Behavioral_Diagnostics_Examples.md`
- Risk:
  - Without a bridge sentence in main text, reviewer may question why hallucination is still discussed if strict `R_H` is low.
- Action:
  - Add one sentence: malformed parse/intention mismatches are treated as governance risk events and are intercepted by identity/physical constraints.

## Suggested Replacement Text (Paste-Ready)

### Intro sentence (ABM examples included)

`In water resources practice, many ABMs encode behavior through explicit theory-grounded rules and utility assumptions: flood adaptation studies often operationalize PMT and related PADM constructs for appraisal-action logic, whereas irrigation-demand studies commonly use utility/risk formulations that can be interpreted through Prospect Theory under scarcity (Rogers, 1983; Lindell & Perry, 2012; Kahneman & Tversky, 1979; Hung & Yang, 2021).`

### Main claim sentence

`The primary governance effect of WAGF is behavioral rationalization with diversity retention: across model-group runs, governance compresses coherence deviations (R_R) while preserving effective behavioral diversity (EHE), with strict feasibility contradictions (R_H) retained as a safety diagnostic channel.`

### Module constraint sentence (requested framing)

`At runtime, identity rules and physical rules are enforced as first-pass constraints before thinking-level coherence checks, so infeasible proposals are blocked prior to execution while bounded heterogeneity is retained.`

## Recommendation

- **Decision**: Major revision required before submission.
- **Rationale**: The paper is close structurally, but metric-definition consistency and claim alignment must be corrected to avoid desk-reject risk on methodological reproducibility.
