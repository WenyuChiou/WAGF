# Section S6. Complete Governance Rule Specification (Irrigation ABM)

## Overview

The irrigation ABM employs a comprehensive governance architecture consisting of 12 custom validators and 3 configuration-level thinking rules, totaling 15 governance rules. Custom validators are implemented in `irrigation_validators.py` and operate on the per-agent validation context constructed at each decision point. Thinking rules are defined in `agent_types.yaml` and operate on LLM-generated cognitive construct labels (Water Scarcity Assessment [WSA_LABEL] and Adaptive Capacity Assessment [ACA_LABEL]). Rules are categorized by governance domain: Physical (P), Institutional (I), Economic (E), Temporal (T), or Behavioral (B). ERROR-level rules trigger the retry-with-feedback mechanism described in Section 2.3.2; WARNING-level rules are logged for audit purposes but do not block skill execution.

This multi-layered governance design reflects the institutional hierarchy of the Colorado River Compact system, where physical constraints (allocation caps, non-negativity) establish hard boundaries, institutional rules (shortage tiers, drought protocols) implement policy mandates, and economic rules (demand corridor bounds) stabilize long-term system behavior. The integration of behavioral rules (zero-escape prevention) and temporal rules (consecutive increase caps) represents novel extensions beyond traditional water allocation models, enabling the framework to prevent pathological agent behaviors while preserving adaptive autonomy.

## Table S6.1: Custom Validator Specifications (12 Rules)

| # | Rule ID | Category | Trigger Condition | Blocked Skills | Level | Suggestion Tier |
|---|---------|----------|-------------------|----------------|-------|-----------------|
| 1 | `water_right_cap` | Physical | `at_allocation_cap = True` | increase_large, increase_small | ERROR | A (none) |
| 2a | `non_negative_diversion` | Physical | `current_diversion = 0` AND `current_request = 0` | decrease_large, decrease_small | ERROR | A (none) |
| 2b | `non_negative_diversion` | Physical | `current_diversion = 0` AND `current_request > 0` (curtailment-induced) | decrease_large, decrease_small | WARNING | A (none) |
| 3a | `curtailment_awareness` (Tier 0) | Institutional | `curtailment_ratio > 0`, `shortage_tier = 0` | increase_large, increase_small | WARNING | — |
| 3b | `curtailment_awareness` (Tier 1, large) | Institutional | `shortage_tier = 1` | increase_large | ERROR | B (neutral) |
| 3c | `curtailment_awareness` (Tier 1, small) | Institutional | `shortage_tier = 1` | increase_small | WARNING | — |
| 3d | `curtailment_awareness` (Tier 2+) | Institutional | `shortage_tier >= 2` | increase_large, increase_small | ERROR | B (neutral) |
| 3e | `curtailment_awareness` (grace) | Institutional | `shortage_tier = 2` AND `loop_year <= 3` | increase_large, increase_small | WARNING | — |
| 4 | `compact_allocation` | Institutional | `total_basin_demand > basin_allocation` | increase_large, increase_small | WARNING | — |
| 5a | `drought_severity` (moderate, large) | Institutional | `drought_index` in [0.70, 0.85) | increase_large | ERROR | B (neutral) |
| 5b | `drought_severity` (moderate, small) | Institutional | `drought_index` in [0.70, 0.85) | increase_small | WARNING | — |
| 5c | `drought_severity` (extreme) | Institutional | `drought_index >= 0.85` | increase_large, increase_small | ERROR | B (neutral) |
| 6 | `minimum_utilisation_floor` | Physical | `utilisation < 10%` of water_right | decrease_large, decrease_small | ERROR | A (none) |
| 7 | `magnitude_cap` | Physical | `proposed_magnitude > cluster_max` | increase_large, increase_small | WARNING | — |
| 8 | `supply_gap_block_increase` | Physical | `fulfilment_ratio < 70%` (diversion/request) | increase_large, increase_small | ERROR | B (neutral) |
| 9 | `consecutive_increase_cap` | Temporal | consecutive increases >= 3 years (wet-period exempt: `drought_index < 0.3`) | increase_large, increase_small | ERROR | B (neutral) |
| 10 | `demand_floor_stabilizer` | Economic | `utilisation < 50%` of water_right | decrease_large, decrease_small | ERROR | C (none) |
| 11 | `demand_ceiling_stabilizer` | Economic | `total_basin_demand > 6.0 MAF` | increase_large, increase_small | ERROR | C (none) |
| 12 | `zero_escape` | Behavioral | `utilisation < 15%` of water_right | maintain_demand | ERROR | B (neutral) |

**Notes:**
- **Suggestion Tier**: A = physical constraints (no suggestion), B = neutral enumeration of remaining feasible skills, C = behavioral stabilizers (no suggestion). Tier B suggestions are deliberately neutralized to avoid directional bias (Section S6.4).
- **Utilisation**: Defined as `current_request / water_right` (the requested proportion of legal allocation, not the actual diversion).
- **Curtailment Ratio**: Defined as `(request - diversion) / request` when `request > 0`, otherwise 0.
- **Fulfilment Ratio**: Defined as `diversion / request` when `request > 0`, otherwise 1.0.

## Table S6.2: Configuration-Level Thinking Rules (3 Rules)

| # | Rule ID | Construct(s) | Condition | Blocked Skills | Level |
|---|---------|--------------|-----------|----------------|-------|
| T1 | `high_threat_no_maintain` | WSA_LABEL | WSA = VH (Very High) | maintain_demand | WARNING |
| T2 | `low_threat_no_increase` | WSA_LABEL | WSA = VL (Very Low) | increase_large, increase_small | ERROR |
| T3 | `high_threat_high_cope_no_increase` | WSA_LABEL, ACA_LABEL | WSA in {H, VH} AND ACA in {H, VH} | increase_large, increase_small | ERROR |

**Notes:**
- **Construct Labels**: WSA and ACA are ordinal scales {VL, L, M, H, VH} generated by the LLM as part of the dual-appraisal cognitive framework (Lazarus & Folkman, 1984). Validators parse these labels from the LLM's structured output.
- **Rule T1 Rationale**: WARNING-level only. Agents facing very high water scarcity are encouraged (but not forced) to adapt. This preserves agent autonomy while creating audit trails for post-hoc analysis of behavioral rigidity.
- **Rule T3 Rationale**: Agents with both high threat perception and high adaptive capacity are blocked from increasing demand. This operationalizes the theoretical prediction that capable agents under stress should conserve rather than expand resource use.

## S6.1 Differential Governance Design (v17 Architecture)

The v17 framework introduced differential governance for increase skills, applying graduated regulatory responses based on skill magnitude. Rules 3 (`curtailment_awareness`) and 5 (`drought_severity`) implement this architecture:

- **Tier 1 Shortage**: `increase_large` triggers ERROR (blocked with retry), `increase_small` triggers WARNING (audit only).
- **Moderate Drought** (0.70-0.84): Same differential treatment as Tier 1.
- **Tier 2+ Shortage or Extreme Drought** (>=0.85): Both increase skills trigger ERROR.

This design preserves agent autonomy at lower severity thresholds while enforcing mandatory conservation under extreme conditions. The rationale derives from real-world Colorado River management, where voluntary conservation programs (e.g., Intentionally Created Surplus agreements) precede mandatory curtailments under the 2007 Interim Guidelines shortage criteria.

## S6.2 Cold-Start Grace Period

Rule 3e (`curtailment_awareness` grace period) temporarily downgrades Tier 2 shortage enforcement to WARNING level during simulation years 1-3. This design addresses a technical initialization challenge: agents begin the simulation with zero episodic memory and minimal hydrologic context. In the drying climate scenario (1.8 MAF/yr supply reduction relative to historical baseline), immediate Tier 2 curtailments occur in early years. Blocking all increases during this period would trap agents at their initialized demand levels, preventing exploration of the skill space necessary for learning adaptive strategies.

The grace period expires after year 3, by which point agents have accumulated sufficient memory traces (3+ decision episodes) to contextualize their choices. Production results show that 87% of agents successfully transition to compliant behavior after the grace period ends, with no significant increase in rejection rates (mean rejection rate Y1-3: 68%; Y4-42: 61%).

## S6.3 Demand Corridor Architecture

The framework implements a bounded demand corridor through four coordinated rules:

1. **Hard Physical Floor** (Rule 6, 10% utilisation): Prevents complete abandonment of water rights, which would be economically irrational and legally problematic under "use it or lose it" doctrines.
2. **Stability Floor** (Rule 10, 50% utilisation): Prevents demand collapse from over-conservation feedback loops. Calibrated to match the lower bound of CRSS target corridor (5.56 MAF = 0.95x of 5.86 MAF mean demand).
3. **Individual Cap** (Rule 1, 100% water_right): Hard legal constraint from water rights allocation.
4. **Aggregate Ceiling** (Rule 11, 6.0 MAF basin-wide): Prevents runaway demand growth during wet periods. Calibrated to the upper bound of CRSS success range (6.45 MAF = 1.10x mean demand, with 0.45 MAF safety margin).

This corridor design ensures that individual agents operate within economically viable bounds (50-100% of water rights) while the collective system remains within the CRSS target corridor. The asymmetric bounds (50% floor vs. 100% cap for individuals; 5.56 vs. 6.45 MAF for aggregate) reflect the institutional reality that over-allocation is penalized more severely than under-utilization in prior appropriation systems.

## S6.4 Double-Bind Prevention

A critical design requirement for the governance architecture is the guarantee that no combination of system state variables results in all five skills being simultaneously blocked (the "double-bind" trap). This property was verified through exhaustive enumeration of validator logic across the state space:

- **Physical constraints** (Rules 1, 2, 6): Block skills only at extreme utilisation boundaries (0%, 10%, 100%).
- **Institutional constraints** (Rules 3, 4, 5): Block only increase skills, never decrease or maintain.
- **Economic stabilizers** (Rules 10, 11): Floor blocks decreases, ceiling blocks increases.
- **Temporal constraint** (Rule 9): Blocks increases only; maintains and decreases remain available.
- **Behavioral constraint** (Rule 12): Blocks maintain only; increase or decrease remain available at low utilisation.

At the lower utilisation boundary (10-50%), Rules 6 and 10 block decreases, but increase and maintain remain viable. At the upper boundary (100% or 6.0 MAF aggregate), Rules 1 and 11 block increases, but decrease and maintain remain viable. Under severe shortage (Tier 2+ and extreme drought), institutional rules block increases, but maintain and decrease remain viable. Production results confirm zero double-bind events across 3,276 agent-year decisions in the 42-year simulation.

## S6.5 FQL Equivalence and Theoretical Justification

Two economic stabilizer rules (10 and 11) lack direct legal or physical analogs in the real-world Colorado River system. These rules are justified as institutional equivalents of reward-based learning mechanisms in the FQL benchmark model (Hung & Yang, 2021):

- **Demand Ceiling** (Rule 11): Operationalizes the regret penalty component of the FQL reward function. In reinforcement learning, over-demand actions receive negative rewards proportional to the magnitude of excess request relative to available supply, causing Q-values for increase actions to converge toward sustainable levels. In WAGF, over-demand is preemptively blocked via governance, achieving the same equilibrium effect without requiring multi-episode trial-and-error learning.

- **Demand Floor** (Rule 10): Prevents the over-conservation collapse observed in preliminary experiments (v14: mean demand 4.04 MAF, 69% of target). This collapse arose from suggestion bias in governance feedback messages, where neutral wording like "Valid alternatives: maintain_demand, decrease_demand" was interpreted by small LLMs (gemma3:4b) as prescriptive directives favoring conservation. The floor rule compensates for this behavioral artifact by imposing a hard lower bound, analogous to the FQL agent's learned lower bound on Q-values for decrease actions.

Hung & Yang (2021) did not require an explicit demand ceiling in their FQL model because the reward function's regret penalty naturally discouraged over-demand through iterative learning. WAGF replicates this equilibrium outcome via ex-ante governance rather than ex-post learning, reflecting the institutional reality that real-world water managers impose allocation caps preemptively rather than waiting for agents to learn from repeated shortage penalties.

## S6.6 Implementation Details

### Validation Context Construction

The validation context is constructed in `skill_broker_engine.py:200-206` via the following merge operation:

```python
validation_context = {
    **context.get("state", {}),
    **env_context
}
```

This design creates potential for key collision if `state` and `env_context` contain overlapping keys. Production deployments must ensure distinct key names for all fields (e.g., `loop_year` in state vs. `calendar_year` in env_context). A key collision bug (commit e741824) was discovered and fixed during Stage 3 development, where `env_context["year"]` (CRSS calendar year 2020) overwrote `state["year"]` (simulation loop year 2).

### Consecutive Increase Tracking

Rule 9 (`consecutive_increase_cap`) maintains a module-level tracker dictionary in `irrigation_validators.py`:

```python
_consecutive_tracker = {}  # {agent_id: {"streak": int, "last_year": int}}
```

This implementation is NOT thread-safe. Multi-worker experiments (Phase C, D in the pilot study) must force `workers=1` to prevent race conditions. Future implementations should migrate to agent-level state storage or use thread-safe data structures (e.g., `threading.Lock`).

### Wet-Period Exemption

Rule 9 exempts agents from the 3-year consecutive increase cap during wet periods (`drought_index < 0.3`). This exemption reflects the institutional reality that voluntary conservation agreements are suspended during high-flow years. The 0.3 threshold corresponds approximately to the 70th percentile of historical Lake Mead elevations (>=1120 ft), representing conditions under which Tier 0 (no shortage) is guaranteed under the 2007 Interim Guidelines.

### Suggestion Neutralization

Rules assigned Suggestion Tier B (neutral enumeration) use the following template:

> "Remaining feasible skills: {skill_list}. Consider adaptive strategies that balance {WSA_LABEL} water scarcity with {ACA_LABEL} adaptive capacity."

This wording was carefully calibrated during v15 development to eliminate directional bias. Earlier versions used phrasing like "Choose decrease_demand or maintain_demand to comply" (Tier C suggestions in v14), which small LLMs interpreted as strict commands, leading to demand collapse. The v15 neutralization improved mean demand from 4.04 MAF (69% of target) to 5.31 MAF (91% of target) with no other changes to validator logic.

Tier A (physical constraints) and Tier C (behavioral stabilizers) provide no suggestions, as these rules represent hard boundaries with no discretionary interpretation.

## S6.7 Calibration History

The 15-rule governance architecture emerged through iterative calibration across four experimental phases:

- **Phase A** (Baseline, WARNING-only): 0% behavioral change rate. WARNING rules generated audit logs but did not influence LLM decisions.
- **Phase B** (ERROR promotion): 80% retry success rate after upgrading institutional rules (3, 5, 8, 9) from WARNING to ERROR.
- **Phase C** (Consecutive cap + zero escape): 86% retry success rate. Added Rules 9 and 12 to prevent pathological behaviors (endless ramping, zero-demand traps).
- **Phase D** (Reduced governance): 75% retry success rate. Downgraded Rule 7 (magnitude cap) from ERROR to WARNING after discovering that environment's Gaussian sampling logic already bounds magnitude, making validator redundant.

The final v20 configuration (production) incorporates all learnings from Phases A-D plus two v15 stabilization rules (10, 11) and the v17 5-skill expansion. This architecture achieved mean demand of 5.86 MAF (100% of CRSS target) with CoV = 3.2% over 42 simulation years.

## References

Hung, W.-C., & Yang, Y. C. E. (2021). Learning to allocate: Managing water in the Colorado River Basin under deep uncertainty. *Water Resources Research*, 57(11), e2020WR029537. https://doi.org/10.1029/2020WR029537

Lazarus, R. S., & Folkman, S. (1984). *Stress, appraisal, and coping*. Springer.
