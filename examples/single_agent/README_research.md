# Single-Agent Flood Reference Implementation

This directory is the primary single-agent flood reference implementation in
WAGF.

It is the main single-agent water-sector benchmark for:

- PMT-governed household decisions
- ablation across governance and memory settings
- long-horizon flood adaptation behavior
- audit-based validation and stress testing

This is the developer-facing entry README. The longer research-oriented
validation narrative is preserved in:

- [README_research.md](README_research.md)

---

## What This Pack Covers

Core runtime surfaces live here:

- [run_flood.py](run_flood.py): main runnable entrypoint
- [agent_types.yaml](agent_types.yaml): agent config, parsing, governance, memory
- [skill_registry.yaml](skill_registry.yaml): available flood adaptation skills
- [config/prompts/](config/prompts/): prompt templates
- [analysis/](analysis/): post-run metrics and paper-side analysis helpers
- [results/](results/): experiment outputs

---

## Start Here

If you are an ABM developer, use this order:

1. Read [skill_registry.yaml](skill_registry.yaml)
2. Read [agent_types.yaml](agent_types.yaml)
3. Read [run_flood.py](run_flood.py)
4. Run a short smoke experiment

---

## Minimal Run

```bash
python examples/single_agent/run_flood.py --model gemma3:4b --agents 5 --years 3
```

Default outputs stay inside this workspace under:

- `examples/single_agent/results/`

---

## Configuration Surface

These are the files most users need first:

| File | Why it matters |
| :--- | :--- |
| `skill_registry.yaml` | Defines the available household actions |
| `agent_types.yaml` | Defines PMT constructs, parsing, governance, and memory |
| `config/prompts/household.txt` | Main household prompt |
| `run_flood.py` | Shows how the experiment is assembled |

If you want to adapt this pack to another single-agent ABM, start by editing the
YAML and prompt surfaces before touching the runner.

---

## Study Modes

The main experiment modes are:

- benchmark / ablation runs through [run_flood.py](run_flood.py)
- survey-driven initialization through `--survey-mode`
- stress testing through `run_stress_marathon.ps1`

This directory contains both production-style runs and paper-analysis helpers.
For the full academic framing, hypotheses, and validation details, read
[README_research.md](README_research.md).

---

## Scope Boundary

This directory is the primary single-agent flood benchmark.

It is not the irrigation workspace, and it is not the multi-agent flood paper
workspace. Related locations:

- Single-agent irrigation reference: [examples/irrigation_abm/](/c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/irrigation_abm)
- Multi-agent flood reference: [examples/multi_agent/flood/](/c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/multi_agent/flood)
- Nature Water manuscript workspace: [paper/nature_water/](/c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/paper/nature_water)

---

## Developer Notes

- This runner is still research-oriented and fairly large.
- `analysis/` contains both reusable metrics code and paper-side helper scripts.
- `results/` contains benchmark outputs and should be treated as experiment data,
  not framework core.
- The flood compact demo lives separately in [examples/governed_flood/](/c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/governed_flood).
