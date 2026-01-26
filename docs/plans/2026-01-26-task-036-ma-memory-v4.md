# Multi-Agent Memory V4 Upgrade (Task-036) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate multi-agent example memory from V2b (humancentric/CognitiveMemory) to SDK V4 SymbolicMemory with FloodMemoryScorer integration.

**Architecture:** Update YAML config to use symbolic memory sensors + scorer. Add SymbolicMemory initialization path in household agent. Wire FloodMemoryScorer into multi-agent entrypoint using create_memory_engine with scorer. Keep legacy behavior when config doesn¡¦t request symbolic.

**Tech Stack:** Python 3, broker components, governed_ai_sdk v1_prototype

---

### Task 1: Update Memory Config (036-A)

**Files:**
- Modify: `examples/multi_agent/ma_agent_types.yaml`

**Step 1: Write the failing test**

Create a config-focused test to ensure symbolic memory fields are parsed.

```python
# examples/multi_agent/tests/test_memory_v4_config.py
import yaml
from pathlib import Path


def test_symbolic_memory_config_exists():
    config_path = Path("examples/multi_agent/ma_agent_types.yaml")
    data = yaml.safe_load(config_path.read_text())
    memory_config = data.get("memory_config", {})
    household = memory_config.get("household_owner", {})
    assert household.get("engine") == "symbolic"
    assert household.get("sensors")
    assert household.get("scorer") == "flood"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest examples/multi_agent/tests/test_memory_v4_config.py -v`
Expected: FAIL (engine still humancentric / missing scorer)

**Step 3: Write minimal implementation**

Update `examples/multi_agent/ma_agent_types.yaml` memory_config to use `engine: symbolic`, add sensors, arousal_threshold, and scorer.

**Step 4: Run test to verify it passes**

Run: `python -m pytest examples/multi_agent/tests/test_memory_v4_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add examples/multi_agent/ma_agent_types.yaml examples/multi_agent/tests/test_memory_v4_config.py
git commit -m "feat(ma): set symbolic memory config"
```

---

### Task 2: Household SymbolicMemory Init (036-B)

**Files:**
- Modify: `examples/multi_agent/ma_agents/household.py`

**Step 1: Write the failing test**

```python
# examples/multi_agent/tests/test_household_memory_v4.py
from examples.multi_agent.ma_agents.household import HouseholdAgent


def test_household_init_memory_v4_symbolic():
    agent = HouseholdAgent(agent_id="h1", config={})
    config = {
        "engine": "symbolic",
        "sensors": [
            {"path": "flood_depth_m", "name": "FLOOD", "bins": [{"label": "SAFE", "max": 0.3}]}
        ],
        "arousal_threshold": 0.5,
    }
    memory = agent._init_memory_v4(config)
    assert memory is not None
    assert memory.__class__.__name__ == "SymbolicMemory"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest examples/multi_agent/tests/test_household_memory_v4.py -v`
Expected: FAIL (no _init_memory_v4 or SymbolicMemory)

**Step 3: Write minimal implementation**

Implement `_init_memory_v4` in `household.py` and add TYPE_CHECKING import.

**Step 4: Run test to verify it passes**

Run: `python -m pytest examples/multi_agent/tests/test_household_memory_v4.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add examples/multi_agent/ma_agents/household.py examples/multi_agent/tests/test_household_memory_v4.py
git commit -m "feat(ma): init symbolic memory in household"
```

---

### Task 3: FloodMemoryScorer Integration (036-C)

**Files:**
- Modify: `examples/multi_agent/run_ma_flood.py`

**Step 1: Write the failing test**

```python
# examples/multi_agent/tests/test_flood_memory_scorer.py
from examples.multi_agent.run_ma_flood import build_memory_engine


def test_build_memory_engine_with_flood_scorer():
    engine = build_memory_engine({"scorer": "flood", "arousal_threshold": 0.5})
    assert engine.scorer is not None
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest examples/multi_agent/tests/test_flood_memory_scorer.py -v`
Expected: FAIL (build_memory_engine missing / scorer not wired)

**Step 3: Write minimal implementation**

Add helper `build_memory_engine` in `run_ma_flood.py` that uses `get_memory_scorer("flood")` and `create_memory_engine` with scorer and arousal threshold.

**Step 4: Run test to verify it passes**

Run: `python -m pytest examples/multi_agent/tests/test_flood_memory_scorer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add examples/multi_agent/run_ma_flood.py examples/multi_agent/tests/test_flood_memory_scorer.py
git commit -m "feat(ma): wire flood memory scorer"
```

---

Plan complete and saved to `docs/plans/2026-01-26-task-036-ma-memory-v4.md`.

Two execution options:

1. Subagent-Driven (this session)
2. Parallel Session (separate)

Which approach?
