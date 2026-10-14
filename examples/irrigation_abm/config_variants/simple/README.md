# Irrigation Config Surface

This directory contains the main configuration surface for the single-agent
irrigation reference implementation.

## Start Here

Read these files in order:

1. [skill_registry.yaml](skill_registry.yaml)
2. [agent_types.yaml](agent_types.yaml)
3. [prompts/irrigation_farmer.txt](prompts/irrigation_farmer.txt)

## What To Change First

If you are adapting this pack, the usual edit order is:

1. `skill_registry.yaml`
   Change the irrigation action space and skill metadata.
2. `agent_types.yaml`
   Change Cognitive Appraisal Theory constructs, parsing, governance, personas,
   and memory settings.
3. `prompts/irrigation_farmer.txt`
   Refine domain wording after the YAML surfaces are stable.

## Advanced Surfaces

Edit these after the primary surfaces are stable:

- [policies/financial_prudence.yaml](policies/financial_prudence.yaml): policy-side governance profile
- [../validators/irrigation_validators.py](../validators/irrigation_validators.py): Python-level domain validators
- [../run_experiment.py](../run_experiment.py): runner assembly and CLI behavior

## Scope Boundary

This config surface is for the single-agent irrigation reference only. It is
not shared with the flood benchmarks.
