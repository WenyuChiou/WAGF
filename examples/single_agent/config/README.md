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

- [../stress_config.yaml](../stress_config.yaml): stress-test configuration
- [../agent_types_stress.yaml](../agent_types_stress.yaml): stress-only variant
- [../run_flood.py](../run_flood.py): runner wiring and experiment assembly

## Scope Boundary

This config surface is for the single-agent flood benchmark only. The
single-agent irrigation config lives separately under:

- [../../irrigation_abm/config/](/c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/irrigation_abm/config)
