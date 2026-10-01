# Irrigation case v3: metric definitions

Code: `examples/irrigation_abm/analysis/v3_metrics.py`. Tests: `examples/irrigation_abm/tests/test_v3_metrics.py`.
Sources: `.research/design_specs/irrigation_v3_spec_2026-09-28.md` (WP6, section 4, 7.2, PI items 9, 16, 19, 21, 23, 28, 30 and 31) and the audit columns of `docs/AUDIT_SCHEMA.md`. Where this page and the spec differ, the spec wins and the difference is a defect of this page.

## 1. Conventions

- A decision is one row of `irrigation_farmer_governance_audit.csv`: one agent in one year. N is the number of decisions in a run (3,276 = 78 agents x 42 years on a full run). ABORTED rows (nothing parsed, `execution_path = aborted`) are decisions and stay in N. So are the runner's `ABORTED_EXCEPTION` sentinel rows (an agent step that raised: no prompt, no supply state, blank `attempt_*` and `state_supply_*` cells): never a violation, a row with no readable decision under P8 (`aborted_exception_rows` in its details), a supply condition that is unknown and counted apart (`condition_unknown` in the census and the exposure table, outside the exposure share); P5 and P6 skip them, since no prompt was sent, and the P5(c) sample never picks one.
- Attempts are the `|`-separated groups of `attempt_skills`, `attempt_labels` and `attempt_failed_rules` (one group per parsed attempt or governance retry; an empty skill group is an attempt that did not parse). The module refuses a row whose three columns disagree with `retry_count + 1`.
- First-stated WSA (item 28): `WSA_LABEL` in `initial_labels` when it is non-blank there, otherwise the first non-blank `WSA_LABEL` in `attempt_labels`, in attempt order. A blank (`WSA_LABEL=`) or an omitted label is not a statement. ACA is read the same way (R2 only).
- Final proposal: the skill of the last attempt. A decision whose last attempt did not parse, or an ABORTED row, has no readable final proposal and violates no rule.
- Final-attempt WSA: `WSA_LABEL` in `final_labels`.
- Supply-rule condition: `state_supply_physical_ratio < FULL_SUPPLY_RATIO` (0.999, imported from `irrigation_personas`, the same object the live rule reads). `state_supply_physical_ratio` is the expected delivery at the keep request (last year's receipt) as a share of it, net of a declared junior-priority cut, logged for every decision in every arm.
- Cap and floor conditions: `at_allocation_cap` and `below_minimum_utilisation` in the decision's `state_before` (`raw/irrigation_farmer_traces.jsonl`), the flags the identity rules read. An ABORTED row has no `state_before`; its cap and floor conditions are unknown and counted apart.
- TR1: first-stated WSA in {H, VH} and the skill is `increase_demand`. TR3: first-stated WSA in {VL, L} and the skill is `decrease_demand` (item 9). The module checks these sets against the strict profile of `config/agent_types.yaml` on every run.
- Rates are percentages of N unless stated.

## 2. IBR (primary, item 19)

    IBR_TR1 = 100 x #{d : final(d) = increase_demand and WSA_first(d) in {H, VH}} / N
    IBR_TR3 = 100 x #{d : final(d) = decrease_demand and WSA_first(d) in {VL, L}} / N
    IBR     = IBR_TR1 + IBR_TR3

The same rules in every arm: live in strict, placebo and silent; post hoc in disabled and feasibility_only. A decision whose retries ran out keeps its blocked proposal as its final proposal and counts. No decision can violate both rules. Columns: `attempt_skills`, `initial_labels`, `attempt_labels`.

Beside it:
- Final-label IBR: the same counts with `WSA_final` (from `final_labels`) in place of `WSA_first`.
- Relabel rate (WSA only): `100 x #{retried d : some attempt states a non-blank WSA other than WSA_first(d)} / #{d : retry_count > 0}`. An ACA change is not counted. Columns: `retry_count`, `attempt_labels`.
- Not reported: the share of relabels made with no change in r (RB 6.4; r is the expected delivery ratio at the keep request). r is fixed within a decision, so that share is always 100%.

## 3. Executed feasibility violation rate (items 10, 19)

For rule k in {supply, cap, floor}, with e(d) = `executed_skill`:

    supply: e(d) = increase_demand and state_supply_physical_ratio < FULL_SUPPLY_RATIO
    cap:    e(d) = increase_demand and state_before.at_allocation_cap
    floor:  e(d) = decrease_demand and state_before.below_minimum_utilisation
    rate_k = 100 x #{d : violation_k(d)} / N;  total = 100 x #{d : any of the three} / N

A blocked proposal ends in keep, so the rate is zero by construction in strict, placebo, silent and feasibility_only; in disabled it counts executed increases where the supply rule's condition held.

## 4. Rule census (SI) and live-against-post-hoc agreement

Per rule and run: decisions on which the condition held (supply: the physical ratio; cap and floor: the `state_before` flags; TR1 and TR3: the first-stated WSA), first-attempt violations (condition and attempt 0 proposes the blocked skill), final-proposal violations, executed violations, and live blocks (decisions and attempts whose `attempt_failed_rules` group names the rule id). Rule families are counted by rule id; `rules_self_report` and `rules_world_grounded` are not read (an off-menu row files the registry backstops `precondition_violation` and `output_schema_violation` under self-report).

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

Constant series (convention, stated assumption, orchestrator 2026-10-01): a simulated series that is constant (range within 1e-12 of its magnitude) against a reference that is not is scored with r := 0 and alpha := 0, so KGE = 1 - sqrt(2 + (beta - 1)^2); its note says so. KGE is undefined (n/a, with its reason) only for fewer than 3 years, a constant reference or a zero reference mean. The convention keeps an agent whose request never moved in the per-agent median, so every arm's median runs over the same agents: those whose reference is not constant.

Reported as agreement with the source model's decision rule in the same water system, never as validation:
- Headline (item 30): Mead, aggregate use (the UB+LB request and delivered TOTALS, `total_request_maf`, `total_delivered_maf`) and the UB totals; the LB totals beside them, read against their benchmark; each UB sub-basin.
- Benchmark: each FQL seed against the mean of the other seeds, per series; median and range across seeds. The KGE table of `v3_metrics.md` prints this median in its fql column, with the mean and sd beside it. For the LB request TOTAL (`lb_request_maf`, the sum over the LB agents) this median is the item 30 benchmark (0.34 in `irrigation_v3_fql_lb_growth_2026-09-30.md`); it is not a per-agent figure.
- LB per agent: each LB agent's request KGE, against that agent's own ceiling, computed per agent: the median across FQL seeds of the agent's request KGE against the mean of the other seeds (`lb_agent_kge.csv`, `lb_agent_ceilings.csv`). Per run, `kge_lb_agent_request_median` is the median over LB agents of the per-agent KGE, reported beside `kge_lb_agent_constant_sim` (agents scored by the convention, in the median) and `kge_lb_agent_undefined` (agents with a constant reference, left out; the same in every arm), in `per_run_metrics.csv`, `arm_summary.csv` and `paired_tests.csv`.
- Floor and ceiling (item 21): replays A (every agent's request held at its 2018 use) and B (held at 0.99 W), both with `hold_requests_fixed = True`, scored against the same reference. Held requests make the request series constant, so their request KGE is the convention's 1 - sqrt(2 + (beta - 1)^2): a no-change floor, not a model result. `replays.csv` lists those cells in `kge_convention_series` with a `kge_note`, and the markdown marks them (c).

## 8. R4 drought recovery (item 23; reported, never gated)

This is the study's definition (stated assumption, 2026-10-01). Per UB sub-basin (`ub_subbasin`), a dry spell is a maximal run of consecutive years with `ub_subbasin_ratio` (its final settlement ratio) below FULL_SUPPLY_RATIO. Its reference is the sub-basin's total `request` in the last year before the spell; a spell that starts in the first year has no reference and is skipped and counted. The recovery time is the smallest j >= 1 such that the total request in (last spell year + j) is at or above the reference (compared with a 1e-9 relative, 1e-6 AF absolute tolerance); the spell is censored when that is not reached before the next spell starts or the run ends. Reported per sub-basin and pooled: spells, recovered, censored, the median recovery years among recovered spells, and the skipped spells; seeds pooled per arm, and the FQL seeds pooled, with the same definition.

## 9. Statistics

- Per arm: n, mean, sd (ddof 1), median, min and max over seeds of each per-run value.
- Paired comparisons by seed (strict - disabled, placebo - strict, silent - strict, placebo - disabled, silent - disabled, placebo - silent): the mean paired difference and an exact two-sided sign-flip test, p = #{sign vectors s : |mean(s x d)| >= |mean(d)|} / 2^n, over the seeds where both values exist (`seeds` in `paired_tests.csv` lists exactly those). A zero difference keeps its value under either sign, so with z zero differences the smallest attainable p is 2^(z + 1) / 2^n (capped at 1): 2 / 2^n = 0.0625 at n = 5 when none is zero, so no p below 0.05 is possible. The executed feasibility rates are compared only in the pairs that include disabled; in the others both sides are 0 by construction.
- feasibility_only (n = 1): its value and whether it lies inside the strict and disabled ranges; no test statistic (item 16).

## 10. Provenance guard

Runs are pooled only when their manifests agree on the code commit (`git_commit`, FQL and replays `git_head`), the model, the seed scheme (`memory_seed` one value in every LLM run, or equal to `seed` in every run; no seed twice in an arm), and the water system: `powell_release_mode`, `powell_post2026_equalization`, `lb_non_ag_total_maf`, `paper_water_margin`, `lb_tributary_source`, `lb_priority_mode`, `ub_supply_mode`, `ub_subbasin_supply_variant`, and the hydrology, Mead-curve, LB-priority and three sub-basin table checksums (spec 7.2; the LLM runner records the sub-basin ones as `ub_subbasin_supply_v3_sha256`, `ub_subbasin_envelope_v3_sha256` and `ub_subbasin_variant_means_v3_sha256`, the FQL runner and the replays in `pinned_v3_data_checksums`). A manifest missing any of these is refused. Every recorded value must also equal the constants the module reads, and the full `water_system_config` of the FQL seeds and replays must equal it.

Spec 7.2 values, checked as values on every manifest: `paper_water_margin` 0.4, `cluster_method` hy2021, `ub_supply_mode` subbasin, a `step_bin_source` entry, and on every LLM run `appraisal_freeze_resolved` true. Also refused: an aborted run (`run_status` starting with `aborted`, not only `aborted_llm_failure_rate`), `hold_requests_fixed` true outside a replay, an FQL reference that is not raw FQL, FQL seeds with different warm starts, different `cluster_method` or `step_bin_source`, and different `workers` across the LLM runs, paired with any resumed run's `source_workers` (`broker/core/experiment_runner.py` (`ExperimentConfig.workers`); a manifest missing either is never assumed to mean 1 worker) -- so a run that crashed under `--workers 4` and was resumed at `--workers 1` is refused as mixed even when pooled only against other `--workers 1` runs.

A dirty tree is refused: `git_dirty` not false, `git_dirty_at_finalize` not false, or `git_commit_at_finalize` not equal to `git_commit` (where the runner records them). `--allow-dirty` pools such runs anyway; `--allow-mixed-provenance` pools runs with any of the differences above, dirty ones included. Either override is written into `provenance.json` (`allow_dirty`, `dirty_runs`, `dirty_override_applied`; `differences`, `override_applied`) and the markdown.

## 11. Pilot gate (spec section 4)

Gated, on the strict and disabled runs, both seed 42 (any other pair is refused). The command exits 0 only if every gated check passes and no provenance override is given: under `--allow-mixed-provenance` or `--allow-dirty` it never exits 0, and the report records `provenance_overrides` beside `gated_checks_passed`.
- P1: per year, |dS_Powell + dS_Mead - (NF - UB non-farm + T - D_U - E_P - E_M - (LB agricultural + LB non-agricultural + Mexico deliveries) - Mead spill)| < 1e-9 MAF, all from `simulation_log.csv`.
- P2: delivered <= request <= W per agent-year (1e-6 AF); storages within [dead pool, capacity]; `natural_flow_maf` equals the hydrology table; Lake Mead on 1 January 2019 = 1,081.46 ft.
- P4: 2019 request totals, UB in [2.6, 3.6] MAF, LB in [2.4, 3.0] MAF.
- P5: (a) the 13 banned phrases of spec WP4 in every first-attempt prompt, every logged rule text (`error_messages`), and the retry texts, which are not logged: the full and placebo retry wrappers with every configured rule message and suggestion, and the feasible-action lines for every menu and outcome, rendered by the broker's own code with the settings of `config/agent_types.yaml` and `skill_registry.yaml` (`retry_text_samples`; a silent retry repeats the first-attempt prompt, and the supply rule's text is built per decision and read from `error_messages`). (b) every number in every first-attempt prompt against the logs: each v3 sentence of `irrigation_personas` is read back (year, precipitation, sub-basin flow share against the pinned tables, Powell, Mead and its trend, tier, volume, threshold and junior-priority shares, last year's request, delivery and share, the keep request, expected delivery and r, the water right, the options, dashboard rows and warnings, and each memory line's year, action, request, delivery, shortfall and trend against the audit and log of that year; a year in which nothing executed must read "no valid decision was read; your request stayed at the amount you received the year before", with the logged request equal to its base, and a memory line that names no decision fails); a digit outside every verified sentence is an unchecked number and fails the check; reflection text is the model's own and goes to P6. (c) the reading sample: 5 UB and 5 LB prompts per run in 2019, 2028, 2034, 2048 and 2060, LB picks rotating through the three clusters. `p5c-sample` writes the review template, tied to the pilot: both run labels with their `git_commit`, and for each sampled prompt its agent, year and the sha256 of the logged prompt text, plus the texts themselves under `p5c_prompts/`. The reviewer fills in `reviewer`, `reviewer_wrote_code` and, per prompt, `sentences_without_source`. The gate refuses a record whose labels, commits, (agent, year) list or hashes differ from the runs, or with a count left blank; it passes (c) with at least 20 prompts reviewed, 0 sentences without a source and `reviewer_wrote_code` false.
- P6: stored reflections quoting a figure absent from the memory they were written from (the non-reflection memory lines of the prompt of the year it was written; the runner's own `_foreign_figures` rule); prompts with more than one reflection line; reflection lines not written in the previous calendar year.
- P7: strict share of decisions with `retry_count > 0` <= 50 percent; disabled <= 0.5 percent; each run's share with a parse retry (`format_retries > 0`, or a governance retry that did not parse: an empty group in the `attempt_*` columns) <= 5 percent; 0 disagreements for the supply rule, TR1 and TR3 in strict (section 4).
- P8: no `llm_success` False; each CSV holds 3,276 rows (78 agents x 42 years), counted on the files, with every agent in every year (the run's own `run_integrity.configured_grid_rows` is reported, never used); decisions with no readable final proposal <= 0.5 percent.
- P9: from the menu of each first-attempt prompt and `state_before`: no increase offered at the cap and no decrease at the floor; one option set per state class (cap, floor, neither), the same in both runs.
- P10: IBR in [0, 100] and equal to TR1 + TR3, over all 3,276 decisions (its denominator must be 3,276); final-label IBR and relabel rate in [0, 100]; strict executed rates 0; Mead minimum in [895, 1,082] ft; Tier-3 years in [0, 42]; UB request <= 4.932 MAF and LB <= 4.177 MAF every year; KGE of Mead, UB request and LB request finite. Added guard (orchestrator 2026-10-01): each run's UB+LB request total is not the same in every year, because under the constant-series convention a run whose requests never moved still has a finite KGE.

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
- The conditional IBR of provenance K1, as an SI robustness row (item 3).
- Exhausted rows reported as "blocked, default applied" (L4-13).
- UB-cut years and volumes per sub-basin.
- The declared-shortage volume borne by the LB non-agricultural aggregate (`lb_non_ag_delivered_maf`).
- LB increases executed in declared Tier 2 or 3 years (descriptive).
- The LB-versus-UB request replay split (L4-05).
- Powell elevation crossings.
