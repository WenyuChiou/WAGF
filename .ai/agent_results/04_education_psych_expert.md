# Expert Review: WAGF C&V Framework -- Education/Psychology ABM Perspective

**Reviewer**: Dr. Aisha Okafor, Educational Psychologist
**Affiliation**: Modeling student learning behavior with TPB/SDT-based LLM agents
**Date**: 2026-02-14
**Scope**: Evaluate whether the WAGF C&V validation module can validate LLM-driven student behavior simulations

---

## Executive Summary

The WAGF C&V framework is the most rigorous validation protocol I have encountered for LLM-agent simulations. Its three-level architecture (L1 micro, L2 macro, L3 cognitive) maps surprisingly well onto the psychometric validation concerns that dominate my field. However, the framework was designed for a domain with hard physical constraints and longitudinal panel data -- two properties that education ABMs typically lack. Adapting the framework to education would be feasible but would require deliberate reconceptualization of hallucination detection and empirical benchmarking. Below I score each evaluation dimension and provide concrete recommendations.

---

## Dimension Scores

### 1. TPB Adaptation Effort -- Score: 5/5

The `BehavioralTheory` Protocol in `base.py` is precisely what I need. It specifies five methods -- `name`, `dimensions`, `agent_types`, `get_coherent_actions`, `extract_constructs`, and `is_sensible_action` -- none of which encode any flood-specific assumptions. The existing `TPBTheory` example in `examples.py` already demonstrates a 3-dimensional construct mapping (attitude, norm, PBC), which is structurally identical to what an SDT implementation would require.

To implement `SDTTheory`, I would:

```python
class SDTTheory:
    @property
    def dimensions(self) -> List[str]:
        return ["autonomy", "competence", "relatedness"]

    def get_coherent_actions(self, construct_levels, agent_type):
        aut = construct_levels.get("autonomy", "M")
        comp = construct_levels.get("competence", "M")
        rel = construct_levels.get("relatedness", "M")
        high = {"H", "VH"}
        if aut in high and comp in high and rel in high:
            return ["deep_study", "collaborative_learning", "seek_challenge"]
        elif comp in {"VL", "L"} and rel in {"VL", "L"}:
            return ["disengage", "surface_study"]
        elif aut in high and comp in {"VL", "L"}:
            return ["seek_help", "tutoring"]
        # ... remaining mappings
```

This is roughly 60-80 lines of code. The Protocol's use of `Dict[str, str]` for construct levels and `List[str]` for actions is theory-agnostic. The `is_sensible_action` fallback method elegantly handles the combinatorial explosion that SDT's three continuous dimensions create -- I can define strict rules for extreme combinations and use the fallback for the moderate middle.

**One concern**: The existing `compute_l1_metrics()` function in `l1_micro.py` (lines 73-126) is still hard-coded to PMT imports (`PMT_OWNER_RULES`, `_extract_tp_label`, `_extract_cp_label`). The Protocol exists but is not yet wired into the metric computation pipeline. This means I would need to either (a) modify `compute_l1_metrics` to accept a `BehavioralTheory` instance, or (b) write a parallel computation function. Option (a) is cleaner and appears to be the intended Phase 3 evolution.

**Recommendation**: Refactor `compute_l1_metrics(traces, agent_type, theory: BehavioralTheory)` to use the Protocol's `extract_constructs()` and `get_coherent_actions()` instead of hard-coded PMT functions. This is probably 2-3 hours of work.

---

### 2. Cross-Sectional Data Only -- Score: 3/5

This is the most significant adaptation challenge. The L2 benchmarks in the flood domain (`l2_macro.py`, `flood_benchmarks.yaml`) are all cumulative rates computed from longitudinal traces: insurance rate, elevation rate, buyout rate, lapse rate. These require multi-year simulation data.

With only cross-sectional survey data (my 500 students), I face two problems:

**Problem A: No temporal trajectory.** I cannot compute temporal metrics like insurance lapse rate or post-flood adaptation spike. However, I *can* compute cross-sectional prevalence benchmarks. For example:
- Fraction of students using deep learning strategies: literature says 0.25-0.40 (Biggs & Tang, 2011)
- Help-seeking rate among struggling students: 0.15-0.35 (Karabenick & Knapp, 1991)
- Disengagement rate by semester: 0.10-0.25 (Fredricks et al., 2004)

These map directly onto the `BenchmarkSpec` dataclass in `config_loader.py` (lines 47-53). The framework's weighted EPI calculation would work without modification.

**Problem B: "Empirical plausibility" changes meaning.** In the flood domain, EPI means "simulated population rates fall within empirically observed ranges." For cross-sectional data, "plausibility" would mean "the distribution of LLM-agent behaviors resembles the distribution in my survey sample." This is more like a goodness-of-fit test than a range check.

**Recommendation**: For cross-sectional domains, add an alternative L2 mode: `distributional_match` that computes chi-squared or KL-divergence between simulated and observed behavioral distributions, rather than checking whether aggregate rates fall within literature ranges. The current range-check approach still works for literature-sourced benchmarks, but my survey data enables a stronger test.

**What I can use immediately**: EBE (behavioral entropy) from L1 is fully applicable -- it checks whether my LLM students show reasonable behavioral diversity without requiring longitudinal data. CACR is also fully applicable to cross-sectional snapshots.

---

### 3. Soft vs Hard Constraints -- Score: 2/5

This is where the framework's flood-domain origins create the most friction. The hallucination rules in `flood_rules.yaml` and `flood.py` are binary physical impossibilities:
- Cannot elevate an already-elevated home (physical state conflict)
- Cannot make decisions after being bought out (logical state conflict)
- Renter cannot elevate (agent-type conflict)

In education, nearly all "impossible" behaviors are probabilistically implausible rather than physically impossible. A failing student *can* choose an advanced research project -- it is unlikely and pedagogically concerning, but not impossible the way double-elevation is. Examples of education "soft hallucinations":

| Scenario | Plausibility | Flood Equivalent |
|----------|-------------|------------------|
| Student with 0 prerequisites choosing graduate seminar | Very low but possible | Renter elevating (blocked) |
| Student reporting high autonomy but never attending | Inconsistent but human | Already elevated re-elevating (blocked) |
| Student with test anxiety choosing oral exam format | Unlikely but adaptive | N/A -- no equivalent |

The binary `_is_hallucination() -> bool` return type cannot express "this is 95% implausible." The `HallucinationRule` dataclass in `config_loader.py` has no `severity` or `probability` field.

**Recommendation**: Extend `HallucinationRule` with a `severity: str` field (values: `hard`, `soft`, `warning`) and modify `_is_hallucination` to return a `HallucinationResult` with `{is_hallucination: bool, severity: str, confidence: float}`. Soft hallucinations would be flagged but counted separately from R_H. This would give:
- `R_H_hard`: physical impossibilities (should be 0)
- `R_H_soft`: probabilistically implausible behaviors (can tolerate up to 0.15-0.20)
- `R_H_warning`: unusual but defensible behaviors (logged but not penalized)

This tiered approach would also benefit the flood domain -- some flood behaviors are "unlikely but not impossible" (e.g., a low-income household choosing the most expensive elevation option).

---

### 4. Construct Validity Concern -- Score: 3/5

The README (line 263) explicitly acknowledges this limitation: "CACR checks whether LLM-generated TP/CP labels are consistent with actions = self-consistency, not construct validity." This is refreshingly honest, and the documentation labels it as "construct label circularity."

In psychology, this is a fundamental problem. When we validate a measurement instrument (e.g., the Academic Motivation Scale), we require:
1. **Internal consistency** (Cronbach's alpha) -- analogous to CACR
2. **Convergent validity** -- the measure correlates with theoretically related constructs
3. **Discriminant validity** -- the measure does NOT correlate with theoretically unrelated constructs
4. **Criterion validity** -- the measure predicts real-world outcomes

CACR addresses only (1). The L3 cognitive validation (ICC, eta-squared) partially addresses (3) -- if different personas yield different responses, the LLM is discriminating. But none of the metrics address (2) or (4).

For my use case, this means: if the LLM labels a student as having "high autonomy" and then chooses a self-directed study strategy, CACR says "coherent." But we have no evidence that the LLM's concept of "autonomy" matches Deci & Ryan's (1985) operationalization of autonomy. The LLM might be using a folk-psychological definition.

**What the framework does well**: The `extract_constructs()` method in the Protocol forces the researcher to define the mapping between LLM output and theoretical constructs. This is better than most LLM-ABM papers, which never make this mapping explicit. The CACR decomposition (raw vs. final) is also valuable -- it separates LLM reasoning quality from governance effects.

**Recommendation**: Add an optional L0 (Construct Grounding) validation level that compares LLM-generated construct labels against human-coded vignettes. For example, present the LLM with 20 student scenarios that experts have pre-coded for SDT constructs, and measure agreement (Cohen's kappa). This does not require simulation traces -- it validates the LLM's understanding of the theory before any experiment runs. The framework already mentions "construct grounding validation" as a future direction (README line 263). This should be prioritized for psychology applications.

---

### 5. L3 Cognitive Validation Portability -- Score: 4/5

The ICC/eta-squared approach is excellent for my use case. In educational psychology, we regularly use ICC to assess inter-rater reliability and eta-squared to measure effect sizes in ANOVA designs. The conceptual mapping is direct:

| Flood L3 | Education L3 Equivalent |
|----------|------------------------|
| 15 extreme personas spanning demographics | 15-20 student archetypes spanning motivation profiles |
| 10+ replicates per persona | 10+ replicates per archetype |
| ICC: same persona gives consistent TP/CP | ICC: same student archetype gives consistent SDT labels |
| eta-squared: different personas yield different responses | eta-squared: different archetypes yield different strategies |
| Directional sensitivity: high-risk persona perceives more threat | Directional sensitivity: high-autonomy student chooses more self-directed strategies |

The implementation in `launch_icc.py` and `run_cv.py` appears to be specific to the flood prompt templates and Ollama model infrastructure, but the statistical core (ICC computation, eta-squared from one-way ANOVA) is domain-agnostic.

**One concern**: The L3 validation module does not appear to have its own sub-package under `validation/metrics/` -- I found no `l3_*.py` file. The ICC computation seems embedded in `run_cv.py` and `launch_icc.py` at the experiment level rather than in the validation module. This makes it harder to reuse.

**Recommendation**: Extract the ICC/eta-squared computation into `validation/metrics/l3_cognitive.py` with a clean interface: `compute_l3_metrics(responses: pd.DataFrame, persona_col: str, response_col: str) -> L3Metrics`. This would make L3 immediately portable to any domain.

---

### 6. Small N Problem -- Score: 3/5

My model has 30-50 student agents, compared to the 400 agents in the flood ABM. This affects metrics differently:

**CACR (per-decision)**: Scales with number of decisions, not number of agents. With 50 agents over 4 semesters, I have 200 decisions. This is sufficient for a stable CACR estimate. Even 50 decisions would give a margin of error of +/-0.14 at 95% confidence (binomial), which is acceptable given the 0.75 threshold.

**EBE (behavioral entropy)**: With 5-7 possible actions and 200 decisions, entropy estimation is reliable. The concern is not N but K (number of action categories). Shannon entropy is biased downward for small samples, but with N/K > 30, the bias is negligible.

**L2 benchmarks (aggregate rates)**: This is where small N hurts. With 50 agents, a benchmark like "help-seeking rate" has a standard error of sqrt(p*(1-p)/50) ~ 0.07 for p=0.25. The benchmark ranges would need to be wider to accommodate this sampling variability. The current flood benchmarks have ranges of 0.15-0.20 width, which is appropriate for N=400 but too narrow for N=50.

**L3 ICC**: With 15-20 archetypes and 10 replicates each, ICC computation is independent of the main simulation N. No issue here.

**R_H (hallucination rate)**: With N=200 decisions, even 1 hallucination gives R_H=0.005. The 0.10 threshold is easily testable. No issue.

**Recommendation**: Add a `minimum_n_warning()` function that checks whether the sample size is sufficient for each metric and adjusts thresholds or widens confidence intervals accordingly. For L2 benchmarks with N < 100, consider using Bayesian credible intervals rather than point-estimate range checks.

---

### 7. Interdisciplinary Communication -- Score: 4/5

The documentation is strong. The README provides a clear three-level overview with a visual diagram, threshold tables, and worked examples. The `example_cv_usage.py` file is exceptionally well-structured -- four self-contained examples with inline comments that walk through synthetic data generation, metric computation, and domain adaptation. My psychology colleagues would understand Examples 1 and 4 without CS training.

**Strengths for interdisciplinary readers**:
- The explicit connection to POM framework (Grimm et al., 2005) provides credibility with social scientists
- Threshold tables with literature citations (README lines 49-61) are formatted like empirical papers
- The irrigation adaptation example demonstrates that this is not a flood-only tool
- Key Design Decisions section (README lines 283-290) addresses the "why" questions social scientists ask

**Weaknesses for psychology audiences**:
- The term "hallucination" carries different connotations in psychology (clinical) vs. AI (confabulation). The README should clarify that "hallucination" here means "action inconsistent with physical/logical constraints," not perceptual phenomena
- CACR is a novel acronym that does not map to any existing psychometric term. Adding a parenthetical "(analogous to internal consistency)" would help
- The Paradigm A vs. Paradigm B distinction in `base.py` (lines 3-6) is valuable but underdeveloped -- Paradigm B (frame-conditional, Prospect Theory) would interest behavioral economists and decision scientists, but there is no example implementation
- The documentation assumes familiarity with JSONL trace formats, which is a CS convention. A "Data Requirements" section with plain-language descriptions would help

**Recommendation**: Add a "For Social Scientists" appendix that maps framework concepts to psychometric equivalents: CACR ~ internal consistency, EBE ~ behavioral diversity index, EPI ~ criterion validity against population norms, L3 ICC ~ inter-rater reliability, R_H ~ logical error rate. This one-page translation table would dramatically improve adoption.

---

## Summary Scorecard

| Dimension | Score | Key Finding |
|-----------|-------|-------------|
| 1. TPB/SDT Adaptation Effort | 5/5 | Protocol is theory-agnostic; SDT implementation is ~60 lines |
| 2. Cross-Sectional Data Only | 3/5 | L1 works fully; L2 needs distributional-match mode; no temporal metrics |
| 3. Soft vs Hard Constraints | 2/5 | Binary hallucination check inadequate for probabilistic domains |
| 4. Construct Validity | 3/5 | Honest about circularity; needs L0 construct grounding level |
| 5. L3 Portability | 4/5 | Statistical core is domain-agnostic; needs extraction into reusable module |
| 6. Small N Problem | 3/5 | CACR/EBE/R_H fine at N=50; L2 benchmarks need wider intervals |
| 7. Interdisciplinary Communication | 4/5 | Strong examples and documentation; needs psychometric translation table |
| **Overall** | **3.4/5** | |

---

## Top 3 Recommendations (Priority Order)

1. **Add severity-graded hallucination detection** (hard/soft/warning) to support domains without physical impossibilities. This is the single change that would most broaden the framework's applicability beyond water resources.

2. **Refactor `compute_l1_metrics` to accept a `BehavioralTheory` instance** instead of hard-coded PMT imports. The Protocol exists but is not yet integrated into the computation pipeline.

3. **Add L0 Construct Grounding validation** -- compare LLM construct labels against expert-coded vignettes (Cohen's kappa) before running any simulation. This addresses the construct validity gap that psychologists will immediately identify.

---

## Would I Use This Framework?

**Yes, with modifications.** The three-level architecture is sound and maps well onto psychometric validation standards. No competing framework offers anything close to this level of rigor for LLM-ABM validation. The `BehavioralTheory` Protocol means I can implement SDT without modifying the core framework. The main barriers are the binary hallucination check and the absence of L0 construct grounding -- both addressable in 1-2 development sprints.

For my immediate next step, I would implement `SDTTheory` as a proof-of-concept, run L1 metrics on a small (30-agent, 4-semester) pilot with synthetic traces, and evaluate whether CACR and EBE produce interpretable results for educational decision-making. If they do, I would commit to a full adaptation including custom L2 benchmarks and L3 archetype probing.

---

*Review prepared by Dr. Aisha Okafor for the WAGF C&V Expert Panel, 2026-02-14*
