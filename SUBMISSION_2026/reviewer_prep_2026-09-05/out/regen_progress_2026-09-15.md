# R20 — regenerated strict-arm progress check, 2026-09-15 (updated 2026-09-16, all 5 seeds)

All five regenerated irrigation strict runs are now complete and
integrity-clean: `examples/irrigation_abm/results/strict_42yr_gemma3_4b_faf1bb12_seed{42,43,44,45,46}`
(3,276 audit rows each, commit `faf1bb12`, `--workers 4`, gemma3:4b). This
replaces the 5-seed corpus destroyed in the 2026-09-15 restore-failure
(`out/r18_restore_verification_2026-09-15.md`: the old
`production_v21_42yr_seed{42..46}` directories are 99.87 % NUL-byte
corrupted and unreadable — every "old" number below comes from the
pre-loss CSVs in `out/`, never from re-reading the destroyed directories).

**Method.** All metrics below are computed by importing the canonical
functions from `SUBMISSION_2026/decomposition/_loader.py` (`L.ibr`,
`L.increase_rate`, `L.load_run`/`L.EXPECTED_ROWS`) and
`SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/_common.py`
(`C.irr_executed`, `C.normalized_entropy`, `C.irr_wsa_audit`, `C.IRR_SKILLS`)
— the same functions `r7_seed_robustness.py` and `r14_advise_arm.py` use —
via scratch scripts at
`C:/Users/wenyu/AppData/Local/Temp/claude/C--Users-wenyu-Desktop-Lehigh-governed-broker-framework/21387aa8-2d35-4c6b-b09a-71504c74882e/scratchpad/regen_compare/compute.py`
and `compute5.py`. Nothing in the reviewer-prep package was modified;
nothing under `examples/` or `broker/` was written. "Old" per-seed values
are read from `out/r14_advise_arm.csv` (arm=strict); old 5-seed mean/sd
from `out/r7_seed_robustness.csv` (`mean_governed`/`sd_governed`, or
computed here from the five `r14_advise_arm.csv` strict rows for the two
metrics r7 does not carry — `approved_first_attempt_pct`,
`rejected_to_fallback_pct`); old top-`failed_rules` shares from
`out/r3_rule_firing_census.csv` (arm=governed, level=ERROR), since the raw
audit CSVs for the old seeds no longer exist to recompute from. The
pre-registered acceptance rule, the integrity gate, and its 0.6 % threshold
are all from `.research/experiment_plan_framework_paper_2026-09-06.md` §0b.

## Pre-registered acceptance (§0b): new 5-seed MEAN vs old ±2sd band — PASS on all 10

§0b's own wording: *"Each regenerated arm's headline must fall within the
OLD arm's 5-seed mean ± 2 sd."* That is a check on the new **mean**, not on
each individual seed (a single seed is expected to wander inside a 5-seed
sampling distribution; the acceptance test is about the arm's headline,
i.e. the new mean). All 10 numeric headline metrics pass.

| metric | old mean ± sd (n=5) | new mean ± sd (n=5) | old band (±2sd) | new mean inside band? |
|---|---:|---:|---|:---:|
| IBR proposal-level (%) | 36.05 ± 3.60 | 31.41 ± 5.47 | [28.86, 43.25] | **yes** |
| IBR executed-level (%) | 0.86 ± 0.12 | 0.97 ± 0.31 | [0.61, 1.11] | **yes** |
| Increase rate, unconditional, proposal (%) | 40.90 ± 4.39 | 38.83 ± 3.99 | [32.12, 49.68] | **yes** |
| Increase rate, unconditional, executed (%) | 3.60 ± 0.99 | 3.38 ± 0.81 | [1.63, 5.57] | **yes** |
| EHE pooled, proposal | 0.672 ± 0.046 | 0.647 ± 0.039 | [0.580, 0.765] | **yes** |
| EHE pooled, executed | 0.170 ± 0.043 | 0.154 ± 0.044 | [0.084, 0.255] | **yes** |
| Mead minimum (ft) | 989.80 ± 14.47 | 996.25 ± 1.21 | [960.87, 1018.74] | **yes** |
| Shortage years (< 1,075 ft) | 14.80 ± 1.92 | 15.20 ± 1.79 | [10.95, 18.65] | **yes** |
| Approved-first-attempt (%) | 36.20 ± 3.78 | 36.22 ± 3.03 | [28.65, 43.75] | **yes** |
| Governance fallback share (%, REJECTED→maintain_demand) | 39.49 ± 4.60 | 38.27 ± 4.08 | [30.29, 48.70] | **yes** |
| First dead-pool year (≤ 895 ft) | "none", all 5 old seeds | "none", all 5 new seeds | — | **yes** |

The earlier 2-seed cut of this report (seed42/43 only) flagged seed42's
IBR as a band miss. With all 5 seeds in, the mean absorbs that seed's
swing — new-mean IBR proposal 31.41 % sits comfortably inside [28.86,
43.25], and new-mean IBR executed 0.97 % sits inside [0.61, 1.11]. New
5-seed sd is larger than old sd for IBR proposal (5.47 vs 3.60) — the
corpus is noisier, not biased — see the per-seed table and sign-consistency
check below for the shape of that noise.

## Per-seed table, old vs new (cell = old / new)

| metric | seed42 | seed43 | seed44 | seed45 | seed46 |
|---|---|---|---|---|---|
| IBR proposal (%) | 36.05 / 26.64 | 36.69 / 39.56 | 33.47 / 27.57 | 32.40 / 34.46 | 41.65 / 28.83 |
| IBR executed (%) | 0.96 / 1.50 | 0.76 / 0.81 | 0.75 / 0.77 | 1.02 / 0.99 | 0.83 / 0.79 |
| Increase rate, proposal (%) | 39.38 / 33.21 | 37.85 / 43.16 | 40.32 / 36.94 | 38.37 / 41.97 | 48.57 / 38.86 |
| Increase rate, executed (%) | 2.78 / 3.05 | 2.81 / 3.11 | 4.79 / 2.75 | 3.08 / 3.17 | 4.55 / 4.79 |
| EHE pooled, proposal | 0.634 / 0.598 | 0.638 / 0.655 | 0.673 / 0.617 | 0.669 / 0.691 | 0.749 / 0.673 |
| EHE pooled, executed | 0.117 / 0.139 | 0.156 / 0.132 | 0.211 / 0.117 | 0.149 / 0.149 | 0.215 / 0.230 |
| Mead minimum (ft) | 997.62 / 996.97 | 994.36 / 995.67 | 996.97 / 996.78 | 996.03 / 994.40 | 964.01 / 997.41 |
| Shortage years | 14 / 13 | 17 / 15 | 15 / 15 | 12 / 15 | 16 / 18 |
| First dead-pool year | none / none | none / none | none / none | none / none | none / none |
| Approved-first-attempt (%) | 38.03 / 40.17 | 39.22 / 36.42 | 36.57 / 37.97 | 37.52 / 32.75 | 29.67 / 33.79 |
| Governance fallback share (%) | 38.68 / 33.30 | 36.36 / 42.40 | 37.21 / 36.66 | 37.64 / 42.58 | 47.59 / 36.39 |

Note on seed46 Mead minimum: the old seed46 value (964.01 ft) was itself
the outlier that inflated the old 5-seed sd for this metric (the other 4
old seeds sit at 994–998 ft); the new seed46 (997.41 ft) is in line with
the other 4 new seeds. This reads as the old seed46 run being the unusual
one, not the new one.

## Paired old→new difference (new − old), by seed, and sign consistency

Sign consistency is a stricter bar than the pre-registered acceptance test
(which only requires the mean to fall in-band) — it asks whether the
regen moved every seed the same direction. None of the 10 metrics pass
that stricter bar; all show 3-vs-2 or worse sign splits, i.e. genuine
seed-to-seed noise rather than a uniform regen-induced shift.

| metric | Δ42 | Δ43 | Δ44 | Δ45 | Δ46 | signs (+/−/0) | all same sign? |
|---|---:|---:|---:|---:|---:|:---:|:---:|
| IBR proposal (pp) | −9.40 | +2.88 | −5.90 | +2.06 | −12.83 | 2+/3− | no |
| IBR executed (pp) | +0.54 | +0.05 | +0.02 | −0.04 | −0.03 | 3+/2− | no |
| Increase rate, proposal (pp) | −6.17 | +5.31 | −3.39 | +3.60 | −9.71 | 2+/3− | no |
| Increase rate, executed (pp) | +0.27 | +0.31 | −2.05 | +0.09 | +0.24 | 4+/1− | no |
| EHE pooled, proposal | −0.036 | +0.018 | −0.056 | +0.021 | −0.076 | 2+/3− | no |
| EHE pooled, executed | +0.022 | −0.023 | −0.094 | 0.000 | +0.015 | 2+/2−/1·0 | no |
| Mead minimum (ft) | −0.65 | +1.31 | −0.19 | −1.63 | +33.39 | 2+/3− | no |
| Shortage years | −1 | −2 | 0 | +3 | +2 | 2+/2−/1·0 | no |
| Approved-first-attempt (pp) | +2.14 | −2.81 | +1.40 | −4.76 | +4.12 | 3+/2− | no |
| Governance fallback share (pp) | −5.37 | +6.04 | −0.55 | +4.95 | −11.20 | 2+/3− | no |

Every metric splits roughly 2-vs-3 or 3-vs-2 across the 5 seeds — consistent
with real-LLM sampling noise at fixed seed+commit (already documented for
gemma4:e4b in `.baselines/BASELINE_HASHES.md`; gemma3:4b evidently shares
the property), not a systematic regen artifact. That is exactly why §0b's
acceptance criterion is a 5-seed-mean-in-band test, not a per-seed or
same-sign test.

## Top failed_rules (validator blocking), all five seeds, old vs new

| rule_id | old s42 | old s43 | old s44 | old s45 | old s46 | old mean±sd | new s42 | new s43 | new s44 | new s45 | new s46 | new mean±sd |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| demand_ceiling_stabilizer | 50.18 | 55.65 | 51.19 | 48.29 | 57.51 | 52.56 ± 3.87 | 45.45 | 55.04 | 51.40 | 56.41 | 53.94 | 52.45 ± 4.32 |
| high_threat_high_cope_no_increase | 32.14 | 34.65 | 34.10 | 27.38 | 38.58 | 33.37 ± 4.08 | 29.00 | 38.10 | 30.13 | 35.96 | 36.45 | 33.93 ± 4.08 |
| curtailment_awareness | 18.93 | 22.25 | 19.84 | 15.42 | 21.12 | 19.51 ± 2.61 | 16.24 | 19.99 | 18.80 | 19.35 | 22.92 | 19.46 ± 2.40 |
| supply_gap_block_increase | 7.02 | 6.78 | 6.72 | 6.44 | 6.96 | 6.78 ± 0.23 | 6.56 | 7.11 | 6.53 | 7.02 | 8.33 | 7.11 ± 0.73 |
| demand_floor_stabilizer | 6.01 | 4.09 | 6.90 | 8.27 | 8.52 | 6.76 ± 1.81 | 6.59 | 4.30 | 4.67 | 8.42 | 6.53 | 6.10 ± 1.67 |
| low_threat_no_increase | 1.50 | 1.28 | 1.53 | 1.95 | 2.08 | 1.67 ± 0.33 | 1.37 | 1.62 | 1.43 | 1.07 | 1.01 | 1.30 ± 0.26 |

Same rank order in every old seed and every new seed
(`demand_ceiling_stabilizer` > `high_threat_high_cope_no_increase` >
`curtailment_awareness` > {`supply_gap_block_increase`,
`demand_floor_stabilizer`} > `low_threat_no_increase`), and old vs new
5-seed mean shares agree to within ≤1.2 pp on every rule — the validator
is blocking the same rule classes at the same relative rates it did
before the corruption.

## LLM-failure counts, governance fallback share, and wall time, per seed

`fallback_activated` and `llm_success` are read directly from
`irrigation_farmer_governance_audit.csv` (not derived from `status`).
`fallback_activated=True` fires only on `status=REJECTED_FALLBACK` rows
(LLM timeout/parse failure → registry-default execution) — a **strict
subset** of the broader "governance fallback share" above (which also
includes ordinary validator-blocked `status=REJECTED` rows, where
`fallback_activated=False`). Wall time = last audit `timestamp` minus
first audit `timestamp` for that seed.

| seed | llm_success=False (n, %) | fallback_activated (n, %) | §0b gate (≤0.6% each) | governance fallback share (%) | wall time (h) | audit start → end (UTC-naive, local) |
|---|---:|---:|:---:|---:|---:|---|
| 42 | 0 / 0.000% | 43 / 1.313% | **FAIL** (fallback_activated) | 33.30 | 3.02 | 2026-09-15 12:04:42 → 15:06:02 |
| 43 | 0 / 0.000% | 44 / 1.343% | **FAIL** (fallback_activated) | 42.40 | 3.22 | 2026-09-15 15:09:02 → 18:22:07 |
| 44 | 0 / 0.000% | 39 / 1.190% | **FAIL** (fallback_activated) | 36.66 | 3.10 | 2026-09-15 18:23:35 → 21:29:37 |
| 45 | 0 / 0.000% | 40 / 1.221% | **FAIL** (fallback_activated) | 42.58 | 3.35 | 2026-09-15 21:31:24 → 2026-09-16 00:52:16 |
| 46 | 0 / 0.000% | 33 / 1.007% | **FAIL** (fallback_activated) | 36.39 | 3.19 | 2026-09-16 00:53:31 → 04:05:03 |
| **mean ± sd** | 0.000% ± 0.000 | **1.215% ± 0.132** | **0/5 seeds pass** | 38.27 ± 4.08 | 3.18 ± 0.12 | queue span 12:04:42 (9/15) → 04:05:03 (9/16), ≈16.0 h total |

**Flagging this, not silently passing it.** The §0b integrity gate is two
separate ≤0.6% checks. `llm_success==False` is clean on every seed (0/3,276
each — no outright LLM call failures). `fallback_activated` is **not**
clean on any seed: 1.01–1.34% (mean 1.22%), roughly **double** the 0.6%
ceiling, on all 5 seeds uniformly (sd across seeds is small, 0.13pp — this
looks like a consistent property of `--workers 4`, not a one-off). Per
§0b's own rule — *"Any seed above the threshold is re-run, not
analysed"* — this is a literal gate miss on the `fallback_activated`
sub-check for all 5 seeds. Two things temper it without resolving it: (1)
the plan's own 0.6% figure is itself derived from two ~0.6%-each old
sub-counts ("20 format retries and 19 structural faults... ≈0.6%" —
20/3276=0.61%, 19/3276=0.58%) whose combined old rate would be ≈1.19% if
`fallback_activated` is the union of both failure modes, which is within
0.05pp of the new mean (1.22%) — i.e. the new rate may in fact be
consistent with the old corpus's own combined repair rate, and the 0.6%
ceiling as literally stated may be under-specified for a single combined
column; (2) `fallback_activated` still only accounts for 33–44 of 3,276
rows per seed (~1.2%) and the headline metrics it feeds (IBR executed,
governance fallback share) are the ones that passed the §0b band check
above. This is a judgment call for the experiment owner, not something to
resolve unilaterally here — recommend re-reading `r19_prelaunch_settings_audit_2026-09-15.md`
§8.3's derivation of the 0.6% figure against the new per-seed numbers
before deciding whether to re-run or to treat the gate as satisfied by the
combined-rate reading.

Wall time at `--workers 4`: 3.02–3.35 h/seed (mean 3.18 ± 0.12 h),
consistently below the plan's own `--workers 1` estimate of ~10–11 h/seed
(§0b GPU-hour table) — the expected effect of 4-way parallelism, and
itself part of why the 120 s-timeout tail risk that produces
`fallback_activated` rows is elevated (per-call latency rises under
`--workers 4`, as `r19` §8.3 predicted before launch).

## Per-year action shares (proposal level), quick trend — seed42/43 only (unchanged from the 2026-09-15 cut)

| seed | increase_pct mean (min–max) | maintain_pct mean (min–max) | decrease_pct mean (min–max) | years maintain is NOT the plurality |
|---|---|---|---|---|
| 42 | 33.21% (6.41–88.46) | 63.43% (8.97–91.03) | 3.36% (0–17.95) | 6/42 (years 1,2,3,6,7,8) |
| 43 | 43.16% (14.10–84.62) | 54.58% (12.82–83.33) | 2.26% (0–11.54) | 13/42 (years 1,2,3,6,7,8,15,18,22,27,28,36,37) |

Both seeds show the same shape: a burst of `increase` in the first few
years (Y1 ≈ 80–88%, consistent with the documented Y1 seed-memory
adaptation pattern, not a defect), settling to `maintain_demand` as the
plurality action for most of the run.

## Context: old ungoverned 5-seed means — SUPERSEDED 2026-09-16, see below

(Originally quoted here, before the ungoverned regen existed, as
context-only: IBR proposal 59.07 ± 1.66, IBR executed 26.77 ± 1.08,
increase rate proposal 62.52 ± 1.18, increase rate executed 33.50 ± 1.50,
EHE proposal 0.857 ± 0.011, EHE executed 0.810 ± 0.026, Mead min 895.0 ±
0.0, shortage years 38.2 ± 0.84. The regenerated ungoverned arm is now
complete — see "Ungoverned arm" and "Governed-vs-ungoverned contrasts"
below for the actual new-corpus numbers and the pre-registered band
check, rather than a directional comparison against a governed-only
regen.)

---

# 2026-09-16 update — ungoverned arm regenerated, governed-vs-ungoverned reproduced on the new corpus

The regenerated irrigation **ungoverned** arm is complete:
`examples/irrigation_abm/results/ungoverned_42yr_gemma3_4b_faf1bb12_seed{42..46}`
(3,276 rows each, commit `faf1bb12`, `--workers 4`, gemma3:4b). In this
arm every non-`APPROVED` row's `failed_rules` value is the single literal
string `precondition_violation` (the skill-registry precondition `not
at_allocation_cap`) — there are no custom governance "thinking rules" to
block on, since this arm has no validators attached. Method, functions
imported, and read-only guarantee are unchanged from the governed-arm
sections above; the new scratch script is
`.../scratchpad/regen_compare/compute_ungoverned.py` (same scratchpad
directory as `compute.py`/`compute5.py`). Old ungoverned per-seed values
are read from `out/r14_advise_arm.csv` (arm=`no_validator`); old 5-seed
mean/sd and old governed-vs-ungoverned contrast statistics (t, paired-t p,
exact permutation p) are read from `out/r7_seed_robustness.csv`
(`pairing=seed_matched_n5`, seeds 42–46) without recomputing them, since
the OLD raw run directories no longer exist post-restore-failure.

## (1) Ungoverned arm — per-seed and 5-seed mean ± sd vs old, band check on new mean

| metric | old mean ± sd (n=5) | new mean ± sd (n=5) | old band (±2sd) | new mean inside band? |
|---|---:|---:|---|:---:|
| IBR proposal-level (%) | 59.07 ± 1.66 | 56.64 ± 2.10 | [55.75, 62.39] | **yes** |
| IBR executed-level (%) | 26.77 ± 1.08 | 27.64 ± 1.62 | [24.60, 28.93] | **yes** |
| Increase rate, unconditional, proposal (%) | 62.52 ± 1.18 | 60.85 ± 1.50 | [60.16, 64.88] | **yes** |
| Increase rate, unconditional, executed (%) | 33.50 ± 1.50 | 34.79 ± 1.18 | [30.50, 36.50] | **yes** |
| EHE pooled, proposal | 0.857 ± 0.011 | 0.872 ± 0.005 | [0.836, 0.878] | **yes** |
| EHE pooled, executed | 0.810 ± 0.026 | 0.818 ± 0.015 | [0.757, 0.863] | **yes** |
| Mead minimum (ft) | 895.00 ± 0.00 | 895.00 ± 0.00 | [895.00, 895.00] | **yes** (exact) |
| Shortage years (< 1,075 ft) | 38.20 ± 0.84 | 38.00 ± 1.00 | [36.53, 39.87] | **yes** |
| Approved-first-attempt (%) | 64.62 ± 2.93 | 65.68 ± 2.25 | [58.75, 70.48] | **yes** |
| No-validator fallback share (%, REJECTED*→maintain_demand — mostly `precondition_violation`, not a "thinking rule") | 29.04 ± 2.49 | 26.11 ± 1.79 | [24.06, 34.02] | **yes** |
| First dead-pool year (≤ 895 ft) | old range 17–18, all 5 seeds | new range 17–18, all 5 seeds | — | **yes** |

All 10 numeric metrics pass; Mead minimum is an exact match (895.00 ft,
i.e. dead pool reached, in **every** old seed and **every** new seed — sd
is 0 on both sides, so the "band" collapses to a point and the new mean
hits it exactly).

Per-seed detail (old/new, Δ=new−old):

| metric | seed42 | seed43 | seed44 | seed45 | seed46 |
|---|---|---|---|---|---|
| IBR proposal (%) | 61.47/59.33 (−2.14) | 58.26/55.29 (−2.97) | 58.86/58.50 (−0.36) | 57.04/55.20 (−1.84) | 59.72/54.88 (−4.84) |
| IBR executed (%) | 25.32/27.58 (+2.26) | 27.16/25.35 (−1.80) | 26.09/29.29 (+3.19) | 28.11/29.08 (+0.96) | 27.16/26.93 (−0.23) |
| Increase rate, proposal (%) | 64.19/62.70 (−1.50) | 62.30/59.65 (−2.66) | 61.84/62.27 (+0.43) | 61.14/59.89 (−1.25) | 63.13/59.77 (−3.36) |
| Increase rate, executed (%) | 31.50/34.07 (+2.56) | 34.25/33.61 (−0.64) | 32.54/35.84 (+3.30) | 35.35/36.26 (+0.92) | 33.85/34.19 (+0.34) |
| EHE pooled, proposal | 0.848/0.868 (+0.020) | 0.874/0.871 (−0.003) | 0.856/0.866 (+0.011) | 0.857/0.879 (+0.022) | 0.849/0.872 (+0.023) |
| EHE pooled, executed | 0.778/0.804 (+0.026) | 0.825/0.804 (−0.021) | 0.789/0.825 (+0.036) | 0.842/0.838 (−0.004) | 0.816/0.819 (+0.003) |
| Mead minimum (ft) | 895.00/895.00 (0.00) | 895.00/895.00 (0.00) | 895.00/895.00 (0.00) | 895.00/895.00 (0.00) | 895.00/895.00 (0.00) |
| Shortage years | 39/39 (0) | 37/37 (0) | 39/39 (0) | 38/37 (−1) | 38/38 (0) |
| First dead-pool year | 17/17 | 17/18 | 18/18 | 18/18 | 17/18 |
| Approved-first-attempt (%) | 60.90/62.79 (+1.89) | 64.62/65.08 (+0.46) | 63.25/65.72 (+2.47) | 68.86/69.08 (+0.21) | 65.45/65.72 (+0.27) |
| No-validator fallback share (%) | 32.69/28.66 (−4.03) | 28.05/26.16 (−1.89) | 29.33/26.43 (−2.90) | 25.82/23.69 (−2.14) | 29.30/25.58 (−3.72) |

Sign consistency of the old→new Δ across all 5 seeds: **consistent** for
IBR proposal (all 5 negative), Mead minimum (all exactly 0), approved-
first-attempt (all 5 positive), and no-validator fallback share (all 5
negative) — those four move together. The rest (IBR executed, both
increase rates, both EHE levels, shortage years) split 3-vs-2 or 4-vs-1,
the same seed-noise signature seen in the governed arm.

## (2) Governed-vs-ungoverned contrasts — NEW corpus vs OLD corpus, seed-paired (n=5, df=4)

Diff = governed − ungoverned, same seed. `p_exact_perm` floor for n=5 is
2/32 = 0.0625 — every row here sits exactly at that floor (all 5 seeds
agree in sign), which is the best a paired n=5 permutation test can ever
report; the paired-t p is the more informative column, and it is what
actually discriminates strength of evidence here.

| metric | OLD mean_diff ± sd | OLD t (df=4), p_paired_t, p_perm | NEW mean_diff ± sd | NEW t (df=4), p_paired_t, p_perm | same sign old vs new? | all 5 new seeds same sign? |
|---|---:|---|---:|---|:---:|:---:|
| ΔIBR proposal (pp) | −23.02 ± 3.19 | −16.15, 0.0001, 0.0625 | −25.23 ± 7.05 | −8.00, 0.0013, 0.0625 | yes | **yes** |
| ΔIBR executed (pp) | −25.90 ± 1.07 | −54.31, <0.0001, 0.0625 | −26.67 ± 1.63 | −36.64, <0.0001, 0.0625 | yes | **yes** |
| Δincrease rate, proposal (pp) | −21.62 ± 4.17 | −11.61, 0.0003, 0.0625 | −22.03 ± 5.37 | −9.17, 0.0008, 0.0625 | yes | **yes** |
| Δincrease rate, executed (pp) | −29.90 ± 1.89 | −35.31, <0.0001, 0.0625 | −31.42 ± 1.63 | −42.97, <0.0001, 0.0625 | yes | **yes** |
| ΔEHE pooled, proposal | −0.185 ± 0.052 | −7.95, 0.0014, 0.0625 | −0.225 ± 0.035 | −14.56, 0.0001, 0.0625 | yes | **yes** |
| ΔEHE pooled, executed | −0.641 ± 0.049 | −29.26, <0.0001, 0.0625 | −0.665 ± 0.046 | −32.67, <0.0001, 0.0625 | yes | **yes** |
| ΔMead minimum (ft) | +94.80 ± 14.47 | +14.65, 0.0001, 0.0625 | +101.25 ± 1.21 | +186.55, <0.0001, 0.0625 | yes | **yes** |
| Δshortage years | −23.40 ± 2.41 | −21.73, <0.0001, 0.0625 | −22.80 ± 2.28 | −22.36, <0.0001, 0.0625 | yes | **yes** |

Every one of the 8 contrasts reproduces on the new corpus: same sign as
the old contrast, same order of magnitude (new mean_diff within
0.4–2.2 pp of the old mean_diff on the four IBR/increase-rate rows,
within 0.02–0.04 on the two EHE rows, within 6.5 ft on ΔMead minimum, and
within 0.6 years on Δshortage years — see the precise figures in the
table above), and — unlike the noisy
old-vs-new per-seed diffs in section (1) and in the governed-arm sections
above — **every governed-vs-ungoverned contrast is sign-consistent across
all 5 new seeds**, exactly as it was in the old corpus. This is the
headline the paper quotes, and it reproduces cleanly.

ΔMead minimum's new sd (1.21) is far smaller than the old sd (14.47) —
this is the same seed46 effect flagged in the governed-arm section above
(old governed seed46 had an anomalous 964.01 ft minimum; new governed
seed46 is 997.41 ft, in line with the other 4 seeds), not a new-corpus
artifact on the ungoverned side (ungoverned mead_min_ft = 895.00 ft
exactly, sd = 0, in both old and new corpora).

## (3) Ungoverned arm — LLM-failure counts, fallback share, wall time

| seed | llm_success=False (n, %) | fallback_activated (n, %) | §0b gate (≤0.6% each) | no-validator fallback share (%) | wall time (h) | audit start → end |
|---|---:|---:|:---:|---:|---:|---|
| 42 | 0 / 0.000% | 1 / 0.031% | **pass** | 28.66 | 2.59 | 2026-09-16 04:06:48 → 06:42:14 |
| 43 | 0 / 0.000% | 4 / 0.122% | **pass** | 26.16 | 2.50 | 2026-09-16 06:43:50 → 09:13:59 |
| 44 | 0 / 0.000% | 0 / 0.000% | **pass** | 26.43 | 2.45 | 2026-09-16 09:15:33 → 11:42:48 |
| 45 | 0 / 0.000% | 2 / 0.061% | **pass** | 23.69 | 2.38 | 2026-09-16 11:44:30 → 14:07:30 |
| 46 | 0 / 0.000% | 0 / 0.000% | **pass** | 25.58 | 2.54 | 2026-09-16 14:11:54 → 16:44:13 |
| **mean ± sd** | 0.000% ± 0.000 | **0.043% ± 0.051** | **5/5 seeds pass** | 26.11 ± 1.79 | 2.49 ± 0.08 | queue span 04:06:48 → 16:44:13, ≈12.6 h total |

Sharp contrast with the governed arm: the ungoverned §0b integrity gate
**passes cleanly on both sub-checks, all 5 seeds** (fallback_activated
mean 0.04%, max 0.12%, well under 0.6%), whereas the governed arm's
`fallback_activated` failed the same 0.6% ceiling on all 5 seeds (mean
1.22%, see the governed-arm section above). That is consistent with the
governed arm's own explanation for its elevated rate: governed prompts
carry the extra validator/rule context, so they run longer per call under
`--workers 4` and cross the 120 s timeout tail more often; the ungoverned
arm has no such extra context and its wall time is correspondingly
shorter too (mean 2.49 h/seed vs governed's 3.18 h/seed, a ~22% speedup
alongside the LLM-failure-rate collapse from ~1.2% to ~0.04%).

## (4) One-paragraph read — does the new corpus reproduce the published governed-vs-ungoverned story?

Yes, on every axis checked. Direction: all 8 governed-vs-ungoverned
contrasts have the same sign on the new corpus as on the old corpus
(governed lower IBR/increase-rate/EHE, governed higher Mead minimum and
lower shortage years), and — unlike the individual old-vs-new
reproduction checks, which are noisy at the single-seed level — every one
of those 8 contrasts is sign-consistent across all 5 new seeds, the same
as the old corpus. Magnitude: every new contrast's mean_diff falls within about 0.4–2.2
percentage points of the old contrast's mean_diff on the four IBR/
increase-rate contrasts, within 0.02–0.04 (unitless) on the two EHE
contrasts, within 6.5 ft on Mead minimum, and within 0.6 years on
shortage years — and both the new ungoverned 5-seed mean and the
new governed 5-seed mean (reported in the governed-arm section above)
land inside their respective old ±2sd bands on all 10 numeric metrics —
so the gap is not just directionally right, it is quantitatively where
the pre-loss corpus put it. Mead dead-pool: reached in **every** one of
the 5 new ungoverned seeds (mead_min_ft = 895.00 ft exactly, first
dead-pool year 17 or 18), identical to all 5 old ungoverned seeds — the
ungoverned arm still runs the reservoir dry every single run, while the
new governed arm never reaches it in any of its 5 seeds (mead_min_ft
994–997 ft, `first_dead_pool_year = "none"` throughout, matching the old
governed corpus). Net: the paper's headline governed-vs-ungoverned gap —
originally quoted as 36.05 vs 59.07 (IBR proposal) — reproduces on the
regenerated corpus as 31.41 vs 56.64 (mean_diff −25.23pp, paired t=−8.00,
p=0.0013, all 5 seeds agree in sign), the same story, inside the same
statistical bands, from an entirely new set of real-LLM runs.

## Summary read

The regenerated 5-seed strict corpus passes the pre-registered §0b
acceptance test on every one of the 10 numeric headline metrics plus the
categorical dead-pool check — the new 5-seed mean falls inside the old
±2sd band in every case, including the two metrics (IBR proposal/executed)
that a single seed (42) had appeared to miss on in the earlier 2-seed cut
of this report. Structurally the trend looks the same: the validator
blocks the same three rule classes in the same rank order at closely
matching shares (≤1.2pp mean-to-mean), Mead never approaches the 895 ft
dead pool in any of the 5 new seeds (matching all 5 old seeds), and the
action mix is still `maintain_demand`-dominated after an early increase
burst. No metric shows the same sign of old→new change across all 5
seeds — every one splits roughly 2-vs-3 — which is the expected signature
of real-LLM sampling noise at fixed seed+commit, not a systematic shift,
and it's why the acceptance test is defined on the mean rather than on
individual seeds or sign agreement. The one finding that does **not**
reduce to noise: `fallback_activated` sits at 1.01–1.34% (mean 1.22%) on
every one of the 5 new seeds, roughly double the plan's literal 0.6%
per-seed ceiling and uniform enough across seeds (sd 0.13pp) to look like
a property of `--workers 4` rather than chance — `llm_success==False` is
clean at 0.000% throughout. Whether this counts as a gate failure
requiring a re-run, or is within the old corpus's own combined repair
rate (≈1.19% if the old "20 format retries + 19 structural faults" both
map to `fallback_activated`), is flagged above for the experiment owner
to decide rather than resolved here.


## Note added by the orchestrator (2026-09-16)

The "integrity-gate finding" above (fallback_activated 1.01–1.34 % vs a literal 0.6 % ceiling) is superseded: on 2026-09-15 the experiment owner REMOVED the fallback gate (plan §0b, "Gate removed"). `fallback_activated` on these rows is governance exhaustion (three blocked proposals → registry default) with `llm_success == True`, 0 timeouts, 0 empty responses; it is reported as a result (1.22 % ± 0.13 across seeds; old corpus ≈ 0.6–1.2 % depending on the sub-count read) and does not trigger re-runs. The acceptance decision for the strict arm is therefore: all 10 headline metrics PASS the pre-registered ±2 sd band on the 5-seed mean; LLM-failure count 0 on every seed.


# 2026-09-16 update — flood single-agent STRICT arm regenerated (faf1bb12), 5 seeds

Full tables: `out/r23_flood_strict_regen.md` (generated by
`scripts/r23_flood_strict_regen.py` from the same rows as
`out/r23_flood_strict_regen.csv`). Runs: `examples/single_agent/results/
JOH_strict_gemma3_4b_faf1bb12/Run_{42..46}`, `--workers 1`,
`--thinking-mode disabled`, all `integrity_ok`, `llm_success==False` count 0
on every seed.

## Band check (new 5-seed mean vs old mean ± 2·sd(old), ddof=1) — PASS on 6/6

| metric | old mean ± sd | new mean ± sd | band | verdict |
|---|---:|---:|---|:---:|
| IBR unconditional (%) | 0.868 ± 0.907 | 0.788 ± 0.434 | [-0.945, 2.681] | PASS |
| IBR tp_not_medium (%) | 1.603 ± 1.514 | 1.624 ± 0.853 | [-1.426, 4.632] | PASS |
| IBR tp_high (%) | 2.510 ± 2.361 | 2.204 ± 1.198 | [-2.212, 7.232] | PASS |
| EHE pooled simlog | 0.861 ± 0.044 | 0.859 ± 0.011 | [0.772, 0.951] | PASS |
| Rejection rate (%) | 1.071 ± 1.060 | 0.882 ± 0.462 | [-1.048, 3.190] | PASS |
| Retry rate (%) | 8.357 ± 3.823 | 8.727 ± 1.467 | [0.711, 16.003] | PASS |

The nine IBR cells (3 conditionings × proposal/final/executed) collapse to the
three rows above because this flood validator writes `final_skill =
do_nothing` on every REJECTED row, so the executed remap is a no-op (asserted
at runtime, 0 mismatches on all 5 seeds).

## Provenance caveat (surfaced by the script, not hidden)

The old published governed corpus's five runs were seeds {42, 4202, 4203,
45, 46}, not {42..46}: `r4_flood_headline_variants.csv` has empty
`run_2_seed43` / `run_3_seed44` columns for every governed row. The new arm
uses literal seeds 42..46, so run positions 2 and 3 pair new 43/44 against
old 4202/4203. The band check is on 5-seed means and is unaffected; the
per-seed table in r23 labels those two columns accordingly.

## Governance fallback, LLM failures, wall time (new arm; no old per-seed record exists)

| seed | rows | LLM fail | APPROVED | REJECTED | REJECTED_FALLBACK | fallback % | wall h |
|---|---:|---:|---:|---:|---:|---:|---:|
| 42 | 877 | 0 | 866 | 11 | 0 | 0.000 | 1.07 |
| 43 | 885 | 0 | 882 | 2 | 1 | 0.113 | 1.00 |
| 44 | 809 | 0 | 798 | 9 | 2 | 0.247 | 1.01 |
| 45 | 867 | 0 | 863 | 4 | 0 | 0.000 | 0.96 |
| 46 | 903 | 0 | 894 | 8 | 1 | 0.111 | 1.01 |

Compute cost (r21, re-run 2026-09-16 with the flood arm included): flood
strict 1.011 ± 0.039 h per run, 868 ± 36 decisions, 977 ± 46 LLM calls,
~0.75 M estimated prompt tokens per run (chars/4); `reflections` is 0 for
flood because that column counts `reflection_log.jsonl`, and these runs use
the runner's default memory engine (`--memory-engine window`; manifest
`memory_engine_class: DecisionFilteredMemoryEngine`, `memory_engine_type`
unset), under which `run_flood.py` instantiates no `ReflectionEngine`. The
salvaged old disabled-arm manifests record the same engine class; the old
governed Run_1 manifest predates the memory fields. The flood domain does
write a reflection log when launched with `--memory-engine humancentric`,
which none of these arms use.

## Read

The regenerated strict arm reproduces the old flood governed arm at the
pre-registered tolerance on every headline metric. Point estimates moved
(unconditional IBR 0.87 → 0.79 %; tp_high 2.51 → 2.20 %) with smaller
between-seed spread in the new arm (sd 0.43 vs 0.91 for unconditional IBR).
The disabled (no-validator) arm is regenerating next; the governed-vs-
ungoverned contrast (old 0.87 vs 7.41 % executed IBR) is checked when it
lands (r24).

Review trail: r23 script + outputs reviewed by a sonnet code-reviewer in two
rounds (round 1 REQUEST CHANGES: the .md had been hand-written with wrong
per-seed cells; round 2 APPROVE after the .md became a script output
rendered from the CSV rows, 0 cell mismatches, deterministic re-run).


# 2026-09-17 update — flood DISABLED (no-validator) arm regenerated; governed-vs-ungoverned contrast checked on both corpora

Full tables: `out/r24_flood_contrast_regen.md` (rendered by
`scripts/r24_flood_contrast_regen.py` from the same rows as
`out/r24_flood_contrast_regen.csv`; imports r23's per-run metric code).
Runs: `examples/single_agent/results/JOH_disabled_gemma3_4b_faf1bb12/
Run_{42..46}`, `--workers 1`, `--thinking-mode disabled`; every row
APPROVED (no validator), `llm_success==False` count 0 on all five seeds,
0.79–0.97 h per run. Queue log: QUEUE_END 2026-09-17 02:26.

## (1) Disabled arm — band check (new 5-seed mean vs old mean ± 2·sd(old), ddof=1): 3 of 4 inside

| metric | old mean ± sd | new mean ± sd | band | verdict |
|---|---:|---:|---|:---:|
| IBR unconditional (%) | 7.412 ± 0.761 | 8.912 ± 0.722 | [5.891, 8.933] | PASS |
| IBR tp_not_medium (%) | 14.218 ± 0.772 | 17.268 ± 0.824 | [12.675, 15.761] | **FAIL** |
| IBR tp_high (%) | 22.560 ± 3.640 | 20.935 ± 1.548 | [15.280, 29.841] | PASS |
| EHE pooled simlog | 0.786 ± 0.040 | 0.863 ± 0.030 | [0.707, 0.865] | PASS |
| Rejection / retry rate (%) | 0 / 0 | 0 / 0 | no band (old all zero) | n.a. |

**Not baselined, stated as found.** The new no-validator arm is more
appraisal-inconsistent than the old one under the threat-relevant
conditioning: tp_not_medium IBR is higher on every seed (+1.5 to +4.9 pp;
new 17.27 % vs old 14.22 %, band upper 15.76 %). Unconditional IBR (8.91 %)
and EHE (0.863) sit just inside their upper bounds. The old band is narrow
because the old arm's between-seed sd was 0.77 pp. Two known vintage
differences between the corpora are candidate explanations and are
recorded rather than tested here: (i) the old no-validator arm mixes two
Feb-2026 runs (mean injected memory 876 and 902 chars) with three
May-2026 backfilled runs (1036 to 1085 chars), per r16, so the old arm is
not one vintage; (ii) the new corpus runs at faf1bb12 with the
per-agent RNG keying and the timeout floor. The old seeds for this arm are
literally {42..46} (r4's 4202/4203 columns are empty for arm=ungoverned),
so this is a same-seed comparison.

## (2) Governed-vs-ungoverned contrast (ungoverned − governed), NEW corpus (paired by seed) vs OLD corpus (paired by run position)

| metric | NEW Δ ± sd | NEW p (paired t, df 4) | NEW all 5 signs agree | OLD Δ ± sd | OLD p | OLD all 5 signs agree |
|---|---:|---:|:---:|---:|---:|:---:|
| IBR unconditional (%) | 8.124 ± 0.543 | < 0.0001 | yes | 6.544 ± 0.915 | 0.0001 | yes |
| IBR tp_not_medium (%) | 15.645 ± 0.654 | < 0.0001 | yes | 12.615 ± 1.450 | < 0.0001 | yes |
| IBR tp_high (%) | 18.731 ± 2.179 | < 0.0001 | yes | 20.050 ± 2.410 | < 0.0001 | yes |
| EHE pooled simlog | 0.003 ± 0.023 | 0.752 | no | −0.075 ± 0.072 | 0.079 | no |
| Rejection rate (%) | −0.882 ± 0.462 | 0.013 | yes | −1.071 ± 1.060 | 0.087 | yes |
| Retry rate (%) | −8.727 ± 1.467 | 0.0002 | yes | −8.357 ± 3.823 | 0.008 | yes |

Exact permutation p is at the n=5 floor (0.0625) wherever all five signs
agree. The OLD-corpus contrast is cross-checked at runtime against r7's
`run_index_n5_published` rows (tolerance 5e-4; IBR ×3 and EHE all match).

## Read

The published flood story is the contrast, and it reproduces on the new
corpus with the same sign on every seed and a larger effect (unconditional
IBR gap 8.1 pp vs 6.5 pp). EHE does not differ between arms in either
corpus. What did not reproduce at the pre-registered tolerance is one
absolute level of the no-validator arm (tp_not_medium IBR), which is
reported above and will be disclosed in Methods/SI alongside the
irrigation and flood strict-arm band checks, all of which passed.

Review trail: r24 reviewed by the same sonnet code-reviewer as r23
(APPROVE; band arithmetic, seed-44 IBR, paired t and permutation p, r7
cross-check, md-vs-CSV 0 mismatches, deterministic re-run all verified).


# 2026-09-18 update — cross-model arm: gemma4:12b flood, both arms (code c3391a53)

Full tables: `out/r26_flood_crossmodel_gemma4_12b.md` (rendered by
`scripts/r26_flood_crossmodel_gemma4_12b.py` from the same rows as its
CSV). Runs: `examples/single_agent/results/JOH_{strict,disabled}_gemma4_12b_
c3391a53/Run_{42..46}`, `--workers 1`, `--thinking-mode disabled`,
`WAGF_LLM_TIMEOUT=1800`, Q4_K_M; launched 2026-09-17 12:08, strict done
20:14, disabled done 2026-09-18 04:15; about 1.6 h per run; every run
`llm_success==False` count 0; token and latency columns are measured at
this commit (about 920 prompt and 220 response tokens per call, 5.7 s per
call). Code c3391a53 was gated against faf1bb12 by the mock byte-identity
recipe for both domains (IDENTICAL after ignoring the five additive
telemetry columns).

## Model-paired comparison, gemma4:12b − gemma3:4b (same seed), n = 5

| arm | metric | Δ ± sd | p (paired t) | all 5 signs agree |
|---|---|---:|---:|:---:|
| strict | IBR unconditional (%) | −0.71 ± 0.45 | 0.024 | yes |
| strict | EHE pooled | −0.25 ± 0.03 | < 0.001 | yes |
| strict | rejection rate (%) | −0.80 ± 0.47 | 0.019 | yes |
| strict | retry rate (%) | −6.59 ± 1.16 | < 0.001 | yes |
| disabled | IBR unconditional (%) | −6.81 ± 1.30 | < 0.001 | yes |
| disabled | IBR tp_not_medium (%) | −14.73 ± 1.43 | < 0.001 | yes |
| disabled | EHE pooled | −0.32 ± 0.02 | < 0.001 | yes |

## Governed-vs-ungoverned contrast (ungoverned − governed), by model

| metric | gemma4:12b Δ ± sd (p) | gemma3:4b Δ ± sd (p) | same sign |
|---|---:|---:|:---:|
| IBR unconditional (%) | 2.02 ± 0.74 (0.004) | 8.12 ± 0.54 (< 0.001) | yes |
| IBR tp_not_medium (%) | 2.44 ± 0.85 (0.003) | 15.65 ± 0.65 (< 0.001) | yes |
| IBR tp_high (%) | 12.61 ± 6.04 (0.010) | 18.73 ± 2.18 (< 0.001) | yes |
| EHE pooled | −0.064 ± 0.028 (0.007) | 0.003 ± 0.023 (0.75) | no |
| rejection rate (%) | −0.08 ± 0.11 (0.18) | −0.88 ± 0.46 (0.013) | yes |
| retry rate (%) | −2.14 ± 0.40 (< 0.001) | −8.73 ± 1.47 (< 0.001) | yes |

## Read

The governance effect keeps its sign on the larger model for the three
IBR conditionings and the retry rate, with a smaller magnitude
(unconditional IBR gap 2.0 pp vs 8.1 pp). The reason is visible in the
arm levels: gemma4:12b commits few appraisal-inconsistent actions even
without a validator (ungoverned IBR 2.1 % vs 8.9 % on gemma3:4b), so the
validator has less to correct (strict-arm rejection 0.08 % vs 0.88 %).
gemma4:12b is also markedly less diverse: pooled EHE 0.61 (strict) and
0.54 (ungoverned) against 0.86 on gemma3:4b and 0.60 for the rule-based
baseline, and under gemma4:12b governance raises EHE slightly rather than
leaving it unchanged. Two of six contrast rows therefore change sign
across models (EHE, rejection rate); this is reported as found. Irrigation
gemma4:12b arms are running next (thinking disabled through the
`run_thinking_disabled.py` wrapper because the irrigation runners expose
no `--thinking-mode` flag; each run carries `think_request_log.jsonl` as
wire-level evidence).

Review trail: r26 reviewed by the same sonnet code-reviewer (APPROVE;
seed-44 strict and seed-42 disabled metrics recomputed, all paired stats
recomputed, 4b columns byte-equal to r23/r24, manifests read directly).
