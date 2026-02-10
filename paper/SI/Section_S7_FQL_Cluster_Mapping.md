# Section S7: FQL-to-LLM Persona Cluster Mapping

The three behavioral clusters used in this study are derived from k-means clustering of the Fuzzy Q-Learning (FQL) parameters reported in Hung and Yang (2021, Table 2). Each of the 78 CRSS irrigation agents is assigned to one of three clusters based on Euclidean distance in a 4-dimensional parameter space (mu, sigma, alpha, regret). The cluster assignment determines the agent's narrative persona, magnitude sampling parameters, and ACA (Adaptive Capacity Assessment) anchoring text. This mapping provides a theoretically grounded bridge between data-driven reinforcement learning parameters and interpretable behavioral archetypes suitable for LLM-based agent simulation.

## Table S4: FQL Parameter-to-Persona Mapping

| Parameter | Symbol | Aggressive | Forward-Looking Conservative | Myopic Conservative | Interpretation |
|-----------|--------|-----------|----------------------------|--------------------|----|
| Action magnitude mean | $\mu$ | 0.36 | 0.20 | 0.16 | Higher $\mu$ = bolder demand adjustments |
| Action magnitude variance | $\sigma$ | 1.22 | 0.60 | 0.87 | Higher $\sigma$ = wider action range |
| Learning rate | $\alpha$ | 0.62 | 0.85 | 0.67 | Higher $\alpha$ = faster belief updating |
| Discount factor | $\gamma$ | 0.77 | 0.78 | 0.64 | Higher $\gamma$ = longer planning horizon |
| Exploration rate | $\epsilon$ | 0.16 | 0.19 | 0.09 | Higher $\epsilon$ = more strategy experimentation |
| Regret penalty | $r$ | 0.78 | 2.22 | 1.54 | Higher $r$ = stronger aversion to unmet demand |
| **Persona scale** | — | **1.15** | **1.00** | **0.80** | Multiplier applied to Gaussian magnitude parameters |

**Cluster centroids**: The k-means centroids used for assignment are computed in the ($\mu$, $\sigma$, $\alpha$, $r$) subspace, matching the four parameters that most differentiate agent behavior in the FQL model. Gamma and epsilon are included in the persona description but not used for distance computation, as preliminary analysis showed these parameters contributed minimal discriminatory power in the clustering space.

**Agent distribution** (78 CRSS agents): 67 aggressive (85.9%), 5 forward-looking conservative (6.4%), 6 myopic conservative (7.7%). The aggressive-dominated distribution reflects the empirical finding that most Colorado River Basin irrigation districts have historically maintained high utilization rates and respond quickly to supply signals (Wheeler et al., 2022). This distribution was not artificially rebalanced, preserving the data-driven cluster assignment from the original FQL calibration.

## Cluster Assignment Algorithm

Each agent's FQL parameters (from the CRSS calibration dataset `ALL_colorado_ABM_params_cal_1108.csv`) are compared to the three centroids using Euclidean distance:

$$d(a, c) = \sqrt{(\mu_a - \mu_c)^2 + (\sigma_a - \sigma_c)^2 + (\alpha_a - \alpha_c)^2 + (r_a - r_c)^2}$$

where $a$ denotes the agent and $c$ denotes the cluster centroid. The agent is assigned to the cluster with minimum distance. A rebalancing algorithm ensures minority clusters maintain at least 15% representation (minimum 12 agents); agents nearest to cluster boundaries are reassigned if needed to achieve this threshold. In practice, the natural cluster distribution (86%/6%/8%) was retained without rebalancing to preserve the empirical behavioral distribution observed in the Colorado River Basin.

## Table S5: Per-Skill Gaussian Magnitude Parameters

The LLM selects a skill (1-5); the environment then samples the adjustment magnitude from a skill-specific Gaussian distribution. This deliberate decoupling prevents the LLM from specifying exact numeric magnitudes—a task at which gemma3:4b consistently produces 0% regardless of context. This design reflects bounded rationality: human decision-makers often choose directional strategies (e.g., "reduce consumption") while the actual magnitude emerges from implementation constraints and stochastic factors.

| Skill | Base $\mu$ (%) | Base $\sigma$ (%) | Min (%) | Max (%) |
|-------|------------|----------------|---------|---------|
| increase_large | 12.0 | 3.0 | 8.0 | 20.0 |
| increase_small | 4.0 | 1.5 | 1.0 | 8.0 |
| maintain_demand | 0 | 0 | 0 | 0 |
| decrease_small | 4.0 | 1.5 | 1.0 | 8.0 |
| decrease_large | 12.0 | 3.0 | 8.0 | 20.0 |

**Persona scaling**: Actual parameters = Base parameters $\times$ persona_scale. For an aggressive agent selecting increase_large: $\mu = 12.0 \times 1.15 = 13.8\%$, $\sigma = 3.0 \times 1.15 = 3.45\%$, clipped to [8.0, 20.0]%. The sampled value is drawn from $\mathcal{N}(\mu_{\text{scaled}}, \sigma_{\text{scaled}}^2)$ and clipped to [min, max].

**Exploration**: With 2% probability ($\epsilon = 0.02$, uniform across clusters), the sigma is doubled to allow occasional out-of-range sampling. This provides the stochastic exploration analog to the FQL epsilon-greedy mechanism. The uniform exploration rate differs from the cluster-specific $\epsilon$ values in Table S4 because gemma3:4b does not exhibit the strategy-switching behavior that those parameters were calibrated to represent; instead, exploration is implemented via magnitude variance amplification.

## Persona Narrative Templates

Each cluster has a characteristic narrative persona injected via the `{narrative_persona}` placeholder in the system prompt. Key differentiating phrases:

- **Aggressive**: "assertive, action-oriented farmer who responds quickly and decisively"; "prefer measured but confident changes rather than extreme swings"; "low sensitivity to unmet demand penalties"
- **Forward-looking conservative**: "cautious but forward-thinking farmer"; "prefer measured, gradual adjustments"; "highly sensitive to unmet demand"; "analyze carefully before acting"
- **Myopic conservative**: "tradition-oriented farmer who relies heavily on past experience"; "modest, incremental changes"; "preferring the status quo"; "rarely explore unfamiliar strategies"

The `{aca_hint}` placeholder provides cluster-specific adaptive capacity anchoring:
- Aggressive: "strong" (high self-efficacy)
- Forward-looking: "moderate" (cautious but capable)
- Myopic: "limited" (constrained by tradition)

This anchoring directly shapes the LLM's Adaptive Capacity Assessment (ACA) label, which in turn interacts with governance Rule T3 (`high_threat_high_cope_no_increase`). Aggressive agents, anchored to "strong" ACA, are more likely to produce ACA=H/VH, triggering the construct-conditioned block on increases during high scarcity—ensuring that even the most aggressive agents face governance constraint under severe drought. This mechanism replicates the role of the regret penalty in the FQL model, where high-$\mu$/low-$r$ agents (aggressive) are penalized for overshooting demand targets, driving convergence to sustainable equilibria.

## Theoretical Justification

The persona mapping operationalizes bounded rationality through three mechanisms:

1. **Heuristic-based decision-making**: Rather than solving a Bellman equation, LLM agents use natural language reasoning anchored by cluster-specific heuristics (e.g., "prefer gradual adjustments"). This mirrors the satisficing behavior observed in real irrigation districts, where managers rely on rules of thumb rather than optimization (Hendricks & Peterson, 2012).

2. **Persona-scaled risk attitudes**: The persona_scale parameter (1.15/1.00/0.80) acts as a risk attitude proxy. Aggressive agents sample from wider magnitude distributions, analogous to risk-seeking behavior; myopic agents sample from narrower distributions, analogous to risk aversion. This parameterization is consistent with the $\mu$-$\sigma$ relationship in the FQL clusters.

3. **Construct-mediated governance**: The ACA anchoring creates a feedback loop where behavioral type (persona) $\to$ cognitive appraisal (ACA label) $\to$ governance constraint (Rule T3) $\to$ feasible action space. This replicates the dual-appraisal framework from stress and coping theory (Lazarus & Folkman, 1984), grounding the LLM's strategic reasoning in established psychological theory.

Importantly, this approach does **not** implement Prospect Theory. There is no loss aversion parameter $\lambda$, no reference-dependent value function, and no probability weighting. The persona scaling reflects risk attitudes derived from FQL parameter variance, not PT-style loss-gain asymmetry.

## References

Hendricks, N. P., & Peterson, J. M. (2012). Fixed effects estimation of the intensive and extensive margins of irrigation water demand. *Journal of Agricultural and Resource Economics*, 37(1), 1-19.

Hung, M. C., & Yang, Y. C. E. (2021). Fuzzy Q-learning-based multi-agent system for intelligent building control. *Water Resources Research*, 57(6), e2020WR028628.

Lazarus, R. S., & Folkman, S. (1984). *Stress, appraisal, and coping*. Springer.

Wheeler, K. G., Jeuland, M., Hall, J. W., Zagona, E., & Whittington, D. (2022). Understanding and managing new risks on the Nile with the Grand Ethiopian Renaissance Dam. *Nature Communications*, 13(1), 6034.
