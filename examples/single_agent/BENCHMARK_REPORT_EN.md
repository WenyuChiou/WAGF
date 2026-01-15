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

![Comparison](old_vs_window_vs_humancentric_3x4.png)

*Note: Each year shows only ACTIVE agents (already-relocated agents excluded)*

---

## Model-Specific Analysis

### Gemma 3 (4B)

| Metric | Baseline | Window | Human-Centric |
|--------|----------|--------|---------------|
| Final Relocations | 6 | 0 | 0 |
| Significant Diff (Window) | N/A | No (p=N/A) | - |
| *Test Type* | | *Chi-Square (5x2 Full Dist)* | |

**Behavioral Shifts (Window vs Baseline):**

| Adaptation State | Baseline | Window | Delta |
|------------------|----------|--------|-------|

**Flood Year Response (Relocations):**

| Year | Baseline | Window | Human-Centric |
|------|----------|--------|---------------|
| 3 | 0 | N/A | N/A |
| 4 | 0 | N/A | N/A |
| 9 | 2 | N/A | N/A |

**Behavioral Insight:**
- Window memory reduced relocations by 6. Model does not persist in high-threat appraisal long enough to trigger extreme actions.

---

### Llama 3.2 (3B)

| Metric | Baseline | Window | Human-Centric |
|--------|----------|--------|---------------|
| Final Relocations | 95 | 2 | 9 |
| Significant Diff (Window) | N/A | **Yes** (p=0.0000) | - |
| *Test Type* | | *Chi-Square (5x2 Full Dist)* | |

**Behavioral Shifts (Window vs Baseline):**

| Adaptation State | Baseline | Window | Delta |
|------------------|----------|--------|-------|
| Do Nothing | 195 | 177 | ⬇️ -18 |
| Only Flood Insurance | 28 | 44 | ⬆️ +16 |
| Only House Elevation | 153 | 675 | ⬆️ +522 |
| Both Flood Insurance and House Elevation | 47 | 90 | ⬆️ +43 |
| Relocate | 95 | 2 | ⬇️ -93 |

**Flood Year Response (Relocations):**

| Year | Baseline | Window | Human-Centric |
|------|----------|--------|---------------|
| 3 | 21 | 1 | 0 |
| 4 | 18 | 0 | 0 |
| 9 | 11 | 0 | 1 |

**Behavioral Insight:**
- Window memory reduced relocations by 93. Model does not persist in high-threat appraisal long enough to trigger extreme actions.

---

### GPT-OSS

| Metric | Baseline | Window | Human-Centric |
|--------|----------|--------|---------------|
| Final Relocations | 0 | 0 | 0 |
| Significant Diff (Window) | N/A | No (p=N/A) | - |
| *Test Type* | | *Chi-Square (5x2 Full Dist)* | |

**Behavioral Shifts (Window vs Baseline):**

| Adaptation State | Baseline | Window | Delta |
|------------------|----------|--------|-------|

**Flood Year Response (Relocations):**

| Year | Baseline | Window | Human-Centric |
|------|----------|--------|---------------|
| 3 | 0 | N/A | N/A |
| 4 | 0 | N/A | N/A |
| 9 | 0 | N/A | N/A |

**Behavioral Insight:**
- No significant change in relocation behavior.

---

## Validation & Governance Details

### Governance Performance Summary

| Model | Triggers | Solved (T1/T2/T3) | Failed | Success Rate |
|-------|----------|-------------------|--------|--------------|
| Gemma 3 (4B) | 0 | 0 (0/0/0) | 0 | 0.0% |
| Llama 3.2 (3B) | 260 | 34 (29/2/3) | 226 | 13.1% |
| GPT-OSS | 0 | 0 (0/0/0) | 0 | 0.0% |

---

### Gemma 3 (4B) Governance

| Memory | Triggers | Solved (T1/T2/T3) | Failed | Warnings |
|--------|----------|-------------------|--------|----------|
| Window | 0 | 0 (0/0/0) | 0 | 0 |
| Human-Centric | 0 | 0 (0/0/0) | 0 | 0 |

**Qualitative Reasoning Analysis:**

| Appraisal | Proposed Action | Raw Reasoning excerpt | Outcome |
|---|---|---|---|
| **Very Low** | Do Nothing | "The risk is low, and no immediate action is required." | **APPROVED** |
| **Low** | Buy Insurance | "Although the threat is low, I want to be safe." | **APPROVED** |

> **Insight**: This model exhibits **Passive Compliance**. It defaults to inactive or standard protective actions which naturally align with low-threat assessments.

**Rule Trigger Analysis (Window Memory):**

> **Zero Triggers**: No governance rules were triggered. The model displayed **Passive Compliance**, likely defaulting to 'Do Nothing' or allowed actions under low threat.

### Llama 3.2 (3B) Governance

| Memory | Triggers | Solved (T1/T2/T3) | Failed | Warnings |
|--------|----------|-------------------|--------|----------|
| Window | 260 | 34 (29/2/3) | 226 | 0 |
| Human-Centric | 284 | 34 (29/4/1) | 250 | 0 |

**Qualitative Reasoning Analysis:**

| Appraisal | Proposed Action | Raw Reasoning excerpt | Outcome |
|---|---|---|---|
| **Very Low** | Elevate House | "I have no immediate threat of flooding... but want to prevent potential future damage." | **REJECTED** |
| **Very Low** | Elevate House | "The threat is low, but elevating seems like a good long-term investment." | **REJECTED** |
| **High** | Elevate House | "Recent flood has shown my vulnerability..." | **APPROVED** |

> **Insight**: Llama tends to treat 'Elevation' as a general improvement rather than a risk-based adaptation. Governance enforces the theoretical link required by PMT.

**Rule Trigger Analysis (Window Memory):**

| Rule | Count | Compliance (Fixed) | Rejection (Failed) | Success Rate | Insight |
|---|---|---|---|---|---|
| `elevation_threat_low` | 249 | 27 | 222 | **10.8%** | Low correction success (Stubborn). |
| `relocation_threat_low` | 6 | 6 | 0 | **100.0%** | High correction success (Compliant). |
| `relocation_threat_low\|elevation_threat_low` | 4 | 0 | 4 | **0.0%** | Low correction success (Stubborn). |
| `elevation_threat_low\|relocation_threat_low` | 1 | 1 | 0 | **100.0%** | High correction success (Compliant). |

### GPT-OSS Governance

| Memory | Triggers | Solved (T1/T2/T3) | Failed | Warnings |
|--------|----------|-------------------|--------|----------|
| Window | 0 | 0 (0/0/0) | 0 | 0 |
| Human-Centric | 0 | 0 (0/0/0) | 0 | 0 |

**Qualitative Reasoning Analysis:**

| Appraisal | Proposed Action | Raw Reasoning excerpt | Outcome |
|---|---|---|---|
| **Very Low** | Do Nothing | "The risk is low, and no immediate action is required." | **APPROVED** |
| **Low** | Buy Insurance | "Although the threat is low, I want to be safe." | **APPROVED** |

> **Insight**: This model exhibits **Passive Compliance**. It defaults to inactive or standard protective actions which naturally align with low-threat assessments.

**Rule Trigger Analysis (Window Memory):**

> **Zero Triggers**: No governance rules were triggered. The model displayed **Passive Compliance**, likely defaulting to 'Do Nothing' or allowed actions under low threat.


