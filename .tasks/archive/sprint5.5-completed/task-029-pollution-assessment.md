# Task-029 MA Pollution Assessment - Critical Gap Found

**Date**: 2026-01-21
**Assessor**: Claude Sonnet 4.5
**Status**: ⚠️ INCOMPLETE - Major pollution remains

---

## Executive Summary

**CRITICAL FINDING**: Sprint 5 did NOT achieve the goal of "zero MA concepts in broker/".

**Remaining Pollution**: broker/modules/survey/ still contains significant MA-specific code:
- `mg_classifier.py` (entire file - 214 lines)
- `agent_initializer.py` (multiple flood/MG references)
- `__init__.py` (exports MG classes)

---

## Detailed Pollution Scan Results

### 1. broker/modules/survey/mg_classifier.py

**Status**: 🔴 ENTIRELY MA-SPECIFIC

**Evidence**:
```python
"""
MG (Marginalized Group) Classifier.

Classifies households as MG or NMG based on three criteria:
1. Housing cost burden >30% of income
2. No vehicle ownership
3. Below federal poverty line (based on family size and income)
"""
```

**Why It's MA-Specific**:
- "Marginalized Group" is a MA research-specific classification
- Criteria (housing burden, vehicle, poverty) are MA study-specific
- Not a general-purpose demographic classifier
- PovertyLineTable uses US Federal Poverty Guidelines (MA study context)

**Lines of Code**: 214 lines
**Severity**: HIGH

---

### 2. broker/modules/survey/agent_initializer.py

**Status**: 🟡 MIXED (Generic + MA pollution)

**MA Pollution Found**:

#### Flood Extension Code (Lines 32-42, 246-259):
```python
def _create_flood_extension(flood_experience: bool, financial_loss: bool):
    """DEPRECATION BRIDGE: Create flood extension (MA-specific)."""
    return SimpleNamespace(
        flood_experience=flood_experience,
        financial_loss=financial_loss,
        flood_zone="unknown",
        base_depth_m=0.0,
        flood_probability=0.0,
        building_rcv_usd=0.0,
        contents_rcv_usd=0.0,
    )
```

#### MG Classification Integration (Lines 23, 238, 296):
```python
from .mg_classifier import MGClassifier, MGClassificationResult

self.mg_classifier = mg_classifier or MGClassifier()

# Later: mg_result = self.mg_classifier.classify(record)
```

#### Flood-Specific Methods (Lines 369-418):
```python
def enrich_with_hazard(self, profiles, position_enricher):
    """Enrich profiles with flood zone and position data."""
    # ... flood-specific logic
```

**Total Pollution**: ~100+ lines of MA-specific code

---

### 3. broker/modules/survey/__init__.py

**Status**: 🟡 EXPORTS MA CLASSES

```python
from .mg_classifier import MGClassifier, PovertyLineTable, MGClassificationResult
```

**Issue**: Exposes MA-specific classes as part of broker API

---

## Why Sprint 5 Didn't Catch This

### What Sprint 5 Actually Did ✅

1. **Removed flood fields from SurveyRecord** ✅
   - `flood_experience` and `financial_loss` removed from base class
   - Created FloodSurveyRecord extension

2. **Created FloodSurveyLoader** ✅
   - MA-specific loader in examples/

3. **AgentProfile uses extensions** ✅
   - Extensions pattern established

### What Sprint 5 MISSED ❌

1. **MG Classification**
   - Still in broker/modules/survey/mg_classifier.py
   - Should be in examples/multi_agent/survey/

2. **Flood Extension Helpers**
   - `_create_flood_extension()` still in agent_initializer.py
   - Marked as DEPRECATION BRIDGE but never removed

3. **AgentInitializer Integration**
   - Still has `mg_classifier` parameter
   - Still has `enrich_with_hazard()` method with flood logic

---

## Comparison to Sprint 5 Goals

### Sprint 5 Goal (from assignment):
> "No hardcoded MA concepts in `broker/modules/survey/`"

### Current Reality:
- ❌ mg_classifier.py = 100% MA concepts (214 lines)
- ❌ agent_initializer.py = ~30% MA concepts (~100 lines)
- ❌ __init__.py = Exports MA classes

**Goal Achievement**: 0% - NOT MET

---

## Root Cause Analysis

### Why Was This Missed?

1. **Incomplete Scope Definition**:
   - Sprint 5 focused on SurveyRecord fields
   - Didn't address MG classification as MA-specific

2. **MG Perceived as Generic**:
   - MG classification uses "generic" socioeconomic factors
   - But the MG/NMG categorization itself is MA research-specific

3. **Deprecation Bridge Confusion**:
   - Flood extension code marked as "bridge"
   - But never had a removal plan

4. **No Comprehensive Audit**:
   - Sprint 5 didn't run full grep audit before completion
   - Assumed SurveyRecord changes = complete

---

## Impact Assessment

### For Task-029 Sprint 6:

**Sprint 6 Goal**: "Grep audit clean: no MA hardcoding in broker/"

**Current Status**: ❌ WILL FAIL

**Blockers**:
1. mg_classifier.py exists
2. agent_initializer.py has flood code
3. __init__.py exports MG classes

### For v0.30 Release:

**Cannot release v0.30** until broker/ is truly domain-agnostic.

---

## Recommended Solution: Sprint 5.5 (Emergency Fix)

### New Sprint: 5.5 - Complete Survey Module Cleanup

**Objective**: Move ALL MA-specific code out of broker/modules/survey/

**Tasks**:

#### Task 5.5-A: Move MG Classifier
1. Move `broker/modules/survey/mg_classifier.py` →
   `examples/multi_agent/survey/mg_classifier.py`
2. Update imports in:
   - agent_initializer.py
   - Any MA scripts
3. Update __init__.py to not export MG classes

#### Task 5.5-B: Clean AgentInitializer
1. Remove `_create_flood_extension()` function
2. Remove `mg_classifier` parameter from AgentInitializer
3. Move MG classification to MA-specific initialization code
4. Remove `enrich_with_hazard()` or make it generic

#### Task 5.5-C: Final Verification
1. Run grep audit: should be clean
2. Update tests to use examples/multi_agent imports
3. Verify MA experiments still work

**Estimated Time**: 4-6 hours

**Risk**: MEDIUM-HIGH (requires careful import updates)

---

## Alternative: Accept Current State

### If We Accept MG in broker/:

**Rationale**:
- MG classification uses generic socioeconomic factors
- Could be reused in other social vulnerability studies
- Not explicitly flood-related

**Arguments Against**:
- "Marginalized Group" terminology is MA research-specific
- Criteria (housing burden, vehicle, poverty) are MA study context
- No other use cases exist or planned

**Recommendation**: ❌ **DO NOT ACCEPT**
- Framework should be domain-agnostic
- MG is not a universal demographic category
- Should follow through on Task-029 objectives

---

## Revised Sprint Plan

### Option 1: Add Sprint 5.5 (Recommended)

```
Sprint 5: SurveyRecord cleanup ✅ DONE
Sprint 5.5: MG Classifier removal ⏳ NEW
Sprint 6: Verification & Documentation ⏳ WAITING
```

### Option 2: Merge into Sprint 6

```
Sprint 6A: Move MG classifier (NEW)
Sprint 6B: Grep audit (EXISTING)
Sprint 6C: Update ARCHITECTURE.md (EXISTING)
Sprint 6D: Migration guide (EXISTING)
```

**Recommendation**: Option 1 (Sprint 5.5 separate) for clarity

---

## Success Criteria (Revised)

### Sprint 5.5 Complete When:
1. ✅ mg_classifier.py moved to examples/multi_agent/survey/
2. ✅ agent_initializer.py has no MG references
3. ✅ agent_initializer.py has no flood helper functions
4. ✅ __init__.py doesn't export MA classes
5. ✅ Grep audit clean: `grep -r "MG\|Marginalized\|flood_zone" broker/modules/survey/` returns empty

### Sprint 6 Can Then Proceed:
- Regression test
- Documentation
- Migration guide

---

## Immediate Action Required

**Decision Needed**:
1. Pause Sprint 6 assignment
2. Create Sprint 5.5 to finish cleanup
3. Re-assign Sprint 6 after 5.5 complete

**OR**

1. Accept MG as "generic enough"
2. Proceed with Sprint 6 as-is
3. Document MG as acceptable exception

**Recommendation**: Pause and complete Sprint 5.5 for true domain-agnostic framework.

---

## Conclusion

**Task-029 Sprint 5**: ⚠️ INCOMPLETE
- Achieved: SurveyRecord cleanup ✅
- Missed: MG classifier cleanup ❌
- Missed: Complete flood code removal ❌

**Sprint 6 Status**: ⚠️ BLOCKED
- Cannot pass grep audit with current state
- Need Sprint 5.5 first

**Overall Task-029**: 🟡 60% COMPLETE
- Sprints 1-4: Done ✅
- Sprint 5: Partial ⚠️
- Sprint 5.5: Needed ⏳
- Sprint 6: Blocked ⏳

---

**Assessed by**: Claude Sonnet 4.5
**Date**: 2026-01-21
**Requires**: User decision on how to proceed
