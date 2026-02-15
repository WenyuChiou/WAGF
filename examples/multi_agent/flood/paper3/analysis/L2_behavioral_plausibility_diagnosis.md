# L2 Behavioral Plausibility Diagnosis: Passaic River Basin Flood ABM

**Analyst**: Dr. Maria Gonzalez, P.E., CFM
**Date**: 2026-02-15
**Scope**: 400-agent x 3-year pilot (per-agent-depth mode, PRB raster hazard)
**Failing benchmarks**: do_nothing_postflood = 0.334, mg_adaptation_gap = 0.045

---

## 1. Year 1 Flood Rate: 70% Is Plausible But Distorts Calibration

The 281/400 agents flooded in Year 1 appears high at first glance, but it is defensible given the simulation design. The PRB raster data maps real flood depths from historical events (2011-2023 FEMA flood maps) to individual grid cells. With 70% of MG agents and 50% of NMG agents assigned to flood-prone zones, and the `FLOOD_DEPTH_THRESHOLD_M = 0.15` (~6 inches), even minor inundation triggers the "flooded" flag. In the actual Passaic basin, Hurricane Irene (2011) and Tropical Storm Ida (2021) each affected 60-75% of structures in the Little Falls-Paterson-Wayne corridor. If Year 1 maps to a major event year in the raster, 70% is realistic.

**However, the calibration problem is severe.** When 70% of the population is flooded in Year 1, the `do_nothing_postflood` benchmark is evaluated against a massive denominator (281 traces), where most agents are experiencing their *first* flood. First-time flood victims exhibit high status quo bias -- Grothmann and Reusswig (2006) found 40-60% inaction rates after single events. But the model's governance architecture actively pushes these agents *away* from do_nothing: the PMT thinking rules block inaction for TP=VH + CP=VH/H agents, and the LLM (gemma3:4b) shows a strong action bias post-flood, proposing elevation even when structurally inappropriate. With only 29 genuine do_nothing choices among 392 flooded traces across all years, the model is clearly under-producing inaction.

**Recommendation**: The status quo bias pathway is underweighted. The `owner_fatalism_allowed` rule (TP=H/VH + CP=VL/L) permits inaction, but 89.8% of agents assign CP=M, which falls outside this pathway. Two fixes: (a) widen the fatalism allowance to include CP=M for first-time flood victims (flood_count < 2), reflecting the "wait-and-see" behavior documented by Botzen et al. (2019); (b) add a `FIRST_FLOOD_INERTIA` rule that blocks complex actions (elevate, buyout) for agents with flood_count = 1, not just flood_count < 2 for elevation specifically.

---

## 2. INCOME_GATE: $40K Is Too Low for PRB

The current `INCOME_GATE` blocks elevation for income < $40,000 unless subsidy >= 90%. In the Passaic River Basin, the median household income is approximately $62,000 (ACS 2019-2023), but there is enormous variance: Little Falls median is $85K while Paterson is $32K. The $40K threshold means only the poorest MG agents are blocked -- anyone earning $41K can propose elevation even though a $40,000 out-of-pocket cost (after 50% subsidy on an $80K elevation) represents 98% of their annual income.

FEMA's own Benefit-Cost Analysis guidelines flag projects where the cost exceeds 50% of household income as financially infeasible without full grant coverage. Bubeck et al. (2012) and Botzen et al. (2019) both document that elevation adoption is concentrated in households where the cost-to-income ratio is below 0.30-0.40.

**Recommendation**: Replace the binary $40K gate with a **cost-burden ratio gate**: block elevation when `out_of_pocket_cost / income > 0.50`. At 50% subsidy with an $80K base cost, this blocks agents earning under $80K -- capturing the actual financial barrier. At 70% subsidy ($24K OOP), the threshold drops to $48K. This creates a dynamic interaction between government subsidy policy and household eligibility, which is the mechanistic pathway the model needs to produce a realistic mg_adaptation_gap.

---

## 3. ELEVATION_EXPERIENCE Gate: flood_count >= 2 Is Defensible But Needs Nuance

The requirement for flood_count >= 2 before elevation cites de Ruig et al. (2023), showing only 11.3% dry-floodproofing uptake after Sandy. This is a reasonable reference, but the picture is more nuanced. FEMA's Hazard Mitigation Grant Program (HMGP) data shows that post-disaster elevation applications spike dramatically after a *single* major event when three conditions align: (a) the event causes > $50K damage, (b) federal disaster declaration triggers HMGP funding, and (c) the household is in a repetitive loss area.

In the PRB specifically, the NJ Blue Acres program received 1,200+ applications after a single Hurricane Irene event. Many of these were for elevation, not just buyout. The 146 MG elevation proposals REJECTED by this gate represent legitimate intent that the real-world policy environment would accommodate after one catastrophic event.

**Recommendation**: Reduce the threshold to `flood_count >= 1` but add a **damage threshold**: elevation is only unblocked after flood_count >= 1 AND cumulative_damage > $25,000 (roughly the deductible + significant structural damage). This preserves the behavioral realism that minor flooding does not trigger major investment, while allowing severely impacted households to act after one event. For agents with flood_count >= 2, remove the damage threshold entirely -- repeated exposure is sufficient motivation regardless of severity.

---

## 4. Insurance Affordability: A Missing Validator

The model lacks any income gate for insurance. At $20K income, a $500-700/yr NFIP premium represents 2.5-3.5% of gross income. While NFIP has no income eligibility requirement (unlike Medicaid or housing assistance), empirical data shows clear income-uptake gradients. Kousky and Michel-Kerjan (2017) document that NFIP penetration in low-income census tracts is 40-60% lower than in high-income tracts *within the same flood zone*. Dixon et al. (2017, RAND) found that Risk Rating 2.0 premiums exceeding 1-2% of household income cause "affordability stress" and accelerate lapse.

The fact that MG renters (58%) have higher insurance than NMG renters (53%) is a red flag -- this inverts the empirical gradient. The LLM treats insurance as a costless "safe choice" because the prompt does not force the agent to evaluate premium-to-income ratios.

**Recommendation**: Add an `INSURANCE_AFFORDABILITY` soft gate: when `annual_premium / income > 0.02`, flag the decision as WARNING-level (not ERROR), appending to the prompt: "This premium represents X% of your annual income." This nudges the LLM toward realistic cost-benefit reasoning without hard-blocking insurance for low-income agents, reflecting the real-world pattern where some low-income households do purchase insurance but at lower rates.

---

## 5. Three-Year Horizon: Necessary But Insufficient

A 3-year pilot is adequate for diagnosing governance logic and validator calibration, but it cannot produce realistic behavioral differentiation for three reasons:

1. **Elevation construction lag**: Real-world elevation takes 6-18 months from approval to completion. In a 3-year sim, agents who become eligible in Year 2 cannot complete elevation until Year 3, leaving no time for the adaptation gap to manifest.
2. **Insurance lapse dynamics**: Gallagher (2014) showed NFIP lapse rates peak 2-4 years post-flood as memory decays. A 3-year window captures at most one lapse cycle.
3. **Subsidy feedback**: Government subsidy changes (5%/yr) need 4-6 years to create meaningful differences in elevation affordability between MG and NMG groups.

**Recommendation**: The 3-year pilot is appropriate for this diagnostic phase. The production run at 13 years (matching the PRB raster data span, 2011-2023) will provide adequate temporal depth. However, ensure the 13-year run includes at least 2 major flood years in the first 5 years to trigger the adaptation cascade early enough to observe differentiation.

---

## 6. Parameter Recommendations Summary

| Parameter | Current | Recommended | Rationale |
|-----------|---------|-------------|-----------|
| ELEVATION_EXPERIENCE | flood_count >= 2 | flood_count >= 1 AND damage > $25K | HMGP data: major single events trigger elevation |
| INCOME_GATE | income < $40K | OOP_cost / income > 0.50 | FEMA BCA guidelines; dynamic with subsidy |
| Fatalism pathway | TP=H/VH + CP=VL/L only | Add CP=M for flood_count < 2 | Botzen et al. (2019): first-flood inertia |
| Insurance affordability | None | WARNING when premium/income > 2% | Kousky & Michel-Kerjan (2017); Dixon et al. (2017) |
| CP distribution (MG) | alpha=4.07, beta=3.30 | alpha=3.5, beta=4.0 (shift mean from 0.55 to 0.47) | Reduce CP=M clustering; widen VL/L pathway |

**Expected impact on failing benchmarks:**
- **do_nothing_postflood**: The widened fatalism pathway + first-flood inertia rule should increase genuine do_nothing from 7.4% to approximately 35-45%, hitting the 0.35-0.65 range.
- **mg_adaptation_gap**: The cost-burden ratio gate creates a continuous income barrier that differentially affects MG agents. Combined with the insurance affordability nudge reducing MG insurance uptake, the gap should widen from 0.045 to approximately 0.10-0.20.

---

## 7. Caveats

These recommendations are calibration adjustments, not structural model changes. They should be validated through a second 3-year pilot before the 13-year production run. The cost-burden ratio gate in particular requires careful testing -- if the ratio threshold is too aggressive, it could overshoot the mg_adaptation_gap upper bound (0.30) and create implausibly large inequality. I recommend testing thresholds of 0.40, 0.50, and 0.60 in a 3-seed sensitivity sweep.

The CP distribution shift is the most uncertain recommendation. It addresses the 89.8% CP=M clustering, but altering the Beta distribution parameters affects all downstream PMT pathways. Monitor the CACR decomposition after this change to ensure L1 coherence is maintained.

---

*References: Botzen et al. (2019) JRU; Bubeck et al. (2012) RA; de Ruig et al. (2023) Nat. Hazards; Dixon et al. (2017) RAND; Gallagher (2014) AER; Grothmann & Reusswig (2006) JRU; Kousky & Michel-Kerjan (2017) JRU; Lindell & Perry (2012) IJMR.*
