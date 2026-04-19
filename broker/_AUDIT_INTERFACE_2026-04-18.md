---
phase: 3
date: 2026-04-18
scope: broker/ public API + examples/ consumer contracts
author: Codex
read_only: true
depends_on:
  - broker/_AUDIT_INVENTORY_2026-04-18.md
  - broker/_AUDIT_CORRECTNESS_2026-04-18.md
---

# Broker Interface Audit

This phase compares the broker package surfaces advertised through `__init__.py` to what the three example domains actually import. The resulting signal is strong enough for Phase 4: the main interface risks are now clear and ranked. The short version is that the framework has a credible root facade (`broker`) and a few clean public subpackages (`broker.agents`, `broker.config`, `broker.interfaces`, `broker.memory`, `broker.simulation`, `broker.validators`), but most of the component layer still behaves like internal implementation detail that examples reach through directly.

To stay within the requested word budget, this report summarizes the symbol-level extraction by package rather than reproducing 166 symbol rows verbatim. The underlying extraction did cover every public symbol and was used to compute the counts, type-hint/docstring coverage, leakage ratios, and zero-consumer totals below.

## 1. Public API contract extraction

Advertised export totals are:

- `broker.components.*`: 9 public symbols total
- Top-level broker subpackages: 115 public symbols total
- Root `broker`: 42 public symbols
- Grand total: 166 public symbols

Package-level surface summary:

| Package | Exported symbols count | Representative exports | Surface assessment |
|---|---:|---|---|
| `broker` | 42 | `SkillProposal`, `MemoryEngine`, `ExperimentBuilder`, `BaseAgent` | Real umbrella facade; broad but partly over-exported |
| `broker.components.memory` | 7 | `CognitiveMemory`, `PolicyFilteredMemoryEngine`, `load_initial_memories_from_json` | Only substantial component-level facade |
| `broker.components.prompt_templates` | 2 | `MemoryTemplateProvider`, `MemoryTemplate` | Narrow facade; examples still bypass it |
| `broker.agents` | 14 | `BaseAgent`, `AgentConfig`, `StateParam`, `Skill` | Clean reusable surface |
| `broker.config` | 18 | `GovernanceRule`, `AgentTypeRegistry`, `MemoryWritePolicy`, `load_memory_policy` | Strong schema/config facade |
| `broker.governance` | 14 | `GovernanceRule`, `RuleCondition`, `TypeValidator`, `validate_all` | Mixed quality because of lazy re-exports |
| `broker.interfaces` | 26 | `UniversalContext`, `RatingScale`, `EnvironmentProtocol` | Cleanest contract in repo |
| `broker.memory` | 28 | `UnifiedCognitiveEngine`, `UnifiedMemoryStore`, `MemoryCheckpoint` | Large public surface; partly experimental |
| `broker.simulation` | 4 | `StateManager`, `IndividualState` | Small coherent surface |
| `broker.validators` | 11 | `AgentValidator`, `ThinkingValidator`, `validate_all` | Usable public validator entrypoint |

Packages with no advertised public symbols through `__init__.py`: `broker.components.analytics`, `broker.components.cognitive`, `broker.components.context`, `broker.components.coordination`, `broker.components.events`, `broker.components.governance`, `broker.components.orchestration`, `broker.components.social`, `broker.core`, `broker.domains`, `broker.modules`, `broker.utils`.

Important boundary note: `broker.core` and `broker.utils` are worse than empty facades because they have no package `__init__.py` at all. `broker.modules` exists but is docstring-only, which is functionally the same outcome for consumers.

## 2. Boundary leakage map

| Package | Exported symbols count | Examples via `__init__.py` | Examples via deep path | Leakage ratio |
|---|---:|---:|---:|---:|
| `broker` | 42 | 9 | 0 | 0.00 |
| `broker.components.memory` | 7 | 2 | 16 | 2.29 |
| `broker.components.prompt_templates` | 2 | 0 | 2 | 1.00 |
| `broker.agents` | 14 | 9 | 0 | 0.00 |
| `broker.config` | 18 | 1 | 2 | 0.11 |
| `broker.governance` | 14 | 0 | 1 | 0.07 |
| `broker.interfaces` | 26 | 0 | 10 | 0.38 |
| `broker.memory` | 28 | 0 | 0 | 0.00 |
| `broker.simulation` | 4 | 0 | 1 | 0.25 |
| `broker.validators` | 11 | 0 | 7 | 0.64 |
| `broker.utils` | 0 | 0 | 21 | forced leakage |
| `broker.core` | 0 | 0 | 4 | forced leakage |
| `broker.modules` | 0 | 0 | 6 | forced leakage |
| `broker.components.context` | 0 | 0 | 6 | forced leakage |
| `broker.components.cognitive` | 0 | 0 | 6 | forced leakage |
| `broker.components.analytics` | 0 | 0 | 5 | forced leakage |
| `broker.components.social` | 0 | 0 | 4 | forced leakage |
| `broker.components.coordination` | 0 | 0 | 3 | forced leakage |
| `broker.components.governance` | 0 | 0 | 3 | forced leakage |
| `broker.components.orchestration` | 0 | 0 | 2 | forced leakage |

Top leaked-into modules:

| Module | Deep-import count |
|---|---:|
| `broker.components.memory.engine` | 9 |
| `broker.interfaces.skill_types` | 9 |
| `broker.utils.llm_utils` | 8 |
| `broker.utils.agent_config` | 7 |
| `broker.components.cognitive.reflection` | 6 |
| `broker.utils.performance_tuner` | 6 |
| `broker.components.analytics.feedback` | 4 |
| `broker.components.context.builder` | 4 |
| `broker.components.memory.legacy` | 4 |
| `broker.components.social.graph` | 4 |

Interpretation: the worst leakage is structural, not accidental. Examples deep-import because entire namespaces lack stable facades. `broker.components.memory` is the main case where a facade exists but consumers still prefer internals.

## 3. Type-hint and docstring coverage

Per-package totals (`Y / partial / N` for type hints; `Y / minimal / N` for docstrings):

| Package | Type hints | Docstrings | Assessment |
|---|---|---|---|
| `broker` | `25 / 15 / 2` | `31 / 10 / 1` | Good root API hygiene overall |
| `broker.components.memory` | `4 / 3 / 0` | `6 / 1 / 0` | Strong for a small facade |
| `broker.components.prompt_templates` | `2 / 0 / 0` | `1 / 1 / 0` | Clean but tiny |
| `broker.agents` | `13 / 1 / 0` | `11 / 3 / 0` | Strong reusable API |
| `broker.config` | `15 / 0 / 3` | `11 / 7 / 0` | Data models well documented; a few config exports weakly typed |
| `broker.governance` | `6 / 1 / 7` | `4 / 3 / 7` | Weakest facade because lazy exports hide the real implementations |
| `broker.interfaces` | `23 / 0 / 3` | `22 / 4 / 0` | Best public contract in the codebase |
| `broker.memory` | `10 / 8 / 10` | `21 / 4 / 3` | Broad surface, but many placeholders/constants dilute clarity |
| `broker.simulation` | `3 / 1 / 0` | `1 / 3 / 0` | Acceptable for a narrow package |
| `broker.validators` | `3 / 8 / 0` | `9 / 1 / 1` | Good docs, mostly partial constructor typing |

Most important per-symbol weaknesses:

- `broker.governance` exposes `BaseValidator`, `PersonalValidator`, `SocialValidator`, `ThinkingValidator`, and `PhysicalValidator` through lazy `__getattr__`, so the facade itself reads as opaque even though the underlying classes are documented.
- `broker.memory` exports unresolved dynamic state (`MemoryGraph`, `AgentMemoryGraph`, `MEMORY_GRAPH_AVAILABLE`) and several constants/placeholders, which makes the package feel more experimental than stable.
- `broker` root over-exports many low-level protocols and result models that examples never consume.

## 4. Cross-domain consumption matrix (refined)

| Package | Symbols consumed by irrigation_abm | Symbols consumed by single_agent | Symbols consumed by multi_agent/flood |
|---|---|---|---|
| `broker` | ? | `ExperimentBuilder`, `load_agents_from_csv` | `ExperimentBuilder`, `MemoryEngine`, `WindowMemoryEngine`, `HumanCentricMemoryEngine`, `TieredContextBuilder`, `InteractionHub`, `create_social_graph` |
| `broker.components.analytics` | `AgentMetricsTracker`, `FeedbackDashboardProvider` | `InteractionHub` | ? |
| `broker.components.cognitive` | `ReflectionEngine` | `AgentReflectionContext`, `ReflectionEngine` | `ReflectionEngine`, `ReflectionTrigger` |
| `broker.components.context` | `TieredContextBuilder` | `PrioritySchemaProvider`, `TieredContextBuilder` | `PerceptionAwareProvider`, `load_prompt_templates` |
| `broker.components.coordination` | ? | ? | `GameMaster`, `MessagePool`, `PassthroughStrategy` |
| `broker.components.governance` | `SkillRegistry` | `SkillRegistry` | ? |
| `broker.components.memory` | `HumanCentricMemoryEngine` | `HierarchicalMemoryEngine`, `HumanCentricMemoryEngine`, `ImportanceMemoryEngine`, `WindowMemoryEngine`, `create_memory_engine` | `CognitiveMemory`, `MemoryBridge`, `MemoryContentType`, `MemoryProvider`, `PolicyFilteredMemoryEngine`, `load_initial_memories_from_json`, `create_memory_engine` |
| `broker.components.orchestration` | ? | ? | `SagaDefinition`, `SagaStep` |
| `broker.components.prompt_templates` | ? | ? | `MemoryTemplate`, `MemoryTemplateProvider` |
| `broker.components.social` | ? | `NeighborhoodGraph` | `SocialGraph`, `SpatialNeighborhoodGraph`, `create_social_graph` |
| `broker.agents` | `AgentConfig`, `BaseAgent` | `AgentConfig`, `BaseAgent` | `AgentConfig`, `BaseAgent`, `PerceptionSource`, `Skill`, `StateParam` |
| `broker.config` | ? | ? | `CLEAN_POLICY`, `LEGACY_POLICY`, `load_memory_policy` |
| `broker.core` | `ExperimentBuilder` | `ExperimentBuilder`, `ExperimentRunner` | ? |
| `broker.governance` | `GovernanceRule` | ? | ? |
| `broker.interfaces` | `ApprovedSkill`, `ExecutionResult`, `ValidationResult` | `ExecutionResult` | `AgentArtifact`, `SkillOutcome`, `SkillProposal`, `ValidationLevel`, `ValidationResult` |
| `broker.modules` | ? | `initialize_agents_from_survey` | `AgentProfile`, `INCOME_MIDPOINTS`, `SurveyLoader`, `SurveyRecord` |
| `broker.simulation` | ? | ? | `TieredEnvironment` |
| `broker.utils` | `GovernanceAuditor`, `LLM_CONFIG`, `apply_to_llm_config`, `create_legacy_invoke`, `get_optimal_config` | same five symbols | `AgentTypeConfig`, `LLM_CONFIG` |
| `broker.validators` | ? | `ConservatismReport`, `KeywordClassifier`, `compute_hallucination_rate`, `run_conservatism_diagnostic` | `CrossAgentValidator`, `CrossValidationResult`, `ValidationLevel` |

This matrix shows that genuine cross-domain reuse exists, but usually at deep-path symbol level rather than through stable facades. `broker.agents` is the clean exception.

## 5. Validator pipeline contract documentation

The six-step sequence is defined in `paper/nature_water/drafts/methods_v4.md:10-21`. Runtime validation enters at `broker/core/skill_broker_engine.py:227` and dispatches through `_run_validators()` at `broker/core/skill_broker_engine.py:491`.

| Methods step | Primary implementation | Match status |
|---|---|---|
| Schema | `broker/validators/agent/agent_validator.py:110-146`; registry output schema `broker/core/skill_broker_engine.py:507-528` | Present, but split across two checks |
| Action legality | `broker/validators/agent/agent_validator.py:177-194`; type eligibility `broker/governance/type_validator.py:61-79` | Present |
| Physical | Domain bundle wiring `broker/domains/water/validator_bundles.py:30-61`; irrigation physical checks `examples/irrigation_abm/validators/irrigation_validators.py:44,83,417,460,510`; flood physical checks `examples/governed_flood/validators/flood_validators.py:28,54,83` | Present |
| Institutional | Irrigation checks at `examples/irrigation_abm/validators/irrigation_validators.py:145,283,328,736`; custom adapter `:882-905` | Present, but not a first-class validator category |
| Magnitude | Generic numeric bounds `broker/validators/agent/agent_validator.py:206-256`; irrigation magnitude cap `examples/irrigation_abm/validators/irrigation_validators.py:460` | Partial / split |
| Theory | `broker/validators/governance/thinking_validator.py:170-193`, PMT/utility/financial built-ins at `:393-555` | Present for theory-driven domains only |

Retry-loop terminator logic lives in `broker/core/_retry_loop.py:152-295`. The loop starts at `:176`, stops after `self.max_retries` (default 3 via `broker/core/skill_broker_engine.py:92`), and EarlyExit triggers only at `broker/core/_retry_loop.py:252-257` when the blocking rule set is unchanged and all blockers are deterministic.

Flags:

- `FLAG`: institutional compliance is documented as a single step, but in code it is distributed across checks labeled `institutional`, `social`, and `economic`, then routed partly through a custom irrigation adapter.
- `FLAG`: magnitude plausibility is not a strict standalone rejection gate. The irrigation magnitude validator is warning-only because execution resamples magnitude later.
- `FLAG`: the Methods text implies repeated blockage alone ends retries; code requires repeated **deterministic** blockage.
- `FLAG`: the Methods text implies a do-nothing fallback; code falls back to the registry default skill (`broker/core/skill_broker_engine.py:360-365`, `462-482`; `broker/core/_retry_loop.py:288-293`).

## 6. Interface stability signals

Component-layer stability is weak.

| Signal | Result |
|---|---|
| Symbols exported from `broker/components/*/__init__.py` and used by all three domains | None |
| Symbols exported from component facades but used by only one domain | `PolicyFilteredMemoryEngine`, `load_initial_memories_from_json`, `MemoryTemplate`, `MemoryTemplateProvider` |
| Heavily used packages with thin/missing facades | `broker.utils`, `broker.core`, `broker.modules`, `broker.components.context`, `broker.components.cognitive`, `broker.components.analytics`, `broker.components.social` |
| Public exports with zero example consumers | 34 in `broker`, 14 in `broker.governance`, 26 in `broker.interfaces`, 28 in `broker.memory`, 11 in `broker.validators`, 9 in `broker.agents`, 5 in `broker.components.memory`, 4 in `broker.simulation` |

The main conclusion is that the component layer is not yet a stable consumer-facing API. The root `broker` package is more stable than the component subpackages beneath it.

## 7. Versioning / deprecation hygiene

Marker counts under `broker/` are low but clustered:

| Slice | Count | Notes |
|---|---:|---|
| `broker/components/*` | 4 | three deprecation markers in legacy memory engines, one TODO in human-centric engine |
| `broker/core/*` | 3 | one psychometric deprecation shim, two builder deprecation warnings |

Oldest markers:

| Date | File:line | Marker |
|---|---|---|
| 2026-02-11 | `broker/components/memory/engines/hierarchical.py:24` | `DeprecationWarning` |
| 2026-02-11 | `broker/components/memory/engines/humancentric.py:340` | `# TODO` |
| 2026-02-11 | `broker/components/memory/engines/importance.py:34` | `DeprecationWarning` |
| 2026-02-11 | `broker/components/memory/universal.py:91` | ignored deprecation warning |
| 2026-02-11 | `broker/core/psychometric.py:298` | `DeprecationWarning` |
| 2026-02-12 | `broker/core/experiment_builder.py:157` | `DeprecationWarning` |
| 2026-02-12 | `broker/core/experiment_builder.py:177` | `DeprecationWarning` |

Old-path imports still present:

- `examples/multi_agent/flood/initial_memory.py:28` still imports `from memory.templates import ...`.
- `tests/test_psychometric.py:11-18` still imports `PMTFramework`, `UtilityFramework`, and `FinancialFramework` from `broker.core.psychometric` rather than directly from `broker.domains.water.*`.

## 8. Summary findings

Top five interface-level findings:

1. Most component namespaces still have no stable public facade, so deep imports are structurally required rather than occasional.
2. `broker.components.memory` is the only meaningful component facade, yet examples still make 16 deep memory imports versus only 2 facade imports.
3. `broker.governance` advertises 14 symbols but 7 package-level exports are effectively opaque lazy re-exports, weakening the public contract.
4. The Methods six-step validator description is directionally correct but not structurally faithful to the code, especially for institutional and magnitude checks.
5. The root `broker` facade is usable, but it is overgrown: 34 of its 42 public exports have zero example consumers.

Count totals:

- Total exported symbols: `166`
- Total deep imports from examples: `99`
- Total undocumented public symbols: `12`

Recommendations ranked by impact ? effort:

1. Add explicit facades for `broker.utils`, `broker.core`, and the heavily used component namespaces.
2. Normalize validator staging into named runtime phases so the paper and code refer to the same pipeline.
3. Deprecate deep imports into `broker.components.memory.*`, `broker.components.context.*`, `broker.components.cognitive.*`, and `broker.utils.*` once facades exist.
4. Trim or formally deprecate zero-consumer public exports at `broker` root and in `broker.governance` / `broker.memory`.
5. Finish path migration for `memory.templates` and psychometric framework imports.

Phase 4 readiness: yes. The audit yielded enough interface-level signal to support a gap analysis without additional execution.
