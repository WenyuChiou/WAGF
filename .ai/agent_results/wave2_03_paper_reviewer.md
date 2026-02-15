# Peer Review: C&V (Credibility & Validation) Module for LLM-ABM

**Reviewer**: Prof. David Abramson (simulated)
**Role**: Journal Reviewer (Nature Water / WRR perspective)
**Date**: 2026-02-14
**Artifact reviewed**: `validation/` package (engine.py, metrics/, theories/, benchmarks/, hallucinations/, reporting/)

---

## 1. Summary & Recommendation

**Recommendation: MAJOR REVISION (with path to acceptance)**

This module presents a structured, three-level validation framework (L1 micro, L2 macro, L3 cognitive) for LLM-based agent-based models. Given that 22 of 35 LLM-ABM papers in the current literature rely solely on subjective validation, this represents a genuine methodological advance. The work introduces several defensible constructs (CACR, CGR, EPI, EBE) and implements them with reasonable statistical infrastructure (bootstrap CIs, Monte Carlo null model, Cohen's kappa).

However, the module suffers from several issues that prevent acceptance in its current form: (1) the hallucination detector is domain-hardcoded rather than pluggable, undermining generalizability claims; (2) the CGR grounding rules are not independently validated; (3) the null model uses only uniform-random agents, ignoring structured null alternatives; (4) there is no temporal validation dimension; and (5) benchmark range selection is insufficiently documented to preclude researcher degrees of freedom. These are addressable in revision, and the underlying architecture is sound.

---

## 2. Novelty Assessment

### What is genuinely novel

1. **Three-level validation hierarchy for LLM-ABMs**. No existing paper implements a systematic multi-level validation protocol specifically designed for LLM-ABMs. Grimm et al. (2005) Pattern-Oriented Modeling (POM) is the closest precedent in traditional ABMs, but POM does not address the unique challenges of LLM agents: construct extraction, hallucination, and the circularity problem of evaluating an LLM's reasoning against its own self-reported constructs.

2. **CACR (Construct-Action Coherence Rate)** is a genuine contribution. It operationalizes what has previously been assessed qualitatively ("does the agent behave consistently with its stated reasoning?"). The decomposition into CACR_raw (pre-governance) vs. CACR_final (post-governance) with quadrant-level breakdowns is methodologically careful.

3. **CGR (Construct Grounding Rate)** as a circularity-breaking mechanism. The explicit recognition that CACR alone is circular -- the LLM reports its own constructs and then acts on them -- and the response of grounding constructs from objective state variables, is a meaningful methodological contribution. Cohen's kappa for measuring agreement between rule-based grounding and LLM labels is appropriate.

4. **BehavioralTheory Protocol** as a pluggable interface. The Protocol-based design (Paradigm A: construct-action mapping, with Paradigm B: frame-conditional noted as future) allows different behavioral theories to be composed with the validation machinery. The PMT, TPB, and IrrigationWSA examples demonstrate extensibility.

### What is NOT novel

- EPI is a weighted pass/fail proportion -- this is standard and not novel per se.
- Bootstrap CIs are textbook non-parametric statistics.
- Shannon entropy for behavioral diversity is well-established.

### Comparison to literature

Park et al. (2023) and Ghaffarzadegan et al. (2024) represent the current state of the art for LLM-ABM validation. Park et al. used human evaluator ratings (subjective). Ghaffarzadegan et al. used aggregate calibration against empirical targets. This module subsumes both approaches: L1 provides per-decision validation that goes beyond subjective rating, L2 provides aggregate calibration, and L3 (ICC probing) provides construct reliability assessment that neither existing paper attempted.

**Assessment**: The module is clearly ahead of the published frontier for LLM-ABM validation. It is not ahead of the broader ABM validation literature (which includes sensitivity analysis, cross-validation, and formal uncertainty quantification), but it adapts those principles to the unique LLM context.

**Novelty score: 4/5**

---

## 3. Statistical Review

### 3.1 EPI (Empirical Plausibility Index)

EPI = sum(w_i * I(benchmark_i in range)) / sum(w_i)

This is a weighted binary scoring function. It is defensible as a screening metric but has known weaknesses:

- **Sensitivity to range width**: A benchmark with range [0.05, 0.30] is far easier to pass than one with range [0.20, 0.25]. The current ranges vary from width 0.05 (renter_uninsured) to 0.30 (insurance_rate_sfha). This heterogeneity means EPI is partially determined by how generous the ranges are.
- **Weight assignment**: The weight of 2.0 for mg_adaptation_gap versus 0.8 for insurance_rate_all is justified by the paper's focus on equity, but this is a researcher degree of freedom. I would require a sensitivity analysis showing EPI conclusions are robust to equal-weight and alternative-weight schemes.
- **Binary scoring loses information**: A benchmark at 0.299 (just inside [0.05, 0.30]) scores the same as one at 0.15 (center of range). A continuous scoring function (e.g., distance from range midpoint, normalized by range width) would be more informative.

**Verdict**: Defensible as a first-generation metric but needs sensitivity analysis. Score: 3.5/5.

### 3.2 Cohen's Kappa for CGR

The use of Cohen's kappa for TP and CP agreement between rule-based grounding and LLM labels is appropriate. The implementation correctly handles the 5-level ordinal scale. However:

- The ordinal nature of the levels (VL < L < M < H < VH) means weighted kappa (e.g., linear or quadratic weights) would be more appropriate than unweighted kappa, because a VH-vs-H disagreement is less severe than VH-vs-VL.
- The adjacent-match rate (cgr_tp_adjacent, cgr_cp_adjacent) partially compensates for this, but formally, weighted kappa is the standard for ordinal data.

**Verdict**: Adequate but should use weighted kappa. Score: 3/5.

### 3.3 Bootstrap CIs

The implementation is a standard non-parametric percentile bootstrap. The code is correct:

```python
indices = rng.integers(0, n, size=n)       # With replacement, correct
lower = np.percentile(samples_arr, 100 * alpha / 2)
upper = np.percentile(samples_arr, 100 * (1 - alpha / 2))
```

Two issues:
- **Percentile method**: The percentile method is the simplest but not the most accurate bootstrap CI method. BCa (bias-corrected and accelerated) would be preferable for small samples. For the sample sizes in this paper (400 agents, 52,000 decisions), the percentile method is adequate.
- **Resampling unit**: The bootstrap resamples individual traces, but traces from the same agent across years are correlated. A clustered bootstrap (resampling agents, not traces) would be more appropriate.

**Verdict**: Correct implementation, minor improvements needed. Score: 3.5/5.

### 3.4 Null Model

The null model generates uniform-random actions per agent per year. The empirical p-value computation is correct (with the +1 correction for discrete distributions):

```python
p_value = float((null_arr >= observed_epi).sum() + 1) / (n + 1)
```

However:
- **Only uniform null**: A uniform-random agent is the weakest possible null model. Stronger nulls would include: (a) frequency-matched random (preserving marginal action frequencies), (b) state-dependent random (actions depend on flood zone but not on reasoning), (c) LLM without governance (to test governance contribution specifically). The current null only answers "is this better than purely random?", which is a low bar.
- **Null traces lack realistic state dynamics**: The null model simulates flooding independently per year (20% HIGH, 5% other) but does not track insurance status, elevation, or buyout. This means the null model's EPI may be artificially low because its agents cannot achieve persistent states (e.g., staying insured). This biases the significance test toward rejection.

**Verdict**: Valid but insufficient alone. Needs at least one additional structured null. Score: 3/5.

### 3.5 CACR

The computation is correct: coherent / eligible, with extraction failures excluded. The fallback to `is_sensible_action` when the exact construct combination is not in the lookup table is a reasonable design choice. However:

- The threshold of 0.75 is not justified from literature. Why 0.75 and not 0.70 or 0.80? This needs either (a) a theoretical justification (e.g., inter-rater reliability convention), (b) a sensitivity analysis, or (c) comparison to human-coded traces.

**Verdict**: Well-implemented, threshold needs justification. Score: 3.5/5.

---

## 4. Threats to Validity

### 4.1 CACR Circularity

The CGR module addresses this directly. The rule-based grounding functions (`ground_tp_from_state`, `ground_cp_from_state`) derive expected TP/CP from objective agent state variables. This breaks the circularity because the grounding is independent of the LLM's self-report.

**However**: The grounding rules themselves are researcher-specified and not independently validated. For example:

```python
if zone == "HIGH" and flooded_now: return "VH"
if zone == "HIGH" and flood_count >= 1: return "H"
```

These rules embed assumptions about how objective conditions map to threat perception. An alternative grounding (e.g., from survey data showing actual TP distributions by flood zone) would strengthen this considerably. Without independent validation, the CGR is only measuring agreement between two sets of researcher assumptions (the grounding rules and the PMT lookup table).

**Severity**: Moderate. Addressable in revision with survey-based calibration.

### 4.2 EPI Gaming

A researcher could tune benchmark ranges to maximize EPI. The current ranges are wide enough to be forgiving (e.g., insurance_rate_sfha: 0.30-0.60), and the module does not formally prevent range shopping. The mitigation would be:

1. Pre-registration of benchmark ranges before running experiments
2. Literature citation for every range bound (partial -- the ranges are cited but not all bounds have individual citations)
3. A "range tightening" sensitivity analysis showing EPI degrades gracefully

**Severity**: Moderate. Partially addressed by using literature-based ranges, but researcher degrees of freedom remain.

### 4.3 Hallucination Detector is Hardcoded

The `_is_hallucination` function in `hallucinations/flood.py` contains exactly three checks:

1. Already elevated + trying to elevate
2. Already bought out + acting
3. Renter trying to elevate

This is not pluggable. A new domain (e.g., irrigation) would need to write a completely new hallucination detector. More critically, these three checks are unlikely to capture all hallucinations -- they only detect physically impossible actions, not semantically implausible ones (e.g., a destitute household buying a $200K elevation).

**Severity**: High for generalizability claims, low for the flood domain specifically.

### 4.4 LLM Prompt Engineering Confounds

The validation module evaluates outputs but does not control for prompt sensitivity. If CACR is 0.85 with one prompt and 0.50 with a semantically equivalent prompt, the validation result is fragile. The L3 sensitivity analysis (75% directional consistency) partially addresses this, but prompt robustness should be formally integrated into the validation pipeline.

**Severity**: Moderate. Partially addressed at L3 but not at L1/L2.

### 4.5 No Temporal Validation

Wave 1 identified this gap and it remains unaddressed. There is no metric that validates temporal dynamics -- e.g., do insurance adoption rates rise after flood events at empirically plausible speeds? The `insurance_lapse_rate` benchmark is temporal in nature but is computed as a single aggregate, not a time series comparison. For a 13-year simulation, temporal plausibility should be a first-class concern.

**Severity**: High for the paper's claims. Partially addressable by adding a temporal benchmark (e.g., year-over-year adaptation trend correlation).

---

## 5. Generalizability Evidence

The paper will claim domain-agnostic design. The evidence for this is:

| Component | Pluggable? | Evidence |
|-----------|-----------|----------|
| BehavioralTheory Protocol | Yes | PMT, TPB, IrrigationWSA implemented |
| BenchmarkRegistry | Yes | Decorator-based, clean interface |
| TheoryRegistry | Yes | Register/get pattern |
| Hallucination detection | **No** | Hardcoded for flood domain |
| CGR grounding rules | **No** | Hardcoded for flood (TP from flood_zone, CP from income/mg) |
| Trace reader | **Partially** | Assumes TP/CP construct names |
| Null model | **No** | Hardcoded owner/renter action pools |

**Assessment**: The core architecture (Protocol, Registry, engine) is genuinely domain-agnostic. But 3 of 7 components are hardcoded for the flood domain. The TPB and IrrigationWSA examples are purely structural -- they show the interface works but have never been validated on actual data. To credibly claim domain-agnostic design, the authors need at minimum:

1. A hallucination detection Protocol (analogous to BehavioralTheory)
2. A CGR Protocol allowing domain-specific grounding rules
3. At least one non-flood domain with actual data (the irrigation ABM exists -- use it)

**Generalizability score: 2.5/5**

---

## 6. Required Revisions (Prioritized)

### Must-Fix (Blocking)

**R1. Weighted Kappa for CGR**
Replace unweighted Cohen's kappa with linear or quadratic weighted kappa for the ordinal TP/CP scales. This is a standard requirement for ordinal reliability assessment and any statistician on a review panel would flag this.

**R2. Independent Validation of CGR Grounding Rules**
Provide evidence that the rule-based TP/CP grounding functions produce outputs consistent with empirical survey data. At minimum, cite Grothmann & Reusswig (2006) or Bubeck et al. (2012) for the specific threshold choices (e.g., "HIGH zone + flooded = VH"). Ideally, validate against the 755-household survey that initialized the agents.

**R3. EPI Weight Sensitivity Analysis**
Run EPI computation under at least 3 weighting schemes: (a) equal weights, (b) current weights, (c) alternative weights with mg_adaptation_gap at 1.0 instead of 2.0. Report whether the pass/fail conclusion changes.

**R4. Structured Null Model**
Add at least one non-uniform null model. The most informative would be a "frequency-matched random" null that preserves the observed marginal action distribution but randomizes the construct-action pairing. This answers: "Does the LLM's reasoning improve over random assignment with the same action frequencies?"

**R5. CACR Threshold Justification**
Justify the 0.75 threshold. Options: (a) map to Cohen's kappa convention (kappa > 0.60 = substantial), (b) derive from human-coded benchmark traces, (c) show results are robust within [0.65, 0.85].

### Should-Fix (Strongly Recommended)

**R6. Hallucination Detection Protocol**
Create a `HallucinationDetector` Protocol mirroring `BehavioralTheory`. The current hardcoded 3-rule detector should become the flood-domain implementation. This is necessary for the generalizability claim.

**R7. CGR as Pluggable Protocol**
Similarly, abstract `ground_tp_from_state` / `ground_cp_from_state` into a `ConstructGrounder` Protocol. The flood-specific grounding becomes one implementation.

**R8. Temporal Benchmark**
Add at least one temporal validation metric. Candidate: Spearman correlation between year-over-year insurance uptake change and flood occurrence, compared to empirical post-flood insurance spike data (Kousky 2017).

**R9. Clustered Bootstrap**
Modify the bootstrap to resample agents (not individual traces) to account for within-agent correlation.

### Nice-to-Have

**R10.** BCa bootstrap intervals instead of percentile method.
**R11.** Continuous EPI scoring function (distance-from-midpoint) as supplementary metric alongside binary.
**R12.** Paradigm B implementation (Prospect Theory frame-conditional validation) as proof of extensibility.
**R13.** Cross-validate CACR against human expert ratings on a subsample of traces (e.g., 200 randomly selected traces rated by 2+ domain experts).

---

## 7. Minor Comments

1. `l1_micro.py:119` -- `_is_hallucination` is imported from `hallucinations.flood` but there is no dispatch mechanism if the domain changes. This hardcodes the flood dependency into the supposedly generic L1 computation.

2. `cgr.py:57` -- The `HIGH` zone check `zone == "HIGH" and flood_count == 0` returns "M", but this case is unreachable because the earlier `zone == "HIGH" and flood_count >= 1` already captures flood_count >= 1. If flood_count == 0 and zone == "HIGH", you fall through the first HIGH check (which requires `flooded_now`), the second HIGH check (which requires `flood_count >= 1`), and then hit MODERATE checks. The `zone == "HIGH" and flood_count == 0` check on line 53 is correctly placed but should be tested explicitly.

3. `null_model.py` -- The null model does not simulate agent state accumulation (insurance persists, elevation persists). This means the null model cannot generate realistic `final_states`, making the comparison asymmetric. Document this limitation.

4. `bootstrap.py` -- The function stores all 1000 bootstrap samples in the return dict. For large-scale use, this could consume significant memory. Consider making sample storage optional.

5. `engine.py:139` -- Bare `except` clause when parsing seed from directory name. Use `except (ValueError, IndexError)` for safety.

6. The `_normalize_action` function is imported from `io/trace_reader.py` but not reviewed here -- if it has bugs, CACR and EPI are both affected. Ensure it has dedicated unit tests.

7. EBE ratio thresholds (0.1 < ratio < 0.9) are not justified. Why not 0.05 < ratio < 0.95? The lower bound of 0.1 is quite generous (allows near-degenerate distributions).

---

## 8. Dimension Scores

| Dimension | Score | Notes |
|-----------|-------|-------|
| D1: Methodological Novelty | 4.0 | Three-level hierarchy + CACR + CGR are genuine contributions |
| D2: Statistical Rigor | 3.0 | Bootstrap correct, but unweighted kappa, uniform-only null, threshold unjustified |
| D3: Reproducibility | 3.5 | Code is clean and well-documented; parameters explicit; but grounding rules need calibration documentation |
| D4: Threat to Validity | 3.0 | CACR circularity partially addressed; EPI gaming risk; no temporal validation |
| D5: Generalizability Claims | 2.5 | Core architecture is pluggable but 3/7 components hardcoded; no non-flood validation on real data |
| D6: Comparison to State-of-Art | 4.0 | Clearly ahead of Park et al. and Ghaffarzadegan et al.; closer to but not yet at POM standard |
| D7: Major Revision Requirements | 3.0 | R1-R5 are blocking but addressable; no fundamental flaws requiring reject |

---

## 9. Overall Score

**Overall: 3.3 / 5.0**

This is a solid Major Revision. The core ideas (CACR, CGR, three-level hierarchy, BehavioralTheory Protocol) are sound and represent a genuine advance over the current LLM-ABM validation literature. The statistical implementation is competent but needs tightening (weighted kappa, structured nulls, clustered bootstrap). The generalizability claim needs honest scoping -- the module is domain-agnostic in architecture but domain-specific in implementation, and the paper should say so. With the R1-R5 revisions and at least R6-R8, this would be publishable in a top methods journal.

The strongest version of this paper would position the C&V module not as "the" validation framework for LLM-ABMs, but as "a principled starting point" -- demonstrating that systematic validation is both feasible and necessary, while acknowledging the open problems (temporal dynamics, Paradigm B theories, cross-domain portability). That framing is both more honest and more likely to generate citation impact.

---

*Review generated by simulated Prof. David Abramson persona. Findings reflect code-level analysis of the validation/ package.*
