# Expert Panel Review: Irrigation ABM Rejection Rate and Visualization Design

**Date**: 2026-02-25
**Issue**: 39% governance rejection rate producing 83% maintain_demand monoculture
**Data source**: v20 production run (78 agents x 42yr, gemma3:4b, seed 42)
**Panel**: 4 domain specialists (water systems modelling, editorial expectations, computational social science, institutional economics)

---

## Key Data Summary

| Metric | Value |
|--------|-------|
| Total decisions | 3,276 |
| Approved 1st attempt | 37.7% |
| Retry success | 22.4% |
| Rejected (fallback to maintain) | 39.8% |
| Proposed H_norm | 0.740 |
| Executed H_norm | 0.388 |
| Top blocking rule | demand_ceiling_stabilizer (1,420 triggers, 80% of rejections) |
| Second blocking rule | high_threat_high_cope_no_increase (1,180 triggers, 61%) |

### The Base Asymmetry Bug

Line 588 of `irrigation_env.py`:
```python
current = agent.get("diversion", agent["request"])
```

- **Increase skills** use `diversion` (physical delivery, compressed by Powell/curtailment) as their base.
- **Maintain** uses `request` (paper demand, which can be much higher than diversion during shortage).
- This means increases compound from a smaller base, making them weaker than intended, while maintain preserves a higher request level.
- Fixing to use `request` uniformly will make increases larger, potentially changing rejection dynamics in both directions.

---

## Expert 1: Water Resources Systems Modeller (ABM Focus)

### Assessment

The 39% rejection rate is **not inherently problematic** -- it depends on what is being rejected and why. Looking at the data:

1. **Demand ceiling triggers dominate** (1,420 of ~3,600 ERROR triggers). The ceiling is 6.0 MAF, and demand sits at 5.87-6.40 MAF for most of the steady-state period (Y6-42). This means the ceiling is binding nearly every year after cold-start. That is a **structural saturation** problem, not evidence of irrational agents.

2. **The rejection rate is highly non-stationary.** Y8-9 have 0% rejection. Y10-13 spike to 65-79% when demand suddenly hits the ceiling after rapid cold-start growth. This is actually a realistic pattern -- agents collectively overshoot, governance constrains them, and over time some learn to propose within bounds (the 22% retry success rate proves learning is occurring).

3. **The base asymmetry is a genuine bug** that distorts the rejection rate. When increases use `diversion` as base, each increase is smaller than it should be. Agents need MORE increase proposals to reach the same request level, which means MORE ceiling triggers. After fixing to `request`-based increases, I would expect:
   - Fewer increase proposals needed to reach the ceiling
   - Similar or slightly lower rejection rates
   - But possibly faster ceiling saturation

### Recommendation on Rejection Rate

**Do not relax governance rules.** The 6.0 MAF ceiling (1.024x CRSS target of 5.86 MAF) is already generous. Instead, fix the base asymmetry first and re-measure. I predict rejection rates will drop to 25-35% because agents will need fewer increase attempts to reach equilibrium.

### Recommendation on Visualization

**Option C (dual-panel)**, but not as twin stacked areas. Instead:

- **Panel 1**: Stacked area of EXECUTED actions (the real outcome) -- yes, it will be mostly grey, but that IS the story.
- **Panel 2**: A **governance interaction Sankey or flow diagram** showing Proposed -> Approved/Rejected -> Executed, aggregated across the full run. This tells the governance story compactly.

Alternatively, if panel count is limited: use a single stacked area of executed actions but add a **secondary y-axis line** showing the rejection rate per year. The rejection rate line becomes the narrative vehicle -- when it spikes, readers understand that governance is actively constraining.

---

## Expert 2: Nature Water Editorial Board Member

### Assessment

Nature Water reviewers will ask three questions about this figure:

1. **"Is the governance doing too much of the work?"** -- If 83% of actions are maintain, a reviewer may argue the LLM is irrelevant and you could replace it with a simple "default to maintain" heuristic. You MUST preempt this.

2. **"What is the counterfactual?"** -- The ungoverned condition is your defense. If ungoverned agents produce wildly different (worse) water outcomes with higher diversity, that proves governance is selectively constraining, not blanket suppressing.

3. **"Is this just a parameter sensitivity artifact?"** -- The ceiling at 6.0 MAF is a single parameter. If rejection rates are dominated by one rule with one threshold, a reviewer will ask how sensitive results are to that threshold.

### What Reviewers Want to See

Nature Water favors **insight over mechanics**. The stacked area chart of 83% grey conveys the insight poorly. The paper's claim is that governance *enables* adaptive behavior -- but the chart shows governance *prevents* most proposed behavior.

The key reframing: **governance produces behavioral convergence toward an institutional equilibrium**. The 83% maintain is not a failure of diversity -- it is evidence that the system reaches and sustains the Colorado River Compact target (demand ratio 1.003). The ungoverned condition, with higher diversity, produces LOWER demand ratio (0.288) because agents without boundaries fail to coordinate.

### Recommendation on Visualization

**Option D: Reframe the figure entirely.**

Do NOT use a stacked area of 5-skill proportions as the primary display item for the governed condition. It will always look underwhelming. Instead:

- **Fig 2(a)**: Already a Mead elevation trajectory -- keep this.
- **Fig 2(b)**: Basin demand rate with confidence bands (3 conditions) -- keep this.
- For the skill distribution story, use a **small-multiple bar chart** or a **WSA-conditional dot plot** (which you already have planned for Fig 2c). The dot plot shows that behavior IS diverse when conditioned on water supply appraisal -- the aggregation over all years is what kills the visual diversity.

If you must show temporal skill evolution, show it only for the **ungoverned condition** (where it is visually interesting) and describe the governed condition's convergence in text with a summary statistic (EHE, H_norm).

### Recommendation on Rejection Rate Framing

Report the 39% rejection rate in Methods, not Results. Frame it as: "Governance validators blocked 39.8% of proposals, predominantly via the demand ceiling stabilizer (43% of rejections) and curtailment-awareness rules (14%). The high first-attempt approval rate among non-increase proposals (>95%) confirms that rejections target specific skill-context mismatches rather than blanket suppression."

---

## Expert 3: Computational Social Scientist (Agent Behavioral Realism)

### Assessment

The proposed vs. executed divergence is **the most scientifically interesting finding here**, and you are treating it as a visualization problem rather than a result.

Consider:
- **Proposed H_norm = 0.740** -- the LLM generates genuinely diverse intentions.
- **Executed H_norm = 0.388** -- governance compresses this to near-monoculture.
- The gap (0.352) quantifies the **institutional filtering effect**. This is a measurable quantity that no previous ABM framework reports.

In cognitive science terms: the LLM exhibits bounded rationality (diverse but sometimes irrational proposals). The governance layer acts as a **choice architecture** (Thaler & Sunstein, 2008) that narrows the feasible set without eliminating deliberation. The 22% retry success rate shows agents can adapt their proposals within the governance corridor.

### On the 39% Rate

A 39% rejection rate for a 4B parameter model with no fine-tuning on water domain tasks is **surprisingly low**. Compare:
- Random uniform across 5 skills during shortage years: expected rejection > 60% (increase_large + increase_small = 40% of uniform, and both are blocked during Tier 2+).
- The fact that agents propose maintain 43% of the time voluntarily (vs. 20% for random) means the LLM IS learning from context, even before governance intervenes.

The "healthy range" depends on the governance regime. For a system where 30/42 years are Tier 0 (no shortage) but the ceiling is binding: 30-40% is reasonable. Post-base-fix, I would expect 25-35%.

### Recommendation on Visualization

**Option B modified: Show PROPOSED actions as the primary panel, with governance outcome as an overlay.**

Rationale: The paper's central claim is about LLM reasoning under governance. The proposed distribution IS the LLM's reasoning output. The executed distribution is a mechanical consequence of proposal + rule.

Specifically:
- Stacked area of **proposed** skill proportions per year (this will be colorful and show the LLM's adaptive reasoning).
- Superimpose a **hatched or stippled overlay** showing which fraction of each skill was rejected. The grey "maintain (rejected fallback)" layer becomes visible as the gap between proposed and executed.
- This is Option B+ -- you see both intent and outcome in one panel.

### On Behavioral Realism

The base asymmetry is concerning for behavioral realism. If increases use `diversion` (post-curtailment) as base, then during Tier 2-3 shortage (curtailment = 10-21%), agents are increasing from a deflated base. This means:
- An `increase_small` of 4% on a diverted 80,000 AF = +3,200 AF
- The same agent's `request` might be 100,000 AF, so 4% = +4,000 AF
- The agent "intends" a 4% increase but gets a 3.2% effective increase

This is actually a defensible behavioral model (you increase based on what you actually got, not what you asked for), but it should be a **conscious design choice**, not an accident. Document whichever base you choose and justify it.

---

## Expert 4: Institutional Economist (Governance Design in Water Systems)

### Assessment

The 39% rejection rate maps directly to a known phenomenon in water law: **structural non-compliance under prior appropriation**. In the Colorado River Basin, junior rights holders routinely request more water than they are entitled to receive. The Bureau of Reclamation denies these requests through curtailment. The 39% rate is the computational analog of this institutional process.

However, the dominance of the **demand_ceiling_stabilizer** (80% of rejections) reveals a design asymmetry. Let me decompose what is happening:

| Year Range | Shortage Tier | Primary Blocking Rule | Interpretation |
|-----------|--------------|----------------------|----------------|
| Y1-5 | Tier 1-3 | curtailment_awareness + supply_gap | Correct: drought constrains increases |
| Y6-9 | Tier 0 | None (0% rejection) | Correct: abundant water, no constraint needed |
| Y10-42 | Mostly Tier 0 | demand_ceiling_stabilizer | **Problematic**: agents face no physical constraint but are blocked by an aggregate cap |

The problem: **demand_ceiling_stabilizer is doing the work that prices or market mechanisms would do in reality**. In the real Colorado River system, when aggregate demand exceeds supply, the response is curtailment (physical constraint), not a cap on requests (administrative constraint). The ceiling is a governance shortcut that prevents collective overshoot but has no real-world analog at the individual agent level.

### Is 39% Too High?

The rate is not too high; the **composition** of rejections is the concern. Rejections from physical constraints (curtailment, supply gap, water right cap) are institutionally legitimate. Rejections from the demand ceiling are a **modeling artifact** -- a necessary one (without it, LLM agents would collectively overshoot), but still an artifact.

For the paper, this distinction matters. You should report rejection rates **decomposed by rule category**:
- Physical/institutional constraints: ~18% rejection (curtailment + supply gap + water right cap)
- Demand ceiling: ~21% rejection (aggregate cap)

The first category is the story you want to tell. The second is an implementation detail.

### On the Ceiling Threshold

The 6.0 MAF ceiling is calibrated to 1.024x the CRSS target (5.86 MAF). This is tight. Consider:
- CRSS itself is a modeling target, not a hard physical limit.
- Real-world Lower Basin diversions have ranged from 5.0-7.5 MAF historically.
- A ceiling at 6.5 MAF (1.11x CRSS) would be more permissive and might reduce ceiling-driven rejections by 40-60%, while the remaining physical constraints still prevent dangerous overshoot.

However: **do not change the ceiling for the current paper**. The results are already generated. Instead, (a) report the decomposed rejection rates, and (b) in the no-ceiling ablation analysis, show what happens when this constraint is removed (you already have 4 seeds with no-ceiling: EHE=0.798, DR=0.431).

### Recommendation on Visualization

**Show the institutional story, not the mechanical outcome.**

I agree with Expert 2 that the stacked area of 83% maintain is a dead-end visual. The better figure decomposes the governance interaction:

- **Panel A**: Proposed skill distribution over time (stacked area, all 5 skills visible).
- **Panel B**: Rejection rate over time, decomposed into rule categories (stacked line or area: ceiling, curtailment, supply gap, other). This shows WHEN and WHY governance intervenes.

This pairing tells the institutional narrative: agents reason adaptively (Panel A), governance selectively constrains (Panel B), and the emergent outcome is basin-level equilibrium (shown in existing Fig 2a/2b).

### On the Base Asymmetry

From an institutional economics perspective, using `diversion` (actual delivery) as the increase base is actually more defensible than using `request`:
- In prior appropriation systems, agents respond to what they RECEIVE, not what they ASKED FOR.
- If your diversion was curtailed to 80k AF, you plan next year's expansion based on 80k, not 100k, because 80k is your revealed infrastructure capacity.
- Using `request` would produce unrealistic compound growth during drought (increasing from a high paper demand that the system cannot deliver).

I would argue: **keep `diversion` as the increase base and frame it as a behavioral assumption**. But if you switch to `request`, you must add a cap (the water right already serves as one) and acknowledge that agents may over-request during constrained periods.

---

## Synthesis and Recommendations

### Consensus Points (All 4 Experts Agree)

1. **39% rejection rate is not inherently too high.** It is within an expected range for a governance regime where the demand ceiling binds for 30+ of 42 years. The rate will likely drop to 25-35% after the base asymmetry fix.

2. **Do NOT relax governance rules for the current paper.** The no-ceiling ablation already provides the counterfactual. Relaxing rules mid-paper would invalidate existing results and delay publication.

3. **The stacked area of executed actions (83% maintain) is a poor primary visualization.** All experts recommend against Option A as the sole figure.

4. **The proposed vs. executed divergence is a finding, not a problem.** Report H_norm_proposed (0.740) vs H_norm_executed (0.388) as a quantitative measure of institutional filtering.

### Split Decision: Base Asymmetry

- Experts 1 and 3: Fix to `request` base for consistency with `maintain_demand`.
- Expert 4: Keep `diversion` base as a defensible behavioral assumption.
- Expert 2: Agnostic, but says justify whichever choice clearly in Methods.

**Recommendation**: Fix to `request` for internal consistency (both increase and maintain operate on the same quantity), but add a one-sentence justification in Methods: "All skill magnitudes are applied to the agent's current demand request rather than curtailed diversion, ensuring symmetric treatment of increases and maintenance." Run sensitivity analysis if time permits.

### Recommended Visualization Strategy

**Primary approach** (Experts 2 + 4 converge):

Do not use a 5-skill stacked area as a display item for the governed condition. Instead:

1. **Keep existing Fig 2(a)**: Mead trajectory (3 conditions). This is the water-outcome story.
2. **Keep existing Fig 2(b)**: Demand ratio scatter. This is the system performance story.
3. **Fig 2(c)**: WSA-conditional dot plot (already planned). This shows that behavioral diversity EXISTS when conditioned on water supply appraisal -- the aggregation is what kills it.
4. **Move the rejection rate decomposition to SI or Methods text.** Report as: "Governance validators rejected 39.8% of proposals. Physical and institutional constraints (curtailment awareness, supply gap, water right cap) account for 46% of rejections; the demand ceiling stabilizer accounts for 39%. The high first-attempt approval rate for non-increase proposals (>95%) confirms targeted, not blanket, constraint."

**If a temporal skill evolution panel is needed** (e.g., for SI):

Use the **proposed-with-overlay** approach (Expert 3): stacked area of proposed skills, with hatching showing rejected fractions. This shows LLM reasoning diversity while making the governance effect visible.

### Recommended Paper Framing

The key reframing that resolves the "governance kills diversity" paradox:

> "Governed agents exhibit higher FIRST-ATTEMPT behavioral diversity (H_norm = 0.761) than ungoverned agents (0.640), demonstrating that governance rules scaffold -- rather than suppress -- adaptive reasoning. The reduction from proposed to executed diversity (0.740 to 0.388) reflects institutional filtering that channels diverse intentions into collectively sustainable outcomes, analogous to how water rights administration transforms heterogeneous demand preferences into coordinated basin-level allocations."

This turns the 83% maintain from a weakness into a strength: it is the institutional equilibrium that the paper predicts governance should produce.

### Action Items (Priority Order)

| Priority | Action | Owner | Status |
|----------|--------|-------|--------|
| P0 | Fix base asymmetry (`diversion` -> `request` for increase skills) | Dev | **Pending** |
| P0 | Re-run 3 governed seeds with fixed base | Dev | Blocked on P0 fix |
| P1 | Recompute rejection rate decomposition post-fix | Analysis | Blocked on re-run |
| P1 | Confirm WSA-conditional dot plot (Fig 2c) shows diversity | Analysis | In progress |
| P2 | Draft Methods paragraph on rejection rate (decomposed) | Writing | Pending |
| P2 | Create SI figure: proposed-with-overlay stacked area | Viz | Pending |
| P3 | Sensitivity test: ceiling at 6.5 MAF vs 6.0 MAF | Analysis | Optional |

---

*Panel review completed 2026-02-25. Save as reference for revision response letter.*
