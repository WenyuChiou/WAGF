# Nature Water — Section 2: Results (v16 — style polish: no em dashes, short sentences, water-first)
## Date: 2026-02-24 | Word count: ~2,200 | Analysis format
## Structure: R1 institutions as cognitive infrastructure → R2 structured non-compliance → R3 adaptive vs arbitrary diversity → R4 cross-domain generalization
## Data: All numbers verified via nw_data_verification.py (basin-aggregate) + ibr_wsa_aca_decomposition.py + nw_flood_pmt_crosstab.py

---

## Results

### Without institutional framing, agents cannot reason about water conservation

Three experimental conditions reveal that institutional rules function as cognitive infrastructure for water-resource reasoning (Fig. 2, Extended Data Table 1; all irrigation results use Gemma-3 4B, 78 agents × 42 years). To assess whether agents make scarcity-appropriate decisions, we measure the Irrational Behaviour Rate (IBR): the fraction of decisions where an agent reports high water-shortage appraisal yet still proposes a demand increase. LLM (no validator) agents exhibited behavioural collapse, with IBR of 91% and 77-82% of all decisions being demand increases even when agents themselves assessed water shortage as severe. Governed LLM agents achieved IBR of 42%, a 49-percentage-point reduction, while extracting substantially more water (demand ratio, defined as requested volume divided by historical baseline allocation, of 0.394 versus 0.288). The unvalidated IBR (91%) far exceeds the null expectation under uniform random action selection (40%), indicating a strong directional bias toward demand increases that governance eliminates. We note that this null assumes agents select actions uniformly from the five available skills; alternative null models may yield different baselines.

The collapse of LLM (no validator) agents is not merely quantitative degradation but a qualitative shift. Without institutional rules defining shortage tiers, demand ceilings, and curtailment triggers, agents could not organize their reasoning around conservation. In the flood domain, governance reduced irrational behaviour tenfold (IBR 8.1% to 0.8%) while maintaining comparable behavioural diversity (EHE 0.846 versus 0.860; Extended Data Table 2). In the irrigation domain, LLM (no validator) agents collapsed into behavioural monoculture, whereas governed agents maintained differentiated strategies across the action space (Extended Data Table 1).

Governed agents extracted more water but responded more sensitively to drought. Lake Mead was consequently lower under governance (42-year mean 1,094 ft versus 1,173 ft) and governed agents triggered shortage conditions more frequently (13.3 versus 5.0 of 42 years). The higher shortage frequency reflects the consequence of adaptive exploitation rather than system failure: governed agents utilized more water during recovery periods while LLM (no validator) agents could not adjust. This pattern, higher extraction during abundance and proportionate response to scarcity signals, is consistent with drought-responsive allocation dynamics where institutional rules make higher use safe by ensuring curtailment during drought.

**Extended Data Table 1. Water-system outcomes and behavioural diversity across four experimental conditions (irrigation domain, Gemma-3 4B, 78 agents × 42 years, 3 runs each). "No Ceiling" removes only the demand-ceiling rule while retaining all 11 other governance rules. FQL = fuzzy Q-learning baseline (Hung and Yang, 2021; see Methods and Supplementary Note 11).**

| Metric | Governed LLM | LLM (no validator) | No Ceiling | FQL Baseline |
|--------|----------|------------|-----------------|--------------|
| Mean demand ratio | 0.394 ± 0.004 | 0.288 ± 0.020 | 0.440 ± 0.012 | 0.395 ± 0.008 |
| 42-yr mean Mead elevation (ft) | 1,094 | 1,173 | 1,069 | 1,065 |
| IBR (%) | 42.0 ± 4.2 | 90.6 ± 1.3 | 49.4 ± 1.4 | — |
| Shortage years (/42) | 13.3 ± 1.5 | 5.0 ± 1.7 | 25.3 ± 1.5 | 24.7 ± 9.1 |
| Min Mead elevation (ft) | 1,002 ± 1 | 1,001 ± 0.4 | 984 ± 11 | 1,020 ± 4 |
| Behavioural diversity (EHE) | 0.738 ± 0.017 | 0.637 ± 0.017 | 0.793 ± 0.002 | — |

*Three independent runs per condition (seeds 42, 43, 44). Demand ratio = requested volume / historical baseline allocation. IBR = Irrational Behaviour Rate: fraction of high-scarcity decisions (agent-reported WSA = H or VH) where the agent proposed a demand increase (lower is better; null expectation under uniform random action = 40%). Behavioural diversity (EHE) = normalized Shannon entropy H/log₂(k) over k action types (0 = all agents choose the same action; 1 = actions uniformly distributed; see Methods). "No ceiling" removes only the demand-ceiling rule (see next section). FQL uses the same reservoir model and governance rules but replaces natural-language reasoning with a Q-learning decision module (2-action: increase/decrease); IBR and behavioural diversity are not computed because 84-89% of FQL actions were rejected by governance rules rather than reflecting agent choice (Supplementary Note 11). See Supplementary Table 6 for additional water-system metrics.*

### Governed agents reveal structured non-compliance at institutional boundaries

The 42% governed IBR is not randomly distributed across the agent population. Decomposing decisions by agents' self-assessed Water Shortage Appraisal (WSA) and Adaptive Capacity Appraisal (ACA) reveals that non-compliance concentrates at a specific institutional boundary: the intersection of high scarcity awareness and high adaptive capacity.

In the high-scarcity quadrant (WSA = H or VH, ACA = H or VH), 54.8% of governed decisions still proposed demand increases, but every one of these proposals was rejected by governance rules (100% rejection rate in this quadrant). The governance effect on increase proposals is monotonically stronger at higher WSA levels, from a 17.5-percentage-point reduction at low WSA to a 65.8-percentage-point reduction at very high WSA. The high-threat/high-capacity rule triggered on 73.8% of decisions in this quadrant (Fig. 3a). LLM (no validator) agents in the same quadrant proposed increases at 95.0%.

This concentration reveals a cognitively structured pattern. Agents that perceive severe scarcity *and* assess themselves as highly capable are precisely those most likely to attempt demand increases, a reasoning pattern consistent with anticipatory extraction ("use it or lose it") observed in real drought-responsive allocation systems. The governance rules intercept these proposals before execution, and the natural-language reasoning traces record why agents attempted them. During Tier 3 shortage, for example, an agent reasoned: "my previous aggressive increase failed... given my scepticism of forecasts, I will cautiously increase," acknowledging failure while repeating it (Supplementary Note 2). This diagnostic capacity, observing what agents attempt at institutional boundaries rather than only what they execute, is not available in conventional agent-based water models where agents execute predetermined rules.

In the flood domain, governance produces a contrasting non-compliance structure. Rather than persistent boundary-testing, governed flood agents rapidly internalized Protection Motivation Theory (PMT)-consistent behaviour: only 0.8% of decisions were rejected, compared to 39.5% in irrigation. But this internalization came with a cost. Ninety-two percent of governed agents self-assessed coping appraisal at a single level (M), suggesting that governance success in flood may partially reflect compression of cognitive differentiation rather than genuinely diverse adaptive reasoning. The two domains thus reveal complementary institutional dynamics: irrigation governance creates a hard boundary that agents persistently test, while flood governance produces rapid compliance but narrower cognitive variation (Extended Data Table 2).

**Extended Data Table 2. Behavioural diversity and action distributions across three experimental conditions (flood domain, Gemma-3 4B, 100 agents × 10 years, 3 runs each).**

| Condition | Behavioural diversity (EHE) | IBR (%) | do_nothing (%) | insurance (%) | elevation (%) | relocation (%) |
|---|---|---|---|---|---|---|
| **Governed LLM** | **0.860 ± 0.063** | 0.8 ± 1.1 | 31.9 | 45.3 | 9.5 | 13.3 |
| **LLM (no validator)** | **0.846 ± 0.042** | 8.1 ± 1.7 | 32.9 | 46.2 | 9.5 | 11.4 |
| **Rule-based PMT** | **0.598 ± 0.017** | 0.0 ± 0.0 | 15.2 | 69.9 | 14.7 | 0.2 |

*Behavioural diversity (EHE) = normalized Shannon entropy H/log₂(k) over k = 4 action types (0 = monoculture; 1 = uniform); mean ± s.d. over 3 runs. IBR = Irrational Behaviour Rate: fraction of decisions classified as PMT-inconsistent via post-hoc rules, excluding the re-elevation rule (see Methods). Governed LLM and LLM (no validator) share identical agent personas, memory systems, and prompt templates; they differ only in whether governance validators are active. Rule-based agent uses stochastic PMT utility logic with parameterized agent heterogeneity (Supplementary Note 12). Post-relocation agent-years excluded.*

### A single institutional rule separates adaptive from arbitrary diversity

To identify which institutional rules enforce scarcity-appropriate behaviour, we removed a single rule, the demand-ceiling rule, which blocks demand-increase proposals when aggregate basin demand exceeds 6.0 million acre-feet (MAF). All eleven other rules were retained (the "no-ceiling" condition; see Methods).

Removing this one rule of twelve increased IBR from 42% to 49%, nearly doubled shortage years from 13.3 to 25.3, and dropped minimum Mead elevation to 984 ft below the Tier 3 shortage threshold (Extended Data Table 1). But removing the ceiling *increased* behavioural diversity from 0.738 to 0.793. Agents diversified further, but into extraction patterns that ignored their own scarcity assessments, producing higher demand ratios (0.440 versus 0.394) with more frequent shortage.

This establishes a distinction central to interpreting the governance effect: between *diversity* (a wider action distribution) and *adaptive diversity* (a wider action distribution where agents act consistently with their own scarcity appraisals; Figs. 2b and 3a). The demand ceiling does not suppress diversity; it channels diversity toward scarcity-appropriate patterns. Without it, agents diversify into individually rational but collectively maladaptive extraction, the hallmark of commons dilemmas that Ostrom (1990) identified as the target of institutional design.

Proposals submitted before any governance feedback already showed higher diversity (first-attempt behavioural diversity 0.761 governed versus 0.640 LLM no validator). This indicates that the governance context shapes the reasoning process itself, rather than diversity emerging post hoc through the rejection-retry mechanism (Supplementary Note 3). Governed LLM agents also produced higher behavioural diversity than hand-coded agents using the same behavioural theory with parameterized heterogeneity (EHE 0.860 versus 0.598 in flood; Extended Data Table 2). A fuzzy Q-learning baseline achieved comparable demand ratios but with 84-89% of decisions rejected by governance (Supplementary Note 11).

The demand ceiling is the only one of twelve governance rules linking individual proposals to aggregate basin state. Its removal demonstrates that governance-induced diversity is functionally adaptive, not a statistical artefact of constraint-based rejection. This experimental decomposition, isolating one institutional rule's contribution to behavioural coherence, is substantially more difficult in conventional agent-based models where institutional rules are typically embedded in procedural code.

### The governance effect generalizes across water hazard types and model scales

The governance mechanism that constrains irrational behaviour in chronic drought operates equivalently under acute flood hazard (Extended Data Table 2; Fig. 3). In the flood domain, 100 household agents made protective decisions (insurance, elevation, relocation, or inaction) over 10 years with stochastic flood events, a fundamentally different water context from continuous irrigation allocation. Governed LLM agents and LLM (no validator) agents achieved comparable behavioural diversity (EHE 0.860 versus 0.846, not significantly different), but governance reduced irrational behaviour tenfold (IBR 0.8% versus 8.1%). Rule-based PMT agents produced lower diversity (EHE 0.598), dominated by insurance with near-zero relocation (Extended Data Table 2).

Six models spanning two families and three parameter scales (3B to 27B parameters) confirmed that governance reduces irrational behaviour without suppressing adaptive diversity (Fig. 4). IBR decreased in all six models, with four reductions statistically significant (p < 0.05; Supplementary Table 2). The largest reductions occurred in models exhibiting the highest unvalidated violation rates (Gemma-3 4B: 8.1% to 0.6%; Ministral 3B: 5.0% to 0.3%). No model showed a significant change in behavioural diversity (ΔEHE range: −0.063 to +0.021; all 95% CIs include zero). This decoupling of IBR reduction from diversity change indicates that governance selectively removes theory-inconsistent decisions rather than constraining the action distribution.

The consistency across two water domains provides converging evidence that institutional rules function as behavioural guardrails for water-resource reasoning. Governance produced significant IBR reduction in four of six model scales, non-significant diversity change in all six, and structured non-compliance patterns in both irrigation and flood. Because domain-specific rule configurations replace redesigned decision logic across both applications, the approach addresses a longstanding limitation of agent-based water models: the need to rebuild decision modules for each application domain.

