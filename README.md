# WAGF — Water Agent Governance Framework

<div align="center">

**A governance layer for LLM-driven agent-based models in coupled human-water systems.**

Every LLM decision passes through a validation pipeline — domain rules, behavioral theory checks, and retry with targeted feedback — before it can modify simulation state.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://github.com/WenyuChiou/WAGF/actions/workflows/test.yml/badge.svg)](https://github.com/WenyuChiou/WAGF/actions/workflows/test.yml)
[![Ollama](https://img.shields.io/badge/Ollama-Local_Inference-000000?style=flat&logo=ollama&logoColor=white)](https://ollama.com/)

[**English**](README.md) | [**中文**](README_zh.md)

</div>

## What is WAGF?

WAGF is a governance layer for LLM-driven agent-based models. A **Governance Broker** validates every LLM decision against physical constraints, behavioral theories, and financial feasibility before execution. Invalid decisions trigger a retry loop with specific feedback — not just re-prompting. The result: auditable, reproducible agent behavior instead of raw LLM output.

The framework ships with two water-sector reference implementations (flood adaptation and irrigation management) and can be extended to other ABM domains through a plugin system.

## Key Features

- **Governance Pipeline** — 6-stage validation before any action reaches the simulation: Context → LLM → Parse → Validate → Approve/Retry → Execute
- **Full Audit Trail** — Every decision, rejection, retry, and reasoning trace logged as structured JSONL/CSV for scientific review
- **Domain Packs** — Add a new domain with 3 files: `skill_registry.yaml` + `agent_types.yaml` + `lifecycle_hooks.py`
- **Pluggable Behavioral Theory** — Ships with Protection Motivation Theory (PMT); swap or extend via YAML configuration
- **Research Ready** — Ablation modes (strict/relaxed/disabled), cross-model comparison across 6+ LLM families, multi-seed reproducibility
- **AI-assisted Workflow** — 5 bundled [Claude Code skills](docs/skills/wagf-skills.md) (`wagf-quickstart`, `wagf-experiment-designer`, `llm-agent-audit-trace-analyzer`, `model-coupling-contract-checker`, `abm-reproducibility-checker`) walk a new researcher from `git clone` to paper-ready metrics without reading the manual first

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

### AI-assisted setup (recommended for first-time users)

Open this repo in [Claude Code](https://claude.ai/code) and say:

> "I just cloned WAGF, help me set this up."

The `wagf-quickstart` skill walks you through environment check, a
2-minute smoke test, and your first experiment in ~10 minutes (plus
LLM run time). Four additional skills cover the full research
lifecycle:

| Need | Skill |
|------|-------|
| Plan an experiment | `wagf-experiment-designer` |
| Analyse audit traces | `llm-agent-audit-trace-analyzer` |
| Verify external-model coupling | `model-coupling-contract-checker` |
| Pre-submission audit | `abm-reproducibility-checker` |

See [`docs/skills/wagf-skills.md`](docs/skills/wagf-skills.md) for the
full chooser. The skills are bundled in `.claude/skills/` and load
automatically when you open the repo in Claude Code.

### Manual setup

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/download) for local LLM inference (optional; mock mode available)

```bash
# Clone and install
git clone https://github.com/WenyuChiou/WAGF.git
cd WAGF
pip install -e ".[llm]"

# Try the mock demo (no Ollama needed)
python examples/quickstart/01_barebone.py

# Run with a real LLM
ollama pull gemma3:4b
python examples/single_agent/run_flood.py --model gemma3:4b --years 3 --agents 10
```

**Cloud LLM providers** (no local GPU needed):

```bash
--model anthropic:claude-sonnet-4-5    # requires ANTHROPIC_API_KEY
--model openai:gpt-4o                  # requires OPENAI_API_KEY
--model gemini:gemini-2.5-flash        # requires GOOGLE_API_KEY
```

### What Happens at Every Step

A concrete trace from the flood simulation:

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

![WAGF Architecture](docs/architecture.png)

The framework operates in three layers:

1. **LLM Layer** — Agents propose actions via natural-language reasoning
2. **Governed Layer** — Parser extracts structured output; Validator checks domain rules; Auditor logs traces. If validation fails (ERROR), the proposal returns to the LLM with targeted feedback
3. **Execution Layer** — Approved actions modify the environment; Memory and Reflection feed back into the next decision cycle

**Key entry points:**

```text
broker/core/skill_broker_engine.py     — 6-stage governance pipeline
broker/core/experiment.py              — ExperimentRunner + Builder API
broker/validators/governance/          — 6 validator implementations
broker/components/memory/              — Memory engine ABC + implementations
broker/components/context/             — Context assembly chain
broker/components/cognitive/           — Reflection engine + cognitive trace
broker/components/governance/          — Skill registry + temporal_rules/
examples/quickstart/                   — Progressive tutorial
```

### Reflection Module

Year-end reflection consolidates recent memories into structured insights,
which are written back into agent memory at `emotion="major"` and surface in
subsequent retrievals. Reflection is YAML-driven — present-moment reflection
questions, multi-modal triggers (crisis / periodic / post-decision /
institutional change), and reflection interval are defined per domain in
`agent_types.yaml` under `global_config.reflection`. Three present-moment
question types cover risk salience, social comparison, and cost-safety
trade-offs.

The framework reserves a fourth dimension — **temporal coherence** — for
conditional extension: when a sequence-level rule (M1 appraisal-history
coherence, M2 behavioural inertia, or M3 evidence-grounded irreversibility)
triggers, a targeted temporal question is injected into the agent's
reflection prompt. In the current release these temporal questions are
specified at the design level but not live-injected; empirical evaluation is
reserved for follow-up work. See `broker/components/cognitive/reflection.py`
for the engine, `broker/components/governance/temporal_rules/` for the
sequence-level rule framework, and `.ai/reflection_taxonomy_design_2026-04-19.md`
for the full design specification.

### Composable Agent Design

Build agents of varying cognitive complexity for controlled experiments:

| Level | Add | Effect |
|:---|:---|:---|
| **Base** | Execution Engine | Can execute actions, no memory or reasoning |
| **+ Level 1** | Context + Window Memory | Bounded perception of recent events |
| **+ Level 2** | Weighted Memory | Emotional encoding, consolidation, decay |
| **+ Level 3** | Governance Broker | Decisions must pass domain rule validation |

Run Level 1 (no governance) vs Level 3 (full governance) to isolate the effect of validation on agent behavior.

---

## Reference Implementations

| Case Study | Agents | Period | Models Tested | Study Area |
|:---|:---|:---|:---|:---|
| **Flood Household** | Single-agent | 13 years | Gemma 3 (4B/12B/27B) | Passaic River Basin, NJ |
| **Flood Multi-Agent** | 402 (200 owner + 200 renter + gov + ins) | 13 years | Gemma 3 4B | Passaic River Basin, NJ |
| **Irrigation** | 78 CRSS agents | 42 years | Gemma 3 4B, Ministral 3B, Gemma 3 12B | Colorado River Basin |

The flood experiments use per-agent flood depth grids from hydrological simulation (2011–2023). The irrigation experiment reproduces the Hung & Yang (2021) Colorado River Simulation System setup with LLM-driven farmer agents. Cross-model experiments compare behavior across LLM families and sizes with 3–5 random seeds per configuration.

| Example | Description | Link |
|:---|:---|:---|
| **Quickstart** | Progressive tutorial for the governance loop | [Go](examples/quickstart/) |
| **Minimal Template** | Scaffold for adding a new domain | [Go](examples/minimal/) |
| **Single-Agent Flood** | Flood adaptation with PMT | [Go](examples/single_agent/) |
| **Irrigation ABM** | Water allocation under scarcity | [Go](examples/irrigation_abm/) |
| **Multi-Agent Flood** | Institutional feedback (gov + ins + household) | [Go](examples/multi_agent/flood/) |

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
