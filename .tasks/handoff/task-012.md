# Task-012: Core State Persistence Interface

## Metadata

| Field            | Value                                                            |
| :--------------- | :--------------------------------------------------------------- |
| **ID**           | task-012                                                         |
| **Title**        | Centralize Agent State Persistence in Core Framework             |
| **Status**       | `ready_for_execution`                                            |
| **Type**         | Architecture Enhancement                                         |
| **Priority**     | High                                                             |
| **Owner**        | antigravity (planning)                                           |
| **Reviewer**     | WenyuChiou                                                       |
| **Assigned To**  | Claude Code / Gemini CLI                                         |
| **Scope**        | `agents/base_agent.py`, `broker/core/experiment.py`              |
| **Done When**    | `BaseAgent.apply_delta()` implemented and `run_flood.py` uses it |
| **Handoff File** | `.tasks/handoff/task-012.md`                                     |

---

## Problem Summary

The `state_changes` returned by `execute_skill()` must be manually applied in application scripts. This caused a critical bug where agent states froze. The fix should be "baked into" the core `BaseAgent` class.

---

## Parity & Logic Consistency (Critical)

To ensure the refactor does not change simulation outcomes, the executor MUST perform a parity check:

1. **Baseline**: Run a 5-agent, 3-year simulation using a fixed seed on the CURRENT code. Save logs to `test_parity/baseline/`.
2. **Refactor**: Apply Phase 1-4 changes.
3. **Comparison**: Run the same 5-agent, 3-year simulation with the NEW code and the SAME seed. Save logs to `test_parity/refactored/`.
4. **Validation Script**:

   ```python
   import pandas as pd
   df_a = pd.read_csv('test_parity/baseline/simulation_log.csv')
   df_b = pd.read_csv('test_parity/refactored/simulation_log.csv')

   # Core logic check: Decisions and resulting states must be identical
   assert df_a['approved_skill'].equals(df_b['approved_skill']), "Decision parity failed!"
   assert df_a['cumulative_state'].equals(df_b['cumulative_state']), "State persistence parity failed!"
   print("✅ Parity Verification Passed: Core logic is identical.")
   ```

## Execution Plan (for CLI Agents)

> **IMPORTANT**: Execute steps **in order**. Report back after each phase.

### Phase 1: Add `apply_delta()` to BaseAgent

**Assigned To**: Claude Code  
**File**: `agents/base_agent.py`  
**Action**: Add new method after line 338 (after `execute_skill`)

```python
# Add this method to BaseAgent class
def apply_delta(self, state_changes: Dict[str, Any]) -> None:
    """
    Apply execution result state changes to agent attributes.

    This is the CANONICAL method for updating agent state from
    skill execution results. Applications SHOULD NOT use setattr
    directly.

    Args:
        state_changes: Dict of {attribute_name: new_value}
    """
    if not state_changes:
        return
    for key, value in state_changes.items():
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            # Store in dynamic_state for new attributes
            self.dynamic_state[key] = value
```

**Verification**:

```bash
python -c "from agents.base_agent import BaseAgent; print(hasattr(BaseAgent, 'apply_delta'))"
# Expected: True
```

---

### Phase 2: Refactor ExperimentRunner

**Assigned To**: Claude Code  
**File**: `broker/core/experiment.py`  
**Location**: `_apply_state_changes` method (around line 178)

**Current Code**:

```python
def _apply_state_changes(self, agent: BaseAgent, result: Any):
    """Update agent attributes and memory from execution results."""
    # 1. Update State Flags
    changes = result.execution_result.state_changes
    for key, value in changes.items():
        setattr(agent, key, value)
```

**New Code**:

```python
def _apply_state_changes(self, agent: BaseAgent, result: Any):
    """Update agent attributes and memory from execution results."""
    # 1. Update State Flags using canonical method
    if result.execution_result and result.execution_result.state_changes:
        agent.apply_delta(result.execution_result.state_changes)
```

**Verification**:

```bash
grep -n "apply_delta" broker/core/experiment.py
# Expected: Line ~180 should show agent.apply_delta(...)
```

---

### Phase 3: Update run_flood.py

**Assigned To**: Claude Code  
**File**: `examples/single_agent/run_flood.py`  
**Location**: `FinalParityHook.post_step` method (around line 301-308)

**Current Code**:

```python
# BUGFIX: Apply state_changes to agent attributes
if result and hasattr(result, 'state_changes') and result.state_changes:
    for key, value in result.state_changes.items():
        setattr(agent, key, value)
```

**New Code**:

```python
# Apply state_changes using canonical BaseAgent method
if result and hasattr(result, 'state_changes') and result.state_changes:
    agent.apply_delta(result.state_changes)
```

**Verification**:

```bash
grep -n "apply_delta" examples/single_agent/run_flood.py
# Expected: Should find one match in post_step
```

---

### Phase 4: Git Commit

**Assigned To**: Claude Code

```bash
git add agents/base_agent.py broker/core/experiment.py examples/single_agent/run_flood.py
git commit -m "feat(core): add BaseAgent.apply_delta for canonical state persistence

- Add apply_delta() method to BaseAgent for standardized state updates
- Refactor ExperimentRunner to use canonical method
- Update run_flood.py hook to use apply_delta()

Closes: task-012"
```

---

## Phase 3 (Optional): Contract Verification

> **Note**: Only implement if requested by reviewer.

**Assigned To**: Claude Code  
**File**: `broker/interfaces/skill_types.py`

Add tracking field to `ExecutionResult`:

```python
@dataclass
class ExecutionResult:
    success: bool
    state_changes: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    _applied: bool = field(default=False, repr=False)  # Track application

    def mark_applied(self):
        self._applied = True

    def verify_applied(self):
        if self.state_changes and not self._applied:
            import warnings
            warnings.warn("ExecutionResult.state_changes were not applied!")
```

---

## Execution Report Template

After completing each phase, CLI agent should report:

```
REPORT
agent: <Claude Code / Gemini CLI>
task_id: task-012
scope: agents/base_agent.py
status: <done|blocked|partial>
changes: <files modified>
tests: <verification commands run>
artifacts: none
issues: <any problems encountered>
next: <next phase or "complete">
```

---

## Risk Assessment

| Risk                      | Likelihood | Impact   | Mitigation                       |
| :------------------------ | :--------- | :------- | :------------------------------- |
| Breaking existing scripts | Low        | Medium   | Method is additive, not breaking |
| Attribute not found       | Low        | Low      | Fallback to `dynamic_state`      |
| Performance overhead      | Very Low   | Very Low | Single loop iteration            |

---

## Timeline

| Phase     | Duration   | Blocker |
| :-------- | :--------- | :------ |
| Phase 1   | 15 min     | None    |
| Phase 2   | 10 min     | Phase 1 |
| Phase 3   | 10 min     | Phase 2 |
| Phase 4   | 5 min      | Phase 3 |
| **Total** | **40 min** |         |

---

## Notes for Executing Agent

1. **Do NOT execute while simulations are running** - Wait for current Llama/Gemma experiments to complete first.
2. **Run verification commands** after each phase before proceeding.
3. **Report any issues** using the template above.
4. **Reference this file** for exact code snippets - do not improvise.
