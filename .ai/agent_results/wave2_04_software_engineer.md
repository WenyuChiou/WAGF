# Wave 2 Expert Review: Software Engineering Assessment

**Reviewer**: Dr. Rachel Kim, Senior Software Engineer (Scientific Computing Frameworks, API Architecture)
**Focus**: SDK-readiness of C&V validation module for LLM-ABMs
**Date**: 2026-02-14

---

## Overall Score: 3.2 / 5.0

**Architecture Assessment**: The module demonstrates strong architectural *intent* with a clean layered design (L1/L2/CGR/bootstrap/null-model) and a Protocol-based theory system that shows genuine software engineering maturity. However, the current implementation has **tight coupling at every seam** between the domain-agnostic metrics engine and flood-specific logic. This is a module that was designed by someone who understands extensibility but built under deadline pressure for a single domain. The good news: the coupling points are identifiable and surgically fixable. The refactoring effort to reach SDK grade is moderate -- roughly 2-3 weeks of focused work, not a rewrite.

---

## Dimension Scores

| Dimension | Score | Assessment |
|-----------|-------|------------|
| D1: API Design & Ergonomics | 3.5 | Clean function signatures; `theory=None` defaulting to PMT is reasonable for first-party use but wrong for SDK; return types are well-structured dataclasses |
| D2: Separation of Concerns | 2.5 | **Biggest gap.** 4 hard imports from flood-specific modules into core metrics. `engine.py` is a flood pipeline masquerading as a generic engine |
| D3: Extensibility Architecture | 3.5 | `BehavioralTheory` Protocol is well-designed; `BenchmarkRegistry` with decorator dispatch is excellent; but 3-4 missing protocols leave gaps |
| D4: Package Structure | 3.5 | Logical decomposition into 7 sub-packages; scalable directory layout; but `hallucinations/flood.py` and `benchmarks/flood.py` need to be entry-points, not imported by core |
| D5: Testing Architecture | 3.0 | Good unit test coverage for CGR/bootstrap/null-model; but no property-based tests, no integration tests for pipeline, no parametric sweeps |
| D6: Configuration & DI | 2.5 | Hardcoded `EMPIRICAL_BENCHMARKS` dict, hardcoded action pools in null_model, hardcoded file patterns in `load_traces`; no config objects or YAML loading |
| D7: Roadmap to pip-installable SDK | 3.0 | TheoryRegistry + BenchmarkRegistry are the right patterns; needs ~6 more protocols, config layer, and plugin system for domains |

---

## Top 3 Engineering Strengths

### 1. Protocol-Based Theory System (Excellent)

The `BehavioralTheory` Protocol in `theories/base.py` is textbook structural subtyping. Five methods, all with clear contracts, `@runtime_checkable` for defensive programming. The `examples.py` file with TPB and IrrigationWSA implementations proves it works across domains. This is the strongest engineering decision in the module.

```python
@runtime_checkable
class BehavioralTheory(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def dimensions(self) -> List[str]: ...
    def get_coherent_actions(self, construct_levels, agent_type) -> List[str]: ...
    def extract_constructs(self, trace) -> Dict[str, str]: ...
    def is_sensible_action(self, construct_levels, action, agent_type) -> bool: ...
```

This is how you design for extensibility without over-engineering. No ABCs, no metaclasses, no registration ceremony -- just implement the shape.

### 2. BenchmarkRegistry with Decorator Dispatch

The `benchmarks/registry.py` + `benchmarks/flood.py` pattern is clean:

```python
_registry = BenchmarkRegistry()

@_registry.register("insurance_rate_sfha")
def _compute_insurance_rate_sfha(df, traces, ins_col, elev_col):
    ...
```

This is the right pattern for a plugin system. The registry is domain-agnostic, the registered functions are domain-specific. The only problem is that `l2_macro.py` imports the flood registry directly instead of accepting it as a parameter.

### 3. Layered Metric Hierarchy (L1/L2/CGR)

The separation of micro (per-decision CACR, R_H, EBE), macro (population-level EPI + benchmarks), and grounding (CGR with Cohen's kappa) is scientifically sound and maps cleanly to software layers. Each layer has its own dataclass, its own computation function, and its own pass/fail threshold. The `bootstrap_ci` function is fully generic and composable with any metric function -- this is exactly the right level of abstraction.

---

## Top 3 Engineering Debts

### 1. Core Metrics Import Flood-Specific Modules (Critical)

Four hard imports create inescapable coupling:

| File | Import | Problem |
|------|--------|---------|
| `l1_micro.py:29` | `from validation.hallucinations.flood import _is_hallucination` | Core L1 metric imports flood hallucination rules |
| `l2_macro.py:15` | `from validation.benchmarks.flood import EMPIRICAL_BENCHMARKS, _compute_benchmark` | Core L2 metric imports flood benchmark definitions |
| `engine.py:23` | `from validation.benchmarks.flood import EMPIRICAL_BENCHMARKS` | Pipeline orchestrator imports flood constants |
| `null_model.py:23-24` | `_OWNER_ACTIONS = [...]` / `_RENTER_ACTIONS = [...]` | Hardcoded flood action pools |

These four imports mean you **cannot use the metrics engine without the flood package**. In a pip-installable SDK, importing `llm_abm_validator.metrics.l1_micro` should not trigger flood-specific code.

### 2. Engine is a Flood Pipeline, Not a Generic Orchestrator

`engine.py:compute_validation()` is the most coupled file:
- `load_traces()` hardcodes `household_owner_traces.jsonl` / `household_renter_traces.jsonl` file patterns
- Line 83: `k_combined = 5  # Fixed: full household action space (owner 4 + renter 3, shared do_nothing)` -- hardcoded flood action space
- Line 100: `"**/*governance_audit.csv"` -- hardcoded audit file pattern
- Line 136: `"seed_"` string parsing for metadata extraction
- Lines 58-64: `print()` statements instead of `logging`

This function should be refactored into a `ValidationPipeline` class that accepts configuration, with `FloodValidationPipeline` as a preconfigured subclass.

### 3. No HallucinationChecker Protocol

Hallucination detection is domain-specific by definition (what is "impossible" depends on the domain's physics). But `l1_micro.py` imports `_is_hallucination` directly from `hallucinations/flood.py`. There is no `HallucinationChecker` protocol that would allow:

```python
class IrrigationHallucinationChecker:
    def is_hallucination(self, trace: Dict) -> bool:
        action = _extract_action(trace)
        # Can't irrigate with zero water allocation
        if action == "increase_large" and trace["state_before"]["allocation"] == 0:
            return True
        return False
```

---

## Refactoring Plan: From Flood Module to Universal SDK

### Phase 1: Decouple Core Metrics (3-5 days)

**Step 1.1**: Add `HallucinationChecker` Protocol

```python
# validation/checkers/base.py
from typing import Dict, Protocol, runtime_checkable

@runtime_checkable
class HallucinationChecker(Protocol):
    def is_hallucination(self, trace: Dict) -> bool: ...

class NullHallucinationChecker:
    """No-op checker for domains without hallucination rules."""
    def is_hallucination(self, trace: Dict) -> bool:
        return False
```

**Step 1.2**: Make `compute_l1_metrics` accept checker as parameter

```python
# BEFORE (l1_micro.py)
from validation.hallucinations.flood import _is_hallucination

def compute_l1_metrics(traces, agent_type="owner", theory=None, action_space_size=None):
    if _is_hallucination(trace): hallucinations += 1

# AFTER
def compute_l1_metrics(
    traces, agent_type="owner", theory=None,
    action_space_size=None, hallucination_checker=None
):
    if hallucination_checker is None:
        hallucination_checker = NullHallucinationChecker()
    if hallucination_checker.is_hallucination(trace): hallucinations += 1
```

**Step 1.3**: Make `compute_l2_metrics` accept benchmarks as parameter

```python
# BEFORE (l2_macro.py)
from validation.benchmarks.flood import EMPIRICAL_BENCHMARKS, _compute_benchmark

def compute_l2_metrics(traces, agent_profiles):
    for name, config in EMPIRICAL_BENCHMARKS.items(): ...

# AFTER
def compute_l2_metrics(
    traces, agent_profiles,
    benchmarks=None, benchmark_registry=None
):
    if benchmarks is None:
        benchmarks = {}  # No benchmarks = EPI undefined
    if benchmark_registry is None:
        benchmark_registry = BenchmarkRegistry()
    ...
```

**Step 1.4**: Make `null_model.py` accept action pools as parameter

```python
# BEFORE
_OWNER_ACTIONS = ["do_nothing", "buy_insurance", "elevate", "buyout", "retrofit"]

# AFTER
def generate_null_traces(
    agent_profiles, n_years=13, seed=0,
    action_pools=None  # Dict[str, List[str]]  e.g. {"owner": [...], "renter": [...]}
):
```

### Phase 2: Extract Pipeline Configuration (2-3 days)

**Step 2.1**: Create `ValidationConfig` dataclass

```python
@dataclass
class ValidationConfig:
    theory: BehavioralTheory
    hallucination_checker: HallucinationChecker
    benchmarks: Dict[str, BenchmarkConfig]
    benchmark_registry: BenchmarkRegistry
    action_pools: Dict[str, List[str]]
    trace_patterns: Dict[str, List[str]]  # {"owner": ["**/owner_*.jsonl"], ...}
    agent_type_resolver: Callable  # (trace) -> str
    action_space_size: Optional[Dict[str, int]]  # {"owner": 4, "renter": 3}
```

**Step 2.2**: Create `FloodValidationConfig` preset

```python
def flood_config() -> ValidationConfig:
    from validation.theories.pmt import PMTTheory
    from validation.hallucinations.flood import FloodHallucinationChecker
    from validation.benchmarks.flood import EMPIRICAL_BENCHMARKS, _registry
    return ValidationConfig(
        theory=PMTTheory(),
        hallucination_checker=FloodHallucinationChecker(),
        benchmarks=EMPIRICAL_BENCHMARKS,
        benchmark_registry=_registry,
        action_pools={"owner": [...], "renter": [...]},
        trace_patterns={"owner": ["**/household_owner_traces.jsonl"], ...},
        ...
    )
```

### Phase 3: CGR Grounding Strategy Protocol (2 days)

The current `ground_tp_from_state` and `ground_cp_from_state` are flood-specific rule-based grounding. Other domains need different grounding logic.

```python
# validation/grounding/base.py
@runtime_checkable
class GroundingStrategy(Protocol):
    def ground_constructs(self, state_before: Dict) -> Dict[str, str]:
        """Ground construct levels from objective state."""
        ...

class FloodGroundingStrategy:
    def ground_constructs(self, state_before: Dict) -> Dict[str, str]:
        return {
            "TP": ground_tp_from_state(state_before),
            "CP": ground_cp_from_state(state_before),
        }
```

Then `compute_cgr` becomes:

```python
def compute_cgr(traces, grounding_strategy=None):
    if grounding_strategy is None:
        return _empty_cgr_result()  # Can't ground without strategy
    for trace in traces:
        grounded = grounding_strategy.ground_constructs(trace["state_before"])
        ...
```

### Phase 4: Replace print() with logging (1 day)

```python
import logging
logger = logging.getLogger("llm_abm_validator")

# Replace all print() calls
logger.info(f"Loading traces from: {traces_dir}")
logger.warning(f"{extraction_failures} traces with UNKNOWN TP/CP labels excluded")
```

---

## Proposed New Protocols (Code Sketches)

The current codebase has 1 protocol (`BehavioralTheory`). For universal SDK grade, I recommend 4 additional protocols:

```python
# 1. HallucinationChecker (shown above)

# 2. GroundingStrategy (shown above)

# 3. TraceLoader — replaces hardcoded load_traces()
@runtime_checkable
class TraceLoader(Protocol):
    def load(self, traces_dir: Path) -> Dict[str, List[Dict]]:
        """Load traces grouped by agent type.
        Returns: {"owner": [...], "renter": [...]} or any grouping.
        """
        ...

# 4. ActionNormalizer — replaces hardcoded _normalize_action()
@runtime_checkable
class ActionNormalizer(Protocol):
    def normalize(self, raw_action: str) -> str: ...

class FloodActionNormalizer:
    MAPPINGS = {
        "buy_insurance": ["purchase_insurance", "get_insurance", ...],
        "elevate": ["elevate_home", "home_elevation", ...],
        ...
    }
    def normalize(self, raw_action: str) -> str:
        for standard, variants in self.MAPPINGS.items():
            if raw_action in variants:
                return standard
        return raw_action
```

I would **not** recommend more than 5 protocols total. Over-abstracting leads to "protocol soup" where users spend more time wiring protocols than computing metrics. The current `BehavioralTheory` + these 4 additions cover 95% of extension points.

---

## Ideal Package Structure for pip-installable SDK

```
llm-abm-validator/
├── pyproject.toml
├── src/
│   └── llm_abm_validator/
│       ├── __init__.py              # Public API: validate(), L1Metrics, L2Metrics
│       ├── config.py                # ValidationConfig dataclass
│       ├── pipeline.py              # ValidationPipeline (replaces engine.py)
│       │
│       ├── protocols/
│       │   ├── __init__.py
│       │   ├── theory.py            # BehavioralTheory Protocol
│       │   ├── checker.py           # HallucinationChecker Protocol
│       │   ├── grounding.py         # GroundingStrategy Protocol
│       │   ├── loader.py            # TraceLoader Protocol
│       │   └── normalizer.py        # ActionNormalizer Protocol
│       │
│       ├── metrics/
│       │   ├── __init__.py
│       │   ├── l1_micro.py          # CACR, R_H, EBE (ZERO domain imports)
│       │   ├── l2_macro.py          # EPI + pluggable benchmarks (ZERO domain imports)
│       │   ├── cgr.py               # CGR with pluggable GroundingStrategy
│       │   ├── bootstrap.py         # Generic bootstrap CI (already clean)
│       │   ├── null_model.py        # Pluggable action pools
│       │   └── entropy.py           # Shannon entropy (already clean)
│       │
│       ├── benchmarks/
│       │   ├── __init__.py
│       │   └── registry.py          # BenchmarkRegistry (already clean)
│       │
│       ├── io/
│       │   ├── __init__.py
│       │   ├── trace_reader.py      # Generic extraction helpers
│       │   └── state_inference.py   # Generic state inference
│       │
│       ├── reporting/
│       │   ├── __init__.py
│       │   ├── report_builder.py
│       │   └── serialization.py     # _to_json_serializable
│       │
│       └── contrib/                 # Domain-specific plugins
│           ├── __init__.py
│           ├── flood/
│           │   ├── __init__.py      # flood_config() preset
│           │   ├── theory.py        # PMTTheory
│           │   ├── benchmarks.py    # 8 flood benchmarks + EMPIRICAL_BENCHMARKS
│           │   ├── hallucinations.py
│           │   ├── grounding.py     # ground_tp/cp_from_state
│           │   └── normalizer.py    # FloodActionNormalizer
│           └── irrigation/
│               ├── __init__.py
│               ├── theory.py        # IrrigationWSATheory
│               ├── benchmarks.py
│               └── ...
│
├── tests/
│   ├── test_l1_micro.py
│   ├── test_l2_macro.py
│   ├── test_cgr.py
│   ├── test_bootstrap.py
│   ├── test_null_model.py
│   ├── test_protocols.py           # Protocol conformance tests
│   └── contrib/
│       ├── test_flood.py
│       └── test_irrigation.py
│
├── docs/
│   ├── quickstart.md
│   ├── extending.md               # "Add your domain in 4 steps"
│   └── api/                       # Auto-generated from docstrings
│
└── examples/
    ├── quickstart_flood.py
    ├── quickstart_irrigation.py
    └── custom_theory.py
```

Key design decisions:
- `src/` layout for proper packaging (PEP 517/518)
- `contrib/` for first-party domain plugins (NOT separate packages -- too fragmented for an early-stage SDK)
- `protocols/` as a standalone sub-package so users can import just the interfaces
- Core metrics have **ZERO imports from contrib/** -- enforced by CI lint rule

### The 5-Minute Quickstart

```python
from llm_abm_validator import validate
from llm_abm_validator.contrib.flood import flood_config

# One-line validation
report = validate("./traces/", "./agent_profiles.csv", config=flood_config())
print(f"L1 CACR: {report.l1.cacr}, L2 EPI: {report.l2.epi}, Pass: {report.pass_all}")

# Custom domain (no flood dependency)
from llm_abm_validator import ValidationConfig, validate
from my_domain import MyTheory, MyBenchmarks, MyChecker

config = ValidationConfig(
    theory=MyTheory(),
    hallucination_checker=MyChecker(),
    benchmarks=MyBenchmarks.EMPIRICAL,
    benchmark_registry=MyBenchmarks.registry,
)
report = validate("./traces/", "./profiles.csv", config=config)
```

That is under 10 lines for both the batteries-included and custom-domain paths.

---

## Testing Architecture Recommendations

### Current State
- 6 test files, ~169 tests (reported), good unit coverage for CGR, bootstrap, null model
- Tests use `sys.path` manipulation instead of proper package installation (fragile)
- No property-based testing, no integration pipeline tests

### Recommended Additions

1. **Protocol conformance tests**: Parametrize across all theory implementations
```python
@pytest.mark.parametrize("theory", [PMTTheory(), TPBTheory(), IrrigationWSATheory()])
def test_theory_protocol_conformance(theory):
    assert isinstance(theory, BehavioralTheory)
    assert len(theory.dimensions) > 0
    assert len(theory.agent_types) > 0
```

2. **Property-based testing with Hypothesis**: CACR must be in [0,1], EBE must be non-negative, EPI must be in [0,1]
```python
from hypothesis import given, strategies as st

@given(st.lists(st.sampled_from(["do_nothing", "buy_insurance", "elevate"]), min_size=1))
def test_cacr_bounded(actions):
    traces = [make_trace(a) for a in actions]
    result = compute_l1_metrics(traces)
    assert 0.0 <= result.cacr <= 1.0
```

3. **Integration smoke test**: Full pipeline with synthetic 10-agent, 3-year traces

4. **Regression snapshot tests**: Golden file comparison for known trace inputs

---

## Would I Hire Someone Based on This Code?

**Yes, with enthusiasm for the design sensibility, and coaching notes on shipping discipline.**

What this code tells me about the developer:

1. **They understand abstraction boundaries**: The Protocol-based theory system, the BenchmarkRegistry with decorator dispatch, the layered L1/L2/CGR hierarchy -- these are not copy-paste patterns. Someone thought carefully about where extension points should live.

2. **They know when NOT to abstract**: The `_to_json_serializable` helper, the `_normalize_action` mapping table, the `_is_adjacent` utility -- these are pragmatic, readable, not over-engineered. No AbstractSerializerFactory.

3. **They ship under pressure**: The flood-specific coupling is clearly a "get it working for the paper" decision, not ignorance. The `examples.py` file with TPB and IrrigationWSA proves they already know how to generalize -- they just did not have time to plumb it through the pipeline.

4. **They write tests**: 169 tests for a research validation module is unusual. Most academic code has zero. The test structure (TestGroundTP, TestCohensKappa, TestComputeCGR with `_make_trace` helper) shows someone who has written production test suites before.

5. **Growth area -- configuration management**: The hardcoded constants (action pools, file patterns, action space sizes) suggest less experience with config-driven frameworks. This is learnable.

6. **Growth area -- logging**: Using `print()` instead of `logging` in a library is a common anti-pattern in scientific computing. It works in scripts but breaks composability. Easy fix.

**Bottom line**: This is someone who can design a framework but was pressured to deliver a product. The architecture is 80% right. The remaining 20% is execution work (decouple imports, add protocols, create config layer), not design work. That is the easier half of the problem to solve.

---

## Summary Verdict

| Aspect | Grade |
|--------|-------|
| **Design intent** | A- (Protocol system, layered metrics, registry pattern) |
| **Current coupling** | C+ (4 hard flood imports in core, hardcoded constants) |
| **Path to SDK** | B (clear 4-phase plan, ~2-3 weeks, no rewrites needed) |
| **Test maturity** | B- (good units, missing property/integration/conformance) |
| **Documentation** | C (good docstrings, no user-facing tutorials or quickstart) |
| **Overall SDK-readiness** | **3.2 / 5.0** |

The module is **not** pip-installable today, but it is **one focused refactoring sprint away** from being a genuinely useful open-source validation SDK for the LLM-ABM community. The architectural foundation is solid. Ship the decoupling.
