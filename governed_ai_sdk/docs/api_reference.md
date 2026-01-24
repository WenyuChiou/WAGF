# GovernedAI SDK API Reference

## Types

- **PolicyRule**: Rule definition for policy evaluation.
- **GovernanceTrace**: Result of policy verification.
- **CounterFactualResult**: XAI explanation output.
- **EntropyFriction**: Entropy-based governance metrics.

## Core

- **PolicyEngine**
  - `verify(action: dict, state: dict, policy: dict) -> GovernanceTrace`
- **PolicyLoader**
  - `from_dict(policy_dict: dict) -> dict`
  - `from_yaml(path: str | Path) -> dict`
  - `from_rules(rules: list[PolicyRule], policy_id: str) -> dict`
  - `load_policy(source: dict | str | Path) -> dict`
- **EntropyCalibrator**
  - `calculate_friction(raw_actions: list[str], governed_actions: list[str]) -> EntropyFriction`

## Memory

- **SymbolicMemory**
  - `observe(world_state: dict) -> tuple[str, float]`
  - `determine_system(surprise: float) -> str`

## XAI

- **CounterfactualEngine**
  - `explain(rule: PolicyRule, state: dict) -> CounterFactualResult`

## Wrapper

- **GovernedAgent**
  - `execute(context: dict) -> GovernanceTrace`
  - `get_state() -> dict`

- **CognitiveInterceptor**: Routing hook for agent decisions.
- **AuditConfig**: Audit logging configuration.
