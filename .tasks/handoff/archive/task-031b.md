# Task-031B: Code Refactoring (Large Files)

**Status**: 🔲 Ready
**Assigned**: Gemini CLI
**Last Updated**: 2026-01-22T18:00:00Z

---

## 🎯 GEMINI CLI ASSIGNMENT

### Objective

Split large modules (>300 lines) into smaller, single-responsibility files to improve maintainability and testability.
---

## Progress

- 1.1 model_adapter.py split complete on branch 	ask-031b-model-adapter (commit cd6329d).
  - Verified: python -m pytest tests/test_model_adapter_split.py -v
- 1.2 context_builder.py split complete on branch 	ask-031b-context-builder (commit 4fe8f5).
  - Verified: python -m pytest tests/test_context_builder_split.py -v
- 1.3 memory_engine.py split complete on branch 	ask-031b-memory-engine (commit 3a5b51).
  - Verified: python -m pytest tests/test_memory_engine_split.py -v


---

## Priority 1: Broker Core (HIGH)

### 1.1 Split `model_adapter.py` (846 lines)

**Current**: Monolithic file mixing parsing, repair, and model-specific logic.

**Target Structure**:
```
broker/utils/
├── model_adapter.py (200行) → ABC + UnifiedAdapter
├── preprocessors.py (200行) → GenericRegex, SmartRepair
├── json_repair.py (150行) → JSON extraction & repair
└── adapters/
    ├── deepseek.py (150行)
    ├── ollama.py (50行)
    └── openai.py (50行)
```

### 1.2 Split `context_builder.py` (948 lines)

**Current**: 6 Provider classes + SafeFormatter + TieredContextBuilder in one file.

**Target Structure**:
```
broker/components/
├── context_builder.py (150行) → ABC + SafeFormatter
├── context_providers.py (250行) → 6 Provider classes
├── tiered_builder.py (400行) → TieredContextBuilder
└── neighbor_utils.py (100行) → Neighbor summary logic
```

### 1.3 Split `memory_engine.py` (760 lines)

**Current**: ABC + 4 engine implementations + seeding + factory.

**Target Structure**:
```
broker/components/
├── memory_engine.py (100行) → ABC + factory
├── engines/
│   ├── window_engine.py (100行)
│   ├── importance_engine.py (150行)
│   ├── humancentric_engine.py (250行)
│   └── hierarchical_engine.py (150行)
└── memory_seeding.py (100行) → seed_memory_from_agents
```

---

## Priority 2: Multi-Agent Examples (MEDIUM)

### 2.1 Split `run_unified_experiment.py` (766 lines)

**Target Structure**:
```
examples/multi_agent/
├── run_unified_experiment.py (150行) → Main entry + argparse
├── orchestration/
│   ├── agent_factories.py (150行) → Government, Insurance, Household
│   ├── lifecycle_hooks.py (200行) → MultiAgentHooks class
│   └── disaster_sim.py (150行) → Disaster event handling
```

### 2.2 Split `initial_memory.py` (586 lines)

**Target Structure**:
```
examples/multi_agent/
├── initial_memory.py (100行) → Main generator
├── memory/
│   ├── templates.py (300行) → 6 memory generators
│   └── pmt_mapper.py (150行) → PMT → memory mapping
```

### 2.3 Split `survey_loader.py` (578 lines)

**Target Structure**:
```
examples/multi_agent/
├── survey_loader.py (150行) → CSV loading + orchestration
├── survey/
│   ├── pmt_calculator.py (150行) → SC, PA, TP, CP, SP scoring
│   ├── mg_classifier.py (100行) → MG status determination
│   └── stratified_sampler.py (100行) → Sampling logic
```

---

## Priority 3: Environment Modules (LOW)

### 3.1 Split `tp_decay.py` (354 lines)

```
environment/
├── tp_decay.py (150行) → TPDecayEngine core
├── decay_models.py (150行) → MG/NMG-specific strategies
└── tp_state.py (54行) → Dataclasses
```

### 3.2 Split `hazard.py` (356 lines)

```
environment/
├── hazard.py (180行) → HazardModule core
├── vulnerability.py (100行) → VulnerabilityModule
└── year_mapping.py (76行) → YearMapping
```

---

## Verification Commands

```bash
# After each split, ensure imports still work
python -c "from broker.components.context_builder import TieredContextBuilder; print('OK')"
python -c "from broker.utils.model_adapter import UnifiedModelAdapter; print('OK')"
python -c "from broker.components.memory_engine import create_memory_engine; print('OK')"

# Run full test suite
pytest tests/ -v --tb=short

# MA specific tests
pytest examples/multi_agent/tests/ -v
```

---

## Key Principles

1. **Backwards Compatibility**: All splits maintain via re-exports
2. **Tests First**: Tests must pass after each split before proceeding
3. **Single Responsibility**: Each new file has one clear purpose
4. **No Behavior Changes**: Refactoring only, no functional changes

---

## Effort Estimate

| Task | Files | Priority |
|------|-------|----------|
| 1.1 model_adapter | 6 new files | HIGH |
| 1.2 context_builder | 4 new files | HIGH |
| 1.3 memory_engine | 5 new files | HIGH |
| 2.1 run_experiment | 4 new files | MEDIUM |
| 2.2 initial_memory | 3 new files | MEDIUM |
| 2.3 survey_loader | 4 new files | MEDIUM |
| 3.1 tp_decay | 3 new files | LOW |
| 3.2 hazard | 3 new files | LOW |
| **Total** | **32 files** | |

---

## Reference

- Plan: `C:\Users\wenyu\.claude\plans\cozy-roaming-perlis.md`
- Current session: `.tasks/handoff/current-session.md`
