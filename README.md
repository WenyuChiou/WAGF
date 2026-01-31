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

### Validator Layer

Governance rules are organized into a 2x2 matrix:

| Dimension                          | **Strict (Block & Retry)**                                       | **Heuristic (Warn & Log)**                                        |
| :--------------------------------- | :--------------------------------------------------------------- | :---------------------------------------------------------------- |
| **Physical / Identity Rules**      | _Impossible actions_ (e.g., elevate an already-elevated house)   | _Suspicious states_ (e.g., wealthy agent choosing "Do Nothing")   |
| **Psychological / Thinking Rules** | _Logical fallacies_ (e.g., High threat + Low cost -> Do Nothing) | _Behavioral anomalies_ (e.g., extreme anxiety but delayed action) |

**Implementation**: Identity Rules check current state (from `StateManager`). Thinking Rules check internal consistency of LLM reasoning (from `SkillProposal`).

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

## Validation Pipeline

| Stage | Validator       | Check                                               |
| :---- | :-------------- | :-------------------------------------------------- |
| 1     | Admissibility   | Does the skill exist? Is the agent eligible?        |
| 2     | Feasibility     | Are preconditions met? (e.g., not already elevated) |
| 3     | Constraints     | One-time or annual limits?                          |
| 4     | Effect Safety   | Is the state change valid?                          |
| 5     | PMT Consistency | Does reasoning match the decision?                  |
| 6     | Uncertainty     | Is the response confident?                          |

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
