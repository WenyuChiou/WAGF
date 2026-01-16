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

---

## Unified Architecture (v3.3)

The framework utilizes a layered middleware approach that unifies single-agent isolated reasoning with complex multi-agent simulations.

![Unified Architecture v3.3](docs/architecture.png)

### Key Architectural Pillars:

1. **Context-Aware Perception**: Explicitly separates Environmental **State** from Historical **Memories**.
2. **One-Way Governance**: LLM proposals flow unidirectionally into a validation pipeline before system execution.
3. **Closed Feedback Loop**: Simulation outcomes are simultaneously committed to memory and environment state.
4. **Lifecycle Auditing**: The `AuditWriter` captures traces from proposal to execution for full reproducibility.

**Version History**:

- **v1 (Legacy)**: Monolithic scripts.
- **v2 (Stable)**: Modular `SkillBrokerEngine` + `providers`.
- **v3 (Latest)**: Unified Single/Multi-Agent Architecture + Professional Audit Trail.
- **v3.1**: **Demographic Grounding & Statistical Validation**. Agents are grounded in real-world surveys.
- **v3.2**: **Advanced Memory & Skill Retrieval**. Implements MemGPT-style Tiered Memory and RAG-based Skill Selection.
- **v3.3 (Production)**: **Domain-Agnostic Parsing & Human-Centric Memory**.
  - All domain-specific logic moved to `agent_types.yaml`.
  - **Human-Centric Memory Engine**: Implements emotional encoding and passive retrieval.

---

## ⚠️ Practical Challenges & Lessons Learned

Developing LLM-based agents within a governed framework revealed several recurring challenges that influenced our architectural decisions.

### 1. The Parsing Breakdown (Syntax vs. Semantics)

**Challenge**: Small language models (e.g., Llama-3.2 3B, Gemma-3 4B) frequently suffer from "Syntax Collapse" when prompts become dense. They may output invalid JSON, nested objects instead of flat keys, or unquoted strings.
**Insight**: We moved from strict JSON parsing to a **Multi-Layer Defensive Parsing** strategy.

- **Example**: In our latest `UnifiedAdapter`, we sequence: **Enclosure Extraction** -> **JSON Repair** (for missing quotes/commas) -> **Keyword Regex** -> **Last-Resort Digit Extraction**.

### 2. The Logic-Action Gap

**Challenge**: Agents often distinguish "Feeling Safe" (Reasoning) from "Relocating" (Action).
**Solution**: **Thinking Validators** in the `SkillBrokerEngine`. When a gap is detected, the broker triggers an immediate **Retry Prompt** with explicit logical feedback.

### 3. Identity Drift

**Challenge**: In later years (Year 7+), agents may forget their role (e.g., Renter attempting to Elevate).
**Solution**: **Identity Guardrails** at the Governance Layer block invalid skills based on the immutable Agent Profile.

---

## 🔧 Domain-Neutral Configuration (v3.3)

All domain-specific logic is now centralized in `agent_types.yaml`. The framework is agnostic to the simulation domain.

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

## 🧠 Human-Centered Memory Mechanism (v3.3)

Unlike traditional RAG systems where the agent queries a database, this framework uses a **System-Push (Passive Retrieval)** mechanism.

### 1. Passive "System-Push" Philosophy

**The LLM does NOT actively search memory.**
Instead, the **Memory Engine** acts as a cognitive filter that runs _before_ the LLM thinks. It algorithmically determines what is "salient" based on the agent's current state and history, then injects these memories directly into the context prompt. This mimics how human memory involuntarily surfaces traumatic or significant events.

### 2. Scoring Mechanics (The Filter)

Memories are retained and retrieved based on a composite **Importance Score**:

$$ \text{Importance} = (\text{Emotion Weight} \times \text{Source Weight}) \times e^{-\lambda t} $$

- **Emotion (What)**: Events with high emotional keywords (`damage`, `success`, `fail`) score higher (0.8-1.0) than routine events (0.1).
- **Source (Who)**: Personal experiences (1.0) outweigh hearsay/neighbor observations (0.7) or generic news (0.5).
- **Time Decay ($e^{-\lambda t}$)**: All memories fade, but high-emotion memories decay much slower, allowing "Accessable History" (e.g., a major flood 5 years ago) to persist while recent trivia vanishes.

### 3. Stochastic Consolidation

Not everything is remembered. The engine uses **Probabilistic Storage**:

- **Working Memory**: Everything is held briefly.
- **Long-Term Memory**: Only items exceeding an importance threshold have a probability $P$ of being consolidated.
- $P(\text{consolidate}) \propto \text{Importance Score}$

---

## Single-Agent Flood Experiment (SA)

### Agent initialization
- `examples/single_agent/run_flood.py` loads agents from a CSV profile file.
- Required columns: `id`, `elevated`, `has_insurance`, `relocated`, `trust_in_insurance`, `trust_in_neighbors`, `flood_threshold`, `memory`.
- Skills are set from the registry, and `agent_type` is `household`.

### Disaster model
- Flood mode:
  - `fixed`: years from `flood_years.csv`
  - `prob`: per-year probability via `FLOOD_PROBABILITY`
- Per-year signals: grant availability (`GRANT_PROBABILITY`), neighbor observations, and stochastic recall.
- Damage model: base $10,000; elevation reduces damage to 10%.
- Elevation reduces future flood susceptibility (`flood_threshold` scaled down after elevation).

### Outputs and logs
- `simulation_log.csv` includes `yearly_decision` (actual per-year choice) and `cumulative_state`.
- Audit traces are auto-cleared per run to avoid mixed `run_id` data.

## Generality and maintainability notes

- SA logic is isolated under `examples/single_agent/` to keep core broker components domain-agnostic.
- Domain-specific parameters live in `run_flood.py`; prompts and actions live in `agent_types.yaml`.
- Keep outputs stable for reproducibility (`config_snapshot.yaml`, audit CSVs, traces).

---

## 🔬 Scientific Research Questions (SQs)

### SQ1: Cognitive vs. Stochastic Adaptation

**Question**: How does LLM-driven reasoning-based adaptation compare to probability-based adaptation?
**Goal**: Evaluate if reasoning-based models better capture "lock-in" effects.

### SQ2: Social Network Influence

**Question**: How do social network effects (gossip) accelerate or dampen adaptation?
**Goal**: Understand how social capital (SC) modulates adaptation for different demographics.

### SQ3: Institutional Feedback

**Question**: How do institutional feedback loops (FEMA solvency, subsidies) interact with community resilience?
**Goal**: Map policy sensitivity.

---

## 📊 Scientific & Statistical Validation

### 1. Chi-square Decision Analysis

We use **Chi-square tests** to prove that governance and memory mechanisms create statistically significant behavioral changes ($p < 0.05$).

### 2. Demographic Grounding Audit

Scores whether the LLM **actually uses** survey context (Identity, Experience) in its reasoning (0.0 - 1.0 scale).

### 3. How to Run Memory Benchmark

To reproduce the 3x4 comparison charts (Baseline vs. Window vs. Human-Centric) across all models:

```bash
python examples/single_agent/analyze_old_vs_memory.py
```

_Output: Generates `README_EN.md`, `README_CH.md`, and statistical plots in `examples/single_agent/benchmark_analysis/`._

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

## 🏗️ Technical Architecture Details

### 1. State Layer: Multi-Level Ownership

- **Individual**: Private (`memory`, `elevated`, `insurance`).
- **Social**: Observable (`neighbor_actions`).
- **Shared**: Environmental (`flood_event`).
- **Institutional**: Policy (`subsidy_rate`).

### 2. Context Builder: Bounded Perception

- **Salience Filtering**: Retrieves top-k relevant memories via Memory Engine.
- **Demographic Anchoring**: Injects fixed traits (Income, Generation).

### 3. Simulation Engine: Sequential World Evolution

- **Sandboxed Execution**: Agents propose skills; Engine executes them.

---

## Documentation

- [Architecture Details](docs/skill_architecture.md)
- [Customization Guide](docs/customization_guide.md)
- [Experiment Design](docs/experiment_design_guide.md)

## License

MIT
