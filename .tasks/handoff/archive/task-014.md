# Task-014: MA State Persistence Alignment

## Metadata

| Field            | Value                                                    |
| :--------------- | :------------------------------------------------------- |
| **ID**           | task-014                                                 |
| **Title**        | MA State Persistence Alignment                           |
| **Status**       | `completed` ✅                                           |
| **Type**         | refactor                                                 |
| **Priority**     | Low                                                      |
| **Owner**        | antigravity                                              |
| **Reviewer**     | WenyuChiou                                               |
| **Assigned To**  | Gemini CLI                                               |
| **Scope**        | `examples/multi_agent/run_unified_experiment.py`         |
| **Done When**    | MA `post_step` 使用 `apply_delta()` 更新狀態              |
| **Handoff File** | `.tasks/handoff/task-014.md`                             |

---

## Problem Summary

Task-012 為 SA 系統建立了 `BaseAgent.apply_delta()` 作為狀態更新的標準方法。MA 系統的 `run_unified_experiment.py` 目前直接寫入 `dynamic_state`，未遵循此模式。

**當前狀態**:
- `BaseAgent.apply_delta()` ✅ 已實作 (agents/base_agent.py:340)
- `ExperimentRunner._apply_state_changes()` ✅ 已更新 (broker/core/experiment.py:182)
- `run_flood.py` (SA) ✅ 已使用 apply_delta (line 306)
- `run_unified_experiment.py` (MA) ❌ 直接寫入 dynamic_state

---

## Execution Plan (for Gemini CLI)

### Phase 1: Update post_step for Household Actions

**File**: `examples/multi_agent/run_unified_experiment.py`
**Location**: `MultiAgentHooks.post_step()` (lines 404-416)

**Current Code**:
```python
elif agent.agent_type in ["household_owner", "household_renter"]:
    current_year = self.env.get("year", 1)

    if decision in ["buy_insurance", "buy_contents_insurance"]:
        agent.dynamic_state["has_insurance"] = True  # Effective immediately
    elif decision == "elevate_house":
        # Elevation takes 1 year to complete
        agent.dynamic_state["pending_action"] = "elevation"
        agent.dynamic_state["action_completion_year"] = current_year + 1
        print(f" [LIFECYCLE] {agent.id} started elevation (completes Year {current_year + 1})")
        agent.dynamic_state["pending_action"] = "buyout"
        agent.dynamic_state["action_completion_year"] = current_year + 2
        print(f" [LIFECYCLE] {agent.id} applied for buyout (finalizes Year {current_year + 2})")
```

**New Code**:
```python
elif agent.agent_type in ["household_owner", "household_renter"]:
    current_year = self.env.get("year", 1)

    if decision in ["buy_insurance", "buy_contents_insurance"]:
        # Use canonical apply_delta method (Task-014)
        agent.apply_delta({"has_insurance": True})
    elif decision == "elevate_house":
        # Elevation takes 1 year to complete - use apply_delta (Task-014)
        agent.apply_delta({
            "pending_action": "elevation",
            "action_completion_year": current_year + 1
        })
        print(f" [LIFECYCLE] {agent.id} started elevation (completes Year {current_year + 1})")
    elif decision == "apply_buyout":
        # Buyout takes 2 years - use apply_delta (Task-014)
        agent.apply_delta({
            "pending_action": "buyout",
            "action_completion_year": current_year + 2
        })
        print(f" [LIFECYCLE] {agent.id} applied for buyout (finalizes Year {current_year + 2})")
```

**Note**: 當前程式碼有邏輯錯誤 (elevate_house 區塊內同時設定 elevation 和 buyout)。修正時應分開處理。

---

### Phase 2: Update pre_year for Pending Resolution

**File**: `examples/multi_agent/run_unified_experiment.py`
**Location**: `MultiAgentHooks.pre_year()` (lines 343-351)

**Current Code**:
```python
if pending and completion_year and year >= completion_year:
    if pending == "elevation":
        agent.dynamic_state["elevated"] = True
        print(f" [LIFECYCLE] {agent.id} elevation COMPLETE.")
    elif pending == "buyout":
        agent.dynamic_state["relocated"] = True
        print(f" [LIFECYCLE] {agent.id} buyout FINALIZED (left community).")
    # Clear pending state
    agent.dynamic_state["pending_action"] = None
    agent.dynamic_state["action_completion_year"] = None
```

**New Code**:
```python
if pending and completion_year and year >= completion_year:
    if pending == "elevation":
        agent.apply_delta({"elevated": True})
        print(f" [LIFECYCLE] {agent.id} elevation COMPLETE.")
    elif pending == "buyout":
        agent.apply_delta({"relocated": True})
        print(f" [LIFECYCLE] {agent.id} buyout FINALIZED (left community).")
    # Clear pending state using apply_delta (Task-014)
    agent.apply_delta({
        "pending_action": None,
        "action_completion_year": None
    })
```

---

### Phase 3: Verification

**Syntax Check**:
```bash
python -c "from examples.multi_agent.run_unified_experiment import MultiAgentHooks; print('Syntax OK')"
```

**Integration Test**:
```bash
cd examples/multi_agent
python run_unified_experiment.py --model mock --years 3 --mode random --agents 5
```

**Expected Output**:
- No import errors
- `[LIFECYCLE]` messages appear correctly
- Agent states update properly

---

### Phase 4: Git Commit

```bash
git add examples/multi_agent/run_unified_experiment.py
git commit -m "refactor(ma): align state persistence with apply_delta pattern

- Update MultiAgentHooks.post_step() to use agent.apply_delta()
- Update MultiAgentHooks.pre_year() to use agent.apply_delta()
- Fix logic error in elevate_house/buyout handling
- Aligns with Task-012 canonical state persistence pattern

Closes: task-014"
```

---

## Risk Assessment

| Risk                      | Likelihood | Impact   | Mitigation                       |
| :------------------------ | :--------- | :------- | :------------------------------- |
| Logic change              | Very Low   | Low      | apply_delta writes to dynamic_state internally |
| Missing attribute         | Low        | Low      | apply_delta falls back to dynamic_state for new keys |
| Breaking existing runs    | Very Low   | Low      | Mock test verifies behavior |

---

## Execution Report Template

After completing, report:

```
REPORT
agent: Gemini CLI
task_id: task-014
scope: examples/multi_agent/run_unified_experiment.py
status: <done|blocked|partial>
changes: <files modified>
tests: <verification commands run>
artifacts: none
issues: <any problems encountered>
next: complete
```

---

## Notes

1. `apply_delta()` 內部實作:
   - 如果 attribute 存在於 agent: 使用 `setattr()`
   - 如果 attribute 不存在: 寫入 `dynamic_state`
2. 此重構為純架構對齊，不應改變任何模擬邏輯
3. 發現程式碼有 bug: `elevate_house` 區塊內同時設定 elevation 和 buyout，應修正為分開的 decision 處理
