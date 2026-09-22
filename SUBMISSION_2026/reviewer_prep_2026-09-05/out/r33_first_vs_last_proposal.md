# R33 -- first (initial) proposal vs last (negotiated) proposal

Source: `r33_first_vs_last_proposal.py`. Every number below is read live from the `rows` list this script writes to the paired CSV.

## Manifest census (target run)

model=gemma3:4b, git_commit=c3391a53..., thinking_mode=auto (value-enforced =='auto', confirmed against strict_42yr_gemma3_4b_faf1bb12_seed42's own manifest which also records 'auto'), llm_timeout_seconds_effective=600, model_quantization=Q4_K_M, model_digest=2026-01-29T12:50:07.405621-05:00, `initial_proposal_columns` key in reproducibility_manifest.json: False, in config_snapshot.yaml `global_config.audit.initial_proposal_columns`: True.

## Part 1 -- IBR headline, six ways (3 actions x 2 label sources)

| action | label source | numerator | denominator | rate (%) | note |
|---|---|---|---|---|---|
| initial_skill | initial | 779 | 1150 | 67.74 |  |
| initial_skill | final | 741 | 1089 | 68.04 |  |
| proposed_skill | initial | 493 | 1150 | 42.87 |  |
| proposed_skill | final | 359 | 1089 | 32.97 | published IBR headline definition |
| executed | initial | 35 | 1150 | 3.04 |  |
| executed | final | 14 | 1089 | 1.29 |  |

## Part 2 -- retry census

n_rows=3276, share with retry_count>0: 63.58%, mean attempts: 2.620, rows with empty initial_skill (first attempt unparsable): 0.

### Transition table: first attempt (initial_skill) -> last attempt

| first attempt \ last attempt | increase_large | increase_small | maintain_demand | decrease_small | decrease_large | UNPARSED |
|---|---|---|---|---|---|---|
| increase_large | 268 | 600 | 362 | 23 | 1 | 42 |
| increase_small | 86 | 341 | 255 | 21 | 4 | 17 |
| maintain_demand | 0 | 0 | 1106 | 0 | 0 | 0 |
| decrease_small | 10 | 23 | 53 | 50 | 2 | 0 |
| decrease_large | 2 | 1 | 3 | 2 | 4 | 0 |
| UNPARSED | 0 | 0 | 0 | 0 | 0 | 0 |

**Walk-back share:** of 779 rows whose first attempt was an increase under high first-attempt WSA, 321 (41.21%) ended (last attempt) as maintain/decrease.

## Part 3 -- faf1bb12 references (strict, ungoverned; last-proposal only)

| arm | action | label | numerator | denominator | rate (%) |
|---|---|---|---|---|---|
| strict_faf1bb12 | proposed_skill | final | 284 | 1066 | 26.64 |
| strict_faf1bb12 | executed | final | 16 | 1066 | 1.50 |
| ungoverned_faf1bb12 | proposed_skill | final | 1635 | 2756 | 59.33 |
| ungoverned_faf1bb12 | executed | final | 760 | 2756 | 27.58 |

## Part 5 -- preview at a different commit and thinking setting (SI only; NOT pooled with the c3391a53 run above)

`SUBMISSION_2026/TAE/runs/firstattempt_gov_seed{42..46}` -- an EARLIER pilot corpus, kept strictly separate from the primary c3391a53 target: 3 distinct git_commit values across the 5 seeds (seed 42 at `0237cb5f...`, seed 43 at `4b49bf46...`, seeds 44/45/46 at `bcee993f...` -- read from each seed's own manifest below, not one frozen commit) and thinking_mode `auto` (vs the target's `auto` too, but never value-enforced here -- this corpus's own manifests are only reported, not asserted against any expected value). Same six-way IBR / retry census / walk-back computation, independent code from Part 1/2 so a bug here cannot alter the target's own rows.

### Per-seed manifests

| seed | model | git_commit | thinking_mode |
|---|---|---|---|
| 42 | gemma3:4b | 0237cb5f... | auto |
| 43 | gemma3:4b | 4b49bf46... | auto |
| 44 | gemma3:4b | bcee993f... | auto |
| 45 | gemma3:4b | bcee993f... | auto |
| 46 | gemma3:4b | bcee993f... | auto |

### Six-way IBR, 5-seed mean +/- sd

| action | label source | n_seeds | rate mean +/- sd (%) |
|---|---|---|---|
| initial_skill | initial | 5 | 65.93 +/- 4.51 |
| initial_skill | final | 5 | 68.16 +/- 4.59 |
| proposed_skill | initial | 5 | 35.61 +/- 5.95 |
| proposed_skill | final | 5 | 32.19 +/- 6.80 |
| executed | initial | 5 | 4.68 +/- 1.42 |
| executed | final | 5 | 2.82 +/- 1.51 |

### Retry census and walk-back, 5-seed mean +/- sd

| metric | n_seeds | mean +/- sd |
|---|---|---|
| share_retried_pct | 5 | 60.923 +/- 3.287 |
| mean_attempts | 5 | 2.477 +/- 0.124 |
| walkback_rate_pct | 5 | 49.40 +/- 6.36 |

## Plain read

The agent's FIRST impulse (initial_skill under its own first-attempt WSA) scores an IBR of 67.74%; the NEGOTIATED result (published headline: last proposal under final WSA) scores 32.97% -- the gap between these two is what governance-plus-retry moved, on this single run.

The EXECUTED action's IBR (1.29%) vs the last-proposal IBR (32.97%) isolates whatever the executed-remap (REJECTED -> registry default) contributes beyond the validator's own retry pressure.

41.2% of first-attempt increases proposed under high first-attempt WSA were walked back to maintain/decrease by the last attempt -- direct evidence of negotiation, not just relabeling.

As an un-nudged reference (different commit, no first-attempt data), the faf1bb12 last-proposal IBR is strict_faf1bb12=26.6%; ungoverned_faf1bb12=59.3% -- ungoverned's higher rate shows what proposal-level coherence looks like with no validator pressure at any attempt.

## Method

`initial_skill`/`initial_labels`/`attempt_skills` are opt-in audit columns gated by `global_config.audit.initial_proposal_columns` (default OFF), added to close the `docs/AUDIT_SCHEMA.md` "Which Plane Answers What" table's documented gap ("Per-attempt retry sequence | no | no | accepted gap"). `initial_skill` = the FIRST attempt's proposal, captured before `_governance_retry_loop` overwrites `skill_proposal`; `initial_labels` = the first attempt's WSA/ACA labels, pipe-joined key=value; `attempt_skills` = every attempt's skill, pipe-joined, first-to-last, with `len(attempt_skills.split('|')) == retry_count+1` verified per row (raises otherwise), and `attempt_skills[-1] == proposed_skill` verified per row (raises otherwise) -- these are not assumed from `broker/tests/test_initial_proposal_columns_p0_1a.py`'s unit tests, they are re-checked against this run's own real data. The published IBR headline is exactly one of the six Part-1 rows: action=proposed_skill (last recorded proposal), label=final (`construct_WSA_LABEL`) -- `_loader.py::ibr()`'s own conditional-high-WSA-increase-rate formula, reimplemented here on audit rows (not simulation_log rows, since `proposed_skill`/`initial_skill` only exist in the audit) rather than imported, because `_loader.ibr()` itself operates on simulation_log's `yearly_decision`/`wsa_label`, a different pair of columns. This script cross-checks the two on every run it touches (`_crosscheck_published_ibr`, raises on disagreement): `final_skill` equals `yearly_decision` exactly and `proposed_skill` equals `final_skill` on all but a small unparsed-proposal share (empty `proposed_skill` on `REJECTED_FALLBACK` rows where the first attempt itself could not be parsed), so the audit-based and simulation_log-based computations agree to 1e-6 -- confirmed live, not assumed from the two columns' names sounding similar. faf1bb12 reference runs verified (raises otherwise) to lack `initial_skill` entirely, so only the two label=final combinations are computable there.
