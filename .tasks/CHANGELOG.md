# Changelog

All notable changes to the governed_broker_framework project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [v0.61.0] - 2026-01-30 - Task-061 Documentation Overhaul (Water-Domain Positioning)

### Changed
- **Root README.md**: Complete rewrite with Water Resources Research (WRR) positioning. Framed as "hydro-social ABM governance middleware". Added all 4 examples to Quick Start, fixed broken image links, merged Chinese-only content (v3.2 memory, state management, validation pipeline, validator matrix, provider layer, framework comparison) into English.
- **Root README_zh.md**: Full structural alignment with English version. Identical section count, tables, images, and references.
- **examples/README.md**: Expanded from 33 lines to full learning path with 4-example comparison table, quick start for each, output structure guide, model recommendations.
- **examples/README_zh.md**: Full Chinese translation aligned with English examples README.
- **examples/single_agent/README.md**: Added Governance Rules v22 section (ERROR vs WARNING, 5 rules documented), Gemma 3 experiment configuration (sampling params, model-specific label behavior).

### Fixed
- Removed broken image link (local Gemini cache path `file:///C:/Users/wenyu/.gemini/...`) from root README
- Fixed all broken documentation paths: `docs/skill_architecture.md` → `docs/architecture/skill_architecture.md`, `docs/customization_guide.md` → `docs/guides/customization_guide.md`, `docs/experiment_design_guide.md` → `docs/guides/experiment_design_guide.md`, `docs/agent_assembly.md` → `docs/guides/agent_assembly.md`
- Standardized version to v3.3 across both EN/ZH READMEs (was v3.0 in Chinese)
- Removed duplicate `human_centric_memory_diagram.png` reference (was used twice in English README)
- Added `docs/framework_evolution.png` to English README (was Chinese-only)

### Added (Zotero — Task-061)
| Paper | Key | Tags |
|-------|-----|------|
| Trope & Liberman (2010) — Construal-Level Theory | `8E2D2IJQ` | Cognitive-Architecture, Psychology |
| Tversky & Kahneman (1973) — Availability Heuristic | `P3FQKGIG` | Memory, Psychology |
| Ebbinghaus (1885) — Memory: Forgetting Curve | `FT3KA4HD` | Memory, Psychology |
| Siegrist & Gutscher (2008) — Natural Hazards Self-Protection | `99747HNH` | Water-Resource-ABM, PMT |
| Hung & Yang (2021) — Adaptive Irrigation, WRR | `BHJX2TS3` | Water-Resource-ABM, Nonstationary |

All items tagged `Task-061` with research notes explaining relevance to framework.

### Delegated to Codex
- Task-061-C5: `examples/governed_flood/README.md` update (governance rules, output interpretation, Chinese version)
- Task-061-C6: `examples/multi_agent/README.md` EN/ZH alignment + Task-060 features
- Task-061-C7: `docs/` path fixes + module documentation verification

---

## [v0.58.1] - 2026-01-30 - Task-058 Generalization & Implementation (5/6 complete)

### Implemented (058-A through 058-E)

Generalized all Task-058 modules to **generic broker/ + domain examples/** architecture. 967 tests pass (63 new).

- **058-A** ✅ Refactored `broker/interfaces/artifacts.py` to ABC pattern (`AgentArtifact` base + `ArtifactEnvelope`); domain subclasses moved to `examples/multi_agent/ma_artifacts.py`
- **058-B** ✅ Rewrote `cross_agent_validator.py` with generic checks + `domain_rules` injection; created `CrossValidationResult` type; flood rules in `ma_cross_validators.py`
- **058-C** ✅ `drift_detector.py` (Shannon entropy, Jaccard stagnation) + `role_permissions.py` (generic `RoleEnforcer`); `FLOOD_ROLES` in `ma_role_config.py`
- **058-D** ✅ `saga_coordinator.py` (generic SagaCoordinator with rollback/timeout); 3 flood saga definitions in `ma_saga_definitions.py`
- **058-E** ✅ `create_drift_observables()` factory added to `observable_state.py`
- **058-F** ❌ Integration wiring — delegated to Codex (`task-058f-codex.md`)

### Architecture

- All flood-specific code isolated in `examples/multi_agent/` (ma_artifacts, ma_cross_validators, ma_role_config, ma_saga_definitions)
- Zero domain imports in new `broker/` modules
- `CrossValidationResult` distinct from `ValidationResult` (different validation domains)

---

## [v0.58.0] - 2026-01-30 - Task-058 MAS Skill Architecture (Planned & Delegated)

### Planned (Task-058)

4-phase MAS extension: Structured Protocols, Cross-Agent Validation, Saga Transactions, Drift Detection.

- **058-A** (Codex): `broker/interfaces/artifacts.py` — `PolicyArtifact`, `MarketArtifact`, `HouseholdIntention`, `ArtifactEnvelope` typed dataclasses for inter-agent communication
- **058-B** (Gemini): `broker/validators/governance/cross_agent_validator.py` — `CrossAgentValidator` with perverse incentive, echo chamber, deadlock, budget coherence checks
- **058-C** (Codex): `broker/components/drift_detector.py` + `role_permissions.py` — `DriftDetector` (Shannon entropy, Jaccard similarity), `RoleEnforcer` (FLOOD_ROLES)
- **058-D** (Gemini): `broker/components/saga_coordinator.py` + `saga_definitions.py` — `SagaCoordinator` with compensatory rollback, `SUBSIDY_APPLICATION_SAGA`
- **058-E** (Codex): `broker/components/observable_state.py` (MODIFY) — `create_drift_observables()` factory method
- **058-F** (Gemini): Integration wiring into `coordinator.py`, `message_provider.py`, `phase_orchestrator.py`, `lifecycle_hooks.py`

### Literature Added (Zotero)

| Paper | Key | Phase |
|-------|-----|-------|
| MetaGPT (Hong et al., ICLR 2024) | `U44MWXQC` | Phase 1 — Artifacts |
| Concordia (Vezhnevets et al., 2023) | `HITVU4HK` | Phase 2 — Validation |
| SagaLLM (Chang & Geng, 2025) | `7G736VMQ` | Phase 3 — Sagas |
| AgentSociety (Piao et al., 2025) | `KBENGEM8` | Phase 4 — Drift |
| Making Waves (Water Research, 2025) | `IFZXPGHE` | Water-Resource-ABM |
| IWMS-LLM (He et al., J. Hydroinformatics, 2025) | `UFF83URE` | Water-Resource-ABM |
| Hung & Yang (2021, Water Resources Research) | `5I6XWJGF` | Water-Resource-ABM |

Collection: `Task-058-MAS-Skill-Architecture` (key: `HSDRSVQ5`)

### Execution Order

```
Phase 1 (parallel):  058-A (Codex) + 058-C (Codex)
Phase 2 (after P1):  058-B (Gemini) + 058-D (Gemini) + 058-E (Codex)
Phase 3 (after P2):  058-F (Gemini)
```

### Registry Updates

- Task-057: `in_progress` -> `completed` (all 4 subtasks verified with commits)
- Task-058: Added as `delegated` with 6 subtasks, 7 handoff files

---

## [v0.57.0] - 2026-01-30 - Task-057 Reflection Optimization (Delegated)

### Planned (Task-057)
- **057-A** (Codex): `AgentReflectionContext` dataclass, per-type reflection questions (household/government/insurance), `generate_personalized_reflection_prompt()`, `generate_personalized_batch_prompt()`, `extract_agent_context()`
- **057-B** (Gemini): `retrieve_stratified()` method in `HumanCentricMemoryEngine` — source-category allocation slots (personal:4, neighbor:2, community:2, reflection:1, abstract:1)
- **057-C** (Codex): `IMPORTANCE_PROFILES` dict with variable importance (0.6-0.95), `compute_dynamic_importance()`, SA `run_flood.py` reflection loop upgrade
- **057-D** (Gemini): `_run_ma_reflection()` in MA lifecycle hooks — per-agent-type batch reflection with stratified retrieval

### Problem Addressed
All agents produced identical reflections because:
1. Generic prompt with no agent identity
2. Pure top-k retrieval dominated by high-importance reflections (echo chamber)
3. Hardcoded importance=0.9 for all insights
4. No MA reflection integration

### Execution Order
1. Phase 1 (parallel): 057-A + 057-B
2. Phase 2: 057-C (depends on A)
3. Phase 3: 057-D (depends on A+B+C)

---

## [v0.56.0] - 2026-01-30 - Task-055/056 Multi-Agent Bug Fixes & MemoryBridge

### Fixed (Task-055)
- **055-A**: `parse_output()` stale config — `self.config` → `parsing_cfg` for `normalization`/`proximity_window` (Codex, commit `2b05b11`)
- **055-B**: `get_adapter()` config path — forwards `config_path` to `UnifiedAdapter` so `valid_skills` is populated (Codex, commit `1667535`)
- **055-C**: `CognitiveCache` governance guard — `invalidate()` method + cache busting on governance failures (Codex, commit `80b8c55`)
- **Test suite**: Fixed 11 pre-existing test failures across 5 files (Claude Code):
  - `test_adapter_parsing`: Added `config_path`, switched to enclosure format, `flood_insurance` → `buy_insurance`
  - `test_agent_profile_extensions`: `is_mg` → `is_classified`, `enrich_with_hazard` → `enrich_with_position`
  - `test_broker_core`: Added `**kwargs` to MockContextBuilder.build()
  - `test_memory_integration`: Removed BaseAgent inheritance, `flood_depth` → `flood_depth_m`
  - `test_v3_2_features`: `agent.id` → `agent._id` (read-only property)

### Added (Task-056)
- **MemoryBridge** (`broker/components/memory_bridge.py`, 150 lines) — Bridges Communication Layer outputs into MemoryEngine (Gemini, commit `81b8eb0`)
  - `store_resolution()`: GameMaster ActionResolution → agent memory (approved/denied)
  - `store_message()`: AgentMessage → tagged memory (source/emotion/importance mapping)
  - `store_unread_messages()`: Top-priority message selection with max_store limit
  - 7 message type mappings: policy_announcement, market_update, neighbor_warning, neighbor_info, media_broadcast, resolution, direct
- **MemoryBridge tests** (`tests/test_memory_bridge.py`, 122 lines, 8 tests)
- **Lifecycle hooks integration**: `MultiAgentHooks` accepts `game_master`/`message_pool`, wires MemoryBridge in `post_step()`/`post_year()`

### Test Results
- **880 passed, 0 failed** (full suite excluding integration/manual/vector_db)
- 34 warnings (Pydantic V2 deprecation only)

---

## [v0.53.1] - 2026-01-29 - Task-053B Group C Test Run + Standalone Example

### Added
- **053B-1: Standalone Governed Flood Example** - `examples/governed_flood/`
  - `run_experiment.py` (479 lines) — Clean Group C entry point using ExperimentBuilder API
  - `README.md` — Three Pillars documentation (Strict Governance, Cognitive Memory, Priority Schema)
  - `config/` — agent_types.yaml, skill_registry.yaml, flood_years.csv (copied from single_agent/)
  - `data/` — agent_initial_profiles.csv (copied from single_agent/)
  - No custom subclasses — uses broker core API directly (vs 1048-line run_flood.py)
  - Fixed Group C: strict governance + HumanCentricMemoryEngine + PrioritySchemaProvider
  - Includes simplified FloodSimulation inline, LifecycleHooks, ReflectionEngine wiring

- **053B-2: gemma3:1b Group C Experiment Run** — Full 10yr/100-agent validation
  - Parameters: seed=401, num-ctx=8192, num-predict=1536, memory-engine=humancentric
  - Output: `examples/single_agent/results/JOH_FINAL/gemma3_1b/Group_C/Run_1/`

### Design Decisions
- **Experiment vs Example separation**: `run_flood.py` (experiment, Groups A/B/C comparison) vs `run_experiment.py` (showcase, Group C only)
- **No custom classes**: Standalone example uses ExperimentBuilder, TieredContextBuilder, HumanCentricMemoryEngine directly
- **Inline FloodSimulation**: Included in run_experiment.py to keep the example self-contained

### Files Created
- `examples/governed_flood/run_experiment.py`
- `examples/governed_flood/README.md`
- `examples/governed_flood/config/agent_types.yaml`
- `examples/governed_flood/config/skill_registry.yaml`
- `examples/governed_flood/config/flood_years.csv`
- `examples/governed_flood/data/agent_initial_profiles.csv`

---

## [v0.53.0] - 2026-01-29 - Task-053 Gemma 3 Experiment Campaign

### Added
- **053-0: Directory Cleanup** - Moved outdated examples to `examples/archive/`
  - `single_agent_modular/` (superseded by `single_agent/`)
  - `unified_flood/` (Task-040 demo, components now in `broker/core/`)

- **053-1: Experiment Script** - Fixed `run_gemma3_experiment.ps1`
  - Replaced broken `--group` flag with explicit CLI parameters
  - Group A: Uses original `LLMABMPMT-Final.py` (no broker framework)
  - Group B: `run_flood.py --governance-mode strict --memory-engine window`
  - Group C: `run_flood.py --governance-mode strict --memory-engine humancentric --use-priority-schema`
  - Standardized: seed=401, agents=100, years=10, num-ctx=8192, num-predict=1536

- **053-5: Analysis Script** - `analysis/gemma3_hallucination_diversity.py`
  - Hallucination metrics: format_retries, parse_confidence, MCC, rule violations, Intv_H
  - Diversity metrics: Shannon entropy time series, decision distribution, sawtooth amplitude
  - 8 chart outputs: H1-H5 (hallucination), D1-D5 (diversity)
  - Handles both original script (Group A) and broker framework (Groups B/C) output formats

### Changed
- `examples/single_agent/run_gemma3_experiment.ps1` - Complete rewrite with proper parameters

### Experiment Matrix
- 4 models: gemma3:1b, 4b, 12b, 27b
- 3 groups: A (Original), B (Strict), C (Full Cognitive)
- 12 total runs

### Research Hypotheses
- H1: Larger models → lower structural hallucination (format_retries ↓)
- H2: Larger models → higher decision-memory consistency (MCC ↑)
- H3: Larger models → higher behavioral diversity (entropy ↑ then plateau)
- H4: Governance compensates small model hallucination (1b-C ≈ 27b-A)
- H5: Larger models → more responsive to flood events (sawtooth ↑)
- H6: Small model + no governance → highest mode collapse risk

---

## [v0.52.0] - 2026-01-29 - Task-052 MAS Five-Layer Architecture Verification

### Added
- **052-A: MAS Literature to Zotero** - Added 14 papers covering all 5 MAS layers
  - State Layer: AgentTorch, PMT (Rogers 1975), Bubeck et al. (2012)
  - Observation Layer: Simon (1955), POMDP (Kaelbling 1998)
  - Action Layer: Generative Agents, MemGPT, Toolformer
  - Transition Layer: Concordia, Gilbert ABM (2019)
  - Communication Layer: MetaGPT, Bandura (1977), Barabási (2016), Wooldridge (2009)

- **052-B: Architecture Documentation** - Comprehensive framework mapping
  - `docs/architecture/mas-five-layers.md` - Complete 5-layer mapping
  - Module-to-literature correspondence tables
  - Gap analysis and recommendations

- **052-A Script**: `.tasks/scripts/add_mas_literature.py` - Batch Zotero addition

### Documentation
- Created `docs/architecture/mas-five-layers.md` (comprehensive architecture doc)
- All 14 literature items have detailed notes explaining framework mapping
- Tags: Task-052, MAS-Architecture, [Layer]-Layer

### Literature References (Zotero Keys)
| Layer | Papers | Keys |
|-------|--------|------|
| State | AgentTorch, PMT, Bubeck | RMNEUT7F, NV3BZ94J, ZADR7ZXE |
| Observation | Simon, POMDP | 6MSEC2KH, QU47TXUP |
| Action | Generative Agents, MemGPT, Toolformer | MATE4MG3, 4K3K9MQJ, 4CUZ2ZTH |
| Transition | Concordia, Gilbert | HITVU4HK, 67PWUHTW |
| Communication | MetaGPT, Bandura, Barabási, Wooldridge | U44MWXQC, V2KWAFB8, DVZAZ8K4, GNC2TMM6 |

### Gap Analysis Summary
| Feature | Status | Priority |
|---------|--------|----------|
| Planning Module | Implicit | MEDIUM |
| Plan Revision | Missing | MEDIUM |
| Pub-Sub Messaging | Missing | LOW |
| Conflict Arbitration | Implicit | MEDIUM |

### References
- Plan: `C:\Users\wenyu\.claude\plans\ancient-beaming-lemur.md` (Task-052 section)

---

## [v0.51.0] - 2026-01-29 - Task-051 Documentation Protocol

### Added
- **Documentation Protocol** - Systematic version recording system
  - `.tasks/templates/task-readme-template.md` - Task documentation template
  - `.tasks/DOCUMENTATION_GUIDE.md` - Documentation writing guide
  - `.tasks/scripts/validate_docs.py` - Documentation validation script

### Documentation
- Mandatory checklist for every task completion
- Version numbering convention: `v0.{task_number}.{patch}`
- CHANGELOG entry format standardized
- registry.json entry format standardized
- Zotero tag system defined

### References
- Plan: `C:\Users\wenyu\.claude\plans\ancient-beaming-lemur.md` (Task-051 section)

---

## [v0.50.0] - 2026-01-29 - Task-050 Memory System Optimization

### Added
- **050-A: Vector DB Integration** - FAISS HNSW index for O(log n) retrieval (14 tests)
  - `cognitive_governance/memory/vector_db.py`
  - `VectorMemoryIndex`, `AgentVectorIndex` classes

- **050-B: Memory Checkpoint/Resume** - Cross-session memory persistence (15 tests)
  - `cognitive_governance/memory/persistence.py`
  - `MemoryCheckpoint`, `save_checkpoint()`, `load_checkpoint()` functions

- **050-C: Multi-dimensional Surprise** - Multi-variable surprise tracking (20 tests)
  - `cognitive_governance/memory/strategies/multidimensional.py`
  - `MultiDimensionalSurpriseStrategy`, `create_flood_surprise_strategy()`

- **050-D: MemoryGraph (NetworkX)** - Graph-based memory structure (28 tests)
  - `cognitive_governance/memory/graph.py`
  - `MemoryGraph`, `AgentMemoryGraph` classes
  - Temporal, semantic, causal edge types

- **050-E: Cognitive Constraints Configuration** - Miller/Cowan based limits (25 tests)
  - `cognitive_governance/memory/config/cognitive_constraints.py`
  - `CognitiveConstraints` dataclass
  - Pre-configured profiles: `MILLER_STANDARD`, `COWAN_CONSERVATIVE`, `EXTENDED_CONTEXT`, `MINIMAL`

### Changed
- `AdaptiveRetrievalEngine` - Added `cognitive_constraints` parameter for dynamic memory count
- `UnifiedMemoryStore` - Integrated checkpoint support

### Literature References
- Miller, G. A. (1956). The magical number seven. DOI: 10.1037/h0043158
- Cowan, N. (2001). The magical number 4. DOI: 10.1017/S0140525X01003922
- A-MEM (2025). Agentic Memory. arXiv:2502.12110
- MemGPT (2023). LLMs as Operating Systems. arXiv:2310.08560
- Park et al. (2023). Generative Agents. arXiv:2304.03442

### Documentation
- Created `docs/task-050-memory-optimization/README.md`
- Zotero items tagged with Task-050

### Tests
- Total: 102 new tests (77 Phase 1 + 25 Cognitive Constraints)
- All tests passing

### Performance Impact
| Metric | Before | After (050-A) |
|--------|--------|---------------|
| Retrieval (100 memories) | ~5ms | ~1ms |
| Retrieval (10000 memories) | ~500ms | ~10ms |

---

## [v0.30.0] - In Progress - Task-030 FLOODABM Parameter Alignment

### Added

- **FLOODABM Parameters** (Sprint 1-5.1 ✅)
  - `CSRV = 0.57` constant in `rcv_generator.py`
  - Risk Rating 2.0 module (`risk_rating.py`) with r1k rates
  - TP decay module (`tp_decay.py`) with MG/NMG calibrated params
  - Beta distribution parameters (Table S3) in YAML
  - 33 verification tests (`test_floodabm_alignment.py`)

- **Config Reorganization** (Sprint 6.1 🔲 - Assigned to Gemini CLI)
  - Centralized config structure: `examples/multi_agent/config/`
  - FLOODABM params extracted to `config/parameters/floodabm_params.yaml`
  - Skill registry: `config/skills/skill_registry.yaml`
  - Config loader: `config/globals.py`

### Changed

- **Insurance Parameters** (FLOODABM Table S2)
  - Deductible: $2,000 → $1,000
  - Added `r1k_structure = 3.56`, `r1k_contents = 4.90`
  - Added `reserve_fund_factor = 1.15`, `small_fee = 100`

- **Damage Parameters**
  - Added `damage_ratio_threshold = 0.5` (theta)
  - Added `shock_scale = 0.3` (cs)

### Design Decisions

- **LLM-Driven Cognition**: Cognitive formulas (tp_decay, EMA) kept as reference/validation only
  - LLM reasons from context to determine TP/CP/SP levels
  - Formulas NOT used for controlling agent decisions

### References

- Handoff: `.tasks/handoff/task-030.md`
- Plan: `C:\Users\wenyu\.claude\plans\cozy-roaming-perlis.md`
- FLOODABM Supplementary Materials (Tables S1-S6)

---

## [v0.29.0] - 2026-01-21 - Task-029 MA Pollution Remediation

### BREAKING CHANGES

- **SurveyRecord No Longer Has Flood Fields**
  - `flood_experience`, `financial_loss` fields removed from base `SurveyRecord`
  - Use `FloodSurveyLoader` from `examples/multi_agent/survey/` for MA-specific fields

- **AgentProfile Uses Extensions Dict**
  - `flood_zone`, `base_depth_m`, `flood_probability` no longer direct attributes
  - Access via `profile.extensions["flood"].field_name`

- **AgentInitializer No Longer Has mg_classifier Parameter**
  - Use `MAAgentInitializer` from `examples/multi_agent/survey/` for MG classification

- **Enrichment API Changed**
  - `include_hazard=True` → `position_enricher=DepthSampler()`
  - `include_rcv=True` → `value_enricher=RCVGenerator()`
  - Old parameters removed (were deprecated in v0.28)

### Added

- **Protocol-Based Dependency Injection** (`broker/interfaces/enrichment.py`)
  - `PositionEnricher` protocol for spatial data assignment
  - `ValueEnricher` protocol for asset value calculation
  - `PositionData` and `ValueData` named tuples

- **MA-Specific Survey Module** (`examples/multi_agent/survey/`)
  - `FloodSurveyLoader` - Survey loader with flood experience fields
  - `FloodSurveyRecord` - Record with flood-specific attributes
  - `MGClassifier` - Marginalized Group classification (moved from broker/)
  - `MAAgentInitializer` - MA-specific agent initialization with MG integration
  - `MAAgentProfile` - Extended profile with flood extension flattening

- **Architecture Documentation** (`ARCHITECTURE.md`)
  - Protocol-based dependency injection patterns
  - Extensions pattern for domain-specific data
  - Config-driven domain logic documentation

- **Migration Guide** (`.tasks/handoff/task-029-migration-guide.md`)
  - Breaking changes with before/after code examples
  - Quick migration checklist

### Changed

- **AgentProfile Classification Fields** (Generic naming)
  - `is_mg` → `is_classified` (with backward-compat alias)
  - `mg_score` → `classification_score` (with backward-compat alias)
  - `mg_criteria` → `classification_criteria` (with backward-compat alias)
  - `group_label` now returns "A"/"B" instead of "MG"/"NMG"

- **AgentInitializer Methods** (Generic naming)
  - `enrich_with_hazard()` → `enrich_with_position()`
  - `enrich_with_rcv()` → `enrich_with_values()`
  - `_create_extensions()` now returns empty dict (override in subclass)

- **Memory Tags** (Config-driven)
  - Tags now loaded from `agent_types.yaml` `memory_config.retrieval_tags`
  - No hardcoded "MG" → "subsidy" mapping in broker/

- **Media Context Fields** (Generic naming)
  - `social_media` → `peer_messages`
  - `news` → `broadcast`

### Removed

- **Hardcoded MA Examples** from broker/ docstrings
  - reflection_engine.py - Removed flood damage examples
  - memory.py - Changed "household_mg" to generic examples
  - context_builder.py - Removed flood-specific field names

- **Path Traversal Anti-Pattern**
  - Removed `sys.path.insert()` hack in agent_initializer.py
  - Domain code no longer imported via path manipulation

### Deprecated

- **Backward Compatibility Aliases** (will be removed in v0.31)
  - `AgentProfile.is_mg` → use `is_classified`
  - `AgentProfile.mg_score` → use `classification_score`
  - `AgentProfile.mg_criteria` → use `classification_criteria`

### Documentation

- **Audit Report** (`.tasks/handoff/task-029-audit-report.md`)
  - Grep audit confirming zero executable MA code in broker/
  - Status: PASS

---

## [2026-01-21] - Task-028 Import Path Fixes

### Fixed
- **Import Errors After File Relocation** (Critical)
  - Fixed 6 import path errors across 4 files after Codex moved files from `broker/` to `examples/multi_agent/`
  - Files affected:
    - `examples/multi_agent/environment/catastrophe.py` - Changed to relative import (`.hazard`)
    - `examples/multi_agent/environment/hazard.py` - Fixed 3 imports (`.prb_loader`, `.depth_sampler`, `.vulnerability`)
    - `examples/multi_agent/hazard/prb_analysis.py` - Updated to new path
    - `examples/multi_agent/tests/test_module_integration.py` - Updated test import
  - Root cause: File moves completed but internal imports not updated
  - Verification: All modules now import successfully ✅

### Changed
- **Task-028 Status Update**
  - 028-C (Move media_channels.py): Marked as completed
  - 028-D (Move hazard module): Marked as completed
  - 028-G (Run verification tests): Status changed from `blocked` to `ready_for_execution`
  - Import fixes documented in artifacts-index.json (028-C-FIX, 028-D-FIX, 028-D-FIX2, 028-D-FIX3)

---

## [2026-01-21] - Workflow Improvement Implementation

### Added
- **Status Synchronization Tool** (`.tasks/scripts/validate_sync.py`)
  - 274 lines, validates registry.json ↔ handoff file status consistency
  - Supports `--fix` flag for auto-correction
  - Successfully detected and helped fix Task-015 status mismatch

- **Dependency Checker** (`.tasks/scripts/check_unblock.py`)
  - 301 lines, checks blocked tasks and auto-unblocks when dependencies complete
  - New blocker format: dict with `depends_on`, `unblock_trigger`, `unblock_action`
  - Successfully unblocked Task-028-G after 028-C/D completion

- **Handoff Templates**
  - Simple template (`.tasks/templates/handoff-simple.md`) - for <5 subtasks
  - Complex template (`.tasks/templates/handoff-complex.md`) - for multi-agent tasks

- **Centralized Artifact Registry** (`.tasks/artifacts-index.json`)
  - Tracks all produced files with metadata (task_id, type, producer, timestamp)
  - Currently tracking 21 artifacts

### Changed
- **GUIDE.md Updates**
  - Section 3.1: Status Synchronization protocol
  - Section 6.2: Handoff Templates selection guide
  - Section 7.1: Centralized Artifact Registry
  - Section 10.1: Blocked Task Management (new blocker format)
  - Section 14: Enhanced RELAY Protocol

- **Registry Cleanup**
  - Removed Task-023 (deprecated duplicate of Task-021)
  - Total tasks reduced from 19 to 18
  - All statuses now synchronized between registry.json and handoff files

---

## [2026-01-20] - Task-027 v3 MA Integration

### Added
- **UniversalCognitiveEngine v3 Integration**
  - Integrated Surprise Engine into Multi-Agent system
  - Added CLI parameters: `--arousal-threshold`, `--ema-alpha`, `--stimulus-key`
  - Updated `run_unified_experiment.py` to support `--memory-engine universal`

### Changed
- **YAML Configuration**
  - Added global_config.memory: arousal_threshold, ema_alpha, stimulus_key, ranking_mode
  - Default values: arousal_threshold=2.0, ema_alpha=0.3, stimulus_key="flood_depth_m"

---

## [2026-01-19] - Task-022 PRB Integration & Spatial Features

### Added
- **PRB Flood Data Integration**
  - Copied 13 PRB grid files (2011-2023) to `examples/multi_agent/input/PRB/`
  - Implemented per-agent flood depth calculation based on grid position
  - Added YearMapping class for simulation year ↔ PRB year conversion

- **Spatial Neighborhood Graph**
  - New `SpatialNeighborhoodGraph` class in `broker/components/social_graph.py`
  - Uses actual (grid_x, grid_y) coordinates instead of K-Nearest ring topology
  - Added CLI parameter: `--neighbor-mode spatial`, `--neighbor-radius`

- **Media Channels System**
  - New file: `broker/components/media_channels.py`
  - NewsMediaChannel: delayed, reliable, community-wide
  - SocialMediaChannel: instant, exaggerated (+/-30%), extended network
  - MediaHub: orchestrates both channels

### Changed
- **CLI Parameters Added**
  - `--neighbor-mode spatial|ring`
  - `--neighbor-radius 3.0` (cells)
  - `--per-agent-depth`
  - `--enable-news-media`
  - `--enable-social-media`
  - `--news-delay 1` (turns)

---

## [2026-01-18] - Task-015 MA System Verification

### Completed
- All 6 verification criteria passed (V1-V6)
- Decision diversity: Shannon entropy > 1.0 ✅
- Behavior rationality: Low-CP expensive < 20% ✅
- Institutional dynamics: Government/Insurance policy changes > 0 ✅

---

## [2026-01-17] - Task-021 Context-Dependent Memory

### Added
- **Contextual Boosters Mechanism**
  - Decoupled design: TieredContextBuilder generates boosters → Memory engine applies them
  - `contextual_boosters` parameter in `memory_engine.retrieve()`
  - Example: `{"emotion:fear": 1.5}` when flood occurs

### Changed
- **Context Builder**
  - New method: `_generate_contextual_boosters(env_context)` in TieredContextBuilder
  - Analyzes environment context and generates tag boosters dynamically

- **Memory Engine**
  - Added `W_context` weight to HumanCentricMemoryEngine
  - Retrieve method now accepts `contextual_boosters` parameter

---

## Known Issues

### Issue-001: Non-ASCII Path Blocker
- **Description**: Gemini CLI cannot execute file operations due to non-ASCII characters in project path
- **Affected**: Gemini CLI agent
- **Workaround**: Use Claude Code or Codex for file operations
- **Status**: Open

### Issue-002: Windows Console Encoding (cp950)
- **Description**: Unicode emoji characters (🔍, ✓, ✗, 💡) cause UnicodeEncodeError
- **Fixed**: Replaced all Unicode with ASCII equivalents in validation scripts
- **Status**: Resolved

---

## File Relocation Checklist (Added 2026-01-21)

When relocating files, follow this checklist to avoid import errors:

- [ ] Physical file move completed
- [ ] Internal imports updated (within moved files)
- [ ] External imports updated (files that import the moved files)
- [ ] Test imports updated (if applicable)
- [ ] Verify all imports: `python -c "from new.path import Module"`
- [ ] Update documentation/README if paths are documented
- [ ] Add artifact entries to `.tasks/artifacts-index.json`
- [ ] Run validation: `python .tasks/scripts/validate_sync.py`

---

## Legend

- **Added**: New features or files
- **Changed**: Changes to existing functionality
- **Deprecated**: Features marked for removal
- **Removed**: Deleted features or files
- **Fixed**: Bug fixes
- **Security**: Security-related changes
