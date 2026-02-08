# JOH Technical Note: Architectural Blueprint & Argumentation Logic

**Target Journal**: Journal of Hydrology / Environmental Modelling & Software
**Article Type**: Technical Note (Focus on Methodological novelty & Initial Validation)
**Core Narrative**: "Enhanced Cognitive Architecture" - Moving from _Generative_ to _Governed_ Agents.

---

## 1. The Reviewer's Lens (Anticipated Critiques & Defense)

| Critique Type     | The "Trap"                                   | Our Defense Strategy (The "Enhanced" Answer)                                                                                                                                                   |
| :---------------- | :------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **"Novelty?"**    | "Just another LLM prompt engineering paper." | **No.** We introduce a **Tiered World Model** and **Cognitive Middleware** (System 2 governance) that operates _outside_ the LLM context windown. Cite **CoALA** to show architectural rigor.  |
| **"Validity?"**   | "LLMs hallucinate. How can this be science?" | **Agreed.** That is precisely the gap we fill. We use **PMT constraints** to force bounded rationality. We define a "Rationality Score" (RS) to quantify this improvement.                     |
| **"Complexity?"** | "Why not just use rules? Why LLMs?"          | **Heterogeneity.** Rules are rigid. LLMs provide linguistic diversity and nuanced social interpretation (Pillar 3). We use LLMs for _System 1_ (Perception) and Code for _System 2_ (Physics). |

---

## 2. Section-by-Section Blueprint

### **I. Introduction (The Hook)**

- **The Hook**: Hydro-social modeling needs human-like agents, but current "Generative Agents" are dangerous "Goldfish" (cite **Park et al., 2023**).
- **The Gap**: Existing tools (e.g., AQUAH) automate the _model_, but not the _behavior_. They lack **Cognitive Governance**.
- **Our Solution**: The **Water Agent Governance Framework**. An "Enhanced" architecture that injects **PMT** (cite **Rogers**) constraints into the LLM's decision loop.

### **II. Methodology: The Framework (The Meat)**

- **2.1 Cognitive Middleware**: Explain the "Broker" as a translator.
  - _Input_: JSON Environment Signals (Global, Local, Social).
  - _Output_: Strict Action Schema.
- **2.2 Tiered World Modeling (Highlight)**:
  - Define the 4 Layers: Global (Sea Level), Local (Tract), Institutional (Grant), Social (Network).
  - _Why this matters_: It allows for "Single Source of Truth" governance.
- **2.3 The Three Pillars**:
  - **Pillar 1 (Gov)**: Budget/Physics checks (System 2).
  - **Pillar 2 (Memory)**: Episodic-Semantic reflection (fighting decay).
  - **Pillar 3 (Perception)**: PMT-based salience (Risk > Status).

### **III. Experimental Design (The Proof)**

- **The Baseline (Group A)**: Ungoverned LLM (Llama 3.2). Expect chaos/hallucination.
- **The Enhanced (Group C)**: Governed + Memory. Expect structured adaptation.
- **The Stress Tests**:
  - "Panic Machine" (Input Overload).
  - "Goldfish" (Long-term consistency).

### **IV. Results (The Evidence)**

- **Metric 1: Rationality Score (RS)**. (Quantifies "Validity").
- **Metric 2: Adaptation Density (AD)**. (Quantifies "Dynamics").
- **Metric 3: Fidelity Index (FI)**. (Quantifies "Explainability").

### **V. Discussion (The Synthesis)**

- **Explainability as Governance**: The "Reject-Retry" loop is not just error handling; it is a _cognitive trace_ of bounded rationality.
- **Generalization**: This isn't just for floods. It's for any ABM where agents face resource constraints.

---

## 3. Key stylistic rules

1.  **Avoid "AI Hype"**: Use terms like "Probabilistic inference" instead of "Thinking".
2.  **Focus on "Constraints"**: Emphasize what the agent _cannot_ do (due to governance) as much as what it _can_ do.
3.  **Data > Anecdotes**: Use the Metrics (RS, IY) to back up every claim.
