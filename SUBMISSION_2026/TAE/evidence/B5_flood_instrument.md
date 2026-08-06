# B5 — did the two flood arms measure threat appraisal with the same instrument?

**Ruling date 2026-08-01.** Reproduce with
`python SUBMISSION_2026/TAE/evidence/e2_flood_instrument.py` (exit 0 = identical instrument,
exit 1 = not identical). Added to `run_all.py` as step 4, before `table1_cells.py`, because a
failure here invalidates every flood number the later scripts print. Every number in this document
is a line of that script's stdout; sections here map 1:1 onto sections there
(1 scheme · 2 prompt · 3 parser · 4 labels · 5 code vintage · 6 the B6 sensitivity · 7 verdict).

---

## VERDICT — **IDENTICAL INSTRUMENT.** Flood deltas MAY be printed, on the per-run-mean basis.

The stray lowercase `l` that left B5 open is **cosmetic**, and it is not even arm-specific: it
appears in **both** arms, on the **same** parse layer, at the **same** confidence, at comparable
rates. B5's partial evidence looked one-sided only because it was read off one run of one model.

Three disclosures travel with any printed flood number. None of them is an instrument defect, and
none of them is new to this ruling:

| # | disclosure | size |
|---|---|---|
| a | the with-validators arm censors the appraisal on retry-exhausted rows (blank `construct_TP_LABEL`, **100% `REJECTED_FALLBACK`**) | 10 rows / 40,739 (0.0245%), no-validator 0 |
| b | the two arms are **not contemporaneous**, and 37,611 of 81,704 rows sit in runs that pin no commit at all | see §5 |
| c | every label statistic must case-normalise before counting | 19 rows / 81,704 (0.0233%) |

(c) is already satisfied in code: `_data.appraisal()` (`_data.py:609`) applies `.strip().upper()`
before any rate is computed, so the TAE pipeline is unaffected by lowercase labels today.

---

## What was traced

`construct_TP_LABEL` is produced by a four-link chain. Every link was compared arm to arm across
**all 90 flood run directories** (9 models × 2 arms × 5 runs) and **all 81,704 decisions**.

| link | where it lives | verdict |
|---|---|---|
| 1 SCHEME | `config_snapshot.yaml` → `shared.rating_scale`, `shared.response_format`, `household.prompt_template_file`, `household.parsing` | one effective scheme, all 90 runs |
| 2 PROMPT | the rendered question, from `raw/household_traces.jsonl` `input` | one appraisal instrument, all 81,704 prompts, byte-identical |
| 3 PARSER | `broker/utils/parsing/unified_adapter.py` → `broker/utils/normalization.py:normalize_construct_value` | same layer semantics, same passthrough behaviour, in both arms |
| 4 COLUMN | `broker/components/analytics/audit.py:399-403` | passthrough, 0 mismatches in either arm |

### 1. SCHEME — one effective scheme, one reported difference

Both arms declare, in every run:

```
rating_scale         : '### RATING SCALE (You MUST use EXACTLY one of these codes):
                        VL = Very Low | L = Low | M = Medium | H = High | VH = Very High'
appraisal fields     : threat_appraisal -> TP_LABEL (required=True)
                       coping_appraisal -> CP_LABEL (required=True)
delimiters           : <<<DECISION_START>>> ... <<<DECISION_END>>>
prompt_template_file : config/prompts/household.txt
parsing.strict_mode  : True     parsing.default_skill: do_nothing
```

The raw snapshots are **not** one fingerprint: 18 no-validator runs (`Run_1/2/3` of the six
pre-`_v2` models) carry `household.psychological_framework: pmt`; the other 72 runs, including all
45 governed runs, omit the key. That is a **config-schema addition, not an instrument change** —
`broker/config/agent_types/base.py:269` reads `data.get("psychological_framework", "pmt")` and
`base.py:234` defaults the dataclass field to `PsychologicalFramework.PMT`; that default has been in
place since commit `c754dca0` (2026-01-28), earlier than every run in this corpus. The value asked
for did not change. The script resolves the key to that default and reports the raw split anyway,
so it cannot be rediscovered later as a surprise.

### 2. PROMPT — one appraisal instrument, 81,704 prompts, zero variation

Recovered per-decision from the trace stream rather than from a template file, so it is the question
that was actually asked, not the question the config says would be asked:

```
Using the Protection Motivation Theory, evaluate your current situation by considering the following factors:
- Perceived Severity: How serious the consequences of flooding feel to you.
- Perceived Vulnerability: How likely you think you are to be affected.
- Response Efficacy: How effective you believe each action is.
- Self-Efficacy: Your confidence in your ability to take that action.
- Response Cost: The financial and emotional cost of the action.
- Maladaptive Rewards: The benefit of doing nothing immediately.
### RATING SCALE (You MUST use EXACTLY one of these codes):
VL = Very Low | L = Low | M = Medium | H = High | VH = Very High
- Use EXACTLY one of: VL, L, M, H, VH for each appraisal label.
"threat_appraisal": {"label": "VL/L/M/H/VH", "reason": "One sentence summary of how threatened you feel by any remaining flood risks."},
"coping_appraisal": {"label": "VL/L/M/H/VH", "reason": "One sentence summary of how well you think you can cope or act."},
```

The **action menu is excluded** from the comparison on purpose. It varies within a single run — an
already-elevated agent is not offered `elevate_house`, so its menu is 3 items and its
`secondary_decision` hint reads `1, 2, or 3`. That is the world moving, which is the paper's own
mechanism, not the measuring device moving. Including it would have produced a false positive.

Nothing else varies. Measured directly at **year 1**, where the two arms' worlds are provably
identical (`e0_year1_exogeneity.py`) and so the whole prompt should match: over the 900
`(model, agent)` year-1 pairs in `Run_1` of all nine models, the governed and no-validator prompts
are **byte-identical on 325** and **the same length on 800**. The 475 same-length-but-not-identical
pairs differ only in the **order of retrieved memory lines** — a set-iteration ordering difference
already known to this corpus, which touches no appraisal-instrument line. All three `gemma4` cells
are **100/100 byte-identical**. The 100 different-length pairs are **entirely** `gemma3:4b Run_1`,
which is the B6 run (see F1 below) — independent confirmation of B6 from a second direction.

### 3. PARSER — same ladder, same semantics, same passthrough, both arms

| parse layer | gov rows | noval rows | confidence, gov | confidence, noval |
|---|---:|---:|---|---|
| `enclosure+json` | 35,473 | 35,306 | 0.95 | 0.95 |
| `enclosure+keyword` | 5,130 | 5,498 | 0.7 | 0.7 |
| `enclosure+json+keyword` | 110 | 128 | 0.95 | 0.95 |
| `enclosure+json+digit` | 8 | 26 | 0.95 | 0.95 |
| `enclosure+digit` | 5 | 7 | 0.5 | 0.5 |
| `keyword` | 3 | 0 | 0.7 | — |
| *(blank)* | 10 | 0 | 0.0 | — |

`construct_TP_LABEL != reason_tp_label` on **0 rows of 40,739** (gov) and **0 of 40,965** (noval), so
the audit column is a plain passthrough of the parsed value in both arms.

**The lowercase question, settled.** The strays are the documented behaviour of
`normalize_construct_value` when it is called **without** `allowed_values` — `unified_adapter.py:610`
is such a call. `"l"` is not a key of `FRAMEWORK_NORMALIZATION_MAP` (only `"low"` is), so it is
returned unchanged; had `allowed_values` been passed, the case-insensitive match at
`normalization.py:59-62` would have returned `"L"`. This happens in **both** arms:

| | values seen | layers | rows |
|---|---|---|---|
| with-validators | `h`, `l`, `m` | `enclosure+keyword` | 8 |
| no-validator | `h`, `l`, `m` | `enclosure+keyword`, `enclosure+json` | 11 |

Two parse layers fire in the governed arm only. Neither is an instrument difference:

- `keyword` (3 rows, 0.0074%, all `ministral3:3b`) — the degraded path taken when the model omits
  the `<<<DECISION_START>>>` fence. Same ladder, offered to both arms; which rung a generation lands
  on is a property of the generation. All three produced `H`, in scheme.
- *(blank)* (10 rows, 0.0245%) — **100% `REJECTED_FALLBACK` with `retry_count = 3`**. These are the
  rows where governance exhausted the retry budget and the fallback skill executed with no proposal
  attached. The no-validator arm has no retry budget to exhaust, so it structurally cannot produce
  this row. It is the treatment, not the device.

### 4. LABELS — exact distribution, both arms

`construct_TP_LABEL`, counted per cell over all 5 runs. Sign convention of the folder applies
elsewhere; this table is raw counts, not deltas.

| model | arm | rows | VL | L | M | H | VH | h | l | m | blank |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gemma3:4b | with-validators | 4,468 | 210 | 619 | 2,183 | 1,260 | 187 | 0 | 0 | 0 | 9 |
| gemma3:4b | no-validator | 4,786 | 318 | 680 | 2,293 | 1,296 | 198 | 0 | 0 | 1 | 0 |
| gemma3:12b | with-validators | 4,840 | 1 | 1,250 | 3,465 | 124 | 0 | 0 | 0 | 0 | 0 |
| gemma3:12b | no-validator | 4,890 | 0 | 1,243 | 3,602 | 45 | 0 | 0 | 0 | 0 | 0 |
| gemma3:27b | with-validators | 4,989 | 1 | 1,733 | 2,299 | 718 | 238 | 0 | 0 | 0 | 0 |
| gemma3:27b | no-validator | 4,984 | 0 | 1,273 | 2,695 | 888 | 128 | 0 | 0 | 0 | 0 |
| ministral3:3b | with-validators | 3,674 | 47 | 720 | 1,760 | 1,053 | 90 | 1 | 3 | 0 | 0 |
| ministral3:3b | no-validator | 3,755 | 60 | 840 | 1,693 | 1,077 | 82 | 2 | 1 | 0 | 0 |
| ministral3:8b | with-validators | 4,195 | 78 | 423 | 2,413 | 1,173 | 108 | 0 | 0 | 0 | 0 |
| ministral3:8b | no-validator | 4,440 | 100 | 466 | 2,679 | 1,078 | 113 | 1 | 2 | 1 | 0 |
| ministral3:14b | with-validators | 4,634 | 520 | 1,296 | 1,913 | 833 | 68 | 0 | 2 | 2 | 0 |
| ministral3:14b | no-validator | 4,448 | 364 | 1,110 | 2,085 | 831 | 55 | 0 | 2 | 1 | 0 |
| gemma4:e2b | with-validators | 4,019 | 0 | 72 | 2,847 | 1,100 | 0 | 0 | 0 | 0 | 0 |
| gemma4:e2b | no-validator | 3,755 | 0 | 69 | 2,622 | 1,064 | 0 | 0 | 0 | 0 | 0 |
| gemma4:e4b | with-validators | 4,921 | 0 | 70 | 2,711 | 2,118 | 21 | 0 | 0 | 0 | 1 |
| gemma4:e4b | no-validator | 4,907 | 0 | 57 | 2,410 | 2,421 | 19 | 0 | 0 | 0 | 0 |
| gemma4:26b | with-validators | 4,999 | 153 | 2,892 | 1,082 | 629 | 243 | 0 | 0 | 0 | 0 |
| gemma4:26b | no-validator | 5,000 | 97 | 2,671 | 1,214 | 767 | 251 | 0 | 0 | 0 | 0 |
| **POOLED** | **with-validators** | **40,739** | 1,010 | 9,075 | 20,673 | 9,008 | 955 | 1 | 5 | 2 | 10 |
| **POOLED** | **no-validator** | **40,965** | 939 | 8,409 | 21,293 | 9,467 | 846 | 3 | 5 | 3 | 0 |

**Values appearing in one arm and not the other: exactly one — the blank, 10 rows, governed only,
100% `REJECTED_FALLBACK`.** No non-blank value is arm-exclusive.

**Case-normalisation reconciles the two vocabularies exactly.** After `.strip().upper()`:

| | VL | L | M | H | VH | blank |
|---|---:|---:|---:|---:|---:|---:|
| with-validators | 1,010 | 9,080 | 20,675 | 9,009 | 955 | 10 |
| no-validator | 939 | 8,414 | 21,296 | 9,470 | 846 | 0 |

Residual non-scheme values after normalisation: **none, in either arm.**

---

## 5. Code vintage — the arms are not contemporaneous, and it is bounded

This is the part of the trace that could have gone the other way, and it is why the ruling is not
just "the label sets look alike".

Three commits touched `broker/utils/parsing/unified_adapter.py` between the April 2026 runs and the
2026-05-30 runs:

| commit | date | what it did | effect here |
|---|---|---|---|
| `36278bfb` | 2026-05-22 | parse-failure fallback skill must come from `parsing.default_skill`, raises if absent | **no-op** — the snapshot declares `default_skill: do_nothing` |
| `b9885ddc` | 2026-05-23 | Phase 6N-B: `.upper()` on the **structured** `_LABEL` capture branch | can change a label's **case only** |
| `103445d9` | 2026-05-24 | Phase 6N-D-4: `if temp_val.upper() not in {VL,L,M,H,VH}: continue` on the free-text capture | **no-op by construction** — the capture comes from `(VL\|L\|M\|H\|VH)` under `re.IGNORECASE`, so every capture that regex can make passes that test |

`broker/components/response_format.py` was also touched on 2026-05-22 (`9698800f`, Phase 6J-A), but
§2 shows the rendered appraisal question is byte-identical across every run in the corpus, so that
change did not reach the flood rendering.

Provenance as recorded in `reproducibility_manifest.json`:

| arm | manifest `git_commit` | date | vintage | rows | lowercase | rate |
|---|---|---|---|---:|---:|---:|
| with-validators | `1efb8f502113` | 2026-04-19 | pre-6N-B | 838 | 0 | 0.0000% |
| with-validators | `eb595df59333` | 2026-04-19 | pre-6N-B | 8,102 | 0 | 0.0000% |
| with-validators | `bdb29f526436` | 2026-04-20 | pre-6N-B | 4,999 | 0 | 0.0000% |
| with-validators | *unrecorded* | — | unknown | 26,800 | 8 | 0.0299% |
| no-validator | `eb595df59333` | 2026-04-19 | pre-6N-B | 8,662 | 0 | 0.0000% |
| no-validator | `bdb29f526436` | 2026-04-20 | pre-6N-B | 5,000 | 0 | 0.0000% |
| no-validator | *unrecorded* | — | unknown | 10,811 | 5 | 0.0462% |
| no-validator | `5a1d467faa34` | **2026-05-30** | **post-6N-B** | 14,499 | 6 | 0.0414% |
| no-validator | `8c82ae41d0b5` | **2026-06-01** | **post-6N-B** | 1,993 | 0 | 0.0000% |

So the no-validator arm's `Run_1/2/3` for the six pre-`_v2` models were produced **five weeks after**
every governed run, on a parser that had changed in between, and **no governed run is post-6N-B**.
The arm is also internally mixed: `Run_4/5` of those same cells are of the older vintage.

**Why that does not make it a second instrument, empirically rather than by argument:** the `.upper()`
fix did **not** remove lowercase labels from the newer runs — the rate is 0.0364% post-6N-B against
0.0199% pre-6N-B. The branch 6N-B changed is therefore not the branch that produced these labels in
this corpus; the free-text path at `unified_adapter.py:610` calls `normalize_construct_value` without
`allowed_values` in **both** vintages. The worst case the vintage difference can account for is the
**case** of 19 rows in 81,704 (0.0233%), all of them legal levels in the wrong case, all of them
already normalised away by `_data.appraisal()`.

---

## Findings raised while tracing, which are NOT part of the B5 ruling

Three of these are load-bearing for other items. Reported here, not acted on.

### F1 — **B6 flips the sign of the flood anchor cell. It is no longer a cheap disclosure.**

`BACKLOG.md` B6 records that `JOH_FINAL/gemma3_4b/Group_C/Run_1` ran a different prompt and reasons
"flood is descriptive-only, so disclosure is the cheap route". **B5 has just removed the premise of
that reasoning**, and the run is not a rounding error.

Independently re-measured here: that run's prompts contain the `### MULTI-ACTION OPTION` block
**0 times in 857 prompts**; all 89 other flood runs contain it in **100%** of theirs. Its label shape
is a visible outlier — `VH = 4`, `VL = 9`, against 33–53 and 39–61 in its four sibling seeds.

Consequence on the per-run-mean basis this ruling authorises, for `high_share` (% of rows with H or VH),
Δ = (no-validator) − (with-validators):

| | gov per-run HIGH% | mean gov | mean noval | **Δ** |
|---|---|---:|---:|---:|
| all 5 governed seeds | 38.51, 31.17, 30.13, 30.34, 32.16 | 32.46 | 31.30 | **−1.16** |
| dropping `Run_1` | 31.17, 30.13, 30.34, 32.16 | 30.95 | 31.30 | **+0.35** |

**One seed decides the sign of the anchor flood cell.** B6 must now be decided on the merits — drop
the seed (governed n = 4) or keep it and disclose — and it must be decided *before* any flood number
is printed, not after. Note the appraisal instrument in that run **is** identical (it passes §2); what
differs is the response schema it was asked to fill, and that is enough to move the distribution.

Whole-corpus per-run-mean ΔHIGH, for context, all five governed seeds included:
`gemma3:4b −1.16 · gemma3:12b −1.63 · gemma3:27b +1.22 · ministral3:3b −0.15 · ministral3:8b −3.66 ·
ministral3:14b +0.47 · gemma4:e2b +0.97 · gemma4:e4b +6.24 · gemma4:26b +2.92`.

### F2 — flood seeds are not paired for six of nine models

`_data.flood_seed_alignment` already reports this and nothing in `TAE/` acts on it. For all six
pre-`_v2` models the governed manifest seeds are `(42, 4202, 4203, 45, 46)` while the no-validator
seeds are `(42, 43, 44, 45, 46)`. Only the three `gemma4` cells are seed-aligned. Any **paired**
flood contrast on those six models is pairing seed 4202 against seed 43. The per-run-mean basis this
ruling authorises is an unpaired cell mean and is unaffected; a paired test would not be.

### F3 — Phase 6N-D-4's whitelist filter cannot do what its commit message says

`unified_adapter.py:605` is `if temp_val.upper() not in {"VL","L","M","H","VH"}: continue`, applied to
`temp_val` captured from `(VL|L|M|H|VH)` under `re.IGNORECASE`. Every capture that regex can make
passes the test, so the filter rejects nothing. The commit message (`103445d9`) claims it rejects the
bare `m` inside `I'm`; `"m".upper() == "M"`, which is in the set, so it does not. This is consistent
with the corpus: lowercase `m` still reaches the audit CSV in post-6N-D-4 runs.

**Good news for B5** — it means that commit changed nothing between the arms. **Not good news for
`broker/`**: the fix does not fix the thing it was written for, and
`broker/tests/test_unified_adapter_label_overmatch.py` asserts the line exists rather than that the
leak is gone. Out of the TAE write boundary; recorded for the user. The related claim in that commit
message that flood Group_C reference data has "2/8918" such leaks is also not what this corpus shows
(8 in 40,739 governed flood rows), though the two may be counting different columns or subsets.

### F4 — audit-writer vintage differs between arms (already known, restated with the measurement)

The governed flood audit CSVs carry 74 columns including the duplicated `construct_completeness` and
lack `shadow_blocked`; the no-validator CSVs carry 75, deduplicated, with `shadow_blocked`, and use
`social_elevated_house / social_insured / social_relocated` where the governed files use
`social_elevated_neighbors / social_relocated_neighbors`. The governed trace JSONL has no `_metadata`
header; the no-validator backfilled runs declare `framework_version 0.5.1, audit_schema_version 1`.
None of this touches the four links above — a column added elsewhere in the row cannot change the
value in this one — and §3 shows the column is a passthrough on every row of both arms.

---

## What this ruling licenses, precisely

- Flood **may** print deltas, computed as **the mean of per-run rates**, never pooled.
- Blanks stay in the denominator and are not HIGH, per `_data.LABEL_LEVELS` / `_data.unparsed_share`;
  this is the existing convention and it is now known to be governed-arm-only, 10 rows.
- Every label statistic must case-normalise. `_data.appraisal()` already does; any new consumer must.
- The lane disagreement in `PLAN.md` §4 (flood `ministral3:3b` ΔHIGH: −0.22 pooled vs −0.15 per-run
  mean) is **no longer moot** — it resolves to **−0.15**, the per-run mean, as `PLAN.md` already picked.
- Flood remains a **cross-theory portability demonstration**, never a low-enforcement-pressure control
  (`DECISION.md` §10). This ruling is about the instrument, not about what flood is for.
- **Blocked on F1**: no flood number may be printed until B6 is decided, because one seed decides the
  sign of the anchor cell.
