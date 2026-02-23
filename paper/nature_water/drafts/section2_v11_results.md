# Nature Water — Section 2: Results (v14 — water-first restructure, verified basin-aggregate data)
## Date: 2026-02-22 | Word count: ~2,100 | Analysis format
## Structure: R1 adaptive exploitation → R2 rule decomposition → R3 strategy diversity → R4 cross-domain
## Data: All numbers verified via nw_data_verification.py (basin-aggregate method)

---

## Results

### Institutional rules enable adaptive exploitation of water resources

Governed agents extracted more water than ungoverned agents while maintaining stronger coupling between individual decisions and reservoir state (Table 1). Over 42 simulated years, governed agents achieved a mean demand ratio of 0.394 compared with 0.288 for ungoverned agents — yet governed agents responded more sensitively to drought, as reflected in the correlation between annual Lake Mead elevation and aggregate demand (r = 0.547 governed versus 0.378 ungoverned). Lake Mead was consequently lower under governance (42-year mean 1,094 ft versus 1,173 ft) and governed agents triggered shortage conditions more frequently (13.3 versus 5.0 of 42 years). The minimum Mead elevation was comparable (governed 1,002 ft versus ungoverned 1,001 ft), confirming that both systems reached the physical floor during severe early drought; the divergence occurred during recovery, where governed agents adaptively adjusted demand while ungoverned agents could not.

This pattern — higher extraction during abundance, proportionate response to scarcity signals — is consistent with adaptive exploitation under prior-appropriation. In real Colorado River management, institutional rules (shortage tiers, delivery obligations) enable senior rights holders to utilize water aggressively in normal years because those rules guarantee curtailment during drought. Governed agents display a structurally analogous dynamic: institutional validators made it safe to extract more water by ensuring that drought-inappropriate proposals were blocked before execution. The water-system consequence is that governance shifts the operating point upward without degrading drought responsiveness.

Without governance, agents collapsed into monotonic demand-increase patterns, concentrating 77–82% of decisions on demand increases across all seeds. Their demand trajectories converged toward a code-level ceiling over 42 years, producing artificially conservative demand profiles driven by clamps rather than adaptive choice. Ungoverned reservoir stability was inertial — agents rarely triggered shortage because they never extracted enough to draw Mead below critical thresholds, not because they responded to drought. This adaptive exploitation pattern — visible because language-based agents generate explicit reasoning that governance can evaluate and channel — represents a water-system dynamic that conventional parameterized decision rules cannot produce.

**Table 1. Water-system outcomes and strategy diversity across three governance conditions (irrigation domain, Gemma-3 4B, 78 agents × 42 years, 3 runs each).**

| Metric | Governed | Ungoverned | A1 (No Ceiling) |
|--------|----------|------------|-----------------|
| Mean demand ratio | 0.394 ± 0.004 | 0.288 ± 0.020 | 0.440 ± 0.012 |
| 42-yr mean Mead elevation (ft) | 1,094 | 1,173 | 1,069 |
| Demand-Mead coupling (r) | 0.547 ± 0.083 | 0.378 ± 0.081 | 0.234 ± 0.127 |
| Shortage years (/42) | 13.3 ± 1.5 | 5.0 ± 1.7 | 25.3 ± 1.5 |
| Min Mead elevation (ft) | 1,002 ± 1 | 1,001 ± 0.4 | 984 ± 11 |
| Strategy diversity (EHE) | 0.738 ± 0.017 | 0.637 ± 0.017 | 0.793 ± 0.002 |
| Behavioural Rationality (BRI, %) | 58.0 | 9.4 | — |

*Three independent runs per condition (seeds 42, 43, 44). Demand ratio = requested volume / historical baseline allocation. Demand-Mead coupling = Pearson r between annual Lake Mead elevation and annual mean demand ratio (positive r indicates agents reduce demand during drought). EHE = Effective Heterogeneity Entropy (normalized Shannon entropy over 5 action types; see Methods). BRI = fraction of high-scarcity decisions where agents did not increase demand (null expectation under uniform random = 60%). A1 removes the demand ceiling stabilizer only (see next section). See Supplementary Table S6 for additional water-system metrics.*

### A single institutional rule couples individual decisions to basin-wide drought

To identify which institutional rules create the coupling between individual decisions and reservoir state, we removed a single validator — the demand ceiling stabilizer, which blocks demand-increase proposals when aggregate basin demand exceeds 6.0 million acre-feet (MAF) — while retaining all eleven other validators (condition A1; see Methods).

Removing this one rule of twelve collapsed demand–Mead coupling from r = 0.547 to 0.234, nearly doubled shortage years from 13.3 to 25.3, and dropped minimum Mead elevation to 984 ft below the Tier 3 shortage threshold (Table 1, A1 column). Yet removing the ceiling *increased* strategy diversity: EHE rose from 0.738 to 0.793. Agents diversified further — but into extraction patterns decoupled from drought signals, producing higher demand ratios (0.440 versus 0.394) with weaker environmental responsiveness.

This establishes a distinction central to interpreting the governance effect: between *diversity* (a wider action distribution) and *adaptive diversity* (an action distribution coupled to environmental state). The demand ceiling does not suppress diversity; it channels diversity toward drought-responsive patterns. Without it, agents diversify into individually rational but collectively maladaptive extraction — the hallmark of commons dilemmas that Ostrom (1990) identified as the target of institutional design.

The demand ceiling is the only one of twelve validators linking individual proposals to aggregate basin state. Its removal demonstrates that governance-induced diversity is functionally adaptive, not a statistical artefact of constraint-based rejection. This experimental decomposition — isolating one institutional rule's contribution to human-water coupling — would be impossible in conventional agent-based models where institutional rules are embedded in code and cannot be independently manipulated.

### Governance generates strategy diversity beyond what hand-coded models can represent

Governed agents exhibited higher strategy diversity than both ungoverned agents and a hand-coded Protection Motivation Theory baseline across both water domains. In irrigation, governed EHE (0.738 ± 0.017) exceeded ungoverned (0.637 ± 0.017) with zero distributional overlap across three seeds (Table 1). In flood adaptation, the ordering was consistent: governed language agents (0.752 ± 0.052) exceeded rule-based PMT agents (0.689 ± 0.001), which exceeded ungoverned language agents (0.337 ± 0.064; Table 2). Ungoverned agents collapsed into behavioural monoculture: 77–82% demand increases in irrigation, 85.9% inaction in flood.

This diversity is generated by agents reasoning within governance, not filtered into existence by validators. Proposals submitted before any governance feedback already showed higher diversity (first-attempt EHE 0.761 governed versus 0.640 ungoverned; irrigation domain), confirming that the governance context shapes the reasoning process, rather than diversity being created post hoc by the rejection-retry mechanism (see Supplementary Information for retry statistics).

The rule-based PMT agent's diversity stems entirely from parameterized variation: agents differ in income, flood zone, and prior experience, producing different threshold crossings, but all follow identical decision logic. Governed language agents achieve higher diversity through qualitatively different reasoning paths — agents develop rationales referencing personal trade-offs, contextual factors, and institutional constraints in ways that threshold-based rules cannot represent. Under identical physical conditions (same year, same shortage tier, same reservoir elevation), four governed agents selected four different skills through distinct cognitive frames: opportunity-seeking under self-assessed confidence, reflective learning from consolidated memory of past failure, tradition-anchored inertia despite the agent's own memory advising otherwise, and social responsibility referencing neighbour dependence (Supplementary Tables S2–S4 present full reasoning traces and a taxonomy of 10 distinct cognitive frames). This is not a marginal improvement in the same representational format; it is a shift from parameterized homogeneity to reasoning-generated heterogeneity.

**Table 2. Strategy diversity: governed LLM vs rule-based PMT vs ungoverned LLM (flood domain, Gemma-3 4B, 100 agents × 10 years, 3 runs each).**

| Condition | EHE | CACR (%) | do_nothing (%) | insurance (%) | elevation (%) | relocation (%) |
|---|---|---|---|---|---|---|
| **Governed LLM** | **0.752 ± 0.052** | 100.0 | 35.6 | 50.7 | 10.6 | 3.0 |
| **Rule-based PMT** | **0.689 ± 0.001** | 100.0 | 10.6 | 49.1 | 40.2 | 0.1 |
| **Ungoverned LLM** | **0.337 ± 0.064** | 85.5 | 85.9 | 11.7 | 2.3 | 0.0 |

*EHE computed from annual action selections. CACR = Construct-Action Coherence Rate: fraction of decisions where the agent's stated risk assessment is consistent with its chosen action (see Methods; operationalized differently from the irrigation-domain BRI in Table 1). Rule-based agent uses deterministic PMT threshold logic with parameterized agent heterogeneity; composite recommendations (simultaneous insurance + elevation) split into constituents for EHE computation (see Methods).*

### The governance effect generalizes across water hazard types and model architectures

The governance mechanism that produces adaptive exploitation in chronic drought also generates higher strategy diversity under acute flood hazard. In the flood domain, 100 household agents made protective decisions (insurance, elevation, relocation, or inaction) over 10 years with stochastic flood events — a fundamentally different water context from continuous irrigation allocation. Governance eliminated reasoning-action mismatches entirely (0.0% across all models versus 0.1–62.3% ungoverned).

Six models spanning two families and three parameter scales all showed positive governance effects on strategy diversity, five statistically significant (Table 3). The effect was strongest where ungoverned agents exhibited behavioural monoculture: Gemma-3 4B (delta = +0.415) and Ministral 3B (+0.302). Only Gemma-3 12B produced a non-significant effect (+0.012), reflecting strong instruction-tuned priors at this scale (see SI for discussion).

**Table 3. Governance effect on strategy diversity across six language models (flood domain, 100 agents × 10 years, 3 runs per condition).**

| Model | Ungoverned EHE | Governed EHE | Delta | 95% CI |
|-------|:-:|:-:|:-:|:-:|
| Gemma-3 4B | 0.337 ± 0.064 | 0.752 ± 0.052 | +0.415 | [+0.393, +0.458] |
| Gemma-3 12B | 0.471 ± 0.014 | 0.483 ± 0.042 | +0.012 | [-0.018, +0.039] |
| Gemma-3 27B | 0.462 ± 0.032 | 0.676 ± 0.018 | +0.214 | [+0.204, +0.231] |
| Ministral 3B | 0.431 ± 0.056 | 0.734 ± 0.020 | +0.302 | [+0.232, +0.350] |
| Ministral 8B | 0.579 ± 0.014 | 0.626 ± 0.008 | +0.047 | [+0.042, +0.091] |
| Ministral 14B | 0.665 ± 0.010 | 0.708 ± 0.012 | +0.043 | [+0.041, +0.054] |

*Delta = governed minus ungoverned EHE. 95% CIs from bootstrap resampling (agent-timestep level, 10,000 iterations). Reasoning-action mismatch rates in Table S1.*

The consistency across two water domains, six model scales, two model families, and against a hand-coded baseline provides converging evidence that institutional governance enables adaptive strategy diversity — a capacity that depends on the governance architecture rather than the specific language model. Because both domains use the same broker with domain-specific rule configurations rather than redesigned decision logic, the architecture addresses a longstanding limitation of agent-based water models: the need to rebuild decision modules for each application domain.

---

## Structural changes from v13 → v14 (expert panel rewrite)
- **R1 leads with water outcomes**: Adaptive exploitation finding opens the section, not diversity metrics
- **Tables merged**: Current Tables 1+2 → new Table 1 (3-column: Governed/Ungoverned/A1). Tables renumbered: old T3→T2, old T4→T3.
- **R2 reframed**: A1 ablation as "institutional rule decomposition", not "robustness check"
- **R3 reframed**: PMT comparison as "representational capacity advance", not "our method beats baseline"
- **R4 reframed**: Cross-domain as "water hazard generalization", not "model validation"
- **Removed from prose**: Experimental setup details (now in Methods only), curtailment spread (unverified per-agent computation), demand variability SD comparison (direction uncertain), "this result may appear paradoxical"
- **Moved to SI**: First-attempt retry statistics (39.5% rejection, 61.9% retry, 0.7% fallback), model-specific 12B discussion detail
- **Phrasing changes**: "strategy diversity" replaces "behavioural diversity" throughout; "adaptive exploitation" replaces "diversity reshapes trajectories"; water is the subject of all finding sentences
- **Data verified**: All numbers confirmed via nw_data_verification.py using basin-aggregate computation
