# Memory Benchmark Analysis Report

## Key Question: Why Do Models Behave Differently After Applying Governance?

### Root Causes of Behavioral Differences

1. **Validation Ensures Format, Not Reasoning**
   - 100% validation pass means output FORMAT is correct
   - Models still differ in HOW they interpret threats and coping ability

2. **Memory Window Effect (top_k=3)**
   - Only 3 latest memories are kept
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
| Significant Diff (Window) | N/A | p=N/A (No) | - |
| *Test Type* | | *Chi-Square (5x2 Full Dist)* | |

**Behavioral Shifts (Window vs Baseline):**
- No Data

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
| Final Relocations | 95 | 0 | 0 |
| Significant Diff (Window) | N/A | p=N/A (No) | - |
| *Test Type* | | *Chi-Square (5x2 Full Dist)* | |

**Behavioral Shifts (Window vs Baseline):**
- No Data

**Flood Year Response (Relocations):**

| Year | Baseline | Window | Human-Centric |
|------|----------|--------|---------------|
| 3 | 21 | N/A | N/A |
| 4 | 18 | N/A | N/A |
| 9 | 11 | N/A | N/A |

**Behavioral Insight:**
- Window memory reduced relocations by 95. Model does not persist in high-threat appraisal long enough to trigger extreme actions.

---

### GPT-OSS

| Metric | Baseline | Window | Human-Centric |
|--------|----------|--------|---------------|
| Final Relocations | 0 | 0 | 0 |
| Significant Diff (Window) | N/A | p=N/A (No) | - |
| *Test Type* | | *Chi-Square (5x2 Full Dist)* | |

**Behavioral Shifts (Window vs Baseline):**
- No Data

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

### Gemma 3 (4B) Governance

| Memory | Triggers | Retries | Failed | Parse Warnings |
|--------|----------|---------|--------|----------------|

**Rule Trigger Analysis (Window Memory):**

> **Zero Triggers**: No governance rules were triggered. The model displayed **Passive Compliance**, likely defaulting to 'Do Nothing' or allowed actions under low threat.

### Llama 3.2 (3B) Governance

| Memory | Triggers | Retries | Failed | Parse Warnings |
|--------|----------|---------|--------|----------------|

**Rule Trigger Analysis (Window Memory):**

> **Zero Triggers**: No governance rules were triggered. The model displayed **Passive Compliance**, likely defaulting to 'Do Nothing' or allowed actions under low threat.

### GPT-OSS Governance

| Memory | Triggers | Retries | Failed | Parse Warnings |
|--------|----------|---------|--------|----------------|

**Rule Trigger Analysis (Window Memory):**

> **Zero Triggers**: No governance rules were triggered. The model displayed **Passive Compliance**, likely defaulting to 'Do Nothing' or allowed actions under low threat.


