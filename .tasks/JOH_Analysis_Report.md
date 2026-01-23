# JOH Experiment Analysis Report (Final Integration)

## 1. The Governance Scaling Law (Consolidated)

Our analysis of DeepSeek R1 1.5B vs 8B across 3 experimental groups (Control, Governed, Memory) reveals a distinct phase transition in how LLMs behave under varying constraint levels.

### Phase 1: The Guardrail Phase (1.5B)

_Governance as "Life Support" against Entropy and Hallucination._

- **The Hallucination Problem**: In Group A (Control), **73.9%** of 1.5B agents claimed to be _"Already Relocated"_ despite never moving.
  - This is a textbook "Fluency-Reality Gap": The model hallucinates a safe state to avoid the cognitive load of decision-making.
- **The Correction**: Group B (Governed) forces the agents to acknowledge their risk state.
  - **Result**: Self-Repair Rate (SRR) indicates **18.77%** of outputs require structural repair.
  - **Behavior**: Shifts from "Lying" (Already Relocated) to "Alarmist" (336 counts of buying insurance).
- **Verdict**: For small models, Governance acts as a **Reality Anchor**, preventing state hallucination.

### Phase 2: The Compass Phase (8B)

_Governance as "Rationality Filter" against Anxiety._

- **The Anxiety Problem**: In Group A (Control), 8B agents exhibit "Action Bias".
  - **45%** chose to Elevate House (Major Action) immediately.
  - **24%** bought insurance.
  - Only **21%** did nothing.
  - _Economic Reality_: If 70% of a city acts instantly, the market collapses. This represents "System 1" anxiety unchecked by "System 2" constraints.
- **The Correction**: Group B (Governed) suppresses this over-reaction.
  - **Result**: "Do Nothing" rises to ~80%. Insurance/Elevation drops to ~10%.
  - **Fidelity**: $\rho = 0.37$ (Honest). Agents only act when threat is high.
- **Verdict**: For medium models, Governance acts as a **Rationality Filter**, damping "Action Bias" and ensuring actions are proportional to risk.

### Phase 3: The Memory Amplifier (Group C)

_How Long-Term Memory alters the equation._

- **1.5B + Memory**: Fidelity $\rho$ jumps to **0.46**. Memory provides context that stabilizes the chaotic 1.5B reasoning better than rules alone.
- **8B + Memory**: Fidelity $\rho$ improves to **0.43** (+16%). Memory refines the risk perception, making the "Compass" more accurate.

---

## 2. Summary of Metrics

| Metric                 | 1.5B (Chaos)                              | 8B (Rational)                          |
| ---------------------- | ----------------------------------------- | -------------------------------------- |
| **Stability (SRR)**    | 18.77% Error Rate                         | 1.53% Error Rate                       |
| **Logic (Group A)**    | Hallucinated Safety ("Already Relocated") | Action Bias (Anxiety/Over-reaction)    |
| **Role of Governance** | **Reality Anchor** (Fixes Hallucination)  | **Rationality Filter** (Fixes Anxiety) |
| **Role of Memory**     | Stabilizer                                | Optimizer                              |

## 3. Conclusion

The "Governance Scaling Law" is non-linear.

- At low parameters, we govern to **prevent lies**.
- At medium parameters, we govern to **prevent panic**.
  This finding directly addresses the "Asymmetry" and "Hallucination" hypothesis in the Technical Note.
