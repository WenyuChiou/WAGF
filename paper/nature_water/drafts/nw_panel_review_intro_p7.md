# Nature Water Expert Panel Review: Introduction P7 (Results Preview)
## Date: 2026-02-23 | Target: Revised P7 of Introduction v14

---

## Panel Composition

- **NW Reviewer** (Nature Water / water science): Evaluates whether findings are framed as water-system insights, whether the paragraph speaks to water resource management audiences, and whether jargon is appropriate for the journal.
- **ABM Reviewer** (agent-based modelling): Evaluates whether claims about ABM limitations and LLM-agent advantages are accurate and well-supported, and whether the PMT baseline comparison is fair.
- **Methods Reviewer** (statistical/computational): Evaluates whether quantitative claims are precise, whether statistical language is correct, and whether the paragraph's logic holds together.

---

## Individual Assessments

### NW Reviewer

**Overall impression**: The paragraph is substantially improved from earlier versions. It leads with water findings (adaptive exploitation) rather than computational architecture, which is correct for Nature Water. The two-domain framing (irrigation + flood) grounds the work in concrete water problems before any methodological claims.

**Strengths**:
1. The adaptive exploitation sentence is strong and water-specific. "Exploit water more aggressively during abundance and curtail during drought" is immediately legible to a water resource audience.
2. The final sentence ("experimentally probing how specific institutional designs shape adaptive water behaviour") connects the computational contribution back to water governance, which is the right landing point.
3. Scale numbers (78 agents, 42 years, 9,800 decisions) are concrete and appropriate.

**Concerns**:
1. **R2 (A1 ablation) is essentially invisible.** The final sentence hints at rule ablation ("independently enabled, disabled, or reconfigured") but never previews the key finding: removing one rule collapses drought coupling while increasing diversity. This is the most water-relevant methodological result — it shows that a single institutional rule (demand ceiling) is responsible for coupling individual decisions to basin state. A NW reader would find this more compelling than the model-scale generalization.
2. **"Neither mathematical optimization nor rule-based agents can represent"** is a strong negative claim. Mathematical optimization certainly can represent state-contingent extraction (that is literally what stochastic dynamic programming does). The claim should be about *reasoning processes*, not outcomes. Suggested: "that emerges from linguistic reasoning rather than parameterized response functions."
3. **"3B to 27B parameters, two model families"** — this is ML jargon that means nothing to a water scientist. The NW reader cares that the finding holds across different computational implementations, not about parameter counts. Consider "across six model configurations" or simply omit the parameter range.
4. **"Irrational behaviour rates from 0.8-11.6% to below 1.7%"** — the IBR numbers are precise but will puzzle a NW reader who has no context for what "irrational behaviour" means here. This detail is better left to Results.

**Verdict**: The paragraph correctly prioritises water findings but needs (a) an explicit R2 preview and (b) removal of ML-specific detail.

---

### ABM Reviewer

**Overall impression**: The PMT comparison is well-positioned and the claim is carefully scoped. The paragraph correctly establishes a three-way comparison (governed LLM > rule-based PMT > ungoverned LLM) without overstating the result.

**Strengths**:
1. Citing Haer et al. (2017) by name in P7 creates a direct bridge to P3 where PMT was introduced as a representative ABM approach. The reader can track the argument.
2. "Operating under the same behavioural theory with parameterized heterogeneity" is precise — it clarifies that the comparison is fair (same theory, different implementation format).
3. "Qualitatively richer decision repertoires than numerical threshold models" is an accurate characterisation. PMT threshold models produce variation only through parameter differences; language-based agents produce variation through different reasoning paths.

**Concerns**:
1. **"Neither mathematical optimization nor rule-based agents can represent"** — I agree with NW Reviewer. Stochastic optimisation can produce state-contingent policies. The unique contribution is that *the reasoning process is observable*, not that the output pattern is unreachable. Consider: "a pattern of adaptive exploitation whose underlying reasoning process — visible in language — neither optimization models nor rule-based agents expose."
2. **"Ungoverned agents collapse into repetitive demand patterns"** — this is fine for irrigation (77-82% demand increases), but in flood the ungoverned collapse is into inaction (85.9% do_nothing). The word "demand" is irrigation-specific. Consider "repetitive behavioural patterns" to cover both domains.
3. **The PMT sentence could be tightened.** "Governed agents also produced higher strategy diversity than a rule-based Protection Motivation Theory baseline (Haer et al., 2017) operating under the same behavioural theory with parameterized heterogeneity" is 27 words. The parenthetical "operating under the same behavioural theory with parameterized heterogeneity" could move to Results where it can be unpacked properly. In P7, something like "than a hand-coded Protection Motivation Theory baseline (Haer et al., 2017)" preserves the key claim at lower word cost.

**Verdict**: PMT comparison is well-framed. Minor wording fixes needed to avoid irrigation-specific language in a two-domain preview.

---

### Methods Reviewer

**Overall impression**: The paragraph attempts to preview four results in roughly 180 words (excluding the setup sentence). This is ambitious but structurally sound. The quantitative claims are accurate against the Results tables.

**Strengths**:
1. The progression is logical: setup (two domains) -> R1 (adaptive exploitation) -> R3 (PMT baseline) -> R4 (cross-domain generalisation) -> method contribution.
2. "Five of six model scales tested... three statistically significant" correctly characterises Table 3 without cherry-picking.
3. The final sentence positions the method contribution as a consequence of the findings, not as the primary claim. This is the right framing for Analysis format.

**Concerns**:
1. **R2 is missing.** The paragraph previews R1, R3, and R4, but R2 (A1 ablation: removing demand ceiling collapses coupling while increasing diversity, establishing adaptive vs. arbitrary diversity) is not previewed. This is a significant omission because R2 provides the mechanistic evidence for R1. Without R2, the adaptive exploitation claim is correlational ("governed agents do X") rather than causal ("removing one rule eliminates X"). The final sentence about "independently enabled, disabled, or reconfigured" is a capability statement, not a finding preview.
2. **"Significantly for four of six models"** — the word "significantly" appears twice in the same sentence (once for EHE, once for IBR). The reader cannot easily parse which claim has which statistical support. Consider splitting into two sentences.
3. **"0.8-11.6% to below 1.7%"** — the precision is fine but the range format (0.8-11.6%) is ambiguous. Is the range across models or across seeds? The Results make clear it is across models, but P7 does not specify. At minimum, add "across models."
4. **Sentence count and paragraph length.** The paragraph contains 7 sentences spanning approximately 180 words of findings-preview after the 50-word setup sentence. For Nature Water, this is acceptable but at the upper bound. If R2 is added, something else should be compressed or removed to avoid an unwieldy paragraph.

**Verdict**: Structurally sound but R2 omission weakens the causal logic. Statistical claims need clearer attribution.

---

## Cross-Discussion

**All three reviewers agree on the following points:**

1. **R2 must be previewed explicitly.** The A1 ablation is the mechanistic backbone of the paper. It transforms "governed agents do better" (correlational) into "this specific rule causes this specific coupling" (causal). The current final sentence alludes to the capability but does not state the finding. This is the panel's highest-priority recommendation.

2. **"Neither mathematical optimization nor rule-based agents can represent"** is overreaching. The panel recommends reframing around observability of reasoning processes, not impossibility of outcomes.

3. **ML jargon ("3B to 27B parameters, two model families") should be softened.** NW Reviewer wants it removed entirely; Methods Reviewer suggests "across six model configurations spanning two architectures"; ABM Reviewer is neutral. Consensus: replace parameter counts with a qualitative descriptor.

**Point of disagreement: IBR numbers in P7**

- NW Reviewer: Remove entirely; detail belongs in Results.
- Methods Reviewer: Keep but clarify "across models."
- ABM Reviewer: Keep a simplified version ("governance nearly eliminates irrational behaviour") without the specific percentages.
- **Resolution**: Use the ABM Reviewer's compromise — a qualitative claim here, numbers in Results.

**Point of disagreement: PMT sentence length**

- ABM Reviewer: Shorten by removing "operating under the same behavioural theory with parameterized heterogeneity."
- NW Reviewer: Keep — it is important for a NW reader to understand the comparison is fair.
- Methods Reviewer: Neutral.
- **Resolution**: Keep a shortened version. "Hand-coded" already implies parameterized; "operating under the same behavioural theory" adds fairness context. Compromise: "than a hand-coded Protection Motivation Theory baseline (Haer et al., 2017) operating under the same behavioural theory."

---

## Consensus Recommendations (Numbered, Priority-Ordered)

### Priority 1 (Must fix)

**1. Add explicit R2 preview (A1 ablation / adaptive vs arbitrary diversity).**
The paragraph must state the finding, not just the capability. Insert after the adaptive exploitation sentences and before the PMT sentence. Suggested insertion:

> "Removing a single institutional rule — the demand ceiling — collapsed this drought coupling (r = 0.547 to 0.234) while increasing strategy diversity, establishing that governance channels diversity toward adaptive patterns rather than merely expanding the action space."

This gives the reader the causal mechanism before the cross-domain evidence.

**2. Reframe "neither mathematical optimization nor rule-based agents can represent."**
Replace with language about reasoning process observability, not output impossibility. Suggested:

> "a pattern of adaptive exploitation whose underlying reasoning — visible in natural language — is compressed away by parameterized decision functions"

This is defensible (parameterized functions do not expose reasoning) and avoids the false claim that optimisation cannot produce state-contingent extraction.

### Priority 2 (Should fix)

**3. Replace ML parameter jargon.**
Change "five of six model scales tested (3B to 27B parameters, two model families)" to "five of six language models tested (spanning two model families and three parameter scales)." Move specific parameter counts to Methods or Results.

**4. Simplify IBR claim.**
Change "governance reduces irrational behaviour rates from 0.8-11.6% to below 1.7%, significantly for four of six models" to "governance nearly eliminates physically irrational behaviour across models (details in Results)." Alternatively, keep one aggregate number but drop the range.

**5. Fix "repetitive demand patterns" to be domain-general.**
Change "repetitive demand patterns" to "repetitive behavioural patterns" since the flood domain collapse is into inaction, not demand increases.

### Priority 3 (Consider)

**6. Split the R4 + IBR compound sentence.**
The sentence "This governance effect on strategy diversity is positive for five of six model scales tested... while governance reduces irrational behaviour rates..." packs two distinct claims (EHE effect + IBR reduction) into one sentence with two "significantly" qualifiers. Consider splitting:

> "This governance effect on strategy diversity is positive for five of six language models tested, three statistically significant. Governance also nearly eliminates physically irrational behaviour, with significant reductions in four of six models."

**7. Evaluate paragraph length after R2 insertion.**
If R2 is added per Recommendation 1, the paragraph will be approximately 210 words of findings-preview. This is acceptable for Nature Water Analysis format but at the limit. If it feels overloaded, the IBR claim (Recommendation 4) can be cut entirely — it is a secondary finding that can debut in R4 of Results without preview.

---

## Suggested Rewrite of P7 (Incorporating Recommendations 1-6)

> Here we test this hypothesis across two contrasting water domains: irrigation management in the Colorado River Basin (78 agents, 42 years, generating over 9,800 governed decisions across three seeds) and household flood adaptation (100 agents, 10 years, stochastic flood events, 3,000 governed decisions validated against empirical behavioural benchmarks). Governed agents exploit water more aggressively during abundance and curtail during drought — a pattern of adaptive exploitation whose underlying reasoning, visible in natural language, is compressed away by parameterized decision functions. Ungoverned agents collapse into repetitive behavioural patterns. Removing a single institutional rule — the demand ceiling — collapsed this drought coupling while increasing strategy diversity, establishing that governance channels diversity toward adaptive patterns rather than merely expanding the action space. Governed agents also produced higher strategy diversity than a hand-coded Protection Motivation Theory baseline (Haer et al., 2017) operating under the same behavioural theory — demonstrating that language-based reasoning generates qualitatively richer decision repertoires than numerical threshold models. This governance effect on strategy diversity is positive for five of six language models tested, three statistically significant. Governance also nearly eliminates physically irrational behaviour, with significant reductions in four of six models. Because each institutional rule can be independently enabled, disabled, or reconfigured, the approach functions as a method for experimentally probing how specific institutional designs shape adaptive water behaviour — a computationally governed representation of how people reason about water under uncertainty.

**Word count (findings-preview)**: ~200 words. **Total P7**: ~250 words (including setup sentence).

---

## Summary Scorecard

| Question | Verdict |
|----------|---------|
| 1. Does P7 preview all four results? | NO — R2 missing. Fixed in rewrite. |
| 2. Is PMT sentence well-positioned? | YES — correctly placed after R1, before R4. Minor tightening suggested. |
| 3. Is R2 adequately previewed? | NO — only implicit. Must be explicit. Highest priority. |
| 4. Are priority highlights correct for NW? | YES — water first, method second. Correct order. |
| 5. Any phrasing too CS/ML? | YES — "3B to 27B parameters", IBR ranges. Fixed in rewrite. |
| 6. Is the paragraph too long? | BORDERLINE — acceptable after rewrite, but monitor after R2 insertion. |

---

*Panel review generated 2026-02-23. Three reviewers, consensus reached on all priority recommendations.*
