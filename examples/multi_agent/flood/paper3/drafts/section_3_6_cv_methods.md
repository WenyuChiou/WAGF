# Section 3.6: Calibration and Validation Protocol

Agent-based models face persistent credibility challenges owing to the absence of standardized validation protocols (Grimm et al., 2005; Windrum et al., 2007). LLM-governed ABMs introduce additional concerns: how do we distinguish genuine emergent behavior from LLM hallucination, and how do we ensure that system-level patterns arise from theoretically grounded micro-processes rather than statistical artifacts? The multi-agent architecture of the present model---400 heterogeneous households interacting with government and insurance agents across a 13-year horizon---makes validation both more necessary and more demanding than in single-agent applications, introducing three additional concerns beyond standard POM: (i) inter-tier consistency, where institutional decisions must themselves fall within plausible policy trajectories; (ii) feedback coupling, where household behavior responds to institutional signals and vice versa; and (iii) emergent inequality, where demographic disparities arise from the intersection of agent heterogeneity and institutional constraints rather than from any single parameter.

We adopt a three-level validation framework extending Pattern-Oriented Modeling (Grimm et al., 2005; Grimm & Railsback, 2012), supplemented by an emergence taxonomy and equity validation protocol specific to multi-agent LLM-ABMs.

## Level 1: Micro-Level Action Coherence

L1 validation assesses whether individual agent decisions satisfy domain-theoretic constraints. We compute three metrics over all agent-timestep decisions:

**Construct-Action Coherence Rate (CACR)**: The proportion of decisions consistent with Protection Motivation Theory (Rogers, 1983; Grothmann & Reusswig, 2006) given the agent's threat perception (TP) and coping perception (CP) labels. We distinguish CACR_raw---unassisted LLM coherence before governance filtering---from CACR_final, the system-level coherence after validation. The gap (CACR_final - CACR_raw) quantifies governance contribution. In the multi-agent context, we report CACR separately by agent type (household owner, household renter, government, insurance) because type-appropriate reasoning quality may vary even when all tiers use the same underlying LLM. We additionally report CACR by PMT quadrant (TP_high/low × CP_high/low) to detect systematic reasoning failures in specific appraisal regions. We require CACR_final >= 0.80.

**Hallucination Rate (R_H)**: The fraction of decisions proposing physically impossible actions (e.g., re-elevating an already-elevated home, renters attempting structural modifications, government proposing actions outside its defined set). We require R_H <= 0.10 to ensure that LLM outputs respect domain constraints.

**Effective Behavioral Entropy (EBE)**: Shannon entropy of the action distribution, normalized by the theoretical maximum log2(K) for K distinct actions. The resulting ratio (0 = degenerate single-action, 1 = uniform random) provides a distributional reference: a credible model should exhibit structured diversity (0.1 < EBE_ratio < 0.9), neither collapsing to a single dominant action nor behaving as a random number generator.

### LLM-Specific Validation Concerns

The use of a single small language model (Gemma 3 4B, 4 billion parameters) across three agent tiers introduces three risks requiring explicit monitoring:

**Persona leakage**: Government or insurance agents may produce reasoning that mimics household-level deliberation rather than institutional decision-making. We assess this through a lexical persona audit of reasoning traces: government traces should reference policy variables (subsidy rates, MG elevation percentages, budget status), while household traces should reference personal variables (income, flood history, premium burden). Cross-contamination---a household citing "community mitigation scores" or a government agent citing "my family's flood experience"---would indicate persona leakage. Detection methods include scanning institutional traces for first-person singular pronouns and household-level language. Additionally, institutional agents cannot be evaluated against PMT because their decisions are not appraisal-driven; we validate them against rule-based decision trees embedded in their prompts, computing a type-specific institutional CACR as the proportion of decisions that correctly implement the first matching rule given the structured context. The simplified decision-tree prompt structure is an explicit reliability tradeoff: it constrains the reasoning space to mitigate persona bleed at the cost of limiting institutional reasoning complexity.

**Default bias**: Small LLMs under uncertainty tend to select "maintain" or status-quo options disproportionately. For institutional agents, this can produce artificial path dependence (e.g., the insurance agent maintaining unchanged CRS discounts for 13 years). We distinguish plausible institutional conservatism from reasoning failure by examining whether maintain decisions include substantive justification referencing environmental signals (loss ratio, uptake rates) rather than generic uncertainty language.

**Governance as capacity compensation**: The governance framework compensates for limited LLM reasoning capacity by enforcing hard constraints, demonstrating that smaller models can produce credible simulations when properly scaffolded. The CACR_raw vs CACR_final gap directly measures this compensation. When governance rejects a proposed action and the agent exhausts retry attempts, the resulting do_nothing outcome constitutes *involuntary non-adaptation*---a mechanism that endogenously generates inequality between agent subgroups without explicitly programming disparate outcomes.

### Prompt Calibration Transparency

Prompt design followed an iterative refinement process (v5 → v6 → v7 → v7d) documented in the supplementary materials. To address the concern that iterative prompt tuning constitutes overfitting rather than calibration, we note three safeguards: (1) only four of sixteen benchmarks served as calibration targets; (2) prompt modifications addressed structural design choices (default-override framing, barrier descriptions) rather than numerical parameter tuning; and (3) all modifications were guided by behavioral theory (status quo bias, present bias, PMT) rather than by arbitrary adjustment to match target values.

## Level 2: Macro-Level Empirical Plausibility

L2 validation evaluates whether aggregate system behavior reproduces known empirical patterns. Following Grimm et al. (2005), we adopt pattern-oriented validation: the model must simultaneously satisfy multiple independent structural benchmarks. We define the Empirical Plausibility Index (EPI) as the weighted proportion of benchmarks falling within empirically supported ranges.

### Benchmark Classification

We maintain a strict separation across three benchmark categories. Conflating calibration and validation targets inflates apparent model performance and undermines credibility (Windrum et al., 2007).

**Calibration targets** (B1, B2, B5, B6) informed iterative prompt engineering and validator threshold adjustments during development:

| # | Benchmark | Range | Weight | Source |
|---|-----------|-------|--------|--------|
| B1 | Insurance rate in SFHA | 0.30--0.60 | 1.0 | Choi et al. (2024); de Ruig et al. (2023) |
| B2 | Overall insurance rate | 0.15--0.55 | 0.8 | Gallagher (2014) |
| B5 | Post-flood inaction rate | 0.35--0.65 | 1.5 | Grothmann & Reusswig (2006); Bubeck et al. (2012) |
| B6 | MG adaptation gap (composite) | 0.05--0.30 | 2.0 | Elliott & Howell (2017); environmental justice literature |

**Validation targets** (B3, B4, B7, B8) were held out entirely---no prompt modifications, threshold adjustments, or behavioral tuning referenced these metrics during development:

| # | Benchmark | Range | Weight | Source |
|---|-----------|-------|--------|--------|
| B3 | Elevation rate | 0.10--0.35 | 1.0 | FEMA P-312; Xian et al. (2017) |
| B4 | Buyout/relocation rate | 0.05--0.25 | 0.8 | Blue Acres program data; Mach et al. (2019) |
| B7 | Renter uninsured rate (SFHA) | 0.15--0.40 | 1.0 | Kousky (2017) |
| B8 | Insurance lapse rate | 0.15--0.30 | 1.0 | Gallagher (2014); Michel-Kerjan et al. (2012) |

**Structural plausibility targets** (B9--B15) represent a third category necessitated by the multi-agent architecture. No agent-level empirical ground truth exists for government subsidy decisions or insurance CRS adjustments at the temporal resolution of our simulation---these are singular institutional actors whose historical trajectories are documented only at the policy level. We define plausible trajectory envelopes derived from FEMA program rules and NFIP Community Rating System documentation:

| # | Benchmark | Range | Weight | Source |
|---|-----------|-------|--------|--------|
| B9 | Govt final subsidy | 0.40--0.75 | 1.0 | FEMA HMA program ranges |
| B10 | Govt average subsidy | 0.45--0.70 | 1.0 | Historical HMGP/FMA data |
| B11 | Govt decrease count | 1.0--5.0 | 1.0 | Must decrease at least once |
| B12 | Govt change count | 3.0--8.0 | 0.8 | Must show policy dynamism |
| B13 | Ins final CRS discount | 0.05--0.25 | 1.0 | CRS program statistics |
| B14 | Ins average CRS discount | 0.03--0.20 | 1.0 | CRS historical averages |
| B15 | Ins improve count | 1.0--5.0 | 0.8 | CRS class improvement frequency |

**Trajectory diagnostic** (B16) is reported but excluded from EPI:

| # | Benchmark | Range | Weight | Source |
|---|-----------|-------|--------|--------|
| B16 | Insurance trajectory change (Y1→Y13) | -0.40--0.10 | 0.0 | OpenFEMA policy data |

### Empirical Grounding of Household Benchmarks

Each benchmark range was constructed to span methodological variation across studies, geographic contexts, and temporal periods, rather than to match any single point estimate.

**B1 (Insurance rate, SFHA: 0.30--0.60).** NFIP administrative data for the 26 census tracts overlapping the PRB show SFHA take-up rates of approximately 39% in 2011 declining to 29% by 2023. Choi et al. (2024) report 48.3% SFHA coverage in their national sample; de Ruig et al. (2023) document 65.9% in post-Sandy New Jersey communities. The 0.30 lower bound reflects long-term erosion observed in OpenFEMA data, while the 0.60 upper bound accommodates post-disaster spikes and methodological heterogeneity between studies measuring policies-in-force versus survey-reported coverage.

**B2 (Insurance rate, all: 0.15--0.55).** Gallagher (2014) documents overall NFIP take-up of 12--18% across U.S. flood-prone communities, with sharp post-disaster spikes decaying over 3--5 years. Our PRB observed data show 16.7% in 2011 declining to 12.5% by 2023. The upper bound accommodates simulation conditions where 60% of agents reside in SFHA zones (by design), mechanically elevating aggregate rates.

**B3 (Elevation rate: 0.10--0.35).** FEMA HMGP records for Brick Township, NJ, indicate approximately 22% of SFHA structures were elevated within 8 years of Hurricane Sandy. Xian et al. (2017) estimate cost-effectiveness thresholds are met for 10--30% of at-risk structures depending on foundation type. The lower bound reflects high-friction barriers (FEMA P-312); the upper bound allows for the model's 13-year horizon with government subsidies.

**B4 (Buyout rate: 0.05--0.25).** New Jersey's Blue Acres program acquired 126 properties along the Passaic River between 2013 and 2020. Nationally, Mach et al. (2019) document 43,633 buyouts from 1989 to 2017. The 0.05 lower bound reflects typical participation in voluntary programs; the 0.25 upper bound acknowledges that repeated flood exposure may push take-up beyond historical norms.

**B5 (Post-flood inaction rate: 0.35--0.65).** Grothmann and Reusswig (2006) established that fatalism and denial suppress protective action even after direct flood experience. Bubeck et al. (2012) report 40--60% inaction among previously flooded German households; Botzen et al. (2009) find similar rates in Dutch communities. The range accommodates variation in coping perception: when perceived self-efficacy is low, PMT predicts fatalistic non-response regardless of threat severity.

**B6 (MG adaptation gap: 0.05--0.30).** Elliott and Howell (2017) document persistent income-based disparities in FEMA Individual Assistance receipt, with low-income households receiving 15--25% less mitigation aid. This benchmark uses a composite measure (any protective action) rather than insurance alone, because structural adaptations better capture inequality in protective capacity and insurance alone is confounded by mortgage mandates. The 0.05 lower bound avoids penalizing models that produce minimal inequality; the 0.30 upper bound prevents acceptance of unrealistically extreme disparities.

**B7 (Renter uninsured rate, SFHA: 0.15--0.40).** Kousky (2017) documents SFHA renter coverage rates of 15--25%. Renters lack mortgage-mandated purchase requirements, face split incentives with landlords, and typically have lower awareness of contents-only policies.

**B8 (Insurance lapse rate: 0.15--0.30).** Michel-Kerjan et al. (2012) report median NFIP policy tenure of 2--4 years, implying annual lapse rates of 25--50%. Gallagher (2014) documents post-disaster insurance spikes eroding within 3--5 years. Our range is intentionally conservative relative to raw administrative lapse rates because the model's annual decision cycle incorporates renewal friction through the LLM's status quo bias.

### Mandatory vs. Voluntary Insurance Limitation

A critical limitation---shared by most agent-based flood adaptation models---is the inability to distinguish mandatory from voluntary NFIP policy purchases. Under the National Flood Insurance Act, homeowners in SFHAs with federally backed mortgages are required to purchase and maintain flood insurance as a condition of their loan. Estimates suggest that 50--60% of SFHA policies in force are mortgage-mandated rather than voluntary behavioral choices (Congressional Budget Office, 2017; Kousky et al., 2018). Our model treats all insurance decisions as voluntary cognitive processes mediated by threat and coping appraisals.

This conflation affects four benchmarks directly. B1 and B2 compare simulated voluntary uptake against observed rates that include a mandatory component. B8 is affected because mandatory policyholders who let coverage lapse face mortgage default consequences, producing lower observed lapse rates than a purely voluntary population. B16 is most severely affected: the observed 29% decline in NFIP policies from 2011 to 2023 was driven primarily by Risk Rating 2.0 premium restructuring (FEMA, 2021), Biggert-Waters Act provisions (P.L. 112-141, 2012), and HFIAA surcharges (P.L. 113-89, 2014)---institutional market forces that priced out voluntary policyholders while mandatory purchasers remained captive.

Our structural plausibility claim therefore applies to the behavioral decision process, not aggregate market trajectory. We validate that individual agent decisions are consistent with PMT predictions (CACR), that the distribution of adaptation choices falls within empirically documented ranges (B1--B8), and that the decision architecture produces theoretically expected heterogeneity (B6, B7). We do not claim that the model reproduces NFIP market dynamics, which would require explicit modeling of mortgage origination, lender compliance, and regulatory pricing. To partially address the trajectory gap, we implement a 13-year premium escalation schedule as exogenous forcing (PREMIUM_ESCALATION), calibrated to approximate three phases of NFIP reform: Biggert-Waters (years 3--5, 5--15% increase), HFIAA gradual adjustment (years 6--9, 18--30%), and Risk Rating 2.0 (years 10--13, 35--65%).

The trajectory diagnostic (B16, weight = 0.0) measures relative change in overall insurance rate from Year 1 to Year 13. OpenFEMA data for the 26 PRB census tracts show a relative change of approximately -25% to -29% over 2011--2023. We assign zero weight because: (1) the observed trajectory is driven by institutional market forces outside the model's scope; (2) the mandatory-voluntary conflation means the observed baseline is not a valid target for a voluntary-decision model; (3) the direction of the simulated trajectory (rising under repeated flood exposure) is a legitimate emergent outcome of PMT behavioral assumptions. The accepted range of -0.40 to +0.10 is deliberately wide, permitting decline (if premium escalation dominates) or modest increase (if flood exposure dominates), without contributing to the pass-fail EPI judgment.

### EPI Computation

The Empirical Plausibility Index aggregates benchmark performance:

EPI = Σ(w_i · I_i) / Σ(w_i) for all benchmarks with non-null values and w_i > 0

where I_i = 1 if benchmark i falls within range, 0 otherwise. The weighting scheme reflects three principles: (1) **equity sensitivity**---B6 (w = 2.0) and B5 (w = 1.5) receive elevated weight because demographic disparities and behavioral inertia are central findings; (2) **empirical confidence**---benchmarks with wider uncertainty receive lower weights (B2, B4, B12, B15 at w = 0.8); (3) **robustness**---we implement weight sensitivity analysis recomputing EPI under equal weights, primary weights, and a capped scheme (max w = 1.0), requiring EPI >= 0.60 under at least two of three schemes.

We require EPI >= 0.60 for structural plausibility.

## Level 3: Cognitive Consistency

L3 validation examines whether LLM responses exhibit stable persona differentiation and theoretically expected sensitivity to risk drivers, independent of the primary experiment.

**Intraclass Correlation (ICC)**: We compute ICC(2,1) across 6 archetypes × 3 vignettes × 30 repetitions (Shrout & Fleiss, 1979). We observe ICC = 0.964, indicating that 96.4% of decision variance derives from between-archetype differences rather than within-archetype noise. This high value warrants a dimensionality caveat: with strong binary constraints (owner vs. renter, high-income vs. low-income), the effective dimensionality is low. ICC quantifies *consistency*, not *diversity*.

**Effect Size (eta-squared)**: Variance in risk appraisal scores explained by flood depth. We observe eta-squared = 0.33, indicating moderate sensitivity to hazard severity.

**Directional Sensitivity**: The proportion of agents who increase protective action probability following severe floods (depth >= 1.0m). We observe 75% directional consistency, satisfying the >= 75% threshold aligned with PMT predictions.

## Cross-Tier Feedback Loop Validation

The three-tier sequential architecture creates co-evolutionary dynamics that require validation beyond endpoint metrics.

### Feedback Loop Structure

Government observes community-level flood damage, cumulative elevation rates, and the proportion of marginalized households, then adjusts subsidy rates. Insurance observes loss ratios and insured counts, then adjusts CRS discounts. Household agents receive updated institutional parameters and make individual adaptation decisions. Aggregate household outcomes feed back to government and insurance observations in the subsequent year.

A "healthy" feedback loop should exhibit: (a) directional responsiveness---institutional decisions should shift in response to changing environmental signals; (b) bounded oscillation---the system should not diverge or cycle between extremes; (c) institutional inertia---real policy systems change slowly, so high-frequency oscillation would indicate unrealistic responsiveness. We validate loop health through trajectory shape analysis and a **policy variability index**: the number of distinct decisions made over the simulation period divided by the number of timesteps. A variability index of 0.0 (all identical decisions) or 1.0 (every decision different) would both be suspicious; the former indicates single-strategy persistence potentially attributable to default bias, the latter suggests over-responsiveness inconsistent with institutional behavior.

We classify institutional trajectories into four canonical shapes: (1) *monotonic* (consistently increasing or decreasing), (2) *step-change* (stable periods punctuated by discrete shifts), (3) *oscillating* (frequent reversals), and (4) *responsive-adaptive* (gradual adjustment tracking environmental signals). Real-world NFIP policy trajectories are primarily step-change, reflecting legislative reform cycles (Biggert-Waters 2012, HFIAA 2014, Risk Rating 2.0 2021). For household cohorts, we group agents by first-flood-year and track adaptation trajectory decay, consistent with the memory-driven lapse patterns documented by Gallagher (2014).

### Emergence Taxonomy

We categorize model outcomes by their degree of emergence to frame validation claims appropriately:

- **Fully emergent**: MG/NMG adaptation gap, spatial clustering of insurance adoption (Moran's I), social channel citation patterns, insurance lapse timing. These arise entirely from agent interactions without explicit programming.
- **Partially emergent**: Insurance rate trajectory is shaped by both LLM household decisions AND the exogenous PREMIUM_ESCALATION schedule. Institutional path dependence arises from LLM decisions but is constrained by the 3-action set (increase/maintain/decrease).
- **Imposed**: Flood zone assignment (70/30 vs 50/50), affordability thresholds, PREMIUM_ESCALATION schedule, PMT coherence rules. These are design choices, not emergent properties.

Only fully emergent outcomes support claims that "the model produces" a given pattern. Partially emergent outcomes should be described as "the model, under exogenous forcing, produces..." Imposed features are model assumptions, not findings.

## Equity Validation

Traditional ABM validation evaluates aggregate outputs against empirical benchmarks, but such metrics are insufficient for models representing heterogeneous populations differentiated by socioeconomic vulnerability (Braveman, 2006). A model can satisfy every aggregate benchmark while producing systematically implausible outcomes for specific subgroups---for instance, overall insurance uptake of 0.40 may mask configurations where NMG households insure at 0.55 while MG households insure at 0.25. We elevate the MG-NMG adaptation gap (B6) to a first-class validation target with the highest benchmark weight (2.0), reflecting a deliberate commitment: an equity-sensitive ABM that cannot reproduce empirically documented adaptation inequality has failed to capture a structurally important feature of the system.

### Endogenous Inequality Generation

The MG-NMG adaptation gap arises endogenously from three structural mechanisms, none of which directly reference group membership in determining outcomes. First, **affordability validators** reject a larger proportion of MG proposals because MG households have lower median RCV ($280,000 vs. $400,000) and lower incomes, encoding the same logic that governs real-world FEMA benefit-cost analysis requirements, which disproportionately exclude low-value properties (Kamel, 2012). Second, **spatial exposure assignment** places 70% of MG households in SFHAs (vs. 50% NMG), reflecting documented patterns of flood-zone demographic sorting (Elliott & Howell, 2017; Masozera et al., 2007)---this generates higher cumulative damage for MG households, paradoxically increasing motivation while depleting resources. Third, **persona-conditioned LLM reasoning** integrates these constraints into deliberative narratives: a low-income persona reasons toward inaction not because the model codes low-income agents as passive, but because its cost-benefit assessment reflects stated financial circumstances.

This emergence property means the adaptation gap can be validated against empirical data as a testable prediction rather than a calibrated input.

### Involuntary Non-Adaptation as Equity Indicator

When governance rejects a household's proposed action, the effective outcome is forced inaction. We track the **constrained non-adaptation rate**---the proportion of decisions in which a household proposed a protective action but was blocked by governance---disaggregated by MG status. If MG rejection rates substantially exceed NMG rejection rates, this validates that institutional barriers bind differentially, consistent with documented disparities in HMGP application denial rates (Greer, 2015). Conversely, similar rejection rates across groups would flag a validation concern even if aggregate EPI passes.

### Composite Gap Measurement

B6 uses a composite indicator (any protective action) rather than insurance alone, reflecting three considerations: (1) structural adaptations (elevation, buyout) permanently reduce physical vulnerability, while insurance only transfers financial risk---conflating the two understates real protection inequality; (2) mortgage-mandated flood insurance in SFHAs inflates MG insurance rates relative to voluntary uptake, compressing the insurance gap artificially; (3) the composite metric better captures "coping capacity" (Rufat et al., 2015)---multi-dimensional measures consistently outperform single-action proxies in explaining post-disaster recovery differentials.

### Equity Validation Limitations

Several limitations constrain equity claims: (1) the LLM may exhibit implicit biases from training corpora, associating poverty with passivity through stereotypic pattern completion rather than structural reasoning (Huang et al., 2025); (2) a 4B model has limited capacity for the sophisticated resource management strategies (informal risk pooling, strategic deferral) that real marginalized households employ (Moser & Ekstrom, 2010); (3) the binary MG/NMG classification oversimplifies intersectional vulnerability---continuous multi-dimensional measures consistently outperform single-threshold classifications (Cutter et al., 2003); (4) flood zone assignment ratios (70/30 vs 50/50) partially pre-determine inequality by construction---sensitivity analysis varying these ratios would help isolate the contribution of spatial sorting from other gap-generating mechanisms.

## Cross-Seed Robustness

LLM-ABMs introduce stochasticity beyond conventional random seeds: nondeterminism in language model sampling (temperature, top-k). We evaluate robustness across three independent replications (seeds 42, 43, 44).

**Structural stability metrics**---EPI, CACR, R_H, and the direction of the MG adaptation gap---should be consistent across seeds. We require EPI >= 0.60 in all seeds and CV < 0.10 for aggregate rates.

**Trajectory-level metrics**---yearly insurance rates, subsidy trajectories, CRS discount paths---are expected to show parallel trends with bounded dispersion. A benchmark with CV > 0.30 warrants investigation into structural fragility.

**MG adaptation gap robustness**: Because B6 is a difference of proportions, it is inherently more variable. We require the gap to remain positive (NMG adapts at higher rates than MG) in all seeds at simulation end, consistent with environmental justice literature, even if its magnitude varies. Convergence of sign and approximate magnitude provides evidence that inequality is a structural property rather than a stochastic artifact.

## Stratified Trace Audit

Aggregate validation metrics (CACR, EPI, R_H) provide necessary but insufficient evidence of simulation credibility. A model can achieve high CACR through systematic action-type associations without producing reasoning that reflects genuine deliberation. We therefore conduct stratified trace audits sampling along three dimensions: agent type (owner, renter, government, insurance), flood exposure (zero, low, high cumulative flood count), and simulation year (early, middle, late). For each stratum, we evaluate: (1) whether the reasoning references the agent's actual state variables (demographic grounding rate); (2) whether the cited rationale is logically consistent with the chosen action; and (3) whether prompt-derived phrases dominate the reasoning (indicating sycophantic anchoring) versus agent-specific elaboration. This audit distinguishes "correct action, correct reason" from "correct action, wrong reason"---both contribute equally to CACR, but only the former supports the claim that the simulation reproduces PMT-consistent micro-processes.

## Methodological Claims

To our knowledge, this represents the first quantitative multi-level validation framework for multi-agent LLM-ABMs in natural hazard research. By anchoring micro-coherence to PMT, macro-patterns to 16 empirical benchmarks spanning household, institutional, and trajectory dimensions, cognitive stability to variance decomposition, and equity to endogenous inequality generation, we provide a replicable protocol for assessing LLM-ABM credibility beyond subjective plausibility judgments.

**Scope Conditions**: All results derive from Gemma 3 4B, a locally deployed open-source model representing a lower bound on model capacity. The governance framework compensates for limited LLM capacity by enforcing hard constraints, demonstrating that smaller models can produce credible multi-agent simulations when properly scaffolded by institutional feasibility rules.
