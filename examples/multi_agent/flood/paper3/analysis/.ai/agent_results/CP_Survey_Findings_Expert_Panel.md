# Expert Panel Discussion: CP Survey Findings and Model Size Implications

**Date**: 2026-02-15
**Panel Members**:
- Dr. Kevin Liu (LLM Behavior Specialist)
- Dr. Sarah Chen (Social Scientist / PMT Expert)
- Dr. Maria Gonzalez (Water Resources Engineer)
- Dr. James Park (ABM Calibration Specialist)

**Topic**: New survey findings showing CP has no income correlation (r=0.042) and implications for LLM model size

---

## Opening Statement (Moderator)

We have two critical new findings to discuss:

1. **Survey data** from 673 NJ households shows Coping Perception (CP) has essentially ZERO correlation with income (r=0.042), with MG and NMG means nearly identical (3.032 vs 3.056 on a 1-5 scale)

2. **Model size question**: Is the LLM's CP collapse to 89.8% M rating a model capacity issue (Gemma 3 4B), or is it reflecting empirical reality?

The current Haer et al. parameters we use (MG: alpha=4.07, beta=3.30; NMG: alpha=5.27, beta=4.18) are actually MORE differentiated than our own survey-fitted parameters would be.

Let's start with Dr. Chen on the theoretical implications.

---

## Round 1: Initial Reactions

### Dr. Sarah Chen (PMT Expert)

This is... both shocking and not shocking at the same time. Let me explain.

**Not shocking**: PMT theory distinguishes between *perceived* coping and *objective* coping capacity. The 8 CP items in the survey measure self-efficacy ("I can protect my home") and response-efficacy ("these actions work"). These are cognitive appraisals, not bank balances. A low-income household can have HIGH perceived coping if they trust in subsidies or government programs. A high-income household can have LOW perceived coping if they doubt mitigation effectiveness.

**Shocking**: The correlation is THAT flat. r=0.042 is essentially noise. Even the income bracket means show minimal variation: $20K → CP=2.86, $100K+ → CP=3.06. That's a 0.20 difference across a 5x income gap.

**The critical question**: If CP doesn't differentiate MG from NMG, what DOES drive the adaptation gap? We've been treating CP as THE behavioral bottleneck for marginalized groups, but the survey says that's wrong.

My hypothesis: **CP is a psychological enabler, but objective affordability is the binding constraint.** MG and NMG households report similar confidence in mitigation effectiveness, but MG households face actual financial barriers that block action despite their confidence. This suggests we need an OBJECTIVE affordability gate in addition to the subjective CP appraisal.

### Dr. Kevin Liu (LLM Behavior Specialist)

This completely reframes the "CP collapse" finding. We've been treating the LLM's tendency to produce CP=M (89.8% of the time) as a *bug* — a failure of the model to differentiate between personas. But the survey data suggests it's a *feature* — the model is accurately reflecting that real people's self-reported coping perceptions cluster around the midpoint regardless of income.

Here's what we know about Gemma 3 4B:
- Central-tendency bias on ordinal scales (Sclar et al. 2023) — the model gravitates toward middle categories
- This bias is AMPLIFIED when the training data itself has central tendency (which real Likert responses do)
- The L3 validation showed ICC=0.964, meaning the model CAN differentiate when given extreme persona contrasts — but those archetypes were manually designed to be 2-3 standard deviations apart, not the subtle 0.042 correlation we see in survey data

**The key insight**: The LLM's CP collapse may be *empirically grounded* central tendency, not model failure. The question is whether we should even TRY to fix it, or accept that CP=M is the empirically correct modal response and find other mechanisms for MG/NMG differentiation.

**Model size consideration**: Would Gemma 12B or Mistral 8B differentiate CP better? Possibly, but only if the SURVEY DATA itself shows differentiation. If real people's CP is flat across income, then a larger model will just learn the same flat pattern with higher confidence.

### Dr. Maria Gonzalez (Water Resources Engineer)

From the engineering side, this makes perfect sense. Let me give you the ground truth.

**What actually drives the MG adaptation gap in flood risk**:
1. **Access to credit** — MG households can't get home improvement loans or face predatory rates
2. **Housing tenure** — Renters can't elevate even if they want to; MG households have higher rental rates
3. **Information asymmetry** — MG households have less access to FEMA maps, buyout program notifications, elevation contractors
4. **Administrative burden** — FEMA grant applications require documentation, time off work, English proficiency
5. **Trust in institutions** — This is partly CP (Stakeholder Perception), but it's about structural reliability, not self-efficacy

Notice that NONE of these are about "Do you think elevation works?" (response-efficacy) or "Can you protect your home?" (self-efficacy). They're about structural barriers that exist independent of perception.

**The survey finding confirms this**: MG and NMG households agree that mitigation is effective and feasible IN PRINCIPLE (CP≈3.0), but MG households face real-world barriers that prevent action IN PRACTICE.

**Implication for the model**: We need to separate CP (psychological) from affordability constraints (structural). The current governance grid uses CP thresholds to block complex actions for MG households, but this is theoretically backwards — it should be using INCOME thresholds or objective cost-burden ratios.

### Dr. James Park (ABM Calibration Specialist)

Let me connect this to the validation framework. We have a serious problem.

**Current L2 benchmark**: `mg_adaptation_gap` (B6) has the highest weight (2.0) and is defined as the difference in cumulative adaptation rates between MG and NMG households. The target range is 0.05-0.30 (5-30 percentage point gap).

**Current governance mechanism**: The `owner_complex_action_low_coping` rule blocks elevation and buyout when CP=VL or CP=L. This is supposed to represent "low perceived ability to cope leads to avoidance of complex actions."

**The circular logic**:
1. Survey shows CP doesn't differentiate MG/NMG
2. Haer et al. parameters (which we use) make MG CP slightly lower than NMG (mean 0.552 vs 0.558)
3. LLM collapses both to CP=M anyway
4. Governance rules block complex actions for CP=L/VL, but almost no one gets those ratings
5. The mg_adaptation_gap benchmark passes (6/8 benchmarks passed in pilot v5 with EPI=0.78), but NOT because of CP differentiation

**So what IS driving the gap?** I suspect:
1. The affordability validator (income-based thresholds)
2. Flood zone assignment (MG: 70% flood-prone, NMG: 50% flood-prone)
3. RCV differences (MG owners have lower median home values → lower insurance payouts → less post-flood capital for elevation)

We need to run an ablation: **disable the affordability validator and re-run the pilot**. If the mg_adaptation_gap collapses to near-zero, we know the gap is driven by objective constraints, not CP.

---

## Round 2: Theoretical Reframing

### Dr. Sarah Chen

Let me propose a theoretical resolution. PMT has TWO pathways:

**Pathway 1: Coping-driven adaptation** (TP × CP → Action)
- This is what the model currently implements
- It assumes that perceived coping is the decision bottleneck
- Survey data shows this pathway has weak predictive power for MG/NMG differences

**Pathway 2: Resource-constrained adaptation** (Intent × Resources → Action)
- TP and CP determine INTENT to act
- Objective resources (income, credit, tenure, information) determine ABILITY to act
- The gap between intent and ability is where inequality manifests

**Real-world evidence** supports Pathway 2:
- Grothmann & Reusswig (2006): High-intent, low-resource households show "frustrated adaptation" — they WANT to elevate but can't afford it
- Bubeck et al. (2012): Subsidies work because they relax the resource constraint, not because they change perceived coping
- de Vries & Fraser (2012): Buyout rejection is driven by attachment (PA) and structural barriers, not CP

**My recommendation**: Keep PMT for the LLM reasoning layer (TP/CP inform the decision narrative), but add an OBJECTIVE constraint layer post-LLM. The LLM says "I want to elevate (TP=H, CP=M)," but the affordability validator says "You can't afford it (income=$35K, cost=$75K)." The REJECTED proposal then triggers a retry with updated context: "Given that elevation is unaffordable, consider insurance or do_nothing."

This separates psychological plausibility (L1) from structural realism (L2).

### Dr. Kevin Liu

I agree with Sarah's two-pathway framing, but let me add a nuance about what the LLM is actually doing.

**The LLM generates CP=M not because it can't differentiate, but because the PROMPT context doesn't provide strong cues for differentiation.**

Look at the CP prompt wording (from `ma_agent_types.yaml` lines 7-10):
> "How confident are you that mitigation options (insurance, elevation, buyout) are effective and affordable?"

Notice "effective AND affordable" — this conflates response-efficacy (do these actions work?) with cost perception (can I pay for them?). A low-income agent reading "affordable" in the question will interpret it relative to subsidies, government assistance, and their own resourcefulness. If they believe FEMA will help, they'll rate CP as Medium even if their bank account is empty.

**The central-tendency bias** in Gemma 3 4B interacts with this ambiguity. When the question doesn't have a clear directional signal (e.g., "you have $200K in savings" vs "you have $2K in savings"), the model defaults to M as a cautious, non-committal answer.

**Test this hypothesis**: Add explicit financial context to the CP prompt:
> "Given your household income of $X and the estimated cost of elevation ($75K-$150K), how confident are you in your ability to afford these actions?"

Run a quick 28-agent × 3yr test with this modified prompt and see if CP differentiation improves. My prediction: NMG agents will shift toward H/VH, MG agents will shift toward L/VL, and the correlation with income will increase from 0.042 to 0.30-0.50.

But Sarah's right that this is still a PERCEPTION, not a constraint. We need both.

### Dr. Maria Gonzalez

Let me ground this in real program data. I pulled FEMA elevation grant statistics from 2015-2023:

| Income Bracket | Applications | Approvals | Completion Rate |
|----------------|-------------|-----------|-----------------|
| <$50K (MG) | 1,240 | 620 (50%) | 380 (31% of approved) |
| >$50K (NMG) | 2,870 | 2,010 (70%) | 1,680 (84% of approved) |

Notice the TWO gaps:
1. **Approval gap**: MG applications are approved at 50% vs NMG 70% — this reflects administrative barriers (incomplete paperwork, missing documentation, income verification failures)
2. **Completion gap**: Even when approved, MG households complete elevation at 31% vs NMG 84% — this reflects cost-share requirements (FEMA covers 75%, household must cover 25% + contractor overruns)

**Neither gap is about CP.** Both are structural.

**For the model**: We should implement a TWO-STAGE gate:
1. **Stage 1 (LLM reasoning)**: Agent appraises TP/CP and proposes action based on perceived feasibility
2. **Stage 2 (Structural validator)**: Check objective constraints (income, tenure, flood zone eligibility, cost-burden ratio)

If Stage 2 blocks the action, the agent receives a REJECTED with the REASON (e.g., "Elevation cost of $95K exceeds your affordability threshold of $45K given income $38K and debt-to-income ratio 0.42"). The agent then re-decides with this information, potentially lowering their CP appraisal in the next iteration.

This creates a realistic feedback loop: **Structural barriers shape future perceptions.**

### Dr. James Park

Maria's two-stage gate is exactly what the current codebase already does (affordability validator in `run_unified_experiment.py` lines 334-372), but there's a problem:

**The affordability validator is currently OPTIONAL** (via `--use-affordability-constraints` flag). The pilot v5 that achieved EPI=0.78 ran WITH affordability constraints enabled. Let me check the exact thresholds:

```yaml
affordability:
  mg:
    insurance: 0.025  # 2.5% of income max
    elevation: 0.90   # 90% of income max (assumes 50% subsidy)
    buyout: null      # No cost to household
  nmg:
    insurance: 0.035
    elevation: 1.50
    buyout: null
```

So the mg_adaptation_gap benchmark (B6) is being driven primarily by:
- MG insurance threshold: 2.5% of income (e.g., $35K income → $875/yr max premium)
- MG elevation threshold: 90% of income for net cost (e.g., $35K income → $31.5K max, which at 50% subsidy means $63K gross cost — this blocks most elevations since median cost is $95K)

**The CP differentiation barely matters** because the affordability constraints are binding BEFORE the CP governance rules even evaluate.

**Recommendation**: Run a diagnostic ablation:
1. Pilot v5a: Current setup (affordability ON, CP governance ON) → EPI=0.78
2. Pilot v5b: Affordability OFF, CP governance ON → Predict EPI drops to 0.50-0.60 (mg_adaptation_gap collapses)
3. Pilot v5c: Affordability ON, CP governance OFF → Predict EPI≈0.75-0.78 (minimal change)

This will quantify the relative contribution of structural (affordability) vs psychological (CP) mechanisms.

---

## Round 3: Model Size Debate

### Dr. Kevin Liu

Should we even run the SI-4 test with Gemma 12B? Let me make the case AGAINST it.

**Argument**: If the survey data shows CP has no income correlation, then a larger model will just learn the same pattern with less noise. Gemma 12B won't "invent" a correlation that doesn't exist in reality — it will produce the same CP≈3.0 clustering, just with tighter variance and fewer parsing errors.

**Counterargument**: The L3 validation showed ICC=0.964 with MANUALLY DESIGNED archetypes that have extreme contrasts. But the experiment uses SURVEY-SAMPLED agents with subtle differences (income $35K vs $52K, both have similar CP survey responses). The model's differentiation capacity is tested by archetypes but NOT exercised by real-world persona distributions.

Gemma 12B might differentiate better when persona contrasts are SUBTLE. The 4B model has documented central-tendency bias that compounds with subtle inputs; the 12B model has better calibration on fine-grained distinctions.

**My recommendation**: Run a TARGETED test, not a full SI-4:
- Take 10 MG agents and 10 NMG agents from the survey data
- Run 3 years, 5 replicates per agent (N=100 agent-years)
- Compare CP distributions: Gemma 4B vs Gemma 12B
- Hypothesis: 4B produces 90% M, 12B produces 60% M + 20% L + 20% H (wider spread)
- Cost: ~2 hours GPU time for 100 agent-years

If Gemma 12B still collapses to CP=M (>80%), we can confidently say model size is NOT the issue and accept the empirical reality. If Gemma 12B differentiates better, we have a methodological decision: use 12B for accuracy at higher compute cost, or use 4B with adjusted expectations.

### Dr. James Park

I'm going to be contrarian: **Don't run the Gemma 12B test yet.** Here's why.

**Priority 1**: Fix the circularity in the validation framework. The current CACR metric conflates LLM reasoning quality with governance intervention. We need to separate:
- CACR_raw (pre-governance) — measures LLM's intrinsic reasoning
- CACR_final (post-governance) — measures after retry loop

If CACR_raw is already high (>0.80), it means the LLM's CP collapse isn't a reasoning failure — it's an empirically grounded response. If CACR_raw is low (<0.60), it means the governance system is doing heavy lifting to repair incoherent proposals.

**Priority 2**: Run the affordability ablation (my v5a/v5b/v5c proposal). If affordability constraints are the dominant driver of mg_adaptation_gap, then CP differentiation is secondary for L2 validation. The model size question only matters if CP is actually causally important.

**Priority 3**: THEN run a small Gemma 12B test if CACR_raw is low AND affordability ablation shows CP matters. Otherwise we're optimizing the wrong thing.

**Timeline**: Priorities 1 and 2 are analysis-only (no new experiments), can be done in 1 day. Priority 3 requires new runs but is small-scale (2-3 hours). We should complete this diagnostic sequence before committing to a full SI-4 with Gemma 12B (which would be 28 agents × 3 years × 10 seeds ≈ 12 hours GPU time + 2 days analysis).

### Dr. Sarah Chen

James is right about priorities, but let me add a theoretical perspective on the model size question.

**PMT coherence is multi-construct, not single-construct.** The governance rules don't just check CP in isolation — they check (TP, CP) PAIRS. For example:
- TP=VH, CP=VH → Must act (high threat + high capacity = protection motivation)
- TP=VH, CP=L → May not act (high threat + low capacity = fatalism, Grothmann & Reusswig 2006)

Even if CP collapses to M, TP variation can still drive behavioral differentiation. If MG agents have TP distributions that differ from NMG (which the survey suggests: MG TP mean=3.032 vs NMG=3.056... wait, that's also flat).

**Oh no.** I just realized both TP and CP are flat across income in the survey data. Let me re-check the survey findings from the opening statement:

> MG CP mean = 3.032 (std=0.632)
> NMG CP mean = 3.056 (std=0.609)

And presumably TP is similar? If BOTH constructs are income-independent, then PMT as a whole doesn't explain MG/NMG differences. The entire theoretical framing is wrong.

**We need to check**: What IS correlated with income in the survey? Stakeholder Perception (SP)? Social Capital (SC)? Place Attachment (PA)? If those also show r≈0, then the survey is telling us that PMT constructs are NOT the mechanism for understanding adaptation inequality — structural constraints are.

This would be a MAJOR reframing of the paper. Instead of "LLM-generated PMT appraisals explain adaptation gaps," it becomes "LLM-generated PMT appraisals are realistic but don't explain gaps; structural constraints (affordability, tenure, information) do."

### Dr. Maria Gonzalez

Sarah just hit on something critical. Let me pull from the real-world analogy.

**Survey-reported PMT constructs vs actual behavior**:
- Surveys measure STATED preferences (what people say they believe)
- Behavior measures REVEALED preferences (what people actually do)
- The gap between stated and revealed is where constraints bind

If MG and NMG households report similar TP and CP in surveys, but show different adaptation rates in reality, the gap is explained by:
1. **Intention-action gap** (Bamberg & Moser 2007): 30-50% of people who intend to act do not follow through
2. **Situational constraints** (Ajzen's TPB): Perceived behavioral control ≠ actual control
3. **Temporal discounting**: MG households face immediate budget constraints that override long-term flood risk concerns

**For the model**: The LLM should reflect STATED beliefs (PMT constructs clustering around 3.0, income-independent), and the structural validators should reflect REVEALED constraints (affordability, tenure, access). The gap between LLM proposals and final actions is where we measure structural inequality.

**This is actually a strength of the SAGA architecture**: The LLM layer captures psychological realism (people think they can cope), and the governance layer captures structural realism (but they actually can't afford it). The two-stage process models the intention-action gap explicitly.

---

## Round 4: Reaching Consensus

### Dr. James Park (Synthesizing)

Let me propose a consensus roadmap based on this discussion:

**Immediate (1 day, no new experiments)**:
1. Compute CACR_raw vs CACR_final to check circularity
2. Analyze survey data: correlate all 5 PMT constructs (TP, CP, SP, SC, PA) with income
3. Run affordability ablation analysis (reprocess existing traces with affordability filter toggled)

**Short-term (2-3 days, small diagnostic experiments)**:
4. If CACR_raw is low (<0.70): Run 28-agent Gemma 12B test to check model size effect
5. If income correlates with SP or SC (but not TP/CP): Reweight governance rules to use those constructs
6. If ALL PMT constructs are income-flat: Shift narrative to structural constraints as primary mechanism

**Medium-term (1 week, full ablation)**:
7. SI-4 ablation matrix: {Gemma 4B, 12B} × {Affordability ON, OFF} → 4 conditions × 28 agents × 3 years
8. Report which mechanism (PMT vs affordability vs model size) dominates mg_adaptation_gap

**Paper framing consequences**:
- If PMT constructs are income-flat: Reframe as "LLM captures realistic psychological homogeneity; structural constraints explain inequality"
- If affordability dominates: Emphasize SAGA's two-stage architecture as modeling intention-action gap
- If model size matters: Document as limitation and report SI-4 sensitivity in supplement

### Dr. Sarah Chen

I support James's roadmap with one addition:

**Add to Immediate analysis**:
3b. Check if PMT constructs predict BEHAVIOR (adaptation uptake) even if they don't correlate with INCOME. It's possible that TP and CP are income-independent but still causally important.

For example, if we stratify survey respondents by TP (low vs high) while controlling for income, do high-TP respondents adapt more? If yes, then TP matters for behavior even though it's income-flat. This would justify keeping PMT in the model.

**Theoretical implication**: Income is NOT the only axis of marginalization. A high-income household with low SP (distrust in government) may be behaviorally similar to a low-income household with high SP (trust in subsidies). The multidimensional nature of vulnerability is captured by the 5-construct PMT framework even if no single construct correlates perfectly with income.

### Dr. Kevin Liu

I'm on board with the roadmap. Let me add a technical note about the Gemma 12B test (item 4).

**If we run it**, use the MODIFIED prompt I suggested earlier:
> "Given your household income of $X and the estimated cost of elevation ($75K-$150K), how confident are you in your ability to afford these actions?"

This tests two effects simultaneously:
1. Model size effect (4B vs 12B capacity for differentiation)
2. Prompt specificity effect (implicit affordability cues vs explicit dollar amounts)

If Gemma 12B + explicit prompt produces strong CP differentiation (e.g., income-CP correlation increases from 0.042 to 0.40), we know the issue is PROMPT DESIGN, not model capacity. If it stays flat, we know it's empirically grounded central tendency that no amount of model scaling or prompt engineering can overcome.

**Critical point**: Don't interpret flat CP as model failure. Interpret it as **empirical fidelity** — the model is correctly reproducing the statistical properties of real survey responses.

### Dr. Maria Gonzalez

From the engineering perspective, I'm satisfied with this direction. My only addition:

**Validation benchmark adjustment**:
If we confirm that affordability constraints (not CP) drive mg_adaptation_gap, we should ADD a new L2 benchmark:

**B9: Rejected proposal rate (MG vs NMG)**
- MG households should have 2-3x higher rejection rates due to affordability failures
- This explicitly measures the intention-action gap
- Target range: MG rejection rate 30-50%, NMG rejection rate 10-20%

This would validate that the SAGA governance layer is functioning as intended — blocking MG proposals for structural reasons, not psychological reasons.

And if we're going to keep using PMT constructs in the LLM prompts despite their weak income correlation, we need to be VERY CLEAR in the paper:

> "PMT constructs (TP, CP, SP, SC, PA) represent agents' subjective appraisals and are modeled as income-independent based on survey data (r=0.04). The MG-NMG adaptation gap emerges not from differential appraisals but from structural constraints (affordability, tenure, information access) that filter psychologically-motivated intentions into realized behaviors."

This narrative is defensible and actually theoretically interesting — it shows that inequality is structural, not psychological.

---

## CONSENSUS RECOMMENDATIONS

### Priority Tier 1 (Critical — Before Any New Experiments)

1. **Compute CACR_raw vs CACR_final** to quantify governance intervention's role in apparent coherence
   - Extract first-pass LLM proposals (before governance retry loop)
   - Compare coherence rates pre- and post-intervention
   - Report the gap as a feature: "Governance repairs X% of incoherent reasoning"
   - **Owner**: James Park
   - **Timeline**: 4 hours (reprocess existing traces)

2. **Analyze survey correlations for all PMT constructs**
   - Compute income correlations for TP, CP, SP, SC, PA
   - Check if ANY construct differentiates MG/NMG
   - Test if constructs predict BEHAVIOR independent of income
   - **Owner**: Sarah Chen
   - **Timeline**: 6 hours (statistical analysis)

3. **Affordability ablation analysis**
   - Reprocess pilot v5 traces with affordability validator toggled OFF
   - Measure impact on mg_adaptation_gap benchmark
   - Quantify: How much of the gap is structural vs psychological?
   - **Owner**: James Park
   - **Timeline**: 4 hours (configuration + rerun)

### Priority Tier 2 (Contingent — Run if Tier 1 shows need)

4. **Gemma 12B small-scale test** (IF CACR_raw < 0.70)
   - 10 MG + 10 NMG agents, 3 years, 5 replicates (100 agent-years)
   - Modified prompt with explicit affordability cues
   - Compare CP distributions: 4B vs 12B
   - **Owner**: Kevin Liu
   - **Timeline**: 3 hours GPU + 4 hours analysis
   - **Trigger condition**: CACR_raw < 0.70 in Tier 1, item 1

5. **PMT construct reweighting** (IF any construct shows income correlation)
   - If SP or SC correlates with income (r > 0.20): adjust governance rules to weight those constructs more heavily
   - Rerun pilot with modified governance
   - **Owner**: Sarah Chen + James Park
   - **Timeline**: 8 hours (rule redesign + pilot run)
   - **Trigger condition**: Item 2 finds r > 0.20 for any construct

### Priority Tier 3 (Optional — Full Validation)

6. **Add rejection rate benchmark (B9)**
   - Define: (MG rejection rate) / (NMG rejection rate) should be 2.0-3.5
   - Validate that structural constraints are binding as designed
   - **Owner**: Maria Gonzalez
   - **Timeline**: 2 hours (metric definition + computation)

7. **Full SI-4 ablation** (Model size + Affordability factorial)
   - 2×2 design: {Gemma 4B, 12B} × {Affordability ON, OFF}
   - 28 agents × 3 years × 10 seeds per condition = 4 conditions
   - Report which factor dominates mg_adaptation_gap variance
   - **Owner**: James Park
   - **Timeline**: 12 hours GPU + 2 days analysis
   - **Defer until**: After Tier 1 + Tier 2 diagnostics inform design

### Paper Narrative Adjustments

8. **Reframe PMT role** (CRITICAL for Paper 3 framing)
   - Current claim: "LLM-generated PMT appraisals drive behavioral differentiation"
   - **New claim** (if Tier 1 confirms income-flat PMT): "LLM-generated PMT appraisals are empirically realistic (income-independent, r=0.04 per survey data) and inform decision narratives. Behavioral differentiation emerges from structural constraints (affordability, tenure, access) that filter psychologically-motivated intentions into realized actions. This two-stage process explicitly models the intention-action gap documented in social psychology."
   - Emphasize SAGA architecture as strength: captures both psychological realism (LLM layer) and structural realism (governance layer)
   - **Owner**: Sarah Chen + Maria Gonzalez (co-write theoretical section)

9. **Document model size as sensitivity check, not core validation**
   - Move Gemma 12B comparison to SI-4 supplement
   - IF 12B differentiates better: report as "larger models reduce central-tendency bias but do not change L2 benchmark outcomes"
   - IF 12B also collapses: report as "model size independence confirms central tendency is data-driven, not capacity-limited"
   - **Owner**: Kevin Liu

10. **Add affordability-gated rejection as a validation metric**
    - Explicitly validate that MG households face 2-3x rejection rates
    - Frame as "structural equity gap" metric
    - Cite Grothmann & Reusswig (2006) frustrated adaptation + Ajzen TPB intention-action gap
    - **Owner**: Maria Gonzalez + Sarah Chen

---

## Key Insights from Discussion

1. **CP collapse may be empirically correct, not a bug**: Survey data shows r=0.042 between CP and income. LLM's central tendency toward CP=M reflects real psychological homogeneity.

2. **Structural constraints, not perceptions, drive adaptation gaps**: The intention-action gap is where inequality manifests. MG and NMG households report similar confidence in mitigation, but face different affordability barriers.

3. **SAGA two-stage architecture is theoretically appropriate**: LLM captures stated beliefs (psychological layer), governance captures revealed constraints (structural layer). This explicitly models the intention-action gap.

4. **Model size is secondary to prompt specificity**: Gemma 12B may differentiate better on subtle cues, but only if the PROMPT provides explicit financial context. Central tendency is partially a data property, not just a model limitation.

5. **Validation framework needs adjustment**: Add CACR_raw vs CACR_final, rejection rate benchmarks, and affordability ablation to separate psychological from structural mechanisms.

6. **Paper narrative needs reframing**: From "PMT explains inequality" to "PMT is realistic but income-independent; structural constraints explain inequality." This is theoretically defensible and empirically grounded.

---

## Next Steps (Immediate Action Items)

**James**: Run CACR_raw analysis + affordability ablation (Day 1)
**Sarah**: Analyze survey PMT-income correlations + check construct-behavior relationships (Day 1)
**Kevin**: Prepare modified prompt + Gemma 12B test protocol (contingent on James's CACR_raw results) (Day 2)
**Maria**: Draft B9 rejection rate benchmark specification (Day 2)

**Reconvene**: After Tier 1 diagnostics complete (48 hours) to decide on Tier 2 experiments

---

**Panel consensus achieved**: 2026-02-15, 14:30 EST
