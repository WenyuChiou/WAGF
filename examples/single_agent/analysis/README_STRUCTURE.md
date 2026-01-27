# Analysis Directory Structure

This directory has been organized into Research Questions (SQ1, SQ2, SQ3) to facilitate modular analysis.

## 📂 SQ1_Final_Results (Rationality & Governance)

**Focus:** Does governance enforce rationality and prevent panic (The Governance Inverse)?

- **Scripts:**
  - `master_report.py`: Main metrics generator (Interventions, Panic, Compliance, Hallucinations).
  - `tools/plot_decision_integrity.py`: Visualizes Internal Fidelity vs Rationality (Figure 5).
  - `tools/analyze_joh_mcc.py`: Calculates Matthews Correlation Coefficient (Panic/Complacency rates).
  - `tools/plot_asymmetry.py`: Visualizes Hallucination Asymmetry (Figure 6).
- **Data:** `sq1_metrics_rules.xlsx` (Rule definitions).

## 📂 SQ2_Final_Results (Heterogeneity & Lifespan)

**Focus:** Does governance preserve diversity and prevent mode collapse (The Monoculture Risk)?

- **Scripts:**
  - `plot_entropy_lifespan.py`: Visualizes Shannon Entropy over time (Cognitive Lifespan).
  - `export_detailed_probabilities.py`: Exports probability distributions for entropy.
- **Data:** `yearly_entropy_audited.csv` (Entropy metrics).
- **Tools:** `tools/plot_temporal_dynamics.py`

## 📂 SQ3_Final_Results (Efficiency & Benchmarking)

**Focus:** Is the framework efficient and scalable (Surgical Governance)?

- **Scripts:**
  - `generate_overall_adaptation_matrix.py`: Summary visualization of adaptation strategies (Matrix).
  - `plot_deep_adaptation_rate.py`: Scaling law analysis for DeepSeek models (Adaptation Rates).
  - `shadow_audit_group_c.py`: Efficiency audit for Group C (Violations vs Interventions).
- **Tools:**
- **Tools:**
  - `tools/analyze_abc_metrics.py`: Calculates **Efficiency Metrics**:
    - **Rationality Score (RS)** (Compliance)
    - **Parse Failure Rate (PF)** (Waste/Overhead)
    - **Flip-Flop Rate (FF)** (Instability/Reversals)
  - `tools/analyze_interventions.py`: Detailed breakdown of **Intervention Transitions**.
  - `tools/analyze_abc.py`, `tools/visualize_group_c_options.py`.

## 📂 analysis_tools (Legacy/Shared)

Contains shared utilities and legacy scripts not yet categorized.
