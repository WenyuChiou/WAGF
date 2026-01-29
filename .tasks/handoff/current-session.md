# Current Session Handoff

## Last Updated
2026-01-28T16:30:00Z

---

## Active Task: Task-043 Realistic Agent Perception

**Status**: ✅ Complete
**Owner**: Claude Code
**Plan**: `C:\Users\wenyu\.claude\plans\ancient-beaming-lemur.md` (Phase 3)

### Summary

Implemented agent-type aware perception filters that transform context based on who is observing:

| Agent Type | Sees Numbers | Sees Qualitative | Social Scope |
|------------|--------------|------------------|--------------|
| Household (NMG) | ❌ | ✅ "waist-deep water" | Spatial (radius=2) |
| Household (MG) | ❌ | ✅ "waist-deep water" | Spatial (radius=1) |
| Government | ✅ exact $ | ❌ | Global |
| Insurance | ✅ exact $ | ❌ | Policyholders |

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

- `depth_ft` → "ankle/knee/waist/chest/over-head water"
- `damage_ratio` → "minimal/minor/moderate/significant/devastating damage"
- `neighbor_count` → "none/a few/some/many/most of your neighbors"
- Dollar amounts and percentages are removed

### MG Agent Restrictions

MG (Marginalized Group) agents have limited community information access:
- Community-wide observables (`insurance_penetration_rate`, etc.) removed
- Personal observables (`my_` prefix) preserved
- Smaller social network radius (1 vs 2)

---

## Previous Task: Task-040 SA/MA Unified Architecture

**Status**: ✅ Complete
**Owner**: Claude Code
**Plan**: `C:\Users\wenyu\.claude\plans\cozy-roaming-perlis.md` (Part 14-15)

### Subtask Status

| ID | Title | Assigned | Status | Notes |
|----|-------|----------|--------|-------|
| 040-A | AgentTypeRegistry | Claude Code | ✅ Done | 38 tests pass |
| 040-B | UnifiedContextBuilder | Codex | ✅ Done | 31 tests pass |
| 040-C | AgentInitializer | Gemini | ✅ Done | 29 tests pass |
| 040-D | PsychometricFramework | Codex | ✅ Done | 55 tests pass |
| 040-E | TypeValidator | Gemini | ✅ Done | 21 tests pass |

**Total Tests**: 174 tests passing

### New Example Created

A new unified example demonstrating all Task-040 components:

```
examples/unified_flood/
├── run_experiment.py       # Main entry using all new components
├── agent_types.yaml        # New unified schema (5 agent types)
├── skill_registry.yaml     # 16 skills with eligible_agent_types
└── README.md               # Documentation
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
[1] Loading Agent Type Registry... ✅ 5 types loaded
[2] Initializing agents (synthetic mode)... ✅ 100 profiles
[3] Setting up Psychometric Framework... ✅ PMT with 3 constructs
[4] Creating experiment components... ✅ 16 skills
[5] Creating Unified Context Builder... ✅ 2 providers
[6] Setting up Type Validator... ✅ Demo validation passed
[7] Output directory... ✅ Created

DRY RUN COMPLETE - Components initialized successfully
```

### Bug Fixes Applied

1. `run_experiment.py:267` - Changed `_providers` to `providers`
2. `context_providers.py:47` - Handle both dict and object agents

---

## Completed Tasks

### Task-037: SDK-Broker Architecture Separation ✅

**Commit**: c7feecc
All 6 phases complete. SDK now standalone.

### Task-036: MA Memory V4 Upgrade ✅

**Commit**: 5af662c
Merged to main.

---

## Architecture Overview

```
broker/config/agent_types/   # Task-040 ✅
├── base.py                  # AgentTypeDefinition
└── registry.py              # AgentTypeRegistry

broker/core/                 # Task-040 ✅
├── unified_context_builder.py  # 040-B
├── agent_initializer.py        # 040-C
└── psychometric.py             # 040-D

broker/governance/           # Task-040 ✅
└── type_validator.py           # 040-E

examples/unified_flood/      # NEW Demo ✅
├── run_experiment.py
├── agent_types.yaml
├── skill_registry.yaml
└── README.md
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
