# Supplementary Table S5: Behavioural Diversity Sensitivity to Normalization Specification

## Composite-Action Treatment Scenarios

Ungoverned agents in the flood domain occasionally selected composite actions (simultaneously purchasing insurance and elevating the structure). This behaviour was not available in the governed interface, creating an asymmetry in the effective action space (k = 5 for ungoverned vs k = 4 for governed). Because strategy diversity = H / log₂(k), different k values produce non-comparable normalizations. We tested four specifications:

| Scenario | Ungoverned k | Governed k | Composite treatment |
|----------|:---:|:---:|---|
| S1 (asymmetric) | 5 | 4 | Counted as 5th distinct action |
| S2 (merge) | 4 | 4 | Remapped to "elevate_house" |
| **S3 (uniform-5)** | 5 | 5 | Same normalization for all |
| **S4 (split, primary)** | 4 | 4 | Split into insurance + elevation decisions |

## Composite Action Frequency by Model

| Model | Composite % (ungoverned) | Interpretation |
|-------|:---:|---|
| Gemma-3 4B | 2.9% | Rare — low instruction-following artifact |
| Gemma-3 12B | 79.0% | Dominant — model defaults to comprehensive response |
| Gemma-3 27B | 2.6% | Rare |
| Ministral 3B | 9.5% | Moderate |
| Ministral 8B | 10.3% | Moderate |
| Ministral 14B | 59.0% | Frequent — hedging behaviour |

The bimodal distribution (models either <10% or >59%) suggests composite selection reflects model-specific instruction-following tendencies rather than a meaningful behavioural choice.

## Sensitivity Results: Per-Model Scaffolding Direction

| Model | S1 (k=5/4) | S2 (merge) | S3 (k=5/5) | S4 (split) |
|-------|:---:|:---:|:---:|:---:|
| Gemma-3 4B | **+0.219** | **+0.191** | **+0.115** | **+0.164** |
| Gemma-3 12B | +0.046 | +0.002 | −0.021 | **−0.150** |
| Gemma-3 27B | **+0.065** | +0.014 | −0.029 | +0.007 |
| Ministral 3B | **+0.161** | **+0.252** | **+0.060** | **+0.116** |
| Ministral 8B | **−0.094** | **−0.125** | **−0.181** | **−0.098** |
| Ministral 14B | +0.013 | **+0.240** | **−0.085** | **+0.058** |

*Bold indicates |delta| > 0.05 (scaffolding or reversal). Positive = governance increases strategy diversity; negative = governance decreases strategy diversity.*

## Sensitivity Results: Pooled Statistics

| Scenario | Scaffolding (n/6) | Mean Δ | Bootstrap 95% CI | CI excludes 0? |
|----------|:---:|:---:|:---:|:---:|
| S1: k_ungov=5, k_gov=4 | 3/6 | +0.068 | [−0.010, +0.148] | No |
| S2: k=4, both→elevate | 3/6 | +0.096 | [−0.018, +0.202] | No |
| S3: k=5 for all | 2/6 | −0.024 | [−0.100, +0.049] | No |
| S4: k=4, split (primary) | 2/6 | +0.047 | [−0.064, +0.172] | No |

## Key Findings

1. **Robust per-model patterns**: Gemma-3 4B and Ministral 3B show scaffolding under all four specifications. Ministral 8B shows reversal under all four. The within-model direction is stable; the across-model pattern varies.

2. **Pooled effect not significant**: No specification produces a 95% CI excluding zero. The flood domain scaffolding effect should be interpreted as model-dependent, not as a general population-level finding.

3. **Primary specification justification (S4)**: k = 4 with split treats composite actions informationally (preserving both constituent decisions) while using a consistent normalization constant. This avoids both (a) rewarding an LLM artifact as a distinct behavioural category and (b) discarding information by merging composites into a single action.
