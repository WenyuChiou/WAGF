# Single-Agent Flood Config Surface

This directory contains the prompt surface for the single-agent flood reference
implementation. The main YAML config files for this pack live one level above
this directory.

## Start Here

Read these files in order:

1. [../skill_registry.yaml](../skill_registry.yaml)
2. [../agent_types.yaml](../agent_types.yaml)
3. [prompts/household.txt](prompts/household.txt)

## What To Change First

If you are adapting this pack to another single-agent domain, the usual edit
order is:

1. `../skill_registry.yaml`
   Use this to change the action space.
2. `../agent_types.yaml`
   Use this to change constructs, parsing, governance, and memory settings.
3. `prompts/household.txt`
   Use this to change the agent-facing wording after the YAML surfaces are
   stable.

## Advanced Surfaces

Edit these only after the three files above make sense:

- [../agent_types_stress.yaml](../agent_types_stress.yaml): stress-only variant
- [../run_flood.py](../run_flood.py): runner wiring and experiment assembly

## Input CSV Data Dictionary

### `../agent_initial_profiles.csv`

| Column | Type / Range | Unit / Meaning |
|---|---|---|
| `id` | string (`Agent_1` ...) | Unique household agent identifier |
| `elevated` | boolean (`TRUE` / `FALSE`) | Whether the house starts already elevated |
| `has_insurance` | boolean (`TRUE` / `FALSE`) | Whether the household holds flood insurance at Year 0 |
| `relocated` | boolean (`TRUE` / `FALSE`) | Whether the household starts already relocated |
| `trust_in_insurance` | float `[0, 1]` | Initial trust in the flood insurer |
| `trust_in_neighbors` | float `[0, 1]` | Initial trust in neighbors' judgment |
| `memory` | pipe-delimited string | Initial historical memory sentences (` \| ` separated) |
| `flood_threshold` | float `[0, 1]` (dimensionless probability) | Conditional damage probability given a basin flood (`damage_draw < flood_threshold` in `FinalParityHook.pre_year`; higher values cause more frequent damage, and house elevation scales it by `0.2` down to a `0.001` floor) |

### `../flood_years.csv`

| Column | Type / Range | Unit / Meaning |
|---|---|---|
| `Flood_Years` | integer `>= 1` | 1-based simulation year indices where basin flooding occurs when `--flood-mode fixed` (default) |

## Scope Boundary

This config surface is for the single-agent flood benchmark only. The
single-agent irrigation config lives separately under:

- [../../irrigation_abm/config/](../../irrigation_abm/config/)
