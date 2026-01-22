# Task-029 Sprint 5.5: Complete Survey Module Cleanup (URGENT)
## Assignment for Gemini & Codex

**Date**: 2026-01-21
**Status**: URGENT - Blocking Sprint 6
**Priority**: CRITICAL
**Risk**: HIGH

---

## Context

**CRITICAL ISSUE FOUND**: Sprint 5 did NOT complete MA pollution removal.

**Problem**: broker/modules/survey/ still contains:
- `mg_classifier.py` (214 lines, 100% MA-specific)
- MA code in `agent_initializer.py` (~100 lines)
- Exports of MA classes in `__init__.py`

**Impact**: Sprint 6 grep audit will **FAIL** without this cleanup.

**See**: [task-029-pollution-assessment.md](.tasks/handoff/task-029-pollution-assessment.md) for full analysis.

---

## Sprint 5.5 Overview

**Objective**: Move ALL remaining MA-specific code out of broker/modules/survey/

**Estimated Time**: 4-6 hours total
**Risk Level**: HIGH (imports must be updated carefully)

---

## Task Assignment

### Codex: Phase 5.5-A + 5.5-B (MG Classifier Relocation)
**Estimated**: 3-4 hours
**Risk**: HIGH

#### Phase 5.5-A: Move MG Classifier to Examples

**Goal**: Relocate mg_classifier.py from broker/ to examples/multi_agent/

1. **Move file**:
   ```bash
   # FROM: broker/modules/survey/mg_classifier.py
   # TO:   examples/multi_agent/survey/mg_classifier.py
   ```

2. **Update imports in mg_classifier.py**:
   ```python
   # OLD: from .survey_loader import SurveyRecord, INCOME_MIDPOINTS
   # NEW: from broker.modules.survey.survey_loader import SurveyRecord, INCOME_MIDPOINTS
   ```

3. **Update broker/modules/survey/__init__.py**:
   ```python
   # REMOVE these lines:
   from .mg_classifier import MGClassifier, PovertyLineTable, MGClassificationResult

   __all__ = [
       # ...
       "MGClassifier",  # REMOVE
       "PovertyLineTable",  # REMOVE
       "MGClassificationResult",  # REMOVE
   ]
   ```

4. **Update imports in agent_initializer.py**:
   ```python
   # OLD: from .mg_classifier import MGClassifier, MGClassificationResult
   # NEW: (Remove this import - will be handled in Phase 5.5-B)
   ```

5. **Update all MA scripts that import MGClassifier**:

   Find with:
   ```bash
   grep -r "from broker.modules.survey import.*MGClassifier" examples/multi_agent/
   grep -r "from broker.modules.survey.mg_classifier import" examples/multi_agent/
   ```

   Update to:
   ```python
   from examples.multi_agent.survey.mg_classifier import MGClassifier
   ```

6. **Test imports**:
   ```bash
   python -c "from examples.multi_agent.survey.mg_classifier import MGClassifier; print('OK')"
   ```

#### Phase 5.5-B: Remove MG from AgentInitializer

**Goal**: Make agent_initializer.py MG-agnostic

1. **Remove MG imports** (line 23):
   ```python
   # DELETE THIS LINE:
   from .mg_classifier import MGClassifier, MGClassificationResult
   ```

2. **Remove mg_classifier parameter** from AgentInitializer.__init__:
   ```python
   # BEFORE:
   def __init__(
       self,
       survey_loader: Optional[SurveyLoader] = None,
       mg_classifier: Optional[MGClassifier] = None,  # DELETE THIS
       ...
   ):
       self.mg_classifier = mg_classifier or MGClassifier()  # DELETE THIS

   # AFTER:
   def __init__(
       self,
       survey_loader: Optional[SurveyLoader] = None,
       ...
   ):
       # No mg_classifier
   ```

3. **Remove MG classification from load_from_survey()**:

   Find the MG classification loop (~line 270-290):
   ```python
   # DELETE THIS BLOCK:
   mg_result = self.mg_classifier.classify(record)

   profile = AgentProfile(
       # ...
       is_mg=mg_result.is_mg,  # DELETE
       mg_score=mg_result.score,  # DELETE
       mg_criteria=mg_result.criteria,  # DELETE
   )

   if mg_result.is_mg:
       mg_count += 1
   ```

4. **Remove MG stats from return**:
   ```python
   # DELETE these from stats dict:
   "mg_count": mg_count,
   "nmg_count": len(profiles) - mg_count,
   "mg_ratio": mg_count / len(profiles) if profiles else 0,
   ```

5. **Update initialize_agents_from_survey() wrapper**:

   This function likely needs MG classification. Move MG logic to MA-specific code:
   ```python
   # Option 1: Remove mg_classifier parameter
   # Option 2: Add deprecation warning and call MA-specific initialization
   ```

**Deliverable**: Commit message:
```
refactor(survey): move MG classifier to examples/ (Phase 5.5-A+B)

BREAKING CHANGE: MG classification removed from broker/

- Moved mg_classifier.py to examples/multi_agent/survey/
- Removed MG imports from agent_initializer.py
- Removed mg_classifier parameter from AgentInitializer
- Updated __init__.py to not export MG classes
- MA scripts must import from examples.multi_agent.survey.mg_classifier

Migration: Use MA-specific initialization wrapper for MG classification

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

---

### Gemini: Phase 5.5-C (Flood Code Removal)
**Estimated**: 2-3 hours
**Risk**: MEDIUM

#### Phase 5.5-C: Remove Flood Helper Functions

**Goal**: Remove flood-specific helper code from agent_initializer.py

1. **Delete _create_flood_extension() function** (~lines 32-42):
   ```python
   # DELETE THIS ENTIRE FUNCTION:
   def _create_flood_extension(flood_experience: bool, financial_loss: bool):
       """DEPRECATION BRIDGE: Create flood extension (MA-specific)."""
       from types import SimpleNamespace
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

2. **Update _create_extensions() method**:
   ```python
   # BEFORE:
   def _create_extensions(self, record) -> Dict[str, Any]:
       extensions = {}
       if hasattr(record, "flood_experience") and hasattr(record, "financial_loss"):
           extensions["flood"] = _create_flood_extension(
               record.flood_experience,
               record.financial_loss
           )
       return extensions

   # AFTER:
   def _create_extensions(self, record) -> Dict[str, Any]:
       """Create extensions dict - domain-specific initialization should handle this."""
       # Generic: just return empty dict
       # Domain-specific code can populate extensions after initialization
       return {}
   ```

3. **Remove/Update enrich_with_hazard() method**:

   Option A - Delete entirely (if only used by MA):
   ```python
   # DELETE enrich_with_hazard() method entirely
   ```

   Option B - Make generic (if could be reused):
   ```python
   def enrich_with_position(self, profiles, position_enricher):
       """Generic position enrichment (domain-agnostic)."""
       # Generic version that doesn't assume "flood" key
   ```

4. **Remove flood stats from load_from_survey()**:
   ```python
   # DELETE this line from stats:
   "flood_experience_count": sum(1 for p in profiles if _get_ext_value(p.extensions.get("flood"), "flood_experience", False)),
   ```

5. **Update docstrings** to remove MA references:
   ```python
   # BEFORE: "Integrates survey loading, MG classification, position assignment..."
   # AFTER:  "Integrates survey loading and profile initialization..."
   ```

6. **Test that generic usage still works**:
   ```python
   # Create test to verify agent_initializer works without MA-specific code
   from broker.modules.survey.agent_initializer import AgentInitializer
   from broker.modules.survey.survey_loader import SurveyRecord

   # Should work with generic records
   initializer = AgentInitializer()
   # ... test basic functionality
   ```

**Deliverable**: Commit message:
```
refactor(survey): remove flood helper functions from agent_initializer (Phase 5.5-C)

- Deleted _create_flood_extension() function
- Made _create_extensions() generic (returns empty dict)
- Removed/updated enrich_with_hazard() method
- Removed flood stats from output
- Updated docstrings to be domain-agnostic

Domain-specific initialization should be handled in examples/

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

---

## MA-Specific Initialization Wrapper (Both)

**After cleanup, MA code needs new initialization path.**

### Create: examples/multi_agent/survey/ma_initializer.py

```python
"""
MA-specific agent initialization wrapper.

Uses generic broker components + MA-specific MG classification and flood setup.
"""

from typing import List, Tuple, Dict, Any, Optional
from pathlib import Path

from broker.modules.survey.agent_initializer import (
    AgentInitializer,
    AgentProfile
)
from broker.modules.survey.survey_loader import SurveyLoader

from .mg_classifier import MGClassifier
from .flood_survey_loader import FloodSurveyLoader


def initialize_ma_agents_from_survey(
    survey_path: Path,
    max_agents: Optional[int] = None,
    seed: int = 42,
    position_enricher = None,
    value_enricher = None,
) -> Tuple[List[AgentProfile], Dict[str, Any]]:
    """
    Initialize MA agents with MG classification and flood extensions.

    This is the MA-specific version that adds:
    - MG (Marginalized Group) classification
    - Flood experience data
    - Flood zone assignment
    - RCV (Replacement Cost Value) generation
    """

    # Use FloodSurveyLoader to get records with flood fields
    loader = FloodSurveyLoader()
    records = loader.load(survey_path, max_records=max_agents)

    # Use generic initializer (no MG classifier)
    initializer = AgentInitializer(survey_loader=loader, seed=seed)

    # Classify MG status for each record
    mg_classifier = MGClassifier()

    profiles = []
    mg_count = 0

    for record in records:
        # MG classification
        mg_result = mg_classifier.classify(record)

        # Create profile with MG data
        profile = AgentProfile(
            agent_id=f"H{len(profiles)+1:04d}",
            record_id=record.record_id,
            family_size=record.family_size,
            generations=record.generations,
            income_bracket=record.income_bracket,
            income_midpoint=loader.get_income_midpoint(record.income_bracket),
            housing_status=record.housing_status,
            house_type=record.house_type,
            is_mg=mg_result.is_mg,
            mg_score=mg_result.score,
            mg_criteria=mg_result.criteria,
            has_children=record.has_children,
            has_elderly=record.elderly_over_65,
            has_vulnerable_members=record.has_vulnerable_members,
            raw_data=record.raw_data,
        )

        # Add flood extension
        from types import SimpleNamespace
        flood_ext = SimpleNamespace(
            flood_experience=record.flood_experience,
            financial_loss=record.financial_loss,
            flood_zone="unknown",
            base_depth_m=0.0,
            flood_probability=0.0,
            building_rcv_usd=0.0,
            contents_rcv_usd=0.0,
        )
        profile.extensions["flood"] = flood_ext

        profiles.append(profile)
        if mg_result.is_mg:
            mg_count += 1

    # Enrich with position data if provided
    if position_enricher:
        for profile in profiles:
            position = position_enricher.assign_position(profile)
            flood_ext = profile.extensions["flood"]
            flood_ext.flood_zone = position.zone_name
            flood_ext.base_depth_m = position.base_depth_m
            flood_ext.flood_probability = position.flood_probability

    # Enrich with RCV if provided
    if value_enricher:
        for profile in profiles:
            values = value_enricher.generate(
                profile.income_bracket,
                profile.is_owner,
                profile.is_mg,
                profile.family_size
            )
            flood_ext = profile.extensions["flood"]
            flood_ext.building_rcv_usd = values.building_rcv_usd
            flood_ext.contents_rcv_usd = values.contents_rcv_usd

    # Statistics
    stats = {
        "total_agents": len(profiles),
        "mg_count": mg_count,
        "nmg_count": len(profiles) - mg_count,
        "mg_ratio": mg_count / len(profiles) if profiles else 0,
        "owner_count": sum(1 for p in profiles if p.is_owner),
        "renter_count": sum(1 for p in profiles if not p.is_owner),
        "flood_experience_count": sum(1 for p in profiles if p.extensions.get("flood").flood_experience),
    }

    return profiles, stats
```

### Update examples/multi_agent/run_unified_experiment.py:

```python
# OLD:
from broker.modules.survey import initialize_agents_from_survey

# NEW:
from examples.multi_agent.survey.ma_initializer import initialize_ma_agents_from_survey as initialize_agents_from_survey
```

---

## Critical Requirements

### For Both Gemini & Codex:

1. **Coordinate Work**: Codex does 5.5-A+B first, then Gemini does 5.5-C
2. **Test After Each Phase**: Run imports and basic tests
3. **Update MA Scripts**: Ensure run_unified_experiment.py still works
4. **Commit Separately**: One commit per phase for easy rollback
5. **Document Breaking Changes**: Note in commit messages

### Testing Checklist:

**Codex (after 5.5-A+B)**:
- [ ] mg_classifier.py imports successfully from examples/
- [ ] broker/modules/survey/__init__.py has no MG exports
- [ ] agent_initializer.py has no MG imports
- [ ] MA scripts can import from new location
- [ ] Unit tests pass

**Gemini (after 5.5-C)**:
- [ ] agent_initializer.py has no flood helper functions
- [ ] _create_extensions() returns empty dict
- [ ] Generic initialization works
- [ ] MA wrapper (ma_initializer.py) created
- [ ] MA experiment runs successfully

**Final Verification**:
```bash
# Should return ONLY deprecation bridge comments (if any):
grep -r "flood\|MG\|Marginalized" broker/modules/survey/ --include="*.py" | grep -v "# " | grep -v '"""'

# Expected: Empty or only harmless references
```

---

## Success Criteria

✅ Sprint 5.5 complete when:
1. mg_classifier.py in examples/multi_agent/survey/
2. agent_initializer.py has no MG references
3. agent_initializer.py has no flood helper functions
4. broker/modules/survey/__init__.py clean
5. Grep audit passes: no MG/flood code in broker/modules/survey/
6. MA experiments still work with new ma_initializer.py
7. All commits merged to main

---

## After Sprint 5.5

**Then Sprint 6 can proceed**:
- Regression testing
- Grep audit (will now pass)
- Documentation
- Migration guide

---

## Reference Files

- [task-029-pollution-assessment.md](.tasks/handoff/task-029-pollution-assessment.md) - Full problem analysis
- [task-029-sprint5-summary.md](.tasks/handoff/task-029-sprint5-summary.md) - What Sprint 5 did
- [elegant-honking-harbor.md](C:\Users\wenyu\.claude\plans\elegant-honking-harbor.md) - Master plan

---

## Questions or Blockers?

Report to: User (wenyu) or Claude Sonnet 4.5

**This is URGENT and blocks Sprint 6**
