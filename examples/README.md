# Examples & Benchmarks

**Language: [English](README.md) | [中文](README_zh.md)**

This directory contains reproduction scripts, experimental configurations, and benchmark results for the Water Agent Governance Framework.

---

## Prerequisites

- **Python 3.10+**
- **Ollama** (for local inference): [ollama.com/download](https://ollama.com/download)
  - Pull a model: `ollama pull gemma3:4b`
- Cloud providers (optional): set `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GEMINI_API_KEY`

---

## Which Example Should I Start With?

| I want to... | Example | Time |
| :--- | :--- | :--- |
| See the core loop (no LLM needed) | `quickstart/01_barebone.py` | 30 sec |
| See governance blocking invalid actions | `quickstart/02_governance.py` | 1 min |
| Try multi-agent phase ordering (no LLM) | `multi_agent_simple/run.py` | 2 min |
| Run a real flood simulation | `governed_flood/run_experiment.py` | 5 min |
| Build my own domain from scratch | Copy `minimal/` as template | -- |
| Reproduce the JOH paper (Groups A/B/C) | `single_agent/` | 2+ hrs |
| Run irrigation water management | `irrigation_abm/` | 1+ hrs |
| Run multi-agent flood with institutions | `multi_agent/flood/` | 4+ hrs |

---

## Learning Path (Recommended Order)

![Example Progression](../docs/example_progression.png)

**Groups A/B/C** refers to the ablation study design used in the JOH (_Journal of Hydrology_) benchmark:

- **Group A** — Baseline: no governance, no memory (raw LLM output)
- **Group B** — Governance + window memory (rational but no long-term memory)
- **Group C** — Full cognitive: governance + HumanCentric memory + priority schema

| # | Example | Complexity | What You Learn |
| :-- | :--- | :--- | :--- |
| 0 | **[quickstart/](quickstart/)** | Tutorial | Core governance loop with mock LLM — no Ollama needed |
| 1 | **[governed_flood/](governed_flood/)** | Beginner | Standalone Group C demo — governance + human-centric memory in action |
| 2 | **[single_agent/](single_agent/)** | Intermediate | Full JOH Benchmark — Groups A/B/C ablation study, stress tests, survey mode |
| 3 | **[irrigation_abm/](irrigation_abm/)** | Intermediate | Different domain — 78 CRSS agents, Colorado River Basin water demand |
| 4 | **[multi_agent/flood/](multi_agent/flood/)** | Advanced | Social dynamics — insurance market, government subsidies, peer effects |

---

## Directory Overview

| Directory | Agents | Social | Governance | Memory | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **[quickstart/](quickstart/)** | 1-7 | No | Demo | None/Window | Tutorial |
| **[multi_agent_simple/](multi_agent_simple/)** | 7 | No | Basic | Window | Tutorial |
| **[governed_flood/](governed_flood/)** | 100 | No | Strict only | HumanCentric | Active |
| **[single_agent/](single_agent/)** | 100 | Optional | 3 profiles (strict/relaxed/disabled) | Configurable | Active |
| **[irrigation_abm/](irrigation_abm/)** | 78 | No | 12 domain validators | Universal | Active |
| **[multi_agent/flood/](multi_agent/flood/)** | 400 | Yes | Advanced | Universal | Active |
| **[minimal/](minimal/)** | -- | -- | -- | -- | Template |
| **[archive/](archive/)** | -- | -- | -- | -- | Archived |

**Status legend**: Tutorial = no LLM required, mock-based | Active = production-ready, used in papers | Template = scaffold for new domains | Archived = deprecated, no longer maintained

**Note**: `quickstart/` and `multi_agent_simple/` form a 3-tier progressive tutorial (barebone → governance → multi-agent). `multi_agent_simple/` is Tier 3 of the quickstart series.

**Note**: `archive/` contains deprecated examples (finance, ma_legacy, single_agent_modular, unified_flood) superseded by current implementations.

---

## Quick Start

### 1. Simplest: Governed Flood Demo

The governed_flood example is a self-contained Group C experiment with full governance and human-centric memory. No configuration required.

```bash
python examples/governed_flood/run_experiment.py --model gemma3:4b --years 3 --agents 10
```

### 2. Full Benchmark: Single Agent (JOH Paper)

Replicate the three-group ablation study with 100 agents over 10 years:

```bash
# Group A: Baseline (no governance, no memory)
python examples/single_agent/run_flood.py --model gemma3:4b --years 10 --agents 100 \
    --governance-mode disabled

# Group B: Governance + Window Memory
python examples/single_agent/run_flood.py --model gemma3:4b --years 10 --agents 100 \
    --memory-engine window --governance-mode strict

# Group C: Full Cognitive (HumanCentric + Priority Schema)
python examples/single_agent/run_flood.py --model gemma3:4b --years 10 --agents 100 \
    --memory-engine humancentric --governance-mode strict --use-priority-schema
```

### 3. Multi-Agent: Social Dynamics

Run a multi-agent flood experiment with household, government, and insurance agents:

```bash
python examples/multi_agent/flood/run_unified_experiment.py --model gemma3:4b
```

---

## Output Structure

Each experiment produces outputs in its `results/` directory. Common files:

| File | Description |
| :--- | :--- |
| `simulation_log.csv` or `household_decisions.csv` | Per-agent, per-year decision log (action, appraisals, reasoning) |
| `*_governance_audit.csv` | Governance audit trail (interventions, retries, warnings) |
| `governance_summary.json` | Aggregate governance statistics |
| `config_snapshot.yaml` | Full experiment configuration snapshot for reproducibility |

**Note**: File names vary by example. Check each example's README for exact output file names.

---

## Models

All examples support Ollama-compatible models and cloud providers. Recommended models:

| Model | Tag | Parameters | Notes |
| :--- | :--- | :--- | :--- |
| Gemma 3 | `gemma3:4b` | 4B | Primary benchmark — fast, good parsing |
| Gemma 3 | `gemma3:12b` | 12B | Better reasoning, slower |
| Gemma 3 | `gemma3:27b` | 27B | Best quality, requires significant VRAM |
| Llama 3.2 | `llama3.2:3b` | 3B | Lightweight, parsing challenges |
| DeepSeek R1 | `deepseek-r1:8b` | 8B | Chain-of-thought reasoning |

Cloud providers: use `anthropic:model-name`, `openai:model-name`, or `gemini:model-name` with the `--model` flag.

---

## Further Reading

- **[Root README](../README.md)**: Framework overview and architecture
- **[Experiment Design Guide](../docs/guides/experiment_design_guide.md)**: How to design new experiments
- **[Agent Assembly Guide](../docs/guides/agent_assembly.md)**: How to configure cognitive stacking levels
- **[YAML Configuration Reference](../docs/references/yaml_configuration_reference.md)**: Full parameter specification
