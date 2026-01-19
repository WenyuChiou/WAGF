# JOH Technical Note: Framework & Validation Strategy

> **Title**: Bridging the Cognitive Governance Gap: A Framework for Explainable Bounded Rationality in LLM-Based Hydro-Social Modeling

This document outlines the core arguments, structure, and validation strategy for the Journal of Hydrology (JOH) Technical Note.

---

## 1. Core Framework Philosophy (The "Why")

Existing LLM-ABMs suffer from a **"Cognitive Governance Gap"**:

1.  **Hallucination**: Agents invent resources or ignore physical constraints.
2.  **Memory Erosion**: "Goldfish Effect" (forgetting past disasters).
3.  **Black Box**: "Why did the agent do that?" is unanswerable.

Our solution is **"Cognitive Middleware"** (The Governed Broker).
It is **NOT** a new ABM; it is a **Governance Layer** that sits _between_ any physical model (e.g., HEC-RAS, TaiCO) and the LLM, enforcing **Bounded Rationality**.

---

## 2. Methodology: The 3+1 Pillars

We define the framework through three cognitive pillars and one extensibility feature:

### Pillar 1: Context-Aware Governance (The "Judge")

- **Mechanism**: `Skill Broker` & `InterventionReport`.
- **Function**: Blocks "Impossible" or "Irrational" moves using PMT Logic rules.
- **Innovation**: **Self-Correction Trace**. Instead of silently failing, it gives the agent a "Rejection Letter" (System 2 Feedback), forcing it to reason correctly (XAI).

### Pillar 2: Episodic Resilience (The "Memory")

- **Mechanism**: `ReflectionEngine` & `HumanCentricMemory`.
- **Function**: Prevents the Goldfish Effect.
- **Innovation**: **Year-End Consolidation & Dual-Layer Logging**. Converts raw daily logs into permanent "Semantic Insights" (e.g., "Flood risk is increasing"). Crucially, these insights are automatically exported to a dedicated `reflection_log` (JSONL), creating an independent audit trail of the agent's _belief evolution_ separate from its operational history.

### Pillar 3: Theoretically-Constrained Perception (The "Lens")

- **Mechanism**: `ContextBuilder` & `PrioritySchema`.
- **Function**: Filters noise.
- **Innovation**: **Schema-Driven Context**. Uses a YAML config to force the LLM to process "Physical Reality" (Flood Depth) _before_ "Social Preference".

### Pillar 4: Combinatorial Intelligence (The "Stacking Blocks")

We present a "Lego-like" architecture where cognitive modules can be stacked to perform ablation studies:

- **Base**: Execution Engine (Body).
- **Level 1**: Context Lens (Eyes) - Solves Context Limit.
- **Level 2**: Memory Engine (Hippocampus) - Solves Availability Bias.
- **Level 3**: Skill Broker (Superego) - Solves Logical Inconsistency.

### (+1) Extensibility: The Coupling Interface

- **Mechanism**: JSON-based Input/Output Decoupling.
- **Function**: Connects to _any_ external world.
- **Argument**: "The framework is model-agnostic Cognitive Middleware, compatible with SWMM/HEC-RAS."

---

## 3. Paper Structure (Proposed Chapters)

### **Section 1: Introduction**

- The Promise: LLMs for Social Simulation.
- The Problem: The "Black Box" & "Goldfish" issues.
- The Solution: Governed Broker as a rationalizing middleware.

### **Section 2: Methodology (The Architecture)**

- Diagram 1: System Overview (Input Signals -> **Middleware** -> Action Output).
- Describe the 3 Pillars (Governance, Memory, Perception).

### **Section 3: Experimental Design**

- **Scenario**: 10-Year Flood Simulation (TaiCO Model).
- **Comparison Groups**:
  - **Group A (Baseline)**: Raw LLM (Chaos).
  - **Group B (Governed)**: + Governance (Rationality).
  - **Group C (Resilient)**: + Memory (Long-term Stability).

### **Section 4: Results & Discussion**

- **4.1 The Instability of Naive Agents (The "Desktop vs Repo" Discovery)**:
  - Present data showing how identical prompts produce divergent behaviors (Adapt vs Do Nothing) based on random seeds when `Memory Window` is small.
  - **Conclusion**: Naive LLM agents are **Stochastically Unstable**.
- **4.2 The Stabilization Effect (Group C)**:
  - Show how Tiered Memory reduces inter-run variance.
- **4.3 Quantitative Analysis**: Rationality Scores & Adaptation Rates.
- **4.4 Qualitative Case Studies**: The Stress Tests (Section 5).
- **4.5 Explainable AI (XAI): Auditing the Cognitive Trace**:
  - Highlights the value of the "Glass Box" approach.
  - Demonstrates how `reflection_log.jsonl` allows researchers to validate the _reasoning_ behind the metrics.
  - **Example**: Distinguishing between an agent who buys insurance because of "Panic" vs. one who buys it due to "Calculated Risk Assessment" using the semantic log trail.

### **Section 5: Conclusion**

- Summary: We successfully turned a Stochastic LLM into a Validatable Scientific Instrument.

---

## 4. Evaluation Metrics (KPIs)

These metrics define "Success" in the paper:

| Metric | Full Name              | Definition                                                              | Target                                       |
| :----- | :--------------------- | :---------------------------------------------------------------------- | :------------------------------------------- |
| **RS** | **Rationality Score**  | % of decisions that pass logic checks without intervention.             | **>95%** (Group B/C)                         |
| **AD** | **Adaptation Density** | Cumulative implementation of protective measures (Elevation/Insurance). | **Growth Trend** (Group C shouldn't plateau) |
| **PC** | **Panic Coefficient**  | Ratio of "Relocation" vs "Do Nothing" under low threat.                 | **Low** (Group B should stop panic)          |
| **FI** | **Fidelity Index**     | Semantic alignment between Context (Risk High) and Action (Elevate).    | **High**                                     |

---

## 5. The "Stress Test" (Qualitative Case Study)

To prove **Explainable Governance (XAI)**, we will include a specific **Micro-Case Study Box** in Section 4.2.

**Goal**: Demonstrate that the model doesn't just "guess right", but is "reasoned into compliance."

**Case 1: "The Impulsive Relocator" (Governance XAI)**

- **Scenario**: Agent wants to relocate despite low threat/funds.
- **Outcome**: Governance intercedes (Budget < Cost), forcing a rational downgrade to "Insurance".

**Case 2: "The Trauma Recall" (Memory XAI)**

- **Scenario**: Year 9 (Sunny). Agent considers dropping insurance.
- **System Push**: "Recall: Year 2 Flood (Depth 1.5m, Trauma High)".
- **Outcome**: Agent cites the past trauma: _"Despite the nice weather, I remember the devastation of Year 2. I will keep insurance."_
- **Significance**: Proves the "Goldfish Effect" is eliminated by Tiered Memory.

---

## 6. Reproducibility Mapping (Stacking Levels)

To ensure the technical note is fully reproducible, each section is mapped to a specific Python script and output artifact:

| Stacking Level            | Goal                                | Primary Script                                                                                                                                                                              | Key Artifact                                                                                                                                                                                        |
| :------------------------ | :---------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Level 1: Chaos**        | Quantification of Naive Instability | [analyze_group_a_instability.py](file:///H:/%E6%88%91%E7%9A%84%E9%9B%B2%E7%AB%AF%E7%A1%AC%E7%A2%9F/github/governed_broker_framework/examples/single_agent/analyze_group_a_instability.py)   | `group_a_stability.csv`                                                                                                                                                                             |
| **Level 2: Rationality**  | Governed Decision Check             | `run_baseline_original.py`                                                                                                                                                                  | `household_governance_audit.csv`                                                                                                                                                                    |
| **Level 3: Resilience**   | Memory Stabilization fix            | [run_tiered_memory.py](file:///H:/%E6%88%91%E7%9A%84%E9%9B%B2%E7%AB%AF%E7%A1%AC%E7%A2%9F/github/governed_broker_framework/examples/single_agent/run_tiered_memory.py)                       | `simulation_log.csv` (Group C)                                                                                                                                                                      |
| **Level 4: Verification** | Inter-run variance & Metrics        | [analyze_all_groups_stability.py](file:///H:/%E6%88%91%E7%9A%84%E9%9B%B2%E7%AB%AF%E7%A1%AC%E7%A2%9F/github/governed_broker_framework/examples/single_agent/analyze_all_groups_stability.py) | [Figure 2](file:///H:/%E6%88%91%E7%9A%84%E9%9B%B2%E7%AB%AF%E7%A1%AC%E7%A2%9F/github/governed_broker_framework/examples/single_agent/results/JOH_FINAL/gemma3_4b/Figure2_Stochastic_Instability.png) |
| **Level 5: Illustration** | Behavioral Sawtooth Curve           | [extract_sawtooth_data.py](file:///H:/%E6%88%91%E7%9A%84%E9%9B%B2%E7%AB%AF%E7%A1%AC%E7%A2%9F/github/governed_broker_framework/examples/single_agent/extract_sawtooth_data.py)               | [Figure 3](file:///H:/%E6%88%91%E7%9A%84%E9%9B%B2%E7%AB%AF%E7%A1%AC%E7%A2%9F/github/governed_broker_framework/examples/single_agent/results/JOH_FINAL/gemma3_4b/Figure3_Sawtooth_Curve.png)         |
