# Examples & Benchmarks

**Language: [English](README.md) | [¤¤¤å](README_zh.md)**

This directory contains four different kinds of assets:

1. Tutorials for new users
2. Templates for new ABM domains
3. Water-sector reference experiments
4. Archived or legacy materials

WAGF is intended to be usable by ABM developers, but it is still a
water-sector-first framework. The flood and irrigation examples remain the main
reference implementations.

---

## Prerequisites

- **Python 3.10+**
- **Ollama** (for local inference): [ollama.com/download](https://ollama.com/download)
  - Pull a model: `ollama pull gemma3:4b`
- Cloud providers (optional): set `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GEMINI_API_KEY`

---

## Which Example Should I Start With?

| I want to... | Example | Role | Time |
| :--- | :--- | :--- | :--- |
| See the core loop (no LLM needed) | `quickstart/01_barebone.py` | Tutorial | 30 sec |
| See governance blocking invalid actions | `quickstart/02_governance.py` | Tutorial | 1 min |
| Try multi-agent phase ordering (no LLM) | `multi_agent_simple/run.py` | Tutorial | 2 min |
| Build my own domain from scratch | Copy `minimal/` as template | Template | -- |
| See a generic non-water configuration | `minimal_nonwater/run_demo.py` | Template / reference | 1 min |
| Run a compact flood simulation | `governed_flood/run_experiment.py` | Teaching demo | 5 min |
| Reproduce the JOH paper (Groups A/B/C) | `single_agent/` | Water reference | 2+ hrs |
| Run irrigation water management | `irrigation_abm/` | Water reference | 1+ hrs |
| Run multi-agent flood with institutions | `multi_agent/flood/` | Water reference | 4+ hrs |

---

## Learning Path

| # | Example | Type | What You Learn |
| :-- | :--- | :--- | :--- |
| 0 | **[quickstart/](quickstart/)** | Tutorial | Core governance loop with mock LLM, no Ollama needed |
| 1 | **[multi_agent_simple/](multi_agent_simple/)** | Tutorial | Small multi-agent teaching example with phase ordering |
| 2 | **[minimal/](minimal/)** | Template | Copy this to start a new ABM domain |
| 3 | **[governed_flood/](governed_flood/)** | Teaching demo | Compact flood-sector demo with full governance |
| 4 | **[single_agent/](single_agent/)** | Water reference | Full JOH benchmark with Groups A/B/C, stress tests, and survey mode |
| 5 | **[irrigation_abm/](irrigation_abm/)** | Water reference | Colorado River irrigation case with cognitive appraisal governance |
| 6 | **[multi_agent/flood/](multi_agent/flood/)** | Water reference | Full multi-agent flood study with institutions and social effects |

---

## Directory Overview

### Tutorials

| Directory | Why it exists | Maintenance status |
| :--- | :--- | :--- |
| **[quickstart/](quickstart/)** | Teaches the core governance loop progressively | Maintained |
| **[multi_agent_simple/](multi_agent_simple/)** | Teaches multi-agent phase ordering and cross-type governance with a tiny mock simulation | Maintained tutorial |

### Templates

| Directory | Why it exists | Maintenance status |
| :--- | :--- | :--- |
| **[minimal/](minimal/)** | Official starting scaffold for a new ABM domain | Maintained |
| **[minimal_nonwater/](minimal_nonwater/)** | Small proof that the core is configurable beyond water | Secondary reference |

### Water-Sector Reference Experiments

| Directory | Why it exists | Maintenance status |
| :--- | :--- | :--- |
| **[governed_flood/](governed_flood/)** | Compact flood-sector teaching demo for full governance | Maintained demo |
| **[single_agent/](single_agent/)** | Main single-agent flood validation suite for paper results | Primary reference |
| **[irrigation_abm/](irrigation_abm/)** | Main irrigation water-management reference pack | Primary reference |
| **[multi_agent/flood/](multi_agent/flood/)** | Main multi-agent flood reference pack | Primary reference |

### Archive / Legacy

| Directory | Why it exists | Maintenance status |
| :--- | :--- | :--- |
| **[archive/](archive/)** | Historical experiments and superseded implementations | Archived |

`archive/` contains deprecated examples such as `finance`, `ma_legacy`,
`single_agent_modular`, and `unified_flood`. They remain for provenance, not as
recommended starting points.

---

## Quick Start

### 1. Simplest Water Demo: Governed Flood

The governed_flood example is a compact teaching demo for the flood domain. It
is useful for first contact with a real water-sector run, but it is not the
main paper-grade validation suite.

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

### 3. Multi-Agent Water Reference

Run a multi-agent flood experiment with household, government, and insurance agents:

```bash
python examples/multi_agent/flood/run_unified_experiment.py --model gemma3:4b
```

---

## Output Structure

Each experiment produces outputs in its `results/` directory. Common files:

| File | Description |
| :--- | :--- |
| `simulation_log.csv` or `household_decisions.csv` | Per-agent, per-year decision log |
| `*_governance_audit.csv` | Governance audit trail |
| `governance_summary.json` | Aggregate governance statistics |
| `config_snapshot.yaml` | Full experiment configuration snapshot for reproducibility |

File names vary by example. Check each example's README for exact output names.

---

## Further Reading

- **[Root README](../README.md)**: Framework overview and architecture
- **[Experiment Design Guide](../docs/guides/experiment_design_guide.md)**: How to design new experiments
- **[Agent Assembly Guide](../docs/guides/agent_assembly.md)**: How to configure cognitive stacking levels
- **[YAML Configuration Reference](../docs/references/yaml_configuration_reference.md)**: Full parameter specification
