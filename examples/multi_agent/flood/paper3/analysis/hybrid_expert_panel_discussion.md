# Expert Panel Discussion: Monotonic Escalation Bias in Hybrid LLM Institutional Agents

**Date**: 2026-03-13
**Subject**: Diagnosis and remediation of persistent upward-only policy selection by gemma3:4b in the hybrid government/insurance agent design
**Simulation**: 400-household Passaic River Basin (PRB) multi-agent flood ABM, 13-year run (2011--2023)

---

## Panel Members

| Expert | Affiliation | Specialization |
|--------|-------------|----------------|
| **Dr. Sarah Chen** | Stanford HAI | LLM alignment & instruction following in small models |
| **Dr. Marcus Webb** | Santa Fe Institute | Computational social science, LLM-ABM decision biases |
| **Dr. Yuki Tanaka** | Google DeepMind | Prompt engineering for constrained decision-making |
| **Dr. Roberto Silva** | MIT Media Lab | Behavioral economics & cognitive biases in AI agents |

**Moderator**: The simulation architect (paper authors).

---

## Observed Behavior Summary

| Metric | Government (NJDEP) | Insurance (CRS) |
|--------|-------------------|-----------------|
| Decisions made | 13 | 13 |
| Chose maximum increase | 11/13 (85%) | 13/13 (100%) |
| Chose small increase | 2/13 (15%) | 0/13 (0%) |
| Chose maintain/decrease voluntarily | 0/13 | 0/13 |
| Blocked by hard validators | 6 (G3: 3, G4: 3) | 6 (I7: 6) |
| Final value | Subsidy = 82.5% | CRS discount = 45% (cap) |
| Resource status | Budget = 17% (near depletion) | At absolute ceiling |

Both agents exhibited **monotonic escalation**: they selected the most aggressive upward action on every single decision, with hard validators as the sole brake.

---

## Round 1: Root Cause Diagnosis

### Dr. Sarah Chen (LLM Alignment)

The core problem is **action-option positional bias** compounded by **insufficient instruction hierarchy** in a 3.3B parameter model.

First, positional bias. In the government prompt, `large_increase_subsidy` is listed first under "YOUR OPTIONS." Research on small LLMs -- including Gemma-family models -- shows a well-documented primacy bias: when multiple-choice options are presented, models disproportionately select the first listed option, especially under ambiguity. With 3.3B parameters, the model lacks the capacity to perform genuine multi-criteria weighing across the five policy dimensions presented. It latches onto the first plausible option and constructs post-hoc reasoning to justify it.

Second, instruction hierarchy. The prompt presents "Reasons to INCREASE," "Reasons to DECREASE," and "Reasons to MAINTAIN" as parallel sections with identical formatting weight. A small LLM cannot reliably infer that these sections represent competing considerations to be balanced. Instead, it processes them sequentially. By the time it reaches the "Reasons to DECREASE" section, it has already formed a strong prior toward increase from the first section -- especially because the increase section contains the most emotionally charged language ("crisis demands stronger support," "vulnerable communities," "falling behind").

Third, there is a known **sycophantic completion pattern** in instruction-tuned small models. The prompt's situation assessment labels -- "Immediate crisis," "Very early stage" -- read as implicit instructions. When the model sees "Flood Urgency: Immediate crisis," it interprets this as a directive to act urgently, not as one input among many to weigh.

### Dr. Marcus Webb (LLM-ABM)

I want to highlight a structural issue that goes beyond prompt design: **the PRB scenario creates a degenerate decision environment for qualitative reasoning**.

In 13 years of PRB data, floods occur every single year, with 16-39% of households affected. The alternating SEVERE/MODERATE pattern means the model never encounters a "calm period" signal. Every year, the flood urgency label reads "Immediate crisis" or at minimum "Ongoing concern." This means the "Reasons to DECREASE" section is never activated by the data itself -- the conditions that would justify decrease (calm period, well-adapted community, constrained budget) are either absent or, critically, presented alongside stronger countervailing signals.

This is a well-known failure mode in ABM design: **environmental invariance defeats adaptive logic**. If the environmental signal never changes valence, a boundedly rational agent has no reason to change strategy. The issue is that the hybrid design assumed the qualitative labels would provide sufficient granularity for the LLM to distinguish between "we had a severe flood and adaptation is at 5%" versus "we had a moderate flood and adaptation is at 60%." But gemma3:4b cannot perform this nuanced distinction -- it sees "flood happened" and "adaptation incomplete" and maps both to "increase."

I also want to flag **trajectory dependence**. Once the model chooses `large_increase_subsidy` in Year 1, the "Last Decision" field in subsequent years reads `large_increase_subsidy`, and "Policy Momentum" reads something like "Aggressive." For a small model prone to self-reinforcing patterns, this creates an echo chamber: the model's own history becomes evidence that increasing is the "right" policy.

### Dr. Yuki Tanaka (Prompt Engineering)

I see three specific prompt design failures, all of which are well-characterized in the prompt engineering literature:

**Failure 1: Symmetric framing with asymmetric emotional valence.** The "Reasons to INCREASE" section uses charged language: "crisis demands," "vulnerable communities," "falling behind." The "Reasons to DECREASE" section uses neutral bureaucratic language: "calm period reduces urgency," "fiscal discipline." For an instruction-tuned model, emotionally charged language functions as a stronger instruction signal. The increase section effectively outranks the decrease section in the model's implicit instruction hierarchy.

**Failure 2: The label-to-action mapping is too transparent.** Labels like "Immediate crisis" have an obvious implied action (act urgently = increase). Labels like "At practical ceiling" are ambiguous -- does "ceiling" mean "stop" or "you have achieved a lot, keep going"? The model consistently resolves ambiguous labels in the direction of increase because the prompt's overall framing positions the agent as a helper/protector. This triggers the model's alignment training: a helpful agent should always do more, not less.

**Failure 3: Option descriptions encode value judgments.** The description of `large_increase_subsidy` reads "A major expansion -- appropriate when facing a crisis with early-stage adaptation and available budget." In PRB, there is always a crisis and adaptation is always incomplete. This description functions as a perpetual green light. Compare `maintain_subsidy`: "appropriate when conditions are stable." Conditions are never stable in PRB. The model reads these descriptions as conditional rules and correctly identifies that the increase condition is always met.

### Dr. Roberto Silva (Behavioral Economics)

I want to frame this through the lens of **action bias** and **omission bias** -- concepts from behavioral economics that map directly onto LLM behavior.

Action bias is the tendency to prefer doing something over doing nothing, especially under perceived threat. In the behavioral economics literature (Bar-Eli et al., 2007, on soccer goalkeepers), decision-makers facing uncertainty and threat disproportionately choose action over inaction, even when inaction would produce better outcomes. The LLM exhibits a computational analogue: when the prompt describes a threatening situation (floods, vulnerable populations), the model's instruction-following training maps "helpful response" to "take action," and the most helpful action is the largest increase.

There is also a **loss aversion asymmetry** in how the prompt frames consequences. Increasing subsidy is framed as helping people; decreasing is framed as withdrawing support. Even without explicit loss/gain framing, the model has learned from its training corpus that withdrawing aid is negatively valenced. The model avoids the "decrease" options not because it has weighed the policy considerations, but because selecting decrease feels like a harmful action -- it conflicts with the model's RLHF-trained preference to be helpful.

Finally, I note an **anchoring effect** from the initial subsidy rate of 50%. The prompt shows "Current Subsidy Rate: 50%." In Year 1, with a crisis happening, the model anchors on "50% is not enough" and increases. But critically, the anchor never resets. Even when subsidy reaches 80%, the model still sees "crisis" and "incomplete adaptation" as dominant signals. The qualitative label "Very high subsidy" does not function as a counter-anchor because the model has no training-data basis for interpreting what constitutes "too high" for a flood subsidy.

---

## Round 2: The PRB Problem

**Moderator**: PRB floods every year. The "reasons to decrease" conditions (calm period, well-adapted community) are structurally absent from this scenario. Is this a prompt design issue, a scenario design issue, or a fundamental limitation of qualitative-label guidance for small LLMs?

### Dr. Chen

It is all three, but the weight distribution matters. Even a large model (70B+) would struggle with this prompt under PRB conditions, because the prompt's decrease logic is contingent on environmental states that never occur. That said, a 70B model might occasionally reason: "We have been increasing for 8 consecutive years and the budget is nearly depleted; fiscal sustainability requires a pause." Gemma3:4b cannot sustain that multi-step counterfactual reasoning.

The fundamental limitation is this: qualitative labels work as decision aids when the decision space has clear thresholds. "Budget: Critically low" should trigger decrease. But the prompt presents budget health alongside flood urgency, and the model cannot arbitrate between competing signals of different categories. It defaults to the most salient signal (flood urgency) every time.

### Dr. Webb

I want to push back on the idea that this is primarily a prompt problem. The real issue is that **the hybrid design assumes the LLM can perform multi-attribute utility maximization**, which is a task that requires comparing incommensurable values (lives vs. dollars, short-term relief vs. long-term sustainability). This is hard for humans and essentially impossible for a 3.3B model operating on a single forward pass.

In a traditional ABM, you would encode these trade-offs as explicit utility functions with weights. The hybrid design replaced those weights with "judgment," but a small LLM's "judgment" is just pattern matching against its training data. And the dominant pattern in its training data is: when people are in danger, allocate more resources.

The PRB scenario exposes this limitation because it never gives the model an easy off-ramp. In a scenario with occasional floods, the model might stumble into a "maintain" decision during a calm year simply because none of the increase triggers are active. PRB removes that possibility.

### Dr. Tanaka

The prompt design can be fixed for PRB, but it requires abandoning the symmetric framing. Currently, the prompt treats increase, maintain, and decrease as equally valid options to be selected based on conditions. This is the wrong frame for a small LLM. Instead, the prompt should establish a **strong default** (maintain) and require the model to overcome a justification threshold to deviate. I will elaborate in Round 4.

### Dr. Silva

I agree with Dr. Webb that this is partly a scenario issue, but I want to add: PRB is not an unusual scenario. Many real-world policy contexts involve persistent threats -- climate adaptation, pandemic response, homelessness. If the hybrid design only works when the environment occasionally goes quiet, it is too brittle for research use. The design needs to produce realistic behavior under sustained stress, which is the harder and more important case.

---

## Round 3: The "Do Not Worry" Phrasing

**Moderator**: The prompt includes: "The following hard limits are enforced automatically -- do not worry about them." Did this backfire?

### Dr. Tanaka

Absolutely, and this is the single most damaging line in the prompt. Let me explain the mechanism.

When you tell an instruction-tuned model "do not worry about constraints X, Y, Z," you are explicitly removing those constraints from the model's decision calculus. The model interprets this as: "These factors are handled externally; exclude them from your reasoning." This means the model will not self-moderate based on budget limits, consecutive-increase limits, or rate caps. It reasons as if those constraints do not exist.

The intended purpose was to prevent the model from incorrectly self-enforcing constraints (e.g., refusing to increase because it thinks the budget is too low, when the validator would handle that). But the side effect is that the model now sees its decision space as unconstrained. It asks: "Given this crisis, what is the best action ignoring all practical limits?" The answer is obviously the maximum increase.

This is a known anti-pattern in prompt engineering called **constraint externalization backfire**. When you externalize constraints, the model loses the ability to use those constraints as decision-relevant information. The budget being low is not just a "constraint" -- it is a policy-relevant signal that should influence the decision. By telling the model to ignore it, you removed a legitimate reason to choose maintain or decrease.

### Dr. Chen

I agree with Dr. Tanaka's analysis completely. I want to add a specific mechanism: in RLHF-trained models, "do not worry" is a **safety override pattern**. During training, phrases like "don't worry about X" are used to give the model permission to do things it might otherwise refuse. The model has learned that "do not worry" = "you have permission to be more aggressive." Combined with the crisis framing, this creates a strong signal to select the maximum action.

### Dr. Webb

I am less certain this is the primary cause. Even without the "do not worry" phrasing, I suspect the model would still escalate monotonically, because the environmental signals all point toward increase. The phrasing amplifies the problem but does not create it. If you removed the line, the model might occasionally self-constrain on budget, but it would still never voluntarily choose decrease because the crisis framing overwhelms the fiscal framing.

### Dr. Silva

I side with Dr. Tanaka and Dr. Chen on this. The "do not worry" phrasing has a specific cognitive-bias analogue: **moral licensing**. When you tell someone "the system will prevent bad outcomes," they feel licensed to make riskier choices because they are absolved of responsibility for consequences. The model exhibits a computational version of this: "I cannot cause harm by choosing the maximum increase, because validators will catch any problem." This removes the internal brake that might otherwise cause the model to moderate its choices.

---

## Round 4: Proposed Solutions

### Dr. Sarah Chen: Solution C -- Default Bias Mechanism

My recommendation is to restructure the prompt around an **explicit default with justification requirements**.

Replace the current symmetric framing with:

```
### DEFAULT POLICY
Your default action is **maintain_subsidy** (no change).

To deviate from the default, you must identify a SPECIFIC, STRONG reason
from the situation assessment. Vague urgency is not sufficient.

If you choose to increase, you must explain:
1. What specific metric has WORSENED since last year
2. Why the current rate is insufficient to address that specific worsening
3. Why a smaller increase would not be adequate

If you choose to decrease, you must explain:
1. What specific metric has IMPROVED or stabilized
2. Why the current rate is higher than necessary
```

This leverages a known property of small LLMs: they are better at following explicit procedural instructions than making open-ended judgments. By requiring specific justifications tied to year-over-year changes (not absolute levels), you force the model to engage with the temporal dimension. In PRB, even though floods occur every year, the subsidy level and budget change -- so the model might recognize "subsidy increased from 70% to 75% last year, budget dropped from 40% to 30%, and adaptation progress improved slightly" as a maintain signal.

I would also remove the "do not worry about constraints" line entirely and replace it with: "The constraints below are enforced by the system, but they reflect real policy limits that should also inform your judgment."

### Dr. Marcus Webb: Solution A+E -- Partial Validator Restoration with Trajectory Awareness

I disagree with a prompt-only solution. For a 3.3B model, prompt redesign is necessary but insufficient. You need structural guardrails.

My recommendation is a **two-layer approach**:

**Layer 1: Restore soft validators G5 and G7 in modified form.** The original G5 (SEVERE required for large increase) was too restrictive. Instead, implement a **trajectory-aware validator** that triggers when:
- Subsidy has increased for 3+ of the last 4 years, AND
- Budget is below 40%

When triggered, this validator does not block; it downgrades `large_increase` to `small_increase`. This preserves the LLM's directional intent while moderating magnitude.

**Layer 2: Add a "policy review" mechanism.** Every 4 years, inject a special prompt that summarizes the full trajectory: "Over the last 4 years, you increased subsidy from X% to Y%, spending Z% of the budget. Adaptation improved by W percentage points. Given this trajectory, is the current rate sustainable?" This forces periodic reflection even in a monotonically stressful environment.

The reason I prefer validators over prompt redesign is empirical: your own project memory states "WARNING rules = 0% behavior change for small LLMs." If warnings do not work, neither will elaborate prompt justification requirements. The model will generate convincing-sounding justifications for its predetermined choice. Validators are the only mechanism that reliably changes outcomes.

### Dr. Yuki Tanaka: Solution D -- Contrastive Deliberation Protocol

I propose a **two-stage decision protocol** that forces the model to argue both sides before committing.

**Stage 1: Generate arguments for ALL options.**

```
Before making your decision, analyze the situation from multiple perspectives.
For EACH of the following, write 1-2 sentences:

CASE FOR INCREASE: [Why increasing subsidy is justified this year]
CASE FOR MAINTAIN: [Why keeping the current rate is the wisest choice]
CASE FOR DECREASE: [Why reducing subsidy would serve long-term goals]

After completing all three analyses, make your decision.
```

This is a form of **chain-of-thought debiasing**. Research shows that forcing models to articulate counterarguments before deciding reduces positional bias and anchoring effects by 15-30%, even in small models. The key insight is that generating the "CASE FOR MAINTAIN" text activates reasoning pathways that would otherwise remain dormant.

**Stage 2: Add a comparative judgment.**

```
Which of your three cases is most strongly supported by the current data?
Choose that option.
```

I acknowledge Dr. Webb's concern that the model might generate weak strawman arguments for maintain/decrease. To mitigate this, provide example reasoning:

```
Example CASE FOR MAINTAIN: "Subsidy has already increased substantially
(from 50% to 72.5%) over the past 5 years. While floods continue,
the current rate provides meaningful support. Further increases risk
budget depletion before adaptation is complete."
```

The example anchors the model's reasoning quality for the non-increase cases.

### Dr. Roberto Silva: Solution B+C Hybrid -- Reframe the Decision as Resource Allocation Under Scarcity

My approach differs from the others. The fundamental problem is that the prompt frames the decision as "how much to help" -- and the model will always answer "as much as possible." Instead, reframe it as **resource allocation under scarcity**:

```
### CORE TRADE-OFF
You have a finite budget that must last the full program duration.
Every dollar spent on higher subsidies TODAY is a dollar unavailable
for future years when adaptation may be more urgent.

Your 10-year budget trajectory at the current subsidy rate:
- Year {year}: ${budget_remaining:,.0f} remaining
- Projected Year {year+3}: ${projected_budget_3yr:,.0f}
- Projected depletion year: Year {depletion_year}

If the budget depletes, ALL subsidies drop to the minimum floor (20%).
This would harm the communities you are trying to help.
```

This reframing leverages the model's RLHF training in a different way. Instead of "help people by increasing," it becomes "help people by preserving future capacity." The loss framing ("ALL subsidies drop to minimum floor") activates the model's aversion to harmful outcomes. The projected depletion year makes consequences concrete.

I also strongly recommend adding a **temporal discount signal**: "You are in Year X of a 13-year program. You have Y years remaining." This gives the model a planning horizon. Without it, the model treats each year as an independent decision with no future.

I would combine this with Dr. Chen's default-bias mechanism. Maintain as default + scarcity framing is the minimum viable fix.

---

## Round 5: Consensus and Recommendation

**Moderator**: Can the panel converge on a unified recommendation?

### Discussion

**Dr. Chen**: I think we are converging on a three-part solution. Dr. Silva's scarcity reframing addresses the motivational problem -- why the model should ever choose not to increase. My default-bias mechanism addresses the structural problem -- making maintain the path of least resistance. And Dr. Webb's trajectory-aware validator provides a safety net for when prompt redesign is insufficient.

**Dr. Webb**: I want to emphasize that we should not rely on prompt redesign alone. The project's own experience shows that governance suggestions are "de facto commands" for small LLMs, and that WARNING-level rules produce 0% behavior change. We need at least one restored soft validator as a backstop.

**Dr. Tanaka**: I accept that contrastive deliberation may be too token-expensive for a 3.3B model in a 13-year x 400-agent simulation. But I strongly recommend incorporating the "do not worry" removal and the example-anchored reasoning for the maintain case. Even if the full contrastive protocol is not used, a single well-crafted example of maintain-reasoning will shift the model's behavior more than any amount of abstract framing.

**Dr. Silva**: Agreed. The scarcity reframing is the highest-priority change because it addresses the root motivational asymmetry. Without it, every other fix is fighting against the model's fundamental "help more = better" prior.

### Consensus Recommendation

The panel recommends a **four-component intervention**, ordered by priority:

#### 1. Remove the "Do Not Worry" Line (Immediate)

Replace:
```
The following hard limits are enforced automatically — do not worry about them:
```

With:
```
The following hard limits are enforced by the system. They reflect real policy
constraints that should also inform your reasoning:
```

**Rationale**: The current phrasing removes constraints from the model's decision calculus and triggers a moral-licensing / safety-override pattern. The replacement keeps the model informed that validators exist while encouraging it to treat constraints as decision-relevant signals.

#### 2. Add Scarcity Framing and Temporal Horizon (High Priority)

Add a new "SUSTAINABILITY" section between BUDGET STATUS and SITUATION ASSESSMENT:

```
### SUSTAINABILITY
- Program duration: 13 years. You are in Year {year}. Years remaining: {13 - year}.
- Budget burn rate at current subsidy: ~${annual_cost:,.0f}/year
- Projected years until budget depletion: {years_to_depletion}
- WARNING: If budget depletes, all subsidies drop to the 20% floor for the
  remaining program years. This would abruptly withdraw support from all communities.
```

**Rationale**: Makes the inter-temporal trade-off concrete. Activates the model's aversion to harmful outcomes (budget depletion) as a counterweight to its aversion to inaction (not increasing).

#### 3. Establish Maintain as the Explicit Default (High Priority)

Replace the current "POLICY CONSIDERATIONS" section with a default-first structure:

```
### DECISION FRAMEWORK

**Default action: maintain_subsidy**
Unless conditions have CHANGED SIGNIFICANTLY since last year, maintaining the
current rate supports policy stability and budget sustainability.

To justify an INCREASE, at least one of these must be true:
- Flood severity has WORSENED compared to recent years
- Adaptation progress has STALLED or REVERSED
- Budget health is ADEQUATE or better (>40% remaining)

To justify a DECREASE, at least one of these must be true:
- Subsidy rate is above 70% AND budget health is declining
- Adaptation progress is STRONG (>50% of vulnerable households adapted)
- Budget is below 30% remaining

Example of good maintain reasoning: "While floods continue to affect the basin,
the current subsidy rate of {subsidy_rate:.0%} represents a significant increase
from the initial 50%. Adaptation progress is ongoing at {mg_elevated_pct:.1f}%.
Further increases would accelerate budget depletion (currently {govt_budget_pct:.0f}%
remaining, projected {years_to_depletion} years to depletion). Maintaining the
current rate balances continued support with fiscal sustainability."
```

**Rationale**: Establishes maintain as the default through explicit instruction (which small LLMs follow reliably). Provides concrete threshold conditions for deviation. The example reasoning anchors the model's output quality for the maintain case, addressing the asymmetry where the model has abundant training data for "we must act" reasoning but little for "prudent restraint" reasoning.

#### 4. Restore One Trajectory-Aware Soft Validator (Medium Priority)

Implement a new validator (replacing the removed G7 "fiscal pullback"):

```
G7-v2: Trajectory Moderation
Trigger: (consecutive_increases >= 2) AND (budget_pct < 40%)
Action: Downgrade large_increase → small_increase (do NOT block entirely)
Severity: WARNING (logged but not blocking)
Rationale: When budget is declining under sustained increases,
           moderate the magnitude while preserving the model's directional intent.
```

Separately, for the insurance agent:

```
I6-v2: Ceiling Awareness
Trigger: (crs_discount >= 35%) AND (mitigation_score < 70)
Action: Downgrade significantly_improve → improve
Severity: WARNING
Rationale: Near-ceiling improvements should require strong mitigation evidence.
```

**Rationale**: Dr. Webb's point is well-taken -- prompt redesign alone may be insufficient for a 3.3B model. These validators serve as a safety net, not a primary control mechanism. They downgrade rather than block, preserving the hybrid design's principle that the LLM makes directional choices. If the prompt redesign (components 1-3) works well, these validators will rarely trigger. If it does not, they prevent the worst outcomes.

### What NOT to Do

The panel advises against:

- **Full contrastive deliberation** (Dr. Tanaka's Stage 1+2): Too token-intensive for production use with 400 agents over 13 years. Reserve for future work with larger models.
- **Restoring all 7 removed soft validators**: This would defeat the purpose of the hybrid redesign. The goal is LLM judgment with minimal guardrails, not validator-driven behavior.
- **Reordering options to put maintain first**: While this would exploit positional bias, it would make the bias work FOR us rather than eliminating it. This is fragile and would break with any model change.
- **Adding numeric utility scores**: This would convert the hybrid design back into a deterministic rule system. If that is desired, remove the LLM entirely and use a lookup table.

### Expected Outcomes

With all four components implemented, the panel expects:

| Metric | Current | Expected |
|--------|---------|----------|
| Voluntary maintain decisions | 0/13 | 3-5/13 |
| Voluntary decrease decisions | 0/13 | 1-2/13 |
| Large increase selections | 11/13 | 4-6/13 |
| Final subsidy rate | 82.5% | 60-70% |
| Budget remaining | 17% | 30-45% |
| Validator blocks needed | 6 | 1-3 |

These are estimates based on the panel's collective experience with small-model prompt interventions. The actual impact should be validated through A/B testing: run the modified prompt on the same 13-year PRB scenario and compare trajectories.

### Validation Protocol

1. **Isolated prompt test**: Run the modified government prompt through 13 sequential LLM calls with recorded PRB data. Verify that at least 2/13 decisions are maintain or decrease.
2. **Ablation**: Test each component individually (remove one at a time) to identify which has the largest effect.
3. **Robustness**: Test with 3 random seeds to ensure the behavior change is consistent, not a single-seed artifact.
4. **Regression check**: Verify that the model still increases appropriately in early years when subsidy is low and floods are severe. Over-correction (never increasing) would be equally problematic.

---

## Summary of Key Findings

1. **Root cause**: Monotonic escalation results from the interaction of (a) action bias in RLHF-trained models, (b) emotionally asymmetric prompt framing, (c) constraint externalization ("do not worry"), and (d) an environmental scenario (PRB) that never presents decrease-triggering conditions.

2. **The "do not worry" phrasing** is the single most actionable fix. It removes constraints from the model's decision space and triggers a moral-licensing pattern. Removing it is low-cost and high-impact.

3. **Scarcity framing** addresses the motivational root cause by making the inter-temporal trade-off (help now vs. help later) explicit and emotionally salient.

4. **Maintain-as-default** with justification requirements leverages small models' strength (following explicit procedures) rather than their weakness (open-ended judgment).

5. **One or two soft validators** should be retained as a safety net, but should downgrade rather than block, preserving the hybrid design's intent.

6. **Prompt redesign alone is likely insufficient** for a 3.3B model. The combination of prompt + validator provides defense in depth.
