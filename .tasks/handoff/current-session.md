# Current Session Handoff

## Last Updated
2026-01-30T01:45:00Z

---

## Current: Task-058 gemma3:1b Parser Bug Fix (Claude Code)

**Status**: COMPLETE (not yet committed)

### Problem: Behavior Collapse in gemma3:1b Group C

gemma3:1b Group C experiment showed **897/1000 elevate_house** decisions, even for already-elevated agents. Root cause analysis (6 layers):

1. **Parser Missing List Case** ¡÷ gemma3:1b outputs `"decision": [2, 3, 4]` (JSON array) instead of single int. The square brackets in template `[Numeric ID: 1, 2, 3, or 4]` mislead the 1b model.
2. **Keyword Fallback Uses Static Map** ¡÷ `_parse_keywords()` called `get_skill_map(agent_type)` WITHOUT context ¡÷ always returns base skill_map where `2=elevate_house`, even for elevated agents whose dynamic map has `2=relocate`.
3. **Template Ambiguity** ¡÷ `response_format.py:139` generates `[Numeric ID: ...]` with brackets.
4. **Model Reasoning Triggers False Match** ¡÷ Reasoning text mentions "elevation" ¡÷ keyword parser catches it.
5. **Appraisal Homogeneity** ¡÷ 86.5% threat = Medium regardless of flood occurrence.
6. **Reflection Echo Chamber** ¡÷ All reflections about "elevation grants" with importance=0.9.

### Fixes Applied

| Priority | Fix | File | Lines |
|----------|-----|------|-------|
| **P0** | List/array decision ¡÷ take first element | `broker/utils/model_adapter.py` | 325-328 |
| **P1** | Pass `context` to `_parse_keywords()` | `broker/utils/model_adapter.py` | 495, 807, 816 |

**P0 code** (line 325):
```python
# Case 0b: List/array (small models like gemma3:1b output [2, 3, 4])
if isinstance(decision_val, list) and decision_val:
    decision_val = decision_val[0]
```

**P1 code** (line 807, 816):
```python
def _parse_keywords(self, text: str, agent_type: str, context: Dict[str, Any] = None):
    ...
    skill_map = self.agent_config.get_skill_map(agent_type, context)
```

### Verification

- Direct parser test: 4/4 cases pass (non-elevated array, elevated array, int, dict)
- Critical fix: Elevated agent with `[2,3]` now correctly maps to `relocate` (was `elevate_house`)
- gemma3:4b confirmed NOT affected (always outputs single integers)
- Full test suite: **901 passed, 0 failed**

### Pending (Optional)

- [ ] P2: Remove square brackets from response template (`response_format.py:139`) ¡÷ preventive for other small models
- [ ] Re-run gemma3:1b experiment to verify fix end-to-end
- [ ] Commit parser fixes to git

---

## Previous: Task-057 Reflection Optimization (Delegated)

**Status**: Phases 1-3 COMPLETE
**Plan**: `C:\Users\wenyu\.claude\plans\peaceful-beaming-peach.md`

### Problem
Reflection outputs are homogeneous across all agents ¡÷ generic prompts, no identity, uniform importance=0.9, no source diversity in retrieval.

### Task Split

| ID | Title | Assigned | Key File | Phase |
|----|-------|----------|----------|-------|
| 057-A | Personalized Reflection Prompt | Codex | `reflection_engine.py` | 1 (parallel) ? |
| 057-B | Source-Stratified Retrieval | Gemini | `humancentric_engine.py` | 1 (parallel) ? |
| 057-C | Dynamic Importance Scoring | Codex | `reflection_engine.py` + `run_flood.py` | 2 (after A) ? |
| 057-D | MA Reflection Integration | Gemini | `lifecycle_hooks.py` | 3 (after all) ? |

### Reflection Integration in SA

Already wired into `run_flood.py` `FinalParityHook.post_year()` (lines 463-517):
- Uses `AgentReflectionContext` + `extract_agent_context()`
- Uses `generate_personalized_batch_prompt()`
- Uses `compute_dynamic_importance()`
- Falls back to `retrieve_stratified()` when available

### Completed (Codex)
- 057-A ? Personalized prompts implemented + tests (`tests/test_reflection_personalization.py`)
  - Commit: `81e40ce`
- 057-B ? Source-stratified retrieval (`tests/test_stratified_retrieval.py`)
- 057-C ? Dynamic importance scoring + SA reflection loop update (`tests/test_dynamic_importance.py`)
  - Commit: `5ed3f94`
- 057-D ? MA reflection integration fixes + test alignment (`tests/test_ma_reflection.py`)
  - Commit: `7ac2314`

---

## Previous: Task-055 + Task-056 + Test Fixes

### Task-055: Multi-Agent Bug Fixes (Codex)

| ID | Description | Commit | Status |
|----|-------------|--------|--------|
| 055-A | Fix stale `self.config` in `parse_output()` | `2b05b11` | ? Verified |
| 055-B | Pass `config_path` to `get_adapter()` | `1667535` | ? Verified |
| 055-C | CognitiveCache governance guard + `invalidate()` | `80b8c55` | ? Verified |

### Task-056: MemoryBridge Integration (Gemini)

| ID | Description | Commit | Status |
|----|-------------|--------|--------|
| 056 | Communication Layer ¡÷ Memory via MemoryBridge | `81b8eb0` | ? Verified (indentation fixed) |

### Test Fixes (Claude Code)

Fixed 11 pre-existing test failures ¡÷ **880 passed, 0 failed**

### Experiment: gemma3:1b Group C

- **Status**: ? Complete (behavior collapse detected ¡÷ see Task-058)
- **Config**: seed=401, 100 agents, 10 years, gemma3:1b
- **Output**: `examples/single_agent/results/JOH_FINAL/gemma3_1b/Group_C/Run_1/`
- **Results**: 897/1000 elevate_house, 101 buy_insurance, 2 do_nothing
- **Diagnosis**: Array decision bug in parser (fixed in Task-058)
- **Re-run needed**: Yes, after committing P0+P1 fixes

### Pending

- [ ] Commit Task-058 parser fixes
- [ ] Re-run gemma3:1b Group C with parser fix
- [ ] 11/12 remaining Gemma 3 experiment runs (053-4, assigned to WenyuChiou)

---

## Previous: Task-053 Gemma 3 Experiment Campaign

**Status**: In Progress (4/5 infrastructure subtasks complete, blocked on 053-4 execution)

| ID | Description | Status |
|----|-------------|--------|
| 053-0 | Directory Cleanup | ? |
| 053-1 | Fix Experiment Script | ? |
| 053-2 | Ollama Environment Check | ? |
| 053-4 | Execute 12 Runs | ? Pending (WenyuChiou) |
| 053-5 | Analysis Script | ? |

---

## Previous: Task-045 Universal Framework Improvements

**Status**: In Progress (A-C,F complete; D,E,G pending)

| ID | Description | Assigned | Status |
|----|-------------|----------|--------|
| 045-A | SDK rename ¡÷ `cognitive_governance` | Claude Code | ? |
| 045-B | `neighbor_pct` 0-1 normalization | Claude Code | ? |
| 045-C | Threshold configuration | Claude Code | ? |
| 045-F | Seed propagation fix | Claude Code | ? |
| 045-D | DeepSeek validation | Claude Code | ? (interrupted) |
| 045-E | Docstring supplement | Codex | pending |
| 045-G | Folder consolidation | Codex | pending |

### Key Decisions

- **SDK Name**: `governed_ai_sdk` ¡÷ `cognitive_governance`
- **Semantic Retrieval**: Confirmed using Cosine Similarity (0-1)
- **Seed Bug**: Memory engine hardcodes `seed=42`, should use CLI seed

---

## Framework Architecture Evaluation ?

**Status**: Complete
**Plan**: `C:\Users\wenyu\.claude\plans\ancient-beaming-lemur.md`
**Score**: 8.5/10

### SDK vs Broker Layer Mapping

| Layer | SDK | Broker |
|-------|-----|--------|
| **Observation** | EnvironmentObserver, SocialObserver | ContextProviders |
| **Perception** | (semantic filter) | PerceptionFilterProtocol |
| **Reasoning** | PolicyEngine, CounterfactualEngine | Validators |
| **Memory** | UnifiedCognitiveEngine v5 | MemoryFactory |
| **Action** | Protocol | SkillBrokerEngine |
| **Audit** | (pipeline) | AuditWriter 50+ |

### Alignment

| Construct | Coverage |
|----------|----------|
| PMT (Protection Motivation) | ? 95% |
| Dual-Process (System 1/2) | ? 90% |
| Memory Psychology | ? 85% |
| Social Influence | ?? 70% |

---

## Active Task: Task-043 Realistic Agent Perception

**Status**: ? Complete
**Owner**: Claude Code
**Plan**: `C:\Users\wenyu\.claude\plans\ancient-beaming-lemur.md` (Phase 3)

### Summary

Implemented agent-type aware perception filters that transform context based on who is observing:

| Agent Type | Sees Numbers | Sees Qualitative | Social Scope |
|------------|--------------|------------------|--------------|
| Household (NMG) | ? | ? "waist-deep water" | Spatial (radius=2) |
| Household (MG) | ? | ? "waist-deep water" | Spatial (radius=1) |
| Government | ? exact $ | ? | Global |
| Insurance | ? exact $ | ? | Policyholders |

### Tests
- `tests/test_perception_filter.py`: 42 tests passing
- `tests/test_social_graph_config.py`: 42 tests passing

### Key Components

| File | Description |
|------|-------------|
| `broker/interfaces/perception.py` | Protocol definitions, descriptor mappings |
| `broker/components/perception_filter.py` | HouseholdPerceptionFilter, GovernmentPerceptionFilter, InsurancePerceptionFilter, PerceptionFilterRegistry |
| `broker/components/social_graph_config.py` | SocialGraphSpec, agent-type social radius config |
| `broker/components/context_providers.py` | PerceptionAwareProvider (add LAST to provider chain) |

### Qualitative Transformations (Household)

- `depth_ft` ¡÷ "ankle/knee/waist/chest/over-head water"
- `damage_ratio` ¡÷ "minimal/minor/moderate/significant/devastating damage"
- `neighbor_count` ¡÷ "none/a few/some/many/most of your neighbors"
- Dollar amounts and percentages are removed

### MG Agent Restrictions

MG (Marginalized Group) agents have limited community information access:
- Community-wide observables (`insurance_penetration_rate`, etc.) removed
- Personal observables (`my_` prefix) preserved
- Smaller social network radius (1 vs 2)

---

## Previous Task: Task-040 SA/MA Unified Architecture

**Status**: ? Complete
**Owner**: Claude Code
**Plan**: `C:\Users\wenyu\.claude\plans\cozy-roaming-perlis.md` (Part 14-15)

### Subtask Status

| ID | Title | Assigned | Status | Notes |
|----|-------|----------|--------|-------|
| 040-A | AgentTypeRegistry | Claude Code | ? Done | 38 tests pass |
| 040-B | UnifiedContextBuilder | Codex | ? Done | 31 tests pass |
| 040-C | AgentInitializer | Gemini | ? Done | 29 tests pass |
| 040-D | PsychometricFramework | Codex | ? Done | 55 tests pass |
| 040-E | TypeValidator | Gemini | ? Done | 21 tests pass |

**Total Tests**: 174 tests passing

### New Example Created

A new unified example demonstrating all Task-040 components:

```
examples/unified_flood/
¢u¢w¢w run_experiment.py       # Main entry using all new components
¢u¢w¢w agent_types.yaml        # New unified schema (5 agent types)
¢u¢w¢w skill_registry.yaml     # 16 skills with eligible_agent_types
¢|¢w¢w README.md               # Documentation
```

### Key Components Demonstrated

| Component | File | Function |
|-----------|------|----------|
| AgentTypeRegistry | `broker/config/agent_types/` | Load 5 agent types from YAML |
| UnifiedContextBuilder | `broker/core/unified_context_builder.py` | Mode-based context building |
| AgentInitializer | `broker/core/agent_initializer.py` | Synthetic/CSV/Survey modes |
| PsychometricFramework | `broker/core/psychometric.py` | PMT/Utility/Financial |
| TypeValidator | `broker/governance/type_validator.py` | Per-type skill validation |

### Dry-Run Test Results

```
[1] Loading Agent Type Registry... ? 5 types loaded
[2] Initializing agents (synthetic mode)... ? 100 profiles
[3] Setting up Psychometric Framework... ? PMT with 3 constructs
[4] Creating experiment components... ? 16 skills
[5] Creating Unified Context Builder... ? 2 providers
[6] Setting up Type Validator... ? Demo validation passed
[7] Output directory... ? Created

DRY RUN COMPLETE - Components initialized successfully
```

### Bug Fixes Applied

1. `run_experiment.py:267` - Changed `_providers` to `providers`
2. `context_providers.py:47` - Handle both dict and object agents

---

## Completed Tasks

### Task-037: SDK-Broker Architecture Separation ?

**Commit**: c7feecc
All 6 phases complete. SDK now standalone.

### Task-036: MA Memory V4 Upgrade ?

**Commit**: 5af662c
Merged to main.

---

## Architecture Overview

```
broker/config/agent_types/   # Task-040 ?
¢u¢w¢w base.py                  # AgentTypeDefinition
¢|¢w¢w registry.py              # AgentTypeRegistry

broker/core/                 # Task-040 ?
¢u¢w¢w unified_context_builder.py  # 040-B
¢u¢w¢w agent_initializer.py        # 040-C
¢|¢w¢w psychometric.py             # 040-D

broker/governance/           # Task-040 ?
¢|¢w¢w type_validator.py           # 040-E

examples/unified_flood/      # NEW Demo ?
¢u¢w¢w run_experiment.py
¢u¢w¢w agent_types.yaml
¢u¢w¢w skill_registry.yaml
¢|¢w¢w README.md
```

---

## Usage Commands

```bash
# Dry run (verify components)
python examples/unified_flood/run_experiment.py --dry-run

# SA mode with synthetic agents
python examples/unified_flood/run_experiment.py --mode single_agent --agents 10 --years 5

# SA mode with social features
python examples/unified_flood/run_experiment.py --mode single_agent --enable-social --agents 20

# MA mode (multi-type agents)
python examples/unified_flood/run_experiment.py --mode multi_agent --enable-multi-type --agents 30
```

---

## Test Commands

```bash
# All Task-040 tests
pytest tests/test_agent_type_registry.py tests/test_unified_context_builder.py tests/test_agent_initializer.py tests/test_psychometric.py tests/test_type_validator.py -v

# Quick verification
pytest tests/test_agent_type_registry.py -v  # 38 tests
```
