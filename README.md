# Water Agent Governance Framework

<div align="center">

**A Governance Framework for LLM-Driven Agent-Based Models in Water Resources**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ollama](https://img.shields.io/badge/Ollama-Local_Inference-000000?style=flat&logo=ollama&logoColor=white)](https://ollama.com/)

[**English**](README.md) | [**中文**](README_zh.md)

</div>

## Mission Statement

> _"Turning LLM Storytellers into Rational Actors for Hydro-Social Agent-Based Models."_

The **Water Agent Governance Framework** addresses the fundamental **Logic-Action Gap** in Large Language Model (LLM) agents: while LLMs produce fluent natural-language reasoning, they exhibit stochastic instability, hallucinations, and memory erosion across long-horizon simulations — problems that undermine the scientific validity of LLM-driven agent-based models (ABMs).

This framework provides an architectural **Governance Layer** that validates agent reasoning against physical constraints and behavioral theories (e.g., Protection Motivation Theory, PMT) in real time. It is designed for **flood risk adaptation research** and other hydro-social modeling contexts where reproducibility, auditability, and long-horizon consistency are essential.

**Target domains**: nonstationary flood risk adaptation, irrigation water management, household adaptation behavior, community resilience, water resource policy evaluation.

**Validated case studies**:

- **Flood Household Adaptation (SA)**: 100 agents using PMT (Protection Motivation Theory), 10-year simulation with Gemma 3 (4B/12B/27B)
- **Flood Multi-Agent (MA)**: 400 agents (balanced 4-cell design: Mapped/Non-Mapped Geography × Owner/Renter) with institutional agents (Government, Insurance), 13-year simulation on the Potomac River Basin (PRB)
- **Irrigation Water Management**: 78 agents from the Colorado River Simulation System (CRSS) representing the Upper Colorado River Basin

---

## Quick Start

### 0. Try the 30-Second Demo (No Ollama Needed)

See the core governance loop with a mock LLM:

```bash
python examples/quickstart/01_barebone.py
```

Then see governance rules blocking invalid actions:

```bash
python examples/quickstart/02_governance.py
```

See `docs/guides/quickstart_guide.md` for the full 3-tier progressive tutorial.

### 1. Install

```bash
pip install -r requirements.txt
```

### 2. Run a Governed Flood Simulation

Launch a 10-agent flood adaptation demo with governance and human-centric memory (requires [Ollama](https://ollama.com/)):

```bash
python examples/governed_flood/run_experiment.py --model gemma3:4b --years 3 --agents 10
```

### 3. Run the Full Benchmark (WRR — _Water Resources Research_ Paper)

Replicate the three-group ablation study (100 agents, 10 years):

```bash
python examples/single_agent/run_flood.py --model gemma3:4b --years 10 --agents 100 \
    --memory-engine humancentric --governance-mode strict
```

### 4. Explore More

| Example | Complexity | Description | Link |
| :--- | :--- | :--- | :--- |
| **Governed Flood** | Beginner | Standalone Group C demo with full governance | [Go](examples/governed_flood/) |
| **Single Agent** | Intermediate | JOH (_Journal of Hydrology_) Benchmark: Groups A/B/C ablation study | [Go](examples/single_agent/) |
| **Irrigation ABM** | Intermediate | Colorado River Basin water demand (Hung & Yang, 2021) | [Go](examples/irrigation_abm/) |
| **Multi-Agent** | Advanced | Social dynamics, insurance market, government policy | [Go](examples/multi_agent/flood/) |

### 5. Provider Support

The framework supports multiple LLM providers via the `providers/` package:

```bash
# Local inference (default)
python examples/governed_flood/run_experiment.py --model gemma3:4b

# Cloud providers (requires API key in environment)
python examples/governed_flood/run_experiment.py --model anthropic:claude-sonnet-4-5-20250929
python examples/governed_flood/run_experiment.py --model openai:gpt-4o
python examples/governed_flood/run_experiment.py --model gemini:gemini-1.5-flash
```

| Provider | Module | Auth |
| :--- | :--- | :--- |
| **Ollama** | `providers/ollama.py` | None (local) |
| **Anthropic** | `providers/anthropic.py` | `ANTHROPIC_API_KEY` |
| **OpenAI** | `providers/openai_provider.py` | `OPENAI_API_KEY` |
| **Gemini** | `providers/gemini.py` | `GOOGLE_API_KEY` |

### 6. ExperimentBuilder API

```python
from broker.core.experiment import ExperimentBuilder
from broker.components.memory.engines.humancentric import HumanCentricMemoryEngine

runner = (
    ExperimentBuilder()
    .with_model("gemma3:4b")          # or "anthropic:claude-sonnet-4-5-20250929"
    .with_years(3)
    .with_agents(agents)
    .with_simulation(sim_engine)
    .with_skill_registry("config/skill_registry.yaml")
    .with_governance("strict", "config/agent_types.yaml")
    .with_memory_engine(HumanCentricMemoryEngine())
    .with_seed(42)
    .build()
)
runner.run()
```

See the [Experiment Design Guide](docs/guides/experiment_design_guide.md) for the full API reference.

---

## Navigation

| I am a... | Start here |
| :--- | :--- |
| **Researcher** wanting to reproduce results | [Theoretical Basis](docs/modules/00_theoretical_basis_overview.md) → [Experiment Design](docs/guides/experiment_design_guide.md) → [Case Studies](examples/README.md) → [C&V Framework](broker/validators/calibration/README.md) |
| **Developer** wanting to extend the framework | [Architecture](docs/architecture/architecture.md) → [ExperimentBuilder API](#6-experimentbuilder-api) → [Customization Guide](docs/guides/customization_guide.md) → [Agent Type Spec](docs/guides/agent_type_specification_guide.md) |
| **Paper contributor** | [For Paper Contributors](#for-paper-contributors) |

---

## Module Directory

The `broker/` package is organized into **9 sub-packages** across seven architectural layers.
L1–L5 and L7 power all experiments; L6 is multi-agent only.

> File paths are relative to `broker/`. Detailed docs linked where available.

### L1 — LLM Interface Layer

> Constructs bounded context for the LLM, invokes the model, and parses structured responses.

| Module | Path | Role |
| :--- | :--- | :--- |
| **TieredContextBuilder** | `components/context/tiered.py` | CORE / HISTORIC / RECENT tiered prompt construction |
| **ContextProviders** | `components/context/providers.py` | Pluggable context enrichment chain |
| **FeedbackProvider** | `components/analytics/feedback.py` | Config-driven metric trends & YAML assertion dashboard |
| **PerceptionFilter** | `components/social/perception.py` | Agent-type-aware information filtering |
| **ResponseFormatBuilder** | `components/response_format.py` | YAML-driven response format & output parsing |
| **Efficiency** | `core/efficiency.py` | Model-adaptive context optimization |

[Context System docs](docs/modules/context_system.md) | [中文](docs/modules/context_system_zh.md)

### L2 — Governance Layer

> Validates proposals against physical, psychological, and semantic rules; manages skill brokering and audit.

| Module | Path | Role |
| :--- | :--- | :--- |
| **SkillBrokerEngine** | `core/skill_broker_engine.py` | Core 6-stage pipeline (context → LLM → parse → validate → approve → execute) |
| **SkillRegistry** | `components/governance/registry.py` | YAML-loaded action ontology with preconditions |
| **SkillRetriever** | `components/governance/retriever.py` | RAG (Retrieval-Augmented Generation) context-aware skill selection |
| **AuditWriter** | `components/analytics/audit.py` | Structured CSV audit trail |
| **DriftDetector** | `components/analytics/drift.py` | Behavioral drift detection across time steps |
| *Governance validators* | `validators/governance/` | 5-category pipeline: Physical, Thinking, Personal, Social, Semantic |
| *Post-hoc analysis* | `validators/posthoc/` | R_H hallucination rate & keyword classifier |
| *Calibration & Validation* | `validators/calibration/` | C&V framework: micro, macro, psychometric |

[Governance docs](docs/modules/governance_core.md) | [中文](docs/modules/governance_core_zh.md) | [C&V Framework](broker/validators/calibration/README.md)

### L3 — Execution & Environment Layer

> Runs experiments, manages simulation state, generates environmental events, handles agent lifecycle.

| Module | Path | Role |
| :--- | :--- | :--- |
| **ExperimentRunner** | `core/experiment.py` | Experiment orchestrator with seed control |
| **AgentInitializer** | `core/agent_initializer.py` | Agent construction from YAML + survey data |
| **SimulationEngine** | `simulation/base_simulation_engine.py` | Sandboxed skill execution engine |
| **ObservableState** | `components/analytics/observable.py` | Bounded agent observation interface |
| *Event generators* | `components/events/generators/` | Domain event sources (flood, hazard, impact, policy) |
| *Event managers* | `components/events/manager.py` | Environment event lifecycle management |

[Simulation Engine docs](docs/modules/simulation_engine.md) | [中文](docs/modules/simulation_engine_zh.md)

### L4 — Memory & Retrieval Layer

> Encodes, stores, consolidates, and retrieves agent memories with emotion-weighted importance and temporal decay.

| Module | Path | Role |
| :--- | :--- | :--- |
| **MemoryEngine** | `components/memory/engine.py` | Abstract memory interface |
| **MemoryFactory** | `components/memory/factory.py` | Engine selection from config flags |
| *Engine implementations* | `components/memory/engines/` | Window, Importance, HumanCentric, Hierarchical |
| **MemoryBridge** | `components/memory/bridge.py` | v2↔v4 compatibility adapter |
| **MemorySeeding** | `components/memory/seeding.py` | Initial memory injection from JSON profiles |
| **UnifiedCognitive** | `components/memory/universal.py` | Hybrid memory with EMA (Exponential Moving Average) surprise detection |

[Memory docs](docs/modules/memory_components.md) | [中文](docs/modules/memory_components_zh.md)

### L5 — Reflection Layer

> Periodically consolidates episodic memories into generalized insights via LLM-driven reflection.

| Module | Path | Role |
| :--- | :--- | :--- |
| **ReflectionEngine** | `components/cognitive/reflection.py` | Batch reflection with domain-specific questions |
| **DomainAdapters** | `components/cognitive/adapters.py` | Domain-specific reflection prompts |

[Reflection docs](docs/modules/reflection_engine.md) | [中文](docs/modules/reflection_engine_zh.md)

### L6 — Social & Communication Layer

> *Multi-agent only.* Manages social networks, inter-agent messaging, phased execution, and conflict resolution.

| Module | Path | Role |
| :--- | :--- | :--- |
| **SocialGraph** | `components/social/graph.py` | Network topology and neighbor queries |
| **InteractionHub** | `components/analytics/interaction.py` | Multi-tier information diffusion |
| **PhaseOrchestrator** | `components/orchestration/phases.py` | Ordered agent-type execution phases |
| **SagaCoordinator** | `components/orchestration/sagas.py` | Multi-step transaction coordination with rollback |
| **ConflictResolver** | `components/coordination/conflict.py` | Inter-agent action conflict arbitration |
| *Messaging* | `components/coordination/messages.py` | Broadcast message queue and context injection |

### L7 — Utilities & Infrastructure

> Cross-cutting services: LLM adapters, JSON repair, configuration schema, type definitions.

| Module | Path | Role |
| :--- | :--- | :--- |
| **LLMUtils** | `utils/llm_utils.py` | Config-driven LLM calls with timeout and model quirks |
| **ModelAdapter** | `utils/model_adapter.py` | Multi-layer defensive parsing (JSON repair → regex → fallback) |
| *LLM Providers* | `providers/` | Ollama, Anthropic, OpenAI, Gemini provider implementations |
| *Config schema* | `config/schema.py`, `config/agent_types/` | YAML configuration and agent type registry |
| *Type interfaces* | `interfaces/` | Type definitions: `skill_types`, `context_types`, `schemas`, etc. |

### Theoretical Foundation & Experiments

- **[Theoretical Basis](docs/modules/00_theoretical_basis_overview.md)** | [中文](docs/modules/00_theoretical_basis_overview_zh.md)
- **[Skill Registry (Action Ontology)](docs/modules/skill_registry.md)** | [中文](docs/modules/skill_registry_zh.md)
- **[Experiments & Benchmarks](examples/README.md)**

---

## Documentation & Guides

### Integration Guides (`docs/guides/`)

- **[Experiment Design Guide](docs/guides/experiment_design_guide.md)**: Recipe for building new experiments.
- **[Agent Assembly Guide](docs/guides/agent_assembly.md)**: How to stack "Cognitive Blocks" (Level 1-3). | [中文](docs/guides/agent_assembly_zh.md)
- **[Customization Guide](docs/guides/customization_guide.md)**: Adding new skills, validators, and audit fields.
- **[Integration Guide](docs/guides/integration_guide.md)**: Connecting external environments to the broker.
- **[Agent Type Specification Guide](docs/guides/agent_type_specification_guide.md)**: Defining new agent types in YAML.
- **[Advanced Patterns Guide](docs/guides/advanced_patterns.md)**: State hierarchy, two-way coupling, per-agent-type LLM configuration.
- **[Multi-Agent Setup Guide](docs/guides/multi_agent_setup_guide.md)**: Full walkthrough for heterogeneous agent populations.
- **[Troubleshooting Guide](docs/guides/troubleshooting_guide.md)**: Error catalog with solutions.
- **[YAML Configuration Reference](docs/references/yaml_configuration_reference.md)**: Field-by-field reference for all YAML files.

### Architecture Specs (`docs/architecture/`)

- **[High-Level Architecture](docs/architecture/architecture.md)**: System diagrams and data flow.
- **[Skill Architecture](docs/architecture/skill_architecture.md)**: Deep dive into the Action/Skill ontology.
- **[MAS Five-Layer Mapping](docs/architecture/mas-five-layers.md)**: Multi-agent system architecture (AgentTorch alignment).

### Multi-Agent Ecosystem (`docs/multi_agent_specs/`)

- **[Government Agents](docs/multi_agent_specs/government_agent_spec.md)**: Subsidies, buyouts & policy logic.
- **[Insurance Market](docs/multi_agent_specs/insurance_agent_spec.md)**: Premium calculation & risk models.
- **[Institutional Behavior](docs/multi_agent_specs/institutional_agent_behavior_spec.md)**: Interaction protocols.
- **[Multi-Agent Constructs](docs/multi_agent_specs/multi_agent_constructs.md)**: Cross-agent behavioral constructs.
- **[Experiment 3 Design](docs/multi_agent_specs/exp3_multi_agent_design.md)**: Full multi-agent experiment design.

---

## Core Problem Statement

![Core Challenges & Framework Solutions](docs/challenges_solutions_v3.png)

LLM-driven ABMs face five recurring problems that this framework solves:

| Challenge            | Problem Description                                  | Framework Solution                                                         | Component           |
| :------------------- | :--------------------------------------------------- | :------------------------------------------------------------------------- | :------------------ |
| **Hallucination**    | LLM generates invalid actions (e.g., "build a wall") | **Strict Registry**: Only registered `skill_id`s are accepted              | `SkillRegistry`     |
| **Context Limit**    | Cannot dump entire history into prompt               | **Salience Memory**: Retrieves only top-k relevant past events             | `MemoryEngine`      |
| **Inconsistency**    | Decisions contradict reasoning (Logical Drift)       | **Thinking Validators**: Checks logical coherence between TP/CP and Choice | `SkillBrokerEngine` |
| **Opaque Decisions** | "Why did agent X do Y?" is lost                      | **Structured Trace**: Logs Input, Reasoning, Validation, and Outcome       | `AuditWriter`       |
| **Unsafe Mutation**  | LLM output breaks simulation state                   | **Sandboxed Execution**: Validated skills are executed by engine, not LLM  | `SimulationEngine`  |
| **Feedback Gap**     | Agent cannot reason about env constraints             | **Feedback Dashboard**: Config-driven metric trends & assertion injection  | `FeedbackProvider`  |

---

## Unified Architecture (v3.5)

The framework utilizes a layered governance architecture that unifies single-agent isolated reasoning with multi-agent social simulations. As of v3.5, all broker-level modules are **fully domain-agnostic** — construct names, action vocabularies, LLM timeouts, and validation keywords are loaded from YAML configuration rather than hardcoded.

![Unified Architecture v3.3](docs/architecture.png)

### Combinatorial Intelligence ("Stacking Blocks")

The framework implements a **Stacking Blocks** architecture. You can build agents of varying cognitive complexity by stacking different modules onto the base Execution Engine:

| Stack Level   | Cognitive Block      | Function          | Effect                                                                                                                                    |
| :------------ | :------------------- | :---------------- | :---------------------------------------------------------------------------------------------------------------------------------------- |
| **Base**      | **Execution Engine** | _The Body_        | Can execute actions but has no memory or rationality.                                                                                     |
| **+ Level 1** | **Context Lens**     | _The Eyes_        | Adds bounded perception (Window Memory). Prevents context overflow.                                                                       |
| **+ Level 2** | **Memory Engine**    | _The Hippocampus_ | Adds **HumanCentric Memory Engine**. Emotional salience encoding (importance = emotion × source) with stochastic consolidation and decay. |
| **+ Level 3** | **Skill Broker**     | _The Superego_    | Adds **Governance**. Enforces "Thinking Rules" to ensure decisions match beliefs (Rationality).                                           |

> **Why this matters for research**: This design enables controlled ablation studies. Run a Level 1 Agent (Group A — baseline) vs. Level 3 Agent (Group C — full cognitive) to isolate exactly _which_ cognitive component resolves a specific behavioral bias.

**[Learn how to assemble custom agents](docs/guides/agent_assembly.md)**

### Framework Evolution

![Framework Evolution](docs/memory_evolution_v1_v2_v3.png)

The memory and governance architecture has evolved through three phases:

- **v1 (Legacy)**: [Availability Heuristic] — Monolithic scripts with basic Window Memory. (Group A/B Baseline).
- **v2 (Weighted)**: [Context-Dependent Memory] — Modular `SkillBrokerEngine` with **Weighted Retrieval** ($S = W_{rec}R + W_{imp}I + W_{ctx}C$).
- **v3 (Current)**: [Emotion-Weighted Memory Architecture] — Introduces multiple memory engines. Production experiments use **HumanCentricMemoryEngine** in basic ranking mode.
  - **Importance = Emotion × Source**: Keyword-classified emotional weight (critical/major/positive/shift/routine) multiplied by source proximity (personal > neighbor > community > abstract).
  - **Stochastic Consolidation**: High-importance memories have probabilistic transfer to long-term storage ($P = 0.7$ when importance $> 0.6$). Memory caps with smart eviction (working: 20, long-term: 100).
  - **Exponential Decay**: $I(t) = I_0 \cdot e^{-\lambda t}$ applied to long-term memories.
  - **Retrieval (basic ranking mode)**: Recent `window_size` working memories + top-K significant long-term memories ranked by `decayed_importance`. No weighted scoring ($W_{rec}, W_{imp}, W_{ctx}$).
  - **v2-next extensions** (available, default-off): Contextual Resonance ($W_{rel}$, overlap coefficient), Interference-Based Forgetting ($W_{int}$, retroactive suppression), and SurprisePlugin interface for Decision-Consistency Surprise (unigram/bigram action prediction). Full 5-dimensional scoring: $S = W_{rec} R + W_{imp} I + W_{ctx} C + W_{rel} Rel - W_{int} Int$.
  - _Note_: A more advanced `UnifiedCognitiveEngine` with EMA-based surprise detection and System 1/2 switching exists but is **not used** in the WRR experiments.

**[Deep Dive: Memory Priority & Retrieval Math](docs/modules/memory_components.md)**

### Sub-Package Architecture

After restructuring, `broker/components/` is organized into 9 domain sub-packages:

```
broker/components/
├── analytics/         # Audit, drift detection, feedback, observable state
├── cognitive/         # Reflection engine, domain adapters, cognitive trace
├── context/           # TieredContextBuilder, context providers
├── coordination/      # Conflict resolution, message pool, coordinator
├── events/            # Event generators (flood, hazard, impact, policy)
├── governance/        # Skill registry, skill retriever, role permissions
├── memory/            # Memory engine, factory, engines/, seeding, bridge
├── orchestration/     # Phase orchestrator, saga coordinator
├── social/            # Social graph, perception filters, graph config
├── prompt_templates/  # Memory prompt templates
└── response_format.py # YAML-driven response format builder
```

### Provider Layer

| Component | File | Description |
| :--- | :--- | :--- |
| **UnifiedAdapter** | `utils/model_adapter.py` | Smart parsing: handles model-specific quirks (DeepSeek `<think>` tags, Llama JSON) |
| **LLM Utils** | `utils/llm_utils.py` | Config-driven LLM calls: timeout, model quirks, mock responses |
| **LLMProvider (ABC)** | `providers/llm_provider.py` | Abstract provider interface with registry and routing |
| **OllamaProvider** | `providers/ollama.py` | Local inference provider (default) |
| **AnthropicProvider** | `providers/anthropic.py` | Anthropic Claude API provider |
| **OpenAIProvider** | `providers/openai_provider.py` | OpenAI API provider |
| **GeminiProvider** | `providers/gemini.py` | Google Gemini API provider |
| **RateLimitedProvider** | `providers/rate_limiter.py` | Token-bucket rate limiting wrapper for cloud providers |

### Validator Layer (Governance Rule Engine)

> **Architecture Overview**
>
> The validator layer is the core governance mechanism of the framework. Every skill proposal
> passes through a pipeline of five category validators before execution. Each validator
> produces `ValidationResult` objects with two severity levels: **ERROR** (blocks the action
> and triggers a retry loop, max 3 attempts) or **WARNING** (logs the observation but
> preserves agent autonomy).

```
broker/validators/governance/
│
├── base_validator.py            # Abstract base: YAML rules + BuiltinCheck injection
│
├── physical_validator.py        # Category: "physical"
│   ├── flood_already_elevated       BuiltinCheck   ERROR
│   ├── flood_already_relocated      BuiltinCheck   ERROR
│   └── flood_renter_restriction     BuiltinCheck   ERROR
│
├── thinking_validator.py        # Category: "thinking"
│   ├── _builtin_pmt_check           BuiltinCheck   ERROR  (PMT: TP/CP)
│   ├── _builtin_utility_check       BuiltinCheck   ERROR  (Utility: Budget/Equity)
│   ├── _builtin_financial_check     BuiltinCheck   ERROR  (Financial: Risk/Solvency)
│   └── _validate_yaml_rules()       Multi-condition YAML engine (domain-agnostic)
│
├── personal_validator.py        # Category: "personal"
│   └── flood_elevation_affordability BuiltinCheck  ERROR
│
├── social_validator.py          # Category: "social"  [WARNING ONLY]
│   └── flood_majority_deviation      BuiltinCheck  WARNING
│
└── semantic_validator.py        # Category: "semantic"
    ├── flood_social_proof_hallucination  BuiltinCheck  ERROR
    ├── flood_temporal_grounding          BuiltinCheck  WARNING
    └── flood_state_consistency           BuiltinCheck  WARNING
```

#### Class Hierarchy (類繼承結構)

```
BaseValidator (ABC)                    # broker/validators/governance/base_validator.py
│   validate(skill_name, rules, ctx)   → List[ValidationResult]
│   _default_builtin_checks()          → List[BuiltinCheck]        # Override per domain
│
├── PhysicalValidator                  # State preconditions + irreversible action guards
│                                        物理驗證器：狀態前置條件 + 不可逆操作守衛
├── ThinkingValidator                  # Construct-action consistency (PMT / Utility / Financial)
│                                        思維驗證器：構念-行為一致性
├── PersonalValidator                  # Financial + cognitive constraints
│                                        個人驗證器：財務與認知約束
├── SocialValidator                    # Neighbor influence observation (WARNING only)
│                                        社會驗證器：鄰居影響觀測（僅警告）
└── SemanticGroundingValidator         # Free-text reasoning vs simulation ground truth
                                         語義接地驗證器：推理文本 vs 模擬事實
```

#### Design Philosophy

| Principle                       | Description                                                                                                                                | Rationale                                                                                                                                                                                          |
| :------------------------------ | :----------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ERROR vs WARNING**            | ERROR (`valid=False`) triggers retry loop (max 3). WARNING (`valid=True`) logs but does not block.                                         | Prevents "Governance Dead Zone" — preserves agent autonomy while maintaining observability. |
| **Insurance Renewal Exclusion** | `buy_insurance` when already insured is NOT flagged as hallucination.                                                                      | Insurance expires annually (`has_insurance` reset each year). Unlike elevation/relocation (irreversible), renewal is rational behavior. |
| **Domain-Agnostic Core**        | `BaseValidator` + `BuiltinCheck` pattern. Domain checks are pluggable functions: `(skill_name, rules, context) -> List[ValidationResult]`. | YAML-driven condition engine is fully generic. Domain-specific logic is injected, not hardcoded. |
| **Dual Evaluation Path**        | 1) YAML-driven rules filtered by `self.category`; 2) Injected `_builtin_checks` (hardcoded domain logic).                                  | YAML rules support rapid prototyping; built-in checks provide compile-time safety for critical invariants.                                                                                         |
| **Template Interpolation**      | Rule messages support `{context.TP_LABEL}`, `{rule.id}` via `RetryMessageFormatter`.                                                       | Retry prompts contain the exact violation reason, enabling the LLM to self-correct.                                                                                                                |

#### Validator Category Details

Five categories: **Physical** (irreversible state guards), **Thinking** (construct-action coherence via PMT/Utility/Financial), **Personal** (financial capacity), **Social** (neighbor influence, WARNING only), **Semantic** (reasoning vs. ground truth hallucination detection).

See [Governance Core docs](docs/modules/governance_core.md) for full check tables, trigger conditions, and hallucination taxonomy.

---

## Advanced Memory & Skill Retrieval (v3.2)

For long-horizon simulations (10+ years), v3.2 introduced a **Tiered Memory System** and **Dynamic Skill Retrieval (RAG)** to maintain decision consistency without exceeding LLM context limits.

### Tiered Memory

Memory is organized into three functional tiers rather than a simple sliding window:

- **CORE (Semantic)**: Fixed agent attributes (income, personality traits, governance profile).
- **HISTORIC (Episodic Summary)**: Long-term compressed history of significant events (e.g., specific flood impacts).
- **RECENT (Episodic)**: High-resolution records from the most recent years.

### Context-Aware Skill Retrieval (RAG)

For simulations with many possible actions, the framework uses a **SkillRetriever** to inject only the most relevant actions into the prompt:

- **Adaptive Precision**: Filters irrelevant skills based on current context (e.g., when threat is high, prioritize relocation-related skills), reducing the LLM's cognitive load.
- **Benchmark Compatibility**: When using `WindowMemoryEngine`, RAG is automatically disabled for fair comparison with legacy baselines (v1.0/v3.1).

---

## Cognitive Architecture & Design Philosophy

The **Context Builder** is not just a data pipe; it is a designed **Cognitive Lens** that structures reality to mitigate LLM hallucinations and cognitive biases.

### 1. Structural Bias Mitigation

We explicitly engineer the prompt context to counteract known LLM limitations:

- **Scale Anchoring (The "Floating M" Problem)**: Small models (3B-4B) lose track of symbol definitions in long contexts.
  - **Design**: We use **Inline Semantic Anchoring** (e.g., `TP=M(Medium)` instead of just `TP=M`) to enforce immediate understanding.
- **Option Primacy Bias**: LLMs statistically prefer the first option in a list.
  - **Design**: The `ContextBuilder` implements **Dynamic Option Shuffling**, ensuring that "Do Nothing" or "Buy Insurance" do not benefit from positional advantage.
- **The "Goldfish Effect" (Recency Bias)**: Models forget early instructions when overloaded with recent events.
  - **Design**: We use a **Tiered Context Hierarchy** (`Personal State -> Local Observation -> Global Memory`). This places survival-critical data (State) closest to the decision block, while compressing distant memories.

### 2. The Logic-Action Validator & Explainable Feedback Loop

- **Challenge**: The "Logic-Action Gap." Small LLMs often output a reasoning string that classifies a threat as "Very High" (VH) but then select "Do Nothing" due to syntax confusion or reward bias.
- **Solution**: The **SkillBrokerEngine** implements a **Recursive Feedback Loop** (see [Skill Architecture](docs/architecture/skill_architecture.md) for the full 6-stage pipeline):
  1. **Detection**: Validators scan the parsed response. If `TP=VH` but `Action=Do Nothing`, an `InterventionReport` is generated.
  2. **Injection**: The framework extracts the specific violation and injects it into a **Retry Prompt**.
  3. **Instruction**: The LLM is told: _"Your previous response was rejected due to logical inconsistency. Here is why: [Violation]. Please reconsider."_
  4. **Trace**: This entire exchange between the Broker and the LLM is captured in the `AuditWriter` for full transparency.

---

## Memory Architecture

![Human-Centric Memory System](docs/human_centric_memory_diagram.png)

### Available Memory Engines

The framework provides four memory engines of increasing cognitive complexity. Each experiment chooses ONE engine via the `--memory-engine` CLI flag:

- Use **WindowMemoryEngine** for baseline comparisons (no importance weighting — fair comparison with traditional ABMs)
- Use **HumanCentricMemoryEngine** for single-agent experiments requiring emotional salience and trauma modeling (validated in JOH/WRR single-agent benchmark)
- **ImportanceMemoryEngine** is a lightweight alternative that adds importance scoring without consolidation
- Use **UnifiedCognitiveEngine** for multi-agent experiments with memory-mediated threat perception (used in Paper 3 WRR multi-agent flood simulation; emotional weights major=1.2, minor=0.8, neutral=0.3; source weights personal=1.0, social=0.7, policy=0.5)

| Engine                       | CLI Flag                       | Complexity | Used In                        | Description                                                                                              |
| :--------------------------- | :----------------------------- | :--------- | :----------------------------- | :------------------------------------------------------------------------------------------------------- |
| **WindowMemoryEngine**       | `--memory-engine window`       | Minimal    | Flood Group B                  | FIFO sliding window. Keeps last N memories, no importance scoring.                                       |
| **ImportanceMemoryEngine**   | `--memory-engine importance`   | Low        | —                              | Adds keyword-based importance scoring to window retrieval.                                               |
| **HumanCentricMemoryEngine** | `--memory-engine humancentric` | Medium     | **Flood Group C, Irrigation**  | Emotion × source importance, stochastic consolidation, exponential decay. v2-next: contextual resonance, interference forgetting, surprise plugin. |
| **UnifiedCognitiveEngine**   | `--memory-engine universal`    | High       | **Flood Multi-Agent (Paper 3)** | Adds EMA-based surprise detection, System 1/2 switching, and recalibrated emotional weights (major=1.2, minor=0.8) for memory-mediated TP.  |

### HumanCentricMemoryEngine — Detail (used in all WRR experiments)

This is the production memory engine for all governed experiments (flood Group C + irrigation). It supports two ranking modes:

- **Basic ranking mode** (`--memory-ranking-mode legacy`, the default): Validated in all WRR experiments. Uses simple recency + decayed importance for retrieval without contextual adjustments. Recommended for reproducibility and baseline comparisons.
- **Weighted mode** (`--memory-ranking-mode weighted`): Experimental. Adds contextual boosters (e.g., flood events increase relevance of flood-related memories). Not used in WRR experiments.

**Encoding** (`add_memory`):

1. Classify emotion type by keyword matching → `emotion_weight` (critical=1.0, major=0.9, positive=0.8, shift=0.7, observation=0.4, routine=0.1)
2. Classify source proximity by keyword matching → `source_weight` (personal=1.0, neighbor=0.7, community=0.5, abstract=0.3)
3. Compute `importance = emotion_weight × source_weight`
4. If importance > `consolidation_threshold` (0.6), probabilistically transfer to long-term memory (P=0.7)

**Retrieval** (basic ranking mode — used in WRR experiments):

1. Return the most recent `window_size` (5) working memories
2. Apply exponential decay to long-term memories: $I(t) = I_0 \cdot e^{-\lambda t}$
3. Select top-K (2) long-term memories by `decayed_importance`
4. Return: `[top-K significant] + [recent N]`
5. No weighted scoring ($W_{rec}, W_{imp}, W_{ctx}$). Contextual boosters are **ignored** in basic ranking mode.

**Retrieval** (weighted mode — available but NOT used in WRR):

- Computes $S = W_{rec} \cdot R + W_{imp} \cdot I + W_{ctx} \cdot C$ (recency 0.3, importance 0.5, context 0.2)
- Contextual boosters actively adjust relevance scores
- Activated via `--memory-ranking-mode weighted`

### Reflection Engine

The `ReflectionEngine` (`broker/components/cognitive/reflection.py`) runs at configurable intervals (default: every year) to consolidate episodic memories into generalized insights. It is automatically invoked by the experiment runner at year-end when using `HumanCentricMemoryEngine` or `UnifiedCognitiveEngine`. Each reflection adds one LLM call per agent per interval.

1. **Batch Consolidation**: Collects recent memories and prompts the LLM to synthesize lessons learned.
2. **Domain-Specific Guidance**: Reflection questions are loaded from `agent_types.yaml` (`global_config.reflection.questions`), enabling domain-tailored consolidation (e.g., flood trauma vs irrigation strategy).
3. **Action-Outcome Feedback**: Agents receive combined action + outcome memories (e.g., "Year 3: You chose to increase demand (by 15%). You requested 120,000 AF and received 95,000 AF."), enabling causal learning.
4. **Insight Storage**: Generated insights are stored with elevated importance scores ($I = 0.9$) to resist decay.

### Memory Tier Structure

| Tier  | Component               | Function                                                                                          |
| :---- | :---------------------- | :------------------------------------------------------------------------------------------------ |
| **1** | **Working Memory**      | Immediate context (last `window_size` years). Always included in retrieval.                       |
| **2** | **Long-Term Memory**    | Consolidated significant events. Subject to exponential decay.                                    |
| **3** | **Reflection Insights** | Abstracted lessons from reflection (e.g., "Insurance is vital"). High importance to resist decay. |

**[Read the full Memory & Reflection Specification](docs/modules/memory_components.md)**

---

## State Management

### State Ownership (Multi-Agent)

| State Type        | Examples                              | Scope                | Read      | Write           |
| :---------------- | :------------------------------------ | :------------------- | :-------- | :-------------- |
| **Individual**    | `memory`, `elevated`, `has_insurance` | Agent-private        | Self only | Self only       |
| **Social**        | `neighbor_actions`, `last_decisions`  | Observable neighbors | Neighbors | System          |
| **Shared**        | `flood_occurred`, `year`              | All agents           | All       | System          |
| **Institutional** | `subsidy_rate`, `policy_mode`         | All agents           | All       | Government only |

> **Key point**: `memory` is **Individual** — each agent has its own memory, never shared.

---

## Validation Pipeline & Domain Configurations

The `SkillBrokerEngine` runs a 5-category ordered validation pipeline (Physical → Thinking → Personal → Social → Semantic) on every `SkillProposal`. ERROR results trigger a retry loop (max 3) with human-readable feedback; WARNING results are logged but do not block execution.

**Four hallucination types** are detected: Physical (irreversible state violations), Thinking (construct-action inconsistency), Economic (absurd resource decisions), and Semantic (reasoning contradicts ground truth).

**Domain support**: The `validate_all(domain=...)` parameter selects which `BuiltinCheck` functions are injected. Flood (11 checks) and Irrigation (8 checks + 4 YAML rules) are built-in. New domains add checks via `builtin_checks=[your_fn]` — no core broker changes needed.

See [Governance Core](docs/modules/governance_core.md) for the full pipeline diagram, per-domain check tables, hallucination taxonomy, and domain extension guide.

---

## Configuration-Driven Extension (v3.5)

As of v3.5, the `broker/` layer contains **zero hardcoded domain-specific values** — all timeouts, model quirks, construct labels, and keyword lists are read from YAML. Existing experiments work without config changes (defaults match previous hardcoded values).

See [YAML Configuration Reference](docs/references/yaml_configuration_reference.md) for the full parameter reference (memory engine, weighted scoring, reflection, LLM, governance, and StateParam normalization).

### YAML vs. Python Extension Boundary

| What You Want to Change | YAML Only | Python Required | Config File |
| :--- | :---: | :---: | :--- |
| Add/remove skills (actions) | Yes | — | `skill_registry.yaml` |
| Define agent types & personas | Yes | — | `agent_types.yaml` |
| Add/modify governance rules | Yes | — | `agent_types.yaml` → `governance.rules` |
| Tune memory parameters (window, decay, weights) | Yes | — | `agent_types.yaml` → `global_config.memory` |
| Change LLM model or timeout | Yes | — | `agent_types.yaml` → `global_config.llm` |
| Change response format fields | Yes | — | `agent_types.yaml` → `response_format.fields` |
| Add a new BuiltinCheck (domain validator) | — | Yes | Implement in `broker/validators/governance/` |
| Add a new MemoryEngine | — | Yes | Subclass `MemoryEngine` ABC |
| Add a new LLM Provider | — | Yes | Subclass `LLMProvider` ABC in `providers/` |
| Add a new domain (beyond flood/irrigation) | — | Yes | New `lifecycle_hooks.py` + `skill_registry.yaml` + `agent_types.yaml` |
| Custom calibration metrics (C&V) | — | Yes | Provide `compute_metrics_fn` to `CalibrationProtocol` |

### How to Extend (Interface Contracts)

To add a **new memory engine**, subclass the ABC in `broker/components/memory/engine.py`:

```python
class MemoryEngine(ABC):
    @abstractmethod
    def add_memory(self, agent_id: str, content: str,
                   metadata: Optional[Dict[str, Any]] = None) -> None: ...
    @abstractmethod
    def retrieve(self, agent: BaseAgent, query: Optional[str] = None,
                 top_k: int = 3, **kwargs) -> List[dict]: ...
    @abstractmethod
    def clear(self, agent_id: str) -> None: ...
```

To add a **new LLM provider**, subclass the ABC in `providers/llm_provider.py`:

```python
class LLMProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str: ...
    @abstractmethod
    def invoke(self, prompt: str, **kwargs) -> LLMResponse: ...
    @abstractmethod
    async def ainvoke(self, prompt: str, **kwargs) -> LLMResponse: ...
    def validate_connection(self) -> bool: ...  # default provided
```

To add a **new validator**, subclass `BaseValidator` in `broker/validators/governance/base_validator.py`:

```python
class BaseValidator(ABC):
    category: str                          # e.g., "physical", "thinking"
    @abstractmethod
    def _default_builtin_checks(self) -> List[BuiltinCheck]: ...
    # validate() is provided by base — override _default_builtin_checks only
```

To add a **new domain** (e.g., wildfire, drought), provide:

1. `skill_registry.yaml` — action ontology for the domain
2. `agent_types.yaml` — persona definitions, constructs, governance rules
3. `lifecycle_hooks.py` — subclass `BaseLifecycleHooks` for environment setup and state transitions
4. (Optional) Domain-specific `BuiltinCheck` functions for validators

---

## Skill System

The Skill System is the framework's **action ontology** — a 6-stage pipeline (Context → LLM → Parse → Validate → Approve → Execute) managed by the `SkillBrokerEngine`. Skills are defined in YAML (`skill_registry.yaml`) with `skill_id`, `preconditions`, `output_schema` (JSON Schema), `conflicts_with`, and `implementation_mapping`.

Key components:

| Concept | Description |
| :--- | :--- |
| **SkillRegistry** | Central registry loaded from YAML — eligibility checks, precondition enforcement, output schema validation |
| **SkillProposal** | Parsed LLM output before validation (skill name, construct labels, magnitude) |
| **ApprovedSkill** | Post-validation result with APPROVED/REJECTED/REJECTED_FALLBACK status |
| **ResponseFormatBuilder** | Converts YAML `response_format.fields` into structured prompt instructions (supports `text`, `appraisal`, `choice`, `numeric` field types) |
| **ModelAdapter** | Multi-layer defensive parsing: enclosure → JSON repair → keyword regex → digit extraction → fallback |

The pipeline supports format retries (2 max, for parse failures) and governance retries (3 max, for validation ERROR), with human-readable feedback injected into retry prompts.

See [Skill Architecture](docs/architecture/skill_architecture.md) for the full pipeline diagram, response format spec, registry configuration, and v3.4/v3.5 enhancements (JSON Schema validation, composite skill declarations, flexible numeric parsing).

---

## Post-Hoc Calibration & Validation (C&V)

While the [Validator Layer](#validator-layer-governance-rule-engine) enforces coherence at **runtime** (blocking hallucinations before execution), the C&V framework evaluates simulation outputs **after** a run completes. It answers: _"Did the governed agents produce scientifically plausible behavior?"_

The pipeline validates at three hierarchical levels, following Grimm et al. (2005) pattern-oriented modelling:

| Level | Scope | Core Metrics | What It Tests |
| :---- | :---- | :----------- | :------------ |
| **L1 — MICRO** | Individual agent | **CACR** (Construct-Action Coherence Rate), **R_H** (Hallucination Rate + EBE: Event-Based Evaluation) | Are individual decisions internally coherent with reported psychological constructs? |
| **L2 — MACRO** | Population | **GCR** (Governance Concordance Rate), **EPI** (Empirical Plausibility Index) | Do aggregate adoption rates match empirical benchmarks (NFIP: National Flood Insurance Program, survey data)? |
| **L3 — COGNITIVE** | Psychometric | **ICC(2,1)** + **eta-squared** (effect size) | Does the LLM produce reliable, discriminable construct ratings across replicates? |

Key design features:

- **Zero LLM calls** for L1/L2 — operates entirely on audit CSV traces
- **Config-driven routing** — the `ValidationRouter` auto-detects applicable metrics from `agent_types.yaml`
- **Domain-agnostic** — construct names, action vocabularies, and vignettes are caller-provided
- **Batch comparison** — `CVRunner.compare_groups()` generates metrics x treatments tables across seeds/ablations

L3 (psychometric probing) uses standardized vignette scenarios with domain-specific archetypes. Callers provide vignettes and archetypes in their project directory; the statistical engine (ICC, Cronbach's alpha, Fleiss' kappa, convergent/discriminant validity) is generic.

### Three-Stage Calibration Protocol

Beyond post-hoc validation, the framework provides a structured **calibration protocol** that iterates from fast pilot runs to full-scale validation:

| Stage | Purpose | Scale | Key Output |
| :---- | :------ | :---- | :--------- |
| **Pilot** | Rapid benchmark comparison, identify out-of-range metrics | 25 agents, 3 years | `AdjustmentRecommendation` list (which metrics deviate, which direction) |
| **Sensitivity** | Verify LLM responds correctly to persona/prompt changes | LLM probing only | Directional pass rate (chi-squared, Mann-Whitney U) |
| **Full** | Multi-seed population-level validation | 400 agents, 13 years, 10 seeds | Aggregate EPI, CACR, ICC across seeds |

Core modules:

| Module | Purpose |
| :----- | :------ |
| `BenchmarkRegistry` | Domain-agnostic empirical benchmark definition, comparison, and weighted EPI computation |
| `DirectionalValidator` | Generic sensitivity testing -- directional probes (stimulus low/high) and persona swap tests with statistical significance |
| `CalibrationProtocol` | Three-stage orchestrator with callback-based architecture -- callers provide `simulate_fn`, `compute_metrics_fn`, `invoke_llm_fn` |

The protocol is fully config-driven via a single `calibration.yaml`. No changes to `broker/` code are needed for new domains -- callers supply benchmarks, directional tests, and metric computation functions.

**[Full C&V documentation, API examples, and metric thresholds](broker/validators/calibration/README.md)**

---

## Experimental Validation & Benchmarks

The framework has been validated through the **WRR Benchmark** (_Water Resources Research_), a three-group ablation study that isolates the contribution of each cognitive component:

| Group                  | Memory Engine | Governance | Purpose                                                   |
| :--------------------- | :------------ | :--------- | :-------------------------------------------------------- |
| **A (Baseline)**       | None          | Disabled   | Raw LLM output — no memory, no validation                 |
| **B (Governed)**       | Window        | Strict     | Governance effect isolation — memory-less but rational    |
| **C (Full Cognitive)** | HumanCentric  | Strict     | Complete system with emotional salience and trauma recall |

### Single-Agent vs. Multi-Agent Comparison

| Dimension     | Single-Agent    | Multi-Agent                                  |
| :------------ | :-------------- | :------------------------------------------- |
| State         | Individual only | Individual + Social + Shared + Institutional |
| Agent types   | 1 (household)   | N (household, government, insurance)         |
| Observability | Self only       | Self + neighbors + community statistics      |
| Context       | Direct          | Context Builder + Social Module              |
| Use case      | Baseline ABM    | Policy simulation with social dynamics       |

### Validated Models (v3.4)

| Model Family     | Variants            | Use Case                             |
| :--------------- | :------------------ | :----------------------------------- |
| **Google Gemma** | 3-4B, 3-12B, 3-27B  | Primary benchmark models (JOH Paper) |
| **Mistral**      | Ministral 3B/8B/14B | Cross-family generalization study    |
| **Meta Llama**   | 3.2-3B-Instruct     | Lightweight edge agents              |
| **DeepSeek**     | R1-Distill-Llama-8B | High-Reasoning (Chain-of-Thought) tasks |

### Flood Experiment Status (WRR Benchmark)

All experiments use v7 code (action-outcome feedback, configurable reflection, reasoning-first ordering).

| Model         | Group A (Ungoverned) | Group B (Governed+Window) | Group C (Governed+HumanCentric) |
| :------------ | :------------------: | :-----------------------: | :-----------------------------: |
| Gemma 3-4B    |          ✓           |            ✓              |               ✓                 |
| Gemma 3-12B   |          ✓           |            ✓              |               ✓                 |
| Gemma 3-27B   |          ✓           |         Pending           |            Pending              |
| Ministral 3B  |          ✓           |            ✓              |               ✓                 |
| Ministral 8B  |          ✓           |            ✓              |               ✓                 |
| Ministral 14B |          ✓           |            ✓              |            Pending              |

**[Full experimental details](examples/single_agent/)**

---

## Practical Challenges & Lessons Learned

### 1. The Parsing Breakdown (Syntax vs. Semantics)

**Challenge**: Small language models (3B-4B parameters) frequently suffer from "Syntax Collapse" when prompts become dense. They may output invalid JSON, nested objects instead of flat keys, or unquoted strings.

**Insight**: We moved from strict JSON parsing to a **Multi-Layer Defensive Parsing** strategy: Enclosure Extraction -> JSON Repair (missing quotes/commas) -> Keyword Regex -> Last-Resort Digit Extraction.

### 2. The Governance Dead Zone

**Challenge**: When governance rules create a narrow "action funnel" (e.g., TP=H blocks "Do Nothing", CP=L blocks "Elevate" and "Relocate"), agents may have only one valid action remaining, removing meaningful choice.

**Insight**: We distinguish between **ERROR** rules (block the action and trigger retry) and **WARNING** rules (allow the action but record the observation in the audit trail). This preserves agent autonomy while maintaining scientific observability.

---

## Single-Agent vs Multi-Agent Compatibility (SA/MA 適配性)

The `SkillBrokerEngine` serves **both** SA and MA experiments. MA adds lifecycle hooks (`pre_year`, `post_step`, `post_year`), phased execution (`ExperimentBuilder.with_phase_order()`), and social context injection — all without modifying the core broker pipeline.

**Known MA limitations**: no cross-agent validation in broker (hooks only), no negotiation protocol (broadcast via `env` state), non-PMT agents require domain-specific validator configs.

See [Multi-Agent Architecture](docs/architecture/mas-five-layers.md) for the full SA/MA compatibility table, phased execution model, and communication protocol details.

---

## For Paper Contributors

### WRR Paper Workspace

| Paper | Directory | Config |
| :---- | :-------- | :----- |
| Paper 2 (Irrigation) | `examples/irrigation_abm/` | `config/agent_types.yaml` |
| Paper 3 (Flood MA) | `examples/multi_agent/flood/` | `config/ma_agent_types.yaml` |

### Zotero Integration

The project uses a shared Zotero library for reference management. Contact the PI for group access credentials. Citation keys follow `AuthorYear` format (e.g., `Rogers1983`, `Bubeck2012`).

See `docs/guides/zotero_guide.md` for setup instructions and collection structure.

---

## References (APA)

The architecture is grounded in and contributes to the following literature:

### Behavioral Theory

1. **Rogers, R. W.** (1983). Cognitive and physiological processes in fear appeals and attitude change: A revised theory of protection motivation. _Social Psychophysiology_.
2. **Trope, Y., & Liberman, N.** (2010). Construal-level theory of psychological distance. _Psychological Review_, 117(2), 440.
3. **Tversky, A., & Kahneman, D.** (1973). Availability: A heuristic for judging frequency and probability. _Cognitive Psychology_, 5(2), 207-232.
4. **Ebbinghaus, H.** (1885). _Memory: A Contribution to Experimental Psychology_. (The Forgetting Curve basis).

### Flood Risk & Adaptation

5. **Siegrist, M., & Gutscher, H.** (2008). Natural hazards and motivation for self-protection: Memory matters. _Risk Analysis_, 28(3), 771-778.
6. **Bubeck, P., Botzen, W. J. W., & Aerts, J. C. J. H.** (2012). A review of risk perceptions and other factors that influence flood mitigation behavior. _Risk Analysis_, 32(9), 1481-1495.
7. **Hung, C.-L. J., & Yang, Y. C. E.** (2021). Assessing adaptive irrigation impacts on water scarcity in nonstationary environments. _Water Resources Research_, 57(7), e2020WR028946.

### LLM Agents & Architecture

8. **Park, J. S., ... & Bernstein, M. S.** (2023). Generative Agents: Interactive Simulacra of Human Behavior. _ACM CHI_.

---

## License

MIT
