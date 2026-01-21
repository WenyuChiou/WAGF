# Current Session Handoff

## Last Updated
2026-01-21T06:30:00Z

---

## Active Task: Task-028

**Title**: Framework Cleanup & Agent-Type Config

**Objective**: Clean up MA-specific code from generic broker framework and implement agent-type-specific cognitive/memory configuration.

---

## Progress Overview

| Subtask | Title | Assigned | Status |
|:--------|:------|:---------|:-------|
| 028-A | Make stimulus_key required in universal_memory.py | Claude Code | **DONE** |
| 028-B | Remove MA hardcoding from context_builder.py | Claude Code | **DONE** |
| 028-C | Move media_channels.py to examples/multi_agent/components/ | **Codex** | **DONE** |
| 028-D | Move broker/modules/hazard/ to examples/multi_agent/environment/ | **Codex** | **DONE** |
| 028-E | Update ma_agent_types.yaml with cognitive_config/memory_config | Claude Code | **DONE** |
| 028-F | Update run_unified_experiment.py for crisis_event/crisis_boosters | Claude Code | **DONE** |
| 028-G | Run verification tests | **Gemini CLI** | **PENDING** |

---

## What Claude Code Completed

### 028-A: stimulus_key Required (DONE)
**File**: `broker/components/universal_memory.py`
- Changed `stimulus_key` from optional (default "flood_depth") to REQUIRED parameter
- Added validation error if not provided

### 028-B: Remove MA Hardcoding (DONE)
**File**: `broker/components/context_builder.py`
- Removed hardcoded `flood_occurred` and `emotion:fear`
- Replaced with generic `crisis_event` / `crisis_boosters` mechanism

### 028-E: Agent-Type Config (DONE)
**File**: `examples/multi_agent/ma_agent_types.yaml`
- Added `cognitive_config` with per-agent-type settings:
  - household_owner: stimulus_key=flood_depth_m, arousal=1.0
  - household_renter: stimulus_key=flood_depth_m, arousal=0.8
  - nj_government: stimulus_key=adaptation_gap, arousal=0.15
  - fema_nfip: stimulus_key=loss_ratio, arousal=0.3
- Added `memory_config` with:
  - household: emotional_weights (fear, critical, etc.)
  - institutional: data-driven (no emotional weights)

### 028-F: crisis_event Setup (DONE)
**File**: `examples/multi_agent/run_unified_experiment.py`
- Added `crisis_event` and `crisis_boosters` to initial env_data
- Set `crisis_event = flood_occurred` and `crisis_boosters = {"emotion:fear": 1.5}` when flood occurs

---

## Codex Assignments (IMMEDIATE)

### 028-C: Move media_channels.py

```bash
# 1. Create target directory
mkdir -p examples/multi_agent/components

# 2. Move file
mv broker/components/media_channels.py examples/multi_agent/components/

# 3. Update imports in run_unified_experiment.py
# Change: from broker.components.media_channels import ...
# To: from components.media_channels import ... (relative)
```

### 028-D: Move hazard module

```bash
# 1. Ensure target exists
mkdir -p examples/multi_agent/environment

# 2. Move hazard contents
mv broker/modules/hazard/* examples/multi_agent/environment/

# 3. Update imports in run_unified_experiment.py
# Change: from broker.modules.hazard import ...
# To: from environment.hazard import ... (relative)
```

**Report format**:
```
REPORT
agent: Codex
task_id: task-028-C/D
status: done | partial | blocked
changes: <list>
issues: <any>
```

---

## Gemini CLI Assignment (After Codex)

### 028-G: Verification Testing

```bash
cd examples/multi_agent
python run_unified_experiment.py \
  --model gemma3:4b \
  --years 3 \
  --agents 5 \
  --memory-engine universal \
  --arousal-threshold 1.0 \
  --mode random \
  --output results_unified/v028_test
```

**Check**:
- [ ] No import errors
- [ ] crisis_event/crisis_boosters in env when flood
- [ ] System 2 triggers on flood (arousal=1.0)

---

## Claude Code Next Steps

1. ~~**028-E**: Update `ma_agent_types.yaml`~~ **DONE**

2. Wait for Codex to complete 028-C/D (file moves)

3. After Codex: Update imports in run_unified_experiment.py if needed

---

## Key Design Decisions (User Confirmed)

| Setting | Value | Rationale |
|:--------|:------|:----------|
| Government stimulus | `adaptation_gap` | Policy effect deviation |
| Insurance stimulus | `loss_ratio` | Claims ratio |
| Household arousal | `1.0` | Lower threshold for sensitivity |
| Framework cleanup | Complete | Move MA files out of broker/ |

---

## Files Modified This Session

| File | Change |
|:-----|:-------|
| `broker/components/universal_memory.py` | stimulus_key now required |
| `broker/components/context_builder.py` | Generic crisis mechanism |
| `examples/multi_agent/run_unified_experiment.py` | Added crisis_event/crisis_boosters |
| `examples/multi_agent/ma_agent_types.yaml` | Added cognitive_config + memory_config |

---

## Completed Tasks (Reference)

| Task | Title |
|:-----|:------|
| 027 | Universal Cognitive v3 MA Integration |
| 026 | Universal Cognitive v3 (Surprise Engine) |
| 025 | Media Channels Prompt Integration |
| 024 | Integration Testing |
