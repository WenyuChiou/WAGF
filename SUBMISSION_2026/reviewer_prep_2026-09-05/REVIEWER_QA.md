# Anticipated reviewer questions — framework paper (follow-up to Yang, WRR 2026, 10.1029/2025WR042111)

> **Written before the 2026-09-15 corpus loss.** Every number below is a
> frozen-corpus value computed 2026-09-05...09-10; the underlying corpora
> were lost 2026-09-15 and have since been partially regenerated. Regenerated
> values are in `out/r25_table1_regen.md`. Item E3 and the "What the paper
> can claim safely" list below are pending re-derivation against the
> regenerated corpus.

Referees assumed: socio-hydrology / water resources (WRR, EM&S, HESS).

**IBR (appraisal–action inconsistency rate)** — share of decisions where the requested action
contradicts the appraisal written in the same answer. Irrigation: asking for more water while
labelling scarcity High or Very High. Flood: rules R1 + R3 + R4, R5 excluded per Extended Data
Table 2. **EHE (action-distribution entropy)** — entropy of a run's pooled action counts over
log2(number of skills); 0 = one action always, 1 = all equally often; pooled once per run.

Numbers carry their table (r0–r9 in `out/`), ledger row
(`PAPER_CLAIM_CONSTRAINTS_2026-09-03.md`), or "verified 2026-09-05" for the independent
recomputation. **UNRESOLVED** marks anything matching no computed cell or reproducing only from the
pre-quarantine arm: flood 0.9 / 8.5 and 0.87 / 8.53, flood EHE 0.815 and its p = 0.166, irrigation
EHE 0.687 / 0.848 as printed.

---

## A. Contribution and delimitation

**A1. What does this add beyond your group's WRR 2026 LLM-ABM flood paper?**
- Evidence: r1 — governed Lake Mead minimum 989.8 ± 14.5 ft, 0 of 5 seeds at dead pool;
  no-validator 895.0 ± 0.0 ft, 5 of 5, first crossing year 17–18. r3 — six named ERROR rules,
  `demand_ceiling_stabilizer` on 52.6 % of governed rows.
- Answer: three things WRR 2026 lacked — a hard-rule layer that refuses a proposal on physical
  feasibility and logs it, a theory-derived soft-rule layer checking the stated appraisal against
  the action, and a declared contract to the reservoir model.
- Weakness left: the contract is a capability, not a property of the published runs (ledger §3).
- Improvement: PROSE — "enforced at construction; published runs predate it" (2 h).

**A2. If the rule layer sets the macro regime, why language agents at all?**
- Evidence: r1 — FQL with validators 999.3 ± 4.7 ft minimum vs without 895.0 ± 0.0 ft, 10 of 10
  seeds at dead pool. r8 — flood shares governed 46.7 / 9.5 / 13.2 / 30.6 % (insurance / elevate /
  relocate / do-nothing) vs rule-based PMT 27.3 / 14.7 / 0.2 / 57.8; EHE 0.861 vs 0.693.
- Answer: the rule layer sets the regime, and saying so is a finding, not a concession. The agents
  add behaviour inside the feasible set — 13.2 % relocation against 0.2 % — plus a written appraisal
  per decision.
- Weakness left: more diverse is not more realistic; r8 puts the governed arm further outside the
  empirical elevation range than the rule-based arm.
- Improvement: PROSE — claim legibility and within-constraint heterogeneity (3 h).

**A3. Is this a water-science paper or a software paper?**
- Evidence: readiness audit §Positioning; ledger §7.
- Answer: a methods paper for water modellers, at WRR or EM&S. The claim: a language-model decision
  can be made inspectable and re-runnable the way a parameterised behavioural rule is. Two water
  testbeds are the evidence, not the point.
- Weakness left: a referee may still ask for a hydrological result we do not have.
- Improvement: PROSE — title and abstract promise a method, not a Colorado River finding (2 h).

---

## B. Coupling to the physical model

**B1. Your flood testbed couples a binary flood event and a fixed damage figure. Is that coupling?**
- Evidence: r8 — three flood benchmarks NOT AVAILABLE for want of a `flooded_this_year` column;
  r2 — 10 years, four actions.
- Answer: no, and we should not call it one. The flood testbed exercises governance; the coupling
  claim rests on irrigation, where decisions and reservoir state advance together over 42 years.
- Weakness left: the hazard-coupled multi-agent flood domain has no no-validator arm, so coupling
  and governance are never shown together.
- Improvement: RERUN — no-validator arm for that domain, 5 seeds (2–4 GPU-days).

**B2. Did the published runs actually run under the coupling contract?**
- Evidence: ledger §3 — every published irrigation run bypassed it and defaulted fifteen
  physical-state fields to 0; at runtime the path checks presence, finite range and dtype only,
  never `check_units()` or `check_cadence()`.
- Answer: no. Direction and double-count are enforced at construction, unit and cadence declared but
  unverified, and the corpus predates all of it. Point referees at `coupling_contract_active` and
  `coupling_guard_calls` in `run_integrity.json`.
- Weakness left: **UNRESOLVED** — which of the fifteen fields reached the rendered prompt is not
  established by r1–r9; reservoir elevation clearly did (r1).
- Improvement: ANALYSIS-ONLY — grep stored prompts per field, publish a presence table (4 h).

**B3. Do the agents respond to the physical state, or only to the rules?**
- Evidence: r1 — over 42 years the no-validator demand-increase rate tracks reservoir elevation at
  r = +0.69, the governed arm at r = +0.19. r1 year 1, before any rule binds: governed IBR 78.3 % vs
  77.1 %, increase rate 84.9 % vs 86.2 %.
- Answer: consistent with a response, not shown. Both series fall over the 42 years, so a positive
  correlation is what a shared downward trend produces whether or not the agents read the reservoir
  at all. The one clean check we have is year 1: with no rule yet binding, the two arms are the same
  model, which is why the year-1 near-identity is evidence and the correlations are not.
- Weakness left: elevation is partly an outcome of demand, so even a within-agent fit will not be a
  clean response test.
- Improvement: ANALYSIS-ONLY — within-agent regression on lagged elevation (1 day).

---

## C. Long horizon

**C1. Is the effect accumulating over 42 years, or a level shift?**
- Evidence: r1 per-year proposal IBR, 5-seed mean — years 1–2 together (+1.1, +10.1 pp), gap opens
  year 3 (−18.7 pp), averages −43.6 pp over years 3–12 and −29.3 pp over years 33–42, reversing sign
  in years 17 (+10.7) and 21 (+1.4). r1, unconditional increase-rate gap, same level and averaging:
  negative in 41 of 42 years, range −42.56 to +14.62 pp, the single exception being year 2 at
  +14.62 pp. On the executed action it is negative in all 42 years (−74.62 to −4.62 pp).
- Answer: persistent, not accumulating. Separation appears within three years and stays, with no
  trend towards a wider gap — the late gap is smaller than the early one.
- Weakness left: the conditional IBR reverses sign in years 17 and 21 because governance thins its
  high-WSA denominator; the unconditional gap reverses only in year 2, before the rules have bitten,
  and never after.
- Improvement: PROSE — delete "accumulating"; report the unconditional gap beside the conditional
  one (3 h).

**C2. Does governed behaviour drift — does it converge on one action?**
- Evidence: r1 per-year entropy (`ehe_yearly`, not the headline EHE) — governed 0.634 over years
  1–10 falling to 0.595 over years 33–42; no-validator 0.720 rising to 0.856.
- Answer: the governed arm narrows slightly, the no-validator arm widens; neither is dramatic. Never
  quote per-year entropy beside the headline EHE — averaging years gives a materially smaller number
  than pooling once.
- Weakness left: no test that the governed decline exceeds seed noise.
- Improvement: ANALYSIS-ONLY — per-seed slope of `ehe_yearly` on year (2 h).

**C3. The flood testbed is ten years and you publish no time series. Why?**
- Evidence: r2 executed level, 5-run means — gap opens year 2–3 (governed 0.0 / 0.0 / 2.8 % vs
  0.8 / 3.6 / 8.0 %) and holds to year 10 (1.5 % vs 9.8 %); per-year entropy falls in both arms from
  0.72–0.80 to 0.53–0.56.
- Answer: it exists and belongs in the SI. The entropy decline in both arms is a domain property —
  households that have elevated or relocated stop deciding — not a governance effect.
- Weakness left: governed seeds are 42 / 4202 / 4203 / 45 / 46 against no-validator 42–46 (verified
  2026-09-05), so the pairing is by run index, not seed; three seeds exist in both arms.
- Improvement: ANALYSIS-ONLY — SI figure with the pairing caveat in the caption (4 h).

---

## D. Measurement validity

**D1. Does the headline score what agents did, or what they asked to do?**
- Evidence: r5 — irrigation IBR 36.05 / 59.07 % on the proposal column, 0.86 / 26.77 % executed;
  r3 — 39.49 % of governed and 29.04 % of no-validator rows end REJECTED-to-fallback. Verified
  2026-09-05, seed 42: a rejected increase leaves the water request unchanged on 1146 of 1146 rows,
  an approved increase moves it on 79 of 79.
- Answer: what they asked to do, and that belongs in the abstract; rejected proposals never move
  water. The executed version has the same sign and a larger gap (−25.90 vs −23.02 pp), so no
  conclusion turns on the choice.
- Weakness left: `final_skill` holds the last proposal after retries, not the executed action, and
  that is frozen into the data (ledger §1).
- Improvement: PROSE — relabel proposal-level, publish the remap, report both columns (1 day).

**D2. Your IBR denominator is a label the treated model wrote — post-treatment conditioning.**
- Evidence: ledger §1 — design-fixed companion estimator, unconditional −21.62 pp, CI
  [−26.80, −16.45], plus a 16-cell specification curve; r5 — unconditional increase rate 40.90 % vs
  62.52 %.
- Answer: correct, and the fix is already computed. The unconditional contrast needs no denominator
  from the treated arm, is fixed by design, and keeps 94 % of the headline magnitude. Lead with it;
  keep conditional IBR as the theory-linked secondary.
- Weakness left: even the unconditional rate uses a self-reported action label.
- Improvement: PROSE + ANALYSIS-ONLY — promote it to the abstract, ship the curve as SI (1 day).

**D3. Every binding rule reads a label the model produced in the same generation. Isn't that circular?**
- Evidence: ledger §2 — every published run built only `AgentValidator`; `ThinkingValidator` and
  every world-conditioned rule were unreachable; `grounded_v1` is new with no published run. r3,
  confirmed 2026-09-05 — the precondition `not at_allocation_cap` blocked 35.38 % of no-validator
  rows and 0 governed rows.
- Answer: for the published corpus, yes — we measure internal consistency, not agreement with the
  world. The control arm is bound by a hard world affordance both arms share, so it is "validators
  disabled", not "ungoverned", and the measured gap isolates the theory layer.
- Weakness left: no non-circular estimate exists; `grounded_v1` has never run.
- Improvement: RERUN — one `grounded_v1` irrigation arm, 5 seeds (2–3 GPU-days).

**D4. Your retry prompt states the reason for the block. Can the agent restate its appraisal to fit?**
- Evidence: r9 — NOT AVAILABLE on released corpora: no first-attempt appraisal column, and the raw
  JSONL holds one record per decision. r9 — 63.8 % of governed irrigation decisions retried, 35.4 %
  no-validator, 8.4 % governed flood. The only measurement, 45.3 % of retried decisions changed
  appraisal, is on the unreleased TAE seed 42, provenance RED.
- Answer: we cannot answer this from the released data, and should say so rather than argue. Report
  the size of the hole; quote the 45.3 % as unreleased disclosure only.
- Weakness left: the objection most likely to be judged fatal.
- Improvement: RERUN — record per-attempt labels, re-run the headline pair (3–4 GPU-days).

**D5. In flood, how much of the effect is one rule?**
- Evidence: r3, flood governed ERROR rules, 5-run mean share of rows — `extreme_threat_block`
  7.91 %; `elevation_threat_low` 0.31 %; `relocation_threat_low` 0.15 %; `elevation_block` 0.12 %;
  unnamed precondition blocks 0.70 %. Rejected-to-fallback 1.07 %.
- Answer: essentially all of it — one rule carries the contrast, the other four firing on about
  1.3 % of rows. Because the flood default skill is `do_nothing`, rejection is behaviourally inert,
  so the effect comes from compliance inside the retry loop.
- Weakness left: a single-rule effect over ten years is thin evidence for a rule layer.
- Improvement: PROSE — "one rule, within-retry compliance", plus R5-inclusive and R5-exclusive
  numerators side by side (4 h).

**D6. What does your WARNING-only condition with 0 % behavioural change establish?**
- Evidence: ledger §1 — an architectural identity: a WARNING has no channel back to the model. r3 —
  WARNING rules do fire (irrigation `curtailment_awareness` 11.36 % of governed rows) and change
  nothing by construction.
- Answer: nothing, and one referee already calls this sentence reject-sufficient alone. Delete it
  from all three files that carry it. [2026-09-10 update: the genuine advise-versus-enforce
  contrast this line called for HAS now been run — r14, `strict` + `governance.advise_mode:
  feedback`, gemma3:4b, FINAL n=5 seeds. Uptake > 0 holds (consistent 5/5, exact permutation p at
  its n=5 floor of 0.0625); rejected_to_fallback ≈ strict does not settle either way — see
  `out/SUMMARY.md` #15 and `out/r14_advise_final_n5_2026-09-10.md`.]
- Weakness left: deleting it removes the only soft-governance evidence we claimed — r14 now
  supplies a replacement, but it does not fully resolve the rejection-rate question (see above).
- Improvement: PROSE — three deletions (1 h) plus a pointer to r14's n=5 result; the RERUN this
  line asked for is DONE.

**D7. How many decisions were recovered by a fallback parser rather than parsed cleanly?**
- Evidence: r6 — released irrigation 3.23 % governed / 4.08 % no-validator; released flood 0.22 % /
  0.21 %; unreleased TAE governed runs 12.43–18.50 %, digit layer alone 10.47 % on seed 42.
- Answer: a few per cent on the released corpora, disclosed with the fact that these are a lower
  bound, because the parse-layer flag postdates those runs (ledger §1).
- Weakness left: a lower bound is not a bound a referee must accept.
- Improvement: PROSE — one Methods paragraph carrying both (2 h).

**D8. Main text and SI report different values for the same flood metric. Which is it?**
- Evidence: r4, confirmed 2026-09-05 — 0.87 / 8.53 (and the published 0.9 / 8.5) and flood EHE
  0.815 ± 0.053 reproduce only with the pre-quarantine no-validator arm, whose Run_1–3 are the
  reflection-OFF seeds 42 / 43 / 44 quarantined in May 2026. The live arm gives 0.87 / 7.41 and EHE
  0.786 ± 0.040. Conditional variants: 1.60 / 14.22 and 2.51 / 22.56.
- Answer: the published flood pair is **UNRESOLVED**. Either move the headline to the live arm
  (0.87 / 7.41, EHE 0.786) or keep the old numbers and disclose in the caption that the comparison
  arm includes three quarantined runs. Moving is cleaner.
- Weakness left: changing the headline changes a published figure.
- Improvement: ANALYSIS-ONLY — repoint figure and Extended Data Table 2 (1 day).

---

## E. Robustness and statistics

**E1. Five seeds, a non-deterministic backend, a paired t-test. Is any of this significant?**
- Evidence: r7 — n = 5 gives an exact sign-flip permutation floor of 2/32 = 0.0625, so no paired
  n = 5 contrast can be permutation-significant at 0.05; irrigation IBR proposal t = −16.15, df = 4,
  p = 0.0001; every irrigation metric and every flood IBR variant same sign on all five seeds.
- Answer: not by a distribution-free test, and we should stop implying otherwise. Sign-consistency
  is what is defensible, and needs no normality assumption five points cannot test.
- Weakness left: the field's soft norm is nearer 30 runs. Flood EHE is fragile: the published
  p = 0.166 reproduces as an unpaired two-sample t on the pre-quarantine arm (0.167); paired there
  gives 0.295; on the live arm unpaired 0.022, paired 0.0785 (verified 2026-09-05). **UNRESOLVED**.
- Improvement: RERUN — extend the headline pair to ~30 seeds (6–10 GPU-days); PROSE — name test
  family and arm wherever a flood EHE p appears (4 h).

**E2. How large is your prompt-sensitivity envelope? Does 23 pp exceed it?**
- Evidence: readiness audit R5 — a `[ROUTINE]` memory tag moved year-1 elevation from 25 % to 70 %;
  r7 — headline gap −23.02 pp.
- Answer: we cannot bound it, and the one perturbation we happen to have measured moved an outcome
  by 45 pp, larger than our headline.
- Weakness left: without a perturbation arm a referee cannot tell whether the effect exceeds the
  framework's own wording sensitivity — the strongest ground for rejection.
- Improvement: RERUN — one paraphrase control plus one persona variant, reduced scale
  (3–5 GPU-days).

**E3. Does the effect hold across language models?**
- Evidence: **UNRESOLVED in this package** — no cross-model comparison is recomputed in r1–r9, and
  part of that corpus is partial data.
- Answer: do not quote a cross-model number until it is recomputed the way r0–r9 recompute
  everything else. The safe statement is one model family at two testbeds.
- Weakness left: a methods paper with one model family is weak on generality.
- Improvement: ANALYSIS-ONLY — extend the r4/r7 recomputation to the cross-model corpora with a
  partial-data flag (2–3 days).

---

## F. The water community's validation bar

**F1. Which empirical ranges are you validating against, and do your own tables agree?**
- Evidence: r8 — the two shipped benchmark tables disagree on six shared names (`buyout_rate`,
  `elevation_rate`, `insurance_lapse_rate`, `insurance_rate_all`, `insurance_rate_sfha`,
  `mg_adaptation_gap`); seven if table A's `rl_uninsured_rate` is matched to table B's
  `renter_uninsured_rate`, a different population. Ledger §4 — two EPI formulas give 0.7049 and
  0.8689 on one fixture.
- Answer: we ship two tables that disagree, which is a decision to make before submission. Pick one,
  delete the other, and never report an EPI without its formula version.
- Weakness left: neither table's ranges are sourced to the standard a water referee applies.
- Improvement: ANALYSIS-ONLY — reconcile to one table with a cited source per range (1 day).

**F2. Where is the rule-based comparison a water modeller expects?**
- Evidence: r1 — FQL irrigation baseline with and without validators, 999.3 ± 4.7 ft vs
  895.0 ± 0.0 ft minimum. r8 — rule-based PMT flood baseline 27.3 / 14.7 / 0.2 / 57.8 %.
- Answer: it exists in both domains, with and without validators — more than the nearest
  water-domain LLM work offers. Kadiyala et al. (2025, *J. Hydroinformatics*), InsurAgent
  (arXiv:2511.02119) and IWMS-LLM (2025) have neither a reject/retry layer nor a rule-based ABM
  comparison. That is our cleanest differentiator.
- Weakness left: the rule-based arm writes six cumulative state labels, so its share depends on the
  "Both" fold; r8 reports three and picks none. **UNRESOLVED** — the printed 0.583 matches no fold;
  the documented reference is 0.598 (`metrics_definitions.md:195`).
- Improvement: ANALYSIS-ONLY — document one fold, correct 0.583 to 0.598 (4 h).

**F3. Have you validated against observed adaptation rates?**
- Evidence: r8 — elevation rate 0.986 / 0.996 / 0.887 (governed / no-validator / rule-based) against
  0.03–0.12 (table A) and 0.10–0.35 (table B): every arm outside both. `insurance_rate_all`
  0.518 / 0.482 / 0.700 — outside A, inside B's 0.15–0.55 for the LLM arms. `buyout_rate`
  0.262 / 0.126 / 0.003 — no-validator inside both, the others outside. Eleven further benchmarks
  NOT AVAILABLE for missing columns.
- Answer: no. Insurance and buyout land inside a published range for at least one arm; elevation is
  an order of magnitude too high everywhere. Against the bar set by Haer & Aerts and by de Ruig et
  al.'s DYNAMO/NFIP benchmarking, this is not calibrated behaviour.
- Weakness left: elevation is the same construct on both sides (share elevated by year 10, verified
  2026-09-05) but our denominator is all agents while both tables are homeowner-restricted — a
  caveat, not an explanation for a tenfold gap.
- Improvement: PROSE — limitation paragraph naming elevation and the denominator mismatch (3 h).

**F4. Did you calibrate anything?**
- Evidence: ledger §4 — the parametric calibration result is not an estimate: three aggregate
  metrics cannot identify four base rates, the ordering comes out behaviourally backwards, and a
  larger budget over-fits (held-out error 0.40 at 40 evaluations, 1.58 at 253); no out-of-sample
  validation of any LLM run.
- Answer: no, and the reason is identifiability rather than effort — the quantities we can compare
  against are fewer than the parameters we would need to fit. Report the failed fit with its
  warnings; present pattern-level agreement, not calibration.
- Weakness left: "not calibrated" plus "not out-of-sample validated" is the pair Larooij & Törnberg
  (arXiv:2504.03274) and TRAILS (arXiv:2605.18890) name as the field's standing failure.
- Improvement: PROSE — state the identifiability argument (4 h); RERUN — held-out-year validation of
  the irrigation arm (4–6 GPU-days).

---

## G. Audit trail and reproducibility

**G1. Can I trust the columns in your released data?**
- Evidence: r3 — dead on every run: `rules_triggered` empty on 100 % of rows; the five
  `rules_*_hit` columns all "0"; `fallback_activated` "False" on 100 % of rows even where `status`
  is `REJECTED_FALLBACK`. Ledger §1 — `mem_top_emotion` and `mem_top_source` unreliable; ABORTED
  steps absent.
- Answer: some columns are wrong and we publish the list rather than shipping them quietly.
- Weakness left: a referee may ask why they were released at all.
- Improvement: PROSE — Data Availability paragraph naming the columns (2 h).

**G2. Can someone reproduce your numbers?**
- Evidence: ledger §1 — the published pair reproduces from the frozen corpus via `reproduction/`;
  mock recipes are byte-identical to the pre-stack baseline (sha256 551f7c99… / 5f485d3f…). r0 — the
  irrigation headline reproduces to +0.002 pp and +0.000 pp.
- Answer: byte-identical reproduction covers the mock-model recipes. Real-model runs are not
  deterministic at a fixed seed, so real-model reproduction is agreement of N-seed aggregates.
- Weakness left: mock byte-identity proves the pipeline is stable, not the scientific result.
- Improvement: PROSE — define reproduction at two levels (3 h).

**G3. Does the repository produce these numbers from a clean clone?**
- Evidence: ledger §1 — clean-clone gate, 2026-09-03; ledger §7 — the PII purge rewrites every
  commit hash, so commits must be cited through the rewritten map. The 17-of-17 count is from the
  prep outline, not recomputed in r1–r9.
- Answer: yes as of the 2026-09-03 gate. One caveat to publish ourselves: the purge rewrote history,
  so any commit hash in an earlier draft is stale.
- Weakness left: continuous integration exercises a small fraction of the suite behind a green
  badge — cheap for a referee to check.
- Improvement: PROSE — state which tests gate merges, or point CI at the full suite (4 h).

---

## H. Generality to other water domains

**H1. Would this work for another discrete adaptation problem — household conservation, say?**
- Evidence: verified 2026-09-05 — a discrete-choice annual-decision domain registers through the
  skill registry and the annual runner loop with no framework-core changes; the health-belief-model
  vaccination domain does exactly that; a benchmark registry, optimiser and held-out target split
  exist. **Updated 2026-09-09** — the domain has now run three real-LLM seeds (gemma3:4b, `strict`,
  100 agents x 10 years, code `88c21542`) and produced audit traces: 100.00 % parity (3000/3000,
  menu-decoded), `integrity_ok=true` all seeds, a live validator (direct positive-control test),
  0 HBM rule fires on any seed (SUMMARY.md "Vaccination T0-4b", r12b).
- Answer: yes for discrete choice on an annual step. The vaccination domain is now a DomainPack-plug
  demonstration (parity, audit-trail integrity, a live and correctly-wired validator), not a
  governance result — traces are not committed to git (project policy: `examples/*/results/` stays
  gitignored everywhere), but they now exist and have been measured. The 5 HBM thinking-rules never
  had a matching (label, action) precondition to fire on in this batch, so no governance-effect
  claim follows from it.
- Weakness left: "generalises beyond water" now has one measured domain (parity + integrity + a
  confirmed-live validator), but zero evidence yet that governance changes an outcome outside
  water — the vaccination batch's own rule preconditions never co-occurred with an action.
- Improvement: RERUN — DONE 2026-09-09 (commit `88c21542`, seeds 42/43/44, r12b). Remaining gap: a
  vaccination batch where at least one HBM rule actually fires, to demonstrate a governance effect
  outside water.

**H2. Could this drive a reservoir operations model — continuous release on a monthly step?**
- Evidence: verified 2026-09-05 — `decision_cadence="step"` is declared but never executed; the
  reservoir example is an annual decision wrapping twelve monthly solver sub-steps; `set_release`
  carries one 0–100 % magnitude and multi-dimensional `parameters` is unused; one dead-pool
  validator is hand-written; REST and file-replay adapters are unbuilt.
- Answer: not today, and one sentence should say so. The agent layer decides once a year and hands a
  scalar to a monthly solver; sub-annual control, multi-dimensional actions and external-model
  adapters are future work.
- Weakness left: reservoir operations is the application a WRR referee most likely has in mind.
- Improvement: PROSE — scope sentence plus future-work paragraph (2 h).

---

## Top 10 fixes before submission
Ordered by reviewer damage times cheapness.

1. **PROSE** — delete the "WARNING-only, 0 % behavioural change" line, all three files (D6). 1 h.
2. **PROSE** — relabel the irrigation headline proposal-level; report the executed column (D1). 1 day.
3. **ANALYSIS-ONLY** — move the flood headline to the live arm (0.87 / 7.41, EHE 0.786) or disclose
   the quarantine (D8). 1 day.
4. **PROSE** — promote the unconditional −21.62 pp estimator; ship the specification curve (D2). 1 day.
5. **ANALYSIS-ONLY** — correct irrigation EHE to 0.6724 / 0.8569 in the four stale files (v19
   markdown, `PAPER_ASSETS.md`, `journal_format.md`, SI v15). 4 h.
6. **PROSE** — Data Availability paragraph naming known-wrong columns and aborted rows (G1). 2 h.
7. **PROSE** — stop claiming contract-validated coupling for the irrigation runs (B2). 2 h.
8. **PROSE** — sign-consistency language; test family named on every flood EHE p (E1). 4 h.
9. **PROSE** — cite our own `[ROUTINE]` prompt-sensitivity finding as a limitation (E2). 2 h.
10. **DONE 2026-09-09** — vaccination domain rerun on the options-text-parity fix, 3 real-LLM seeds,
    traces measured (not committed — project policy keeps `examples/*/results/` gitignored) (H1).

## Claims we should drop or downgrade
- **Drop** "WARNING-only governance produces 0 % behavioural change" — an architectural identity.
- **Drop** "contract-validated coupling" for the published irrigation runs (ledger §3).
- **Drop** flood 0.9 / 8.5, 0.87 / 8.53 and EHE 0.815 as live-corpus values — pre-quarantine only
  (r4). **UNRESOLVED**.
- **Drop** irrigation EHE 0.687 / 0.848 as printed; the 5-seed value is 0.6724 ± 0.046 /
  0.8569 ± 0.011, Δ −0.1845, p = 0.0014 (r7). Docx v50 already avoids EHE numerals.
- **Drop** rule-based flood EHE 0.583 — matches no fold; the documented reference is 0.598 (r8).
- **Downgrade** "no significant EHE difference in flood" — 0.166 is unpaired on the pre-quarantine
  arm; the live arm unpaired gives 0.022 (E1). **UNRESOLVED**.
- **Downgrade** "governance changes behaviour" → "changes what agents propose" (D1).
- **Downgrade** "ungoverned arm" → "validators disabled"; a shared affordance blocked 35.38 % of its
  rows (D3).
- **Downgrade** "accumulating divergence" → "opens by year 3 and persists" (r1).
- **Downgrade** "generalises beyond water" → "registers without core edits; no traces yet" (H1).
- **Downgrade** cross-model generality — not recomputed here (E3). **UNRESOLVED**.
- **Downgrade** "validated against empirical rates" → "compared against published ranges" (r8).

## What the paper can claim safely
1. Rules change what a language agent asks for: appraisal–action inconsistency falls from 59.07 % to
   36.05 % at the proposal stage and from 26.77 % to 0.86 % executed, same sign on all five seeds
   (r5, r7).
2. That gap isolates the theory layer: both arms are bound by the same hard world affordance, which
   blocked 35.38 % of control rows (r3).
3. It reaches the physical system: no governed seed drives Lake Mead to dead pool, all five
   no-validator seeds do, first crossing year 17–18 (r1).
4. Rejected proposals never move water — 1146 of 1146 rows on seed 42.
5. The same pattern holds for a rule-based Q-learning decider, so the reservoir outcome belongs to
   the rule layer, not the language model (r1).
6. The gap opens within three years and persists to year 42 without widening (r1).
7. Each decision leaves a proposal, a rule verdict, a retry count and an executed action in one row,
   which is what makes the rejection auditable (r3).
8. We do not claim calibration, out-of-sample validation, a bounded prompt-sensitivity envelope,
   sub-annual control, or non-circular rule grounding.
