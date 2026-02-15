# Expert Review: LLM Engineering Perspective

**Reviewer**: Alex Kim, Senior LLM Engineer
**Date**: 2026-02-14
**Scope**: WAGF C&V Validation Module -- LLM-specific failure mode coverage

---

## Executive Summary

The C&V framework represents a genuinely thoughtful attempt to validate LLM-agent behavior, and it is ahead of most LLM-ABM papers I have reviewed (which typically stop at "looks reasonable" or "matches aggregate stats"). The three-level architecture (L1 micro, L2 macro, L3 cognitive) is structurally sound. However, from a production LLM engineering standpoint, the framework has significant blind spots around the failure modes that actually bite you in deployment: sycophancy, prompt fragility, label gaming, and distributional drift. Below I score each dimension and provide actionable recommendations.

---

## Dimension Scores

### 1. Hallucination Coverage -- Score: 2/5

**What exists**: Three rules in `hallucinations/flood.py` (lines 23-35):
- Double elevation (already elevated + elevate again)
- Bought-out agent still acting
- Renter trying to elevate (ownership-gated action)

These are correct and necessary. The YAML config in `flood_rules.yaml` mirrors these rules declaratively, which is good for auditability.

**What is missing**: These rules catch only *state-constraint violations* -- a narrow subset of LLM hallucinations. In my experience with production LLM agents, the more dangerous hallucination modes are:

1. **Numerical fabrication**: The LLM invents specific dollar amounts, probabilities, or damage estimates not present in its context window. The framework never inspects the reasoning text for fabricated numbers. If the LLM says "my flood damage was $47,000" but the actual damage was $12,000, nothing catches this.

2. **Temporal confusion**: The LLM conflates past, present, and future states. For example, referencing a flood that has not occurred yet, or "remembering" an insurance policy it never purchased. The trace format includes `state_before` but nobody validates whether the LLM's *reasoning text* accurately reflects that state.

3. **Entity confusion**: In a 400-agent simulation, the LLM might reference another agent's situation, neighbor's flood zone, or community-level statistics that were never in its prompt context.

4. **Reasoning-action disconnection**: The LLM produces a coherent chain of reasoning that logically leads to action A, then outputs action B. CACR catches some of this via construct-action mapping, but it does not parse the free-text reasoning chain.

5. **Confabulated justifications**: The LLM produces plausible-sounding but fabricated citations to FEMA programs, government policies, or subsidy rates that do not match the simulation parameters.

**Recommendation**: Add a `reasoning_grounding_check` that validates key claims in the LLM's reasoning text against the actual `state_before` dictionary. Even a simple keyword-matching approach (does the reasoning mention "HIGH" zone when the agent is actually in "LOW"?) would catch a meaningful class of hallucinations.

---

### 2. Sycophancy Detection -- Score: 2/5

**What exists**: CACR measures whether the LLM's TP/CP labels align with the action it chose, using PMT theory rules as the ground truth mapping.

**The problem**: CACR is fundamentally a *self-consistency* check, not a sycophancy check. Consider this scenario:

- The prompt describes a HIGH flood zone with recent flooding, high damage, low income
- The prompt implicitly "suggests" high threat through vivid flood descriptions
- The LLM dutifully outputs TP=VH (sycophantic agreement with prompt framing)
- The LLM then picks `buy_insurance` (coherent with VH threat)
- CACR scores this as "coherent" -- correct!

But the sycophancy problem is real: if you reframe the same objective situation with neutral language, would the LLM still output TP=VH? The framework provides no mechanism to test this.

**Evidence from L3 validation**: The L3 cognitive validation (ICC probing with 15 archetypes) partially addresses this -- it tests whether the LLM differentiates between personas. The reported ICC=0.964 and eta-squared=0.33 are strong. But L3 tests *extreme* archetypes by design. The sycophancy failure mode is most dangerous in the *middle* of the construct space (M threat, M coping), where the LLM has no strong signal and is most susceptible to prompt framing effects.

**What would a proper sycophancy test look like**:
- Take 50 agents with identical objective states
- Present the same state with 3 prompt framings: threat-emphasizing, neutral, safety-emphasizing
- Measure whether TP/CP distributions shift with framing
- Report a "prompt framing sensitivity" metric (e.g., Cramer's V between framing condition and TP label)

**Recommendation**: The CACR decomposition (raw vs. final, quadrant analysis) is the strongest existing defense -- it shows the LLM reasons coherently even before governance intervenes. But it does not distinguish coherent-because-correct from coherent-because-sycophantic. Add a framing perturbation test to L3.

---

### 3. Prompt Sensitivity -- Score: 1/5

**What exists**: Nothing. There is no prompt sensitivity analysis, no ablation study protocol, and no robustness testing infrastructure in the validation module.

**Why this matters**: In my experience, small models (4B parameters) are extremely sensitive to:
- Prompt ordering (information presented first vs. last)
- Numerical formatting ($50,000 vs. 50000 vs. "fifty thousand dollars")
- Instruction phrasing ("choose an action" vs. "what would you do" vs. "select from the following")
- Context window position effects (primacy/recency bias)

For a 400-agent x 13-year simulation producing 52,000 decisions, even a 5% systematic bias from prompt phrasing could produce statistically significant but artifactual patterns.

**The MEMORY.md acknowledgment**: The project memory notes "WARNING rules = 0% behavior change for small LLMs" and "Governance suggestions = de facto commands for small LLMs." This is exactly the kind of prompt sensitivity finding that should be formalized into a validation test, not left as a project note.

**Recommendation**: Implement a "prompt perturbation protocol" as part of L3:
1. Define 5 semantically-equivalent prompt variants
2. Run 100 agents x 3 years per variant
3. Compute distributional divergence (Jensen-Shannon divergence) between variant outputs
4. Report as "Prompt Robustness Index" (PRI)
5. Threshold: JSD < 0.10 for each pair

This is the single most impactful missing validation for an LLM-ABM paper.

---

### 4. Construct Label Reliability -- Score: 2/5

**What exists**: The trace reader (`trace_reader.py`) extracts TP_LABEL and CP_LABEL from `skill_proposal.reasoning`. CACR then checks whether the action matches the PMT mapping for those labels. The UNKNOWN sentinel (line 20-21 in trace_reader.py) correctly excludes failed extractions from the denominator.

**The circularity problem**: The LLM generates BOTH the construct labels AND the action. CACR measures their mutual consistency, but this is a self-fulfilling prophecy. A sufficiently capable LLM can learn to:
1. Decide on an action first (based on whatever internal heuristic)
2. Reverse-engineer which TP/CP labels would justify that action
3. Output those labels in the reasoning field

This produces high CACR with zero actual construct reasoning. The framework has no way to distinguish genuine PMT reasoning from post-hoc rationalization.

**Partial mitigation**: The CACR decomposition (lines 141-260 in `l1_micro.py`) helps by showing raw vs. final coherence and quadrant-level breakdowns. If the LLM were simply gaming labels, you would expect uniform CACR across all quadrants. Differential quadrant performance (e.g., lower CACR in the M/M quadrant where multiple actions are valid) provides indirect evidence of genuine construct reasoning.

**What would break the circularity**:
- **External construct grounding**: Have a separate classifier (or rule-based system) assign TP/CP labels based on objective state features (flood zone, income, flood history), then compare against LLM-assigned labels. Report agreement rate as "Construct Grounding Rate" (CGR).
- **Construct perturbation**: Explicitly modify one construct input (e.g., change flood zone from HIGH to LOW) and verify the LLM's TP label shifts accordingly. The L3 "directional sensitivity" test (reported at 75%) does this to some degree, but only for extreme persona pairs.

**Recommendation**: Add CGR as an L1 supplementary metric. A rule-based TP/CP estimator from `state_before` features would take approximately 50 lines of code and would immediately break the circularity.

---

### 5. Model-Agnostic Design -- Score: 4/5

**What exists**: The validation module reads JSONL trace files with a well-defined schema (agent_id, year, outcome, skill_proposal, approved_skill, state_before, state_after). The `trace_reader.py` module handles multiple nesting patterns (lines 36-48 in `_extract_action`) and the `_normalize_action` function (lines 51-75) maps diverse action names to canonical forms.

**Strengths**:
- No model-specific code anywhere in the validation module
- The `BehavioralTheory` protocol (`theories/base.py`) is clean and extensible
- The `BenchmarkRegistry` pattern allows pluggable benchmark functions
- JSONL as interchange format is the right choice

**Minor concerns**:
- The action normalization mappings (line 59-68 in `trace_reader.py`) are hard-coded. A model that uses different action naming conventions (e.g., "purchase_flood_insurance" vs. "buy_insurance") might not be caught. The mapping should be exhaustive or configurable.
- The construct extraction assumes TP_LABEL/CP_LABEL are in `skill_proposal.reasoning`. A different model integration might place them elsewhere. The fallback to top-level `trace.get("TP_LABEL")` helps, but this path should be documented as a contract.
- Agent ID convention (H prefix, numbers > 200 = renter in `l1_micro.py` line 181) is fragile and domain-specific.

**Recommendation**: Add a `TraceSchema` validator that checks required fields exist before processing. Document the trace JSONL schema as a formal contract (JSON Schema or similar).

---

### 6. EBE as Diversity Metric -- Score: 3/5

**What exists**: Shannon entropy computed from action frequency counts (`entropy.py`), normalized by log2(k) where k = number of unique actions observed. Threshold: 0.1 < ratio < 0.9 (avoiding both monoculture and uniform randomness).

**Strengths**:
- Simple, interpretable, well-established information-theoretic metric
- The ratio normalization handles varying action space sizes
- The dual-sided threshold (not just "entropy > 0") is smart -- it catches both degenerate cases

**Limitations**:

1. **No temporal dimension**: EBE is computed over the entire trace corpus. It does not capture whether diversity is stable over time or collapses after year 5. A time-windowed entropy plot would be more informative. (The README acknowledges this as "no temporal trajectory validation.")

2. **No per-agent diversity**: EBE is a population-level metric. It cannot distinguish between "all agents use all actions" (genuine diversity) and "each agent always picks the same action, but different agents pick different actions" (Simpson's paradox). Per-agent action entropy would catch this.

3. **Sensitivity to action granularity**: With 6 canonical actions (buy_insurance, elevate, buyout, relocate, retrofit, do_nothing), max entropy is log2(6) = 2.58 bits. The EBE ratio is heavily influenced by whether rare actions (retrofit, buyout) appear at all. A single buyout in 52,000 decisions shifts k from 5 to 6 and changes ebe_max.

4. **Alternative metrics worth considering**:
   - **KL divergence from empirical distribution**: Instead of "is there diversity?", ask "does the diversity match real-world patterns?" This is partially addressed by L2 benchmarks but not at the distributional level.
   - **Effective number of actions** (exp(H)): More interpretable than raw entropy. "The population uses 3.2 effective actions" is clearer than "entropy ratio = 0.65."
   - **Temporal n-gram diversity**: Sequence-level diversity (do agents switch actions, or do they lock in?). Important because real households exhibit path dependence.

**Recommendation**: EBE is adequate as a first-pass metric. For the paper, supplement with time-windowed entropy and per-agent entropy distribution. Report effective number of actions for interpretability.

---

### 7. Missing LLM Validation -- Score: N/A (gap analysis)

The following LLM-specific validation tests are completely absent and would be expected in a serious LLM-ABM paper:

#### Critical (should block publication)

1. **Temperature/sampling sensitivity test**: The simulation presumably uses a fixed temperature for the LLM. Does changing temperature from 0.3 to 0.7 produce qualitatively different population-level outcomes? If yes, all results are contingent on an arbitrary hyperparameter. If no, that is a strong robustness finding worth reporting.

2. **Seed stability test**: Run the same 400-agent simulation 3-5 times with different random seeds (for both LLM sampling and any stochastic simulation components). Report coefficient of variation for each L2 benchmark. Without this, the single-seed results could be a lucky draw.

3. **Position bias test**: LLMs exhibit primacy and recency bias in their context windows. If the prompt lists available actions, the order matters. Shuffle action order in prompts and measure distributional shift. For a 4B model, this effect can be substantial.

#### Important (should be addressed or acknowledged)

4. **Reasoning faithfulness audit**: Manually inspect 50-100 randomly sampled reasoning traces. Do the LLM's stated reasons match its objective state? What fraction contain fabricated details? This is the standard LLM audit practice and its absence would be questioned by reviewers.

5. **Construct distribution analysis**: Plot the distribution of TP and CP labels across all 52,000 decisions. If TP=M accounts for 60% of labels, the LLM is defaulting to the middle -- a known failure mode of small models that lack confidence in extreme classifications. Report label entropy separately from action entropy.

6. **Governance dependency analysis**: What fraction of "correct" behavior (CACR, EPI) is attributable to the governance layer versus the LLM itself? The CACR decomposition (raw vs. final) exists but is supplementary. This should be a primary metric. If CACR_raw is 0.40 but CACR_final is 0.85 due to governance filtering, the LLM is not doing the reasoning -- the governance layer is.

7. **Cross-model replication**: Run at least one alternative model (e.g., Llama 3.1 8B, Phi-3) on a subset (100 agents, 3 years) and compare L1/L2 metrics. If results are wildly different, the findings are model-specific, not general. The README mentions "4B model as scope condition" which is honest, but a single cross-model check would significantly strengthen the paper.

#### Nice to have

8. **Calibration curve for construct labels**: If the LLM outputs TP=VH, how often is the agent actually in a high-threat situation (HIGH zone, recent flood, high damage)? Plot reliability diagrams. This directly addresses construct label reliability (Dimension 4).

9. **Repetition/mode collapse detection**: Over 13 years, does a given agent produce the same (TP, CP, action) tuple every year? Report the "unique decision" rate per agent. Mode collapse is a common LLM failure with repeated prompting.

10. **Sycophancy gradient test**: Systematically vary the "nudge strength" in prompts (from neutral to strong suggestion) and measure response shift. This is distinct from binary framing tests -- it characterizes the sycophancy dose-response curve.

---

## Summary Scores

| Dimension | Score | Assessment |
|-----------|-------|------------|
| 1. Hallucination Coverage | 2/5 | Catches physical impossibilities only; misses numerical, temporal, and reasoning hallucinations |
| 2. Sycophancy Detection | 2/5 | CACR measures self-consistency, not sycophancy; L3 ICC partially mitigates for extremes |
| 3. Prompt Sensitivity | 1/5 | Completely absent; single biggest gap for an LLM-ABM paper |
| 4. Construct Label Reliability | 2/5 | Fundamental circularity unbroken; no external grounding |
| 5. Model-Agnostic Design | 4/5 | Clean JSONL-based architecture; minor hardcoding issues |
| 6. EBE as Diversity Metric | 3/5 | Adequate first-pass; needs temporal and per-agent decomposition |
| 7. Missing LLM Validation | N/A | 3 critical gaps, 4 important gaps, 3 nice-to-haves |

**Overall LLM Validation Maturity: 2.3/5**

---

## Top 3 Actionable Recommendations (Prioritized)

1. **Add prompt perturbation protocol to L3** (addresses Dimensions 2, 3). Estimated effort: 2-3 days. Impact: transforms the weakest dimension (1/5) into a defensible finding. Even a negative result ("small model is prompt-sensitive") is publishable if quantified.

2. **Add construct grounding rate (CGR)** (addresses Dimension 4). Estimated effort: 1 day. A rule-based TP/CP estimator from objective state features breaks the circularity and provides an external anchor for CACR. This is low-hanging fruit.

3. **Run 3-seed replication + temperature sensitivity** (addresses Missing #1, #2). Estimated effort: compute time only (3-5 additional runs). Without this, all quantitative findings have an implicit "n=1" asterisk.

---

## Honest Assessment

The framework is architecturally well-designed and ahead of the LLM-ABM literature baseline. The README is refreshingly honest about limitations (listing construct circularity, lack of spatial/temporal validation). The BehavioralTheory protocol and BenchmarkRegistry show genuine software engineering thinking.

However, the validation is currently testing "does the simulation produce plausible population statistics?" (L2) and "are individual decisions internally consistent?" (L1). It is NOT testing "is the LLM reasoning reliably and robustly?" -- which is the question that LLM-skeptical reviewers will ask first. The gap between what the framework validates and what LLM engineering best practices require is substantial, particularly around prompt sensitivity and construct grounding.

The good news: the architecture is extensible enough that adding these tests does not require restructuring. The JSONL trace format, the BehavioralTheory protocol, and the modular validation pipeline all support incremental addition of LLM-specific tests.

---

*Review completed by Alex Kim, Senior LLM Engineer*
