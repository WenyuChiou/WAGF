# Task-030: FLOODABM Parameter Alignment

**Status**: ✅ COMPLETE
**Last Updated**: 2026-01-22T16:00:00Z

---

## ✅ ALL SPRINTS COMPLETE

---

## Objective

Reorganize configuration files into a centralized, clean structure.

## Current State (散亂)
```
examples/multi_agent/
├── ma_agent_types.yaml          # Agent config + FLOODABM params 混在一起
├── config/coherence_rules.yaml  # 單獨放
├── environment/
│   ├── core.py                  # ENV_CONFIG global vars
│   ├── risk_rating.py           # RR2.0 constants
│   └── tp_decay.py              # TP decay constants
└── (no skill_registry.yaml)     # 缺失
```

## Target Structure (清晰分離)
```
examples/multi_agent/
├── config/                           # 所有配置檔案集中
│   ├── agents/
│   │   └── agent_types.yaml          # Agent definitions only
│   ├── skills/
│   │   └── skill_registry.yaml       # Skill definitions (NEW)
│   ├── parameters/
│   │   └── floodabm_params.yaml      # FLOODABM parameters (EXTRACTED)
│   ├── governance/
│   │   └── coherence_rules.yaml      # Validation rules (MOVED)
│   └── globals.py                    # Global constants loader (NEW)
├── environment/                      # Environment modules (unchanged)
```

---

## Step-by-Step Tasks

### 6.1.1 Create Directory Structure
```bash
mkdir -p examples/multi_agent/config/agents
mkdir -p examples/multi_agent/config/skills
mkdir -p examples/multi_agent/config/parameters
mkdir -p examples/multi_agent/config/governance
```

### 6.1.2 Extract FLOODABM Parameters
**From**: `ma_agent_types.yaml` (lines 135-240)
**To**: `config/parameters/floodabm_params.yaml`

Extract the entire `floodabm_parameters:` section:
```yaml
# floodabm_params.yaml
# FLOODABM Supplementary Materials Tables S1-S6

tp_distribution:
  mg: { alpha: 4.44, beta: 2.89 }
  nmg: { alpha: 5.35, beta: 3.62 }
cp_distribution:
  mg: { alpha: 4.07, beta: 3.30 }
  nmg: { alpha: 5.27, beta: 4.18 }
sp_distribution:
  mg: { alpha: 1.37, beta: 1.69 }
  nmg: { alpha: 1.73, beta: 1.93 }
sc_distribution:
  mg: { alpha: 2.37, beta: 3.11 }
  nmg: { alpha: 4.56, beta: 2.39 }
pa_distribution:
  mg: { alpha: 2.56, beta: 2.17 }
  nmg: { alpha: 4.01, beta: 2.79 }

tp_decay:
  mg:
    alpha: 0.50
    beta: 0.21
    tau_0: 1.00
    tau_inf: 32.19
    k: 0.03
  nmg:
    alpha: 0.22
    beta: 0.10
    tau_0: 2.72
    tau_inf: 50.10
    k: 0.01
  theta: 0.5
  shock_scale: 0.3

insurance:
  r1k_structure: 3.56
  r1k_contents: 4.90
  limit_structure: 250000
  limit_contents: 100000
  deductible_structure: 1000
  deductible_contents: 1000
  reserve_fund_factor: 1.15
  small_fee: 100

initial_uptake:
  flood_prone_owner: 0.25
  flood_prone_renter: 0.08
  non_flood_prone_owner: 0.03
  non_flood_prone_renter: 0.01

elevation:
  h_elevate_ft: 5.0
  ffe_default_ft: 1.0

csrv: 0.57

rcv_lognormal:
  homeowner:
    ln_mu: 12.46
    ln_sigma: 0.63
    mean_rcv_usd: 313250
    cv: 0.69
  renter:
    ln_mu: 12.82
    ln_sigma: 1.20
    mean_rcv_usd: 766352
    cv: 1.81
```

**After extraction**: Remove from `ma_agent_types.yaml` and add reference comment.

### 6.1.3 Move Agent Types
Copy `ma_agent_types.yaml` (without floodabm_parameters) to `config/agents/agent_types.yaml`

### 6.1.4 Create Skill Registry
**File**: NEW `config/skills/skill_registry.yaml`

```yaml
# Flood Adaptation Skills for Household Agents
skills:
  buy_insurance:
    id: 1
    description: "Purchase NFIP flood insurance policy"
    eligible_agents: [household_owner, household_renter]
    preconditions:
      - "savings >= estimated_premium"
      - "has_insurance == false"
    effects:
      - "has_insurance = true"
      - "savings -= premium"

  elevate_house:
    id: 2
    description: "Elevate structure above BFE"
    eligible_agents: [household_owner]
    preconditions:
      - "is_owner == true"
      - "is_elevated == false"
    effects:
      - "is_elevated = true"
      - "ffe += 5ft"

  relocate:
    id: 3
    description: "Permanently relocate out of flood zone"
    eligible_agents: [household_owner, household_renter]
    effects:
      - "relocated = true"

  do_nothing:
    id: 4
    description: "Take no protective action"
    eligible_agents: [household_owner, household_renter]
    effects: []

skill_map:
  "1": "buy_insurance"
  "2": "elevate_house"
  "3": "relocate"
  "4": "do_nothing"
```

### 6.1.5 Move Coherence Rules
```bash
mv examples/multi_agent/config/coherence_rules.yaml examples/multi_agent/config/governance/
```

### 6.1.6 Create Config Loader
**File**: NEW `config/globals.py`

```python
"""Centralized configuration loader for multi-agent flood simulation."""

import yaml
from pathlib import Path
from typing import Dict, Any

CONFIG_DIR = Path(__file__).parent

def load_yaml(filename: str, subdir: str = "") -> Dict[str, Any]:
    """Load a YAML config file."""
    path = CONFIG_DIR / subdir / filename if subdir else CONFIG_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_floodabm_params() -> Dict[str, Any]:
    """Load FLOODABM parameters (Tables S1-S6)."""
    return load_yaml("floodabm_params.yaml", "parameters")

def load_agent_types() -> Dict[str, Any]:
    """Load agent type definitions."""
    return load_yaml("agent_types.yaml", "agents")

def load_skill_registry() -> Dict[str, Any]:
    """Load skill registry definitions."""
    return load_yaml("skill_registry.yaml", "skills")

def load_coherence_rules() -> Dict[str, Any]:
    """Load governance coherence rules."""
    return load_yaml("coherence_rules.yaml", "governance")

# Singleton cache
_CACHE: Dict[str, Any] = {}

def get_floodabm_params() -> Dict[str, Any]:
    if "floodabm" not in _CACHE:
        _CACHE["floodabm"] = load_floodabm_params()
    return _CACHE["floodabm"]

def get_skill_registry() -> Dict[str, Any]:
    if "skills" not in _CACHE:
        _CACHE["skills"] = load_skill_registry()
    return _CACHE["skills"]

def clear_cache() -> None:
    _CACHE.clear()
```

---

## Verification Commands

```bash
# 1. Verify directory structure
ls -la examples/multi_agent/config/

# 2. Test config loader
python -c "
from examples.multi_agent.config.globals import get_floodabm_params, get_skill_registry
p = get_floodabm_params()
assert p['csrv'] == 0.57, 'CSRV mismatch'
s = get_skill_registry()
assert 'buy_insurance' in s['skills'], 'Missing skill'
print('Config loader: OK')
"

# 3. Run existing tests (should still pass)
pytest examples/multi_agent/tests/test_floodabm_alignment.py -v
```

---

## Progress Tracking

| Sprint | Description | Status | Agent |
|--------|-------------|--------|-------|
| 1.1-5.1 | FLOODABM parameters | ✅ DONE | Claude Code |
| 2.2 | RR2.0 insurance integration | ✅ DONE | Gemini CLI |
| **6.1** | **Config reorganization** | 🔲 NOW | **Gemini CLI** |
| 5.2 | Experiment integration | 🔲 Pending | Claude Code |

---

## References

- Plan: `C:\Users\wenyu\.claude\plans\cozy-roaming-perlis.md`
- Handoff: `.tasks/handoff/current-session.md`
- FLOODABM Supplementary Materials (Tables S1-S6)
