# Migration Guide: Broker -> GovernedAI SDK

This guide maps broker components to the SDK equivalents.

## Component Mapping

| Broker | SDK |
|--------|-----|
| `validators/agent_validator.py` | `v1_prototype/core/engine.py` (PolicyEngine) |
| `broker/utils/agent_config.py` | `v1_prototype/core/policy_loader.py` (PolicyLoader) |
| `broker/components/universal_memory.py` | `v1_prototype/memory/symbolic.py` (SymbolicMemory) |
| `broker/components/xai_counterfactual.py` | `v1_prototype/xai/counterfactual.py` |
| `broker/components/governance_calibrator.py` | `v1_prototype/core/calibrator.py` (EntropyCalibrator) |

## Step-by-Step

1. **Start with Types**
   - Import `PolicyRule`, `GovernanceTrace` from `v1_prototype.types`.
2. **Policy Evaluation**
   - Replace rule evaluation with `PolicyEngine.verify()`.
3. **Policy Loading**
   - Use `PolicyLoader.from_dict()` or `.from_yaml()` to load policies.
4. **Memory Layer**
   - Use `SymbolicMemory.observe()` to detect novel states.
5. **XAI**
   - Use `CounterfactualEngine.explain()` for actionable explanations.
6. **Calibration**
   - Use `EntropyCalibrator.calculate_friction()` to measure governance impact.

## Notes

- The SDK is stateless by default; you can wrap it into your existing orchestration.
- All outputs are dataclasses to simplify logging and auditing.
