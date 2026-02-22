# Nature Water — Section 2: Results (v13 — A1 ablation added, table renumbering)
## Date: 2026-02-22 | Word count: ~2300 | Analysis format
## Restructure: irrigation-first → water outcomes → rule-based comparison → flood cross-domain

---

## Results

### Institutional constraints widen behavioural diversity under chronic drought

To test whether institutional constraints widen or suppress behavioural diversity, we first examine the irrigation domain, where the governance effect is unambiguous. Seventy-eight agents representing Colorado River Simulation System (CRSS) demand nodes managed continuous water-allocation decisions over 42 years, choosing among five actions (increase large, increase small, maintain, decrease small, decrease large) in each annual decision round. We conducted a two-condition ablation with three random seeds each (n = 3 governed, n = 3 ungoverned; 78 agents x 42 years = 3,276 agent-year observations per seed). Governed agents used 12 active validators enforcing mass balance, institutional eligibility, and temporal consistency; ungoverned agents used identical personas with validators disabled.

Governed agents exhibited higher decision diversity than ungoverned agents across all three independent seeds (Table 1). Effective Heterogeneity Entropy (EHE; see Methods) averaged 0.738 +/- 0.017 (governed) versus 0.637 +/- 0.017 (ungoverned), a mean difference of +0.101 (bootstrap 95% CI [0.078, 0.122], 10,000 resamples). Zero distributional overlap was observed: the lowest governed EHE (0.720, seed 44) exceeded the highest ungoverned EHE (0.655, seed 42). Ungoverned agents exhibited behavioural collapse, concentrating 77-82% of decisions on demand increases with no decrease_large actions in two of three seeds; governed agents maintained all five skill types across all seeds.

The first-attempt analysis confirmed that this effect is not a retry artefact: governed first-attempt EHE (0.761 +/- 0.020) exceeded ungoverned first-attempt EHE (0.640 +/- 0.017), indicating that agents operating within a governance architecture produce more diverse proposals even before any rejection feedback. Tracing each decision through the governance filter revealed that 39.5% of governed proposals were rejected by institutional rules, with 61.9% requiring at least one retry but only 0.7% triggering fallback to a default action. The Behavioural Rationality Index (BRI) — the fraction of decisions where agents facing high water scarcity did not increase demand — was 58.0% under governance versus 9.4% without, compared with a null-model expectation of 60% under random action selection (3 of 5 skill types are non-increase). Governance removes the systematic increase-bias of ungoverned agents without imposing prescriptive structure.

**Table 1. Behavioural diversity, decision quality, and water-system outcomes (irrigation ablation, Gemma-3 4B, 78 agents x 42 years, 3 runs).**

| Metric | Governed | Ungoverned | Difference |
|--------|----------|------------|------------|
| Behavioural diversity (EHE) | 0.738 +/- 0.017 | 0.637 +/- 0.017 | +0.101 |
| Behavioural Rationality Index, BRI (%) | 58.0 | 9.4 | +48.6 pp |
| Mean demand ratio | 0.394 +/- 0.004 | 0.288 +/- 0.020 | +0.106 |
| 42-yr mean Mead elevation (ft) | 1,094 | 1,173 | -79 |
| Demand-Mead coupling (r) | 0.547 +/- 0.083 | 0.378 +/- 0.081 | +0.169 |

*Three independent runs (seeds 42, 43, 44); zero distributional overlap across seeds. Bootstrap 95% CI for EHE difference: [0.078, 0.122] (agent-timestep level, 10,000 resamples). BRI = fraction of decisions where agents facing high scarcity chose not to increase demand (higher = more appropriate; null expectation under uniform random selection = 60%, since 3 of 5 actions are non-increase). Demand ratio = requested volume / historical baseline allocation. Demand-Mead coupling = Pearson r between annual Lake Mead elevation and annual mean demand ratio; positive r indicates agents reduce demand during drought and increase demand when water is abundant.*

### Behavioural diversity reshapes water-system trajectories

The diversity difference between governed and ungoverned agents translates into distinct water-system outcomes over the 42-year simulation. Governed agents extracted more water than ungoverned agents (mean demand ratio 0.394 +/- 0.004 versus 0.288 +/- 0.020 of legal entitlements), and consequently Lake Mead elevation was lower under governance (42-year mean 1,094 ft versus 1,173 ft). This result may appear paradoxical — governance was expected to promote conservation — but reflects how behavioural diversity interacts with the prior-appropriation system.

Ungoverned agents, having collapsed into monotonic demand-increase patterns, were constrained by the code-level demand ceiling that clamps requests at the legal water right. Their demand trajectories converged toward a ceiling (reaching ~0.35 by year 42 from initial ~0.31), producing an artificially conservative profile driven by the ceiling clamp rather than adaptive choice. Governed agents utilized all five skill types including demand decreases, enabling higher extraction in favourable years while reducing demand during drought — reflected in the demand-Mead coupling (governed r = 0.547 +/- 0.083 versus ungoverned r = 0.378 +/- 0.081 between Mead elevation and demand ratio). The minimum Mead elevation was comparable (governed 1,002 ft versus ungoverned 1,001 ft), indicating both systems reached the physical floor during severe drought (years 2-4); the divergence occurs in recovery, where governed agents' drought-responsive behaviour produces adaptive demand fluctuations that ungoverned agents' rigidity cannot.

The lower mean Mead elevation under governance (1,094 ft versus 1,173 ft) admits two interpretations: governed agents adaptively exploit available water within institutional bounds, or they extract more aggressively and institutional safety nets (shortage tiers) catch them. The evidence favours a combination: governance enables higher extraction with stronger drought responsiveness. Governed agents crossed the 1,075-ft shortage threshold in 13.3 ± 1.5 of 42 years versus 5.0 ± 1.7 for ungoverned agents. In shortage years, governed agents curtailed demand to 0.322 ± 0.008 from a plentiful-year baseline of 0.406 ± 0.009 — a curtailment spread of 0.084 matching ungoverned agents (0.083) but at 53% higher absolute extraction, suggesting governance shifts the operating point rather than the adaptive capacity. Year-over-year demand variability was 19% higher under governance (SD 0.0255 versus 0.0215). Ungoverned agents, converging toward ceiling-capped monotonic growth, were seldom drawn below shortage thresholds — their reservoir stability is inertial, not adaptive (see Supplementary Table S6 for additional water-system metrics).

### Removing a single governance rule decouples diversity from drought responsiveness

To test whether the diversity effect requires the full governance stack or depends on specific rules, we removed a single validator — the demand ceiling stabilizer, which blocks demand-increase proposals when basin-wide demand exceeds 6.0 MAF — while retaining all other 11 validators. This targeted ablation (condition A1) used the same 3 seeds and agent configurations as the main experiment.

Removing the demand ceiling increased behavioural diversity: EHE rose from 0.738 +/- 0.017 (full governance) to 0.793 +/- 0.002 (A1), confirming that the ceiling actively constrains the action distribution. However, demand-Mead coupling collapsed (r = 0.234 +/- 0.127 versus 0.547 +/- 0.083 under full governance), shortage years nearly doubled (25.3 +/- 1.5 versus 13.3 +/- 1.5), and minimum Mead elevation dropped below the Tier 3 threshold to 984 +/- 11 ft (Table 2). Without the ceiling linking individual proposals to aggregate basin state, agents diversified into maladaptive extraction patterns — higher demand ratios (0.440 +/- 0.012 versus 0.394 +/- 0.004) decoupled from drought signals. The demand ceiling does not suppress diversity; it channels diversity toward drought-responsive patterns. This establishes that governance-induced diversity is functionally adaptive, not a statistical artefact of constraint-based rejection sampling.

**Table 2. Targeted ablation: removing the demand ceiling stabilizer (78 agents x 42 years, 3 runs each).**

| Metric | Full Governance | No Ceiling (A1) | Ungoverned |
|--------|:-:|:-:|:-:|
| EHE | 0.738 +/- 0.017 | 0.793 +/- 0.002 | 0.637 +/- 0.017 |
| Demand ratio | 0.394 +/- 0.004 | 0.440 +/- 0.012 | 0.288 +/- 0.020 |
| Demand-Mead r | 0.547 +/- 0.083 | 0.234 +/- 0.127 | 0.378 +/- 0.081 |
| Shortage years (/42) | 13.3 +/- 1.5 | 25.3 +/- 1.5 | 5.0 +/- 1.7 |
| Min Mead (ft) | 1,002 +/- 1 | 984 +/- 11 | 1,001 +/- 0.4 |

*Demand ceiling stabilizer blocks demand-increase proposals when aggregate basin demand exceeds 6.0 MAF. A1 removes this single rule while retaining all 11 other validators. Demand-Mead r = Pearson correlation between annual Mead elevation and mean demand ratio (higher = more drought-responsive). Shortage years = count of years where shortage tier > 0.*

### Governed language agents produce broader action distributions than hand-coded decision rules

A hand-coded Protection Motivation Theory (PMT) agent provides a direct comparison with the traditional ABM approach. This rule-based agent computes threat appraisal and coping appraisal scores from objective flood risk, income, and prior adaptation state, then selects actions deterministically based on threshold combinations — the standard paradigm described in the Introduction. We ran three independent simulations (100 agents, 10 years) using the same flood domain and evaluation protocol as the language-based experiments.

The rule-based PMT agent achieved EHE = 0.689 +/- 0.001. This positions rule-based agents between the two language-agent conditions: governed language agents (EHE = 0.752 +/- 0.052, Group C) exceeded the rule-based baseline, while ungoverned language agents (0.337 +/- 0.064) fell far below it (Table 3). The ungoverned deficit is stark: 85.9% of ungoverned annual decisions were do_nothing, reflecting behavioural collapse into inaction. The rule-based agent's diversity stems entirely from parameterized variation — agents differ in income, flood zone, and prior experience, producing different threshold crossings — but all agents follow the same decision logic. The governed language agent achieves higher diversity through qualitatively different reasoning paths that the rule-based architecture cannot represent.

**Table 3. Decision diversity: governed LLM vs rule-based PMT vs ungoverned LLM (flood domain, Gemma-3 4B, 100 agents x 10 years, 3 runs each).**

| Condition | EHE | BRI (%) | do_nothing (%) | insurance (%) | elevation (%) | relocation (%) |
|---|---|---|---|---|---|---|
| **Governed LLM** | **0.752 +/- 0.052** | 100.0 | 35.6 | 50.7 | 10.6 | 3.0 |
| **Rule-based PMT** | **0.689 +/- 0.001** | 100.0 | 10.6 | 49.1 | 40.2 | 0.1 |
| **Ungoverned LLM** | **0.337 +/- 0.064** | 85.5 | 85.9 | 11.7 | 2.3 | 0.0 |

*EHE computed from annual action selections; rule-based composites (simultaneous insurance + elevation recommendations) split into constituents (see Methods). BRI = Behavioural Rationality Index: fraction of decisions where the agent's stated risk assessment is consistent with its chosen action (higher = more rational). Action shares are fractions of all agent-year decisions. Rule-based agent uses deterministic PMT threshold logic with parameterized agent heterogeneity.*

### The diversity effect transfers across domains and model scales

The flood domain tests whether the governance-diversity effect generalises from continuous institutional allocation to discrete household choices under stochastic hazard. In this domain, 100 household agents made protective decisions (insurance, elevation, relocation, or inaction) over 10 simulated years under stochastic flood events. Six models spanning two families and three scales (Gemma-3 4B/12B/27B, Ministral 3B/8B/14B) were tested with three runs per condition. Behavioural diversity was measured from each agent's annual action selection — the decision actually made in each year — consistent with the irrigation domain (see Methods).

Governance eliminated reasoning-action mismatches entirely (0.0% across all models, versus 0.1-62.3% ungoverned). The diversity effect was positive for all six models (Table 4), with five showing statistically significant gains (bootstrap 95% CI excluding zero). The effect was strongest for models whose ungoverned agents collapsed into behavioural monoculture: Gemma-3 4B agents chose do_nothing in 85.9% of ungoverned decisions, yielding EHE = 0.337; under governance, the same model achieved EHE = 0.752 (delta = +0.415). Ministral 3B showed a similar pattern (ungoverned do_nothing = 82.5%, delta = +0.302). Only Gemma-3 12B produced a non-significant effect (delta = +0.012, CI [-0.018, +0.039]), reflecting near-identical decision distributions across conditions: both governed and ungoverned 12B agents concentrated on insurance (80-81% of annual decisions). The A1 ablation (Table 2; irrigation domain) demonstrates that this diversity is not merely wider — it is functionally coupled to environmental state through specific governance rules.

Effect magnitudes ranged from +0.012 (Gemma-3 12B) to +0.415 (Gemma-3 4B); even where the diversity effect was modest, governance eliminated constraint violations entirely (0.0% versus up to 62.3% reasoning–action mismatches ungoverned; Table S1). Gemma-3 12B's non-significant result likely reflects strong instruction-tuned action priors at this scale (see SI for discussion).

**Table 4. Governance effect on behavioural diversity (EHE) across six language models (flood domain, 100 agents x 10 years, 3 runs per condition). Positive delta indicates governance increases diversity.**

| Model | Ungoverned EHE | Governed EHE | Delta | 95% CI |
|-------|:-:|:-:|:-:|:-:|
| Gemma-3 4B | 0.337 +/- 0.064 | 0.752 +/- 0.052 | +0.415 | [+0.393, +0.458] |
| Gemma-3 12B | 0.471 +/- 0.014 | 0.483 +/- 0.042 | +0.012 | [-0.018, +0.039] |
| Gemma-3 27B | 0.462 +/- 0.032 | 0.676 +/- 0.018 | +0.214 | [+0.204, +0.231] |
| Ministral 3B | 0.431 +/- 0.056 | 0.734 +/- 0.020 | +0.302 | [+0.232, +0.350] |
| Ministral 8B | 0.579 +/- 0.014 | 0.626 +/- 0.008 | +0.047 | [+0.042, +0.091] |
| Ministral 14B | 0.665 +/- 0.010 | 0.708 +/- 0.012 | +0.043 | [+0.041, +0.054] |

*EHE computed from annual action selections (see Methods). Delta = governed minus ungoverned EHE. Per-model 95% CIs from bootstrap resampling (agent-timestep level, 10,000 iterations; CIs reflect within-condition variation; seed-level replication (n = 3) provides limited power for between-condition inference). Reasoning–action mismatch rates in Table S1.*

---

## Structural changes from v10
- **Reordered**: Irrigation leads (was section 3), flood becomes secondary (was section 1)
- **NEW section**: "Removing a single governance rule..." (Table 2, A1 ablation)
- **NEW section**: "Governed language agents surpass hand-coded decision rules" (Table 3)
- **Elevated**: Water-system outcomes moved to position 2 (was position 5)
- **Merged**: "Governance compensates for model scale" folded into flood section
- **Trimmed**: Removed redundant old irrigation summary — data now in Table 1 + text
- **Reframed headings**: Insight-first, not metric-first
- **Word count**: ~2300 (4 tables: T1 irrigation, T2 A1 ablation, T3 PMT comparison, T4 cross-scale)
