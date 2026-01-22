# Task-029 Current Status - Sprint 5.5 URGENT

**Date**: 2026-01-21
**Status**: ⚠️ Sprint 5 INCOMPLETE - Sprint 5.5 URGENT
**Priority**: CRITICAL (Blocks Sprint 6)

---

## Executive Summary

**Problem**: Sprint 5 only cleaned SurveyRecord fields, but significant MA pollution remains in broker/modules/survey/.

**Impact**: Sprint 6 grep audit will FAIL without completing cleanup.

**Solution**: Execute Sprint 5.5 to move MG classifier and remove flood helpers.

---

## Completed Work ✅

### Sprint 1-4 (100% Complete)
- ✅ Sprint 1: Documentation cleanup
- ✅ Sprint 2: Protocol-based enrichment
- ✅ Sprint 3: Config-driven memory tags
- ✅ Sprint 4: Docstring cleanup

### Sprint 5 (PARTIAL - 60% Complete) ⚠️
- ✅ Phase 5A: Generic CSV loader created (Codex)
- ✅ Phase 5B: SurveyRecord made generic (Claude Code)
- ✅ Phase 5C: AgentProfile extensions pattern (Codex)

**What Sprint 5 Achieved**:
- Removed flood fields from SurveyRecord ✅
- Created FloodSurveyRecord extension ✅
- Implemented extensions pattern ✅

**What Sprint 5 MISSED** ❌:
- MG (Marginalized Group) classifier still in broker/
- Flood helper functions still in agent_initializer.py
- MG classification integrated in broker code

---

## Critical Gap Found 🚨

### Remaining MA Pollution

**File: broker/modules/survey/mg_classifier.py**
- **Status**: 100% MA-specific (214 lines)
- **Problem**: "Marginalized Group" is MA research concept, not generic
- **Evidence**: Uses MA-specific criteria (housing burden, vehicle, poverty line)
- **Should be**: examples/multi_agent/survey/mg_classifier.py

**File: broker/modules/survey/agent_initializer.py**
- **Status**: ~100 lines of MA pollution
- **Problems**:
  - Line 23: Imports MGClassifier
  - Lines 32-42: `_create_flood_extension()` function
  - Lines 246-259: Flood extension creation
  - Lines 369-418: `enrich_with_hazard()` method
- **Should be**: Generic initialization only

**File: broker/modules/survey/__init__.py**
- **Status**: Exports MA classes
- **Problem**: `from .mg_classifier import MGClassifier, ...`
- **Should be**: No MG exports

---

## Sprint 5.5 Plan (URGENT)

### Overview
**Objective**: Move ALL remaining MA-specific code out of broker/modules/survey/
**Estimated Time**: 4-6 hours total
**Risk Level**: HIGH (imports must be updated carefully)

### Phase 5.5-A+B: MG Classifier Relocation (Codex - 3-4 hrs)

**Tasks**:
1. Move file: `broker/modules/survey/mg_classifier.py` → `examples/multi_agent/survey/mg_classifier.py`
2. Update imports in mg_classifier.py (absolute imports to broker)
3. Remove MG exports from `broker/modules/survey/__init__.py`
4. Remove MG imports from `agent_initializer.py` (line 23)
5. Remove mg_classifier parameter from AgentInitializer.__init__
6. Remove MG classification from load_from_survey() method
7. Update all MA scripts to import from examples/

**Verification**:
```bash
python -c "from examples.multi_agent.survey.mg_classifier import MGClassifier; print('OK')"
grep -r "from broker.modules.survey import.*MGClassifier" examples/multi_agent/
# Should return empty
```

### Phase 5.5-C: Flood Helper Removal (Gemini - 2-3 hrs)

**Tasks**:
1. Delete `_create_flood_extension()` function (lines 32-42)
2. Make `_create_extensions()` return empty dict (generic)
3. Remove/update `enrich_with_hazard()` method
4. Remove flood stats from `load_from_survey()`
5. Update docstrings to be domain-agnostic
6. Test generic initialization works

**Verification**:
```python
from broker.modules.survey.agent_initializer import AgentInitializer
initializer = AgentInitializer()  # Should work without mg_classifier
```

### MA-Specific Initialization Wrapper (Both)

**Create**: `examples/multi_agent/survey/ma_initializer.py`

This wrapper will:
- Use generic broker components
- Add MA-specific MG classification
- Add flood extensions
- Provide initialize_ma_agents_from_survey() function

**Update**: `examples/multi_agent/run_unified_experiment.py`
```python
# OLD:
from broker.modules.survey import initialize_agents_from_survey

# NEW:
from examples.multi_agent.survey.ma_initializer import initialize_ma_agents_from_survey
```

---

## Success Criteria

Sprint 5.5 complete when:
1. ✅ mg_classifier.py in examples/multi_agent/survey/
2. ✅ agent_initializer.py has no MG references
3. ✅ agent_initializer.py has no flood helper functions
4. ✅ broker/modules/survey/__init__.py clean
5. ✅ Grep audit passes: no MG/flood code in broker/modules/survey/
6. ✅ MA experiments still work with new ma_initializer.py
7. ✅ All commits merged to main

---

## Testing Checklist

### After Phase 5.5-A+B (Codex):
- [ ] mg_classifier.py imports successfully from examples/
- [ ] broker/modules/survey/__init__.py has no MG exports
- [ ] agent_initializer.py has no MG imports
- [ ] MA scripts can import from new location
- [ ] Unit tests pass

### After Phase 5.5-C (Gemini):
- [ ] agent_initializer.py has no flood helper functions
- [ ] _create_extensions() returns empty dict
- [ ] Generic initialization works
- [ ] MA wrapper (ma_initializer.py) created
- [ ] MA experiment runs successfully

### Final Verification:
```bash
# Should return ONLY comments/docstrings (no executable code):
grep -r "flood\|MG\|Marginalized" broker/modules/survey/ --include="*.py" | grep -v "# " | grep -v '"""'

# Expected: Empty or only harmless references
```

---

## Risk Mitigation

### Risk 1: Breaking MA Experiments
**Mitigation**:
- Codex does 5.5-A+B first (MG relocation)
- Gemini then does 5.5-C (flood removal)
- Test after each phase
- Commit separately for easy rollback
- Create MA wrapper to maintain functionality

### Risk 2: Import Errors
**Mitigation**:
- Update all imports systematically
- Use grep to find all import locations
- Test imports after each change
- Verify both broker/ and examples/ work

---

## Timeline

| Sprint | Status | Time Spent | Time Remaining |
|:-------|:-------|:-----------|:---------------|
| Sprint 1-4 | ✅ Complete | ~19 hours | - |
| Sprint 5 | ⚠️ Partial | ~17 hours | - |
| **Sprint 5.5** | ⏳ **URGENT** | - | **4-6 hours** |
| Sprint 6 | 🚫 Blocked | - | 4-5 hours |

**Total Task-029**: ~40-47 hours (5-6 days focused work)

**Current Progress**: ~36 hours (~77%)

---

## Assignment Status

### Codex: Phase 5.5-A+B
- **Status**: ⏳ ASSIGNED
- **Document**: [task-029-sprint5.5-assignment.md](.tasks/handoff/task-029-sprint5.5-assignment.md)
- **Estimated**: 3-4 hours
- **Priority**: CRITICAL - Must complete first

### Gemini: Phase 5.5-C
- **Status**: ⏳ ASSIGNED
- **Document**: [task-029-sprint5.5-assignment.md](.tasks/handoff/task-029-sprint5.5-assignment.md)
- **Estimated**: 2-3 hours
- **Priority**: CRITICAL - Depends on Codex completion

---

## Reference Documents

1. [task-029-pollution-assessment.md](.tasks/handoff/task-029-pollution-assessment.md) - Full problem analysis
2. [task-029-sprint5.5-assignment.md](.tasks/handoff/task-029-sprint5.5-assignment.md) - Detailed task breakdown
3. [task-029-sprint5-summary.md](.tasks/handoff/task-029-sprint5-summary.md) - What Sprint 5 achieved
4. [elegant-honking-harbor.md](C:\Users\wenyu\.claude\plans\elegant-honking-harbor.md) - Master plan

---

## Blocking Issues

**Sprint 6 CANNOT START** until Sprint 5.5 completes because:
- Grep audit will fail (MA pollution present)
- "Zero MA concepts in broker/" standard not met
- Documentation cannot be finalized with incorrect state

**User Feedback** (2026-01-21):
> "Sprint 6 驗證已開始，但目前無法通過（仍有 MA 污染在 broker/）。我執行了污染掃描，結果顯示 broker/modules/survey/*、mg_classifier.py、survey_loader.py、agent_initializer.py 仍包含 flood/MG 等字樣，因此不符合 Sprint 6 的「broker 內零 MA 概念」標準。"

**Acknowledgment**: User is correct. Sprint 5 scope was incomplete.

---

## Next Steps

1. **Codex**: Execute Phase 5.5-A+B (MG classifier relocation)
2. **Gemini**: Execute Phase 5.5-C (flood helper removal)
3. **Both**: Test and verify after each phase
4. **Both**: Create MA-specific wrapper (ma_initializer.py)
5. **Verification**: Run grep audit to confirm zero MA pollution
6. **Then**: Sprint 6 can begin

---

**Updated**: 2026-01-21T22:15:00Z
**Next Update**: After Sprint 5.5 completion
