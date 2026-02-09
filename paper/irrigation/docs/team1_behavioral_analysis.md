# Behavioral Analysis Report: v20 Production Run

**Experiment**: 78 LLM agents (gemma3:4b), 42 simulation years, seed 42
**Total decisions**: 3,276 | **Finalized**: 2026-02-08

---

## Key Numbers for Paper

| Metric | Value | Use In Paper |
|--------|-------|--------------|
| Proposed H_norm | **0.7401** | LLM behavioral richness |
| Executed H_norm | **0.3884** | Post-governance realized diversity |
| Governance compression ratio | **0.74 -> 0.39** | Institutional constraint power |
| Construct coverage (WSA/ACA) | **99.2%** | Prompt engineering reliability |
| Mean demand | **5.873 MAF** | Aggregate outcome accuracy |
| CRSS ratio | **1.0027** | Near-perfect calibration to historical |
| Steady-state CoV (Y6-42) | **5.3%** | Post-calibration stability |
| maintain_demand share (executed) | **83.3%** | Institutional conservatism metric |
| Aggressive cluster governance compression | **60% -> 17% increase** | Differential constraint evidence |
| Cold-start decline (Y1-Y5) | **5.715 -> 4.442 MAF (-22%)** | Memory-dependent calibration period |

---

## A. Construct Completeness

The dual-appraisal constructs -- Water Scarcity Assessment (WSA) and Adaptive Capacity Assessment (ACA) -- achieved **99.2% valid label coverage** across all 3,276 agent-year decisions. Both constructs required the LLM to output a categorical label from the set {VL, L, M, H, VH}, and gemma3:4b produced parseable labels in all but approximately 26 instances.

This result is noteworthy because gemma3:4b is a small (4-billion parameter) model. The near-perfect compliance demonstrates that structured prompt engineering -- providing explicit label enumerations and formatting constraints -- can reliably elicit cognitive appraisal constructs even from lightweight models. The 0.8% failure rate is well within acceptable bounds for production-scale ABM experiments and does not materially affect downstream governance rule evaluation, as invalid labels default to conservative fallback handling.

For the paper, this finding supports the claim that LLM-based agents can operationalize theoretically grounded psychological constructs (here, dual cognitive appraisal per Lazarus & Folkman, 1984) without requiring frontier-scale models.

---

## B. Behavioral Diversity: The H_norm Three-Version Interpretation

Normalized Shannon entropy (H_norm) across the 5-skill action space reveals a systematic compression of behavioral diversity through the governance pipeline:

- **Proposed H_norm = 0.7401**: This measures what agents *intended* to do before governance screening. The high value indicates that the LLM generates genuinely heterogeneous skill choices -- agents do not converge on a single action. Proposed skill shares are: 43.4% maintain, 32.1% increase_small, 20.0% increase_large, 2.6% decrease_small, 1.0% decrease_large.

- **Approved H_norm = 0.5464**: Among the 1,971 decisions that passed governance (60.2% of total), diversity is moderate. Governance filters preferentially block increase skills, shifting the approved distribution toward maintain_demand (72.2%).

- **Executed H_norm = 0.3884**: Including the REJECTED-to-maintain_demand fallback, realized behavioral diversity drops substantially. maintain_demand accounts for 83.3% of executed actions.

The **governance compression ratio** from 0.74 to 0.39 (a 47% reduction in entropy) is the single most important behavioral metric for the paper. It quantifies the degree to which institutional rules constrain heterogeneous agent intentions into conservative realized behavior. This is the computational analog of what Ostrom (1990) describes as rules-in-use narrowing the feasible action space -- here measured precisely via information-theoretic entropy.

**Recommendation**: Report proposed H_norm (0.74) as the measure of LLM behavioral richness and the governance compression ratio (0.74 to 0.39) as the measure of institutional constraint strength.

---

## C. maintain_demand Dominance: Institutional Conservatism, Not Behavioral Collapse

The 83.3% executed share of maintain_demand warrants careful framing. The proposed-to-executed gap tells the story:

| Skill Category | Proposed | Executed | Delta |
|----------------|----------|----------|-------|
| Increase (any) | 52.2% | 14.9% | -37.3 pp |
| Maintain | 43.4% | 83.3% | +39.9 pp |
| Decrease (any) | 3.6% | 1.9% | -1.7 pp |

The 40-point increase in maintain_demand share comes almost entirely from REJECTED agents (39.8% of all decisions) falling back to the maintain_demand default. This is by design: when governance blocks an increase proposal (due to ceiling breach, curtailment, or construct inconsistency) and the agent fails to self-correct within the retry budget, the system executes maintain_demand as the safe fallback.

This should be framed as **institutional conservatism under chronic water shortage** rather than behavioral collapse. The governance system converts heterogeneous agent intentions into risk-averse realized behavior -- the institutional equivalent of a risk-averse Nash equilibrium. Agents still *want* to increase (52.2% proposed), but the institutional structure prevents destabilizing over-extraction. The result is a basin that tracks the CRSS historical mean almost exactly (ratio = 1.0027).

---

## D. Cluster Differentiation: Persona-Consistent Governance Response

The three FQL-derived persona clusters (Hung & Yang, 2021) exhibit sharply differentiated governance compression:

| Cluster | N agents | Proposed increase | Executed increase | Compression |
|---------|----------|-------------------|-------------------|-------------|
| Aggressive | 67 | 60.0% | 17.1% | -42.9 pp |
| Forward-looking | 5 | 10.0% | 2.9% | -7.1 pp |
| Myopic | 6 | 0.0% | 0.0% | 0.0 pp |

Governance disproportionately constrains aggressive agents (42.9 percentage-point reduction in increase actions) while leaving conservative agents virtually unchanged. This is the expected result: aggressive agents propose the most increases, which triggers demand ceiling and curtailment validators at higher rates. Forward-looking agents propose moderate increases, facing moderate compression. Myopic agents, already status-quo biased (98.4% maintain), require no governance correction at all.

This pattern mirrors the FQL benchmark: in Hung & Yang (2021), the aggressive cluster also exhibited the highest demand levels before Q-value convergence penalized over-extraction via the regret term. In WAGF, the same equilibrium effect is achieved not through learned reward signals but through explicit governance rules -- a structurally different mechanism producing functionally equivalent outcomes. This correspondence validates the persona calibration and demonstrates that governance rules can substitute for reward-based learning in constraining boundedly rational agents.

---

## E. Cold-Start Analysis: Memory-Dependent Calibration

The demand trajectory reveals a distinct cold-start transient during years 1-5:

| Year | Demand (MAF) | Rejection Rate | Lake Mead (ft) | Tier |
|------|-------------|----------------|-----------------|------|
| Y1 | 5.715 | 66.7% | 1052.8 | 1 |
| Y2 | 4.650 | 42.3% | 1028.1 | 2 |
| Y3 | 4.516 | 56.4% | 1003.1 | 3 |
| Y4 | 4.453 | 11.5% | 1051.2 | 1 |
| Y5 | 4.442 | 12.8% | 1065.0 | 1 |

Y1 starts at 5.715 MAF, close to the CRSS target (5.858), but high rejection rates (66.7%) combined with Tier 1-3 shortage conditions drive rapid demand contraction to 4.442 MAF by Y5 -- a 22.3% decline. The cause is straightforward: agents begin with no episodic memory, so the LLM cannot condition on past action-outcome pairs. Proposals are uninformed by basin conditions, triggering high governance rejection. The REJECTED-to-maintain_demand fallback, combined with active curtailment under Tiers 1-3, compounds the demand decline.

Recovery begins at Y6 (4.828 MAF) as Lake Mead rises above 1075 ft (Tier 0) and agents accumulate memory traces. By Y9, demand peaks at 6.396 MAF, at which point the demand ceiling stabilizer activates and regulates the basin into the 5.5-6.4 MAF steady-state band (Y6-42 mean = 6.024 MAF, CoV = 5.3%).

This cold-start transient is analogous to the exploration phase in reinforcement learning. In FQL, early episodes feature high epsilon-greedy randomness before Q-values converge. In WAGF, early years feature uninformed LLM proposals before memory accumulation enables context-sensitive decision-making. The 5-year calibration period suggests a practical guideline: LLM-ABM experiments should either (a) pre-seed agent memory or (b) exclude the first 5 years from steady-state analysis.

---

## F. Key Framing Recommendations for the Paper

1. **LLM behavioral richness**: Use proposed H_norm = 0.74 to demonstrate that even a 4B-parameter model generates genuinely diverse action portfolios across a 5-skill space. This is not random noise -- it correlates with persona cluster assignments.

2. **Governance compression ratio**: The 0.74 to 0.39 entropy reduction (47%) is the headline metric for institutional constraint power. Frame it as: "Governance rules reduce realized behavioral entropy by nearly half, converting heterogeneous agent intentions into stable basin-level outcomes."

3. **maintain_demand dominance**: Frame the 83.3% executed maintain share as "institutional conservatism under chronic shortage," not behavioral collapse. The 52.2% proposed increase rate proves agents are not passive -- they are actively constrained.

4. **Cluster differentiation**: Frame as "persona-consistent governance response." Aggressive agents face 43 pp compression; myopic agents face zero. This validates both the FQL-derived persona calibration and the differential governance design.

5. **Cold-start period**: Frame as "memory-dependent calibration period" analogous to RL exploration. Report steady-state statistics from Y6-42 (mean = 6.024 MAF, CoV = 5.3%) as the primary outcome metrics, with the Y1-5 transient discussed as a known initialization artifact.

6. **CRSS fidelity**: The 42-year mean of 5.873 MAF (ratio 1.0027 to CRSS historical) and 88.1% of years within the 10% success band demonstrate that governance-constrained LLM agents reproduce historical Colorado River Basin demand patterns with high fidelity.
