# Nature Water Pre-Submission Readiness Review

**Paper**: Institutional Constraints Widen Adaptive Strategy Diversity in Language-Based Water Agents
**Format**: Analysis (~4,000 words + Methods + SI)
**Date**: 2026-02-24
**Reviewers**: 3-person expert panel (Water Resources / Computational Social Science / NW Editorial)

---

## Reviewer A -- Water Resources / Sociohydrology

### Overall Assessment
- **Verdict**: Minor Revisions
- **Confidence**: High
- **Summary**: A genuinely novel contribution that introduces language-based agents to water resource simulation with a credible governance architecture, though the simplified reservoir model and single-model irrigation design limit the strength of some claims.

### Narrative Coherence: 8/10
The paper tells a clear story: governance enables adaptive exploitation, a single-rule ablation reveals the mechanism, diversity exceeds hand-coded baselines, and the effect generalizes. The adaptive exploitation framing is compelling and water-authentic -- it correctly parallels how prior-appropriation institutions work in practice. The transition from R1 (water outcomes) to R2 (institutional decomposition) to R3 (representational advance) to R4 (generalization) is logical and well-paced.

Two weak points: (1) The jump from irrigation to flood in R4 is somewhat abrupt -- the reader has been deeply immersed in Colorado River dynamics for 1,500 words and then must suddenly care about household flood insurance. A bridging sentence framing both as "institutional governance of water risk" would help. (2) The Discussion opens by restating R1 findings rather than immediately advancing to new interpretation; the first paragraph could be tightened.

### Scientific Rigor: 6.5/10
This is where I have the most concern.

**Strengths:**
- The A1 ablation is excellent experimental design -- isolating one rule's contribution is genuinely powerful and rare in ABM work.
- The FQL baseline comparison is a valuable addition that separates the governance effect from the reasoning-format effect.
- Demand-Mead coupling as a metric is well-chosen and interpretable.
- Three seeds per condition with reported variance is adequate for the scale of agent-decisions.

**Weaknesses:**
- The reservoir model is a heavily simplified single-reservoir representation of a 12-reservoir system. The paper acknowledges this but still draws conclusions about "prior-appropriation dynamics" and "Colorado River management." The shortage tiers apply uniform curtailment rather than seniority-based curtailment, which is the defining feature of prior-appropriation. This is a significant simplification that undermines the institutional analogy the paper leans on. The paper should be more explicit that the simulated institution is "prior-appropriation-inspired" rather than prior-appropriation.
- Only one model (Gemma-3 4B) was tested in irrigation. The paper's central claims about adaptive exploitation rest entirely on this single model. The cross-model analysis exists only for the flood domain, which tests a different phenomenon (strategy diversity, not adaptive exploitation). This asymmetry weakens the generalizability claim.
- The BRI metric is confusing. Governed BRI = 58%, null random = 60%. The paper says governance "removes the increase-bias" but a BRI of 58% means governed agents are slightly *less* rational than random chance under high scarcity. This needs much more careful framing. Is 58% actually a success?
- n=3 seeds is standard for ABM but thin for the statistical claims being made. The 95% CIs from t-distributions with df=2 are very wide and the paper occasionally makes claims ("significantly for four of six models") that depend on these small-sample tests.
- The demand ceiling at 6.0 MAF is a researcher-imposed threshold, not derived from actual Colorado River operations. How sensitive are results to this value? A sensitivity analysis on the ceiling threshold would strengthen the ablation story considerably.

### Novelty & Contribution: 8/10
This is genuinely new for the water resources community. No prior work has combined LLM-based agents with formal institutional governance for water simulation. The key contributions are:
1. The governance-as-institutional-boundary concept, connecting Ostrom to computational agent architecture
2. The ablation methodology -- removing individual rules to probe institutional effects
3. Demonstrating that language agents produce qualitatively richer reasoning than parameterized ABMs

The Ostrom parallel is carefully qualified ("structural parallel... requiring empirical rather than theoretical justification") and not overclaimed. The distinction between diversity and adaptive diversity is a genuine conceptual contribution.

### Nature Water Fit: 7/10
The paper is clearly about water and clearly policy-relevant. The Colorado River and flood adaptation contexts are timely. However, the paper sometimes reads more like a methods paper (here is our framework and what it can do) than a water-science paper (here is what we learned about water governance). The "computational laboratory" framing in the Discussion is powerful but arrives late. Nature Water readers will want to know: what does this tell us about real water management? The paper gestures at this but does not fully deliver.

### Specific Issues

**MUST FIX:**
1. **BRI interpretation is misleading.** Governed BRI of 58% vs. random baseline of 60% needs honest discussion. Either reframe what "success" means here (governance removes pathological bias, not that it produces optimal decisions) or acknowledge this as a limitation. Currently the paper presents 58% as a positive result without adequate context.
2. **Irrigation single-model limitation must be foregrounded.** The abstract says "the effect generalized from chronic drought to acute flood hazard" -- but adaptive exploitation was never tested with multiple models. Only diversity was tested cross-model. This conflation must be corrected. The abstract should distinguish which claims are single-model and which are cross-model.

**SHOULD FIX:**
3. **Demand ceiling sensitivity.** Add at least a paragraph in Methods or SI discussing how the 6.0 MAF threshold was chosen and what happens at 5.5 or 6.5 MAF. If you cannot run additional experiments, at least discuss the sensitivity conceptually.
4. **Prior-appropriation framing.** Soften the PA analogy given that the model uses uniform (not seniority-based) curtailment. "Prior-appropriation-inspired shortage tiers" rather than implying faithful PA representation.
5. **Shortage years interpretation.** 13.3 shortage years (governed) vs. 5.0 (ungoverned) is presented as a positive result ("productive engagement"). But from a water manager's perspective, tripling shortage frequency is alarming. The paper needs to more carefully explain why this is adaptive rather than simply reckless.
6. **Premium doubling reversal.** The SI reports that premium doubling reverses the diversity effect. This is potentially devastating for the generality claim and should be discussed in the main text, not buried in SI.

**MINOR:**
7. Supplementary Table 7 shows that under some normalization specifications, Gemma-3 12B and Gemma-3 27B show reversed effects. This instability should be briefly noted in the main text.
8. The "42-year mean Mead elevation" in Table 1 appears to be a single number (no variance reported). Should this have variance across seeds?
9. Figure 1d: The axis labels and point annotations are small and hard to read. The "Arbitrary diversity / Adaptive diversity" labels are conceptually important but visually lost.

### Key Questions
- Q1: If governed BRI (58%) is statistically indistinguishable from random (60%), what exactly has governance achieved for rationality in the irrigation domain?
- Q2: Would the adaptive exploitation pattern survive with a larger model (e.g., Gemma-3 27B) in the irrigation domain, or is it an artifact of 4B model limitations?
- Q3: What is the physical basis for the 6.0 MAF demand ceiling? Is it calibrated to historical Colorado River total use?

---

## Reviewer B -- Computational Social Science / LLM-Agents

### Overall Assessment
- **Verdict**: Minor Revisions
- **Confidence**: High
- **Summary**: A well-executed study that advances LLM-agent simulation methodology with a principled governance architecture, though the reliance on small open-weight models and the absence of human-subject validation limit claims about behavioural representativeness.

### Narrative Coherence: 8.5/10
The paper makes a clear argument: LLM agents need governance, governance enables (not restricts) diversity, and the effect is robust. The Introduction efficiently surveys the evolution from Harvard Water Program through sociohydrology to ABMs to LLMs, positioning the contribution precisely. The "adaptive exploitation" framing is effective because it grounds a computational finding in water-domain language rather than CS jargon.

The reasoning traces in the SI are a genuine highlight. The taxonomy of 10 cognitive frames (Supplementary Table 5) demonstrates the qualitative richness that language agents produce. The memory-overriding persistence example (agent contradicting its own memory) is particularly compelling as evidence of emergent reasoning complexity.

### Scientific Rigor: 7/10
**Strengths:**
- The experimental design is sound: governed vs. ungoverned vs. ablation, with a hand-coded PMT baseline and an FQL baseline. This is more rigorous than most LLM-agent papers.
- The first-attempt analysis (Supplementary Note 3) convincingly addresses the retry confound.
- The composite-action sensitivity analysis (Supplementary Table 7) is unusually thorough for this literature.

**Weaknesses:**
- **No human-subject comparison.** The paper claims agents produce "reasoning-generated heterogeneity" that is qualitatively richer than parameterized models. But there is no comparison to actual human decision-making data. The reasoning traces look plausible, but plausibility is not validity. Park et al. (2023) at least compared agent behaviour to human ratings. Without any human benchmark, the "reasoning" could be sophisticated confabulation.
- **Temperature sensitivity.** The paper uses temperature=0.8 and explicitly notes "no temperature sensitivity analysis was conducted." For a paper whose central finding is about behavioural *diversity*, the sampling temperature is a critical confound. Higher temperature mechanically increases output diversity. This should be tested, or at minimum discussed as a major limitation.
- **Model size confound.** The strongest governance effects occur in the smallest models (Gemma-3 4B: +0.329; Ministral 3B: +0.198) while larger models show non-significant effects. This pattern suggests governance may be compensating for model incapability rather than enabling genuine adaptive behaviour. A more capable model may already produce diverse, contextually appropriate responses without governance. The paper acknowledges this ("less room for governance to expand") but does not adequately grapple with the implication: is governance a scaffold for weak models or a genuine institutional mechanism?
- **Prompt sensitivity.** The persona prompts are described as "establishing cognitive framing, institutional context, and behavioural theory orientation." How sensitive are results to prompt wording? The paper underwent extensive prompt calibration (v5 through v7d for flood), but no systematic prompt sensitivity analysis is reported. Given that LLM behaviour is notoriously prompt-sensitive, this is a significant omission.
- **The "10 cognitive frames" taxonomy** was produced by the authors through "open coding" of agent outputs. This is a qualitative method applied to synthetic data. Without inter-rater reliability or systematic coding methodology (beyond "saturation at 10"), this analysis is illustrative rather than evidential.

### Novelty & Contribution: 7.5/10
The governance-as-institution framing is the main contribution and it is genuine. Most LLM-agent work treats constraints as engineering necessities (prevent hallucination, enforce JSON). This paper reframes constraints as institutional boundaries, connecting to Ostrom and institutional theory. This is a meaningful conceptual advance.

However, the technical implementation -- validator pipeline, retry loop, severity levels -- is relatively straightforward engineering. The novelty is in the framing and the application domain, not in the computational architecture. Park et al.'s generative agents, Vezhnevets's Concordia, and Guo et al.'s large-scale simulation all face similar constraint problems; this paper's contribution is showing that systematic constraint enforcement has interpretable effects in a domain-specific context.

The FQL comparison is a genuine contribution that most LLM-agent papers lack: comparing against an established non-LLM method.

### Nature Water Fit: 7.5/10
The paper bridges two communities (LLM agents and water resources) and is better positioned in a water journal than a CS venue. Nature Water readers will find the Colorado River application compelling. The writing is at journal quality.

### Specific Issues

**MUST FIX:**
1. **Temperature confound.** Either run a temperature sensitivity analysis (even just T=0.5 and T=1.0 for one condition) or add a prominent limitation paragraph explaining that sampling temperature directly affects output diversity and could be a confound for the strategy diversity metric. Currently this is a one-sentence acknowledgment buried in Methods.
2. **Model-size-as-confound discussion.** The paper must explicitly address whether the governance effect is a genuine institutional mechanism or a compensatory scaffold for underpowered models. The data suggest the latter (effect strongest in smallest models, absent in largest), and reviewers will seize on this.

**SHOULD FIX:**
3. **Human behavioural comparison.** Add a paragraph acknowledging that no human decision data was compared, and frame the reasoning traces as demonstrating *plausible* heterogeneity rather than *validated* human-like reasoning. The paper currently implies the reasoning is meaningful because it "looks like" real reasoning.
4. **Prompt sensitivity caveat.** Add a limitations paragraph noting that the extensive prompt calibration history (v5-v7d) itself suggests high sensitivity to prompt design, and that results may not transfer to different prompt formulations.
5. **Cognitive frame coding methodology.** Either add inter-rater reliability for the taxonomy or explicitly label it as "illustrative" rather than "systematic."

**MINOR:**
6. The paper uses "EHE" in figure labels (Fig. 2, Fig. 3) but "strategy diversity" in the text. This inconsistency should be resolved -- use one term throughout.
7. The "Group B vs Group C" distinction (window memory vs. HumanCentric memory) is confusing. The paper claims they produce "identical strategy diversity" but the memory systems are quite different. This deserves either more explanation or simplification.
8. The paper cites "Huang et al., 2025" for LLM hallucination but this appears to be a hallucination survey paper. The connection between NLP hallucination and domain-specific constraint violation could be made more precise.

### Key Questions
- Q1: If you ran the irrigation experiment at temperature=0.2, would you still observe strategy diversity differences between governed and ungoverned conditions?
- Q2: Given that Gemma-3 27B shows a small (+0.174) and Ministral 14B shows a near-zero (+0.034) governance effect, what is the expected governance effect for GPT-4-class models? Would it vanish entirely?
- Q3: The cognitive frame taxonomy has 10 frames identified through "open coding." What was the coding procedure? How many coders? What was the agreement rate?

---

## Reviewer C -- Nature Water Editor / Format

### Overall Assessment
- **Verdict**: Minor Revisions
- **Confidence**: High
- **Summary**: A well-structured Analysis paper that fits Nature Water's scope and addresses a timely question at the intersection of AI and water governance, though some formatting issues and one potential scope concern need attention.

### Narrative Coherence: 8/10
The paper follows the Analysis format well: a focused question, clear experimental design, quantitative results, and measured interpretation. The "so what" moment is clear: governance creates conditions for adaptive water management that neither unconstrained AI nor parameterized models can achieve. The adaptive exploitation framing is effective and water-native.

The Introduction is strong -- the six-decade narrative arc from Harvard Water Program to LLM agents is well-constructed and gives the reader a clear sense of where this work fits historically. The Discussion appropriately does not overclaim.

One structural concern: the Results section at ~2,100 words is longer than typical for Nature Water Analysis papers. The four-subsection structure (R1-R4) is logical but could be tightened. R3 (strategy diversity beyond hand-coded models) partially overlaps with R1 and R4 in its claims; consider whether R3 can be compressed.

### Scientific Rigor: 7/10
From an editorial perspective, the paper meets the basic standards: replicated experiments, reported variance, honest limitations section. The SI is thorough and well-organized. The three baselines (ungoverned, PMT rule-based, FQL) provide adequate comparison.

However, two issues would likely concern external reviewers:
- The n=3 seeds design is thin by Nature standards. While the paper argues this is standard for ABM, Nature Water reviewers may expect more statistical power, particularly for the cross-model claims.
- The premium doubling reversal (SI Note 5) is a red flag. If a single parameter change reverses the main finding, the finding is fragile. This needs main-text discussion.

### Novelty & Contribution: 8/10
This is clearly novel for the water community. LLM agents in water simulation is a new direction, and the governance framing connects it to established institutional theory rather than presenting it as a pure engineering contribution. The ablation approach -- removing individual institutional rules -- is a methodological contribution that water modellers will find appealing.

### Nature Water Fit: 8/10
**Strengths:**
- The paper is fundamentally about water governance, not about AI methods. The computational framework serves the water question, not the other way around.
- Both application domains (Colorado River irrigation, flood adaptation) are highly relevant to Nature Water's readership.
- The Ostrom connection gives the paper theoretical grounding that elevates it above a technical demonstration.
- The writing quality is high -- precise, minimal jargon, well-paced.

**Concerns:**
- Nature Water's Analysis format allows approximately 4,000 words. The main text (abstract ~145 + intro ~830 + results ~2,100 + discussion ~950) totals approximately 4,025 words, which is at the limit. Methods are not counted, which is good. But any revisions that add text will push over. The authors should be prepared to trim.
- The paper references 6 language models but the primary irrigation analysis uses only one. Nature Water editors may ask why the full cross-model analysis was not done for both domains.
- The figures are functional but not at Nature Water's visual standard (see specific issues below).

### Specific Issues

**MUST FIX:**
1. **Figure quality.** Nature Water requires publication-quality figures at 300+ DPI with consistent typography. Figure 1 (adaptive exploitation) is decent but the panel labels (a,b,c,d) and axis text are too small. Figure 2 (cross-model) has two different versions in the figures folder (Fig2_crossmodel_diversity.png and Fig3_crossmodel.png) -- ensure consistency. Figure 3 (cumulative adaptation) has very small text and the hatching patterns may not reproduce well in print. All figures need a professional polish pass.
2. **Abstract word count.** The abstract is ~145 words against a 150-word limit. This is fine, but confirm against Nature Water's exact requirements -- some Analysis formats require an unstructured abstract of 100 words.

**SHOULD FIX:**
3. **Word count management.** At ~4,025 main-text words, the paper is at the Analysis limit. Identify 100-200 words that can be cut if reviewers request additions. R3 is the most compressible section.
4. **Figure-text agreement.** The figures use "EHE" (Effective Heterogeneity Entropy) as the y-axis label but the text uses "strategy diversity" throughout. This mismatch will confuse readers. Relabel figures to use "Strategy diversity" or define EHE in the figure caption.
5. **Table formatting.** Tables 1-3 contain a lot of information. Nature Water strongly prefers concise tables. Consider moving some metrics to SI (e.g., min Mead elevation, BRI from Table 1) to streamline.
6. **Reference count.** Count total references against Nature Water's Analysis limit (typically 30-50). The Introduction alone cites ~20 works.

**MINOR:**
7. The paper title "Institutional Constraints Widen Adaptive Strategy Diversity in Language-Based Water Agents" is accurate but long (11 words). Consider shortening: "Institutional Governance Widens Adaptive Diversity in Language-Based Water Agents" (10 words) or even "Governance Enables Adaptive Diversity in Language-Based Water Simulation" (8 words).
8. Ensure SI Note numbering is sequential and all cross-references are correct.
9. The cover letter should emphasize the water-governance insight, not the AI methodology.

### Key Questions
- Q1: Can you provide a concise (2-sentence) statement of what this paper teaches water managers that they did not know before? This should appear verbatim in the cover letter.
- Q2: Nature Water may ask for a "Reporting Summary" -- is the statistical reporting adequate for this?
- Q3: How will you handle data availability? The raw outputs are 100+ GB. Nature Water requires data accessibility.

---

## Final Consensus

### Overall Recommendation: **Minor Revisions** (Confidence: High)

The panel unanimously recommends Minor Revisions. The paper is above the threshold for Nature Water but has identifiable weaknesses that, if unaddressed, would give external reviewers grounds for rejection. No single issue is fatal, but the accumulation of the BRI interpretation gap, temperature confound, model-size confound, and premium doubling reversal creates a vulnerability surface.

### Top 3 Strengths

1. **Conceptual framing is genuinely original.** Recasting computational constraints as institutional boundaries (Ostrom) and demonstrating that they widen rather than narrow adaptive capacity is a contribution that bridges CS and water science. The "adaptive vs. arbitrary diversity" distinction is a conceptual tool the field can adopt.

2. **Ablation methodology is powerful and rare.** Removing a single institutional rule and measuring the system-level consequence (demand-Mead decoupling, doubled shortage frequency) is the kind of clean experimental design that most ABM papers cannot achieve. This is the paper's strongest empirical result.

3. **Cross-domain evidence with multiple baselines.** Testing governance across irrigation and flood, against ungoverned, rule-based PMT, and FQL baselines, with six model scales, provides unusually comprehensive evidence for an LLM-agent study. The honesty about non-significant results (3 of 6 models) and the premium doubling reversal (in SI) builds credibility.

### Top 3 Weaknesses

1. **Temperature and model-size confounds are unresolved.** The paper's central metric (strategy diversity) is directly affected by sampling temperature, and the governance effect is strongest in the weakest models. Without temperature sensitivity analysis or a clear argument for why this pattern reflects genuine institutional dynamics rather than model-capability compensation, reviewers will question the mechanism.

2. **BRI interpretation and single-model irrigation design.** The governed BRI of 58% (vs. 60% random) is not clearly a success, and the entire irrigation narrative depends on one 4B model. If that model has idiosyncratic properties, the adaptive exploitation story collapses. Cross-model irrigation runs (even for 2-3 models) would substantially strengthen the paper.

3. **Simplified reservoir model vs. institutional claims.** The paper draws institutional conclusions (prior-appropriation dynamics, shortage-sharing rules) from a model that applies uniform curtailment rather than seniority-based curtailment. The institutional analogy is weaker than the paper implies.

### Submission Readiness: **Needs 1 More Round**

The paper is close but not quite ready. The following should be addressed before submission:

1. **Critical (1-2 days):** Fix BRI framing, add temperature limitation paragraph, address model-size confound explicitly in Discussion, soften PA framing, harmonize EHE/strategy diversity terminology across figures and text.

2. **Important (3-5 days):** Consider running one additional irrigation model (e.g., Gemma-3 12B) to have at minimum a two-model irrigation result. Add premium doubling discussion to main text. Professional figure polish.

3. **If time permits:** Temperature sensitivity experiment (T=0.5, T=1.0) for one condition. Demand ceiling sensitivity analysis. Inter-rater reliability for cognitive frame taxonomy.

After addressing items 1 and 2, the paper would be competitive at Nature Water. Item 3 would make it strong.

---

*Review conducted 2026-02-24. Panel: Water Resources (A), Computational Social Science (B), NW Editorial (C).*
