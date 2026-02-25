# WRR Keyword Selection Expert Review (TA/CP Parsing)

## Purpose

This note records the reviewer-facing rationale for appraisal keyword selection in flood `Group_A` free-text logs.

The objective is to keep metric interpretation defensible:

- preserve comparability of the current `R_R` definition (three thinking rules),
- reduce obvious lexical misclassification risk,
- document why some intuitive words are intentionally excluded.

## Multi-Reviewer Assessment (Independent Lenses)

1. Hydrologic ABM reviewer lens
- Concern: keyword mapping can silently change behavioral findings.
- Requirement: fixed rule set and explicit sensitivity note.

2. NLP measurement lens
- Concern: broad tokens (`high`, `low`, `confidence`, `concern`) produce unstable label mapping.
- Requirement: phrase-level and negation-aware matching.

3. Statistical reviewer lens
- Concern: post-hoc lexicon expansion can inflate effect size.
- Requirement: freeze primary lexicon; report sensitivity separately.

## Evidence Snapshot (Run_1 + Run_2, Group_A)

- Threat appraisal parser source usage showed high fallback reliance (`default -> M`) in some models.
- Coping appraisal free text also had substantial fallback cases, with many generic terms:
  - `ability`, `confidence`, `can`, `capable`.

Interpretation:
- naive expansion of TA high-risk terms can cause large jumps in `R_R`;
- therefore lexicon should prioritize precision over recall in main-table pipeline.

## Final Lexicon Policy (v1)

### Threat appraisal (`extract_ta_label`)

- Keep established high-risk cues:
  - `extreme`, `severe`, `catastrophic`, `high risk`, `very high`, `dangerous`, `afraid`, `worried`
- Keep established low-risk cues:
  - `low`, `minimal`, `unlikely`, `safe`, `no risk`
- Add negation-aware low matching:
  - example: `not safe` should not map to low threat.

### Coping appraisal (`extract_cp_label`)

- Use phrase-oriented low-efficacy cues:
  - `lack of confidence`, `not confident`, `unable`, `cannot`, `can't`, `limited ability`, `hampered`, `insufficient resources`, `low self-efficacy`, `low confidence`
- Use phrase-oriented high-efficacy cues:
  - `confident`, `high confidence`, `capable`, `can manage`, `can cope`, `able to`, `prepared`, `sufficient resources`, `high self-efficacy`
- Avoid standalone `high` / `low` as CP cues to reduce false positives.

## Why Not Include Broad Terms (Main Pipeline)

Excluded from primary lexicon:

- `concern`, `concerned`, `moderate`, `anxiety` (alone)
- generic `high` / `low`

Reason:
- these words are context-dependent and can shift labels substantially without true construct change.

## Metric Scope Lock

- Manuscript `R_R` remains the three-rule threat-action metric:
  1. `TA in {H,VH} + do_nothing`
  2. `TA in {L,VL} + relocate`
  3. `TA in {L,VL} + elevation/both`
- `CP_LABEL` is parsed and available for construct auditing, but not introduced as a fourth `R_R` rule in v6 main tables.

## Reviewer-Ready Statement

The appraisal parser uses a fixed, high-precision lexicon with negation handling and preserves a locked three-rule `R_R` definition for cross-run comparability. Broader lexical alternatives are treated as sensitivity analyses rather than primary specification.
