# R18 — restore verification, 2026-09-15

**Verdict up front: the restore FAILED. This is not a byte-completeness edge
case — it is catastrophic, corpus-wide zero-byte corruption.** All four
restored roots (`examples/irrigation_abm/results`, `examples/single_agent/results`,
`examples/vaccination_demo/results`, `ref/CRSS_DB`) contain files that are the
**correct name, the correct size, and the correct mtime**, but whose content
has been overwritten with NUL (`0x00`) bytes — in full or in large part. Of
183 run directories that still carry a `reproducibility_manifest.json`,
**zero (0/183) are clean**. This report documents how that was found, how
wide it goes, and what is and is not usable.

**Read-only throughout.** Nothing under `examples/`, `broker/`, or `ref/` was
modified. Ten of the eleven target scripts wrote nothing to `out/` (they
raised before reaching their `write_csv` call, so the pre-loss files there
are untouched, not re-verified). `r13` (reads a sibling checkout unaffected
by the incident) regenerated and matched byte-for-byte. This file and the
`out_before_restore/` reference copy are the only new artifacts.

---

## 1. How the corruption was found

`r0_sanity_gate.py` — expected to reproduce IBR 36.05 / 59.07 exactly — was
the first script run and it raised immediately, before printing a single
per-seed line:

```
_csv.Error: field larger than field limit (131072)
```

on `examples/irrigation_abm/results/production_v21_42yr_seed42/simulation_log.csv`.
That is not a script bug: the file is 2,833,906 bytes, and a direct byte scan
shows **2,830,336 of them (99.87%) are `0x00`**, with real content surviving
only in the final 3,570 bytes — a fragment of narrative text cut off
mid-word (`"...Year 40: Decided to: Ma"`, then EOF). Everything before that
tail is null.

That pattern — right file name, right size, right mtime, content replaced by
`0x00` — repeats across every corpus this task touches. It was confirmed
independently three ways:
1. A streaming byte scan (below) over all four roots.
2. `od -A d -t x1` on individual files (bypasses any Python I/O layer).
3. `git show <blob>` vs the on-disk file for 10 sampled `ref/CRSS_DB` files
   and one irrigation manifest.

## 2. Scope: streaming NUL-byte scan, all four roots

Every `.csv/.json/.jsonl/.yaml/.txt/.log` file under the four roots (6,225
files, 4.93 GB) was streamed in 4 MB chunks and checked for any `0x00` byte
— a valid text file of this project's own format never contains one, so any
NUL byte is restore damage, not legitimate content.

| extension | scanned | contains ≥1 NUL byte | % corrupted |
|---|---|---|---|
| `.jsonl` (raw traces) | 317 | 317 | **100.0 %** |
| `.csv` (sim/audit logs) | 553 | 478 | 86.4 % |
| `.yaml` (config snapshots) | 178 | 145 | 81.5 % |
| `.txt` (CRSS_DB reference series) | 4,518 | 3,722 | 82.4 % |
| `.log` | 46 | 32 | 69.6 % |
| `.json` (manifests, integrity) | 613 | 172 | 28.1 % |
| **total** | **6,225** | **4,866** | **78.2 %** |

Every raw JSONL trace file examined is damaged. `.json` fares best (28.1 %)
because it includes many small static config files, but the load-bearing
ones — `reproducibility_manifest.json`, `run_integrity.json` — are hit at
similar rates to everything else (see §4).

## 3. Script re-run: 8/9 fail on the corrupted corpora, 1/9 (control) passes

Commands run from repo root, in the order specified:

```
python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r0_sanity_gate.py
python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r4_flood_headline_variants.py
python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r7_seed_robustness.py
python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r11_flood_seed_matched.py
python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r12b_vaccination_t04b.py
python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r14_advise_arm.py
python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r16_vintage_prompt_check.py
python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r17_strict_arm_vintage_check.py
python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r13_reservoir_t06.py
```

| script | expected headline | recomputed | tail of stdout/stderr |
|---|---|---|---|
| `r0_sanity_gate.py` | governed 36.05 %, no-validator 59.07 % (exact, TOL 0.05) | **FAILED, exit 1** | `_csv.Error: field larger than field limit (131072)` reading seed42 governed `simulation_log.csv` — file is 99.87 % NUL |
| `r4_flood_headline_variants.py` | 3×3×2 IBR grid, governed/live/pre-quarantine | **FAILED, exit 1** | same `_csv.Error` reading `household_governance_audit.csv` |
| `r7_seed_robustness.py` | per-seed irrigation + flood metrics, paired/unpaired p | **FAILED, exit 1** | same `_csv.Error` on `L.load_run` (irrigation `simulation_log.csv`) |
| `r11_flood_seed_matched.py` | n=7 matched flood table, IBR gaps ~7-20 pp | **FAILED, exit 1** | `json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)` — `reproducibility_manifest.json` is 100 % NUL, decodes as an empty string |
| `r12b_vaccination_t04b.py` | parity 3000/3000 (100.00 %), 0 rule fires, uptake 56.7±7.0 % | **FAILED, exit 1** | `_csv.Error` reading `individual_governance_audit.csv` |
| `r14_advise_arm.py` | uptake 16.12±2.02 %, n=5 | **FAILED, exit 1** | discovery step printed `advise-arm seeds COMPLETE: ['42','43','44','45','46']` (directory names present), then `_csv.Error` reading `irrigation_farmer_governance_audit.csv` |
| `r16_vintage_prompt_check.py` | 33 runs, 1 flagged | **FAILED, exit 1** | `_csv.Error` on the first audit CSV it opens |
| `r17_strict_arm_vintage_check.py` | seed-46 outlier check, 5 seeds | **FAILED, exit 1** | `json.decoder.JSONDecodeError` reading a strict-arm `reproducibility_manifest.json` (100 % NUL) |
| `r13_reservoir_t06.py` | 3 seeds, dead_pool 30/23/19 fire/seen, storage min/max/final as in README | **RAN, exit 0** | `wrote out/r13_reservoir_t06.csv (85 rows)` — all 3 seeds report `42/42 rows, clean — no flags` |

**r13 is not evidence the restore is fine.** `RES_ROOT` in `_common.py`
resolves to `wagf-main-runs` (a sibling checkout) whenever the data is absent
from this repo, and it is: `examples/reservoir_control/results/` in this repo
only has 4-year smoke dirs, no T0-6 data. r13's source data was never
touched by the deletion/restore incident, so its success is a **control**
confirming the harness and this verification's diff method work correctly
(it did re-run and re-write its own CSV), not a data point about the four
affected corpora.

Widening the field limit (`csv.field_size_limit`) was **not** attempted — it
would not help: the underlying bytes are gone (replaced with `0x00`), not
merely mis-delimited. A larger limit only changes how far the parser gets
before hitting end-of-file or genuinely garbled rows; it cannot recover
deleted content.

## 4. CSV diff: `out/*.csv` vs the pre-loss reference

Reference copy taken **before any script was re-run**, from
`SUBMISSION_2026/reviewer_prep_2026-09-05/out/` to
`.../scratchpad/out_before_restore/` (31 entries, matches `out/`'s 31 entries
at copy time). Diffed by SHA-256 plus an mtime check, since the interesting
distinction is not just "same bytes" but "did the file even get touched":

| file | byte diff | note |
|---|---|---|
| `r13_reservoir_t06.csv` | **IDENTICAL** | **genuinely regenerated** (mtime advanced) and matched — control passed |
| all other 29 files (`SUMMARY.md`, `r0`...`r17`, `r1`, `r2`...) | IDENTICAL | **NOT regenerated** — mtimes unchanged from 2026-09-06/09/10, because every one of the 8 scripts that write into that set raised before calling `write_csv`. "Identical" here means "never touched this session," not "re-verified." |

No `out/*.csv` is DIFFERENT from the pre-loss reference, because nothing but
r13 was rewritten. **This is the corruption's second effect worth naming
explicitly: the fail-loud contract in `_common.py`/`_loader.py` is working
exactly as designed** ("Missing directory, missing file, missing column,
empty denominator -> raise. Nothing here ever substitutes 0 or NaN") — it
refuses to overwrite a good table with a wrong one computed from corrupted
input. That is the correct behavior, but it also means this diff step
produced no positive evidence about the corpora — only the census (§5) and
the script tracebacks (§3) do.

## 5. Row-count census of the restored corpora

`find <root> -maxdepth 4 -name reproducibility_manifest.json` (as specified)
returns only 42+42+3+0 = 45 hits, because the flood corpus nests one level
deeper than the other three (`single_agent/results/JOH_FINAL/gemma3_4b/Group_C/Run_1/...`
is 5 levels under `results`, not 4). Re-run at `-maxdepth 6` to actually cover
the corpus: **183 manifest-bearing run directories** (irrigation 47 → 47
still, single_agent 42 → 133, vaccination 3 → 3, CRSS_DB 0 → 0 — CRSS_DB has
no per-run manifests, it is reference data, not simulation output).

For each of the 183 dirs: audit CSV located by glob, raw JSONL located under
`raw/*.jsonl` (or top-level), both checked for NUL-byte fraction and line
count; `run_integrity.json` presence checked.

**Headline census numbers:**

| metric | value |
|---|---|
| manifest dirs found | 183 |
| dirs with **zero** anomaly | **0 / 183** |
| dirs whose audit CSV is missing entirely | 5 / 183 |
| dirs whose audit CSV is present but **100 % NUL** (total loss, 0 usable rows) | 96 / 183 |
| dirs with `run_integrity.json` present | 46 / 183 |
| of those, `run_integrity.json` itself 100 % NUL | 10 / 46 |
| total audit rows recoverable across all 178 present-audit-CSV dirs (raw line count − header, not CSV-parsed since most files break mid-field) | **478 rows** |
| largest single-run row recovery | 45 rows (expected 1,000–3,276 per run depending on domain) |

Every single manifest-bearing directory in all three simulation-output roots
carries at least one anomaly (missing file, NUL-corrupted file, or
audit-rows≠jsonl-lines mismatch — the mismatch check itself is close to
meaningless here since both sides are usually independently truncated, but
it is reported as specified). Representative rows (full detail for all 183
in the scratchpad census run, not reproduced here in full):

```
DIR: examples/irrigation_abm/results/advise_feedback_42yr_gemma3_4b_e0eee08c_seed42
  manifest_nul%=0.00
  audit=irrigation_farmer_governance_audit.csv size=8160536 nul%=100.00 lines-1=0
  jsonl=irrigation_farmer_traces.jsonl size=52779797 nul%=94.45 lines=257
  run_integrity.json exists=True nul%=0.0
  ANOMALY: audit csv 100.0% NUL; jsonl 94.5% NUL; audit_rows(0) != jsonl_lines(257)

DIR: examples/vaccination_demo/results/JOH_T0-4b_gemma3_4b_88c21542/Run_42
  manifest_nul%=0.00
  audit=individual_governance_audit.csv size=3322631 nul%=99.38 lines-1=6
  jsonl=individual_traces.jsonl size=11584021 nul%=56.01 lines=455
  run_integrity.json exists=True nul%=0.0
  ANOMALY: audit csv 99.4% NUL; jsonl 56.0% NUL; audit_rows(6) != jsonl_lines(455)
```

**Dirs with `LAUNCH_COMMAND.txt` but no manifest: 12/12, and they are exactly
the pre-registered expected set** (2026-09-10 failed launches, unrelated to
this incident):

- `strict_replication_42yr_gemma3_4b_e0eee08c_seed{42,43,44,45,46}` (5)
- `JOH_T0-2c_disabled_gemma3_4b_e0eee08c_matched/Run_{43,44}` (2)
- `JOH_T1-3_grounded_v1_gemma3_4b_e0eee08c/Run_{42,43,44,45,46}` (5)

No `_FAILED_2026-09-10_ollama_down` copies were found (checked
`-iname "*FAILED*ollama*"` under all three simulation roots — zero hits).
**This one category checks out clean** — it is the same known, pre-existing
gap the package's own README already accounts for, not a new casualty of the
restore.

## 6. `ref/CRSS_DB` vs git

```
git ls-tree -r --name-only 4d9428ad^ -- ref/CRSS_DB | wc -l   ->  4484
find ref/CRSS_DB -type f | wc -l                               ->  4605
```

Structurally: **0 files missing** (every git-tracked path exists on disk),
121 extra untracked files (`Archive/`, `~$....xlsx` lock files, etc. —
pre-existing clutter, not restore-related). The nested
`ref/CRSS_DB/CRSS_DB/...` path is **original repo structure**, confirmed
directly in `git ls-tree` output — not a restore artifact.

10-file SHA-256 sample (`git show 4d9428ad^:<path>` vs disk):

| result | count |
|---|---|
| SHA match | 0 / 10 |
| SHA mismatch, disk content **100 % NUL** (real data loss) | 6 / 10 |
| SHA mismatch, disk content 0 % NUL, size differs by exactly (line count) bytes | 4 / 10 |

The 4 non-null mismatches are **not corruption**: byte-level inspection shows
they are pure LF→CRLF line-ending conversions (verified on
`LB_Baseline_DB/JuniorAgUsesBelowCameo_JuniorAg_Div_req.txt`: git blob is
4,169 bytes / 510 bare `\n`; disk file is 4,679 bytes / 510 `\r\n` / 0 bare
`\n` — exactly +510 bytes, content otherwise identical). The 6 null
mismatches are real: full-file zero-wipe, content unrecoverable from this
copy. This 6/10 rate on a small sample is consistent with, and slightly
worse than, the corpus-wide 82.4 % NUL-file rate measured in §2 for all
CRSS `.txt` files.

## 7. Per-corpus verdict

| corpus | verdict | basis |
|---|---|---|
| **Irrigation** (`examples/irrigation_abm/results`) | **INCOMPLETE — severe data loss.** `r0` (the sanity gate everything else depends on) cannot even load seed 42's `simulation_log.csv` (99.87 % NUL). Across the corpus's manifest dirs, audit rows recoverable are in single/low-double digits per run against an expected 3,276 (78-agent×42-year runs) or 1,000 (advise-arm-style). | r0/r7/r14/r16/r17 tracebacks; census §5 |
| **Flood** (`examples/single_agent/results`) | **INCOMPLETE — severe data loss.** `reproducibility_manifest.json` files (needed just to determine which seed a run directory *is*, per `flood_seed_of`) are frequently 100 % NUL and fail to parse as JSON at all. Audit CSVs that do open hit the same field-limit wall. | r4/r7/r11/r17 tracebacks; census §5 |
| **Vaccination** (`examples/vaccination_demo/results`) | **INCOMPLETE — severe data loss.** All 3 `JOH_T0-4b_gemma3_4b_88c21542/Run_*` dirs: audit CSV ≥99.26 % NUL, single-digit recoverable rows against an expected 1,000/run; one manifest and one `run_integrity.json` are also 100 % NUL. | r12b traceback; census §5 |
| **`ref/CRSS_DB`** | **INCOMPLETE — partial data loss, structurally intact.** Every git-tracked path exists at the right location (0 missing), but content is silently zeroed on a majority of files (82.4 % of `.txt` files corpus-wide contain NUL bytes; 6/10 sampled files are 100 % NUL against their git blob). The 4/10 sampled files that are NOT corrupted differ from git only by a benign CRLF line-ending conversion. | §6; §2 |

**None of the four corpora is byte-complete.** This is not a "some files
missing, most intact" outcome — it is the opposite: file *names, sizes, and
timestamps* were restored correctly (robocopy's directory listing and
`/COPY:DAT` metadata look right, which is presumably why the loss wasn't
caught by eye), but a large majority of file *content* across all four roots
was replaced by NUL bytes. The pattern (whole small files 100 % zeroed; large
append-written logs zeroed everywhere except a trailing fragment near EOF) is
consistent with reading from an invalidated or storage-exhausted Volume
Shadow Copy diff area, or a failed block-level read during the `robocopy /E
/COPY:DAT` restore — root cause is not something this read-only pass can
determine and is flagged for Wenyu's own investigation, not concluded here.

## 8. Recommendation

Do not treat this restore as recovery. Every headline number in
`reviewer_prep_2026-09-05/out/*.csv` is currently **unverifiable against the
restored corpora** — the out/ files on disk are the 2026-09-05/06/09/10
pre-loss values, never re-confirmed, not the corrupted 2026-09-15 state
reproducing them. The restored data should not be relied on for any figure,
table, or reproducibility claim until either (a) a different backup/snapshot
is tried and passes this same script + census + SHA-sample check, or (b) the
affected runs are re-executed from scratch (real-LLM reruns are already
known non-deterministic per project memory, so a rerun is not a byte-for-byte
fix, only a fresh, honest corpus).
