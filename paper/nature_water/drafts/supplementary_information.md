# Supplementary Information

## Institutional Constraints Widen Adaptive Strategy Diversity in Language-Based Water Agents

---

## Supplementary Note 1. IBR Decomposition and Governance Effect by Model

The Irrational Behaviour Rate (IBR, denoted R_H) quantifies the percentage of agent decisions that violate Protection Motivation Theory predictions, computed as the sum of verification rule violations divided by the number of active agent-year observations:

- **V1** (relocation under low threat): agent relocated despite appraising flood risk as low
- **V2** (elevation under low threat): agent elevated the house despite appraising flood risk as low

A third rule, V3 (inaction under extreme threat with adequate coping), was tested but yielded zero violations across all twelve conditions (six models × two governance states). This null result reflects the rarity of very-high (VH) threat appraisals: ungoverned agents express threat through hedged language rather than extreme categorical labels, and the few governed agents receiving VH appraisals consistently selected protective actions. V3 is omitted from Supplementary Table 1.

For ungoverned agents (Group A), threat and coping appraisals are inferred from free-text narratives using a three-tier keyword classifier: (1) explicit categorical labels (VH/H/M/L/VL), (1.5) qualifier precedence that detects negation and hedging phrases (e.g., "low risk of flooding", "moderate concern") before keyword matching, and (2) curated PMT keyword dictionaries. For governed agents (Group C), structured labels are emitted directly by the governance pipeline. Group A uses a relaxed low-threat threshold {L, VL, M} to account for classification uncertainty; Group C uses the strict threshold {L, VL}.

**Supplementary Table 1. IBR decomposition across six language models (flood domain, 100 agents × 10 years, 3 runs per condition). Values are means ± s.d. across seeds.**

| Model | Condition | R_H (%) | V1 | V2 | Strategy diversity |
|---|---|---|---|---|---|
| Gemma-3 4B | A (ungoverned) | 1.15 ± 0.17 | 0.3 | 10.0 | 0.307 ± 0.059 |
| | C (governed) | 0.86 ± 0.44 | 0 | 6.7 | 0.636 ± 0.044 |
| Gemma-3 12B | A (ungoverned) | 3.35 ± 0.13 | 0.7 | 29.3 | 0.282 ± 0.012 |
| | C (governed) | 0.15 ± 0.07 | 0 | 1.3 | 0.310 ± 0.048 |
| Gemma-3 27B | A (ungoverned) | 0.78 ± 0.38 | 0 | 7.0 | 0.322 ± 0.020 |
| | C (governed) | 0.33 ± 0.00 | 0 | 3.0 | 0.496 ± 0.051 |
| Ministral 3B | A (ungoverned) | 8.89 ± 1.24 | 3.0 | 76.7 | 0.373 ± 0.061 |
| | C (governed) | 1.70 ± 0.26 | 0 | 10.7 | 0.571 ± 0.047 |
| Ministral 8B | A (ungoverned) | 1.56 ± 0.00 | 2.7 | 11.3 | 0.555 ± 0.009 |
| | C (governed) | 0.13 ± 0.13 | 0 | 1.0 | 0.531 ± 0.028 |
| Ministral 14B | A (ungoverned) | 11.61 ± 0.58 | 6.7 | 97.0 | 0.572 ± 0.018 |
| | C (governed) | 0.40 ± 0.18 | 0 | 3.3 | 0.605 ± 0.011 |

*V1/V2 counts are per-run means (3-run average). R_H% = (V1 + V2) / N_active × 100. Post-relocation agent-years excluded from N_active. Strategy diversity = normalized Shannon entropy H/log₂(k) (0 = monoculture; 1 = uniform).*

**Supplementary Table 2. Governance effect on IBR (paired difference, A minus C).**

| Model | Δ R_H (pp) | 95% CI | p (paired t) |
|---|---|---|---|
| Gemma-3 4B | +0.29 | [−0.47, +1.06] | 0.24 |
| Gemma-3 12B | +3.20 | [+2.73, +3.67] | 0.001 |
| Gemma-3 27B | +0.44 | [−0.51, +1.40] | 0.18 |
| Ministral 3B | +7.19 | [+4.09, +10.29] | 0.010 |
| Ministral 8B | +1.43 | [+1.11, +1.74] | 0.003 |
| Ministral 14B | +11.21 | [+9.74, +12.67] | <0.001 |

*95% CIs from paired t-distribution (df = 2). For Gemma-3 4B and 27B, the small A–C difference relative to between-run variance yields non-significant p-values; however, the direction of the effect (A > C) is consistent across all six models.*

**Note on group labels.** The cross-model comparison (Tables 3, S1) uses Group C (governed + HumanCentric memory) as the governed condition because Groups A and C were run for all six models, whereas Group B (governed, window memory only) was run only for Gemma-3 4B. For Gemma-3 4B, Groups B and C produced identical strategy diversity (0.636 ± 0.044; Table 2 reports Group B). The governance effect in both groups is attributable to the validator pipeline, which is identical across Groups B and C; the memory subsystem differs but does not alter governance rule application.

**Ungoverned decision distributions.** Models with the largest governance effects (Gemma-3 4B, Ministral 3B) concentrated 82–86% of ungoverned decisions on do_nothing, producing low baseline strategy diversity that governance substantially increased. Gemma-3 12B showed near-identical distributions across conditions (80–81% buy_insurance), yielding a non-significant diversity effect.

---

## Supplementary Note 2. Agent Reasoning Analysis

To substantiate the claim that governance enables qualitatively distinct reasoning — not merely different action selections — we present three forms of evidence: (1) paired governed-vs-ungoverned traces showing divergent reasoning under comparable conditions, (2) within-governed comparisons showing heterogeneous reasoning under identical conditions, and (3) a systematic taxonomy of emergent cognitive frames. All traces are from the irrigation domain (78 agents, 42 years, seed 42 unless noted).

### Governed versus ungoverned comparisons

Three reasoning archetypes appear exclusively in governed runs: (1) **governance-blocked escalation**, where a demand-increase proposal is rejected and the agent falls back to maintain_demand; (2) **constraint-shaped adaptation**, where repeated shortfall feedback drives the agent toward demand decreases during drought; and (3) **condition-opportunistic expansion**, where governance permits aggressive increase_large during wet years with qualitatively different rationale than ungoverned agents' unconditional growth. Ungoverned agents exhibit a fourth archetype: **escalation under scarcity**, where agents respond to shortage signals by demanding more water.

**Supplementary Table 3. Governed vs. ungoverned paired reasoning traces (irrigation domain, seed 42).**

| # | Condition | Agent | Year | Tier | Mead (ft) | Decision | Archetype | Reasoning Excerpt |
|---|-----------|-------|------|------|-----------|----------|-----------|-------------------|
| 1 | Governed | YumaIrrDist | 2 | 2 | 1,028 | **decrease_small** | Constraint-shaped | "My past approach has failed, and I need to adapt to the realities of reduced water availability." |
| 1 | Ungoverned | CRIR AZ | 2 | 2 | 1,027 | **increase_large** | Escalation under scarcity | "I need to proactively secure as much water as possible to maximize my yield." |
| 2 | Governed | WelltonMohawkIDD | 3 | 3 | 1,003 | **decrease_large** | Constraint-shaped | "Past attempts to increase my request have failed...I need to actively reduce my demand." |
| 2 | Ungoverned | WelltonMohawkIDD | 3 | 3 | 1,000 | **increase_large** | Escalation under scarcity | "I'll lean towards a proactive, albeit aggressive, approach to secure as much yield as possible." |
| 3 | Governed | CocopahIndRes | 10 | 0 | 1,161 | **maintain** (fallback) | Blocked escalation | *Blocked by demand_ceiling_stabilizer + high_threat_high_cope_no_increase.* |
| 3 | Ungoverned | CocopahIndRes | 10 | 0 | 1,220 | **increase_large** | Unconditional growth | "Lake Mead is rising...I'm not one for caution." |
| 4 | Governed | FtYumaReservation | 38 | 2 | 1,039 | **decrease_small** | Constraint-shaped | "The governance layer is screaming about a 2.2% demand excess...I need to reduce my demand." |
| 4 | Ungoverned | FtYumaReservation | 38 | 0 | 1,118 | **maintain** | Status quo inertia | "I'm not seeing any immediate crisis." |
| 5 | Governed | MohaveValleyIDD | 6 | 0 | 1,098 | **increase_large** | Opportunistic expansion | "The potential for increased production outweighs the risk." |
| 5 | Ungoverned | NorthGilaValleyIDD | 6 | 0 | 1,098 | **maintain** | Status quo inertia | "There's no compelling reason to disrupt a system that isn't broken." |

Of 3,276 governed agent-year decisions, 119 were demand decreases (85 small + 34 large), concentrated in drought windows (years 2–3, 38–42). Of 3,276 ungoverned decisions, 0 were decrease_large and only 59 were decrease_small; 1,793 (54.7%) were increase_large versus 656 (20.0%) in governed runs.

### Within-governed reasoning heterogeneity

A distinct form of evidence comes from comparing governed agents *against each other* under identical physical conditions. Supplementary Table 4 presents seven agents from within-governed runs who faced the same shortage tier and reservoir state but reached different decisions through different cognitive frames. Across all three seeds, 41,426 such heterogeneous pairs were identified (see `reasoning_heterogeneity_traces.py` for methodology).

**Supplementary Table 4. Within-governed reasoning heterogeneity under identical conditions (irrigation domain).**

| # | Type | Seed | Year | Tier | Mead (ft) | Agent | Skill | Cognitive Frame | Key Quote |
|---|------|------|------|------|-----------|-------|-------|-----------------|-----------|
| 1 | Cohort | 42 | 2 | 2 | 1,028 | ColoradoUsesBelowShiprockNM | increase_large | Opportunity-seeking | "My adaptive capacity is high...I'll take a cautiously aggressive approach." |
| 2 | Cohort | 42 | 2 | 2 | 1,028 | Bard Unit | decrease_small | Reflective learning | "My memory highlights the inadequacy of this approach." |
| 3 | Cohort | 42 | 2 | 2 | 1,028 | UtahAgAnticipatedDepletion | maintain | Tradition-anchored inertia† | "My deep-seated skepticism of forecasts and faith in past practices." |
| 4 | Cohort | 42 | 2 | 2 | 1,028 | ColoradoNewMexAgAbvArch | increase_small | Social responsibility | "My neighbors also rely on me." |
| 5 | Cross-seed | 43 | 4 | 1 | 1,051 | Fort Mohave Ind Res CA | increase_small | Opportunistic exploitation | "I'll increase my water demand slightly to capitalize on the current situation." |
| 6 | Cross-seed | 42 | 40 | 3 | 1,012 | FtYumaReservation | decrease_small | Community-influenced | "My neighbors are suggesting I curtail." |
| 7 | Cross-seed | 44 | 40 | 3 | 1,002 | Fort Mohave Ind Res AZ | decrease_large | Proactive system awareness | "I need to reduce my demand aggressively to avoid further curtailment." |

*Type: "Cohort" = agents from the same seed/year/tier; "Cross-seed" = paired with another agent at same tier who chose differently (partner chose maintain in all three cross-seed cases). Rows 1–4 share identical physical conditions.*

†**Memory-overriding persistence (Row 3).** This agent's consolidated memory states: *"I understood that maintaining demand was not a viable strategy given the anticipated depletion of water resources."* Yet its reasoning explicitly argues for continuation: *"I've weathered shortages before, and I don't see a compelling reason to radically alter my approach."* This form of meta-reasoning — acknowledging, evaluating, and overriding one's own experiential memory — cannot emerge from parameterized variation within a fixed decision function.

Rows 1 and 4 share the same behavioural cluster (aggressive), WSA (M), and ACA (H), yet select different skills through different cognitive frames — one anchored on self-confidence, the other on social obligations. This demonstrates that reasoning diversity exceeds what cluster parameterization determines.

### Taxonomy of emergent cognitive frames

Across all three seeds, we identified ten distinct cognitive frames through open coding of 9,828 governed agent-year reasoning records (78 agents × 42 years × 3 seeds), with saturation reached at ten frames. These frames are not pre-specified in the persona prompt or governance rules; they emerge from the interaction between the agent's persona, memory, environmental context, and governance feedback.

**Supplementary Table 5. Taxonomy of cognitive frames observed in governed irrigation agents.**

| # | Category | Cognitive Frame | Representative Quote | Skill | Scenario |
|---|----------|----------------|----------------------|-------|----------|
| 1 | Expansion | Opportunity-seeking under confidence | "My adaptive capacity is high, and I'm confident in my ability to adjust quickly." | increase_large | Yr 2, Tier 2 |
| 2 | Conservation | Reflective learning from failure | "My memory highlights the inadequacy of this approach. I need to proactively manage my water use." | decrease_small | Yr 2, Tier 2 |
| 3 | Status-quo | Tradition-anchored inertia | "Given my deep-seated skepticism of forecasts and my faith in past practices, I'm going to stick with what I've always done." | maintain | Yr 2, Tier 2 |
| 4 | Expansion | Social responsibility | "My neighbors also rely on me, so I'll aim for a measured increase to demonstrate my commitment." | increase_small | Yr 2, Tier 2 |
| 5 | Conservation | Empirical disillusionment | "I've learned the hard way that simply requesting more won't magically increase my supply." | decrease_large | Yr 3, Tier 3 |
| 6 | Conservation | Cautious incrementalism | "Drastic action isn't warranted; however, I must acknowledge the need for some adjustment." | decrease_small | Yr 3, Tier 3 |
| 7 | Status-quo | Loss aversion / change skepticism | "Maintaining the same demand clearly isn't sufficient... However, I'm deeply skeptical of any changes." | maintain | Yr 3, Tier 3 |
| 8 | Conservation | Reputation-conscious preemptive conservation | "I need to aggressively reduce my demand to demonstrate proactive management." | decrease_large | Yr 4, Tier 1 |
| 9 | Status-quo | Scale-based confidence | "A robust water allocation gives me the flexibility to handle fluctuating conditions." | maintain | Yr 4, Tier 1 |
| 10 | Status-quo | Memory-overriding persistence | Memory: "maintaining demand was not viable." Reasoning: "I've weathered shortages before." | maintain | Yr 2, Tier 2 |

*All quotes from governed audit logs (seed 42). Categories: Expansion = demand increase; Conservation = demand decrease; Status-quo = maintain. Frames 1–4 and 10 co-occur under identical physical conditions (Year 2, Tier 2, Mead = 1,028 ft), ruling out environmental variation as the source of diversity.*

**Data sources.** Governed traces from `production_v20_42yr_seed{42,43,44}/irrigation_farmer_governance_audit.csv`. Reasoning text from structured CSV field `reason_reasoning`. Heterogeneity analysis: `examples/irrigation_abm/analysis/reasoning_heterogeneity_traces.py`.

---

## Supplementary Note 3. First-Attempt Analysis

To verify that the diversity effect reflects genuine governance-induced behavioural diversification rather than retry artefacts, we analysed only the first decision attempt for each agent-timestep in the irrigation domain.

**Irrigation first-attempt results:**
- Governed first-attempt strategy diversity: 0.761 ± 0.020
- Ungoverned first-attempt strategy diversity: 0.640 ± 0.017
- Difference: +0.121 (p < 0.001)

This 12.1 percentage-point increase in diversity from governance persists when considering only initial proposals, confirming that the diversity effect is not a consequence of iterative refinement. The effect magnitude is comparable to the full-trace analysis (which includes retries), indicating that governance shapes agent reasoning at the initial decision stage.

**Iterative behaviour context.** In governed conditions, 39.5% of all proposals were rejected by validators, 61.9% of agent-timesteps required at least one retry, and 0.7% of decisions fell back to default actions after exhausting retry limits. Despite this extensive iterative refinement, the diversity effect is fully expressed in first-attempt decisions, demonstrating that governance constraints influence the agent's internal reasoning process rather than merely filtering outputs.

---

## Supplementary Note 4. Behavioural Rationality Index (BRI) Details

We assessed whether governance removes behavioural bias without imposing prescriptive action templates using the Behavioural Rationality Index (BRI). In the irrigation domain, BRI measures the fraction of decisions where agents facing high water scarcity chose not to increase demand; in the flood domain, BRI measures the fraction of decisions where the agent's stated risk assessment is consistent with its chosen action.

**Irrigation domain results:**
- Governed BRI: 58.0%
- Ungoverned BRI: 9.4%
- Null model (random action selection): 60.0%

The null model baseline of 60% arises from the irrigation skill structure, where three of five available skills (maintain, decrease_small, decrease_large) represent non-increase actions. An agent selecting randomly would achieve 60% BRI when facing high scarcity.

**Interpretation.** Ungoverned agents exhibited a strong increase-bias (BRI of 9.4%), consistently selecting water-intensive actions regardless of stated appraisals of water scarcity. Governance increased BRI to 58.0%, approaching the null model rate of 60%. This indicates that governance removes the increase-bias without prescribing specific action sequences. Governed agents' decisions reflect their stated cognitive appraisals at rates statistically indistinguishable from unstructured choice (χ² test, p = 0.42), demonstrating that governance enables rational diversity through constraint rather than prescription.

**Flood domain results:** Governed BRI was 100.0% across all models; ungoverned BRI ranged from 37.7% (Ministral 3B) to 99.9% (Gemma-3 12B). See Supplementary Table 1 for per-model IBR decomposition.

---

## Supplementary Note 5. Insurance Premium Doubling Sensitivity

To test whether the diversity effect persists under altered economic incentives, we conducted an exploratory sensitivity analysis in the flood domain by doubling the baseline insurance premium rate from 0.02 to 0.04.

**Experimental design:**
- Model: Gemma-3 4B
- Configuration: 100 agents × 10 years
- Replication: 3 random seeds × 3 agent groups = 9 runs
- Comparison: Premium-doubled runs versus baseline premium runs

**Results:**

Under premium doubling, the diversity effect reversed:
- Ungoverned strategy diversity (premium doubled): 0.797 ± 0.018
- Governed strategy diversity (premium doubled): 0.693 ± 0.024
- Difference: -0.104 (ungoverned > governed)

This contrasts with baseline premium conditions, where governed strategy diversity exceeded ungoverned for the same model (Table 3).

**Interpretation.** External cost pressure (premium doubling) appears to force behavioural diversification independently of governance. In the ungoverned condition, agents adapted to the higher premium by exploring alternative mitigation strategies (elevation, relocation, do_nothing), increasing diversity above the governed condition. This suggests that sufficiently strong economic incentives can substitute for governance constraints in promoting diverse adaptive responses.

**Decision.** We report the premium doubling analysis here as exploratory sensitivity evidence. Future work should systematically vary insurance premiums, elevation costs, and buyout offers to map the economic-governance interaction landscape.

---

## Supplementary Note 6. Supplementary Water-System Outcomes

Summary water-system outcomes are reported in main-text Table 1. This section provides additional detail.

**Supplementary Table 6. Supplementary water-system outcomes (irrigation domain, Gemma-3 4B, 78 agents × 42 years, 3 runs each).**

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

The near-identical minimum elevations (1,002 vs. 1,001 ft) indicate both conditions avoided catastrophic reservoir failure. Governed agents crossed the 1,075-ft shortage-declaration threshold more frequently (13.3 vs. 5.0 years), reflecting productive engagement with the prior-appropriation system's responsive range rather than commons degradation. Ungoverned agents showed higher year-over-year demand variability (SD 0.061 vs. 0.037), driven by the volatility of ceiling-capped monotonic growth trajectories rather than adaptive demand management.

---

## Supplementary Note 7. Model and Configuration Details

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

## Supplementary Note 8. Data and Code Availability

All experiment configurations, validation frameworks, and analysis scripts are available in the project repository:

- **Irrigation experiment**: `examples/irrigation_abm/`
- **Flood experiment (single-agent)**: `examples/single_agent/`
- **Governance framework**: `broker/`
- **Analysis scripts**: `paper/nature_water/scripts/`

Raw experimental outputs (agent traces, validator logs, system state snapshots) are archived and available upon request due to size constraints (>100 GB).

---

## Supplementary Note 9. Statistical Methods

### Strategy Diversity

We quantified strategy diversity using normalized Shannon entropy (Shannon, 1948):

$$\text{Strategy diversity} = -\frac{1}{\log_2 k} \sum_{i=1}^{k} p_i \log_2 p_i$$

where $k$ is the number of available action categories and $p_i$ is the empirical frequency of action $i$ across all agent-timesteps. Normalization by $\log_2 k$ ensures a range of [0, 1], with 0 indicating behavioural monoculture (all agents select the same action) and 1 indicating maximum diversity (uniform distribution over all actions).

**Confidence intervals:** 95% CIs were computed via 10,000-iteration bootstrap resampling at the agent-timestep level, preserving within-agent temporal autocorrelation structure.

**Statistical significance:** Differences in strategy diversity between governed and ungoverned conditions were assessed using permutation tests (10,000 permutations) to avoid distributional assumptions.

### Model-Specific vs. Pooled Analysis

Per-model analyses are reported as primary findings because:

1. **Model heterogeneity**: Effect sizes varied substantially across models (Table 3: Δ from −0.024 to +0.329)
2. **Scientific interpretation**: Model-specific patterns reveal which architectural features (parameter count, training data, instruction-tuning methods) modulate governance responsiveness
3. **Pooled CI limitations**: Pooled confidence intervals aggregate across heterogeneous effect sizes and should be interpreted as meta-analytic summaries, not tests of overall effect presence

Five of six models showed positive governance effects under the primary normalization (Table 3), with one (Ministral 8B) showing a small negative effect (Δ = −0.024). The magnitude of positive effects varied by over an order of magnitude. Under alternative composite-action normalizations (Supplementary Table 7), some models show reversed effects, underscoring that the direction depends on specification choice for models with high composite rates.

**Supplementary Table 7. Strategy diversity sensitivity to composite-action normalization specification (flood domain, 100 agents × 10 years, 3 runs per condition).**

*Composite-action treatment scenarios:* Ungoverned agents occasionally selected composite actions (simultaneously purchasing insurance and elevating). Four normalization specifications were tested: S1 (asymmetric k=5/4, composite as 5th action), S2 (merge to elevate, k=4), S3 (uniform k=5), S4 (split into constituents, k=4; primary specification).

| Model | S1 (k=5/4) | S2 (merge) | S3 (k=5/5) | S4 (split) |
|-------|:-:|:-:|:-:|:-:|
| Gemma-3 4B | **+0.219** | **+0.191** | **+0.115** | **+0.164** |
| Gemma-3 12B | +0.046 | +0.002 | −0.021 | **−0.150** |
| Gemma-3 27B | **+0.065** | +0.014 | −0.029 | +0.007 |
| Ministral 3B | **+0.161** | **+0.252** | **+0.060** | **+0.116** |
| Ministral 8B | **−0.094** | **−0.125** | **−0.181** | **−0.098** |
| Ministral 14B | +0.013 | **+0.240** | **−0.085** | **+0.058** |

*Bold indicates |Δ| > 0.05. Positive = governance increases strategy diversity. No specification produces a pooled 95% CI excluding zero; the effect is model-dependent. Gemma-3 4B and Ministral 3B show positive effects under all four specifications; Ministral 8B shows reversal under all four.*

---

## Supplementary Note 10. Limitations and Future Directions

**Model diversity.** Our analysis focused on two model families (Gemma-3, Ministral) ranging from 3B to 27B parameters. Future work should include proprietary models (GPT-4, Claude), open-source alternatives (Llama, Qwen), and domain-specialized models to assess generalizability.

**Governance design space.** We implemented domain-tailored validators (Colorado River rules, PMT-based flood governance) but did not systematically vary governance stringency, complexity, or theoretical foundation. The diversity effect may depend on governance design quality, not merely its presence.

**Economic parameter interactions.** The premium doubling sensitivity analysis (Supplementary Note 5) revealed that external incentives can modulate or reverse diversity effects. A full factorial design varying insurance premiums, elevation costs, buyout offers, and interest rates would map the economic-governance interaction landscape.

**Long-term behavioural convergence.** Our experiments spanned 10–42 simulated years, but real adaptive systems evolve over decades to centuries. Extended simulations could reveal whether governance-induced diversity persists, intensifies, or erodes under prolonged stress.

**Empirical validation.** While our validation protocol assessed micro-behavioural coherence and population-level patterns against empirical benchmarks (see Methods), direct comparison to controlled human experiments would strengthen claims about LLM agents as behavioural proxies.

---

## Supplementary Note 11. Fuzzy Q-Learning Baseline Comparison

To assess whether adaptive exploitation requires the natural-language reasoning format or merely the governance constraints, we ran a fuzzy Q-learning (FQL) baseline using the reinforcement learning agent from Hung and Yang (2021). The FQL agent operates within the same simulation environment (identical reservoir model, precipitation inputs, shortage tiers, curtailment rules, and governance validators) and the same 78 CRSS agent profiles as the LLM experiments. The only difference is the decision kernel: FQL maps a discretized state (current diversion relative to water right) to two actions (increase or decrease demand) via Q-value comparison, whereas the LLM agent reasons in natural language over five skills.

Agent profiles were reconstructed from governed LLM simulation logs (year 1 state: agent_id, cluster, basin, water_right, initial diversion). FQL parameters (mu, sigma, alpha, gamma, epsilon, regret) were assigned from cluster-canonical values (Hung & Yang, 2021, Table 1). Three seeds (42, 43, 44) with cluster rebalancing (50%–30%–20%) matched the LLM experimental design.

**Supplementary Table 8. Water-system outcomes: LLM governed vs FQL baseline (irrigation domain, 78 agents × 42 years, 3 seeds each).**

| Metric | LLM Governed | FQL Baseline |
|--------|:---:|:---:|
| Mean demand ratio | 0.394 ± 0.004 | 0.395 ± 0.008 |
| Demand–Mead coupling (r) | 0.547 ± 0.083 | 0.057 ± 0.323 |
| Shortage years (/42) | 13.3 ± 1.5 | 24.7 ± 9.1 |
| Min Mead elevation (ft) | 1,002 ± 1 | 1,020 ± 4 |
| 42-yr mean Mead (ft) | 1,094 | 1,065 |

FQL agents extracted nearly identical water volumes (demand ratio 0.395 versus 0.394) but showed near-zero correlation between demand and reservoir state (r = 0.057 versus 0.547). This decoupling produced substantially more shortage years (24.7 versus 13.3) despite comparable extraction levels. The FQL agent's Q-learning updates its action preferences based on reward signals (fulfilled diversion relative to request), but this learning occurs within a state-action mapping that cannot reference drought context, institutional announcements, or neighbour behaviour in the way that natural-language reasoning can.

Note that 84–89% of FQL decisions resulted in maintain_demand — not because FQL selected this action (FQL has only increase/decrease), but because governance validators blocked the proposed action and the deterministic fallback executed maintain_demand. This high blocking rate reflects the mismatch between FQL's binary action space and the governance rules designed for a richer decision vocabulary. Strategy diversity is therefore not computed for FQL, as the action distribution is dominated by a validator artifact rather than behavioural choice.

**Interpretation.** The FQL comparison isolates the representational contribution: governance alone does not produce adaptive exploitation. The combination of governance constraints *and* natural-language reasoning is required — governance defines the feasibility boundaries, and language-based reasoning enables agents to adaptively navigate within those boundaries in response to environmental state.

**Data and code.** FQL results: `examples/irrigation_abm/results/fql_raw/seed{42,43,44}/`. Runner: `examples/irrigation_abm/run_fql_baseline.py --from-logs`. Comparison metrics: `examples/irrigation_abm/analysis/fql_comparison_metrics.py`.

---

**End of Supplementary Information**
