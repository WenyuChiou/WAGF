# R17 — strict irrigation arm (`production_v21_42yr_seed{42..46}`) provenance +
# seed-46 outlier check (2026-09-10)

Read-only follow-up to `out/r14_advise_final_n5_2026-09-10.md` §4-5. Nothing here
reruns a simulation, touches `broker/`/`examples/` code, or uses GPU/`ollama` — it
reads five already-complete strict-arm corpora plus `git log`/`git show` on already
-committed history. New script added (untracked, matching the r14/r16 convention):
`SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r17_strict_arm_vintage_check.py`.

---

## 0. Scope

r14 found the published strict reference arm's five seeds carry three different git
commits (42/43/44), no recorded commit for 45/46 (older, sparser manifest schema),
and that seed 46 is a wide outlier against its own four strict seed-mates. This file
answers, in order: (1) full provenance table, (2) what the three recorded commits
actually change, (3) which vintage seed 46 (and 45) belong to and whether that
vintage explains the outlier, (4) what the headline strict-arm numbers look like
with/without seed 46, (5) a rerun recommendation for the orchestrator.

---

## 1. Provenance table

Sources: `reproducibility_manifest.json`, `config_snapshot.yaml`, `audit_summary.json`
(`finalized_at`), and filesystem mtimes (`os.path.getmtime`, all files within a run
directory land within ~1 second of each other — a single write burst per run, so the
choice of which file's mtime to quote does not matter).

| seed | dir | manifest `timestamp` | `audit_summary.finalized_at` | file mtime (manifest) | git_commit | model_digest | num_ctx / num_predict | thinking_mode | config_hash | schema_version field |
|---|---|---|---|---|---|---|---|---|---|---|
| 42 | `production_v21_42yr_seed42` | 2026-04-25T07:41:01.232947 | 2026-04-25T07:41:01.265760 | (matches) | `d8a5da41a1e8c55e8e31aa311b4024a5e8dfd95c` | `2026-01-29T12:50:07.405621-05:00` | 8192 / 4096 | `auto` | `75ad0628600f` | none in any file |
| 43 | `production_v21_42yr_seed43` | 2026-04-26T04:34:59.540526 | 2026-04-26T04:34:59.573272 | (matches) | `db05d3a2019a0afaaaf00e6881d6f7d0f69a6708` | `2026-01-29T12:50:07.405621-05:00` | 8192 / 4096 | `auto` | `75ad0628600f` | none |
| 44 | `production_v21_42yr_seed44` | 2026-04-27T04:07:24.255432 | 2026-04-27T04:07:24.282589 | (matches) | `708d34f18f7b01b5b481c92516048c92eb2b8607` | `2026-01-29T12:50:07.405621-05:00` | 8192 / 4096 | `auto` | `75ad0628600f` | none |
| 45 | `production_v21_42yr_seed45` | **absent** (sparse schema: only model/seed/num_years/governance_profile/agent_types_config keys) | **2026-03-04T05:56:29.851289** | 2026-03-04 05:56:29.840461200 | **absent** | **absent** | 8192 / 4096 (`config_snapshot.yaml` only, not runtime-verified) | **absent** | **absent** | none |
| 46 | `production_v21_42yr_seed46` | **absent** (same sparse schema) | **2026-03-04T16:06:29.092589** | 2026-03-04 16:06:29.088008700 | **absent** | **absent** | 8192 / 4096 (`config_snapshot.yaml` only) | **absent** | **absent** | none |

Additional provenance facts, not in r14:

- **`run_integrity.json` is absent from all five strict-arm directories** (42-46
  alike) — this is not a 45/46-specific gap, it applies to the whole strict arm.
  Contrast with the advise arm, whose r14 integrity gate requires and verifies this
  file on every seed. The strict arm's own completeness can only be checked via
  audit-row counts, not a written integrity verdict.
- `audit_summary.json.finalized_at` gives 45/46 a genuine, explicit timestamp (not
  merely a filesystem mtime) — it independently confirms the March 2026 vintage:
  seed 45 finalized 2026-03-04T05:56:29, seed 46 finalized 2026-03-04T16:06:29,
  roughly ten hours apart on the same day.
- `config_hash` (42-44) is **identical across all three** (`75ad0628600f`) despite
  three different git commits — the strongest available evidence that the *resolved
  configuration* did not change across that vintage span, independent of code.
- `config_snapshot.yaml` is otherwise byte-identical across all five seeds (the only
  per-seed line is the `seed:` value itself) **except one key**: seeds 42/43/44 carry
  `irrigation_farmer.psychological_framework: cognitive_appraisal`; seeds 45/46 do
  not have that key at all (515 lines vs 516). This is a genuine content difference
  between the two vintages, not just a missing-metadata gap — see §3.
- `irrigation_farmer_governance_audit.csv` header is byte-identical (71 columns) across
  seed 42 and seed 45 — no schema drift in the audit CSV itself.

---

## 2. Code delta between the three recorded commits (d8a5da41 → db05d3a2 → 708d34f1)

Ordering confirmed by ancestry (`git merge-base --is-ancestor`):
`d8a5da41` (seed 42, 2026-04-25 01:55:52) → `db05d3a2` (seed 43, 2026-04-26 00:29:26)
→ `708d34f1` (seed 44, 2026-04-26 18:41:59).

```
git log --oneline d8a5da41..708d34f1 -- broker/ examples/irrigation_abm/ ':!*/results/*' ':!*.md'
```

Output — **one commit**:

```
16dee6a0 feat(broker): Phase 6A — domain-genericity narrow fix
```

The full unrestricted range (`git log --oneline d8a5da41..708d34f1`) has 7 commits;
the other 6 are WAGF-skills documentation/onboarding commits (`98a75ef0`, `27e39b2e`,
`d546e159`, `4146a024`) and one flood-only fix (`972cea41`, touches
`examples/governed_flood/run_experiment.py` and
`examples/multi_agent/flood/orchestration/lifecycle_hooks.py` — neither irrigation
nor broker/) plus the merge commit `db05d3a2` and `708d34f1` themselves.

**Per-commit verdict, governance path:**

| commit | touches broker/governance path? | verdict |
|---|---|---|
| `d8a5da41` (seed 42's own commit) | `broker/components/memory/engine.py` — abstract type-hint only (`List[str]` → `List[Dict]`), two test files. Commit message states explicitly: "no production code changes — running batches unaffected." | **no-op** |
| `98a75ef0`/`27e39b2e`/`d546e159`/`4146a024` (WAGF skills docs) | `.claude/skills/`, `README.md` only | **irrelevant** (not irrigation/broker) |
| `972cea41` (flood memory-pipeline crash fix) | `examples/governed_flood/*`, `examples/multi_agent/flood/*` | **irrelevant** (not irrigation) |
| `16dee6a0` (Phase 6A domain-genericity) | `broker/components/governance/registry.py`, `broker/components/governance/retriever.py`, `broker/core/experiment_runner.py`, `broker/components/cognitive/reflection.py` | **touches the governance path by file, but verified no-op by content** — see below |

`16dee6a0` in detail (this is the one commit that could plausibly matter):

- `registry.py` / `retriever.py`: both changes only add a one-time **warning** when a
  domain's YAML omits `default_skill:` / `global_skills`; the fallback value itself
  is unchanged when the YAML declares them explicitly. Irrigation's
  `skill_registry.yaml` declares `default_skill: maintain_demand` (confirmed by
  grep) — so behavior is identical to before the commit.
- `experiment_runner.py`: 6 cache-fallback sites replace the literal `"do_nothing"`
  default with `skill_registry.get_default_skill()`. This is a REAL behavior change,
  but only on the code path taken when a *cached* proposal/approved-skill dict is
  missing its `skill_name` key — the commit message states "Irrigation cache misses
  now correctly fall back to maintain_demand," i.e. the pre-commit behavior would
  have been WRONG (silently returning `"do_nothing"`, not a legal irrigation skill)
  had this path ever been exercised. Whether it was ever exercised in the
  publish production runs is not re-verified here (out of scope), but any exercise
  of it pre-commit would already show up as an off-registry `"do_nothing"` action in
  `simulation_log.csv`'s `yearly_decision` column, which `_loader.ibr`/`_common`
  would have raised on (`"off-registry ... action"` PrepError) — no such error is on
  record for seeds 42-44 in r14 or here.
- `reflection.py`: adds a one-time **warning log line only** (gated by
  `_legacy_importance_warned`); the importance-scoring arithmetic below it is
  untouched.
- Commit message's own verification: "Behavior preserved for all 9 existing domain
  configs (verified: each declares default_skill: in its skill_registry.yaml)" and
  "Background irrigation/Gemma-4 batches unaffected."

**Plain answer: no, the three vintages cannot differ in behaviour for the strict
irrigation arm** (parsing/prompts/`agent_types.yaml`/memory engine untouched; the one
governance-adjacent commit is a warning-only + verified-inert cache-fallback fix).
This is independently corroborated by `config_hash` being bit-identical
(`75ad0628600f`) across all three seeds. The three-different-commits fact is a
**tooling/audit-trail artifact** (three separate launches captured three different
`HEAD`s across an active-development day, none of which changed anything the strict
irrigation run exercises), not a behavioral confound.

---

## 3. Seed 46's vintage (and seed 45's)

**Both seed 45 and seed 46 are the same, older, pre-cognitive-appraisal vintage —
not merely "commit unknown."**

```
git log --oneline --since="2026-03-03 00:00" --until="2026-03-05 00:00" --all
# 4fbdbc33 chore: remove private/paper files from git tracking   <- ~HEAD at seed45/46 runtime
# 4be50921 update(paper): NW drafts, Fig 3/4, SI tables with verified flood data
```

- File mtimes / `audit_summary.finalized_at` place both runs on **2026-03-04**
  (seed 45 at 05:56, seed 46 at 16:06 — same day, ~10 h apart), i.e. ~7 weeks before
  seed 42 (2026-04-25).
- The commit that added the very framework named in seeds 42-44's config
  (`1c11c853 feat: add cognitive appraisal framework`) landed **2026-03-07
  16:23:03 -0500 — three days AFTER seed 45/46 finished**. Seeds 45/46 ran on code
  that did not yet contain `cognitive_appraisal` at all, which is exactly why their
  `config_snapshot.yaml` has no `psychological_framework:` line for
  `irrigation_farmer` (515 vs 516 lines; diff confirmed, §1).
- Between the ~March-4 vintage and `d8a5da41` (seed 42), **30 commits touch
  `broker/`+`examples/irrigation_abm/`** (excluding results/md); **13 of those touch
  governance/validator/memory/skill-broker paths specifically**, including real
  feature work — not refactors verified inert like §2's single commit:
  `1c11c853` (add cognitive appraisal framework), `9057097f` (broker-level memory
  write governance / ratchet-fix generalization), `129e33a4` (preserve structured
  memory salience through retrieval), `301e5710` (decouple broker from example
  validators), `c834d9b6` (generic temporal-rule framework). This is categorically
  different from the §2 finding for 42→43→44 (one commit, content-verified inert)
  — the 45/46 vintage gap is real, substantive, multi-feature drift in the memory
  and governance layers, not a tooling artifact.

**Does this vintage difference explain seed 46's outlier behaviour? The evidence
says no**, for four independent reasons:

1. **Governance rule set is identical.** `governance_summary.json`'s
   `rule_frequency` keys are the same three irrigation rule ids on all five seeds
   (`high_threat_high_cope_no_increase`, `low_threat_no_increase`,
   `high_threat_no_maintain`) — the older vintage did not silently substitute a
   different (e.g. PMT/flood) rule set. Totals: 42=2853, 43=3215, 44=2938,
   **45=2410 (lowest)**, **46=3487 (highest)** — seed 45 and seed 46 sit at
   opposite ends despite sharing a vintage.
2. **Year-1 exogenous input is bit-identical across all five seeds.** `drought_index`
   at year 1 = `0.3988299284628388` and `lake_mead_level` = `1052.7963974358975` to
   full float precision on every one of 42/43/44/45/46 (`irrigation_env.py` loads
   real CRSS/PRISM precipitation from a static CSV file — `load_crss_precipitation`,
   present already at the March vintage per `git log -S`) — ruling out a different
   or corrupted CRSS input file for the older vintage.
3. **The r16-style prompt/memory check finds no anomaly of the kind that corrupted
   the flood May-backfill / ministral-Aug-backfill runs.** (See §3a table.) Memory
   length deviates at most +11.1% from the 5-seed median (seed 46) — far under the
   30% flag threshold r16 uses and nowhere near the ~+20%+/truncation-driven effects
   documented there. Reflection-item truncation is 0.0% on all five seeds (no
   `"Consolidated Reflection: {"`-style truncation bug). The one confirmed vintage
   artifact is `memory_pre` item **schema**: `plain_string` for 45/46 vs
   `dict_with_content` for 42-44 (the same March/April split r16 already documented
   for other domains) — but this is a storage-representation difference, not a
   rendered-prompt-length or truncation difference.
4. **Seed 45 shares seed 46's vintage and shows none of seed 46's outlier
   signature.** If the vintage itself caused the outlier, seed 45 (same code, same
   day, same missing `psychological_framework` key) should show it too; it does not
   (r14 already noted seed 45 "slots in cleanly" on every metric; confirmed again
   here in the year-by-year trajectory, §3b).

### 3a. r16 method applied to the 5 strict seeds (`r17_strict_arm_vintage_prompt_check.csv`)

```
python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r17_strict_arm_vintage_check.py
```

| seed | memory_mean (chars) | prompt_mean (chars) | memory_pre schema | reflection_len_mean | %reflection truncated ≤60 chars | memory % dev from 5-seed median | flagged (>30%)? |
|---|---|---|---|---|---|---|---|
| 42 | 458.5 | 4761.2 | dict_with_content | 227.5 | 0.0% | -6.2% | No |
| 43 | 414.6 | 4723.4 | dict_with_content | 205.0 | 0.0% | -15.2% | No |
| 44 | 489.0 | 4792.5 | dict_with_content | 239.9 | 0.0% | 0.0% (= median) | No |
| 45 | 541.6 | 4854.8 | plain_string | 241.7 | 0.0% | +10.8% | No |
| 46 | 543.3 | 4852.7 | plain_string | 247.7 | 0.0% | +11.1% | No |

Memory match rate = 100.0% on all five (the `"Your memory includes:"` marker never
missed). No run is flagged by the r16 30%-deviation rule on either memory or prompt
length.

### 3b. Year-by-year trajectory (`r17_strict_arm_yearly_trajectory.csv`), Mead + drought_index + increase_rate

Full table is 210 rows (5 seeds × 42 years); key facts:

- **Seed 46 tracks its four seed-mates closely through year 41.** At year 41,
  mead_mean = 998.2 (46) vs 1004.8 (42) / 998.1 (43) / 997.3 (44) / 1012.1 (45) —
  seed 46 is mid-pack, not an outlier, one year before the published `mead_min`.
- **The mead_min < 970 ft event is a single year-42 event**: seed 46's mead_mean
  drops from 998.2 (y41) to **964.0 (y42)**, a 34 ft one-year drop; no other seed
  drops below 997 in any year. `drought_index` (global, one value per year — verified
  identical across all 78 agents each year) simultaneously jumps to **0.6397** at
  y42 for seed 46 vs 0.31-0.42 for the other four seeds at y42 — but `drought_index`
  is `f(precip, mead_level)` and mead_level is itself endogenous (drawn down by
  aggregate agent diversions), so this is consistent with the low mead_level driving
  the elevated drought_index reading, not an independent exogenous-input difference
  (§3, point 2, already rules out a differing precip file).
- **The underlying cause is NOT a one-year event — it's a persistently elevated
  increase-rate across virtually the whole 42-year run.** Segment means:

  | seed | y1-19 | y20-34 | y35-41 | y42 | y1-42 (whole run) |
  |---|---|---|---|---|---|
  | 42 | 49.9% | 33.5% | 27.7% | 9.0% | 39.4% |
  | 43 | 41.5% | 39.1% | 28.8% | 14.1% | 37.9% |
  | 44 | 44.5% | 43.8% | 25.6% | 11.5% | 40.3% |
  | 45 | 48.9% | 33.8% | 23.3% | 12.8% | 38.4% |
  | **46** | **52.6%** | **49.9%** | **36.1%** | **38.5%** | **48.6%** |

  Seed 46 is the highest (or tied-highest) increase-rate seed in **every** segment,
  not just the last year — a cumulative excess of increase decisions across the run
  depletes the reservoir more than in the other four seeds, and this shows up
  sharply once the depletion crosses the 970 ft mead_min threshold at y42. This
  pattern (gradual divergence, same rule set, same exogenous input, same vintage as
  a non-outlier seed-mate) reads as ordinary real-LLM sampling variance for this
  seed's population of 78 agents' decisions, consistent with the project's own
  documented gemma3/gemma4 non-determinism finding (`.baselines/BASELINE_HASHES.md`
  per CLAUDE.md), not a vintage-driven or data artifact.

---

## 4. Headline numbers with vs. without strict seed 46

All values recomputed from `out/r14_advise_arm.csv` (already-written, r14-canonical)
using `_loader.py`/`_common.py`'s own `mean`/`sd`/`paired_t`/`t_two_sided_p`/
`exact_perm_p` — no new metric definitions.

### 4a. Strict-arm IBR (proposal) and EHE (proposal), own-arm mean/sd

| metric | n=5 (42-46) mean ± sd | n=4 (42-45, drop 46) mean ± sd |
|---|---|---|
| IBR % (proposal) | 36.0521 ± 3.5974 | 34.6516 ± 2.0442 |
| EHE pooled (proposal) | 0.6724 ± 0.0462 | 0.6534 ± 0.0206 |

Dropping seed 46 lowers both means (IBR −1.40 pp, EHE −0.019) and roughly halves
both standard deviations (IBR sd ×0.57, EHE sd ×0.45).

### 4b. Paired advise-minus-strict `rejected_to_fallback_pct`, n=4 (seeds 42-45 only)

Per-seed diffs (advise − strict): 42 = +3.6020, 43 = +3.1746, 44 = +1.7705,
45 = +2.7167 pp.

| n | mean diff (pp) | sd | t | df | p (t, two-sided) | exact perm p | floor at this n | all seeds same sign? |
|---|---|---|---|---|---|---|---|---|
| 5 (42-46, r14 canonical) | +1.3309 | 3.3896 | 0.8780 | 4 | 0.4295 | 0.4375 | 2/32=0.0625 | No — 4 pos / 1 neg (46) |
| **4 (42-45, drop 46)** | **+2.8160** | **0.7851** | **7.1731** | **3** | **0.0056** | **0.1250** | **2/16=0.1250** | **YES — 4/4 positive** |

Dropping seed 46 more than doubles the paired mean difference (+1.33 → +2.82 pp),
shrinks its sd by more than 4×, and the exact sign-flip permutation p **reaches its
own floor** (0.125 at n=4) with a parametric p of 0.0056 — the same computation that
was "NOT SETTLED" at n=5 (§6 of r14) becomes the best-obtainable result at n=4 once
seed 46 is excluded. Numbers only, per task scope — no claim here about which n the
paper should report.

---

## 5. Recommendation for the ORCHESTRATOR (not the paper)

**Rerun strict seed 46 only (~9.5-11 h, matching the plan's measured strict-profile
per-seed cost), not all five, and not none.** Evidence:

- **Seeds 42/43/44's vintage gap needs no rerun.** §2 shows the only commit between
  them that touches the governance path is content-verified inert (warning-only /
  cache-fallback-only, with the author's own "behavior preserved... verified" note
  and matching `config_hash` across all three). Rerunning these would burn ~28-33 h
  of GPU time to re-confirm a gap already shown to be behaviorally void.
- **Seed 45 needs no rerun either**, despite sharing seed 46's older vintage. §3
  shows no governance/rule-set/CRSS-input/prompt-length anomaly traceable to that
  vintage, and seed 45's own year-by-year trajectory and every r14 headline metric
  sit inside the range set by 42-44 — it is behaviourally indistinguishable from the
  newer-vintage seeds despite the code difference.
- **Seed 46 is the one seed that is BOTH provenance-incomplete (no recorded git
  commit, no `run_integrity.json` like every other strict seed, older vintage
  predating 13 governance/memory-relevant commits) AND a measured behavioral
  outlier** (mead_min, IBR, EHE, approved_first_attempt, increase_rate all outside
  its own arm's range — r14 §3-4). §3's checks (rule set, CRSS input, prompt/memory
  length, reflection truncation) each individually clear the vintage of causing the
  outlier, and seed 45 (the vintage control) behaves normally — but none of that
  positively explains *why* seed 46 in particular drew a persistently higher
  increase-rate population across 42 years; "ordinary real-LLM seed variance" is the
  most consistent read of the evidence gathered here, not a proven fact.
- **The stakes of leaving it unresolved are concrete, not hypothetical**: §4b shows
  the paired advise-vs-strict `rejected_to_fallback` result flips from "not settled"
  (n=5, seed 46 breaks the sign-consistency) to "hits the n=4 exact-permutation
  floor" (drop seed 46) — one seed's inclusion/exclusion currently decides whether a
  pre-registered T1-2 hypothesis (H-b) reads as resolved or open.
- **A same-commit seed-46 rerun is the cheapest experiment that can move this
  forward**: if the rerun reproduces a similarly elevated increase-rate trajectory,
  that is positive evidence for "legitimate stochastic outlier, not an artifact of
  the old code" and the current seed 46 data can be trusted (or optionally replaced
  1:1 with the new same-commit run for provenance cleanliness); if it does not
  reproduce the outlier, that would point back at the old vintage (or simply at
  ordinary sampling variance resolving differently on a second draw) and materially
  change what the n=4-vs-n=5 headline in §4 should be read as. Either outcome is
  informative, at roughly 1/5 the cost of a full 5-seed rerun that would spend most
  of its GPU-hours re-confirming a vintage gap (42/43/44) already shown to be inert.

---

## Appendix: exact commands run for this file

```bash
# provenance (task 1)
for s in 42 43 44 45 46; do
  cat examples/irrigation_abm/results/production_v21_42yr_seed$s/reproducibility_manifest.json
  ls -l --time-style=full-iso examples/irrigation_abm/results/production_v21_42yr_seed$s/*.json
  python -c "import json; print(json.load(open('.../audit_summary.json'))['finalized_at'])"
done
diff <(cat .../seed42/config_snapshot.yaml) <(cat .../seed45/config_snapshot.yaml)   # etc for all pairs

# code delta (task 2)
git merge-base --is-ancestor d8a5da41 db05d3a2   # ordering
git log --oneline d8a5da41..708d34f1 -- broker/ examples/irrigation_abm/ ':!*/results/*' ':!*.md'
git show --stat 16dee6a0
git show 16dee6a0 -- broker/core/experiment_runner.py broker/components/governance/registry.py \
  broker/components/governance/retriever.py broker/components/cognitive/reflection.py

# vintage of seed 45/46 (task 3)
git log --oneline --since="2026-03-03 00:00" --until="2026-03-05 00:00" --all
git show -s --format='%H %ci %s' 1c11c853
git log --oneline 4fbdbc33..d8a5da41 -- broker/ examples/irrigation_abm/ ':!*/results/*' ':!*.md'
git log --oneline 4fbdbc33..d8a5da41 -- broker/validators/ broker/components/governance/ \
  broker/core/skill_broker_engine.py broker/components/memory/ broker/core/parsing* \
  examples/irrigation_abm/config/ examples/irrigation_abm/adapters/

python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r17_strict_arm_vintage_check.py
# -> out/r17_strict_arm_vintage_prompt_check.csv (5 rows)
# -> out/r17_strict_arm_yearly_trajectory.csv (210 rows)

# headline recompute (task 4): read out/r14_advise_arm.csv, apply _loader.mean/sd/
# paired_t/t_two_sided_p and _common.exact_perm_p to the seed 42-45 subset (script
# run inline, not saved as a file -- values reported in §4 above).
```
