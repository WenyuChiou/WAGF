# Quickstart Tutorial

Progressive introduction to the WAGF governance loop. No Ollama required.

## Scripts

| Script | What It Shows |
|--------|--------------|
| `01_barebone.py` | Core workflow: agent proposes → broker validates → engine executes |
| `02_governance.py` | Governance blocking: agent proposes invalid action → rejected → retry with feedback → approved |

## Run

```bash
# From project root
python examples/quickstart/01_barebone.py
python examples/quickstart/02_governance.py
```

Both scripts use a mock LLM (no external model needed). Output explains each step as it happens.

## Configuration

- `agent_types.yaml` — Agent persona, governance rules, response format
- `skill_registry.yaml` — Available actions and preconditions

## Next Steps

- [Experiment Design Guide](../../docs/guides/experiment_design_guide.md) — Run with real LLMs
- [Domain Pack Guide](../../docs/guides/domain_pack_guide.md) — Add your own domain
