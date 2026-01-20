# JOH Technical Note: Bridging the Cognitive Governance Gap

**Title**: Bridging the Cognitive Governance Gap: A Framework for Explainable Bounded Rationality in LLM-Based Hydro-Social Modeling

**Abstract**
Agent-Based Models (ABMs) are increasingly using Large Language Models (LLMs) to simulate how humans make decisions during disasters. However, these "Generative Agents" often suffer from a critical flaw: they are improved storytellers but poor actors. We call this the **"Fluency-Reality Gap."** Agents may write convincing arguments for actions that are logically inconsistent with their own internal appraisals (e.g., relocating despite perceived low risk). This Technical Note introduces the **Governed Broker Framework**, a system that forces these agents to "check their math" before acting.

In a **Pilot Study** comparing Naive (Group A) vs Governed (Group B) agents in a 10-year flood simulation, we found a stark divergence:

- **Group A (Naive)**: exhibited a **Panic Rate of <1%** and **Adaptation Rate of ~0%**, confirming a "Goldfish Effect" where agents normalize risk instantly.
- **Group B (Governed)**: exhibited a **Panic Rate of ~25%**, demonstrating that static constraints can force reactivity, but potentially at the cost of artificial "Sawtooth" behavior.

This validation demonstrates that while Governance restricts hallucinate irrationality, true behavioral realism requires a **Universal Cognitive Architecture (v3)** to internalize the "Crisis Mode" dynamically.

**Keywords**: Socio-hydrology, Large Language Models, Agent-Based Modeling, Cognitive Governance, Explainable AI.

## 1. Introduction: The Calibration Crisis in Generative ABM

Integrating realistic human behavior into physical models (Socio-Hydrology) is essential for accurate disaster risk assessment (Di Baldassarre et al., 2013). Traditional Agent-Based Models (ABMs) often rely on rigid, hard-coded rules that struggle to capture the complex, boundedly rational nature of human decision-making under stress. The emergence of Large Language Models (LLMs) offers a transformative path: **"Generative Agents"** (Park et al., 2023) capable of reasoning, reflection, and natural language communication.

However, the use of LLMs in scientific simulations introduces a new "Calibration Crisis." While LLMs are exceptionally fluent, their reasoning often lacks grounding in physical reality—a phenomenon we term the **"Fluency-Reality Gap."** Recent research suggests that LLMs frequently produce **Unfaithful Explanations** (Turpin et al., 2023), where the stated reasoning (System 1) does not causally align with the final action. In socio-hydrological contexts, this manifests as agents who can poetically describe flood trauma but fail to take protective actions (Apathy), or conversely, agents who "hallucinate" resources to justify irrational panic.

Valid scientific modeling requires the enforcement of **Bounded Rationality** (Simon, 1955). Pure LLM agents act as unconstrained "System 1" probabilistic engines, vulnerable to stochastic volatility and temporal incoherence (the "Goldfish Effect"). To transform these agents into reliable scientific instruments, we argue for a move toward **Cognitive Governance**. This requires an architecture that decouples "Reasoning" from "Execution," forcing agents to align their actions with internal logic and physical constraints.

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

![Framework Architecture](file:///C:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/docs/architecture.png)

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

- **Group A (Baseline)**: Ungoverned "System 1" agents using standard LLM prompting. Represents the "Naive" approach.
- **Group B (Governed - Window)**: Governed agents using standard sliding-window memory. Represents the "Prosthetic System 2" with **Rigid Constraints**.
- **Group C (Governed - Human-Centric)**: Governed agents using **Human-Centric Memory** (Episodic-Semantic Consolidation). Represents the "State-Dependent" approach.

### 3.2 Metrics

We tracked:

1.  **Adaptation Rate**: Percentage of population relocating.
2.  **Panic Rate**: Frequency of `High` Threat Appraisal decisions in non-flood years.
3.  **Internal Fidelity (IF)**: Correlation between Threat Appraisal and Action.

## 4. Results: The "Apathy vs Reactivity" Dilemma

We evaluated the framework using a "Difference-in-Differences" approach.

### 4.1 Group A: The "Frozen" Agent (Apathy)

We found that Naive LLMs (Group A) exhibit a profound **Inaction Bias**.

- **Panic Rate**: **0.8%** (Extremely low reactivity).
- **Adaptation Rate**: **~0%** (Even after 3 catastrophic floods).
- **Behavioral Phenotype**: Agents would write text acknowledging the flood ("This is terrible!") but select `Do Nothing` actions in the simulation. This confirms the **Fluency-Reality Gap**.

### 4.2 Group B: The "Sawtooth" Effect (Artificial Reactivity)

The introduction of basic Governance (Group B) successfully "woke up" the agents, but introduced a new artifact.

- **Panic Rate**: **~25%** (High reactivity).
- **Pattern**: Agents exhibited a **"Sawtooth"** pattern: High Panic immediately after a flood, followed by a sharp drop when external rule constraints relaxed.
- **Mechanism**: The Governance acts as an external "Prosthetic," forcing action without changing internal belief.

### 4.3 Group C: The "Ratchet" Effect (True Persistence)

Group C (Human Centric) demonstrated the superior stability of **Internalized Governance**.

- **Persistence**: Unlike Group B's rapid decay, Group C agents maintained high risk perception for >3 years after a flood (**The Ratchet Effect**).
- **Fidelity**: High Internal Fidelity (IF > 0.8), indicating actions were driven by consolidated "Trauma Anchors" rather than just external rules.

## 5. Discussion: Why Human-Centric Memory Matters

### 5.1 Rules vs. Memory

Group A proves that Naive LLMs are apathetic. Group B proves that Static Rules can force action but create "Sawtooth" instability.
**Group C (Human Centric)** bridges this gap by using memory to create _durable_ behavioral change.

### 5.2 Conclusion

The **Governed Broker Framework** successfully bridges the calibration gap.

- **Window Memory (Group B)** provides a "Safety Net" against hallucination.
- **Human-Centric Memory (Group C)** provides "Psychological Realism" (Trauma Persistence).

This confirms that valid socio-hydrological modeling requires not just "Smart Agents" (LLMs), but **"Deep Agents"** with architecturally enforced memory structures.

## 7. References

- **Di Baldassarre, G., et al. (2013)**. _Socio-hydrology: conceptualising human-flood interactions_.
- **Park, J. S., et al. (2023)**. _Generative agents: Interactive simulacra of human behavior_.
- **Turpin, M., et al. (2023)**. _Language Models Don't Always Say What They Think_.
- **Simon, H. A. (1955)**. _A Behavioral Model of Rational Choice_.
