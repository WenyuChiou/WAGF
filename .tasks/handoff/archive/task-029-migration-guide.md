# Migration Guide: v0.28 → v0.29 (Task-029)

## Overview

Task-029 removed MA-specific pollution from the broker framework, making it truly domain-agnostic.

If you built on top of `broker/` assuming flood-specific APIs, follow this guide to migrate.

---

## Summary of Changes

| Component | v0.28 (Old) | v0.29 (New) |
|:----------|:------------|:------------|
| SurveyRecord | Had `flood_experience`, `financial_loss` | Generic - no flood fields |
| AgentProfile | Had flood fields directly | Uses `extensions` dict |
| AgentInitializer | Had `mg_classifier` param | Generic - no MG integration |
| Enrichers | `include_hazard=True` | `position_enricher=DepthSampler()` |
| Memory tags | Hardcoded "MG" → "subsidy" | Config-driven from YAML |

---

## Breaking Changes

### 1. SurveyRecord No Longer Has Flood Fields

**Before (v0.28)**:
```python
from broker.modules.survey.survey_loader import SurveyLoader

loader = SurveyLoader()
records = loader.load(survey_path)

# This worked in v0.28:
for record in records:
    if record.flood_experience:  # ❌ AttributeError in v0.29!
        print("Has flood experience")
```

**After (v0.29)**:
```python
# Option 1: Use FloodSurveyLoader for MA
from examples.multi_agent.survey.flood_survey_loader import FloodSurveyLoader

loader = FloodSurveyLoader()
records = loader.load(survey_path)

for record in records:
    if record.flood_experience:  # ✅ Works - FloodSurveyRecord has this field
        print("Has flood experience")
```

```python
# Option 2: Use generic loader if you don't need flood fields
from broker.modules.survey.survey_loader import SurveyLoader

loader = SurveyLoader()
records = loader.load(survey_path)

# Access only generic fields:
for record in records:
    print(f"Family size: {record.family_size}")
    print(f"Income: {record.income_bracket}")
```

---

### 2. AgentProfile Uses Extensions Dict

**Before (v0.28)**:
```python
# These fields existed directly on AgentProfile:
print(profile.flood_zone)       # ❌ AttributeError in v0.29
print(profile.base_depth_m)     # ❌ AttributeError in v0.29
print(profile.flood_experience) # ❌ AttributeError in v0.29
```

**After (v0.29)**:
```python
# Access via extensions dict:
flood_ext = profile.extensions.get("flood")
if flood_ext:
    print(flood_ext.flood_zone)        # ✅
    print(flood_ext.base_depth_m)      # ✅
    print(flood_ext.flood_experience)  # ✅
```

**Helper function**:
```python
def get_flood_value(profile, key, default=None):
    """Safely get flood extension value."""
    flood = profile.extensions.get("flood")
    if flood is None:
        return default
    if hasattr(flood, key):
        return getattr(flood, key)
    if isinstance(flood, dict):
        return flood.get(key, default)
    return default

# Usage:
zone = get_flood_value(profile, "flood_zone", "unknown")
```

---

### 3. AgentInitializer No Longer Has mg_classifier

**Before (v0.28)**:
```python
from broker.modules.survey.agent_initializer import AgentInitializer
from broker.modules.survey.mg_classifier import MGClassifier  # ❌ Moved!

initializer = AgentInitializer(
    mg_classifier=MGClassifier()  # ❌ Parameter removed!
)
```

**After (v0.29)**:
```python
# Option 1: Use MA-specific initializer
from examples.multi_agent.survey.ma_initializer import (
    MAAgentInitializer,
    initialize_ma_agents_from_survey
)

# Includes MG classification automatically
profiles, stats = initialize_ma_agents_from_survey(survey_path)

# Or use class directly:
from examples.multi_agent.survey.mg_classifier import MGClassifier
initializer = MAAgentInitializer(mg_classifier=MGClassifier())
```

```python
# Option 2: Use generic initializer (no MG classification)
from broker.modules.survey import initialize_agents_from_survey

profiles, stats = initialize_agents_from_survey(survey_path)
# profiles will have is_classified=False, classification_score=0
```

---

### 4. Enrichment API Changed

**Before (v0.28)** - Deprecated parameters:
```python
profiles, stats = initialize_agents_from_survey(
    survey_path,
    include_hazard=True,  # ❌ Deprecated - will be removed in v0.30
    include_rcv=True      # ❌ Deprecated - will be removed in v0.30
)
```

**After (v0.29)** - Protocol-based API:
```python
from examples.multi_agent.environment.depth_sampler import DepthSampler
from examples.multi_agent.environment.rcv_generator import RCVGenerator

profiles, stats = initialize_agents_from_survey(
    survey_path,
    position_enricher=DepthSampler(seed=42),  # ✅ New API
    value_enricher=RCVGenerator(seed=42)      # ✅ New API
)
```

---

## Non-Breaking Changes (Backward Compatible)

### 1. is_mg Property Still Works

The `is_mg`, `mg_score`, and `mg_criteria` properties are still available as aliases:

```python
# Both work in v0.29:
if profile.is_classified:  # New generic name
    print("Classified")

if profile.is_mg:  # Old name, still works
    print("Classified (MG)")
```

**Note**: These aliases may be removed in v0.31. Plan to migrate to generic names.

### 2. Generic Statistics

v0.29 statistics are more generic:

```python
# v0.28 stats included:
# - mg_count, nmg_count, mg_ratio
# - flood_experience_count

# v0.29 generic stats:
stats = {
    "total_agents": 100,
    "owner_count": 60,
    "renter_count": 40,
    "validation_errors": 0
}

# For MA stats, use ma_initializer:
from examples.multi_agent.survey.ma_initializer import initialize_ma_agents_from_survey

profiles, stats = initialize_ma_agents_from_survey(survey_path)
# stats now includes: mg_count, nmg_count, flood_experience_count
```

---

## Deprecation Warnings

Code marked for removal in v0.30:

| Item | Location | Replacement |
|:-----|:---------|:------------|
| `include_hazard` param | `initialize_agents_from_survey()` | Use `position_enricher` |
| `include_rcv` param | `initialize_agents_from_survey()` | Use `value_enricher` |
| `is_mg` alias | `AgentProfile` | Use `is_classified` |
| `mg_score` alias | `AgentProfile` | Use `classification_score` |
| `mg_criteria` alias | `AgentProfile` | Use `classification_criteria` |

Plan to migrate before v0.30.

---

## Quick Migration Checklist

### For MA Flood Simulation Users

- [ ] Change `from broker.modules.survey.mg_classifier import MGClassifier`
      → `from examples.multi_agent.survey.mg_classifier import MGClassifier`

- [ ] Change `SurveyLoader()` → `FloodSurveyLoader()` if you need flood fields

- [ ] Change `include_hazard=True` → `position_enricher=DepthSampler(seed=42)`

- [ ] Change `include_rcv=True` → `value_enricher=RCVGenerator(seed=42)`

- [ ] Access flood fields via `profile.extensions["flood"].field_name`

- [ ] Or use `initialize_ma_agents_from_survey()` which handles everything

### For Generic Framework Users

- [ ] No changes needed for generic survey loading
- [ ] Use `profile.extensions[domain]` pattern for domain-specific data
- [ ] Implement your own enrichers satisfying Protocol interfaces

---

## Testing Your Migration

```bash
# Run your existing tests
pytest tests/ -v

# Common errors and fixes:

# AttributeError: 'SurveyRecord' object has no attribute 'flood_experience'
# Fix: Use FloodSurveyLoader or FloodSurveyRecord

# AttributeError: 'AgentProfile' object has no attribute 'flood_zone'
# Fix: Access via profile.extensions["flood"].flood_zone

# TypeError: initialize_agents_from_survey() got unexpected keyword argument 'mg_classifier'
# Fix: Use MAAgentInitializer or remove mg_classifier param
```

---

## Full MA Migration Example

**Before (v0.28)**:
```python
from broker.modules.survey.survey_loader import SurveyLoader
from broker.modules.survey.agent_initializer import AgentInitializer
from broker.modules.survey.mg_classifier import MGClassifier

loader = SurveyLoader()
initializer = AgentInitializer(
    survey_loader=loader,
    mg_classifier=MGClassifier()
)

profiles, stats = initializer.load_from_survey(survey_path)
initializer.enrich_with_hazard(profiles, depth_sampler)
initializer.enrich_with_rcv(profiles, rcv_generator)

for profile in profiles:
    print(f"Agent {profile.agent_id}:")
    print(f"  MG: {profile.is_mg}")
    print(f"  Zone: {profile.flood_zone}")
    print(f"  RCV: ${profile.building_rcv_usd:,.0f}")
```

**After (v0.29)**:
```python
from examples.multi_agent.survey.ma_initializer import initialize_ma_agents_from_survey
from examples.multi_agent.environment.depth_sampler import DepthSampler
from examples.multi_agent.environment.rcv_generator import RCVGenerator

profiles, stats = initialize_ma_agents_from_survey(
    survey_path,
    position_enricher=DepthSampler(seed=42),
    value_enricher=RCVGenerator(seed=42)
)

for profile in profiles:
    flood = profile.extensions["flood"]
    print(f"Agent {profile.agent_id}:")
    print(f"  MG: {profile.is_mg}")
    print(f"  Zone: {flood.flood_zone}")
    print(f"  RCV: ${flood.building_rcv_usd:,.0f}")
```

---

## Support

If you encounter issues migrating:

1. Check this guide for common fixes
2. Review [ARCHITECTURE.md](../../ARCHITECTURE.md) for design patterns
3. Look at `examples/multi_agent/` for reference implementation
4. Open an issue on GitHub

---

**Migration Guide Version**: v0.29.0
**Last Updated**: 2026-01-21
**Author**: Claude Opus 4.5
