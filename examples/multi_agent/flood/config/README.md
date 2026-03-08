# Multi-Agent Flood Config Surface

This directory contains the main configuration surface for the multi-agent
flood reference implementation.

## Start Here

Read these files in order:

1. [skill_registry.yaml](skill_registry.yaml)
2. [ma_agent_types.yaml](ma_agent_types.yaml)
3. [information_visibility.yaml](information_visibility.yaml)
4. [parameters/floodabm_params.yaml](parameters/floodabm_params.yaml)

Then read the prompt files under [prompts/](prompts/).

## What To Change First

If you are adapting this pack to another multi-agent ABM, the usual edit order
is:

1. `skill_registry.yaml`
   Define the shared action space.
2. `ma_agent_types.yaml`
   Define agent types, parsing behavior, governance, and memory settings.
3. `information_visibility.yaml`
   Control what each role can observe.
4. `prompts/*.txt`
   Refine role-specific wording after the YAML surfaces are stable.

## Advanced Surfaces

Edit these after the primary surfaces are stable:

- [governance/coherence_rules.yaml](governance/coherence_rules.yaml): additional governance rule surface
- [agents/agent_types.yaml](agents/agent_types.yaml): supporting agent-type definitions
- [globals.py](globals.py) and [schemas.py](schemas.py): config helpers
- [../run_unified_experiment.py](../run_unified_experiment.py): runner assembly and orchestration wiring

## Scope Boundary

This config surface belongs to the multi-agent flood implementation. It is not
the same as the single-agent flood or irrigation config surfaces.
