# Software Engineering Review: WAGF C&V Validation Module

**Reviewer**: Sarah Zhang, Senior Software Engineer (Python frameworks, open-source library design)
**Date**: 2026-02-14
**Scope**: Architecture, API design, extensibility, and package-readiness assessment

---

## Executive Summary

The C&V validation module is a well-structured, domain-specific validation pipeline for LLM-driven ABMs. It exhibits clear separation of concerns across 7 sub-packages (theories, metrics, benchmarks, io, hallucinations, reporting, configs) and uses Protocol-based extensibility that would be familiar to any scikit-learn contributor. The codebase is **approximately 70% ready** for extraction into a standalone `pip install llm-abm-validation` package. The main gaps are: tight coupling to the flood domain in the engine, reliance on `sys.path` hacks for import resolution, some functions that bypass the Protocol/Registry patterns they define, and the absence of streaming for large trace files.

**Overall Assessment**: 3.8 / 5.0 -- a strong research codebase with genuine library aspirations, but requiring a focused extraction pass before PyPI publication.

---

## Dimension Scores

| # | Dimension | Score | Summary |
|---|-----------|-------|---------|
| 1 | API Design | 4/5 | Clean top-level API; some private leakage |
| 2 | Separation of Concerns | 4/5 | Logical split; engine.py is borderline god-module |
| 3 | Extensibility Patterns | 4/5 | Protocol + Registry well-done; not yet wired into pipeline |
| 4 | Error Handling | 3/5 | Handles missing files; bare except in engine; silent fallbacks |
| 5 | Testing Quality | 4/5 | 43+ tests, good coverage; gaps in edge cases |
| 6 | Documentation | 4/5 | Excellent README; inline docstrings could be richer |
| 7 | Package-Readiness | 3/5 | Sub-package structure exists; import plumbing needs work |
| 8 | Code Smells | 3/5 | Duplication between config_loader and modules; underscore-prefixed public API |
| 9 | Performance | 2/5 | All-in-memory; iterrows in CACR decomposition; no streaming |
| 10 | Dependency Management | 4/5 | Lean (pandas, numpy); optional yaml handled gracefully |

---

## Detailed Analysis

### 1. API Design (4/5)

**Strengths:**
- `__init__.py` exports a clean, minimal public surface: `compute_validation()`, `compute_l1_metrics()`, `compute_l2_metrics()`, `load_traces()`, plus data classes. A new user can call `compute_validation(traces_dir, profiles_path, output_dir)` and get a `ValidationReport` -- that is a good one-liner entry point.
- Function signatures are intuitive. `compute_l1_metrics(traces, agent_type)` and `compute_l2_metrics(traces, agent_profiles)` are self-explanatory.
- Data classes (`L1Metrics`, `L2Metrics`, `ValidationReport`, `CACRDecomposition`) provide structured return types rather than raw dicts.

**Issues:**
- `_to_json_serializable` is exported in `__all__` with a leading underscore. This signals "private" but is publicly exposed -- pick one convention. Either rename to `to_json_serializable` or remove from `__all__`.
- `compute_validation()` in `engine.py` does too many things: loads traces, computes L1, computes L2, extracts metadata, writes 4 output files, prints progress. The I/O side-effects (file writing, print statements) should be separated from the computation. A user who wants the `ValidationReport` object without writing files cannot currently do so.
- The backward-compatibility wrapper (`compute_validation_metrics.py`) re-exports 20+ symbols including private functions (`_extract_tp_label`, `_is_hallucination`). This creates a parallel import surface that will confuse users.

**Recommendation:** Split `compute_validation()` into `compute_validation()` (pure computation) and `save_validation_report()` (file I/O). Remove private symbols from `__all__` and the backward-compat wrapper.

### 2. Separation of Concerns (4/5)

**Strengths:**
- The 7 sub-packages map cleanly to concerns:
  - `theories/` -- behavioral theory Protocol, implementations, registry
  - `metrics/` -- L1 micro, L2 macro, entropy
  - `benchmarks/` -- benchmark definitions and registry
  - `io/` -- trace reading, state inference
  - `hallucinations/` -- impossible action detection
  - `reporting/` -- report builder, CLI
  - (external) `configs/` -- YAML externalization via config_loader
- No circular imports detected in the sub-packages.
- `entropy.py` is properly isolated as a pure function.

**Issues:**
- `engine.py` is a borderline god-module: it orchestrates L1, L2, CACR decomposition, metadata extraction, and 4 file writes in a single 200-line function. It also directly references `EMPIRICAL_BENCHMARKS` from `benchmarks/flood.py` rather than accepting benchmarks as a parameter.
- `l1_micro.py` directly imports `PMT_OWNER_RULES` and `PMT_RENTER_RULES` rather than going through the `TheoryRegistry` or accepting a `BehavioralTheory` instance. This means the Protocol/Registry pattern exists but is not actually used in the main computation path.
- `l2_macro.py` imports `PMT_OWNER_RULES` and `PMT_RENTER_RULES` (line 12) but does not appear to use them -- dead import.
- `config_loader.py` sits outside the `validation/` package in `analysis/`, creating an architectural boundary ambiguity.

**Recommendation:** Wire `compute_l1_metrics()` to accept an optional `BehavioralTheory` parameter (defaulting to PMT via the registry). Move `config_loader.py` into `validation/config/`. Extract file-writing from `engine.py` into `reporting/`.

### 3. Extensibility Patterns (4/5)

**Strengths:**
- `BehavioralTheory` as a `@runtime_checkable` Protocol is the right choice for Python -- it is structural typing, not requiring inheritance. This is exactly how scikit-learn's estimator checks work.
- The Protocol has 5 clear methods: `name`, `dimensions`, `agent_types`, `get_coherent_actions`, `extract_constructs`, `is_sensible_action`.
- `TheoryRegistry` with `register()` / `get()` / `set_default()` / `default` property is clean.
- `BenchmarkRegistry` with decorator-based registration (`@_registry.register("insurance_rate_sfha")`) is Pythonic and familiar (Flask/FastAPI style).
- Example implementations (TPBTheory, IrrigationWSATheory) demonstrate extensibility convincingly.
- `PMTTheory.__init__` accepts custom rules, allowing override without subclassing.

**Issues:**
- The `BenchmarkRegistry.dispatch()` signature is rigid: `(name, df, traces, ins_col, elev_col)`. The `ins_col` and `elev_col` parameters are flood-domain-specific. A generic library would need `**kwargs` or a context object.
- `_is_hallucination()` is a flat function, not a protocol-based pluggable system. For a different domain, you must replace the function entirely rather than registering rules.
- The `config_loader.py` defines rich data classes (`TheoryConfig`, `BenchmarkConfig`, `HallucinationRule`) that are never consumed by the main pipeline. The pipeline uses the hard-coded Python objects directly. This is dead infrastructure.

**Recommendation:** Make `BenchmarkRegistry.dispatch()` accept a generic context dict. Create a `HallucinationChecker` protocol parallel to `BehavioralTheory`. Wire `config_loader` output into the actual pipeline.

### 4. Error Handling (3/5)

**Strengths:**
- `load_traces()` handles empty lines gracefully (`if line.strip()`).
- `compute_validation()` raises `ValueError` on zero traces -- fail-fast is correct.
- `_compute_benchmark()` catches all exceptions and returns `None` with a warning -- graceful degradation for individual benchmarks.
- `config_loader.py` handles missing YAML gracefully with `None` returns and hard-coded fallbacks.
- `_is_hallucination()` handles `state_before` as both dict and JSON string.
- Coverage check warns when < 90% of profiled agents have traces.

**Issues:**
- `engine.py:124` has a bare `except: pass` for seed extraction. This silently swallows all exceptions including `KeyboardInterrupt`. Use `except (ValueError, IndexError): pass` at minimum.
- `_normalize_action()` silently returns the raw action string if it does not match any mapping. This means typos in action names (e.g., "buY_insurance") pass through without warning. At scale (500K traces), a 1% typo rate means 5,000 silently miscategorized decisions.
- `compute_cacr_decomposition()` uses `iterrows()` which is slow and prints warnings to stdout rather than using `logging`. In a library context, `print()` statements are an anti-pattern -- they cannot be suppressed or redirected.
- `_extract_final_states_from_decisions()` silently skips REJECTED and UNCERTAIN traces and traces where `validated=False`, but never reports how many were skipped.

**Recommendation:** Replace all `print()` with `logging`. Replace bare `except` with specific exception types. Add a `strict` mode that raises on unrecognized actions rather than passing them through.

### 5. Testing Quality (4/5)

**Strengths:**
- `test_decision_based_inference.py` (43+ tests across 7 test classes) is thorough:
  - Unit tests for each state inference scenario (insurance lapse, irreversible elevation, buyout, relocation)
  - Integration tests for L2 benchmarks with synthetic data
  - Regression tests explicitly documenting the state_after bug
  - Parametrized normalization tests
  - Edge cases: empty traces, missing agent_id, out-of-order years, malformed traces
- `test_behavioral_theory.py` validates Protocol compliance, rule consistency, registry operations, and example theories.
- `test_config_loader.py` ensures YAML/hard-coded parity -- a good "golden master" pattern.
- Tests use `pytest.approx()` correctly for floating-point comparisons.
- Test helper `make_trace()` is well-designed for readability.

**Gaps:**
- No tests for `engine.py` (`compute_validation()`) as an integration test. The main pipeline is only tested through its sub-components.
- No tests for `load_traces()` -- file I/O with glob patterns is tricky and should be tested with `tmp_path`.
- No tests for `cli.py` (`main()`).
- No tests for `_to_json_serializable()` with edge cases (nested numpy arrays, NaN values, pandas Timestamps).
- No tests for `_compute_entropy()` directly (only tested indirectly through L1 metrics).
- No negative tests for malformed JSONL files (truncated lines, non-UTF8 encoding, mixed schemas).
- The `sys.path` manipulation in test files is fragile. If the repo structure changes, all test files break.

**Recommendation:** Add integration tests for `compute_validation()` using `tmp_path` fixtures. Add property-based tests (hypothesis) for normalization round-trips. Test entropy edge cases (single element, very large distributions).

### 6. Documentation (4/5)

**Strengths:**
- `README.md` is excellent: three-level architecture diagram, metric tables with thresholds and literature sources, usage examples, input format specification, domain adaptation guide with code examples, and known limitations with a roadmap.
- The README's "Adapting to Other Domains" section with TPB and irrigation examples is genuinely useful for onboarding.
- Module-level docstrings are present in every file and describe purpose clearly.
- `BehavioralTheory` Protocol has docstrings on every method with Args/Returns.
- The `CLAUDE.local.md` serves as effective machine-readable documentation.

**Issues:**
- `README.md` Phase 2-5 in the roadmap are marked as "Planned" but Phases 2-3 are actually complete (sub-modules exist, Protocol + Registry exist). This is stale.
- Function-level docstrings are minimal in `l1_micro.py` and `l2_macro.py`. `compute_l2_metrics()` has no docstring explaining parameters.
- No API reference documentation (Sphinx/mkdocs). For a library, auto-generated API docs are table stakes.
- No CHANGELOG or versioning scheme.
- The `validation/` package has no README of its own.

**Recommendation:** Update README roadmap. Add Sphinx-compatible docstrings (numpy or Google style) to all public functions. Add a minimal `docs/` with auto-generated API reference.

### 7. Package-Readiness (3/5)

**Strengths:**
- Sub-package structure is already correct for a pip-installable package.
- `__init__.py` with `__all__` is properly defined.
- Dependencies are minimal (pandas, numpy, optional yaml).
- `cli.py` with `argparse` is ready to become an entry point.
- The code is pure Python with no compiled extensions.

**Issues:**
- **No `setup.py` or `pyproject.toml`**. The package lives 6 levels deep inside an example directory.
- **Import path: `from validation.X import Y`** assumes the `analysis/` directory is on `sys.path`. A real package would be `from llm_abm_validation.X import Y`. The current approach requires `sys.path.insert()` hacks in every consumer.
- The backward-compat wrapper `compute_validation_metrics.py` manipulates `sys.path` at import time (lines 31-38). This is a deployment hazard.
- `config_loader.py` uses relative imports from `compute_validation_metrics` for fallback defaults (line 273: `from compute_validation_metrics import PMT_OWNER_RULES`). This creates a circular dependency between the wrapper and the package.
- The `_default_registry` module-level singleton in `theories/registry.py` uses lazy initialization with a global variable. This is fine for a script but problematic for testing (state leaks between tests).
- No `py.typed` marker for type checking support.
- No `__version__` attribute.

**Recommendation:** Create a standalone `llm-abm-validation/` directory at repo root with `pyproject.toml`. Use relative imports within the package. Add `__version__`. Replace the backward-compat wrapper with a deprecation shim that imports from the new package location.

### 8. Code Smells (3/5)

**Duplication:**
- Action normalization mappings appear in both `trace_reader.py` (the `mappings` dict in `_normalize_action()`) and `config_loader.py` (`action_aliases` in `TheoryConfig`). These should be a single source of truth.
- PMT rules are defined in `pmt.py`, also loadable from YAML via `config_loader.py`, and also re-exported via the backward-compat wrapper. Three sources of truth for the same data.
- The `_get_rules_for_row()` function inside `compute_cacr_decomposition()` uses a magic number (`num > 200` means renter). This is fragile coupling to the agent ID naming convention.

**Naming:**
- Many public functions have leading underscores (`_compute_benchmark`, `_compute_entropy`, `_is_hallucination`, `_extract_tp_label`). These are used across module boundaries, which contradicts the "private" convention. Either remove the underscore or make them genuinely private by exposing through a public wrapper.
- `_to_json_serializable` is exported in `__all__` -- contradictory.

**Complexity:**
- `compute_cacr_decomposition()` at 120 lines is the longest function and mixes CSV parsing, column detection, agent type inference, coherence computation, retry rate computation, and fallback rate computation. This should be decomposed.
- The `_compute_mg_adaptation_gap()` function checks 5 hardcoded column names. If a new protective action is added, this function must be manually updated.

**Anti-patterns:**
- `print()` used throughout for logging (27+ print statements in engine.py alone).
- Module-level mutable state in `theories/registry.py` (`_default_registry = None`).

### 9. Performance (2/5)

**Bottlenecks:**
- `load_traces()` reads all JSONL files into memory as a list of dicts. For 500K traces at ~1KB each, this is ~500MB. No streaming or chunked processing.
- `compute_cacr_decomposition()` uses `audit.iterrows()` -- the single slowest pattern in pandas. For 50K audit rows, this dominates runtime. Should use vectorized operations.
- `_compute_insurance_lapse_rate()` iterates all traces to build per-agent timelines, then iterates again. Two O(N) passes where one would suffice with a sorted groupby.
- `_extract_final_states_from_decisions()` iterates all traces in a single pass -- this is correctly O(N), but the dict-of-dicts structure means high allocation pressure for large trace counts.
- `compute_l2_metrics()` iterates `final_states` and does per-agent `df.loc[mask]` updates. For 400 agents this is fine; for 10K agents this is O(N*M) where M is DataFrame rows.
- No caching. If you call `compute_l1_metrics()` and `compute_l2_metrics()` separately (as users might), trace processing work is duplicated.

**Recommendation:** Add a `TraceIterator` that streams JSONL files line by line. Replace `iterrows()` with vectorized pandas operations. For large-scale use, consider a `polars` backend option.

### 10. Dependency Management (4/5)

**Strengths:**
- Core dependencies are just `pandas` and `numpy` -- appropriate and minimal.
- `yaml` is optional with a clean `try/except ImportError` guard.
- No heavyweight ML dependencies (torch, tensorflow, etc.).
- No vendored code or pinned versions.
- Standard library used where possible (`json`, `math`, `pathlib`, `collections`, `dataclasses`).

**Issues:**
- `numpy` is only used in `report_builder.py` for type conversion (`np.bool_`, `np.integer`, etc.) and in one test. This dependency could be eliminated if `_to_json_serializable` used duck typing instead.
- No `requirements.txt` or dependency specification file.
- No lower/upper version bounds specified for pandas/numpy.

---

## Package Extraction Roadmap

If the goal is `pip install llm-abm-validation`, here is a prioritized task list:

### P0: Blocking for PyPI

1. Create `pyproject.toml` with package metadata, dependencies, entry points
2. Rename package to `llm_abm_validation/` (PEP 8 compliant)
3. Fix all imports to be relative within the package
4. Remove `sys.path` manipulation from all modules
5. Add `__version__`
6. Replace all `print()` with `logging.getLogger(__name__)`

### P1: Required for credible library

7. Wire `BehavioralTheory` Protocol into `compute_l1_metrics()` (accept theory parameter)
8. Wire `BenchmarkRegistry` into `compute_l2_metrics()` (accept benchmarks parameter)
9. Separate computation from I/O in `engine.py`
10. Add integration tests for `compute_validation()` and `load_traces()`
11. Remove bare `except` and fix error specificity
12. Eliminate duplication between config_loader and module-level constants

### P2: Nice to have

13. Streaming `TraceIterator` for large files
14. Replace `iterrows()` with vectorized operations
15. Sphinx documentation with auto-generated API reference
16. `HallucinationChecker` protocol for pluggable domain rules
17. Type stubs and `py.typed` marker

---

## Conclusion

This is a genuinely well-designed research codebase that has already undergone significant architectural improvement (the sub-package split, Protocol/Registry patterns, YAML externalization). The main gap is that the extensibility patterns exist but are not yet wired into the actual computation pipeline -- the Protocol and Registry are defined but `compute_l1_metrics()` still hard-codes PMT rules via direct import. Closing that gap, plus the mechanical work of proper packaging (pyproject.toml, relative imports, logging), would make this a credible open-source library.

The test suite is strong for a research project (43+ tests with good edge case coverage), but needs integration tests and property-based tests for library-grade confidence. The README is publication-quality and would serve well as the basis for library documentation.

**Bottom line**: With approximately 2-3 focused engineering days, this could go from "good research code" to "installable library with proper packaging." The architectural bones are already there.
