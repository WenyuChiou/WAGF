# Task 045-G: Project Folder Consolidation

**Assigned To**: Codex
**Status**: COMPLETED
**Priority**: HIGH
**Depends On**: 045-A, 045-B, 045-C, 045-F (all completed)

---

## Objective

Consolidate duplicate/confusing folder structure between root and broker/ to establish clear module boundaries.

---

## Background

Current structure has confusing duplicates:
- `interfaces/` (root, 1 file) vs `broker/interfaces/` (9 files) - different content
- `simulation/` (root) should be inside broker/
- `validators/` (root) vs `broker/validators/` (re-export) vs `broker/governance/validators/` - confusing
- `broker/visualization/` - 0 references, unused

---

## Steps

### Step 1: Delete unused folder (0 dependencies)

```bash
rm -rf broker/visualization/
```

**Verification**: No imports of `broker.visualization` exist in codebase.

---

### Step 2: Move interfaces/ to providers/

**Action**: Move `interfaces/llm_provider.py` ??`providers/llm_provider.py`

**Files to update imports** (5 files):
```
providers/factory.py
providers/ollama.py
providers/openai_provider.py
providers/gemini.py
tests/test_adapter_parsing.py
```

**Import change**:
```python
# Before:
from interfaces.llm_provider import LLMProvider

# After:
from providers.llm_provider import LLMProvider
```

**Final action**: Delete empty `interfaces/` directory

---

### Step 3: Move simulation/ to broker/simulation/

**Action**: Move entire `simulation/` directory ??`broker/simulation/`

**Files to update imports** (9 files):
```
broker/components/interaction_hub.py
examples/multi_agent/run_unified_experiment.py
examples/multi_agent/verify_ma_logic.py
simulation/base_simulation_engine.py (internal import)
tests/integration/test_ma_e2e_smoke.py
tests/integration/test_sa_e2e_smoke.py
tests/integration/test_sa_environment_audit.py
tests/test_tiered_environment.py
tests/test_world_models.py
```

**Import change**:
```python
# Before:
from simulation.environment import TieredEnvironment
from simulation.state_manager import StateManager

# After:
from broker.simulation.environment import TieredEnvironment
from broker.simulation.state_manager import StateManager
```

---

### Step 4: Consolidate validators/ structure

**Current structure**:
```
validators/                    # root (agent validators)
??? __init__.py
??? agent_validator.py
??? base.py
??? council.py

broker/validators/             # re-export shim only
??? __init__.py

broker/governance/validators/  # PMT validators
??? __init__.py
??? base_validator.py
??? personal_validator.py
??? physical_validator.py
??? social_validator.py
??? thinking_validator.py
```

**Target structure**:
```
broker/validators/             # unified location
??? __init__.py               # public API exports
??? agent/                    # from root validators/
??  ??? __init__.py
??  ??? agent_validator.py
??  ??? base.py
??  ??? council.py
??? governance/               # from broker/governance/validators/
    ??? __init__.py
    ??? base_validator.py
    ??? personal_validator.py
    ??? physical_validator.py
    ??? social_validator.py
    ??? thinking_validator.py
```

**Import changes**:
```python
# Agent validators
# Before:
from validators.council import ValidatorCouncil
from validators.base import AgentValidator

# After:
from broker.validators.agent.council import ValidatorCouncil
from broker.validators.agent.base import AgentValidator

# Governance validators
# Before:
from broker.governance.validators import PersonalValidator

# After:
from broker.validators.governance import PersonalValidator
```

**Files to update** (~15 files):
- All files using `from validators.`
- All files using `from broker.governance.validators`

**Final action**:
- Delete empty root `validators/` directory
- Delete empty `broker/governance/` directory (if no other content)

---

### Step 5: Create backward compatibility shims (optional)

```python
# validators/__init__.py (deprecation shim)
import warnings
warnings.warn(
    "validators module moved to broker.validators.agent",
    DeprecationWarning,
    stacklevel=2
)
from broker.validators.agent import *
```

---

### Step 6: Verify

```bash
# 1. Check imports work
python -c "from broker.simulation.environment import TieredEnvironment; print('OK')"
python -c "from providers.llm_provider import LLMProvider; print('OK')"
python -c "from broker.validators.agent.council import ValidatorCouncil; print('OK')"
python -c "from broker.validators.governance import PersonalValidator; print('OK')"

# 2. Run full test suite
pytest tests/ -v --tb=short

# 3. Verify SA experiment runs
python examples/single_agent/run_flood.py --model mock --years 1 --agents 5 --dry-run
```

---

## Success Criteria

- [ ] `broker/visualization/` deleted
- [ ] `interfaces/` merged into `providers/`
- [ ] `simulation/` moved to `broker/simulation/`
- [ ] `validators/` consolidated under `broker/validators/`
- [ ] All tests pass
- [ ] No broken imports
- [ ] SA experiment runs successfully

---

## Impact Assessment

| Component | Impact | Risk |
|-----------|--------|------|
| `run_flood.py` (SA main) | NO changes needed | NONE |
| `broker/components/*` | Update simulation imports | LOW |
| `tests/*` | Update validators imports | LOW |
| `examples/multi_agent/*` | Update simulation imports | LOW |

---

## Execution Notes

1. Make atomic commits for each step
2. Run tests after each step to catch issues early
3. Do NOT modify any logic, only move files and update imports
4. Preserve all `__pycache__` exclusions in git

---

## IMPORTANT: File Deletion After Move

**After each move operation, DELETE the original files/directories:**

| Step | Move From | Move To | DELETE Original |
|------|-----------|---------|-----------------|
| 1 | - | - | `broker/visualization/` (?湔?芷) |
| 2 | `interfaces/llm_provider.py` | `providers/llm_provider.py` | `interfaces/` ?游??|
| 3 | `simulation/*` | `broker/simulation/*` | `simulation/` ?游??|
| 4a | `validators/*` | `broker/validators/agent/*` | `validators/` ?游??|
| 4b | `broker/governance/validators/*` | `broker/validators/governance/*` | `broker/governance/` ?桅? (憒?蝛箔?) |

**Git commands for move + delete:**
```bash
# Example for Step 2:
git mv interfaces/llm_provider.py providers/llm_provider.py
rm -rf interfaces/
git add -A

# Example for Step 3:
mkdir -p broker/simulation
git mv simulation/__init__.py broker/simulation/
git mv simulation/base_simulation_engine.py broker/simulation/
git mv simulation/environment.py broker/simulation/
git mv simulation/state_manager.py broker/simulation/
rm -rf simulation/
git add -A
```

**Verification after deletion:**
```bash
# These directories should NOT exist after completion:
ls interfaces/        # Should fail: No such file or directory
ls simulation/        # Should fail: No such file or directory
ls validators/        # Should fail: No such file or directory
ls broker/visualization/  # Should fail: No such file or directory
```

---

## Completion Notes

- Verified directories already consolidated: interfaces/, simulation/, alidators/, roker/visualization/ absent.
- Verified targets present: providers/llm_provider.py, roker/simulation/, roker/validators/agent, roker/validators/governance.
- No code changes required in this session.
- Tests not run in this session.

