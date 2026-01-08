# Governed Broker Framework Examples

This directory contains example experiments demonstrating the Governed Broker Framework.

## Examples

| Example | Description | Agent Types | Key Features |
|---------|-------------|-------------|--------------|
| [`single_agent/`](./single_agent/) | Flood Adaptation | Households (100) | PMT coherence validation, skill-based decisions |
| [`multi_agent/`](./multi_agent/) | Multi-Agent ABM | Households + Insurance + Government | Agent-agent interaction, institutional policies |

---

## Single-Agent Example

The **single_agent** example demonstrates:
- 100 household agents making flood adaptation decisions
- PMT (Protection Motivation Theory) coherence validation
- Skill-based architecture with validation-retry loop
- Dynamic data loading from CSV (agent profiles, flood years)

```bash
cd single_agent
python run_experiment.py --model llama3.2:3b --num-agents 100 --num-years 10
```

---

## Multi-Agent Example

The **multi_agent** example demonstrates:
- Multiple agent types: Household, Insurance Company, Government
- Agents observe and respond to each other
- Institutional state management with write access control
- Policy feedback loops

```bash
cd multi_agent
python run_experiment.py --model llama3.2:3b --num-years 10
```

---

## Quick Start (Both Examples)

```bash
# Test with mock LLM (fast, no GPU required)
python run_experiment.py --model mock --num-years 1

# Run with Ollama
python run_experiment.py --model llama3.2:3b --num-years 10

# Custom output directory
python run_experiment.py --model llama3.2:3b --output-dir results/my_run
```

---

## Example Structure

Each example follows the same structure:

```
example_name/
├── README.md              # Example-specific documentation
├── run_experiment.py      # Main experiment script
├── agent_types.yaml       # Agent definitions, prompts, validation rules
├── skill_registry.yaml    # Skill definitions
├── *.csv                  # Data files (agent profiles, events)
└── results/               # Output directory (created on run)
```

---

## Creating Your Own Example

1. Copy an existing example directory
2. Modify `agent_types.yaml` for your domain
3. Update `skill_registry.yaml` with domain skills
4. Adjust CSV data files as needed
5. Customize `run_experiment.py` simulation logic

**No framework code changes required** - all configuration is in YAML/CSV.
