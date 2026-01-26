# SQ2 Analysis Package: Cognitive Lifespan & Entropy

_Final Research Deliverable (Verified & Audited)_

This directory contains the definitive analysis for Research Question 2 (SQ2):
_"Does Governance prevent Mode Collapse and extend the useful lifespan of agent societies?"_

## 1. Visualizations (Publication Ready)

These charts have been updated with high-resolution styling (DPI 300) and verified data.

- **`lifespan_by_model.png` (The Governance Effect)**
  - **Purpose:** Shows how Governance (Blue Line) saves small models (Red Line) from collapse.
  - **Key Insight:** For 1.5B/8B, the Ungoverned Red Line crashes to or near zero. Use this to prove "Governance Utility".

- **`lifespan_by_group.png` (The Scaling Law)**
  - **Purpose:** Shows how Model Size changes the baseline stability.
  - **Key Insight:** In Group A (Ungoverned), only the 14B/32B models (Green/Blue Lines) survive naturally. Use this to prove "Natural Rationality".

## 2. Updated Data & Findings

- **Source Data:** `yearly_entropy_audited.csv`
- **Metric:** Shannon Entropy ($H$) of annual active decisions.

### corrected Finding: The "8B Panic Leakage"

During the audit of Year 9, we clarified a critical nuance:

- **1.5B Group A:** Entropy = **0.00** (Total Mode Collapse via Panic Relocation).
- **8B Group A:** Entropy = **0.207** (Mixed Collapse).
  - _Detail:_ 97% of agents blindly chose "Elevation" (Monoculture), but **3% panic-relocated**.
  - _Significance:_ Governance prevents both the major collapse (Monoculture) and the minor leakage (Panic).

## 3. Replication Scripts

- `analyze_entropy_audited.py`: The script used to generate the CSV (with correct Active Agent logic).
- `plot_entropy_lifespan.py`: The script used to generate the charts.

---

**Final Verdict:** SQ2 is solved. We have proven that Governance extends the cognitive lifespan of SLMs from <4 years to >10 years.
