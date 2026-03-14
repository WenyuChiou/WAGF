# Expert Panel: Renter Relocation Behavior in Multi-Agent Flood Simulation

**Date**: 2026-03-14
**Simulation**: 400 agents (200 owners, 200 renters), Passaic River Basin, NJ, 13 years, Gemma 3 4B
**Moderator**: Research Team

## Panel Members

| Expert | Domain | Affiliation |
|--------|--------|-------------|
| Dr. Sarah Chen | Behavioral flood science, PMT, renter/owner differences | UC Davis |
| Dr. Marcus Rivera | Disaster relocation, housing mobility, managed retreat | Columbia CIESIN |
| Dr. Aya Tanaka | LLM behavioral calibration, prompt engineering effects | Stanford HAI |

---

## Question 1: Is the renter relocation rate (0.35%) empirically plausible?

### Dr. Sarah Chen (Behavioral Flood Science)

Let me start with what the empirical literature tells us. The 0.35% rate --- 9 relocations out of 2,600 renter-year decisions --- is extremely low, but we need to be careful about what we compare it to.

In the PMT literature, renters are generally understood to have *lower* place attachment and *lower* sunk costs than owners. Grothmann and Reusswig (2006) found that coping appraisal --- not just threat perception --- is the primary driver of protective action. If renters perceive that they *cannot* cope with relocation costs, PMT predicts non-protective responses (denial, wishful thinking, fatalism), regardless of threat level.

However, the empirical relocation data tells a different story from pure inaction. FEMA's post-disaster mobility studies (Zagorsky et al., 2006; Deryugina et al., 2018) show that renter displacement rates after major floods are substantially higher than owner displacement rates. After Hurricane Katrina, approximately 30-40% of renters in heavily flooded areas had not returned to their original neighborhoods within 2 years, compared to ~15-20% of owners. After Hurricane Harvey, Ratcliffe et al. (2019) found renter out-migration from flooded census tracts was roughly 2x the owner rate.

The critical distinction is between *voluntary planned relocation* (what the model simulates) and *forced displacement* (what the empirical data often captures). Many renters do not "choose" to relocate --- their landlord raises rent, declines to repair, or sells the property. Others leave because affordable replacement housing is unavailable in the flooded area.

**My assessment**: A 0.35% *voluntary, proactive* relocation rate is plausible for a single decision year, but it is implausible that only 9 relocations occur across 13 years in a population where 146/200 renters experience an 18-foot flood in Year 1 and repeated flooding thereafter. The cumulative relocation rate for repeatedly-flooded renters should be in the range of 5-15% over a 13-year period, based on longitudinal panel data from the PSID and AHS (Gallagher, 2014; Boustan et al., 2020).

### Dr. Marcus Rivera (Disaster Relocation)

I agree with Dr. Chen's framing. The distinction between voluntary and involuntary relocation is essential, and the model currently only captures the voluntary channel.

Let me add specifics from the managed retreat literature. In the Passaic River Basin itself, the Blue Acres buyout program has relocated approximately 700+ properties since its inception, but these are predominantly homeowners. For renters, the relocation pathway is entirely different --- there is no government program that *purchases* a renter's lease or funds their move. Renters who relocate bear the full cost themselves.

That said, the empirical evidence clearly shows that renters are MORE mobile than owners, not less. The American Housing Survey consistently shows renter median tenure of ~2-3 years vs. owner median tenure of ~13 years. Baker (2011) and Kick et al. (2011) found that flood-affected renters in the Mississippi Delta had 3-4x the out-migration rate of owners.

The key finding from my work on post-Sandy relocation in NJ specifically: among renters in substantially damaged units (>$50K damage), approximately 25% relocated within 18 months. The primary drivers were (1) landlord decisions (not repairing, raising rent), (2) mold and habitability issues, and (3) fear of recurrence. Notably, only about 5-8% of these relocations were "proactive flood adaptation" --- most were reactive to immediate habitability problems.

**My assessment**: 0.35% is too low by roughly an order of magnitude. Even excluding involuntary displacement, I would expect 3-8% of repeatedly-flooded renters to voluntarily relocate over 13 years. The model is missing two critical channels:
1. **Landlord-mediated displacement** (rent increases, non-repair, property sale)
2. **Habitability-driven relocation** (mold, structural issues post-flood)

These are not "renter choices" in the PMT sense, but they are empirically dominant pathways.

### Dr. Aya Tanaka (LLM Calibration)

I want to flag something the other panelists haven't addressed: the *reasoning patterns* in the model output. The user reports that 95.6% of do_nothing decisions explicitly mention relocation in reasoning but dismiss it, primarily citing the $5K-$10K cost as "prohibitive."

This is a telltale sign of prompt anchoring in small LLMs. Gemma 3 4B is latching onto the specific dollar figures in the prompt ($5,000-$10,000) and the phrase "major upheaval" and treating them as dispositive. The LLM is not performing genuine cost-benefit reasoning --- it is pattern-matching the prompt language that says "Do not choose relocation unless..." and finding that the threshold is never met, regardless of accumulated damage.

Consider: a renter with $300K+ cumulative damage over 10+ floods is dismissing a $5K-$10K relocation cost as "prohibitive." For a household earning $50K-$100K/year (NMG income range), $5K-$10K is 5-20% of annual income --- significant but clearly not prohibitive when weighed against $300K in cumulative losses. The fact that the LLM consistently reaches this conclusion suggests it is not reasoning from the numbers but from the prompt framing.

**My assessment**: The 0.35% rate is an artifact of prompt suppression, not a genuine simulation finding. The prompt is functioning as a near-absolute block on relocation for the Gemma 3 4B model.

---

## Question 2: Why do renters show no significant adaptation response to severe flood years?

### Dr. Sarah Chen

This is where the 3-option limitation becomes critical. Look at the owner decision space:

| Owners | Renters |
|--------|---------|
| do_nothing | do_nothing |
| buy_insurance (structure+contents) | buy_contents_insurance |
| elevate_house (3/5/8 ft) | relocate |
| buyout_program | --- |

Owners have a *graduated* adaptation ladder: insurance (low cost, low commitment) -> elevation (high cost, high commitment, reversible in the sense that you keep your home) -> buyout (irreversible). Each step represents a meaningful escalation in response to increasing risk.

Renters have a *binary* ladder: insurance (low cost) -> relocation (high cost, high disruption, irreversible in terms of community ties). There is no intermediate step. When insurance alone is insufficient but relocation feels excessive, renters are trapped --- the rational response is to keep buying insurance and hoping for the best.

This is actually consistent with PMT's "protection motivation gap" (Bubeck et al., 2012): when the available coping options are perceived as either trivial or extreme, agents default to the trivial option even when threat is high.

**The adaptation response IS there** --- it shows up in the insurance channel. Flooded renters buying insurance at 62-92% rates is a strong and appropriate response. The issue is that we are looking for a relocation signal that the decision architecture makes nearly impossible to produce.

### Dr. Marcus Rivera

I want to push back slightly on the framing of the question. The data shows renters DO respond to severe flood years --- through insurance. Year 1 (18.0 ft): 58.5% buy insurance. That is a dramatic response. The question should be: why don't renters show an *escalating* response over time?

And the answer, I believe, is structural. In reality, renters have several additional adaptation options that this model does not capture:

1. **Flood-proofing contents** (elevated storage, waterproof containers): $200-$1,000
2. **Emergency preparedness investments** (go-bags, backup documents, emergency savings): $100-$500
3. **Lease negotiation** (requesting landlord flood-proof the unit, install sump pumps): $0
4. **Partial relocation** (moving within the basin to a lower-risk unit): $2,000-$5,000
5. **Reducing exposure** (moving valuables to upper floors, reducing total contents value): $0

These options fill the gap between "buy insurance" and "full relocation." Without them, the model forces a binary choice that does not reflect actual renter behavior.

I would also note that the relocation cost framing ($5K-$10K within PRB, $15K-$25K out of basin) may be miscalibrated. For a local move within the Passaic River Basin --- say, from a flood-prone unit in Little Falls to a non-flood-prone unit in Wayne --- the actual cost for a renter is primarily:
- Security deposit: 1.5 months rent (~$2,000-$3,000)
- Moving truck: $200-$500
- Overlap rent: 1 month (~$1,200-$2,000)
- Miscellaneous: $500-$1,000

Total: $3,500-$6,500 --- at the low end of the stated range. And critically, this is money that would otherwise be spent on insurance premiums, flood damage deductibles, and replacement of damaged contents.

### Dr. Aya Tanaka

The decay pattern is also revealing. Insurance uptake *declines* from Year 1 (58.5%) through Years 11-13 (42-44%) despite continued severe flooding. This suggests that whatever adaptation signal exists is being eroded by the prompt's default framing: "Your default choice is do_nothing... Choosing do_nothing means you focus on your everyday life and budget. This is a rational and common choice."

For a 4B LLM, this framing establishes a powerful prior. Every year, the agent starts from a position of "do_nothing is the default rational choice," and must overcome that framing through threat perception alone. Over time, the LLM appears to habituate --- the repeated flood signal loses its ability to override the default framing. This is actually an interesting emergent behavior (it resembles real-world "flood fatigue"), but it is unclear whether it emerges from genuine reasoning or from the LLM's tendency to return to its trained prior when prompted with strong default language.

I also want to highlight the governance rules in `ma_agent_types.yaml`. The `renter_complex_action_low_coping` rule blocks relocation when CP is VL or L:

```yaml
- id: renter_complex_action_low_coping
  conditions:
    - construct: CP_LABEL
      values: [VL, L]
  blocked_skills: [relocate]
  level: ERROR
```

This means any renter who rates their coping perception as Low or Very Low --- which is precisely the profile of a financially constrained, repeatedly-flooded renter --- is *mechanically blocked* from relocating. Combined with the prompt language, this creates a double suppression: the prompt discourages relocation, and the governance validator blocks it for the agents most likely to feel they cannot cope. This is the PMT fatalism pathway working as designed, but the question is whether the threshold is set correctly.

---

## Question 3: Is the prompt language too directive for a 4B LLM?

### Dr. Aya Tanaka

I will lead on this one. Let me do a direct comparison of the critical sentences:

**Renter relocation (line 60-61):**
> "Do not choose relocation unless your personal flood experience has been severe and repeated."

**Owner buyout (line 71):**
> "Buyout is realistic only for homeowners who have experienced 3+ severe floods, have exhausted other options (insurance, elevation), and are emotionally prepared to leave their neighborhood permanently."

Both are directive, but they differ in important ways:

1. **Imperative vs. descriptive**: The renter prompt uses an imperative command ("Do not choose X unless Y"). The owner prompt uses a descriptive frame ("X is realistic only for Y"). For a large LLM (70B+), these might be functionally equivalent. For Gemma 3 4B, the imperative "Do not" is processed as a hard instruction, not a heuristic.

2. **Threshold specificity**: The owner prompt gives a specific, checkable threshold (3+ severe floods, exhausted other options, emotionally prepared). The renter prompt gives a vague threshold ("severe and repeated") with no concrete number. For a small LLM, vague thresholds default to "never met."

3. **Escape hatch**: The owner prompt embeds the buyout threshold within a longer passage that also describes the practical mechanics (Blue Acres, wait times, funding). This dilutes the directive force. The renter prompt concentrates the directive in two sentences with no mitigating context.

4. **Outcome**: ~15 owner buyouts vs. 9 renter relocations --- despite buyout being objectively a harder decision (permanent, irreversible, involves selling property). This asymmetry strongly suggests the prompt language, not the decision difficulty, is the primary driver.

**My verdict**: Yes, the renter relocation prompt is too directive for Gemma 3 4B. The phrase "Do not choose relocation unless" is functioning as a near-absolute command.

### Dr. Sarah Chen

I agree with Dr. Tanaka's linguistic analysis. But I want to add a behavioral science perspective on *why* the current language might have seemed reasonable during calibration.

The intent behind the directive language is sound: in reality, renters do not relocate proactively after a single flood. There is extensive literature on status quo bias, loss aversion in housing decisions, and the "hassle factor" of moving (Samuelson & Zeckhauser, 1988). The prompt is trying to prevent the LLM from being unrealistically proactive about relocation.

However, the calibration target should not be "almost never relocate" --- it should be "relocate at empirically observed rates for repeatedly-flooded renters." And those rates, as Dr. Rivera and I discussed, are in the 5-15% range over a multi-year period for severely affected populations.

The fundamental issue is that the prompt language was calibrated to prevent *false positive* relocations (unrealistic early relocation) but overcorrected to the point of preventing *true positive* relocations (realistic late relocation after repeated severe flooding).

### Dr. Marcus Rivera

I want to add one more observation. The owner buyout language includes this critical sentence: "most choose to stay and adapt in place." This is descriptive and normalizes staying --- but it does not *command* staying. The renter language crosses that line.

Also, consider the information asymmetry. The owner prompt provides detailed cost information for *every* option (insurance premiums, elevation costs at 3 tiers with subsidy calculations, buyout offer value). The renter prompt provides detailed cost information that *discourages* relocation ($5K-$10K within PRB, $15K-$25K out of basin, plus "loss of community ties") but does not provide a corresponding cost-benefit framing (e.g., "If your cumulative flood damage exceeds $X, relocation costs may be offset within Y years").

For a small LLM reasoning about costs, having only the cost side and not the benefit side of the relocation calculus creates a systematic bias toward inaction.

---

## Cross-Discussion: The Double Suppression Problem

### Dr. Tanaka

I want to name what I see as the core finding of this panel: **renter relocation is subject to double suppression** in the current model design.

Layer 1: **Prompt suppression** --- "Do not choose relocation unless..." functions as a near-command for Gemma 3 4B, causing the LLM to dismiss relocation in reasoning even when the numerical evidence (cumulative damage, repeated floods) would justify it.

Layer 2: **Governance suppression** --- The `renter_complex_action_low_coping` validator blocks relocation when CP = VL or L. But repeatedly-flooded, financially constrained renters are precisely the agents most likely to self-rate low coping perception --- because the prompt tells them relocation costs are "prohibitive." The prompt creates low CP, and the validator then blocks the action that low-CP agents might be driven to by desperation.

### Dr. Chen

This is a critical feedback loop. In the PMT literature, there is a phenomenon called "protective action decision making under resource constraints" (Lindell & Perry, 2012) where agents with high threat and low coping sometimes take *desperate* protective actions --- moving in with family, doubling up in a friend's apartment, or simply leaving with no plan. The current model architecture makes this pathway impossible.

### Dr. Rivera

And empirically, this is exactly what we observe in post-disaster renter mobility. The renters who relocate are often NOT the ones with high coping capacity --- they are the ones who have been pushed past their threshold by repeated losses. They do not relocate because they have the resources; they relocate because they have exhausted their tolerance. The model's equation of "low coping = cannot relocate" inverts the empirical reality for the most extreme cases.

---

## Consensus Recommendations

The panel reaches consensus on the following findings and action items:

### Finding 1: The 0.35% renter relocation rate is empirically implausible

**Confidence**: High (all three panelists agree)

The empirical literature suggests a cumulative voluntary relocation rate of 5-15% for repeatedly-flooded renters over a 13-year period. The model's 0.35% rate (9/2,600 decisions) represents prompt-induced suppression, not a genuine behavioral finding.

### Finding 2: Double suppression is the root cause

**Confidence**: High

The combination of directive prompt language ("Do not choose relocation unless...") and the governance validator (`renter_complex_action_low_coping` blocking relocation at CP = VL/L) creates a near-complete block on renter relocation. These two mechanisms interact: the prompt induces low coping perception, and the validator then blocks action based on that low coping perception.

### Finding 3: The 3-option limitation exacerbates the problem

**Confidence**: Medium-High

Renters have no intermediate adaptation step between insurance and full relocation. This creates a "protection motivation gap" where agents default to insurance even when it is insufficient, because the only alternative is perceived as too extreme.

---

### Action Item 1: Revise renter relocation prompt language (HIGH PRIORITY)

**Current (line 60-61):**
> "Relocation is a major upheaval. Moving means breaking your lease, finding new housing, disrupting work and school, and leaving your familiar neighborhood. Renters who relocate due to flood risk have typically experienced repeated severe flooding and decided their current home is no longer safe. Do not choose relocation unless your personal flood experience has been severe and repeated."

**Proposed revision:**
> "Relocation is a significant decision. Moving means finding new housing, managing moving costs, and adjusting to a new neighborhood. Most renters stay in place after a single flood. However, renters who have experienced multiple severe floods sometimes decide that moving to a safer area --- even within the same region --- is worth the short-term cost and disruption. If you have been flooded 3 or more times, or your cumulative damage significantly exceeds relocation costs, moving may be a reasonable choice."

**Rationale** (Dr. Tanaka):
- Removes imperative "Do not choose" framing
- Replaces "major upheaval" with "significant decision" (less emotionally loaded)
- Provides concrete threshold (3+ floods) matching the owner buyout threshold
- Introduces cost-benefit framing (cumulative damage vs. relocation cost)
- Retains the descriptive norm that most renters stay after a single flood

### Action Item 2: Revise governance validator threshold (MEDIUM PRIORITY)

**Current**: `renter_complex_action_low_coping` blocks relocation at CP = VL or L

**Proposed**: Block relocation only at CP = VL; allow at CP = L with WARNING

```yaml
- id: renter_complex_action_low_coping
  conditions:
    - construct: CP_LABEL
      values: [VL]
  blocked_skills: [relocate]
  level: ERROR
  message: Relocation is blocked due to very low confidence in your ability to cope.

- id: renter_relocation_low_coping_warning
  conditions:
    - construct: CP_LABEL
      values: [L]
  blocked_skills: [relocate]
  level: WARNING
  message: Low coping capacity makes relocation difficult but not impossible if flood damage is severe.
```

**Rationale** (Dr. Rivera): Empirically, low-coping renters do relocate under duress. Blocking at L is overly conservative. WARNING at L allows the model to reason through the tradeoff rather than being mechanically blocked.

### Action Item 3: Add cost-benefit context to renter financial details (MEDIUM PRIORITY)

**Current**: Only relocation costs are listed ($5K-$10K / $15K-$25K)

**Proposed addition** (after the relocation cost lines):
```
- Cumulative Flood Damage: ${cumulative_damage:,.0f}
- Average Annual Flood Loss (if flooded): ${avg_annual_loss:,.0f}
- NOTE: If your cumulative damage already exceeds relocation costs, moving may save money over time.
```

**Rationale** (Dr. Chen): The LLM needs both cost and benefit information to perform meaningful cost-benefit reasoning. Currently, cumulative damage is listed in the FLOOD HISTORY section (line 16) but is not co-located with relocation costs, making cross-referencing difficult for a 4B model with limited reasoning depth.

### Action Item 4: Consider adding intermediate renter options (LOW PRIORITY, FUTURE WORK)

**Options to consider for future iterations:**
- `flood_proof_contents`: Low-cost contents protection ($200-$500)
- `request_landlord_mitigation`: Zero-cost lease negotiation action
- `local_relocation`: Reduced-cost move within basin ($2K-$5K, less disruption)

**Rationale** (Dr. Rivera): These fill the adaptation gap between insurance and full relocation. However, adding options requires validation data and may increase model complexity. Recommended for a future model iteration, not the current experiment.

### Action Item 5: Run ablation test after prompt revision (HIGH PRIORITY)

**Design**: Run identical 13-year simulation with revised prompt language (Action Item 1) and revised validator (Action Item 2). Compare:
- Renter relocation rate (target: 3-8% cumulative over 13 years for high-flood-count agents)
- Insurance uptake patterns (should remain similar)
- Timing of relocation decisions (should cluster in years following severe floods)
- Do_nothing rate (should decrease slightly, primarily for high-flood-count agents)

**Success criteria**: Relocation rate increases to empirically plausible range without triggering unrealistic early relocation (Year 1-2 relocations should remain rare).

---

## Summary Table

| Issue | Severity | Root Cause | Fix |
|-------|----------|------------|-----|
| 0.35% relocation rate | Critical | Prompt imperative + validator double suppression | Revise prompt (AI-1) + validator (AI-2) |
| No escalating adaptation | High | 3-option limitation + no cost-benefit framing | Add cost-benefit context (AI-3) |
| Insurance decay over time | Medium | "do_nothing is rational" default framing + habituation | Monitor; may resolve with relocation option unlocked |
| Missing renter adaptation options | Low | Model scope limitation | Future work (AI-4) |

---

## Dissent and Caveats

**Dr. Chen** notes that the proposed 3-flood threshold for relocation may still be too conservative. Empirical data from Hurricane Sandy recovery suggests that a single catastrophic flood (>$100K damage) is sufficient to trigger relocation for many renters. A damage-based threshold rather than a count-based threshold may be more empirically grounded.

**Dr. Rivera** cautions that adding relocation options without also modeling landlord behavior (rent increases, non-repair, eviction) will still undercount renter displacement. The model fundamentally captures only the demand side of renter relocation; the supply side (housing availability, landlord decisions) is equally important.

**Dr. Tanaka** emphasizes that any prompt revision must be tested specifically on Gemma 3 4B. Language that is appropriately suggestive for GPT-4 or Claude may still be overly directive for a 4B model. She recommends A/B testing the revised language with 50-agent pilot runs before committing to full 400-agent experiments.

---

*Panel discussion conducted 2026-03-14. Report prepared for Paper 3 calibration review.*
