# WAGF — Water Agent Governance Framework

<div align="center">

**Govern LLM-driven agents with domain rules, behavioral theory, and full audit trails.**

Built for water resources. Extensible to any domain.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://github.com/WenyuChiou/WAGF/actions/workflows/test.yml/badge.svg)](https://github.com/WenyuChiou/WAGF/actions/workflows/test.yml)
[![Ollama](https://img.shields.io/badge/Ollama-Local_Inference-000000?style=flat&logo=ollama&logoColor=white)](https://ollama.com/)

[**English**](README.md) | [**中文**](README_zh.md)

</div>

## What is WAGF?

Large Language Models (LLMs) can generate rich, human-like reasoning for agent-based models, but they also hallucinate, contradict themselves, and produce invalid actions. WAGF provides a **Governance Broker** that validates every LLM decision against domain rules before execution, turning unreliable LLM outputs into scientifically auditable agent behavior.

## Key Features

- **Governance Pipeline** — 6-stage validation (Context → LLM → Parse → Validate → Approve/Retry → Execute) before any action reaches the simulation
- **Cognitive Memory** — Weighted retrieval combining recency, importance, and context match, with emotional encoding, stochastic consolidation, and exponential decay
- **Multi-Agent Institutions** — Government, insurance, and household agents with sequential decision-making and endogenous policy feedback
- **Full Audit Trail** — Every decision, rejection, retry, and reasoning trace logged as structured JSONL/CSV
- **Domain Packs** — Add a new domain with 3 files: `skill_registry.yaml` + `agent_types.yaml` + `lifecycle_hooks.py`
- **Model Agnostic** — Ollama (local GPU), OpenAI, Anthropic, Google Gemini, Azure
- **Theory Integration** — Protection Motivation Theory, bounded rationality, dual-process cognition (pluggable via YAML)
- **Research Ready** — Ablation modes (strict/relaxed/disabled), cross-model comparison, multi-seed reproducibility

## Why Governance?

| Challenge | What Goes Wrong | WAGF Solution |
|:---|:---|:---|
| **Hallucination** | LLM invents actions that don't exist | Strict skill registry: only registered actions accepted |
| **Logical drift** | Reasoning contradicts the chosen action | Thinking validators enforce construct-action coherence |
| **Context overflow** | Can't dump full history into prompt | Weighted memory retrieval (top-k by recency + importance + context) |
| **Opaque decisions** | No audit trail for scientific review | Structured JSONL traces: input, reasoning, validation, outcome |
| **Unsafe mutation** | LLM modifies simulation state directly | Broker-gated execution: validated skills run by engine, not LLM |

---

## Quick Start

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/download) for local LLM inference (optional; mock mode available)

```bash
# 1. Clone and install
git clone https://github.com/WenyuChiou/WAGF.git
cd WAGF
pip install -e ".[llm]"

# 2. Try the mock demo (no Ollama needed)
python examples/quickstart/01_barebone.py
python examples/quickstart/02_governance.py

# 3. Run with a real LLM (requires Ollama)
ollama pull gemma3:4b
python examples/single_agent/run_flood.py --model gemma3:4b --years 3 --agents 10

# 4. Run the multi-agent flood experiment
cd examples/multi_agent/flood
python run_unified_experiment.py --model gemma3:4b --seed 42 --years 3 \
    --mode balanced --agent-profiles data/agent_profiles_balanced.csv --gossip
```

**Cloud LLM providers** (no local GPU needed):

```bash
--model anthropic:claude-sonnet-4-5    # requires ANTHROPIC_API_KEY
--model openai:gpt-4o                  # requires OPENAI_API_KEY
--model gemini:gemini-2.5-flash        # requires GOOGLE_API_KEY
```

### What Happens at Every Step

```text
Year 3, Agent #42 (low-income homeowner, high flood zone):

  LLM proposes: elevate_home (cost $30,000)
    Physical validator:  PASS  (not already elevated)
    Thinking validator:  ERROR — threat=Medium but chose costliest action
    → Retry with feedback: "Your threat assessment is Medium. Consider
      whether insurance ($1,200/yr) better matches your risk assessment."

  LLM proposes (retry 1): buy_insurance ($1,200/yr)
    Physical validator:  PASS
    Thinking validator:  PASS  (Medium threat → moderate action)
    Personal validator:  PASS  (income $35,000 > premium $1,200)
    Social validator:    WARNING — 70% of neighbors did nothing (logged)
    APPROVED → Executed by simulation engine

  Audit trace: year=3, agent=42, proposed=elevate_home, rejected,
               retry=1, final=buy_insurance, approved
```

---

## Architecture

```text
┌─────────────────────────────────────────────────┐
│                Governance Broker                 │
│                                                  │
│  1. Context Assembly (memory + state + social)   │
│  2. LLM Inference (any provider)                 │
│  3. Output Parsing (JSON/enclosure extraction)   │
│  4. Validation (Physical → Thinking → Personal   │
│                  → Social → Semantic)             │
│  5. Approve or Retry (with targeted feedback)    │
│  6. Execute + Audit                              │
│                                                  │
│  If step 4 returns ERROR → back to step 2       │
│  If step 4 returns WARNING → log and continue    │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│             Execution Environment                │
│                                                  │
│  Lifecycle: pre_year → agent decisions →         │
│             post_step → post_year → next year    │
│                                                  │
│  Domain config: skill_registry.yaml              │
│                 agent_types.yaml                  │
│                 lifecycle_hooks.py                │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│            Supporting Subsystems                  │
│                                                  │
│  Memory      Weighted retrieval, consolidation   │
│  Context     Tiered prompt (core/historic/recent)│
│  Social      Gossip, news media, social media    │
│  Reflection  Periodic LLM-driven consolidation   │
└─────────────────────────────────────────────────┘
```

**Key entry points:**

```text
broker/core/skill_broker_engine.py     — 6-stage governance pipeline
broker/core/experiment.py              — ExperimentRunner + Builder API
broker/validators/governance/          — 6 validator implementations
broker/components/memory/              — Memory engine ABC + implementations
broker/components/context/             — Context assembly chain
examples/quickstart/                   — Progressive tutorial
```

### Composable Agent Design

Build agents of varying cognitive complexity:

| Level | Add | Effect |
|:---|:---|:---|
| **Base** | Execution Engine | Can execute actions, no memory or reasoning |
| **+ Level 1** | Context + Window Memory | Bounded perception of recent events |
| **+ Level 2** | Weighted Memory | Emotional encoding, consolidation, decay |
| **+ Level 3** | Governance Broker | Decisions must pass domain rule validation |

---

## Case Studies

| Case Study | Agents | Period | LLM | Domain |
|:---|:---|:---|:---|:---|
| **Flood Household (SA)** | Single-agent | 13 years | Gemma 3 (4B/12B/27B) | Passaic River Basin, NJ |
| **Flood Multi-Agent (MA)** | 402 (200 owner + 200 renter + gov + ins) | 13 years | Gemma 3 4B | Passaic River Basin, NJ |
| **Irrigation** | 78 CRSS agents | 42 years | Gemma 3 4B, Ministral 3B, Gemma 3 12B | Colorado River Basin |

The flood experiments use per-agent flood depth grids from hydrological simulation (2011–2023). The irrigation experiment uses historical CRSS inflow data. Cross-model experiments compare 6+ LLM families across 3–5 random seeds.

| Surface | Description | Link |
|:---|:---|:---|
| **Quickstart** | Progressive tutorial | [Go](examples/quickstart/) |
| **Minimal Template** | Scaffold for a new domain | [Go](examples/minimal/) |
| **Single-Agent Flood** | Flood adaptation reference | [Go](examples/single_agent/) |
| **Irrigation ABM** | Water allocation reference | [Go](examples/irrigation_abm/) |
| **Multi-Agent Flood** | Institutional feedback reference | [Go](examples/multi_agent/flood/) |

---

## How WAGF Differs

| | WAGF | LangChain / LangGraph | AutoGen | Traditional ABM (PyCHAMP, NetLogo) |
|:---|:---|:---|:---|:---|
| Domain validation | 6-stage pipeline with typed feedback | No built-in domain validation | Agents validate via conversation | N/A (rule-based, no LLM) |
| LLM reasoning | Yes + governance constraints | Yes, unconstrained | Yes, unconstrained | No |
| Audit trail | Structured JSONL per decision | No standard format | Conversation logs | Varies |
| Theory enforcement | PMT / pluggable via YAML | None | None | Hardcoded equations |
| Retry with feedback | Targeted error → specific retry prompt | Generic retry | Re-conversation | N/A |
| Memory system | Weighted retrieval + consolidation + decay | Vector store retrieval | Shared context window | Static variables |
| Multi-agent institutions | Government → Insurance → Household | Generic agent roles | Generic agent roles | Predefined rules |

---

## Configuration & Extension

All domain-specific values load from YAML. Zero hardcoded domain logic in `broker/`.

| What You Want to Change | YAML Only | Python Required |
|:---|:---:|:---:|
| Add/remove skills (actions) | Yes | No |
| Define agent types & personas | Yes | No |
| Add/modify governance rules | Yes | No |
| Tune memory parameters | Yes | No |
| Change LLM model or provider | Yes | No |
| Add a new domain validator | No | Yes |
| Add a new memory engine | No | Yes |
| Add a new LLM provider | No | Yes |

**To add a new domain**, provide three files:
1. `skill_registry.yaml` — available actions and preconditions
2. `agent_types.yaml` — persona definitions, construct labels, governance rules
3. `lifecycle_hooks.py` — subclass `BaseLifecycleHooks` for environment transitions

### Programmatic API

```python
from broker.core.experiment import ExperimentBuilder
from broker.components.memory.engines.humancentric import HumanCentricMemoryEngine

runner = (
    ExperimentBuilder()
    .with_model("gemma3:4b")
    .with_years(13)
    .with_agents(agents)
    .with_simulation(sim_engine)
    .with_skill_registry("config/skill_registry.yaml")
    .with_governance("strict", "config/agent_types.yaml")
    .with_memory_engine(HumanCentricMemoryEngine(ranking_mode="weighted"))
    .with_seed(42)
    .build()
)
runner.run()
```

See [Customization Guide](docs/guides/customization_guide.md), [Experiment Design Guide](docs/guides/experiment_design_guide.md), and [Domain Pack Guide](docs/guides/domain_pack_guide.md).

---

## Documentation

**Getting Started**: [Quickstart Guide](docs/guides/quickstart_guide.md) | [Experiment Design](docs/guides/experiment_design_guide.md) | [Domain Packs](docs/guides/domain_pack_guide.md) | [Troubleshooting](docs/guides/troubleshooting_guide.md)

**Guides**: [Agent Assembly](docs/guides/agent_assembly.md) | [Customization](docs/guides/customization_guide.md) | [Multi-Agent Setup](docs/guides/multi_agent_setup_guide.md) | [Advanced Patterns](docs/guides/advanced_patterns.md) | [YAML Reference](docs/references/yaml_configuration_reference.md)

**Architecture**: [System Overview](docs/architecture/architecture.md) | [Skill Pipeline](docs/architecture/skill_architecture.md) | [Governance Core](docs/modules/governance_core.md) | [Memory System](docs/modules/memory_components.md)

**Theory**: [Theoretical Basis](docs/modules/00_theoretical_basis_overview.md) | [Skill Registry](docs/modules/skill_registry.md)

| I am a... | Start here |
|:---|:---|
| **Researcher** wanting to try it | [Quickstart](docs/guides/quickstart_guide.md) → [Examples](examples/README.md) → [Experiment Design](docs/guides/experiment_design_guide.md) |
| **Developer** extending the framework | [Architecture](docs/architecture/architecture.md) → [Customization](docs/guides/customization_guide.md) → [Domain Packs](docs/guides/domain_pack_guide.md) |

---

## Roadmap

- [ ] Structured function calling (replace text parsing for supported models)
- [ ] Async/parallel agent execution
- [ ] Web dashboard for experiment monitoring
- [ ] Additional domain packs: urban heat, drought, wildfire
- [ ] ODD protocol documentation generator

---

## How to Cite

```bibtex
@article{wagf2026,
  title={Water Agent Governance Framework: Governing LLM-Driven Agent-Based Models for Water Resources},
  author={Chiou, Wenyu and Yang, Y. C. Ethan},
  year={2026},
  note={Manuscript in preparation}
}
```

## References

1. Rogers, R. W. (1983). Cognitive and physiological processes in fear appeals and attitude change: A revised theory of protection motivation. *Social Psychophysiology*.
2. Grimm, V., et al. (2005). Pattern-oriented modeling of agent-based complex systems. *Science*, 310(5750), 987-991.
3. Park, J. S., et al. (2023). Generative Agents: Interactive Simulacra of Human Behavior. *ACM CHI*.
4. Hung, C.-L. J., & Yang, Y. C. E. (2021). Assessing adaptive irrigation impacts on water scarcity in nonstationary environments. *Water Resources Research*, 57(7).
5. Bubeck, P., Botzen, W. J. W., & Aerts, J. C. J. H. (2012). A review of risk perceptions and other factors that influence flood mitigation behavior. *Risk Analysis*, 32(9), 1481-1495.

---

## License

MIT
