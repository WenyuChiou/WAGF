# Task-061-C6: multi_agent/README.md EN/ZH Alignment

> **Branch**: `feat/memory-embedding-retrieval`
> **Priority**: MEDIUM
> **Depends on**: None (standalone)

## Objective

Align `examples/multi_agent/README.md` (282 lines) with `examples/multi_agent/README_zh.md` (67 lines — severely misaligned). Add Task-060 features documentation.

## Current State

- English: 282 lines, comprehensive but missing Task-060 features
- Chinese: 67 lines, severely incomplete — needs full translation

## Changes Required

### 1. Add Task-060 Features to English Version

Add a section documenting these features (implemented in Task-060):

- **Insurance premium disclosure**: Insurance agent now discloses premium rates to household agents
- **Skill ordering randomization**: Action options are shuffled per-agent per-year to prevent primacy bias
- **SC/PA trust indicators**: Self-confidence and protective action trust scores visible in agent context
- **Communication layer**: Inter-agent message passing with `MessagePool` and `MessageProvider`
- **Echo chamber detection**: `DriftDetector` monitors for action distribution stagnation using Shannon entropy and Jaccard similarity

### 2. Add Quick Start Section

Add a Quick Start section for first-time users (currently missing):

```bash
# Basic multi-agent experiment
python examples/multi_agent/run_unified_experiment.py --model gemma3:4b

# With social dynamics enabled
python examples/multi_agent/run_unified_experiment.py --model gemma3:4b --enable-social
```

### 3. Align Chinese Version

Rewrite `examples/multi_agent/README_zh.md` to match the full English version. Follow the bilingual pattern established in `examples/README_zh.md`.

### 4. DO NOT Reference ref/ Directory

The `ref/` directory is reserved for upcoming MA experiments. Do not add references or links to files in `ref/`.

## Reference Files

- `examples/multi_agent/README.md`: Current English version
- `examples/multi_agent/README_zh.md`: Current Chinese version (needs rewrite)
- `examples/README.md` + `examples/README_zh.md`: Pattern for bilingual structure
- `.tasks/handoff/task-060-rlabm-ma.md`: Task-060 implementation details

## Verification

1. Chinese version has identical section structure as English
2. Task-060 features are documented
3. Quick Start section works (test the commands)
4. No references to `ref/` directory
