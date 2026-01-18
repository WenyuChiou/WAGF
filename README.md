# Governed Broker Framework

**🌐 Language / 語言: [English](README.md) | [中文](README_zh.md)**

<div align="center">

**A Governance Middleware for Rational & Reproducible Agent-Based Models**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ollama](https://img.shields.io/badge/Ollama-Local_Inference-000000?style=flat&logo=ollama&logoColor=white)](https://ollama.com/)

</div>

---

## 📖 Mission Statement

The **Governed Broker Framework** addresses the fundamental "Logic-Action Gap" in Large Language Model (LLM) agents. While LLMs are highly fluent, they often exhibit stochastic instability, hallucinations, and "memory erosion" in long-horizon simulations. This framework provides an architectural **Governance Layer** that validates agent reasoning against physical constraints and psychological theories in real-time.

![Core Challenges & Solutions](docs/challenges_solutions_v3.png)

---

## 🏗️ Technical Architecture

The framework is structured as a **Cognitive Middleware** that decouples the agent's reasoning (LLM) from the environment physics (ABM).

![Governed Broker Architecture](docs/governed_broker_architecture_v3_1.png)

### Core Components & Directory Structure

| Module                | Purpose                                                    | Directory Path                             |
| :-------------------- | :--------------------------------------------------------- | :----------------------------------------- |
| **Skill Registry**    | Defines valid action spaces, costs, and constraints.       | [`broker/core/`](broker/core/)             |
| **Skill Broker**      | The "Judge" that enforces logic/action consistency.        | [`broker/core/`](broker/core/)             |
| **Memory Engine**     | Tiered memory retrieval (Window, Salience, Human-Centric). | [`broker/components/`](broker/components/) |
| **Reflection Engine** | Long-term semantic consolidation & "Lessons Learned".      | [`broker/components/`](broker/components/) |
| **Context Builder**   | Synthesizes bounded reality for unbiased prompts.          | [`broker/components/`](broker/components/) |
| **World Simulation**  | Environmental physics and world-state management.          | [`simulation/`](simulation/)               |

---

## 🛠️ Key Features

- **Pillar 1: Context Governance**: Mitigates hallucinations by structuring reality through bounded perception.
- **Pillar 2: Cognitive Intervention**: Real-time validation of agent reasoning (Thinking Rules) vs. chosen actions.
- **Pillar 3: Human-Centric Memory**: Emotional encoding and stochastic consolidation to prevent "The Goldfish Effect."
- **Pillar 4: Multi-Stage Robust Parsing**: A resilient parser designed to rescue insights from small models even when JSON formatting is malformed.

---

## 🚀 Deployment & Usage

### Setup

```bash
git clone https://github.com/WenyuChiou/governed-broker-framework.git
cd governed-broker-framework
pip install -r requirements.txt
```

### Running Simulations

The framework includes specialized benchmarks for hydro-social adaptation and stress testing.

- **[JOH Benchmark (Single Agent)](examples/single_agent/)**: Longitudinal study of household flood adaptation. Includes experimental results and detailed behavioral metrics.
- **[Multi-Agent Dynamics](examples/multi_agent/)**: Complex social interaction and peer-effect simulations.

---

## 🗺️ Framework Evolution

![Framework Evolution](docs/framework_evolution.png)

---

**Contact**: [Wenyu Chiou](https://github.com/WenyuChiou)
