# Extending the C&V Validation Package to New Domains

This guide shows how to use the validation package for any LLM-ABM domain
(irrigation, earthquake, epidemiology, etc.) without modifying framework code.

## Architecture Overview

```
compute_validation()
    │
    ├── load_traces()           ← trace_patterns (configurable file globs)
    │
    ├── compute_l1_metrics()    ← BehavioralTheory + HallucinationChecker
    │   ├── CACR               ← theory.get_coherent_actions()
    │   ├── R_H                ← hallucination_checker.is_hallucination()
    │   └── EBE                ← action_space_size
    │
    ├── compute_cgr()           ← GroundingStrategy
    │   └── CGR_TP, CGR_CP     ← grounder.ground_constructs()
    │
    └── compute_l2_metrics()    ← BenchmarkRegistry + state_rules
        ├── State Inference     ← state_rules (configurable)
        ├── Benchmarks          ← benchmark_compute_fn (pluggable)
        └── EPI                 ← benchmarks dict (configurable)
```

**4 Protocols to implement:**

| Protocol | File | Purpose |
|----------|------|---------|
| `BehavioralTheory` | `theories/base.py` | Construct-action coherence rules |
| `HallucinationChecker` | `hallucinations/base.py` | Impossible action detection |
| `GroundingStrategy` | `grounding/base.py` | Objective construct derivation |
| Benchmark functions | `benchmarks/registry.py` | Domain-specific L2 benchmarks |

**6 Configurable parameters** (all with backward-compatible defaults):

| Parameter | Location | Default |
|-----------|----------|---------|
| `action_aliases` | `io/trace_reader.py` | `_FLOOD_ACTION_ALIASES` |
| `state_rules` | `io/state_inference.py` | `FLOOD_STATE_RULES` |
| `trace_patterns` | `engine.py` | `_FLOOD_TRACE_PATTERNS` |
| `action_space_size` | `engine.py` | `5` (flood) |
| `hazard_fn` | `metrics/null_model.py` | `_default_flood_hazard` |
| `benchmarks` + `benchmark_compute_fn` | `engine.py` → `metrics/l2_macro.py` | Flood benchmarks |

---

## Step 1: Implement BehavioralTheory

The theory defines which actions are coherent for each construct combination.

```python
# my_domain/irrigation_theory.py
from typing import Dict, List
from validation.theories.base import BehavioralTheory

# WSA = Water Stress Appraisal, ACA = Adaptive Capacity Appraisal
WSA_ACA_RULES = {
    ("VH", "VH"): ["decrease_large"],
    ("VH", "H"):  ["decrease_large", "decrease_small"],
    ("VH", "M"):  ["decrease_small", "maintain"],
    ("VH", "L"):  ["maintain"],         # fatalism
    ("H", "VH"):  ["decrease_small"],
    ("H", "H"):   ["decrease_small", "maintain"],
    ("H", "M"):   ["maintain"],
    ("M", "VH"):  ["maintain", "increase_small"],
    ("M", "H"):   ["maintain"],
    ("M", "M"):   ["maintain"],
    ("L", "VH"):  ["increase_small", "increase_large"],
    ("L", "H"):   ["increase_small"],
    ("L", "M"):   ["maintain"],
    ("L", "L"):   ["maintain"],
    ("VL", "VH"): ["increase_large"],
    ("VL", "H"):  ["increase_small", "increase_large"],
    # ...fill remaining cells...
}

class IrrigationWSATheory:
    """WSA/ACA-based behavioral theory for irrigation agents."""

    @property
    def name(self) -> str:
        return "irrigation_wsa"

    @property
    def dimensions(self) -> List[str]:
        return ["WSA", "ACA"]

    @property
    def agent_types(self) -> List[str]:
        return ["irrigator"]

    @property
    def action_space_size(self) -> int:
        return 5  # increase_large, increase_small, maintain, decrease_small, decrease_large

    def get_coherent_actions(self, construct_levels: Dict[str, str],
                              agent_type: str) -> List[str]:
        wsa = construct_levels.get("WSA", "UNKNOWN")
        aca = construct_levels.get("ACA", "UNKNOWN")
        return WSA_ACA_RULES.get((wsa, aca), [])

    def extract_constructs(self, trace: Dict) -> Dict[str, str]:
        reasoning = trace.get("skill_proposal", {}).get("reasoning", {})
        return {
            "WSA": reasoning.get("WSA_LABEL", "UNKNOWN"),
            "ACA": reasoning.get("ACA_LABEL", "UNKNOWN"),
        }

    def is_sensible_action(self, construct_levels: Dict[str, str],
                           action: str, agent_type: str) -> bool:
        wsa = construct_levels.get("WSA", "UNKNOWN")
        if wsa in ("VH", "H") and action.startswith("increase"):
            return False
        if wsa in ("VL", "L") and action.startswith("decrease"):
            return False
        return True
```

---

## Step 2: Implement HallucinationChecker

Define physically impossible actions for your domain.

```python
# my_domain/irrigation_hallucination.py
from typing import Dict
from validation.io.trace_reader import _normalize_action, _extract_action

class IrrigationHallucinationChecker:
    @property
    def name(self) -> str:
        return "irrigation_physical"

    def is_hallucination(self, trace: Dict) -> bool:
        action = _normalize_action(_extract_action(trace))
        # Invalid: increasing when allocation is already at maximum
        state = trace.get("state_before", {})
        if action == "increase_large" and state.get("at_allocation_cap", False):
            return True
        # Invalid: decreasing below zero
        if action == "decrease_large" and state.get("current_demand", 1) <= 0:
            return True
        return False
```

---

## Step 3: Implement GroundingStrategy

Derive expected construct levels from objective state variables.

```python
# my_domain/irrigation_grounding.py
from typing import Dict

class IrrigationGroundingStrategy:
    @property
    def name(self) -> str:
        return "irrigation_wsa"

    def ground_constructs(self, state_before: Dict) -> Dict[str, str]:
        # WSA from reservoir level
        mead_level = state_before.get("lake_mead_level", 1075)
        if mead_level < 1025:
            wsa = "VH"
        elif mead_level < 1050:
            wsa = "H"
        elif mead_level < 1075:
            wsa = "M"
        elif mead_level < 1100:
            wsa = "L"
        else:
            wsa = "VL"

        # ACA from financial capacity
        income = state_before.get("income", 50000)
        aca = "H" if income > 60000 else "M" if income > 40000 else "L"

        return {"WSA": wsa, "ACA": aca}
```

---

## Step 4: Register Domain Benchmarks

Use the `BenchmarkRegistry` decorator pattern with `**kwargs` dispatch.

```python
# my_domain/irrigation_benchmarks.py
from typing import Dict, List, Optional
import pandas as pd
from validation.benchmarks.registry import BenchmarkRegistry

_registry = BenchmarkRegistry()

IRRIGATION_BENCHMARKS = {
    "conservation_rate": {
        "range": (0.20, 0.50),
        "weight": 1.5,
        "description": "Fraction of agents who decreased demand",
    },
    "demand_ratio": {
        "range": (0.30, 0.45),
        "weight": 1.0,
        "description": "Mean demand/allocation ratio",
    },
}

@_registry.register("conservation_rate")
def _compute_conservation_rate(df, traces, **kwargs):
    if "final_reduced_demand" not in df.columns:
        return None
    return df["final_reduced_demand"].fillna(False).astype(float).mean()

@_registry.register("demand_ratio")
def _compute_demand_ratio(df, traces, **kwargs):
    ratio_col = kwargs.get("ratio_col", "demand_ratio")
    if ratio_col not in df.columns:
        return None
    return df[ratio_col].mean()

def compute_irrigation_benchmark(name, df, traces):
    """Backward-compatible wrapper."""
    return _registry.dispatch(name, df, traces)
```

---

## Step 5: Define Action Aliases and State Rules

```python
# my_domain/irrigation_config.py

# Action normalization aliases
IRRIGATION_ACTION_ALIASES = {
    "increase_large": ["increase_large", "boost_water", "maximize_draw"],
    "increase_small": ["increase_small", "slight_increase"],
    "maintain": ["maintain", "keep_current", "status_quo", "do_nothing"],
    "decrease_small": ["decrease_small", "slight_decrease", "reduce_water"],
    "decrease_large": ["decrease_large", "cut_water", "minimize_draw"],
}

# State inference rules: (state_key, "last"|"ever", action_name)
IRRIGATION_STATE_RULES = [
    ("reduced_demand", "ever", "decrease_large"),
    ("increased_demand", "ever", "increase_large"),
    ("last_action_maintain", "last", "maintain"),
]

# Trace file patterns
IRRIGATION_TRACE_PATTERNS = {
    "upstream": ["**/upstream_agent_traces.jsonl"],
    "downstream": ["**/downstream_agent_traces.jsonl"],
}
```

---

## Step 6: Wire Everything Together

A single `compute_validation()` call with your domain implementations:

```python
from pathlib import Path
from validation.engine import compute_validation

# Import your domain implementations
from my_domain.irrigation_theory import IrrigationWSATheory
from my_domain.irrigation_hallucination import IrrigationHallucinationChecker
from my_domain.irrigation_grounding import IrrigationGroundingStrategy
from my_domain.irrigation_benchmarks import (
    IRRIGATION_BENCHMARKS,
    compute_irrigation_benchmark,
)
from my_domain.irrigation_config import IRRIGATION_TRACE_PATTERNS

report = compute_validation(
    traces_dir=Path("results/irrigation_run1/seed_42"),
    agent_profiles_path=Path("data/agent_profiles.csv"),
    output_dir=Path("results/validation"),
    # Protocol implementations
    theory=IrrigationWSATheory(),
    hallucination_checker=IrrigationHallucinationChecker(),
    grounder=IrrigationGroundingStrategy(),
    # Domain configuration
    trace_patterns=IRRIGATION_TRACE_PATTERNS,
    action_space_size=5,
    benchmarks=IRRIGATION_BENCHMARKS,
    benchmark_compute_fn=compute_irrigation_benchmark,
)

print(f"L1 CACR: {report.l1.cacr}")
print(f"L2 EPI:  {report.l2.epi}")
print(f"Pass:    {report.pass_all}")
```

For null model testing with custom hazard:

```python
from validation.metrics.null_model import compute_null_epi_distribution

def drought_hazard(row, rng):
    """Drought probability based on location."""
    zone = str(row.get("water_district", "normal"))
    return rng.random() < (0.30 if zone == "critical" else 0.10)

null = compute_null_epi_distribution(
    agent_profiles,
    action_pools={"upstream": [...], "downstream": [...]},
    hazard_fn=drought_hazard,
)
```

---

## Testing Checklist

When extending to a new domain, verify:

1. `BehavioralTheory` protocol: `isinstance(theory, BehavioralTheory)` returns `True`
2. `HallucinationChecker` protocol: `isinstance(checker, HallucinationChecker)` returns `True`
3. `GroundingStrategy` protocol: `isinstance(grounder, GroundingStrategy)` returns `True`
4. Custom action aliases: `_normalize_action("your_alias", your_aliases) == "canonical"`
5. Custom state rules: `_extract_final_states_from_decisions(traces, your_rules)` populates expected keys
6. Custom benchmarks: `registry.dispatch("your_benchmark", df, traces, **kwargs)` returns expected value
7. Custom trace patterns: `load_traces(dir, your_patterns)` finds your JSONL files
8. Full pipeline: `compute_validation(...)` completes without error and produces `validation_report.json`

---

## End-to-End Example: Irrigation Domain

See the WAGF irrigation ABM for a complete real-world example:

- **Theory**: `examples/single_agent/irrigation/irrigation_wsa_theory.py` (WSA/ACA dual-appraisal)
- **5 skills**: increase_large, increase_small, maintain, decrease_small, decrease_large
- **78 agents** × 42 years, 12 governance validators
- **Benchmarks**: demand ratio, conservation rate, Mead elevation tracking

The flood domain implementation serves as the reference implementation:

- **Theory**: `validation/theories/pmt.py` (PMT with TP/CP)
- **Hallucination checker**: `validation/hallucinations/flood.py`
- **Grounding**: `validation/grounding/flood.py`
- **Benchmarks**: `validation/benchmarks/flood.py` (8 empirical benchmarks)
