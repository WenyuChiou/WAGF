# Task-029 Sprint 5: Survey Module Restructuring
## Assignment for Gemini & Codex

**Date**: 2026-01-21
**Status**: Ready for Assignment
**Priority**: HIGH
**Risk**: MEDIUM-HIGH

---

## Context

Task-029 is cleaning MA (Multi-Agent flood simulation) pollution from the generic broker framework. **Sprints 1-4 are complete** (commit: 52fc63c). Sprint 5 addresses two critical issues discovered during comprehensive audit:

- **C5**: `broker/modules/survey/survey_loader.py` is entirely MA-specific (should move to examples/)
- **C6**: `AgentProfile` dataclass contains MA-specific fields (should use extensions pattern)

---

## Sprint 5 Overview

**Objective**: Extract MA-specific survey code from broker/ to examples/multi_agent/

**Estimated Time**: 6-8 hours
**Risk Level**: MEDIUM-HIGH (impacts core data structures)

---

## Task Assignment

### Gemini: Phase 5A + 5B (CSV Loader & File Relocation)
**Estimated**: 3-4 hours
**Risk**: LOW-MEDIUM

#### Phase 5A: Extract Generic CSV Loader

1. **Create**: `broker/utils/csv_loader.py`
   - Generic CSV parsing with flexible column mapping
   - No domain assumptions
   - Signature:
     ```python
     def load_csv_with_mapping(
         csv_path: str,
         column_mapping: Dict[str, Dict],
         required_fields: List[str]
     ) -> pd.DataFrame:
         """Generic CSV loader with flexible column mapping."""
     ```

2. **Extract logic from**: `broker/modules/survey/survey_loader.py`
   - Pure CSV parsing (no flood references)
   - Column index/code mapping
   - Validation logic

3. **Write unit tests**: `tests/test_csv_loader.py`
   - Test column mapping
   - Test required field validation
   - Test error handling

#### Phase 5B: Relocate MA-Specific Code

1. **Create directory**: `examples/multi_agent/survey/`

2. **Create**: `examples/multi_agent/survey/flood_survey_loader.py`
   - Import from `broker.utils.csv_loader`
   - Define `FLOOD_SURVEY_MAPPING` (hardcoded MA columns)
   - Wrapper function: `load_flood_survey(csv_path)`

3. **Update all imports**:
   - Find: `from broker.modules.survey.survey_loader import`
   - Replace: `from examples.multi_agent.survey.flood_survey_loader import`
   - Files to check:
     - `examples/multi_agent/run_unified_experiment.py`
     - `examples/multi_agent/*.py`
     - Any scripts in `examples/multi_agent/`

4. **Delete**: `broker/modules/survey/survey_loader.py` (after confirming no imports remain)

5. **Test**: Run MA experiment (quick 1-year test)
   ```bash
   cd examples/multi_agent
   python run_unified_experiment.py --years 1 --agents 5 --model gemma3:4b --output test_phase5b/
   ```

**Deliverable**: Commit message:
```
refactor(survey): extract MA-specific survey loader to examples (Phase 5A+5B)

- Created generic broker/utils/csv_loader.py
- Moved survey_loader.py → examples/multi_agent/survey/flood_survey_loader.py
- Updated all imports in examples/multi_agent/
- Tests: Unit tests passing, MA experiment runs successfully
```

---

### Codex: Phase 5C (AgentProfile Refactoring)
**Estimated**: 3-4 hours
**Risk**: HIGH (core data structure)

#### Phase 5C: Refactor AgentProfile Extensions Pattern

1. **Read current structure**: `broker/modules/survey/agent_initializer.py`
   - Current AgentProfile has MA fields: `flood_zone`, `base_depth_m`, `flood_probability`, `building_rcv_usd`, `contents_rcv_usd`, `flood_experience`, `financial_loss`

2. **Refactor AgentProfile** in `broker/modules/survey/agent_initializer.py`:
   ```python
   from dataclasses import dataclass, field
   from typing import Dict, Any

   @dataclass
   class AgentProfile:
       """Generic agent profile from survey data."""
       agent_id: str
       family_size: int
       income_bracket: str
       housing_status: str
       is_mg: bool
       tenure: str  # Owner/Renter
       # Extensible domain-specific data
       extensions: Dict[str, Any] = field(default_factory=dict)
   ```

3. **Create**: `examples/multi_agent/survey/flood_profile.py`
   ```python
   from dataclasses import dataclass

   @dataclass
   class FloodExposureProfile:
       """MA-specific flood exposure data."""
       flood_zone: str
       base_depth_m: float
       flood_probability: float
       building_rcv_usd: float
       contents_rcv_usd: float
       flood_experience: bool
       financial_loss: float
   ```

4. **Update enrichers** to use `profile.extensions["flood"]`:
   - `examples/multi_agent/environment/depth_sampler.py`:
     - Read from `profile.extensions.get("flood")` if available
     - Create and store FloodExposureProfile in `profile.extensions["flood"]`

   - `examples/multi_agent/environment/rcv_generator.py`:
     - Similar pattern: read/write to `profile.extensions["flood"]`

5. **Update initialization code** in `examples/multi_agent/run_unified_experiment.py`:
   - After `initialize_agents_from_survey()`, populate `profile.extensions["flood"]`
   - Example:
     ```python
     from examples.multi_agent.survey.flood_profile import FloodExposureProfile

     for profile in profiles:
         # Create flood extension
         flood_data = FloodExposureProfile(
             flood_zone=profile.flood_zone,  # migrate from old fields
             base_depth_m=profile.base_depth_m,
             # ... etc
         )
         profile.extensions["flood"] = flood_data
     ```

6. **Full regression test**:
   ```bash
   cd examples/multi_agent
   python run_unified_experiment.py --years 3 --agents 5 --model gemma3:4b --output test_phase5c/
   ```
   - Verify: No attribute errors
   - Verify: Flood events trigger correctly
   - Verify: Metrics match baseline (within 5% tolerance)

**Deliverable**: Commit message:
```
refactor(survey): use extensions pattern for AgentProfile (Phase 5C)

- Refactored AgentProfile to generic fields + extensions dict
- Created FloodExposureProfile in examples/multi_agent/survey/
- Updated enrichers (DepthSampler, RCVGenerator) to use extensions
- Full regression test passed (3 years, 5 agents)
```

---

## Critical Requirements

### For Both Gemini & Codex:

1. **Backward Compatibility**: Ensure existing MA experiments still work
2. **Test Before Commit**: Run at least a quick MA experiment (1-3 years, 5 agents)
3. **No SA Impact**: Single-agent experiments must not be affected
4. **Documentation**: Update docstrings to be generic
5. **Commit Format**: Use format above with Co-Authored-By line:
   ```
   Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
   ```

### Coordination:

- **Gemini completes Phase 5A+5B first** → Commit
- **Then Codex starts Phase 5C** (depends on 5B being done)
- **Both**: Update `.tasks/handoff/current-session.md` after your commit

---

## Testing Checklist

### Gemini (Phase 5A+5B):
- [ ] Unit tests for csv_loader pass
- [ ] No imports remain for old survey_loader
- [ ] MA experiment runs (1 year, 5 agents)
- [ ] No import errors during run

### Codex (Phase 5C):
- [ ] AgentProfile has no MA-specific fields
- [ ] FloodExposureProfile created in examples/
- [ ] Enrichers use profile.extensions["flood"]
- [ ] MA experiment runs (3 years, 5 agents)
- [ ] Flood events trigger correctly
- [ ] No AttributeError for flood fields
- [ ] Metrics within 5% of baseline

---

## Reference Files

**Read these first**:
- [.tasks/handoff/current-session.md](.tasks/handoff/current-session.md) - Current progress
- [.tasks/handoff/task-029.md](.tasks/handoff/task-029.md) - Full task details
- [C:\Users\wenyu\.claude\plans\elegant-honking-harbor.md](C:\Users\wenyu\.claude\plans\elegant-honking-harbor.md) - Master plan

**Key files to modify**:
- Gemini: `broker/utils/csv_loader.py` (new), `examples/multi_agent/survey/flood_survey_loader.py` (new)
- Codex: `broker/modules/survey/agent_initializer.py`, `examples/multi_agent/survey/flood_profile.py` (new), `examples/multi_agent/environment/*.py`

---

## Success Criteria

✅ Sprint 5 complete when:
1. All tests passing
2. MA experiment runs without errors (3 years minimum)
3. No hardcoded MA concepts in `broker/modules/survey/`
4. Grep audit clean: `grep -r "flood_zone\|base_depth_m" broker/` returns empty
5. Both commits merged to main

---

## Questions or Blockers?

Report to: User (wenyu) or Claude Sonnet 4.5 session

**Previous work**: Sprints 1-4 complete (commits: e00dc5f, 78d692c, 4d19a8e, 52fc63c)
