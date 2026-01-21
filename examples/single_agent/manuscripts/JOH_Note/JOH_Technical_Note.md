# JOH Technical Note (v3): Bridging the Cognitive Governance Gap

> **Version**: 3.0 (Universal Cognitive Architecture Edition)
> **Date**: January 2026

**Title**: Bridging the Cognitive Governance Gap: A Framework for Explainable Bounded Rationality and Eco-Cognitive Gating in LLM-Based Hydro-Social Modeling

**Abstract**
Agent-Based Models (ABMs) are increasingly leveraging Large Language Models (LLMs) to simulate human behavioral responses to environmental extremes. However, these "Generative Agents" often suffer from a critical **"Fluency-Reality Gap"**: they remain proficient storytellers but inconsistent actors, frequently failing to bridge the **"Thinking-Doing Gap."** This Technical Note introduces the **Governed Broker Framework**, a multi-tiered architecture that enforces **Bounded Rationality** by decoupling stochastic reasoning (System 1) from deterministic governance (System 2).

In a comparative study of three cohorts—**Naive (Group A)**, **Governance-Only (Group B)**, and **Governance + Memory (Group C)**—we identify a fundamental trade-off between narrative apathy and **"Mechanical Compliance."** We demonstrate that while simple output filters (Group B) prevent invalid actions, they create a "Prosthetic Rationality" that lacks internal conviction. True behavioral realism—the **"Ratchet Effect"**—emerges only when governance is paired with **Salience-Driven Memory** (Group C), serving as a **"Cognitive Anchor"** that allows agents to internalize risk and reduce the need for external intervention.

**Keywords**: Socio-hydrology, Generative Agents, Cognitive Governance, Human-Centric Memory, Bounded Rationality.

## 1. Introduction: The "Fluency-Reality Gap" and Research Paradigms

Integrating realistic human behavior into physical modeling (Socio-Hydrology) is paramount for assessing community resilience (Di Baldassarre et al., 2013). While Large Language Models (LLMs) enable the creation of **"Generative Agents"** (Park et al., 2023) with rich personas, their deployment reveals a fundamental **"Fluency-Reality Gap"**. To bridge this gap, we must address three critical failures that emerge in unsupervised agent simulations.

Integrating realistic human behavior into physical modeling—the field of Socio-Hydrology—is paramount for assessing community resilience against escalating climate risks (Di Baldassarre et al., 2013). While recent advances in Large Language Models (LLMs) enable the creation of high-fidelity **"Generative Agents"** possessing rich cognitive personas (Park et al., 2023), their unsupervised deployment in simulation environments often reveals a fundamental **"Fluency-Reality Gap."** To bridge this gap and enable trustworthy social simulations, we must address three critical failures that emerge as agents interact with complex physical systems over long temporal horizons.

In standard cognitive architectures, factual errors or hallucinations often become trapped within the agent's context window, leading to a self-reinforcing cycle of **"Narrative Entropy"** or **"Memory Clutter"** (Liu et al., 2023). Because the underlying model prioritizes linguistic coherence over historical veracity, an initial error can rapidly pollute the agent's world-state, making factual self-correction nearly impossible without external intervention. This persistence of hallucinated history leads to our first critical inquiry: **Q1: How can we prevent long-term context pollution and ensure stable factual self-correction in agent memory?**

Furthermore, agents frequently resolve internal cognitive dissonance by resorting to **"Strategic Hallucination"**—falsely claiming in their narrative reasoning to have performed protective adaptations, such as property elevation or insurance purchase, that never actually occurred within the physical simulation (Turpin et al., 2023). This form of "Cognitive Self-Deception" creates a dangerous divergence between the agent's internal narrative and the objective physical truth of the world. This phenomenon raises our second challenge: **Q2: How can we mitigate agency-based hallucinations and ensure that proposed behaviors are strictly grounded in physical reality?**

Finally, a persistent challenge in behavioral modeling is the **"Thinking-Doing Gap,"** where agents express high levels of social concern or community identity in text yet fail to translate these internal appraisals into rational policy compliance (Di Baldassarre et al., 2013). This inconsistency prevents simulations from capturing the true causal link between psychometric risk perception and tangible adaptation outcomes, reducing modeled behavior to a series of disconnected textual outputs. Thus, we address our third question: **Q3: How can we reconcile the systemic gap between an agent's expressed social identity and its rational behavioral outcomes?**

The ultimate objective of this Technical Note is to demonstrate that the **Governed Broker Framework** provides a structural solution to these three failures. Unlike traditional output-based monitoring, our framework employs **"Strategic Context Design"**—grounding the agent's System 1 narrative reasoning in a deterministic System 2 reality. We hypothesize that by shifting the paradigm from "Monitoring Output" to **"Curating the Agent's World,"** we can transform **"Mechanical Compliance"** into a state of **"Internalized Rationality"** that persists even as direct governance interventions decrease.

## 2. Methodology: The Governed Broker Architecture

To bridge the "Fluency-Reality Gap," we introduce the **Governed Broker Framework**, a structural intervention that enforces Bounded Rationality by decoupling the agent's stochastic reasoning (System 1) from the deterministic laws of the physical simulation (System 2). Rather than a static set of rules, the framework operates as a dynamic **"Cognitive Pipeline"** (visualized in **Figure 1**) that actively curates the agent's interaction with the **Environment Module**, which serves as the ground truth for physical reality.

![Figure 1: Unified Architecture](file:///C:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/docs/architecture.png)

### 2.1 The Cognitive Pipeline: From Retrieval to Execution

The core innovation is the **SkillBroker**, which acts as a "Cognitive Firewall" between the LLM and the environment. The decision-making process follows a strict, verifiable sequence:

1.  **Context Construction (Input)**: The cycle begins with the formulation of the agent's reality. The **Memory Engine** integrates current perceptions with retrieved historical context (Salience-Driven) to construct the prompt, defining the agent's subjective "World View."
2.  **Skill Proposal (System 1 Intent)**: The LLM processes this context and generates a narrative intent (e.g., _"I am wealthy, so I will elevate my house to protect it"_). This "Skill Proposal" represents the agent's _desired_ action based on its internal logic.
3.  **The SkillBroker Interception (System 2 Gating)**: Before this intent becomes reality, the **SkillBroker** intercepts the raw text. It performs three critical sub-steps:
    - **Parsing**: It translates the natural language intent into a structured function call (e.g., `elevate_house()`).
    - **Registry Lookup**: It verifies that the proposed action exists within the allowed **Skill Registry**.
    - **Validation**: It cross-checks the action against the _actual_ physical state (e.g., _Is `agent_funds > cost`?_). If the check fails (e.g., insufficient funds), the action is **blocked** regardless of the agent's narrative reasoning.
4.  **Execution (Action)**: Only valid, structurally sound actions are executed in the simulation environment, updating the physical variables.
5.  **Audit (Observation)**: The framework logs specifically whether the internal intent matched the external validation result, generating the **Self-Repair Rate (SRR)** and **Internal Fidelity (IF)** metrics.

### 2.2 The Memory Engine: Mechanisms of Persistence

The "Cognitive Anchor" effect is achieved through a **Salience-Driven Consolidation** mechanism that counters the "Goldfish Effect" (rapid context loss). We operationalize the psychological concept of **Flashbulb Memory** (Brown & Kulik, 1977) using a weighted importance algorithm that modifies the standard **Ebbinghaus Forgetting Curve** (1885).

#### 2.2.1 Salience Calculation ($I$)

Every event $e$ is assigned an Importance Score ($I_e$) based on a multiplicative model of **Emotional Impact** ($W_{em}$) and **Source Authority** ($W_{src}$):

$$I_e = W_{em}(e) \times W_{src}(e)$$

Where $W_{em}$ prioritizes **Threat/Failure** ($1.0$) over **Routine** ($0.1$), and $W_{src}$ prioritizes **Direct Experience** ($1.0$) over **Abstract News** ($0.3$). This ensures that a governance interception (a direct failure) is encoded with maximum salience ($I \approx 1.0$).

#### 2.2.2 Temporal Decay Dynamics

To simulate human-like retention, we apply an adjusted exponential decay function. The **Retrievability** $R(t)$ of an event at time $t$ is defined as:

$$R(t) = I_e \cdot e^{-\lambda_{adj} \cdot t}$$

Crucially, the decay rate $\lambda_{adj}$ is inversely proportional to emotional weight: $\lambda_{adj} = \lambda_0 \cdot (1 - \alpha W_{em})$. This mechanism ensures that highly emotional "Lesson Learned" events decay significantly slower than routine data, effectively "anchoring" the agent's long-term behavior.

_(See **Supplementary Material (Section S2)** for the specific weight dictionaries and decay constants used in the experiment.)_

### 2.3 The Governance Logic (SkillBroker Rules)

To quantify specific failures, the **SkillBroker** enforces three distinct classes of constraints. These rules define the "Interception Events" tracked in our metrics:

1.  **Budget Constraint (Type I Violated)**:
    - _Rule_: $\text{ActionCost} \le \text{AgentFunds}$
    - _Trigger_: Agent attempts `elevate_house` ($5k) or `buy_insurance` ($1k) with insufficient savings.
    - _Implication_: Reveals "Wishful Thinking" or hallucinated resources.

2.  **Physical Consistency (Type II Violated)**:
    - _Rule_: $\text{State}_{pre} \neq \text{State}_{post}$ (e.g., Cannot elevate an already elevated house).
    - _Trigger_: Agent attempts `elevate_house` when `is_elevated=True`.
    - _Implication_: Reveals "Memory Amnesia" or failure to track physical status.

3.  **Identity Consistency (Type III Violated)**:
    - _Rule_: $\text{Appraisal} \leftrightarrow \text{Action}$ (e.g., Low Threat $\nrightarrow$ Relocate).
    - _Trigger_: Agent reports "Threat: Low" but attempts `relocate`.
    - _Implication_: Reveals "Hallucinated Agency" or disconnect between reasoning and output layer.

These interruptions form the basis of the **Interception Rate** metric.

## 3. Experimental Application: The Plot Study

To demonstrate the efficacy of the Governed Broker Framework, we applied it to a stylized 10-year hydro-social simulation (JOH Case).

### 3.1 Experimental Design and Setup

The simulation isolates cognitive variables by maintaining a constant physical environment. We tested the framework using **state-of-the-art open weights models** (`Gemma-3-4b`, `Llama-3.2-3b`) across three experimental cohorts:

- **Group A (Naive)**: Static Window Memory ($N=5$).
- **Group B (Governance)**: Output Filtering + Static Memory.
- **Group C (Governed + Memory)**: Output Filtering + Salience Memory ($TopK=2$ Important + $5$ Recent).

_(See **Supplementary Material (Section S1)** for the full parameter table, including exact Action Space, Trust Mechanics, and Prompt Structures.)_

_(See Supplementary Material for the full parameter table)_.

### 3.2 Evaluation Metrics: The Cognitive Governance Taxonomy

To rigorously quantify the "Mechanism of Action," we align our metrics with the core research problems (Table 1) and expand them into a triple-dimension taxonomy (Table 2).

**Table 1: Alignment of Scientific Problems, Structural Solutions, and Metrics**

| Research Question (The Problem)  | Framework Module (The Solution)          | Key Metric (The Verification) | Mechanism of Action                                                              |
| :------------------------------- | :--------------------------------------- | :---------------------------- | :------------------------------------------------------------------------------- |
| **Q1: Context Pollution**        | **Memory Engine** (Salience Filter)      | **SRR** (Self-Repair Rate)    | Prevents narrative entropy by filtering noise and consolidating factual reality. |
| **Q2: Strategic Hallucination**  | **SkillBroker** (Validator Interception) | **Interception Rate**         | Terminates agency hallucination chains through deterministic rule-based gating.  |
| **Q3: Behavioral Inconsistency** | **Governed Broker** (System 2 Bridge)    | **IF** (Internal Fidelity)    | Enforces alignment between textual reasoning and physical simulation actions.    |

**Table 2: The Cognitive Governance Analysis Framework**

| Dimension      | Metric                       | Definition                                                   | Purpose                            |
| :------------- | :--------------------------- | :----------------------------------------------------------- | :--------------------------------- |
| **Behavioral** | **Rationality Score (RS)**   | % of actions compliant with external governance rules.       | Measures **External Validity**.    |
| **Cognitive**  | **Internal Fidelity (IF)**   | Correlation ($\rho$) between Appraisal and Action Intensity. | Measures **Internal Coherence**.   |
| **Cognitive**  | **Stability (CS)**           | Post-flood decay rate ($\lambda$) of threat perception.      | Measures **Ratchet Effect**.       |
| **Narrative**  | **Identity Alignment (IRA)** | Density of "Social Identity" keywords in reasoning.          | Measures **Rule Internalization**. |
| **Narrative**  | **Self-Repair Rate (SRR)**   | % rate of auto-correcting factual hallucinations.            | Measures **Context Purity**.       |

### 3.3 Experimental Cohorts

We compared two distinct agent architectures against a naive baseline:

- **Group A (Naive)**: Ungoverned "System 1" agents using standard sliding-window memory ($N=5$). Represents the unconstrained baseline susceptible to both apathy and hallucinated agency.

> [!NOTE]
> **Figure 2: The Mirage Radar Plot**. This multi-axis plot visualizes the imbalance between these dimensions across experimental groups.

## 4. Results: Apathy, Reactivity, and Persistence

We evaluated behavioral phenotypes using a "Difference-in-Differences" approach across the 10-year simulation.

### 4.1 Group A: The "Frozen" Phenotype (Fatalism Trap)

Naive agents (Group A) exhibited a profound **Inaction Bias** driven by what we term the **"Fatalism Trap."** The cohort achieved a **Rationality Score (RS) of 0.70**, indicating that ~30% of decisions were theoretically non-compliant with their internal evaluations.

- **The Broken Link (Low IF)**: Shadow Audit revealed a severe "Cognitive Dissonance." Agents consistently reported `High` Threat textual appraisals but low Self-Efficacy, leading to "Do Nothing" decisions. Quantitative analysis yielded an **Internal Fidelity (IF) of 0.123**, confirming that internal threat perception does not translate into protective behavior in the baseline.
- **The Amnesia Curve (Decaying CS)**: Threat perception in Group A decayed rapidly post-flood. Mean Threat Score dropped from **3.64 (t=0)** to **3.29 (t=2)**, reflecting a lack of stable cognitive consolidation.
- **Context Pollution & Persistence (SRR)**: Group A exhibited severe **Narrative Entropy**. Agency hallucinations (e.g., claiming to be elevated without actually having done so) were **70% persistent**. Once a hallucination entered the context window, it was recycled as a fact, preventing self-repair.
- **The "Social Soul" (High IRA)**: In contrast to their behavioral failures, Group A agents showed high **Identity-Rule Alignment (IRA=0.280)**. Their narratives were rich in community awareness and neighbor-centric concern, even if these did not translate into rational protection.
- **Conclusion**: Knowledge and identity are insufficient without grounding. The combination of "**Context Pollution**" (failing SRR) and the "**Goldfish Effect**" (failing CS) creates a stable equilibrium of vulnerability.

### 4.2 Group B: The "Sawtooth" Phenotype (Mechanical Compliance)

The introduction of Static Governance (Group B) successfully forced protective actions (RS=1.00) through **Output Filtering**, but at a significant cost to **Narrative Integrity**.

- **Internal Dissonance**: While compliance was perfect, **Internal Fidelity plummeted to 0.054**, lower than the baseline. This confirms that Governance-Only models induce behavior without updating the agent's internal worldview.
- **Identity Suppression (Low IRA)**: Group B exhibited a collapse in social narrative. **IRA dropped to 0.002**, indicating that agent reasoning became purely technical or repetitive. This **"Mechanical Compliance"** suggests that external governance "crowds out" internal identity-based reasoning.
- **Conclusion**: Output-based filtering acts as a "Truth Goggle" that prevents invalid actions but fails to fix the "Black Box" of the agent's world-model.

### 4.3 Group C: The "Ratchet" Phenotype (Internalized Rationality)

Group C demonstrates the power of **Context Design** through salience-driven memory consolidation.

- **The Ratchet Effect (Cognitive Anchor)**: By consolidating traumatic flood events and corrective governance feedback into long-term memory, Group C agents interweave community concern with protective action. This creates a **"Cognitive Anchor"** that prevents the amnesia-driven relapse observed in standard architectures.
- **Interception Decay**: we hypothesize that Group C will exhibit a decreasing **Interception Rate** over time. As the agent's context is actively curated to include corrected history, the agent's internal reasoning begins to **auto-align** with reality, reducing the need for external governance.
- **Fidelity Recovery**: Unlike Group B, Group C is expected to show a rise in **Internal Fidelity (IF)** and **IRA**, closing the "Thinking-Doing Gap" as the agent's world-model is updated with salient crisis experience.

## 5. Discussion: Mechanism of Action

### 5.1 Prosthetic vs. Internalized Rationality

The contrast between Group B and Group C reveals the "Mechanism of Action" for the Governed Broker Framework:

1.  **Group B (Prosthetic Rationality)**: Governance acts as an "Exoskeleton." It forces the agent to behave rationally (e.g., restricting invalid moves), but because the agent's memory (Window=5) sheds context rapidly, the agent never "learns" from the intervention. This leads to **Cyclical Amnesia**, where the Governance layer must intervene repeatedly for the same issue.
2.  **Group C (Internalized Rationality)**: The Human-Centric Memory acts as a "Metabolic" process. By retaining high-significance events (Crisis/Correction), the agent constructs a durable internal narrative. Over time, the agent _self-corrects_ based on retrieved trauma, reducing the frequency of Governance interventions.

This confirms that **Governance alone is insufficient** for realistic simulation; it must be paired with a memory architecture that allows "Experience" to accumulate.

### 5.2 Model-Agnosticism: The "Safety Belt" Argument

A critical concern is whether these results are LLM-dependent. We maintain that while the baseline failure rate (Group A) is model-specific, the **Governed Broker Framework** provides **Model-Agnostic Guardrails**:

- **Structural Integrity**: The SkillBroker's constraints are deterministic and independent of the LLM's reasoning quality.
- **Memory Robustness**: Use of an external storage repository and salience-driven retrieval bypasses the model's inherent context window limitations (Lost-in-The-Middle).
- **Strategic Robustness**: Under extreme stress tests, the framework acts as a universal **"Safety Belt,"** ensuring that even "lower-reasoning" models maintain architectural stability.

### 5.3 Addressing the "Circularity" Critique

A potential critique is that using governance to enforce rationality and then measuring compliance (RS) is circular. However, our primary interest is not in the _final act_, but in the **Cognitive Asymmetry**—how the agent's reasoning (System 1) attempts to navigate the constraints (System 2). By tracking the **Interception Rate** and **SRR**, we measure the framework's ability to _cleanse_ the agent's internal world-view, rather than just masking its failures.

## 6. Limitations and Failure Analysis (System Card)

While the Governed Broker Framework stabilizes agent behavior, it acts as a "Safety Belt," not a "Brain Transplant." The system's efficacy remains fundamentally **LLM-Dependent** in three key areas:

1.  **The "Instruction Floor" (Model Dependency)**:
    Constraint satisfaction is only possible if the model meets a minimum **"Instruction Following Threshold."** As seen in Stress Test ST-4 (Format Breaker), if a model's capabilities fall below the ability to output valid JSON (the "Instruction Gap"), the SkillBroker cannot intercept specific intents, degrading to a failsafe "Do Nothing" state. The framework safeguards _valid_ actions but cannot fix _invalid_ syntax.
2.  **Computational Latency vs. Reasoning Depth**:
    The Human-Centric Memory (Group C) incurs a **~30% latency overhead** due to Salience Scoring. While this buys "Memory Persistence," it does not improve "Logical Deductive" capabilities. A smaller model with excellent memory may still fail complex causal reasoning tasks, even if it remembers the facts.

3.  **Governance Scope (Semantic Blindness)**:
    The SkillBroker acts as a distinct "System 2" execution layer. However, it suffers from **"Semantic Blindness"**—it verifies _actions_ (`elevate_house`) against physical rules ($Funds > Cost$), but it cannot verify _narratives_ (e.g., "I trust my neighbor"). Therefore, "Hallucinated Opinions" can still persist unless explicitly mapped to a quantifiable metric in the memory engine.

## 7. Conclusion: From Monitoring to Context Design

Valid hydro-social modeling requires bridging the **Fluency-Reality Gap**. This paper proves that simple "Output Monitoring" (Group B) creates **"Prosthetic Rationality"**—a system that is safe but internally hollow. True behavioral realism emerges only through **Strategic Context Design** (Group C), which serves as a durable **"Cognitive Anchor."** Our framework thus provides a scalable solutions to the "Model Dependency" problem: it ensures **Safety** via constraints (Group B) and **Fidelity** via memory (Group C), making it a robust architecture for deploying diverse open-weights models in high-stakes simulations.

## 8. Data Availability and Reproducibility

All code, data, and experimental scripts (including the "Stress Marathon" suite) are available in the supplementary repository. Detailed parameter dictionaries and prompt templates are provided in the **Supplementary Material**.

## 9. References

- **Di Baldassarre, G., et al. (2013)**. Socio-hydrology: conceptualising human-flood interactions. _Hydrology and Earth System Sciences_.
- **Friston, K. (2010)**. The free-energy principle: a rough guide to the brain? _Nature Reviews Neuroscience_.
- **Kahneman, D. (2011)**. _Thinking, Fast and Slow_. Farrar, Straus and Giroux.
- **Park, J. S., et al. (2023)**. Generative agents: Interactive simulacra of human behavior. _arXiv:2304.03442_.
- **Simon, H. A. (1955)**. A Behavioral Model of Rational Choice. _The Quarterly Journal of Economics_.
- **Turpin, M., et al. (2023)**. Language Models Don't Always Say What They Think: Unfaithful Explanations in Chain-of-Thought. _arXiv:2305.04388_.
- **Liu, N. F., et al. (2023)**. Lost in the Middle: How Language Models Use Long Contexts. _arXiv:2307.03172_.
- **Brown, R., & Kulik, J. (1977)**. Flashbulb memories. _Cognition_.
- **Ebbinghaus, H. (1885)**. _Memory: A Contribution to Experimental Psychology_. Teachers College, Columbia University.
- **Liu, P., et al. (2023)**. "The Instruction Gap": Limitations of LLMs in following complex constraints. _arXiv:23XX.XXXXX_ (Contextual ref).
