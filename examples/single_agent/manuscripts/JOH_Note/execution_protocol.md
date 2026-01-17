# Research Execution Protocol: The Governed Broker Project

**Status**: Active Execution
**Document Type**: Master Protocol / Lab Notebook
**Objective**: Publish a high-impact Technical Note/Letter on "Cognitive Governance for Hydro-Social Agents".

---

## 1. Target Venue Strategy

| Journal                                | Format              | Length Constraint                             | Fit Rationale                                                                                                       |
| :------------------------------------- | :------------------ | :-------------------------------------------- | :------------------------------------------------------------------------------------------------------------------ |
| **GRL (Geophysical Research Letters)** | Research Letter     | Max 12 Publication Units (~4-6k words + figs) | **High Impact**. Excellent for the "Novelty" of coupling LLMs with Physics. Requires strong "Implications" section. |
| **EMS (Env. Modelling & Software)**    | Short Communication | Flexible (typ. 3-5k words)                    | **Perfect Scope**. Fits the "Cognitive Middleware" software contribution perfectly. Best technical audience.        |
| **WRR (Water Resources Research)**     | Research Article    | Max 25 PUs                                    | **Solid Domain Fit**. Good if we need more space to explain the hydrology.                                          |

**Decision**: Target **GRL** style (concise, high impact) first. If "novelty" is questioned, pivoting to **EMS** is safe.

---

## 2. The Core Problem: "The Fluency-Reality Gap"

- **Observation**: Standard "Generative Agents" (System 1) are excellent at conversation but terrible at physical survival. They act like "Goldfish" (forgetting floods) or "Hallucinators" (ignoring constraints).
- **Hypothesis**: A "Cognitive Middleware" layer (System 2) can enforce bounded rationality _interactions_ without needing to fine-tune the LLM _weights_.
- **The "Enhanced" Claim**: We are not just building an agent; we are defining a **Protocol for Hydro-Social Consistency**.

---

## 3. Experimental Design (The "JOH Core Set")

We utilize a **4-Model Benchmark** to prove the framework is model-agnostic.

| Model           | Size | Role                                                                                                     | Status      |
| :-------------- | :--- | :------------------------------------------------------------------------------------------------------- | :---------- |
| **Llama 3.2**   | 3B   | **The Baseline**. Fast, prone to hallucination. Proven beneficiary of governance.                        | ✅ Complete |
| **Gemma 3**     | 4B   | **The Challenger**. Google's open weight contender.                                                      | 🚀 Active   |
| **DeepSeek-R1** | 8B   | **The Reasoner**. Chain-of-Thought native. Tests if governance conflicts with strong internal reasoning. | 🚀 Active   |
| **GPT-OSS**     | ~20B | **The Proxy**. Represents cloud-tier performance (local simulation).                                     | 🚀 Active   |

### **Experimental Matrix**

- **Group A (Control)**: Raw LLM. (Expected: Low RS, High Hallucination).
- **Group B (Governance)**: Valid Actions, but "Goldfish" memory. (Expected: High RS, Low AD).
- **Group C (Governance + Memory)**: The "Enhanced" Agent. (Expected: High RS, High AD).

---

## 4. Key Performance Indicators (Metrics)

We quantify "Rationality" using the standard **JOH Metrics Suite**:

1.  **Rationality Score (RS)**: $\% \text{ of decisions compliant with physical constraints (Budget/Elevation)}$.
    - _Target_: >95% for Group B/C.
2.  **Intervention Yield (IY)**: $\% \text{ of attempts rejected by System 2}$.
    - _Significance_: High IY = The LLM is trying to cheat physics.
3.  **Adaptation Density (AD)**: $\frac{\text{Significant Coping Actions}}{\text{Total Actions}}$.
    - _Significance_: Measures "Goldfish Effect". Low AD = Passive agent.

---

## 5. Workflow & Action Plan

1.  **Data Harvesting**: Monitor valid `simulation_log.csv` generation for all 4 models. **[Current Block]**
2.  **Audit & Synthesis**: Use `joh_evaluator.py` to generate the consolidated `Tab 1` (Metrics Table).
3.  **Visual Proof**: Generate Figure 2 (Adaptation Rate) and Figure 4 (The Trace Log).
4.  **Drafting**: Write Section 1 (Intro) and 2 (Method) while data finishes.

---

## 6. Risk Management

- **Risk**: DeepSeek "Thinking" tags break the JSON parser.
  - _Mitigation_: Pre-processor in `model_adapter.py` strips `<think>` tags. (Already Implemented).
- **Risk**: Gemma "Safety Filter" refusals.
  - _Mitigation_: Retry logic with simplified prompts.

---

## 7. Reviewer Defense Strategy (Gap Closure Plan)

**Based on "Scientific Assistant" Audit (2026-01-17)**

1.  **Metric Data Gap**:

    - _Status_: **CRITICAL**. Reviewer #2 correctly notes we only have Llama 3.2 data.
    - _Action_: Verify DeepSeek/Gemma logs by **10:00 AM**. If logs are empty, restart simulations with `debug=True`.
    - _Fallback_: If 4-model benchmark fails, pivot paper to "Llama 3.2 Case Study" (weaker impact, but valid).

2.  **Citation Gap**:

    - _Status_: **SOLVED**. Added O'Brien et al. (AQUAH) and Zhang et al. (WaterGPT) to `bibliography.md`.
    - _Narrative_: "Unlike AQUAH which automates the _hydrologist's workflow_, we automate the _resident's decision-making_."

3.  **Visual Gap**:
    - _Status_: **PENDING**. Need "Methodology Diagram" (Figure 1).
    - _Action_: Use Mermaid.js to define the "Cognitive Middleware" flow in a separate artifact.
