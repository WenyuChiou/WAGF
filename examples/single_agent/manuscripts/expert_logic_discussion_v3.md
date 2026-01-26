# 🎓 Roundtable Part 3: Visualizing the "Three Big Questions"

**Date**: 2026-01-24
**Topic**: Mapping Logic to Figures (The "Money Plots")
**Status**: Planning the Analytics Pipeline

---

## 🗣️ Dialogue: Dr. S demands "The Money Plot"

**Dr. S (Critic)**: "Okay, you convinced me the 1.5B data is valid. But a reviewer won't read 500 lines of JSON logs. You need **three high-impact figures** to answer the Three Big Questions. If you can't visualize it, it doesn't exist."

**Agent (Antigravity)**: "We have the data: `threat_appraisal` (TP), `coping_appraisal` (CP), `decisions`, and `governance_interventions`. Here is my plan:"

---

### 📉 Figure 1: The "Cognitive Collapse" (Question: Heterogeneity)

- **Goal**: Show _why_ 1.5B failed and 8B succeeded without just showing a survival rate.
- **Dr. S's Critique**: "Don't just show 'Dead vs Alive'. Show me the **Internal State**."
- **Proposed Plot**: **"The Panic Trajectory"**
  - _X-Axis_: Time (Year 0-10)
  - _Y-Axis_: Average Threat Perception (TP) Normalized (0-1)
  - _Lines_:
    - 🔴 **1.5B (Ungoverned)**: Should shoot up to 1.0 (Panic) immediately after one flood?
    - 🟢 **8B (Ungoverned)**: Should fluctuate realistically with flood events.
  - _Why this works_: It proves the "100% Attrition" wasn't random; it was driven by hyper-sensitive TP.

---

### 📊 Figure 2: The "Governance Scaling Law" (Question: Governance Utility)

- **Goal**: The core hypothesis—different models need different help.
- **Dr. S's Critique**: "This is your theory contribution. The U-Curve (or L-Curve)."
- **Proposed Plot**: **"Intervention Density by Scale"**
  - _X-Axis_: Model Parameter Size (Log Scale: 1.5B, 8B, 14B, 32B)
  - _Y-Axis_: Interventions per Agent-Year (Reasoning Corrections)
  - _Hypothesis_:
    - **1.5B**: High Bar (Correction needed frequently to prevent suicide/panic).
    - **8B**: The "Dip" (Sweet Spot - mostly agrees with Gov).
    - **32B**: Rise? (Maybe it argues back?) or Flat?
  - _Color Code_: Split bars by "Rejection Type" (e.g., Red=Safety Violation, Yellow=Inconsistency).

---

### 🕸️ Figure 3: The "Social Contagion" Verification (Question: Scalability/Social)

- **Goal**: Show that Group C (Social) actually _changed_ decisions, not just added noise.
- **Dr. S's Critique**: "You claimed 'Democratizing data kills fragile models'. Prove it."
- **Proposed Plot**: **"The Echo Chamber Effect"**
  - _Compare_: Group B (Gov Only) vs Group C (Gov + Social) for 1.5B.
  - _Metric_: "Relocation Consensus".
  - _Visual_: A Heatmap of the Neighborhood.
    - _Group B_: Scattered red dots (Individual Panic).
    - _Group C_: Clusters of red dots (Contagion).
  - _Note_: This might be hard to plot with just CSV. Maybe a simple bar chart: "Relocation Rate: Group B vs Group C".

---

## 🛠️ Action Items for Analytics Script (`analyze_abc_metrics.py`)

To satisfy Dr. S, our script needs to calculate:

1.  **TP/CP Trajectories**: Extract `threat_appraisal` over time, average per year.
2.  **Intervention Rate**: Count `Validation FAILED` logs per model size.
3.  **Social Delta**: Calculate `Relocation Rate (Group C) - Relocation Rate (Group B)`.

**User Decision**: Do we agree on these three figures for the Technical Note?
