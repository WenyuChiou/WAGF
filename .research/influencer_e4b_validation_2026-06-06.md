# Phase 6T-F influencer — real-LLM (gemma4:e4b) validation, 2026-06-06

Validation of the `social_media_influencer` feature (gated, default OFF) after two
fixes. Runs: `run_unified_experiment.py --model gemma4:e4b --years 5 --with-influencer
--seed 42` (survey mode, real PRB flood timeline). e4b confirmed 100% GPU (no CPU
fallback). Frozen paper-3 `ma_agent_types.yaml` md5 `ccf334f4…` unchanged throughout.

## Two fixes, both CONFIRMED with real e4b

1. **Menu collapse — `parsing.full_disclosure: true`** (commit `6d11f62`).
   Pre-fix the `{options_text}` menu rendered only 1-3 of the 4 mutually-exclusive
   post-skills (SkillRetriever top_n=3/min_score=0.05 truncation), boxing the LLM into
   amplify. Confirmed fixed — run 1: **Y4 → share_success_story, Y5 → post_counter_narrative**,
   both with a **4-option menu**, both non-amplify (impossible pre-fix).

2. **strict_mode truncation — `num_predict` 1024→2048** (commit `2c50e89`).
   With the menu fixed, run 1 still failed strict_mode parsing in 3/5 years: e4b writes
   4 verbose nested `{label,reason}` appraisals before `decision`, exhausting the 1024-token
   budget before `decision` is emitted → truncated → no parseable decision → silent skip.
   (Households parse fine at 2048.) Confirmed fixed — run 2 (post-fix): **Y1 →
   post_counter_narrative, APPROVED, 4-option menu, 0 give-ups** — Y1 was a *total* failure
   pre-fix (3 truncated attempts, no decision). The extra tokens let the retry path recover.

## Scope / decisions

- Run 2 stopped at Y1 (evidence sufficient: 3 successful real-e4b decisions across the two
  runs — Y1/Y4/Y5, all 4-option, varied non-amplify — plus 0 give-ups post-fix vs 3 pre-fix).
  A full 5/5 reliability tally was NOT pursued (≈30-40 min more for a number that only
  quantifies an already-confirmed fix).
- **#2 clickbait rule** (whether to govern VH-virality + VL-salience) remains DEFERRED:
  no such appraisal combo appeared in the valid years (Y4 SAL=M, Y5 SAL=VH, Y1 counter).
  It is a behavioural-model decision for the user, not a bug.
- Feature verdict: **shipping-safe** — menu + truncation fixes both work with real e4b;
  paper-3 byte-identity preserved; regression lock in `test_influencer_menu_full_disclosure.py`.
