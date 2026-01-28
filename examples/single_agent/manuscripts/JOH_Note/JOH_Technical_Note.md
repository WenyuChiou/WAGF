# Technical Note: Surgical Governance Architectures for Stabilizing Small Language Models in Hydro-Social Simulations

> **Version**: 6.0 (Scientific Manuscript Edition)
> **Date**: January 2026
> **Authors**: [Author Names]

## Abstract

As Large Language Model (LLM) agents are increasingly deployed in complex social simulations, a critical tension emerges between model scale and behavioral reliability. This technical note investigates the "Rationality Gap" and "Cognitive Collapse" prevalent in Small Language Models (SLMs) and introduces the **Governed Broker Framework** as a restorative architecture. By subjecting model tiers (1.5B–32B) to rule-based surgical interventions, we demonstrate that structural governance can serve as a "Cognitive Equalizer," allowing resource-efficient 1.5B models to achieve the decisional stability and heterogeneity typically reserved for much larger counterparts. Our results show that governed SLMs not only suppress "unjustified panic" but also sustain a 10-year cognitive lifespan, providing a scalable path for high-fidelity agent-based modeling.

---

## 1. Introduction: The Executive Function Deficit

The integration of Large Language Models (LLMs) into Agent-Based Modeling (ABM) has catalyzed a paradigm shift in socio-hydrology, enabling simulations of human adaptation that transcend the limitations of static, rule-based agents. In these environments, LLM agents act as autonomous decision-makers, navigating complex trade-offs between flood insurance, property elevation, and relocation. However, the adoption of efficient Small Language Models (SLMs) is currently hindered by significant behavioral instability. Research suggests that models with lower parameter counts often lack the "Executive Function" necessary for long-term policy alignment, leading to stochastic reasoning and a fundamental deficit in decisional consistency.

### ❓ SQ1: The Rationality Gap & Unjustified Panic

The first primary challenge is the "Rationality Gap," where synthesized perceived threat fails to justify the resultant high-cost actions. In flood scenarios, SLMs frequently exhibit "Unjustified Panic"—a systemic behavioral misalignment where low-risk stimuli trigger extreme survival responses like relocation. This phenomenon invalidates the predictive utility of simulations by producing disproportionate and irrational migration patterns. This motivates our first research question:

> **SQ1: To what extent can an external governance layer mitigate "unjustified panic" and behavioral misalignment in resource-constrained LLM agents during social simulations?**

### ❓ SQ2: Cognitive Collapse & Heterogeneity Dispersion

Beyond individual decision-making, population-level dynamics suffer from "Cognitive Collapse" or "Mode Collapse." Over extended temporal horizons, ungoverned SLM populations tend to converge into repetitive, low-entropy behavioral monocultures, abandoning the heterogeneity required for valid social modeling. As decisional entropy ($H$) decays, the simulation loses its ability to represent diverse stakeholder responses, effectively "dying" cognitively after only a few years. This leads to our second inquiry:

> **SQ2: How does the application of rule-based constraints (Surgical Governance) influence the cognitive lifespan and decisional entropy of agent populations over extended temporal horizons?**

### ❓ SQ3: The Precision-Efficiency Trade-off

Finally, the implementation of oversight mechanisms introduces a trade-off between safety and performance. Traditional "heavy-handed" governance can inadvertently suppress agentic autonomy, leading to operational stalling or "hallucinated compliance." To maintain scientific validity, a governance framework must be "surgical"—intervening only when explicit safety norms are violated while otherwise remaining silent to preserve emergent agent diversity. This trade-off between scale, surgical precision, and operational overhead is the focus of our third inquiry:

> **SQ3: What is the relationship between model scale, surgical precision, and operational efficiency within the Governed Broker Framework, and can governed SLMs achieve performance parity with benchmark large models?**

### The Solution: The Governed Broker Framework

To address these challenges, we propose the **Governed Broker Framework**, a multi-layered middleware architecture designed to serve as a "Cognitive Prosthetic" for LLM agents. By enforcing a strict "Decision-Action Separation," the framework intercepts agentic intents, audits them against symbolic socio-safe rules (e.g., Protection Motivation Theory thresholds), and provides reflective feedback to correct irrational trajectories. This technical note evaluates the framework's effectiveness across the DeepSeek R1 model family, demonstrating that "Surgical Governance" can bridge the rationality gap and enable the use of efficient SLMs as rigorous scientific instruments.

---

## 2. Methodology & Metric Framework

To quantify the "Surgical Gain" of our framework, we employ a 5-axis metric model vetted against contemporary AI safety literature:

| Metric          | Definition                                                    | Academic Mapping                    |
| :-------------- | :------------------------------------------------------------ | :---------------------------------- |
| **Rationality** | Proportion of agent decisions that align with safety norms.   | Omnibus Rationality (Wang et al.)   |
| **Stability**   | Resistance to "Panic Relocation" under low-threat stimuli.    | Decision Persistance (VeriLA, 2025) |
| **Precision**   | The frequency of "silent" governance (Autonomy Preservation). | Minimum Necessary Oversight (Zhao)  |
| **Efficiency**  | The operational cost and formatting reliability of the model. | Operational Overhead Protocols      |
| **Diversity**   | Normalized Shannon Entropy ($H$) of decision distributions.   | Cognitive Heterogeneity (2024)      |

### Experimental Design: The Three Archetypes

We compare three distinct architectural states to isolate the impact of governance:

- **Group A (Native)**: Ungoverned agents (Stochastic Baseline).
- **Group B (Governed)**: Agents under constant rule-governance (Surgical Filter).
- **Group C (Governed + Memory)**: Governed agents with reflective history (The "Reflective Sage" model).

---

## 3. Results & Discussion

### 3.1 Mitigating Unjustified Panic (SQ1)

Our results demonstrate that while ungoverned 1.5B models exhibit a Panic Rate of ~41% in low-threat conditions, the Governed Broker reduces this to **<1%**. The framework intercepts irrational relocation intents and redirects agents toward calibrated adaptations like insurance, effectively emulating the behavior of 14B benchmark models.

### 3.2 Extending Cognitive Lifespan (SQ2)

Governance acts as a mathematical regularizer for behavioral diversity. Native 1.5B models typically suffer entropy collapse by Year 4 ($H \to 0$), whereas governed agents maintain a stable entropy plateau ($H \approx 1.5$) throughout a 10-year horizon. This stabilization allows SLMs to maintain the agentic heterogeneity required for valid socio-hydrological simulations.

### 3.3 The Surgical Gain (SQ3)

We identify a "Surgical Gain" where governed SLMs achieve near-perfect precision (0.99), proving that the framework preserves autonomy while enforcing safety. Although 1.5B models pay a high "Efficiency" tax to maintain formatting, the resulting behavior is statistically indistinguishable from ungoverned 32B models in specific rationality axes, validating the "Cognitive Equalizer" hypothesis.

---

## 4. Conclusion

Surgical Governance provides a path forward for the **reasonable and reliable use of LLMs** in scientific simulation. By decoupled reasoning from execution, the Governed Broker Framework allows researchers to leverage the efficiency of Small Language Models without compromising the rationality or diversity required for high-stakes policymaking support.

---

## References

- **Wang et al. (2025)**: _Rationality of LLMs: A Comprehensive Evaluation._
- **Rogers, A. et al. (2023)**: _A Guide to Language Model Evaluation._
- **Shumailov, I. et al. (2024)**: _AI models collapse when trained on recursively generated data. Nature._
- **Zhao et al. (2024)**: _The Minimum Necessary Oversight Principle in Agentic Systems._
- **VeriLA (2025)**: _Measuring Resilience to Reasoning Perturbations in Agents._
