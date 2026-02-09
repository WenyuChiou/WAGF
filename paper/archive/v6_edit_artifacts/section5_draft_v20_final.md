# Section 5 Draft — Case Study 2: Colorado River Irrigation

> Style: WRR Technical Note, ~500 words, matching Section 4 density.
> Data source: production_v20_42yr traces (78 agents, 42 years, seed 42, gemma3:4b).
> Status: FINAL — all metrics from v20_metrics.json (finalized 2026-02-08).

---

## 5. Case Study 2: Colorado River Irrigation

### 5.1 Setup

[P1] To demonstrate domain transferability, we apply WAGF to irrigation demand management in the Colorado River Basin without modifying broker architecture. We instantiate 78 irrigation districts mapped one-to-one to CRSS diversion nodes (56 Upper Basin, 22 Lower Basin), simulated over 42 years (2019–2060) with CRSS PRISM precipitation projections (USBR, 2012). Three behavioral clusters derived from k-means analysis of calibrated FQL parameters (Hung and Yang, 2021) are mapped to LLM persona templates: Aggressive (large demand swings, low regret sensitivity), Forward-Looking Conservative (future-oriented, high regret sensitivity), and Myopic Conservative (status-quo biased, incremental adjustments). Agents select among five graduated skills (increase_large, increase_small, maintain_demand, decrease_small, decrease_large) through natural-language reasoning, while demand-change magnitude is independently sampled from cluster-parameterized Gaussian distributions at execution time—a hybrid agency design that separates qualitative strategic choice (LLM) from quantitative magnitude (code). Across flood and irrigation, the framework changes only in YAML-level artifacts: skill definitions, validator rules, appraisal constructs, and persona templates.

[P2] The irrigation domain introduces two extensions absent from the flood case. First, endogenous human–water coupling: agent demand decisions influence Lake Mead storage via an annual mass balance (SI Section S6), and the resulting elevation changes trigger USBR shortage tiers and curtailment ratios that constrain future decisions—creating a bidirectional feedback loop that the governance chain must mediate without hard-coded demand schedules. Second, a demand corridor bounds agent behavior between a per-agent floor (50% of water right; blocks over-conservation) and a basin-wide ceiling (6.0 MAF aggregate demand; blocks collective overshoot). This corridor is the institutional equivalent of the FQL reward function's regret penalty: in reinforcement learning, over-demand is penalized through negative reward and agents self-regulate; in WAGF, the same equilibrium boundary is encoded as governance rules, reflecting how real-world administrative mechanisms (compacts, allocation limits) constrain behavior rather than relying on individual experiential learning alone.

### 5.2 Results

[P3] Over the full 42-year production run (78 agents, 3,276 agent-year decisions), governance outcomes remain active throughout multi-decadal simulation: 37.7% of agent-year decisions are approved on first attempt, 22.4% succeed after retry-mediated correction, and 39.8% are ultimately rejected (with maintain_demand executed as fallback). Importantly, retry-mediated recovery indicates that governance interventions function as corrective mechanisms preserving agent execution continuity, not purely terminal filters. Intervention counts are reported as governance workload indicators; because one decision can induce multiple retry attempts, retry statistics are not interpreted as counts of unique violating agents.

[P4] Rule-frequency diagnostics reveal that intervention burden concentrates on hydrologically meaningful constraints. The most frequently triggered rule is `demand_ceiling_stabilizer` (n = 1,420), followed by `high_threat_high_cope_no_increase` (n = 1,180) and `curtailment_awareness` (n = 499), indicating that governance increasingly enforces feasibility boundaries under chronic shortage conditions. Cluster differentiation remains visible in governed outcomes and is qualitatively consistent with original FQL cluster behavior (Hung and Yang, 2021, Figure 7). Despite high rejection pressure, proposed-action diversity yields H_norm = 0.74 (normalized Shannon entropy over five skills); governance compression reduces executed diversity to H_norm = 0.39, reflecting institutional conservatism under chronic shortage. This entropy reduction quantifies how governance rules narrow the feasible action space while preserving the behavioral repertoire at the proposal stage.

[P5] The irrigation case validates the metric framework introduced in Section 3. Infeasible proposals (e.g., increasing demand at allocation cap, decreasing below minimum utilization) contribute to feasibility hallucination rate R_H. Coherence failures that remain technically feasible (e.g., high scarcity assessment with high adaptive capacity selecting increase) are tracked as rationality deviation R_R through thinking-rule ERROR traces, enabling cross-domain comparison of governance performance without conflating infeasibility and bounded-rational behavior (Figure 3).

---

## Notes for revision

1. **P3-P4 numbers** are FINAL from v20_metrics.json (42-year, 3,276 decisions, finalized 2026-02-08).
2. **Governance outcomes**: 37.7% approved first attempt, 22.4% retry success, 39.8% rejected (total 99.9%, rounding).
3. **Top 3 rules**: demand_ceiling_stabilizer (1,420), high_threat_high_cope_no_increase (1,180), curtailment_awareness (499).
4. **H_norm**: Proposed = 0.74 (behavioral richness), Executed = 0.39 (governance compression). Per Team 1 recommendation: report both as a compression ratio.
5. **P1** uses "five graduated skills" which is accurate (v17+ expansion).
6. **P2** "demand corridor as institutional equivalent of FQL reward" is the key conceptual claim. Supported by irrigation_validators.py comments at line 748-751.
7. **Demand trajectory (not in Section 5 text)**: 42-year mean = 5.873 MAF, CRSS ratio = 1.003, steady-state CoV (Y6-42) = 5.3%.
8. **Figure 3** referenced in P5: (a) Governance outcome proportions over years; (b) Top rule-trigger composition; (c) Aggregate demand vs CRSS baseline.
