# v20 Production Metrics Report

**Experiment**: 78 agents × 42 years, gemma3:4b, seed 42
**Total decisions**: 3276
**Finalized**: 2026-02-08T22:45:06

## 1. Governance Outcomes
| Category | Count | % |
|----------|-------|---|
| Approved (1st attempt) | 1236 | 37.7% |
| Retry Success | 735 | 22.4% |
| Rejected | 1305 | 39.8% |
| **Total Approved** | **1971** | **60.2%** |

## 2. Rule Frequencies (ERROR triggers)
| Rule | Triggers |
|------|----------|
| demand_ceiling_stabilizer | 1420 |
| high_threat_high_cope_no_increase | 1180 |
| curtailment_awareness | 499 |
| supply_gap_block_increase | 237 |
| demand_floor_stabilizer | 216 |
| low_threat_no_increase | 70 |

### Warning Rules
| curtailment_awareness | 335 |
| high_threat_no_maintain | 99 |
| non_negative_diversion | 12 |

## 3. Behavioral Diversity (H_norm)
| Version | H_norm | Interpretation |
|---------|--------|----------------|
| Proposed (LLM choice) | 0.7401 | What agents wanted to do |
| Approved only | 0.5464 | Among those that passed governance |
| Executed (with fallback) | 0.3884 | What actually happened |

### Skill Distribution
| Skill | Proposed | Approved | Executed |
|-------|----------|----------|----------|
| increase_large | 656 (20.0%) | 228 (11.6%) | 228 (7.0%) |
| increase_small | 1053 (32.1%) | 259 (13.1%) | 259 (7.9%) |
| maintain_demand | 1423 (43.4%) | 1423 (72.2%) | 2728 (83.3%) |
| decrease_small | 85 (2.6%) | 38 (1.9%) | 38 (1.2%) |
| decrease_large | 34 (1.0%) | 23 (1.2%) | 23 (0.7%) |

## 4. Demand Trajectory
| Metric | Value |
|--------|-------|
| mean_maf | 5.873 |
| stdev_maf | 0.54 |
| cov_pct | 9.2 |
| crss_mean_maf | 5.858 |
| ratio_to_crss | 1.0027 |
| within_10pct_count | 37 |
| within_10pct_pct | 88.1 |
| min_maf | 4.442 |
| max_maf | 6.404 |
| cold_start_mean_y1_5 | 4.755 |
| cold_start_cov_y1_5 | 11.4 |
| steady_state_mean_y6_42 | 6.024 |
| steady_state_cov_y6_42 | 5.3 |

## 5. Shortage Tier Distribution
| Tier | Years |
|------|-------|
| Tier 0 | 30 |
| Tier 1 | 5 |
| Tier 2 | 2 |
| Tier 3 | 5 |

Lake Mead range: 1003.1 - 1178.7 ft

## 6. Cluster Behavior
| Cluster | Agents | Proposed inc% | Proposed maint% | Executed inc% | Executed maint% |
|---------|--------|---------------|-----------------|---------------|-----------------|
| aggressive | 67 | 60.0% | 35.9% | 17.1% | 81.1% |
| forward_looking_conservative | 5 | 10.0% | 79.0% | 2.9% | 94.3% |
| myopic_conservative | 6 | 0.0% | 98.4% | 0.0% | 98.4% |

## 7. Construct Coverage
- WSA valid labels: 99.2%
- ACA valid labels: 99.2%

## 8. Ceiling × Tier Cross-Analysis
| Year | Tier | Ceiling Triggers |
|------|------|-----------------|
| Y12 | 0 | 67 |
| Y11 | 0 | 65 |
| Y13 | 0 | 63 |
| Y10 | 0 | 62 |
| Y18 | 1 | 61 |
| Y20 | 0 | 61 |
| Y38 | 2 | 60 |
| Y37 | 1 | 59 |
| Y14 | 0 | 57 |
| Y23 | 0 | 57 |
| Y22 | 0 | 56 |
| Y26 | 0 | 55 |
| Y21 | 0 | 54 |
| Y32 | 0 | 53 |
| Y17 | 0 | 52 |
