# Task-035: SDK-Broker Integration (Codex Assignment)

**Assigned To**: Codex
**Status**: READY FOR EXECUTION
**Priority**: High

---

## Objective

Integrate the new SDK v2 features (Memory Scoring, Reflection Templates) into the Broker framework.

---

## Subtasks for Codex

### 035-A: Memory Scorer Integration

**File**: `broker/components/memory_engine.py`

**Changes Required**:

1. Add import at top:
```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from governed_ai_sdk.v1_prototype.memory import MemoryScorer
```

2. Update `MemoryEngine` base class to accept optional scorer:
```python
class MemoryEngine(ABC):
    def __init__(self, scorer: Optional["MemoryScorer"] = None):
        self.scorer = scorer  # SDK domain scorer
```

3. Add new method `retrieve_with_scoring`:
```python
def retrieve_with_scoring(self, agent, context: dict, **kwargs):
    """v2 retrieval with domain-aware scoring."""
    memories = self.retrieve(agent, **kwargs)
    if self.scorer:
        scored = [
            (m, self.scorer.score(m, context, getattr(agent, '__dict__', {})))
            for m in memories
        ]
        scored.sort(key=lambda x: x[1].total, reverse=True)
        return scored
    return [(m, None) for m in memories]
```

### 035-B: Reflection Template Integration

**File**: `broker/components/reflection_engine.py`

**Changes Required**:

1. Add import at top:
```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from governed_ai_sdk.v1_prototype.reflection import ReflectionTemplate, ReflectionMemoryIntegrator
```

2. Update `ReflectionEngine.__init__` to accept SDK template:
```python
def __init__(
    self,
    llm_client=None,
    template: Optional["ReflectionTemplate"] = None,
    integrator: Optional["ReflectionMemoryIntegrator"] = None,
):
    self.llm_client = llm_client
    self.template = template  # SDK domain template
    self.integrator = integrator  # SDK feedback loop
```

3. Add new method `reflect_v2`:
```python
def reflect_v2(self, agent_id: str, memories: list, context: dict):
    """v2 reflection using SDK templates."""
    if self.template:
        prompt = self.template.generate_prompt(agent_id, memories, context)
        response = self._call_llm(prompt)
        insight = self.template.parse_response(response, memories, context)

        # Auto-promote to memory if configured
        if self.integrator:
            self.integrator.process_reflection(agent_id, response, memories, context)

        return insight
    return self.reflect(agent_id, memories, context)  # Fallback to legacy
```

---

## Verification

After making changes, run:

```bash
# Broker tests
pytest tests/ -v --tb=short

# SDK tests (should still pass)
pytest governed_ai_sdk/tests/ -v
```

---

## Files to Read First

Before editing, read these files to understand the current implementation:

1. `broker/components/memory_engine.py` - Current MemoryEngine base class
2. `broker/components/reflection_engine.py` - Current ReflectionEngine
3. `governed_ai_sdk/v1_prototype/memory/scoring.py` - SDK MemoryScorer
4. `governed_ai_sdk/v1_prototype/reflection/__init__.py` - SDK ReflectionTemplate

---

## Report Format

When done, add to `current-session.md`:

```
---
REPORT
agent: Codex
task_id: task-035-A/B
scope: broker/components
status: done
changes:
- broker/components/memory_engine.py (added scorer support)
- broker/components/reflection_engine.py (added template support)
tests: pytest tests/ -v (XX passed)
artifacts: none
issues: none
next: none
---
```

---

## Notes

- Keep backwards compatibility (existing code should work without SDK)
- Use TYPE_CHECKING to avoid circular imports
- Methods use `_v2` suffix to indicate new API
