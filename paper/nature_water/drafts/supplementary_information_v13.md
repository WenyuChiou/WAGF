# Supplementary Information (v13 — 9-model cross-model update with Gemma-4 26B paired; 2026-04-19)

## Institutional Constraints Shape Adaptive Strategy Diversity in Language-Based Water Agents

---

## Supplementary Note 1. Model Configuration and Inference Details

### Language Models

All experiments were conducted using locally hosted models via Ollama inference engine. The following models were tested across both irrigation and flood domains:

**Gemma-3 family** (Google DeepMind):
- gemma3:4b — 4 billion parameters (primary model for all main analyses)
- gemma3:12b — 12 billion parameters
- gemma3:27b — 27 billion parameters

**Gemma-4 family** (Google DeepMind):
- gemma4:e2b — efficient 2 billion parameter variant
- gemma4:e4b — efficient 4 billion parameter variant
- gemma4:26b — 26 billion parameters (paired comparison complete, 5 seeds each condition)

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

### Experimental Replication

**Irrigation:** 78 agents × 42 years × 5 random seeds × 2 conditions (with validators / LLM (no validator)) = 10 experiments (Gemma-3 4B).

**Flood:** 100 agents × 10 years × 5 random seeds × 9 model configurations × 2 conditions = 90 experiments in the completed cross-model set.

All random seeds controlled both agent initialization (persona assignment) and stochastic processes (hazard exposure under per-agent-depth flood sampling).

---

## Supplementary Note 2. Governance Rule Specifications

The governance pipeline validates each agent decision through validators organised in three tiers: **behavioural governance rules** (derived from the domain's behavioural theory — the paper's primary methodological contribution), **domain constraints** (physical, financial, and institutional feasibility checks standard in any ABM), and **epistemic guardrails** (LLM-specific checks that ensure reasoning is grounded in actual simulation state). Validators operate at two severity levels: ERROR (blocks the proposed action and triggers re-reasoning, up to 3 attempts) and WARNING (flags but does not block). The Irrational Behaviour Rate (IBR) reported in the main text is computed using the same behavioural governance rules applied post-hoc to executed decisions (see Methods: Validation Protocol).

**Supplementary Table 1. Irrigation domain governance validators (12 active).**

| # | Validator | Category | Severity | Trigger Condition |
|---|-----------|----------|----------|-------------------|
| 1 | Water-right cap | Physical | ERROR | Agent at allocation cap proposes demand increase |
| 2 | Non-negative diversion | Physical | ERROR | Agent at zero diversion proposes demand decrease |
| 3 | Minimum utilisation floor | Physical | ERROR | Utilisation < 10% of water right; blocks further decrease |
| 4 | Demand-floor stabiliser | Economic | ERROR | Utilisation < 50% of water right; blocks decrease below stability corridor |
| 5 | **Demand-ceiling rule** | **Institutional** | **ERROR** | **Basin demand > 6.0 MAF; blocks demand increase** |
| 6 | Drought severity | Institutional | ERROR/WARN | Drought index ≥ 0.7: blocks large increase; ≥ 0.85: blocks all increases |
| 7 | Magnitude cap | Physical | WARNING | Proposed magnitude exceeds persona cluster bounds |
| 8 | Supply-gap block | Physical | ERROR | Fulfilment ratio < 70%; blocks demand increase |
| 9 | Curtailment awareness | Social | ERROR/WARN | Tier 2+: blocks all increases; Tier 1: blocks large only |
| 10 | Compact allocation | Social | WARNING | Basin demand exceeds Colorado River Compact share |
| 11 | Consecutive-increase cap | Temporal | ERROR | ≥ 3 consecutive demand increases (feature-flagged; default OFF in production) |
| 12 | WSA-ACA coherence | Behavioural | ERROR | High water-shortage appraisal + high adaptive capacity → blocks demand increase |

*Notes: Validators 1–8 enforce physical and economic feasibility. Validator 5 is the demand-ceiling rule that links individual proposals to aggregate basin state (main text, Methods). Validator 6 uses split severity: drought index ≥ 0.7 triggers WARNING (flags large increases), while drought index ≥ 0.85 escalates to ERROR (blocks all increases). Validator 9 similarly uses split severity: Tier 2+ shortage triggers ERROR (blocks all increases), while Tier 1 triggers WARNING (blocks large increases only). Validator 11 was disabled in production runs. Validator 12 operationalises the dual-appraisal framework (WSA/ACA). Irrigation IBR decomposes into three rule sets mapped to specific validators: (A) physical impossibilities — validators 1, 2, 3, and 8; (B) dual-appraisal incoherence — validator 12 (WSA/ACA label–action mismatches); (C) temporal violations — validator 11 logic applied post-hoc.*

**Supplementary Table 2. Flood domain governance validators (12 total: 4 behavioural + 4 domain + 4 epistemic).**

| # | Validator | Category | Severity | Trigger Condition |
|---|-----------|----------|----------|-------------------|
| | **Behavioural governance rules (PMT-derived)** | | | |
| 1 | Extreme-threat block | PMT governance | ERROR | Threat perception ≥ High; blocks do_nothing |
| 2 | Low-coping block | PMT governance | WARNING | Coping perception ≤ Low; warns against elevate/relocate |
| 3 | Relocation-threat-low | PMT governance | ERROR | Threat perception ≤ Low; blocks relocate |
| 4 | Elevation-threat-low | PMT governance | ERROR | Threat perception ≤ Low; blocks elevate |
| | **Domain constraints (simulation infrastructure)** | | | |
| 5 | Re-elevation block (configuration) | Physical | ERROR | Home already elevated; blocks elevate (declared in skill registry) |
| 6 | Re-elevation block (code) | Physical | ERROR | Defence-in-depth duplicate of rule 5 implemented in Python validator; both must pass |
| 7 | Post-relocation block | Physical | ERROR | Agent relocated; blocks all property actions |
| 8 | Elevation affordability | Financial | ERROR | Savings < elevation cost; blocks elevate |
| | **Epistemic guardrails (LLM-specific)** | | | |
| 9 | Majority-deviation warning | Social | WARNING | > 50% neighbours adapted but agent chooses do_nothing |
| 10 | Social-proof hallucination | Semantic | WARNING | Reasoning cites neighbours but agent has 0 neighbours |
| 11 | Temporal grounding | Semantic | WARNING | Reasoning references floods that did not occur |
| 12 | State consistency | Semantic | WARNING | Reasoning contradicts known agent state variables |

*Notes: Behavioural governance rules (1–4) are derived from Protection Motivation Theory and constitute the paper's primary governance contribution. The same rules are applied post-hoc to compute IBR: rules 3 and 4 correspond to IBR violation types V1 (relocation under low threat) and V2 (elevation under low threat); rule 1 corresponds to V3 (inaction under extreme threat), which is excluded from the reported IBR because the pipeline intercepted all violations before execution (see Supplementary Note 5). Rule 2 operates at WARNING severity, which for small LLMs (≤ 4B parameters) produces no measurable behavioural change — a boundary condition of soft governance. Domain constraints (5–8) enforce feasibility checks standard in any flood ABM. Epistemic guardrails (9–12) address reasoning errors unique to LLM-based agents; these operate at WARNING severity and are not included in IBR computation.*

---

## Supplementary Note 3. LLM Prompt Templates

Two prompt templates drive agent reasoning: one for the single-agent flood household and one for the irrigation farmer. Each template is a Jinja-style text file with placeholders (e.g., `{memory}`, `{options_text}`) filled at each decision step by the context builder. The exact placeholder names and the runtime substitution logic are in `broker/components/context/tiered.py`; source files are in `examples/single_agent/config/prompts/household.txt` and `examples/irrigation_abm/config/prompts/irrigation_farmer.txt` in the public repository.

### 3.1 Flood household prompt (single-agent)

```
{narrative_persona}
{elevation_status_text}
Your memory includes:
{memory}

You currently {insurance_status} flood insurance.
You {trust_insurance_text} the insurance company. You {trust_neighbors_text} your neighbors' judgment.

Using the Protection Motivation Theory, evaluate your current situation by considering the following factors:
- Perceived Severity: How serious the consequences of flooding feel to you.
- Perceived Vulnerability: How likely you think you are to be affected.
- Response Efficacy: How effective you believe each action is.
- Self-Efficacy: Your confidence in your ability to take that action.
- Response Cost: The financial and emotional cost of the action.
- Maladaptive Rewards: The benefit of doing nothing immediately.

Now, choose one of the following actions:
{options_text}
Note: If no flood occurred this year, since no immediate threat, most people would choose "Do Nothing."

### MULTI-ACTION OPTION
You may OPTIONALLY choose a SECOND action in addition to your primary action.
- "decision" is your MAIN action this year.
- "secondary_decision" is an OPTIONAL additional action (set to 0 for none).
- You CANNOT choose the same action twice.
- Each action can have its own magnitude.

{rating_scale}

Please respond using the EXACT JSON format below.
- IMPORTANT: The "decision" field MUST be the NUMERIC ID (e.g. 1, 2, 3, or 4) from the available options list.
- Use EXACTLY one of: VL, L, M, H, VH for each appraisal label.
- Ensure all keys match the format exactly.

{response_format}
```

### 3.2 Irrigation farmer prompt

```
{narrative_persona}
{water_situation_text}
{feedback_dashboard}
Your memory includes:
{memory}

You currently {conservation_status} water conservation practices.
Your ability to implement changes to your water management is {aca_hint}.
You {trust_forecasts_text} climate and hydrological forecasts. You {trust_neighbors_text} neighboring farmers' water management advice.

First, assess your WATER SUPPLY situation by considering:
- Water Supply Outlook: Is your water supply abundant, adequate, tight, or critically short this season?
- Demand–Supply Balance: Is your current water request well matched to the available supply, or is there a gap?
Then rate your water_scarcity_assessment.

Next, assess your ADAPTIVE CAPACITY by considering:
- Capacity to Adjust: How easily could you change your water demand (financial, technical, labor)?
- Cost of Change: What would it cost you (financially, operationally) to adjust your irrigation practices?
- Benefit of Current Path: What is the advantage of keeping your current water demand level unchanged?
Then rate your adaptive_capacity_assessment.

Now, choose one of the following water management actions:
{options_text}
Your decision should reflect your farming philosophy and risk tolerance.

{rating_scale}

Please respond using the EXACT JSON format below.
- Use EXACTLY one of: VL, L, M, H, VH for each appraisal label.
- "decision" MUST be the NUMERIC ID (1-5) from the options list.
- Ensure all keys match the format exactly.
{response_format}
```

### 3.3 Runtime placeholder substitutions

| Placeholder | Source | Example value |
|---|---|---|
| `{narrative_persona}` | agent profile CSV column `narrative_persona` | *"You are a cautious farmer in the Upper Basin with senior water rights..."* |
| `{memory}` | HumanCentric memory engine, top-K retrieval | *"Last year's Tier 2 shortage reduced my delivery by 10%"* |
| `{options_text}` | skill registry for the agent type | `1: increase_large, 2: small_increase_subsidy, ...` |
| `{rating_scale}` | config `rating_scales.yaml` | *"Rate on VL / L / M / H / VH"* |
| `{response_format}` | agent type's structured-response schema | JSON skeleton with required keys |
| `{water_situation_text}` | yearly drought index + reservoir state | *"Drought index 0.7; Mead at 1,040 ft; Tier 1 shortage active"* |
| `{trust_insurance_text}`, `{trust_neighbors_text}`, `{trust_forecasts_text}` | agent profile columns, mapped to adverb phrases | *"somewhat trust"*, *"do not trust"* |
| `{aca_hint}` | derived from ACA rating | *"high (you can adapt quickly)"* |
| `{feedback_dashboard}` | validator-layer feedback from the previous decision (if any) | *"Last year: your demand increase was blocked by the demand-ceiling rule."* |

### 3.4 Retry / feedback injection format

When the governance pipeline rejects a proposal, the agent receives its next decision prompt prefixed with an explanatory block listing every blocking rule, the agent's offending proposal, and the reason. The formatter is defined in `broker/utils/retry_message_formatter.py`. Example injection:

```
### GOVERNANCE FEEDBACK (previous attempt rejected)
Your proposed action was: increase_large (magnitude 15%)
Blocked by: demand_ceiling_stabilizer (basin demand 6.2 MAF exceeds 6.0 MAF cap)
Guidance: select an action that does not raise total basin demand above the 6.0 MAF ceiling.
```

Up to three revision attempts are permitted; if the same deterministic blocker set repeats between attempts, the retry loop exits early and the agent's registry-default skill (`maintain_demand` for irrigation, `do_nothing` for flood) executes, with audit status `REJECTED_FALLBACK`.

---

## Supplementary Note 4. Statistical Methods and Metric Definitions

### Behavioural Diversity (EHE)

We quantified behavioural diversity using normalized Shannon entropy (Shannon, 1948):

$$\text{Behavioural diversity} = -\frac{1}{\log_2 k} \sum_{i=1}^{k} p_i \log_2 p_i$$

where $k$ is the number of available action categories and $p_i$ is the empirical frequency of action $i$ across all agent-timesteps. Normalization by $\log_2 k$ ensures a range of [0, 1], with 0 indicating behavioural monoculture (all agents select the same action) and 1 indicating maximum diversity (uniform distribution over all actions).

**Confidence intervals:** 95% CIs were computed via 10,000-iteration bootstrap resampling at the agent-timestep level, preserving within-agent temporal autocorrelation structure.

**Statistical significance:** Differences in behavioural diversity between with-validators and LLM (no validator) conditions were assessed using permutation tests (10,000 permutations) to avoid distributional assumptions.

### Irrational Behaviour Rate (IBR) and Behavioural Rationality Index (BRI)

IBR quantifies the percentage of agent decisions that violate domain-specific behavioural theory predictions. In the irrigation domain, IBR = fraction of high-scarcity decisions (WSA ≥ H) where the agent proposed a demand increase; the null expectation under uniform random action selection is 40% (2 of 5 skills are increases). In the flood domain, IBR = fraction of decisions violating PMT-derived rules (see Supplementary Note 5).

The Behavioural Rationality Index (BRI) is the complement: BRI = 1 − IBR. The null model baseline of 60% for irrigation arises from the skill structure (3 of 5 available skills are non-increase actions). Governed irrigation BRI (61.8% ± 4.7%) is statistically indistinguishable from the null model (60%), indicating that governance removes the increase-bias without prescribing specific action sequences. LLM (no validator) BRI (38.9% ± 3.3%) falls well below the null model, indicating a directional bias toward demand increases that exceeds random chance.

### Model-Specific vs. Pooled Analysis

Per-model analyses are reported as primary findings because:

1. **Model heterogeneity**: Effect sizes varied across models (ΔEHE from −0.099 to +0.047; ΔIBR from +0.25 to +7.66 pp)
2. **Scientific interpretation**: Model-specific patterns reveal which architectural features modulate governance responsiveness
3. **Pooled CI limitations**: Pooled confidence intervals aggregate across heterogeneous effect sizes and should be interpreted as meta-analytic summaries

All nine completed model pairs showed non-increasing IBR under validators, with seven of nine reaching statistical significance (p < 0.05; Supplementary Table 6). Within the Ministral family, three of three models showed significant EHE reduction (Ministral 3B, 8B, 14B; all p < 0.05), indicating that validators moderately narrow behavioural diversity in that family. The three Gemma-3 models showed non-significant EHE changes. The Gemma-4 e4b model was the exception within that family, with a larger EHE reduction (−0.149) paired with a 5.50 pp IBR reduction. Gemma-4 e2b was approximately flat. The largest configuration, Gemma-4 26B, showed a significant IBR reduction (2.30 pp, p = 0.008) alongside a small EHE gain with validators (+0.034), consistent with validators enabling rather than constraining behavioural options when the base model has sufficient capacity. Under alternative composite-action normalizations (Supplementary Table 3), EHE direction depends on specification choice for models with high composite rates.

### Composite-Action Normalization Sensitivity

**Supplementary Table 3. Behavioural diversity sensitivity to composite-action normalization specification (flood domain, 100 agents × 10 years, 3 runs per condition).**

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

## Supplementary Note 5. Cross-Model Replication

### IBR Decomposition

The Irrational Behaviour Rate (IBR, denoted R_H) is computed as the sum of verification rule violations divided by the number of active agent-year observations:

- **V1** (relocation under low threat): agent relocated despite appraising flood risk as low
- **V2** (elevation under low threat): agent elevated the house despite appraising flood risk as low

A third rule, V3 (inaction under extreme threat), blocks do_nothing when threat appraisal is H or VH. V3 yielded zero IBR violations in final executed decisions across all eighteen conditions (nine models × two validator states) because the governance pipeline intercepted V3-violating proposals before execution. In with-validators runs (Gemma-3 4B, 3 seeds), V3 triggered 238 times (9.15% of audited decisions); 220 proposals (92.4%) were corrected by the agent on retry, and 18 (7.6%) were ultimately rejected. Two additional thinking rules — blocking elevation and relocation under low threat — triggered 4 and 2 times respectively, all corrected on retry (Supplementary Table 4). This pattern demonstrates that governance validators actively shape agent proposals through iterative feedback, not merely filter final outputs. V3 is omitted from IBR computation in Supplementary Table 5 because no V3 violations survived the governance pipeline to affect executed behaviour.

**Supplementary Table 4. Governance rule trigger frequency (flood domain, Gemma-3 4B with-validators, 100 agents × 10 years, 3 seeds, 2,600 audited decisions).**

| Rule | Description | Level | Triggers | Corrected on retry | Final rejected | Trigger rate |
|---|---|---|---|---|---|---|
| extreme_threat_block | Block do_nothing when TP ≥ H | ERROR | 238 | 220 (92.4%) | 18 (7.6%) | 9.15% |
| elevation_threat_low | Block elevation when TP ≤ L | ERROR | 4 | 4 (100%) | 0 | 0.15% |
| relocation_threat_low | Block relocation when TP ≤ L | ERROR | 2 | 2 (100%) | 0 | 0.08% |
| elevation_block | Block elevation if already elevated | ERROR | 1 | 1 (100%) | 0 | 0.04% |
| low_coping_block | Block elevation/relocation when CP ≤ L | WARNING | 0 | — | — | 0.00% |

*Triggers counted across the full retry loop. "Corrected on retry" = agent revised to a compliant action after feedback. Overall correction rate: 97.6%.*

### Appraisal Classification for LLM (No Validator) Agents

For LLM (no validator) agents, threat and coping appraisals are inferred from free-text narratives using a three-tier keyword classifier: (1) explicit categorical labels (VH/H/M/L/VL), (1.5) qualifier precedence that detects negation and hedging phrases (e.g., "low risk of flooding", "moderate concern") before keyword matching, and (2) curated PMT keyword dictionaries. For with-validators agents, structured labels are emitted directly by the governance pipeline. LLM (no validator) agents use a relaxed low-threat threshold {L, VL, M} to account for classification uncertainty; with-validators agents use the strict threshold {L, VL}.

### Cross-Model Results

**Supplementary Table 5. Cross-model IBR and behavioural diversity (flood domain, 100 agents × 10 years, 5 seeds per condition unless noted). Values are means ± s.d. across seeds. IBR excludes R5 (re-elevation block, a code-level constraint).**

| Model | Condition | Seeds | IBR (%) | R1 | R3 | R4 | EHE |
|---|---|---|---|---|---|---|---|
| Ministral 3B | LLM (no validator) | 5 | 7.7 ± 1.2 | 82 | 43 | 137 | 0.829 ± 0.016 |
| | Governed LLM | 5 | 0.1 ± 0.1 | 2 | 0 | 2 | 0.806 ± 0.019 |
| Gemma-3 4B | LLM (no validator) | 5 | 8.5 ± 1.1 | 383 | 2 | 13 | 0.815 ± 0.053 |
| | Governed LLM | 5 | 0.9 ± 0.9 | 38 | 0 | 0 | 0.861 ± 0.045 |
| Ministral 8B | LLM (no validator) | 5 | 2.9 ± 0.6 | 70 | 12 | 46 | 0.797 ± 0.024 |
| | Governed LLM | 5 | 0.0 ± 0.1 | 1 | 0 | 0 | 0.769 ± 0.019 |
| Gemma-3 12B | LLM (no validator) | 4 | 0.3 ± 0.2 | 0 | 0 | 10 | 0.585 ± 0.077 |
| | Governed LLM | 5 | 0.0 ± 0.0 | 0 | 0 | 1 | 0.495 ± 0.056 |
| Ministral 14B | LLM (no validator) | 3 | 3.6 ± 0.3 | 34 | 18 | 41 | 0.876 ± 0.026 |
| | Governed LLM | 5 | 0.0 ± 0.0 | 0 | 0 | 0 | 0.795 ± 0.019 |
| Gemma-3 27B | LLM (no validator) | 3 | 0.4 ± 0.3 | 11 | 0 | 0 | 0.662 ± 0.019 |
| | Governed LLM | 5 | 0.0 ± 0.0 | 0 | 0 | 0 | 0.681 ± 0.020 |
| Gemma-4 e2b | LLM (no validator) | 5 | 0.1 ± 0.1 | 3 | 0 | 1 | 0.601 ± 0.012 |
| | Governed LLM | 5 | 0.0 ± 0.0 | 0 | 0 | 0 | 0.612 ± 0.015 |
| Gemma-4 e4b | LLM (no validator) | 5 | 5.5 ± 1.0 | 269 | 0 | 0 | 0.504 ± 0.068 |
| | Governed LLM | 5 | 0.0 ± 0.0 | 0 | 0 | 0 | 0.355 ± 0.017 |
| Gemma-4 26B | LLM (no validator) | 5 | 2.3 ± 0.9 | 114 | 0 | 0 | 0.462 ± 0.021 |
| | Governed LLM | 5 | 0.0 ± 0.0 | 0 | 0 | 0 | 0.496 ± 0.009 |

*R1 = high-threat inaction (do_nothing when TP ≥ H); R3 = low-threat relocation (relocate when TP ≤ L); R4 = low-threat elevation (elevate when TP ≤ L). Counts are seed totals across all 5 runs. EHE = normalized Shannon entropy H/log₂(4), where 0 = monoculture and 1 = uniform. All three Gemma-4 governed rows showed zero violations in every seed (100% validator capture rate); R3/R4 violations were absent across the entire Gemma-4 family regardless of condition, indicating that Gemma-4 base models do not exhibit low-threat over-reaction errors that characterise some smaller LLMs.*

**Supplementary Table 6. Governance effect on IBR and EHE (paired t-test across matched seeds).**

| Model | Seeds | ΔIBR (pp) | 95% CI | p | ΔEHE | 95% CI | p |
|---|---|---|---|---|---|---|---|
| Ministral 3B | 5 | +7.59 | [+6.20, +8.98] | <0.001 | −0.023 | [−0.040, −0.006] | 0.020 |
| Gemma-3 4B | 5 | +7.66 | [+7.01, +8.30] | <0.001 | +0.047 | [−0.061, +0.155] | 0.295 |
| Ministral 8B | 5 | +2.85 | [+2.13, +3.57] | <0.001 | −0.028 | [−0.053, −0.003] | 0.037 |
| Gemma-3 12B | 4 | +0.25 | [−0.15, +0.66] | 0.139 | −0.099 | [−0.317, +0.120] | 0.247 |
| Ministral 14B | 3 | +3.61 | [+2.75, +4.46] | 0.003 | −0.072 | [−0.131, −0.013] | 0.035 |
| Gemma-3 27B | 3 | +0.37 | [−0.26, +1.00] | 0.127 | +0.023 | [−0.000, +0.047] | 0.051 |
| Gemma-4 e2b | 5 | +0.11 | — | 0.072 | +0.011 | — | — |
| Gemma-4 e4b | 5 | +5.50 | — | 0.008 | −0.149 | — | — |
| Gemma-4 26B | 5 | +2.30 | — | 0.008 | +0.034 | — | — |

*ΔIBR = (no validator) − (with validators); positive = validators reduce IBR. ΔEHE = (with validators) − (no validator). 95% CIs from paired t-distribution where seed counts permit; Gemma-4 rows are from the pooled cross-model analysis (`gemma4_nw_crossmodel_analysis.md`). Seven of nine models show significant IBR reduction (p < 0.05); the two non-significant pairs (Gemma-3 12B, Gemma-4 e2b) are near-zero baseline cases with little room for reduction. ΔEHE: Gemma-4 e4b is the exception with a larger magnitude change (−0.149, with-validators less diverse); Gemma-4 26B shows a small EHE gain (+0.034) consistent with validators enabling rather than constraining options at 26B scale. All flood experiments use with-validators agents with HumanCentric memory and the same validator pipeline.

**Decision distribution patterns.** Gemma-3 4B shows the largest IBR gap in the Gemma-3 family (+7.66 pp), driven by R1 violations (383 without validators vs. 38 with); Gemma-4 e4b shows a comparable 5.50 pp reduction. Ministral 3B distributes violations across all three rules. Gemma-3 12B and Gemma-4 e2b are near-null cases (IBR < 0.3% in both conditions), floor-effect outcomes where there is little violation to reduce. In the Ministral family, three of three models show significant EHE reduction under validators (Ministral 3B, 8B, 14B), suggesting that validators moderately narrow behavioural diversity in that family. The three Gemma-3 models show non-significant EHE changes. Gemma-4 e2b is approximately flat on EHE, while Gemma-4 e4b stands out with a larger EHE reduction (−0.149) coupled with the IBR reduction above; this combination matches the pattern Hung and Yang (2021) describe for rule-constrained agents in demand-management settings.

### Supplementary Figure 1

Supplementary Fig. 1 visualizes the effect of the validators in EHE–IBR space across the nine completed flood model configurations and the irrigation domain (Gemma-3 4B). Each arrow connects the LLM (no validator) condition (tail) to the with-validators condition (head) for a single model. Arrows pointing leftward with minimal vertical displacement indicate that validators reduce irrational behaviour without suppressing behavioural diversity. Flood models cluster in the low-IBR region (0–9%), with validators shifting all models further left. The irrigation domain occupies a distinct region (IBR 38–61%) owing to the higher complexity of the 42-year allocation task.

---

## Supplementary Note 6. Agent Reasoning and Cognitive Heterogeneity

To substantiate the claim that validators enable qualitatively distinct reasoning — not merely different action selections — we present three forms of evidence: (1) paired with-validators-vs-LLM (no validator) traces showing divergent reasoning under comparable conditions, (2) within-with-validators comparisons showing heterogeneous reasoning under identical conditions, and (3) a systematic taxonomy of emergent cognitive frames. All traces are from the irrigation domain (78 agents, 42 years, seed 42 unless noted).

### Governed versus LLM (no validator) comparisons

Three reasoning archetypes appear exclusively in with-validators runs: (1) **governance-blocked escalation**, where a demand-increase proposal is rejected and the agent falls back to maintain_demand; (2) **constraint-shaped adaptation**, where repeated shortfall feedback drives the agent toward demand decreases during drought; and (3) **condition-opportunistic expansion**, where governance permits aggressive increase_large during wet years with qualitatively different rationale than LLM (no validator) agents' unconditional growth. LLM (no validator) agents exhibit a fourth archetype: **escalation under scarcity**, where agents respond to shortage signals by demanding more water.

**Supplementary Table 7. Governed vs. LLM (no validator) paired reasoning traces (irrigation domain, seed 42).**

| # | Condition | Agent | Year | Tier | Mead (ft) | Decision | Archetype | Reasoning Excerpt |
|---|-----------|-------|------|------|-----------|----------|-----------|-------------------|
| 1 | Governed | YumaIrrDist | 2 | 2 | 1,028 | **decrease_small** | Constraint-shaped | "My past approach has failed, and I need to adapt to the realities of reduced water availability." |
| 1 | LLM (no validator) | CRIR AZ | 2 | 2 | 1,027 | **increase_large** | Escalation under scarcity | "I need to proactively secure as much water as possible to maximize my yield." |
| 2 | Governed | WelltonMohawkIDD | 3 | 3 | 1,003 | **decrease_large** | Constraint-shaped | "Past attempts to increase my request have failed...I need to actively reduce my demand." |
| 2 | LLM (no validator) | WelltonMohawkIDD | 3 | 3 | 1,000 | **increase_large** | Escalation under scarcity | "I'll lean towards a proactive, albeit aggressive, approach to secure as much yield as possible." |
| 3 | Governed | CocopahIndRes | 10 | 0 | 1,161 | **maintain** (fallback) | Blocked escalation | *Blocked by demand-ceiling rule + high_threat_high_cope_no_increase.* |
| 3 | LLM (no validator) | CocopahIndRes | 10 | 0 | 1,220 | **increase_large** | Unconditional growth | "Lake Mead is rising...I'm not one for caution." |
| 4 | Governed | FtYumaReservation | 38 | 2 | 1,039 | **decrease_small** | Constraint-shaped | "The governance layer is screaming about a 2.2% demand excess...I need to reduce my demand." |
| 4 | LLM (no validator) | FtYumaReservation | 38 | 0 | 1,118 | **maintain** | Status quo inertia | "I'm not seeing any immediate crisis." |
| 5 | Governed | MohaveValleyIDD | 6 | 0 | 1,098 | **increase_large** | Opportunistic expansion | "The potential for increased production outweighs the risk." |
| 5 | LLM (no validator) | NorthGilaValleyIDD | 6 | 0 | 1,098 | **maintain** | Status quo inertia | "There's no compelling reason to disrupt a system that isn't broken." |

Across 16,380 with-validators agent-year decisions (78 agents × 42 years × 5 seeds), 675 were demand decreases (576 small + 99 large, 4.1%), concentrated in drought windows (years 2–3, 38–42). Across 16,380 LLM (no validator) decisions, 3,357 were decreases (3,246 small + 111 large, 20.5%); 10,482 (64.0%) were increases versus 6,829 (41.7%) in with-validators runs.

### Within the with-validators condition: reasoning heterogeneity

A distinct form of evidence comes from comparing with-validators agents *against each other* under identical physical conditions. Supplementary Table 8 presents seven agents from within-with-validators runs who faced the same shortage tier and reservoir state but reached different decisions through different cognitive frames. Across the three illustration seeds (42–44), 41,426 such heterogeneous pairs were identified (see `reasoning_heterogeneity_traces.py` for methodology).

**Supplementary Table 8. Within the with-validators condition: reasoning heterogeneity under identical conditions (irrigation domain).**

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

Across the three illustration seeds (42–44), we identified ten distinct cognitive frames through open coding of 9,828 with-validators agent-year reasoning records (78 agents × 42 years × 3 seeds), with saturation reached at ten frames. These frames are not pre-specified in the persona prompt or governance rules; they emerge from the interaction between the agent's persona, memory, environmental context, and governance feedback.

**Supplementary Table 9. Taxonomy of cognitive frames observed in with-validators irrigation agents.**

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

*All quotes from with-validators audit logs (seed 42). Categories: Expansion = demand increase; Conservation = demand decrease; Status-quo = maintain. Frames 1–4 and 10 co-occur under identical physical conditions (Year 2, Tier 2, Mead = 1,028 ft), ruling out environmental variation as the source of diversity.*

**Data sources.** Governed traces from `production_v21_42yr_seed{42,43,44,45,46}/irrigation_farmer_governance_audit.csv`. Reasoning text from structured CSV field `reason_reasoning`. Heterogeneity analysis: `examples/irrigation_abm/analysis/reasoning_heterogeneity_traces.py`. Reasoning traces in Supplementary Tables 7–9 are presented from seeds 42–44 for illustration; quantitative results in the main text cover all five seeds (42–46).

---

## Supplementary Note 7. Stability Checks

### First-Attempt Analysis

To verify that the diversity difference between conditions is not an artefact of the governance retry loop, we analysed only the first decision attempt for each agent-timestep in the irrigation domain (5 seeds, 16,380 agent-year decisions per condition).

**Irrigation first-attempt results:**
- Governed first-attempt behavioural diversity (EHE): 0.689 ± 0.052
- LLM (no validator) first-attempt behavioural diversity (EHE): 0.848 ± 0.012
- Difference: −0.159 (LLM no validator > with-validators)

LLM (no validator) agents proposed a wider repertoire of actions on their first attempt (EHE 0.848 versus 0.689). This mirrors the full-trace difference reported in Extended Data Table 1 (0.848 versus 0.687), confirming that the diversity gap is present from the initial proposal and is not introduced by the retry process. The higher no-validator diversity reflects arbitrary extraction (agents proposing increases regardless of scarcity context), whereas with-validators agents' lower first-attempt diversity reflects scarcity-appropriate concentration on maintain and decrease actions (see main text, R1).

**Iterative behaviour context.** In with-validators conditions, 40.9% of all proposals were rejected by validators, 65.5% of agent-timesteps required at least one retry, and 0% of decisions fell back to default actions (all proposals eventually resolved within the retry limit). In LLM (no validator) conditions, 31.5% of proposals were rejected by physical precondition checks (at allocation cap), and 37.4% of agent-timesteps required at least one retry. The retry process does not alter the direction of the diversity difference; it slightly narrows the gap because with-validators agents whose increase proposals are rejected on retry sometimes switch to alternative actions on subsequent attempts.

### Insurance Premium Doubling Sensitivity

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
- Difference: −0.104 (no validator > with-validators)

This contrasts with baseline premium conditions, where with-validators and no-validator agents show comparable behavioural diversity for the same model (Supplementary Fig. 1).

**Interpretation.** External cost pressure (premium doubling) appears to force behavioural diversification independently of governance. In the no-validator condition, agents adapted to the higher premium by exploring alternative mitigation strategies (elevation, relocation, do_nothing), increasing diversity above the with-validators condition. This suggests that sufficiently strong economic incentives can substitute for governance constraints in promoting diverse adaptive responses. Future work should systematically vary insurance premiums, elevation costs, and relocation incentives to map the economic-governance interaction landscape.

---

## Supplementary Note 8. Supplementary Water-System Outcomes

### Irrigation Domain

Summary water-system outcomes are reported in Extended Data Table 1. This section provides additional detail.

**Supplementary Table 10. Supplementary water-system outcomes (irrigation domain, Gemma-3 4B, 78 agents × 42 years, 5 seeds each).**

| Metric | Governed | LLM (no validator) |
|--------|----------|------------|
| Minimum Lake Mead elevation (ft) | 988 ± 14 | 895 ± 0 (dead pool) |
| Shortage years (/42) | 14.2 ± 1.5 | 39.2 ± 1.1 |
| Shortage-year demand ratio | 0.407 ± 0.004 | 0.809 ± 0.027 |
| Plentiful-year demand ratio | 0.412 ± 0.004 | 0.640 ± 0.008 |
| Curtailment spread (plentiful − shortage) | 0.005 | −0.169 |
| Year-over-year demand variability (SD) | 0.003 | 0.015 |
| Percentage of proposed decisions that were demand increases | 41.7% | 64.0% |

*All demand ratios computed as basin-aggregate (total requests / total water rights per year). Curtailment spread = plentiful-year DR minus shortage-year DR; negative values indicate higher demand during shortage years. Values are means ± s.d. across 5 seeds.*

LLM (no validator) agents depleted Lake Mead to the dead-pool threshold (895 ft) in every seed, triggering near-permanent shortage (39.2 of 42 years). This collapse resulted from persistent over-extraction: LLM (no validator) agents proposed demand increases in 64% of decisions, driving demand ratios above 0.80 even during shortage years. With-validators agents maintained demand ratios near 0.41 regardless of shortage status (curtailment spread 0.005), with lower year-over-year variability (SD 0.003 versus 0.015), indicating stable operations within institutional bounds. The negative curtailment spread for LLM (no validator) agents (−0.169) indicates that these agents demanded more water during shortage years than during plentiful years, a pattern consistent with anticipatory extraction under scarcity.

### Fuzzy Q-Learning Baseline Comparison

To assess whether adaptive exploitation requires the natural-language reasoning format or merely the governance constraints, we ran a fuzzy Q-learning (FQL) baseline using the reinforcement learning agent from Hung and Yang (2021). The FQL agent operates within the same simulation environment (identical reservoir model, precipitation inputs, shortage tiers, curtailment rules, and governance validators) and the same 78 CRSS agent profiles as the LLM experiments. The only difference is the decision kernel: FQL maps a discretized state (current diversion relative to water right) to two actions (increase or decrease demand) via Q-value comparison, whereas the LLM agent reasons in natural language over five skills.

Agent profiles were reconstructed from with-validators simulation logs (year 1 state: agent_id, cluster, basin, water_right, initial diversion). FQL parameters (mu, sigma, alpha, gamma, epsilon, regret) were assigned from cluster-canonical values (Hung & Yang, 2021, Table 1). Ten seeds (42–51) with cluster rebalancing (50%–30%–20%) were run for FQL; the LLM with-validators comparison uses 5 seeds (42–46).

**Supplementary Table 11. Water-system outcomes: LLM with-validators vs FQL baseline (irrigation domain, 78 agents × 42 years).**

| Metric | LLM with-validators (5 seeds) | FQL Baseline (10 seeds) |
|--------|:---:|:---:|
| Mean demand ratio | 0.411 ± 0.004 | 0.352 ± 0.013 |
| Shortage years (/42) | 14.2 ± 1.5 | 8.5 ± 1.5 |
| Min Mead elevation (ft) | 988 ± 14 | 999 ± 5 |
| 42-yr mean Mead (ft) | 1,087 | 1,140 |

FQL agents extracted less water than LLM with-validators agents (demand ratio 0.352 versus 0.411), resulting in fewer shortage years (8.5 versus 14.2) and higher mean Mead elevation (1,140 versus 1,087 ft). This conservative extraction pattern reflects the FQL agent's binary action space (increase/decrease only) combined with governance validators that block most increase proposals: 84–89% of FQL decisions resulted in maintain_demand as a fallback, producing a near-monoculture output. The FQL agent's Q-learning updates action preferences based on reward signals (fulfilled diversion relative to request), but this learning occurs within a state-action mapping that cannot reference drought context, institutional announcements, or neighbour behaviour in the way that natural-language reasoning can.

The key distinction is not extraction volume but behavioural character. FQL's conservative extraction is a mechanical consequence of validator blocking in a binary action space, not a deliberate adaptation to scarcity signals. LLM with-validators agents extract more water but do so adaptively, with demand ratios that remain stable across shortage and plentiful years (curtailment spread 0.005, Supplementary Table 10). Behavioural diversity is not computed for FQL because the action distribution is dominated by a validator artifact rather than behavioural choice.

**Interpretation.** The FQL comparison isolates the representational contribution: governance constraints alone, applied to a simple decision kernel, produce conservative extraction through mechanical blocking. The combination of governance constraints and natural-language reasoning produces adaptive extraction, where agents navigate within institutional bounds in response to environmental state. Both approaches avoid the system collapse observed in LLM (no validator) agents (Mead = 895 ft, 39.2 shortage years), but through qualitatively different mechanisms.

**Data and code.** FQL results: `examples/irrigation_abm/results/fql_raw/seed{42-51}/`. Runner: `examples/irrigation_abm/run_fql_baseline.py --from-logs`. Comparison metrics: `examples/irrigation_abm/analysis/fql_comparison_metrics.py`.

---

## Supplementary Note 9. Rule-Based PMT Agent Parameterization

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

## Supplementary Note 10. HumanCentric Memory Decay and Cognitive-Architecture Scope

This note documents (a) the quantitative form of the memory decay function used by all WAGF agents in this study and (b) which components of the cognitive architecture are active in this study versus reserved for follow-up work. The goal is transparent disclosure of modelling choices rather than a calibration contribution; the parameters were not fit to household-level survey data and represent deliberate design choices rooted in the Generative Agents framework (Park et al., 2023), adapted for water-risk reasoning.

### 10.1 Decay function form

Each retained memory *m* stored for agent *a* at simulation time *t₀* is reweighted at retrieval time *t* by an emotion-modified exponential decay:

$$
\text{strength}_m(t) = I_0 \cdot \exp\!\left(-\lambda \cdot (1 - \tfrac{1}{2} \cdot w_e) \cdot (t - t_0)\right)
$$

where:
- *I₀* is the initial importance assigned at encoding (domain-adapter output; see §10.2)
- *λ* = 0.1 per simulated year, the base decay rate
- *wₑ* ∈ [0.1, 1.0] is an emotion-class weight (see table below)

The `(1 − ½ · wₑ)` term produces *emotion-modified* decay: a memory encoded with emotion = "critical" (*wₑ* = 1.0) decays at half the baseline rate, whereas a "routine" memory (*wₑ* = 0.1) decays at 95% of baseline. This yields distinct retention horizons by event class without hard-coding per-class *τ* values.

**Emotion-class weights** (configured in `agent_types.yaml`, classified at encoding via keyword matching on memory content):

| Class | *wₑ* | Typical water-domain trigger |
|-------|-----|------------------------------|
| critical | 1.00 | Direct flood damage, property loss |
| major | 0.90 | Significant adaptation decisions (elevate, relocate) |
| positive | 0.80 | Successful protective action (insurance claim paid) |
| shift | 0.70 | Changes in trust toward institutions or neighbours |
| observation | 0.40 | Neighbour/community observations without direct impact |
| routine | 0.10 | No-flood years, uneventful observations |

### 10.2 Domain adapter for importance assignment

Initial importance *I₀* is assigned at memory-write time by a domain adapter (flood-domain implementation at `examples/single_agent/adapters/flood_adapter.py:20-97`). The adapter maps event type to importance value: flood occurrence → 0.9; agent taking an irreversible action (elevate, relocate) → 0.7; agent observing neighbour adoption → 0.4; no-event year → 0.1. The adapter protocol (`DomainReflectionAdapter`) is domain-agnostic; irrigation and future hazards (drought, heat) plug in their own mapping without broker-layer changes.

### 10.3 Calibration scope and limitations

The *λ* = 0.1 year⁻¹ baseline and *wₑ* values were selected to produce qualitative decay patterns consistent with the Generative Agents architecture (Park et al., 2023). They were **not** fit to household-level survey data of post-flood risk perception (e.g., Bubeck and Botzen, 2018). Survey literature reports roughly 50% decay in self-reported flood-risk perception over 3–5 years post-event. Our default parameters produce ~40% decay over 5 years for "critical" memories (*wₑ* = 1.0), a plausible approximation that lies within the cited range but should not be interpreted as a calibrated match. Future work could estimate *λ* and the *wₑ* vector empirically against longitudinal flood-survey data.

### 10.4 Retrieval ranking and prompt composition

Retrieved memories are sorted by decayed importance (descending); ties break by chronological timestamp (ascending). The prompt layer renders each memory as a bare bullet without explicit salience markers (`- {content}`), after an early-stage experiment found that any bracketed prefix (e.g., `[ROUTINE]`) shifted small-LLM Y1 action distributions by >40 percentage points despite identical content, a prompt-structure artefact documented in the framework invariants (`broker/INVARIANTS.md`). The LLM therefore perceives the salience of a memory only via its ordering in the prompt, not via explicit labels.

### 10.5 Cognitive architecture scope

The WAGF implementation includes a cognitive dual-process module (System 1 / System 2 with surprise-gated escalation; `broker/components/cognitive/trace.py`, `broker/components/memory/universal.py`) that is **not activated in the experiments reported here**. Activation requires setting `memory_engine_type = "universal"`; all runs in this study use `memory_engine_type = "humancentric"`, which retains memory scoring and decay but does not populate the surprise / novelty / system-mode audit fields. We defer full dual-process activation to a follow-up study because (a) the present paper's claims rest on validator-layer effects on single-decision reasoning, for which the existing memory engine suffices; and (b) the cognitive module introduces additional calibration parameters (System 2 trigger thresholds) that warrant dedicated evaluation.

### 10.6 Reflection engine

At the end of each simulated year, the reflection engine (`broker/components/cognitive/reflection.py`) consolidates retained memories into a "Consolidated Reflection" insight, which is written back into memory with *wₑ* = "major" and a dynamically computed importance derived from the domain adapter. This provides an event-sensitive mechanism for long-horizon salience: agents with recent flood exposure accumulate year-over-year reflections that surface to retrieval, while agents without notable events accumulate reflections at lower importance. The reflection engine is active in all experiments reported here.

---

**End of Supplementary Information**
