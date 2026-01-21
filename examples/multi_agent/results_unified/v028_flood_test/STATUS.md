# Task-028-G Flood Verification Test - RUNNING

**Started**: 2026-01-21 14:25
**Task ID**: bac167a (background bash)
**Status**: IN PROGRESS

---

## Experiment Configuration

```bash
python run_unified_experiment.py \
  --model gemma3:4b \
  --years 3 \
  --agents 5 \
  --memory-engine universal \
  --mode random \
  --gossip \
  --neighbor-mode spatial \
  --neighbor-radius 3 \
  --per-agent-depth \
  --enable-news-media \
  --enable-social-media \
  --output results_unified/v028_flood_test
```

---

## New Features Being Tested

### From Task-028 (Framework Cleanup)
- ✅ Import paths fixed (no errors expected)
- ⏳ `crisis_event` / `crisis_boosters` mechanism
- ⏳ UniversalCognitiveEngine v3 with System 1/2 switching
- ⏳ Agent-type-specific cognitive config

### From Task-022 (PRB Integration & Spatial)
- ⏳ Spatial neighbor graph (radius-based)
- ⏳ Per-agent flood depth from PRB grids
- ⏳ News media channel (1-turn delay)
- ⏳ Social media channel (instant, ±30% exaggeration)

---

## Current Progress (Last Check: 14:26)

- **Year 1**: In progress
  - Government: ✅ maintain_subsidy
  - Insurance: ✅ maintain_premium
  - Households: 🔄 Processing (H0001-H0003 started)
  - PMT constructs calculating correctly
  - 1 retry observed (H0001 - empty response)

---

## How to Monitor

### Option 1: Check output file
```bash
tail -f C:\Users\wenyu\AppData\Local\Temp\claude\c--Users-wenyu-Desktop-Lehigh-governed-broker-framework\tasks\bac167a.output
```

### Option 2: Use PowerShell monitor (recommended)
```powershell
.\monitor_experiment.ps1
```

This will highlight:
- 🟢 Year transitions
- 🟡 Flood events
- 🟣 Crisis mechanism activations
- 🔵 System 1/2 switches

### Option 3: Check for flood events
```bash
grep -i "flood" C:\Users\wenyu\AppData\Local\Temp\claude\c--Users-wenyu-Desktop-Lehigh-governed-broker-framework\tasks\bac167a.output | tail -20
```

---

## Expected Outcomes

### ✅ If Flood Occurs:
1. `[ENV] Year X: Flood depth = Y.YYm`
2. `crisis_event: true` in agent context
3. `crisis_boosters: {"emotion:fear": 1.5}` applied
4. System 2 activation messages (if surprise > 2.0)
5. Memory retrieval with contextual boosting

### ⚠️ If No Flood (Like Last Test):
- Years 1-3: "No flood events"
- System remains in System 1 (default)
- Cannot verify crisis mechanism
- Need to rerun with specific PRB year

---

## Post-Completion Checklist

When experiment finishes:

1. **Check for flood events**:
   ```bash
   grep "\[ENV\].*Year" bac167a.output
   ```

2. **Verify crisis mechanism** (if flood occurred):
   ```bash
   grep -i "crisis" results_unified/v028_flood_test/gemma3_4b_strict/raw/*.jsonl | head -5
   ```

3. **Check System 2 activation**:
   ```bash
   grep "System 2" bac167a.output
   ```

4. **Analyze traces**:
   ```bash
   ls -lh results_unified/v028_flood_test/gemma3_4b_strict/raw/
   ```

5. **Create final report**:
   - Update [VERIFICATION_REPORT.md](../v028_verification/VERIFICATION_REPORT.md)
   - Mark Task-028 as completed or identify issues

---

## Quick Status Commands

```bash
# Check if experiment is still running
ps aux | grep "run_unified_experiment.py"

# Check latest output
tail -20 C:\Users\wenyu\AppData\Local\Temp\claude\c--Users-wenyu-Desktop-Lehigh-governed-broker-framework\tasks\bac167a.output

# Check output directory size (grows during execution)
du -sh results_unified/v028_flood_test/

# Count trace files (should be 4 files when complete)
ls results_unified/v028_flood_test/gemma3_4b_strict/raw/*.jsonl 2>/dev/null | wc -l
```

---

## Estimated Completion Time

- **Single agent per year**: ~30-60 seconds (with LLM retries)
- **5 agents × 3 years**: ~7-15 minutes
- **With governance retries**: +2-5 minutes
- **Total estimate**: 10-20 minutes

---

## Next Steps

### If Test Succeeds (Flood + Crisis Verified):
1. Mark Task-028-G as **DONE** ✅
2. Update registry.json: Task-028 → completed
3. Create final verification summary
4. Proceed to Task-029 or next planned task

### If Test Fails (No Flood Again):
1. Create Task-028-G-RERUN with explicit `--prb-year 2011`
2. Force flood year to ensure crisis testing
3. Document findings in handoff

### If Import Errors Found:
1. Create Task-028-FIX subtask
2. Address specific import issues
3. Rerun verification

---

## Background Task Info

**Task ID**: bac167a
**Output File**: `C:\Users\wenyu\AppData\Local\Temp\claude\c--Users-wenyu-Desktop-Lehigh-governed-broker-framework\tasks\bac167a.output`
**Results Dir**: `examples/multi_agent/results_unified/v028_flood_test/`
**Log File**: `v028_flood_output.log` (if tee worked)

To kill if needed:
```bash
# Find process
ps aux | grep run_unified_experiment

# Kill by PID
kill <PID>
```
