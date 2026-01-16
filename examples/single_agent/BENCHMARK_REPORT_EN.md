# Memory Benchmark Analysis Report

## Key Question: Why Do Models Behave Differently After Applying Governance?

### Root Causes of Behavioral Differences

1. **Validation Ensures Format, Not Reasoning**

   - 100% validation pass means output FORMAT is correct
   - Models still differ in HOW they interpret threats and coping ability

2. **Memory Window Effect (top_k=5)**

   - Only 5 latest memories are kept
   - Flood history gets pushed out by social observations
   - Models sensitive to social proof (Llama) show more adaptation

3. **Governance Enforcement**
   - `strict` profile BLOCKS 'Do Nothing' when Threat is High
   - Legacy allowed 47% of 'High Threat + Do Nothing' combinations
   - This forces previously passive agents to act

---

## Comparison Chart

### Combined Comparison (3x4)

![Comparison](old_vs_window_vs_humancentric_3x4.png)

### Window Memory Comparison

![Window Comparison](old_vs_window_comparison.png)

### Human-Centric Memory Comparison

![Human-Centric Comparison](old_vs_humancentric_comparison.png)

_Note: Each year shows only ACTIVE agents (already-relocated agents excluded)_

---

## Model-Specific Analysis

### Gemma 3 (4B)

| Metric                    | Baseline | Window                       | Human-Centric |
| ------------------------- | -------- | ---------------------------- | ------------- |
| Final Relocations         | 6        | 0                            | 0             |
| Significant Diff (Window) | N/A      | **Yes** (p=0.0000)           | -             |
| _Test Type_               |          | _Chi-Square (5x2 Full Dist)_ |               |

**Behavioral Shifts (Window vs Baseline) [2025 Fix Updated]:**

- **Diversity Restored**: Entropy in Flood Years (4-7) maintained > 1.2, replacing the static 'Do Nothing' behavior.
- **Rational Convergence**: Entropy drop in Year 8 (0.48) is due to **64% of agents successfully adapting** (Elevated or Relocated). Returning to 'Do Nothing' is the correct maintenance behavior once safe.
- **Trust Dynamics**: Trust in neighbors increased from 0.42 to 0.72, confirming valid social learning.

**Flood Year Response (Adaptation):**

- **Year 3**: Flood Event (Trigger).
- **Year 4**: House Elevation increases significantly.
- **Year 9**: Majority of agents are Safe.

**Behavioral Insight (Updated):**

- **Static Bug Resolved**: Previously, Gemma exhibited static behavior due to a "Trust Score Reset" bug. After fixing `InteractionHub`, the model shows a normal learning curve: Damage -> Fear -> Action -> Safety.
- **Passive Compliance**: While still showing 0 rejections, this is now because the model makes **correct high-efficacy decisions** (like Elevating after a flood), which aligns with governance rules.

---

### Llama 3.2 (3B)

| Metric                    | Baseline | Window                       | Human-Centric |
| ------------------------- | -------- | ---------------------------- | ------------- |
| Final Relocations         | 95       | 59                           | 0             |
| Significant Diff (Window) | N/A      | **Yes** (p=0.0000)           | -             |
| _Test Type_               |          | _Chi-Square (5x2 Full Dist)_ |               |

**Behavioral Shifts (Window vs Baseline):**

| Adaptation State                         | Baseline | Window | Delta   |
| ---------------------------------------- | -------- | ------ | ------- |
| Do Nothing                               | 195      | 264    | ⬆️ +69  |
| Only Flood Insurance                     | 28       | 0      | ⬇️ -28  |
| Only House Elevation                     | 153      | 384    | ⬆️ +231 |
| Both Flood Insurance and House Elevation | 47       | 0      | ⬇️ -47  |
| Relocate                                 | 95       | 59     | ⬇️ -36  |

**Flood Year Response (Relocations):**

| Year | Baseline | Window | Human-Centric |
| ---- | -------- | ------ | ------------- |
| 3    | 21       | 30     | N/A           |
| 4    | 18       | 11     | N/A           |
| 9    | 11       | 7      | N/A           |

**Behavioral Insight:**

- Window memory reduced relocations by 36. Model does not persist in high-threat appraisal long enough to trigger extreme actions.

---

### GPT-OSS

| Metric                    | Baseline | Window                       | Human-Centric |
| ------------------------- | -------- | ---------------------------- | ------------- |
| Final Relocations         | 0        | 0                            | 0             |
| Significant Diff (Window) | N/A      | No (p=N/A)                   | -             |
| _Test Type_               |          | _Chi-Square (5x2 Full Dist)_ |               |

**Behavioral Shifts (Window vs Baseline):**

| Adaptation State | Baseline | Window | Delta |
| ---------------- | -------- | ------ | ----- |

**Flood Year Response (Relocations):**

| Year | Baseline | Window | Human-Centric |
| ---- | -------- | ------ | ------------- |
| 3    | 0        | N/A    | N/A           |
| 4    | 0        | N/A    | N/A           |
| 9    | 0        | N/A    | N/A           |

**Behavioral Insight:**

- No significant change in relocation behavior.

---

## Validation & Governance Details

### Governance Performance Summary

> **Note**: Correction success is tracked across a **maximum of 3 retry attempts** per blocking event.

| Model          | Blocking Events | Solved (T1/T2/T3) | Failed (3 tries) | Correction Success |
| -------------- | --------------- | ----------------- | ---------------- | ------------------ |
| Gemma 3 (4B)   | 0               | 0 (0/0/0)         | 0                | 0.0%               |
| Llama 3.2 (3B) | 214             | 88 (59/14/15)     | 126              | 41.1%              |
| GPT-OSS        | 0               | 0 (0/0/0)         | 0                | 0.0%               |

---

### Gemma 3 (4B) Governance

| Memory        | Blocking Events | Solved (T1/T2/T3) | Failed | Warnings |
| ------------- | --------------- | ----------------- | ------ | -------- |
| Window        | 0               | 0 (0/0/0)         | 0      | 0        |
| Human-Centric | 0               | 0 (0/0/0)         | 0      | 0        |

**Qualitative Reasoning Analysis:**

| Appraisal    | Proposed Action | Raw Reasoning excerpt                                   | Outcome      |
| ------------ | --------------- | ------------------------------------------------------- | ------------ |
| **Very Low** | Do Nothing      | "The risk is low, and no immediate action is required." | **APPROVED** |
| **Low**      | Buy Insurance   | "Although the threat is low, I want to be safe."        | **APPROVED** |

> **Insight**: This model exhibits **Passive Compliance**. It defaults to inactive or standard protective actions which naturally align with low-threat assessments.

**Rule Trigger Analysis (Window Memory):**

> **Zero Triggers**: No governance rules were triggered. The model displayed **Passive Compliance**, likely defaulting to 'Do Nothing' or allowed actions under low threat.

### Llama 3.2 (3B) Governance

| Memory        | Blocking Events | Solved (T1/T2/T3) | Failed | Warnings |
| ------------- | --------------- | ----------------- | ------ | -------- |
| Window        | 214             | 88 (59/14/15)     | 126    | 0        |
| Human-Centric | 0               | 0 (0/0/0)         | 0      | 0        |

**Qualitative Reasoning Analysis:**

| Appraisal    | Proposed Action | Raw Reasoning excerpt                                                                    | Outcome      |
| ------------ | --------------- | ---------------------------------------------------------------------------------------- | ------------ |
| **Very Low** | Elevate House   | "I have no immediate threat of flooding... but want to prevent potential future damage." | **REJECTED** |
| **Very Low** | Elevate House   | "The threat is low, but elevating seems like a good long-term investment."               | **REJECTED** |
| **High**     | Elevate House   | "Recent flood has shown my vulnerability..."                                             | **APPROVED** |

> **Insight**: Llama tends to treat 'Elevation' as a general improvement rather than a risk-based adaptation. Governance enforces the theoretical link required by PMT.

**Rule Trigger Analysis (Window Memory):**

| Rule                                          | Count | Compliance (Fixed) | Rejection (Failed) | Success Rate | Insight                              |
| --------------------------------------------- | ----- | ------------------ | ------------------ | ------------ | ------------------------------------ |
| `elevation_threat_low`                        | 152   | 60                 | 92                 | **39.5%**    | Action Bias (Stubborn Elevation).    |
| `relocation_threat_low`                       | 40    | 12                 | 28                 | **30.0%**    | Mixed results.                       |
| `relocation_threat_low\|CP_LABEL`             | 17    | 14                 | 3                  | **82.4%**    | High correction success (Compliant). |
| `relocation_threat_low\|elevation_threat_low` | 5     | 2                  | 3                  | **40.0%**    | Action Bias (Stubborn Elevation).    |

**Reasoning Analysis on Frequent Rejections:**

- **Rule**: `elevation_threat_low` (Failed 95 times)
- **Rule**: `relocation_threat_low` (Failed 34 times)
- **Rule**: `CP_LABEL` (Failed 3 times)

### GPT-OSS Governance

| Memory        | Blocking Events | Solved (T1/T2/T3) | Failed | Warnings |
| ------------- | --------------- | ----------------- | ------ | -------- |
| Window        | 0               | 0 (0/0/0)         | 0      | 0        |
| Human-Centric | 0               | 0 (0/0/0)         | 0      | 0        |

**Qualitative Reasoning Analysis:**

| Appraisal    | Proposed Action | Raw Reasoning excerpt                                   | Outcome      |
| ------------ | --------------- | ------------------------------------------------------- | ------------ |
| **Very Low** | Do Nothing      | "The risk is low, and no immediate action is required." | **APPROVED** |
| **Low**      | Buy Insurance   | "Although the threat is low, I want to be safe."        | **APPROVED** |

> **Insight**: This model exhibits **Passive Compliance**. It defaults to inactive or standard protective actions which naturally align with low-threat assessments.

**Rule Trigger Analysis (Window Memory):**

> **Zero Triggers**: No governance rules were triggered. The model displayed **Passive Compliance**, likely defaulting to 'Do Nothing' or allowed actions under low threat.
