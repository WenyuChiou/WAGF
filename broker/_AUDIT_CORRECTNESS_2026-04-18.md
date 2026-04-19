# Broker Correctness Audit

Date: 2026-04-18

## 1. Scope declaration

This pass followed `.ai/codex_task_broker_audit_phase2_correctness.md` with one necessary environment workaround: `pytest-timeout` is not installed, and Python 3.14 tempdir cleanup in this workspace produced false infrastructure errors. To keep the run read-only against `broker/` while still completing the audit, I ran pytest with a temporary plugin loaded from scratch space, disabled the builtin `tmpdir` plugin, and redirected temp usage to a writable scratch root outside `broker/`. No LLM or Ollama calls were made.

Skipped tests:

| Test or scope | Reason |
|---|---|
| `tests/integration/test_real_llm_smoke.py` | Explicit real-Ollama smoke test; excluded per task brief |
| 9 tests skipped by suite | Built-in skips in the test suite; no manual extra skip filter applied |

Actual commands used:

```text
python -m pytest tests/ --ignore=tests/integration/test_real_llm_smoke.py --collect-only -q
python -m pytest -p audit_tmp_plugin -p no:tmpdir tests/ --ignore=tests/integration/test_real_llm_smoke.py --audit-tmp-root C:\Users\wenyu\.codex\memories\broker_audit_tmp\tmp_root_final -x --tb=short --durations=0 -o cache_dir=C:\Users\wenyu\.codex\memories\broker_audit_tmp\cache_final -q
python -m pytest -p audit_tmp_plugin -p no:tmpdir tests/ --ignore=tests/integration/test_real_llm_smoke.py --audit-tmp-root C:\Users\wenyu\.codex\memories\broker_audit_tmp\tmp_root_final --tb=short --durations=0 -o cache_dir=C:\Users\wenyu\.codex\memories\broker_audit_tmp\cache_final -q --junitxml C:\Users\wenyu\.codex\memories\broker_audit_tmp\full2_junit.xml
python -m pytest -p audit_tmp_plugin -p no:tmpdir tests/ --ignore=tests/integration/test_real_llm_smoke.py --audit-tmp-root C:\Users\wenyu\.codex\memories\broker_audit_tmp\tmp_root_cov --cov=broker --cov-report=term-missing -o cache_dir=C:\Users\wenyu\.codex\memories\broker_audit_tmp\cache_cov -q
```

The `-x` reconnaissance pass stopped on `tests/flood/test_parsing.py::TestInstitutionalParsing::test_government_decision_numeric`. The final full pass completed successfully as a suite run and produced stable counts.

## 2. Discovery report

- Collected tests: 1829
- Collection errors: 0
- Import errors: 0
- First-pass discovery also confirmed the known pydantic warnings from `broker/config/schema.py` and did not touch the real-Ollama smoke file

## 3. Test run summary

| Metric | 2026-02-11 baseline | 2026-04-18 run | Delta |
|---|---|---|---|
| Tests passed | 1776 | 1808 | +32 |
| Tests failed | 18 | 12 | -6 |
| Tests errored | 0 | 0 | 0 |
| Tests skipped | ? | 9 | n/a |
| New regressions | 0 | 12 | +12 |
| Wall time | ? | 46.21s | n/a |

Only one test exceeded 5 seconds in the final full run:

| Test | Duration |
|---|---|
| `tests/core/test_experiment_runner.py::TestSingleYearExecution::test_single_year_completes` | 7.24s |

## 4. Failure list with categorisation

Heuristic used: a failure is marked **NEW** when the test file was unchanged since 2026-02-11 but the implicated production module changed after 2026-02-11, indicating a likely regression introduced in code rather than a historically failing test.

| Test | Last-modified (test file) | Last-modified (subject module) | Category | Failure type | 1-line visible cause |
|---|---|---|---|---|---|
| `tests/flood/test_parsing.py::TestInstitutionalParsing::test_government_decision_numeric` | 2026-02-11 | `broker/utils/parsing/unified_adapter.py` 2026-04-03 | NEW | assert | numeric code `1` maps to `large_increase_subsidy` instead of `increase_subsidy` |
| `tests/flood/test_parsing.py::TestInstitutionalParsing::test_government_decision_text` | 2026-02-11 | `broker/utils/parsing/unified_adapter.py` 2026-04-03 | NEW | assert | text parse returns `maintain_subsidy` instead of `increase_subsidy` |
| `tests/flood/test_parsing.py::TestInstitutionalParsing::test_insurance_decision_numeric` | 2026-02-11 | `broker/utils/parsing/unified_adapter.py` 2026-04-03 | NEW | assert | numeric insurance parse returns `significantly_improve_crs` instead of `improve_crs` |
| `tests/flood/test_parsing.py::TestInstitutionalParsing::test_insurance_decision_text` | 2026-02-11 | `broker/utils/parsing/unified_adapter.py` 2026-04-03 | NEW | assert | text insurance parse also resolves to the larger action alias |
| `tests/test_irrigation_integration.py::test_execute_skill_decrease_demand` | 2026-02-11 | `examples/irrigation_abm/irrigation_env.py` 2026-03-03 | NEW | assert | actual request is `73777.78` vs expected tapered value `72222.22` |
| `tests/test_ma_reflection.py::TestMAReflectionIntegration::test_run_ma_reflection_called_in_post_year` | 2026-02-11 | `examples/multi_agent/flood/orchestration/lifecycle_hooks.py` 2026-04-11 | NEW | assert | post-year hook stores a plain memory string, not a `Consolidated Reflection:` memory |
| `tests/test_ma_reflection.py::TestMAReflectionIntegration::test_reflection_uses_stratified_retrieval_params` | 2026-02-11 | `examples/multi_agent/flood/orchestration/lifecycle_hooks.py` 2026-04-11 | NEW | assert | reflection allocation is `{personal:3, neighbor:1, reflection:1}` instead of expected reflection-heavy split |
| `tests/test_ma_reflection.py::TestMAReflectionIntegration::test_reflection_logic_skips_if_no_flood` | 2026-02-11 | `examples/multi_agent/flood/orchestration/lifecycle_hooks.py` 2026-04-11 | NEW | assert | `retrieve_stratified()` is still called when `flood_occurred=False` |
| `tests/test_tiered_builder_no_hub.py::TestTieredBuilderNoHub::test_build_no_hub_returns_context` | 2026-02-11 | `broker/components/context/providers.py` 2026-02-24 | NEW | assert | provider compares `MagicMock` income to `int`, causing `TypeError` |
| `tests/test_tiered_builder_no_hub.py::TestTieredBuilderNoHub::test_build_no_hub_fallback_structure` | 2026-02-11 | `broker/components/context/providers.py` 2026-02-24 | NEW | assert | same `income > 0` `TypeError` path in no-hub fallback |
| `tests/test_tiered_builder_no_hub.py::TestTieredBuilderNoHub::test_build_no_hub_with_env_context` | 2026-02-11 | `broker/components/context/providers.py` 2026-02-24 | NEW | assert | same `MagicMock` vs `int` comparison with env context |
| `tests/test_tiered_builder_no_hub.py::TestTieredBuilderNoHub::test_build_no_hub_agent_type` | 2026-02-11 | `broker/components/context/providers.py` 2026-02-24 | NEW | assert | same provider type/comparison failure before context completion |

The failure shape is concentrated rather than broad. Four regressions are parser/action-alias mismatches, three are MA reflection policy changes, four are the same no-hub context-provider type assumption, and one is irrigation execution math drift. That is materially narrower than the February failure count, but it is not “0 new regressions”; it is a new regression cluster in four areas.

## 5. Coverage report

Overall broker coverage from the scoped pass: **73%** (`15459` statements, `11222` covered, `4237` missed).

### 5a. `broker/components/*` sub-packages

| Package | LOC | Covered | % |
|---|---:|---:|---:|
| `broker.components.analytics` | 842 | 594 | 71 |
| `broker.components.cognitive` | 367 | 182 | 50 |
| `broker.components.context` | 702 | 464 | 66 |
| `broker.components.coordination` | 347 | 330 | 95 |
| `broker.components.events` | 537 | 436 | 81 |
| `broker.components.governance` | 235 | 158 | 67 |
| `broker.components.memory` | 1175 | 733 | 62 |
| `broker.components.orchestration` | 225 | 214 | 95 |
| `broker.components.prompt_templates` | 114 | 109 | 96 |
| `broker.components.social` | 371 | 232 | 63 |

### 5b. Top-level broker directories

| Package | LOC | Covered | % |
|---|---:|---:|---:|
| `broker.agents` | 198 | 119 | 60 |
| `broker.config` | 445 | 398 | 89 |
| `broker.core` | 1694 | 1035 | 61 |
| `broker.domains` | 247 | 213 | 86 |
| `broker.governance` | 242 | 180 | 74 |
| `broker.interfaces` | 717 | 655 | 91 |
| `broker.memory` | 1420 | 1136 | 80 |
| `broker.modules` | 373 | 138 | 37 |
| `broker.simulation` | 168 | 71 | 42 |
| `broker.utils` | 1576 | 991 | 63 |
| `broker.validators` | 3307 | 2688 | 81 |

Modules below 50% coverage: `broker/agents/loader.py`, `broker/components/analytics/interaction.py`, `broker/components/cognitive/trace.py`, `broker/components/governance/permissions.py`, `broker/components/memory/initial_loader.py`, `legacy.py`, `policy_classifier.py`, `policy_filter.py`, `seeding.py`, `universal.py`, `broker/components/social/graph.py`, `broker/core/_audit_helpers.py`, `_retry_loop.py`, `experiment_builder.py`, `broker/domains/water/cognitive_appraisal.py`, `broker/interfaces/schemas.py`, `broker/memory/embeddings.py`, `broker/modules/survey/survey_loader.py`, `broker/simulation/base_simulation_engine.py`, `state_manager.py`, `broker/utils/adapters/deepseek.py`, `data_loader.py`, `json_repair.py`, `llm_utils.py`, `broker/validators/agent/agent_validator.py`, `base.py`, `broker/validators/calibration/conservatism_diagnostic.py`, `broker/validators/posthoc/keyword_classifier.py`.

Modules at 0% coverage and worth Phase 4 review as dead-code or dormant-code candidates: `broker/components/cognitive/trace.py`, `broker/components/governance/permissions.py`, `broker/interfaces/schemas.py`, `broker/memory/embeddings.py`, `broker/simulation/base_simulation_engine.py`, `broker/validators/agent/base.py`, `broker/validators/calibration/conservatism_diagnostic.py`.

## 6. Warning summary

Confirmed known warnings:

- `broker/config/schema.py:142`: `RuleCondition.construct` shadows a `BaseModel` attribute
- `broker/config/schema.py:172`: `GovernanceRule.construct` shadows a `BaseModel` attribute

Other unique warnings seen during scoped runs:

- `requests` emitted `RequestsDependencyWarning` about unsupported `urllib3` / `chardet` / `charset_normalizer` version combinations
- `langsmith.schemas` emitted a `UserWarning` that Pydantic v1 compatibility is not supported on Python 3.14+
- `examples/multi_agent/flood/initial_memory.py` emitted a deprecation warning to import from `broker.components.prompt_templates.memory_templates`
- `broker.core.psychometric` old import paths emitted framework-move deprecations for PMT, Utility, and Financial frameworks
- Python import bootstrap emitted three SWIG-related `DeprecationWarning`s for missing `__module__`
- `tests/flood/test_module_integration.py` and `broker/components/memory/registry.py` emitted deprecation warnings for `ImportanceMemoryEngine` and `HierarchicalMemoryEngine`
- `scipy.stats.ks_2samp` emitted a runtime warning that exact calculation failed and it switched to `method=asymp`
- `broker/validators/posthoc/unified_rh.py` and `thinking_rule_posthoc.py` emitted pandas `FutureWarning`s on silent downcasting after `fillna(...).infer_objects(...)`
- `broker/memory/persistence.py` emitted deprecation warnings for `datetime.utcnow()`

## 7. Phase 3 readiness

Phase 3 is not blocked by infrastructure anymore, but it is blocked by correctness debt. The suite is now runnable without touching Ollama, and coverage is solid enough to support an interface audit. The blocker is the 12-regression cluster in parser aliasing, irrigation skill execution math, MA reflection orchestration, and no-hub context building. If Phase 3 assumes current broker behavior is semantically trustworthy, those four areas should be fixed or explicitly waived first; otherwise the interface audit will be measuring unstable behavior rather than a known-good baseline.
