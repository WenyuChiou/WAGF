# How and Why Do LLM-Driven Agents Differ from Traditional ABMs in Household Flood Adaptation? A Multi-Agent Governance Framework Approach

**Draft v2 — 2026-03-25**

*Prepared for Water Resources Research (WRR)*

---

## Highlights

- LLM-governed ABM produces structurally plausible flood adaptation
- Reasoning traces reveal barriers invisible to probability models
- Dynamic institutions affect equity more than aggregate behavior
- Protection motivation constructs evolve with cumulative exposure
- Action exhaustion explains rising inaction despite rising risk

---

## Abstract

Household flood adaptation is shaped by risk perception, institutional constraints, and social learning. Traditional rule-based agent-based models (ABMs) represent these processes through fixed behavioral rules and externally calibrated parameters. We developed a multi-agent LLM-governed ABM using the Water Agent Governance Framework (WAGF) to simulate 400 households making annual flood adaptation decisions over 13 years in the Passaic River Basin, New Jersey. The framework couples a three-tier governance architecture with Protection Motivation Theory constraints that enforce construct-action coherence. Each agent, powered by Gemma 3 4B, produces structured decisions with natural language reasoning traces. We compared LLM-ABM outputs against a survey-calibrated Bayesian ABM on the same study area. The two paradigms converge on renter insurance uptake and owner buyout participation, consistent with strong empirical constraints. They diverge on owner inaction (LLM [pending re-run]% vs. Traditional [pending re-run]%) and renter relocation (LLM [pending re-run]% vs. Traditional [pending re-run]%). These divergences suggest that narrative reasoning and institutional feedback produce different behavioral regimes than probability-based decision rules. Endogenous institutional agents alter adaptation equity more than aggregate adoption rates. Reasoning trace analysis reveals decision barriers, including action exhaustion, compounding hassle costs, and trust erosion, that probabilistic models cannot capture. These findings suggest that LLM-governed ABMs offer a structurally distinct approach to modeling coupled human-flood systems.

---

## 1. Introduction

Flood losses have increased globally over the past several decades, driven by changing hydroclimate conditions and expanding urban development in flood-prone areas (Wing et al., 2022). In the United States, the National Flood Insurance Program (NFIP) has paid over $70 billion in claims since its inception. Repetitive-loss properties account for a disproportionate share of total payouts (FEMA, 2020). Household-level adaptation, including flood insurance purchase, structural elevation, and voluntary buyout, represents a primary line of defense against flood losses. Adaptation decision-making varies across income levels, housing tenure types, risk perception states, prior flood experiences, and access to institutional support (Grothmann & Reusswig, 2006; Bubeck et al., 2012). Marginalized communities face compounding barriers: affordability constraints limit access to structural measures, information asymmetries reduce awareness of available programs, and historical distrust of government institutions dampens participation in voluntary programs (Rufat et al., 2015). How these varied behaviors interact with institutional feedback to produce aggregate adaptation outcomes remains a central challenge for flood risk management.

Agent-based modeling (ABM) has been widely applied to study household flood adaptation (Haer et al., 2017; de Ruig et al., 2022; Aerts et al., 2018). In the ABM framework, individual households are autonomous agents whose adaptive behaviors are governed by decision rules, and the model aggregates bottom-up choices to produce emergent system-level patterns. However, traditional rule-based ABMs require the modeler to define ex ante all possible behavioral pathways, typically through threshold-based decision trees or probabilistic choice models (An et al., 2021). Such approaches can reproduce aggregate patterns when carefully calibrated, but they cannot represent emergent reasoning, contextual judgment, or the influence of narrative memory on risk perception (Grothmann & Reusswig, 2006). Furthermore, rule-based models have limited capacity for endogenous institutional feedback. The co-evolution (i.e., bidirectional interactions) between government policy responses, insurance market adjustments, and household adaptive behaviors typically requires hard-coding institutional decision rules rather than allowing them to emerge from simulation dynamics.

Recent advances in large language models (LLMs) offer a potential pathway to address these limitations. LLMs can serve as decision engines that generate natural language reasoning, maintain persona-specific memory, and differentiate behavioral responses across heterogeneous agent profiles (Park et al., 2023; Gao et al., 2024). Several studies have demonstrated that LLM-based agents can produce plausible social behaviors in controlled settings (Park et al., 2023; Li et al., 2024). However, applying LLMs to domain-specific decision-making in coupled natural-human systems introduces challenges. Small-capacity models are prone to generating physically implausible or domain-inconsistent outputs (Huang et al., 2025), producing decisions that may be linguistically coherent but violate real-world feasibility constraints. Without systematic constraint enforcement, LLM-generated decisions may drift from the behavioral theory motivating the simulation.

However, few studies have systematically compared LLM-driven ABM outputs against traditional survey-calibrated ABMs on the same study area. It remains unclear how endogenizing institutional decision-making (i.e., allowing government and insurance agents to adapt their policies within the simulation) alters household adaptation trajectories relative to fixed-parameter institutional assumptions. The reasoning traces that LLM agents produce remain unexplored as a source of behavioral insight. Whether the decision rationales they generate align with established flood adaptation theories is unknown.

To address these research gaps, we developed the Water Agent Governance Framework (WAGF), a multi-agent LLM-governed ABM that couples institutional and household decision-making through a three-tier sequential governance architecture. We adopt five psychological constructs grounded in Protection Motivation Theory (Rogers, 1983) and its extensions to flood adaptation (Grothmann & Reusswig, 2006): threat perception (TP) and coping perception (CP) from the original PMT framework, supplemented by stakeholder perception (SP), social capital (SC), and place attachment (PA) drawn from flood-specific behavioral research. These five constructs serve as the psychological dimensions along which agents assess flood risk and evaluate adaptive responses in RQ3. We pursue three objectives: (1) compare LLM-driven and traditional ABM adaptation outcomes on the same study area, (2) isolate the effect of endogenous institutional decision-making on household adaptation equity, and (3) examine whether LLM-generated reasoning traces produce behavioral insight consistent with established psychological constructs. We address these objectives through three research questions:

- **RQ1**: How and why do household flood adaptation behaviors differ between an LLM-driven ABM and a traditional ABM?
- **RQ2**: How do government subsidy and insurance pricing adjustments affect adaptation outcomes across households with different socioeconomic characteristics?
- **RQ3**: How do household psychological constructs (i.e., TP, CP, SP, SC, and PA) evolve under repeated flood exposure, and how do their dynamics shape adaptation behavior?

We characterized model behavior through three diagnostics assessing micro-level action coherence, macro-level empirical plausibility against independently sourced benchmarks, and cognitive consistency through pre-experiment persona probing. The remainder of this paper is organized as follows. We introduce the study area in Section 2. The model architecture, agent initialization, governance rules, and diagnostics framework are presented in Section 3. Results for the three research questions and cross-seed robustness analysis appear in Section 4. Implications, limitations, and future work are discussed in Section 5, followed by conclusions in Section 6.

---

## 2. Study Area

The Passaic River Basin (PRB) is located in northern New Jersey and drains approximately 2,400 km^2 across portions of 10 counties (Figure 1). The basin encompasses 27 census tracts spanning urban, suburban, and semi-rural communities. The PRB is one of the most flood-prone urban watersheds in the northeastern United States, with a history of repetitive flood losses dating back to the early 20th century (USACE, 2014). Major flood events within the simulation period include Hurricane Irene (2011), Hurricane Sandy (2012), and Hurricane Ida (2021), along with multiple nor'easters that produced riverine and pluvial flooding. The basin's topography, a combination of steep uplands and low-lying floodplains, creates rapid hydrologic response that concentrates flood risk in densely populated downstream communities.

The PRB exhibits substantial demographic heterogeneity. Household incomes range from less than $25,000 to more than $75,000, with significant populations of marginalized households characterized by low income (i.e., below $50,000), high housing cost burden (i.e., exceeding 30% of income), or limited transportation access (i.e., no vehicle). NFIP participation rates vary widely across communities, and the New Jersey Department of Environmental Protection (NJDEP) has operated the Blue Acres buyout program since 1995, acquiring repetitive-loss properties in flood-prone areas (NJDEP, 2020). This combination of recurring flood hazard, demographic diversity, and active institutional programs makes the PRB a well-suited case study for investigating the co-evolution of household adaptive behaviors and institutional responses.

---

## 3. Methods

We present the WAGF architecture (Section 3.1), agent design (Section 3.2), institutional agents (Section 3.3), governance pipeline (Section 3.4), memory and social channels (Section 3.5), experimental design (Section 3.6), and model diagnostics (Section 3.7).

### 3.1 Framework Architecture

WAGF operates as a three-tier sequential decision framework that couples institutional and household decision-making within each annual simulation cycle (Figure 2). The three tiers, government, insurance, and households, execute sequentially so that each tier's decisions propagate as updated institutional parameters to the subsequent tier.

The framework implements a six-stage governance pipeline for each agent decision: (1) context assembly, where the agent receives its demographic profile, flood history, memory, social information, and current institutional parameters; (2) LLM generation, where the language model produces a structured decision with reasoning; (3) parsing, where the raw output is converted into a typed decision record; (4) validation, where five categories of validators (Physical, Thinking, Personal, Social, and Semantic) check the decision against domain constraints; (5) approval or retry, where rejected decisions trigger up to three re-generation attempts with targeted feedback explaining the violation; and (6) execution, where approved decisions update the simulation state.

All three tiers use Gemma 3 4B (Google, 2025), a locally deployed open-source language model with 4 billion parameters. We selected this model to represent a resource-constrained language model. This choice demonstrates that credible coupled human-natural system simulations are achievable without reliance on proprietary or computationally expensive models.

### 3.2 Agent Design

We simulated 400 household agents (200 owner-occupied, 200 renter-occupied) in a 2x2 factorial design crossing marginalization status (MG/NMG) with housing tenure (owner/renter), yielding 100 agents per cell. We assigned agent-specific flood exposure using 13 years of spatially distributed flood depth raster grids (2011-2023) derived from PRB hydrologic records. Each agent's location determines its flood depth in any given year, producing heterogeneous hazard experience across the population. A household is classified as marginalized if its annual income is below $50,000, its housing cost burden exceeds 30% of income, or it lacks vehicle access, consistent with social vulnerability indices in environmental justice research (Rufat et al., 2015). Demographic attributes (i.e., income, household size, education, and employment) were sampled from distributions derived from a New Jersey household survey (n = 755).

Owner-occupied households choose among four actions at each annual time step: buy_insurance (NFIP flood insurance), elevate_house (structural elevation above base flood elevation), buyout_program (voluntary acquisition through Blue Acres), and do_nothing. Renter households choose among three actions: buy_contents_insurance, relocate, and do_nothing.

Each agent produces a structured JSON decision record containing the chosen action and self-assessed construct ratings on a five-point scale (VL, L, M, H, VH) for TP, CP, SP, SC, and PA. The record also includes a natural language reasoning trace explaining the decision rationale. Flood zone assignment reflects the empirical pattern that marginalized communities are disproportionately located in flood-prone areas (Wing et al., 2022): MG agents are assigned 70% to Special Flood Hazard Areas (SFHAs) and 30% to lower-risk zones, while NMG agents are assigned 50/50. Replacement cost values (RCVs) for owner-occupied homes follow lognormal distributions with medians of $280,000 (MG) and $400,000 (NMG).

We designed a default-override decision structure informed by behavioral decision theory (Samuelson & Zeckhauser, 1988). Inaction (do_nothing) is the explicit default. To override inaction, an agent must pass a three-gate filter: (1) Is the flood risk urgent enough to act? (2) Is the adaptation financially affordable? (3) Is the disruption worth the benefit? This structure operationalizes the status quo bias and present bias documented in household flood adaptation research (Gallagher, 2014). For elevation and buyout, the agent's decision context describes concrete PRB-specific feasibility barriers, including local permitting requirements, specialized contractor scarcity (fewer than 12 firms in northern New Jersey), federal grant competition (2-5 year timelines), and temporary relocation costs. These experiential barriers replace population-level adoption statistics that individual agents cannot observe.

### 3.3 Institutional Agents

We modeled two institutional agents that operate above the household tier and adjust policy parameters annually based on observed community outcomes.

The government agent (representing NJDEP) observes the following metrics each year: total community flood damage ($), cumulative elevation rate (fraction of eligible owners who have elevated), and the proportion of marginalized households in the agent population. It selects one of five actions: increase subsidy by 5%, increase by 2.5%, maintain current rate, decrease by 2.5%, or decrease by 5%. The subsidy rate is bounded between 20% and 95%.

The insurance agent (representing FEMA's Community Rating System) observes: the loss ratio (claims paid divided by premiums collected), the number of currently insured households, and the current CRS class level. It selects among the same five adjustment options (plus or minus 5%, plus or minus 2.5%, or maintain) for the CRS discount, which is bounded between 0% and 45%.

Both institutional agents use a hybrid design: Python code computes summary metrics from the simulation state, and the LLM selects the policy action based on those metrics embedded in a structured prompt. This design ensures that institutional reasoning is grounded in quantitative indicators while allowing the language model to weigh competing objectives (e.g., equity vs. fiscal sustainability). The sequential ordering (i.e., government sets subsidy, then insurance sets CRS discount, then households decide) ensures that household agents observe the current year's institutional parameters when making their decisions.

### 3.4 Governance Pipeline

The governance pipeline enforces domain-theoretic coherence through five validator categories.

Thinking validators check whether the agent's chosen action is consistent with its self-assessed threat and coping appraisals. Each cell in the TP-by-CP matrix specifies the set of actions consistent with that appraisal state. Agents reporting high threat perception and high coping perception are permitted to pursue structural measures (elevation, buyout, insurance). Agents with low threat perception are restricted to do_nothing or optional insurance, reflecting the prediction that protective motivation requires both perceived vulnerability and perceived efficacy (Grothmann & Reusswig, 2006).

Physical validators check action preconditions. An agent cannot elevate a house that is already elevated, cannot participate in buyout after relocation, and cannot purchase insurance on a property that has been bought out.

Personal validators enforce affordability constraints. An action is blocked if its estimated cost exceeds three times the agent's annual income, computed from income, existing debt burden, and available subsidy.

Social validators check consistency between the agent's stated social capital assessment and the social information available in its context.

Semantic validators catch parsing failures and structurally malformed outputs.

Elevation requires a cumulative flood count of at least two, consistent with FEMA's repetitive loss definition. When a proposed action is rejected by any validator with ERROR severity, the agent receives up to three retry attempts with targeted feedback explaining the specific violation. WARNING-level violations are logged but do not block the action. If all retry attempts are exhausted, the agent defaults to do_nothing, an outcome we term involuntary non-adaptation (i.e., the agent intended to act but was blocked by a binding feasibility constraint). This mechanism distinguishes deliberate inaction from constrained non-participation. The income-dependent affordability threshold produces differential constraint-binding rates across income groups, a structural consequence of the feasibility gate rather than programmed disparate treatment.

### 3.5 Memory and Social Channels

Each agent maintains a memory store managed by a weighted-ranking memory engine. Memory retrieval computes a composite score:

S = W_r x R + W_i x I + W_c x C

where S is the retrieval priority score, R is recency (i.e., exponential decay from the event year), I is importance (i.e., emotional encoding from flood damage severity), C is contextual relevance (i.e., semantic similarity to the current decision prompt), and W_r = 0.3, W_i = 0.5, W_c = 0.2 are fixed weights. Memories undergo stochastic consolidation: high-importance memories are more likely to persist across years, while low-importance memories decay. This produces heterogeneous memory profiles even among agents with identical flood exposure histories.

We modeled three social information channels available to each agent at the beginning of every annual decision cycle. Gossip (i.e., local peer information based on observed neighbor actions) represents the most proximate social signal: each agent receives a summary of the adaptive actions taken by its five spatially nearest neighbors in the previous year. Social media provides community-wide aggregate statistics, including the overall proportion of agents who purchased insurance, elevated, or relocated in the previous year. News media delivers flood event reporting with PRB-specific context when a flood event occurs, including damage estimates and affected areas. In Year 1, when no prior neighbor actions exist, the gossip channel delivers an inaction baseline to provide a neutral starting condition.

A domain-specific reflection module synthesizes the year's flood experience, action outcomes, and governance feedback into a consolidated memory entry. This entry informs the following year's decision context.

### 3.6 Experimental Design

We conducted three experimental conditions to isolate the effects of LLM-based reasoning and institutional endogenization.

The Full Model runs the complete WAGF three-tier architecture with 3 random seeds (42, 123, 456) over 13 years with 402 agents (400 households plus 2 institutional agents). Each seed produces 5,200 household-year decisions (200 owners plus 200 renters times 13 years), for a total of 15,600 decisions across seeds.

Ablation A replays the Full Model's institutional policy trajectory (i.e., the exact subsidy and CRS discount sequence from each seed) through the household tier, serving as a manipulation check to verify that observed behavioral differences arise from household-level reasoning rather than institutional parameter variation.

Ablation B fixes institutional parameters at traditional ABM defaults (subsidy rate = 50%, CRS discount = 0%) for all 13 years, isolating the effect of institutional endogenization by removing the government and insurance agents while preserving LLM-based household reasoning.

For cross-paradigm comparison, we reference results from a survey-calibrated Bayesian ABM [FLOODABM reference] that simulates approximately 52,000 households across 27 census tracts in the PRB over the same 2011-2023 period using 15 Monte Carlo runs. We frame this comparison as structural rather than statistical, because the two models differ in agent count (400 vs. 52,000), decision mechanism (language reasoning vs. Bayesian regression), and institutional architecture (endogenous three-tier vs. fixed parameters). These differences preclude direct statistical testing between models. The Bayesian ABM computes action probabilities from survey-trained posteriors, which are then sampled through Bernoulli trials. Its threat perception decays exponentially between flood events, while coping perception, stakeholder perception, social capital, and place attachment remain static throughout the simulation. The Bayesian ABM has no institutional agents and no social interaction between agents. Aggregate rate convergence or divergence between the two models reveals where these structural differences matter rather than which model is correct (Oreskes et al., 1994). Each Full Model seed required approximately [pending] hours of wall-clock time on a single workstation with an NVIDIA RTX [pending] GPU.

### 3.7 Model Diagnostics

We characterized model behavior through three diagnostics that assess whether agent decisions are internally coherent, empirically plausible, and reliably produced. Construct-action coherence measures the fraction of decisions where the chosen action falls within theory-predicted options given the agent's self-assessed TP and CP. Four empirical benchmarks compare aggregate behavior against independently sourced ranges (Table 1). Pre-experiment construct reliability testing, conducted before any simulation, probed 2,700 controlled scenarios (15 demographic archetypes x 6 flood vignettes x 30 replicates) to assess whether the language model produces consistent construct ratings for identical demographic-situational configurations. Full diagnostic results, including specific values and additional benchmarks, are reported in Section 4.1.

---

## 4. Results

### 4.1 Model Diagnostics

Table 1 summarizes the four primary empirical benchmarks used to assess macro-level behavioral plausibility.

**Table 1.** Empirical benchmarks for macro-level behavioral plausibility. Values are three-seed means. Empirical ranges are drawn from independently sourced data (see Section 3.7 for sources).

| Benchmark | Three-Seed Mean | Empirical Range | Status |
|-----------|----------------|-----------------|--------|
| Insurance rate (SFHA) | 0.469 | 0.30 - 0.60 | Within range |
| Cumulative elevation rate | 0.248 | 0.10 - 0.35 | Within range |
| Buyout participation rate | 0.219 | 0.05 - 0.25 | Within range |
| Post-flood inaction rate | 0.480 | 0.35 - 0.65 | Within range |

Construct-action coherence (CACR = 0.855 +/- 0.006) indicates that 85.5% of all agent decisions are consistent with PMT predictions given the agent's self-assessed TP and CP. The remaining 14.5% of decisions include both genuine PMT-inconsistent choices (e.g., low-TP agents purchasing insurance, consistent with social influence) and edge cases at construct boundaries (e.g., M/M appraisals where multiple actions are defensible). No hallucinated actions (i.e., actions outside the agent's eligible set) were observed across any seed (R_H = 0.000).

### 4.2 RQ1: Behavioral Comparison Between LLM-ABM and Traditional ABM

**The two frameworks converge on low-frequency protective actions and diverge on high-frequency choices.** We compared annual action rates between the LLM-ABM (seed 42, weighted memory; seeds 123 and 456 pending) and FLOODABM across 13 years for six household actions (Figure X, Table X). Mean absolute difference (MAD) and Pearson temporal correlation quantify the magnitude and directional agreement of year-by-year trajectories.

Owner elevation (MAD = 1.5 percentage points) and owner buyout participation (MAD = 0.6 pp) converge between frameworks. Both models produce cumulative elevation rates below 5% and buyout rates below 2%, consistent with the empirical observation that structural flood protection and managed retreat remain rare even in repeatedly flooded communities (de Ruig et al., 2022; Mach et al., 2019). Renter contents insurance shows moderate agreement (MAD = 4.8 pp) with strong temporal correlation (r = +0.96, p < 0.001), indicating that the two frameworks track the same flood-driven insurance dynamics despite different decision mechanisms.

**Owner insurance and renter relocation diverge substantially.** Owner insurance rates in the LLM-ABM remain stable near 33% across years, while FLOODABM rates decline from 30% to 19% over the simulation period (MAD = 14.2 pp). The divergence reflects a structural difference in flood memory: FLOODABM's threat perception decays exponentially between flood events, reducing insurance renewal motivation in dry years, while LLM agents re-evaluate risk each year using accumulated flood memories that decay more slowly. Renter relocation shows the largest divergence (MAD = 20.8 pp): FLOODABM produces ~24% annual relocation through Bernoulli sampling of survey-calibrated probabilities, while the LLM-ABM produces ~2%. Owner inaction diverges in the opposite direction (MAD = 15.5 pp): LLM owners show lower do-nothing rates (~48%) than FLOODABM (~63%).

**Reasoning traces reveal barriers that probability-based models omit.** We analyzed the natural-language reasoning text from all 5,200 household-year decisions (seed 42) to identify what considerations agents articulate when choosing each action (Table X). Among agents choosing do_nothing (N = 2,586), 67.5% reference fatalistic language (e.g., "cannot afford," "nothing I can do," "beyond my means") and 70.0% reference feasibility barriers (e.g., "contractors," "permits," "months of construction"). These agents are not uninformed about flood risk: 99.7% reference flood experience in their reasoning. The co-occurrence of high experiential awareness with fatalistic and feasibility language is consistent with the adaptation deficit concept, where households perceive risk but lack the capacity or options to act (Bubeck et al., 2012).

Among the 94 renter agents who chose relocation, 100% reference relocation-specific barriers (e.g., "security deposit," "lease," "moving costs," "social ties") in their reasoning. This suggests that the LLM-ABM's low relocation rate (2% vs. FLOODABM's 24%) reflects the intention-action gap documented in protective action research (Grothmann & Reusswig, 2006): survey-calibrated models capture stated relocation intention, while LLM reasoning incorporates the post-intentional barriers that suppress realized relocation. Among agents choosing elevation (N = 465), 95.9% reference institutional support (subsidy, grants, FEMA programs), and 60.2% reference feasibility barriers (contractor scarcity, permitting timelines). Elevation decisions in the LLM-ABM are not cost-driven alone but reflect agents weighing institutional access against logistical obstacles, a deliberative process that Bernoulli sampling from calibrated probabilities cannot represent.

[Note: Numbers from seed_42 only. Will update with 3-seed pooled statistics when seeds 123 and 456 complete.]

### 4.3 RQ2: Institutional Endogenization and Adaptation Equity

[Results pending re-run completion]

### 4.4 RQ3: Psychological Construct Dynamics Under Repeated Exposure

[Results pending re-run completion]

### 4.5 Cross-Seed Robustness

[Results pending re-run completion]

---

## 5. Discussion

### 5.1 Implications for LLM-ABM in Water Resources

[Placeholder: Discuss what the convergence and divergence patterns between LLM-ABM and traditional ABM mean for the field. Address the structural plausibility framing. Consider how reasoning traces provide behavioral insight unavailable from probability-based models.]

### 5.2 Comparison with Traditional ABMs

[Placeholder: Discuss the fundamental architectural differences (endogenous institutions, dynamic psychology, social channels) and how they produce different behavioral regimes. Address whether the LLM-ABM's lower inaction rate and lower renter relocation rate are more consistent with observed behavior than the traditional ABM's calibrated probabilities. Reference the intention-action gap in survey-calibrated models (Bubeck et al., 2012).]

### 5.3 Limitations

[Placeholder: Address the following limitations.
- Single LLM (Gemma 3 4B) limits generalizability across model architectures.
- 400 agents vs. 52,000 in FLOODABM limits statistical power for subgroup analysis.
- Three seeds provide limited sampling of LLM stochasticity.
- Structural comparison cannot determine which model is closer to ground truth.
- PMT construct self-assessment relies on the LLM's interpretation of psychological scales.
- Memory decay parameters are not empirically calibrated.
- No agent-to-agent direct communication beyond the three social channels.
- Prompt sensitivity: results depend on prompt design choices documented in Section 3.2.]

### 5.4 Future Work

[Placeholder: Address scaling to larger agent populations, multi-model ensembles, integration with hydrodynamic models for real-time flood mapping, empirical calibration of memory parameters against longitudinal survey data, and extension to other water resource domains (drought adaptation, water allocation).]

---

## 6. Conclusions

[Placeholder: Summarize contributions to each RQ. Restate that LLM-governed ABMs with institutional feasibility constraints produce structurally plausible adaptation dynamics. Emphasize the reasoning trace analysis as a distinctive contribution. Note implications for flood risk management policy evaluation.]

---

## Data Availability Statement

The simulation code, agent initialization data, and analysis scripts are available at [repository URL]. Raw LLM outputs (reasoning traces) for all seeds are archived at [archive URL]. The traditional ABM (FLOODABM) outputs used for comparison are available from [source].

---

## Acknowledgments

[Placeholder]

---

## References

Aerts, J. C. J. H., Botzen, W. J., Clarke, K. C., Cutter, S. L., Hall, J. W., Merz, B., Michel-Kerjan, E., Mysiak, J., Surminski, S., & Kunreuther, H. (2018). Integrating human behaviour dynamics into flood disaster risk assessment. *Nature Climate Change*, 8(3), 193-199.

An, L., Grimm, V., Sullivan, A., Turner, B. L., Malleson, N., Heppenstall, A., Vincenot, C., Robinson, D., Ye, X., Liu, J., Schulte, E., & Tang, W. (2021). Challenges, tasks, and opportunities in modeling agent-based complex systems. *Ecological Modelling*, 457, 109685.

Bubeck, P., Botzen, W. J., & Aerts, J. C. J. H. (2012). A review of risk perceptions and other factors that influence flood mitigation behavior. *Risk Analysis*, 32(9), 1481-1495.

de Ruig, L. T., Haer, T., de Moel, H., Botzen, W. J., & Aerts, J. C. J. H. (2022). A micro-scale cost-benefit analysis of building-level flood risk adaptation measures in Los Angeles. *Water Resources Research*, 58(6), e2021WR031294.

FEMA. (2020). *National Flood Insurance Program: Flood Insurance Manual*. Federal Emergency Management Agency.

Gallagher, J. (2014). Learning about an infrequent event: Evidence from flood insurance take-up in the United States. *American Economic Journal: Applied Economics*, 6(3), 206-233.

Gao, C., Lan, X., Li, N., Yuan, Y., Ding, J., Zhou, Z., Xu, F., & Li, Y. (2024). Large language models empowered agent-based modeling and simulation: A survey and perspectives. *Humanities and Social Sciences Communications*, 11, 1014.

Grimm, V., Revilla, E., Berger, U., Jeltsch, F., Mooij, W. M., Railsback, S. F., Thulke, H.-H., Weiner, J., Wiegand, T., & DeAngelis, D. L. (2005). Pattern-oriented modeling of agent-based complex systems: Lessons from ecology. *Science*, 310(5750), 987-991.

Grothmann, T., & Reusswig, F. (2006). People at risk of flooding: Why some residents take precautionary action while others do not. *Natural Hazards*, 38(1-2), 101-120.

Haer, T., Botzen, W. J., de Moel, H., & Aerts, J. C. J. H. (2017). Integrating household risk mitigation behavior in flood risk analysis: An agent-based model approach. *Risk Analysis*, 37(10), 1977-1992.

Huang, L., Yu, W., Ma, W., Zhong, W., Feng, Z., Wang, H., Chen, Q., Peng, W., Feng, X., Qin, B., & Liu, T. (2025). A survey on hallucination in large language models: Principles, taxonomy, challenges, and open questions. *ACM Computing Surveys*, 57(3), 1-38.

Hung, C.-L. J., & Yang, Y. C. E. (2021). An agent-based modeling approach for the exploration of water-agriculture-economic feedback. *Water Resources Research*, 57(11), e2021WR030528.

Li, J., Zhang, R., Chen, Y., Yin, H., & Ge, Y. (2024). Agent-based simulation meets large language models: A survey. *arXiv preprint arXiv:2405.13966*.

Mach, K. J., Kraan, C. M., Hino, M., Siders, A. R., Johnston, E. M., & Field, C. B. (2019). Managed retreat through voluntary buyouts of flood-prone properties. *Science Advances*, 5(10), eaax8995.

NJDEP. (2020). *Blue Acres Buyout Program Annual Report*. New Jersey Department of Environmental Protection.

Oreskes, N., Shrader-Frechette, K., & Belitz, K. (1994). Verification, validation, and confirmation of numerical models in the earth sciences. *Science*, 263(5147), 641-646.

Park, J. S., O'Brien, J. C., Cai, C. J., Morris, M. R., Liang, P., & Bernstein, M. S. (2023). Generative agents: Interactive simulacra of human behavior. In *Proceedings of the 36th Annual ACM Symposium on User Interface Software and Technology* (pp. 1-22).

Rogers, R. W. (1983). Cognitive and psychological processes in fear appeals and attitude change: A revised theory of protection motivation. In J. T. Cacioppo & R. E. Petty (Eds.), *Social Psychophysiology: A Sourcebook* (pp. 153-176). Guilford Press.

Rufat, S., Tate, E., Burton, C. G., & Maroof, A. S. (2015). Social vulnerability to floods: Review of case studies and implications for measurement. *International Journal of Disaster Risk Reduction*, 14, 470-486.

Samuelson, W., & Zeckhauser, R. (1988). Status quo bias in decision making. *Journal of Risk and Uncertainty*, 1(1), 7-59.

USACE. (2014). *Passaic River Basin: Flood Risk Management Feasibility Study*. U.S. Army Corps of Engineers.

Wing, O. E. J., Bates, P. D., Smith, A. M., Sampson, C. C., Johnson, K. A., Fargione, J., & Morefield, P. (2022). Inequitable patterns of US flood risk in the Anthropocene. *Nature Climate Change*, 12(2), 156-162.

---

## Supporting Information

**Text S1.** Extended validation diagnostics, including 12 institutional trajectory benchmarks, prompt sensitivity analysis, and metrics falling outside target ranges.

**Table S1.** Full empirical benchmark table with 8 metrics, weights, and three-seed statistics.

**Table S2.** PMT construct-action coherence matrix for owner and renter agents.

**Table S3.** Governance validator specification table (14 validators, 5 categories).

**Figure S1.** Agent spatial distribution across PRB census tracts.

**Figure S2.** Institutional parameter trajectories (subsidy rate and CRS discount) across three seeds.

**Figure S3.** Year-by-year action distributions for all four agent cells (MG-Owner, NMG-Owner, MG-Renter, NMG-Renter).
