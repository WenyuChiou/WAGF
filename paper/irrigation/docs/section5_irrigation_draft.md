# Section 5: Case Study 2 — Colorado River Irrigation

**Target: ~600 words (~1.2 PU) | Data source: production_v16_42yr (3-skill, Phase C governance)**

---

## 5.1 Setup

We demonstrate WAGF's domain transferability by applying it to irrigation demand management in the Colorado River Basin, following Hung and Yang (2021). We simulate 78 irrigation districts over a 42-year planning horizon (2019–2060) using CRSS precipitation projections (USBR, 2012). Districts are mapped one-to-one onto real Upper Basin and Lower Basin diversion nodes from the CRSS database: 56 Upper Basin agents across seven state groups (WY, UT, CO, NM, AZ) and 22 Lower Basin agents (e.g., Imperial Irrigation District, Yuma County WUA, Mohave Valley IDD).

Each district is assigned to one of three behavioral clusters calibrated via Farmer Q-Learning by Hung and Yang (2021): *Aggressive* (bold demand swings, magnitude default 10%), *Forward-Looking Conservative* (cautious planning, 7.5%), and *Myopic Conservative* (status-quo bias, 4%). Agents choose among three skills per year — `increase_demand`, `decrease_demand`, and `maintain_demand` — matching the original FQL two-action structure (increase/decrease) with the natural extension of a status-quo option. Each demand-change skill carries a cluster-specific magnitude cap (20%/15%/8%), allowing quantitative heterogeneity within the governed action space.

Unlike the flood domain, which employs PMT to model protective behavior, the irrigation domain frames demand decisions through Prospect Theory (Kahneman & Tversky, 1979). Each agent evaluates its annual demand adjustment relative to a reference point — its established water right allocation — and perceives deviations as gains (surplus supply) or losses (supply deficit due to drought or curtailment). Loss aversion (λ > 1) predicts that agents resist demand cuts more strongly than they pursue equivalent increases, producing the asymmetric adjustment behavior documented in Western U.S. irrigation (Scheierling et al., 2006; Schoengold et al., 2006). The three FQL archetypes map to distinct loss aversion profiles: *Aggressive* agents exhibit low loss aversion (willing to swing demand in either direction), *Forward-Looking Conservative* agents exhibit standard loss aversion (cautious, anchored to historical demand), and *Myopic Conservative* agents exhibit strong status-quo bias (resisting any change). The environment computes supply-side signals (drought index, shortage tier, curtailment ratio) that position agents in the gain or loss domain; agents then reason over these signals through natural-language prompts rather than Q-value updates. Governance rules enforce physical constraints — agents cannot request water beyond their legal right (`water_right_cap`) or reduce demand below a 10% utilisation floor (`minimum_utilisation_floor`) — and institutional constraints derived from the Colorado River Compact (`compact_allocation`, `drought_severity`). A 50% demand floor prevents over-correction during drought. The experiment uses Gemma 3 4B with strict governance (11 validators, Phase C) and human-centric memory (5-year window, importance-weighted episodic storage).

## 5.2 Results

Figure 3 presents aggregate demand trajectories. WAGF-governed agents produce a mean demand of [MEAN] MAF/yr ([RATIO]x the CRSS static baseline of 5.86 MAF/yr) with a coefficient of variation of [CoV]% — the gap between "paper water" (requested) and "wet water" (delivered) that is a central tension in Colorado River management (Hadjimichael et al., 2020).

Governance produces [N_INT] interventions across [N_TOTAL] agent-year decisions ([INT_RATE]% intervention rate), with [N_RETRY] successful retries (agents self-corrected after receiving the violation message) and zero parsing failures. Early years show high rejection rates as agents explore the constraint boundary; governance stabilizes as agents learn viable action paths through memory-mediated feedback. The most frequently triggered rules are `curtailment_awareness` (blocking demand increases during Tier 2+ shortage) and `low_threat_no_increase` (preventing unjustified increases during low-scarcity periods).

Agents maintain heterogeneous adaptive behavior throughout the simulation, with cluster-specific strategic differentiation. Aggressive agents favor `increase_demand`; Forward-Looking Conservative agents favor `decrease_demand`; Myopic Conservative agents favor `maintain_demand`. This behavioral stratification mirrors the qualitative patterns documented in the FQL calibration (Hung & Yang, 2021, Figure 5), despite operating through natural-language reasoning rather than Q-value updates. Importantly, agents do not converge to a single strategy — Shannon entropy of the action distribution remains stable across the 42-year horizon, indicating sustained behavioral diversity rather than homogenization.

Governance catches a hallucination type absent in the flood domain: *economic hallucination*, where persona-anchored conservative agents repeatedly reduce demand until utilisation approaches zero — a physically possible but economically absurd trajectory. The `minimum_utilisation_floor` rule (10% hard floor) combined with a `demand_floor_stabilizer` (50% stability floor) prevents this spiral while allowing genuine conservation behavior.

---

**Word count: ~580**

### Figure 3 Caption

**Figure 3.** Irrigation case study: 78 CRSS districts, 42 years, Gemma 3 4B, Phase C governance. (a) Annual aggregate water demand. Dashed: CRSS static baseline (USBR, 2012). Solid teal: WAGF governed request. Dotted blue: actual diversion after curtailment. Shaded band: ±10% CRSS range. (b) Governance intervention outcomes. Agents learn constraint boundaries through governance feedback: early years show high rejection; governance stabilizes as agents internalize viable action paths.

