# Task-029 Sprint 6: Final Verification & Documentation
## Assignment for Gemini & Codex

**Date**: 2026-01-21
**Status**: Ready for Assignment
**Priority**: HIGH
**Risk**: LOW-MEDIUM

---

## Context

Task-029 Sprints 1-5 are **COMPLETE** ✅:
- Sprint 1-4: Documentation cleanup, Protocol refactoring, Config-driven logic (commits: e00dc5f, 78d692c, 4d19a8e, 52fc63c)
- Sprint 5: Survey module restructuring (commits: 24f2686, 0a1f43f, f07fedf, 04341ad)

Sprint 6 is the **final verification and documentation phase** before releasing v0.30.

---

## Sprint 6 Overview

**Objective**: Verify framework genericity, document architecture changes, and prepare v0.30 release.

**Estimated Time**: 6-8 hours total
**Risk Level**: LOW-MEDIUM

---

## Task Assignment

### Gemini: Phase 6A + 6B (Verification & Audit)
**Estimated**: 3-4 hours
**Risk**: MEDIUM

#### Phase 6A: Full Regression Test

**Goal**: Verify MA experiments still work after all refactoring.

1. **Run baseline test** (if not already captured):
   ```bash
   cd examples/multi_agent
   python run_unified_experiment.py \
     --years 5 \
     --agents 10 \
     --model gemma3:4b \
     --output ../../results/task029_baseline/ \
     --mode survey
   ```
   - Capture metrics: adaptation rates, memory counts, reflection counts
   - Save as `task029_baseline_metrics.json`

2. **Run verification test**:
   ```bash
   python run_unified_experiment.py \
     --years 5 \
     --agents 10 \
     --model gemma3:4b \
     --output ../../results/task029_verification/ \
     --mode survey
   ```

3. **Compare results**:
   - Adaptation rates within 5% tolerance
   - Memory consolidation counts similar
   - Reflection insight counts similar
   - No crashes or errors

4. **Document findings** in `.tasks/handoff/task-029-regression-report.md`:
   ```markdown
   # Task-029 Regression Test Report

   ## Test Configuration
   - Years: 5
   - Agents: 10
   - Model: gemma3:4b

   ## Results
   | Metric | Baseline | After Refactor | Delta | Status |
   |:-------|:---------|:---------------|:------|:-------|
   | Elevated rate | X% | Y% | Z% | ✅/❌ |
   | Insured rate | ... | ... | ... | ... |

   ## Conclusion
   [PASS/FAIL with explanation]
   ```

#### Phase 6B: Comprehensive Grep Audit

**Goal**: Confirm no MA-specific hardcoding remains in broker/.

1. **Run audit commands**:
   ```bash
   # Flood-specific terms
   grep -r "flood\|buyout\|elevation\|nfip" broker/ \
     --include="*.py" \
     --exclude-dir=__pycache__ \
     | grep -v "# " | grep -v '"""' | grep -v "DEPRECATION BRIDGE"

   # Household-specific terms
   grep -r "household_owner\|household_mg" broker/ \
     --include="*.py" \
     --exclude-dir=__pycache__ \
     | grep -v "# " | grep -v '"""'

   # MA-specific field names
   grep -r "flood_zone\|base_depth_m\|flood_experience\|financial_loss" broker/ \
     --include="*.py" \
     --exclude-dir=__pycache__ \
     | grep -v "# " | grep -v '"""' | grep -v "DEPRECATION BRIDGE"
   ```

2. **Analyze results**:
   - Exceptions allowed:
     - Protocol definitions in `broker/interfaces/enrichment.py`
     - DEPRECATION BRIDGE marked code in `agent_initializer.py`
     - Comments and docstrings
   - Any other occurrences: investigate and fix or document

3. **Create audit report** in `.tasks/handoff/task-029-audit-report.md`:
   ```markdown
   # Task-029 Grep Audit Report

   ## Audit Date
   2026-01-21

   ## Commands Run
   [List of grep commands]

   ## Findings
   ### Acceptable Occurrences
   - broker/interfaces/enrichment.py: Protocol definitions ✅
   - broker/modules/survey/agent_initializer.py: DEPRECATION BRIDGE ✅

   ### Issues Found
   [List any unexpected MA hardcoding]

   ## Status
   PASS ✅ / FAIL ❌
   ```

**Deliverable**: Commit message:
```
test(task-029): verify regression and audit MA pollution removal (Phase 6A+6B)

- Ran 5-year MA experiment: baseline vs refactored comparison
- All metrics within 5% tolerance
- Grep audit confirms no unexpected MA hardcoding
- Documented findings in regression-report.md and audit-report.md
```

---

### Codex: Phase 6C + 6D (Documentation)
**Estimated**: 3-4 hours
**Risk**: LOW

#### Phase 6C: Update ARCHITECTURE.md

**Goal**: Document new architectural patterns introduced in Task-029.

1. **Read existing** [ARCHITECTURE.md](../../ARCHITECTURE.md) (if exists) or create new

2. **Add section: "Domain-Agnostic Design Patterns"**:
   ```markdown
   ## Domain-Agnostic Design Patterns (v0.29+)

   ### 1. Protocol-Based Dependency Injection

   **Problem**: broker/modules/survey/ was importing from examples/multi_agent/

   **Solution**: PEP 544 Protocols define interfaces without implementation coupling.

   ```python
   # broker/interfaces/enrichment.py
   class PositionEnricher(Protocol):
       def assign_position(self, profile) -> PositionData: ...

   # examples/multi_agent/environment/depth_sampler.py
   class DepthSampler:  # Implicitly implements PositionEnricher
       def assign_position(self, profile) -> PositionData:
           # MA-specific flood zone assignment
   ```

   ### 2. Extensions Pattern for Domain-Specific Data

   **Problem**: SurveyRecord and AgentProfile contained MA-specific fields.

   **Solution**: Generic base classes + domain-specific extensions.

   ```python
   # broker/modules/survey/survey_loader.py
   @dataclass
   class SurveyRecord:
       family_size: int
       income_bracket: str
       # No flood fields ✅

   # examples/multi_agent/survey/flood_survey_loader.py
   @dataclass
   class FloodSurveyRecord(SurveyRecord):
       flood_experience: bool  # Domain extension
       financial_loss: bool
   ```

   ### 3. Config-Driven Domain Logic

   **Problem**: Memory tags hardcoded as "MG" → "subsidy".

   **Solution**: Load tags from agent_types.yaml.

   ```yaml
   # examples/multi_agent/ma_agent_types.yaml
   household_mg:
     memory:
       retrieval_tags: ["subsidy", "vulnerability"]
   ```
   ```

3. **Add section: "Migration from v0.28 to v0.29"**:
   - Summarize breaking changes (if any)
   - Provide migration examples
   - Reference task-029-migration-guide.md

4. **Update diagrams** (if applicable):
   - Show broker/ → examples/ separation
   - Illustrate Protocol usage

#### Phase 6D: Create Migration Guide

**Goal**: Help users migrate from v0.28 → v0.29.

1. **Create** `.tasks/handoff/task-029-migration-guide.md`:
   ```markdown
   # Migration Guide: v0.28 → v0.29 (Task-029)

   ## Overview

   Task-029 removed MA-specific pollution from the broker framework.
   If you built on top of broker/ assuming flood-specific APIs, follow this guide.

   ---

   ## Breaking Changes

   ### 1. SurveyRecord No Longer Has Flood Fields

   **Before (v0.28)**:
   ```python
   from broker.modules.survey.survey_loader import SurveyRecord

   record = loader.load(survey_path)[0]
   if record.flood_experience:  # ❌ AttributeError in v0.29
       ...
   ```

   **After (v0.29)**:
   ```python
   from examples.multi_agent.survey.flood_survey_loader import FloodSurveyRecord

   record = loader.load(survey_path)[0]
   if record.flood_experience:  # ✅ Works with FloodSurveyRecord
       ...
   ```

   **Fix**: Use `FloodSurveyLoader` instead of generic `SurveyLoader`.

   ---

   ### 2. AgentProfile Uses Extensions Dict

   **Before (v0.28)**:
   ```python
   profile.flood_zone  # ❌ AttributeError in v0.29
   ```

   **After (v0.29)**:
   ```python
   flood_ext = profile.extensions.get("flood")
   if flood_ext:
       zone = flood_ext.flood_zone  # ✅
   ```

   **Fix**: Access domain-specific data via `profile.extensions["domain"]`.

   ---

   ## Non-Breaking Changes

   ### 1. Enrichment Protocols (Backward Compatible)

   Old import path still works via deprecation bridge:
   ```python
   # Still works in v0.29 (deprecated in v0.30)
   from broker.modules.survey.agent_initializer import initialize_agents_from_survey

   profiles, stats = initialize_agents_from_survey(
       survey_path,
       include_hazard=True  # Deprecated parameter
   )
   ```

   New protocol-based approach:
   ```python
   from examples.multi_agent.environment.depth_sampler import DepthSampler

   profiles, stats = initialize_agents_from_survey(
       survey_path,
       position_enricher=DepthSampler(seed=42)  # ✅ New API
   )
   ```

   ---

   ## Deprecation Warnings

   Code marked with `DEPRECATION BRIDGE` will be removed in v0.30:
   - `_create_flood_extension()` in agent_initializer.py
   - `include_hazard` parameter in initialize_agents_from_survey()

   Plan to migrate before v0.30.

   ---

   ## Testing Your Migration

   Run your existing tests after upgrading:
   ```bash
   pytest tests/ -v
   ```

   If you see `AttributeError` for flood fields, apply fixes above.
   ```

2. **Add examples** for common migration scenarios

3. **Link from ARCHITECTURE.md**

**Deliverable**: Commit message:
```
docs(task-029): add architecture guide and migration docs (Phase 6C+6D)

- Updated ARCHITECTURE.md with domain-agnostic patterns
- Created migration guide (v0.28 → v0.29)
- Documented Protocol usage, Extensions pattern, Config-driven logic
- Added examples for common migration scenarios
```

---

## Critical Requirements

### For Both Gemini & Codex:

1. **Verify No Breakage**: Existing MA experiments must work
2. **Document Thoroughly**: Clear examples for all patterns
3. **Follow Style**: Use project's existing documentation style
4. **Commit Format**: Include Co-Authored-By line:
   ```
   Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
   ```

### Coordination:

- **Gemini starts Phase 6A+6B** (verification) → Commit
- **Codex starts Phase 6C+6D** (documentation) after 6A/6B done
- **Both**: Update `.tasks/handoff/current-session.md` after commit

---

## Testing Checklist

### Gemini (Phase 6A+6B):
- [ ] Baseline test runs successfully (5 years, 10 agents)
- [ ] Verification test runs successfully
- [ ] Metrics within 5% tolerance
- [ ] Grep audit shows only expected exceptions
- [ ] Reports created and committed

### Codex (Phase 6C+6D):
- [ ] ARCHITECTURE.md updated with new patterns
- [ ] Migration guide created with examples
- [ ] Documentation is clear and complete
- [ ] Links between docs work correctly
- [ ] Committed with proper message

---

## Reference Files

**Read these first**:
- [.tasks/handoff/current-session.md](.tasks/handoff/current-session.md) - Current status
- [.tasks/handoff/task-029-sprint5-summary.md](.tasks/handoff/task-029-sprint5-summary.md) - Sprint 5 work
- [C:\Users\wenyu\.claude\plans\elegant-honking-harbor.md](C:\Users\wenyu\.claude\plans\elegant-honking-harbor.md) - Master plan

**Key files to reference**:
- Gemini: `examples/multi_agent/run_unified_experiment.py`
- Codex: Existing `ARCHITECTURE.md` or similar docs

---

## Success Criteria

✅ Sprint 6 complete when:
1. Regression test passes (metrics within 5% tolerance)
2. Grep audit clean (only expected exceptions)
3. ARCHITECTURE.md documents new patterns
4. Migration guide helps users upgrade
5. Both commits merged to main

---

## Final Steps (After Both Complete)

**User or Claude Code**:
1. Review all Sprint 6 work
2. Tag release: `git tag v0.29.0 -m "Task-029: MA Pollution Remediation Complete"`
3. Update CHANGELOG.md with v0.29 release notes
4. Close Task-029 in registry
5. Create Task-030 for v0.30 cleanup (remove deprecation bridges)

---

## Questions or Blockers?

Report to: User (wenyu) or Claude Sonnet 4.5 session

**Previous work**:
- Sprints 1-4 complete (commits: e00dc5f, 78d692c, 4d19a8e, 52fc63c)
- Sprint 5 complete (commits: 24f2686, 0a1f43f, f07fedf, 04341ad)
