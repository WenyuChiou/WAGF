# Paper readiness audit, 2026-09-22

Date: 2026-09-22 13:10
Code commit: 83fa97e1 (origin/main; the local `main` ref is stale)
Branch: p0-1-governance-instrumentation
Queue state: step [1] irrigation placebo seeds 42-43 running on the GPU; steps [2] no-ceiling ablation, [3a] flood initprop seeds 42-46, [3b] irrigation initprop seeds 43-44, [4] flood seeds 47-51, [5] paraphrase prompts all pending.

Coverage of this audit: all five planned dimensions are now covered (evidence consistency, reproducibility, claims and literature and venue, figures and docs, and code and CI health at 83fa97e1). The fifth was out of reach during the first pass, because the Codex delegate lane returned quota exhaustion three times and the Antigravity lane excludes honesty-critical verdicts by its own rules. It was run afterwards by a separate sonnet auditor; its result is the "Code and CI at 83fa97e1" section below, plus items M14 and M15. The assumption the first pass had to leave open, that the tree is green at 83fa97e1, now has evidence behind it.

Evidence base: the r-series memos under `SUBMISSION_2026/reviewer_prep_2026-09-05/out/`, `SUMMARY.md`, `SUBMISSION_2026/PAPER_CLAIM_CONSTRAINTS_2026-09-03.md`, the `SUBMISSION_2026/TAE/` state files, `ICLR2027/submission/`, and the on-disk results manifests. The untracked `out/r35*.md` through `out/r38*.md` files are pre-landing placeholders for the pending queue steps and were excluded as evidence.

---

## VERDICT

**NOT READY** for the framework methods paper (WRR-class), and **NOT READY** for the live archival target (ICLR 2027 main track, 25 September 2026 AoE, three days out). The TAE workshop submission is **MOOT**: `SUBMISSION_2026/TAE/DECISION.md` records that the organisers withdrew the workshop on 2026-08-05 over an AGU date-line conflict, so there is no TAE deadline to be ready for, only a folder whose other four state files still assert one.

The verdict rests on two things. First, the package quotes one corpus and stays silent about the other. The frozen corpus does reproduce the published point values, which is exactly what the r0 sanity gate checks. The regenerated fresh-seed set passes the pre-registered band check on all ten irrigation cells, under the heading `## Pre-registered acceptance (§0b): new 5-seed MEAN vs old ±2sd band — PASS on all 10` in `out/regen_progress_2026-09-15.md`, and it reproduces the governed-versus-ungoverned direction, which `out/r25_table1_regen.md` states as "Both cases reproduce the governed-vs-ungoverned direction on the new corpus: irrigation IBR headline mean_diff 23.02 pp old vs 25.23 pp new". What it does not give is the same point values: 31.41/56.64 against 36.05/59.07. The blocker is that the two machine-readable gate files a submission pipeline would read, `SUBMISSION_2026/TAE/manuscript_state.json` and `SUBMISSION_2026/TAE/NUMBERS.md`, quote the old point values with a CONFIRMED status and no staleness banner, so nothing on the page tells a reader which corpus produced them. Second, three headline claims are either unsupported or contradicted on the regenerated corpus: flood decision entropy, Lake Mead trajectory fidelity, and the claim that the coherence gain comes from the validator's specific rules.

---

## Blockers (confirmed): 6

### B1. `manuscript_state.json` declares READY_TO_SUBMIT on pre-regeneration numbers

What: the machine-readable submission-state file carries the pre-loss anchors with status CONFIRMED and a release status of READY_TO_SUBMIT, with no trace of the 2026-09-15 corpus loss and no record of the regenerated set. The blocker is that status and those unqualified anchors, not a failed reproduction. The frozen corpus still reproduces the published values, and the regenerated set passes the pre-registered band check on all ten irrigation cells; the file names neither corpus, so a pipeline reading it ships one set of numbers as though there were only one.

Evidence: `SUBMISSION_2026/TAE/manuscript_state.json` (`facts` -> `fact-anchor`) reads `"In gemma3:4b irrigation, HIGH prevalence Delta is +45.73 pp and conditional increase-rate Delta is +23.02 pp."` with `"status": "CONFIRMED"`; `facts` -> `fact-evidence` reads `"The evidence regeneration pipeline completes 15/15 scripts with exit code 0 on 2026-08-05."`, also CONFIRMED; `release.status` is `READY_TO_SUBMIT`. Against that, `out/r25_table1_regen.md` gives the regenerated irrigation contrast as `25.227 +/- 7.054`. `grep -c "2026-09" manuscript_state.json` returns 0.

Fix: set `release.status` to a non-ready value, flip the two `CONFIRMED` fact statuses to a stale marker, and add the 2026-09-15 loss plus the regenerated values (31.413 / 56.640, delta 25.227) as the current anchors. Do not delete the old values; mark them superseded so the provenance trail survives.

Who: script edit (sonnet), then Wenyu confirms the new release status wording.

### B2. `TAE/NUMBERS.md` carries the stale headline as current, with no banner

What: the file whose own contract is "if a number is in the manuscript and not in this table, it is unsourced and must not ship" now passes numbers that are 4.6 pp and 2.4 pp away from the regenerated corpus.

Evidence: `SUBMISSION_2026/TAE/NUMBERS.md` lines 143-144 and 163 give `36.05`, `59.07`, and `+23.02`. `out/r25_table1_regen.md` gives `36.052 +/- 3.597 / 31.413 +/- 5.474` and `59.070 +/- 1.659 / 56.640 +/- 2.099`. `grep -c "2026-09" NUMBERS.md` returns 0. By contrast `SUMMARY.md` does carry a loss banner, so NUMBERS.md is the one unguarded gate document.

Fix: add the same loss banner `SUMMARY.md` carries at the top of NUMBERS.md, and add a regenerated column beside every pre-loss cell rather than overwriting, so a reader can see both and the source of each.

Who: script edit (sonnet) for the mechanical column add; opus writing for the banner sentence.

### B3. The Lake Mead trajectory claim overclaims fidelity

What: stating that governed agents track the traditional model's Lake Mead trajectory (KGE 0.9456 governed against 0.2823 ungoverned) is not supportable, because the governed value sits inside a band with no signal in it: bounded above by the reference model's disagreement with itself and below by a null with no LLM at all.

Evidence: `out/r28_trajectory_vs_traditional.md` Part 1 reports that two runs of the same traditional FQL baseline already disagree at mead_elevation KGE = 0.98. `out/r29_kge_null_and_demand.md` reports that holding demand at its year-1 level for 42 years, with no LLM, yields a Mead-elevation KGE of 0.87 to 0.90. The governed arm's 0.9456 falls between 0.90 and 0.98.

Fix: delete every sentence of the form "the governed agents reproduce the traditional model's trajectory". Keep only the envelope reading: 0 of 5 governed seeds reach dead pool against 5 of 5 ungoverned seeds, Mead minimum 989.8 +/- 14.5 ft against 895.0 +/- 0.0 ft. Print the two bounds (0.98 self-disagreement, 0.87 to 0.90 no-LLM null) in the same table as the KGE number, so the reader sees the band.

Who: opus writing; the r28 upper bound (0.98) stands, the r29 lower bound (0.87 to 0.90) must first be re-run from the 83fa97e1 tree per M15. [envelope = demand-ceiling rule confirmed 2026-09-23, see Resolution log; rewrite still pending]

### B4. The flood decision-entropy claim is unsupported on the regenerated corpus

What: the flood EHE governance effect changes sign between the old and the new corpus and is not distinguishable from zero on the new one.

Evidence: `out/r25_table1_regen.md` contrast table: `flood | EHE pooled | old | -0.075 +/- 0.072 | 0.0785 | 0.1250 | False` against `new | 0.003 +/- 0.023 | 0.7521 | 0.9375 | False`. `SUMMARY.md` adds that the published p = 0.166 reproduces only as an unpaired two-sample t against the pre-quarantine arm, while the v50 Methods describe seed-level paired comparisons.

Fix: remove flood EHE from the claim set and from any table that presents it as a governance effect. If it is kept at all, it belongs in the SI as a null result with both corpora and both test forms printed. Step [4] is the only thing that could change this.

Who: opus writing now; GPU run (step [4]) before any attempt to revive the claim.

### B5. The rule-content claim is contradicted, not merely unevidenced

What: the claim that the coherence gain comes from the validator's specific rules is currently pointing the other way. The placebo control on flood says most of the measured value comes from the extra attempt existing at all.

Evidence: `out/r34_placebo_retry_flood.md`: "placebo sits close to STRICT on IBR (mean share 0.115, range -0.011 to 0.252, i.e. near 0) -- most of governance's measured value here looks like it comes from the EXTRA ATTEMPT existing at all ... not from the specific rule id/reason/suggestion". The same file states the limit itself: n = 2 seeds, no significance test computed, "suggestive, not statistically established".

Fix: reword every rule-content sentence to governance as a package, meaning validator plus rule-carrying retry, and state the placebo result in the paper rather than leaving it in the package. Wait for step [1] before deciding whether the flood result generalises.

Who: opus writing; GPU run (step [1]) decides the final wording.

### B6. The live archival deadline is three days out and the manuscript predates the corpus loss

What: `ICLR2027/submission/` was last written 2026-08-10/11, before the 2026-09-15 corpus loss and before every one of r23 through r34. Its abstract states numbers (82.80 / 37.08 percent, +45.73 pp) that no file in the reviewer-prep package re-derives on the regenerated corpus.

Evidence: file mtimes on `ICLR2027/submission/` are 2026-08-10/11; `ICLR2027/submission/paper/manuscript.tex` (abstract) states those values; `out/r18_restore_verification_2026-09-15.md` concludes "Every headline number in reviewer_prep_2026-09-05/out/*.csv is currently unverifiable against the restored corpora", and regeneration has since landed only for flood strict (r23) and Table 1 (r25).

Fix: either re-derive the six numbers of the Table 1 anchor row, which the abstract repeats, on the regenerated corpus and update the manuscript, or do not submit on 25 September. This is a decision, not an edit: the re-derivation is a day of work at best and the three claim blockers above land in the same manuscript.

Who: Wenyu decision first (submit or skip); then sonnet script for the re-derivation and opus writing for the abstract.

---

## Major items (confirmed): 15

### M1. The irrigation headline sentence names one corpus and is silent about the other

Evidence: `SUMMARY.md` states "**Sanity gate (r0): PASS.** Irrigation headline IBR reproduces to 36.05 % governed (sd 3.60) and 59.07 % no-validator (sd 1.66)". That is true of the frozen corpus, and r0 does reproduce it; the sentence simply never says which corpus it holds for. The regenerated fresh-seed set gives a different pair, `31.413 +/- 5.474` and `56.640 +/- 2.099` (`out/r25_table1_regen.md`), while passing the pre-registered band check on all ten irrigation cells. Fix: name the frozen corpus in that sentence and print the regenerated pair beside it together with the band-check result, so both numbers and both sources are on the page. Who: opus writing.

### M2. The ungoverned-demand multiplier is two different numbers and neither reproduces from r29

Evidence: `out/r32_contribution_stress_test_2026-09-21.md` says "demand approximately 2.3x allocation"; `out/regen_progress_2026-09-15.md` says "about twice the ceiling". `out/r29_kge_null_and_demand.md` Part (b) gives ungoverned mean 11,761,867 +/- 196,654 AF against `DEMAND_CEILING_AF` = 6,000,000 AF, which is 1.96x, or 2.01x against the CRSS target 5.86 MAF. The value 2.3x reproduces only from the maximum 13,508,008 AF, and no document says so. Fix: pick one denominator, state it in the sentence, and use 1.96x (mean against ceiling). Who: opus writing, one sentence.

### M3. `PAPER_CLAIM_CONSTRAINTS` blesses a flood number its own package says came from a quarantined arm

Evidence: `SUBMISSION_2026/PAPER_CLAIM_CONSTRAINTS_2026-09-03.md` section 1 says "The published NW pair (irrigation 36.05 / 59.07, flood 0.87 / 8.53) is reproduced from the frozen corpus by reproduction/". `SUMMARY.md` says "The published 8.5 reproduces only from the PRE-QUARANTINE no-validator arm (quarantined Run_1-3 + live Run_4-5). The live corpus gives 7.41". Project memory `reference_flood_ibr_denominator_2026-08-20` records 0.87/7.41 as canonical, so the constraints ledger is the outlier. Fix: correct section 1 of the constraints file to 0.87/7.41 and add the quarantine sentence. Who: script edit (sonnet) with opus reviewing the wording.

### M4. The flood IBR number has three candidate values and needs its provenance sentence attached

Evidence: published 8.53, live corpus 7.41, regenerated 8.912 (`out/r25_table1_regen.md`). The regenerated value is nearer the published one than the live pre-loss value was. Fix: quote the regenerated 8.912 as primary, with a single sentence naming all three and the corpus each comes from. Who: opus writing.

### M5. The flood arms sit far outside empirical adaptation base rates, including the rule-based control

Evidence: `out/r28_trajectory_vs_traditional.md` Part 2 gives relocation share 15.72 +/- 4.02 percent governed, 13.82 +/- 7.19 percent no-validator, 0.30 +/- 0.33 percent rule-based. `SUMMARY.md` row 10: "Elevation rate 0.986 / 0.996 / 0.887 (governed / no-validator / rule-based) against empirical ranges 0.03-0.12 (table A) and 0.10-0.35 (table B) | Every arm is far outside both". `out/r25_table1_regen.md` gives flood governed final-year protection 100.000 +/- 0.000 percent. Fix: state plainly that the flood testbed is not calibrated to adaptation base rates, in the Methods and again in the Limitations, rather than letting a reviewer find it. Who: opus writing.

### M6. The first-attempt result is single-seed and single-commit, printed next to a five-seed headline from a different commit

Evidence: `out/r33_first_vs_last_proposal.md` gives initial_skill 67.74 percent and proposed_skill final 32.97 percent at commit c3391a53, while the corpus used in r25, r27, r30 and r34 is faf1bb12, where the same cell is 26.64 percent. The five-seed Part 5 pilot is fenced as "SI only; NOT pooled" and spans three commits. Fix: do not print 67.74 against 32.97 as a headline until step [3b] lands. If it must be mentioned now, print it as one seed at one commit with both ratios (2.05x and 2.54x) and say which corpus each uses. Who: GPU run (step [3b]), then opus writing. [single-seed half closed 2026-09-23, see Resolution log]

### M7. The cross-model transfer claim risks reading as a scale law from two points, one of which saturates

Evidence: `out/r25_table1_regen.md` gemma4:12b block gives irrigation governed IBR `0.000 +/- 0.000` with retry rate `73.571 +/- 2.532`. Fix: word it as an observation between two models, not a trend, and state the saturation explicitly, because a floor of exactly zero is a definitional ceiling and a reviewer will read it as one. Who: opus writing.

### M8. Moving to an archival venue removes the reproducibility waiver the package's status relied on

Evidence: `SUBMISSION_2026/TAE/DECISION.md`: "the RED-reproducibility waiver rests on TAE being non-archival ... that waiver does not transfer to an archival venue". `out/r18_restore_verification_2026-09-15.md` concludes the headline numbers are unverifiable against the restored corpora, and regeneration has landed only for flood strict and Table 1. Fix: finish the regeneration sweep for every number the manuscript prints, or submit somewhere the waiver still holds. Who: Wenyu decision, then sonnet script for the remaining regeneration.

### M9. The regeneration command list in the reviewer-prep README stops at r16

Evidence: `grep -n "r17_\|r21_\|r25_\|r27_\|r28_\|r33_" SUBMISSION_2026/reviewer_prep_2026-09-05/README.md` returns nothing. 34 scripts exist on disk (r0 through r38 with gaps); the README documents 17 of them, and the undocumented 18 include `r25_table1_regen.py`, which produces the paper's main table. Fix: extend the "How to regenerate everything" block to r17 through r34 in run order. Who: script edit (sonnet). Note that all four scripts spot-checked (r25, r27, r28, r33) regenerate byte-identical output, so the scripts themselves are sound; only the instructions are missing.

### M10. `SUBMISSION_2026/INDEX.md` describes the reviewer-prep package as stopping at r10

Evidence: `INDEX.md` reads "reviewer_prep_2026-09-05/ | Pre-computed answers (r0–r10 scripts + CSVs) to the questions a water-journal reviewer will ask..."; a grep for r2[5-9] or r3[0-9] on that file returns nothing, while the five most recent repo commits are titled r28, r32, r33 and r34. Fix: update the one-line description and the date stamp. Who: script edit (sonnet).

### M11. `initial_proposal_columns` is a shipped, tested feature with no documentation anywhere

Evidence: greps for `initial_proposal_columns` on `CHANGELOG.md`, `ARCHITECTURE.md`, `broker/INVARIANTS.md` and `docs/` return nothing, and the `[Unreleased]` section of `CHANGELOG.md` is empty. The feature exists in `broker/core/_retry_loop.py`, `broker/core/_audit_helpers.py`, `broker/components/analytics/audit.py` and `broker/core/skill_broker_engine.py`, with a dedicated test at `broker/tests/test_initial_proposal_columns_p0_1a.py`. Fix: add a CHANGELOG `[Unreleased]` entry and one paragraph in `ARCHITECTURE.md`. This matters for the paper because r33's first-attempt analysis depends on it and a reviewer following the repo cannot learn it exists. Who: script edit (sonnet), opus reviews the paragraph.

### M12. The literature gap is partly a gap against the group's own prior paper, with no stated delta

Evidence: `.research/lit_sweep_2026-09-17/D_positioning_synthesis.md` lists "A5/C1-1 | Yang & Chiou 2026 (self-authored, this group) | Water Resources Research" as one of the five closed-loop works establishing the gap. No sentence states what this paper adds beyond it. Fix: write the delta explicitly, in the third person for a double-blind venue. Who: opus writing, then Wenyu confirms the delta is the one he wants to claim.

### M13. Four TAE state files still assert a withdrawn venue

Evidence: `TAE/DECISION.md` records the withdrawal on 2026-08-05 and the move to ICLR 2027 (deadline 25 September 2026 AoE), while `TAE/STATUS.md`, `TAE/BOUNDARY.md`, `TAE/PLAN.md` and `TAE/SUBMISSION_READINESS.md` all still name the NeurIPS 2026 TAE workshop and the 29 August 2026 deadline, all written between 2026-07-31 and 2026-08-03, before the 2026-08-05 withdrawal (`grep -n "NeurIPS" SUBMISSION_2026/TAE/STATUS.md`, and the same grep against the other three). All four do already carry a generic banner, "Entry point is HANDOVER.md ... status claims go stale", but it names no venue and no withdrawal, so a reader who heeds it still comes away with NeurIPS TAE as the target and 29 August as the date. The fix stands. Fix: add the DECISION.md withdrawal banner to the top of all four. Who: script edit (sonnet).

### M14. `INVARIANTS.md` cites three guard-test names that do not exist

Evidence: `test_audit_no_hardcoded_sentinels_leak` (cited for Invariant 2), `test_dormant_field_policy` (cited for Invariants 2 and 4) and `test_parallel_api_consistency` (cited for Invariant 3) occur only inside `broker/INVARIANTS.md` itself; `grep -rn "test_audit_no_hardcoded_sentinels_leak" broker/` returns the document and no test. The guards that exist and do run are the classes `TestAuditSentinelDetection`, `TestDormantFieldPolicy` and `TestParallelAPIConsistency` in `broker/tests/test_framework_invariants.py`, alongside `test_audit_aggregate_keys_have_upstream_writers` for the dormant-field half of Invariant 4. Invariants 1, 5 and 6 cite correctly (`TestMemoryTypeContract`, `TestDomainGenericity` plus `tests/test_domain_genericity.py`, `TestRunIntegrityContract`), so this is three broken citations in a document whose whole purpose is to point at the guard that enforces each contract. Fix: cite the class names. Who: sonnet script.

### M15. Runs and evidence live on different branches and nothing in the package says so

Evidence: `p0-1-governance-instrumentation` and `origin/main` share merge-base 3cb67302 (2026-07-21). p0-1 holds 99 commits main lacks; main holds 61 p0-1 lacks. p0-1's own `broker/` commits are dated 2026-07-29 to 2026-08-20, for example 2a1d889b "feat(governance): make the retry-exhaustion fallback a domain policy" and c10411b0 "fix(broker): five silent-failure paths in the framework core". Every one of them precedes the stacked-PR series that ported the framework to main, which opens with PR #26 `stack/pr1-docs-truth`, merged 2026-09-03 as 95453fcf. So p0-1's `broker/` is the pre-port snapshot of the same work, not a rival implementation, and the large two-way diff is mostly that ordering rather than disagreement. There are no open PRs.

The paper-relevant risk is provenance, not conflict. Every experiment run was executed from the `wagf-main-runs` worktree at 83fa97e1, which is main, while the evidence package, meaning the r-series scripts and their memos, exists only on p0-1. A reader handed either branch alone cannot reconstruct the other half, and no file states the split.

One concrete check decides whether the split also touches a result. Of the r-series scripts only `r29_kge_null_and_demand.py` imports domain code (`examples.irrigation_abm.irrigation_env`, `.validators.irrigation_validators`, `.irrigation_personas`) from whatever tree it runs in, so it is the one script whose output depends on the branch it ran on. `git diff --stat origin/main..HEAD` over those three modules is not empty: `examples/irrigation_abm/irrigation_env.py` differs by 9 added and 239 removed lines, and `examples/irrigation_abm/irrigation_personas.py` by 3 added and 2 removed. Only `examples/irrigation_abm/validators/irrigation_validators.py` is byte-identical on both branches. r29's no-LLM null replay must therefore be re-run from the 83fa97e1 tree before it is cited, which matters directly for B3, where r29's 0.87 to 0.90 Mead-elevation bound is load-bearing.

Fix: one paragraph in `SUBMISSION_2026/README.md` stating that runs come from main at 83fa97e1 through the `wagf-main-runs` worktree, that analysis and memos live on p0-1, and what the r29 parity check found. Who: sonnet script.

---

## Minor and docs items: 12

- `out/r32_contribution_stress_test_2026-09-21.md` cites a governed-demand maximum of 6.071 MAF from the old corpus in a paragraph otherwise computed on the new one, whose maximum is 6.184 MAF (`out/r29_kge_null_and_demand.md`, irrigation_strict_gemma3_4b).
- The retry multiplier is not comparable across r27 (mean retry_count 2.49 over retried rows) and r33 (mean attempts 2.620), because the denominators are never stated; the two reconcile only if r33's mean is over all rows.
- Claim 5 (governed agents do not track the demand trajectory: basin-demand KGE 0.1825 +/- 0.2094 and -0.0600 +/- 0.3063 against an FQL-vs-FQL floor of 0.3802) must appear in the same table as the Mead KGE claim, or the Mead claim becomes an overclaim by omission.
- `out/r27_irrigation_crossmodel_gemma4_12b.md` reports a pooled audit-derived IBR (31.512 / 56.680) while r25 and r30 report a per-seed mean (31.41 +/- 5.47 / 56.64 +/- 2.10); the relationship is never stated in one sentence, and a rounded Table 1 caption could turn the 0.1 pp difference into an apparent mismatch.
- The untracked `out/r35*.md` through `out/r38*.md` placeholders are formatted exactly like landed evidence and all four still contain PENDING table rows; move them out of `out/` until their runs land. Nothing cites them today.
- `.research/lit_sweep_2026-09-17/D_positioning_synthesis.md` contains 39 em-dashes and r32 contains 1, against the paper's own style rule; `manuscript.tex` has 0, so the risk is copying working-file text into prose.
- The gap sentence should use the words "not reported", not "not stated" or "not done", and should say the column was judged from abstracts.
- `paper/nature_water/scripts/gen_fig2_case1_irrigation.py` (`draw_stacked_panel`) duplicates the live regen script's FQL-as-line logic under the older output name `Fig2_irrigation_case`, outside `_retired/`.
- The uncommitted change to `examples/irrigation_abm/results/README.md` is line-ending noise, not content (`git diff --numstat` reports no changed lines); do not commit it as a substantive change.
- `--ablation-mode` is not recorded by `broker/core/experiment_runner.py` (`_collect_reproducibility_metadata`), so a reader cannot tell from a manifest alone which ablation was active. Info-level for the paper, but worth closing before the ablation runs in step [2] land.
- The "no provenance box on canvas" rule has one exception: `paper/nature_water/scripts/regen/gen_fig2_regen.py` (`draw_pending_stamp`) draws `DATA_COMMIT` on the panel, but only when an arm's data is missing. Confirm no shipped panel is in that state at the next regeneration.
- All faf1bb12 and c3391a53 results directories cited in r25 and regen_progress exist with matching manifests, seed counts are complete for every stated n, and all four spot-checked analysis scripts regenerate byte-identical output. This is the part of the package that is in good shape.

---

## Code and CI at 83fa97e1

This dimension was run after the four above, by a separate sonnet auditor, on the p0-1 working tree unless stated otherwise.

**CI.** GitHub Actions run 35687506025 has headSha `83fa97e1d3200ca85cb5710eeb76c40ff70871fb`, which is the commit this audit is written against, and its conclusion is success. Four jobs ran and all four succeeded: `test (3.12)`, `test (3.11)`, `test (3.10)` and `scaffold-smoke`. The run is titled "Merge pull request #46 from WenyuChiou/feat/placebo-retry-feedback".

**Version trio.** `pyproject.toml` reads `version = "0.6.0"` and `broker/__init__.py` reads `__version__ = "0.6.0"`. The literal top heading of `CHANGELOG.md` is `## [Unreleased]` and the newest released heading is `## [0.6.0] - 2026-06-10`; `broker/tests/test_version_consistency.py` (`test_version_trio_agrees`) skips `[Unreleased]` by design, so the trio agrees and the test passes. The `[Unreleased]` entry is not empty: it opens "**Retry-feedback ablation for red-team objection 3 (default OFF)**: `global_config.governance.retry_feedback_mode: full | placebo`", which is the switch r34 and pending step [1] exercise. That corrects one aside inside M11; M11's own point, that `initial_proposal_columns` appears nowhere in the changelog, still holds (`grep -c "initial_proposal_columns" CHANGELOG.md` returns 0).

**Water-token leak.** None genuine. The nine highest-hit generic files were sampled (`broker/core/agent_initializer.py`, `broker/tools/validate_prompt.py`, `broker/components/social/config.py`, `broker/utils/agent_config.py`, `broker/domains/protocol.py`, `broker/components/cognitive/reflection.py`, `broker/interfaces/coordination.py`, `broker/memory/strategies/symbolic.py`, `broker/components/context/providers.py`) and every hit is docstring, comment or example prose except one: `broker/interfaces/coordination.py` (`AgentCategory`) has executable value-aliases `INDIVIDUAL = "household"` and `HOUSEHOLD = "household"`, documented in place as intentional paper-3 wire compatibility, which matches the Phase 6U note in `CLAUDE.md`. Two limits on this finding: `broker/tests/` holds 1286 hits across 75 files and was not itemised, and roughly 50 generic files outside `broker/domains/` were not exhaustively classified.

**Invariant guard tests.** `broker/tests/test_framework_invariants.py` together with `tests/test_domain_genericity.py` gives 53 passed and 1 skipped in 2.07s, and `broker/tests/test_version_consistency.py` gives 2 passed. Both were run in the foreground on the p0-1 working tree, not on main, so they are evidence about p0-1; for main the evidence is origin/main's own CI run above. Three of the six guard-test names cited in `broker/INVARIANTS.md` do not exist, which is M14.

**Frozen files.** The four files the package treats as frozen were last touched well before the experiment campaign: `examples/multi_agent/flood/config/prompts/government.txt` and `insurance.txt` at 2b90e33a, 2026-03-13, "feat(flood): hybrid institutional agents"; `examples/multi_agent/flood/config/ma_agent_types.yaml` at 83005616, 2026-05-27, the v0.5.0 release; `examples/multi_agent/flood/config/skill_registry.yaml` at 79cf8358, 2026-04-03. Nothing in the 2026-09 campaign moved them.

**Manifest coverage.** `broker/core/experiment_runner.py` (`_collect_reproducibility_metadata`) does record `retry_feedback_mode`, in its own block labelled "3b" with its own try/except, and it records governance strictness as `governance_profile_resolved`. It does not record the `--ablation-mode no_demand_ceiling` flag that pending step [2] uses; the string "ablation" appears in that function only in comments. The minor item below about `--ablation-mode` therefore stands unchanged: the auditor's "not a gap" remark covers the governance profile, not the ceiling flag. Until the flag is recorded, step [2] is verifiable only the way r36 does it, from `LAUNCH_COMMAND.txt` plus a zero count of ceiling-rule fires, not from the manifest alone.

---

## What the pending queue steps can change

**Step [1], irrigation placebo, seeds 42-43, running.** Touches B5 (rule-content claim) and bounds the coherence claim. Decision rule: if the irrigation placebo arm's IBR sits within about 1 pp of the strict arm, as it does on flood, the rule-content claim is dead in both domains and every sentence becomes "validator plus rule-carrying retry as a package", including in the abstract. If the irrigation placebo is clearly worse than strict, with the same sign on both seeds and a gap wider than the between-seed spread, then rule content matters in irrigation but not in flood, the claim becomes domain-dependent, and the two-domain transfer claim (M7) weakens in the same move. Either way n = 2 supports a direction, not a test.

**Step [2], no-ceiling ablation.** Touches the envelope claim and B3. Decision rule: if removing the demand ceiling rule sends governed seeds to dead pool, the envelope is one institutional ceiling rule and the claim must be restated as such, not as governance in general. If the envelope survives without the ceiling, the claim generalises and B3's envelope-only fallback becomes strong rather than a retreat. Given that `PAPER_CLAIM_CONSTRAINTS` already records the ceiling rule as triggering about 80 percent of rejections, plan the prose for the first outcome.

**Step [3a] flood initprop seeds 42-46 and [3b] irrigation initprop seeds 43-44.** Touch M6. Decision rule: if the five-seed first-attempt IBR mean exceeds the last-proposal mean by more than the pooled standard deviation, "negotiation, not relabelling" holds at n = 5 on one corpus and can be printed as a headline. If the gap falls inside one standard deviation, drop the claim and keep only the walk-back rate (41.21 percent of high-WSA first attempts ended as maintain or decrease), which is descriptive and does not need the contrast.

**Step [4], flood seeds 47-51 (n = 10).** Touches B4 and M4. This is the only pending step that can lift a flood contrast off the n = 5 exact-permutation floor of 0.0625. Decision rule: if flood IBR keeps its sign across all ten seeds, quote it with a permutation p below 0.01 and the claim is safe. For EHE, the claim returns only if the sign becomes consistent across ten seeds under the paired test the Methods describe; a second null at n = 10 retires it permanently rather than leaving it open.

**Step [5], paraphrase prompts.** Touches every effect size rather than one claim. Decision rule: if the governed-minus-ungoverned contrast moves by less than one between-seed standard deviation under paraphrase, report the effects as prompt-robust and say so in one sentence. If it moves more, every effect size in the paper becomes specific to one prompt, that has to be stated in the Limitations, and the transfer claim (M7) weakens a second time.

---

## Refuted findings, so nobody re-raises them

- "Two different seed-42 strict irrigation proposal-level IBR values, 32.97 and 26.64, sit in the same document without a stated pairing rule." Refuted: the two percentages come from clearly separate, labelled sections at named commits and are never paired as claimed. The real issue is the one recorded as M6, which is about which commit the headline uses, not about an ambiguous pairing.
- "Any sentence claiming the effect of pre-execution validation has not been measured is refutable by entry B1, which already measured it with better numbers." Refuted: no such sentence exists in the shipped manuscript, and the manuscript's actual novelty claim is the narrower one about conditional-scoring contamination. B1 remains worth citing, but it does not contradict anything the paper says.

---

## Checklist to reach READY

1. Decide submit or skip for ICLR 2027 on 25 September, given that three claim blockers and six unverified abstract numbers stand between here and a defensible manuscript. **Wenyu decision.** Everything below assumes the answer is "skip 25 September and target the next archival date", because items 2 through 6 cannot honestly be finished in three days. [moot after pause]
2. Add the 2026-09-15 loss banner and the regenerated values to `TAE/NUMBERS.md` and flip `manuscript_state.json` off READY_TO_SUBMIT. **Sonnet script**, opus reviews the wording. Closes B1 and B2. [status half closed 2026-09-22, see Resolution log]
3. Correct section 1 of `PAPER_CLAIM_CONSTRAINTS_2026-09-03.md` to the canonical flood pair 0.87/7.41 with the quarantine sentence. **Sonnet script.** Closes M3. [closed 2026-09-22, see Resolution log]
4. Rewrite the Mead trajectory claim to the envelope reading, with the 0.98 self-disagreement and the 0.87 to 0.90 no-LLM null printed in the same table. **Opus writing.** Closes B3.
5. Remove flood EHE from the claim set and the tables. **Opus writing.** Closes B4 pending step [4].
6. Reword every rule-content sentence to governance as a package and put the flood placebo result into the paper. **Opus writing**, after step [1] lands. Closes B5.
7. Let steps [1] and [2] finish on the GPU, then apply the two decision rules above. **GPU run**, then opus writing.
8. Run steps [3a], [3b] and [4]. **GPU run.** Unblocks M6 and gives flood its first chance at a permutation p below the n = 5 floor. [3a and 3b landed 2026-09-23; step 4 still running]
9. Re-derive the full Table 1 anchor row (37.08 / 82.80 / +45.73 / 0.86 / 26.77 / +25.90 in `ICLR2027/submission/paper/manuscript.tex`; `grep -n "gemma3:4b & 5" ICLR2027/submission/paper/manuscript.tex`) on the regenerated corpus, and update both that row and the abstract sentences that repeat its numbers. **Sonnet script** for the derivation, **opus writing** for the abstract. Closes B6 and M8. [moot after pause]
10. Fix the package's own navigation: extend the README regeneration list to r34, update the `SUBMISSION_2026/INDEX.md` description, banner the four stale TAE state files, and move the r35 through r38 placeholders out of `out/`. **Sonnet script.** Closes M9, M10, M13 and one minor item. [closed 2026-09-22, see Resolution log]
11. Document `initial_proposal_columns` in CHANGELOG and ARCHITECTURE, and in the same pass replace the three non-existent guard-test names in `broker/INVARIANTS.md` with the class names that actually run. **Sonnet script**, opus reviews. Closes M11 and M14. [closed 2026-09-22, see Resolution log]
12. Add the branch-provenance paragraph to `SUBMISSION_2026/README.md`, naming main at 83fa97e1 through the `wagf-main-runs` worktree for runs and p0-1 for analysis, and re-run r29's null replay from the 83fa97e1 tree before B3 cites its bound. **Sonnet script.** Closes M15. [closed 2026-09-22, see Resolution log]
13. Write the delta against the group's own WRR paper, in the third person. **Opus writing**, **Wenyu decision** on what the delta is. Closes M12.
14. Sweep the minor items: one denominator for the demand multiplier, the retry-denominator sentence, the demand-KGE counterweight row, the pooled-versus-mean sentence, the em-dashes in working files, and the "not reported" wording. **Opus writing.**
15. Run step [5] and add the prompt-robustness sentence the result licenses. **GPU run**, then opus writing.

---

## Resolution log (2026-09-22 to 2026-09-23)

1. **M15, r29 half.** I copied `_common.py` and `r29_kge_null_and_demand.py` into a scratch directory and edited only those copies, never a tracked file. In the copy of `scripts/r29_kge_null_and_demand.py` (the `examples.irrigation_abm.irrigation_env` import), the single `sys.path.insert(0, C.REPO)` call that precedes that import was changed to insert the `wagf-main-runs` worktree path (origin/main at 83fa97e1) instead, and `_common.py`'s `OUT` was redirected to scratch so nothing wrote back into the repo. A standalone import check printed `irrigation_env.__file__` resolving under `wagf-main-runs`, and two full runs, about 3 seconds each, came out byte-identical to each other and to the committed `out/r29_kge_null_and_demand.md` (SHA-256 `4c13d8b80135277d38afc804f6a58dfd4e943fc454eed70701d224965e8a093e`) and `.csv` (SHA-256 `c9c591f574086570ab8fc17282656f91dbfbd64f2aee0189dd4f29fb238f4a71`); every number matched the committed file, null KGE fql_matched 0.8720 +/- 0.0110, governed 0.9033 +/- 0.0116, replay-fidelity RMSE 0.0000 ft on 10 of 10 (source, seed) pairs, ungoverned demand mean 11,761,867 AF. The reason is structural: r29 never calls `execute_skill()`, the only method that consumes the environment's own rng, and the p0-1 tree's 239-line reduction does not touch the `WaterSystemConfig`/`IrrigationEnvironment` methods r29 exercises, so B3's 0.87 to 0.90 lower bound stands and M15's r29 half is closed.

2. **M15, documentation half.** `SUBMISSION_2026/README.md` (the new Provenance section) now states that runs execute from the `wagf-main-runs` worktree at main commit 83fa97e1, that results reach this clone only through junctions into `examples/*/results/`, and that analysis lives only on branch p0-1. It names `r29_kge_null_and_demand.py` as the one r-series script that imports domain code directly, records that it was re-run with the `examples.*` imports resolved from the 83fa97e1 worktree, and points at this Resolution log for the SHA-256 values. That paragraph is committed together with this Resolution log in the same commit, which closes the documentation half of M15.

3. **M13 and the B1 status half.** Commit b74dd166 closes both. It adds an identical three-line withdrawal-plus-pause blockquote under the HANDOVER banner to `TAE/STATUS.md`, `TAE/BOUNDARY.md`, `TAE/PLAN.md` and `TAE/SUBMISSION_READINESS.md`, and a PAUSED banner to `TAE/DECISION.md`, closing M13; it also flips `TAE/manuscript_state.json` (`release.status`) from READY_TO_SUBMIT to PAUSED_2026-09-22 with a status_note pointing at this audit, closing the status half of B1. The anchors half of B1, the pre-loss fact values still marked CONFIRMED, stays open; the commit message says so explicitly.

4. **B2 (banner scope), M3, M9, M10, M11, M14.** Commit 4943cca6 closes four items: it adds a DATA STATUS banner to `TAE/NUMBERS.md` (closing B2 as scoped after the pause, banner only, no column rebuild), corrects the flood pair in `PAPER_CLAIM_CONSTRAINTS_2026-09-03.md` section 1 from 0.87/8.53 to 0.87/7.41 with the SUMMARY.md quarantine sentence quoted verbatim (closing M3), extends the reviewer-prep README's regeneration list through r34 (closing M9), and updates the `SUBMISSION_2026/INDEX.md` reviewer_prep row to r0 through r34 landed, r35 through r38 pending (closing M10). PR #47, merged as c9357ebc, closes the remaining two: it adds a `CHANGELOG.md` (`[Unreleased]`) entry and an `ARCHITECTURE.md` paragraph documenting `initial_proposal_columns`, closing M11, and replaces the three non-existent guard-test names in `broker/INVARIANTS.md` with the class names that actually run, closing M14.

5. **B6 and M8.** Both are moot. `TAE/DECISION.md` (the PAUSED banner added by b74dd166) records the author's 2026-09-22 decision to pause every top-conference submission, including the ICLR 2027 main track that B6 and M8 were about, so re-deriving the Table 1 anchor row for a 25 September deadline and finishing the reproducibility sweep that only mattered for TAE's waiver are no longer live requirements. Both items remain correct as written, in case a future archival deadline reopens them.

6. **Step [1] and B5.** Step [1] landed on 2026-09-22. The regenerated `out/r35_placebo_retry_irrigation.md` corrects its verdict to the same non-degenerate-cells-only rule `r34_placebo_retry_flood.py` introduced, and now reads placebo close to UNGOVERNED on IBR (mean share 0.962, range 0.934 to 0.990), with a new Part 4b splitting the result by proposal level versus executed level. That flips B5's reading from single-domain to domain-dependent: in irrigation the rule text in the retry prompt is what moves the agent's last recorded proposal and blocking alone protects the executed outcome, while in flood the placebo tracked STRICT on IBR (r34). The file is untracked, so this entry is pending review and commit, not yet closed.

7. **Step [2] (r36), landed 2026-09-23, commit 086c673a.** Both no-ceiling seeds reach the 895.0 ft Mead floor (strict 997.0 / 995.7), shortage years are 35 / 35, and IBR headline stays at the strict level (27.15 / 26.78). Decision-rule branch 1 holds: B3's envelope reading must name the demand-ceiling rule. B3's Who line now carries the status note above.

8. **Steps [3a] and [3b] (r41), landed 2026-09-23, commit 9a83b169.** Flood n = 5: first-attempt IBR 9.03 percent, last proposal 0.50, executed 0.50, walk-back 63.00 percent, gate MET, permutation p 0.0625. Irrigation n = 3 (seed 42 at c3391a53, seeds 43 and 44 at 83fa97e1): first-attempt 65.47 percent, last proposal 30.03, executed 1.18, gate MET, permutation p 0.2500. M6's single-seed half is closed; the commit mix stays stated as recorded above.

**Sampling parameters (2026-09-23).** Flood sends temperature 0.8 / top_p 0.9 / top_k 40 from its per-type llm block; irrigation sends none, so the gemma3:4b modelfile defaults (temperature 1 / top_p 0.95 / top_k 64) apply; no Ollama seed is sent. Manifests recorded null for both (r19 G7); fixed on branch fix/manifest-resolved-llm-params (PR pending). Methods must state the per-domain settings; corpus unchanged.
