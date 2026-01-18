# Governed Broker Framework

**🌐 Language / 語言: [English](README.md) | [中文](README_zh.md)**

<div align="center">

**A Governance Middleware for LLM-driven Agent-Based Models**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ollama](https://img.shields.io/badge/Ollama-Local_Inference-000000?style=flat&logo=ollama&logoColor=white)](https://ollama.com/)

</div>

---

## 📖 Overview

The **Governed Broker Framework** addresses the "Logic-Action Gap" in LLM simulations. While modern LLMs are fluent, they often exhibit stochastic instability, hallucinations, and "memory erosion" over long-horizon simulations. This framework provides an architectural "superego" that validates agent reasoning against physical reality and institutional rules.

![Core Challenges & Solutions](docs/challenges_solutions_v3.png)

---

## 🏗️ System Architecture

The framework is structured as a **modular cognitive middleware** sitting between the Agent's decision model (LLM) and the Simulation Environment (ABM).

![System Architecture](docs/governed_broker_architecture_v3_1.png)

### Core Modules Breakdown

| Module                 | Purpose                                                         | Location             |
| :--------------------- | :-------------------------------------------------------------- | :------------------- |
| **`SkillRegistry`**    | Defines the action space, costs, and physical constraints.      | `broker/core/`       |
| **`SkillBroker`**      | Validates LLM proposals against logic/action consistency rules. | `broker/core/`       |
| **`MemoryEngine`**     | Manages tiered memory (Window, Salience, Human-Centric).        | `broker/components/` |
| **`ReflectionEngine`** | Performs high-level semantic consolidation (Lessons Learned).   | `broker/components/` |
| **`ContextBuilder`**   | Synthesizes bounded reality for LLM prompts.                    | `broker/components/` |
| **`SimulationEngine`** | Orchestrates world-state evolution and physics.                 | `simulation/`        |

---

## 🧠 Functional Modules Registry

### 1. Governed Broker (`broker/`)

The central orchestrator of the framework. It handles the "Thinking-Action" loop:

- **Validators**: Checks if the LLM's reasoning matches its final decision (e.g., if Threat is High but Action is Nothing, it triggers self-correction).
- **Audit Trails**: Generates professional, machine-readable traces of every decision.

### 2. Cognitive Memory Layer (`broker/components/`)

A sophisticated memory system inspired by human heuristics:

- **Tiered Memory**: Separates Recent (Episodic) and Semantic (Long-Term) memory.
- **Reflection Engine**: Periodically summarizes experiences into "Long-Term Lessons." Optimized with **multi-stage robust parsing** for small models (Llama 3.2).
- **Salience Retrieval**: Uses an Importance/Retrieval formula to fetch the most relevant memories.

### 3. Simulation Environment (`simulation/`)

A modular environment engine that simulates external shocks (e.g., Floods) and calculates physical outcomes (e.g., Damage, Insurance payouts).

### 4. Experimental Suite (`examples/`)

- **JOH (Just-In-Time Household)**: Benchmarking agent adaptation under adversarial stress.
- **Stress-Test Marathons**: Automated scripts to test model resilience over years.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/) (for local LLM execution) or OpenAI API Key.

### Installation

```bash
git clone https://github.com/WenyuChiou/governed-broker-framework.git
cd governed-broker-framework
pip install -r requirements.txt
```

### Running a Benchmark

Execute a standard 10-year flood adaptation benchmark:

```bash
python examples/single_agent/run_flood.py --model llama3.2:3b --years 10 --agents 100 --memory-engine humancentric
```

---

## 📊 Experimental Results

### Human-Centric Stability (Group C)

Our latest benchmarks show that the **Governed Broker** significantly reduces "Trauma Amplification" in small models through structured reflection.

![Stochastic Instability Visualization](doc/images/Figure2_Stochastic_Instability.png)

---

## 🗺️ Roadmap

- [x] **v3.3**: Robust multi-stage reflection parsing for 3B-7B models.
- [ ] **v3.4**: Multi-agent social network influence propagation.
- [ ] **v4.0**: Domain-neutral "Thinking Rules" for generalized policy analysis.

---

**Contact**: [Wenyu Chiou](https://github.com/WenyuChiou)
