# JOH Technical Note: Bridging the Cognitive Governance Gap

**Title**: Bridging the Cognitive Governance Gap: A Framework for Explainable Bounded Rationality in LLM-Based Hydro-Social Modeling

## 1. Introduction: Governing the Ghost in the Machine

The coupling of human systems with hydrological processes—_socio-hydrology_—requires agents that are not only linguistically fluent but behaviorally plausible [Di Baldassarre et al., 2013]. Recent advances in Large Language Models (LLMs) have enabled "Generative Agents" capable of complex planning and social interaction [Park et al., 2023; Xi et al., 2023]. However, when applied to physically constrained environments like flood adaptation, these agents exhibit a critical **"Fluency-Reality Gap."** They may eloquently justify a decision to raise a house (Fluency) while ignoring that they hold zero capital (Reality). They suffer from the "Goldfish Effect," forgetting catastrophic flood events from just a few timesteps prior due to limited context windows [Gao et al., 2024].

Existing frameworks (e.g., AQUAH, Water_Agent) have successfully automated _modeling tasks_—configuring HEC-RAS or retrieving data [Reference Needed]. Yet, they lack a unified architecture for **Cognitive Governance**—the enforcement of bounded rationality constraints without retraining the foundation model.

This Technical Note introduces the **Governed Broker Framework**, an _enhanced cognitive architecture_ that acts as "Cognitive Middleware" between raw LLM reasoning (System 1) and physical world constraints (System 2) [Kahneman, 2011]. Grounded in **Protection Motivation Theory (PMT)** [Rogers, 1975] and the **CoALA framework** [Sumers et al., 2023], our approach enforces:

1.  **Physical Validity**: Rejection of hallucinated or impossible actions via a governance layer.
2.  **Long-Term Resilience**: A tiered memory system that consolidates episodic trauma into semantic wisdom.
3.  **Explainable Bounded Rationality**: A transparent "Self-Correction Trace" that provides scientific auditability.

We validate this framework using a 4-model benchmark (Llama 3.2, Gemma 3, DeepSeek-R1, GPT-OSS) across a 10-year coastal flood simulation, demonstrating that governance significantly improves **Rationality Scores (RS)** and **Adaptation Density (AD)** compared to ungoverned baselines.

---

## 2. Methodology: The Governed Broker Framework

The framework is designed as a domain-agnostic "Broker" that decouples the cognitive agent from the physical simulator. It consists of three core components: (2.1) The Tiered World Model, (2.2) The Cognitive Middleware, and (2.3) The Three Pillars of Governance.

### 2.1 Tiered World Modeling: The Single Source of Truth

Unlike standard ABMs where agents access global variables directly, we implement a **Tiered Environment** to strictly separate _perception_ from _reality_:

- **Global Layer**: Macro-scale drivers (e.g., Sea Level Rise, Inflation Rates).
- **Local Layer**: Spatially explicit constraints (e.g., Tract-level Flood Depth, Paving Density).
- **Institutional Layer**: Policy constraints (e.g., FEMA Grant Budget, Insurance Availability).
- **Social Layer**: Observable neighbor states (e.g., "70% of neighbors elevated").

This separation ensures that the LLM agent interacts only with a _perceived_ subset of the world, processed through its sensory inputs, preventing "omniscient" cheating.

### 2.2 Cognitive Middleware: The System 1-System 2 Bridge

We implement the **CoALA** (Cognitive Architectures for Language Agents) pattern by treating the LLM not as the _agent itself_, but as the _reasoning core_ (System 1). The "Broker" acts as the wrapper (System 2), managing the input/output cycle:

1.  **Perception**: The Broker fetches signals from the Tiered Environment and formats them into a JSON `Context`.
2.  **Reasoning**: The LLM processes the `Context` and proposes an `Action`.
3.  **Governance**: The `Proposal` is intercepted by the Governance Engine. If it violates laws (e.g., `cost > budget`), it is rejected with a specific error message.
4.  **Learning**: The agent receives the error (e.g., "Insufficient Funds") and must retry, mimicking the human process of realizing constraints.

### 2.3 The Three Pillars of Cognitive Governance

To enforce PMT-consistent behavior, the framework rests on three pillars:

- **Pillar 1: Bounded Rationality Governance**: Hard-coded checks against the Physical Layer. An agent cannot "will" a house elevation into existence without the required funds and permits.
- **Pillar 2: Episodic-Semantic Consolidation**: To counter the "Goldfish Effect," a background process summarizes past events (Episodic) into high-level beliefs (Semantic). E.g., "Year 3 Flood was bad" becomes "I am vulnerable to floods."
- **Pillar 3: Perception Anchoring**: The input prompt is structured to force a PMT appraisal: "Assess Threat" -> "Assess Efficacy" -> "Decide." This structure ensures hazards are not drowned out by irrelevant social chit-chat.
