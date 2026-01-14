# Governed Broker Framework

**🌐 Language / 語言: [English](README.md) | [中文](README_zh.md)**

<div align="center">

**A governance middleware for LLM-driven Agent-Based Models**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

## Modular Middleware Architecture

The framework is designed as a **governance middleware** that sits between the Agent's decision-making model (LLM) and the simulation environment (ABM). Each component is decoupled, allowing for flexible experimentation with different models, validation rules, and environmental dynamics.

### The 4 Core Modules

| Module              | Role          | Description                                                                                          |
| :------------------ | :------------ | :--------------------------------------------------------------------------------------------------- |
| **Skill Registry**  | _The Charter_ | Defines _what_ an agent can do (actions), including costs, constraints, and physical consequences.   |
| **Skill Broker**    | _The Judge_   | The central governance engine. Enforces institutional and psychological coherence on LLM proposals.  |
| **Sim Engine**      | _The World_   | Executes validated actions and manages the physical state evolution (e.g., flood damage).            |
| **Context Builder** | _The Lens_    | Synthesizes a bounded view of reality (Personal Memory, Social Signals, Global State) for the agent. |

---

---

## 🛡️ Core Problems Statement

![Core Challenges & Framework Solutions](docs/challenges_solutions_v3.png)

| Challenge            | Problem Description                                | Framework Solution                                                                | Component           |
| :------------------- | :------------------------------------------------- | :-------------------------------------------------------------------------------- | :------------------ |
| **Hallucination**    | LLM generates invalid actions (e.g., "build wall") | **Strict Registry**: Only registered `skill_id`s are accepted.                    | `SkillRegistry`     |
| **Context Limit**    | Cannot dump entire history into prompt.            | **Salience Memory**: Retrieves only top-k relevant past events.                   | `MemoryEngine`      |
| **Inconsistency**    | Decisions contradict reasoning (Logical Drift).    | **Thinking Validators**: Checks logical coherence between `TP`/`CP` and `Choice`. | `SkillBrokerEngine` |
| **Opaque Decisions** | "Why did agent X do Y?" is lost.                   | **Structured Trace**: Logs Input, Reasoning, Validation, and Outcome.             | `AuditWriter`       |
| **Unsafe Mutation**  | LLM output breaks simulation state.                | **Sandboxed Execution**: Validated skills are executed by engine, not LLM.        | `SimulationEngine`  |

---

## Unified Architecture (v3.0)

The framework utilizes a layered middleware approach that unifies single-agent isolated reasoning with complex multi-agent simulations.

![Unified Architecture v3.0](docs/governed_broker_architecture_v3.png)

### Key Architectural Pillars:

1. **Context-Aware Perception**: Explicitly separates Environmental **State** from Historical **Memories**.
2. **One-Way Governance**: LLM proposals flow unidirectionally into a validation pipeline before system execution.
3. **Closed Feedback Loop**: Simulation outcomes are simultaneously committed to memory and environment state.
4. **Lifecycle Auditing**: The `AuditWriter` captures traces from proposal to execution for full reproducibility.

**Migration Note**:

- **v1 (Legacy)**: Monolithic scripts.
- **v2 (Stable)**: Modular `SkillBrokerEngine` + `providers`.
- **v3 (Latest)**: Unified Single/Multi-Agent Architecture + Professional Audit Trail. Use `run_unified_experiment.py`.
- **v3.1**: **Demographic Grounding & Statistical Validation**. Agents are grounded in real-world surveys.
- **v3.2 (Production)**: **Advanced Memory & Skill Retrieval**. Implements MemGPT-style Tiered Memory (Core/Episodic/Semantic) and RAG-based Skill Selection for large action spaces.

---

## 🔬 Scientific Research Questions (SQs)

The framework is designed to address three primary scientific questions regarding flood adaptation:

### SQ1: Cognitive vs. Stochastic Adaptation

**Question**: How does LLM-driven reasoning-based adaptation compare to probability-based adaptation in predicting long-term flood outcomes under repeated exposure?

- **Experimental Design**: Control (Traditional Probability ABM) vs. Treatment (LLM + PMT Reasoning).
- **Goal**: Evaluate if reasoning-based models better capture the "lock-in" or "threshold" effects of adaptation compared to stochastic models.

### SQ2: Social Network Influence & Tenure Gap

**Question**: How do social network effects (neighbor influence via gossip) accelerate or dampen the adaptation gap between renters and homeowners?

- **Experimental Design**: Comparative study of "Social Gossip Enabled" vs. "Gossip Disabled" in Multi-Agent scenarios.
- **Goal**: Understand how social capital (SC) modulates adaptation for different demographic segments.

### SQ3: Institutional Feedback & Financial Resilience

**Question**: How do institutional feedback loops (FEMA solvency vs. Blue Acres subsidies) interact to shape community-level adaptation and financial resilience?

- **Experimental Design**: 2x2 Matrix varying FEMA Initial Solvency (Low/High) and Blue Acres Subsidy Rate (Low/High).
- **Goal**: Map the policy sensitivity of the adaptation system to institutional health.

---

## 🔧 Configurable Module Parameters (v3.2)

All core modules expose configurable parameters following a **0-1 normalization standard** for psychological, behavioral, and importance weights.

### Memory Engine Parameters

| Parameter            | Type  | Range   | Default | Description                                         |
| -------------------- | ----- | ------- | ------- | --------------------------------------------------- |
| `window_size`        | int   | 1-10    | **3**   | Number of recent memories always included           |
| `top_k_significant`  | int   | 1-5     | **2**   | Number of high-importance historical events         |
| `consolidation_prob` | float | 0.0-1.0 | **0.7** | Probability of consolidating high-importance memory |
| `decay_rate`         | float | 0.0-1.0 | **0.1** | Exponential decay rate for time-based forgetting    |

**Emotional Weights (0-1)**:
| Category | Default | Description |
|----------|---------|-------------|
| `fear` | 1.0 | Flood damage, high threat perception |
| `regret` | 0.9 | Missed opportunities, should-have decisions |
| `relief` | 0.8 | Successful insurance claims, assistance received |
| `trust_shift` | 0.7 | Changes in trust towards institutions/neighbors |
| `observation` | 0.4 | Neutral social observation |
| `routine` | 0.1 | No notable event |

### Skill Retriever Parameters

| Parameter       | Type      | Range   | Default                           | Description                                         |
| --------------- | --------- | ------- | --------------------------------- | --------------------------------------------------- |
| `top_n`         | int       | 1-10    | **3**                             | Number of relevant skills to retrieve via RAG       |
| `min_score`     | float     | 0.0-1.0 | **0.05**                          | Minimum relevance score threshold                   |
| `global_skills` | List[str] | -       | `["do_nothing", "buy_insurance"]` | Skills always available regardless of RAG filtering |

**Context Source Weights (0-1)**:
| Source | Default | Description |
|--------|---------|-------------|
| `state` | 1.0 | Direct internal state keywords |
| `perception` | 1.2 | Immediate external signals (NOTE: can exceed 1.0 for emphasis) |
| `memory` | 0.8 | Historical context from episodic/semantic memory |

---

## 🧠 Advanced Memory & Skill Retrieval (v3.2) ✅

To handle long-term simulations (10+ years), v3.2 introduces a **Tiered Memory System** and **Dynamic Skill Retrieval (RAG)** to ensure agents remain consistent without exceeding LLM context limits.

### 1. Hierarchical (Tiered) Memory

Instead of a simple sliding window, memory is now categorized into three functional tiers:

- **CORE**: Fixed agent attributes (Income, Persona, Governance Profile).
- **HISTORIC (Semantic)**: Long-term condensed history of major events (e.g., past flood impacts).
- **RECENT (Episodic)**: High-resolution logs of the most recent interactions.

### 2. Context-Aware Skill Retrieval (RAG)

For complex simulations with many possible actions, the framework uses a **SkillRetriever** to inject only the most relevant actions into the prompt.

- **Adaptive Precision**: Reduces cognitive load on the LLM by filtering irrelevant skills based on the current situation (e.g., only retrieval relocation skills when threat is high).
- **Parity Mode**: Automatically disables for `WindowMemoryEngine` to allow for clean comparative research against legacy baselines.

---

## 📊 Scientific & Statistical Validation (v3.1) ✅

To bridge the gap between "Simulation" and "Science", the framework now includes built-in statistical validation tools to quantify behavioral shifts.

### 1. Chi-square Decision Analysis

We use **Chi-square tests of independence** to compare agent decision distributions across different models (Llama, Gemma, DeepSeek) and memory engines (Window vs Importance).

- **Objective**: Prove that governance and memory mechanisms create statistically significant behavioral changes ($p < 0.05$).
- **Success Metric**: Reduction in "Panic Relocations" (irrational adaptation) compared to un-governed legacy baselines.

### 2. Demographic Grounding Audit

Scores whether the LLM **actually uses** survey context (Identity, Experience) in its reasoning.

- **Score 1.0**: Strong Integration (Cites specific anchors like '2012', 'income').
- **Score 0.0**: Hallucination / Generic reasoning.

---

Run the new verified multi-agent example:

```bash
python examples/multi_agent/run_flood.py --verbose
```

---

## Core Components (V3 Skill-Governed Architecture) ✅

> **Note**: The following components are part of the **v3.0 Framework**.
> For legacy v1 MCP components, see `broker/legacy/`.

### Broker Layer (`broker/`)

| Component             | File                     | Purpose                                                           |
| --------------------- | ------------------------ | ----------------------------------------------------------------- |
| **SkillBrokerEngine** | `skill_broker_engine.py` | 🎯 Main orchestrator: validates skills → executes via simulation  |
| **SkillRegistry**     | `skill_registry.py`      | 📋 Skill definitions with eligibility rules & parameters          |
| **SkillProposal**     | `skill_types.py`         | 📦 Structured LLM output format (JSON)                            |
| **Schemas**           | `interfaces/schemas.py`  | ✅ Pydantic validation schemas for strict oversight               |
| **Plugin Registry**   | `plugins.py`             | 🔌 Central registry for custom extensions (Validators, Providers) |
| **ModelAdapter**      | `model_adapter.py`       | 🔄 Parses raw LLM text → SkillProposal                            |
| **ContextBuilder**    | `context_builder.py`     | 👁️ Builds bounded context for agents                              |
| **Memory**            | `memory.py`              | 🧠 Working + Episodic memory with consolidation                   |
| **AuditWriter**       | `audit_writer.py`        | 📊 Complete audit trail for reproducibility                       |

### Audit & Transparency (`broker/components/audit_writer.py`)

The `AuditWriter` provides a "Glass Box" view into the simulation, exporting high-resolution CSVs for every decision.

| Column             | Description                                                            |
| :----------------- | :--------------------------------------------------------------------- |
| **step_id**        | Unique identifier for the simulation step/year.                        |
| **agent_id**       | The specific agent identifier (e.g., `Agent_1`).                       |
| **proposed_skill** | The raw action proposed by the LLM before validation.                  |
| **final_skill**    | The actual action executed (may differ if proposal was rejected).      |
| **status**         | Result of the action (SUCCESS, FAILED, or BLOCKED).                    |
| **validated**      | Boolean flag indicating if the decision passed all governance checks.  |
| **failed_rules**   | Pipe-separated IDs of rules that were violated (e.g., `TP_COHERENCE`). |
| **reason_tp / cp** | Extracted psychological appraisal (Threat/Coping Perception).          |
| **demo_score**     | Demographic Grounding Score (0.0 to 1.0) measuring survey usage.       |
| **llm_retries**    | Number of LLM-level retries due to parsing or empty output.            |

---

## 🏗️ Technical Architecture Details

### 1. State Layer: Multi-Level Ownership

Managed by `simulation/state_manager.py`, the state is partitioned to ensure strict permissions:

- **Individual**: Private variables unique to an agent (e.g., `elevated=True`, `has_insurance=False`).
- **Social**: Observable behavioral signals from neighbors (e.g., `neighbor_decisions`).
- **Shared**: Global environmental variables visible to all (e.g., `flood_occurrence`).
- **Institutional**: Policy-level variables controlled by specific entities (e.g., `tax_rate`, `subsidy`).

### 2. Context Builder: Bounded Perception

Managed by `broker/components/context_builder.py`, this module generates the "World View" for the agent:

- **Salience Filtering**: Instead of a full history, it uses weighted importance to retrieve relevant memories.
- **Demographic Anchoring**: Automatically injects fixed survey traits (Income, Generation) into the persona.
- **Adaptive Precision**: Converts raw state numbers (e.g., `0.85 wealth`) into semantic labels (e.g., `High Wealth`) for better LLM reasoning.

### 3. Simulation Engine: Sequential World Evolution

Managed by `simulation/engine.py`, the engine orchestrates the time loop:

- **Step Process**: Year-end state update → Environment shock transition → Agent decision loop → Skill execution.
- **Sandboxed Execution**: Agents never modify state directly. They propose a `skill_id`, and the engine applies the physical consequences.

### Provider Layer & Adapters (`providers/` & `broker/utils/`)

| Component          | File               | Description                                                                                      |
| ------------------ | ------------------ | ------------------------------------------------------------------------------------------------ |
| **UnifiedAdapter** | `model_adapter.py` | 🧠 **Smart Parsing**: Handles model-specific quirks (e.g., DeepSeek `<think>` tags, Llama JSON). |
| **LLM Utils**      | `llm_utils.py`     | ⚡ Centralized invocation with robust error handling and verbosity control.                      |
| **OllamaProvider** | `ollama.py`        | Default local provider.                                                                          |

### Validator Layer (`validators/`)

We categorize governance rules into a 2x2 matrix:

---

## 🏗️ Universality & Standardization Guide (v3.0)

To ensure the framework remains domain-agnostic and maintains high comparability across different simulations, we follow a strict **0-1 Normalization Standard**.

### 1. The 0-1 Parameter Rule

All psychological, institutional, and physical state parameters within core modules should be normalized to a `[0.0, 1.0]` range.

| Category        | Recommended Parameters | Default / Range | Description                                           |
| :-------------- | :--------------------- | :-------------- | :---------------------------------------------------- |
| **Cognitive**   | `semantic_thresholds`  | `(0.3, 0.7)`    | Lower/Upper bounds for L/M/H labels in prompts.       |
| **Memory**      | `importance_weights`   | `0.1` to `1.0`  | Significance scoring for different memory categories. |
| **Validation**  | `risk_tolerance`       | `0.5`           | Baseline for psychological coherence checks.          |
| **Environment** | `shock_intensity`      | `0.0` to `1.0`  | Magnitude of external shocks / state changes.         |

### 2. Universality Checklist

When extending the framework to a new domain (e.g., Finance, Healthcare):

- [ ] **Decoupled Prompting**: Use `prompt_template` in `agent_types.yaml` instead of hardcoding text.
- [ ] **Generic Skills**: Register domain actions in `skill_registry.yaml` with unique `skill_id`s.
- [ ] **Reflective Discovery**: Ensure agent attributes used in prompts are publicly accessible.
- [ ] **Audit Compatibility**: Use `snake_case` for directory and model names to ensure log consistency.

### 3. Default Configuration Suggestions

- **Window Memory**: `window_size=3` (Balanced context vs simplicity).
- **Governance Profile**: `strict` for scientific research, `permissive` for creative exploration.
- **Retry Logic**: `max_retries=2` (3 total attempts) is optimal for recovery without excessive cost.

---

| Axis                         | **Strict (Block & Retry)**                                                         | **Heuristic (Warn & Log)**                                             |
| :--------------------------- | :--------------------------------------------------------------------------------- | :--------------------------------------------------------------------- |
| **Physical / Identity**      | _Impossible Actions_ <br> (e.g., "Already elevated", "Insuring while relocated")   | _Suspicious States_ <br> (e.g., "Wealthy agent doing nothing")         |
| **Psychological / Thinking** | _Logical Fallacies_ <br> (e.g., "High Threat + Low Cost $\rightarrow$ Do Nothing") | _Behavioral Anomalies_ <br> (e.g., "High Anxiety but delaying action") |

**Implementation:**

- **Identity Rules**: Checks against current state (from `StateManager`).
- **Thinking Rules**: Checks internal consistency of the LLM's reasoning (from `SkillProposal`).

### Initial Data & Context Linking

| Component             | Role       | Description                                                                                                                                                         |
| --------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **AttributeProvider** | _The Seed_ | Loads potential agent profiles from CSV (`agent_initial_profiles.csv`) or generates them stochastically.                                                            |
| **ContextBuilder**    | _The Link_ | dynamically pulls: <br> 1. **Static Traits** (from AttributeProvider) <br> 2. **Dynamic State** (from StateManager) <br> 3. **Social Signals** (from SocialNetwork) |

```mermaid
graph TD
    CSV["data/profiles.csv"] --> AP["AttributeProvider"]
    AP --"Initial Traits"--> SM["StateManager"]
    SM --"Current State"--> CB["ContextBuilder"]
    SN["SocialNetwork"] --"Neighbor Acts"--> CB
    CB --"Prompt"--> LLM
```

#### Validation Pipeline Details

Each SkillProposal passes through a **configurable validation pipeline**:

```
SkillProposal → [Validator 1] → [Validator 2] → ... → [Validator N] → Execution
                    ↓               ↓                    ↓
               If FAIL → Reject with reason, fallback to default skill
```

#### Built-in Validator Types

| Validator Type      | Purpose                                 | When to Use                     |
| ------------------- | --------------------------------------- | ------------------------------- |
| **Admissibility**   | Skill registered? Agent eligible?       | Always (core)                   |
| **Feasibility**     | Preconditions met?                      | When skills have prerequisites  |
| **Constraints**     | Institutional rules (once-only, limits) | When enforcing regulations      |
| **Effect Safety**   | State changes valid?                    | When protecting state integrity |
| **Domain-Specific** | Custom business logic                   | Define per use case             |

> **Key Point**: Validators are **modular and configurable**. Add/remove validators based on your domain requirements.

```yaml
# config/validators.yaml - Example Configuration
validators:
  - name: admissibility
    enabled: true # Core validator, always recommended
  - name: feasibility
    enabled: true # Enable if skills have preconditions
  - name: constraints
    enabled: true # Enable for institutional rules
  - name: custom_rule # Your domain-specific validator
    enabled: true
    config:
      threshold: 0.5
```

---

## State Management

### State Ownership (Multi-Agent)

```
┌─────────────────────────────────────────────────────────────┐
│  Agent 1          Agent 2          Agent 3                  │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐            │
│  │ INDIVIDUAL│     │ INDIVIDUAL│     │ INDIVIDUAL│           │
│  │ • memory  │     │ • memory  │     │ • memory  │           │
│  │ • elevated│     │ • elevated│     │ • elevated│           │
│  │ • insured │     │ • insured │     │ • insured │           │
│  └─────┬────┘     └─────┬────┘     └─────┬────┘            │
│        │                │                │                  │
│        └────────────────┼────────────────┘                  │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │               SHARED STATE                           │   │
│  │  • flood_occurred  • year  • community_stats         │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

| State Type        | Examples                              | Scope                | Read      | Write     |
| ----------------- | ------------------------------------- | -------------------- | --------- | --------- |
| **Individual**    | `memory`, `elevated`, `has_insurance` | Per-agent private    | Self only | Self only |
| **Social**        | `neighbor_actions`, `last_decisions`  | Observable neighbors | Neighbors | System    |
| **Shared**        | `flood_occurred`, `year`              | All agents           | All       | System    |
| **Institutional** | `subsidy_rate`, `policy_mode`         | All agents           | All       | Gov only  |

> **Key Point**: `memory` is **Individual** - each agent has their own memory, not shared.

```python
from simulation import StateManager

state = StateManager()
state.register_agent("agent_1", agent_type="homeowner")

# Individual: agent's private state (including memory)
state.update_individual("agent_1", {
    "memory": ["flood in year 2", "bought insurance in year 3"],
    "elevated": True
})

# Shared: environment visible to all
state.update_shared({"flood_occurred": True, "year": 5})
```

---

## Validation Pipeline

| Stage | Validator       | Check                                           |
| ----- | --------------- | ----------------------------------------------- |
| 1     | Admissibility   | Skill exists? Agent eligible for this skill?    |
| 2     | Feasibility     | Preconditions met? (e.g., not already elevated) |
| 3     | Constraints     | Once-only? Annual limit?                        |
| 4     | Effect Safety   | State changes valid?                            |
| 5     | PMT Consistency | Reasoning matches decision? (Warning or Error)  |
| 6     | Uncertainty     | Response confident?                             |

### Governance Taxonomy: Major Pillars vs. Minor Nuances

To maintain a balance between logical consistency and agent autonomy, we categorize governance rules into two tiers:

| Category          | Mapping     | Logic                                                                                                            | Example                                                                  |
| :---------------- | :---------- | :--------------------------------------------------------------------------------------------------------------- | :----------------------------------------------------------------------- |
| **Major Pillars** | **ERROR**   | **Foundational PMT principles.** Violation creates systematic bias or non-physical behavior.                     | High Threat + Inaction; Low Threat + Drastic Adaptation (Relocation/HE). |
| **Minor Nuances** | **WARNING** | **Behavioral diversity.** Suspicious or sub-optimal choices that are still within the realm of "human" variance. | Medium Threat + Inaction; High Coping + Delayed response.                |

Currently, all core PMT gates (Threat & Coping alignment) are set to **ERROR** to establish a baseline of "Rational Adaptation."

---

## 🧩 Prompt & Parsing Guidelines

To ensure the Skill Broker can correctly interpret LLM decisions, your prompt templates (e.g., in `ma_agent_types.yaml`) must follow a strict logical contract.

### 1. Expected Output Format

The `UnifiedAdapter` is designed for modularity; while it can capture any appraisal logic, it expects a structured response format to enable governance filters. We use **Threat/Coping Perception (TP/CP)** as standard examples:

- **Appraisal Blocks (Modular)**: (e.g., `TP Assessment`, `CP Assessment`) These are mapped to specific psychological constructs used by validators to check for logical consistency.
- **Final Decision (Required)**: (e.g., `Final Decision: [number]`) The core action identifier that the framework maps to a registered skill in the `SkillRegistry`.
- **Reasoning**: (e.g., `Reasoning: [text]`) Captured as metadata for detailed audit logs and behavioral analysis.

### 2. Common Parsing Failures

- **Missing Labels**: If the model omits `Final Decision:`, the parser falls back to a default action (usually `do_nothing`).
- **Mixed Formats**: Large reasoning models (like DeepSeek-R1) may include `<think>` blocks. The framework automatically strips these before parsing.
- **Ambiguous Choices**: We recommend using numbered lists (1, 2, 3) for actions to minimize ambiguity in smaller models (e.g., Llama 3.2 3B).

### 3. Debugging & Robustness

- **Log Prompts**: Use the `--verbose` flag to see the exact prompt sent to the LLM and its raw competitive output.
- **Parse Warnings**: Review the generated governance CSVs for `parsing_warnings` to identify systematic template errors.
- **Fail-Safe Mechanism**: The `SafeFormatter` handles missing demographic fields for institutional agents (e.g., `{income}`) without crashing the simulation.

---

## Multi-Agent Configuration

```yaml
# config/agent_types.yaml
agent_types:
  homeowner:
    skills: [buy_insurance, elevate_house, relocate, do_nothing]
    observable: [neighbors, community]

  government:
    skills: [set_subsidy, change_policy]
    can_modify: [institutional]
```

---

## Framework Comparison

| Dimension   | Single-Agent    | Multi-Agent                                  |
| ----------- | --------------- | -------------------------------------------- |
| State       | Individual only | Individual + Social + Shared + Institutional |
| Agent Types | 1 type          | N types (Resident, Gov, Insurance)           |
| Observable  | Self only       | Self + Neighbors + Community Stats           |
| Context     | Direct          | Via Context Builder + Social Module          |
| Use Case    | Basic ABM       | Policy simulation with social dynamics       |

---

## Extensibility

The framework is designed for extensibility to support:

### 1. Disaster Models Integration

Extend `SharedState` to include disaster model outputs:

```python
@dataclass
class DisasterSharedState(SharedState):
    # From disaster model
    flood_probability: float = 0.0
    flood_severity: float = 0.0
    sea_level_rise: float = 0.0

    # From climate model
    precipitation_forecast: float = 0.0
    storm_surge_risk: float = 0.0
```

### 2. Survey Data for Agent Demographics

Load real-world survey data as agent attributes:

```python
@dataclass
class SurveyFloodAgent(IndividualState):
    # Standard attributes
    elevated: bool = False
    has_insurance: bool = False

    # PMT attributes (from survey)
    trust_in_insurance: float = 0.3
    trust_in_neighbors: float = 0.4

    # Demographic attributes (from survey)
    age: int = 40
    income: str = "middle"           # low/middle/high
    education: str = "bachelor"
    household_size: int = 3
    homeownership: str = "owner"     # owner/renter
    years_in_community: int = 10
```

### 3. CSV Auto-Loading

Place `agent_initial_profiles.csv` in framework root:

```csv
id,elevated,has_insurance,trust_in_insurance,age,income,education
Agent_1,False,False,0.35,45,high,master
Agent_2,False,True,0.52,32,middle,bachelor
```

The framework automatically loads survey data if CSV exists.

### 4. Custom Context with Demographics

```python
class SurveyContextBuilder(ContextBuilder):
    def build(self, agent_id: str) -> Dict:
        return {
            # Standard context...
            "age": agent.age,
            "income": agent.income,
            "education": agent.education,
            # Include in LLM prompt for personalized decisions
        }
```

---

## Documentation

- [Architecture Details](docs/skill_architecture.md)
- [Customization Guide](docs/customization_guide.md)
- [Experiment Design](docs/experiment_design_guide.md)

---

## 🔮 Future Roadmap (v3.3+)

Building upon the v3.2 foundation, we are moving towards:

- **Parallel Execution Mode**: Implementing `MultiprocessingBroker` for large-scale simulation efficiency.
- **Multi-Modal Sensing**: Support for vision-based environmental perception (e.g., agents "seeing" flood maps).
- **Advanced Agent Councils**: Expanding governance to multi-agent peer-review committees.
- **Dynamic Semantic Embedding**: Using Vector DBs (ChromaDB) for high-precision skill retrieval.

## License

MIT
