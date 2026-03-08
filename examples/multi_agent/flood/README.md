# Multi-Agent Flood Reference Pack

This directory is the primary multi-agent water-sector reference implementation
in WAGF.

It demonstrates how to build an LLM-governed ABM with:

- heterogeneous agent types
- phase ordering across institutions and households
- shared environmental state
- social and media channels
- domain-specific governance and validation

This is a developer-facing entry README. The longer research-oriented
description of the Passaic River Basin study is preserved in:

- [README_research.md](README_research.md)
- [paper3/README.md](paper3/README.md)

---

## What This Pack Covers

Core runtime components live here:

- [run_unified_experiment.py](run_unified_experiment.py): main runnable entrypoint
- [config/](config/): agent types, skills, prompts, governance, parameters
- [orchestration/](orchestration/): factories and lifecycle hooks
- [environment/](environment/): hazard, depth, and environmental logic
- [components/](components/): media and supporting subsystems
- [memory/](memory/): memory-related utilities
- [ma_validators/](ma_validators/): multi-agent validation logic

Research packaging for the MA flood paper lives under:

- [paper3/](paper3/)

---

## Start Here

If you are an ABM developer, use this order:

1. Read [config/skill_registry.yaml](config/skill_registry.yaml)
2. Read [config/ma_agent_types.yaml](config/ma_agent_types.yaml)
3. Read [orchestration/lifecycle_hooks.py](orchestration/lifecycle_hooks.py)
4. Run [run_unified_experiment.py](run_unified_experiment.py)

---

## Minimal Run

```bash
python examples/multi_agent/flood/run_unified_experiment.py --mode random --agents 10 --years 3
```

Default outputs stay inside this workspace:

- `examples/multi_agent/flood/results_unified/`

---

## Configuration Surface

These are the files most users need to understand first:

| File | Why it matters |
| :--- | :--- |
| `config/skill_registry.yaml` | Defines available actions |
| `config/ma_agent_types.yaml` | Defines agent prompts, parsing, and governance |
| `config/information_visibility.yaml` | Controls information exposure by agent type |
| `config/prompts/*.txt` | Domain prompts per agent class |
| `config/parameters/floodabm_params.yaml` | Flood/environment model parameters |

If you want to adapt this pack to another multi-agent ABM, start by editing the
YAML files above before touching the runner.

---

## Modes

The runner supports multiple initialization modes:

- `survey`: initialize from survey-derived agents
- `random`: initialize synthetic agents quickly
- `balanced`: initialize from prepared balanced profiles

Balanced and paper-grade workflows depend on supporting assets under:

- [paper3/output/](paper3/output/)
- [data/](data/)

---

## Scope Boundary

This directory is a reusable water-sector multi-agent pack.

It is not the Nature Water manuscript workspace, and it is not the single-agent
flood benchmark. Related locations:

- Single-agent flood benchmark: [examples/single_agent/](../single_agent/)
- Nature Water manuscript workspace: [paper/nature_water/](/c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/paper/nature_water)
- MA flood paper workspace: [paper3/](paper3/)

---

## Developer Notes

- The current runner is still research-oriented and relatively large.
- `paper3/` contains the main WRR-oriented experiment package, validation, and
  analysis pipeline.
- Some docs under [docs/](docs/) are still research-facing rather than tutorial-facing.

For the full research framing, hypotheses, study area, and validation narrative,
read [README_research.md](README_research.md).
