---
phase: 1
date: 2026-04-18
scope: broker/ + providers/ + tests/ + examples/ import sites
author: Codex
read_only: true
---

# Broker Audit Inventory

This inventory treats `broker/components/*` as one architectural cluster and the other top-level `broker/*` directories as a second cluster, per the task spec. Counts exclude `__pycache__/`, no tests were run, and all import, dead-code, and consumer signals below come from static analysis of the repository on 2026-04-18.

A few structural themes stand out before the tables. First, the codebase is not a single broker package but a layered accretion: the restructured `broker.components.*` core, legacy or domain-facing top-level broker packages, a separate research-oriented `broker.memory` toolkit, and flat provider adapters at repo root. Second, example code consumes only a subset of that surface area, so several packages look framework-internal even when they remain large. Third, package boundaries are uneven: some sub-packages present a clean `__init__.py` facade, while others are bypassed by deep imports from example code.

Methodologically, this phase uses static signals only: AST parsing, import-edge reconstruction, export extraction from `__init__.py`, simple call-site scans for dead-code candidates, and grep-style test counting via `def test_`. That makes the inventory strong on structure and coupling, but intentionally conservative on runtime behavior. Anything loaded via YAML, reflection, provider factories, or string-selected registry lookups may appear less connected here than it is during execution.

The most useful distinction in the tables is not simply used versus unused, but framework-internal versus externally consumed. A module with `external consumers = 0` is often still part of a valid broker execution path when the examples only touch it indirectly through a builder, runner, or package root. By contrast, direct imports into deep module paths are stronger evidence of boundary leakage, because they reveal where consumers depend on internal file layout instead of a stable package surface.

The split between `broker.memory` and `broker.components.memory` also matters analytically. The top-level package reads like a larger research toolkit with multiple engines and strategies, while the component package looks like the production-facing integration point used by the restructured broker core. Treating them as one inventory bucket would hide real differences in consumer patterns, test attachment, and probable refactor cost. The same caution applies to the two governance namespaces: top-level `broker.governance` and `broker.components.governance` are adjacent by name but not identical by role.

## 1. Sub-package File Map

### 1a. `broker/components/*` cluster

#### `broker.components.analytics`

| File | Lines | Fan-in (# of other broker files that import this) | External consumers (# of `examples/` files that import this) | One-sentence purpose (from docstring or code) |
|---|---|---|---|---|
| broker/components/analytics/__init__.py | 9 | 0 | 0 | Analytics and state tracking sub-package. |
| broker/components/analytics/audit.py | 450 | 1 | 0 | Configuration for audit writing. |
| broker/components/analytics/drift.py | 266 | 1 | 0 | Generic drift detection for multi-agent population behavior monitoring. |
| broker/components/analytics/feedback.py | 412 | 1 | 2 | Feedback Provider — Config-driven environment feedback for LLM agents. |
| broker/components/analytics/interaction.py | 461 | 4 | 1 | Interaction Hub Component - PR 2 |
| broker/components/analytics/observable.py | 331 | 0 | 0 | Observable State Manager - Computes and caches cross-agent observables. |
Notes: external-consumer=0 -> broker/components/analytics/__init__.py, broker/components/analytics/audit.py, broker/components/analytics/drift.py, broker/components/analytics/observable.py. Phase-4 duplicate/variant flags -> none.

#### `broker.components.cognitive`

| File | Lines | Fan-in (# of other broker files that import this) | External consumers (# of `examples/` files that import this) | One-sentence purpose (from docstring or code) |
|---|---|---|---|---|
| broker/components/cognitive/__init__.py | 7 | 0 | 0 | Cognitive processes sub-package. |
| broker/components/cognitive/adapters.py | 71 | 1 | 0 | Domain Reflection Adapters — Plugin interface for domain-specific reflection & memory. |
| broker/components/cognitive/reflection.py | 672 | 0 | 4 | Reflection Engine - Cognitive consolidation for long-term memory resilience. |
| broker/components/cognitive/trace.py | 116 | 1 | 0 | Dataclass definition for CognitiveTrace. |
Notes: external-consumer=0 -> broker/components/cognitive/__init__.py, broker/components/cognitive/adapters.py, broker/components/cognitive/trace.py. Phase-4 duplicate/variant flags -> none.

#### `broker.components.context`

| File | Lines | Fan-in (# of other broker files that import this) | External consumers (# of `examples/` files that import this) | One-sentence purpose (from docstring or code) |
|---|---|---|---|---|
| broker/components/context/__init__.py | 7 | 0 | 0 | Context building sub-package. |
| broker/components/context/builder.py | 82 | 4 | 3 | Implements builder. |
| broker/components/context/providers.py | 796 | 4 | 1 | Context provider implementations. |
| broker/components/context/tiered.py | 701 | 0 | 1 | Tiered context builder implementations. |
Notes: external-consumer=0 -> broker/components/context/__init__.py. Phase-4 duplicate/variant flags -> none.

#### `broker.components.coordination`

| File | Lines | Fan-in (# of other broker files that import this) | External consumers (# of `examples/` files that import this) | One-sentence purpose (from docstring or code) |
|---|---|---|---|---|
| broker/components/coordination/__init__.py | 8 | 0 | 0 | Multi-agent coordination sub-package. |
| broker/components/coordination/conflict.py | 321 | 1 | 0 | Conflict Resolver - Detect and resolve multi-agent resource conflicts. |
| broker/components/coordination/coordinator.py | 417 | 0 | 1 | Game Master / Coordinator - Central action resolution for MAS. |
| broker/components/coordination/messages.py | 404 | 2 | 1 | Shared Message Pool - Agent-to-agent structured messaging. |
| broker/components/coordination/provider.py | 91 | 0 | 0 | Message Pool Context Provider - Injects agent messages into LLM context. |
Notes: external-consumer=0 -> broker/components/coordination/__init__.py, broker/components/coordination/conflict.py, broker/components/coordination/provider.py. Phase-4 duplicate/variant flags -> none.

#### `broker.components.events`

| File | Lines | Fan-in (# of other broker files that import this) | External consumers (# of `examples/` files that import this) | One-sentence purpose (from docstring or code) |
|---|---|---|---|---|
| broker/components/events/__init__.py | 7 | 0 | 0 | Event management sub-package. |
| broker/components/events/generators/__init__.py | 8 | 0 | 0 | Event generators. |
| broker/components/events/generators/flood.py | 205 | 0 | 0 | Flood Event Generator - Domain-specific implementation. |
| broker/components/events/generators/hazard.py | 292 | 0 | 0 | Hazard Event Generator - Adapter for existing HazardModule. |
| broker/components/events/generators/impact.py | 325 | 0 | 0 | Impact Event Generator - Calculates financial impact from hazard events. |
| broker/components/events/generators/policy.py | 219 | 0 | 0 | Policy Event Generator - Institutional decision events. |
| broker/components/events/ma_manager.py | 336 | 0 | 0 | Multi-Agent Event Manager - Orchestrates events with dependencies. |
| broker/components/events/manager.py | 176 | 2 | 0 | Environment Event Manager - Orchestrates multiple event generators. |
Notes: external-consumer=0 -> broker/components/events/__init__.py, broker/components/events/generators/__init__.py, broker/components/events/generators/flood.py, broker/components/events/generators/hazard.py, broker/components/events/generators/impact.py, broker/components/events/generators/policy.py, broker/components/events/ma_manager.py, broker/components/events/manager.py. Phase-4 duplicate/variant flags -> none.

#### `broker.components.governance`

| File | Lines | Fan-in (# of other broker files that import this) | External consumers (# of `examples/` files that import this) | One-sentence purpose (from docstring or code) |
|---|---|---|---|---|
| broker/components/governance/__init__.py | 7 | 0 | 0 | Skill governance sub-package. |
| broker/components/governance/permissions.py | 142 | 0 | 0 | Generic role-based permission enforcement for multi-agent systems. |
| broker/components/governance/registry.py | 264 | 2 | 3 | Skill Registry - Central registry for skill definitions. |
| broker/components/governance/retriever.py | 140 | 1 | 0 | Skill Retriever - Implements RAG-based skill selection. |
Notes: external-consumer=0 -> broker/components/governance/__init__.py, broker/components/governance/permissions.py, broker/components/governance/retriever.py. Phase-4 duplicate/variant flags -> none.

#### `broker.components.memory`

| File | Lines | Fan-in (# of other broker files that import this) | External consumers (# of `examples/` files that import this) | One-sentence purpose (from docstring or code) |
|---|---|---|---|---|
| broker/components/memory/__init__.py | 34 | 0 | 1 | Memory sub-package — operational memory integration. |
| broker/components/memory/bridge.py | 150 | 0 | 1 | Memory Bridge — Wires Communication Layer outputs into MemoryEngine. |
| broker/components/memory/content_types.py | 71 | 9 | 4 | Canonical memory content type taxonomy. |
| broker/components/memory/engine.py | 171 | 16 | 4 | Abstract Base Class for managing agent memory and retrieval. |
| broker/components/memory/engines/__init__.py | 8 | 0 | 0 | Concrete MemoryEngine implementations. |
| broker/components/memory/engines/hierarchical.py | 95 | 2 | 0 | Tiered memory system inspired by MemGPT. |
| broker/components/memory/engines/humancentric.py | 719 | 2 | 0 | Human-Centered Memory Engine with: |
| broker/components/memory/engines/importance.py | 149 | 2 | 0 | Active Retrieval Engine. |
| broker/components/memory/engines/window.py | 36 | 2 | 0 | Standard sliding window memory. Returns the last N items. |
| broker/components/memory/factory.py | 53 | 1 | 0 | Shared Memory Engine Factory for SA/MA. |
| broker/components/memory/initial_loader.py | 151 | 1 | 0 | Broker-level initial memory loader. |
| broker/components/memory/legacy.py | 209 | 0 | 3 | Legacy Memory Module — CognitiveMemory for multi-agent examples. |
| broker/components/memory/policy_classifier.py | 86 | 3 | 0 | Legacy metadata classifier: map unlabeled metadata dicts to canonical |
| broker/components/memory/policy_filter.py | 118 | 5 | 1 | PolicyFilteredMemoryEngine: proxy that enforces a MemoryWritePolicy. |
| broker/components/memory/registry.py | 195 | 1 | 0 | Plugin registry for memory engines. |
| broker/components/memory/seeding.py | 59 | 1 | 0 | Seed memory engine storage from agent.profile memory lists. |
| broker/components/memory/universal.py | 685 | 1 | 0 | Universal Cognitive Engine (v3) - EMA-based System 1/2 Memory Architecture |
Notes: external-consumer=0 -> broker/components/memory/engines/__init__.py, broker/components/memory/engines/hierarchical.py, broker/components/memory/engines/humancentric.py, broker/components/memory/engines/importance.py, broker/components/memory/engines/window.py, broker/components/memory/factory.py, broker/components/memory/initial_loader.py, broker/components/memory/policy_classifier.py, .... Phase-4 duplicate/variant flags -> legacy.py.

#### `broker.components.orchestration`

| File | Lines | Fan-in (# of other broker files that import this) | External consumers (# of `examples/` files that import this) | One-sentence purpose (from docstring or code) |
|---|---|---|---|---|
| broker/components/orchestration/__init__.py | 6 | 0 | 0 | Orchestration sub-package. |
| broker/components/orchestration/phases.py | 306 | 0 | 0 | Phase Orchestrator - Configurable multi-phase agent execution ordering. |
| broker/components/orchestration/sagas.py | 300 | 0 | 1 | Generic saga transaction coordinator for multi-step agent workflows. |
Notes: external-consumer=0 -> broker/components/orchestration/__init__.py, broker/components/orchestration/phases.py. Phase-4 duplicate/variant flags -> none.

#### `broker.components.prompt_templates`

| File | Lines | Fan-in (# of other broker files that import this) | External consumers (# of `examples/` files that import this) | One-sentence purpose (from docstring or code) |
|---|---|---|---|---|
| broker/components/prompt_templates/__init__.py | 3 | 0 | 0 | Implements   init  . |
| broker/components/prompt_templates/memory_templates.py | 356 | 1 | 0 | Implements memory templates. |
Notes: external-consumer=0 -> broker/components/prompt_templates/__init__.py, broker/components/prompt_templates/memory_templates.py. Phase-4 duplicate/variant flags -> none.

#### `broker.components.social`

| File | Lines | Fan-in (# of other broker files that import this) | External consumers (# of `examples/` files that import this) | One-sentence purpose (from docstring or code) |
|---|---|---|---|---|
| broker/components/social/__init__.py | 7 | 0 | 0 | Social graph and perception sub-package. |
| broker/components/social/config.py | 401 | 0 | 0 | Social Graph Configuration by Agent Type |
| broker/components/social/graph.py | 392 | 2 | 2 | Social Graph Component |
| broker/components/social/perception.py | 392 | 1 | 0 | Perception Filter Implementation - Agent-type specific context transformation. |
Notes: external-consumer=0 -> broker/components/social/__init__.py, broker/components/social/config.py, broker/components/social/perception.py. Phase-4 duplicate/variant flags -> none.

The components cluster shows the intended modular architecture most clearly. Memory, context, cognitive, governance, and analytics each have recognizable responsibilities, but the external-consumer counts indicate that examples still exercise that architecture unevenly. Some sub-packages already behave like shared infrastructure, while others appear to exist primarily for one experiment family or as internal support layers reached indirectly.

### 1b. Top-level `broker/*` cluster

#### `broker.agents`

| File | Lines | Fan-in (# of other broker files that import this) | External consumers (# of `examples/` files that import this) | One-sentence purpose (from docstring or code) |
|---|---|---|---|---|
| broker/agents/__init__.py | 61 | 10 | 5 | Governed AI SDK - Agents Module. |
| broker/agents/base.py | 414 | 1 | 0 | Generic Institutional Agent Framework |
| broker/agents/loader.py | 135 | 0 | 0 | YAML Configuration Loader for Base Agents |
| broker/agents/protocols.py | 154 | 0 | 0 | Agent Protocol Definitions for SDK. |
Notes: external-consumer=0 -> broker/agents/base.py, broker/agents/loader.py, broker/agents/protocols.py. Phase-4 duplicate/variant flags -> none.

#### `broker.config`

| File | Lines | Fan-in (# of other broker files that import this) | External consumers (# of `examples/` files that import this) | One-sentence purpose (from docstring or code) |
|---|---|---|---|---|
| broker/config/__init__.py | 48 | 1 | 1 | Implements   init  . |
| broker/config/agent_types/__init__.py | 73 | 1 | 0 | Agent Types Module - SA/MA Unified Agent Type Configuration. |
| broker/config/agent_types/base.py | 376 | 2 | 0 | Agent Type Base Definitions - Core types for SA/MA unified architecture. |
| broker/config/agent_types/registry.py | 406 | 2 | 0 | Agent Type Registry - Central registry for agent type definitions. |
| broker/config/memory_policy.py | 130 | 5 | 2 | Memory write policy - broker-level content-type-aware governance. |
| broker/config/schema.py | 339 | 0 | 0 | Implements schema. |
Notes: external-consumer=0 -> broker/config/agent_types/__init__.py, broker/config/agent_types/base.py, broker/config/agent_types/registry.py, broker/config/schema.py. Phase-4 duplicate/variant flags -> none.

#### `broker.core`

| File | Lines | Fan-in (# of other broker files that import this) | External consumers (# of `examples/` files that import this) | One-sentence purpose (from docstring or code) |
|---|---|---|---|---|
| broker/core/_audit_helpers.py | 158 | 1 | 0 | AuditMixin — audit trace writing and state management helpers. |
| broker/core/_retry_loop.py | 295 | 1 | 0 | RetryMixin — LLM retry and governance retry loop logic. |
| broker/core/_skill_filtering.py | 96 | 1 | 0 | SkillFilterMixin — skill filtering and option injection for LLM prompts. |
| broker/core/agent_initializer.py | 749 | 0 | 0 | Unified Agent Initializer for SA/MA experiments. |
| broker/core/efficiency.py | 127 | 1 | 0 | Efficiency Hub: Centralized utilities for LLM performance and scaling. |
| broker/core/experiment.py | 10 | 0 | 3 | Modular Experiment System - The "Puzzle" Architecture |
| broker/core/experiment_builder.py | 443 | 2 | 0 | Experiment Builder — fluent API for assembling experiments. |
| broker/core/experiment_runner.py | 607 | 2 | 0 | Experiment Runner — simulation loop engine. |
| broker/core/psychometric.py | 303 | 6 | 0 | Psychometric Framework — Psychological assessment frameworks for agent validation. |
| broker/core/skill_broker_engine.py | 574 | 2 | 0 | Skill Broker Engine - Main orchestrator for Skill-Governed Architecture. |
| broker/core/unified_context_builder.py | 655 | 0 | 0 | Unified Context Builder - SA/MA compatible context construction. |
Notes: external-consumer=0 -> broker/core/_audit_helpers.py, broker/core/_retry_loop.py, broker/core/_skill_filtering.py, broker/core/agent_initializer.py, broker/core/efficiency.py, broker/core/experiment_builder.py, broker/core/experiment_runner.py, broker/core/psychometric.py, .... Phase-4 duplicate/variant flags -> none.

#### `broker.domains`

| File | Lines | Fan-in (# of other broker files that import this) | External consumers (# of `examples/` files that import this) | One-sentence purpose (from docstring or code) |
|---|---|---|---|---|
| broker/domains/__init__.py | 40 | 3 | 0 | Domain packs — pluggable domain-specific content for the governance framework. |
| broker/domains/water/__init__.py | 31 | 0 | 0 | Water domain pack — Protection Motivation Theory, Utility Theory, and |
| broker/domains/water/cognitive_appraisal.py | 78 | 0 | 0 | Cognitive Appraisal Theory framework for irrigation agents. |
| broker/domains/water/financial.py | 94 | 0 | 0 | Financial Risk Theory framework for insurance agents. |
| broker/domains/water/pmt.py | 233 | 0 | 0 | Protection Motivation Theory (PMT) framework for household agents. |
| broker/domains/water/thinking_checks.py | 117 | 0 | 0 | Water-domain thinking-validator metadata and builtin checks. |
| broker/domains/water/utility.py | 91 | 0 | 0 | Utility Theory framework for government agents. |
| broker/domains/water/validator_bundles.py | 64 | 1 | 0 | Water-domain validator bundle adapters. |
Notes: external-consumer=0 -> broker/domains/__init__.py, broker/domains/water/__init__.py, broker/domains/water/cognitive_appraisal.py, broker/domains/water/financial.py, broker/domains/water/pmt.py, broker/domains/water/thinking_checks.py, broker/domains/water/utility.py, broker/domains/water/validator_bundles.py. Phase-4 duplicate/variant flags -> none.

#### `broker.governance`

| File | Lines | Fan-in (# of other broker files that import this) | External consumers (# of `examples/` files that import this) | One-sentence purpose (from docstring or code) |
|---|---|---|---|---|
| broker/governance/__init__.py | 80 | 0 | 0 | Governance Module - Extensible rule-based validation system. |
| broker/governance/rule_types.py | 329 | 5 | 1 | Governance Rule Types - Core type definitions for extensible rule system. |
| broker/governance/type_validator.py | 370 | 1 | 0 | Type Validator - Per-agent-type validation. |
Notes: external-consumer=0 -> broker/governance/__init__.py, broker/governance/type_validator.py. Phase-4 duplicate/variant flags -> none.

#### `broker.interfaces`

| File | Lines | Fan-in (# of other broker files that import this) | External consumers (# of `examples/` files that import this) | One-sentence purpose (from docstring or code) |
|---|---|---|---|---|
| broker/interfaces/__init__.py | 77 | 0 | 0 | Broker Interfaces Package |
| broker/interfaces/artifacts.py | 201 | 2 | 1 | Generic artifact protocol for inter-agent structured communication. |
| broker/interfaces/context_types.py | 570 | 1 | 0 | Context Types - Universal context structures for SA/MA prompt generation. |
| broker/interfaces/coordination.py | 265 | 7 | 0 | Coordination Types - Core type definitions for MAS Communication Layer. |
| broker/interfaces/enrichment.py | 134 | 0 | 0 | Enrichment Protocols - Generic interfaces for agent profile enrichment. |
| broker/interfaces/environment_protocols.py | 134 | 0 | 0 | Environment Protocol Definitions. |
| broker/interfaces/event_generator.py | 122 | 9 | 0 | Event Generator Protocol - Domain-agnostic event generation. |
| broker/interfaces/lifecycle_protocols.py | 94 | 1 | 0 | Lifecycle Hook Protocols - Standardized signatures for experiment orchestration. |
| broker/interfaces/observable_state.py | 115 | 1 | 0 | Observable State Module - General-purpose mechanism for cross-agent observation. |
| broker/interfaces/perception.py | 167 | 1 | 0 | Perception Filter Protocol - Agent-type specific context transformation. |
| broker/interfaces/rating_scales.py | 309 | 3 | 0 | Framework-Aware Rating Scale System. |
| broker/interfaces/schemas.py | 106 | 0 | 0 | Pydantic Schema Validation for Adapter Output. |
| broker/interfaces/simulation_protocols.py | 67 | 0 | 0 | Simulation Engine Protocols - Duck-typed interfaces for environment advancement. |
| broker/interfaces/skill_types.py | 234 | 21 | 7 | Skill Types - Core type definitions for Skill-Governed Architecture. |
Notes: external-consumer=0 -> broker/interfaces/__init__.py, broker/interfaces/context_types.py, broker/interfaces/coordination.py, broker/interfaces/enrichment.py, broker/interfaces/environment_protocols.py, broker/interfaces/event_generator.py, broker/interfaces/lifecycle_protocols.py, broker/interfaces/observable_state.py, .... Phase-4 duplicate/variant flags -> none.

#### `broker.memory`

| File | Lines | Fan-in (# of other broker files that import this) | External consumers (# of `examples/` files that import this) | One-sentence purpose (from docstring or code) |
|---|---|---|---|---|
| broker/memory/__init__.py | 126 | 1 | 0 | Unified Memory Module (v5) - Consolidated Cognitive Memory Architecture. |
| broker/memory/config/__init__.py | 21 | 1 | 0 | Implements   init  . |
| broker/memory/config/cognitive_constraints.py | 205 | 1 | 0 | Cognitive Constraints Configuration based on psychological research. |
| broker/memory/config/defaults.py | 24 | 0 | 0 | Implements defaults. |
| broker/memory/config/domain_config.py | 15 | 0 | 0 | Implements domain config. |
| broker/memory/embeddings.py | 92 | 1 | 0 | Protocol for embedding providers. |
| broker/memory/graph.py | 726 | 0 | 0 | Graph-based Memory Structure with NetworkX. |
| broker/memory/persistence.py | 437 | 0 | 0 | Memory Persistence - Checkpoint and Resume Functionality. |
| broker/memory/retrieval.py | 420 | 1 | 0 | Adaptive Retrieval Engine - Dynamic weight adjustment based on arousal. |
| broker/memory/store.py | 250 | 3 | 0 | Unified Memory Store - Working/Long-term memory with consolidation. |
| broker/memory/strategies/__init__.py | 32 | 2 | 0 | Surprise Calculation Strategies. |
| broker/memory/strategies/base.py | 98 | 1 | 0 | SurpriseStrategy Protocol - Interface for pluggable surprise calculation. |
| broker/memory/strategies/decision_consistency.py | 227 | 0 | 0 | Decision-Consistency Surprise (DCS) Strategy. |
| broker/memory/strategies/ema.py | 225 | 3 | 0 | EMA Surprise Strategy - Exponential Moving Average based surprise detection. |
| broker/memory/strategies/hybrid.py | 134 | 0 | 0 | Hybrid Surprise Strategy - Combines EMA and Symbolic approaches. |
| broker/memory/strategies/multidimensional.py | 311 | 0 | 0 | Multi-dimensional Surprise Strategy - Track multiple variables simultaneously. |
| broker/memory/strategies/symbolic.py | 274 | 1 | 0 | Symbolic Surprise Strategy - Frequency-based novelty detection. |
| broker/memory/unified_engine.py | 554 | 4 | 0 | Unified Cognitive Engine (v5) - Consolidated Memory Architecture. |
| broker/memory/vector_db.py | 355 | 0 | 0 | Vector Database for O(log n) Memory Retrieval. |
Notes: external-consumer=0 -> broker/memory/__init__.py, broker/memory/config/__init__.py, broker/memory/config/cognitive_constraints.py, broker/memory/config/defaults.py, broker/memory/config/domain_config.py, broker/memory/embeddings.py, broker/memory/graph.py, broker/memory/persistence.py, .... Phase-4 duplicate/variant flags -> none.

#### `broker.modules`

| File | Lines | Fan-in (# of other broker files that import this) | External consumers (# of `examples/` files that import this) | One-sentence purpose (from docstring or code) |
|---|---|---|---|---|
| broker/modules/__init__.py | 2 | 1 | 0 | Shared modules for extensible framework components. |
| broker/modules/survey/__init__.py | 30 | 0 | 0 | Generic survey data processing module for agent initialization. |
| broker/modules/survey/agent_initializer.py | 421 | 1 | 2 | Agent Initializer from Survey Data. |
| broker/modules/survey/survey_loader.py | 468 | 2 | 2 | Generic survey data loader for agent initialization. |
Notes: external-consumer=0 -> broker/modules/__init__.py, broker/modules/survey/__init__.py. Phase-4 duplicate/variant flags -> none.

#### `broker.simulation`

| File | Lines | Fan-in (# of other broker files that import this) | External consumers (# of `examples/` files that import this) | One-sentence purpose (from docstring or code) |
|---|---|---|---|---|
| broker/simulation/__init__.py | 11 | 0 | 0 | Simulation Package |
| broker/simulation/base_simulation_engine.py | 50 | 0 | 0 | Base Simulation Engine - Optional reference implementation. |
| broker/simulation/environment.py | 163 | 2 | 1 | Tiered Environment for Scientific World Modeling. |
| broker/simulation/state_manager.py | 222 | 0 | 0 | State Manager - Multi-level state management for single and multi-agent scenarios. |
Notes: external-consumer=0 -> broker/simulation/__init__.py, broker/simulation/base_simulation_engine.py, broker/simulation/state_manager.py. Phase-4 duplicate/variant flags -> none.

#### `broker.tests`

| File | Lines | Fan-in (# of other broker files that import this) | External consumers (# of `examples/` files that import this) | One-sentence purpose (from docstring or code) |
|---|---|---|---|---|
| broker/tests/test_experiment_builder_policy.py | 70 | 0 | 0 | Unit tests for ExperimentBuilder.with_memory_write_policy wiring. |
| broker/tests/test_initial_loader.py | 192 | 0 | 0 | Unit tests for broker initial memory loader. |
| broker/tests/test_memory_content_types.py | 136 | 0 | 0 | Unit tests for MemoryContentType enum and policy_classifier. |
| broker/tests/test_memory_policy_filter.py | 214 | 0 | 0 | Unit tests for PolicyFilteredMemoryEngine proxy. |
Notes: external-consumer=0 -> broker/tests/test_experiment_builder_policy.py, broker/tests/test_initial_loader.py, broker/tests/test_memory_content_types.py, broker/tests/test_memory_policy_filter.py. Phase-4 duplicate/variant flags -> none.

#### `broker.utils`

| File | Lines | Fan-in (# of other broker files that import this) | External consumers (# of `examples/` files that import this) | One-sentence purpose (from docstring or code) |
|---|---|---|---|---|
| broker/utils/adapters/__init__.py | 3 | 0 | 0 | Implements   init  . |
| broker/utils/adapters/deepseek.py | 48 | 2 | 0 | Implements deepseek. |
| broker/utils/adapters/ollama.py | 10 | 0 | 0 | Implements ollama. |
| broker/utils/adapters/openai.py | 10 | 0 | 0 | Implements openai. |
| broker/utils/agent_config.py | 854 | 8 | 7 | Agent Type Configuration Loader |
| broker/utils/async_adapter.py | 117 | 0 | 0 | Async Adapter - Asynchronous model adapter methods. |
| broker/utils/csv_loader.py | 53 | 0 | 0 | Generic CSV loader with flexible column mapping. |
| broker/utils/data_loader.py | 76 | 0 | 0 | Loads agents from a CSV file using a column mapping. |
| broker/utils/governance_auditor.py | 210 | 1 | 0 | Governance Auditor — Singleton for tracking governance interventions. |
| broker/utils/json_repair.py | 20 | 0 | 0 | Implements json repair. |
| broker/utils/llm_utils.py | 568 | 4 | 4 | LLM Utilities - Shared model invocation methods. |
| broker/utils/logging.py | 25 | 19 | 0 | Setup a standard logger with a clean format. |
| broker/utils/model_adapter.py | 10 | 3 | 0 | Model Adapter - Thin layer for multi-LLM support. |
| broker/utils/normalization.py | 64 | 2 | 1 | Normalization utilities for LLM output parsing. |
| broker/utils/parsing/__init__.py | 26 | 1 | 0 | Parsing sub-package — LLM output parsing and model adapters. |
| broker/utils/parsing/base.py | 46 | 1 | 0 | Model Adapter ABC — abstract interface for LLM output parsing. |
| broker/utils/parsing/unified_adapter.py | 859 | 0 | 0 | Unified Adapter — single adapter supporting all models and agent types. |
| broker/utils/parsing_audits.py | 219 | 1 | 0 | Parsing audit utilities extracted from UnifiedAdapter. |
| broker/utils/performance_tuner.py | 251 | 1 | 3 | Performance Tuner - Adaptive configuration for LLM experiments. |
| broker/utils/preprocessors.py | 86 | 1 | 0 | Implements preprocessors. |
| broker/utils/replay.py | 132 | 0 | 0 | Replay Engine - Replay runs from audit trace. |
| broker/utils/retry_formatter.py | 197 | 1 | 0 | Retry Message Formatter with Template Engine support. |
Notes: external-consumer=0 -> broker/utils/adapters/__init__.py, broker/utils/adapters/deepseek.py, broker/utils/adapters/ollama.py, broker/utils/adapters/openai.py, broker/utils/async_adapter.py, broker/utils/csv_loader.py, broker/utils/data_loader.py, broker/utils/governance_auditor.py, .... Phase-4 duplicate/variant flags -> none.

The top-level broker directories read as a mixture of core runtime, compatibility layers, older abstractions, and domain support code. That is not necessarily wrong, but it means future change risk is distributed unevenly: touching the component cluster likely affects the intended modern architecture, while touching some top-level packages may disturb legacy or bridging paths that are no longer obvious from examples alone.

## 2. Public API Surface Per Sub-package

| Sub-package | Exported symbols | Actually imported by examples | Unused exports | Missing exports (imported directly by deep path) |
|---|---|---|---|---|
| broker.components.analytics | - | - | - | broker.components.analytics.feedback:AgentMetricsTracker, broker.components.analytics.feedback:FeedbackDashboardProvider, broker.components.analytics.interaction:InteractionHub |
| broker.components.cognitive | - | - | - | broker.components.cognitive.reflection:AgentReflectionContext, broker.components.cognitive.reflection:ReflectionEngine, broker.components.cognitive.reflection:ReflectionTrigger |
| broker.components.context | - | - | - | broker.components.context.builder:PrioritySchemaProvider, broker.components.context.builder:TieredContextBuilder, broker.components.context.providers:PerceptionAwareProvider, broker.components.context.tiered:load_prompt_templates |
| broker.components.coordination | - | - | - | broker.components.coordination.coordinator:GameMaster, broker.components.coordination.coordinator:PassthroughStrategy, broker.components.coordination.messages:MessagePool |
| broker.components.events | - | - | - | - |
| broker.components.governance | - | - | - | broker.components.governance.registry:SkillRegistry |
| broker.components.memory | CognitiveMemory, InitialLoadReport, MemoryContentType, MemoryProvider, PolicyFilteredMemoryEngine, classify_memory_content, load_initial_memories_from_json | PolicyFilteredMemoryEngine, load_initial_memories_from_json | CognitiveMemory, InitialLoadReport, MemoryContentType, MemoryProvider, classify_memory_content | broker.components.memory.bridge:MemoryBridge, broker.components.memory.content_types:MemoryContentType, broker.components.memory.engine:HierarchicalMemoryEngine, broker.components.memory.engine:HumanCentricMemoryEngine, broker.components.memory.engine:ImportanceMemoryEngine, broker.components.memory.engine:WindowMemoryEngine, broker.components.memory.engine:create_memory_engine, broker.components.memory.legacy:CognitiveMemory, broker.components.memory.legacy:MemoryProvider, broker.components.memory.policy_filter:PolicyFilteredMemoryEngine |
| broker.components.orchestration | - | - | - | broker.components.orchestration.sagas:SagaDefinition, broker.components.orchestration.sagas:SagaStep |
| broker.components.prompt_templates | - | - | - | - |
| broker.components.social | - | - | - | broker.components.social.graph:NeighborhoodGraph, broker.components.social.graph:SocialGraph, broker.components.social.graph:SpatialNeighborhoodGraph, broker.components.social.graph:create_social_graph |
| broker.agents | AgentConfig, AgentProtocol, BaseAgent, Constraint, MemoryCapableAgentProtocol, Objective, PerceptionSource, Skill, StateParam, StatefulAgentProtocol, denormalize, load_agent_configs, load_agents, normalize | AgentConfig, BaseAgent, PerceptionSource, Skill, StateParam | AgentProtocol, Constraint, MemoryCapableAgentProtocol, Objective, StatefulAgentProtocol, denormalize, load_agent_configs, load_agents, normalize | - |
| broker.config | - | load_memory_policy | - | broker.config.memory_policy:CLEAN_POLICY, broker.config.memory_policy:LEGACY_POLICY, broker.config.memory_policy:load_from_config |
| broker.core | - | - | - | broker.core.experiment:ExperimentBuilder, broker.core.experiment:ExperimentRunner |
| broker.domains | - | - | - | - |
| broker.governance | BaseValidator, ConditionType, GovernanceRule, PersonalValidator, PhysicalValidator, RuleCategory, RuleCondition, RuleLevel, SocialValidator, ThinkingValidator, TypeValidator, categorize_rule, get_rule_breakdown, validate_all | - | BaseValidator, ConditionType, GovernanceRule, PersonalValidator, PhysicalValidator, RuleCategory, RuleCondition, RuleLevel, SocialValidator, ThinkingValidator, TypeValidator, categorize_rule, get_rule_breakdown, validate_all | broker.governance.rule_types:GovernanceRule |
| broker.interfaces | ConstructAppraisal, DAMAGE_SEVERITY_DESCRIPTORS, DescriptorMapping, EnvironmentProtocol, FLOOD_DEPTH_DESCRIPTORS, FrameworkType, MemoryContext, NEIGHBOR_COUNT_DESCRIPTORS, PerceptionConfig, PerceptionFilterProtocol, PerceptionFilterRegistryProtocol, PerceptionMode, PositionData, PositionEnricher, PriorityItem, PromptVariables, PsychologicalFrameworkType, RatingScale, RatingScaleRegistry, SocialEnvironmentProtocol, TieredEnvironmentProtocol, UniversalContext, ValueData, ValueEnricher, get_scale_for_framework, validate_rating_value | - | ConstructAppraisal, DAMAGE_SEVERITY_DESCRIPTORS, DescriptorMapping, EnvironmentProtocol, FLOOD_DEPTH_DESCRIPTORS, FrameworkType, MemoryContext, NEIGHBOR_COUNT_DESCRIPTORS, PerceptionConfig, PerceptionFilterProtocol, PerceptionFilterRegistryProtocol, PerceptionMode, PositionData, PositionEnricher, PriorityItem, PromptVariables, PsychologicalFrameworkType, RatingScale, RatingScaleRegistry, SocialEnvironmentProtocol, TieredEnvironmentProtocol, UniversalContext, ValueData, ValueEnricher, get_scale_for_framework, validate_rating_value | broker.interfaces.artifacts:AgentArtifact, broker.interfaces.skill_types:ApprovedSkill, broker.interfaces.skill_types:ExecutionResult, broker.interfaces.skill_types:SkillOutcome, broker.interfaces.skill_types:SkillProposal, broker.interfaces.skill_types:ValidationLevel, broker.interfaces.skill_types:ValidationResult |
| broker.memory | AdaptiveRetrievalEngine, AgentMemoryGraph, AgentVectorIndex, COWAN_CONSERVATIVE, CognitiveConstraints, DomainMemoryConfig, EMASurpriseStrategy, EXTENDED_CONTEXT, FloodDomainConfig, GlobalMemoryConfig, HybridSurpriseStrategy, MEMORY_GRAPH_AVAILABLE, MILLER_STANDARD, MINIMAL, MemoryCheckpoint, MemoryGraph, MemorySerializer, MultiDimensionalSurpriseStrategy, SurpriseStrategy, SymbolicSurpriseStrategy, UnifiedCognitiveEngine, UnifiedMemoryItem, UnifiedMemoryStore, VECTOR_DB_AVAILABLE, VectorMemoryIndex, create_flood_surprise_strategy, load_checkpoint, save_checkpoint | - | AdaptiveRetrievalEngine, AgentMemoryGraph, AgentVectorIndex, COWAN_CONSERVATIVE, CognitiveConstraints, DomainMemoryConfig, EMASurpriseStrategy, EXTENDED_CONTEXT, FloodDomainConfig, GlobalMemoryConfig, HybridSurpriseStrategy, MEMORY_GRAPH_AVAILABLE, MILLER_STANDARD, MINIMAL, MemoryCheckpoint, MemoryGraph, MemorySerializer, MultiDimensionalSurpriseStrategy, SurpriseStrategy, SymbolicSurpriseStrategy, UnifiedCognitiveEngine, UnifiedMemoryItem, UnifiedMemoryStore, VECTOR_DB_AVAILABLE, VectorMemoryIndex, create_flood_surprise_strategy, load_checkpoint, save_checkpoint | - |
| broker.modules | - | - | - | broker.modules.survey.agent_initializer:AgentProfile, broker.modules.survey.agent_initializer:initialize_agents_from_survey, broker.modules.survey.survey_loader:INCOME_MIDPOINTS, broker.modules.survey.survey_loader:SurveyLoader, broker.modules.survey.survey_loader:SurveyRecord |
| broker.simulation | IndividualState, InstitutionalState, SharedState, StateManager | - | IndividualState, InstitutionalState, SharedState, StateManager | broker.simulation.environment:TieredEnvironment |
| broker.tests | - | - | - | - |
| broker.utils | - | - | - | broker.utils.agent_config:AgentTypeConfig, broker.utils.agent_config:GovernanceAuditor, broker.utils.llm_utils:LLM_CONFIG, broker.utils.llm_utils:create_legacy_invoke, broker.utils.normalization:normalize_construct_value, broker.utils.performance_tuner:apply_to_llm_config, broker.utils.performance_tuner:get_optimal_config |
The API comparison confirms that several broker packages are advertised more broadly than the examples actually consume. In practical terms, the stable public surface today is smaller than the exported surface, and the deep-path imports identify where example code still depends on package internals rather than the package facade. Over-exporting increases the compatibility surface that future refactors must preserve, while under-exporting or inconsistent export use creates the more urgent problem of leaky boundaries.

## 3. Providers Map

| Provider dir | Entry-point file | LOC | Tests present | External API env vars referenced | Current status (WORKING / SKELETON / UNUSED) |
|---|---|---|---|---|---|
| anthropic | providers/anthropic.py | 132 | yes | ANTHROPIC_API_KEY | SKELETON |
| factory | providers/factory.py | 192 | yes | - | WORKING |
| gemini | providers/gemini.py | 115 | no | GOOGLE_API_KEY | SKELETON |
| llm_provider | providers/llm_provider.py | 196 | yes | - | WORKING |
| ollama | providers/ollama.py | 133 | yes | - | SKELETON |
| openai_provider | providers/openai_provider.py | 118 | no | OPENAI_API_KEY | WORKING |
| rate_limiter | providers/rate_limiter.py | 199 | no | - | UNUSED |
| smoke | providers/smoke.py | 133 | yes | - | UNUSED |
Providers remain a flat adapter layer at repo root rather than a `broker.providers` package. Static usage suggests only part of this layer participates in active execution paths, while the remainder exists as compatibility or experimental scaffolding. That separation is visible in the graph: the broker core appears to depend more on provider factories and generic interfaces than on every concrete provider file, which is healthy for abstraction but also lets stale adapters survive unnoticed.

## 4. Dead-code Flags

### 4a. Unimported files

| File | Sub-package | Lines | Last modified |
|---|---|---|---|
| broker/_archive/agent_protocols.py | providers | 154 | 2026-02-10 |
| broker/_archive/async_adapter.py | providers | 117 | 2026-01-30 |
| broker/_archive/enrichment.py | providers | 134 | 2026-01-30 |
| broker/_archive/replay.py | providers | 132 | 2026-01-29 |
| broker/agents/loader.py | broker.agents | 135 | 2026-02-11 |
| broker/agents/protocols.py | broker.agents | 154 | 2026-02-11 |
| broker/components/governance/permissions.py | broker.components.governance | 142 | 2026-02-11 |
| broker/domains/water/financial.py | broker.domains | 94 | 2026-02-11 |
| broker/domains/water/pmt.py | broker.domains | 233 | 2026-02-11 |
| broker/domains/water/thinking_checks.py | broker.domains | 117 | 2026-03-07 |
| broker/domains/water/utility.py | broker.domains | 91 | 2026-02-11 |
| broker/interfaces/enrichment.py | broker.interfaces | 134 | 2026-02-11 |
| broker/interfaces/environment_protocols.py | broker.interfaces | 134 | 2026-02-07 |
| broker/interfaces/schemas.py | broker.interfaces | 106 | 2026-01-29 |
| broker/interfaces/simulation_protocols.py | broker.interfaces | 67 | 2026-02-10 |
| broker/memory/config/defaults.py | broker.memory | 24 | 2026-02-10 |
| broker/memory/config/domain_config.py | broker.memory | 15 | 2026-02-10 |
| broker/memory/strategies/hybrid.py | broker.memory | 134 | 2026-02-10 |
| broker/simulation/base_simulation_engine.py | broker.simulation | 50 | 2026-02-10 |
| broker/simulation/state_manager.py | broker.simulation | 222 | 2026-01-30 |
| broker/tests/test_experiment_builder_policy.py | broker.tests | 70 | 2026-04-11 |
| broker/tests/test_initial_loader.py | broker.tests | 192 | 2026-04-11 |
| broker/tests/test_memory_content_types.py | broker.tests | 136 | 2026-04-11 |
| broker/tests/test_memory_policy_filter.py | broker.tests | 214 | 2026-04-11 |
| broker/utils/adapters/ollama.py | broker.utils | 10 | 2026-02-11 |
| broker/utils/adapters/openai.py | broker.utils | 10 | 2026-02-11 |
| broker/utils/async_adapter.py | broker.utils | 117 | 2026-02-11 |
| broker/utils/data_loader.py | broker.utils | 76 | 2026-02-11 |
| broker/utils/json_repair.py | broker.utils | 20 | 2026-02-11 |
| broker/utils/parsing/unified_adapter.py | broker.utils | 859 | 2026-04-03 |
| broker/utils/replay.py | broker.utils | 132 | 2026-02-11 |
| broker/validators/agent/base.py | providers | 135 | 2026-02-11 |
| providers/rate_limiter.py | providers | 199 | 2026-01-29 |
| providers/smoke.py | providers | 133 | 2026-03-07 |
### 4b. Unused classes

| Class | File | Defined but never instantiated? | Defined but only used inside the same file? |
|---|---|---|---|
| ActionConfig | broker/utils/agent_config.py | yes | yes |
| AgentCategory | broker/config/agent_types/base.py | yes | no |
| AgentDriftReport | broker/components/analytics/drift.py | yes | yes |
| AgentLike | broker/components/social/config.py | yes | yes |
| AgentProtocol | broker/_archive/agent_protocols.py | yes | no |
| AgentProtocol | broker/agents/protocols.py | yes | no |
| AgentTCSResult | broker/validators/calibration/temporal_coherence.py | yes | yes |
| AgentTypeConfig | broker/utils/agent_config.py | yes | no |
| AsyncModelAdapter | broker/_archive/async_adapter.py | yes | no |
| AsyncModelAdapter | broker/utils/async_adapter.py | yes | no |
| AuditMixin | broker/core/_audit_helpers.py | yes | no |
| BalancedSampleResult | examples/multi_agent/flood/survey/balanced_sampler.py | yes | yes |
| BaseSimulationEngine | broker/simulation/base_simulation_engine.py | yes | yes |
| BaseValidator | broker/validators/agent/base.py | yes | no |
| BaseValidator | broker/validators/governance/base_validator.py | yes | no |
| BasinSimulation | examples/multi_agent_simple/run.py | yes | yes |
| BehavioralTheory | examples/multi_agent/flood/paper3/analysis/validation/theories/base.py | yes | no |
| BenchmarkCategory | broker/validators/calibration/benchmark_registry.py | yes | no |
| BenchmarkComparison | broker/validators/calibration/benchmark_registry.py | yes | yes |
| BenchmarkConfig | examples/multi_agent/flood/paper3/analysis/config_loader.py | yes | yes |
| BenchmarkReport | broker/validators/calibration/benchmark_registry.py | yes | no |
| BenchmarkSpec | examples/multi_agent/flood/paper3/analysis/config_loader.py | yes | yes |
| CACRDecomposition | examples/multi_agent/flood/paper3/analysis/validation/metrics/l1_micro.py | yes | no |
| CACRResult | broker/validators/calibration/micro_validator.py | yes | yes |
| CalibrationReport | broker/validators/calibration/calibration_protocol.py | yes | yes |
| CalibrationStage | broker/validators/calibration/calibration_protocol.py | yes | no |
| CausalTestReport | examples/multi_agent/flood/paper3/analysis/memory_causal_test.py | yes | yes |
| ClaimResult | examples/multi_agent/flood/environment/core.py | yes | yes |
| CognitiveAppraisalFramework | broker/domains/water/cognitive_appraisal.py | yes | no |
| CoherenceRule | broker/utils/agent_config.py | yes | yes |
| ConditionType | broker/governance/rule_types.py | yes | yes |
| ConservatismReport | broker/validators/calibration/conservatism_diagnostic.py | yes | yes |
| ContextProvider | broker/components/context/providers.py | yes | no |
| CoordinatorStrategy | broker/components/coordination/coordinator.py | yes | yes |
| CrossRunStability | examples/multi_agent/flood/paper3/analysis/validation/metrics/l4_meta.py | yes | yes |
| CustomEnricher | tests/test_agent_initializer.py | yes | yes |
| CustomFilter | tests/test_perception_filter.py | yes | yes |
| CustomFramework | tests/test_psychometric.py | yes | yes |
| CustomGraph | broker/components/social/graph.py | yes | yes |
| CustomMemoryEnricher | tests/test_agent_initializer.py | yes | yes |
### 4c. Unused functions

| Function | File | Call sites outside its module |
|---|---|---|
| action_dist | examples/multi_agent/flood/paper3/analysis/rq2_equity_figure.py | 0 |
| action_rates | examples/multi_agent/flood/paper3/analysis/rq2_institutional_analysis.py | 0 |
| actions_only_df | tests/test_cv_router.py | 0 |
| adapter | tests/integration/test_sa_e2e_smoke.py | 0 |
| adapter | tests/test_adapter_parsing.py | 0 |
| adapter | tests/test_adapter_parsing.py | 0 |
| adapter | tests/test_alias_normalization.py | 0 |
| add_agent_post | examples/multi_agent/flood/components/media_channels.py | 0 |
| add_experience | broker/components/memory/legacy.py | 0 |
| add_experience | broker/components/memory/legacy.py | 0 |
| add_flood_bands | examples/multi_agent/flood/paper3/analysis/figures/working/scripts/gen_rq2_pub_figure.py | 0 |
| add_inset_nj | examples/multi_agent/flood/paper3/analysis/figures/working/scripts/gen_study_area_map.py | 0 |
| add_memory_with_persist | broker/components/memory/universal.py | 0 |
| add_north_arrow | examples/multi_agent/flood/paper3/analysis/figures/working/scripts/gen_study_area_map.py | 0 |
| add_note | examples/multi_agent/flood/paper3/scripts/add_rq3_refs.py | 0 |
| add_scale_bar | examples/multi_agent/flood/paper3/analysis/figures/working/scripts/gen_study_area_map.py | 0 |
| add_state_snapshot | tests/integration/test_sa_e2e_smoke.py | 0 |
| add_swap_tests | broker/validators/calibration/directional_validator.py | 0 |
| add_table_row | examples/multi_agent/flood/paper3/analysis/_build_expert_review_docx.py | 0 |
| add_trace | tests/integration/test_sa_e2e_smoke.py | 0 |
| add_working | broker/components/memory/legacy.py | 0 |
| agent_and_state | tests/test_fql.py | 0 |
| agent_ids | examples/irrigation_abm/irrigation_env.py | 0 |
| agent_pair | tests/conftest.py | 0 |
| agent_type | broker/_archive/agent_protocols.py | 0 |
| agent_type | broker/agents/base.py | 0 |
| agent_type | broker/agents/protocols.py | 0 |
| agent_type | broker/components/social/perception.py | 0 |
| agent_type | broker/components/social/perception.py | 0 |
| agent_type | broker/components/social/perception.py | 0 |
| agent_type | broker/interfaces/perception.py | 0 |
| agent_type | examples/multi_agent/flood/ma_agents/government.py | 0 |
| agent_type | examples/multi_agent/flood/ma_agents/household.py | 0 |
| agent_type | examples/multi_agent/flood/ma_agents/insurance.py | 0 |
| agent_type_registry | tests/test_unified_context_builder.py | 0 |
| agent_types | broker/utils/agent_config.py | 0 |
| agent_types | examples/multi_agent/flood/paper3/analysis/validation/theories/base.py | 0 |
| agent_types | examples/multi_agent/flood/paper3/analysis/validation/theories/examples.py | 0 |
| agent_types | examples/multi_agent/flood/paper3/analysis/validation/theories/examples.py | 0 |
| agent_types | examples/multi_agent/flood/paper3/analysis/validation/theories/pmt.py | 0 |
| agents | tests/test_phase_orchestrator.py | 0 |
| aggregate_ehe | examples/irrigation_abm/analysis/ensemble_analysis.py | 0 |
| all_validators | broker/validators/calibration/validation_router.py | 0 |
| allowed_counts | broker/components/memory/policy_filter.py | 0 |
| always_hazard | examples/multi_agent/flood/paper3/tests/test_null_model.py | 0 |
| analysis_1 | examples/multi_agent/flood/paper3/analysis/rq3_crosslayer_analysis.py | 0 |
| analysis_2 | examples/multi_agent/flood/paper3/analysis/rq3_crosslayer_analysis.py | 0 |
| analysis_3 | examples/multi_agent/flood/paper3/analysis/rq3_crosslayer_analysis.py | 0 |
| analysis_4 | examples/multi_agent/flood/paper3/analysis/rq3_crosslayer_analysis.py | 0 |
| analysis_a | examples/multi_agent/flood/paper3/analysis/rq3_feedback_rigorous.py | 0 |
| analysis_b | examples/multi_agent/flood/paper3/analysis/rq3_feedback_rigorous.py | 0 |
| analysis_c | examples/multi_agent/flood/paper3/analysis/rq3_feedback_rigorous.py | 0 |
| analysis_d | examples/multi_agent/flood/paper3/analysis/rq3_feedback_rigorous.py | 0 |
| analysis_e | examples/multi_agent/flood/paper3/analysis/rq3_feedback_rigorous.py | 0 |
| analysis_f | examples/multi_agent/flood/paper3/analysis/rq3_feedback_rigorous.py | 0 |
| analyze_clusters | examples/irrigation_abm/analysis/governed_vs_ungoverned.py | 0 |
| analyze_cohort_entropy | examples/single_agent/archive/deepseek_r1_finished/analysis_scripts/calculate_entropy_time_series.py | 0 |
| analyze_rule_interventions | examples/single_agent/archive/deepseek_r1_finished/analysis_scripts/analyze_rule_blocks.py | 0 |
| apply_base_style | examples/multi_agent/flood/paper3/analysis/figures/working/scripts/gen_rq2_pub_figure.py | 0 |
| apply_decay | broker/memory/unified_engine.py | 0 |
These dead-code tables should be read as Phase 1 candidates, not deletion instructions. Static analysis undercounts dynamic loading, registry lookup, reflection, and YAML-selected entry points, so the strongest signals are repeated zero-import modules and same-file-only helpers in non-registry code. The most credible cleanup targets are where multiple indicators agree: no incoming imports, no external consumers, and no cross-module class or function use.

## 5. Test File Map

| Sub-package | Unit-test files | Integration-test files | Approximate test count (via grep `def test_`) | Coverage status (unknown at this phase) |
|---|---|---|---|---|
| broker.components.analytics | tests/connectivity_smoke_test.py, tests/test_feedback_provider.py, tests/test_drift_detector.py, tests/test_context_providers.py, tests/test_observable_state.py, tests/flood/test_interaction.py, tests/test_audit_modular.py | tests/integration/test_sa_environment_audit.py, tests/manual/test_visible_neighbor_actions.py | 129 | unknown at this phase |
| broker.components.cognitive | tests/test_cognitive_cache_governance.py, tests/test_reflection_engine_v2.py, tests/core/test_cognitive_cache.py, tests/test_cognitive_constraints.py, tests/test_irrigation_integration.py, tests/test_dynamic_importance.py, tests/test_reflection_personalization.py | - | 67 | unknown at this phase |
| broker.components.context | tests/connectivity_smoke_test.py, tests/test_context_providers.py, tests/test_irrigation_integration.py, tests/test_context_builder_split.py, tests/test_tiered_builder_no_hub.py, tests/test_v3_2_features.py, tests/verify_dynamic_context.py, tests/test_unified_context_builder.py, tests/test_context_types.py | - | 107 | unknown at this phase |
| broker.components.coordination | tests/test_message_pool.py, tests/test_058_integration.py, tests/test_conflict_resolver.py, tests/test_coordinator.py | tests/integration/test_communication_layer.py | 71 | unknown at this phase |
| broker.components.events | tests/test_event_manager.py, tests/test_context_providers.py, tests/test_event_generator.py, tests/test_ma_event_generators.py | - | 44 | unknown at this phase |
| broker.components.governance | tests/test_governance_rules.py, tests/connectivity_smoke_test.py, tests/test_cognitive_cache_governance.py, tests/test_skill_retrieval.py, tests/test_multi_skill.py, tests/test_broker_core.py, tests/conftest.py, tests/test_v3_2_features.py | tests/integration/test_sa_skill_registry.py, tests/integration/test_sa_e2e_smoke.py | 75 | unknown at this phase |
| broker.components.memory | broker/tests/test_experiment_builder_policy.py, tests/test_ma_reflection.py, broker/tests/test_memory_policy_filter.py, broker/tests/test_initial_loader.py, tests/test_unified_memory.py, tests/test_memory_factory.py, tests/flood/test_flood_memory_scorer.py, tests/flood/test_memory_v4_config.py, tests/test_memory_integration.py, tests/test_memory_persistence.py, tests/test_memory_templates.py, tests/test_human_centric_memory_engine.py, tests/test_initial_memory_split.py, tests/test_memory_engine_scoring.py, tests/test_memory_bridge.py, tests/test_memory_engine_split.py, tests/test_memory_config.py, tests/test_irrigation_integration.py, tests/flood/test_module_integration.py, tests/test_tiered_builder_no_hub.py, tests/core/test_experiment_runner.py, tests/conftest.py, tests/test_v3_2_features.py, tests/test_universal_memory.py, tests/test_memory_graph.py, tests/test_stratified_retrieval.py, tests/test_universal_stratified.py, broker/tests/test_memory_content_types.py | - | 295 | unknown at this phase |
| broker.components.orchestration | tests/test_saga_coordinator.py, tests/test_phase_orchestrator.py, tests/test_058_integration.py | tests/integration/test_communication_layer.py | 49 | unknown at this phase |
| broker.components.prompt_templates | - | - | 0 | unknown at this phase |
| broker.components.social | tests/flood/test_social_network_mini.py, tests/connectivity_smoke_test.py, tests/test_social_graph_config.py, tests/flood/test_interaction.py, tests/test_perception_filter.py | tests/manual/test_visible_neighbor_actions.py | 120 | unknown at this phase |
| broker.agents | tests/connectivity_smoke_test.py, tests/core/test_experiment_runner.py, tests/conftest.py, tests/test_v3_2_features.py | tests/integration/test_sa_e2e_smoke.py | 23 | unknown at this phase |
| broker.config | broker/tests/test_experiment_builder_policy.py, broker/tests/test_memory_policy_filter.py, broker/tests/test_initial_loader.py, tests/test_agent_type_registry.py, tests/flood/test_memory_v4_config.py, tests/test_psychometric.py, tests/test_social_graph_config.py, tests/test_type_validator.py, tests/test_memory_config.py, tests/test_config_schema.py, tests/test_minimal_nonwater_config.py, tests/test_agent_config_rating_scale.py, tests/test_unified_context_builder.py | - | 284 | unknown at this phase |
| broker.core | broker/tests/test_experiment_builder_policy.py, tests/test_agent_initializer.py, tests/connectivity_smoke_test.py, tests/flood/test_flood_memory_scorer.py, tests/test_skill_retrieval.py, tests/test_psychometric.py, tests/core/__init__.py, tests/core/test_cognitive_cache.py, tests/core/test_experiment_runner.py, tests/test_broker_core.py, tests/test_v3_2_features.py, tests/test_unified_context_builder.py | - | 184 | unknown at this phase |
| broker.domains | tests/test_psychometric.py, tests/test_domain_validator_dispatch.py | - | 58 | unknown at this phase |
| broker.governance | tests/test_governance_rules.py, tests/test_cognitive_cache_governance.py, tests/test_thinking_validator.py, tests/test_type_validator.py | - | 84 | unknown at this phase |
| broker.interfaces | tests/test_artifacts.py, tests/test_governance_rules.py, tests/test_ma_reflection.py, tests/test_rating_scales.py, tests/connectivity_smoke_test.py, tests/test_skill_retrieval.py, tests/test_message_pool.py, tests/test_phase_orchestrator.py, tests/test_type_validator.py, tests/test_event_manager.py, tests/test_context_providers.py, tests/test_memory_bridge.py, tests/test_058_integration.py, tests/test_event_generator.py, tests/test_council.py, tests/test_observable_state.py, tests/test_framework_registration_generic.py, tests/flood/test_interaction.py, tests/test_irrigation_integration.py, tests/test_cross_agent_validation.py, tests/test_agent_config_rating_scale.py, tests/flood/test_module_integration.py, tests/test_action_feedback.py, tests/test_multi_skill.py, tests/test_conflict_resolver.py, tests/test_ma_event_generators.py, tests/core/test_experiment_runner.py, tests/test_coordinator.py, tests/test_broker_core.py, tests/test_response_format_builder.py, tests/conftest.py, tests/test_v3_2_features.py, tests/test_unified_context_builder.py, tests/test_context_types.py, tests/test_adapter_parsing.py, tests/test_artifact_fallbacks.py | tests/integration/test_communication_layer.py, tests/integration/test_sa_skill_registry.py, tests/integration/test_sa_e2e_smoke.py, tests/integration/test_sa_validators.py, tests/integration/test_sa_parsing.py | 583 | unknown at this phase |
| broker.memory | broker/tests/test_memory_policy_filter.py, tests/test_unified_memory.py, tests/test_memory_factory.py, tests/flood/test_flood_memory_scorer.py, tests/flood/test_memory_v4_config.py, tests/test_memory_integration.py, tests/test_vector_db.py, tests/test_memory_persistence.py, tests/test_multidim_surprise.py, tests/test_memory_templates.py, tests/test_human_centric_memory_engine.py, tests/test_initial_memory_split.py, tests/test_memory_engine_scoring.py, tests/test_memory_bridge.py, tests/test_memory_engine_split.py, tests/test_cognitive_constraints.py, tests/test_memory_config.py, tests/test_decision_consistency_surprise.py, tests/test_universal_memory.py, tests/test_memory_graph.py, broker/tests/test_memory_content_types.py | - | 261 | unknown at this phase |
| broker.modules | tests/test_flood_survey_loader.py, tests/test_survey_pollution.py, tests/test_agent_profile_extensions.py | - | 14 | unknown at this phase |
| broker.simulation | tests/test_world_models.py, tests/test_tiered_environment.py | tests/integration/test_sa_environment_audit.py, tests/integration/test_sa_e2e_smoke.py | 32 | unknown at this phase |
| broker.tests | broker/tests/test_experiment_builder_policy.py, tests/flood/test_social_network_mini.py, tests/test_artifacts.py, tests/test_governance_rules.py, tests/test_ma_reflection.py, broker/tests/test_memory_policy_filter.py, tests/test_agent_initializer.py, tests/test_calibration_protocol.py, tests/test_provider_smoke.py, broker/tests/test_initial_loader.py, tests/test_rating_scales.py, tests/test_saga_coordinator.py, tests/test_agent_type_registry.py, tests/connectivity_smoke_test.py, tests/test_unified_memory.py, tests/test_cognitive_cache_governance.py, tests/test_memory_factory.py, tests/flood/test_flood_memory_scorer.py, tests/flood/test_memory_v4_config.py, tests/test_memory_integration.py, tests/test_reflection_engine_v2.py, tests/test_skill_retrieval.py, tests/test_alias_normalization.py, tests/test_feedback_provider.py, tests/test_message_pool.py, tests/test_vector_db.py, tests/test_phase_orchestrator.py, tests/test_memory_persistence.py, tests/test_drift_detector.py, tests/test_cv_temporal.py, tests/test_multidim_surprise.py, tests/test_memory_templates.py, tests/test_human_centric_memory_engine.py, tests/test_flood_survey_loader.py, tests/test_psychometric.py, tests/test_thinking_validator.py, tests/test_gemma4_nw_crossmodel_analysis.py, tests/test_survey_pollution.py, tests/core/__init__.py, tests/core/test_cognitive_cache.py, tests/test_initial_memory_split.py, tests/test_memory_engine_scoring.py, tests/test_world_models.py, tests/sdk/__init__.py, tests/test_reflection_triggers.py, tests/test_social_graph_config.py, tests/test_cv_distribution.py, tests/test_cv_psychometric.py, tests/test_type_validator.py, tests/test_survey_loader_split.py, tests/test_event_manager.py, tests/test_context_providers.py, tests/test_memory_bridge.py, tests/test_memory_engine_split.py, tests/test_agent_profile_extensions.py, tests/test_cognitive_constraints.py, tests/test_058_integration.py, tests/test_memory_config.py, tests/test_tp_decay_split.py, tests/test_model_adapter_split.py, tests/test_parse_confidence.py, tests/test_run_unified_experiment_split.py, tests/test_event_generator.py, tests/test_nature_water_figure_helpers.py, tests/test_cv_runner.py, tests/test_prompt_file_loading.py, tests/test_council.py, tests/test_domain_validator_dispatch.py, tests/test_benchmark_registry.py, tests/test_observable_state.py, tests/test_decision_consistency_surprise.py, tests/test_csv_loader.py, tests/test_retry_formatter.py, tests/test_framework_registration_generic.py, tests/flood/test_interaction.py, tests/test_irrigation_integration.py, tests/flood/__init__.py, tests/test_config_schema.py, tests/test_cross_agent_validation.py, tests/test_dynamic_importance.py, tests/test_minimal_nonwater_config.py, tests/test_agent_config_rating_scale.py, tests/test_audit_modular.py, tests/flood/test_module_integration.py, tests/test_action_feedback.py, tests/test_multi_skill.py, tests/test_conflict_resolver.py, tests/test_reflection_personalization.py, tests/fixtures/mock_llm.py, tests/test_ma_event_generators.py, tests/test_context_builder_split.py, tests/test_tiered_builder_no_hub.py, tests/toy_domain/engine.py, tests/core/test_experiment_runner.py, tests/test_coordinator.py, tests/test_broker_core.py, tests/test_response_format_builder.py, tests/flood/test_parsing.py, tests/conftest.py, tests/fixtures/__init__.py, tests/test_v3_2_features.py, tests/verify_dynamic_context.py, tests/test_fql.py, tests/test_hazard_split.py, tests/test_universal_memory.py, tests/test_tiered_environment.py, tests/flood/test_floodabm_alignment.py, tests/test_unified_context_builder.py, tests/test_memory_graph.py, tests/test_directional_validator.py, tests/test_stratified_retrieval.py, tests/test_cv_micro.py, tests/test_multi_skill_integration.py, tests/test_context_types.py, tests/test_adapter_parsing.py, tests/test_demographic_audit.py, tests/test_irrigation_env.py, tests/test_universal_stratified.py, tests/test_cv_router.py, broker/tests/test_memory_content_types.py, tests/test_perception_filter.py, tests/test_artifact_fallbacks.py | tests/integration/test_real_llm_smoke.py, tests/integration/test_communication_layer.py, tests/integration/test_sa_skill_registry.py, tests/integration/__init__.py, tests/integration/test_sa_environment_audit.py, tests/manual/test_visible_neighbor_actions.py, tests/integration/test_sa_e2e_smoke.py, tests/integration/test_sa_validators.py, tests/integration/test_sa_parsing.py | 1900 | unknown at this phase |
| broker.utils | tests/connectivity_smoke_test.py, tests/test_alias_normalization.py, tests/test_csv_loader.py, tests/test_retry_formatter.py, tests/test_framework_registration_generic.py, tests/test_minimal_nonwater_config.py, tests/test_agent_config_rating_scale.py, tests/test_audit_modular.py, tests/flood/test_module_integration.py, tests/test_broker_core.py, tests/test_response_format_builder.py, tests/flood/test_parsing.py, tests/test_multi_skill_integration.py, tests/test_adapter_parsing.py, tests/test_demographic_audit.py | tests/integration/test_real_llm_smoke.py, tests/integration/test_sa_e2e_smoke.py, tests/integration/test_sa_parsing.py | 226 | unknown at this phase |
Red flags: packages with zero associated test files -> broker.components.prompt_templates. This table is directional rather than definitive, but it still highlights where there is no obvious dedicated verification footprint before Phase 2. In a governance framework, sparse test attachment is most concerning around packages that alter prompts, memory semantics, or validation behavior, because those failures often surface late in end-to-end runs.

## 6. Cross-domain Usage Matrix

| Broker sub-package | irrigation_abm | single_agent | multi_agent/flood |
|---|---|---|---|
| broker.components.analytics | Y | Y | N |
| broker.components.cognitive | Y | Y | Y |
| broker.components.context | Y | Y | Y |
| broker.components.coordination | N | N | Y |
| broker.components.events | N | N | N |
| broker.components.governance | Y | Y | N |
| broker.components.memory | Y | Y | Y |
| broker.components.orchestration | N | N | Y |
| broker.components.prompt_templates | N | N | N |
| broker.components.social | N | Y | Y |
| broker.agents | Y | Y | Y |
| broker.config | N | N | Y |
| broker.core | Y | Y | N |
| broker.domains | N | N | N |
| broker.governance | Y | N | N |
| broker.interfaces | Y | Y | Y |
| broker.memory | N | N | N |
| broker.modules | N | Y | Y |
| broker.simulation | N | N | Y |
| broker.tests | N | N | N |
| broker.utils | Y | Y | Y |
Sub-packages consumed by only one example domain: broker.components.coordination, broker.components.orchestration, broker.config, broker.governance, broker.simulation. Cross-domain asymmetry is not automatically a defect, but it is a useful pressure test for package placement. If a broker package is truly framework-level, one expects either direct imports across multiple domains or an obvious indirect role in shared builders and runners; otherwise the code may be generalized earlier than reuse justifies.

## 7. Summary Findings

Top 5 inventory-level surprises:

1. No example import sites touch broker.components.events, broker.components.prompt_templates, broker.domains, broker.memory ....

2. Top-level broker.memory (19 modules) and broker.components.memory (17 modules) are distinct stacks with different consumer patterns.

3. Provider inventory includes non-working or inactive entries: anthropic, gemini, ollama, rate_limiter, smoke.

4. Zero associated tests were detected for broker.components.prompt_templates.

5. Examples reach into internal modules for broker.components.analytics, broker.components.cognitive, broker.components.context, broker.components.coordination, broker.components.governance ..., indicating leaky package boundaries.


Count totals: total broker modules = 193; total LOC = 44387; total test files = 131; total providers = 8.

Phase 2 readiness: Requested context file memory/MEMORY.md is absent, so historical provider notes had to be inferred from code instead of prior memory. Syntax errors were observed while parsing: broker/components/context/builder.py, broker/components/prompt_templates/__init__.py, broker/components/prompt_templates/memory_templates.py, broker/config/__init__.py, broker/config/schema.py, ...

Overall, the repository looks structurally ready for a correctness pass because the major package clusters are parseable and the import graph is coherent enough to inspect without execution. The main uncertainties are operational rather than architectural: provider credentials are environment-dependent, some runtime behavior is likely selected through YAML or builder wiring instead of direct imports, and several packages rely on broad integration-style coverage rather than narrow unit tests. That does not block Phase 2, but it argues for starting with focused smoke imports and package-targeted tests before any broad suite run.
