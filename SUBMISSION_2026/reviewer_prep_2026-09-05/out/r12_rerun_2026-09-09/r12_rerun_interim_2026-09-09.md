# R12 rerun — vaccination options-text-parity fix (88c21542), seeds 42/43

**Scope.** Read-only re-check of the r12 parity table against the two completed
NEW-arm runs. Run_44 is still writing (only `LAUNCH_COMMAND.txt` + an in-progress
`raw/` dir exist for it) and is excluded per instructions. No file under
`examples/` or `broker/` was modified; the original
`SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r12_vaccination_t04.py` was not
touched or executed as-is (see "Why r12 was adapted, not run directly" below).

- **NEW arm** (fixed): `examples/vaccination_demo/results/JOH_T0-4b_gemma3_4b_88c21542/Run_42`, `Run_43`
- **OLD arm** (rejected, mis-decoded proposed_skill 57–63% from year 2): `C:/Users/wenyu/Desktop/Lehigh/wagf-main-runs/examples/vaccination_demo/results/JOH_T0-4_gemma3_4b_e0eee08c/Run_42..44` — labelled **REJECTED** in every table below; do not quote these as current numbers.
- Settings: both arms actually ran at **num_ctx 4096 / num_predict 1024** (per `SETTINGS_NOTE.md` — the `reproducibility_manifest.json` value of 16384/-1 is confirmed wrong/unused; the two arms are settings-matched).

## Why r12 was adapted, not run directly

`r12_vaccination_t04.py` as committed cannot run against these two directories unmodified, for two independent reasons found on disk, not assumed:

1. It hardcodes `RUN_DIR_NAME = "JOH_T0-4_gemma3_4b_e0eee08c"` (the OLD/rejected dir name) — it was written for the old batch.
2. It calls `validator_health_rows()`, which reads `<run_dir>/validator_health.csv`. That file **does not exist** in either new run directory (`find ... -iname "*validator*"` on both `Run_42` and `Run_43` returns nothing) — it exists only under the old `e0eee08c` runs. `rule_census_rows()` (the part of r12 that actually drives the parity/rule-fire numbers) does **not** need that file — it reads `failed_rules`/`warning_rules` straight out of the audit CSV — so this only blocks the extra per-rule `seen_count`/`fire_rate` detail table, not the core census.
3. r12's own decision-check (`decision_field_check_row`) decodes the digit against a **fixed** alias table (`{"1":"get_vaccinated","2":"delay","3":"refuse"}`) taken from `config_snapshot.yaml`, not against the literal "Available actions" menu text rendered into each row's own prompt. Per the task, this rerun decodes each row against **the actual menu the model saw that row** (read from `raw/individual_traces.jsonl`'s `input` field), which is the more exacting test given that a menu-vs-mapping mismatch is exactly the class of bug being re-verified.

Adapted script (new file, does not touch the original):
`.../scratchpad/r12_rerun/analyze_r12_rerun.py`

## Exact commands run

```
python .../scratchpad/r12_rerun/analyze_r12_rerun.py
```

(plus several one-off inline `python -c` sanity probes reading the same CSV/JSONL/JSON files, quoted inline below where they inform a specific number). All commands were single-process, read-only, non-GPU.

---

## 1. Parity check — raw-output decision digit vs the rendered option menu, vs `proposed_skill`

Method: for every audit row, joined to its `raw/individual_traces.jsonl` record on
`step_id` (unique 1..1000 in both files; cross-checked on `agent_id`+`year` too —
0 join failures, 0 key mismatches, both seeds). Extracted the literal
`"Available actions:"` block from that record's own `input` (the rendered prompt),
mapped each digit to a skill name by keyword match on that option's own prose
(not an assumed fixed order), extracted the `"decision"` digit from `raw_output`,
and compared the decoded skill to the audit CSV's `proposed_skill`.

| Seed | Year 1 | Year 2 | Year 3 | Year 4 | Year 5 | Year 6 | Year 7 | Year 8 | Year 9 | Year 10 | **Overall** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 42 | 100/100 (100.0%) | 100/100 | 100/100 | 100/100 | 100/100 | 100/100 | 100/100 | 100/100 | 100/100 | 100/100 | **1000/1000 (100.00%)** |
| 43 | 100/100 (100.0%) | 100/100 | 100/100 | 100/100 | 100/100 | 100/100 | 100/100 | 100/100 | 100/100 | 100/100 | **1000/1000 (100.00%)** |

**Pre-registered acceptance (100% parity, all years) is MET on both seeds.** No mismatches — task item 4's "3 example rows if not 100%" does not apply; nothing to show.

Two data-quality checks run alongside the join, both benign:

- `raw_output` differs character-for-character between the audit CSV and `raw/individual_traces.jsonl` on **all 1000/1000 rows, both seeds** — but this is whitespace-only: the CSV writer collapses the JSON's newlines/indentation to spaces (verified on row 1: identical length, first diff at char 7 is `` ` ``` `json {`` (CSV) vs `` ` ```json\n{\n `` (JSONL), rest of the text otherwise identical). Directly confirmed the `"decision"` digit extracted from the CSV copy vs the JSONL copy is **identical on all 1000/1000 rows, both seeds** (0 digit mismatches) — the parity numbers above are insensitive to which copy is used as the source.
- Menu decode never failed (all 3 skills recovered from the prose on every row, both seeds) and the menu's digit→skill mapping was **1=get_vaccinated, 2=delay, 3=refuse on every row inspected** — i.e. the fix appears to have made the menu render identically (order and content) every year, which is consistent with 100% parity holding at every year rather than only year 1 (year 1 was already clean pre-fix per the `SETTINGS_NOTE`/docstring history; years 2–10 were the ones that broke before).

---

## 2. Governance sanity

| Seed | status_counts | failed_rules (ERROR) | warning_rules (WARNING) | retry_count dist | integrity_ok | anomaly counters | render_check_skipped_rows |
|---|---|---|---|---|---|---|---|
| 42 | `{APPROVED: 1000}` | `{}` | `{}` | `{0: 1000}` | `True` | none (all 0/None) | field absent from `run_integrity.json` |
| 43 | `{APPROVED: 1000}` | `{}` | `{}` | `{0: 1000}` | `True` | none (all 0/None) | field absent from `run_integrity.json` |

Anomaly counters checked explicitly (all `0`/`None` on both seeds): `audit_rows_missing_vs_grid`, `audit_rows_missing_vs_configured_grid`, `audit_sentinel_write_failures`, `rules_uncategorised_total`, `world_grounded_coverage_gap`; also `audit_corrected_status_columns=False` on both. `render_check_skipped_rows` is not a key in either `run_integrity.json` (full key list checked; not present under any name).

**HBM construct-rule-fire acceptance criterion: NOT MET.** Zero rules fired (ERROR or WARNING) on either seed — `audit_summary.json`'s own `rule_frequency` and `validator_health` are both `{}` on Run_42, matching the CSV directly. This is a real change from the OLD/rejected arm, which did fire WARNING rules:

| Arm | Seed | failed_rules (ERROR) | warning_rules (WARNING) |
|---|---|---|---|
| NEW (88c21542) | 42 | `{}` | `{}` |
| NEW (88c21542) | 43 | `{}` | `{}` |
| OLD-REJECTED (e0eee08c) | 42 | `{}` | `low_susceptibility_no_get_vaccinated: 4, low_severity_low_benefits_get_vaccinated: 4` |
| OLD-REJECTED (e0eee08c) | 43 | `{}` | `low_severity_low_benefits_get_vaccinated: 2, low_susceptibility_no_get_vaccinated: 6` |
| OLD-REJECTED (e0eee08c) | 44 | `high_cues_low_barriers_refuse_inconsistent: 1` | `low_susceptibility_no_get_vaccinated: 3` |

Checked directly, not inferred: read the five HBM rule definitions out of `config_snapshot.yaml` (`thinking_rules:` block — 1 ERROR `high_susceptibility_high_severity_high_efficacy_no_refuse`, 1 ERROR `high_cues_low_barriers_refuse_inconsistent`, 3 WARNING) and, for every row in both new seeds, evaluated each rule's own precondition directly against that row's `construct_*_LABEL` columns and `proposed_skill`. **Result: 0/1000 rows match any of the five preconditions, on both seeds** — e.g. `low_susceptibility_no_get_vaccinated` requires `SUSCEPTIBILITY_LABEL=VL` and `proposed_skill=get_vaccinated` together, which never co-occurs in either new run. So the zero-fire count is consistent with the label/action combinations that actually occurred in this batch, not (from what the audit columns show) a rule silently failing to fire on a matching row. No claim is made about *why* the label/action combinations shifted between the two arms — that would require comparing model behavior across the fix, which is outside this parity/integrity check.

---

## 3. Outcome numbers — vaccination uptake, per year

"Annual share" = % of the 100 agents whose executed action that year was `get_vaccinated` (agents decide every year; this is not a one-time state — Agent_001/seed42 for example proposes `get_vaccinated` in years 1,2,4-10 and `delay` in year 3). "Cumulative share" = % of agents who have executed `get_vaccinated` at least once by that year. No REJECTED rows exist in any of the 5 runs checked (old or new), so `executed == final_skill == proposed_skill` throughout — **remap_count (proposed_skill ≠ final_skill) is 0 on every run, both arms.**

| Arm | Seed | Y1 | Y2 | Y3 | Y4 | Y5 | Y6 | Y7 | Y8 | Y9 | Y10 | **Final cumulative uptake** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NEW (88c21542) | 42 | 31.0 / 31.0 | 42.0 / 43.0 | 16.0 / 43.0 | 38.0 / 43.0 | 43.0 / 45.0 | 43.0 / 46.0 | 46.0 / 49.0 | 45.0 / 49.0 | 46.0 / 50.0 | 46.0 / 50.0 | **50.0%** |
| NEW (88c21542) | 43 | 39.0 / 39.0 | 48.0 / 48.0 | 20.0 / 49.0 | 48.0 / 50.0 | 48.0 / 51.0 | 49.0 / 52.0 | 52.0 / 55.0 | 51.0 / 56.0 | 51.0 / 56.0 | 51.0 / 56.0 | **56.0%** |
| OLD-REJECTED (e0eee08c) | 42 | 12.0 / 12.0 | 70.0 / 70.0 | 71.0 / 77.0 | 75.0 / 99.0 | 51.0 / 99.0 | 47.0 / 99.0 | 70.0 / 100.0 | 71.0 / 100.0 | 65.0 / 100.0 | 64.0 / 100.0 | **100.0%** |
| OLD-REJECTED (e0eee08c) | 43 | 21.0 / 21.0 | 73.0 / 73.0 | 72.0 / 80.0 | 76.0 / 100.0 | 54.0 / 100.0 | 60.0 / 100.0 | 67.0 / 100.0 | 73.0 / 100.0 | 62.0 / 100.0 | 68.0 / 100.0 | **100.0%** |
| OLD-REJECTED (e0eee08c) | 44 | 22.0 / 22.0 | 77.0 / 77.0 | 77.0 / 87.0 | 69.0 / 100.0 | 56.0 / 100.0 | 68.0 / 100.0 | 68.0 / 100.0 | 74.0 / 100.0 | 59.0 / 100.0 | 74.0 / 100.0 | **100.0%** |

Cell format is `annual% / cumulative%`.

**Read with caution, not as a governance-effect finding:** the NEW arm's cumulative uptake curve (50/56% final) is far below the OLD-REJECTED arm's (100/100/100%). Given the OLD arm's `proposed_skill` was itself mis-decoded 57–63% of the time from year 2 onward, its 100% "cumulative uptake" numbers are exactly the corrupted quantity the parity bug was reported against — they are not a trustworthy baseline to compare the fix's uptake against. This table is provided for later side-by-side use, per the task's ask, not as a conclusion about the fix's effect on uptake.

---

## 4. Files read / commands run

- `SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r12_vaccination_t04.py` (read only, for method/column reference)
- `SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/_common.py` (read only)
- `SUBMISSION_2026/reviewer_prep_2026-09-05/README.md` (read only)
- `examples/vaccination_demo/results/JOH_T0-4b_gemma3_4b_88c21542/SETTINGS_NOTE.md` (read only)
- `examples/vaccination_demo/results/JOH_T0-4b_gemma3_4b_88c21542/Run_{42,43}/{individual_governance_audit.csv, config_snapshot.yaml, reproducibility_manifest.json, run_integrity.json, audit_summary.json, governance_summary.json, raw/individual_traces.jsonl}` (read only)
- `C:/Users/wenyu/Desktop/Lehigh/wagf-main-runs/examples/vaccination_demo/results/JOH_T0-4_gemma3_4b_e0eee08c/Run_{42,43,44}/individual_governance_audit.csv` (read only, reference arm)
- Adapted analysis script (new file): `.../scratchpad/r12_rerun/analyze_r12_rerun.py`, run as:
  ```
  python .../scratchpad/r12_rerun/analyze_r12_rerun.py
  ```
  Full stdout saved alongside at `.../scratchpad/r12_rerun/output.txt`; machine-readable parity summary at `.../scratchpad/r12_rerun/parity_summary.json`.
- Ad hoc `python -c` probes (inline, not saved as files): directory listings for `validator_health.csv` absence; `run_integrity.json` full key dump (both seeds); `reproducibility_manifest.json` full dump (seed 42); CSV-vs-JSONL `raw_output` character-diff + digit-only diff (both seeds); `config_snapshot.yaml` `thinking_rules:` block dump; per-row precondition evaluation of all 5 HBM rules against `construct_*_LABEL`/`proposed_skill` (both seeds).

## 5. Bottom line

1. **Parity: 100.00% on both seeds, all 10 years — pre-registered acceptance MET.** The digit written in `raw_output`, decoded against the actual menu rendered into that row's own prompt, agrees with `proposed_skill` on every one of 2000 rows across the two completed new-arm runs.
2. **Integrity: clean.** `integrity_ok=True`, all anomaly counters 0/None, both seeds; no retries, no rejections, no format faults.
3. **HBM rule-fire acceptance criterion: NOT met** — 0 rule fires (ERROR or WARNING) on both new seeds, versus 8 and 8 WARNING fires on the corresponding OLD-REJECTED seeds. Directly checked that this traces to the label/action combinations in this batch never satisfying any of the 5 rules' own preconditions (0/1000 matches on both seeds) — not, from what the audit columns show, a rule silently failing to fire.
4. **Outcome numbers** are reported side by side for later use; the OLD-REJECTED arm's numbers are exactly the quantity the parity bug corrupted and should not be treated as a baseline.
