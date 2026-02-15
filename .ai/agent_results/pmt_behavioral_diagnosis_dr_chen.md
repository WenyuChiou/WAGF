# PMT Behavioral Diagnosis: Why the Flood ABM Fails Two Empirical Benchmarks

**Analyst**: Dr. Sarah Chen, Social Scientist (Protection Motivation Theory, Disaster Risk Behavior, Environmental Justice)
**Date**: 2026-02-15
**Subject**: 400-agent x 3-year Passaic River Basin flood adaptation ABM

---

## 1. Executive Summary

Two L2 benchmarks fail because the model's PMT implementation suffers from **construct collapse** and **missing behavioral mechanisms**. The coping perception (CP) distribution collapses to a near-universal "Medium" rating (89.8%), which eliminates the theoretical pathway through which PMT differentiates marginalized from non-marginalized behavior. Simultaneously, the LLM exhibits a strong **action bias** -- it reasons like a rational optimizer rather than a boundedly rational human affected by status quo bias, optimism bias, and cognitive inertia. These are not calibration problems; they are structural model specification gaps.

---

## 2. Benchmark Failure Diagnosis

### 2.1 do_nothing_postflood = 0.334 (Target: 0.35-0.65)

The model is marginally below the lower bound, but the mechanism producing this number is deeply problematic. Of the 131 "effective do_nothing" outcomes post-flood, **101 come from governance REJECTION of elevation proposals** -- not from genuine inaction decisions. The LLM itself produces only 7.7% voluntary do_nothing choices. This means the model achieves its do_nothing rate almost entirely through institutional constraint, not through the psychological mechanisms that actually produce inaction in the real world.

**What the literature says**: Post-flood inaction arises from multiple interacting mechanisms:

- **Status quo bias** (Samuelson & Zeckhauser 1988): Humans exhibit a strong preference for the current state of affairs, even when alternatives are objectively superior. This is entirely absent from the LLM's reasoning patterns.
- **Optimism bias** (Botzen et al. 2015): "It won't happen again" or "It won't be as bad next time." Flood victims systematically underestimate future risk within 2-5 years of an event, a phenomenon called the **levee effect** or **flood memory decay** (Atreya et al. 2013).
- **Competing financial priorities**: Real households face mortgage payments, medical bills, car repairs. The prompt presents flood adaptation in isolation, as if the household has no other demands on its budget.
- **Decision fatigue and cognitive overload**: Post-disaster households face dozens of simultaneous decisions (FEMA claims, insurance claims, temporary housing, school disruption). Adaptation is deferred not from irrationality but from genuine cognitive capacity constraints (Peek & Mileti 2002).
- **Fatalism pathway in PMT** (Grothmann & Reusswig 2006): When threat appraisal is high but coping appraisal is low (TP=H, CP=L), PMT predicts *non-protective responses* -- denial, wishful thinking, fatalism. The governance rules correctly encode this pathway (`owner_fatalism_allowed`), but because 89.8% of agents assign CP=M, almost no agents ever enter this branch.

**Root cause**: The LLM is a helpful assistant by training. It reasons toward solutions. When presented with a flood scenario, financial details, and a menu of options, it performs cost-benefit analysis and selects the "best" action. It does not naturally model the psychological paralysis, information avoidance, or temporal discounting that characterizes real post-flood behavior.

### 2.2 mg_adaptation_gap = 0.045 (Target: 0.05-0.30)

MG agents adapt at nearly the same rate as NMG agents, and in some categories (insurance), MG agents adapt *more*. This fundamentally contradicts the environmental justice literature (Cutter 2003; Thomas & Twyman 2005; Masozera et al. 2007).

**Root cause -- CP Collapse**: The CP distribution parameters for MG (alpha=4.07, beta=3.30) produce a Beta distribution with mean ~0.55, while NMG (alpha=5.27, beta=4.18) produces mean ~0.56. These are nearly identical. When discretized into the VL/L/M/H/VH scale, both groups pile into the "M" bin. The PMT pathway that should differentiate behavior -- MG agents perceiving lower coping capacity due to income constraints, information barriers, and institutional distrust -- is numerically erased before it reaches the LLM.

Even if the Beta parameters produced more separation, the current CP construct definition is too abstract. It asks about confidence that "mitigation options are effective and affordable" without anchoring to specific income-to-cost ratios. A $20K household and a $100K household both read "coping perception" and both think "Medium" because the LLM interprets "coping" as a general sense of agency, not as a computation of financial feasibility.

---

## 3. Missing Behavioral Mechanisms

### 3.1 Insurance Affordability Constraints

The governance layer correctly blocks unaffordable elevations for low-income agents. But there is **no equivalent affordability gate for insurance**. At $20K annual income, even a $500/year NFIP premium represents 2.5% of gross income -- a non-trivial burden that competes with food, rent, and transportation. The renter prompt mentions "Consider your income carefully. Even $300-600/year in premiums can be a significant burden on a tight budget" (line 51), but this is advisory language that the LLM systematically ignores. Small LLMs treat suggestions as decoration; only ERROR-level governance rules produce behavioral change (a lesson already documented in this project's MEMORY.md).

**Recommendation**: Add an `insurance_affordability` governance rule: if `annual_premium / income > 0.03` (3%), block insurance at WARNING level for renters and ERROR level for MG renters below the poverty line. This would reduce MG insurance uptake toward empirical ranges while preserving NMG uptake.

### 3.2 Status Quo Bias and Decision Inertia

The prompt's "DECISION CALIBRATION CONTEXT" section provides base rates (60-70% do_nothing for owners, 70-80% for renters), but the LLM treats these as informational context rather than behavioral constraints. The LLM's training objective -- to be maximally helpful and provide reasoned recommendations -- directly opposes the empirical finding that most people do nothing.

**Recommendation**: Introduce a **stochastic do_nothing override** at the governance level. After flood, if `random() < 0.35`, force do_nothing regardless of LLM output. This is not ideal from a theoretical standpoint, but it acknowledges that status quo bias, optimism bias, and decision fatigue are not easily elicited from an LLM through prompt engineering alone. An alternative: add a `decision_inertia` pre-filter that checks whether the agent took action in the previous year and, if not, applies a 60% probability of repeating do_nothing.

### 3.3 CP Construct Operationalization

The CP construct collapses because it conflates three distinct sub-dimensions:

1. **Response efficacy**: "Will insurance/elevation actually protect me?" (belief about the action)
2. **Self-efficacy**: "Can I personally execute this action?" (belief about one's own capacity)
3. **Response cost**: "Can I afford this action?" (financial feasibility)

In PMT theory (Rogers 1983; Grothmann & Reusswig 2006), these three interact multiplicatively. A $20K MG household might believe insurance is effective (high response efficacy) and know how to purchase it (moderate self-efficacy) but cannot afford it (high response cost). The net CP should be Low. But the current single-dimension CP label compresses all three into one rating, and the LLM defaults to the modal "Medium."

**Recommendation**: Decompose CP into at least two sub-constructs in the response format:
- `cp_efficacy` (VL-VH): "How effective would protective actions be for your situation?"
- `cp_affordability` (VL-VH): "How affordable are protective actions given your specific income and expenses?"

Then use `cp_affordability` as the governance gate. MG agents with low `cp_affordability` should be blocked from insurance (not just elevation) and routed to the fatalism/do_nothing pathway.

### 3.4 Temporal Discounting and Memory Decay

The prompt includes `years_since_flood` and the model has TP decay parameters, but the LLM's reasoning shows no evidence of temporal discounting. The MG owner example (flood_count=2) reasons about elevation as "the most prudent course" -- showing no discounting of past events. In reality, Atreya et al. (2013) show that willingness to pay for flood protection drops by 4-9% per year after a flood event. By year 3 post-flood, many households have psychologically "moved on."

**Recommendation**: Make TP decay explicit in the prompt: "Your last flood was {years_since_flood} years ago. Research shows that flood concern naturally diminishes over time -- after 3+ years, most people feel significantly less urgency about flood protection."

---

## 4. The Renter Problem

Renters show pathologically low do_nothing rates (5-9.4% post-flood). This is the single largest contributor to the do_nothing_postflood failure. The governance rules for renters are more aggressive than for owners: `renter_inaction_moderate_threat` blocks do_nothing at WARNING level when TP is H/VH and CP is M. Since most renters get TP=H after flooding and CP=M (the collapsed default), this rule fires constantly, pushing nearly all post-flood renters toward insurance purchase.

**The empirical reality is the opposite**: renters are *less* likely than owners to take protective action post-flood (Grothmann & Reusswig 2006; Bubeck et al. 2012). Renters have shorter time horizons, lower financial stakes in the property, and often assume the landlord's insurance covers them.

**Recommendation**: Remove `renter_inaction_moderate_threat` entirely. The WARNING level is documented as producing 0% behavioral change for small LLMs (see MEMORY.md), but this appears to be acting on behavior nonetheless -- likely because the warning message text is included in the retry prompt and the LLM complies. Renters should face *less* governance pressure toward action than owners, not more.

---

## 5. Summary of Recommendations (Priority Order)

| Priority | Intervention | Expected Effect | Benchmark Impact |
|----------|-------------|-----------------|------------------|
| P0 | Remove `renter_inaction_moderate_threat` rule | Renters can choose do_nothing post-flood | +do_nothing_postflood |
| P0 | Widen CP Beta separation (MG alpha~2.5/beta~4.5 vs NMG alpha~6/beta~3) | MG agents get CP=L/VL, triggering fatalism pathway | +mg_adaptation_gap |
| P1 | Add insurance affordability governance rule | MG insurance uptake drops from 58% toward 30-40% | +mg_adaptation_gap |
| P1 | Add explicit TP decay language in prompt | Post-flood urgency fades over time | +do_nothing_postflood |
| P2 | Decompose CP into efficacy + affordability sub-constructs | Finer-grained PMT differentiation | Both benchmarks |
| P2 | Decision inertia pre-filter (repeat last year's action at 60%) | Status quo bias without prompt engineering | +do_nothing_postflood |

---

## 6. Theoretical Assessment

The current model implements PMT's *structure* (five constructs, appraisal ratings, action selection) but not its *dynamics*. PMT is fundamentally a theory about the balance between threat appraisal and coping appraisal, where the coping pathway is the primary determinant of whether threat translates into protection or fatalism (Rogers 1983). When CP collapses to a single mode, the entire theory reduces to: "higher threat = more action." This is a rational actor model wearing a PMT costume.

The governance layer partially compensates by blocking unaffordable actions, but governance operates post-decision -- it corrects the LLM's output rather than shaping the LLM's reasoning process. The result is a model where 77% of "inaction" comes from institutional rejection rather than psychological process. This is empirically indistinguishable in aggregate outcome metrics, but it is theoretically invalid and will produce incorrect predictions under policy counterfactuals (e.g., "what happens if subsidies increase?" -- the model would predict more elevation, but in reality, status quo bias would dampen the response).

The path forward requires making the LLM *reason like a boundedly rational human*, not correcting its rational-optimizer outputs after the fact. This means anchoring CP to concrete financial ratios, introducing explicit bias language in prompts, and accepting that some behavioral patterns (status quo bias, optimism bias) may require stochastic mechanisms rather than prompt engineering.

---

*References: Atreya et al. 2013 (J Risk Uncertainty); Botzen et al. 2015 (Risk Analysis); Bubeck et al. 2012 (Risk Analysis); Cutter 2003 (Social Science Quarterly); Grothmann & Reusswig 2006 (J Hydrology); Masozera et al. 2007 (J Environmental Management); Peek & Mileti 2002 (Natural Hazards Review); Rogers 1983 (Social Psychophysiology); Samuelson & Zeckhauser 1988 (J Risk Uncertainty); Thomas & Twyman 2005 (Global Environmental Change)*
