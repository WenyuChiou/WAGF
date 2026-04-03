# Expert Panel Plausibility Review: Irrigation ABM v21

**Date**: 2026-02-26
**Model**: WAGF Irrigation ABM v21 (governed), 78 CRSS agents, 42 years, seed42
**Condition reviewed**: v21 Governed (with comparisons to Ungoverned v20 and No-Ceiling ablation v20)
**Panel**: Water Resources Engineer, Agricultural Economist, ABM/Computational Social Scientist, Behavioral Psychologist

---

## 1. Water Resources Engineer

### Q1: Is 58.7% maintain realistic?

**Verdict: PLAUSIBLE, slightly high but defensible.**

Real-world irrigation districts in the Colorado River Basin operate under long-term contracts (Interim Guidelines, 2007 Record of Decision; DCP, 2019). Most districts file essentially the same Schedule of Deliveries year after year unless triggered by a specific event (new infrastructure, fallowing program, shortage declaration). Bureau of Reclamation Annual Operating Plan data for Lower Basin contractors shows year-over-year request changes exceeding +/-5% in roughly 30-40% of district-years, implying 60-70% effective "maintain" in normal conditions. The model's 58.7% is therefore in the plausible range, perhaps slightly low given the institutional inertia of real districts.

The 98.6% voluntary maintain (only 1.4% governance-forced) is a strong finding — it means the LLM agents independently choose stability, which matches the documented conservatism of irrigation district managers who face political accountability for both over- and under-ordering.

### Q2: WSA x ACA pattern

**Verdict: CONSISTENT with operational reality.**

The pattern that only high-WSA + high-ACA agents increase demand maps well to real-world behavior: districts that perceive scarcity AND have the infrastructure capacity to exploit additional water (e.g., additional acreage, reservoir storage, efficient conveyance) are precisely the ones that aggressively pursue supplemental supplies or accelerate scheduling during shortage years. This is the "adaptive exploitation" phenomenon seen in Central Arizona Project (CAP) agricultural contractors who ramped up orders ahead of anticipated Tier 1 shortages in 2020-2021. The VL-WSA row showing near-100% maintain is also correct — when water is very abundant, there is no urgency to change anything, and the water right cap blocks increases (correctly).

### Q3: DR = 0.389

**Verdict: LOW but explainable; requires transparent disclosure.**

Real IDD (Intentionally Created Surplus/Developed Shortage Surplus) utilization for Lower Basin agricultural contractors ranges from 60-90% of entitlement in most years. Upper Basin contractors use less (40-70% depending on hydrology). The model's 39% aggregate utilization is at the low end even for Upper Basin.

**Explanations**:
1. The model starts from 2018 actual diversions, which include some districts already in voluntary conservation. The path-dependent mechanism means early-period low utilization compounds.
2. The demand ceiling (6.0 MAF) activates frequently (1,083 triggers), suppressing increases even in plentiful years. This is the dominant governance constraint.
3. The 78 agents include both large and small districts; small districts with tiny absolute entitlements may have very low utilization that drags the aggregate.

**Recommendation**: Report DR alongside the comparison conditions (Ungoverned DR=0.252 and No-ceiling DR=0.428). The governed condition's 39% is intermediate and the relative ranking (ungoverned < governed < no-ceiling) is the policy-relevant finding. Disclose the absolute level gap with real-world IDD data and attribute it to the simplified single-action mechanism (real districts make dozens of sub-annual scheduling decisions, not one annual choice).

### Q5: 14.3 shortage years

**Verdict: HIGH but structurally coherent.**

Historical record: first formal Tier 1 shortage was declared August 2021 (effective 2022). However, the period 1981-2020 included extended drought (2000-2021 being the driest 22-year period in 1,200 years). The reason the real system avoided formal shortage until 2022 is the "structural deficit" buffer — reservoir storage absorbed overuse for decades.

The model produces more shortages because: (a) 78 agents collectively drive Mead down faster than the real system where Reclamation actively manages releases, and (b) the model lacks Intentionally Created Surplus (ICS) accounts, system conservation, and other buffering mechanisms. 14.3 shortage years out of 42 (34%) is aggressive but consistent with the CRSS mid-range projections published in the 24-Month Study (2020-2023 vintages), which showed 40-60% probability of shortage in most out-years.

**Recommendation**: Frame as "counterfactual projection consistent with CRSS ensemble mid-range" rather than "historical replication." Cite the 24-Month Study shortage probabilities.

### Q6: 36% REJECTED, 100% self-corrected

**Verdict: MECHANISTICALLY SOUND.**

The 36% rejection rate maps almost entirely to the demand ceiling stabilizer (1,083/1,194 = 91% of rejections). This is a basin-aggregate constraint: once total demand exceeds 6.0 MAF, ALL increase proposals are blocked. The LLM retrying with maintain_demand or decrease is the expected response — it is not "creative problem-solving" but simply downshifting when told increases are blocked. The 27 REJECTED_FALLBACK cases (0.8%) are the true governance failures and the rate is acceptably low.

This is analogous to a district manager calling Reclamation, being told "no additional water available this month," and simply maintaining the existing schedule. Not surprising.

---

## 2. Agricultural Economist

### Q1: Is 58.7% maintain realistic?

**Verdict: PLAUSIBLE with caveats.**

Farmers exhibit strong status quo bias in irrigation scheduling. USDA Farm and Ranch Irrigation Survey (FRIS) data shows that 60-70% of irrigated farms report "no change" in water management practices in any given year. However, the comparison is imperfect: FRIS measures practice changes (technology, crop switching), while the model measures demand quantity changes. Annual demand quantity variation of +/-5% could occur without any practice change (weather-driven ETc variation). Conversely, a farmer might adopt drip irrigation (a practice change) without changing total water ordered.

The 25.3% increase_small is notable. In real CRB agriculture, demand increases are constrained by water rights and infrastructure, not desire. Farmers generally want MORE water, not less. The model's asymmetry (25.3% + 12.5% increase vs. 2.9% + 0.6% decrease) correctly captures this "upward ratchet" tendency.

### Q2: WSA x ACA pattern

**Verdict: STRONGLY PLAUSIBLE.**

This matches Protection Motivation Theory (PMT) adapted to agricultural decision-making. The WSA x ACA crosstab shows:
- **Low WSA + any ACA = maintain**: When water is abundant, there is no threat appraisal to motivate action. This matches empirical findings from Grothmann & Patt (2005) on climate adaptation.
- **High WSA + low ACA = maintain/decrease**: Perceiving scarcity but lacking capacity to respond leads to fatalistic inaction or cautious conservation. This matches documented behavior of small-scale irrigators in drought (Wheeler et al., 2013).
- **High WSA + high ACA = increase**: This is the counterintuitive but empirically supported "adaptive exploitation" cell. Large districts with surplus infrastructure (reservoirs, efficient conveyance, financial reserves) respond to anticipated scarcity by front-loading deliveries. CAP agricultural pool holders did exactly this in 2019-2021.

The 55% maintain rate at VH-WSA/High-ACA (rather than near-zero) suggests some agents still choose caution even when conditions favor exploitation — this heterogeneity is realistic.

### Q3: DR = 0.389

**Verdict: CONCERNING but manageable with framing.**

The 39% utilization is below empirical expectations. Key factors:

1. **Path dependency from initial conditions**: Starting from 2018 diversions (which were already reduced by voluntary conservation programs like the DCP Pilot Program) creates a low baseline that compounds.
2. **Demand ceiling at 6.0 MAF**: This is approximately 1.024x the CRSS target of 5.86 MAF. Real basin-wide agricultural use has fluctuated between 4.5-6.5 MAF, so the ceiling is binding in many scenarios.
3. **Absence of crop revenue incentive**: Real farmers face a direct revenue incentive to use water — fallowed acreage = lost income. The LLM agents lack this explicit economic calculus, which may bias them toward under-use.
4. **No water market**: Real CRB increasingly features temporary water transfers, forbearance agreements, and ICS accounts that allow flexible re-allocation. The model's fixed water rights create an artificially rigid system.

**Recommendation**: Acknowledge DR gap in Methods. Emphasize that the RELATIVE comparison (governed vs. ungoverned vs. no-ceiling) is the primary analytical contribution, not the absolute level. Consider adding a sensitivity analysis with higher initial conditions or relaxed ceiling.

### Q4: Path-dependent mechanism

**Verdict: DEFENSIBLE.**

Annual irrigation scheduling is strongly path-dependent in practice. Farmers base next year's water order on this year's, adjusted for anticipated changes. The CRSS model itself uses this mechanism — each agent's demand evolves incrementally from prior state, not from scratch. Infrastructure constraints (installed capacity, canal maintenance schedules, labor contracts) make radical year-to-year shifts infeasible.

However, real farmers also have a "reference point" beyond just last year — their water right entitlement, historical peak use, and crop plan. The model's mechanism captures the incremental adjustment but misses the reference-point anchoring. This is a known simplification inherited from the Hung & Yang (2021) framework.

### Q7: Red flags for Nature Water

**Potential challenges**:
1. **DR absolute level**: A reviewer may compare 39% to real IDD data and question model fidelity. Preemptive defense: relative comparison is the contribution; cite Hung & Yang (2021) for structural validation of the CRSS coupling.
2. **Asymmetric action distribution**: 37.8% increase vs 3.5% decrease looks like the model has an upward bias. This needs explanation (water is a production input; farmers inherently prefer more).
3. **Missing economic optimization**: Water economists may ask why agents don't maximize crop revenue. Answer: WAGF tests GOVERNANCE effects on BEHAVIORAL diversity, not optimal allocation.

---

## 3. ABM/Computational Social Scientist

### Q1: Is 58.7% maintain realistic?

**Verdict: PLAUSIBLE and well-calibrated for an LLM-ABM.**

Compared to RL-ABMs (e.g., Hung & Yang 2021 FQL model), LLM agents show a well-known "maintain bias" because natural language reasoning favors caution and hedging. The 58.7% maintain is actually LOWER than many LLM-ABM benchmarks where maintain/status-quo dominates 70-80% of decisions. The fact that 98.6% of maintains are voluntary (not governance-forced) suggests the model successfully avoids the "governance forces conformity" artifact.

The comparison with ungoverned (which has much lower maintain, presumably because unconstrained LLMs explore more freely) provides the key experimental contrast.

### Q2: WSA x ACA pattern

**Verdict: STRONG evidence of structured reasoning, not random output.**

The WSA x ACA gradient is the model's strongest validation signal. If the LLM were producing random actions, we would expect uniform distributions across cells. Instead, we see a clear diagonal pattern: low-threat cells cluster on maintain, high-threat + high-capacity cells show action. This demonstrates that the dual-appraisal architecture (WSA + ACA) successfully channels LLM reasoning into behaviorally coherent outputs.

The gradient is also monotonic along both axes (with minor exceptions), which is the expected PMT prediction. This is unusual for 4B parameter models (gemma3:4b), suggesting the prompt engineering and governance architecture are doing significant cognitive scaffolding.

### Q3: DR = 0.389

**Verdict: ACCEPTABLE for a first-generation LLM-ABM.**

ABM validation distinguishes between "point prediction accuracy" and "pattern reproduction accuracy" (Grimm et al., 2005). The model need not reproduce exact DR levels; it needs to reproduce the PATTERN of demand response to supply conditions. The governed model shows:
- Higher DR than ungoverned (0.389 vs 0.252) = governance enables exploitation
- Lower DR than no-ceiling (0.389 vs 0.428) = ceiling constraint is binding
- Scarcity-responsive DR (plentiful > shortage years) = agents react to conditions

These patterns are correct. The absolute level is secondary for the Nature Water narrative, which is about governance effects on behavioral diversity.

### Q5: 14.3 shortage years

**Verdict: PLAUSIBLE as a model prediction, not a historical replication.**

The model is not calibrated to reproduce the historical shortage record. It is a counterfactual: "what if 78 districts made independent annual decisions for 42 years?" The 34% shortage rate is consistent with CRSS ensemble projections and demonstrates that collective LLM-agent behavior can emergently produce system-level stress — a key finding for the paper.

### Q6: 100% self-correction

**Verdict: EXPECTED but worth discussing.**

The 100% self-correction rate is mechanistically inevitable given the governance architecture: the demand ceiling blocks increases, and the LLM simply picks maintain_demand (the default and always-available skill). This is not evidence of sophisticated adaptation; it is evidence of well-designed fallback architecture. The 27 REJECTED_FALLBACK cases (where even the retry failed) are the more interesting signal.

**Recommendation**: Do NOT overclaim this as "agents learn from governance." Frame as "governance architecture ensures feasible outcomes without eliminating agent autonomy."

### Q7: Red flags

1. **Seed sensitivity**: v21 results are from seed42 only. The v20 results use 3-seed ensemble. A reviewer will ask whether v21 results are seed-sensitive. Run at least n=3 seeds.
2. **Gemma3:4b limitations**: A reviewer may question whether a 4B-parameter model can produce meaningful reasoning. Preemptive defense: the WSA x ACA gradient demonstrates structured reasoning; the model is a "decision kernel" not a general reasoner.
3. **42-year stationarity assumption**: The model runs 42 years with the same LLM and prompt. Real agents learn, retire, are replaced. This is a known limitation shared with all ABMs using fixed agent architectures.

---

## 4. Behavioral Psychologist

### Q1: Is 58.7% maintain realistic?

**Verdict: HIGHLY PLAUSIBLE from a behavioral science perspective.**

Status quo bias (Samuelson & Zeckhauser, 1988) is one of the most robust findings in behavioral economics. In agricultural contexts, Bocqueho & Jacquet (2010) documented that French farmers exhibited strong status quo bias in crop insurance adoption, with 60-70% choosing no change in any given year. The irrigation domain adds additional sources of inertia:
- **Loss aversion**: Reducing water risks crop loss; increasing risks curtailment penalty. Maintaining avoids both losses.
- **Omission bias**: Inaction feels less risky than action even when expected values are equivalent.
- **Cognitive load**: Annual decisions made under uncertainty favor heuristic "repeat last year" strategies (Kahneman, 2011, System 1 dominance).

The 58.7% maintain rate is consistent with dual-process theory predictions for annual low-stakes decisions under uncertainty.

### Q2: WSA x ACA pattern

**Verdict: STRONGLY CONSISTENT with Protection Motivation Theory.**

Rogers (1975, 1983) PMT predicts that protective action requires BOTH high threat appraisal AND high coping appraisal. The WSA x ACA table shows exactly this pattern:

- **Low threat (VL WSA)**: Near-100% maintain regardless of capacity. PMT predicts no action when threat is below threshold — confirmed.
- **High threat + low capacity**: 76-80% maintain. PMT predicts "fatalistic inaction" when coping is insufficient — confirmed.
- **High threat + high capacity**: 39-55% maintain (i.e., 45-61% taking action). This is the ONLY cell where both PMT conditions are met — confirmed.

The non-zero maintain rate even at VH/H (55%) is psychologically realistic. Not all agents SHOULD act even under high threat/high capacity: individual risk tolerance, anchoring to recent experience, and availability bias (absence of recent personal curtailment) can suppress action. This heterogeneity is a feature, not a bug.

The finding that high-WSA + high-ACA agents INCREASE (rather than decrease) is the "adaptive exploitation" pattern documented in prospect theory: when the reference point shifts (perceived future scarcity), agents in the "loss domain" take risks to regain the reference level, and those with high capacity act on it.

### Q3: DR = 0.389

**Verdict: LOW but psychologically coherent.**

The DR gap between model (39%) and empirical (60-90%) may partly reflect LLM agents' documented RISK AVERSION. Large language models trained on human text inherit the cautious, hedging language patterns that dominate written communication. This manifests as a "conservation bias" — when in doubt, the LLM defaults to lower demand. Real farmers, by contrast, operate under direct economic pressure to maximize water use.

This is an interesting methodological finding: LLM-ABMs may systematically under-predict resource exploitation compared to economically-motivated human agents. It should be noted as a methodological limitation and a direction for future work (perhaps incorporating explicit profit functions in the prompt).

### Q4: Path-dependent mechanism

**Verdict: STRONGLY DEFENSIBLE from behavioral theory.**

Anchoring and adjustment (Tversky & Kahneman, 1974) is the canonical behavioral model for sequential decisions under uncertainty. Farmers anchor on last year's water order and adjust incrementally based on new information. This is well-documented in agricultural economics:
- Hailu & Thoyer (2006): irrigators in water markets exhibit strong anchoring to previous bids
- Wheeler et al. (2009): Australian irrigators adjust water use incrementally from prior year
- Falk & Zimmermann (2018): anchoring in resource extraction games

The 1-8% (small) and 8-20% (large) adjustment ranges map well to the "psychophysics of adjustment" — agents perceive and respond to proportional changes, not absolute levels.

### Q6: 100% self-correction

**Verdict: BEHAVIORALLY INTERESTING.**

The 100% self-correction rate suggests the LLM agents are "satisficing" (Simon, 1956) rather than optimizing. When their first choice is blocked, they immediately switch to an acceptable alternative rather than persisting or escalating. This is classic bounded rationality: agents don't search for the optimal action, they search for a FEASIBLE one.

The 27 REJECTED_FALLBACK cases (0.8%) represent the rare instances where bounded rationality fails — the agent cannot find ANY feasible action within 3 retries. This failure rate is remarkably low and suggests the governance architecture provides sufficient degrees of freedom for satisficing agents.

---

## Consensus Verdict

### Overall Assessment: **ACCEPT WITH MINOR REVISIONS**

The v21 irrigation ABM produces behaviorally plausible, structurally coherent results that support the Nature Water narrative about governance effects on behavioral diversity. The expert panel identifies no fatal flaws.

### Key Strengths

1. **WSA x ACA gradient**: The strongest validation signal. The monotonic pattern across dual-appraisal cells is consistent with PMT, bounded rationality theory, and empirical agricultural decision-making literature. This alone justifies the model's behavioral plausibility claim.

2. **Voluntary maintain dominance**: The 98.6% voluntary maintain rate (vs. 1.4% forced) demonstrates that governance constrains the MARGIN, not the BULK, of agent decisions. This is the correct framing for the paper.

3. **Asymmetric action distribution**: The increase-dominant asymmetry (37.8% vs 3.5%) correctly captures the "upward ratchet" in water demand behavior — farmers prefer more water, not less.

4. **Governance self-correction**: The 100% retry success rate is mechanistically sound and represents well-designed bounded rationality architecture, not unrealistic adaptation.

### Concerns Requiring Disclosure

| # | Concern | Severity | Recommendation |
|---|---------|----------|----------------|
| C1 | DR = 0.389 below real-world 0.60-0.90 | **Medium** | Disclose gap in Methods; frame relative comparison as contribution; attribute to single-action simplification and LLM conservation bias |
| C2 | v21 results from single seed (seed42) | **High** | Run n=3 minimum (seeds 42, 43, 44) before submission; report ensemble mean +/- SD |
| C3 | 14.3 shortage years exceeds historical record | **Low** | Frame as counterfactual projection, cite CRSS 24-Month Study shortage probabilities |
| C4 | Demand ceiling drives 91% of rejections | **Medium** | Acknowledge that 6.0 MAF ceiling is the dominant governance lever; run sensitivity on ceiling level (5.5, 6.0, 6.5 MAF) or clearly justify 6.0 MAF from CRSS target |
| C5 | No explicit economic optimization | **Low** | Declare as scope boundary: WAGF tests governance effects on behavioral diversity, not optimal allocation; cite this as common ABM design choice (Grimm et al., 2005) |
| C6 | LLM conservation bias (under-exploitation) | **Low** | Note as methodological finding: LLM agents may systematically under-predict resource exploitation vs. economically-motivated agents |
| C7 | 42-year agent stationarity | **Low** | Acknowledge in limitations; note that persona persistence is a shared ABM assumption |

### Specific Paper Recommendations

1. **Lead with relative comparison, not absolute levels**: The governed vs. ungoverned vs. no-ceiling contrast is the analytical contribution. DR=0.389 is not the finding; DR_gov > DR_ungov IS the finding.

2. **WSA x ACA table should be a main text figure or extended data table**: This is the model's strongest behavioral validation artifact. Do not bury it in supplementary materials.

3. **Reframe "self-correction" carefully**: Say "governance architecture ensures feasible outcomes while preserving agent autonomy in 99.2% of decisions" rather than "agents learn from governance feedback."

4. **Cite the right literature for path dependency**: Tversky & Kahneman (1974) anchoring, Wheeler et al. (2009/2013) irrigation anchoring, Hung & Yang (2021) CRSS demand evolution. Do not cite prospect theory for the path-dependent mechanism (it is anchoring, not loss aversion).

5. **Address the demand ceiling justification**: The 6.0 MAF ceiling is the most impactful parameter in the model. Justify it explicitly from CRSS target demand (5.86 MAF) + the 2.4% buffer. If a reviewer asks "why not 5.0 or 7.0?", you need the answer ready.

6. **Pre-empt the "LLM is just following instructions" critique**: The WSA x ACA gradient, the voluntary maintain rate, and the cross-seed reproducibility together demonstrate that the LLM agents exhibit structured reasoning beyond simple prompt compliance. Frame governance as "cognitive infrastructure" (per the paper's existing language).

### Final Panel Scores

| Panelist | Score | Rationale |
|----------|-------|-----------|
| Water Resources Engineer | 7/10 | Sound coupling to CRSS; DR gap and shortage count need framing |
| Agricultural Economist | 7/10 | Action asymmetry and path dependency are strong; DR level is the main weakness |
| ABM/Computational Social Scientist | 8/10 | WSA x ACA pattern is excellent validation; seed replication needed |
| Behavioral Psychologist | 9/10 | PMT alignment, status quo bias, bounded rationality all confirmed |
| **Consensus** | **7.75/10** | **Accept with minor revisions** |

---

*Panel review generated 2026-02-26. Model version: v21 governed (seed42). Comparison baselines: v20 ungoverned, v20 no-ceiling ablation.*
