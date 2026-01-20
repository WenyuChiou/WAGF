# Task-015F: Global Configuration Centralization

**Date:** 2026-01-20
**Status:** Completed
**Related Task:** Task-015 (JOH Finalization)

## Objective

Centralize all "Universal Constants" (simulation parameters that apply globally) into `agent_types.yaml` under a new `global_config` section. This eliminates hardcoded values in Python scripts, improves reproducibility, and simplifies parameter tuning.

## Changes

### 1. Configuration Structure (`agent_types.yaml`)

Introduced `global_config` with the following categories:

- **[Cognitive Biology]** (`memory`):
  - `window_size`: 5 (Default working memory)
  - `consolidation_threshold`: 0.6
  - `consolidation_probability`: 0.7
  - `top_k_significant`: 2
  - `decay_rate`: 0.1
- **[Cognitive Routine]** (`reflection`):
  - `interval`: 1
  - `batch_size`: 10
  - `importance_boost`: 0.9
- **[Universe Physics]** (`llm`):
  - `temperature`: 0.1
  - `top_p`: 0.9, `top_k`: 40
  - `max_retries`: 2
- **[System Governance]** (`governance`):
  - `max_retries`: 3
  - `max_reports_per_retry`: 3

Removed redundant `shared` config sections for governance, llm, and reflection.

### 2. Code Logic (`agent_config.py`)

Implemented **Layered Configuration** hierarchy:

1. **Agent Specific Override** (e.g., `household.memory.window_size`)
2. **Global Config Default** (e.g., `global_config.memory.window_size`)
3. **Hardcoded Fallback** (Safety net)

### 3. Execution (`run_flood.py`)

Updated experiment runner to load parameters via this layered logic, ensuring legacy hardcoded values are replaced by configurable YAML entries.

## Verification

- [x] `run_flood.py` loads without error.
- [x] Memory engine receives correct values from YAML.
- [x] Agent override logic verified via script `verify_global_config.py`.

### Bug Fixes (2026-01-20)

- Fixed `NameError: global_cfg` in `run_flood.py` (Benchmarking mode) by ensuring `global_cfg` is loaded from `agent_types.yaml` at startup.
- Refactored `llm_utils.py` to load default config (temperature, retries) from `agent_types.yaml` via `AgentTypeConfig`, removing hardcoded defaults. Updated `agent_config.py` to prioritize `CWD/agent_types.yaml`.

### MA Sync Notes (2026-01-20)

- Added `global_config` to `examples/multi_agent/ma_agent_types.yaml`.
- `run_unified_experiment.py` now reads `global_config.memory` for MA memory engine setup.
- MA smoke test rerun (1y/5 agents) after config reload fix: no "agent_type not found" warnings. Output: `results_unified/v024_globalcfg_smoke3/`.
