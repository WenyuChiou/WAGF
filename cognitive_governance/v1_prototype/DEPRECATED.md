# v1_prototype - Legacy Code

> **Status**: DEPRECATED (preserved for historical reference)

This folder contains the original v1 prototype implementation of the Governed AI SDK.

## What This Was

The v1 prototype provided:
- `PolicyEngine` - Stateless rule verification
- `PolicyLoader` - YAML/JSON policy loading
- `SymbolicMemory` - O(1) state signature lookup
- `EntropyCalibrator` - Governance entropy detection

## Why It's Deprecated

The functionality has been superseded by:
- **broker/validators/** - Modern governance validation pipeline
- **broker/components/memory_engine.py** - Production memory engines
- **cognitive_governance/memory/** - v5 UnifiedCognitiveEngine

## Should I Use This?

**No.** Use the modern implementations instead:

```python
# Instead of v1_prototype PolicyEngine:
# from cognitive_governance.v1_prototype.core.engine import PolicyEngine

# Use broker validators (5-category governance pipeline):
from broker.validators.governance import (
    PhysicalValidator,
    ThinkingValidator,
    PersonalValidator,
    SocialValidator,
    SemanticGroundingValidator,
)

# Or modern memory engines:
from broker.components.memory_factory import create_memory_engine
engine = create_memory_engine(
    engine_type="humancentric",  # or: window, importance, universal, unified
    config={"window_size": 5}
)
```

## Why Is It Still Here?

- Historical reference for design decisions
- Some legacy tests may still reference it
- Gradual migration path

---

*Last updated: 2026-02-05*
