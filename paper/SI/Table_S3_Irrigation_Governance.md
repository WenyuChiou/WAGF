### Table S3: Irrigation ABM Governance Summary (v20 Production)

| Category | Metric | Value |
|----------|--------|-------|
| Experiment | Agents | 78 (56 UB, 22 LB) |
| | Years | 42 (2019-2060) |
| | LLM | gemma3:4b |
| | Total decisions | 3,276 |
| Governance Outcomes | Approved (1st attempt) | 37.7% |
| | Retry success | 22.4% |
| | Rejected | 39.8% |
| Rule Triggers (ERROR) | demand_ceiling_stabilizer | 1,420 |
| | high_threat_high_cope_no_increase | 1,180 |
| | curtailment_awareness | 499 |
| | supply_gap_block_increase | 237 |
| | demand_floor_stabilizer | 216 |
| | low_threat_no_increase | 70 |
| Behavioral Diversity | H_norm (proposed) | 0.7401 |
| | H_norm (approved) | 0.5464 |
| | H_norm (executed) | 0.3884 |
| Demand Trajectory | Mean demand | 5.873 MAF/yr |
| | CRSS ratio | 1.003x |
| | CoV (overall) | 9.2% |
| | CoV (Y6-42 steady-state) | 5.3% |
| | Within CRSS +/-10% | 88.1% (37/42 yr) |
| Shortage Tiers | Tier 0 (no shortage) | 30 years |
| | Tier 1 (5% cut) | 5 years |
| | Tier 2 (10% cut) | 2 years |
| | Tier 3 (20% cut) | 5 years |
| Cluster Behavior | Aggressive (67 agents) | 60% proposed increase -> 17% executed |
| | Forward-looking (5 agents) | 10% proposed increase -> 3% executed |
| | Myopic (6 agents) | 0% proposed increase -> 0% executed |

**Caption**: Summary statistics from the 42-year production run (seed 42, gemma3:4b). Governance outcomes, rule frequencies, and behavioral diversity metrics computed from irrigation_farmer_governance_audit.csv. Behavioral clusters follow Hung and Yang (2021, Table 2) k-means classification. CRSS nodes from USBR (2012). H_norm per Shannon (1948). Demand corridor as institutional allocation limits (Ostrom, 1990).

### Table S7: WAGF vs FQL Benchmark Comparison

| Metric | FQL (Hung & Yang, 2021) | WAGF v20 | Assessment |
| ------ | ----------------------- | -------- | ---------- |
| Agents / Period | 78 / 42 yr (2019-2060) | Same | Matched |
| Monte Carlo seeds | 100 | 1 (seed 42) | WAGF limited |
| Mean demand | Ensemble distribution around CRSS | 5.87 MAF (1.003x CRSS) | Within FQL range |
| Demand variability | Ensemble spread narrows after drought | CoV 5.3% (Y6-42) | Comparable stability |
| Shortage years | 13-30 yr (path-dependent) | 12 yr | Within FQL range |
| Cluster ordering | Aggressive > FL > Myopic (Q-value) | Same ordering (governance compression) | Preserved |
| Stabilization mechanism | Endogenous (reward-based Q-convergence) | Exogenous (governance corridor) | Structurally different |
| Cold-start transient | Q-value exploration noise | Memory initialization (Y1-5) | Analogous |
| Convergence guarantee | Yes (Q-learning theorem) | No (depends on rule design) | WAGF weaker |
| Explainability | Q-table values (opaque) | NL reasoning + InterventionReport | WAGF stronger |

**Caption**: Comparison of WAGF irrigation results against the FQL benchmark from Hung and Yang (2021). Both models use the same reduced-form CRSS mass balance, 78 real CRSS agents, and 42-year horizon (2019-2060). WAGF replaces FQL's reward-based self-regulation with explicit governance rules (12 validators + demand corridor). The comparison targets scientific plausibility (mean demand within CRSS ±10%, cluster ordering preserved), not statistical equivalence. FQL ensemble statistics are approximate ranges from Hung and Yang (2021, Figures 4-6).
