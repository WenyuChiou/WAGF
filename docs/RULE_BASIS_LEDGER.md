Tracked copy of the working ledger; every threshold in the framework's shipped rules needs a literature source (L) or a stated assumption (A).
Updated 2026-09-07.

# Rule and threshold basis ledger (irrigation + flood single-agent), 2026-09-06

Rule agreed with the user 2026-09-06: every threshold or rule in the paper must have
either (L) a literature source or (A) a stated reasonable assumption. A number derived
from our own corpus (a quantile) is neither and is not allowed. This file is the working
record; nothing here is manuscript prose.

## Irrigation (published v21 strict profile + environment)

| Rule / number | Value | Basis type | Basis | Where in code |
|---|---|---|---|---|
| Shortage tiers | Mead 1,075 / 1,050 / 1,025 ft | L | Bureau of Reclamation 2007 Interim Guidelines (Record of Decision); 2019 Drought Contingency Plan (verify citations before use) | `irrigation_env.py:62-64`, `_compute_shortage_tier` |
| Curtailment per tier | 5 / 10 / 20 % | A | uniform-percentage simplification of the volumetric state-by-state cuts in the Guidelines/DCP; state as a simplification | `irrigation_env.py:1001` |
| `water_right_cap` | per-agent water right | L | Colorado River Compact (1922) allocation + CRSS water rights (Hung & Yang 2021 WRR) | `agent_types.yaml` strict identity rule; skill-registry precondition |
| `demand_ceiling_stabilizer` | 6.0 MAF | A anchored on L | 1.024 × CRSS basin demand target 5.86 MAF (Hung & Yang 2021); the 2.4 % headroom is an assumption | `irrigation_validators.py:682, 736-788` |
| `demand_floor_stabilizer` | 50 % of water right | A | economic-viability floor | `irrigation_validators.py:681` |
| `minimum_utilisation_floor` | 10 % of water right | A | hard economic floor | `agent_types.yaml` strict identity rule |
| Compact aggregate warning | basin share | L | 1922 Compact | `irrigation_validators.py:286-317` |
| `low_threat_no_increase` | WSA = VL | L (theory) | mirrors the FQL decider's WSA×ACA logic (Hung & Yang 2021); appraisal–action consistency | `agent_types.yaml:347-353` |
| `high_threat_high_cope_no_increase` | WSA, ACA ∈ {H, VH} | L (theory) | same | `agent_types.yaml:355-365` |
| `high_threat_no_maintain` | WSA = VH, WARNING | L (theory) | same; WARNING has no channel to the model unless advise_mode is on | `agent_types.yaml:336-343` |
| `drought_index` composite | 0.5 × precip deficit + 0.5 × Mead depletion | A | model-defined index; weights are an assumption | `irrigation_env.py:951-960` |
| grounded_v1 threshold | 0.08 | **none** | 3-seed corpus p85 → NOT allowed; arm dropped | PR-6 profile |
| Optional variant `grounded_tier1eq` | 0.227 | A derived from L | drought_index evaluated at 1,075 ft (Tier-1 elevation) under baseline precipitation | `config_variants/grounded_tier1eq` (unscheduled) |

## Flood single-agent (published strict profile)

| Rule / number | Value | Basis type | Basis | Where |
|---|---|---|---|---|
| `extreme_threat_block` | TP ∈ {H, VH} → no do_nothing | L (theory) | Protection Motivation Theory: high threat appraisal should not end in inaction | `examples/single_agent/agent_types.yaml:342-348` |
| `relocation_threat_low`, `elevation_threat_low` | TP ∈ {VL, L} → no relocate / elevate | L (theory) | PMT: costly protection without threat is inconsistent | `:358-372` |
| `low_coping_block` | CP ∈ {VL, L}, WARNING | L (theory) | PMT coping appraisal | `:349-357` |
| `elevation_block` | already elevated → no elevate | A (physical) | state precondition | `:373-379` |
| grounded_v1 `observed_flood_low_threat_inaction` | flood_event is true AND TP low AND do_nothing | A (observed event) | conditions on the simulated flood event, a boolean world fact; no threshold | PR-6 profile |
| Fallback default `do_nothing` | — | A | status-quo default; makes rejection behaviourally inert in flood (disclose) | `agent_types.yaml:102` |

## Advise arm

| Setting | Value | Basis type | Basis |
|---|---|---|---|
| `governance.advise_mode: feedback` | WARNING-level rules delivered as advice; ERROR rules unchanged | A (design) | soft channel holds blocking constant by construction; the arm tests whether advice alone changes proposals |
