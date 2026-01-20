# JOH Technical Note (v3): Bridging the Cognitive Governance Gap

> **Version**: 3.0 (Universal Cognitive Architecture Edition)
> **Date**: January 2026

**Title**: Bridging the Cognitive Governance Gap: A Framework for Explainable Bounded Rationality and Eco-Cognitive Gating in LLM-Based Hydro-Social Modeling

**Abstract**
Agent-Based Models (ABMs) are increasingly leveraging Large Language Models (LLMs) to simulate human behavioral responses to environmental extremes. However, these "Generative Agents" often suffer from a critical **"Fluency-Reality Gap"** (Turpin et al., 2023): they remain proficient storytellers but inconsistent actors. Agents frequently produce unfaithful explanations, where stated appraisals are logically decoupled from simulated actions (e.g., acknowledging catastrophic risk while taking zero protective measures). This Technical Note introduces the **Governed Broker Framework**, a multi-tiered architecture that enforces **Bounded Rationality** by decoupling stochastic reasoning (System 1) from deterministic governance (System 2).

In a comparative study of three cohorts—**Naive (Group A)**, **Static-Governed (Group B)**, and **Human-Centric (Group C)**—we identify a fundamental trade-off between "Apathy" and "Artificial Reactivity." We demonstrate that while static governance provides a safety net, behavioral realism requires a **v3 Universal Cognitive Architecture** driven by **Active Inference** (Friston, 2010). By implementing a "Surprise Engine" (Prediction-Error-driven gating), we allow agents to dynamically switch between low-power routine habits and high-fidelity crisis reasoning, bridging the gap between fluency and physical reality.

**Keywords**: Socio-hydrology, Generative Agents, Cognitive Governance, Active Inference, Bounded Rationality, LLM-ABM.

## 1. Introduction: The Calibration Crisis in Generative ABM

Integrating realistic human behavior into physical modeling (Socio-Hydrology) is paramount for assessing community resilience (Di Baldassarre et al., 2013). While Large Language Models (LLMs) enable the creation of **"Generative Agents"** (Park et al., 2023) with rich narrative personas, their deployment in scientific simulations reveals a "Calibration Crisis." LLMs act as unconstrained "System 1" probabilistic engines, often drifting into **temporal incoherence** (the "Goldfish Effect") or producing **unfaithful reasoning** where internal appraisals (Threat/Coping) do not causally drive the final decision.

To address this, we argue for the enforcement of **Bounded Rationality** (Simon, 1955) via an externalized **Cognitive Governance** layer. This layer must move beyond simple rule-checking toward **Eco-Cognitive Gating**—a process where the agent's internal state determines the depth of its cognitive processing. This paper explores the transition from "Static Governance" (Prosthetic System 2) to an "Emergent Governance" (v3) based on **Predictive Coding**, where environmental "Surprise" (Prediction Error) triggers the activation of high-fidelity memory and reasoning.

## 2. Methodology: The Three-Layer Architecture

The framework is implemented as a **Three-Layer Architecture** that strictly decouples the stochastic reasoning of the agent from the deterministic laws of the simulation. This design, visualized in the Unified Architecture (Figure 1), consists of:

1.  **Layer 1: The Tiered World Model** (The deterministic "Source of Truth").
2.  **Layer 2: The Cognitive Middleware** (The "Governed Broker" managing input/output).
3.  **Layer 3: The Reasoning Core** (The "System 1" LLM).

This Structure ensures that the LLM never interacts with the simulation directly, but always through the **Broker** middleware (Layer 2), which enforces the "Three Pillars of Governance."

### 2.1 Tiered World Modeling: The Single Source of Truth

Unlike standard ABMs where agents access global variables directly, we implement a **Tiered Environment** to strictly separate _perception_ from _reality_:

- **Global Layer**: Macro-scale drivers (e.g., Sea Level Rise, Inflation Rates).
- **Local Layer**: Spatially explicit constraints (e.g., Tract-level Flood Depth, Paving Density).
- **Institutional Layer**: Policy constraints (e.g., FEMA Grant Budget, Insurance Availability).
- **Social Layer**: Observable neighbor states (e.g., "70% of neighbors elevated").

### 2.2 Cognitive Middleware: The System 1-System 2 Bridge

We implement the **Unified Architecture** (Figure 1), following the CoALA pattern by treating the LLM not as the _agent itself_, but as the _reasoning core_ (System 1). The "Broker" acts as the wrapper (System 2), managing the input/output cycle:

![Figure 1: The Unified Structural Architecture (Mechanism Independent)](file:///C:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/docs/architecture.png)

1.  **Perception (`ContextBuilder`)**: The system aggregates signals from the Tiered Environment (Global, Local, Social) into a structured JSON prompt, filtering out "omniscient" data.
2.  **Reasoning (`Generative Agent`)**: The LLM (System 1) processes the context and proposes an adaptation `Skill` (e.g., "Elevate House").
3.  **Governance (`SkillBroker`)**: The Broker intercepts the raw proposal. It executes the `Governance Logic` defined in the `AgentType` registry.
4.  **Correction (`Feedback Loop`)**: If a validator (e.g., `budget_constraint`) is triggered, the action is rejected, and a structured error is fed back for a retry (System 2 correction).

### 2.3 The Three Pillars of Cognitive Governance

To enforce **theoretically grounded behavior** (whether based on PMT, PADM, or economic rationality), the framework rests on three foundational pillars of governance.

First, **Bounded Rationality Governance** serves as the primary defense against **Factuality Hallucinations**. Rooted in Simon's theory of **Bounded Rationality (Simon, 1955)**, it implements hard-coded constraints against the physical world layer, ensuring that agents cannot execute actions—such as "elevating a house"—without sufficient financial capital.

Second, **Episodic-Semantic Consolidation** addresses the "Goldfish Effect" by utilizing a background reflection and consolidation mechanism. This mirrors the **Episodic Buffer** model of working memory (Baddeley, 2000).

Third, **Perception Anchoring** mitigates **Faithfulness Hallucinations** by structuring the reasoning process. By explicitly requiring the model to assess key situational variables (e.g., risk level, resource availability) before making a final decision, this pillar prevents the agent from drifting into "social chit-chat."

## 3. Experimental Application: The Plot Study

To demonstrate the efficacy of the Governed Broker Framework, we applied it to a stylized 10-year hydro-social simulation (JOH Case). We compared two distinct agent architectures:

### 3.1 Experimental Cohorts

- **Group A (Naive)**: Ungoverned "System 1" agents using standard LLM prompting. Represents the unconstrained baseline susceptible to stochastic drift.
- **Group B (Static-Governed)**: Agents monitored by a "Prosthetic System 2" with hard-coded logic constraints. Uses sliding-window memory.
- **Group C (Human-Centric/v1)**: Agents using **Human-Centric Memory** (Episodic-Semantic Consolidation) with multiplicative decay. Represents the "State-Dependent" baseline where memory persistence is tied to emotional significance.

### 3.2 Metrics

We tracked:

1.  **Adaptation Rate**: Percentage of population relocating.
2.  **Panic Rate**: Frequency of `High` Threat Appraisal decisions in non-flood years.
3.  **Internal Fidelity (IF)**: Correlation between Threat Appraisal and Action.

## 4. Results: Apathy, Reactivity, and Persistence

We evaluated behavioral phenotypes using a "Difference-in-Differences" approach across the 10-year simulation.

### 4.1 Group A: The "Frozen" Phenotype (Inaction Bias)

Naive agents (Group A) exhibited a profound **Inaction Bias**. While they did take disjointed actions (approx. 20% cumulative adaptation), these decisions were rarely sustained.

- **Behavioral Drift**: Agents would write text acknowledging "High" risk in year 3 but revert to "Do Nothing" in year 4 despite rising water levels.
- **Conclusion**: Without governance, agents normalize risk instantly—the **Goldfish Effect**.

### 4.2 Group B: The "Sawtooth" Phenotype (Artificial Reactivity)

The introduction of Static Governance (Group B) successfully forced protective actions but induced a **"Sawtooth"** behavioral artifact.

- **Pattern**: Agents exhibited a burst of protective activity (Panic Rate ~25%) immediately after a flood, followed by a sharp drop in perception once the external rule-trigger was removed.
- **Interpretation**: Governance here acts as a "Prosthetic"—it forces a valid action record but fails to update the agent's internal world-model.

### 4.3 Group C: The "Ratchet" Phenotype (Trauma Persistence)

Group C (Human-Centric v1) demonstrated the stability of **Internalized Persistence**.

- **The Ratchet Effect**: Unlike Group B's rapid decay, Group C agents maintained high risk perception for multiple years after an event. Memory retention was driven by the $Recency \times Significance$ decay formula.
- **Fidelity**: Internal Fidelity (IF > 0.8) indicated that actions were causally driven by consolidated "Trauma Anchors."

## 5. Discussion: Why Human-Centric Memory Matters

### 5.1 Rules vs. Memory

Group A proves that Naive LLMs are apathetic. Group B proves that Static Rules can force action but create "Sawtooth" instability.
**Group C (Human Centric)** bridges this gap by using memory strategies (specifically emotional decay) to create _durable_ behavioral change.

## 6. The v3 Universal Cognitive Engine: Surprise-Driven Gating

The limitations observed in Groups B (Artificial Reactivity) and C (Static Persistence) necessitate a transition to **Emergent Realism**. We propose the **v3 Universal Cognitive Engine**, which unifies efficient routine behavior with high-fidelity crisis management through **Eco-Cognitive Gating**.

### 6.1 Theoretical Framework: Active Inference

Drawing on the **Free Energy Principle (FEP)** (Friston, 2010), the v3 engine treats the agent as a "Categorical Predictor" that seeks to minimize informational surprise. Behavioral realism is not hard-coded but emerges from the agent's attempt to reconcile its internal expectations with environmental reality.

### 6.2 Mathematical Formalization

We model the agent's expectation of environmental stress (e.g., flood depth) using an **Exponential Moving Average (EMA)** predictor:

**1. Expected Stress ($\bar{S}_t$):**
$$\bar{S}_t = (1 - \alpha) \bar{S}_{t-1} + \alpha R_t$$
_Where $\alpha$ is the cognitive smoothing factor and $R_t$ is the current environmental reality._

**2. Prediction Error ($\delta_t$):**
$$\delta_t = | R_t - \bar{S}_{t-1} |$$

**3. The Cognitive Gating Function ($\Phi$):**

$$
\text{Memory Mode} = \begin{cases}
\text{Crisis (System 2/Weighted)} & \text{if } \delta_t > \tau \cdot \bar{S}_{t-1} + \epsilon \\
\text{Routine (System 1/Legacy)} & \text{otherwise}
\end{cases}
$$

Here, $\tau$ represents the **Arousal Sensitivity** and $\epsilon$ the **Baseline Arousal Threshold**. When "Surprise" exceeds the threshold, the system "cranks the gain," forcing a switch from low-fidelity window memory (v1) to high-fidelity weighted retrieval (v2). This mechanism aligns with **Arousal-Biased Competition (ABC) Theory** (Mather & Sutherland, 2011), ensuring that deep reasoning is reserved for critical anomalies.

### 6.3 Conclusion: Toward "Deep Agents"

The **Governed Broker Framework** provides the necessary infrastructure to bridge the Fluency-Reality Gap. While **Window Memory (Group B)** and **Human-Centric Memory (Group C)** provide baseline persistence, the **Universal Cognitive Architecture (v3)** offers a neuro-inspired path toward adaptive, explainable, and ecologically rational agents. Valid hydro-social modeling requires not just "Smart Agents," but "Deep Agents" capable of cognitive surprise.

## 7. References

- **Di Baldassarre, G., et al. (2013)**. Socio-hydrology: conceptualising human-flood interactions. _Hydrology and Earth System Sciences_.
- **Friston, K. (2010)**. The free-energy principle: a rough guide to the brain? _Nature Reviews Neuroscience_.
- **Kahneman, D. (2011)**. _Thinking, Fast and Slow_. Farrar, Straus and Giroux.
- **Park, J. S., et al. (2023)**. Generative agents: Interactive simulacra of human behavior. _arXiv:2304.03442_.
- **Simon, H. A. (1955)**. A Behavioral Model of Rational Choice. _The Quarterly Journal of Economics_.
- **Turpin, M., et al. (2023)**. Language Models Don't Always Say What They Think: Unfaithful Explanations in Chain-of-Thought. _arXiv:2305.04388_.
- **Mather, M., & Sutherland, G. C. (2011)**. Arousal-biased competition in perception and memory. _Perspectives on Psychological Science_.
