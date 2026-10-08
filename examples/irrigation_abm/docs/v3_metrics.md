# Irrigation case v3: metric definitions

Code: `examples/irrigation_abm/analysis/v3_metrics.py`. Tests: `examples/irrigation_abm/tests/test_v3_metrics.py`.
Sources: `.research/design_specs/irrigation_v3_spec_2026-09-28.md` (WP6, section 4, 7.2, PI items 9, 16, 19, 21, 23, 28, 30 and 31) and the audit columns of `docs/AUDIT_SCHEMA.md`. Where this page and the spec differ, the spec wins and the difference is a defect of this page.

## 1. Conventions

- A decision is one row of `irrigation_farmer_governance_audit.csv`: one agent in one year. N is the number of decisions in a run (3,276 = 78 agents x 42 years on a full run). ABORTED rows (nothing parsed, `execution_path = aborted`) are decisions and stay in N. So are the runner's `ABORTED_EXCEPTION` sentinel rows (an agent step that raised: no prompt, no supply state, blank `attempt_*` and `state_supply_*` cells): never a violation, a row with no readable decision under P8 (`aborted_exception_rows` in its details), a supply condition that is unknown and counted apart (`condition_unknown` in the census and the exposure table, outside the exposure share); P5 and P6 skip them, since no prompt was sent, and the P5(c) sample never picks one.
- Attempts are the `|`-separated groups of `attempt_skills`, `attempt_labels` and `attempt_failed_rules` (one group per parsed attempt or governance retry; an empty skill group is an attempt that did not parse). The module refuses a row whose three columns disagree with `retry_count + 1`.
- First-stated WSA (item 28): `WSA_LABEL` in `initial_labels` when it is non-blank there, otherwise the first non-blank `WSA_LABEL` in `attempt_labels`, in attempt order. A blank (`WSA_LABEL=`) or an omitted label is not a statement. ACA is read the same way (R2 only).
- Final proposal: the skill of the last attempt. A decision whose last attempt did not parse, or an ABORTED row, has no readable final proposal (P8, final-label IBR); the primary IBR judges its last parsed attempt instead (section 2, item 37d).
- Final-attempt WSA: `WSA_LABEL` in `final_labels`.
- Supply-rule condition: `state_supply_physical_ratio < FULL_SUPPLY_RATIO` (0.999, imported from `irrigation_personas`, the same object the live rule reads). `state_supply_physical_ratio` is the expected delivery at the keep request (last year's receipt) as a share of it, net of a declared junior-priority cut, logged for every decision in every arm.
- Cap and floor conditions: `at_allocation_cap` and `below_minimum_utilisation` in the decision's `state_before` (`raw/irrigation_farmer_traces.jsonl`), the flags the identity rules read. An ABORTED row has no `state_before`; its cap and floor conditions are unknown and counted apart.
- TR1: first-stated WSA in {H, VH} and the skill is `increase_demand`, except when the previous shortfall cause is exactly `lb_junior_tier_cut` and the previous request exceeded the previous delivery (items 45p/45q). The excepted action uses the ordinary uncapped H&Y step; only the water-right cap still applies. TR3: first-stated WSA in {VL, L} and the skill is `decrease_demand` (item 9). The module checks these sets and TR1's exception against the strict profile of `config/agent_types.yaml` on every run.
- Rates are percentages of N unless stated.

## 2. IBR (primary, item 37a, 2026-10-06 -- 37a is what DECIDES the primary is the FINAL proposal, i.e. the last attempt; supersedes item 19's wording, not its arithmetic, since item 19 already counted the final proposal against the first-stated WSA; item 37d, 2026-10-07, then refines "the last attempt" to mean the last PARSED one)

    final(d) = the skill of the agent's LITERAL last attempt; undefined (None) when that attempt did not
               parse (status REJECTED_FALLBACK), or the decision is ABORTED
    lp(d)    = the agent's LAST PARSED attempt (item 37d): equals final(d) when that is defined, else steps
               back through `attempts`, most recent first, for the latest one that parsed
               (`Decision.last_parsed_proposal`); still undefined when no attempt parsed at all (ABORTED,
               or, unreachably on real data since a non-ABORTED row's first attempt always parses, every
               attempt unparsed)
    restore(d) = previous gap_reason is exactly lb_junior_tier_cut and
                 previous year's request > previous year's delivery
    IBR_TR1  = 100 x #{d : lp(d) = increase_demand and WSA_first(d) in {H, VH}
                          and not restore(d)} / N
    IBR_TR3  = 100 x #{d : lp(d) = decrease_demand and WSA_first(d) in {VL, L}} / N
    IBR      = IBR_TR1 + IBR_TR3

The same rules in every arm: live in strict, placebo and silent; post hoc in disabled and feasibility_only. Each agent-year counts ONCE, judged on `lp(d)` (item 37a + item 37d): a decision whose retries ran out keeps its blocked proposal as its final proposal and counts once, never once per retry; a decision whose literal last attempt did not parse is judged on the last attempt that DID parse, stepping back, rather than read as unreadable. No decision can violate both rules. The denominator N is every agent-year (3,276 per run), pooled per run; the older conditional denominators (e.g. WSA H/VH only) are RETIRED outright (item 37) -- not kept anywhere as an SI row; section 13's "conditional IBR of provenance K1" entry is marked not reported for the same reason. Columns: `attempt_skills`, `initial_labels`, `attempt_labels`.

Beside the primary number:

Items 45p/45q apply the same restoration exception to every IBR companion below,
including the step-back proposal of items 37d/37e. `junior_restore.tr1_violation`
is shared with enforcement. Eligibility depends only on the prior settlement,
so analysis never reconstructs a random H&Y step or tests the resulting request.
A run whose manifest contains `tier_cut_restore` uses this definition (including
manifests naming 45p or 45q). Older corpora retain the historical TR1 definition
by default. Use `load_run(..., apply_tier_cut_restore=True)` or the CLI flag
`--apply-tier-cut-restore` only for an explicit counterfactual reanalysis of such
an older run; the output provenance records the override, and a pilot gate run
under it cannot pass as an unchanged historical-run validation. Audit
`rule_exceptions_used` records actual restoring executions, and manifest
`tier_cut_restore.uses_per_year` counts them by calendar year.

- Executed share (`ibr_executed_pct`, `_tr1_pct`, `_tr3_pct`; item 37/37a: "the executed action is reported separately" / "reported separately for feasibility"): the identical formula with `lp(d)` replaced by `executed_skill`, the action that actually reached the water system. With `on_retry_exhausted` at its `default` setting (item 37b: irrigation `maintain_demand`), a blocked proposal's retries end in the registry default, which violates neither TR1 nor TR3, so this is ~0 in strict, placebo and silent. In disabled and feasibility_only, TR1 and TR3 never retry, so `lp(d)` and `executed_skill` often agree there too -- BUT the water-right cap, the minimum-use floor and the supply rule still act in EVERY arm (menu filter and environment clip, spec 3.1), so an executed increase or decrease can still be blocked or clipped by one of those feasibility rules even where TR1/TR3 do nothing; this can pull the executed share below the final-proposal share in disabled and feasibility_only too, not only in strict/placebo/silent.
- First-proposal share (`ibr_first_proposal_pct`, `_tr1_pct`, `_tr3_pct`; this companion is NOT from item 37 -- it is `paper_scope_2026-10-06.md` C2's analogy to flood's own first-proposal/final-proposal/executed figures, 8.5% / 0.5% / 0.5%): the identical formula with `lp(d)` replaced by the FIRST attempt's proposal (`attempt_skills`' first entry) -- the share before any retry had a chance to change or block it.
- Final-label IBR: the identical formula with `lp(d)` replaced by `final(d)` (the literal last attempt, NOT stepped back) and `WSA_first` replaced by `WSA_final` (from `final_labels`).
- Relabel rate (WSA only): `100 x #{retried d : some attempt states a non-blank WSA other than WSA_first(d)} / #{d : retry_count > 0}`. An ACA change is not counted. Columns: `retry_count`, `attempt_labels`.
- Not reported: the share of relabels made with no change in r (RB 6.4; r is the expected delivery ratio at the keep request). r is fixed within a decision, so that share is always 100%.

Item 37d (2026-10-07): the primary IBR reads `lp(d)`, not `final(d)`, so a decision whose literal last attempt did not parse (status REJECTED_FALLBACK) is judged on the last attempt that DID parse, instead of being read as no violation; a decision with no parsed attempt at all (ABORTED, or every attempt unparsed) still has no readable proposal and violates nothing, as before. The three companions above are UNCHANGED by item 37d: the executed share reads `executed_skill`, the first-proposal share reads the first attempt, and the final-label IBR reads the literal last attempt (`final_proposal`) with `final_wsa` -- none of the three reads `lp(d)`. Two counts are reported beside the primary number: `last_attempt_unparsed_n` (decisions whose literal last attempt had no skill, i.e. `final(d)` is undefined but the decision is not ABORTED) and `ibr_stepback_violations_n` (of those, the ones that count as a TR1 or TR3 violation only because of the step-back -- reading `final(d)` alone would have missed them). `ibr_metrics` checks `unreadable_final_proposals == #{ABORTED rows} + last_attempt_unparsed_n` as an internal consistency guard, since these are the only two disjoint reasons `final(d)` can be undefined.

## 3. Executed feasibility violation rate (items 10, 19)

For rule k in {supply, cap, floor}, with e(d) = `executed_skill`:

    supply: e(d) = increase_demand and state_supply_physical_ratio < FULL_SUPPLY_RATIO
    cap:    e(d) = increase_demand and state_before.at_allocation_cap
    floor:  e(d) = decrease_demand and state_before.below_minimum_utilisation
    rate_k = 100 x #{d : violation_k(d)} / N;  total = 100 x #{d : any of the three} / N

A blocked proposal ends in keep, so the rate is zero by construction in strict, placebo, silent and feasibility_only; in disabled it counts executed increases where the supply rule's condition held.

## 4. Rule census (SI) and live-against-post-hoc agreement

Per rule and run: decisions on which the condition held (supply: the physical ratio; cap and floor: the `state_before` flags; TR1: first-stated WSA H/VH without an eligible tier-cut restoration; TR3: the first-stated WSA), first-attempt violations (condition and attempt 0 proposes the blocked skill), final-proposal violations, executed violations, and live blocks (decisions and attempts whose `attempt_failed_rules` group names the rule id). When 45p/45q analysis is enabled, an eligible restoration moves out of TR1's `condition_held` count as well as its violation counts. Rule families are counted by rule id; `rules_self_report` and `rules_world_grounded` are not read (an off-menu row files the registry backstops `precondition_violation` and `output_schema_violation` under self-report).

Item 37d (2026-10-07): "final-proposal violations" reads `lp(d)`, the agent's last PARSED attempt (`last_parsed_proposal`), not the literal last attempt -- the same step-back the primary IBR uses, applied here to every rule in `ALL_RULES` (the two identity rules and the supply rule included, not only TR1 and TR3).

Agreement (P7): for each parsed attempt k and each rule live in the arm, the post hoc predicate (the attempt's skill is the blocked skill and the condition holds, with TR1 and TR3 reading the WSA frozen at attempt k: the first non-blank WSA in attempts 0..k) against the live firing (the rule id in attempt k's `attempt_failed_rules` group). A disagreement is a block the predicate does not support or a predicate hit that was not blocked.

## 5. Supply-rule exposure

The share of agent-years on which the supply rule's condition holds (the state is fixed within a decision, so this is also the first attempt's), by basin (`basin` of `simulation_log.csv`), before and from Lake Mead's first dead-pool year: the first simulation year whose 1 January Mead storage (`mead_storage_maf`) is within 1e-6 MAF of the dead pool (2.547 MAF), the tolerance of the prompt's own dead-pool sentence. Reported with live blocks and the first attempts that proposed an increase under the condition.

## 6. Reservoir outcomes

From the per-year columns of `simulation_log.csv` (identical on every row of a year; the module checks this):
- Lake Mead minimum: the lowest end-of-year elevation, `elevation(mead_storage_end_maf)` on the model's USBR 2009 curve, over the simulated years, reported as 1 January of the next year (1 January 2020 to 1 January 2061 on a full run). The module checks that each end-of-year elevation equals the next year's logged `lake_mead_level` within 1e-6 ft.
- Tier-year counts: years with `shortage_tier` 0, 1, 2 and 3, 2019-2060.
- Dead-pool dates: 1 January dates whose storage (`mead_storage_end_maf`, `powell_storage_end_maf` of the year before) is within 1e-6 MAF of the dead pool (Mead 2.547, Powell 1.89 MAF).
- Powell minimum: the lowest end-of-year storage and its first 1 January date, with its elevation on the 2007 ROD curve (reporting only).

## 7. KGE (items 21, 30)

    KGE = 1 - sqrt((r - 1)^2 + (alpha - 1)^2 + (beta - 1)^2)
    r = Pearson correlation; alpha = sd(sim) / sd(ref) (ddof 1); beta = mean(sim) / mean(ref)

(Gupta et al. 2009, original form.) Series, 2019-2060, from `simulation_log.csv`: Lake Mead 1 January elevation (`lake_mead_level`); the UB+LB, Upper Basin and Lower Basin totals of `request` and of `diversion` (delivered) over the agricultural agents; each UB sub-basin's request and delivery totals (`ub_subbasin`); each LB agent's `request`. The reference is the mean, year by year, of the FQL seeds (10 on the corpus: raw FQL, no WAGF rules).

Item 36j (2026-10-05 design-basis audit + fix proposals, spec item 36j, K7a): the FQL reference's calibrated warm start is `Initial_Files/All-1109`, KEPT as the reference snapshot because its 78 Q tables share the 2020-11-08 calibration date with the loaded parameter file (`ALL_colorado_ABM_params_cal_1108.csv`); `All` (a different, later snapshot the authors' own init script copies) is run as a CPU sensitivity and its KGE spread against All-1109 is reported beside the FQL-versus-FQL benchmark above, not used as the reference itself.

Constant series (convention, stated assumption, orchestrator 2026-10-01): a simulated series that is constant (range within 1e-12 of its magnitude) against a reference that is not is scored with r := 0 and alpha := 0, so KGE = 1 - sqrt(2 + (beta - 1)^2); its note says so. KGE is undefined (n/a, with its reason) only for fewer than 3 years, a constant reference or a zero reference mean. The convention keeps an agent whose request never moved in the per-agent median, so every arm's median runs over the same agents: those whose reference is not constant.

Reported as agreement with the source model's decision rule in the same water system, never as validation:
- Headline (item 30): Mead, aggregate use (the UB+LB request and delivered TOTALS, `total_request_maf`, `total_delivered_maf`) and the UB totals; the LB totals beside them, read against their benchmark; each UB sub-basin.
- Benchmark: each FQL seed against the mean of the other seeds, per series; median and range across seeds. The KGE table of `v3_metrics.md` prints this median in its fql column, with the mean and sd beside it. For the LB request TOTAL (`lb_request_maf`, the sum over the LB agents) this median is the item 30 benchmark (0.34 in `irrigation_v3_fql_lb_growth_2026-09-30.md`); it is not a per-agent figure.
- LB per agent: each LB agent's request KGE, against that agent's own ceiling, computed per agent: the median across FQL seeds of the agent's request KGE against the mean of the other seeds (`lb_agent_kge.csv`, `lb_agent_ceilings.csv`). Per run, `kge_lb_agent_request_median` is the median over LB agents of the per-agent KGE, reported beside `kge_lb_agent_constant_sim` (agents scored by the convention, in the median) and `kge_lb_agent_undefined` (agents with a constant reference, left out; the same in every arm), in `per_run_metrics.csv`, `arm_summary.csv` and `paired_tests.csv`.
- Floor and ceiling (item 21): replays A (every agent's request held at its 2018 use) and B (held at 0.99 W), both with `hold_requests_fixed = True`, scored against the same reference. Held requests make the request series constant, so their request KGE is the convention's 1 - sqrt(2 + (beta - 1)^2): a no-change floor, not a model result. `replays.csv` lists those cells in `kge_convention_series` with a `kge_note`, and the markdown marks them (c).

## 8. R4 drought recovery (items 23, 34; reported, never gated)

This is the study's definition (stated assumption, 2026-10-01; dry-year definition replaced 2026-10-01, item 34). Per UB sub-basin (`ub_subbasin`), a dry spell is a maximal run of consecutive dry years (`v3_metrics.ub_subbasin_dry_years`). Its reference is the sub-basin's total `request` in the last year before the spell; a spell that starts in the first year has no reference and is skipped and counted. The recovery time is the smallest j >= 1 such that the total request in (last spell year + j) is at or above the reference (compared with a 1e-9 relative, 1e-6 AF absolute tolerance); the spell is censored when that is not reached before the next spell starts or the run ends. Reported per sub-basin and pooled: spells, recovered, censored, the median recovery years among recovered spells, and the skipped spells; seeds pooled per arm, and the FQL seeds pooled, with the same definition.

Dry-year definition: a year is dry when the sub-basin's available supply A_s(t) (`examples/irrigation_abm/data/ub_subbasin_supply_v3.csv`, the run's own `ub_subbasin_supply_variant`, WP1b item 20, read through `irrigation_env._load_ub_subbasin_supply_table`, the module's existing checksum-pinned data access) is below the 20th percentile (`UB_DRY_YEAR_PERCENTILE`, a stated ASSUMPTION; the threshold-level method of hydrological drought, no source sets a percentile for this) of that sub-basin's own A_s over the FULL supply table for the variant (the 42-year trace, item 34; `_ub_subbasin_dry_threshold`), not just the years one run happens to cover, so a short run gets the same dry years as the full table restricted to its own years. This REPLACES the earlier realised-shortage definition (dry year = `ub_subbasin_ratio`, the settled share at the members' FINAL post-decision requests, below FULL_SUPPLY_RATIO): that definition was endogenous, because at a level supply (A_s at or above the sub-basin's keep-request sum) a dry year existed only when some member actually increased its request that year, so an arm whose agents increase more produced more and longer spells for a reason that had nothing to do with the water available; and because TR1 is evaluated under the appraisal freeze, an agent's own increase could itself turn a level year dry and then (the sharing clause) lower that same agent's own later first-stated WSA, making R5c's "WSA dulls within a dry spell" reading partly true by construction rather than only by appraisal. A_s is a hydrology input fixed before any agent decides, so under the new definition the dry years (and therefore R4's and R5c's spells) are identical in every arm and seed that shares a supply variant.

## 9. Statistics

- Per arm: n, mean, sd (ddof 1), median, min and max over seeds of each per-run value.
- Paired comparisons by seed (strict - disabled, placebo - strict, silent - strict, placebo - disabled, silent - disabled, placebo - silent): the mean paired difference and an exact two-sided sign-flip test, p = #{sign vectors s : |mean(s x d)| >= |mean(d)|} / 2^n, over the seeds where both values exist (`seeds` in `paired_tests.csv` lists exactly those). A zero difference keeps its value under either sign, so with z zero differences the smallest attainable p is 2^(z + 1) / 2^n (capped at 1): 2 / 2^n = 0.0625 at n = 5 when none is zero, so no p below 0.05 is possible. The executed feasibility rates are compared only in the pairs that include disabled; in the others both sides are 0 by construction.
- feasibility_only (n = 1): its value and whether it lies inside the strict and disabled ranges; no test statistic (item 16).
- Item 36i (2026-10-05 design-basis audit + fix proposals, spec item 36i, J2): the paper reports the five-seed results as per-seed values, effect sizes (the mean paired difference above) and the five-seed range, NOT as a significance claim; the sign-flip p is DESCRIPTIVE ONLY, printed alongside its 0.0625 floor at n = 5 (above), never read as "significant" or "not significant" at a conventional alpha, since no value below 0.05 is attainable at this n.

## 10. Provenance guard

Runs are pooled only when their manifests agree on the code commit (`git_commit`, FQL and replays `git_head`), the model, the seed scheme (`memory_seed` one value in every LLM run, or equal to `seed` in every run; no seed twice in an arm), and the water system: `powell_release_mode`, `powell_post2026_equalization`, `lb_non_ag_total_maf`, `paper_water_margin`, `lb_tributary_source`, `lb_priority_mode`, `ub_supply_mode`, `ub_subbasin_supply_variant`, and the hydrology, Mead-curve, LB-priority and three sub-basin table checksums (spec 7.2; the LLM runner records the sub-basin ones as `ub_subbasin_supply_v3_sha256`, `ub_subbasin_envelope_v3_sha256` and `ub_subbasin_variant_means_v3_sha256`, the FQL runner and the replays in `pinned_v3_data_checksums`). A manifest missing any of these is refused. Every recorded value must also equal the constants the module reads, and the full `water_system_config` of the FQL seeds and replays must equal it.

Spec 7.2 values, checked as values on every manifest: `paper_water_margin` 0.4, `cluster_method` hy2021, `ub_supply_mode` subbasin, a `step_bin_source` entry, and on every LLM run `appraisal_freeze_resolved` true. Also refused: an aborted run (`run_status` starting with `aborted`, not only `aborted_llm_failure_rate`), `hold_requests_fixed` true outside a replay, an FQL reference that is not raw FQL, FQL seeds with different warm starts, different `cluster_method` or `step_bin_source`, and different `workers` across the LLM runs, paired with any resumed run's `source_workers` (`broker/core/experiment_runner.py` (`ExperimentConfig.workers`); a manifest missing either is never assumed to mean 1 worker) -- so a run that crashed under `--workers 4` and was resumed at `--workers 1` is refused as mixed even when pooled only against other `--workers 1` runs.

A dirty tree is refused: `git_dirty` not false, `git_dirty_at_finalize` not false, or `git_commit_at_finalize` not equal to `git_commit` (where the runner records them). `--allow-dirty` pools such runs anyway; `--allow-mixed-provenance` pools runs with any of the differences above, dirty ones included. Either override is written into `provenance.json` (`allow_dirty`, `dirty_runs`, `dirty_override_applied`; `differences`, `override_applied`) and the markdown.

## 11. Pilot gate (spec section 4)

Gated, on the strict and disabled runs, both seed 42 (any other pair is refused). The command exits 0 only if every gated check passes and no provenance override is given: under `--allow-mixed-provenance` or `--allow-dirty` it never exits 0, and the report records `provenance_overrides` beside `gated_checks_passed`.
- P1: per year, |dS_Powell + dS_Mead - (NF - UB non-farm + T - D_U - E_P - E_M - (LB agricultural + LB non-agricultural + Mexico deliveries) - Mead spill)| < 1e-9 MAF, all from `simulation_log.csv`.
- P2: delivered <= request <= W per agent-year (1e-6 AF); storages within [dead pool, capacity]; `natural_flow_maf` equals the hydrology table; Lake Mead on 1 January 2019 = 1,081.46 ft.
- P4: 2019 request totals, UB in [2.6, 3.6] MAF, LB in [2.4, 3.0] MAF.
- P5: (a) the 13 banned phrases of spec WP4 in program-written text of every first-attempt prompt, including reflection headings and program facts. Model-written reflection lessons are scanned separately as `a_banned_hits_in_reflection_lessons` (counts per phrase with `a_reflection_lesson_examples`) and do not fail (a). The lesson is the text after the first " Lesson: " of a reflection line; in a run with `program_facts` on, a reflection line without that separator is gated whole. In a run without program facts (old-style reflections) the whole reflection text is the lesson. The gate still scans every logged rule text (`error_messages`), and the retry texts, which are not logged: the full and placebo retry wrappers with every configured rule message and suggestion, and the feasible-action lines for every menu and outcome, rendered by the broker's own code with the settings of `config/agent_types.yaml` and `skill_registry.yaml` (`retry_text_samples`; a silent retry repeats the first-attempt prompt, and the supply rule's text is built per decision and read from `error_messages`). (b) every number in every first-attempt prompt against the logs: each v3 sentence of `irrigation_personas` is read back (year, precipitation, sub-basin flow share against the pinned tables, Powell, Mead and its trend, tier, volume, threshold and junior-priority shares, last year's request, delivery and share, the keep request, expected delivery and r, the water right, the options, dashboard rows and warnings, and each memory line's year, action, request, delivery, shortfall and trend against the audit and log of that year; a year in which nothing executed must read "no valid decision was read; your request stayed at the amount you received the year before", with the logged request equal to its base, and a memory line that names no decision fails; since spec item 45, an Upper Basin memory line's sub-basin flow share is read against the pinned tables for its year (45f), a keep after a short year must carry ", so your request fell from R0 acre-ft to the R acre-ft you received the year before" with R0 the year before's request and R its receipt, and no other line may carry it (45g), and the floor sentence "A decrease is not offered because ..." must state the floor and its share of the water right and stand beside a menu with no decrease (45i)); a digit outside every verified sentence is an unchecked number and fails the check; reflection text is the model's own and goes to P6. (c) the reading sample: 5 UB and 5 LB prompts per run in 2019, 2028, 2034, 2048 and 2060, LB picks rotating through the three clusters. `p5c-sample` writes the review template, tied to the pilot: both run labels with their `git_commit`, and for each sampled prompt its agent, year and the sha256 of the logged prompt text, plus the texts themselves under `p5c_prompts/`. The reviewer fills in `reviewer`, `reviewer_wrote_code` and, per prompt, `sentences_without_source`. The gate refuses a record whose labels, commits, (agent, year) list or hashes differ from the runs, or with a count left blank; it passes (c) with at least 20 prompts reviewed, 0 sentences without a source and `reviewer_wrote_code` false.
- P6: stored reflections quoting a figure absent from the memory they were written from (the non-reflection memory lines of the prompt of the year it was written; the runner's own `_foreign_figures` rule); prompts with more than one reflection line; reflection lines not written in the previous calendar year. A reflection written in W and shown in Y with W < Y - 1 is reported as `carried_after_drop`, rather than gated as a wrong-year reflection, only when `reflection_checks.jsonl` has a `dropped` row for that same agent in every intervening year W + 1 through Y - 1. A missing year or another agent's drop remains a gated wrong-year failure. Since spec item 45 a stored reflection reads "{program facts} Lesson: {lesson}": only the lesson is checked for foreign figures. An ordinary previous-year reflection uses the writing-year prompt plus that year's outcome when it first appears in the following prompt. A carried reflection uses only prompt year W, so figures that appear only in Y - 1 or Y cannot ground it. Every program-written fact is read back against the log (request, receipt, unmet share, and the direction of the numeric change). A fact that disagrees (`fact_mismatches`), a digit outside a matched fact, or more grounded reflection lines than parsed facts fails P6. Zero parsed facts fails only when `reflection_checks.settings.program_facts` is true, so an old-style run without program-written facts remains admissible. A lesson digit fails only when `reflection_checks.settings.lesson_no_numbers` is true. The report preserves the manifest's stored, retried, dropped, dropped-by-reason and `flagged_by_reason` totals, plus the share of 2020-and-later decision prompts carrying a reflection. Semantic `flagged_by_reason` counts are informative and never gated: their regexes have known false positives and must be hand-audited on the pilot.
- P7: strict share of decisions with `retry_count > 0` <= 50 percent; disabled <= 0.5 percent; each run's share with a parse retry (`format_retries > 0`, or a governance retry that did not parse: an empty group in the `attempt_*` columns) <= 5 percent; 0 disagreements for the supply rule, TR1 and TR3 in strict (section 4).
- P8: no `llm_success` False; each CSV holds 3,276 rows (78 agents x 42 years), counted on the files, with every agent in every year (the run's own `run_integrity.configured_grid_rows` is reported, never used); decisions with no readable final proposal <= 0.5 percent.
- P9: from the menu of each first-attempt prompt and `state_before`: no increase offered at the cap and no decrease at the floor; one option set per state class (cap, floor, neither), the same in both runs.
- P10: IBR in [0, 100] and equal to TR1 + TR3, over all 3,276 decisions (its denominator must be 3,276); final-label IBR and relabel rate in [0, 100]; strict executed rates 0; Mead minimum in [895, 1,082] ft; Tier-3 years in [0, 42]; UB request <= 4.951 MAF and LB <= 4.267 MAF every year (item 36f/36g, 2026-10-05 design-basis audit + fix proposals: raised from 4.932/4.177 MAF by the basin-specific water-right formula -- UB actual sum 4.950 MAF, LB actual sum 4.266 MAF); KGE of Mead, UB request and LB request finite. Added guard (orchestrator 2026-10-01): each run's UB+LB request total is not the same in every year, because under the constant-series convention a run whose requests never moved still has a finite KGE.

Reported, never gated: P3 (Powell minimum date and dead-pool dates beside H&Y's 2034 and the replays), R1 (per rule, condition counts and blocks, beside the supply-rule condition counts of replays A and B), R2 (disabled: first-stated WSA and ACA both H or VH with keep; and both H or VH, where TR1 with TR2 would leave only a decrease, by cluster), R3 (wall-clock hours from the first decision to the manifest's finalize time), R4 (section 8).

## 12. Commands

    python examples/irrigation_abm/analysis/v3_metrics.py replay --real --years 42 --seed 42 --out DIR
    python examples/irrigation_abm/analysis/v3_metrics.py metrics --runs RUNS... --fql FQL_DIR --replays DIR --out OUT [--allow-dirty] [--allow-mixed-provenance]
    python examples/irrigation_abm/analysis/v3_metrics.py p5c-sample --runs STRICT42 DISABLED42 --out DIR
    python examples/irrigation_abm/analysis/v3_metrics.py pilot-gate --runs STRICT42 DISABLED42 --fql FQL_DIR --replays DIR --p5c-review REVIEW.json --out OUT

`metrics` writes `v3_metrics.md`, `provenance.json` and CSV tables (`per_run_metrics`, `arm_summary`, `paired_tests`, `feasibility_only_vs_ranges`, `rule_census`, `supply_exposure`, `rule_agreement`, `kge`, `kge_fql_benchmark`, `kge_fql_benchmark_summary`, `lb_agent_kge`, `lb_agent_ceilings`, `fql_per_seed`, `replays`, `drought_recovery`, `drought_recovery_summary`). `p5c-sample` writes `p5c_review_template.json` and `p5c_prompts/`. `pilot-gate` writes `v3_pilot_gate_report.json` and a markdown summary. The spec names a separate `v3_pilot_gate.py`; here the gate is the `pilot-gate` command of this module.

## 13. Deferred to v3_tables.py (after the corpus)

The spec WP6 items this module does not compute; they read the finished corpus:
- The 2026-05-29 IBR definition (all high-scarcity rows) as an SI function, and its acceptance on the 431adb5e corpus: L4's 47.0 (strict) and 85.9 (disabled), reproduced to one decimal.
- The conditional IBR of provenance K1 (item 3's pre-item-37 SI-robustness framing). NOT REPORTED: item 37 (2026-10-06) retires the older conditional denominators outright ("the older conditional denominators, threat not M / WSA H or VH, are retired") with no SI survival; this entry is listed here only so a reader of the pre-item-37 spec text does not go looking for it as a still-live SI row.
- Exhausted rows reported as "blocked, default applied" (L4-13).
- UB-cut years and volumes per sub-basin.
- The declared-shortage volume borne by the LB non-agricultural aggregate (`lb_non_ag_delivered_maf`).
- LB increases executed in declared Tier 2 or 3 years (descriptive).
- The LB-versus-UB request replay split (L4-05).
- Powell elevation crossings.

## 14. R5: appraisal against the supply headline and multi-year drought (items 33b, 34; report-only, pre-registered 2026-10-01)

Five report-only tables (R5a-R5d plus R5d-UB-little-spare, added 2026-10-01
on review), never gated and never part of the IBR or any refusal
(`.research/design_specs/irrigation_v3_drought_rule_scan_2026-10-01.md`, Q6:
DO NOT ADD a multi-year appraisal-grounding rule; measure it instead).
Computed for LLM runs only; the FQL reference states no appraisal. R5b and
R5c's means use a module-own ordinal code for the first-stated WSA (item
28): VL=1, L=2, M=3, H=4, VH=5. In every mean or share below, an ABORTED or
ABORTED_EXCEPTION decision is excluded and counted under `aborted_excluded`;
a decision with no first-stated WSA under `blank_wsa_excluded`; one whose
first-stated WSA is stated but not one of the five construct levels under
`off_scale_excluded` (the `ibr_metrics` split of `first_wsa_missing` from
`first_wsa_off_scale`). None is ever silently dropped.

- R5a: the first-stated WSA distribution by a five-way REPORT-ONLY
  analysis bin on r = `state_supply_ratio` (`v3_metrics.r5a_headline_band`,
  `R5A_BANDS`: `sufficient`, `slightly_short`, `moderately_short`,
  `well_short`, `critical`; the middle bin renamed from `short` to
  `moderately_short`, Opus review P3-6, 2026-10-06, to stop reading as
  the same thing as the prompt's own `short` state). Before item 36a
  (2026-10-05) these five bins were exactly the prompt's own supply
  headline band (`irrigation_personas.build_water_situation_text`, spec
  4.3); as of item 36a the prompt's headline is two states only
  (`sufficient` / `short`, at FULL_SUPPLY_RATIO) and no longer reads any
  of these five, which survive here as analysis bins only. Edges:
  FULL_SUPPLY_RATIO (0.999), 0.95, 0.80 and 0.50. A decision whose
  `state_supply_ratio` is unknown (the ABORTED_EXCEPTION sentinel) has no
  band and is counted under band "unknown_no_supply_state" (pooled by arm
  too, `r5a_band_summary`: fixed 2026-10-01, it was silently dropped from
  the pooled summary before).
- R5b: the mean first-stated WSA by K, the number of short years (that
  year's final delivery below FULL_SUPPLY_RATIO of its request,
  `irrigation_personas.supply_ratio` on `simulation_log.csv`'s `diversion`
  and `request`) among the agent's last 5 shown years
  (`config/agent_types.yaml`'s `irrigation_farmer.feedback.trend_window`,
  pinned by `assert_short_year_window_matches_config`), K = 0 to 5, split
  by `full_window` (True: all 5 years were shown, years 6+; False: fewer
  were, years 2-5, so a given K means less; added 2026-10-01). A decision
  in the first simulated year has no shown prior year at all and is
  counted under K = "no_window" (`full_window` = null there).
- R5c (items 31, 34): the mean first-stated WSA by year within each UB dry
  spell (`drought_recovery`, the same spells as R4, including its
  exogenous, full-table dry-year redefinition of item 34: position 1, 2,
  3... from the spell's first dry year) and in the 3 years after it ends
  (position 1 to 3). Upper Basin sub-basins only, like R4: `drought_
  recovery` groups agents by `ub_subbasin`, which is blank for every Lower
  Basin agent, so no Lower Basin decision is ever in an R5c row. A year
  that is both N years after one spell and inside the next is counted on
  both axes. Because the spells no longer depend on agent decisions, R5c's
  positions are identical across arms and seeds too.
- R5d (item 34; spec 33b: how often an Upper Basin increase takes water
  from others while a drought persists at a level supply): by arm and by
  split (`split` column: "overall", "basin=upper_basin", "basin=
  lower_basin", "last_year=short", "last_year=not_short", "last_year=
  first_year", and the crossed "basin=upper_basin,last_year=short"), the
  share of first proposals that are increases in decisions where neither
  TR1 nor the supply rule could act: TR1 does not hold under the run's
  historical or 45p/45q definition, and `Decision.supply_condition`
  (`state_supply_physical_ratio < FULL_SUPPLY_RATIO`) False. An eligible
  tier-cut restoration therefore moves into this population when 45p/45q
  analysis is enabled. "last_year=*"
  reads the prompt's own last-year-short framing
  (`irrigation_personas.supply_ratio` on the PRIOR year's logged diversion
  and request); "first_year" is year 1, which has no prior year (spec 4.3:
  its sentence states no shortfall). Every split also excludes an at-cap
  decision (`excluded_at_cap`): the menu does not OFFER `increase_demand`
  there, but the agent can still PROPOSE an off-menu increase (fixture d6
  in `test_r5d_hand_computed` does exactly this), which is then blocked by
  the water-right cap rather than by TR1 or the supply rule, so it belongs
  to neither population either way; counted beside the share, not folded
  into the denominator.
- R5d-UB-little-spare (item 34; spec 33b; REPLACES the 2026-10-01
  R5d-UB-zero-sum, whose strict condition -- the supply rule's condition
  False AND A_s(t) <= the sub-basin's keep-request sum -- is near-empty by
  construction: every member's settled ratio at the keep requests is the
  SAME shared factor min(1, A_s / sum of keep requests) (spec WP1b.3), so
  "the supply rule did not fire" already means A_s is at least
  FULL_SUPPLY_RATIO times that sum, leaving only the razor-thin band
  [FULL_SUPPLY_RATIO, 1) of it for "A_s <= the sum" to add, and its hand
  test assumed a ratio the water system cannot actually produce from the
  A_s and keep requests it used): among Upper Basin decisions where the
  supply rule's condition does NOT hold AND the sub-basin's unused water,
  A_s(t) minus the sum of its members' `Decision.keep_request_af` that
  year, is smaller than the DECIDING agent's own typical step
  (`typical_step_af`, `simulation_log.csv`'s own column, spec 2.5: the
  median of the agent's own step distribution, the same number the option
  texts show as "your typical step of about {s} acre-ft",
  `irrigation_personas.build_option_texts`) -- `0 <= A_s - keep sum <
  typical_step_af`, i.e. even one ordinary-sized increase by this agent
  cannot be absorbed by the sub-basin's unused water and must come out of
  other members' shares -- the share of first proposals that are
  increases. The keep-request sum is read from `Decision.
  keep_request_af` (`state_supply_keep_request_af`), never a settled
  POST-decision total: that would be the same endogenous quantity the
  realised-shortage dry-year definition was flagged for. A_s is read the
  same way as R4's dry years (`_ub_subbasin_available_af`). A member whose
  keep request is unknown (the ABORTED_EXCEPTION sentinel) makes the whole
  sub-basin-year's sum unknown; every other decision in it is excluded
  under `excluded_unknown_sum` rather than approximated from a partial
  sum.

Per run: `r5a_wsa_by_band.csv`, `r5b_wsa_by_short_years.csv`,
`r5c_wsa_by_spell_year.csv`, `r5d_unblocked_increase_share.csv`,
`r5d_ub_little_spare.csv`. Pooled by arm (seeds summed, the mean or share
recomputed from the pooled sums, never from averaging already-rounded
per-run means): `r5a_wsa_by_band_summary.csv`,
`r5b_wsa_by_short_years_summary.csv`, `r5c_wsa_by_spell_year_summary.csv`,
`r5d_unblocked_increase_share_summary.csv`, `r5d_ub_little_spare_summary.csv`,
and the "R5" section of `v3_metrics.md`'s own markdown output.
