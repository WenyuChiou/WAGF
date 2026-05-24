# Examples & Benchmarks

**Language: [English](README.md) | [Chinese](README_zh.md)**

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
| Study the main single-agent flood case | `single_agent/` | Primary SA reference |
| Study the single-agent irrigation case | `irrigation_abm/` | Primary SA reference |
| Study the institutional multi-agent flood case | `multi_agent/flood/` | Primary MA reference |

Everything else in `examples/` is secondary teaching support, a compact demo, or historical/archive material.

---

## Recommended Learning Path

| # | Example | Type | What You Learn |
| :-- | :--- | :--- | :--- |
| 0 | **[quickstart/](quickstart/)** | Tutorial | Core governance loop with mock LLM, no Ollama needed |
| 1 | **[minimal/](minimal/)** | Template | Copy this to start a new ABM domain |
| 2 | **[single_agent/](single_agent/)** | SA water reference | Full single-agent flood benchmark |
| 3 | **[irrigation_abm/](irrigation_abm/)** | SA water reference | Colorado River irrigation case |
| 4 | **[multi_agent/flood/](multi_agent/flood/)** | MA water reference | Institutional multi-agent flood study |
| 5 | **[governed_flood/](governed_flood/)** | Teaching demo + broker test fixture | Compact flood-sector demo (also the FloodDomainPack source for several broker tests; kept as load-bearing fixture) |
| 6 | **[vaccination_demo/](vaccination_demo/)** | Non-water Tier-2 showcase | HBM-driven vaccination decisions; 25 agents × 5 yr COVID-19 schedule; 3 seeds × 2 models |
| 7 | **[vaccination_ma_demo/](vaccination_ma_demo/)** | Non-water multi-agent reference | 3 agent types (health_authority + community_org + individual); env-dict-whitelist coupling |
| 8 | **[gossip_demo/](gossip_demo/)** | Non-water social-media reference | Daily-cadence multi-agent (moderator + influencer + user) |

---

## Directory Overview

### Primary Water-Sector Reference Implementations

#### Single-Agent Reference Implementations

| Directory | Why it exists | Maintenance status |
| :--- | :--- | :--- |
| **[single_agent/](single_agent/)** | Main single-agent flood validation suite for paper results | Primary reference |
| **[irrigation_abm/](irrigation_abm/)** | Main single-agent irrigation water-management reference implementation | Primary reference |

#### Multi-Agent Reference Implementations

| Directory | Why it exists | Maintenance status |
| :--- | :--- | :--- |
| **[multi_agent/flood/](multi_agent/flood/)** | Main multi-agent flood reference implementation | Primary reference |

### Tutorials and Templates

| Directory | Why it exists | Maintenance status |
| :--- | :--- | :--- |
| **[quickstart/](quickstart/)** | Teaches the core governance loop progressively | Maintained |
| **[minimal/](minimal/)** | Official starting scaffold for a new ABM domain | Maintained |
### Non-Water Reference Implementations

| Directory | Why it exists | Maintenance status |
| :--- | :--- | :--- |
| **[vaccination_demo/](vaccination_demo/)** | Non-water Tier-2 showcase — HBM-driven vaccination decisions, literature-grounded population, 5-year COVID-19 outbreak schedule | Tier-2 showcase (L3-1 2026-05-24) |
| **[vaccination_ma_demo/](vaccination_ma_demo/)** | Multi-agent counterpart to vaccination_demo — health authority + community org + individual | PoC reference |
| **[gossip_demo/](gossip_demo/)** | Daily-cadence social-media multi-agent reference (moderator + influencer + casual user) | PoC reference |

### Secondary Teaching / Demonstration Examples

| Directory | Why it exists | Maintenance status |
| :--- | :--- | :--- |
| **[governed_flood/](governed_flood/)** | Compact flood-sector teaching demo for full governance — also the canonical `FloodDomainPack` source for `broker/tests/test_initial_loader.py` + `broker/tests/test_memory_content_types.py` (kept as broker test fixture, not removable) | Maintained demo + broker test fixture |

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
