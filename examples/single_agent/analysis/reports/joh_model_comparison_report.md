# JOH Comparative Analysis: Group A-B-C

**Study**: Impact of Cognitive Governance on Llama 3.2 3B

## 1. Experimental Design (The "ABC" Cohorts)

We evaluate the framework across three increasing levels of cognitive architecture:

| Group | Name                      | Configuration                                                                    | Hypothesis                                                                                                                                                     |
| :---- | :------------------------ | :------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A** | **Control (Ungoverned)**  | • Model: Llama 3.2 3B<br>• Memory: Window (N=5)<br>• **Governance: OFF**         | **High Volatility.** Agent behavior will be dominated by "System 1" impulses (Panic/Hallucination). High Adaptation Density (>90%) but Low Rationality.        |
| **B** | **Baseline (Standard)**   | • Model: Llama 3.2 3B<br>• Memory: Window (N=5)<br>• **Governance: ON (Strict)** | **Rational Stability.** "System 2" constraints (Budget, Threat) will block hallucinations. Adaptation Density drops to realistic levels (~65%).                |
| **C** | **Final (Human-Centric)** | • Model: Llama 3.2 3B<br>• **Memory: Human-Centric (SEM)**<br>• Governance: ON   | **Long-Term Consistency.** Semantic Episodic Memory (SEM) allows better year-over-year strategy (e.g., "I am saving for elevation"). Higher Rationality Score. |

---

## 2. Comparative Metrics

### Metric 1: Adaptation Density (AD)

_Measures the frequency of protective actions (Insurance, Elevation, Relocation)._

- **Group A (Hypothesis)**: **High (>85%)**. Without budget checks, agents "spam" actions (e.g., Relocating every year).
- **Group B (Result)**: **Moderate (~72%)**. Governance blocks unfeasible actions.
- **Group C (Hypothesis)**: **Optimized (~65%)**. Better memory allows "waiting" strategies (Inaction is a choice, not random).

### Metric 2: Rationality Score (RS)

_Percentage of proposals accepted by the Environment/Governance._

- **Group A**: N/A (No audit layer to measure against).
- **Group B**: **~70%**. Logic Block frequently intervenes (e.g., "Elevating without funds").
- **Group C**: **>80%**. Reflection helps Agent learn constraints implies fewer rejections? (TBD)

---

## 3. Preliminary Findings (B vs. Stress)

_Note: "Stress-Panic" serves as a proxy for the ungoverned impulses of Group A._

- **Suppression of Panic**: In Stress Test 1, the raw impulse to relocate was 100%. Group B governance suppressed this to 77%, effectively "saving" 23% of agents from irrational financial ruin.
- **Cost of Governance**: The retry mechanism in Group B introduces latency but ensures validity.

## 4. Next Steps

1.  **Group C Execution**: Pending processing.
2.  **Adaptation Plot**: Overlay Group B and Group C adaptation curves (Figure 3).
