# GovernedAI SDK

Universal Cognitive Governance Middleware for Agent Frameworks.

## Quick Start

```python
from governed_ai_sdk.v1_prototype.core.engine import PolicyEngine
from governed_ai_sdk.v1_prototype.core.policy_loader import PolicyLoader

# Create engine and policy
engine = PolicyEngine()
policy = PolicyLoader.from_dict({
    "rules": [
        {
            "id": "min_savings",
            "param": "savings",
            "operator": ">=",
            "value": 500,
            "message": "Need $500",
            "level": "ERROR",
        }
    ]
})

# Verify action
trace = engine.verify(
    action={"action": "buy_insurance"},
    state={"savings": 300},
    policy=policy,
)

if trace.valid:
    print("Action ALLOWED")
else:
    print(f"Action BLOCKED: {trace.rule_message}")
    print(f"To pass: {trace.state_delta}")
```

## Features

| Feature | Description |
|---------|-------------|
| **PolicyEngine** | Stateless rule verification |
| **XAI Counterfactual** | "What change would make this pass?" |
| **SymbolicMemory** | O(1) state signature lookup |
| **EntropyCalibrator** | Detect over/under-governance |

## Testing

```bash
python governed_ai_sdk/demo_sdk_usage.py
python -m pytest governed_ai_sdk/tests/ -v
```
