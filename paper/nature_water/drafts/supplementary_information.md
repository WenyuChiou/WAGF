# Supplementary Information

## Institutional Constraints Widen Adaptive Strategy Diversity in Language-Based Water Agents

---

## Supplementary Note 1. IBR Decomposition and Governance Effect by Model

The Irrational Behaviour Rate (IBR, denoted R_H) quantifies the percentage of agent decisions that violate Protection Motivation Theory predictions, computed as the sum of verification rule violations divided by the number of active agent-year observations:

- **V1** (relocation under low threat): agent relocated despite appraising flood risk as low
- **V2** (elevation under low threat): agent elevated the house despite appraising flood risk as low

A third rule, V3 (inaction under extreme threat), blocks do_nothing when threat appraisal is H or VH. V3 yielded zero IBR violations in final executed decisions across all twelve conditions (six models × two governance states) because the governance pipeline intercepted V3-violating proposals before execution. In governed runs (Gemma-3 4B, 3 seeds), V3 triggered 238 times (9.15% of audited decisions); 220 proposals (92.4%) were corrected by the agent on retry, and 18 (7.6%) were ultimately rejected. Two additional thinking rules — blocking elevation and relocation under low threat — triggered 4 and 2 times respectively, all corrected on retry (Supplementary Table 1b). This pattern demonstrates that governance validators actively shape agent proposals through iterative feedback, not merely filter final outputs. V3 is omitted from IBR computation in Supplementary Table 1 because no V3 violations survived the governance pipeline to affect executed behaviour.

**Supplementary Table 1b. Governance rule trigger frequency (flood domain, Gemma-3 4B governed, 100 agents × 10 years, 3 seeds, 2,600 audited decisions).**

| Rule | Description | Level | Triggers | Corrected on retry | Final rejected | Trigger rate |
|---|---|---|---|---|---|---|
| extreme_threat_block | Block do_nothing when TP ≥ H | ERROR | 238 | 220 (92.4%) | 18 (7.6%) | 9.15% |
| elevation_threat_low | Block elevation when TP ≤ L | ERROR | 4 | 4 (100%) | 0 | 0.15% |
| relocation_threat_low | Block relocation when TP ≤ L | ERROR | 2 | 2 (100%) | 0 | 0.08% |
| elevation_block | Block elevation if already elevated | ERROR | 1 | 1 (100%) | 0 | 0.04% |
| low_coping_block | Block elevation/relocation when CP ≤ L | WARNING | 0 | — | — | 0.00% |

*Triggers include all governance-intercepted proposals across the retry loop, not only final outcomes. "Corrected on retry" indicates the agent revised its proposal to a compliant action after receiving governance feedback. The high correction rate (97.6% overall) indicates that agents incorporate governance feedback into subsequent reasoning.*

For LLM (no validator) agents, threat and coping appraisals are inferred from free-text narratives using a three-tier keyword classifier: (1) explicit categorical labels (VH/H/M/L/VL), (1.5) qualifier precedence that detects negation and hedging phrases (e.g., "low risk of flooding", "moderate concern") before keyword matching, and (2) curated PMT keyword dictionaries. For governed LLM agents, structured labels are emitted directly by the governance pipeline. LLM (no validator) agents use a relaxed low-threat threshold {L, VL, M} to account for classification uncertainty; governed agents use the strict threshold {L, VL}.

**Supplementary Table 1. Cross-model IBR and behavioural diversity (flood domain, 100 agents × 10 years, 3 seeds per condition). Values are means ± s.d. across seeds. IBR excludes R5 (re-elevation block, a code-level constraint).**

| Model | Condition | IBR (%) | R1 | R3 | R4 | EHE |
|---|---|---|---|---|---|---|
| Ministral 3B | LLM (no validator) | 5.0 ± 0.6 | 49 | 26 | 76 | 0.825 ± 0.017 |
| | Governed LLM | 0.3 ± 0.3 | 1 | 1 | 6 | 0.810 ± 0.014 |
| Gemma-3 4B | LLM (no validator) | 8.1 ± 1.7 | 235 | 2 | 6 | 0.846 ± 0.042 |
| | Governed LLM | 0.6 ± 0.4 | 17 | 0 | 0 | 0.866 ± 0.045 |
| Ministral 8B | LLM (no validator) | 2.3 ± 0.3 | 31 | 5 | 32 | 0.791 ± 0.030 |
| | Governed LLM | 0.0 ± 0.0 | 0 | 0 | 0 | 0.728 ± 0.009 |
| Gemma-3 12B | LLM (no validator) | 0.2 ± 0.3 | 0 | 0 | 7 | 0.603 ± 0.084 |
| | Governed LLM | 0.1 ± 0.1 | 0 | 0 | 2 | 0.612 ± 0.071 |
| Ministral 14B | LLM (no validator) | 3.1 ± 0.2 | 34 | 18 | 41 | 0.876 ± 0.026 |
| | Governed LLM | 0.0 ± 0.0 | 0 | 0 | 0 | 0.833 ± 0.013 |
| Gemma-3 27B | LLM (no validator) | 0.4 ± 0.3 | 11 | 0 | 0 | 0.662 ± 0.019 |
| | Governed LLM | 0.0 ± 0.0 | 0 | 0 | 0 | 0.638 ± 0.028 |

*R1 = high-threat inaction (do_nothing when TP ≥ H); R3 = low-threat relocation (relocate when TP ≤ L); R4 = low-threat elevation (elevate when TP ≤ L). Counts are 3-seed totals (N = 3,000 agent-years per condition per model). EHE = normalized Shannon entropy H/log₂(4), where 0 = monoculture and 1 = uniform.*

**Supplementary Table 2. Governance effect on IBR and EHE (paired difference across 3 seeds, df = 2).**

| Model | ΔIBR (pp) | 95% CI | p | ΔEHE | 95% CI | p |
|---|---|---|---|---|---|---|
| Ministral 3B | +4.77 | [+3.89, +5.64] | 0.002 | −0.014 | [−0.068, +0.039] | 0.370 |
| Gemma-3 4B | +7.53 | [+2.81, +12.26] | 0.021 | +0.021 | [−0.194, +0.236] | 0.716 |
| Ministral 8B | +2.27 | [+1.64, +2.89] | 0.004 | −0.063 | [−0.136, +0.009] | 0.064 |
| Gemma-3 12B | +0.17 | [−0.35, +0.68] | 0.300 | +0.008 | [−0.264, +0.280] | 0.907 |
| Ministral 14B | +3.10 | [+2.60, +3.60] | 0.001 | −0.042 | [−0.138, +0.053] | 0.198 |
| Gemma-3 27B | +0.37 | [−0.26, +0.99] | 0.128 | −0.024 | [−0.115, +0.066] | 0.370 |

*ΔIBR = (no validator) − (governed); positive = governance reduces IBR. ΔEHE = (governed) − (no validator); negative ≈ governance does not suppress diversity. 95% CIs from paired t-distribution (df = 2). Four of six models show significant IBR reduction (p < 0.05); no model shows significant EHE change, confirming that governance constrains irrational behaviour without suppressing adaptive diversity.*

**Note on governed conditions.** The cross-model comparison (Fig. 4, Supplementary Table 1) uses governed agents with window memory (Group_B), which was run for all six models. The main text flood results (Table 2) use governed agents with HumanCentric memory, which was only run for Gemma-3 4B. Both governed conditions share the same validator pipeline; the memory subsystem differs but does not alter governance rule application. For Gemma-3 4B, the two governed conditions produce comparable EHE (0.866 ± 0.045 window vs. 0.860 ± 0.063 HumanCentric).

**Decision distribution patterns.** Gemma-3 4B shows the largest IBR gap (+7.5 pp) driven primarily by R1 violations (high-threat inaction: 235 occurrences without validators vs. 17 with). Ministral 3B distributes violations across all three rules. Gemma-3 12B is a near-null case (IBR < 0.3% in both conditions), suggesting this model's base behaviour already aligns with PMT predictions. EHE differences are small and non-significant across all models (|ΔEHE| < 0.07), confirming that governance reduces irrational behaviour without suppressing adaptive diversity.

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
| 3 | Governed | CocopahIndRes | 10 | 0 | 1,161 | **maintain** (fallback) | Blocked escalation | *Blocked by demand-ceiling rule + high_threat_high_cope_no_increase.* |
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
- Governed first-attempt behavioural diversity: 0.761 ± 0.020
- Ungoverned first-attempt behavioural diversity: 0.640 ± 0.017
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

**Flood domain results:** Governed LLM BRI was 100.0% across all models; LLM (no validator) BRI ranged from 37.7% (Ministral 3B) to 99.9% (Gemma-3 12B). See Supplementary Table 1 for per-model IBR decomposition.

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
- LLM (no validator) behavioural diversity (premium doubled): 0.797 ± 0.018
- Governed LLM behavioural diversity (premium doubled): 0.693 ± 0.024
- Difference: −0.104 (no validator > governed)

This contrasts with baseline premium conditions, where governed and no-validator agents show comparable behavioural diversity for the same model (Fig. 4).

**Interpretation.** External cost pressure (premium doubling) appears to force behavioural diversification independently of governance. In the no-validator condition, agents adapted to the higher premium by exploring alternative mitigation strategies (elevation, relocation, do_nothing), increasing diversity above the governed condition. This suggests that sufficiently strong economic incentives can substitute for governance constraints in promoting diverse adaptive responses.

**Decision.** We report the premium doubling analysis here as exploratory sensitivity evidence. Future work should systematically vary insurance premiums, elevation costs, and buyout offers to map the economic-governance interaction landscape.

---

## Supplementary Note 6. Supplementary Water-System Outcomes

Summary water-system outcomes are reported in Extended Data Table 1. This section provides additional detail.

**Supplementary Table 6. Supplementary water-system outcomes (irrigation domain, Gemma-3 4B, 78 agents × 42 years, 3 runs each).**

| Metric | Governed | Ungoverned |
|--------|----------|------------|
| Minimum Lake Mead elevation (ft) | 1,002 | 1,001 |
| Shortage years (/42) | 13.3 ± 1.5 | 5.0 ± 1.7 |
| Shortage-year demand ratio | 0.362 ± 0.008 | 0.234 ± 0.012 |
| Plentiful-year demand ratio | 0.409 ± 0.009 | 0.295 ± 0.019 |
| Curtailment spread (plentiful − shortage) | 0.047 | 0.061 |
| Year-over-year demand variability (SD) | 0.037 | 0.061 |
| Percentage of decisions that were demand increases | ~53% | 77–82% |

*All demand ratios computed as basin-aggregate (total requests / total water rights per year). Curtailment spread = plentiful-year DR minus shortage-year DR.*

The near-identical minimum elevations (1,002 vs. 1,001 ft) indicate both conditions avoided catastrophic reservoir failure. Governed agents crossed the 1,075-ft shortage-declaration threshold more frequently (13.3 vs. 5.0 years), reflecting productive engagement with the drought-responsive allocation system's responsive range rather than commons degradation. Ungoverned agents showed higher year-over-year demand variability (SD 0.061 vs. 0.037), driven by the volatility of ceiling-capped monotonic growth trajectories rather than adaptive demand management.

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

### Domain-Specific Governance Validator Inventory

The governance pipeline validates each agent decision through validators organised in three tiers: **behavioural governance rules** (derived from the domain's behavioural theory — the paper's primary methodological contribution), **domain constraints** (physical, financial, and institutional feasibility checks standard in any ABM), and **epistemic guardrails** (LLM-specific checks that ensure reasoning is grounded in actual simulation state). Validators operate at two severity levels: ERROR (blocks the proposed action and triggers re-reasoning, up to 3 attempts) and WARNING (flags but does not block). The Irrational Behaviour Rate (IBR) reported in the main text is computed using the same behavioural governance rules applied post-hoc to executed decisions (see Methods: Validation Protocol).

**Supplementary Table SN-A. Irrigation domain governance validators (12 active).**

| # | Validator | Category | Severity | Trigger Condition |
|---|-----------|----------|----------|-------------------|
| 1 | Water-right cap | Physical | ERROR | Agent at allocation cap proposes demand increase |
| 2 | Non-negative diversion | Physical | ERROR | Agent at zero diversion proposes demand decrease |
| 3 | Minimum utilisation floor | Physical | ERROR | Utilisation < 10% of water right; blocks further decrease |
| 4 | Demand-floor stabiliser | Economic | ERROR | Utilisation < 50% of water right; blocks decrease below stability corridor |
| 5 | **Demand-ceiling rule** | **Institutional** | **ERROR** | **Basin demand > 6.0 MAF; blocks demand increase (ablation target)** |
| 6 | Drought severity | Institutional | ERROR/WARN | Drought index ≥ 0.7: blocks large increase; ≥ 0.85: blocks all increases |
| 7 | Magnitude cap | Physical | WARNING | Proposed magnitude exceeds persona cluster bounds |
| 8 | Supply-gap block | Physical | ERROR | Fulfilment ratio < 70%; blocks demand increase |
| 9 | Curtailment awareness | Social | ERROR/WARN | Tier 2+: blocks all increases; Tier 1: blocks large only |
| 10 | Compact allocation | Social | WARNING | Basin demand exceeds Colorado River Compact share |
| 11 | Consecutive-increase cap | Temporal | ERROR | ≥ 3 consecutive demand increases (feature-flagged; default OFF in production) |
| 12 | WSA-ACA coherence | Behavioural | ERROR | High water-shortage appraisal + high adaptive capacity → blocks demand increase |

*Notes: Validators 1–8 enforce physical and economic feasibility. Validator 5 is the demand-ceiling rule tested in the ablation experiment (main text, R2). Validator 6 uses split severity: drought index ≥ 0.7 triggers WARNING (flags large increases), while drought index ≥ 0.85 escalates to ERROR (blocks all increases). Validator 9 similarly uses split severity: Tier 2+ shortage triggers ERROR (blocks all increases), while Tier 1 triggers WARNING (blocks large increases only). Validator 11 was disabled in production runs. Validator 12 operationalises the dual-appraisal framework (WSA/ACA). Irrigation IBR decomposes into three rule sets mapped to specific validators: (A) physical impossibilities — validators 1, 2, 3, and 8 (proposing increases at cap, decreases at zero, below minimum utilisation, or during supply gaps); (B) dual-appraisal incoherence — validator 12 (WSA/ACA label–action mismatches evaluated against a 25-cell coherence matrix); (C) temporal violations — validator 11 logic applied post-hoc (≥ 4 consecutive increases during drought, evaluated regardless of whether the runtime validator was active). BRI ≈ 1 − IBR, using a domain-specific definition where rational behaviour = not increasing demand during high scarcity (see Methods).*

**Supplementary Table SN-B. Flood domain governance validators (13 total: 4 behavioural + 5 domain + 4 epistemic).**

| # | Validator | Category | Severity | Trigger Condition |
|---|-----------|----------|----------|-------------------|
| | **Behavioural governance rules (PMT-derived)** | | | |
| 1 | Extreme-threat block | PMT governance | ERROR | Threat perception ≥ High; blocks do_nothing |
| 2 | Low-coping block | PMT governance | WARNING | Coping perception ≤ Low; warns against elevate/relocate |
| 3 | Relocation-threat-low | PMT governance | ERROR | Threat perception ≤ Low; blocks relocate |
| 4 | Elevation-threat-low | PMT governance | ERROR | Threat perception ≤ Low; blocks elevate |
| | **Domain constraints (simulation infrastructure)** | | | |
| 5 | Re-elevation block (YAML) | Physical | ERROR | Home already elevated; blocks elevate (declared in skill registry) |
| 6 | Re-elevation block (code) | Physical | ERROR | Defence-in-depth duplicate of rule 5 implemented in Python validator; both must pass |
| 7 | Post-relocation block | Physical | ERROR | Agent relocated; blocks all property actions |
| 8 | Renter restriction | Institutional | ERROR | Tenure = renter; blocks elevation and buyout |
| 9 | Elevation affordability | Financial | ERROR | Savings < elevation cost; blocks elevate |
| | **Epistemic guardrails (LLM-specific)** | | | |
| 10 | Majority-deviation warning | Social | WARNING | > 50% neighbours adapted but agent chooses do_nothing |
| 11 | Social-proof hallucination | Semantic | WARNING | Reasoning cites neighbours but agent has 0 neighbours |
| 12 | Temporal grounding | Semantic | WARNING | Reasoning references floods that did not occur |
| 13 | State consistency | Semantic | WARNING | Reasoning contradicts known agent state variables |

*Notes: Behavioural governance rules (1–4) are derived from Protection Motivation Theory and constitute the paper's primary governance contribution. The same rules are applied post-hoc to compute IBR: rules 3 and 4 correspond to IBR violation types V1 (relocation under low threat) and V2 (elevation under low threat); rule 1 corresponds to V3 (inaction under extreme threat), which is excluded from the reported IBR because governance intercepted all violations before execution (see Supplementary Note 1). Rule 2 operates at WARNING severity, which for small LLMs (≤ 4B parameters) produces no measurable behavioural change — a boundary condition of soft governance. Domain constraints (5–9) enforce feasibility checks standard in any flood ABM. Epistemic guardrails (10–13) address reasoning errors unique to LLM-based agents; these operate at WARNING severity and are not included in IBR computation.*

### Experimental Replication

**Irrigation:** 78 agents × 42 years × 3 random seeds × 2 conditions (governed/ungoverned) = 6 experiments (37.3 hours total runtime)

**Flood:** 100 agents × 10 years × 3 random seeds × 6 models × 3 agent groups × 2 conditions = 54 complete experiments (baseline premium configuration)

All random seeds controlled both agent initialization (persona assignment) and stochastic processes (hazard exposure under per-agent-depth flood sampling).

---

## Supplementary Note 8. Data and Code Availability

All experiment configurations, validation frameworks, and analysis scripts are available in the project repository:

- **Irrigation experiment**: `examples/irrigation_abm/`
- **Flood experiment**: `examples/single_agent/` (100-agent household simulation; "single_agent" refers to the single-tier agent hierarchy, as distinct from the three-tier multi-agent configuration used in a companion study)
- **Governance framework**: `broker/`
- **Analysis scripts**: `paper/nature_water/scripts/`

All simulation code and configuration files will be archived on Zenodo upon acceptance (DOI to be assigned). Raw experimental outputs (agent traces, validator logs, system state snapshots) are archived and available upon request due to size constraints (>100 GB).

---

## Supplementary Note 9. Statistical Methods

### Strategy Diversity

We quantified behavioural diversity using normalized Shannon entropy (Shannon, 1948):

$$\text{Behavioural diversity} = -\frac{1}{\log_2 k} \sum_{i=1}^{k} p_i \log_2 p_i$$

where $k$ is the number of available action categories and $p_i$ is the empirical frequency of action $i$ across all agent-timesteps. Normalization by $\log_2 k$ ensures a range of [0, 1], with 0 indicating behavioural monoculture (all agents select the same action) and 1 indicating maximum diversity (uniform distribution over all actions).

**Confidence intervals:** 95% CIs were computed via 10,000-iteration bootstrap resampling at the agent-timestep level, preserving within-agent temporal autocorrelation structure.

**Statistical significance:** Differences in behavioural diversity between governed and ungoverned conditions were assessed using permutation tests (10,000 permutations) to avoid distributional assumptions.

### Model-Specific vs. Pooled Analysis

Per-model analyses are reported as primary findings because:

1. **Model heterogeneity**: Effect sizes varied substantially across models (Fig. 4: ΔEHE from −0.063 to +0.021; ΔIBR from +0.17 to +7.53 pp)
2. **Scientific interpretation**: Model-specific patterns reveal which architectural features (parameter count, training data, instruction-tuning methods) modulate governance responsiveness
3. **Pooled CI limitations**: Pooled confidence intervals aggregate across heterogeneous effect sizes and should be interpreted as meta-analytic summaries, not tests of overall effect presence

All six models showed IBR reduction under governance, with four reaching statistical significance (p < 0.05; Supplementary Table 2). No model showed a significant EHE change, confirming that governance constrains irrational behaviour without suppressing adaptive diversity. Under alternative composite-action normalizations (Supplementary Table 7), EHE direction depends on specification choice for models with high composite rates.

**Supplementary Table 7. Behavioural diversity sensitivity to composite-action normalization specification (flood domain, 100 agents × 10 years, 3 runs per condition).**

*Composite-action treatment scenarios:* LLM (no validator) agents occasionally selected composite actions (simultaneously purchasing insurance and elevating). Four normalization specifications were tested: S1 (asymmetric k=5/4, composite as 5th action), S2 (merge to elevate, k=4), S3 (uniform k=5), S4 (split into constituents, k=4; primary specification).

| Model | S1 (k=5/4) | S2 (merge) | S3 (k=5/5) | S4 (split) |
|-------|:-:|:-:|:-:|:-:|
| Gemma-3 4B | **+0.219** | **+0.191** | **+0.115** | **+0.164** |
| Gemma-3 12B | +0.046 | +0.002 | −0.021 | **−0.150** |
| Gemma-3 27B | **+0.065** | +0.014 | −0.029 | +0.007 |
| Ministral 3B | **+0.161** | **+0.252** | **+0.060** | **+0.116** |
| Ministral 8B | **−0.094** | **−0.125** | **−0.181** | **−0.098** |
| Ministral 14B | +0.013 | **+0.240** | **−0.085** | **+0.058** |

*Bold indicates |Δ| > 0.05. Positive = governance increases behavioural diversity. No specification produces a pooled 95% CI excluding zero; the effect is model-dependent. Gemma-3 4B and Ministral 3B show positive effects under all four specifications; Ministral 8B shows reversal under all four.*

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

Note that 84–89% of FQL decisions resulted in maintain_demand — not because FQL selected this action (FQL has only increase/decrease), but because governance validators blocked the proposed action and the deterministic fallback executed maintain_demand. This high blocking rate reflects the mismatch between FQL's binary action space and the governance rules designed for a richer decision vocabulary. Behavioural diversity is therefore not computed for FQL, as the action distribution is dominated by a validator artifact rather than behavioural choice.

**Interpretation.** The FQL comparison isolates the representational contribution: governance alone does not produce adaptive exploitation. The combination of governance constraints *and* natural-language reasoning is required — governance defines the feasibility boundaries, and language-based reasoning enables agents to adaptively navigate within those boundaries in response to environmental state.

**Data and code.** FQL results: `examples/irrigation_abm/results/fql_raw/seed{42,43,44}/`. Runner: `examples/irrigation_abm/run_fql_baseline.py --from-logs`. Comparison metrics: `examples/irrigation_abm/analysis/fql_comparison_metrics.py`.

---

## Supplementary Note 12. Rule-Based PMT Agent Parameterization

The rule-based PMT agent uses a softmax utility framework to operationalize Protection Motivation Theory. At each decision step, the agent computes utilities for four actions and selects probabilistically via softmax with temperature τ = 0.5.

**Base utilities:**

| Parameter | Value | Description |
|-----------|-------|-------------|
| U₀(do_nothing) | 0.6 | Inertia / status quo bias |
| U₀(insurance) | 0.3 | Baseline insurance propensity |
| U₀(elevation) | 0.1 | Baseline elevation propensity |
| U₀(relocation) | −1.5 | Relocation strongly disfavoured |

**Modifiers:**

| Parameter | Value | Description |
|-----------|-------|-------------|
| Flood effect (community) | +0.8 | Utility boost for protective actions when community flood occurs |
| Flood effect (personal) | +1.2 | Additional boost when agent personally flooded |
| Grant effect on elevation | +0.8 | Elevation utility boost when grant available |
| Elevation cost | −1.0 | Cost penalty for elevation |
| Relocation cost | −2.0 | Cost penalty for relocation |
| Memory decay | 0.85 | Exponential decay rate for flood memory |
| Memory coefficient (insurance) | 0.35 | Memory-driven insurance utility |
| Memory coefficient (elevation) | 0.35 | Memory-driven elevation utility |
| Memory coefficient (relocation) | 0.20 | Memory-driven relocation utility |
| Memory coefficient (inaction) | −0.20 | Memory discourages inaction |
| Softmax temperature (τ) | 0.5 | Higher = more stochastic |

Base utilities were calibrated to reproduce empirical PMT patterns (Bubeck et al., 2012): high do-nothing propensity reflecting status quo bias, moderate insurance uptake, low elevation rates reflecting practical barriers, and very rare relocation. The stochastic softmax framework (rather than deterministic thresholds) generates within-population heterogeneity from agent-specific flood histories and grant exposure, providing a fair comparison against language agents that generate diversity through reasoning.

---

**End of Supplementary Information**
