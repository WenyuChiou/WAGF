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

*Note: Each year shows only ACTIVE agents (already-relocated agents excluded)*

---

## Model-Specific Analysis

### Gemma 3 (4B)

| Metric | Baseline | Window | Human-Centric |
|--------|----------|--------|---------------|
| Final Relocations | 6 | 6 | 0 |
| Significant Diff (Window) | N/A | **Yes** (p=0.0001) | - |
| *Test Type* | | *Chi-Square (5x2 Full Dist)* | |

**Behavioral Shifts (Window vs Baseline):**

| Adaptation State | Baseline | Window | Delta |
|------------------|----------|--------|-------|
| Do Nothing | 609 | 531 | ⬇️ -78 |
| Only Flood Insurance | 47 | 24 | ⬇️ -23 |
| Only House Elevation | 296 | 373 | ⬆️ +77 |
| Both Flood Insurance and House Elevation | 40 | 24 | ⬇️ -16 |

**Flood Year Response (Relocations):**

| Year | Baseline | Window | Human-Centric |
|------|----------|--------|---------------|
| 3 | 0 | 6 | N/A |
| 4 | 0 | 0 | N/A |
| 9 | 2 | 0 | N/A |

**Behavioral Insight:**
- **Rational Convergence**: Previously exhibited static behavior (fixed 2025), now shows a clear learning curve: Damage -> Adaptation -> Safety. By Year 9, 64% of agents have efficiently adapted (Elevated/Relocated), returning to 'Do Nothing' only because they are safe.
- **Trust Dynamics**: 0 triggers because the model acts rationally. It elevates when threat is high (Outcome: APPROVED) and does nothing when threat is low (Outcome: APPROVED).

---

### Llama 3.2 (3B)

| Metric | Baseline | Window | Human-Centric |
|--------|----------|--------|---------------|
| Final Relocations | 95 | 86 | 0 |
| Significant Diff (Window) | N/A | **Yes** (p=0.0000) | - |
| *Test Type* | | *Chi-Square (5x2 Full Dist)* | |

**Behavioral Shifts (Window vs Baseline):**

| Adaptation State | Baseline | Window | Delta |
|------------------|----------|--------|-------|
| Do Nothing | 195 | 182 | ⬇️ -13 |
| Only Flood Insurance | 28 | 21 | ⬇️ -7 |
| Only House Elevation | 153 | 250 | ⬆️ +97 |
| Both Flood Insurance and House Elevation | 47 | 22 | ⬇️ -25 |
| Relocate | 95 | 86 | ⬇️ -9 |

**Flood Year Response (Relocations):**

| Year | Baseline | Window | Human-Centric |
|------|----------|--------|---------------|
| 3 | 21 | 16 | N/A |
| 4 | 18 | 18 | N/A |
| 9 | 11 | 6 | N/A |

**Behavioral Insight:**
- Window memory reduced relocations by 9. Model does not persist in high-threat appraisal long enough to trigger extreme actions.

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

> **Note**: Correction success is tracked across a **maximum of 3 retry attempts** per blocking event.

| Model | Blocking Events | Solved (T1/T2/T3) | Failed (3 tries) | Correction Success |
|-------|-----------------|-------------------|------------------|--------------------|
| Gemma 3 (4B) | 0 | 0 (0/0/0) | 0 | 0.0% |
| Llama 3.2 (3B) | 265 | 246 (170/55/21) | 19 | 92.8% |
| GPT-OSS | 0 | 0 (0/0/0) | 0 | 0.0% |

---

### Gemma 3 (4B) Governance

| Memory | Blocking Events | Solved (T1/T2/T3) | Failed | Warnings |
|--------|-----------------|-------------------|--------|----------|
| Window | 0 | 0 (0/0/0) | 0 | 0 |
| Human-Centric | 0 | 0 (0/0/0) | 0 | 0 |

**Qualitative Reasoning Analysis:**

| Appraisal | Proposed Action | Raw Reasoning excerpt | Outcome |
|---|---|---|---|
| **High** | Elevate House | "Given my past flooding... I perceive a high threat... Elevating the house offers the best long-term protection." | **APPROVED** |
| **High** | Relocate | "Given previous flood damage... relocating offers the most substantial protection." | **APPROVED** |

> **Insight**: **Rational Convergence**. The model correctly identifies high threats from memory (unlike previous versions) and takes appropriate high-cost actions without needing governance intervention.

**Rule Trigger Analysis (Window Memory):**

> **Zero Triggers**: No governance rules were triggered. The model displayed **Rational Convergence**, appropriately taking high-cost actions when threats were high (allowed) and remaining inactive when threats were low (allowed).

### Llama 3.2 (3B) Governance

| Memory | Blocking Events | Solved (T1/T2/T3) | Failed | Warnings |
|--------|-----------------|-------------------|--------|----------|
| Window | 265 | 246 (170/55/21) | 19 | 0 |
| Human-Centric | 0 | 0 (0/0/0) | 0 | 0 |

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
| `elevation_threat_low` | 146 | 145 | 1 | **99.3%** | High correction success (Compliant). |
| `relocation_threat_low` | 60 | 60 | 0 | **100.0%** | High correction success (Compliant). |
| `relocation_threat_low\|elevation_threat_low` | 16 | 11 | 5 | **68.8%** | Cost Sensitive (Compliant). |
| `elevation_threat_low\|relocation_threat_low` | 13 | 9 | 4 | **69.2%** | Cost Sensitive (Compliant). |
| `CP_LABEL\|elevation_threat_low` | 9 | 9 | 0 | **100.0%** | High correction success (Compliant). |
| `elevation_threat_low\|CP_LABEL\|relocation_threat_low` | 7 | 6 | 1 | **85.7%** | High correction success (Compliant). |
| `relocation_threat_low\|elevation_threat_low\|CP_LABEL` | 4 | 1 | 3 | **25.0%** | Action Bias (Stubborn Elevation). |
| `relocation_threat_low\|CP_LABEL` | 2 | 2 | 0 | **100.0%** | High correction success (Compliant). |
| `CP_LABEL\|relocation_threat_low\|elevation_threat_low` | 2 | 0 | 2 | **0.0%** | Low correction success (Stubborn). |
| `elevation_threat_low\|relocation_threat_low\|CP_LABEL` | 2 | 1 | 1 | **50.0%** | Mixed results. |
| `CP_LABEL\|relocation_threat_low` | 1 | 1 | 0 | **100.0%** | High correction success (Compliant). |
| `TP_LABEL` | 1 | 1 | 0 | **100.0%** | High correction success (Compliant). |
| `elevation_threat_low\|relocation_threat_low\|Unknown` | 1 | 0 | 1 | **0.0%** | Low correction success (Stubborn). |
| `elevation_threat_low\|CP_LABEL` | 1 | 0 | 1 | **0.0%** | Low correction success (Stubborn). |

**Reasoning Analysis on Frequent Rejections:**

- **Rule**: `elevation_threat_low` (Failed 19 times)
- **Rule**: `relocation_threat_low` (Failed 17 times)
- **Rule**: `CP_LABEL` (Failed 8 times)


### GPT-OSS Governance

| Memory | Blocking Events | Solved (T1/T2/T3) | Failed | Warnings |
|--------|-----------------|-------------------|--------|----------|
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


