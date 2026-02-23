# Supplementary Information

## Institutional Constraints Widen Adaptive Strategy Diversity in Language-Based Water Agents

---

## S1. Annual Decision Distributions and Data Quality by Model

Strategy diversity in the flood domain is measured from each agent's annual action selection — the single decision submitted in each yearly round — rather than from cumulative protection states (see Methods). Table S1 reports the ungoverned annual decision distributions and reasoning–action mismatch rates for each model.

**Table S1. Ungoverned annual decision distributions and reasoning–action mismatch rates (flood domain, 100 agents × 10 years, 3 runs).**

| Model | do_nothing (%) | buy_insurance (%) | elevate_house (%) | relocate (%) | Reasoning–action mismatch (%) |
|-------|:-:|:-:|:-:|:-:|:-:|
| Gemma-3 4B | 85.9 | 11.7 | 2.3 | 0.0 | 14.5 |
| Gemma-3 12B | 9.4 | 80.3 | 9.8 | 0.5 | 0.1 |
| Gemma-3 27B | 72.5 | 26.2 | 1.4 | 0.0 | 11.2 |
| Ministral 3B | 82.5 | 7.4 | 9.7 | 0.4 | 62.3 |
| Ministral 8B | 38.7 | 58.2 | 2.6 | 0.5 | 6.4 |
| Ministral 14B | 27.9 | 61.4 | 9.9 | 0.8 | 18.2 |

Models with the largest governance effects (Gemma-3 4B, Ministral 3B) concentrated 82–86% of ungoverned decisions on do_nothing, producing low baseline EHE that governance substantially increased. Gemma-3 12B showed near-identical distributions across conditions (80–81% buy_insurance), yielding a non-significant diversity effect. Reasoning–action mismatches — where the agent's stated risk assessment contradicts its chosen action — were eliminated entirely under governance (0.0% across all models).

---

## S2. Representative Agent Reasoning Traces

To substantiate the claim that governed agents produce qualitatively distinct reasoning paths, we present five paired reasoning traces extracted from the irrigation ABM (seed 42, production_v20). Each pair matches a governed and ungoverned agent under comparable physical conditions (same year, same shortage tier). Three reasoning archetypes appear exclusively in governed runs: (1) **governance-blocked escalation**, where a demand-increase proposal is rejected by a broker rule and the agent falls back to maintain_demand; (2) **constraint-shaped adaptation**, where repeated shortfall feedback drives the agent toward decrease_small or decrease_large during multi-year droughts; and (3) **condition-opportunistic expansion**, where the governance layer permits aggressive increase_large during wet years with qualitatively different rationale than ungoverned agents' unconditional growth. Ungoverned agents exhibit a fourth dominant archetype: **escalation under scarcity**, where high adaptive-capacity agents respond to shortage signals by demanding more water.

**Table S2. Paired reasoning traces: governed vs. ungoverned irrigation agents.**

| # | Condition | Agent | Year | Shortage Tier | Mead (ft) | Decision | Reasoning Excerpt |
|---|-----------|-------|------|---------------|-----------|----------|-------------------|
| 1 | Governed | YumaIrrDist | 2 | Tier 2 | 1,028 | decrease_small | "The Bureau has declared Tier 2 shortage...my past approach has failed, and I need to adapt to the realities of reduced water availability." |
| 1 | Ungoverned | CRIR AZ | 2 | Tier 2 | 1,027 | increase_large | "I need to proactively secure as much water as possible to maximize my yield." |
| 2 | Governed | WelltonMohawkIDD | 3 | Tier 3 | 1,003 | decrease_large | "Past attempts to increase my request have failed...I need to actively reduce my demand to avoid further penalties." |
| 2 | Ungoverned | WelltonMohawkIDD | 3 | Tier 3 | 1,000 | increase_large | "I'll lean towards a proactive, albeit somewhat aggressive, approach to secure as much yield as possible." |
| 3 | Governed | CocopahIndRes | 10 | Tier 0 | 1,161 | maintain (fallback) | *Proposal blocked by demand_ceiling_stabilizer + high_threat_high_cope_no_increase.* |
| 3 | Ungoverned | CocopahIndRes | 10 | Tier 0 | 1,220 | increase_large | "Lake Mead is rising...I'm not one for caution." |
| 4 | Governed | FtYumaReservation | 38 | Tier 2 | 1,039 | decrease_small | "The governance layer is screaming about a 2.2% demand excess...I need to be proactive and reduce my demand." |
| 4 | Ungoverned | FtYumaReservation | 38 | Tier 0 | 1,118 | maintain | "I'm not seeing any immediate crisis." |
| 5 | Governed | MohaveValleyIDD | 6 | Tier 0 | 1,098 | increase_large | "Given the favorable water supply conditions...the potential for increased production outweighs the risk." |
| 5 | Ungoverned | NorthGilaValleyIDD | 6 | Tier 0 | 1,098 | maintain | "There's no compelling reason to disrupt a system that isn't broken." |

Of 3,276 governed agent-year decisions, 119 were demand decreases (85 small + 34 large), concentrated in drought windows (years 2–3, 38–42). Of 3,276 ungoverned decisions, 0 were decrease_large and only 59 were decrease_small; 1,793 (54.7%) were increase_large versus 656 (20.0%) in governed runs.

### Reasoning-generated heterogeneity within governed agents

The paired traces above compare governed against ungoverned agents. A distinct form of evidence for reasoning-generated heterogeneity comes from comparing governed agents *against each other* under identical physical conditions. Table S2b presents three cases where agents facing the same shortage tier and reservoir state reached different decisions through qualitatively different reasoning strategies. Across all three seeds, 41,426 such heterogeneous pairs were identified (see `reasoning_heterogeneity_traces.py` for methodology).

**Table S2b. Reasoning heterogeneity among governed agents under identical conditions.**

| # | Seed | Year | Tier | Mead (ft) | Agent A | Decision A | Agent B | Decision B |
|---|------|------|------|-----------|---------|------------|---------|------------|
| 1 | 43 | 4 | 1 | 1,051 | Fort Mohave Ind Res CA | increase_small | HopiTribe | maintain |
| 2 | 42 | 40 | 3 | 1,012 | FtYumaReservation | decrease_small | CO-NM Ag | maintain |
| 3 | 44 | 40 | 3 | 1,002 | Fort Mohave Ind Res AZ | decrease_large | Powers | maintain |

**Pair 1 (Tier 1 — opportunistic vs conservation):** Fort Mohave CA reasoned: "Lake Mead is rising, and we're still in Tier 1 shortage. Given my skepticism about forecasts and my preference for maximizing yield, I'll increase my water demand slightly to capitalize on the current situation." HopiTribe reasoned: "My memory strongly advises against increasing water demand, given the history of shortages. I've learned that chasing larger yields with water isn't sustainable in this basin." Both agents face the same Mead elevation and shortage tier; the divergence stems from different reasoning frames — forward-looking exploitation versus experience-driven conservation.

**Pair 2 (Tier 3 — community-influenced vs yield-focused):** FtYumaReservation reasoned: "My neighbors are suggesting I curtail, and my past attempts at maintaining demand have resulted in shortages...I need to proactively reduce my water request to minimize the risk of further curtailment while still achieving a reasonable yield." CO-NM Ag reasoned: "My current allocation is already severely curtailed. Given the ongoing shortfall and my need to reliably produce hay, I need to increase my request, but cautiously, to maximize my potential yield given the constraints." The first agent incorporates social signals and past experience; the second prioritizes production needs under constraint.

**Pair 3 (Tier 3 — aggressive conservation vs cautious status quo):** Fort Mohave AZ reasoned: "My water use is already high at 46%. I need to reduce my demand aggressively to avoid further curtailment, even if it means a slight yield reduction." Powers reasoned: "Maintaining the status quo, while risky, is the safest approach to avoid significant shortfall issues, consistent with my past experience." Both face the same severe shortage, yet reach opposite conclusions — one through proactive system awareness, the other through risk-averse inertia.

These within-governed contrasts demonstrate that reasoning-generated heterogeneity is not merely a statistical property of the action distribution (which EHE captures) but reflects qualitatively different cognitive strategies operating within the same institutional boundaries. A rule-based PMT agent with identical threshold logic and different parameter values could produce different actions, but not different *reasoning frames* — the distinction between "capitalize on rising Mead" and "chasing yields isn't sustainable" cannot emerge from parameterized variation within a single decision function.

**Data sources.** Governed traces from `production_v20_42yr_seed{42,43,44}/irrigation_farmer_governance_audit.csv`. Reasoning text from structured CSV field `reason_reasoning`. Heterogeneity analysis: `examples/irrigation_abm/analysis/reasoning_heterogeneity_traces.py`.

---

## S3. First-Attempt Analysis

To verify that the diversity effect reflects genuine governance-induced behavioural diversification rather than retry artefacts, we analysed only the first decision attempt for each agent-timestep in the irrigation domain.

**Irrigation first-attempt results:**
- Governed first-attempt EHE: 0.761 ± 0.020
- Ungoverned first-attempt EHE: 0.640 ± 0.017
- Difference: +0.121 (p < 0.001)

This 12.1 percentage-point increase in entropy from governance persists when considering only initial proposals, confirming that the diversity effect is not a consequence of iterative refinement. The effect magnitude is comparable to the full-trace analysis (which includes retries), indicating that governance shapes agent reasoning at the initial decision stage.

**Iterative behaviour context.** In governed conditions, 39.5% of all proposals were rejected by validators, 61.9% of agent-timesteps required at least one retry, and 0.7% of decisions fell back to default actions after exhausting retry limits. Despite this extensive iterative refinement, the diversity effect is fully expressed in first-attempt decisions, demonstrating that governance constraints influence the agent's internal reasoning process rather than merely filtering outputs.

---

## S4. Behavioural Rationality Index (BRI) Details

We assessed whether governance removes behavioural bias without imposing prescriptive action templates using the Behavioural Rationality Index (BRI). In the irrigation domain, BRI measures the fraction of decisions where agents facing high water scarcity chose not to increase demand; in the flood domain, BRI measures the fraction of decisions where the agent's stated risk assessment is consistent with its chosen action.

**Irrigation domain results:**
- Governed BRI: 58.0%
- Ungoverned BRI: 9.4%
- Null model (random action selection): 60.0%

The null model baseline of 60% arises from the irrigation skill structure, where three of five available skills (maintain, decrease_small, decrease_large) represent non-increase actions. An agent selecting randomly would achieve 60% BRI when facing high scarcity.

**Interpretation.** Ungoverned agents exhibited a strong increase-bias (BRI of 9.4%), consistently selecting water-intensive actions regardless of stated appraisals of water scarcity. Governance increased BRI to 58.0%, approaching the null model rate of 60%. This indicates that governance removes the increase-bias without prescribing specific action sequences. Governed agents' decisions reflect their stated cognitive appraisals at rates statistically indistinguishable from unstructured choice (χ² test, p = 0.42), demonstrating that governance enables rational diversity through constraint rather than prescription.

**Flood domain results:** Governed BRI was 100.0% across all models; ungoverned BRI ranged from 37.7% (Ministral 3B) to 99.9% (Gemma-3 12B). See Table S1 for per-model reasoning–action mismatch rates.

---

## S5. Insurance Premium Doubling Sensitivity (B1 Analysis)

To test whether the diversity effect persists under altered economic incentives, we conducted an exploratory sensitivity analysis in the flood domain by doubling the baseline insurance premium rate from 0.02 to 0.04.

**Experimental design:**
- Model: Gemma-3 4B
- Configuration: 100 agents × 10 years
- Replication: 3 random seeds × 3 agent groups = 9 runs
- Comparison: Premium-doubled runs versus baseline premium runs

**Results:**

Under premium doubling, the diversity effect reversed:
- Ungoverned EHE (premium doubled): 0.797 ± 0.018
- Governed EHE (premium doubled): 0.693 ± 0.024
- Difference: -0.104 (ungoverned > governed)

This contrasts with baseline premium conditions, where governed EHE exceeded ungoverned EHE for the same model (Table 3).

**Interpretation.** External cost pressure (premium doubling) appears to force behavioural diversification independently of governance. In the ungoverned condition, agents adapted to the higher premium by exploring alternative mitigation strategies (elevation, relocation, do_nothing), increasing entropy above the governed condition. This suggests that sufficiently strong economic incentives can substitute for governance constraints in promoting diverse adaptive responses.

**Expert panel assessment.** Four domain experts (water policy, behavioural economics, resilience modelling, computational social science) reviewed these findings. Three of four recommended reporting the premium doubling analysis in Supplementary Information rather than the main text, citing (1) the need for additional replications across models and parameter ranges, (2) potential interaction effects with other economic parameters, and (3) the exploratory nature of single-scenario sensitivity tests.

**Decision.** We report the premium doubling analysis here as exploratory sensitivity evidence. Future work should systematically vary insurance premiums, elevation costs, and buyout offers to map the economic-governance interaction landscape.

---

## S6. Supplementary Water-System Outcomes

Summary water-system outcomes are reported in main-text Table 1. This section provides additional detail.

**Table S6. Supplementary water-system outcomes (irrigation domain, Gemma-3 4B, 78 agents × 42 years, 3 runs each).**

| Metric | Governed | Ungoverned |
|--------|----------|------------|
| Minimum Lake Mead elevation (ft) | 1,002 | 1,001 |
| Shortage-threshold crossings (of 42 yr) | 13.3 ± 1.5 | 5.0 ± 1.7 |
| Shortage-year demand ratio | 0.362 ± 0.008 | 0.234 ± 0.012 |
| Plentiful-year demand ratio | 0.409 ± 0.009 | 0.295 ± 0.019 |
| Curtailment spread (plentiful − shortage) | 0.047 | 0.061 |
| Year-over-year demand variability (SD) | 0.037 | 0.061 |
| Percentage of agents increasing demand | ~53% | 77–82% |

*All demand ratios computed as basin-aggregate (total requests / total water rights per year). Curtailment spread = plentiful-year DR minus shortage-year DR.*

The near-identical minimum elevations (1,002 vs. 1,001 ft) indicate both conditions avoided catastrophic reservoir failure. Governed agents crossed the 1,075-ft shortage-declaration threshold more frequently (13.3 vs. 5.0 years), reflecting productive engagement with the prior-appropriation system's responsive range rather than commons degradation. Ungoverned agents showed higher year-over-year demand variability (SD 0.061 vs. 0.037), driven by the volatility of ceiling-capped monotonic growth trajectories rather than adaptive demand management. The larger curtailment spread for ungoverned agents (0.061 vs. 0.047) reflects their lower baseline extraction — proportionally, ungoverned agents curtailed more relative to their plentiful-year demand, but from a much lower operating point (0.295 vs. 0.409).

---

## S7. Model and Configuration Details

### Language Models

All experiments were conducted using locally hosted models via Ollama inference engine. The following models were tested across both irrigation and flood domains:

**Gemma-3 family** (Google DeepMind):
- gemma3:4b — 4 billion parameters (primary model for all main analyses)
- gemma3:12b — 12 billion parameters
- gemma3:27b — 27 billion parameters

**Ministral family** (Mistral AI):
- ministral:3b — 3 billion parameters
- ministral:8b — 8 billion parameters
- ministral:14b — 14 billion parameters

**Inference configuration** (consistent across all models):
- Temperature: 0.8
- Top-p (nucleus sampling): 0.9
- Context window: 8,192 tokens
- Inference mode: Local (Ollama)
- Hardware: NVIDIA RTX GPU with Ollama serving

### Domain-Specific Validation Frameworks

**Irrigation domain (Colorado River Basin):**

Twelve validators enforcing physical, social, temporal, and behavioural constraints:

*Physical validators (7):*
1. Water balance constraint (USBR allocation rules)
2. Reservoir capacity bounds (Lake Mead: 1,000–1,229 ft)
3. Demand magnitude feasibility (≤200% baseline)
4. Infrastructure capacity limits
5. Drought tier consistency (USBR 2007 guidelines)
6. Evaporation rate bounds
7. Upstream flow variability constraints

*Institutional validators (1):*
8. Demand ceiling stabilizer (blocks demand-increase proposals when aggregate basin demand exceeds 6.0 MAF — the rule tested in the A1 ablation)

*Social validators (2):*
9. Equity constraint (within-group demand variance limits)
10. Communication protocol compliance

*Temporal validators (1):*
11. Inter-annual demand smoothness (≤30% year-over-year change)

*Behavioural validators (1):*
12. WSA-ACA construct-action alignment

**Flood domain (coastal household adaptation):**

Protection Motivation Theory (PMT)-based governance framework with four validator classes:

1. **Threat-appraisal alignment**: Blocks mitigation actions (elevate, insure) when agent appraises flood risk as low
2. **Coping-appraisal alignment**: Blocks actions when agent rates their self-efficacy or response efficacy as insufficient
3. **Physical feasibility**: Enforces wealth constraints, rental status restrictions, and sequential elevation limits
4. **Re-elevation block**: Prevents redundant elevation after prior implementation

All validators operated at severity level ERROR (blocking + retry), not WARNING (logging only), to ensure governance constraints actively shaped agent behaviour.

### Experimental Replication

**Irrigation:** 78 agents × 42 years × 3 random seeds × 2 conditions (governed/ungoverned) = 6 experiments (37.3 hours total runtime)

**Flood:** 100 agents × 10 years × 3 random seeds × 6 models × 3 agent groups × 2 conditions = 54 complete experiments (baseline premium configuration)

All random seeds controlled both agent initialization (persona assignment) and stochastic processes (hazard exposure under per-agent-depth flood sampling).

---

## S8. Data and Code Availability

All experiment configurations, validation frameworks, and analysis scripts are available in the project repository:

- **Irrigation experiment**: `examples/irrigation_abm/`
- **Flood experiment (single-agent)**: `examples/single_agent/`
- **Governance framework**: `broker/`
- **Analysis scripts**: `paper/nature_water/scripts/`

Raw experimental outputs (agent traces, validator logs, system state snapshots) are archived and available upon request due to size constraints (>100 GB).

---

## S9. Statistical Methods

### Effective Heterogeneity Entropy (EHE)

We quantified strategy diversity using normalized Shannon entropy:

$$H_{\text{eff}} = -\frac{1}{\log k} \sum_{i=1}^{k} p_i \log p_i$$

where $k$ is the number of available action categories and $p_i$ is the empirical frequency of action $i$ across all agent-timesteps. Normalization by $\log k$ ensures $H_{\text{eff}} \in [0, 1]$, with 0 indicating complete homogeneity (all agents select the same action) and 1 indicating maximum diversity (uniform distribution over all actions).

**Confidence intervals:** 95% CIs were computed via 10,000-iteration bootstrap resampling at the agent-timestep level, preserving within-agent temporal autocorrelation structure.

**Statistical significance:** Differences in EHE between governed and ungoverned conditions were assessed using permutation tests (10,000 permutations) to avoid distributional assumptions.

### Model-Specific vs. Pooled Analysis

Per-model analyses are reported as primary findings because:

1. **Model heterogeneity**: Effect sizes varied substantially across models (Table 3: Δ EHE from +0.012 to +0.415)
2. **Scientific interpretation**: Model-specific patterns reveal which architectural features (parameter count, training data, instruction-tuning methods) modulate governance responsiveness
3. **Pooled CI limitations**: Pooled confidence intervals aggregate across heterogeneous effect sizes and should be interpreted as meta-analytic summaries, not tests of overall effect presence

All six models showed positive governance effects under the primary normalization (Table 3), but the magnitude varied by over an order of magnitude. Under alternative composite-action normalizations (Table S3), some models show reversed effects, underscoring that the direction depends on specification choice for models with high composite rates. Table S3 reports EHE sensitivity to composite-action normalization specification across four scenarios.

---

## S10. Limitations and Future Directions

**Model diversity.** Our analysis focused on two model families (Gemma-3, Ministral) ranging from 3B to 27B parameters. Future work should include proprietary models (GPT-4, Claude), open-source alternatives (Llama, Qwen), and domain-specialized models to assess generalizability.

**Governance design space.** We implemented domain-tailored validators (Colorado River rules, PMT-based flood governance) but did not systematically vary governance stringency, complexity, or theoretical foundation. The diversity effect may depend on governance design quality, not merely its presence.

**Economic parameter interactions.** The premium doubling sensitivity analysis (S5) revealed that external incentives can modulate or reverse diversity effects. A full factorial design varying insurance premiums, elevation costs, buyout offers, and interest rates would map the economic-governance interaction landscape.

**Long-term behavioural convergence.** Our experiments spanned 10–42 simulated years, but real adaptive systems evolve over decades to centuries. Extended simulations could reveal whether governance-induced diversity persists, intensifies, or erodes under prolonged stress.

**Empirical validation.** While our validation protocol assessed micro-behavioural coherence and population-level patterns against empirical benchmarks (see Methods), direct comparison to controlled human experiments would strengthen claims about LLM agents as behavioural proxies.

---

## S11. Fuzzy Q-Learning Baseline Comparison

To assess whether adaptive exploitation requires the natural-language reasoning format or merely the governance constraints, we ran a fuzzy Q-learning (FQL) baseline using the reinforcement learning agent from Hung and Yang (2021). The FQL agent operates within the same simulation environment (identical reservoir model, precipitation inputs, shortage tiers, curtailment rules, and governance validators) and the same 78 CRSS agent profiles as the LLM experiments. The only difference is the decision kernel: FQL maps a discretized state (current diversion relative to water right) to two actions (increase or decrease demand) via Q-value comparison, whereas the LLM agent reasons in natural language over five skills.

Agent profiles were reconstructed from governed LLM simulation logs (year 1 state: agent_id, cluster, basin, water_right, initial diversion). FQL parameters (mu, sigma, alpha, gamma, epsilon, regret) were assigned from cluster-canonical values (Hung & Yang, 2021, Table 1). Three seeds (42, 43, 44) with cluster rebalancing (50%–30%–20%) matched the LLM experimental design.

**Table S4. Water-system outcomes: LLM governed vs FQL baseline (irrigation domain, 78 agents × 42 years, 3 seeds each).**

| Metric | LLM Governed | FQL Baseline |
|--------|:---:|:---:|
| Mean demand ratio | 0.394 ± 0.004 | 0.395 ± 0.008 |
| Demand–Mead coupling (r) | 0.547 ± 0.083 | 0.057 ± 0.323 |
| Shortage years (/42) | 13.3 ± 1.5 | 24.7 ± 9.1 |
| Min Mead elevation (ft) | 1,002 ± 1 | 1,020 ± 4 |
| 42-yr mean Mead (ft) | 1,094 | 1,065 |

FQL agents extracted nearly identical water volumes (demand ratio 0.395 versus 0.394) but showed near-zero correlation between demand and reservoir state (r = 0.057 versus 0.547). This decoupling produced substantially more shortage years (24.7 versus 13.3) despite comparable extraction levels. The FQL agent's Q-learning updates its action preferences based on reward signals (fulfilled diversion relative to request), but this learning occurs within a state→action mapping that cannot reference drought context, institutional announcements, or neighbour behaviour in the way that natural-language reasoning can.

Note that 84–89% of FQL decisions resulted in maintain_demand — not because FQL selected this action (FQL has only increase/decrease), but because governance validators blocked the proposed action and the deterministic fallback executed maintain_demand. This high blocking rate reflects the mismatch between FQL's binary action space and the governance rules designed for a richer decision vocabulary. EHE is therefore not computed for FQL, as the action distribution is dominated by a validator artifact rather than behavioural choice.

**Interpretation.** The FQL comparison isolates the representational contribution: governance alone does not produce adaptive exploitation. The combination of governance constraints *and* natural-language reasoning is required — governance defines the feasibility boundaries, and language-based reasoning enables agents to adaptively navigate within those boundaries in response to environmental state.

**Data and code.** FQL results: `examples/irrigation_abm/results/fql_raw/seed{42,43,44}/`. Runner: `examples/irrigation_abm/run_fql_baseline.py --from-logs`. Comparison metrics: `examples/irrigation_abm/analysis/fql_comparison_metrics.py`.

---

**End of Supplementary Information**
