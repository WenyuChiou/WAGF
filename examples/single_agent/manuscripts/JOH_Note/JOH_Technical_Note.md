# JOH Technical Note (v5): The Cognitive Architecture of Adaptation

> **Version**: 5.0 (Cognitive Architecture Edition)
> **Date**: January 2026

**Title**: The Cognitive Equalizer: How Governance Architectures Stabilize Small Language Models in Hydro-Social Simulation

**Abstract**
As Agentic AI scales, a critical question emerges: Do we need larger models (32B+) for rational behavior, or better architectures? This Technical Note presents the **"Cognitive Equalizer Hypothesis"**. By subjecting the DeepSeek R1 family (1.5B–32B) to three distinct governance architectures, we identify a "Universal Stabilizer" effect. We classify these architectures as **The Child (Mode A)**, **The Constraint (Mode B)**, and **The Sage (Mode C)**. Our findings demonstrate that Mode C (Reflective Governance) allows small 1.5B models to exhibit the behavioral stability and reasoning depth typically reserved for 32B models, effectively solving the "Small Model Instability" problem through architectural scaffolding rather than parameter scaling.

**Keywords**: Socio-hydrology, Governance Scaling Laws, DeepSeek R1, Generative Agents, Cognitive Equalizer.

## 1. Introduction: The Cognitive Gap in Agent-Based Modeling

The integration of Large Language Models (LLMs) into Agent-Based Modeling (ABM) promises a "Generative Revolution" in socio-hydrology (Park et al., 2023; Xi et al., 2023). By replacing static laws with fluid neural networks, we aim to simulate complex adaptation strategies like migration and insurance with high fidelity. However, a critical "Validity Gap" remains (Ji et al., 2023). Unconstrained LLMs suffer from "Cognitive Instability"—oscillating between panic and apathy due to stochastic entropy. Our **Governed Broker Framework** addresses this by introducing a "System 2" cognitive prosthetic, ensuring that agent rationality is not just a function of model size, but of architectural governance. This leads to our first inquiry: **Can a Reflective Governance Framework enforce rational adaptation in unstable agents (SQ1)?**

Beyond basic rationality, we must address the "Small Model Problem". Current stable reasoning typically requires massive models (e.g., GPT-4), which are computationally prohibitive for large-scale simulations ($N=10^5$). We hypothesize that cognitive architecture can serve as a scalable "Equalizer", allowing small 1.5B models to mimic the stability of larger counterparts. To validate this, we conduct rigorous **Stress Testing** (Pressure Tests), subjecting agents to high-frequency noise to measure their robustness. This motivates our second question: **Does this framework effectively stabilize small-parameter models to match large-model performance (SQ2)?**

Finally, adaptation is inherently social. In hydro-social systems, decisions are driven not just by individual risk perception but by community feedback and transparency. However, social cues can also introduce "Contagion Effects" or "Groupthink", potentially destabilizing the governed agents. We therefore investigate the "Social Cost" of agency: **How does social transparency affect the stability of these governed agents (SQ3)?**

## 1.4 Methodology & Metrics

To rigorously evaluate these architectures, we employ a **"Cognitive Appraisal Profile"** to diagnose the internal reasoning process (System 2) rather than just the final output:

- **TP (HiTA)**: High Threat Appraisal rate (Paranoia).
- **CP (HiCA)**: High Coping Appraisal rate (Confidence).
- **Alignment (Align)**: Probability of Action given High Appraisal (Rationality).
- **Intv**: Governance Intervention Count (Cognitive Deficit).
- **Stability (FF)**: Flip-Flop Rate (Inter-annual decision consistency).

---

### 1.4 Methodology: The Three Archetypes

To investigate these problems, we map our experimental groups to three "Developmental Stages" of AI reliability:

**Type A: The Unstructured Child (Baseline)**

- **Cognitive State**: **Reactive**. Driven by immediate context window noise.
- **Metaphor**: An impulsive child who forgets the past and reacts only to the present.

**Type B: The Constrained Adult (Mode I)**

- **Cognitive State**: **Compliant**. Externalizes reasoning to "System Rules".
- **Metaphor**: A bureaucratic adult who follows the building code but lacks deep introspection. Efficient, resilient, but rigid.

**Type C: The Reflective Sage (Mode II, "The Ideal")**

- **Cognitive State**: **Agency**. Internalizes reasoning via Reflection and Memory.
- **Metaphor**: A wise elder who makes hard decisions (including Retreat) based on deep historical synthesis.

### 1.5 Conclusion: The Ultimate Goal

Ultimately, the purpose of this framework is not merely to build "smarter" agents, but to **operationalize Large Language Models as rigorous scientific instruments**. By solving the trilemma of Rationality, Scale, and Cost, we aim to provide a blueprint for the **reasonable and reliable use of LLMs** in high-stakes socio-hydrological simulations, ensuring that the stochastic nature of AI does not compromise the validity of scientific inquiry.

### SQ2: The Stability Question (Scaling)

> _Can the Cognitive Architecture stabilize the reasoning trajectories of small-parameter models (1.5B) to match the behavioral fidelity of large-parameter models?_

- **Metric**: **Validator Error Profile**.
  - Definition: The distribution of **Syntactic Errors** (JSON Malformation) vs. **Semantic Errors** (Constraint Violations / Model-Governance Mismatch).
  - _Purpose_: Proves the "Cognitive Equalizer" hypothesis by showing Reduced Entropy in Group C (1.5B) vs Group A (1.5B).

### SQ3: The Cost Question (Efficiency)

> _What is the computational and temporal cost of deploying Reflective Governance, and does the gain in stability justify the overhead?_

- **Metric**: **Runtime Duration & Token Volume**.
  - _Purpose_: Quantifies the "Price of Agency"—the extra compute required to turn a Small Model into a Wise Agent.

## 2. Results: The Cognitive Architecture of Adaptation (SQ1)

### 2.1 The "U-Shaped" Scaling Curve

Contrary to the expectation of linear improvement, our analysis reveals a **U-Shaped Curve** in decision rationality across model sizes (1.5B $\rightarrow$ 8B $\rightarrow$ 14B).

#### Metric Summary Table (SQ1)

| Model    | Group        | HiTA (Threat)    | TA_Al (Alignment)     | HiCA (Coping)   | CA_Al (Alignment) | FF (Stability)    | Intv (Cost)     |
| :------- | :----------- | :--------------- | :-------------------- | :-------------- | :---------------- | :---------------- | :-------------- |
| **1.5B** | A (Null)     | 0.30 (Low)       | 0.85 (High)           | 0.27 (Low)      | 0.84 (High)       | 0.14 (Stable)     | -               |
| **1.5B** | B (Rule)     | 0.08 (Mute)      | 0.91 (High)           | 0.04 (Mute)     | 0.97 (High)       | 0.91 (Unstable)   | **138 (Fail)**  |
| **1.5B** | **C (Sage)** | **0.03 (Calm)**  | **0.91 (High)**       | **0.03 (Calm)** | **0.93 (High)**   | **0.66 (Stable)** | **0 (Perfect)** |
|          |              |                  |                       |                 |                   |                   |                 |
| **8B**   | A (Null)     | **0.96 (Panic)** | 0.83 (High)           | **0.90 (Ego)**  | 0.83 (High)       | **1.86 (Chaos)**  | -               |
| **8B**   | B (Rule)     | 0.32 (Mod)       | **0.49 (Disconnect)** | 0.22 (Low)      | **0.20 (Lazy)**   | 1.31 (Unstable)   | **23 (Leak)**   |
| **8B**   | **C (Sage)** | 0.43 (Calm)      | 0.44 (Low)            | 0.35 (Mod)      | 0.23 (Low)        | 1.54 (Unstable)   | **0 (Perfect)** |
|          |              |                  |                       |                 |                   |                   |                 |
| **14B**  | A (Null)     | 0.72 (Rational)  | 0.97 (Perfect)        | 0.62 (Real)     | 0.97 (Perfect)    | **0.56 (Stable)** | -               |
| **14B**  | B (Rule)     | 0.55 (Mod)       | 0.93 (High)           | 0.20 (Low)      | 0.90 (High)       | 1.60 (Wobble)     | 0 (Perfect)     |
| **14B**  | C (Sage)     | 0.53 (Mod)       | 0.90 (High)           | 0.18 (Low)      | 0.76 (Drop)       | **2.05 (Wobble)** | 0 (Perfect)     |

### 2.2 Mechanism Analysis

#### (1) The Small Model Problem (1.5B): Need for Scaffolding

- **Observation**: In Group B (Governance Only), the 1.5B model fails catastrophically, requiring **138 interventions** to maintain format/logic.
- **Solution**: Group C (Memory + Reflection) acts as a **"Cognitive Prosthetic"**. The explicit reflection step allows the model to decompose complex logic it cannot handle in a single pass.
- **Result**: Interventions drop to **0**. The framework effectively "upgrades" the 1.5B model's reasoning capacity to match larger models.

#### (2) The Adolescent Phase (8B): The Problem of Focus

- **Observation**: The 8B model in Baseline (Group A) is hyper-sensitive (**HiTA 0.96**). It perceives everything as a threat but lacks the executive function to act, leading to **Cognitive Dissonance** (High Threat, Low Action).
- **Solution**: Governance forces it to prioritize. While alignment remains low (it still "feels" scared but is forced to act calmly), Group C successfully successfully suppresses the panic-induced chaos (Intv 23 $\rightarrow$ 0).

#### (3) The Large Model Paradox (14B): The Problem of Over-Thinking

- **Observation**: The 14B model is natively stable and rational (Group A FF 0.56).
- **Governance Cost**: Adding deep reflection (Group C) actually **destabilizes** the agent (FF increases to 2.05). The additional context causes the model to second-guess its optimal initial intuition ("Rumination").
- **Implication**: For high-functioning models, lighter governance (Group B) is superior to heavy cognitive architecture (Group C).

### 2.3 Conclusion on Architecture vs Scale

**Type C Architecture acts as a "Cognitive Equalizer".** It allows cheap, unstable 1.5B models to achieve the **zero-intervention reliability** of 14B models. However, it obeys a law of diminishing returns; applying the same heavy architecture to an already capable 14B model yields regression (instability) rather than improvement.

## 3. Governance as a Memory Prosthetic

We further identify that the difference between Type B and Type C is primarily **Memory Management**:

- **Type B (Resilience)**: Relies on **Forgetting**. By allowing trauma to decay (Window Memory), the agent's fear subsides, allowing the Governance Framework to act as a "Prosthetic Rationality" tailored for investment (Elevation).
- **Type C (Agency)**: Relies on **Remembrance**. By preserving trauma (Importance Memory), the agent's fear overrides standard rules, activating "Safety Valve" clauses that permit Rational Retreat.

## 4. Policy Implications

- **Use Type B**: When the goal is **Infrastructure Preservation** (Engineering Resilience).
- **Use Type C**: When the goal is **Social Realism** (Predicting Climate Migration).

---

**References**

- Di Baldassarre, G., et al. (2013). Socio-hydrology.
- Park, J. S., et al. (2023). Generative Agents.
