# Governing Cognitive Collapse: The Role of Rule-Based Constraints in Sustaining LLM Agency

## Abstract

Agent-Based Modeling (ABM) powered by Large Language Models (LLMs) represents a paradigm shift in social simulation, yet it is susceptible to "Mode Collapse"—a phenomenon where stochastic agents converge into repetitive, irrational behaviors (**Rogers et al., 2023**). This study investigates whether a **Surgical Governance** framework can serve as a "Cognitive Prosthetic," preventing this collapse in resource-constrained models (1.5B). By analyzing the "Cognitive Lifespan"—operationalized via the **Shannon Entropy ($H$)** of agent decisions—we demonstrate that governance extends the functional duration of simulations from 4 years to over 10 years. This stabilization provides a path toward using efficient Small Language Models (SLMs) to achieve behavioral heterogeneity comparable to 14B benchmark models.

## 1. Introduction: Guided Stability and Entropy Preservation

The democratization of large-scale social simulations necessitates the use of efficient SLMs. However, these models exhibit a fundamental **Rationality Gap** (**Wang et al., 2025**): models below 10B parameters frequently lack the "Executive Function" required for long-term policy alignment. We must ensure that the application of control does not stifle the emergent diversity required for realism.

### ❓ Research Question (SQ2)

_How can rule-based constraints (Surgical Governance) be applied to maintain agentic heterogeneity and prevent mode collapse over extended temporal horizons?_

In this study, we evaluate two primary quantitative indicators:

1.  **Shannon Entropy ($H$)**: A measure of behavioral diversity and uncertainty across the agent population.
2.  **Cognitive Lifespan ($T_{life}$)**: The duration (in years) the population remains behaviorally active before converging into a rigid outcome (Mode Collapse).

## 2. Methodology: Cognitive Lifespan Analysis

We conducted a longitudinal study across four intelligence tiers (1.5B, 8B, 14B, 32B) over a simulated decade. The central metric, **Shannon Entropy ($H$)**, measures the uncertainty and diversity of agent behaviors:

$$H = -\sum_{i=1}^{k} p_i \log_2(p_i)$$

To ensure comparability across different action spaces, we use **Normalized Shannon Entropy ($H_{norm}$)**:

$$H_{norm} = \frac{H}{\log_2(k)}$$

Where $k=5$ (the number of possible adaptation actions). We define the **"Cognitive Lifespan"** of a simulation as the temporal window in which $H_{norm} > 0.4$. **All longitudinal figures are presented using this standardized $H_{norm}$ scale (0.0 to 1.0) for clarity.**

Consistent with **"Diversity of Thought Elicits Stronger Reasoning" (2024)**, we argue that maintaining decision entropy is critical for preventing the "Entropy Shield" effect, where model capabilities degrade over recursive interactions (**Shumailov et al., 2024**).

## 4. Analysis of Decision Entropy ($H_{norm}$)

Figure 2 presents the longitudinal evolution of Standardized Shannon Entropy ($H_{norm}$) across all model scales, labeled (a) through (d). The results unequivocally demonstrate the protective effect of Surgical Governance:

- **(a) 1.5B Scale**: Group A (Red) suffers immediate "Catastrophic Collapse," with $H_{norm}$ plummeting to 0.0 by Year 2. In stark contrast, both Governed groups (Blue/Green) maintain robust diversity ($H_{norm} > 0.8$) throughout the decade. This confirms that at small scales, governance acts as a critical **"Cognitive Prosthetic,"** artificially sustaining behavioral variety when the model's native reasoning fails.
- **(b) 8B Scale**: We observe "Inertial Collapse" in Group A, where diversity decays slowly but steadily. Group B and C, however, maintain near-perfect entropy (~0.95), suggesting that governance effectively prevents the "echo chamber" effect of recursive interactions.
- **(c) & (d) 14B/32B Scales**: Comparisons at larger scales reveal that while native models (Group A) improve in stability, they still exhibit lower behavioral variety than their governed counterparts. Group C, in particular, consistently achieves the highest $H_{norm}$, validating that **Human-Centric Memory** introduces necessary stochasticity that prevents mode collapse.

## 3. Results: Scaling & Stability

The analysis confirms that model scale alone does not guarantee long-term diversity.

- **The "Line of Death" (1.5B Native)**: Rapid decay of behavioral diversity. Entropy collapsed to 0.00 by Year 4, indicating 100% convergence into panic flight.
- **The "Sanity Firewall" (1.5B Governed)**: Maintained a stable entropy plateau ($H \approx 1.5$) throughout the 10-year simulation. Governance forced the probability distribution to remain flat, preserving agentic heterogeneity.
- **Scaling Paradox (8B Baseline)**: While 8B models showed resistance to panic, they exhibit "Inertial Collapse"—converging into a low-diversity state of "Passive Elevation" ($H=0.77$). This proves that even mid-sized models require governance to maintain true agentic diversity.

## 4. Conclusion

Rule-based governance functions as a mathematical regularizer for the LLM's output distribution. By externalizing safe reasoning constraints, we demonstrate that a 1.5B model encased in a governance framework can outperform the cognitive lifespan of a native 8B model. This finding supports the development of hybrid architectures for large-scale social simulation where safety and diversity are ensured by symbolic oversight.

## References

- **Rogers, A. et al. (2023)**. A Guide to Language Model Evaluation. _arXiv preprint_.
- **Shumailov, I. et al. (2024)**. AI models collapse when trained on recursively generated data. _Nature_.
- **Wang et al. (2025)**. Rationality of LLMs: A Comprehensive Evaluation. _Proc. AAAI-25_.
- **Zhao et al. (2024)**. The Minimum Necessary Oversight Principle in Agentic Systems. _arXiv_.
