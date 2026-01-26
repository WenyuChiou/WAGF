# Task-028: Framework Cleanup & Agent-Type Cognitive Config

## Metadata

- **ID**: Task-028
- **Type**: refactor
- **Priority**: high
- **Owner**: Claude Code
- **Reviewer**: WenyuChiou
- **Status**: in_progress
- **Created**: 2026-01-21T06:00:00Z
- **Dependencies**: Task-027

## Objective

Clean up MA-specific code from generic broker framework and implement agent-type-specific cognitive/memory configuration.

**Problem**: During Task-027 evaluation, found framework contamination:
- `universal_memory.py`: Default `stimulus_key="flood_depth"` (MA-specific)
- `context_builder.py`: Hardcoded `flood_occurred` and `emotion:fear` (MA-specific)
- `media_channels.py`: Entire file is MA-specific but in generic broker/
- `broker/modules/hazard/`: Entire module is MA-specific

## User Decisions (Confirmed via AskUserQuestion)

| Decision | Value | Rationale |
|:---------|:------|:----------|
| Government stimulus | `adaptation_gap` | Policy effect deviation (not flood depth) |
| Insurance stimulus | `loss_ratio` | Claims ratio (financial indicator) |
| Household arousal | `1.0` | Lowered from 2.0 for first-flood sensitivity |
| Framework cleanup | Complete | Move MA files out of broker/ |

## Subtasks

### 028-A: Make stimulus_key Required ✅

**Assigned**: Claude Code
**Status**: completed

**Changes**:
- File: `broker/components/universal_memory.py`
- Changed `stimulus_key` from optional (default "flood_depth") to REQUIRED parameter
- Added validation error if not provided

```python
# BEFORE
def __init__(
    self,
    arousal_threshold: float = 2.0,
    ema_alpha: float = 0.3,
    stimulus_key: str = "flood_depth",  # MA pollution

# AFTER
def __init__(
    self,
    stimulus_key: str,  # REQUIRED
    arousal_threshold: float = 2.0,
    ema_alpha: float = 0.3,
```

### 028-B: Remove MA Hardcoding ✅

**Assigned**: Claude Code
**Status**: completed

**Changes**:
- File: `broker/components/context_builder.py`
- Removed hardcoded `flood_occurred` and `emotion:fear`
- Replaced with generic `crisis_event` / `crisis_boosters` mechanism

```python
# BEFORE (L574-583) - MA pollution
if env_context and env_context.get("flood_occurred"):
    contextual_boosters_for_memory["emotion:fear"] = 1.5

# AFTER - Generic mechanism
if env_context.get("crisis_event") or env_context.get("crisis_boosters"):
    crisis_boosters = env_context.get("crisis_boosters", {})
    for tag, weight in crisis_boosters.items():
        contextual_boosters_for_memory[tag] = weight
```

### 028-C: Move media_channels.py ⏳

**Assigned**: Codex
**Status**: pending

**Task**:
```bash
# 1. Create target directory
mkdir -p examples/multi_agent/components

# 2. Move file
mv broker/components/media_channels.py examples/multi_agent/components/

# 3. Update imports in run_unified_experiment.py
# Change: from broker.components.media_channels import ...
# To: from components.media_channels import ... (relative)
```

### 028-D: Move hazard/ Module ⏳

**Assigned**: Codex
**Status**: pending

**Task**:
```bash
# 1. Ensure target exists
mkdir -p examples/multi_agent/environment

# 2. Move hazard contents
mv broker/modules/hazard/* examples/multi_agent/environment/

# 3. Update imports in run_unified_experiment.py
# Change: from broker.modules.hazard import ...
# To: from environment.hazard import ... (relative)
```

### 028-E: Agent-Type Config ✅

**Assigned**: Claude Code
**Status**: completed

**Changes**:
- File: `examples/multi_agent/ma_agent_types.yaml`
- Added `cognitive_config` section with per-agent-type settings:
  - `household_owner`: stimulus_key=flood_depth_m, arousal=1.0
  - `household_renter`: stimulus_key=flood_depth_m, arousal=0.8
  - `nj_government`: stimulus_key=adaptation_gap, arousal=0.15
  - `fema_nfip`: stimulus_key=loss_ratio, arousal=0.3
- Added `memory_config` section:
  - `household`: emotional_weights (fear, critical, hope, anxiety)
  - `institutional`: data-driven (no emotional weights)

### 028-F: crisis_event Setup ✅

**Assigned**: Claude Code
**Status**: completed

**Changes**:
- File: `examples/multi_agent/run_unified_experiment.py`
- Added `crisis_event` and `crisis_boosters` to initial env_data
- Set `crisis_event = flood_occurred` when flood occurs (both per-agent and legacy modes)
- Set `crisis_boosters = {"emotion:fear": 1.5}` during floods

### 028-G: Verification Tests 🚫

**Assigned**: Gemini CLI
**Status**: blocked
**Blocker**: Waiting for 028-C/D file moves to complete

**Test command**:
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

**Verification criteria**:
- [ ] No import errors (media_channels, hazard moved correctly)
- [ ] crisis_event/crisis_boosters appear in env when flood occurs
- [ ] System 2 triggers on first significant flood (arousal=1.0)

## Files Modified

| File | Change |
|:-----|:-------|
| `broker/components/universal_memory.py` | stimulus_key now required |
| `broker/components/context_builder.py` | Generic crisis mechanism |
| `examples/multi_agent/run_unified_experiment.py` | Added crisis_event/crisis_boosters |
| `examples/multi_agent/ma_agent_types.yaml` | Added cognitive_config + memory_config |

## Next Steps

1. **Codex**: Execute 028-C and 028-D file moves
2. **Codex**: Report completion in standard format
3. **Gemini CLI**: Run 028-G verification after Codex completes
4. **Claude Code**: Review results and close task

## Risks

- Import path changes may break existing code
- Need to verify all imports updated correctly after file moves

## Rollback

```bash
# Revert code changes
git revert <commit-028-A>
git revert <commit-028-B>
git revert <commit-028-E>
git revert <commit-028-F>

# Restore moved files (if needed)
mv examples/multi_agent/components/media_channels.py broker/components/
mv examples/multi_agent/environment/* broker/modules/hazard/
```
