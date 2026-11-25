# WAGF Domain Templates (`templates/`)

Clean, standalone starter templates designed to be copied and adapted when building a new governed simulation case with `python -m broker.run`.

Unlike the research paper benchmarks under `examples/`, files here carry zero historical experiment flags or legacy migration notes.

## Available Templates

| Template | Purpose | Command |
|---|---|---|
| [water_starter/](water_starter/README.md) | Minimal governed 1-reservoir water-release template demonstrating `broker.run`, prompt validation, and a dead-pool physical rule block -> retry -> repair loop | `python -m broker.run templates/water_starter/config/agent_types.yaml --model mock --years 2 --output .tmp/starter-run` |

## Alternative: CLI Domain Generator

If you prefer generating the files from a domain name and skill names, use the scaffolder CLI instead of copying a folder:

```bash
python -m broker.tools.scaffold_domain my_domain --skills skill_a,skill_b --output my_domain
```

See [User Manual](../docs/index.md) and [How to Add a New Domain](../docs/guides/HOW_TO_ADD_A_NEW_DOMAIN.md) for the full workflow.
