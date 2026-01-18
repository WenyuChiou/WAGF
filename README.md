# 🏛️ Governed Broker Framework

<div align="center">

**A Governance Middleware for Rational & Reproducible Agent-Based Models**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ollama](https://img.shields.io/badge/Ollama-Local_Inference-000000?style=flat&logo=ollama&logoColor=white)](https://ollama.com/)

[**English**](README.md) | [**中文**](README_zh.md)

</div>

## 📖 Mission Statement

> _"Turning LLM Storytellers into Rational Actors."_

The **Governed Broker Framework** addresses the fundamental **"Logic-Action Gap"** in Large Language Model (LLM) agents. While LLMs are highly fluent, they often exhibit stochastic instability, hallucinations, and "memory erosion" in long-horizon simulations.

This framework provides an architectural **Governance Layer** that validates agent reasoning against _physical constraints_ and _psychological theories_ in real-time.

---

## 🚀 Quick Start

Get your first governed agent running in under 5 minutes.

### 1. Installation

```bash
pip install -r requirements.txt
```

### 2. Run a Simulation

Launch a 50-agent flood simulation with **Llama 3.2** (requires Ollama):

```bash
python examples/single_agent/run_flood.py --model llama3.2:3b --agents 50 --years 10
```

### 3. Explore More

| Experiment Type     | Description                                   | Link                                     |
| :------------------ | :-------------------------------------------- | :--------------------------------------- |
| **🏃 Single Agent** | Longitudinal studies, Adaptation Trajectories | [**Go to Examples**](examples/README.md) |

---

## 🗺️ Module Directory (Documentation Hub)

- **🧠 Components (Memory, Reflection)**: [docs/modules/memory_components.md](docs/modules/memory_components.md)
- **👁️ Context (Context System)**: [docs/modules/context_system.md](docs/modules/context_system.md)
- **⚖️ Governance (Core Logic)**: [docs/modules/governance_core.md](docs/modules/governance_core.md)
- **🌍 Simulation (Environment)**: [docs/modules/simulation_engine.md](docs/modules/simulation_engine.md)
- **🧪 Experiments**: [examples/README.md](examples/README.md)

---

## 📚 Documentation & Guides

### 🎓 Integration Guides (`docs/guides/`)

- **[Experiment Design Guide](docs/guides/experiment_design_guide.md)**: Recipe for building new experiments.
- **[Agent Assembly Guide](docs/guides/agent_assembly.md)**: How to stack "Cognitive Blocks" (Level 1-3).
- **[Customization Guide](docs/guides/customization_guide.md)**: Adding new skills, validators, and audit fields.

### 🏗️ Architecture Specs (`docs/architecture/`)

- **[High-Level Architecture](docs/architecture/architecture.md)**: System diagrams and flow.
- **[Skill Architecture](docs/architecture/skill_architecture.md)**: Deep dive into the Action/Skill ontology.

### 👥 Multi-Agent Ecosystem (`docs/multi_agent_specs/`)

- **[Government Agents](docs/multi_agent_specs/government_agent_spec.md)**: Subsidies, Buyouts & Policy Logic.
- **[Insurance Market](docs/multi_agent_specs/insurance_agent_spec.md)**: Premium calculation & Risk models.
- **[Institutional Behavior](docs/multi_agent_specs/institutional_agent_behavior_spec.md)**: Interaction protocols.

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

---

## Unified Architecture (v3.3)

The framework utilizes a layered middleware approach that unifies single-agent isolated reasoning with complex multi-agent simulations.

![Unified Architecture v3.3](docs/architecture.png)

### 🧩 Combinatorial Intelligence (The "Building Blocks")

This framework implements a **"Stacking Blocks"** architecture. You can build agents of varying complexity by stacking different cognitive modules onto the base Execution Engine—just like Legos.

| Stack Level   | Cognitive Block      | Function          | Effect                                                                                          |
| :------------ | :------------------- | :---------------- | :---------------------------------------------------------------------------------------------- |
| **Base**      | **Execution Engine** | _The Body_        | Can execute actions but has no memory or rationality.                                           |
| **+ Level 1** | **Context Lens**     | _The Eyes_        | Adds bounded perception (Window Memory). Prevents context overflow.                             |
| **+ Level 2** | **Memory Engine**    | _The Hippocampus_ | Adds **Tiered Memory**. Enables trauma recall (Availability Heuristic) and long-term learning.  |
| **+ Level 3** | **Skill Broker**     | _The Superego_    | Adds **Governance**. Enforces "Thinking Rules" to ensure decisions match beliefs (Rationality). |

> **Why this matters?** allows for controlled scientific experiments. You can run a "Level 1 Agent" (Baseline) vs. a "Level 3 Agent" (Full) to isolate exactly _which_ cognitive component solves a specific bias.

👉 **[Learn how to assemble custom agents](docs/agent_assembly.md)**

**Version History**:

- **v1 (Legacy)**: Monolithic scripts.
- **v2 (Stable)**: Modular `SkillBrokerEngine` + `providers`.
- **v3 (Latest)**: Unified Single/Multi-Agent Architecture + Professional Audit Trail.
- **v3.3 (JOH Edition)**: **Cognitive Middleware Implementation**.
  - **Coupling Interface**: Decoupled Input (JSON Signals) and Output (Action JSONs) for integration with HEC-RAS/SWMM.
  - **Human-Centric Memory**: Emotional encoding and stochastic consolidation.
  - **Explainable Governance**: Self-correction traces for transparent rationality.
- **v3.1**: **Demographic Grounding & Statistical Validation**. Agents are grounded in real-world surveys.
- **v3.2**: **Advanced Memory & Skill Retrieval**. Implements MemGPT-style Tiered Memory and RAG-based Skill Selection.
- **v3.3 (Production)**: **Domain-Agnostic Parsing & Human-Centric Memory**.
  - All domain-specific logic moved to `agent_types.yaml`.
  - All domain-specific logic moved to `agent_types.yaml`.
  - **Human-Centric Memory Engine**: Implements emotional encoding and passive retrieval.
- **v3.4 (Core Persistence)**: **Atomic State Management**.
  - **`apply_delta` Interface**: Standardized state updates across all agent types.
  - **Rigorous Parity**: Canonical synchronization between LLM Context and Agent Object.

---

## 🧠 Cognitive Architecture & Design Philosophy

The **Context Builder** is not just a data pipe; it is a designed **Cognitive Lens** that structures reality to mitigate LLM hallucinations and cognitive biases.

### 1. Structural Bias Mitigation

We explicitly engineer the prompt context to counteract known LLM limitations:

- **Scale Anchoring (The "Floating M" Problem)**: Small models (3B) lose track of symbol definitions in long contexts.
  - **Design**: We use **Inline Semantic Anchoring** (e.g., `TP=M(Medium)` instead of just `TP=M`) to enforce immediate understanding.
- **Option Primacy Bias**: LLMs statistically prefer the first option in a list.
  - **Design**: The `ContextBuilder` implements **Dynamic Option Shuffling**, ensuring that "Do Nothing" or "Buy Insurance" do not benefit from positional advantage.
- **The "Goldfish Effect" (Recency Bias)**: Models forget early instructions when overloaded with news.
  - **Design**: We use a **Tiered Context Hierarchy** (`Personal State -> Local Observation -> Global Memory`). This places survival-critical data (State) closest to the decision block, while compressing distant memories.

### 2. The Logic-Action Validator

- **Challenge**: Agents often hallucinate a reasoning path ("I feel unsafe") but fail to select the corresponding action ("Relocate").
- **Design**: The **Thinking Validator** component (in `Skill Broker`) performs a logical consistency check between `Threat Appraisal` and `Action Choice` before execution, triggering a retry if a mismatch is found.

---

## ⚠️ Practical Challenges & Lessons Learned

Developing LLM-based agents within a governed framework revealed several recurring challenges that influenced our architectural decisions.

### 1. The Parsing Breakdown (Syntax vs. Semantics)

**Challenge**: Small language models (e.g., Llama-3.2 3B, Gemma-3 4B) frequently suffer from "Syntax Collapse" when prompts become dense. They may output invalid JSON, nested objects instead of flat keys, or unquoted strings.
**Insight**: We moved from strict JSON parsing to a **Multi-Layer Defensive Parsing** strategy.

- **Example**: In our latest `UnifiedAdapter`, we sequence: **Enclosure Extraction** -> **JSON Repair** (for missing quotes/commas) -> **Keyword Regex** -> **Last-Resort Digit Extraction**.

### 2. The Logic-Action Validator & Explainable Feedback Loop

- **Challenge**: The "Logic-Action Gap." Small LLMs often output a reasoning string that classifies a threat as "Very High" (VH) but then select a "Do Nothing" action due to syntax confusion or reward bias.
- **Solution**: The **SkillBrokerEngine** implements a **Recursive Feedback Loop**.
  1. **Detection**: Validators scan the parsed response. If `TP=VH` but `Action=Buy Insurance` (which cost-effectively addresses risks) is ignored for `Do Nothing`, an `InterventionReport` is generated.
  2. **Injection**: Instead of a generic "Parse Error," the framework extracts the specific violation (e.g., _"Mismatch: High appraisal but passive action"_) and injects it into a **Retry Prompt**.
  3. **Instruction**: The LLM is told: _"Your previous response was rejected due to logical inconsistency. Here is why: [Violation]. Please reconsider your action based on your appraisal."_
  4. **Trace**: This entire "Argument" between the Broker and the LLM is captured in the `AuditWriter` for full transparency.

---

## 🧠 Memory Evolution: From Window to Tiered (v4 Roadmap)

The framework is transitioning from a simple sliding window memory to a **Tiered Cognitive Architecture**, solving the context-overload problem while maintaining historical grounding.

### Tier 1: Working Memory (Sliding Window)

- **Scope**: Last 5 years of detailed events.
- **Function**: Provides immediate context for the current decision step.
- **Cleanup**: Low-importance events are purged to maintain LLM token efficiency.

### Tier 2: Episodic Summary (Human-Centric Search)

- **Scope**: Historical traumatic events (e.g., "The great flood of Year 2").
- **Function**: Uses **Stochastic Retrieval**. Memories are scored by `Importance = (Emotion x Source) x Decay`. High-emotion memories bypass the window limit and are "pushed" into the prompt even 10 years later.

### Tier 3: Semantic Insights (The Reflection Engine) - [ROADMAP / FUTURE]

- **Scope**: Consolidated life lessons.
- **Status**: _Design phase / Not used in current JOH experiments._
- **Function**: At Year-End, the **Reflection Engine** triggers a "System 2" thinking process. It asks the LLM to summarize the year's events into a single **Insight** (e.g., _"Insurance is my only buffer against financial ruin"_).
- **Consolidation**: These insights are stored as high-priority semantic memories, ensuring the agent's "Personality" evolves based on past successes or failures.

---

---

## 🧪 Experimental Validation & Benchmarks

For detailed experimental setups (Baseline vs. Full), stress tests, and results from the JOH Paper, please refer to:
👉 **[Benchmarks & Examples](examples/README.md)**

---

## 🔧 Domain-Neutral Configuration (v3.3)

All domain-specific logic is centralized in `agent_types.yaml`. The framework is agnostic to the simulation domain.

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
```

---

## 🧠 Human-Centered Memory Mechanism

The **Human-Centric Memory Engine** (v3.3) solves the "Goldfish Effect" by prioritizing memories based on **Emotional Salience** rather than just recency. It includes a **Reflection Engine** that consolidates yearly experiences into long-term insights.

![Human-Centric Memory System](docs/human_centric_memory_diagram.png)

### Key Features:

1.  **Passive Retrieval**: The system pushes relevant memories to the LLM based on `Importance = Emotion x Source x Decay`.
2.  **Reflection Loop**: Yearly consolidation of events into generalized "Insights" (e.g., "Insurance is vital").
3.  **Bounded Context**: Filters thousands of logs into a concise, token-efficient prompt.

👉 **[Read the full Memory & Reflection Specification](docs/modules/memory_components.md)**

---

---

## ✅ Validated Models (v3.3)

The framework is strictly validated against the following model families to ensure consistent parsing and governance:

| Model Family     | Variant             | Use Case                       |
| :--------------- | :------------------ | :----------------------------- |
| **DeepSeek**     | R1-Distill-Llama-8B | High-Reasoning (CoT) Tasks     |
| **GPT-OSS**      | Strict-7B           | Baseline comparison            |
| **Meta Llama**   | 3.2-3B-Instruct     | Lightweight edge agents        |
| **Google Gemma** | 3-4B-IT             | Balanced / Multilingual agents |

---

### 1. State Layer: Multi-Level Ownership

- **Individual**: Private (`memory`, `elevated`, `insurance`).
- **Social**: Observable (`neighbor_actions`).
- **Shared**: Environmental (`flood_event`).
- **Institutional**: Policy (`subsidy_rate`).

### 2. Context Builder: Bounded Perception

- **Salience Filtering**: Retrieves top-k relevant memories via Memory Engine.
- **Demographic Anchoring**: Injects fixed traits (Income, Generation).

---

---

---

## 📜 References (APA)

The architecture is derived from and contributes to the following literature:

1.  **Park, J. S., ... & Bernstein, M. S.** (2023). Generative Agents: Interactive Simulacra of Human Behavior. _ACM CHI_.
2.  **Trope, Y., & Liberman, N.** (2010). Construal-level theory of psychological distance. _Psychological Review_, 117(2), 440.
3.  **Tversky, A., & Kahneman, D.** (1973). Availability: A heuristic for judging frequency and probability. _Cognitive Psychology_, 5(2), 207-232.
4.  **Siegrist, M., & Gutscher, H.** (2008). Natural hazards and motivation for self-protection: Memory matters. _Risk Analysis_, 28(3), 771-778.
5.  **Rogers, R. W.** (1983). Cognitive and physiological processes in fear appeals and attitude change: A revised theory of protection motivation. _Social Psychophysiology_.
6.  **Ebbinghaus, H.** (1885). _Memory: A Contribution to Experimental Psychology_. (The Forgetting Curve basis).

---

## Documentation

- [Architecture Details](docs/skill_architecture.md)
- [Customization Guide](docs/customization_guide.md)
- [Experiment Design](docs/experiment_design_guide.md)

## License

MIT
