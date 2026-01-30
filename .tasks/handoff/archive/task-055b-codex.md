# Task-055B: Eliminate AgentTypeConfig Singleton Order Dependency (Codex Assignment)

**Assigned To**: Codex
**Status**: COMPLETED (commit `1667535`, verified by Claude Code)
**Priority**: Low
**Estimated Scope**: ~15 lines changed, 2 files

---

## Objective

The `AgentTypeConfig` uses a singleton pattern (class-level `_instance`). The `UnifiedAdapter.__init__` calls `load_agent_config(config_path=None)` which relies on the singleton already being loaded with the correct YAML path by a prior call (typically from `AgentValidator` or `ExperimentBuilder`). If the call order changes, the adapter may silently load a wrong or empty config.

Fix: Make `UnifiedAdapter.__init__` propagate `config_path` to `load_agent_config()` so it's always explicit.

---

## Context

### Current Flow (fragile)

In `broker/core/experiment.py` `ExperimentBuilder.build()`:

1. Line 616: `AgentValidator(config_path=self.agent_types_path)` -- loads singleton with correct path
2. Line 623: `adapter = get_adapter(self.model)` -- calls `UnifiedAdapter()` with no config_path
3. Line 625: `adapter.config_path = self.agent_types_path` -- sets attribute but does NOT reload `agent_config`

`UnifiedAdapter.__init__` (line 137):
```python
self.agent_config = load_agent_config(config_path)  # config_path is None from get_adapter()
```

This works because `AgentValidator` already loaded the singleton at step 1. But it's an implicit dependency.

### Desired Flow (explicit)

`get_adapter()` should accept and forward `config_path`, so the adapter always loads from the correct source.

---

## Changes Required

### File 1: `broker/utils/model_adapter.py`

**Change 1**: Update `get_adapter()` factory (line 872) to accept `config_path`:

```python
# BEFORE (line 872):
def get_adapter(model_name: str) -> ModelAdapter:

# AFTER:
def get_adapter(model_name: str, config_path: str = None) -> ModelAdapter:
```

**Change 2**: Pass `config_path` through to `UnifiedAdapter` (lines 882, 886):

```python
# BEFORE:
    if 'deepseek' in model_lower:
        return UnifiedAdapter(preprocessor=deepseek_preprocessor)
    return UnifiedAdapter()

# AFTER:
    if 'deepseek' in model_lower:
        return UnifiedAdapter(preprocessor=deepseek_preprocessor, config_path=config_path)
    return UnifiedAdapter(config_path=config_path)
```

### File 2: `broker/core/experiment.py`

**Change 3**: Pass `agent_types_path` to `get_adapter()` (line 623):

```python
# BEFORE (line 623):
adapter = get_adapter(self.model)

# AFTER:
adapter = get_adapter(self.model, config_path=self.agent_types_path)
```

**Change 4**: Remove the now-redundant line 625:

```python
# REMOVE (line 625):
adapter.config_path = self.agent_types_path
```

Wait -- keep line 625 for backward compatibility (some code reads `adapter.config_path` later at line 174). Just change it to also reload if needed:

```python
# KEEP line 625 as-is (it's used for reproducibility_manifest.json at line 174):
adapter.config_path = self.agent_types_path
```

---

## Verification

### 1. Unit test

No new test file needed. Existing tests should continue to pass because the singleton still works as before -- but now the adapter explicitly provides the path.

### 2. Run tests

```bash
pytest tests/test_parse_confidence.py tests/test_alias_normalization.py -v
pytest tests/ --ignore=tests/integration --ignore=tests/manual --ignore=tests/test_vector_db.py -v
```

No new failures.

---

## DO NOT

- Do NOT remove the `AgentTypeConfig` singleton pattern (other code depends on it)
- Do NOT change `AgentTypeConfig.load()` logic
- Do NOT modify `UnifiedAdapter.__init__` beyond what's needed for config_path propagation
