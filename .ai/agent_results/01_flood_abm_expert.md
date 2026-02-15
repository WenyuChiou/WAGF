# C&V Validation Module Expert Review
## Reviewer: Dr. Maria Santos, Flood Risk ABM Researcher
## Date: 2026-02-14

---

## Executive Summary

The WAGF C&V (Construct & Validation) module offers a genuinely novel contribution to LLM-ABM validation. It is the first framework I have seen that operationalizes theory-informed behavioral fidelity testing at three levels (cognitive, micro-decision, macro-aggregate) with quantitative pass/fail thresholds. As someone who has spent 15 years validating flood ABMs using NetLogo and MASON, I find much to admire here -- and several areas where the module falls short of what I would need for my own NSF-funded research.

**Overall Assessment: 3.7 / 5.0** -- A strong prototype with clear academic value, but not yet production-ready for adoption by external researchers.

---

## Dimension 1: Onboarding Ease

**Score: 3 / 5**

### Strengths

- The README (`examples/multi_agent/flood/paper3/analysis/README.md`) is well-structured with the three-level architecture diagram (lines 13-25) and clear metric tables for L1/L2/L3. A new researcher can quickly grasp *what* the module validates.
- The `example_cv_usage.py` file is excellent -- four progressive examples from L1 micro (hand-crafted traces) to domain adaptation (irrigation). This is exactly the kind of worked example that my grad students would need. The synthetic data generation in Example 2 (lines 179-288) is particularly helpful because it shows realistic PMT-based decision logic.
- The input format specification (README lines 109-131) with JSONL + CSV examples is clear and minimal.

### Weaknesses

- **Installation is unclear.** The README says `pip install pandas numpy` (line 79) but the module also requires `pyyaml` for YAML config loading (`config_loader.py`, line 12). This optional dependency creates a silent fallback path -- if YAML is missing, the module silently uses hard-coded defaults. A researcher might not even realize they are running without their custom config.
- **No `pyproject.toml` or `setup.py`.** The validation module is nested 7 directories deep (`examples/multi_agent/flood/paper3/analysis/validation/`). To use it, you need to manipulate `sys.path` manually (`compute_validation_metrics.py`, lines 26-38). This is a serious adoption barrier. I cannot `pip install wagf-validation` and import it cleanly.
- **The example file imports from `compute_validation_metrics`** (line 28 of `example_cv_usage.py`), which itself is a backward-compatibility wrapper that re-exports from the `validation/` package. This indirection is confusing for a new user who wants to understand the actual module structure.
- **No Jupyter notebook.** For an academic audience, a notebook walkthrough would be far more accessible than a Python script.

### Recommendation

Package the `validation/` directory as a standalone installable module. Add a `notebooks/` directory with a quickstart Jupyter notebook. Document the YAML dependency explicitly.

---

## Dimension 2: Theory Integration

**Score: 4 / 5**

### Strengths

- The `BehavioralTheory` Protocol (`validation/theories/base.py`) is well-designed. It uses Python's `Protocol` type (runtime-checkable), which means any class implementing the 5 required methods/properties can be used without inheritance. This is the correct architectural choice for extensibility.
- The two-paradigm distinction (lines 5-6 of `base.py`) -- Paradigm A (Construct-Action Mapping) for PMT/TPB/HBM vs. Paradigm B (Frame-Conditional) for Prospect Theory/Nudge -- shows sophisticated understanding of behavioral theory heterogeneity.
- The PMT implementation (`validation/theories/pmt.py`) covers all 25 (TP x CP) combinations for both owners (lines 15-45) and renters (lines 47-75). The rules are defensible:
  - High Threat + High Coping -> active protection (buy_insurance, elevate, buyout) aligns with Rogers (1983) and Grothmann & Reusswig (2006).
  - High Threat + Low Coping -> do_nothing (fatalism) aligns with maladaptive coping appraisal failure (Rogers 1975).
  - Low Threat + any CP -> do_nothing or habitual insurance aligns with PADM (Lindell & Perry 2012, explicitly cited on line 34).
  - The inclusion of `buy_insurance` in low-threat / high-coping cells (lines 35-38) is a thoughtful PADM extension -- insurance as habitual prudent behavior regardless of threat level.
- The `extract_constructs()` method (lines 134-151) supports nested extraction paths (`skill_proposal.reasoning.TP_LABEL`) with fallback to top-level keys -- this is robust to trace format variations.
- Example implementations for TPB and Irrigation WSA (`validation/theories/examples.py`) demonstrate extensibility convincingly.

### Weaknesses

- **PMT is still hard-coded in the computation pipeline.** Despite the beautiful `BehavioralTheory` Protocol, `l1_micro.py` (lines 17-21) directly imports `PMT_OWNER_RULES` and `PMT_RENTER_RULES`. The `compute_l1_metrics()` function (line 73) takes `agent_type: str` and selects rules with a ternary operator (line 75). It does NOT accept a `BehavioralTheory` instance. This means the Protocol is aspirational, not functional -- you cannot actually plug in TPB or PADM without modifying `l1_micro.py`.
- **The sensibility check (`_is_sensible_action`, pmt.py lines 82-93) is ad hoc.** It uses ordinal numeric mapping (VL=1...VH=5) and hardcoded thresholds (`tp_level >= 4 and cp_level >= 3`). This is not derived from PMT theory; it is a hand-tuned heuristic. A reviewer specializing in PMT would question why the threshold is at 4/3 and not 3/3, and why the function returns `True` for all low-threat cases (line 90) regardless of the action.
- **No PADM implementation.** Despite citing Lindell & Perry (2012) multiple times, PADM is not actually implemented as a separate theory. The PADM-inspired rules (insurance as habitual behavior for low threat) are folded into the PMT rule table. A purist would argue this conflates two theories.
- **No social influence dimension.** PMT as implemented is purely individual-cognitive. In my own flood ABM work, social norms (neighbors' actions, community-level adaptation rates) significantly modulate coping appraisal. The current 2D (TP x CP) mapping cannot capture this without a third dimension.

### Recommendation

Wire the `BehavioralTheory` Protocol into `compute_l1_metrics()` as the primary parameter, falling back to PMT only as default. Replace the ad hoc sensibility check with a theory-method call. Consider a 3D extension for PMT that includes a social influence dimension (SN for Subjective Norm).

---

## Dimension 3: Benchmark Rigor

**Score: 3.5 / 5**

### Strengths

- The 8 benchmarks (`validation/benchmarks/flood.py`, lines 21-62) cover four important categories: aggregate uptake (B1-B4), conditional behavior (B5, B7), demographic disparity (B6), and temporal dynamics (B8). This is more comprehensive than most ABM validation I have seen.
- Each benchmark has a defensible literature source. Key references:
  - B1 (SFHA insurance 0.30-0.60): Choi et al. 2024 + de Ruig et al. 2023 -- good recent sources.
  - B5 (post-flood inaction 0.35-0.65): Grothmann & Reusswig 2006 + Bubeck et al. 2012 -- canonical PMT flood papers.
  - B6 (MG adaptation gap 0.05-0.30): Elliott & Howell 2020 -- appropriate environmental justice reference.
  - B8 (insurance lapse 0.15-0.30): Michel-Kerjan et al. 2012 -- the definitive NFIP lapse study.
- The composite MG adaptation gap metric (B6, lines 141-159) counts ANY protective action (insurance OR elevation OR buyout OR relocation) rather than a single proxy. This is methodologically sound and avoids the narrow-proxy fallacy.
- The weighted EPI formula (l2_macro.py, line 93) with B5 at weight=1.5 and B6 at weight=2.0 appropriately emphasizes the most policy-relevant benchmarks.

### Weaknesses

- **Benchmark ranges are wide.** B2 (overall insurance rate 0.15-0.55) spans 40 percentage points. B3 (elevation rate 0.10-0.35) spans 25 percentage points. At these ranges, a random model could pass several benchmarks by chance. A reviewer might compute the probability of random pass and find it uncomfortably high.
- **B3 (elevation rate 0.10-0.35) seems high.** National elevation rates post-disaster are typically 3-12% of SFHA properties (FEMA HMGP data). The 0.10-0.35 range appears to be for a highly subsidized post-Sandy scenario (Brick Township). This is acknowledged in the README as a specific case study, but using it as a "general" benchmark is questionable.
- **B8 (insurance lapse rate 0.15-0.30) computes lapse from action traces** (flood.py lines 171-199). The computation is fragile: it infers "insured" from `action == "buy_insurance"` in any prior year, then checks if the next year's action is not "buy_insurance". This misses agents who maintain insurance via `do_nothing` (i.e., passive renewal). Real insurance lapses are non-renewal events, not "chose a different action."
- **No confidence intervals or effect sizes.** The benchmarks are binary pass/fail against a range. There is no reporting of how far inside/outside the range a benchmark falls, and no statistical test (e.g., bootstrap CI). This limits the diagnostic value.
- **NOTE on discrepancy**: The README (`README.md`) and `CLAUDE.local.md` show *different* benchmark ranges. For example, B1 is 0.30-0.60 in the README but 0.30-0.50 in CLAUDE.local.md; B3 is 0.10-0.35 in README but 0.03-0.12 in CLAUDE.local.md. This inconsistency would immediately flag concerns in peer review. The code in `flood.py` uses 0.30-0.60 and 0.10-0.35, so the CLAUDE.local.md values appear to be stale. This kind of documentation drift is dangerous.

### Recommendation

Tighten benchmark ranges where literature supports it (especially B2 and B3). Fix the insurance lapse logic to distinguish non-renewal from action switching. Add distance-from-range or z-score metrics alongside binary pass/fail. Synchronize all documentation with the code's actual values.

---

## Dimension 4: C&V Vulnerability (Most Likely Peer Review Challenges)

**Score: 3 / 5**

### Challenge 1: CACR Circularity

The most serious vulnerability is **CACR circularity**, which the authors themselves acknowledge (README line 263). CACR checks whether the LLM's self-reported TP/CP labels are consistent with its chosen action. But the LLM generates BOTH the labels AND the action in the same prompt. A sophisticated reviewer would argue this is self-consistency, not construct validity.

The CACR decomposition (`l1_micro.py` lines 141-260) partially addresses this by separating `cacr_raw` (pre-governance) from `cacr_final` (post-governance). If `cacr_raw` is high, the LLM is coherent before any external filtering. This is a clever defense, but it still does not demonstrate that the LLM's TP/CP labels correspond to the psychological constructs Rogers (1975, 1983) intended. For that, you would need:
- **External construct measurement**: Present the same scenario to human subjects and compare their TP/CP ratings with the LLM's.
- **Discriminant validity**: Show that TP and CP are not just proxies for each other (they should have distinct factor loadings if probed with multiple items).

### Challenge 2: EPI Threshold Selection

The EPI threshold of 0.60 (l2_macro.py, line 28) seems arbitrary. Why 0.60 and not 0.50 or 0.70? With 8 benchmarks and generous ranges, 0.60 is achievable by many models. A reviewer might ask: "What is the baseline EPI of a random-action model? If it is 0.30, then 0.60 is meaningful. If it is 0.45, then 0.60 is weak."

### Challenge 3: No Spatial Validation

The README acknowledges this (line 264), but for a flood ABM paper, the absence of spatial validation (Moran's I, flood zone gradient analysis) is a significant gap. Flood adaptation is inherently spatial -- proximity to rivers, neighborhood effects, SFHA designation all drive decisions. A reviewer from the hydrological community would expect spatial metrics.

### Challenge 4: Governance as Institutional Constraint

The framework treats REJECTED proposals as analogous to institutional barriers (README line 286). This is a defensible interpretation, but it conflates two phenomena:
1. **Real institutional constraints** (e.g., a renter cannot elevate a home they do not own)
2. **LLM output filtering** (governance rejects incoherent outputs)

A reviewer could argue that the latter is an artifact of the LLM's limitations, not an institutional phenomenon. The constrained non-adaptation rate (l2_macro.py lines 143-155) is a useful supplementary metric, but it does not resolve this ambiguity.

### Challenge 5: Theory-Model Coupling

The PMT rules are defined by the researchers, and the LLM is prompted with PMT-derived constructs. The validation then checks whether the LLM's outputs conform to the researchers' PMT rules. This creates a feedback loop: if the rules are wrong, the validation would still pass as long as the LLM follows the (wrong) rules consistently. There is no independent test of whether the rules themselves accurately represent PMT.

### Recommendation

Add a "baseline EPI" computation using a uniform-random action model. Implement at least one spatial metric (Moran's I on adaptation decisions). Commission an independent construct validity study (even a small one with N=50 human subjects) to break the CACR circularity.

---

## Dimension 5: Historical Data Dependency

**Score: 3.5 / 5**

### For Researchers WITH Historical Flood Data

The framework works well. The trace format (JSONL) is flexible enough to accommodate any simulation output. The agent profile CSV format (agent_id, tenure, flood_zone, mg) is minimal and adaptable. The benchmark ranges are based on US NFIP data, so they are directly applicable to US flood studies.

### For Researchers WITHOUT Historical Data

The framework is much harder to use. The 8 benchmarks (flood.py) are hard-coded for US flood contexts. A researcher studying flood adaptation in Bangladesh, the Netherlands, or Australia would need to:
1. Redefine all 8 benchmark ranges from their local literature
2. Possibly redefine the benchmark *types* (e.g., Bangladesh has no NFIP, so insurance benchmarks are irrelevant)
3. Modify the `_compute_benchmark` functions if their data structure differs

The YAML config system (`config_loader.py`) partially addresses this -- benchmark ranges can be externalized to YAML. But the *computation functions* (flood.py lines 87-199) are still hard-coded for flood-specific data columns (`flood_zone`, `final_has_insurance`, `final_elevated`, `final_bought_out`). A drought ABM researcher would need to write entirely new computation functions.

### For Researchers with Survey Data Only

If I have household survey data (PMT constructs measured via Likert scales) but no simulation traces, I cannot use this framework at all. There is no pathway to validate an LLM-ABM against survey-measured PMT constructs. This is a significant gap, because many flood adaptation studies start with survey data (e.g., Grothmann & Reusswig 2006 original study).

A useful addition would be a "survey-vs-LLM construct comparison" module: given survey-measured TP/CP distributions, compare them with the LLM's generated TP/CP distributions using KL-divergence or two-sample KS tests.

### Recommendation

Create a "benchmark template" system where users specify benchmark names, ranges, and computation functions in YAML/Python. Provide a cookbook for non-US contexts. Add a survey-data validation pathway.

---

## Dimension 6: Extensibility

**Score: 3.5 / 5**

### What Works

- **Theory extensibility** is well-architected. The `BehavioralTheory` Protocol and `TheoryRegistry` (`validation/theories/registry.py`) provide clean extension points. The TPB and Irrigation WSA examples (`validation/theories/examples.py`) are convincing demonstrations.
- **Benchmark extensibility** via the `BenchmarkRegistry` decorator pattern (registry.py lines 16-21) is clean. Adding a new benchmark requires only a `@_registry.register("new_benchmark")` decorator on a function.
- **Hallucination rule extensibility** via YAML config (`config_loader.py` lines 201-237) allows adding new physically-impossible-action rules without code changes.

### What Does Not Work

- **The pipeline itself is not extensible.** Despite the beautiful extension points, the actual execution pipeline (`engine.py`) hard-codes:
  - `load_traces()` expects specific file naming (`household_owner_traces.jsonl`, `household_renter_traces.jsonl`) on lines 30-31
  - `compute_l1_metrics()` takes `agent_type: str` and looks up PMT rules directly (l1_micro.py line 75)
  - `compute_l2_metrics()` imports `EMPIRICAL_BENCHMARKS` directly (l2_macro.py line 15)
  - The CACR decomposition assumes agent IDs follow `H####` format and infers owner/renter from numeric ID > 200 (l1_micro.py lines 178-188) -- this is extremely fragile
- **Coastal vs. riverine adaptation**: Different action spaces (seawalls, beach nourishment, managed retreat vs. levees, floodplain zoning, elevation). The current skill set (buy_insurance, elevate, buyout, relocate, retrofit, do_nothing) is riverine-centric. Extending to coastal would require new PMT rules, new benchmarks, and new hallucination rules -- all doable with the extension points, but the pipeline glue code would need modification.
- **Different countries**: As noted above, the benchmarks are US-centric. The theory layer is country-agnostic (PMT is universal), but the empirical validation is not.

### Recommendation

Refactor `compute_l1_metrics()` to accept a `BehavioralTheory` instance. Make `load_traces()` configurable for different file naming conventions. Remove the hard-coded agent ID parsing in CACR decomposition.

---

## Dimension 7: Missing Features

### Critical Missing Features

1. **Temporal trajectory validation (L2.5).** The README acknowledges this (line 265). Currently, EPI compresses 13 years into a single number. There is no validation of:
   - Post-flood adaptation spike (do agents actually increase protection after flooding?)
   - Insurance survival curves (how long do agents maintain policies?)
   - Adaptation S-curves (does cumulative adoption follow a logistic curve?)
   These temporal patterns are central to flood ABM validity. Without them, a model that produces correct aggregate rates but completely wrong dynamics would still pass.

2. **Spatial validation (L2.5).** No Moran's I, no flood zone gradient analysis, no neighborhood clustering metrics. For a 400-agent simulation in a real watershed (PRB), spatial patterns are essential.

3. **Cross-model comparison.** No built-in support for comparing validation results across different LLMs (e.g., Gemma 3 4B vs. GPT-4 vs. Claude). The `ValidationReport` stores a `model` field, but there is no comparison framework.

4. **Sensitivity analysis integration.** No connection between L3 persona probing and L1/L2 metrics. The L3 validation (ICC, eta-squared) runs independently of the main experiment. There should be a way to trace: "Agent H0042 was initialized from Archetype 7 --> L3 shows Archetype 7 has ICC=0.95 --> Agent H0042's L1 CACR is 0.82" for individual-level coherence tracking.

5. **Statistical testing for L2 benchmarks.** No bootstrap confidence intervals, no Monte Carlo baseline comparison. Binary pass/fail against wide ranges is weak for a quantitative paper.

### Important but Non-Critical Missing Features

6. **Streaming trace processing.** Currently loads all traces into memory (engine.py line 55 concatenates all traces). For 400 agents x 13 years x 54 seeds = ~2.8M traces, this will hit memory limits. The README acknowledges this (line 267).

7. **Visualization suite.** No built-in plotting functions for validation results. A researcher would need to write their own matplotlib code to visualize benchmark comparisons, CACR decomposition, action distributions, etc.

8. **Multi-seed aggregation.** The CLI supports `--all-seeds`, but there is no ensemble-level validation (e.g., "across 54 seeds, what fraction pass EPI >= 0.60?"). Individual seed validation is necessary but not sufficient.

9. **Theory-specific diagnostic reports.** When CACR is low, what specific (TP, CP) combinations are failing? The quadrant CACR decomposition (l1_micro.py lines 207-214) helps, but there should be a full confusion matrix: for each (TP, CP) pair, what actions were expected vs. observed?

10. **Automated benchmark literature lookup.** No Zotero/DOI integration for benchmark sources. Each benchmark's literature source is a comment string, not a structured citation.

---

## Summary Scorecard

| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| 1. Onboarding Ease | 3.0 | 1.0 | 3.0 |
| 2. Theory Integration | 4.0 | 1.5 | 6.0 |
| 3. Benchmark Rigor | 3.5 | 1.5 | 5.25 |
| 4. C&V Vulnerability | 3.0 | 1.0 | 3.0 |
| 5. Historical Data Dependency | 3.5 | 1.0 | 3.5 |
| 6. Extensibility | 3.5 | 1.0 | 3.5 |
| 7. Missing Features | -- | -- | (see list) |
| **Overall** | **3.7** | | |

---

## Top 5 Recommendations for the Authors

1. **Wire the BehavioralTheory Protocol into the pipeline.** The Protocol exists but is not used. `compute_l1_metrics()` should accept a `BehavioralTheory` instance as its primary parameter. This is the single highest-impact change for extensibility.

2. **Add temporal trajectory benchmarks.** At minimum: post-flood adaptation spike ratio (do agents act more protectively in the year after flooding?) and insurance survival half-life (median time before lapse). These can be computed from existing traces with no new data.

3. **Package as installable module.** Create a `pyproject.toml` with `pip install wagf-validation`. The current 7-level nesting makes adoption impractical.

4. **Compute baseline EPI.** Run a uniform-random-action model through the validation pipeline and report its EPI. If baseline EPI is > 0.30, the 0.60 threshold needs justification. This pre-empts the most likely reviewer objection.

5. **Fix the benchmark range inconsistencies.** The ranges in `flood.py`, `README.md`, and `CLAUDE.local.md` do not match. Synchronize all documentation from a single source of truth (the YAML config).

---

## Would I Adopt This for My NSF Project?

**Conditionally yes.** If the authors (a) wire the Protocol into the pipeline, (b) package it as installable, and (c) add temporal benchmarks, I would use the C&V framework as the validation backbone for my next LLM-ABM flood study. The theory integration architecture is sound, the benchmark coverage is reasonable, and the three-level validation concept (L1-L2-L3) is genuinely novel in the ABM validation literature.

Without those changes, I would likely extract the conceptual framework (the three-level architecture, CACR decomposition, EPI formula) and re-implement it in my own codebase, citing the WAGF paper but not using the code directly.

---

*Review completed by Dr. Maria Santos, 2026-02-14*
*15 papers published on household flood adaptation using PMT*
*Affiliations: [Redacted for review]*
