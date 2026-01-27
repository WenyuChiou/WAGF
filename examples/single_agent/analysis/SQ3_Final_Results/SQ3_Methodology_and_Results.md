# SQ3 Methodology & Results: The Cost of Governance

_Analysis of Operational Efficiency and System Stability_

## 1. Metric Definitions & Formulas

To strictly quantify the "Cost" of governance, we defined two primary metrics: **Efficiency** (Intervention Rate) and **Stability** (Flip-Flop Rate).

### A. Intervention Rate ($R_{intv}$)

- **Goal:** Measure the "Heavy-handedness" of the framework.
- **Formula:**
  $$ R*{intv} = \frac{N*{interventions}}{N\_{total_steps}} $$
- **Data Source:** `household_traces.jsonl`
  - Count distinct steps where `retry_count > 0` OR `failed_rules != []`.

### B. Flip-Flop Rate (Decision Instability) ($R_{ff}$)

- **Goal:** Measure the "Cognitive Jitter" or lack of conviction in the agent.
- **Formula:**
  $$ R*{ff} = \frac{\sum*{t=1}^{T} (Action*t \neq Action*{t-1})}{N\_{active_years}} $$
- **Logic:**
  1.  Sort logs by `Agent_ID` and `Year`.
  2.  For each agent, compare Year $N$ vs Year $N-1$.
  3.  If Action changes (e.g., "DoNothing" -> "Insurance"), count as 1 Flip.
  4.  Exclude agents who have `Relocated` (as they leave the system).

---

## 2. Calculated Results (The Data)

| Model Scale | Group              | Intervention Rate (Efficiency) | Flip-Flop Rate (Stability) | Parse Errors |
| :---------- | :----------------- | :----------------------------- | :------------------------- | :----------- |
| **1.5B**    | **Ungoverned (A)** | 0.0%                           | 55.47%                     | 0%           |
| **1.5B**    | **Governed (B)**   | **31.7%**                      | **61.05%**                 | **0%**       |
| **8B**      | **Governed (B)**   | 2.4%                           | 44.55%                     | 0%           |
| **14B**     | **Governed (B)**   | 0.0%                           | 41.98%                     | 0%           |
| **32B**     | **Group A**        | **0.0%**                       | **29.05%**                 | **0%**       |

## 3. Analysis & Interpretation

### Finding 1: The "Intelligence-Efficiency" Inverse Law

- **Observation:** Intervention Rate drops exponentially as model size increases (31.7% -> 2.4% -> 0%).
- **Conclusion:** The Framework is **Adaptive**. It imposes high costs on weak agents but near-zero costs on strong agents. It does not "tax the rich" (smart models).

### Finding 2: The "Alignment Tax" (Stability Trade-off)

- **Observation:** The Governed 1.5B model (61% FF) is significantly less stable than the 32B Benchmark (29% FF).
- **Comparison:** Governance _saved_ the 1.5B agents from Panic (SQ1/SQ2), but it left them in a state of **High Anxiety** (High Jitter).
- **The Trade-off:** We traded **Tranquility** (Low FF) for **Survival** (High Lifespan). The agent is alive, but it is "nervous."

## 4. Conclusion for SQ3

The Governed Broker Framework proves to be:

1.  **Surgically Precise:** Zero parse errors, adaptive intervention levels.
2.  **Costly in Stability:** It induces higher decision variance in weaker models as they struggle to align their impulses with the rules.
3.  **Net Positive:** This "Tax" is acceptable because the alternative is "Death" (Panic Mode Collapse).
