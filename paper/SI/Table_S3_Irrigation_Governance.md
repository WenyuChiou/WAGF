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

**Caption**: Summary statistics from the 42-year production run (seed 42, gemma3:4b). Governance outcomes, rule frequencies, and behavioral diversity metrics computed from irrigation_farmer_governance_audit.csv.
