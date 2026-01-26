# SDK-Broker Integration (Task-035) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate SDK v2 Memory Scoring and Reflection Templates into Broker with backward compatibility.

**Architecture:** Add optional SDK types via TYPE_CHECKING to avoid circular imports. Extend MemoryEngine with optional scorer and a v2 retrieval method. Extend ReflectionEngine with optional template/integrator and a v2 reflection method. Preserve legacy behavior as fallback.

**Tech Stack:** Python 3, broker components, governed_ai_sdk v1_prototype

---

### Task 1: Memory Scorer Integration (035-A)

**Files:**
- Modify: `broker/components/memory_engine.py`

**Step 1: Write the failing test**

Create a small unit test for `retrieve_with_scoring` using a stub scorer.

```python
# tests/test_memory_engine_scoring.py
from broker.components.memory_engine import MemoryEngine

class DummyEngine(MemoryEngine):
    def retrieve(self, agent, **kwargs):
        return ["m1", "m2"]

class DummyScore:
    def __init__(self, total):
        self.total = total

class DummyScorer:
    def score(self, memory, context, agent_state):
        return DummyScore(2 if memory == "m2" else 1)

class DummyAgent:
    def __init__(self):
        self.foo = "bar"


def test_retrieve_with_scoring_orders_by_total():
    engine = DummyEngine(scorer=DummyScorer())
    scored = engine.retrieve_with_scoring(DummyAgent(), {"ctx": 1})
    assert scored[0][0] == "m2"
    assert scored[0][1].total == 2
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_memory_engine_scoring.py -v`
Expected: FAIL (missing scorer support + method)

**Step 3: Write minimal implementation**

Implement TYPE_CHECKING import, scorer init, and `retrieve_with_scoring` in `broker/components/memory_engine.py`.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_memory_engine_scoring.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add broker/components/memory_engine.py tests/test_memory_engine_scoring.py
git commit -m "feat(broker): add memory scorer integration"
```

---

### Task 2: Reflection Template Integration (035-B)

**Files:**
- Modify: `broker/components/reflection_engine.py`

**Step 1: Write the failing test**

Create a small unit test for `reflect_v2` using a stub template and integrator.

```python
# tests/test_reflection_engine_v2.py
from broker.components.reflection_engine import ReflectionEngine

class DummyTemplate:
    def generate_prompt(self, agent_id, memories, context):
        return f"prompt:{agent_id}"
    def parse_response(self, response, memories, context):
        return {"insight": response}

class DummyIntegrator:
    def __init__(self):
        self.calls = []
    def process_reflection(self, agent_id, response, memories, context):
        self.calls.append((agent_id, response))

class DummyEngine(ReflectionEngine):
    def _call_llm(self, prompt):
        return f"response:{prompt}"


def test_reflect_v2_uses_template_and_integrator():
    integrator = DummyIntegrator()
    engine = DummyEngine(template=DummyTemplate(), integrator=integrator)
    insight = engine.reflect_v2("a1", ["m"], {"c": 1})
    assert insight == {"insight": "response:prompt:a1"}
    assert integrator.calls == [("a1", "response:prompt:a1")]
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_reflection_engine_v2.py -v`
Expected: FAIL (missing reflect_v2 + init changes)

**Step 3: Write minimal implementation**

Implement TYPE_CHECKING import, optional template/integrator, and `reflect_v2` in `broker/components/reflection_engine.py`.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_reflection_engine_v2.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add broker/components/reflection_engine.py tests/test_reflection_engine_v2.py
git commit -m "feat(broker): add reflection template integration"
```

---

Plan complete and saved to `docs/plans/2026-01-26-task-035-sdk-broker.md`.

Two execution options:

1. Subagent-Driven (this session)
2. Parallel Session (separate)

Which approach?
