# WRR v9 Introduction Change Map (v8 -> v9)

This note records the exact introduction edits made for `paper/SAGE_WRR_Paper_v9.docx` relative to v8.

## Scope

- Section: `1. Introduction`
- Paragraphs updated: first three introduction paragraphs.
- Goal: neutralize tone and add explicit validation/evaluation grounding for LLM-agent literature.

## Change Summary

1. ABM baseline paragraph softened to neutral framing.
2. Governance challenge paragraph reframed as validation challenge with citations.
3. Contribution paragraph changed from stronger causal wording to association wording.

## Before/After (semantic diff)

1. ABM baseline statement
- Before: emphasized ABMs as theory-grounded but potentially limiting.
- After: states that theory-grounded rules/utility assumptions keep behavior interpretable/calibratable, while LLM agents are an additional option.

2. Challenge statement
- Before: emphasized unconstrained outputs and prompt-only limits.
- After: explicitly references validation challenge in generative social simulation and positions auditable constraints as a transparency mechanism.
- Added citations in-text:
  - `Boelaert et al., 2025`
  - `Yehudai et al., 2025`

3. Contribution claim tone
- Before: wording closer to deterministic effect.
- After: changed to: governance is associated with fewer infeasible/incoherent outputs while retaining bounded variation.

## Reference File Changes

- `paper/references.bib` added:
  - `boelaert2025validation`
  - `yehudai2025evaluation`

## Zotero Sync (completed)

- Collection: `WRR_WAGF_2026_Intro` (`4KDW9UZ9`)
- Added items:
  - `FMX2X493` (Boelaert et al., 2025)
  - `TFR6QWJN` (Yehudai et al., 2025)
- Both entries include manuscript-purpose notes.
