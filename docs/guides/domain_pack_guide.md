# Domain Pack Guide

This guide explains how to use WAGF as a reusable ABM governance core rather than as a flood-only framework.

## Mental Model

Treat the repository as three layers:

1. `broker/`
   The reusable governance core. It handles prompt formatting, parsing, validator orchestration, memory, context construction, retries, and audit.
2. `broker/domains/` plus experiment config
   Domain packs register theory metadata, custom validators, construct naming, and any domain-specific lifecycle logic.
3. `examples/`
   Complete reference experiments that show how to assemble the core and a domain pack into a runnable ABM.

## What Belongs in the Core

Keep code in `broker/` only if it is reusable across domains:

- skill proposal parsing
- governance retry loop
- validator routing
- context and memory interfaces
- audit writers
- provider abstraction

If a rule depends on flood insurance, basin hydrology, household elevation, or irrigation scarcity semantics, it should live in a domain pack instead.

## What Belongs in a Domain Pack

A domain pack owns:

- `skill_registry.yaml`
- `agent_types.yaml`
- theory metadata and construct labels
- custom validator checks
- lifecycle hooks
- optional domain-specific analysis helpers

The water-domain implementations in this repository are reference packs. They are mature examples, not mandatory dependencies for new ABM domains.

## Theory Packs

WAGF supports theory-driven governance by mapping behavioral constructs to governed actions.

For a new theory pack, define:

- construct names
- rating scale labels
- label normalization rules
- construct-action coherence rules

Examples:

- PMT: `TP_LABEL`, `CP_LABEL`
- dual-appraisal: `WSA_LABEL`, `ACA_LABEL`
- a generic non-water pack: `RISK_LABEL`, `CAPACITY_LABEL`

## Recommended Extension Path

When adding a new domain:

1. Copy `examples/minimal/` to a new experiment directory.
2. Define your constructs and actions in YAML.
3. Reuse generic validators first.
4. Add Python-level validators only for domain logic that cannot be expressed cleanly in YAML.
5. Keep experiment-specific analysis outside the core framework.

## Multi-Skill Boundary

The current multi-skill implementation should be treated as a bounded composite-action feature:

- primary action plus optional secondary action
- sequential execution
- backward compatible when disabled

It should not be described as a general-purpose planner unless stronger planning semantics and tests are added later.
