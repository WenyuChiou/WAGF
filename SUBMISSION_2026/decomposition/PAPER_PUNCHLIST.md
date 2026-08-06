# NW Paper 1b — punch list after the conditioning revision (2026-07-30)

M0 was decided: **the markdown drafts are authoritative**, so the v50 docx is not the live main text.

## Applied in this pass

| Item | File | What changed |
|---|---|---|
| M1 | `methods_v7.md` Level 1 | AAI restated as a *conditional* rate; the conditioning variable named as an intervention outcome; unconditional companion added with CI and test; A/B/C rule decomposition demoted to a separate diagnostic (it was never the reported quantity) |
| M2 | `methods_v7.md`, `supplementary_information_v15.md` Note 5 | "executed action" corrected to *last proposed action*; executed-action values given (0.9 / 26.8) |
| M3 | `abstract_v16.md`, `introduction_v16.md` | causal verb moved off the conditional measure onto the identified one |
| M4 | `section2_v19_results.md`, `section3_v17_discussion.md` | quadrant paragraph **rebuilt, not cut** — cross-arm cell comparison and the per-cell effect claims (31.7 pp, 7.9–28.9 pp) removed; the within-arm evidence (53.5% rejected, 70.5% rule firing) kept, since it involves no cross-condition conditioning and is what observable (ii) actually rests on |
| M5 | `section2_v19_results.md`, SI Note 5 | 40% uniform-random null moved off the conditional rate onto the unconditional one, where the denominator is fixed by design |
| M6 | SI Notes 5 and 8 | Note 8's unconditional denominator corrected to the threat-relevant one, removing the contradiction with Note 5 |
| M7 | EDT 1 | new row: demand-increase share over all decisions, 40.9 ± 4.4 vs 62.5 ± 1.2 |
| S1–S3 | new **Supplementary Note 13** | per-model conditional vs unconditional table, cross-model spread, year-1 contrast, flood comparison, two-sided collapse |

## Verified from raw data this session (three independent implementations agree)

| Quantity | With validators | No validator |
|---|--:|--:|
| Conditional AAI (published) | 36.05 | 59.07 |
| Unconditional demand-increase share | 40.90 | 62.52 |
| High-appraisal share | 37.08 | 82.80 |
| AAI on **executed** actions | 0.86 | 26.77 |
| Rejected decisions (5 seeds) | 6,469 / 16,380 (39.5%) | 4,757 / 16,380 (29.0%) |
| Rejection cause | 100% behavioural-theory rules | 100% water-right allocation cap, no rule evaluated |

Year 1 (worlds bit-identical): high-appraisal share −3.33 pp (CI −10.42, +3.75); conditional
+1.15 (CI −4.71, +7.00); unconditional −1.28 (CI −2.87, +0.31). All null. Over 42 years all three
are significant. The appraisal shift is cumulative, not an immediate response to correction.

## Still open — NOT fixed here, each needs a decision

1. **Orphan Supplementary Notes.** Notes 10, 11 and 12 are cited but defined nowhere in
   `supplementary_information_v15.md` (which defines 1–9, plus new 13). Note 11 was deliberately
   deleted (`_reserve_SN11_sequence_level_2026-05-29.md`, "don't document what was not used") but
   `methods_v7.md:115` and `section3_v17_discussion.md:37` still point at it, and `methods_v7.md:85`
   points at Note 10 for the memory and reflection documentation. Either restore the notes or reword
   the three citing sentences. **Submission blocker.**
2. **Supplementary Table 13** is cited but has no definition matching the bold-heading convention.
3. **Eight of nine, or nine of nine?** `methods_v7.md` Level 3 says eight of nine flood AAI
   reductions reached significance, naming Gemma-3 12B as the exception; SI line 540 says all nine
   pairs reached significance. Both cannot stand. This is the flood cross-model analysis, untouched
   by the conditioning work, and it needs recomputation to settle.
4. **Figure 2 caption number.** `compile_paper.py:520-527` hardcodes 51.2% where the Results text
   says 49.7% and the plotted panel shows neither.
5. **EDT 2 flood values** still carry 0.9 / 8.5 while the SI has moved to the conditional 1.6 / 14.2.
6. **Do not run** `gen_sfig_forest.py` — it writes the adopted Supplementary Figure 1 filename using
   the old unconditional denominator.
7. **`.paper/journal_format.md:111-113` holds stale anchor numbers** (38.2 / 61.1 irrigation, and a
   flood pair marked as 3 seeds). It is the file future sessions check against, so it should be
   refreshed to 36.1 / 59.1 plus the new unconditional pair.

## What a reviewer can still attack after all of this

- The behaviour-versus-composition split is descriptive, not causal, on both sides. The appraisal
  shift is partly veridical: enforcement made the modelled river less scarce, so a lower
  high-scarcity share is partly agents describing a better world correctly.
- Gemma-3 12B retains almost nothing once the conditioning is removed (−11.4 pp conditional against
  −0.2 pp unconditional). Supplementary Note 13 states this; no main-text sentence should claim the
  irrigation result generalises across configurations.
- The outcome is binary throughout. `increase_large` and `increase_small` count alike, and
  `magnitude_pct` / `request` / `diversion` never enter the metric, so none of these numbers speaks
  to how much water moved.

Reproduce everything: `python SUBMISSION_2026/decomposition/run_all.py`

## Added after the style audit (2026-07-30)

**Fixed in this pass**
- `section2_v19_results.md` R1 opened with "isolate the governance effect", a phrase `.paper/journal_format.md`
  names as banned. Replaced with "compare water-resource reasoning with and without governance".
- **Sign convention.** The new Supplementary Note 13 table originally used with-validators minus
  no-validator (Δ negative). The rest of the SI has used the opposite convention since Supplementary
  Table 6: *no-validator minus with-validators, positive means validators lowered it*. The new table
  and the year-1 figures were flipped to match the document, not the other way round. The BRI
  paragraph's "+23.0 pp" was correct all along under that convention.
- The BRI paragraph still attached a causal verb to the conditional measure, and BRI inherits that
  denominator by construction (BRI = 1 − AAI). Made descriptive and pointed at Note 13.
- Flood kept its causal verb, but only where the justification fits: the Abstract now states the
  flood numbers descriptively (no room to justify in 150 words), while the Introduction keeps
  "reduced" and says inline why it is safe there (rules bind on under 1% of decisions, reported
  appraisal barely differs between conditions). The asymmetry was previously unexplained.
- Punctuation caps, em-dash pair in the new Methods block, and two consecutive bare demonstratives
  in Results.

**Still open**
8. `SI_reasoning_traces_v2.md` contains both "ungoverned" and "isolates the effect", the two phrases
   `.paper/journal_format.md` bans outright. That file was outside the scope of this revision and was
   not edited. It needs its own pass before submission.
9. `introduction_v16.md` is ~1042 words against a ≤950 target, and this revision added roughly 40 more
   to it. The trim was already deferred once; it is now overdue.
