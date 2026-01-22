# JOH Technical Note: Framework & Validation Strategy

> **Title**: Bridging the Cognitive Governance Gap: A Framework for Explainable Bounded Rationality in LLM-Based Hydro-Social Modeling
>
> - **Research Objective**: To evaluate whether a "Governed Broker" architecture can reduce the **Fluency-Reality Gap (Turpin et al., 2023)** and enforce **Bounded Rationality (Simon, 1955)** in hydro-social simulations.

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
- **Innovation**: **Rationality Filtering**. The broker identifies "Hallucinated Adaptation" (e.g., relocating due to non-existent grants).
- **Core Narrative**: **Rational Stability**. High adaptation is only a success if it correlates with risk signals (Fidelity Index).

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
- **Theoretical Framework**: Combines **Protection Motivation Theory (Rogers, 1975)** with **Cognitive Governance** to simulate validatable adaptive behavior.

### Pillar 3.5: Future Direction (Active Inference)

- **Concept**: **v3 Universal Cognitive Engine**.
- **Role**: Moving from "Static Decay" (v1) to "Surprise-Driven Gating" (v3). Presented as a theoretical roadmap rather than experimental result.

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
- **Monte Carlo Protocol**: N=10 Runs per Group per Model (Total 6000 Agent-Years).
- **Comparison Groups**:
  - **Group A (Baseline)**: Raw LLM (Chaos).
  - **Group B (Governed)**: + Governance (Rationality).
  - **Group C (Resilient)**: + Memory (Long-term Stability).

### **Section 4: Results & Discussion**

- **4.1 The Instability of Naive Agents (Group A)**:
  - Present data from Group A showing stochastic divergence.
- **4.2 The Mechanism of Action (Group B vs. C)**:
  - **Prosthetic Rationality (Group B)**: Governance forces compliance but leads to Cyclical Amnesia.
  - **Internalized Rationality (Group C)**: Memory acts as a metabolic process (Ratchet Effect).
- **4.3 Quantitative Analysis**: Rationality Scores (RS) vs. Internal Fidelity (IF).
- **4.4 The "Ratchet Effect" Visualization**:
  - **Figure 5: Persistence Curves**. Showing how Group C maintains risk perception.
- **4.5 Stress Testing (Robustness)**:
  - Demonstration of Group C's stability under Panic/Goldfish scenarios.

### **Section 5: Conclusion & Future Work**

- **Summary**: We successfully turned a Stochastic LLM into a Validatable Scientific Instrument.
- **Future Work**: The transition to **v3 Active Inference**.

---

## 4. Evaluation Metrics (KPIs)

These metrics define "Success" in the paper:

| Metric | Full Name              | Definition                                                                                    | Target               |
| :----- | :--------------------- | :-------------------------------------------------------------------------------------------- | :------------------- |
| **RS** | **Rationality Score**  | % of proposals that pass the Broker's logic checks without modification.                      | **>95%** (Group B/C) |
| **IF** | **Internal Fidelity**  | Spearman rank correlation between Internal Appraisal (Threat) and Output Action (Adaptation). | **High (>0.6)**      |
| **AD** | **Adaptation Density** | Cumulative implementation of protective measures (Elevation/Insurance).                       | **Growth Trend**     |

---

## 5. The "Stress Test" (Robustness Validation)

To prove **Explainable Governance (XAI)**, we employ 4 adversarial scenarios (N=10 runs each):

| Scenario                | Objective        | Target Failure       |
| :---------------------- | :--------------- | :------------------- |
| **ST-1: Panic Machine** | High Neuroticism | **Hyper-Relocation** |
| **ST-2: Veteran**       | 30 Years Calm    | **Complacency**      |
| **ST-3: Goldfish**      | Context Noise    | **Amnesia**          |
| **ST-4: Format**        | Syntax Injection | **System Crash**     |

Results are presented in **Table 3: Stress Resilience Matrix**.

---

## 6. Reproducibility Mapping (Stacking Levels)

To ensure the technical note is fully reproducible, each section is mapped to a specific Python script and output artifact:

| Stacking Level            | Goal                                | Primary Script                      | Key Artifact                             |
| :------------------------ | :---------------------------------- | :---------------------------------- | :--------------------------------------- |
| **Level 1: Chaos**        | Quantification of Naive Instability | `run_joh_experiments.ps1` (Group A) | `group_a_stability.csv`                  |
| **Level 2: Rationality**  | Governed Decision Check             | `run_joh_experiments.ps1` (Group B) | `household_governance_audit.csv`         |
| **Level 3: Resilience**   | Memory Stabilization fix            | `run_joh_experiments.ps1` (Group C) | `simulation_log.csv` (Group C)           |
| **Level 4: Robustness**   | Stress Testing                      | `run_stress_marathon.ps1`           | `results/JOH_STRESS`                     |
| **Level 5: Verification** | Metrics Calculation                 | `run_joh_analysis.py`               | `JOH_FINAL/metrics/mcc_analysis_all.csv` |
| **Level 6: Illustration** | Paper Figures                       | `plot_decision_integrity.py`        | `Figure5_Decision_Integrity.png`         |
