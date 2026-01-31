# Irrigation ABM Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add irrigation-specific integration tests and complete magnitude + regret feedback plumbing so the irrigation ABM uses governance-bounded magnitudes and records factual regret memory.

**Architecture:** Extend irrigation governance with a magnitude-cap BuiltinCheck, parse/apply `magnitude` in the irrigation experiment runner, and add a neutral regret feedback helper. Validate all pieces with a focused integration test suite that exercises memory, reflection triggers, parsing, governance, and a mocked full-loop run.

**Tech Stack:** Python, pytest, GBF broker components (memory_engine, reflection_engine), irrigation ABM runner.

---

### Task 1: Add magnitude cap validator + tests

**Files:**
- Modify: `broker/validators/governance/irrigation_validators.py`
- Modify: `tests/test_irrigation_env.py`

**Step 1: Write the failing tests**

Add to `tests/test_irrigation_env.py` in `TestIrrigationValidators`:

```python
    def test_magnitude_cap_allows_aggressive_within(self):
        ctx = self._make_context(proposed_magnitude=25, cluster="aggressive")
        results = magnitude_cap_check("increase_demand", [], ctx)
        assert len(results) == 0

    def test_magnitude_cap_blocks_forward_looking(self):
        ctx = self._make_context(proposed_magnitude=25, cluster="forward_looking_conservative")
        results = magnitude_cap_check("increase_demand", [], ctx)
        assert len(results) == 1
        assert not results[0].valid

    def test_magnitude_cap_blocks_myopic(self):
        ctx = self._make_context(proposed_magnitude=12, cluster="myopic_conservative")
        results = magnitude_cap_check("increase_demand", [], ctx)
        assert len(results) == 1
        assert not results[0].valid
```

Update list-length assertions:

```python
        assert len(IRRIGATION_PHYSICAL_CHECKS) == 5
        assert len(ALL_IRRIGATION_CHECKS) == 7
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_irrigation_env.py::TestIrrigationValidators::test_magnitude_cap_allows_aggressive_within -v`
Expected: FAIL with `NameError` for `magnitude_cap_check` or missing imports.

**Step 3: Write minimal implementation**

In `broker/validators/governance/irrigation_validators.py`, add:

```python
def magnitude_cap_check(skill_name: str, rules: List[GovernanceRule], context: Dict[str, Any]) -> List[ValidationResult]:
    if skill_name != "increase_demand":
        return []

    magnitude = context.get("proposed_magnitude", 0)
    cluster = context.get("cluster", "myopic_conservative")

    caps = {
        "aggressive": 30,
        "forward_looking_conservative": 15,
        "myopic_conservative": 10,
    }
    max_mag = caps.get(cluster, 10)

    if abs(magnitude) > max_mag:
        return [
            ValidationResult(
                valid=False,
                validator_name="IrrigationMagnitudeValidator",
                errors=[
                    f"Magnitude {magnitude}% exceeds {cluster} cap ({max_mag}%)."
                ],
                warnings=[],
                metadata={
                    "rule_id": "magnitude_cap",
                    "category": "physical",
                    "blocked_skill": skill_name,
                    "level": "ERROR",
                },
            )
        ]
    return []
```

Add it to `IRRIGATION_PHYSICAL_CHECKS` and `ALL_IRRIGATION_CHECKS`.

**Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_irrigation_env.py::TestIrrigationValidators -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_irrigation_env.py broker/validators/governance/irrigation_validators.py
git commit -m "feat(irrigation): add magnitude cap governance check"
```

---

### Task 2: Add `magnitude` to response format + parsing + apply logic

**Files:**
- Modify: `examples/irrigation_abm/run_experiment.py`
- Create: `tests/test_irrigation_integration.py`

**Step 1: Write failing tests**

In `tests/test_irrigation_integration.py` (new file):

```python
import json
from examples.irrigation_abm.run_experiment import _parse_decision, _apply_skill


def test_parse_decision_extracts_magnitude():
    payload = {
        "water_threat_appraisal": {"label": "H", "reason": ""},
        "water_coping_appraisal": {"label": "M", "reason": ""},
        "decision": "1",
        "magnitude": 15,
        "reasoning": ""
    }
    raw = "<<<DECISION_START>>>\n" + json.dumps(payload) + "\n<<<DECISION_END>>>"
    result = _parse_decision(raw)
    assert result["magnitude"] == 15
    assert result["skill"] == "increase_demand"


def test_apply_skill_uses_magnitude_percent():
    # 15% of 100k = 15k increase
    new_request = _apply_skill("increase_demand", 50_000, 100_000, magnitude_pct=15)
    assert new_request == 65_000
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_irrigation_integration.py::test_parse_decision_extracts_magnitude -v`
Expected: FAIL because `_parse_decision` doesn’t return `magnitude` and `_apply_skill` lacks param.

**Step 3: Minimal implementation**

In `examples/irrigation_abm/run_experiment.py`:

- Update `_RESPONSE_FORMAT` to include `magnitude`.
- In `_parse_decision`, parse `magnitude` (int), default to 10 if missing/invalid.
- Update `_apply_skill` signature to `def _apply_skill(skill, current_diversion, water_right, magnitude_pct=10)` and compute change as `water_right * (magnitude_pct / 100.0)`.
- In `run_group_b` and `run_group_c`, pass `decision.get("magnitude", 10)` into `_apply_skill`.

**Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_irrigation_integration.py::test_parse_decision_extracts_magnitude -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add examples/irrigation_abm/run_experiment.py tests/test_irrigation_integration.py
git commit -m "feat(irrigation): parse and apply magnitude in decisions"
```

---

### Task 3: Add regret feedback builder + tests

**Files:**
- Modify: `examples/irrigation_abm/irrigation_personas.py`
- Modify: `tests/test_irrigation_integration.py`

**Step 1: Write failing test**

Append to `tests/test_irrigation_integration.py`:

```python
from examples.irrigation_abm.irrigation_personas import build_regret_feedback


def test_build_regret_feedback_formats_shortfall():
    text = build_regret_feedback(
        year=2025,
        request=120_000,
        diversion=90_000,
        drought_index=0.72,
        preceding_factor=0,
    )
    assert "Year 2025" in text
    assert "requested 120000" in text.replace(",", "")
    assert "received 90000" in text.replace(",", "")
    assert "shortfall" in text.lower()
    assert "drought index" in text.lower()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_irrigation_integration.py::test_build_regret_feedback_formats_shortfall -v`
Expected: FAIL with import error or missing function.

**Step 3: Minimal implementation**

Add to `examples/irrigation_abm/irrigation_personas.py`:

```python
def build_regret_feedback(
    year: int,
    request: float,
    diversion: float,
    drought_index: float,
    preceding_factor: int,
) -> str:
    gap = max(0.0, request - diversion)
    gap_pct = (gap / request * 100.0) if request > 0 else 0.0
    precip_text = "above" if preceding_factor else "below"

    if gap > 0:
        shortfall = f"Shortfall: {gap:,.0f} acre-ft ({gap_pct:.0f}% unmet)."
    else:
        shortfall = "Demand fully met."

    return (
        f"Year {year}: You requested {request:,.0f} acre-ft and received "
        f"{diversion:,.0f} acre-ft. {shortfall} "
        f"Drought index: {drought_index:.2f}. Precipitation was {precip_text} last year."
    )
```

**Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_irrigation_integration.py::test_build_regret_feedback_formats_shortfall -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add examples/irrigation_abm/irrigation_personas.py tests/test_irrigation_integration.py
git commit -m "feat(irrigation): add regret feedback builder"
```

---

### Task 4: Integration tests for memory + reflection + full loop

**Files:**
- Modify: `tests/test_irrigation_integration.py`

**Step 1: Write failing tests**

Append to `tests/test_irrigation_integration.py`:

```python
from types import SimpleNamespace

from broker.components.engines.window_engine import WindowMemoryEngine
from broker.components.engines.hierarchical_engine import HierarchicalMemoryEngine
from broker.components.reflection_engine import ReflectionEngine, ReflectionTrigger
from broker.validators.governance import validate_all
from examples.irrigation_abm.run_experiment import _apply_skill


def test_memory_window_keeps_last_five():
    engine = WindowMemoryEngine(window_size=5)
    agent = SimpleNamespace(id="Agent_001", memory=[])
    for i in range(10):
        engine.add_memory(agent.id, f"mem-{i}")
    mems = engine.retrieve(agent, top_k=5)
    assert mems == ["mem-5", "mem-6", "mem-7", "mem-8", "mem-9"]


def test_hierarchical_memory_returns_semantic():
    engine = HierarchicalMemoryEngine(window_size=3, semantic_top_k=2)
    agent = SimpleNamespace(id="Agent_001", memory=[])
    # Older high-importance entries
    engine.add_memory(agent.id, "routine year", {"importance": 0.2})
    engine.add_memory(agent.id, "big shortfall", {"importance": 0.9})
    engine.add_memory(agent.id, "moderate shortfall", {"importance": 0.7})
    engine.add_memory(agent.id, "recent 1", {"importance": 0.1})
    engine.add_memory(agent.id, "recent 2", {"importance": 0.1})
    engine.add_memory(agent.id, "recent 3", {"importance": 0.1})
    mems = engine.retrieve(agent)
    assert "semantic" in mems
    assert len(mems["semantic"]) == 2


def test_reflection_triggers():
    engine = ReflectionEngine(reflection_interval=5)
    assert engine.should_reflect_triggered("A", "household", 10, ReflectionTrigger.PERIODIC)
    assert engine.should_reflect_triggered("A", "household", 1, ReflectionTrigger.CRISIS)
    assert engine.should_reflect_triggered(
        "A", "household", 1, ReflectionTrigger.DECISION, context={"decision": "decrease_demand"}
    ) is False


def test_governance_validate_magnitude_cap():
    ctx = {"proposed_magnitude": 25, "cluster": "forward_looking_conservative"}
    results = validate_all("increase_demand", [], ctx, domain="irrigation")
    errors = [r for r in results if not r.valid]
    assert len(errors) >= 1


def test_apply_skill_with_governance_bounded_magnitude():
    # magnitude already bounded by governance
    new_req = _apply_skill("increase_demand", 50_000, 100_000, magnitude_pct=10)
    assert new_req == 60_000
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_irrigation_integration.py::test_memory_window_keeps_last_five -v`
Expected: FAIL until file exists and imports resolve.

**Step 3: Minimal implementation (if needed)**

No production code changes expected for these tests once Tasks 1–3 are complete.

**Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_irrigation_integration.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_irrigation_integration.py
git commit -m "test(irrigation): add integration coverage for memory/reflection/governance"
```

---

### Task 5: Full test run

**Files:**
- Test: `tests/test_fql.py`
- Test: `tests/test_irrigation_env.py`
- Test: `tests/test_irrigation_integration.py`

**Step 1: Run full targeted suite**

Run: `python -m pytest tests/test_fql.py tests/test_irrigation_env.py tests/test_irrigation_integration.py -v`
Expected: PASS.

**Step 2: Commit (if any uncommitted changes)**

```bash
git status
```

---

**Plan complete and saved to `docs/plans/2026-01-30-irrigation-abm-integration-plan.md`. Two execution options:**

1. Subagent-Driven (this session) – I dispatch fresh subagent per task, review between tasks.
2. Parallel Session (separate) – Open new session with executing-plans and run task-by-task.

Which approach?
