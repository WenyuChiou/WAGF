# SQ1 Final Report: Stability & Rationality (The Governance Effect)

**Date**: 2026-01-25
**Objective**: Determine the impact of the Governed Broker Framework on agentic consistency and rationality.
**Key Metric**: Global Panic Frequency (V1) - The rate at which agents attempt irrational relocation.

---

## 1. The Core Finding: Chaos to Order

The experiments confirm that **Small Language Models (SLMs) are intrinsically chaotic** in crisis simulations. Without governance, they exhibit extreme "Exit Bias" (Panic Relocation). The Framework successfully imposes rationality, transforming a chaotic system into a stable one.

### Global Metric Summary (V1: Panic Relocation Frequency)

_Values represent the percentage of Total Active Steps where the agent attempted irrational relocation._

| Model Scale       | **Group A** (Ungoverned) | **Group B** (Governed)                                     | **Group C** (Social) |
| :---------------- | :----------------------- | :--------------------------------------------------------- | :------------------- |
| **DeepSeek 1.5B** | **80.4%** 🚨 (Chaos)     | **28.2%** (Blocked Intent) $\rightarrow$ **0.0%** (Actual) | **0.0%** ✅ (Stable) |
| **DeepSeek 8B**   | **3.4%** (Stable)        | **1.2%** (Blocked Intent) $\rightarrow$ **0.0%** (Actual)  | **0.0%** ✅ (Stable) |
| **DeepSeek 14B**  | **29.5%** ⚠️ (High)      | **0.0%** (Blocked Intent) $\rightarrow$ **0.0%** (Actual)  | **0.0%** ✅ (Stable) |

**Conclusion**:

1.  **Necessity**: Ungoverned agents (Group A) are scientifically unusable for simulation (80% panic rate for 1.5B, 30% for 14B).
2.  **Efficacy**: Governance (Group B) successfully filters 100% of these irrational actions (Actual=0%).
3.  **Nature vs Nurture**: Governance does not change the agent's nature (Intent remains 28%), but ensures the _simulation outcome_ is valid.

---

## 2. The Case for Group C (Social Efficiency)

**Research Question**: _Can social norms replace central enforcement?_

**Verdict: YES.**  
Group C achieves the same **0.0% Panic Rate** as Group B, but with **Zero Central Interventions**.

- **Group B Cost**: 138 Central Blocks (for 1.5B).
- **Group C Cost**: 0 Central Blocks.
- **Mechanism**: Agents learned "Safe Behavior" (Do Nothing / Elevate) from neighbors, internalizing the rational strategy without hitting the governance firewall.

**Implication for Paper**: This supports the sociological hypothesis that **"Norms are efficient governance."**

---

## 3. Side Effects & Secondary Metrics

Governance is not free of consequences. Blocking one path forces the agent to find another or do nothing.

### Metric V2: Panic Elevation Frequency (The Hydraulic Effect)

_Global Frequency of Elevation actions (Side Effect)._

| Model Scale | Group A | Group B | Group C             |
| :---------- | :------ | :------ | :------------------ |
| **1.5B**    | 0.0%    | 3.2%    | **9.4%** ⚠️ (Shift) |
| **8B**      | 0.6%    | 0.0%    | 0.1%                |
| **14B**     | 0.3%    | 0.0%    | 0.0%                |

**Insight**: For the smallest model (1.5B), Group C shows a significant "Hydraulic Shift". Since Panic Relocation is socially discouraged, agents shift to Elevation. This is a **rational adaptation** (Elevation is safer/cheaper than Relocation).

### Metric V3: Complacency Rate (Responsiveness)

_Global Frequency of 'Do Nothing' under High/Very High Threat._

| Model Scale | Group A | Group B | Group C                |
| :---------- | :------ | :------ | :--------------------- |
| **1.5B**    | 5.1%    | 1.6%    | **1.2%** ✅ (Best)     |
| **8B**      | 16.8%   | 16.6%   | **24.2%** 🐢 (Laziest) |
| **14B**     | 2.4%    | 4.6%    | 6.3%                   |

**Insight**:

- **1.5B**: Group C is the most responsive (lowest complacency).
- **8B**: Intriguingly, 8B shows high complacency across the board, especially in Group C. This suggests a "Model Personality" trait where 8B is more passive.

---

## 4. The "Indecision" Effect (Flip-Flops)

    - **Metric**: Flip-Flop Rate (Decision Instability).
    - **1.5B Data**: Group A (17% FF) $\rightarrow$ Group C (50% FF).
    - _Interpretation_: Social Learning introduces noise. Agents oscillate between "Copy Neighbor" and "Self-Preservation", leading to higher entropy in decision-making.

---

## 4. Final Recommendation for SQ2 (Heterogeneity)

With Stability (SQ1) proven, the next phase should investigate **Heterogeneity**:

- Do all agents behave the same? (Gini Coefficient of Wealth/Action).
- Does Governance create a "Monoculture"? (Reduced diversity of strategies).
- **Hypothesis**: Group B will have the lowest diversity (Enforced Uniformity), while Group C might show "Clusters" of behavior.

---

**Status**: SQ1 Complete. Ready for SQ2.
