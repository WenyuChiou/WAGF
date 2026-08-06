# When Guardrails Change What Gets Counted: Conformance Metrics with Agent-Reported Rule Conditions

## Abstract

Runtime guardrails check proposed actions and ask language-model agents to retry when they break a rule.
Evaluations often summarize this effect with a conformance rate.
However, this rate becomes difficult to interpret when the rule condition is written by the agent in the response being judged.
Blocking a response can change both the final action and which decisions satisfy the condition used by the metric.
This mechanism does not require deception.
Some rules read an agent-reported condition, while others read simulator-recorded state.
We study this distinction on paired runs with and without validators.
We evaluate {{CLAIM:n_model_configs}} model configurations across two agent testbeds.
The primary rate counts demand increases among decisions reporting high scarcity.
This group is a superset of the rule's full high-scarcity and high-coping condition; we report the full conjunction separately.
In the anchor configuration, the no-validator-minus-validator contrast is {{CLAIM:anchor_high_delta_bare}} for high-scarcity prevalence and {{CLAIM:anchor_cond_delta_bare}} for the conditional increase rate.
A descriptive reweighting to a common simulator-recorded world-state distribution leaves {{CLAIM:world_residual_coarse}} at {{CLAIM:world_coverage_coarse}} coverage and {{CLAIM:world_residual_finest}} at the finest stratification.
Because that world state is downstream of enforcement, this is not a causal adjustment.
It is consistent with a large composition contribution, but does not rule out a within-world reporting effect.
On gemma3:1{{CLAIM:year1_divergence_year}}b, the conditional gain {{CLAIM:b12_cond_delta_bare}} becomes {{CLAIM:b12_uncond_delta}} over a design-fixed denominator on {{CLAIM:retry_budget}} seeds.
Replacing the agent-reported condition with a world-state condition does not remove the feedback problem.
We recommend reporting condition prevalence in both arms beside every conformance rate.
We also recommend logging the independent world state behind an agent report when it exists.

## 1 Introduction

Conformance metrics for large language model (LLM) agents can be misleading when enforcement changes the condition used for scoring.
LLMs are commonly paired with runtime guardrails.
A validator checks a proposed action against rules.
It identifies any broken rule and asks the agent to retry [1--4].
A conformance rate measures how often the agent follows the rule with validators compared to without them.
This loop also builds on earlier work on machine-readable norms and agent institutions [5--8].
This rate is only informative if both conditions count comparable decisions.
When the condition used by the metric is written by the agent in the response being judged, enforcement can change the condition itself.

Consider an irrigation agent that proposes increasing water demand while reporting high water scarcity.
A validator can block this response and ask for a retry.
The validator changes the final response, and the final response changes which records enter the rate's denominator.
For example, if the evaluation only counts increases among decisions that report high scarcity, a blocked response might be retried with a different report.
This changes both the recorded action and the set of decisions the metric counts.
Figure 1 previews this measurement path.
We observe the recorded response, not the agent's hidden intent.

This feedback loop connects to broader work on evaluation and construct validity [12--14].
Our setting highlights a specific version of this problem.
Because the condition used by the rule is written by the agent, enforcement affects the condition.

This problem also relates to treatment-affected variables.
In agentic code repair, a variable observed after an intervention can be affected by that intervention [9, 10].
Causal-methods work warns against treating such a variable as an independent control.
Some settings can address this issue by branching from a frozen external state.
However, an agent-reported condition has no independent version outside the response being evaluated.
Freezing the original report would remove the behavior that the rule is intended to evaluate.

We ask three questions.
First, does enforcement change how often the agent reports the condition, as well as the rate computed among those reports?
Second, how much of the change in the anchor configuration is descriptively associated with different simulator-recorded world states?
Third, which additional statistics remain interpretable when a rate over every decision is available?

We make three contributions.
First, we identify a construct-validity failure mode for runtime guardrail evaluation.
When a rule condition is written by the agent, enforcement can change both the response and the set of responses used to score it.
Second, we demonstrate this failure mode in paired simulations across two agent testbeds.
We separate rules that read agent reports from rules that read simulator-recorded state.
Third, we provide a reporting protocol.
This protocol pairs the conditional rate with condition prevalence, an independent world-state record, and a rate over every decision.
Our claims are descriptive.
We do not claim that agents deceive or that recorded-world reweighting is a causal adjustment.
We also do not claim that the pattern applies to every model or governance stack.
Section 2 defines the guardrail loop and the paired simulation design.

<!-- FIGURE 1 -- figures/fig0_problem_schematic.pdf -->

**Figure 1.** How an agent-reported condition changes what a metric counts. One response contains an action and a reported state. The validator reads the report to decide whether to block. The metric reads the same report to select decisions for the rate. A blocked response may be retried, producing a different recorded response. High scarcity is an illustrative irrigation label. This is a conceptual example, not a data figure.

## 2 Experimental Setup

Both testbeds run the same guardrail loop.
In each generation, the agent returns an action and two agent-reported conditions about its situation.
Validators check the proposal against those reports and against the simulator's recorded state.
A world state is the condition of the environment recorded independently by the simulator.
An ERROR-level violation returns the broken rule and asks for another answer, up to three attempts.
After that, a domain default executes.

The rule under study forbids an increase in demand when the agent reports both high water scarcity and high coping capacity.
Both labels are written by the agent in the generation being judged.
We use the scarcity label as the primary conditioning variable.
It is a marginal proxy, meaning it contains every decision satisfying the full condition while also including decisions with low coping.
Table 1 reports the coping label and the full conjunction separately.
The full conjunction is the combination of both high scarcity and high coping.

Irrigation is the primary testbed.
It features 78 farm agents over 42 years, {{CLAIM:decisions_per_run}} decisions per run, and a two-part theory of scarcity and coping.
It includes {{CLAIM:n_seeds}} actions and a water right capping what any agent may withdraw.
A reservoir is coupled to those withdrawals.
An action in one year changes the state the next year's decision sees.
Flood is the second testbed.
It uses Protection Motivation Theory [11] over {{CLAIM:flood_action_count}} actions on the same loop.
It is a portability demonstration with no action-to-environment feedback and no standing as a control for enforcement pressure.

The corpus holds nine model configurations from {{CLAIM:model_scope}}.
Each configuration has validator-on and validator-off runs.
All nine configurations appear in flood, and {{CLAIM:irrigation_action_count}} appear in irrigation, giving fourteen model/testbed cells.
The two arms are paired within a cell, with five seeds in most cells and fewer in two irrigation cells.
Table 1 reports *n*.

## 3 Rule Inputs: Agent-Reported vs. World-Recorded

We must separate rules that read the agent's report from rules that read world-recorded state before interpreting the conditional rate.
World-feasibility rules use state recorded by the simulator and not written by the agent, such as a water-right allocation cap.
Other rules use the scarcity and coping labels written in the same response as the action.

We isolate the agent-reported subset in the anchor cell, which has five seeds and {{CLAIM:anchor_arm_n}} decisions per arm.
Without validators, {{CLAIM:novrej_pct}} of decisions are rejected.
All {{CLAIM:novrej_count}} are bare precondition failures, so no validator rule is evaluated.
With validators, {{CLAIM:govrej_pct}} are rejected.
All {{CLAIM:govrej_count}} name a validator rule, and none is a bare precondition failure (Figure 2a).
The split is exact in {{CLAIM:rule_purity}} irrigation model-arm cells (Figure 2b).
Governed rejection rates span {{CLAIM:govrej_range}} and validator-off rates span {{CLAIM:novrej_range}}, pooled across seeds.

This separation does not mean that every governed rejection reads the agent's report.
The validator stack carries both kinds of rules.
Among the 6,469 with-validator rejections, {{CLAIM:appraisal_conditioned_pct}} name at least one rule whose condition uses the reported state.
The remaining {{CLAIM:world_conditioned_pct}} use only world-recorded conditions.
Figure 2a shows why the denominators must be read carefully.
The outer rows contain all decisions, while the middle row re-bases only the 6,469 with-validator rejections.
It is not a third arm.
The rest of the paper concerns the agent-reported subset, not the full rejection rate.

The water-right precondition still binds without validators and applies to the same increase action that the conditional rate counts.
It is attached only to the two increase skills.
The {{CLAIM:novrej_increase_pct}} share of validator-off rejections that are increase proposals (Figure 2c) follows from the configuration rather than from behavior.
This effect is large only in the anchor cell.
With validators off, {{CLAIM:atcap_noval_pct}} of agent-years are at or above 99% of the water right, compared with {{CLAIM:atcap_gov_pct}} with validators on.
The other four configurations reject {{CLAIM:novrej_range_excl_anchor}}, so the large-rejection statement is limited to the anchor cell.

The two layers also block different actions.
Across the five irrigation configurations, {{CLAIM:govrej_increase_pct}} of validator-on rejections are increase proposals.
Meanwhile, {{CLAIM:govrej_decrease_pct}} are decrease proposals; the world layer has no precondition for decrease.
The agent-reported layer is therefore the part whose rule condition is written by the agent.
The next section asks whether that condition changes across validator arms.

<!-- FIGURE 2 -- figures/fig1_rule_layers.pdf -->

**Figure 2.** Rule-layer decomposition and proposed actions across five LLM configurations in irrigation. In the panel labels, *blocked* denotes a rejected proposal and *passed* an approved one. The *water-right cap* is a bare allocation-cap failure reached before any validator rule runs. A rule that *reads self-report* uses an agent-reported condition. A rule that *reads world state* uses simulator state only. Panel a is the anchor cell, gemma3:4b, five seeds. Its outer rows contain all 16,380 decisions per arm. The middle row contains only the 6,469 validator-on rejections, re-based to show their causes. Panel b shows the same separation across all five models, exact in 10/10 model-arm cells. Panel c shows proposed actions by blocking rule kind, pooled over the five models. The near-total *proposed increase* share under the water-right cap follows from the configuration, not from behavior (§3). *Unparsed proposal* is under half a percent of blocks everywhere and carries no claim. The increase/decrease split in the text uses all validator-on blocks; panel c uses a separate denominator within each rule type. Counts are pooled across seeds, so this is a decomposition rather than a paired contrast and no confidence intervals are attached.

## 4 Enforcement Changes the Reported Condition

We examine if enforcement changes the condition itself, which could skew the rate.
The reported condition changes more than the rate it supports.
In the anchor cell, the high-scarcity contrast is {{CLAIM:anchor_high_delta}} against {{CLAIM:anchor_cond_delta}} for the conditional increase rate.
High scarcity appears in {{CLAIM:anchor_high_gov}}% of governed decisions and {{CLAIM:anchor_high_nov}}% of no-validator decisions.
Among those decisions, the increase rate is {{CLAIM:anchor_cond_gov}}% and {{CLAIM:anchor_cond_nov}}%, respectively.
Without the prevalence, a changed rate could mean fewer increases, a different set of counted decisions, or both.

The coping report moves too, so the scarcity label alone does not describe the full rule condition.
Coping is reported high in {{CLAIM:anchor_cope_gov}}% of governed anchor decisions and {{CLAIM:anchor_cope_nov}}% without validators.
This is a contrast of {{CLAIM:anchor_cope_delta}}.
The full condition appears in {{CLAIM:anchor_conj_gov}}% and {{CLAIM:anchor_conj_nov}}% of the two arms.
This represents a contrast of {{CLAIM:anchor_conj_delta}} and a conditional gap of {{CLAIM:anchor_conj_rate_gap}}.
A second enforced rule, defined by very low reported scarcity on a disjoint set, moves {{CLAIM:anchor_r2_delta}}.

The anchor cell is not special.
Every irrigation cell moves the same way, ranging {{CLAIM:irrigation_high_delta_range}} across the five, with *p* < 0.05 in all five.
The nine flood cells show {{CLAIM:flood_high_delta_range}} pp, mostly null.
There are {{CLAIM:flood_positive_count}} positive cells and one significant cell (gemma4:26b, {{CLAIM:flood_sig_cell}}).
Rejection pressure also differs.
Governed irrigation decisions are rejected at {{CLAIM:gov_rej_range_irrigation_perseed}} on the Table 1 per-seed-mean basis.
Flood pressure ranges {{CLAIM:flood_pressure_range}}, where the no-validator arm rejects {{CLAIM:flood_pressure_noval}}.

We use flood as a portability demonstration, not as a control for enforcement pressure.
The regime is confounded with the testbed, and the two testbeds differ in feedback and reporting instrument.
The near-null flood shifts only show that the direction is not universal across the second testbed.
They do not isolate a model-family or instrument effect.

**Table 1.** Agent-reported high-scarcity prevalence and the increase rate among those decisions, for both arms across fourteen model-testbed cells. HIGH is the share of a run's decisions whose reported water-scarcity condition is high or very high. It contains every decision satisfying the full two-part rule condition, but also includes decisions with low coping. The conditional rate is the share of HIGH decisions whose recorded action was a demand increase; it is not a norm-violation rate. On and off mean with and without validators, and Delta means off minus on, so a positive value means that validators lowered the quantity. Cells are per-seed means using the LAST-PROPOSED reading, which is the agent's final answer. The seed is the inferential unit and df = *n* - 1. The nine flood cells share one line and carry no conformance rate.

| testbed | model | *n* | HIGH, on | HIGH, off | Δ HIGH | cond., on | cond., off | Δ cond. |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| irrigation | gemma3:4b | 5 | 37.08 | 82.80 | **+45.73** | 36.05 | 59.07 | **+23.02** |
| irrigation | gemma3:12b | 3 | 5.49 | 26.76 | **+21.27** | 5.45 | 16.89 | **+11.44** |
| irrigation | gemma4:e2b | 5 | 18.26 | 65.79 | **+47.53** | 12.71 | 31.65 | **+18.94** |
| irrigation | gemma4:e4b | 5 | 45.27 | 88.65 | **+43.38** | 23.{{CLAIM:world_min_cell_finest}} | 41.08 | **+17.41** |
| irrigation | ministral3:8b | 3 | 13.56 | 44.69 | **+31.13** | 3.25 | 6.05 | **+2.80** |
| flood | 9 cells | 5 | — | — | −3.66 to +6.24 | — | — | — |

## 5 What Recorded-World Reweighting Can and Cannot Show

We investigate whether the reported condition changes because the actual world state changes.
On the anchor cell, descriptive reweighting shows that much of the change in the reported condition follows the arms' different simulator-recorded worlds.
The relevant variables—shortage tier, reservoir elevation, and drought index—are written by the simulator, not by the response.
They can be used for a post hoc descriptive comparison.
They are independent of the current response, but not independent of enforcement.
Governance changes the reservoir and therefore the distribution of world states.
This analysis is consequently descriptive, not a causal adjustment.

Reweighting both arms to a common world-state distribution leaves residuals that are small relative to the raw +45.73 pp gap.
However, they are not uniformly zero.
Reweighting by shortage tier leaves -2.53 pp across 100% of the anchor corpus.
The finest reported stratification leaves +0.21 pp across {{CLAIM:world_coverage_finest}} of the corpus.
No reported resolution produces a residual larger than {{CLAIM:world_residual_max}}.
These results are consistent with a large composition contribution.
They do not show that the agent would give the same report in an identical world.

Table 2 gives the reweighting ladder, with a count and interval at every rung.
A stratum enters only if it holds 40 decisions in each arm, so coverage falls as the strata become finer.
The finest rung covers just under half of the corpus, and its smallest comparable cell holds 67 decisions.
Two of the four intervals exclude zero, both below it.
The governed arm reports more scarcity within those strata.
This is inconsistent with treating the raw shift as purely a reporting effect.
It does not identify a within-world behavioral mechanism.

**Table 2.** Reported high-scarcity prevalence after stratification on simulator-recorded world state. The anchor cell has five paired seeds and a raw shift of **+45.73 pp** before reweighting. Residual = no-validator minus with-validators in prevalence, in percentage points, after both arms are reweighted to the pooled stratum distribution. Reweighting on either arm's own distribution instead moves the residual by at most {{CLAIM:world_weighting_swing}}. *n* is the smallest and largest per-arm cell on the rung. The last column recomputes the residual within each seed and takes a paired interval, df = 4. Curtailment ratio is collinear with tier and adds no stratum.

| recorded-world stratification | strata | n per stratum | coverage | residual | per-seed mean (95% CI) |
|---|---:|---:|---:|---:|---:|
| shortage tier | 4 | 858–12,558 | 100.0% | −2.53 | −3.12 (−5.56, −0.68) |
| tier + Mead elevation, 25 ft | 7 | 78–4,602 | 81.9% | −4.47 | −4.95 (−8.29, −1.62) |
| tier + Mead 10 ft + drought decile | 19 | 78–1,326 | 50.5% | +0.57 | −0.53 (−4.32, +3.25) |
| tier + Mead + drought + agent cluster | 19 | 67–1,139 | 43.4% | +0.21 | −0.87 (−4.94, +3.19) |

The reweighting tracks where each arm spends its run.
The governed arm takes {{CLAIM:tier0_gov_share}} of its decisions in shortage tier 0, where no shortage is declared.
The no-validator arm takes {{CLAIM:tier3_noval_share}} in tier 3, which represents severe shortage.
The two arms occupy different worlds.
This comparison does not show that they would produce the same report in an identical world.

The reservoir explains the observed world-state difference (Figure 3b).
The governed arm ends {{CLAIM:reservoir_final_gap}} higher on Lake Mead, with an average gap of {{CLAIM:reservoir_mean_gap}} over 42 years.
The no-validator arm first touches the 895 ft floor in year {{CLAIM:noval_floor_years}} in all five seeds.
The governed arm does so in none.
This divergence is an observed consequence of the coupled guardrail loop.
The data do not identify whether the size of the reporting change scales with the size of the world-state change.

Two further comparisons are consistent with this account.
At year 1, the two arms' worlds are identical on all nine pre-decision columns across {{CLAIM:year1_matched_pairs}} matched anchor pairs.
They first disagree at year 2, and the year-1 prevalence shift is {{CLAIM:year1_high_delta}}, a null (Figure 3a).
Retry pressure is already high in year 1.
In year 1, {{CLAIM:year1_retried_pct}} of governed decisions are rejected and retried at least once, compared with {{CLAIM:allyears_retried_pct}} across all 42 years.
Also, {{CLAIM:year1_exhausted_pct}} reach the end of the retry budget.
The year-1 contrast is not distinguishable from zero.
The gap is not monotone after year 1 either: {{CLAIM:postyear1_reversals}}, and years 2 to 11 are mixed in sign.
These per-year tests are descriptive checks across correlated years, not multiplicity-adjusted confirmatory claims.

As a descriptive sensitivity check, the never-retried stratum has a larger rather than smaller shift in {{CLAIM:neverretried_larger_cells}} irrigation cells (Figure 3c).
In the anchor cell, the shift is {{CLAIM:neverretried_delta_anchor}}, compared with +45.73 pp over all decisions.
Pooled over 21 paired seeds, it is {{CLAIM:pooled_neverretried_delta}} compared with {{CLAIM:pooled_alldecisions_delta}}.
This comparison cannot separate world composition from treatment-affected selection because the two arms are filtered differently.
The larger contrast is compatible with selection as well as world composition, so it is not evidence that selection is irrelevant.
The stratum is also unbalanced.
{{CLAIM:neverretried_share_gov}} of governed decisions are never retried, compared with {{CLAIM:neverretried_share_noval}} of no-validator decisions.
One quantity remains unobserved: the reported condition on a governed decision that was retried and then approved (§8).

<!-- FIGURE 3 -- figures/fig2_mechanism.pdf -->

**Figure 3. World-state divergence and the agent-reported scarcity gap.** Panels a and c plot the gap in the share of decisions carrying a high or very high agent-reported scarcity condition, no-validator minus validator-on, in percentage points. A positive value means that validators lowered the share. *Never blocked* denotes decisions with no rejection, no retry, and retry count zero. *Nonmonotone* means that the gap changes direction over time. Panel a plots the gap by year over 42 simulated years, with a 95% confidence band across seeds. At year 1 the two arms' worlds are identical on all nine pre-decision columns and the gap is {{CLAIM:year1_high_delta_bare}}, a null. The significant reversals in years 4 and 7 are marked. Panel b plots Lake Mead elevation for each arm, not a gap. Its band is the per-seed min-max range, not a confidence interval. The 895 ft floor is reached by the no-validator arm in every seed and by the governed arm in none. Panel c compares the gap over all decisions with the gap in the never-blocked stratum for five irrigation configurations, pooled over 21 paired seeds. Panels a and b show the anchor cell (gemma3:4b, irrigation), five paired seeds.

## 6 Changing the Denominator Changes the Estimate

We compare the conditional rate with a rate over a fixed set of decisions.
An estimand is the statistical quantity being estimated.
Recomputed over 3,276 decisions per run in both arms, the fixed-denominator contrast changes in every irrigation cell.
It is smaller in four cells, nearly zero on gemma3:12b, and reverses sign on ministral3:8b (Figure 4).

On the anchor cell, the contrast is +23.02 pp when conditioned on high scarcity and {{CLAIM:anchor_uncond_delta_bare}} over every decision.
This represents a difference of {{CLAIM:anchor_gap}}.
The two gemma4 cells also change.
Gemma4:e2b moves from {{CLAIM:e2b_cond_delta}} to {{CLAIM:e2b_uncond_delta}}, and gemma4:e4b moves from {{CLAIM:e4b_cond_delta}} to {{CLAIM:e4b_uncond_delta}}.

On gemma3:12b, the conditional contrast changes from {{CLAIM:b12_cond_delta}} to +0.16 pp (95% CI -13.92, +14.25; p = 0.965).
This uses the LAST-PROPOSED action reading from the published statistics.
Substituting the executed action on rejected rows moves the same fixed-denominator contrast to {{CLAIM:b12_uncond_exec_delta}}.
The reported condition changed, but this corpus does not establish a change in the increase rate over a fixed denominator.
A reader given only the conditional number could infer a behavior change that this comparison does not identify.

On ministral3:8b, the two statistics disagree in sign.
The conditional rate is {{CLAIM:ministral_cond_delta}}, while the unconditional is {{CLAIM:ministral_uncond_delta}}, on three paired seeds at df = 2.
The conditional interval is wider than the effect it brackets and clears zero by less than the second decimal.
This cell supports the reversal between estimands, not the conditional result itself.

A fixed denominator permits an external reference that the conditional rate cannot use.
The irrigation action set holds {{CLAIM:action_set_shape}}, so a uniformly random agent would propose an increase on {{CLAIM:uniform_null}} of decisions.
Without validators, the unconditional rate is far above that null ({{CLAIM:anchor_uncond_nov}}, {{CLAIM:nov_null_t}}, 95% CI {{CLAIM:nov_null_ci}}).
With validators, we do not reject comparison with the null ({{CLAIM:anchor_uncond_gov}}, {{CLAIM:gov_null_t}}, 95% CI {{CLAIM:gov_null_ci}}).
No equivalent reference exists for the conditional rate because its denominator is written by the evaluated process.
The null is weak and bounds the direction only.
A marginal rate at chance means no net pull toward increases, not that governed behavior is random.

<!-- FIGURE 4 -- figures/fig3_consequence.pdf -->

**Figure 4.** Changing the denominator changes the measured contrast. Each irrigation cell shows two estimates: solid bars give the rate among decisions where the agent reports high scarcity, while hatched bars give the rate over every decision. The y axis is no-validator minus validator-on, in percentage points, so a positive value means that validators lowered the rate. Whiskers are two-sided 95% confidence intervals from paired *t*-tests on per-seed gaps, df = *n* - 1, with the seed as the inferential unit. *n* appears under each model. The action reading is LAST-PROPOSED throughout. In the shaded gemma3:12b cell, the fixed-denominator estimate is +0.16 pp. Using the executed action on rejected rows moves it to +27.82 pp (p = 0.004). This is an existence proof tied to that action reading, not a general finding. The difference between estimands is descriptive, not causal, and the all-decision rate is not a corrected effect size.

## 7 Reporting Protocol

A world-state condition is not an automatic repair, so we tested this alternative on the anchor cell.
Replacing the agent report with a simulator-recorded condition also changes the counted condition.
Shortage tier 2 or worse shifts {{CLAIM:world_tier2_shift}} against the agent-reported conjunction's +45.73 pp.
Tier 1 or worse and a nonzero curtailment ratio each shift {{CLAIM:world_tier1_curtail_shift}}.
A drought index at or above 0.5 shifts {{CLAIM:world_drought_shift}}.
The simulator records these variables outside the response, which makes the reweighting in Section 5 possible.
However, governance changes the world through the irrigation feedback loop.
The alternative condition is different, not unaffected.

Three reporting requirements follow.
First, report the condition's prevalence in both arms beside every conformance rate.
Second, log the independent world state behind an agent report when it exists.
Third, when the design fixes a denominator, report that all-decision rate beside the conditional rate as a different estimand.
Without the world record, a deployment that logs only rule fires, retries, and outcomes cannot recover the descriptive decomposition later.

## 8 Limitations and Missing Tests

An accepted report after a retry is selected by the rule that judged it.
This stratum is {{CLAIM:acceptance_selection_pct}} of governed decisions, and its first attempt is absent from the shipped corpus.
Three checks found no first-attempt record.
The never-retried stratum is not a bound on this missing quantity.
No report there was rewritten, but the two arms are filtered differently.

Finer stratification trades coverage for resolution.
The finest rung covers 43.4%, compared with 100% for the coarse rung.
The corpus covers three open-weight families from 3B to 27B, no frontier models, and flood-only size endpoints.
Whether the finding is architectural rather than a capability limit is untested.
Regime is confounded with testbed, so inference is within irrigation.
One no-validator run used a later code revision and labels the same precondition differently.
No rate depends on that label.
Flood has three provenance defects: denominator coverage is {{CLAIM:flood_coverage_range}} by design, manifest seeds disagree in {{CLAIM:flood_manifest_disagree}} when paired by run index, and one governed gemma3:4b run used a shorter prompt.
None bears on irrigation.

Two missing arms would settle the remaining ambiguity.
Log the first-attempt report before retry, and run enforcement with the environment pinned to the untreated trajectory.
Neither exists here.
This is one guardrail stack with a nondeterministic backend, so comparisons are aggregates over *N* seeds.

## 9 Conclusion 

In a guardrail loop with environmental feedback, an agent-reported rule condition can change both the recorded response and the decisions used to score it.
Our irrigation results show why a changed conditional rate is not enough to establish a change in the behavior being measured.
Report condition prevalence, preserve an independent world-state record, and show an all-decision rate when the design provides one.

## Artifact availability 

On acceptance we will release code, configurations, manifests, and the inventory; one command regenerates tables/figures without GPU or network. Of 42 identifying runs, 27 have enriched and 15 minimal manifests; dirty or missing hashes prevent clean source-run reproduction for every run. This is a descriptive audit, not a bitwise-reproducible benchmark.

## References 

<!-- BIBLIOGRAPHY:BEGIN -- generated by make_bibliography.py from references.bib; do not hand-edit -->
[1] Haoyu Wang, Christopher M. Poskitt, and Jun Sun. AgentSpec: Customizable Runtime Enforcement for Safe and Reliable LLM Agents. In Proceedings of the 48th IEEE/ACM International Conference on Software Engineering (ICSE 2026), 2026. arXiv:2503.18666.

[2] Traian Rebedea, Razvan Dinu, Makesh Narsimhan Sreedhar, Christopher Parisien, and Jonathan Cohen. NeMo Guardrails: A Toolkit for Controllable and Safe LLM Applications with Programmable Rails. In Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing: System Demonstrations, pages 431–445, 2023. Association for Computational Linguistics. doi:10.18653/v1/2023.emnlp-demo.40. arXiv:2310.10501.

[3] Seongjae Kang, Taehyung Yu, and Sung Ju Hwang. PolicyGuard: A Dialogue-Grounded Sub-Agent Verifier for Policy Adherence in LLM Agents. Preprint, 2026. arXiv:2606.29225.

[4] Wenhao Yuan, Chenchen Lin, Jian Chen, Jinfeng Xu, Xuehe Wang, and Edith Cheuk Han Ngai. Verify Before You Commit: Towards Faithful Reasoning in LLM Agents via Self-Auditing. In Proceedings of the 64th Annual Meeting of the Association for Computational Linguistics (ACL 2026), 2026. arXiv:2604.08401.

[5] Davide Grossi, Huib Aldewereld, and Frank Dignum. Ubi Lex, Ibi Poena: Designing Norm Enforcement in E-Institutions. In Coordination, Organizations, Institutions, and Norms in Agent Systems II (COIN 2006, Revised Selected Papers), Lecture Notes in Computer Science, pages 101–114, 2007. Springer. doi:10.1007/978-3-540-74459-7_7.

[6] Marc Esteva, Bruno Rosell, Juan A. Rodríguez-Aguilar, and Josep Lluís Arcos. AMELI: An Agent-Based Middleware for Electronic Institutions. In Proceedings of the Third International Joint Conference on Autonomous Agents and Multiagent Systems (AAMAS 2004), pages 236–243, 2004. IEEE Computer Society. doi:10.1109/AAMAS.2004.10060.

[7] Virginia Dignum. A Model for Organizational Interaction: Based on Agents, Founded in Logic. PhD thesis, Utrecht University, 2004. SIKS Dissertation Series. Introduces the OperA model. https://dspace.library.uu.nl/handle/1874/890

[8] Jomi Fred Hübner, Jaime Simão Sichman, and Olivier Boissier. A Model for the Structural, Functional, and Deontic Specification of Organizations in Multiagent Systems. In Advances in Artificial Intelligence: 16th Brazilian Symposium on Artificial Intelligence (SBIA 2002), Lecture Notes in Computer Science, pages 118–128, 2002. Springer. Introduces the MOISE+ model. doi:10.1007/3-540-36127-8_12.

[9] Xueping Gao, Jianwei Yang, and Qiang Yang. Looping Is Not Reliability: State-Bound Evidence and Typed Revision Contracts for Agentic Code Repair. Preprint, 2026. arXiv:2607.24604.

[10] Paul R. Rosenbaum. The Consequences of Adjustment for a Concomitant Variable That Has Been Affected by the Treatment. Journal of the Royal Statistical Society, Series A (General), 147(5):656–666, 1984. doi:10.2307/2981697.

[11] Ronald W. Rogers. A Protection Motivation Theory of Fear Appeals and Attitude Change. The Journal of Psychology, 91(1):93–114, 1975. doi:10.1080/00223980.1975.9915803.

[12] Andrew M. Bean and others. Measuring what Matters: Construct Validity in Large Language Model Benchmarks. In 39th Conference on Neural Information Processing Systems (NeurIPS 2025) Track on Datasets and Benchmarks, 2025. arXiv:2511.04703.

[13] Sayash Kapoor, Benedikt Stroebl, Zachary S. Siegel, Nitya Nadgir, and Arvind Narayanan. AI Agents That Matter. Preprint, 2024. arXiv:2407.01502.

[14] Yao Liu, Tien-Ping Tan, and Zhilan Liu. Charge as a Construct-Validity Factor in Chinese Legal Case Retrieval: A Cross-Benchmark Audit. Preprint, 2026. arXiv:2606.12993.

<!-- BIBLIOGRAPHY:END -->
