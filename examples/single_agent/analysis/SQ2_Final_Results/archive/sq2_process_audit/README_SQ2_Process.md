# SQ2 Process Audit Report

_Step-by-Step Verification of "Cognitive Lifespan" Calculations_

This folder contains the complete audit trail for Research Question 2 (Heterogeneity & Entropy).

## 1. Tracking Individual Agents (Source Data)

- **Method:** We track every agent's decision at every time step (Year).
- **Source File:** `simulation_log.csv` (Located in result folders).
- **Audit Check:**
  - Agent IDs are persistent (e.g., `agent_001` to `agent_100`).
  - Decisions are logged annually.
  - The state `relocated` is tracked to filter out inactive agents.

## 2. Statistical Distributions (Step-by-Step Probability)

- **Method:** For each Year/Group, we count the exact frequency of every action taken by the _Active Population_.
- **File:** [`detailed_distribution_audit.csv`](detailed_distribution_audit.csv)
- **Columns:**
  - `Count`: Number of agents choosing this action.
  - `Probability`: $p_i = Count / N_{active}$
  - `Entropy_Contribution`: $-p_i \log_2 p_i$

## 3. Entropy Calculation (Final Metric)

- **Method:** Summing the entropy contributions to get the total Shannon Entropy ($H$).
- **File:** [`summary_entropy_audit.csv`](summary_entropy_audit.csv)
- **Formula:** $H = \sum \text{Entropy\_Contribution}$

## 4. Anomaly Verification (8B Group A, Year 9)

- User Question: "Why is Entropy 0.00 but behavior seems different?"
- **Audit Finding:**
  - Raw Count: 89 Elevation, **3 Relocation**.
  - Corrected Entropy: **0.2073**.
  - _Correction applied in `summary_entropy_audit.csv`._

---

**How to Reproduce:**
Run `python examples/single_agent/analysis/export_detailed_probabilities.py` to regenerate the detailed distribution file from raw logs.
