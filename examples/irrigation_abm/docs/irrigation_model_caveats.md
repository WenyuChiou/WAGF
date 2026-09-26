# Irrigation model caveats (2026-09-16 review)

The model is a stated simplification of Hung & Yang (2021) RL-ABM-CRSS, not a reproduction.

## Methods/SI Caveats

1. "Lake Powell and Lake Mead are two annual storage stocks in a closed-form surrogate water balance, not RiverWare/CRSS as in Hung & Yang (2021). Lake Powell releases the 7.0 MAF minimum (more only when it spills at full pool); the 2007 Interim Guidelines release tiers (equalization, balancing, 7.48 / 8.23 MAF) and Lake Mead protection levels are not modelled. Diversions are treated as fully consumptive (no return flow). With the release pinned at the minimum, Lake Mead reaches Tier 2 or 3 far more often than under the pre-redesign balance (24 vs 3 of 42 years at fixed 2018 requests; see docs/irrigation_physics.md, Two-Reservoir Simplification)." (Supply-side redesign, 2026-09-25; before it the balance tracked Lake Mead only, with a +/-3.5 MAF clamp on its annual storage change.)
2. "Shortage-tier curtailment, triggered by the 1 January Lake Mead elevation per the Colorado River Interim Guidelines (simplified), applies to Lower Basin users only, as one ratio to all Lower Basin consumptive use (agricultural agents and the 5.0 MAF non-agricultural bucket). Upper Basin agents are limited by the 5.0 MAF delivery capacity and, when Lake Powell cannot otherwise make its minimum release, by a pro-rata cut." (Before 2026-09-25 one flat tier ratio applied to all 78 agents. Consequence for governance counts: `curtailment_awareness_check` reads `curtailment_ratio`, which is now 0 for every Upper Basin agent, so the tier warning and the Tier 2+ increase block never fire for Upper Basin agents.)
3. "The demand-ceiling and demand-floor stability corridors (6.0 MAF / 50% of water right) are framework-added stabilization heuristics, not institutional rules from Hung & Yang (2021); the 6.0 MAF ceiling is checked against the previous year's aggregate demand, not a live intra-year total, and can be — and in the reported run routinely is — exceeded before the check engages the following year."
4. "The 70% fulfilment cutoff used by `supply_gap_block_increase` is an unvalidated modeling choice, not derived from CRSS or the Interim Guidelines."
5. "Calibrated FQL parameters (mu, sigma, alpha, regret) from Hung & Yang (2021) are used only to assign each of the 78 agents to one of three behavioral clusters via nearest-centroid classification; the magnitude of each agent's demand change is drawn from a separately-tuned per-skill Gaussian, not from the paper's calibrated parameters. Cluster centroids were not rebalanced to a target distribution for the reported run; the realized split (67 aggressive / 6 myopic-conservative / 5 forward-looking-conservative of 78) should not be assumed to match the paper's own cluster proportions."
6. "Within each Upper Basin state group, individual agents share identical calibrated behavioral parameters (only water rights and narrative persona text differ), reflecting the state-group resolution at which the source calibration was performed."
7. "Precipitation is generated as a single Upper-Basin-wide signal shared by all Upper Basin agents, rather than per-state-group signals as in the reference model."
8. "In the `strict` governance profile, drought-perception rules (WSA/ACA labels) constrain the LLM's own self-reported scarcity labels and are not cross-checked against the environment's computed drought index; only the `grounded_v1` profile performs that grounding."
9. "A cold-start grace period converts Tier-2 shortage blocks into warnings for simulation years 1-3, making governance strictness non-uniform across the study horizon within the `strict` profile."
10. "Per-agent logged diversion is the delivered water from the year's final settlement (after every decision), so the per-agent column sums to the basin deliveries used in the water balance." (Before the F11b and supply-side fixes, Upper Basin rows could carry the pre-Powell-clamp value.)

## Caveat to Code Location Mapping

Locations are given as file plus symbol name rather than line numbers, so they stay valid as the files evolve; run `grep -n <symbol> <file>` for the current line.

| Caveat | Code location (file, symbol) |
| :----- | :--------------------------- |
| 1. Two-storage surrogate balance, minimum-release Powell | `examples/irrigation_abm/irrigation_env.py` (`_settle`, `settle_year`, `advance_year`; constants in `WaterSystemConfig`) |
| 2. Lower-Basin-only tier cut on all Lower Basin use | `examples/irrigation_abm/irrigation_env.py` (`_apply_curtailment`, `_settle`) |
| 3. Demand ceiling/floor corridors; stale aggregate check | `examples/irrigation_abm/irrigation_env.py` (`advance_year`: the `total_basin_demand` aggregate), `examples/irrigation_abm/validators/irrigation_validators.py` (`DEMAND_FLOOR_RATIO`, `DEMAND_CEILING_AF`, `demand_ceiling_stabilizer`) |
| 4. 70% fulfilment cutoff | `examples/irrigation_abm/validators/irrigation_validators.py` (`supply_gap_block_increase`: the `fulfilment >= 0.70` branch) |
| 5. FQL cluster assignment; unrebalanced cluster split | `examples/irrigation_abm/irrigation_personas.py` (`_infer_cluster`, `rebalance_clusters`, `create_profiles_from_data`), `examples/irrigation_abm/run_experiment.py` (the `--rebalance-clusters` flag) |
| 6. Upper Basin state-group shared parameters | `examples/irrigation_abm/irrigation_personas.py` (`_UB_STATE_GROUPS`, `_UB_GROUP_AGENT_COUNTS`, `_build_ub_state_group_map`) |
| 7. Single Upper-Basin-wide precipitation signal | `examples/irrigation_abm/irrigation_env.py` (`_generate_precipitation`, called once per year from `advance_year`) |
| 8. Strict profile WSA/ACA labels ungrounded in drought index | `examples/irrigation_abm/config/agent_types.yaml` (`governance: strict` rules `high_threat_no_maintain`, `low_threat_no_increase`, `high_threat_high_cope_no_increase`, conditioned on `WSA_LABEL` / `ACA_LABEL`) |
| 9. Cold-start grace period (Y1-3 Tier-2 blocks to warnings) | `examples/irrigation_abm/validators/irrigation_validators.py` (`curtailment_awareness_check`: the `year <= 3 and shortage_tier == 2` branch; location verified against the code on 2026-09-16, the review text gives no reference for this item) |
| 10. Per-agent logged diversion = settled delivery | `examples/irrigation_abm/irrigation_env.py` (`settle_year` writes the per-agent diversion; `update_agent_request` writes a provisional value) |

None of these change the water balance; they are disclosure items for Methods/SI. Items 1, 2 and 10 were rewritten for the 2026-09-25 supply-side redesign; item 3 describes rules retired from dispatch in the same round (see `validators/irrigation_validators.py`).
