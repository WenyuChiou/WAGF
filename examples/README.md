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
| Start a new domain | `python -m broker.tools.scaffold_domain <name> --skills ...` (see `docs/guides/domain_pack_guide.md`) | Template CLI |
| Study the main single-agent flood case | `single_agent/` | Primary SA reference |
| Study the single-agent irrigation case | `irrigation_abm/` | Primary SA reference |
| Study the institutional multi-agent flood case | `multi_agent/flood/` | Primary MA reference |

Everything else in `examples/` is secondary teaching support, a compact demo, or historical/archive material.

---

## Recommended Learning Path

| # | Example | Type | What You Learn |
| :-- | :--- | :--- | :--- |
| 0 | **[quickstart/](quickstart/)** | Tutorial | Core governance loop with mock LLM, no Ollama needed |
| 2 | **[single_agent/](single_agent/)** | SA water reference | Full single-agent flood benchmark |
| 3 | **[irrigation_abm/](irrigation_abm/)** | SA water reference | Colorado River irrigation case |
| 4 | **[multi_agent/flood/](multi_agent/flood/)** | MA water reference | Institutional multi-agent flood study |
| 5 | **[governed_flood/](governed_flood/)** | Teaching demo + broker test fixture | Compact flood-sector demo (also the FloodDomainPack source for several broker tests; kept as load-bearing fixture) |
| 6 | **[vaccination_demo/](vaccination_demo/)** | Non-water Tier-2 showcase | HBM-driven vaccination decisions; 25 agents × 5 yr COVID-19 schedule; 3 seeds × 2 models |

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
### Non-Water Reference Implementations

| Directory | Why it exists | Maintenance status |
| :--- | :--- | :--- |
| **[vaccination_demo/](vaccination_demo/)** | Non-water Tier-2 showcase — HBM-driven vaccination decisions, literature-grounded population, 5-year COVID-19 outbreak schedule | Tier-2 showcase (L3-1 2026-05-24) |

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
python examples/governed_flood/run_experiment.py --model gemma3:4b --years 2 --agents 10
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

## Full Directory Index

Every directory under `examples/`, one line each. This is the
complete list; the sections above are curated subsets for someone
picking a starting point.

| Directory | One line | Start here |
|---|---|---|
| `quickstart/` | Progressive tutorial for the core governance loop, mock LLM only | `python examples/quickstart/02_governance.py` |
| `single_agent/` | Primary single-agent flood reference (paper validation suite) | `python examples/single_agent/run_flood.py --model gemma3:4b --years 10 --agents 100` |
| `irrigation_abm/` | Primary single-agent irrigation reference (Colorado River / CRSS) | see `irrigation_abm/README.md` |
| `multi_agent/` | Container directory for multi-agent domains; today holds one (`flood/`) | see `multi_agent/README.md` |
| `multi_agent/flood/` | Primary multi-agent reference (institutional + household flood ABM) | `python examples/multi_agent/flood/run_unified_experiment.py --model gemma3:4b` |
| `governed_flood/` | Compact flood teaching demo; also a load-bearing fixture imported by 17 `broker/tests/` files | `python examples/governed_flood/run_experiment.py --model gemma3:4b --years 2 --agents 10` |
| `vaccination_demo/` | Non-water Tier-2 showcase — HBM-driven vaccination decisions | see `vaccination_demo/README.md` |
| `cat_model/` | Catastrophe-model coupling worked example (insurer solvency governance) | `python examples/cat_model/run_cat.py --model mock --years 3` |
| `reservoir_control/` | Reservoir continuous-control worked example (single setpoint) | `python examples/reservoir_control/run_reservoir_ops.py --model mock --years 4` |
| `reservoir_control_multidim/` | Reservoir worked example with three setpoints proposed per decision | `python examples/reservoir_control_multidim/run_reservoir_multidim.py --model mock --years 4` |
| `coupling_examples/` | `broker.coupling` connector pattern teaching material (Archetype C subprocess) | `python examples/coupling_examples/archetype_c_subprocess/run_archetype_c.py --model mock --years 4` |
| `_test_fixtures/` | Non-water `DomainPack` fixture proving broker genericity; not runnable standalone | exercised via `tests/integration/test_e2e_genericity.py` |

See `docs/REPO_MAP.md` section 4 for the same directories cross-referenced
against README/tests/run-script/DomainPack-registration status.

---

## Further Reading

- **[Root README](../README.md)**: Framework overview and architecture
- **[Experiment Design Guide](../docs/guides/experiment_design_guide.md)**: How to design new experiments
- **[Agent Assembly Guide](../docs/guides/agent_assembly.md)**: How to configure cognitive stacking levels
- **[YAML Configuration Reference](../docs/references/yaml_configuration_reference.md)**: Full parameter specification
