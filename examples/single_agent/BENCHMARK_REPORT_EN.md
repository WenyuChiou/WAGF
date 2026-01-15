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
| Significant Diff (Window) | N/A | p=0.0000 (**Yes**) | - |
| *Test Type* | | *Chi-Square (5x2 Full Dist)* | |

**Behavioral Shifts (Window vs Baseline):**
- ⬆️ **Do Nothing**: 609 -> 734 (+125)
- ⬆️ **Only Flood Insurance**: 47 -> 114 (+67)
- ⬇️ **Only House Elevation**: 296 -> 135 (-161)
- ⬇️ **Both Flood Insurance and House Elevation**: 40 -> 17 (-23)
- ⬇️ **Relocate**: 6 -> 0 (-6)

**Flood Year Response (Relocations):**

| Year | Baseline | Window | Human-Centric |
|------|----------|--------|---------------|
| 3 | 0 | 0 | 0 |
| 4 | 0 | 0 | 0 |
| 9 | 2 | 0 | 0 |

**Behavioral Insight:**
- **Optimism Bias**: High perceived coping (Medium+) masks threat perception.
- **Passive Compliance**: 0 rejections because it defaults to 'Do Nothing', which is allowed under low threat.

---

### Llama 3.2 (3B)

| Metric | Baseline | Window | Human-Centric |
|--------|----------|--------|---------------|
| Final Relocations | 95 | 9 | 6 |
| Significant Diff (Window) | N/A | p=0.0000 (**Yes**) | - |
| *Test Type* | | *Chi-Square (5x2 Full Dist)* | |

**Behavioral Shifts (Window vs Baseline):**
- ⬇️ **Do Nothing**: 195 -> 145 (-50)
- ⬆️ **Only Flood Insurance**: 28 -> 68 (+40)
- ⬆️ **Only House Elevation**: 153 -> 624 (+471)
- ⬆️ **Both Flood Insurance and House Elevation**: 47 -> 117 (+70)
- ⬇️ **Relocate**: 95 -> 9 (-86)

**Flood Year Response (Relocations):**

| Year | Baseline | Window | Human-Centric |
|------|----------|--------|---------------|
| 3 | 21 | 1 | 0 |
| 4 | 18 | 0 | 0 |
| 9 | 11 | 0 | 0 |

**Behavioral Insight:**
- Window memory reduced relocations by 86. Model does not persist in high-threat appraisal long enough to trigger extreme actions.

---

### GPT-OSS

| Metric | Baseline | Window | Human-Centric |
|--------|----------|--------|---------------|
| Final Relocations | 0 | 0 | 0 |
| Significant Diff (Window) | N/A | p=0.0000 (**Yes**) | - |
| *Test Type* | | *Chi-Square (5x2 Full Dist)* | |

**Behavioral Shifts (Window vs Baseline):**
- ⬆️ **Do Nothing**: 37 -> 151 (+114)
- ⬆️ **Only Flood Insurance**: 48 -> 95 (+47)
- ⬆️ **Only House Elevation**: 457 -> 630 (+173)
- ⬇️ **Both Flood Insurance and House Elevation**: 458 -> 124 (-334)

**Flood Year Response (Relocations):**

| Year | Baseline | Window | Human-Centric |
|------|----------|--------|---------------|
| 3 | 0 | 0 | N/A |
| 4 | 0 | 0 | N/A |
| 9 | 0 | 0 | N/A |

**Behavioral Insight:**
- No significant change in relocation behavior.

---

## Validation & Governance Details

### Gemma 3 (4B) Governance

| Memory | Triggers | Retries | Failed | Parse Warnings |
|--------|----------|---------|--------|----------------|
| Window | 0 | 0 | 0 | 0 |
| Human-Centric | 0 | 0 | 0 | 0 |

> **Zero Triggers**: This model is 'Passive Compliant'. It tends to choose 'Do Nothing' or low-cost actions when threat is low, thus never triggering the *Action vs Logic* blocked rules.

### Llama 3.2 (3B) Governance

| Memory | Triggers | Retries | Failed | Parse Warnings |
|--------|----------|---------|--------|----------------|
| Window | 515 | 287 | 228 | 0 |
| Human-Centric | 299 | 155 | 144 | 0 |

**Rule Trigger Analysis (Window Memory):**

| Rule | Count | Compliance (Fixed) | Rejection (Failed) | Success Rate | Insight |
|---|---|---|---|---|---|
| `elevation_threat_low` | 273 | 52 | 221 | **19.0%** | Low correction success (Stubborn). |
| `relocation_threat_low` | 10 | 6 | 4 | **60.0%** | Cost Sensitive (Compliant). |
| `elevation_threat_low|relocation_threat_low` | 4 | 1 | 3 | **25.0%** | Action Bias (Stubborn Elevation). |

### GPT-OSS Governance

| Memory | Triggers | Retries | Failed | Parse Warnings |
|--------|----------|---------|--------|----------------|
| Window | 0 | 0 | 0 | 0 |

> **Zero Triggers**: This model is 'Passive Compliant'. It tends to choose 'Do Nothing' or low-cost actions when threat is low, thus never triggering the *Action vs Logic* blocked rules.


