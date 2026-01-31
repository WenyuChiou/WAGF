# Irrigation ABM Experiment — Hung & Yang (2021) LLM Adaptation

LLM-driven reproduction of the Colorado River Basin irrigation ABM from Hung & Yang (2021, *Water Resources Research*). 78 agricultural water users make annual demand decisions using language model reasoning instead of Q-learning (FQL).

## Three Pillars

| Pillar | Name | Configuration | Effect |
|--------|------|---------------|--------|
| 1 | **Strict Governance** | Water rights, curtailment caps, efficiency checks | Blocks physically impossible or redundant actions |
| 2 | **Cognitive Memory** | `HumanCentricMemoryEngine` + year-end reflection | Emotional encoding of droughts and outcomes |
| 3 | **Priority Schema** | Water situation enters context before preferences | Physical reality anchors LLM reasoning |

## Quick Start

```bash
# Smoke test (5 synthetic agents, 5 years)
python run_experiment.py --model gemma3:4b --years 5 --agents 5

# Validation (10 synthetic agents, 10 years)
python run_experiment.py --model gemma3:4b --years 10 --agents 10 --seed 42

# Production (78 real CRSS agents, 42 years — requires ref/CRSS_DB data)
python run_experiment.py --model gemma3:4b --years 42 --real --seed 42
```

## Behavioral Clusters

Three k-means clusters from Hung & Yang (2021) Section 4.1, mapped from FQL parameters to LLM personas:

| Cluster | FQL mu/sigma | LLM Persona | Governance Effect |
|---------|-------------|-------------|-------------------|
| **Aggressive** | 0.36/1.22 | Bold, large demand swings | Low regret sensitivity |
| **Forward-looking Conservative** | 0.20/0.60 | Cautious, future-oriented | High regret sensitivity |
| **Myopic Conservative** | 0.16/0.87 | Tradition-oriented, slow updates | Status quo preference |

## Available Skills

| Skill | Description | Constraints |
|-------|-------------|-------------|
| `increase_demand` | Request more water allocation | Blocked at allocation cap |
| `decrease_demand` | Request less allocation | Always available |
| `adopt_efficiency` | Invest in drip/precision irrigation | One-time only |
| `reduce_acreage` | Fallow farmland to lower requirement | Always available |
| `maintain_demand` | No change to practices | Default action |

## Governance Rules (Strict Profile)

| Rule | Severity | Trigger |
|------|----------|---------|
| `high_threat_no_maintain` | ERROR | WSA=VH blocks `maintain_demand` |
| `low_coping_block_expensive` | ERROR | ACA=VL blocks `adopt_efficiency` |
| `low_threat_no_increase` | ERROR | WSA in {VL,L} blocks `increase_demand` |
| `water_right_cap` | ERROR | At allocation cap blocks `increase_demand` |
| `already_efficient` | ERROR | Has efficient system blocks `adopt_efficiency` |

## Output Files

```
results/<run_name>/
  simulation_log.csv                     # Year, agent, skill, constructs
  irrigation_farmer_governance_audit.csv # Governance interventions
  governance_summary.json                # Aggregate audit stats
  config_snapshot.yaml                   # Reproducibility snapshot
  raw/irrigation_farmer_traces.jsonl     # Full LLM traces
  reflection_log.jsonl                   # Memory consolidation events
```

## Project Structure

```
irrigation_abm/
  run_experiment.py          # Main runner (ExperimentBuilder pipeline)
  irrigation_env.py          # Water system simulation environment
  irrigation_personas.py     # Cluster persona builder + context helpers
  config/
    agent_types.yaml         # Agent config, governance rules, personas
    skill_registry.yaml      # Available irrigation skills
    policies/                # Domain-specific governance policies
    prompts/                 # LLM prompt templates
  validators/
    irrigation_validators.py # 7 custom governance validators
  learning/
    fql.py                   # Reference FQL algorithm (not used by LLM runner)
```

## Reference

Hung, F., & Yang, Y. C. E. (2021). Assessing adaptive irrigation impacts on water scarcity in nonstationary environments — A multi-agent reinforcement learning approach. *Water Resources Research*, 57, e2020WR029262.
