# R14 irrigation advise arm — FINAL n = 5 (2026-09-10)

Supersedes the n = 3 interim look (`out/SUMMARY.md` #15 and the r14 section, as they
read on 2026-09-07/08). This file is the working paper behind that update: exact
commands, the full seed-matched statistics, the interim-vs-final comparison, and the
manifest caveat check. Nothing here reruns a simulation or touches `broker/`/`examples/`
code — it reads five already-complete real-LLM corpora on disk.

---

## 0. Scope and what changed in the script

`SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r14_advise_arm.py` (untracked,
editing in place is in scope) was extended from the n=3 interim version:

1. **Discovery bug fix.** `discover_advise_seeds()` used
   `re.search(r"seed(\d+)$", basename)` on every directory matching the advise-arm
   glob prefix. The killed-and-restarted seed 46 attempt left behind
   `advise_feedback_42yr_gemma3_4b_e0eee08c_seed46_PARTIAL_killed_2026-09-08/`
   alongside the real `..._seed46/` — a directory that matches the *glob* prefix but
   not the seed regex (no digit-only suffix after `seed46`), so the old code would
   have raised `PrepError("cannot parse a seed out of ...")` the moment it tried to
   run with seed 46 present. Fixed to `re.fullmatch` on the full prefix + digits, so
   a non-matching directory is skipped with a printed note and never counted as
   incomplete or complete. Confirmed at runtime: `IGNORED (not a 'seed<digits>' run
   directory): advise_feedback_42yr_gemma3_4b_e0eee08c_seed46_PARTIAL_killed_2026-09-08`.
2. **Cross-seed stats block rewritten.** The n=3 version computed a paired t for only
   3 metrics and smuggled the result into 3 extra rows of `r14_advise_arm.csv`'s
   column union. The n=5 version computes, for every pre-registered T1-2 metric:
   mean ± sd per arm, the paired (or one-sample, for uptake) mean difference, a 95 %
   CI via a stdlib bisection against `_loader.t_two_sided_p` (no scipy — the same
   constraint `_loader.py` already imposes on itself), the parametric paired-t p,
   the exact sign-flip permutation p (`_common.exact_perm_p`, already
   implemented — not reinvented here), and whether all seeds agree on sign. Written
   to a new `out/r14_advise_stats_n5.csv` rather than into `r14_advise_arm.csv`.
3. Docstring carries a `# 2026-09-10 n=5` note describing both changes.

`out/r14_advise_arm.csv`'s 15 per-arm/per-seed rows (advise/strict/no_validator × 5
seeds) are otherwise produced by unchanged logic — same metric definitions, same
integrity gate, same column names.

## 1. Exact command

```
python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r14_advise_arm.py
```

Run from the repository root. No arguments, no GPU, no `ollama` call — pure CSV/JSON
analysis over already-complete corpora. Outputs (all under
`SUBMISSION_2026/reviewer_prep_2026-09-05/out/`):

| file | rows | change from n=3 |
|---|---|---|
| `r14_advise_arm.csv` | 15 (3 arms × 5 seeds) | was 12 rows + 3 paired-t summary rows |
| `r14_advise_findings.csv` | 46 | was 28 |
| `r14_advise_yearly.csv` | 210 (42 yr × 5 seeds) | was 126 |
| `r14_advise_stats_n5.csv` | 8 (one per pre-registered metric) | **new** |

Console output of the run is reproduced in §2 below (condensed).

## 2. Per-seed table (`r14_advise_arm.csv`, advise_feedback + strict rows)

| metric | seed 42 | seed 43 | seed 44 | seed 45 | seed 46 |
|---|---|---|---|---|---|
| advise IBR % (proposal) | 40.61 | 41.52 | 33.30 | 37.16 | 45.56 |
| strict IBR % (proposal) | 36.05 | 36.69 | 33.47 | 32.40 | 41.65 |
| advise IBR % (executed) | 1.23 | 0.95 | 1.14 | 0.78 | 0.18 |
| strict IBR % (executed) | 0.96 | 0.76 | 0.75 | 1.02 | 0.83 |
| advise increase_rate % (proposal) | 43.25 | 40.54 | 39.74 | 40.72 | 43.77 |
| strict increase_rate % (proposal) | 39.38 | 37.85 | 40.32 | 38.37 | **48.57** |
| advise EHE pooled (proposal) | 0.6761 | 0.6464 | 0.6152 | 0.6778 | 0.6703 |
| strict EHE pooled (proposal) | 0.6338 | 0.6375 | 0.6731 | 0.6691 | **0.7487** |
| advise mead_min ft | 994.67 | 995.94 | 996.45 | 995.55 | 996.31 |
| strict mead_min ft | 997.62 | 994.36 | 996.97 | 996.03 | **964.01** |
| advise shortage years | 15 | 13 | 12 | 13 | 15 |
| strict shortage years | 14 | 17 | 15 | 12 | 16 |
| advise rejected_to_fallback % | 42.28 | 39.53 | 38.98 | 40.35 | 42.98 |
| strict rejected_to_fallback % | 38.68 | 36.36 | 37.21 | 37.64 | **47.59** |
| advise approved_first_attempt % | 34.46 | 37.61 | 36.23 | 35.47 | 35.87 |
| strict approved_first_attempt % | 38.03 | 39.22 | 36.57 | 37.52 | **29.67** |
| advise n_advised (/3276) | 151 | 116 | 134 | 140 | 140 |
| advise uptake % (of n_advised) | 16.56 | 14.66 | 18.66 | 13.57 | 17.14 |

Bold = strict seed 46, flagged below as an outlier against its own four seed-mates.

## 3. Seed-matched statistics (advise seed *s* vs strict seed *s*), n = 5

Full precision in `out/r14_advise_stats_n5.csv`. df = 4 throughout (paired) or 4
(one-sample, n=5). Permutation floor at n=5 is 2/32 = 0.0625.

| metric | mean ± sd (advise) | mean ± sd (strict) | mean diff | 95% CI | paired t | p (t) | exact perm p | all 5 same sign? |
|---|---|---|---|---|---|---|---|---|
| uptake % (one-sample vs 0, **H-a**) | 16.12 ± 2.02 | n/a | +16.12 | [+13.61, +18.62] | 17.85 | 0.0001 | **0.0625 (floor)** | **YES — 5/5 positive** |
| rejected_to_fallback % (**H-b**) | 40.82 ± 1.74 | 39.49 ± 4.60 | +1.33 | [-2.88, +5.54] | 0.88 | 0.430 | 0.4375 | NO — 4 pos / 1 neg (seed 46) |
| IBR % proposal | 39.63 ± 4.64 | 36.05 ± 3.60 | +3.58 | [+0.94, +6.22] | 3.76 | 0.020 | 0.1250 | NO — 4 pos / 1 neg (seed 44) |
| IBR % executed | 0.86 ± 0.42 | 0.86 ± 0.12 | -0.01 | [-0.54, +0.53] | -0.03 | 0.976 | 1.0000 | NO — 3 pos / 2 neg (seeds 45, 46) |
| increase_rate % proposal (unconditional) | 41.61 ± 1.79 | 40.90 ± 4.39 | +0.71 | [-3.62, +5.03] | 0.45 | 0.673 | 0.6875 | NO — 3 pos / 2 neg (seeds 44, 46) |
| EHE pooled (proposal) | 0.6572 ± 0.0266 | 0.6724 ± 0.0462 | -0.0153 | [-0.0782, +0.0477] | -0.67 | 0.538 | 0.5625 | NO — 3 pos / 2 neg (seeds 44, 46) |
| mead_min ft | 995.78 ± 0.72 | 989.80 ± 14.47 | +5.98 | [-12.39, +24.36] | 0.90 | 0.417 | 0.7500 | NO — 2 pos / 3 neg (seeds 42, 44, 45) |
| shortage years | 13.60 ± 1.34 | 14.80 ± 1.92 | -1.20 | [-4.03, +1.63] | -1.18 | 0.305 | 0.4375 | NO — 2 pos / 3 neg (seeds 43, 44, 46) |

**Only uptake (H-a) reaches the n=5 exact-permutation floor.** No other metric's
exact permutation p is below 0.125, and every one of them loses same-sign
consistency the moment seed 44 and/or seed 46 enter the pool. IBR-proposal is the
strongest of the remaining metrics (t-test p = 0.020, 95 % CI excluding 0) but its
exact permutation p (0.125) is not the floor — one sign flip (seed 44) is enough to
double it off the floor.

## 4. Interim (n = 3) → final (n = 5): what moved

| quantity | n = 3 interim (seeds 42-44) | n = 5 final (seeds 42-46) | moved by |
|---|---|---|---|
| advised rows, % of 3276 | 4.08 ± 0.53 | 4.16 ± 0.39 | +0.08 pp, sd shrank |
| uptake %, mean ± sd | 16.62 ± 2.00 | 16.12 ± 2.02 | -0.50 pp, essentially flat |
| uptake > 0 (H-a) | HOLDS, 3/3 (reported qualitatively — the n=3 script never computed an exact one-sample permutation p for uptake) | **HOLDS, 5/5** — one-sample t=17.85, exact perm p=0.0625 (the n=5 floor) | verdict unchanged; the n=5 rerun adds the exact-test number the interim never had |
| rejected_to_fallback, advise mean ± sd | 40.26 ± 1.77 | 40.82 ± 1.74 | +0.56 pp — barely moved |
| rejected_to_fallback, strict mean ± sd | 37.41 ± 1.17 | **39.49 ± 4.60** | +2.08 pp mean, sd nearly **4×** — driven entirely by seed 46 |
| rejected_to_fallback, paired diff | +2.85 ± 0.96 pp | +1.33 ± 3.39 pp | diff shrank AND got much noisier |
| rejected_to_fallback, direction | same sign on 3/3 (perm floor 0.25) | **NOT consistent, 4/5 (perm p 0.4375, not the floor)** | **verdict weakened, not strengthened, by adding seeds** |
| IBR % proposal, paired diff | +3.08 ± 1.78 pp (t=1.89, p=0.199, perm 0.50) | +3.58 ± 2.13 pp (t=3.76, p=0.020, perm 0.125) | direction held (seed 44 the flip both times), t-test got *more* significant, permutation floor improved from 0.50 to 0.125 but did not reach the n=5 floor |

**Bottom line on seeds 45/46's effect:** seed 45 slots in cleanly — every one of its
values sits inside the range set by seeds 42-44 on both arms. Seed 46 is the seed
that changes the story, and it changes it on the **strict** side, not the advise
side: advise seed 46's numbers (IBR 45.56 %, rejected_to_fallback 42.98 %) are
higher than the other 4 advise seeds but not wildly so; strict seed 46's numbers
(mead_min 964.0 ft vs 994-998 ft on seeds 42/43/44/45, rejected_to_fallback 47.59 %
vs 36-38 %, approved_first_attempt 29.67 % vs 36-39 %, increase_rate 48.57 % vs
37-40 %) are outliers against its own arm's other four seeds by a wide margin. The
practical result: the interim's "rejected_to_fallback higher on advise, same
direction on all 3 seeds so far" reads as a plausible small effect at n=3; at n=5 it
is exactly as likely to be "the strict reference arm has at least one anomalous
seed" as "advise_mode changes blocking." The data as released cannot separate these
two explanations (see §5).

## 5. Caveat check — manifests, both arms, all seeds

### Advise arm (`advise_feedback_42yr_gemma3_4b_e0eee08c_seed{42..46}`)

All 5 `reproducibility_manifest.json` files agree exactly on every field checked:

| seed | git_commit | model | model_digest | num_ctx | num_predict | config_hash | soft_advise_mode (audit, all rows) |
|---|---|---|---|---|---|---|---|
| 42 | `e0eee08c141b16cc0c683a0cfc43d36bad451da5` | gemma3:4b | 2026-01-29T12:50:07.405621-05:00 | 8192 | 4096 | 62d2eeb2373e | feedback |
| 43 | `e0eee08c141b16cc0c683a0cfc43d36bad451da5` | gemma3:4b | 2026-01-29T12:50:07.405621-05:00 | 8192 | 4096 | 62d2eeb2373e | feedback |
| 44 | `e0eee08c141b16cc0c683a0cfc43d36bad451da5` | gemma3:4b | 2026-01-29T12:50:07.405621-05:00 | 8192 | 4096 | 62d2eeb2373e | feedback |
| 45 | `e0eee08c141b16cc0c683a0cfc43d36bad451da5` | gemma3:4b | 2026-01-29T12:50:07.405621-05:00 | 8192 | 4096 | 62d2eeb2373e | feedback |
| 46 | `e0eee08c141b16cc0c683a0cfc43d36bad451da5` | gemma3:4b | 2026-01-29T12:50:07.405621-05:00 | 8192 | 4096 | 62d2eeb2373e | feedback |

**All five advise seeds are the same code commit, same model digest, same
inference settings, same advise_mode.** `config_hash` (a hash the manifest itself
computes over the resolved config) is also identical across all 5 — the strongest
available single check that nothing besides the seed differed between runs.
`run_integrity.json integrity_ok=True` and `audit_rows=3276` on all 5; r14's own
integrity gate (which raises rather than continues on any mismatch) passed on all 5
without exception.

### Strict reference arm (`production_v21_42yr_seed{42..46}`)

**Not internally consistent, and NOT the same commit as the advise arm.**

| seed | git_commit (manifest) | model_digest | num_ctx / num_predict | advise_mode key present? |
|---|---|---|---|---|
| 42 | `d8a5da41a1e8c55e8e31aa311b4024a5e8dfd95c` | 2026-01-29T12:50:07.405621-05:00 | 8192 / 4096 (config_snapshot.yaml) | no |
| 43 | `db05d3a2019a0afaaaf00e6881d6f7d0f69a6708` | 2026-01-29T12:50:07.405621-05:00 | 8192 / 4096 | no |
| 44 | `708d34f18f7b01b5b481c92516048c92eb2b8607` | 2026-01-29T12:50:07.405621-05:00 | 8192 / 4096 | no |
| 45 | **not recorded** (sparser manifest schema — only `model`/`seed`/`num_years`/`governance_profile`/`agent_types_config` present) | not recorded | 8192 / 4096 (config_snapshot.yaml only) | no |
| 46 | **not recorded** (same sparse schema) | not recorded | 8192 / 4096 (config_snapshot.yaml only) | no |

Findings, stated plainly:

- The strict arm's own seeds 42, 43 and 44 carry **three different git commits**,
  none equal to each other and none equal to the advise arm's `e0eee08c`. Seeds 45
  and 46 predate whatever manifest-schema change started recording `git_commit` at
  all — their commit is simply unknown from this file, not merely "different."
- `model_digest` (the Ollama model-file timestamp, distinct from code commit) IS
  identical across the advise arm and strict seeds 42-44 — the same physical
  `gemma3:4b` weights were used, even though the harness code around them changed
  commit three times. This is the one piece of positive evidence that the model
  itself is held constant; the harness code is not.
- `num_ctx=8192` / `num_predict=4096` match the advise arm on every strict seed
  that records them directly (42-44) and on every seed's `config_snapshot.yaml`
  (all 5) — a config-time record, not runtime-verified for 45/46 the way the r14
  integrity gate verifies it for the advise arm.
- The `advise_mode` key is **absent** from every strict-arm `config_snapshot.yaml`
  checked (42, 45 confirmed directly; 43/44 use the identical harness invocation
  pattern) — the soft-advice channel is not merely turned off on the strict arm, it
  does not exist in that arm's config at all. This is the intended reference
  condition, not a data gap.
- **Net effect on interpretation:** the strict arm is not a byte-identical
  "advise_mode flipped off" rerun of the advise arm at any seed — it is a separate
  real-LLM corpus produced across at least 3 different code commits (2 more
  unknown), sharing only the model weights and, where recorded, the context/predict
  settings. Combined with seed 46's outlier behavior (§4), any advise-vs-strict
  contrast at the rejected_to_fallback / IBR-executed / increase_rate / EHE /
  mead_min / shortage_years level should be read as suggestive at best — exactly
  the caveat the n=3 interim already carried, now sharpened by the fact that adding
  2 seeds made the rejected_to_fallback picture noisier rather than clearer.

## 6. Hypothesis verdicts (plan §3, T1-2)

- **H-a, uptake > 0: HOLDS.** Consistent positive direction on 5/5 seeds
  (13.57-18.66 %, mean 16.12 % ± 2.02 %), one-sample t = 17.85 (df=4, p=0.0001),
  exact sign-flip permutation p = 0.0625 — the best this n=5 design can certify.
  This is the one pre-registered hypothesis fully resolved by the final run.
- **H-b, rejected_to_fallback ≈ strict: NOT SETTLED.** The direction is no longer
  unanimous at n=5 (4/5 positive, seed 46 negative), the paired-diff 95 % CI
  includes 0 ([-2.88, +5.54] pp), and the exact permutation p (0.4375) is far from
  its floor. Per the plan's own pre-registered fallback ("if uptake CI includes 0,
  the soft channel is reported as inert" — inapplicable here since uptake's CI
  excludes 0 cleanly), no equivalent pre-registered fallback exists for an
  inconclusive rejection-rate read; the honest report is that this question remains
  open, and that the strict arm's seed-46 anomaly (not the advise arm) is the
  proximate reason it did not resolve at n=5.

## 7. `out/SUMMARY.md` and `REVIEWER_QA.md` — what was edited

Full before/after text is in the file diffs (both files are untracked, in the
working tree). Summary of the edits:

**`out/SUMMARY.md`**
- Table row #15 (headline number list): replaced the n=3 interim numbers with the
  n=5 finals — uptake 16.62→16.12 (one-sample stats added), IBR-proposal paired
  diff +3.08→+3.58 pp (df 2→4, exact perm 0.25→0.125), rejected_to_fallback
  +2.85→+1.33 pp diff (and explicit "NOT consistent, seed 46 outlier" replacing
  "same direction on 3/3 seeds").
- The full r14 prose section (headline `## Irrigation advise arm...`): every
  n=3/interim number replaced with its n=5/final counterpart — rule-id table
  extended to 5 columns, uptake before/after direction table extended to 5 rows,
  rejection-rate table extended to 5 rows with the seed-46 flip called out, the
  headline-metrics table extended to 5 seed columns, the paired-stats table
  rewritten with 95 % CIs and n=5 permutation floors, and the "what holds and what
  doesn't" hypothesis section rewritten to state H-a HOLDS and H-b NOT SETTLED
  (previously "final call awaits seeds 45-46"). Output-file row counts updated
  (12→15, 28→46, 126→210, plus the new `r14_advise_stats_n5.csv`).

**`REVIEWER_QA.md`**
- D6 ("What does your WARNING-only condition ... establish?"): the Answer/Weakness/
  Improvement lines said "a genuine advise-versus-enforce contrast ... has not been
  run" — stale, since r14 already existed even at the n=3 interim stage. Added a
  factual 2026-09-10 update noting the contrast has now run at final n=5, pointing
  to this file and `out/SUMMARY.md` #15, and correcting "RERUN ... (2 GPU-days)" to
  "RERUN ... is DONE." This was not one of the two files named as the numeric
  interim→final swap target, but D6 literally asserted a false "has not been run"
  once r14 existed at all, so it is corrected here for consistency with the rest of
  this update. No other REVIEWER_QA.md line cites r14 or the advise arm.

**Explicitly not touched, per task scope:** flood, vaccination, and every other
irrigation-arm number in both files; `README.md`'s own r14 section
(`SUBMISSION_2026/reviewer_prep_2026-09-05/README.md:603-734` and the corpus
inventory row at line 859) still carries the n=3 interim numbers verbatim — it was
not named in the task's file list. Flagging this for a follow-up mirror-sync pass:
`README.md` and `SUMMARY.md` are meant to carry the same numbers and currently do
not for r14.
