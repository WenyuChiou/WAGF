# Sprint 5.5 Quick Start Guide

**URGENT - BLOCKING SPRINT 6**

---

## Quick Context

**Problem**: Sprint 5 incomplete - MA pollution remains in broker/modules/survey/

**Files to Clean**:
- `broker/modules/survey/mg_classifier.py` (214 lines - move to examples/)
- `broker/modules/survey/agent_initializer.py` (~100 lines MA code - remove)
- `broker/modules/survey/__init__.py` (remove MG exports)

**Goal**: Zero MA concepts in broker/modules/survey/

---

## Codex: Phase 5.5-A+B (3-4 hours) - DO THIS FIRST

### Step 1: Move MG Classifier

```bash
# Create directory
mkdir -p examples/multi_agent/survey

# Move file
git mv broker/modules/survey/mg_classifier.py examples/multi_agent/survey/mg_classifier.py
```

### Step 2: Update imports in mg_classifier.py

```python
# OLD (line ~12):
from .survey_loader import SurveyRecord, INCOME_MIDPOINTS

# NEW:
from broker.modules.survey.survey_loader import SurveyRecord, INCOME_MIDPOINTS
```

### Step 3: Remove MG exports from broker/__init__.py

```python
# broker/modules/survey/__init__.py
# REMOVE these lines:
from .mg_classifier import MGClassifier, PovertyLineTable, MGClassificationResult

__all__ = [
    # ...
    "MGClassifier",  # REMOVE
    "PovertyLineTable",  # REMOVE
    "MGClassificationResult",  # REMOVE
]
```

### Step 4: Remove MG from agent_initializer.py

```python
# Line 23 - DELETE:
from .mg_classifier import MGClassifier, MGClassificationResult

# Lines 108-112 - DELETE mg_classifier parameter:
def __init__(
    self,
    survey_loader: Optional[SurveyLoader] = None,
    mg_classifier: Optional[MGClassifier] = None,  # DELETE THIS
    ...
):
    self.mg_classifier = mg_classifier or MGClassifier()  # DELETE THIS

# Lines 270-290 - DELETE MG classification loop:
mg_result = self.mg_classifier.classify(record)

profile = AgentProfile(
    # ...
    is_mg=mg_result.is_mg,  # DELETE
    mg_score=mg_result.score,  # DELETE
    mg_criteria=mg_result.criteria,  # DELETE
)

if mg_result.is_mg:
    mg_count += 1

# DELETE from stats dict:
"mg_count": mg_count,
"nmg_count": len(profiles) - mg_count,
"mg_ratio": mg_count / len(profiles) if profiles else 0,
```

### Step 5: Update MA scripts

```bash
# Find all imports
grep -r "from broker.modules.survey import.*MGClassifier" examples/multi_agent/
grep -r "from broker.modules.survey.mg_classifier import" examples/multi_agent/
```

Update to:
```python
from examples.multi_agent.survey.mg_classifier import MGClassifier
```

### Step 6: Test

```bash
python -c "from examples.multi_agent.survey.mg_classifier import MGClassifier; print('OK')"
python -m pytest tests/ -v
```

### Commit Message:
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

## Gemini: Phase 5.5-C (2-3 hours) - DO AFTER CODEX

### Step 1: Delete flood extension helper

```python
# broker/modules/survey/agent_initializer.py
# Lines 32-42 - DELETE ENTIRE FUNCTION:
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

### Step 2: Make _create_extensions() generic

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

### Step 3: Remove/update enrich_with_hazard()

Option A - Delete entirely (if only used by MA):
```python
# DELETE enrich_with_hazard() method entirely
```

Option B - Make generic:
```python
def enrich_with_position(self, profiles, position_enricher):
    """Generic position enrichment (domain-agnostic)."""
    # Generic version that doesn't assume "flood" key
```

### Step 4: Remove flood stats

```python
# DELETE this line from stats:
"flood_experience_count": sum(1 for p in profiles if _get_ext_value(p.extensions.get("flood"), "flood_experience", False)),
```

### Step 5: Update docstrings

```python
# BEFORE: "Integrates survey loading, MG classification, position assignment..."
# AFTER:  "Integrates survey loading and profile initialization..."
```

### Step 6: Test

```python
from broker.modules.survey.agent_initializer import AgentInitializer
from broker.modules.survey.survey_loader import SurveyRecord

# Should work with generic records
initializer = AgentInitializer()
# ... test basic functionality
```

### Commit Message:
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

## Both: Create MA-Specific Wrapper

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

### Update: examples/multi_agent/run_unified_experiment.py

```python
# OLD:
from broker.modules.survey import initialize_agents_from_survey

# NEW:
from examples.multi_agent.survey.ma_initializer import initialize_ma_agents_from_survey as initialize_agents_from_survey
```

---

## Final Verification

### Grep Audit (Should be CLEAN):

```bash
# Should return ONLY deprecation bridge comments (if any):
grep -r "flood\|MG\|Marginalized" broker/modules/survey/ --include="*.py" | grep -v "# " | grep -v '"""'

# Expected: Empty or only harmless references
```

### MA Experiment Test:

```bash
cd examples/multi_agent
python run_unified_experiment.py \
  --years 3 \
  --agents 5 \
  --model gemma3:4b \
  --output results_unified/sprint5.5_verification/ \
  --mode survey
```

Expected: Should run successfully with MG classification and flood data.

---

## Success Checklist

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
- [ ] Grep audit passes (no executable MA code in broker/)
- [ ] All tests pass
- [ ] MA experiments work with new architecture
- [ ] All changes committed

---

## Questions or Blockers?

Report to: User (wenyu) or Claude Sonnet 4.5

**This is URGENT and blocks Sprint 6**

---

**Reference**: [task-029-sprint5.5-assignment.md](task-029-sprint5.5-assignment.md) for full details
