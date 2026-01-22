# JOH Experiment: Preliminary Analysis Report

**Status**: Main Experiment (Gemma) Complete. Stress Test (Marathon) In Progress (50%).

## 1. The "Ratchet Effect" Verified (Gemma 3)

The Main Experiment (A/B/C) results for Gemma 3 (4b) strongly validate the **Group C (Governed + Memory)** architecture.

| Metric                | Group A (Naive)     | Group B (Gov Only) | Group C (Gov + Mem) | Interpretation                                                           |
| :-------------------- | :------------------ | :----------------- | :------------------ | :----------------------------------------------------------------------- |
| **MCC** (Rationality) | **-0.015** (Random) | 0.456 (Improved)   | **0.607** (Best)    | Group C achieves highest fidelity between thought & action.              |
| **Panic Rate**        | 22.2%               | 0.9%               | **1.0%**            | Memory + Governance eliminates irrational panic.                         |
| **Complacency**       | 13.4%               | 32.8%              | **20.4%**           | Group C reduces the "Mechanical Compliance" complacency seen in Group B. |

> **Conclusion**: Group C successfully "Ratchets" performance, retaining the safety of Group B while recovering internal fidelity.
> **Verification Update**: Analysis of Group C logs confirms the **"Year-End Reflection"** mechanism is active. Agents effectively synthesized "Lessons Learned" (e.g., "I observed a trend of increasing flood frequency") at the end of each year, which were re-injected with high importance ($0.9$).

---

## 2. Stress Test: A Tale of Two Models

The "Panic" and "Veteran" stress tests reveal a fascinating divergence between the two models (Llama 3.2 vs Gemma 3).

| Scenario          | Metric              | Llama 3.2 (3b) | Gemma 3 (4b) | Narrative Insight                                                                                                                                                                |
| :---------------- | :------------------ | :------------- | :----------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ST-1: Panic**   | **Relocation Rate** | **97.3%**      | **3.7%**     | **Llama is "Anxious"**: It blindly follows the "Panic" persona. **Gemma is "Stubborn"**: It resists the persona's urge to relocate (possibly due to internal reasoning vs cost). |
| **ST-2: Veteran** | **Inaction Rate**   | **0.1%**       | **22.0%**    | **Llama is "Obedient"**: It immediately adapts despite the "Veteran" stubbornness. **Gemma is "Resilient"**: It holds onto the "Old Ways" longer.                                |

### Theoretical Implication

- **Llama 3.2** behaves like a **"Soft Student"**: High interaction with the prompt, easily swayed by Persona Injections (both Panic and Veteran). Good for "Compliance", bad for "Stability".
- **Gemma 3** behaves like a **"Hard Engineer"**: Stronger internal priors, resists persona changes. Better for "Robustness", but harder to steer.

---

## 3. Immediate Next Steps

1.  **Wait**: `ST-3 Goldfish` and `ST-4 Format` are currently computing (Job started ~7:00 AM).
2.  **Synthesis**: Once finished, we will see if Llama's "Compliance" makes it perform better or worse on the "Goldfish" (Memory) test.
