Tracked copy of the working ledger; every threshold in the framework's shipped rules needs a literature source (L) or a stated assumption (A).
Updated 2026-11-22 to describe the rules as they ran in the paper runs (earlier text described the v21 irrigation corpus).

# Rule and threshold basis ledger (irrigation + flood single-agent)

Rule agreed with the user 2026-09-06: every threshold or rule in the paper must have
either (L) a literature source or (A) a stated reasonable assumption. A number derived
from our own corpus (a quantile) is neither and is not allowed. This file is the working
record; nothing here is manuscript prose. Code is cited by file and symbol, not line number.

## Irrigation (the rules of the irrigation paper runs, `examples/irrigation_abm/config/agent_types.yaml`)

The thinking rules TR1 and TR3 run in the `strict` profile only. The identity rules are menu
filters in every profile. The supply rule runs in every profile except `disabled`.
Thinking rules read the water-scarcity appraisal (WSA) as first stated in the decision.
The v21 rules R1, R2 and R4, the demand ceiling and floor stabilizers, and the `grounded_v1`
and `grounded_tier1eq` variants are not part of the paper runs and are not listed.

| Rule / number | Value | Basis type | Basis | Where in code |
|---|---|---|---|---|
| Shortage tiers | Mead 1,075 / 1,050 / 1,025 ft | L | Bureau of Reclamation 2007 Interim Guidelines (Record of Decision); 2019 Drought Contingency Plan (verify citations before use) | `irrigation_env.py` (`WaterSystemConfig.mead_shortage_tier1` to `tier3`, `_compute_shortage_tier`) |
| Lower Basin shortage volumes | 333 / 417 / 500 kaf (Arizona share 320 / 400 / 480 kaf) | L | 2007 Interim Guidelines Record of Decision, Section 2.D.1; the Arizona priority-4 fraction is not independently verified | `irrigation_env.py` (`_tier_shortage_volume_maf`, `_AZ_LB_TIER_VOLUME_AF`, `_lb_junior_tier_fraction`) |
| TR1 `high_scarcity_no_increase` | WSA in {H, VH} blocks `increase_demand` (ERROR, strict only) | L (theory) + A | dual-appraisal theory: an increase on a shared supply when the user judges water scarce is a maladaptive response; mapping the theory onto this menu is our assumption | `examples/irrigation_abm/config/agent_types.yaml` (`governance.strict.thinking_rules`) |
| TR3 `low_scarcity_no_decrease` | WSA in {VL, L} blocks `decrease_demand` (ERROR, strict only) | L (theory) + A | same, kept for symmetry with the flood over-reaction rules; support weak to moderate | same |
| TR2 (WSA and ACA both H or VH, keep) | not enforced in any profile | - | - | - |
| Supply rule `supply_gap_block_increase` | blocks `increase_demand` when the expected delivery of last year's request is below `FULL_SUPPLY_RATIO` of it | A | world-state rule; reads only water-system state; no other numeric threshold | `examples/irrigation_abm/validators/irrigation_validators.py` (`supply_gap_block_increase`, `supply_rule_fields`) |
| `water_right_cap` | no increase at or above 0.99 of the water right | L + A | Colorado River Compact (1922) allocation and CRSS water rights (Hung & Yang 2021); the 0.99 margin is an assumption | `examples/irrigation_abm/config/agent_types.yaml` (`identity_rules`), skill-registry precondition |
| `beneficial_use_limit` | no increase at about the most water the fields can use | L + A | beneficial use as the basis and limit of a water right (A.R.S. 45-141(B); Upper Colorado River Basin Compact 1948, Art. III(b)(2)); the per-agent limit comes from the model's data | `examples/irrigation_abm/config/agent_types.yaml`, `irrigation_env.py` (`at_beneficial_use_limit`) |
| `minimum_utilisation_floor` | no decrease at or below 1.01 × 10 % of the water right | A | the legal basis (forfeiture of unused rights after years of non-use) sets multi-year periods, not an annual fraction, so the 10 % is this model's assumption; the source model has no floor; sensitivities at 0 and 0.05 are recorded | `examples/irrigation_abm/config/agent_types.yaml`, `irrigation_env.py` (`WaterSystemConfig.min_utilisation_fraction`) |
| `drought_index` | legacy proxy | A | no prompt, rule or metric reads it in the paper runs; it still scales the legacy `total_available_water` term | `irrigation_env.py` (`_compute_drought_index`) |

## Flood single-agent (the `strict` profile of the paper runs, `examples/single_agent/agent_types.yaml`)

| Rule / number | Value | Basis type | Basis | Where |
|---|---|---|---|---|
| `extreme_threat_block` (R1) | TP ∈ {H, VH} and CP not in {VL, L} → no do_nothing (ERROR) | L (theory) | Protection Motivation Theory: high threat appraisal with coping not low should not end in inaction (non-protective response, Grothmann and Reusswig 2006); with low coping the rule does not fire, and the post-hoc measure reads it the same way (`test_pi_r1_requires_coping_not_low`) | `agent_types.yaml` (`governance.strict.thinking_rules`) |
| `relocation_threat_low` (R3), `elevation_threat_low` (R4) | TP ∈ {VL, L} → no relocate / elevate | L (theory) | PMT: costly protection without threat is inconsistent | same |
| `low_coping_block` | CP ∈ {VL, L}, WARNING | L (theory) | PMT coping appraisal | same |
| `elevation_block` (R5) | already elevated → no elevate | A (state precondition) | state precondition | `agent_types.yaml` (`governance.strict.identity_rules`) |
| grounded_v1 (not in paper runs) `observed_flood_low_threat_inaction` | flood_event is true AND TP low AND do_nothing | A (observed event) | conditions on the simulated flood event, a boolean world fact; no threshold | not part of the paper runs; see the `grounded_v1` profile |
| Fallback default `do_nothing` | — | A | status-quo default; makes rejection behaviourally inert in flood (disclose) | `agent_types.yaml` (fallback skill) |

## Advise arm

| Setting | Value | Basis type | Basis |
|---|---|---|---|
| `governance.advise_mode: feedback` | WARNING-level rules delivered as advice; ERROR rules unchanged | A (design) | soft channel holds blocking constant by construction; the arm tests whether advice alone changes proposals |
