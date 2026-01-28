# Memory Config System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a configuration system for governed_ai_sdk/memory with global and domain configs, and wire it into UnifiedCognitiveEngine and SymbolicSurpriseStrategy.

**Architecture:** Introduce dataclass-based config objects under governed_ai_sdk/memory/config/. UnifiedCognitiveEngine accepts config objects (global + domain) and passes config-derived sensors into SymbolicSurpriseStrategy. Keep backward compatibility by allowing existing args to default to config values.

**Tech Stack:** Python 3.10+, governed_ai_sdk, dataclasses, pytest.

---

### Task 1: Add failing tests for config wiring

**Files:**
- Create: `tests/test_memory_config.py`

**Step 1: Write failing tests**

```python
from governed_ai_sdk.memory import UnifiedCognitiveEngine
from governed_ai_sdk.memory.config import GlobalMemoryConfig, FloodDomainConfig
from governed_ai_sdk.memory.strategies.symbolic import SymbolicSurpriseStrategy


def test_unified_engine_accepts_config_objects():
    global_cfg = GlobalMemoryConfig(arousal_threshold=0.6)
    domain_cfg = FloodDomainConfig(stimulus_key="flood_depth")
    engine = UnifiedCognitiveEngine(global_config=global_cfg, domain_config=domain_cfg)
    assert engine.global_config.arousal_threshold == 0.6
    assert engine.domain_config.stimulus_key == "flood_depth"


def test_symbolic_strategy_uses_config_sensors():
    global_cfg = GlobalMemoryConfig(arousal_threshold=0.6)
    domain_cfg = FloodDomainConfig(stimulus_key="flood_depth")
    engine = UnifiedCognitiveEngine(global_config=global_cfg, domain_config=domain_cfg)
    strategy = engine.surprise_strategy
    assert isinstance(strategy, SymbolicSurpriseStrategy)
    assert strategy.sensors is not None
```

**Step 2: Run tests to verify failure**

Run: `pytest tests/test_memory_config.py -v`
Expected: FAIL (config module not found / UnifiedCognitiveEngine signature mismatch / sensors missing).

---

### Task 2: Implement config dataclasses

**Files:**
- Create: `governed_ai_sdk/memory/config/__init__.py`
- Create: `governed_ai_sdk/memory/config/defaults.py`
- Create: `governed_ai_sdk/memory/config/domain_config.py`

**Step 1: Implement GlobalMemoryConfig**

```python
# governed_ai_sdk/memory/config/defaults.py
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

@dataclass
class GlobalMemoryConfig:
    arousal_threshold: float = 0.5
    ema_alpha: float = 0.3
    window_size: int = 5
    top_k_significant: int = 2
    consolidation_prob: float = 0.7
    consolidation_threshold: float = 0.6
    decay_rate: float = 0.1
    retrieval_weights: Dict[str, float] = field(default_factory=lambda: {
        "recency": 0.3,
        "importance": 0.5,
        "context": 0.2,
    })
```

**Step 2: Implement DomainMemoryConfig**

```python
# governed_ai_sdk/memory/config/domain_config.py
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

@dataclass
class DomainMemoryConfig:
    stimulus_key: Optional[str] = None
    sensory_cortex: Optional[List[Dict[str, Any]]] = None


@dataclass
class FloodDomainConfig(DomainMemoryConfig):
    pass
```

**Step 3: Export config objects**

```python
# governed_ai_sdk/memory/config/__init__.py
from .defaults import GlobalMemoryConfig
from .domain_config import DomainMemoryConfig, FloodDomainConfig

__all__ = [
    "GlobalMemoryConfig",
    "DomainMemoryConfig",
    "FloodDomainConfig",
]
```

**Step 4: Commit**

```bash
git add governed_ai_sdk/memory/config
git commit -m "feat(memory): add config dataclasses"
```

---

### Task 3: Wire config into UnifiedCognitiveEngine

**Files:**
- Modify: `governed_ai_sdk/memory/unified_engine.py`

**Step 1: Update __init__ signature**

Add params: `global_config: Optional[GlobalMemoryConfig] = None`, `domain_config: Optional[DomainMemoryConfig] = None`.
Default missing configs to new instances.
Preserve existing args if passed; config values should be used when explicit args are not given.

**Step 2: Store config on instance**

```python
self.global_config = global_config or GlobalMemoryConfig()
self.domain_config = domain_config or DomainMemoryConfig()
```

**Step 3: Update surprise strategy wiring**

When selecting SymbolicSurpriseStrategy, pass `self.domain_config.sensory_cortex` into it.

**Step 4: Commit**

```bash
git add governed_ai_sdk/memory/unified_engine.py
git commit -m "feat(memory): accept config objects in unified engine"
```

---

### Task 4: Update SymbolicSurpriseStrategy to read sensors from config

**Files:**
- Modify: `governed_ai_sdk/memory/strategies/symbolic.py`

**Step 1: Accept sensors in constructor**

Ensure SymbolicSurpriseStrategy can receive `sensors` (list of dicts) and build Sensor objects from it.
If sensors not provided, fall back to existing behavior.

**Step 2: Commit**

```bash
git add governed_ai_sdk/memory/strategies/symbolic.py
git commit -m "feat(memory): configure symbolic sensors from config"
```

---

### Task 5: Update retrieval/exports if needed

**Files:**
- Modify: `governed_ai_sdk/memory/retrieval.py` (only if it needs config access)
- Modify: `governed_ai_sdk/memory/__init__.py` to export config symbols

**Step 1: Export config**

```python
from .config import GlobalMemoryConfig, DomainMemoryConfig, FloodDomainConfig
```

**Step 2: Commit**

```bash
git add governed_ai_sdk/memory/__init__.py governed_ai_sdk/memory/retrieval.py
git commit -m "feat(memory): export config types"
```

---

### Task 6: Verify

**Step 1: Run tests**

```bash
pytest tests/test_memory_config.py -v
```

Expected: PASS

**Step 2: Run user verification snippet**

```bash
python -c "
from governed_ai_sdk.memory import UnifiedCognitiveEngine
from governed_ai_sdk.memory.config import GlobalMemoryConfig, FloodDomainConfig

global_cfg = GlobalMemoryConfig(arousal_threshold=0.6)
domain_cfg = FloodDomainConfig(stimulus_key='flood_depth')
engine = UnifiedCognitiveEngine(global_config=global_cfg, domain_config=domain_cfg)
print('Config system works!')
"
```

Expected: `Config system works!`

**Step 3: Commit test if not already**

```bash
git add tests/test_memory_config.py
git commit -m "test(memory): add config wiring tests"
```

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-01-28-memory-config-system.md`.

Two execution options:

1. **Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks
2. **Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
