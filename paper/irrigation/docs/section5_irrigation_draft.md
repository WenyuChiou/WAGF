# Section 5: Case Study 2 — Colorado River Irrigation

**Target: ~650 words (~1.3 PU) | Data source: production_v20_42yr (5-skill, Phase C governance, seed 42)**

---

## 5.1 Setup

We demonstrate WAGF's domain transferability by applying it to irrigation demand management in the Colorado River Basin, following Hung and Yang (2021). We simulate 78 irrigation districts over a 42-year planning horizon (2019–2060) using CRSS precipitation projections (USBR, 2012). Districts are mapped one-to-one onto real Upper Basin and Lower Basin diversion nodes from the CRSS database: 56 Upper Basin agents across seven state groups (WY, UT, CO, NM, AZ) and 22 Lower Basin agents (e.g., Imperial Irrigation District, Yuma County WUA, Mohave Valley IDD).

Each district is assigned to one of three behavioral clusters calibrated from the Fuzzy Q-Learning (FQL) parameters in Hung and Yang (2021, Table 2) via k-means clustering: *Aggressive* (67 agents, persona scale 1.15), *Forward-Looking Conservative* (5 agents, scale 1.00), and *Myopic Conservative* (6 agents, scale 0.80). Agents choose among five skills per year — `increase_large`, `increase_small`, `maintain_demand`, `decrease_small`, and `decrease_large` — extending the original FQL two-action structure (increase/decrease) with granularity and a status-quo option. Demand-change magnitudes are sampled from skill-specific bounded Gaussian distributions scaled by persona, decoupling the qualitative decision (which skill) from the quantitative outcome (how much).

Unlike the flood domain, which employs PMT to model protective behavior against acute binary events, the irrigation domain frames demand decisions through a dual-appraisal framework grounded in cognitive appraisal theory (Lazarus & Folkman, 1984). Each agent independently assesses two dimensions: Water Scarcity Assessment (WSA, primary appraisal of threat severity) and Adaptive Capacity Assessment (ACA, secondary appraisal of coping ability), each rated on a 5-level ordinal scale (VL/L/M/H/VH). Governance rules condition on these constructs — for example, blocking demand increases when WSA and ACA are both high (the agent perceives severe scarcity but has the capacity to adapt, so increasing demand is inconsistent). The environment computes supply-side signals (drought index, shortage tier, curtailment ratio) through a simplified Lake Mead mass balance model (SI Section S6). Governance enforces physical constraints (water right cap, minimum utilisation floor), institutional constraints (curtailment awareness, compact allocation), and a demand corridor (50% floor preventing over-conservation, 6.0 MAF basin ceiling preventing collective overshoot). The experiment uses Gemma 3 4B with Phase C governance (12 validators) and human-centric memory (5-year window, importance-weighted episodic storage with annual reflection).

## 5.2 Results

Figure 3 presents aggregate demand trajectories and governance outcomes. WAGF-governed agents produce a mean demand of 5.87 MAF/yr (1.00x the CRSS static baseline of 5.86 MAF/yr) with a steady-state coefficient of variation of 5.3% (Y6-42), and 88% of simulation years fall within the ±10% CRSS reference corridor. The first five years exhibit a cold-start transient (mean 4.76 MAF) as agents initialize without memory; this mirrors the early exploration instability in FQL but resolves as episodic memory accumulates.

Governance produces 2,040 interventions across 3,276 agent-year decisions (62.3% intervention rate): 735 successful retries (22.4%) where agents self-corrected after receiving violation feedback, and 1,305 rejections (39.8%) where agents fell back to `maintain_demand`. The most frequently triggered rules are `demand_ceiling_stabilizer` (1,420 triggers, blocking increases when basin demand exceeds 6.0 MAF), `high_threat_high_cope_no_increase` (1,180, construct-conditioned), and `curtailment_awareness` (499, blocking increases during Tier 2+ shortage). This persistent intervention is a structural feature, not a deficiency — it demonstrates that bounded-rationality LLM agents in chronic drought require continuous governance constraint to maintain plausible demand trajectories.

Governance compresses behavioral diversity from H_norm = 0.74 (proposed) to 0.39 (executed), a 47% reduction quantifying institutional constraint strength. Aggressive agents face 43 percentage-point compression (proposing 60% increase actions, executing 17%), while Myopic agents face near-zero compression (98% maintain). This preserves the qualitative behavioral ordering from FQL k-means clusters through governance rules rather than individually calibrated penalty sensitivities. Shannon entropy shows no significant downward trend (slope = +0.003, p = 0.25), indicating agents maintain heterogeneous adaptive behavior rather than converging to a single strategy.

---

**Word count: ~630**

### Figure 3 Caption

**Figure 3.** Irrigation case study: 78 CRSS districts, 42 years, Gemma 3 4B, Phase C governance. (a) Annual aggregate water demand. Dashed indigo: CRSS static baseline (USBR, 2012). Solid teal: WAGF governed request. Dotted blue: actual diversion after curtailment. Shaded band: ±10% CRSS reference range. The cold-start transient (2019–2023) reflects zero-memory initialization; steady-state demand (2024–2060) tracks the CRSS baseline within the ±10% corridor (88% of years). (b) Governance intervention outcomes as proportion of 78 agent decisions per year. Persistent intervention (60% retry + rejected) reflects the structural governance load required to constrain bounded-rationality LLM agents under chronic drought. The demand ceiling rule (1,420 triggers) and construct-conditioned rules (1,180 triggers) account for 71% of all interventions.
