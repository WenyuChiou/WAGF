# P0 Expert Panel Response — Statistical Corrections Summary

**Date**: 2026-02-15
**Author**: WAGF Research Team
**Reviewer**: Biostatistics Professor (Nature Water Editorial Board)

---

## Executive Summary

This document summarizes the statistical corrections made in response to P0 recommendations and provides the reviewer's assessment. **Status: 4/6 corrections complete; 2 require additional work (CACR formal tests).**

---

## Question-by-Question Assessment

### Q1: Do these corrections adequately address your P0 concerns?

**Reviewer Answer: PARTIALLY (60% complete)**

#### ✓ **ACCEPTABLE** (4/6 corrections):
1. **Per-seed reporting**: Raw values now visible with matched SDs (0.017 each)
2. **Bootstrap CI for EHE difference**: Narrow, excludes zero [0.078, 0.122]
3. **Leave-one-out sensitivity**: Effect robust (d=4.76–8.13) across all subsets
4. **Permutation test framing**: Honest acknowledgment of n=3 limitation

#### ✗ **INCOMPLETE** (2/6 corrections):
5. **Cohen's d bootstrap CI**: Uninformative [5.11, 21.05] → needs caveat
6. **CACR null-model comparison**: Lacks formal statistical tests

**Verdict**: Strong foundation, but critical gaps in CACR analysis prevent acceptance.

---

### Q2: Is the bootstrap CI for Cohen's d [5.11, 21.05] informative or problematic?

**Reviewer Answer: PROBLEMATIC**

#### Issues Identified:

**Issue A: Extreme Width (CI width = 16.0)**
- Upper bound (21.05) is 3.5× the point estimate (5.99)
- **Root cause**: With n=3, occasional bootstrap samples have near-zero pooled SD
  - Example: [0.754, 0.754, 0.754] → SD ≈ 0 → d → ∞
- **Impact**: 97.5th percentile includes pathological resamples

**Issue B: Heavy Right-Skew**
- Median (7.37) ≠ Mean (~9.0 estimated)
- **Implication**: Distribution is NOT Normal → percentile CI questionable

**Issue C: Scientific Uninformativity**
- "Is the effect d=6 or d=20?" → 4-fold range provides no guidance
- Reviewers will reject as uninformative

#### Recommended Solutions:

**Option A: Report with Caveat (RECOMMENDED)**
```
"Cohen's d = 6.0 (very large effect), though the 95% CI [5.1, 21.0]
is uninformative due to n=3 per group leading to occasional near-zero
pooled SDs in bootstrap resamples."
```

**Option B: Use Robust Effect Size**
- **Cliff's Delta** (ordinal effect size, insensitive to SD instability)
- For zero-overlap data: Cliff's Δ = 1.0 (perfect separation)
- Pro: Stable CI, interpretable
- Con: Requires methodological justification

**Option C: Report Median + IQR**
```
"Cohen's d = 6.0 (median = 7.4, IQR [6.1, 9.2])"
```

**Reviewer Recommendation**: Use Option A for main text, move bootstrap diagnostics to supplement.

---

### Q3: Is the leave-one-out sensitivity sufficient given n=3?

**Reviewer Answer: YES (Gold Standard)**

#### Why It's Sufficient:

✓ **Exhaustive coverage**: All 3 possible LOO subsets tested
✓ **Effect stability**: Cohen's d remains "very large" (4.76–8.13) in all cases
✓ **Significance maintained**: Delta remains +0.091 to +0.109 across subsets
✓ **Zero overlap preserved**: min(gov) > max(ungov) in all LOO analyses

**Reviewer Verdict**: No additional sensitivity analysis needed.

**Approved Language**:
> "Leave-one-out sensitivity analysis confirmed robustness: Cohen's d ranged from 4.8 to 8.1 across all three subsets, with zero distributional overlap maintained in each case."

---

### Q4: Is the null-model CACR comparison (58% ≈ 60% >> 9.4%) statistically sound?

**Reviewer Answer: NO (Scientifically Plausible, Statistically Incomplete)**

#### What's Missing:

**1. Binomial CI on Governed CACR (58%)**
- **Question**: Does the 95% CI include 60%?
- **Required**: Wilson score interval
- **Formula**:
  ```python
  from statsmodels.stats.proportion import proportion_confint
  n = ???  # MUST report total decision count
  ci_low, ci_high = proportion_confint(int(0.58*n), n, method='wilson')
  ```
- **Interpretation**:
  - If 60% ∈ CI → claim "near-random" is **valid** ✓
  - If 60% ∉ CI → must report as "different from random" ✗

**2. One-Sample Proportion Test (Ungoverned < Random)**
- **Current claim**: "9.4% << 60%" (qualitative only)
- **Required**: Formal significance test
- **Formula**:
  ```python
  from statsmodels.stats.proportion import binom_test
  p = binom_test(int(0.094*n), n, prop=0.60, alternative='smaller')
  ```
- **Expected**: p < 0.001 (extremely significant) — BUT MUST BE SHOWN

**3. Sample Size Not Reported**
- **Critical omission**: How many decisions? 100? 1,000? 10,000?
- **Impact on CI width**: n=100 → CI ≈ [48%, 68%] (wide)
                         n=1000 → CI ≈ [55%, 61%] (narrow)

**4. Flood CACR Null Model Was Estimated, Not Computed**

**Original claim**:
> "Rough estimate: if 5 actions, ~40-60% coherent by chance"

**Reviewer response**: "This is hand-waving, not analysis."

**NOW COMPUTED** (see `compute_cacr_null_model.py`):

| Agent Type | Null CACR | Interpretation |
|------------|-----------|----------------|
| Owners     | 43.2%     | Random owner: 43.2% coherent by chance |
| Renters    | 57.3%     | Random renter: 57.3% coherent by chance |
| Combined   | 47.4%     | Weighted avg (70% owners, 30% renters) |

**Key Finding**: Null baseline is 47.4%, NOT the "40-60%" range previously estimated.

**Approved Language** (once observed CACR is computed):
> "Under uniform random action selection, the expected CACR is 47.4% (owners: 43.2%, renters: 57.3%). Governed agents' observed CACR of XX% (95% CI [XX%, XX%]) is statistically [indistinguishable from / significantly above] this baseline (p = X.XX), confirming that governance rules [restore coherence without prescriptive bias / promote construct-driven decisions]."

**Reviewer Verdict**: Must complete binomial CIs and significance tests before publication.

---

### Q5: What is the recommended paper language for reporting these statistics?

**Reviewer Answer: See Below**

#### Main Text (Results Section)

```
Governance Effect on Behavioral Diversity

Governed agents exhibited significantly higher effective heterogeneity
entropy (EHE) than ungoverned agents (0.738 ± 0.017 vs 0.637 ± 0.017;
bootstrap 95% CI for difference [0.078, 0.122]; Cohen's d = 6.0, though
the 95% CI [5.1, 21.0] is uninformative due to occasional near-zero
pooled SDs in bootstrap resamples with n=3 per group). The effect was
robust to single-seed influence (leave-one-out Cohen's d range: 4.8–8.1)
and demonstrated zero distributional overlap (min(governed) = 0.720 >
max(ungoverned) = 0.655). Exact permutation test yielded p = 1/20 = 0.05,
the minimum achievable p-value for n=3 per group, further supported by
the zero overlap.

Mechanism: Coherence Without Prescription

Governed agents' construct-action coherence rate (CACR) was XX%
(95% CI [XX%, XX%]), statistically [indistinguishable from / above] the
random baseline of YY% (p = X.XX, [two-sided / one-sided] proportion test),
confirming that governance rules [restore decision coherence to near-random
levels / promote construct-driven decisions]. In contrast, ungoverned agents
exhibited systematic bias toward water demand increases (CACR = 9.4%,
95% CI [XX%, XX%]), significantly below the random baseline (p < 0.001,
one-sided proportion test). This finding generalizes across domains: flood
adaptation agents showed CACR = XX% under governance (null model: 47.4%),
[INTERPRETATION BASED ON ACTUAL VALUES].
```

**PLACEHOLDERS (XX%, YY%) MUST BE REPLACED** with computed values.

#### Supplement (Statistical Methods)

```
Bootstrap Procedure

We used non-parametric bootstrap (10,000 resamples, seed=12345) to
construct 95% confidence intervals for the EHE difference and Cohen's d.
For each bootstrap iteration, we resampled with replacement from the
three governed and three ungoverned seed values independently, computed
the mean difference and effect size, and extracted the 2.5th and 97.5th
percentiles.

Cohen's d Caveat

The bootstrap CI for Cohen's d [5.1, 21.0] is extremely wide due to
occasional resamples with near-zero pooled standard deviations (a known
issue with n=3 per group). We therefore report the point estimate (d=6.0)
as the primary effect size measure and interpret it qualitatively as a
"very large effect" (Cohen's benchmark: d>0.8). The leave-one-out
sensitivity analysis (d range: 4.8–8.1) provides additional evidence
of effect robustness.

CACR Null Model

For irrigation agents, the random baseline coherence rate is 60% (3 of 5
skills do not increase water demand in high-WSA conditions). For flood
agents, we computed the expected coherence rate under uniform random
action selection by averaging the proportion of PMT-coherent actions
across all 25 TP×CP cells. Under the assumption of random action choice:
  • Owners: 43.2% coherent (5 action pool, 25 PMT cells)
  • Renters: 57.3% coherent (3 action pool, 25 PMT cells)
  • Combined: 47.4% (weighted by 70% owners, 30% renters)

We tested whether observed CACR rates differed from these baselines using
Wilson score binomial CIs and one-sample proportion tests.
```

---

### Q6: Any remaining statistical concerns for Nature Water standards?

**Reviewer Answer: TWO P0 BLOCKERS + ONE P1 RECOMMENDATION**

#### P0 Blockers (MUST FIX):

**1. Cohen's d Bootstrap CI**
- Current: [5.11, 21.05] (uninformative)
- **Fix**: Add in-line caveat (Option A) OR use Cliff's Delta
- **Timeline**: 30 minutes (caveat) or 2 hours (Cliff's Delta)

**2. CACR Null-Model Tests**
- Missing: Binomial CIs, significance tests, sample sizes
- **Fix**: Run `statsmodels` proportion tests (see code snippets below)
- **Timeline**: 1 hour (if decision counts are readily available)

#### P1 Recommendation (SHOULD ADD):

**Power Analysis for Supplement**
- Compute post-hoc power for n=3 with observed effect sizes
- Demonstrates whether study was adequately powered
- **Timeline**: 1 hour

#### P2 Suggestion (OPTIONAL):

**Eta-Squared (η²) Effect Size**
- Bounded [0,1], more interpretable than unbounded Cohen's d
- **Formula**:
  ```python
  grand_mean = (3*0.738 + 3*0.637) / 6
  SS_between = 3*((0.738-grand_mean)**2 + (0.637-grand_mean)**2)
  SS_total = SS_between + sum((x - grand_mean)**2 for each value)
  eta_sq = SS_between / SS_total
  ```
- **Timeline**: 15 minutes

---

## Completed Analyses

### 1. Irrigation EHE Bootstrap Analysis
**File**: `C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\irrigation_abm\analysis\nw_bootstrap_ci.py`

**Results**:
```
Per-Seed Values:
  Seed    Governed  Ungoverned     Delta
    42      0.7393      0.6549   +0.0844
    43      0.7536      0.6343   +0.1192
    44      0.7200      0.6217   +0.0984
  Mean      0.7376      0.6370   +0.1007
    SD      0.0168      0.0168

Bootstrap 95% CIs (10,000 resamples):
  EHE Difference: +0.1007 [0.0784, 0.1224]
  Cohen's d: 5.99 [5.11, 21.05]

Leave-One-Out Sensitivity:
  Drop seed 42: d = 6.08, delta = +0.1088
  Drop seed 43: d = 4.76, delta = +0.0914
  Drop seed 44: d = 8.13, delta = +0.1018

Permutation Test:
  p = 1/20 = 0.05 (minimum for n=3+3)
  Zero overlap: min(gov)=0.7200 > max(ungov)=0.6549
```

**Reviewer Verdict**: ✓ ACCEPTABLE (except Cohen's d CI needs caveat)

---

### 2. Flood CACR Null Model Computation
**File**: `C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\multi_agent\flood\paper3\analysis\compute_cacr_null_model.py`

**Results**:
```
Owner Null Model:
  Action pool: 5 (do_nothing, buy_insurance, elevate, buyout, retrofit)
  PMT cells: 25 (5 TP × 5 CP)
  Null CACR: 43.2% ± 18.5%
  Range: [20.0%, 80.0%]

Renter Null Model:
  Action pool: 3 (do_nothing, buy_insurance, relocate)
  PMT cells: 25
  Null CACR: 57.3% ± 15.0%
  Range: [33.3%, 66.7%]

Combined Null Model:
  Weighted (70% owners, 30% renters): 47.4%
```

**Reviewer Verdict**: ✓ COMPUTATION COMPLETE; awaiting comparison to observed CACR

---

## Still Required: CACR Formal Tests

### Code Snippet A: Governed CACR Binomial CI
```python
from statsmodels.stats.proportion import proportion_confint

# IRRIGATION DOMAIN
n_decisions_governed = ???  # MUST be extracted from simulation logs
n_coherent_governed = int(0.58 * n_decisions_governed)

ci_low, ci_high = proportion_confint(
    n_coherent_governed, n_decisions_governed, method='wilson'
)

print(f"Irrigation Governed CACR: 58% (95% CI [{ci_low:.1%}, {ci_high:.1%}])")
print(f"Random baseline (60%) within CI? {ci_low <= 0.60 <= ci_high}")

# FLOOD DOMAIN (once observed CACR is computed)
n_decisions_flood = ???
n_coherent_flood = int(observed_cacr_flood * n_decisions_flood)

ci_low_f, ci_high_f = proportion_confint(
    n_coherent_flood, n_decisions_flood, method='wilson'
)

print(f"Flood Governed CACR: {observed_cacr_flood:.1%} (95% CI [{ci_low_f:.1%}, {ci_high_f:.1%}])")
print(f"Random baseline (47.4%) within CI? {ci_low_f <= 0.474 <= ci_high_f}")
```

### Code Snippet B: Ungoverned CACR Significance Test
```python
from statsmodels.stats.proportion import binom_test

# IRRIGATION DOMAIN
n_decisions_ungov = ???
n_coherent_ungov = int(0.094 * n_decisions_ungov)

p_value = binom_test(
    n_coherent_ungov, n_decisions_ungov, prop=0.60, alternative='smaller'
)

print(f"Irrigation Ungoverned CACR (9.4%) vs null (60%): p = {p_value:.6f}")
print(f"Significant? {p_value < 0.05}")
```

---

## Timeline to Acceptance

| Task | Status | Time Required |
|------|--------|---------------|
| Per-seed values | ✓ DONE | - |
| EHE bootstrap CI | ✓ DONE | - |
| Leave-one-out sensitivity | ✓ DONE | - |
| Permutation test framing | ✓ DONE | - |
| Cohen's d caveat | ⏳ PENDING | 30 min (writing) |
| Irrigation CACR tests | ⏳ PENDING | 1 hour (extract n, run tests) |
| Flood CACR null model | ✓ DONE | - |
| Flood CACR tests | ⏳ PENDING | 1 hour (compute observed, run tests) |
| Power analysis (P1) | ⚪ OPTIONAL | 1 hour |
| **TOTAL** | **67% complete** | **~3 hours remaining** |

**Reviewer Recommendation**:
> "ACCEPT after minor revision (P0 issues addressable in 3-4 hours). Re-review turnaround: 1-2 weeks."

---

## Summary of Deliverables

### Completed Files:
1. `nw_bootstrap_ci.py` — Irrigation EHE bootstrap analysis
2. `compute_cacr_null_model.py` — Flood CACR null model
3. `cacr_null_model.json` — Exported null model values

### Required Additions:
1. **Irrigation CACR formal tests** (binomial CIs, significance tests)
   - Extract decision counts from `simulation_log.csv`
   - Run proportion tests
   - Update manuscript language

2. **Cohen's d caveat** (in-line, main text)
   - 1-sentence acknowledgment of CI instability
   - Move bootstrap diagnostics to supplement

3. **Flood CACR observed values** (from pilot v5 validation)
   - Compute CACR from experiment traces
   - Compare to null model (47.4%)
   - Run formal tests

---

## Contact

**Questions?** Contact WAGF research team or refer to:
- Full review: `P0_STATISTICAL_REVIEW.md`
- Bootstrap code: `nw_bootstrap_ci.py`
- CACR null model: `compute_cacr_null_model.py`

**Next Steps**:
1. Extract decision counts from simulation logs
2. Run CACR formal tests (see code snippets)
3. Add Cohen's d caveat to manuscript
4. Resubmit statistical supplement

**Target**: Complete P0 revisions within 1 week → fast-track acceptance.

---

**End of Summary**
