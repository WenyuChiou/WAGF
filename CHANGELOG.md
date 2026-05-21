# Changelog

All notable changes to the Water Agent Governance Framework (WAGF) will be
documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Phase 6H (DomainPack v2 + genericity hardening) — **Items 1–5 of 8**.
Net-zero test regression vs v0.3.0 (full `broker/ tests/`: 11 failures,
all pre-existing and identical before/after); real-model `gemma4:e4b`
smoke green. Items 6–8 (affordability validator, FinancialCostProvider
dedup, thinking-validator rules) and the reflection status-text /
importance fallbacks remain on the I5 `TestDomainGenericity` KNOWN-DEBT
allowlist — the framework is more generic but not yet
flood-coupling-free.

### Added

- **DomainPack v2 contract** (Item 2): three hooks added to the
  `DomainPack` Protocol — `perception_descriptors()`,
  `perception_field_policy()`, `retrieval_policy()` — each with a no-op
  default in `DefaultDomainPack`. `FloodDomainPack` / `IrrigationDomainPack`
  / `VaccinationDomainPack` now subclass `DefaultDomainPack`, so future
  protocol additions auto-default instead of breaking `isinstance`.
- **Config-driven skill retrieval** (Item 3):
  `AgentTypeConfig.get_retrieval_config()` resolves `top_n` / `min_score`
  from `global_config.governance.retrieval` YAML and
  `DomainPack.retrieval_policy()`; framework defaults unchanged
  (top_n=3, min_score=0.05).
- **Build-time `default_skill` enforcement** (Item 3):
  `SkillRegistry.has_explicit_default_skill()`; `ExperimentBuilder.build()`
  now fails fast — before any LLM call — when a domain never declared a
  `default_skill:` (INVARIANTS.md §I5 rule 4).
- **Domain-definable reflection questions** (Item 4):
  `AgentTypeConfig.get_reflection_questions(agent_type)` resolves questions
  from per-agent-type or domain-wide `agent_types.yaml`, or
  `DomainPack.reflection_questions()` (previously a never-called hook).

### Changed

- **Calibration package relocated** (Item 1): the flood-PMT C&V package
  moved `broker/validators/calibration/` → `broker/domains/water/calibration/`,
  out of generic broker code. Pure import-path rename; all importers
  repointed.
- `REFLECTION_QUESTIONS` (the flood-agent-type dict in
  `broker/components/cognitive/reflection.py`) replaced by a domain-neutral
  `_DEFAULT_REFLECTION_QUESTIONS` generic fallback and removed from the
  `broker.components.cognitive` public export;
  `generate_personalized_reflection_prompt()` gains a `reflection_questions`
  parameter.
- **Perception filter de-flooded** (Item 5): `FLOOD_DEPTH_DESCRIPTORS`
  and the flood field-lists moved out of generic broker code to
  `examples/governed_flood/adapters/flood_perception.py`.
  `HouseholdPerceptionFilter` is domain-neutral by default (strips /
  verbalizes nothing); `PerceptionFilterRegistry` injects the active
  DomainPack's `perception_descriptors()` / `perception_field_policy()`.
  `interfaces/perception.py` is now flood-free and off the I5 allowlist.
- **Verbalization fully generic** (Item 5b): the filter's `filter()`
  body is now a single `{input_context_field: DescriptorMapping}`
  lookup loop with zero domain knowledge — it maps numbers to words,
  never computes. A model builder verbalizes any domain's numbers
  (signed changes via negative ranges; same-context ratios via
  `DescriptorMapping.denominator_field`) purely by declaring
  `perception_descriptors()` — no broker or filter edits.
- **Perception filter assignment generic** (Item 5c): new
  `DomainPack.passthrough_agent_types()` hook — the model builder
  declares which agent types perceive raw numbers vs verbalized text.
  The two flood-named pass-through filters collapse into one generic
  `PassThroughPerceptionFilter`; `PerceptionFilterRegistry` hardcodes
  no agent-type names. Default: every agent type verbalizes.
- **Audit tool relocated** (Item 5d): the irrigation-bound
  `appraisal_grounding_audit` post-hoc CLI moved from `broker/tools/`
  to `broker/domains/water/tools/` — out of generic broker code. Zero
  production importers; pure relocation.
- **Affordability validation de-flooded** (Item 6): new
  `DomainPack.affordability_constraints()` hook —
  `AgentValidator.validate_affordability()` no longer hardcodes the
  flood elevation cost model ($150k / 3x income / 50% subsidy); a
  domain declares its own per-decision cost models, or none.
  `agent_validator.py` is now domain-token-free. I5 KNOWN-DEBT
  allowlist down to 3 entries (`thinking_rule_posthoc`, `unified_rh`,
  `reflection.py`).

### Notes

- **Existing experiments unaffected**: irrigation, single-agent flood and
  governed_flood declare `reflection.questions` in YAML → reflection prompts
  byte-identical; retriever / registry defaults preserve pre-6H behaviour.
  MA flood (Paper 3, frozen) reflection now draws from `ma_agent_types.yaml`
  rather than the removed hardcoded dict.

## [0.3.0] - 2026-05-20

Major release: Phase 6A–6G framework genericity + audit hardening + multi-agent
domain support. **88 `broker/` commits since v0.2.0** (Feb–May 2026); broker
side fully green (148 passed, 1 skipped, 0 fails on the 149-test gate).

### Added

#### Framework genericity (Phase 6A → 6C)
- **DomainPack Protocol + Registry** (`broker/components/domain_pack/`):
  declarative domain configuration moving water-specific defaults out of
  generic broker code. Status text, event types, perception filter fields,
  agent-profile structure, validator bundles, financial-cost providers,
  institutional agent types, and reflection adapters all configurable via
  DomainPack.
- **ValidatorRegistry** + **FilterRegistry**: plugin pattern for validator
  and neighbour-filter discovery without touching broker code.
- **scaffold_domain CLI** (`broker.tools.scaffold_domain`): one-command
  domain skeleton for new researchers.
- **validate_prompt CLI** (`broker.tools.validate_prompt`): config-time
  BLOCKER pre-check.
- **Custom framework registration**: support for user-defined behavioural
  frameworks beyond PMT and dual-appraisal.
- **Generic temporal-rule framework** (M1/M2/M3): post-hoc diagnostic
  layer for sequence-level rules (appraisal–history coherence,
  behavioural inertia, evidence-grounded irreversibility) with
  domain-agnostic adapter contract.
- **FloodAgentProfile split** from generic AgentProfile.

#### Audit hardening (Phase 6G)
- **Crash-safe JSONL fsync**: per-decision flush to prevent partial-trace
  loss; `broker.tools.recover_csv_from_jsonl` CLI rebuilds CSV from
  streaming JSONL after crash, with schema parity enforced by
  `tests/test_recover_csv_from_jsonl.py` (INVARIANTS.md §I2 LOAD-BEARING).
- **validator_health.csv**: per-agent-type validator firing-rate audit
  with dead-rule steering (Gate-3 canonical item 4).
- **Audit log schema versioning** (Phase 6G W2): version tag on every CSV
  header for forward-compatible analysis.
- **Shadow|active validator modes** (Phase 6G W4 + W5 end-to-end): per
  validator toggle for staged rollout.
- **Appraisal-grounding post-hoc audit** (Gate-2 #1): trace consistency
  between stated appraisal and chosen action.
- **`fallback_activated` column written at source** (Phase 6G W1 #4a):
  no derived metric; intentional semantic change documented in
  INVARIANTS.md.

#### Framework invariants
- **Five framework invariants** + CI regression guards in
  `broker/tests/test_framework_invariants.py`: memory contract (I1),
  audit integrity (I2), API consistency (I3), dormant-code policy (I4),
  domain-genericity (I5). Plus `tests/test_domain_genericity.py` and
  `tests/test_recover_csv_from_jsonl.py` as additional LOAD-BEARING
  guards. `broker/INVARIANTS.md` is the human-facing index.

#### Memory subsystem
- **Broker-level memory write governance**
  (`broker/components/memory/policy_filter.py`): content-type-aware policy
  proxy preventing the rationalization ratchet for any new MA experiment.
  Nine `MemoryContentType` enum members (6 safe + 3 risky);
  `CLEAN_POLICY` (default) vs `LEGACY_POLICY` selection via
  `ExperimentBuilder.with_memory_write_policy()`.
- **Insertion-order preservation** for equal-salience memories.

#### Multi-agent support
- **Phase 6E multi-agent BLOCKER fixes** generalized from flood-specific
  to generic broker (3 fixes).
- **Phase 6F spatial gossip validation**: community moderator +
  influencer + casual_user reference domain
  (`examples/gossip_demo/`).
- **DomainReflectionAdapter** wired via DomainPack (Invariant 4).

#### Diagnostics
- **Model conservatism diagnostic** (CCA / CSI / ACI / ESRR metrics) for
  cross-model comparison.
- **Audit trace enrichment** + default-skill CLI override.
- **Enhanced reproducibility manifest** + audit thread safety.

### Changed
- **Architecture refactor**: decouple broker from example validators;
  clean public API; deprecate legacy hook aliases; standardize logging.
- **Code organisation**: split god classes; extract domain content;
  parameterize analysis script paths for cross-domain extensibility.
- **`memory_factory.py`** registry-dispatched (continued from v0.2.0).

### Fixed
- **Memory pipeline v2 contract**: `retrieve()` returns `List[MemoryRecord]`
  per Invariant 1; legacy plain-string consumers use
  `retrieve_content_only()`. Memory-dict items coerced to text in
  reflection + irrigation logger.
- **R5 re-elevation bug**: `_inject_filtered_skills` now respects
  pre-filtered `available_skills`.
- **Ollama `think` parameter** must be top-level, not in `options`
  (commit `fc6c599`; corrected all prior Gemma-4 thinking-mode runs).
- **Per-agent exception isolation**: experiment continues on single-agent
  LLM failure (`ac7faea`).
- **Lazy-load faiss** for Python 3.14 import-hang prevention.
- **E5 builtin-check agent-type scoping** (Phase 6G canonical item 2).
- **Keyword classifier negation bug** + IBR formula sync to production
  (R1+R3+R4, R5 excluded per EDT2).
- **SP_REASON keyword collision** + hardcoded reflection stub.

### Removed
- **Eight `tests/test_*_split.py` structural-smoke tests** retired: the
  2026-02 broker restructuring shipped 3 months ago and stayed green;
  structural asserts subsumed by real unit-test coverage of post-split
  modules. Test count **2165 → 2156**. Per
  `.ai/2026/05/18/pytest_inventory.md` §6 Phase 2.

### Documentation
- **Refreshed WAGF architecture figure** (`docs/architecture.png`):
  updated for NW Paper 1b Fig 1 framework (governed 3-layer loop with
  appraisal-grid output, water-relabeled arrows, de-flooded Environment
  icon).
- **`broker/INVARIANTS.md`**: documents the five framework invariants
  with executable-guard cross-references, plus intentional
  `fallback_activated` semantic change and v2→v3 cross-comparability
  verdict.

### Known Issues
- **9 stale tests on `tests/` side** (pre-existing, NOT broker/-side):
  3 in `test_nature_water_figure_helpers.py` (Fig2 helper logic updated
  during NW Paper 1b F4 round, test assertions not synced); 6 in
  `test_dynamic_importance.py` (flood memory module, Python 3.14 /
  numeric-stack ABI). Broker/ side is 100% green. Triage planned for
  v0.3.1.
- **2 misnamed CLI scripts** in `examples/multi_agent/flood/paper3/analysis/`
  (`memory_causal_test.py`, `pa_prompt_calibration_test.py`) trigger
  accidental pytest collection if `pytest examples/.../paper3/analysis/`
  is run; gate-standard `pytest tests/ broker/` unaffected. Rename
  deferred to avoid breaking README `python -m paper3.analysis.*`
  cross-references.

## [0.2.0] - 2026-02-10

### Added
- **Per-agent-type model names**: `llm_params.model` in YAML overrides CLI `--model`
  for individual agent types, enabling heterogeneous LLM configurations
- **MemoryEngineRegistry**: Plugin registry for memory engines — register custom
  engines without modifying framework code
- **ExperimentBuilder.validate()**: Pre-build validation with actionable error messages
- **CognitiveCache**: Decision-reuse cache (SHA-256 hash of state+env+memory) that
  bypasses LLM calls when context is identical
- **Advanced Patterns Guide**: State hierarchy, two-way coupling, per-type LLM docs
- **Multi-Agent Setup Guide**: Full walkthrough for heterogeneous agent populations
- **YAML Configuration Reference**: Field-by-field reference for all YAML config files
- **Troubleshooting Guide**: 21+ error patterns with diagnosis steps
- **Customization Guide (English)**: Translated from Chinese with added recipes
- **Multi-agent simple example**: 7-agent experiment (regulator + farmers) bridging
  the quickstart-to-production gap
- **Framework Parameter Reference** in README: All parameters with valid ranges
- **Test infrastructure**: `tests/conftest.py` with shared fixtures, 29 core tests
  covering ExperimentRunner and CognitiveCache

### Fixed
- **SkillProposal mutation**: Removed direct mutation of `magnitude_pct` and
  `magnitude_fallback` on the original proposal object
- **Validation context key collision**: Added `__debug__`-only diagnostic warning
  when `agent_state` and `env_context` share key names
- **AgentTypeConfig cache staleness**: Added `clear_cache()` classmethod for test
  teardown; improved error messages with actionable tips

### Changed
- **memory_factory.py**: Refactored from 147-line if/elif chain to 53-line
  delegation to MemoryEngineRegistry (backward compatible)
- **YAML error messages**: Now include file path, tip text, and suggested fix

## [0.1.0] - 2025-12-01

### Added
- Initial release of the Water Agent Governance Framework
- 7-layer architecture: LLM Interface, Governance, Execution, Memory,
  Reflection, Social, Utilities
- SkillBrokerEngine 6-stage pipeline (Context, LLM, Parse, Validate,
  Approve, Execute)
- Three governance profiles: strict, flexible, autonomous
- Identity rules (boolean state checks) and thinking rules (construct evaluation)
- Five memory engines: Window, Importance, Hierarchical, HumanCentric, Universal
- ExperimentBuilder fluent API
- Phase ordering for multi-agent simulations
- Social graph with observation and gossip channels
- InteractionHub for tiered context assembly
- Five quickstart tiers with progressive complexity
- Flood domain (Paper 3) and irrigation domain (Paper 2) examples

### Known Issues
- `PrioritySchemaProvider`, `NarrativeProvider`, `EnvironmentObservationProvider`,
  and `InsuranceInfoProvider` are defined but not actively used in current examples
- `HierarchicalMemoryEngine` and `ImportanceMemoryEngine` are deprecated in favor
  of `HumanCentricMemoryEngine`
- No CI/CD pipeline (GitHub Actions)
- Test collection errors in `tests/sdk/` due to import issues
