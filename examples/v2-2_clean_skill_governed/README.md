# Skill-Governed Flood Adaptation Experiment (v2-2 Clean)

This experiment demonstrates the **Generic Governed Broker Framework** applied to flood adaptation. All domain logic is isolated in configuration files (YAML/CSV), with the experiment code using only generic framework modules.

## Architecture: Experiment ↔ Framework Separation

| Layer | Experiment-Specific | Framework (Generic) |
|-------|---------------------|---------------------|
| **Agents** | `agent_initial_profiles.csv` | `agents.base_agent.BaseAgent` |
| **State** | CSV columns (dynamic) | `simulation.state_manager.SharedState` |
| **Skills** | `skill_registry.yaml` | `broker.skill_registry.SkillRegistry` |
| **Prompts** | `agent_types.yaml` | `broker.context_builder.create_context_builder` |
| **Validation** | `coherence_rules` in YAML | `validators.AgentValidator` |
| **Execution** | `FloodSimulation` (inherits) | `simulation.BaseSimulationEngine` |

## Validation (PMT Coherence)

The experiment uses **label-based coherence rules** defined in `agent_types.yaml`:

```yaml
coherence_rules:
  urgency_check:
    construct: TP          # Threat Appraisal
    when_above: ["H"]      # If label is High
    blocked_skills: ["do_nothing"]
    message: "High Threat but chose inaction"
```

**Validation Flow:**
1. LLM outputs `Threat Appraisal: High because...`
2. Parser extracts `TP = 'H'`
3. Validator checks: if `TP in ['H']` AND `decision in ['do_nothing']` → **Invalid**
4. Broker triggers retry with error message

## Data Input/Output

### Input Files
| File | Format | Purpose |
|------|--------|---------|
| `agent_initial_profiles.csv` | CSV | Agent profiles (any columns auto-available in prompts) |
| `flood_years.csv` | CSV | Years with flood events |
| `agent_types.yaml` | YAML | Prompt templates, validation rules, actions |
| `skill_registry.yaml` | YAML | Skill definitions and execution mappings |

### Output Files
| File | Location | Purpose |
|------|----------|---------|
| `experiment.log` | `results/<model>/` | High-level simulation log |
| `audit_trace.jsonl` | `results/<model>/` | Detailed decision trace |
| `audit_summary.json` | `results/<model>/` | Aggregated statistics |
| `comparison_results.png` | `results/<model>/` | Visualization |

## Running the Experiment

```bash
# Full experiment (100 agents, 10 years)
python run_experiment.py --model llama3.2:3b --num-agents 100 --num-years 10

# Quick validation test
python run_experiment.py --model mock --num-agents 50 --num-years 1

# With custom output directory
python run_experiment.py --model llama3.2:3b --output-dir results/my_run
```

## Adding New Agent Attributes

1. Add column to `agent_initial_profiles.csv` (e.g., `income`)
2. Use in prompt template: `Your income is {income}`
3. No code changes required ✅

## Framework Module Independence

The experiment code (`run_experiment.py`) imports ONLY from:
- `agents.base_agent` (generic agent)
- `simulation.state_manager` (generic state)
- `broker.*` (generic broker components)
- `validators.*` (generic validation)

**No framework files are modified for this experiment.**
