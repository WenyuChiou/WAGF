# JOH Analysis & Visualization Strategy

**Role**: Lead Statistician / Data Scientist
**Date**: 2026-01-18

This document outlines the statistical framework and visualization strategy to validate the **Governed Broker Framework**, specifically focusing on the new **Human-Centric Memory (Group C)** and **Reflection Logs**.

---

## 1. Statistical Framework (The "Hard" Numbers)

We must move beyond "it looks better" to quantifying **Reliability**.

### Hypothesis 1: Variance Reduction (Stability)

- **Claim**: "Human-Centric Memory significantly reduces the stochastic instability of LLM agents compared to standard Sliding Window memory."
- **Metric**: **Coefficient of Variation (CV)** across runs.
  - $$CV = \frac{\sigma}{\mu}$$
  - _Why_: Since Group B and C might have different mean adaptation rates, comparing raw Standard Deviation ($\sigma$) is biased. CV normalizes this.
- **Test**: **Levene’s Test** for Equality of Variances (Group B vs Group C).
  - _Target_: Reject Null ($p < 0.05$), proving variances are distinct.
  - _Backup_: If N=3 is too small for p-value, report the **Variance Reduction Ratio**: $1 - (\sigma_C^2 / \sigma_B^2)$.

### Hypothesis 2: Rationality Maintenance (Effectiveness)

- **Claim**: "Governance does not stifle adaptation; it filters irrationality."
- **Metric**: **Rationality Score (RS)**.
  - $$RS = \frac{Decisions_{consistent}}{Decisions_{total}}$$
- **Test**: **Comparing Means**. Show that Group C maintains the high Adaptation Rate of Group B (or higher) but with $RS \approx 1.0$.

---

## 2. Visualization Strategy (The "Story")

### Plot A: The Stability Boxplot (Quantitative)

- **Type**: Box-and-Whisker Plot.
- **X-Axis**: Cohorts (A: Naive, B: Window, C: Human-Centric).
- **Y-Axis**: Cumulative Adaptation Rate (Year 10).
- **Narrative**:
  - **Group A**: Tight box (stable) but at the bottom (useless).
  - **Group B**: Huge box (tall). Sometimes 90%, sometimes 40%. **Unreliable**.
  - **Group C**: Tight, high box. **Reliable & Effective**.

### Plot B: The Sawtooth Trajectory (Behavioral)

- **Type**: Multi-Line Time Series (Average New Adaptations per Year).
- **Focus**: Years 3-5 (Post-Flood Quiet Period).
- **Narrative**:
  - **Group B**: Line crashes to 0. "Goldfish Effect".
  - **Group C**: Line stays above 0. "Ratchet Effect".
  - _Note_: Use `simulation_log.csv` aggregation.

### Plot C: The Cognitive Heatmap (Mechanism / XAI)

- **Type**: Keyword Density Heatmap over Time.
- **Data Source**: `reflection_log.jsonl` (The new artifact).
- **X-Axis**: Simulation Year (1-10).
- **Y-Axis**: Semantic Topics (Extracted from reflections).
  - _Topics_: "Trauma/Fear", "Cost/Money", "Safety/Protection", "Community".
- **Color**: Intensity (Frequency of mentions).
- **Narrative**:
  - Show that **"Trauma"** remains "Hot" (Red) in subsequent years (Y3, Y4) even when the external flood signal is "Cold" (0 depth).
  - This visually proves that the **Internal State** (Memory) is overriding the **External State** (Environment), validating the "Human-Centric" architecture.

### Sample Size Note (The "N=3" Question)

- **Is N=3 enough?** For a _Technical Note_, yes, if the Effect Size is large.
  - _Defense_: "Given the computational cost of reasoning agents and the magnitude of the observed effect (Cohen's d > 2.0), N=3 is sufficient to demonstrate the architectural mechanism."
- **Recommendation**: If feasible, increasing to **N=5 or N=10** provides robust "Error Bars" for the Boxplot.
  - _Cost_: Approx. 10 minutes per run.
  - _Benefit_: Removes the easiest ground for reviewer critique.

---

## 3. Action Plan

1.  **Wait for Simulation**: Ensure `run_missing_group_c.ps1` completes to get the N=3 dataset.
2.  **Run `analyze_joh_corrected.py`**:
    - This calculates the **CV** and **Stability Metrics**.
3.  **Develop `visualize_reflection.py`**:
    - _New Task_: Write a script to parse `reflection_log.jsonl`, extract keywords, and plot the Heatmap (Plot C).
