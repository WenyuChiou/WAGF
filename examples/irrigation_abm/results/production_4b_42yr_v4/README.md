# production_4b_42yr_v4 — Irrigation Production Run

Model: `gemma3:4b` | 78 CRSS agents | 42 years | Seed: 42
Governance: strict (irrigation domain) | Memory: HumanCentric

## Status: Complete

## Agent Distribution

| Cluster | Count | Basin Split |
|---------|-------|-------------|
| aggressive | 67 (86%) | 56 UB, 11 LB |
| forward_looking_conservative | 5 (6%) | 0 UB, 5 LB |
| myopic_conservative | 6 (8%) | 0 UB, 6 LB |

Total: 78 agents (56 Upper Basin + 22 Lower Basin)

## Decision Distribution (3276 agent-years)

| Action | Count | Share |
|--------|-------|-------|
| maintain_demand | 2458 | 75.0% |
| increase_demand | 551 | 16.8% |
| reduce_acreage | 232 | 7.1% |
| adopt_efficiency | 24 | 0.7% |
| decrease_demand | 11 | 0.3% |

## Governance Summary

- **Total interventions**: 252
- `high_threat_no_maintain`: 246 (VH threat + maintain blocked)
- `water_right_cap`: 6 (at allocation cap)
- Retry success: 15, Exhausted: 43
- Parse errors: 0

## Known Issues (led to v6 fix)

- **Economic hallucination (critical)**: FLC agents compound `reduce_acreage` (demand *= 0.75)
  to near-zero over ~30 years despite receiving "0% utilisation" in context. The LLM ignores
  quantitative signals due to persona anchoring ("cautious farmer") and memory reinforcement.
  Example: GilaMonsterFarms (17,400 AF water right) → 0 AF by Year 31.
  Fixed in v6 via MIN_UTIL=0.10 floor + P1 diminishing returns taper.
- **CRSS cancellation artifact**: Total SAGE/CRSS ratio appears reasonable (0.92-0.95x) but
  hides offsetting errors: UB is 1.72x CRSS (+72%) while LB is 0.35x CRSS (-65%).
- **Aggressive skew**: 86% of agents are aggressive (from FQL clustering), producing
  demand well above CRSS baseline for UB. Original FQL distribution is retained (not rebalanced)
  because it reflects the calibrated behavioral composition.

## CSV Columns

`agent_id, year, cluster, basin, yearly_decision, wta_label, wca_label, request, diversion, water_right, curtailment_ratio, drought_index, shortage_tier, has_efficient_system, memory`

## File Inventory

- `simulation_log.csv` — 3277 rows (78 agents x 42 years + header)
- `config_snapshot.yaml` — full configuration dump
- `governance_summary.json` — intervention counts by rule
- `irrigation_farmer_governance_audit.csv` — per-decision audit trail
- `audit_summary.json` — aggregated audit stats (3276 traces, 359 validation errors)
- `reproducibility_manifest.json` — SHA256 hashes
- `reflection_log.jsonl` — reflection engine outputs
- `raw/` — raw LLM response traces

## Reproduction

```bash
python examples/irrigation_abm/run_experiment.py \
  --model gemma3:4b --years 42 --real --seed 42
```
