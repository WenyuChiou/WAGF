# Examples & Benchmarks

**Language: [English](README.md) | [¤¤¤å](README_zh.md)**

This directory contains four kinds of assets:

1. Tutorials for new users
2. Templates for new ABM domains
3. Primary water-sector reference implementations
4. Archived or legacy materials

WAGF is intended to be usable by ABM developers, but it is still a
water-sector-first framework. Most users should focus on the main reference
implementations first and treat the remaining examples as support material.

---

## Prerequisites

- **Python 3.10+**
- **Ollama** (for local inference): [ollama.com/download](https://ollama.com/download)
  - Pull a model: `ollama pull gemma3:4b`
- Cloud providers (optional): set `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GEMINI_API_KEY`

---

## Start Here

Most users should only look at five entry points:

| Goal | Start here | Role |
| :--- | :--- | :--- |
| Understand the broker loop in minutes | `quickstart/` | Tutorial |
| Start a new domain | `minimal/` | Template |
| Study the main single-agent flood case | `single_agent/` | Primary reference |
| Study the irrigation case | `irrigation_abm/` | Primary reference |
| Study the institutional multi-agent flood case | `multi_agent/flood/` | Primary reference |

Everything else in `examples/` is secondary teaching support, a compact demo, or historical/archive material.

---

## Recommended Learning Path

| # | Example | Type | What You Learn |
| :-- | :--- | :--- | :--- |
| 0 | **[quickstart/](quickstart/)** | Tutorial | Core governance loop with mock LLM, no Ollama needed |
| 1 | **[minimal/](minimal/)** | Template | Copy this to start a new ABM domain |
| 2 | **[single_agent/](single_agent/)** | Water reference | Full single-agent flood benchmark |
| 3 | **[irrigation_abm/](irrigation_abm/)** | Water reference | Colorado River irrigation case |
| 4 | **[multi_agent/flood/](multi_agent/flood/)** | Water reference | Institutional multi-agent flood study |
| 5 | **[governed_flood/](governed_flood/)** | Teaching demo | Compact flood-sector demo |
| 6 | **[multi_agent_simple/](multi_agent_simple/)** | Tutorial | Tiny phase-ordering example |
| 7 | **[minimal_nonwater/](minimal_nonwater/)** | Secondary reference | Small proof of non-water configurability |

---

## Directory Overview

### Primary Water-Sector Reference Implementations

| Directory | Why it exists | Maintenance status |
| :--- | :--- | :--- |
| **[single_agent/](single_agent/)** | Main single-agent flood validation suite for paper results | Primary reference |
| **[irrigation_abm/](irrigation_abm/)** | Main irrigation water-management reference implementation | Primary reference |
| **[multi_agent/flood/](multi_agent/flood/)** | Main multi-agent flood reference implementation | Primary reference |

### Tutorials and Templates

| Directory | Why it exists | Maintenance status |
| :--- | :--- | :--- |
| **[quickstart/](quickstart/)** | Teaches the core governance loop progressively | Maintained |
| **[minimal/](minimal/)** | Official starting scaffold for a new ABM domain | Maintained |
| **[multi_agent_simple/](multi_agent_simple/)** | Small multi-agent teaching example with phase ordering | Maintained tutorial |

### Secondary Teaching / Demonstration Examples

| Directory | Why it exists | Maintenance status |
| :--- | :--- | :--- |
| **[governed_flood/](governed_flood/)** | Compact flood-sector teaching demo for full governance | Maintained demo |
| **[minimal_nonwater/](minimal_nonwater/)** | Small proof that the core is configurable beyond water | Secondary reference |

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

### 2. Full Benchmark: Single Agent Flood

```bash
python examples/single_agent/run_flood.py --model gemma3:4b --years 10 --agents 100 \
    --memory-engine humancentric --governance-mode strict
```

### 3. Multi-Agent Water Reference

```bash
python examples/multi_agent/flood/run_unified_experiment.py --model gemma3:4b
```

---

## Further Reading

- **[Root README](../README.md)**: Framework overview and architecture
- **[Experiment Design Guide](../docs/guides/experiment_design_guide.md)**: How to design new experiments
- **[Agent Assembly Guide](../docs/guides/agent_assembly.md)**: How to configure cognitive stacking levels
- **[YAML Configuration Reference](../docs/references/yaml_configuration_reference.md)**: Full parameter specification
