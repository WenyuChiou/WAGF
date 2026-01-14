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

![Comparison](old_vs_window_vs_humancentric_3x3.png)

*Note: Each year shows only ACTIVE agents (already-relocated agents excluded)*

---

## Model-Specific Analysis

### Gemma 3 (4B)

| Metric | Baseline | Window | Human-Centric |
|--------|----------|--------|---------------|
| Final Relocations | 64 | 0 | 0 |
| Significant Diff (Window) | N/A | p=0.0000 (**Yes**) | - |

**Flood Year Response:**

| Year | Baseline Reloc | Window Reloc | Human-Centric Reloc |
|------|----------------|--------------|---------------------|
| 3 | 5 | 0 | 0 |
| 4 | 7 | 0 | 0 |
| 9 | 14 | 0 | 0 |

**Behavioral Root Cause:**
- **Optimism Bias**: High perceived coping (Medium+) masks threat perception.
- **Validation Stats**: 0 blocks on inaction.
- **Threat Perception**: High threat perceived 0 times (often overridden by coping).

---

### Llama 3.2 (3B)

| Metric | Baseline | Window | Human-Centric |
|--------|----------|--------|---------------|
| Final Relocations | 64 | 27 | 39 |
| Significant Diff (Window) | N/A | p=0.0000 (**Yes**) | - |

**Flood Year Response:**

| Year | Baseline Reloc | Window Reloc | Human-Centric Reloc |
|------|----------------|--------------|---------------------|
| 3 | 5 | 5 | 1 |
| 4 | 7 | 4 | 5 |
| 9 | 14 | 3 | 4 |

**Behavioral Root Cause:**
- Window memory decreased relocations by 37.
- Model rarely appraised threat as `High`, avoiding governance triggers.

---

### DeepSeek-R1 (8B)

| Metric | Baseline | Window | Human-Centric |
|--------|----------|--------|---------------|
| Final Relocations | 64 | 0 | 0 |
| Significant Diff (Window) | N/A | p=N/A (No) | - |

**Flood Year Response:**

| Year | Baseline Reloc | Window Reloc | Human-Centric Reloc |
|------|----------------|--------------|---------------------|
| 3 | 5 | N/A | N/A |
| 4 | 7 | N/A | N/A |
| 9 | 14 | N/A | N/A |

**Behavioral Root Cause:**
- Window memory decreased relocations by 64.
- Model rarely appraised threat as `High`, avoiding governance triggers.

---

## Validation & Governance Impact

| Model | Memory | Total Traces | Retries | Failed | Parse Warnings |
|-------|--------|--------------|---------|--------|----------------|
| Gemma 3 (4B) | Window | 1000 | 0 | 0 | 0 |
| Gemma 3 (4B) | Human-Centric | 1000 | 0 | 0 | 0 |
| Llama 3.2 (3B) | Window | 1000 | 271 | 40 | 0 |
| Llama 3.2 (3B) | Human-Centric | 1000 | 203 | 25 | 0 |

