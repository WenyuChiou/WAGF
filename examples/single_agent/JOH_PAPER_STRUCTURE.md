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
- **Innovation**: **Year-End Consolidation**. Converts raw daily logs into permanent "Semantic Insights" (e.g., "Flood risk is increasing"), ensuring long-term adaptation.

### Pillar 3: Theoretically-Constrained Perception (The "Lens")

- **Mechanism**: `ContextBuilder` & `PrioritySchema`.
- **Function**: Filters noise.
- **Innovation**: **Schema-Driven Context**. Uses a YAML config to force the LLM to process "Physical Reality" (Flood Depth) _before_ "Social Preference".

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

- **4.1 Quantitative (Macro)**: Rationality Scores & Adaptation Rates.
- **4.2 Qualitative (Micro)**: **The Stress Test Case Study**.

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

**The Scenario: "The Impulsive Relocator"**

- **Agent Setup**: Low Income, Moderate Flood Damage.
- **Agent Impulse (System 1)**: "I am scared! I will RELOCATE!" (Classic Hallucination).
- **Governance Intervention**:
  > _BLOCK: "Budget Insufficient ($500 < $50,000). Threat Level is only Moderate. Relocation is disproportionate."_
- **Agent Correction (System 2)**:
  > _"I understand. I cannot afford relocation. Given the moderate threat, I will apply for a government subsidy and buy insurance instead."_

**Why this matters**: This trace **is** the result. It proves the middleware actively **teaches** the agent to follow domain rules.
