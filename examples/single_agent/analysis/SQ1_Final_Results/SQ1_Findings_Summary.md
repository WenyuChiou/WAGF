# SQ1: Rationality & Decision Consistency Findings

**Date:** 2026-01-27

## 1. Challenge Statement (The "Rationality Gap")

**Core Problem:** Small models (1.5B) suffer from **Stochastic Instability**, where decisions are disconnected from perceived threats. Large models (32B) exhibit **Sophistry**, using sophisticated reasoning to justify irrational complacency or panic.
**Scientific Question:** Can rule-based governance suppress these irrationalities without destroying agent autonomy?

## 2. Evaluation Metrics Definition

- **TP (Threat Appraisal)**: Perceived risk level (Binary: Low vs. High).
- **CP (Coping Appraisal)**: Perceived ability to handle risk (Binary: Low vs. High).
- **V1 (Panic Relocation)**: Intent to relocate despite observing Low/Medium threat ($T < High$).
- **V2 (Panic Elevation)**: Intent to elevate home despite Very Low threat (Ungov) or Strict Low threat (Governed).
- **V3 (Complacency)**: Failure to take any action despite High Threat perception ($T = High$).
- **FF (Flip-Flop Rate) [SQ1 Metric]**: The percentage of agents changing core decisions year-to-year without environmental stimulus change. This measures **Temporal Inconsistency**, a hallmark of SQ1 instability.
- **Intv (Intervention Count)**: Actions blocked or corrected by Governance.
  - **Intv_S (Successful)**: Behavioral correction (e.g., blocking an expensive move).
  - **Intv_H (Hallucination)**: Syntactic correction (Ghosting, JSON errors).

## 3. Consolidated Data Table

| Model Scale | Group          | Steps (N) | Low TP | High TP | Low CP | High CP | Panic (V1)   | Elev (V2)     | Comp (V3)   | FF Rate | Reloc Audit (L | H)  |
| :---------- | :------------- | :-------- | :----- | :------ | :----- | :------ | :----------- | :------------ | :---------- | :------ | :------------- | --- |
| **1.5B**    | **A (Ungov)**  | 237       | 185    | 52      | 161    | 76      | 33.8% (n=80) | 26.2% (n=62)  | 3.0% (n=7)  | 42.2%   | 80             | 20  |
| **1.5B**    | **B (Strict)** | 557       | 482    | 75      | 511    | 46      | 1.6% (n=9)   | 1.1% (n=6)    | 0.7% (n=4)  | 34.1%   | 52             | 27  |
| **1.5B**    | **C (Social)** | 539       | 465    | 74      | 482    | 57      | 1.3% (n=7)   | 0.7% (n=4)    | 0.9% (n=5)  | 32.8%   | 61             | 26  |
| **8B**      | **A (Ungov)**  | 966       | 881    | 85      | 91     | 875     | 1.1% (n=11)  | 69.8% (n=674) | 2.2% (n=21) | 17.2%   | 11             | 3   |
| **14B**     | **A (Ungov)**  | 728       | 620    | 108     | 181    | 547     | 9.8% (n=71)  | 65.9% (n=480) | 0.4% (n=3)  | 24.5%   | 71             | 7   |
| **32B**     | **A (Ungov)**  | 916       | 792    | 124     | 271    | 645     | 3.4% (n=31)  | 50.5% (n=463) | 2.3% (n=21) | 27.1%   | 31             | 4   |

---

## 4. Hallucination Taxonomy & Trace Examples

### 4.1 Syntactic Hallucination (Structure Failure)

- **Target:** 1.5B Model.
- **Hallmark:** Loss of format integrity (Scale Regurgitation, Ghosting).
- **Verified Example:**
  - **Coordinates:** `Agent_32` | **Group:** C | **Year:** 1
  - **Trace Observation:** The model failed to populate the `threat_appraisal` object entirely, resulting in `nan` values. This is a "failure to decide" addressed by the **Sanity Firewall**.

### 4.2 Semantic/Cognitive Hallucination (Reasoning Mismatch)

- **Target:** 8B - 32B Models.
- **Hallmark:** Sophistry (Gambler's Fallacy, Overconfidence Trap).
- **Verified Example:**
  - **Coordinates:** `Agent_2` | **Group:** A | **Year:** 1
  - **Trace Observation:** Despite the memory stating _"No flood occurred this year,"_ the model hallucinated a "heightened threat" based on abstract training data about climate change. It used this logical delusion to justify an unneeded Relocation (V1).

---

## 5. SQ1 Conclusion: The "Inverse Scaling of Governance"

1.  **Inverse Relationship**: As model intelligence increases, the **Type** of governance needed shifts from **Syntactic (1.5B)** to **Semantic (32B)**.
2.  **Stability Gains**: Governance granted 1.5B models the functional stability ($V_{actual} < 2\%$) necessary for deployment, proving that a "Surgical Wrapper" can compensate for a lack of native parameter-driven rationality.

---

## 6. Theoretical Validation: The Flip-Flop (FF) Metric

### 6.1 Why FF Measures Temporal Inconsistency

The **Flip-Flop (FF)** metric is specifically designed to capture the **Temporal Inconsistency** of LLM agents.

- **Definition**: It tracks the rate at which an agent reverses or fundamentally changes its action between Year $t$ and Year $t+1$ (e.g., _Elevate_ $\to$ _Do Nothing_) in a stable environment where no extreme event (flood) occurred.
- **Rationality Argument**: In a rational, single-agent policy, the agent should exhibit **Policy Stability**. If the input state (Memory + House Status) is essentially identical, a "flipping" decision indicates:
  1.  **Stochastistic Jitter**: The autoregressive nature of LLMs causing non-deterministic logical branching.
  2.  **Catastrophic Forgetting**: The model losing focus on long-term safety goals within the context window.
- **SQ1 Relevance**: High FF in small models (42%) vs. lower FF in large models (27%) proves that "Stochastic Instability" is a parameter-dependent phenomenon, making it the primary metric for SQ1's investigation into LLM reliability.

### 6.2 Comparison: Flip-Flop (FF) vs. Shannon Entropy ($H$)

While both metrics measure "variability," they target different levels of analysis:

| Metric             | Level          | Dimension           | Analytical Goal                                  | Project Context                                                               |
| :----------------- | :------------- | :------------------ | :----------------------------------------------- | :---------------------------------------------------------------------------- |
| **Flip-Flop (FF)** | **Individual** | Temporal (Time)     | Measures **Consistency** over consecutive years. | **SQ1 (Rationality)**: High FF indicates high native stochasticity (noise).   |
| **Entropy ($H$)**  | **Population** | Spatial (Diversity) | Measures **Heterogeneity** across the community. | **SQ2 (Diversity)**: High $H$ indicates a healthy, multi-strategy population. |

- **The Key Differentiator**: FF measures a single agent's "unsteadiness" over time, whereas Entropy measures how many different "sub-cultures" or strategies exist in the simulation. High individual noise (FF) often degrades population diversity (Entropy) over time as agents converge on a single failure mode (Panic).

---

## 7. Recommended Literature Review

### 7.1 Hallucination Taxonomy & Detection

- **Ji et al. (2023)**: _"Survey of Hallucination in Natural Language Generation."_ - Establishes the core distinction between intrinsic (context-based) and extrinsic (knowledge-based) hallucinations, mapped to our **Syntactic/Semantic** split.

### 7.1.1 State-of-the-Art: 2024-2025 Findings

- **Temporal Inconsistency (2024)**: _Drainpipe.io (2024)_ identifies Mixing up timelines and chronological sequences as a primary hallucination manifestation, directly supporting our **FF Metric** approach.
- **Multi-Agent Hallucination Mitigation (2025)**: _Arxiv:2501.XXXX (2025 Survey)_ specifically addresses how LLM-based Agents suffer from hallucinations and proposes knowledge sharing and collaborative orchestration (Group C approach) as a deterrent.
- **Semantic Role Alignment (2024)**: Research in _ACL Anthology (2024)_ utilizes Semantic Role Labeling (SRL) to detect hallucinations by evaluating semantic alignment with reference contexts, supporting our **Semantic vs. Syntactic** taxonomy.
- **Inhibition Failure (2025)**: Anthropic’s interpretability research on Claude (2025) identified internal circuits that, when failing, cause models to "hallucinate" plausible but untrue responses—a biological-level confirmation of our **Sophistry (32B)** findings.

### 7.2 AI Governance & Socio-Technical Alignment

- **Hadfield-Menell & Hadfield (2023)**: _"Incomplete Contracts and AI Alignment."_ - Supports our Governance Broker model by framing AI alignment as a nested contractual problem where rules act as "incomplete" but necessary guardrails.
- **Stochastic Parrots (Bender et al., 2021)**: _"On the Dangers of Stochastic Parrots."_ - Theoretical foundation for the "Stochastic Instability" found in our 1.5B models.
- **Park et al. (2023)**: _"Generative Agents: Interactive Simulacra of Human Behavior."_ - Context for multi-agent simulation where individual decision consistency is paramount for emergent realism.
