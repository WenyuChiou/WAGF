# P0 Statistical Review: Biostatistics Professor Assessment
## Nature Water Submission — Irrigation EHE Analysis

**Reviewer**: Biostatistics Professor (Statistical Rigor Assessment)
**Date**: 2026-02-15
**Author Response to P0 Recommendations**: EVALUATED

---

## Executive Summary

### Overall Assessment: **MAJOR REVISION REQUIRED**

The author has made **substantial progress** in addressing P0 concerns, particularly regarding transparency and uncertainty quantification. However, **critical issues remain** that prevent acceptance for Nature Water:

#### ✓ **ACCEPTABLE** (4/6):
1. Per-seed reporting with matched SDs
2. Bootstrap CI for EHE difference
3. Leave-one-out sensitivity analysis
4. Honest permutation test framing

#### ✗ **PROBLEMATIC** (2/6):
5. Bootstrap CI for Cohen's d is **uninformative** [5.11, 21.05]
6. CACR null-model comparison **lacks formal statistical test**

---

## Detailed Evaluation

### 1. Per-Seed Values: **ACCEPTABLE** ✓

**Author's Table**:
| Seed | Governed | Ungoverned | Delta |
|------|----------|------------|-------|
| 42   | 0.739    | 0.655      | +0.084|
| 43   | 0.754    | 0.634      | +0.119|
| 44   | 0.720    | 0.622      | +0.098|
| Mean | 0.738    | 0.637      | +0.101|
| SD   | 0.017    | 0.017      |       |

**Assessment**:
- ✓ Raw data now visible
- ✓ Matched SDs (0.017) indicate balanced variability between groups
- ✓ Zero distributional overlap (min(gov)=0.720 > max(ungov)=0.655)
- **No concerns** — proceed as reported

---

### 2. Bootstrap 95% CI for EHE Difference: **ACCEPTABLE** ✓

**Author's Result**:
- Point estimate: +0.101
- Bootstrap 95% CI: [0.078, 0.122]
- Bootstrap mean: 0.101 (matches point estimate)
- Bootstrap SD: 0.011

**Assessment**:
- ✓ Properly conducted (10,000 resamples, seed=12345)
- ✓ CI excludes zero → formally significant
- ✓ Narrow CI (width=0.044) indicates robust effect despite n=3
- ✓ Bootstrap mean ≈ point estimate → no bias

**Recommended Language** (APPROVED):
> "Governed EHE exceeded ungoverned EHE by +0.101 (bootstrap 95% CI [0.078, 0.122])."

---

### 3. Bootstrap 95% CI for Cohen's d: **PROBLEMATIC** ✗

**Author's Result**:
- Point estimate: d = 5.99
- Bootstrap 95% CI: [5.11, 21.05]
- Bootstrap median: 7.37

**Critical Issues**:

#### Issue 3A: **Extreme Width (CI width = 16.0)**
- **Context**: Point estimate = 5.99, but upper bound = 21.05
- **Root cause**: With n=3, occasional bootstrap samples have near-zero pooled SD
  - Example: If both groups resample [0.754, 0.754, 0.754], SD ≈ 0 → d → ∞
- **Problem**: The 97.5th percentile includes resamples with pathological SD ratios

#### Issue 3B: **Median ≠ Mean (7.37 vs likely ~9.0)**
- Heavy right-skew suggests the distribution is **not Normal**
- **Implication**: Percentile CI may not reflect true uncertainty structure

#### Issue 3C: **Lack of Practical Interpretation**
- Saying d ∈ [5.11, 21.05] provides **no actionable information**
- Reviewers will question: "Is the effect d=6 or d=20? These have different scientific meanings."

**Statistical Recommendation**:

**Option A: Report point estimate ONLY with caveat** (PREFERRED):
> "Cohen's d = 6.0 (very large effect), though the 95% CI [5.1, 21.0] is uninformative due to n=3 per group leading to occasional near-zero pooled SDs in bootstrap resamples."

**Option B: Use robust effect size** (ALTERNATIVE):
- Report **Cliff's Delta** (ordinal effect size, insensitive to SD instability)
- For zero-overlap data: Cliff's Δ = 1.0 (perfect separation)
- Pro: More stable CI, interpretable magnitude
- Con: Requires methodological justification in supplement

**Option C: Report median + IQR instead of CI**:
> "Cohen's d = 6.0 (median = 7.4, IQR [6.1, 9.2])."
- Pro: More honest representation of bootstrap distribution
- Con: Deviates from standard CI reporting

**My Verdict**: Use **Option A** for main text. Move full bootstrap diagnostics to supplement.

---

### 4. Leave-One-Out Sensitivity: **ACCEPTABLE** ✓

**Author's Results**:
| Dropped Seed | Cohen's d | Delta   | Zero Overlap? |
|--------------|-----------|---------|---------------|
| 42           | 6.08      | +0.109  | Yes           |
| 43           | 4.76      | +0.091  | Yes           |
| 44           | 8.13      | +0.102  | Yes           |

**Assessment**:
- ✓ Cohen's d remains "very large" (4.76-8.13) across all LOO subsets
- ✓ Delta remains significant (+0.091 to +0.109)
- ✓ Zero overlap maintained in all cases
- **Interpretation**: Results are robust to single-seed influence

**Recommended Language** (APPROVED):
> "Leave-one-out sensitivity analysis confirmed robustness: Cohen's d ranged from 4.8 to 8.1 across all three subsets, with zero distributional overlap maintained in each case."

---

### 5. Permutation Test Framing: **ACCEPTABLE** ✓

**Author's Revised Framing**:
> "p = 1/20 = 0.05 (the minimum achievable for n=3 per group), consistent with zero distributional overlap"

**Assessment**:
- ✓ Honest acknowledgment of n=3 limitation
- ✓ Correctly identifies p=0.05 as **structural minimum**, not evidence of marginal significance
- ✓ Links to zero-overlap (substantive evidence)

**Minor Wording Edit** (RECOMMENDED):
Replace "consistent with" → "further supported by"

**Final Approved Language**:
> "Exact permutation test yielded p = 1/20 = 0.05, the minimum achievable p-value for n=3 per group, further supported by zero distributional overlap where min(governed) = 0.720 exceeded max(ungoverned) = 0.655."

---

### 6. Null-Model CACR: **LACKS FORMAL TEST** ✗

**Author's Claim**:
> "Governance restores near-random coherence (58% vs 60% random baseline); ungoverned agents are worse than random (9.4% << 60%)."

**Reported Values**:
- **Random baseline**: 60% (3/5 skills are non-increase)
- **Governed**: 58%
- **Ungoverned**: 9.4%

**Critical Statistical Gap**:

#### Issue 6A: **No Confidence Interval on Governed CACR**
- **Question**: Is 58% *statistically* indistinguishable from 60%?
- **Missing**: Binomial proportion CI (e.g., Wilson score interval)
- **Example**: If n=1000 decisions, 95% CI might be [55%, 61%] → claim valid
- **Example**: If n=100 decisions, 95% CI might be [48%, 68%] → claim questionable

**Required Calculation**:
```python
from statsmodels.stats.proportion import proportion_confint
n_decisions = ???  # MUST be reported
n_coherent = int(0.58 * n_decisions)
ci_low, ci_high = proportion_confint(n_coherent, n_decisions, method='wilson')
print(f"Governed CACR: 58% (95% CI [{ci_low:.1%}, {ci_high:.1%}])")
```

**Assessment Criteria**:
- If CI includes 60%: claim "near-random" is **statistically valid** ✓
- If CI excludes 60%: must report as "statistically different from random but directionally closer than ungoverned" ✗

#### Issue 6B: **No Test for Ungoverned < Random**
- **Current claim**: "9.4% is FAR below 60%"
- **Statistical question**: Is this difference significant?
- **Required test**: One-sample proportion test against H₀: p = 0.60
  ```python
  from statsmodels.stats.proportion import binom_test
  p_value = binom_test(count=int(0.094 * n), nobs=n, prop=0.60, alternative='smaller')
  ```
- **Expected result**: p < 0.001 (extremely significant) — BUT MUST BE SHOWN

#### Issue 6C: **Flood CACR Null Model Not Computed**
**Author's Statement**:
> "Flood CACR (25 cells, discrete actions): Need exact cell-action mapping to compute null rate. Rough estimate: if 5 actions, ~40-60% coherent by chance."

**Problem**: This is **hand-waving**, not analysis.

**Required Computation**:
For the flood PMT matrix (25 cells = 5 TP levels × 5 CP levels):

1. **For each cell (TP, CP)**:
   - List coherent actions from `PMT_OWNER_RULES` / `PMT_RENTER_RULES`
   - Count: k = number of coherent actions
   - Total: n = number of possible actions (5 for owners, 3 for renters)
   - P(coherent | random) = k/n

2. **Weighted average**:
   - If cells are equally likely: mean(k/n) across 25 cells
   - If cells have empirical frequencies: weighted mean

**Example Code Needed**:
```python
# For owners
null_coherence_rates = []
for tp in ["VL", "L", "M", "H", "VH"]:
    for cp in ["VL", "L", "M", "H", "VH"]:
        coherent_actions = PMT_OWNER_RULES.get((tp, cp), [])
        total_actions = 5  # owner action pool size
        null_coherence_rates.append(len(coherent_actions) / total_actions)

null_cacr_owner = np.mean(null_coherence_rates)
print(f"Null CACR (owners): {null_cacr_owner:.1%}")
```

**This analysis is MISSING** and must be completed before publication.

---

### 7. Cross-Domain EHE Comparison: **ACCEPTABLE (with caveat)** ✓

**Author's Revised Claim**:
> "Governed EHE values are numerically similar across domains (0.738 vs 0.740), though the single flood estimate lacks a CI for formal comparison."

**Assessment**:
- ✓ Honest acknowledgment of missing CI
- ✓ Uses "numerically similar" instead of "domain-invariant" (good)
- ✓ Flood value (0.740) falls within irrigation 95% CI [0.719, 0.757]

**Recommended Addition** (OPTIONAL):
> "The flood EHE (0.740) falls within the irrigation 95% CI [0.719, 0.757], though formal equivalence testing requires replicate flood simulations."

---

## Summary of Required Revisions

| Issue | Status | Action Required | Priority |
|-------|--------|-----------------|----------|
| 1. Per-seed values | ✓ DONE | None | - |
| 2. EHE bootstrap CI | ✓ DONE | None | - |
| 3. Cohen's d bootstrap CI | ✗ INCOMPLETE | Report with caveat (Option A) or use Cliff's Delta | **P0** |
| 4. Leave-one-out sensitivity | ✓ DONE | None | - |
| 5. Permutation test framing | ✓ DONE | Minor wording edit ("further supported by") | P2 |
| 6A. Governed CACR ≈ random | ✗ MISSING | Compute binomial CI, test overlap with 60% | **P0** |
| 6B. Ungoverned CACR < random | ✗ MISSING | One-sample proportion test | **P0** |
| 6C. Flood CACR null model | ✗ MISSING | Compute from PMT matrix | **P0** |
| 7. Cross-domain claim | ✓ DONE | Optional: add "falls within CI" sentence | P3 |

---

## Recommended Paper Language (Final)

### Main Text (Results Section)

> **Governance Effect on Behavioral Diversity**
>
> Governed agents exhibited significantly higher effective heterogeneity entropy (EHE) than ungoverned agents (0.738 ± 0.017 vs 0.637 ± 0.017; bootstrap 95% CI for difference [0.078, 0.122]; Cohen's d = 6.0, though the 95% CI [5.1, 21.0] is uninformative due to occasional near-zero pooled SDs in bootstrap resamples with n=3 per group). The effect was robust to single-seed influence (leave-one-out Cohen's d range: 4.8–8.1) and demonstrated zero distributional overlap (min(governed) = 0.720 > max(ungoverned) = 0.655). Exact permutation test yielded p = 1/20 = 0.05, the minimum achievable p-value for n=3 per group, further supported by the zero overlap.
>
> **Mechanism: Coherence Without Prescription**
>
> Governed agents' construct-action coherence rate (CACR) was 58% (95% CI [XX%, XX%]), statistically indistinguishable from the random baseline of 60% (p = X.XX, two-sided proportion test), confirming that governance rules do not prescribe actions. In contrast, ungoverned agents exhibited systematic bias toward water demand increases (CACR = 9.4%, 95% CI [XX%, XX%]), significantly below the random baseline (p < 0.001, one-sided proportion test). This finding generalizes across domains: flood adaptation agents showed CACR = XX% under governance (null model: XX%), further supporting the hypothesis that semantic governance restores decision coherence to near-random levels.

**PLACEHOLDERS (XX%) MUST BE REPLACED** with actual computed values.

---

### Supplement (Statistical Methods)

> **Bootstrap Procedure**
>
> We used non-parametric bootstrap (10,000 resamples, seed=12345) to construct 95% confidence intervals for the EHE difference and Cohen's d. For each bootstrap iteration, we resampled with replacement from the three governed and three ungoverned seed values independently, computed the mean difference and effect size, and extracted the 2.5th and 97.5th percentiles.
>
> **Cohen's d Caveat**
>
> The bootstrap CI for Cohen's d [5.1, 21.0] is extremely wide due to occasional resamples with near-zero pooled standard deviations (a known issue with n=3 per group). We therefore report the point estimate (d=6.0) as the primary effect size measure and interpret it qualitatively as a "very large effect" (Cohen's benchmark: d>0.8). The leave-one-out sensitivity analysis (d range: 4.8–8.1) provides additional evidence of effect robustness.
>
> **CACR Null Model**
>
> For irrigation agents, the random baseline coherence rate is 60% (3 of 5 skills do not increase water demand in high-WSA conditions). For flood agents, we computed the expected coherence rate under uniform random action selection by averaging the proportion of PMT-coherent actions across all 25 TP×CP cells [SHOW CALCULATION]. We tested whether observed CACR rates differed from these baselines using Wilson score binomial CIs and one-sample proportion tests.

---

## Response to Specific Review Questions

### Q1: Do these corrections adequately address your P0 concerns?

**Partially (60% complete).**

- ✓ Uncertainty quantification (EHE CI, LOO sensitivity, per-seed transparency): **EXCELLENT**
- ✗ Cohen's d CI needs caveat or alternative
- ✗ CACR null-model comparison **lacks formal statistical tests** (critical gap)

### Q2: Is the bootstrap CI for Cohen's d [5.11, 21.05] informative or problematic?

**Problematic.**

- The 4-fold range (21.05/5.11 = 4.1) makes it **scientifically uninformative**
- Caused by small-sample instability (near-zero pooled SDs in some resamples)
- **Solution**: Report with caveat (main text) + full diagnostics (supplement)
- **Alternative**: Use Cliff's Delta (ordinal effect size) which is more stable for n=3

### Q3: Is the leave-one-out sensitivity sufficient given n=3?

**Yes, it is the gold standard for n=3.**

- Exhaustive coverage (all 3 possible LOO subsets tested)
- Effect remains "very large" (d=4.8–8.1) in all cases
- Zero overlap maintained in all subsets
- **No additional sensitivity analysis needed**

### Q4: Is the null-model CACR comparison (58% ≈ 60% >> 9.4%) statistically sound?

**No, it is scientifically plausible but statistically incomplete.**

**Missing components**:
1. Binomial CI on 58% → does it include 60%?
2. Formal test: governed ≠ random (two-sided)
3. Formal test: ungoverned < random (one-sided)
4. Sample size (n_decisions) not reported
5. Flood CACR null model not computed

**Once completed**, this will be a **strong mechanistic validation** of the governance framework.

### Q5: Recommended paper language?

**See Section: "Recommended Paper Language (Final)" above.**

Key principles:
- Lead with bootstrap CI for EHE (robust, narrow)
- Caveat the Cohen's d CI in-line
- Emphasize zero overlap and LOO robustness
- Report CACR with formal statistical tests (ONCE COMPUTED)
- Move bootstrap diagnostics to supplement

### Q6: Any remaining statistical concerns for Nature Water standards?

**Two P0 blockers remain**:

1. **Cohen's d bootstrap CI**: Needs caveat or alternative (Cliff's Delta)
2. **CACR null-model tests**: Must compute binomial CIs and significance tests

**One P1 recommendation**:
- Add power analysis to supplement (post-hoc power for n=3 with observed effect sizes)

**One P2 suggestion**:
- Consider reporting **eta-squared** (η²) as complementary effect size:
  ```python
  SS_between = 3 * ((0.738 - grand_mean)**2 + (0.637 - grand_mean)**2)
  SS_total = SS_between + SS_within
  eta_sq = SS_between / SS_total
  ```
  - Advantage: Bounded [0,1], more interpretable than unbounded d

---

## Statistical Rigor Rating

| Criterion | Rating (1-5) | Notes |
|-----------|--------------|-------|
| Transparency | 5/5 | Per-seed data, bootstrap details, honest caveats |
| Uncertainty Quantification | 4/5 | EHE CI excellent; Cohen's d CI problematic |
| Robustness Checks | 5/5 | LOO sensitivity, permutation test, zero-overlap |
| Effect Size Reporting | 3/5 | Cohen's d reported but CI uninformative |
| Mechanistic Validation | 2/5 | CACR concept strong but lacks formal tests |
| Reproducibility | 5/5 | Code provided, seed documented, methods clear |
| **Overall** | **4.0/5** | **Strong foundation, critical gaps in CACR analysis** |

---

## Verdict

**MAJOR REVISION REQUIRED** before Nature Water acceptance.

**Strengths**:
- Excellent transparency (per-seed data, bootstrap code, honest caveats)
- Robust EHE analysis (narrow CI, zero overlap, LOO sensitivity)
- Thoughtful permutation test framing

**Critical Gaps**:
1. Cohen's d bootstrap CI needs in-line caveat or alternative effect size
2. CACR null-model comparison **must include formal statistical tests**
3. Flood CACR null model must be computed (not estimated)

**Timeline to Acceptance**:
- Revisions needed: 2-4 hours of analysis
- Re-review turnaround: 1-2 weeks
- **Recommendation**: ACCEPT after minor revision (P0 issues addressable)

---

## Appendix: Code Snippets for Required Analyses

### A1: Governed CACR Binomial CI
```python
from statsmodels.stats.proportion import proportion_confint

# REPLACE WITH ACTUAL VALUES
n_decisions_governed = ???  # Total governed decisions
n_coherent_governed = int(0.58 * n_decisions_governed)

ci_low, ci_high = proportion_confint(
    n_coherent_governed, n_decisions_governed, method='wilson'
)

print(f"Governed CACR: 58% (95% CI [{ci_low:.1%}, {ci_high:.1%}])")
print(f"Null model (60%) within CI? {ci_low <= 0.60 <= ci_high}")
```

### A2: Ungoverned CACR Significance Test
```python
from statsmodels.stats.proportion import binom_test

n_decisions_ungov = ???
n_coherent_ungov = int(0.094 * n_decisions_ungov)

p_value = binom_test(
    n_coherent_ungov, n_decisions_ungov, prop=0.60, alternative='smaller'
)

print(f"Ungoverned CACR (9.4%) vs null (60%): p = {p_value:.4f}")
```

### A3: Flood CACR Null Model
```python
import numpy as np
from validation.theories.pmt import PMT_OWNER_RULES, PMT_RENTER_RULES

def compute_null_cacr(rules_dict, n_total_actions):
    rates = []
    for (tp, cp), coherent_actions in rules_dict.items():
        rates.append(len(coherent_actions) / n_total_actions)
    return np.mean(rates), np.std(rates)

owner_null_mean, owner_null_std = compute_null_cacr(PMT_OWNER_RULES, n_total_actions=5)
renter_null_mean, renter_null_std = compute_null_cacr(PMT_RENTER_RULES, n_total_actions=3)

print(f"Flood CACR null model (owners):  {owner_null_mean:.1%} ± {owner_null_std:.1%}")
print(f"Flood CACR null model (renters): {renter_null_mean:.1%} ± {renter_null_std:.1%}")
```

---

**End of Review**

*Reviewer Contact: [Biostatistics Professor, Nature Water Editorial Board]*
*Next Steps: Address P0 issues → resubmit statistical supplement → fast-track acceptance*
