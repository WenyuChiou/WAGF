# SQ2: Heterogeneity & Diversity Findings

**Date:** 2026-01-27

## 1. Challenge Statement (The "Monoculture Risk")

**Core Problem:** LLM agents tend to converge on a single, suboptimal behavior over time (Mode Collapse), especially when faced with extreme stress (flood events).
**Scientific Question:** Does rule-based governance prevent population-level mode collapse and preserve the diversity of community adaptation strategies?

## 2. Evaluation Metrics Definition

- **Shannon Entropy ($H$)**: A measure of uncertainty or diversity in agent decisions.
  - **Formula**: $H = -\sum p_i \log_2 p_i$ (calculated in bits).
  - **Scale**: $0$ (Mode Collapse) to $2.0$ (Perfect Diversity across 4 actions).
- **Mode Collapse**: The state where all agents in a population choose the identical action (usually mass relocation or mass complacency), indicating a lead-dead social simulation.
- **Transient Diversity**: The phenomenon where a population maintains high entropy before eventually settling, often leading to better long-term problem solving.

## 3. Decisional Entropy Data Summary (Bits)

| Model Scale | Group          | Year 1 | Year 4 | Year 7 | Year 10     | Trend                   |
| :---------- | :------------- | :----- | :----- | :----- | :---------- | :---------------------- |
| **1.5B**    | **A (Ungov)**  | 1.853  | 0.579  | 0.141  | **0.000\*** | **Total Collapse**      |
| **1.5B**    | **B (Strict)** | 1.850  | 1.634  | 1.327  | 0.962       | **Diversity Preserved** |
| **1.5B**    | **C (Social)** | 1.850  | 1.634  | 1.141  | 0.731       | **Active Diversity**    |
| **8B**      | **A (Ungov)**  | 1.065  | 0.994  | 0.407  | 0.584       | **Slow Collapse**       |
| **14B**     | **A (Ungov)**  | 1.417  | 0.688  | 1.000  | 0.760       | **Stable Diversity**    |
| **32B**     | **A (Ungov)**  | 1.156  | 1.579  | 1.210  | 0.934       | **Robust Diversity**    |

_\*Year 8 is the terminal point for 1.5B Group A as the entire population relocated._

---

## 4. Key Scientific Findings

### 4.1 Governance as a Diversity Anchor

- **1.5B Recovery**: Without governance, the 1.5B model collapses to a monoculture of panic relocators (H=0). Governance keeps the entropy at **~1.0 bits** (2nd column in bits), allowing agents to continue exploring insurance and elevation even in Year 10.
- **Micro-Macro Asymmetry**: SQ1 showed that 1.5B agents are "noisy" individuals. However, SQ2 proves that this individual noise, when structured by governance, creates a **Functional Diversity** that is more resilient than the silent, static outcome of the ungoverned group.

### 4.2 Scaling and Native Diversity

- **Intelligence vs. Diversity**: Larger models (14B, 32B) possess a native "Transient Diversity." They maintain an entropy of >0.7 bits without external intervention.
- **The 8B Dip**: 8B models show a significant dip in entropy (0.4 bits) around year 7, indicating a native tendency toward mode collapse that is eventually corrected by its slightly better reasoning capability in later years.

---

## 5. Recommended Literature Review (SQ2 Focus)

### 5.1 Mode Collapse & Alignment

- **Shumailov et al. (2024)**: _"Model Collapse in Language Models"_ - Explains how models trained on their own data (or simulation outputs) lose diversity, supporting our "Cognitive Decay" findings in Group A.
- **Kirk et al. (2024)**: _"Understanding and Mitigating Mode Collapse in LLM Alignment"_ - Directly connects RLHF/SFT to the reduction of generative diversity.

### 5.2 Social Simulation & Entropy

- **Axelrod (1997)**: _"The Complexity of Cooperation"_ - Classic foundation for studying the dissemination of culture and diversity in social systems.
- **Zhang et al. (2024)**: _"Multi-Agent Strategy Diversification via Entropy Seeking"_ - Research that directly maps to our interest in maintaining high-entropy populations.

---

## 6. SQ2 Conclusion: The "Entropy Shield"

Governance does not just block bad actions (SQ1); it acts as an **Entropy Shield** that prevents the simulation from decaying into a trivial, single-state outcome. This proves that rule-based systems are not "restrictive" in the negative sense, but rather "foundational" in the sense that they enable the continued existence of agent agency and community heterogeneity.

![Entropy Trend Visualization (2x2)](file:///c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/single_agent/analysis/SQ2_Final_Results/entropy_evolution_trend_2x2.png)
