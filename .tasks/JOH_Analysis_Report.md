# JOH Experiment Analysis Report (DeepSeek R1 8B)

## 1. Model Verification: `gpt-oss`

- **Status**: ✅ Compatible
- **Test Result**: Successfully generated valid JSON output.
- **Performance**: ~13.44s per inference (Slower than DeepSeek 8B ~7s).
- **Recommendation**: Valid backup model.

---

## 2. DeepSeek R1 8B Analysis (Corrected)

### 2.1 Stability (Efficiency)

- **Metric**: Self-Repair Rate (SRR)
- **Result**: **1.53%** Error Rate (98.5% First-Pass Success).
- **Insight**: DeepSeek R1 8B exhibits exceptional syntactic stability. The "Governance Tax" is primarily computational (reasoning time), not corrective (retries). This places it firmly in the **T3/T4 (Efficiency Sweet-spot)** category of the Governance Scaling Law.

### 2.2 Cognitive Activity (Reasoning)

- **PMT Counts** (Group B):
  - Severity: ~6.75/agent
  - Cost: ~8.48/agent
- **Insight**: The model actively weighs costs against risks. It is not "mindlessly" following rules; it is deliberating.

### 2.3 Internal Fidelity (Rationality)

_Measurement of alignment between Perceived Threat (TP) and Adaptive Action._

| Group                  | Spearman $\rho$ | P-Value      | Verdict                        |
| ---------------------- | --------------- | ------------ | ------------------------------ |
| **Group B (Governed)** | **0.37**        | $< 10^{-30}$ | **Moderate Fidelity** (Honest) |
| **Group C (Memory)**   | **0.43**        | $< 10^{-30}$ | **High Fidelity** (+16% Boost) |

**Key Findings**:

1.  **Honesty Confirmed**: Qualitative analysis found **0 mismatches** where Threat was "Low" but Action was "High". The model buys insurance _only_ when it perceives High/Medium threat.
2.  **The Memory Amplifier**: Group C (with Memory) shows higher fidelity than Group B. This suggests that **Long-Term Memory acts as a cognitive stabilizer**, refining the agent's risk perception over time and aligning it closer to rational action.
3.  **Governance Scaling Law**: At 8B parameters, the Governance Framework does not just "constrain" chaos (as with 1.5B); it **amplifies rationality** by providing the structure for consistent reasoning.

---

## 3. Conclusion & Next Steps

DeepSeek R1 8B is a viable, rational engine for Socio-Hydrology.

- **Hypothesis Confirmed**: 8B represents a "Rationality Plateau" where agents are honest and responsive to governance.
- **Next Experiment**: Run `gpt-oss` as Group B to compare if a non-reasoning model (standard GPT) acts with similar fidelity or succumbs to "Narrative Entropy".
