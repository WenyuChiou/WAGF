# Governed Broker Framework

<div align="center">

**A Governance Middleware for LLM-Driven Hydro-Social Agent-Based Models**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ollama](https://img.shields.io/badge/Ollama-Local_Inference-000000?style=flat&logo=ollama&logoColor=white)](https://ollama.com/)

[**English**](README.md) | [**中文**](README_zh.md)

</div>

## Mission Statement

> _"Turning LLM Storytellers into Rational Actors for Hydro-Social Agent-Based Models."_

The **Governed Broker Framework** addresses the fundamental **Logic-Action Gap** in Large Language Model (LLM) agents: while LLMs produce fluent natural-language reasoning, they exhibit stochastic instability, hallucinations, and memory erosion across long-horizon simulations — problems that undermine the scientific validity of LLM-driven agent-based models (ABMs).

This framework provides an architectural **Governance Layer** that validates agent reasoning against physical constraints and behavioral theories (e.g., Protection Motivation Theory) in real time. It is designed for **flood risk adaptation research** and other hydro-social modeling contexts where reproducibility, auditability, and long-horizon consistency are essential.

**Target domains**: nonstationary flood risk adaptation, irrigation water management, household adaptation behavior, community resilience, water resource policy evaluation.

**Validated case studies**:
- **Flood Household Adaptation**: 100 PMT-based agents, 10-year simulation with Gemma 3 (4B/12B/27B)
- **Irrigation Water Management**: 78 CRSS agents from the Upper Colorado River Basin

---

## Quick Start

### 1. Install

```bash
pip install -r requirements.txt
```

### 2. Run a Governed Flood Simulation

Launch a 10-agent flood adaptation demo with governance and human-centric memory (requires [Ollama](https://ollama.com/)):

```bash
python examples/governed_flood/run_experiment.py --model gemma3:4b --years 3 --agents 10
```

### 3. Run the Full Benchmark (JOH Paper)

Replicate the three-group ablation study (100 agents, 10 years):

```bash
python examples/single_agent/run_flood.py --model gemma3:4b --years 10 --agents 100 \
    --memory-engine humancentric --governance-mode strict --use-priority-schema
```

### 4. Explore More

| Example            | Complexity   | Description                                          | Link                           |
| :----------------- | :----------- | :--------------------------------------------------- | :----------------------------- |
| **Governed Flood** | Beginner     | Standalone Group C demo with full governance         | [Go](examples/governed_flood/) |
| **Single Agent**   | Intermediate | JOH Benchmark: Groups A/B/C ablation study           | [Go](examples/single_agent/)   |
| **Multi-Agent**    | Advanced     | Social dynamics, insurance market, government policy | [Go](examples/multi_agent/)    |
| **Finance**        | Extension    | Cross-domain demonstration (portfolio decisions)     | [Go](examples/finance/)        |

---

## Module Directory (Documentation Hub)

The framework is organized into five conceptual chapters, each with bilingual documentation:

- **Chapter 0 — Theoretical Basis**: [Overview](docs/modules/00_theoretical_basis_overview.md) | [中文](docs/modules/00_theoretical_basis_overview_zh.md)
- **Chapter 1 — Memory & Reflection**: [Memory & Surprise Engine](docs/modules/memory_components.md) | [Reflection Engine](docs/modules/reflection_engine.md)
- **Chapter 2 — Governance Core**: [Governance Logic & Validators](docs/modules/governance_core.md)
- **Chapter 3 — Context & Perception**: [Context Builder](docs/modules/context_system.md) | [Simulation Engine](docs/modules/simulation_engine.md)
- **Chapter 4 — Skill Registry**: [Action Ontology](docs/modules/skill_registry.md)
- **Experiments**: [Benchmarks & Examples](examples/README.md)

---

## Documentation & Guides

### Integration Guides (`docs/guides/`)

- **[Experiment Design Guide](docs/guides/experiment_design_guide.md)**: Recipe for building new experiments.
- **[Agent Assembly Guide](docs/guides/agent_assembly.md)**: How to stack "Cognitive Blocks" (Level 1-3).
- **[Customization Guide](docs/guides/customization_guide.md)**: Adding new skills, validators, and audit fields.

### Architecture Specs (`docs/architecture/`)

- **[High-Level Architecture](docs/architecture/architecture.md)**: System diagrams and data flow.
- **[Skill Architecture](docs/architecture/skill_architecture.md)**: Deep dive into the Action/Skill ontology.
- **[MAS Five-Layer Mapping](docs/architecture/mas-five-layers.md)**: Multi-agent system architecture (AgentTorch alignment).

### Multi-Agent Ecosystem (`docs/multi_agent_specs/`)

- **[Government Agents](docs/multi_agent_specs/government_agent_spec.md)**: Subsidies, buyouts & policy logic.
- **[Insurance Market](docs/multi_agent_specs/insurance_agent_spec.md)**: Premium calculation & risk models.
- **[Institutional Behavior](docs/multi_agent_specs/institutional_agent_behavior_spec.md)**: Interaction protocols.

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

---

## Unified Architecture (v3.3)

The framework utilizes a layered middleware approach that unifies single-agent isolated reasoning with multi-agent social simulations.

![Unified Architecture v3.3](docs/architecture.png)

### Combinatorial Intelligence ("Stacking Blocks")

The framework implements a **Stacking Blocks** architecture. You can build agents of varying cognitive complexity by stacking different modules onto the base Execution Engine:

| Stack Level   | Cognitive Block      | Function          | Effect                                                                                                     |
| :------------ | :------------------- | :---------------- | :--------------------------------------------------------------------------------------------------------- |
| **Base**      | **Execution Engine** | _The Body_        | Can execute actions but has no memory or rationality.                                                      |
| **+ Level 1** | **Context Lens**     | _The Eyes_        | Adds bounded perception (Window Memory). Prevents context overflow.                                        |
| **+ Level 2** | **Memory Engine**    | _The Hippocampus_ | Adds **Universal Cognitive Engine (v3)**. Includes Surprise-driven System 1/2 switching and trauma recall. |
| **+ Level 3** | **Skill Broker**     | _The Superego_    | Adds **Governance**. Enforces "Thinking Rules" to ensure decisions match beliefs (Rationality).            |

> **Why this matters for research**: This design enables controlled ablation studies. Run a Level 1 Agent (Group A — baseline) vs. Level 3 Agent (Group C — full cognitive) to isolate exactly _which_ cognitive component resolves a specific behavioral bias.

**[Learn how to assemble custom agents](docs/guides/agent_assembly.md)**

### Framework Evolution

![Framework Evolution](docs/memory_evolution_v1_v2_v3.png)

The memory and governance architecture has evolved through three phases:

- **v1 (Legacy)**: [Availability Heuristic] — Monolithic scripts with basic Window Memory. (Group A/B Baseline).
- **v2 (Weighted)**: [Context-Dependent Memory] — Modular `SkillBrokerEngine` with **Weighted Retrieval** ($S = W_{rec}R + W_{imp}I + W_{ctx}C$).
- **v3 (Current)**: [Dual-Process & Active Inference] — **Universal Cognitive Architecture (The Surprise Engine)**.
  - **Dynamic Switching**: Flips between System 1 (Routine) and System 2 (Rational Focus) based on Prediction Error ($PE$).
  - **State-Mind Coupling**: Expectation ($E$) and Reality ($R$) drive the arousal loop.
  - **Explainable Audit**: Provides a full logic trace of "Why the agent remembered/selected this action."

**[Deep Dive: Memory Priority & Retrieval Math](docs/modules/memory_components.md)**

### Provider Layer & Adapter

| Component          | File               | Description                                                                                         |
| :----------------- | :----------------- | :-------------------------------------------------------------------------------------------------- |
| **UnifiedAdapter** | `model_adapter.py` | Smart parsing: handles model-specific quirks (e.g., DeepSeek `<think>` tags, Llama JSON formatting) |
| **LLM Utils**      | `llm_utils.py`     | Centralized LLM calls with robust error handling and verbosity control                              |
| **OllamaProvider** | `ollama.py`        | Default local inference provider                                                                    |

### Validator Layer (Governance Rule Engine)

> **Architecture Overview / 架構概覽**
>
> The validator layer is the core governance mechanism of the framework. Every skill proposal
> passes through a pipeline of five category validators before execution. Each validator
> produces `ValidationResult` objects with two severity levels: **ERROR** (blocks the action
> and triggers a retry loop, max 3 attempts) or **WARNING** (logs the observation but
> preserves agent autonomy).
>
> 驗證層是框架的核心治理機制。每個技能提案在執行前都會通過五類驗證器組成的流水線。
> 每個驗證器產生 `ValidationResult` 物件，包含兩個嚴重級別：**ERROR**（阻止操作並觸發
> 重試循環，最多 3 次）或 **WARNING**（僅記錄觀測但保留智能體自主性）。

```
broker/validators/governance/
│
├── base_validator.py            # Abstract base: YAML rules + BuiltinCheck injection
│                                  (抽象基類：YAML 規則 + 領域檢查注入)
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
│   _format_rule_message()             # {context.TP_LABEL} template interpolation
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

#### Design Philosophy (設計哲學)

| Principle | Description | Rationale |
| :--- | :--- | :--- |
| **ERROR vs WARNING** | ERROR (`valid=False`) triggers retry loop (max 3). WARNING (`valid=True`) logs but does not block. | Prevents "Governance Dead Zone" — preserves agent autonomy while maintaining observability. 防止「治理死區」——保留智能體自主性並維持可觀測性。 |
| **Insurance Renewal Exclusion** | `buy_insurance` when already insured is NOT flagged as hallucination. | Insurance expires annually (`has_insurance` reset each year). Unlike elevation/relocation (irreversible), renewal is rational behavior. 保險每年過期（`has_insurance` 每年重置），續保是理性行為。 |
| **Domain-Agnostic Core** | `BaseValidator` + `BuiltinCheck` pattern. Domain checks are pluggable functions: `(skill_name, rules, context) -> List[ValidationResult]`. | YAML-driven condition engine is fully generic. Domain-specific logic is injected, not hardcoded. YAML 驅動的條件引擎完全通用，領域邏輯通過注入而非硬編碼實現。 |
| **Dual Evaluation Path** | 1) YAML-driven rules filtered by `self.category`; 2) Injected `_builtin_checks` (hardcoded domain logic). | YAML rules support rapid prototyping; built-in checks provide compile-time safety for critical invariants. |
| **Template Interpolation** | Rule messages support `{context.TP_LABEL}`, `{rule.id}` via `RetryMessageFormatter`. | Retry prompts contain the exact violation reason, enabling the LLM to self-correct. |

#### Validator Category Details (各類驗證器詳解)

**1. PhysicalValidator** — State Preconditions (物理驗證器 — 狀態前置條件)

Guards against actions that contradict irreversible simulation state. These represent the most unambiguous hallucination type: the agent proposes an action that is physically impossible given the current world state.

| Check | Trigger | Level | Hallucination Type |
| :--- | :--- | :--- | :--- |
| `already_elevated` | `elevate_house` when `state.elevated=True` | ERROR | Physical |
| `already_relocated` | Any property action when `state.relocated=True` | ERROR | Physical |
| `renter_restriction` | `elevate_house` or `buyout` when `state.tenure="renter"` | ERROR | Physical |

**2. ThinkingValidator** — Construct-Action Consistency (思維驗證器 — 構念-行為一致性)

Enforces coherence between the agent's self-reported psychological appraisals and the action it proposes. Supports three psychological frameworks (PMT, Utility, Financial) via the `framework` constructor parameter. The multi-condition YAML engine (`_validate_yaml_rules`) uses AND-logic across conditions and is fully domain-agnostic.

| Rule (PMT) | Condition | Blocked Skill | Level |
| :--- | :--- | :--- | :--- |
| `high_tp_cp` | TP in {H, VH} AND CP in {H, VH} | `do_nothing` | ERROR |
| `extreme_threat` | TP = VH | `do_nothing` | ERROR |
| `low_tp_extreme` | TP in {VL, L} | `relocate`, `elevate_house` | ERROR |

**3. PersonalValidator** — Financial & Cognitive Constraints (個人驗證器 — 財務與認知約束)

Validates that the agent has the economic capacity to execute a proposed action. Prevents the LLM from ignoring budget constraints entirely.

| Check | Trigger | Level |
| :--- | :--- | :--- |
| `elevation_affordability` | `elevate_house` when `savings < elevation_cost * (1 - subsidy_rate)` | ERROR |

**4. SocialValidator** — Neighbor Influence Observation (社會驗證器 — 鄰居影響觀測)

Social rules are **WARNING only** by design. They log social pressure signals for the audit trail but never block decisions. This reflects the theoretical position that social influence is an input to decision-making, not a constraint on it (社會影響是決策輸入而非約束).

| Check | Trigger | Level |
| :--- | :--- | :--- |
| `majority_deviation` | `do_nothing` when >50% neighbors have elevated | WARNING |

**5. SemanticGroundingValidator** — Reasoning vs Ground Truth (語義接地驗證器 — 推理文本 vs 事實)

Detects hallucinations where the agent's free-text reasoning contradicts observable simulation state. This is the most nuanced validator category, as it performs NLP-level pattern matching against structured ground truth.

| Check | What It Detects | Level |
| :--- | :--- | :--- |
| `social_proof` | Agent cites "neighbors" when context shows 0 neighbors (hallucinated consensus) | ERROR |
| `temporal_grounding` | Agent references "last year's flood" when no flood occurred | WARNING |
| `state_consistency` | Agent claims "I'm insured" when `has_insurance=False` | WARNING |

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
- **Solution**: The **SkillBrokerEngine** implements a **Recursive Feedback Loop**:
  1. **Detection**: Validators scan the parsed response. If `TP=VH` but `Action=Do Nothing`, an `InterventionReport` is generated.
  2. **Injection**: The framework extracts the specific violation and injects it into a **Retry Prompt**.
  3. **Instruction**: The LLM is told: _"Your previous response was rejected due to logical inconsistency. Here is why: [Violation]. Please reconsider."_
  4. **Trace**: This entire exchange between the Broker and the LLM is captured in the `AuditWriter` for full transparency.

---

## Memory Architecture

![Human-Centric Memory System](docs/human_centric_memory_diagram.png)

The **Human-Centric Memory Engine** (v3.3) solves the "Goldfish Effect" by prioritizing memories based on **Emotional Salience** rather than just recency. It includes a **Reflection Engine** that consolidates yearly experiences into long-term insights.

### Key Features

1. **Priority-Driven Retrieval**: The Context Builder dynamically injects memories based on the retrieval score $S = (W_{rec} \cdot S_{rec}) + (W_{imp} \cdot S_{imp}) + (W_{ctx} \cdot S_{ctx})$. This ensures that even distant trauma (High Importance) or situationally-relevant facts (High Context) are pushed to the LLM's working memory.
2. **Reflection Loop**: Yearly consolidation of events into generalized "Insights" (assigned maximum weight $I = 10.0$ to resist decay).
3. **Bounded Context**: Filters thousands of logs into a concise, token-efficient prompt, prioritizing accuracy over volume.

### Tiered Memory Roadmap (v4 Target)

| Tier  | Component             | Function (Theory)                                                                       |
| :---- | :-------------------- | :-------------------------------------------------------------------------------------- |
| **1** | **Working Memory**    | **Sensory Buffer**. Immediate context (last 5 years).                                   |
| **2** | **Episodic Summary**  | **Hippocampus**. Long-term storage of "Significant" events (Phase 1/2 logic).           |
| **3** | **Semantic Insights** | **Neocortex**. Abstracted "Rules" derived from reflection (e.g., "Insurance is vital"). |

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

### Runtime Validation Sequence (運行時驗證流水線)

When the `SkillBrokerEngine` receives a parsed `SkillProposal`, it executes the following ordered pipeline. The function `validate_all(skill_name, rules, context, domain=...)` orchestrates all five category validators.

```
SkillProposal  ─────────────────────────────────────────────────────────────►  Execute
     │                                                                          ▲
     │   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                   │
     ├──►│  Physical    │──►│  Thinking   │──►│  Personal   │───┐               │
     │   │ (state pre-  │   │ (construct- │   │ (financial  │   │               │
     │   │  conditions) │   │  action     │   │  capacity)  │   │               │
     │   └─────────────┘   │  coherence) │   └─────────────┘   │               │
     │                     └─────────────┘                     │               │
     │   ┌─────────────┐   ┌─────────────────┐                │               │
     └──►│  Social      │──►│  Semantic        │───────────────┘               │
         │ (neighbor    │   │  Grounding       │                               │
         │  influence)  │   │ (text vs truth)  │                               │
         └─────────────┘   └─────────────────┘                               │
                                    │                                          │
                                    ▼                                          │
                          Any ERROR? ──YES──► RetryLoop (max 3) ──► Re-parse ─┘
                              │
                             NO
                              │
                              ▼
                         Pass (execute skill)
```

### Hallucination Taxonomy (幻覺分類體系)

The framework defines four hallucination types, each detected by a different validator category. This taxonomy is used both at runtime (governance) and in post-hoc analysis (paper metrics).

| Type | Definition | Validator | Example |
| :--- | :--- | :--- | :--- |
| **Physical** | Action contradicts irreversible state | `PhysicalValidator` | Elevate an already-elevated house |
| **Thinking** | Construct-action inconsistency | `ThinkingValidator` | TP=VH threat appraisal, yet selects `do_nothing` |
| **Economic** | Operationally absurd resource decision | `PhysicalValidator` (irrigation) | Reduce demand below 10% utilisation floor |
| **Semantic** | Reasoning text contradicts ground truth | `SemanticGroundingValidator` | Cites "neighbors" when agent has 0 neighbors |

### Domain Validator Configurations (領域驗證器配置)

The `validate_all()` function accepts a `domain` parameter that controls which `BuiltinCheck` functions are injected into each validator. The YAML-driven condition engine always runs regardless of domain.

```python
# Flood domain (default)
validate_all(skill_name, rules, context, domain="flood")

# Irrigation domain
validate_all(skill_name, rules, context, domain="irrigation")

# YAML rules only (no hardcoded built-in checks)
validate_all(skill_name, rules, context, domain=None)
```

#### Flood Domain Validators (洪水領域驗證器)

| Category | Check ID | Trigger | Level |
| :--- | :--- | :--- | :--- |
| Physical | `already_elevated` | `elevate_house` when `elevated=True` | ERROR |
| Physical | `already_relocated` | Property action when `relocated=True` | ERROR |
| Physical | `renter_restriction` | `elevate_house`/`buyout` when `tenure=renter` | ERROR |
| Thinking | `high_tp_cp` | TP in {H,VH} + CP in {H,VH} + `do_nothing` | ERROR |
| Thinking | `extreme_threat` | TP=VH + `do_nothing` | ERROR |
| Thinking | `low_tp_extreme` | TP in {VL,L} + `relocate`/`elevate_house` | ERROR |
| Personal | `elevation_affordability` | `elevate_house` when `savings < cost` | ERROR |
| Social | `majority_deviation` | `do_nothing` when >50% neighbors elevated | WARNING |
| Semantic | `social_proof` | Reasoning cites neighbors; context shows 0 | ERROR |
| Semantic | `temporal_grounding` | Reasoning cites flood; no flood occurred | WARNING |
| Semantic | `state_consistency` | Reasoning claims insurance; `has_insurance=False` | WARNING |

#### Irrigation Domain Validators (灌溉領域驗證器)

Source: `examples/irrigation_abm/validators/irrigation_validators.py`

**Physical Checks (6 rules):**

| Check ID | Trigger | Level | Notes |
| :--- | :--- | :--- | :--- |
| `water_right_cap` | `increase_demand` when `at_allocation_cap=True` | ERROR | Enforces senior water right limit |
| `non_negative_diversion` | `decrease_demand` when `current_diversion=0` | ERROR | Floor constraint |
| `efficiency_already_adopted` | `adopt_efficiency` when `has_efficient_system=True` | ERROR | Irreversible (like elevation in flood) |
| `minimum_utilisation` | `decrease_demand`/`reduce_acreage` when utilisation <10% | ERROR | Economic hallucination type |
| `drought_severity` | `increase_demand` when `drought_index >= 0.8` | ERROR | Conservation mandate |
| `magnitude_cap` | `increase_demand` when proposed magnitude > cluster cap | ERROR | Cluster-specific bounds |

**Institutional Checks (2 rules):**

| Check ID | Trigger | Level | Notes |
| :--- | :--- | :--- | :--- |
| `curtailment_awareness` | `increase_demand` during active curtailment | WARNING | Informational only |
| `compact_allocation` | `increase_demand` when basin exceeds Compact share | WARNING | Colorado River Compact |

**Irrigation Thinking Rules (YAML-driven):**

| Rule | Condition | Blocked Skill |
| :--- | :--- | :--- |
| `high_threat_no_maintain` | WSA = VH threat | `maintain_demand` |
| `high_threat_high_cope_no_increase` | WSA = VH + ACA = H | `increase_demand` |
| `water_right_cap` | At allocation cap | `increase_demand` |
| `already_efficient` | Has efficient system | `adopt_efficiency` |

#### Domain Comparison Summary (領域對比)

| Dimension | Flood | Irrigation |
| :--- | :--- | :--- |
| **Behavioral Theory** | PMT (Protection Motivation Theory) | Dual Appraisal (WSA/ACA) |
| **Constructs** | TP (Threat), CP (Coping), SP, SC, PA | WSA (Water Stress), ACA (Adaptive Capacity) |
| **Irreversible Actions** | Elevation, Relocation | Efficiency Adoption |
| **Renewable Actions** | Insurance (annual expiry) | Demand adjustment (annual) |
| **Physical Checks** | 3 built-in checks | 6 built-in checks |
| **Social Checks** | 1 WARNING (majority deviation) | 2 WARNINGs (curtailment, compact) |
| **Semantic Checks** | 3 (social proof, temporal, state) | YAML-only (no built-in) |
| **Hallucination Types** | Physical, Thinking, Semantic | Physical, Thinking, Economic |

### Extending to a New Domain (擴展至新領域)

The validator architecture is designed for domain extensibility. To add validators for a new domain (e.g., groundwater management, drought response), follow this pattern:

**Step 1**: Define `BuiltinCheck` functions in a domain-specific file.

```python
# examples/groundwater_abm/validators/groundwater_validators.py
from broker.validators.governance.base_validator import BuiltinCheck

def well_depth_limit_check(skill_name, rules, context):
    """Block pumping increase if well exceeds depth limit."""
    if skill_name != "increase_pumping":
        return []
    if context.get("well_depth", 0) >= context.get("max_depth", 500):
        return [ValidationResult(
            valid=False,
            validator_name="GroundwaterPhysicalValidator",
            errors=["Well depth limit exceeded"],
            metadata={"rule_id": "well_depth_limit", "category": "physical"}
        )]
    return []

GROUNDWATER_PHYSICAL_CHECKS = [well_depth_limit_check]
```

**Step 2**: Inject checks when constructing validators.

```python
from broker.validators.governance import PhysicalValidator, ThinkingValidator

validators = [
    PhysicalValidator(builtin_checks=GROUNDWATER_PHYSICAL_CHECKS),
    ThinkingValidator(builtin_checks=[]),   # YAML rules only
]
```

**Step 3**: Or register the domain in `validate_all()` for framework-level support.

```python
# In broker/validators/governance/__init__.py
elif domain == "groundwater":
    validators = [
        PhysicalValidator(builtin_checks=GROUNDWATER_PHYSICAL_CHECKS),
        ThinkingValidator(builtin_checks=[]),
        # ...
    ]
```

> **Key pattern / 關鍵模式**: `builtin_checks=None` uses flood defaults (backward compatibility);
> `builtin_checks=[]` disables all built-in checks (YAML-only mode);
> `builtin_checks=[your_fn]` injects domain-specific logic.
>
> `builtin_checks=None` 使用洪水預設值（向後相容）；`builtin_checks=[]` 禁用所有內建檢查
> （純 YAML 模式）；`builtin_checks=[your_fn]` 注入領域特定邏輯。

---

## Configuration-Driven Extension (v3.3)

All domain-specific logic is centralized in YAML configuration files. New water sub-domains (e.g., groundwater management, drought response) can be added by defining skill registries, validators, and agent configurations — without modifying the core broker:

```yaml
# agent_types.yaml - Parsing & Memory Configuration
parsing:
  decision_keywords: ["decision", "choice", "action"]
  synonyms:
    tp: ["severity", "vulnerability", "threat", "risk"]
    cp: ["efficacy", "self_efficacy", "coping", "ability"]

memory_config:
  emotional_weights:
    critical: 1.0 # Flood damage, trauma
    major: 0.9 # Important life decisions
    positive: 0.8 # Successful adaptation
    routine: 0.1 # Daily noise

  source_weights:
    personal: 1.0 # Direct experience "I saw..."
    neighbor: 0.7 # "My neighbor did..."
    community: 0.5 # "The news said..."

  # Context Priority Weights
  priority_schema:
    flood_depth: 1.0 # Highest: physical reality
    savings: 0.8 # Financial reality
    risk_tolerance: 0.5 # Psychological factor
```

---

## Experimental Validation & Benchmarks

The framework has been validated through the **JOH Benchmark** (Journal of Hydrology), a three-group ablation study that isolates the contribution of each cognitive component:

| Group                  | Memory Engine           | Governance | Purpose                                                   |
| :--------------------- | :---------------------- | :--------- | :-------------------------------------------------------- |
| **A (Baseline)**       | None                    | Disabled   | Raw LLM output — no memory, no validation                 |
| **B (Governed)**       | Window                  | Strict     | Governance effect isolation — memory-less but rational    |
| **C (Full Cognitive)** | HumanCentric + Priority | Strict     | Complete system with emotional salience and trauma recall |

### Single-Agent vs. Multi-Agent Comparison

| Dimension     | Single-Agent    | Multi-Agent                                  |
| :------------ | :-------------- | :------------------------------------------- |
| State         | Individual only | Individual + Social + Shared + Institutional |
| Agent types   | 1 (household)   | N (household, government, insurance)         |
| Observability | Self only       | Self + neighbors + community statistics      |
| Context       | Direct          | Context Builder + Social Module              |
| Use case      | Baseline ABM    | Policy simulation with social dynamics       |

### Validated Models (v3.3)

| Model Family     | Variants            | Use Case                             |
| :--------------- | :------------------ | :----------------------------------- |
| **Google Gemma** | 3-4B, 3-12B, 3-27B  | Primary benchmark models (JOH Paper) |
| **Meta Llama**   | 3.2-3B-Instruct     | Lightweight edge agents              |
| **DeepSeek**     | R1-Distill-Llama-8B | High-Reasoning (CoT) tasks           |

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
