# Water modelling reference

Setup, rule semantics and reproducibility details for water-modelling studies. Start with the [mock water tutorial](../tutorial/README.md) for a first run with the built-in mock model.

## Check your Python setup

Use the same Python interpreter for installation and runs. On macOS/Linux,
`python3` may be the available command; use it consistently in place of `python`.
After the [quickstart installation](../../README.md#quickstart), check the imports:

```bash
python -c "import broker; from broker.core.experiment import ExperimentBuilder; print('WAGF imports OK')"
```

## Core concepts

| Stage | What it does | Read more |
|---|---|---|
| Context Builder | Collects the agent's attributes, current water conditions, available actions and recalled experience. | [Context system](../../docs/modules/context_system.md) |
| LLM | Reads the prompt and proposes an action, with its assessment of the situation, such as how severe the shortage is. | [Configuration](../../docs/references/yaml_configuration_reference.md) |
| Governance: Parser | Reads the response into the action fields required by the domain. | [Governance core](../../docs/modules/governance_core.md) |
| Governance: Validator | Checks that the action is feasible and fits the assessment; if a blocking rule fails, the model is asked again. | [Governance guide](../../docs/guides/governance_layers.md) |
| Governance: Auditor | Records parsing, validation and retry outcomes. | [Audit schema](../../docs/AUDIT_SCHEMA.md) |
| Environment and Execution | Applies the final action and updates water conditions and agent state. | [Simulation engine](../../docs/modules/simulation_engine.md) |
| Memory and Retrieval | Stores experience and selects it for later prompts. | [Memory guide](../../docs/modules/memory_components.md) |
| Reflection | Optionally summarises past experience into lessons. | [Reflection guide](../../docs/modules/reflection_engine.md) |

See [ARCHITECTURE.md](../../ARCHITECTURE.md) for the design and [broker/INVARIANTS.md](../../broker/INVARIANTS.md) for required behaviour.

- The `strict` profile applies the domain's configured rules. A profile named `disabled` can still retain checks; irrigation keeps its water-right, minimum-use and beneficial-use limits (its `identity_rules`) under `disabled`.
- ERROR findings block a proposal; WARNING findings do not. A rejected proposal is retried up to the configured limit; see [configuration](../../docs/references/yaml_configuration_reference.md) for retry feedback.
- When retries run out, the domain's default action runs without a further check. The opt-in `keep_proposal` setting runs the rejected proposal itself instead, unless a rule that blocked it is marked as a hard limit, in which case the default action runs. The setting is refused when a coupled model is enabled; see [invariants](../../broker/INVARIANTS.md).
- A `CouplingContract` lists each value exchanged with your model, with its unit, allowed range and timing. WAGF checks values against the declared range; it does not convert units or check a conversion.
- The irrigation example implements its water balance within its domain. Its model is a simplified stand-in for CRSS, the Bureau of Reclamation's Colorado River Simulation System, not CRSS itself.

## Local and cloud models

Install the optional model and analysis packages. Install and start Ollama, a free program that runs language models on your own computer (https://ollama.com), then download a model:

```bash
python -m pip install -e ".[llm,analysis]"
ollama pull gemma3:4b
python examples/single_agent/run_flood.py --model gemma3:4b --years 3 --agents 10 --output results/flood_first_run
```

Expect yearly household decisions and `results/flood_first_run/simulation_log.csv`, `household_governance_audit.csv` and `raw/household_traces.jsonl`. Use a new output folder for each run. Speed and memory needs depend on your computer.

Thinking (extra reasoning output from models that support it) is off by default; add `--thinking-mode enabled` to request it. A few models cannot turn thinking off; WAGF notes this in the run manifest. See the [model configuration reference](../../docs/references/yaml_configuration_reference.md#214-global_configllm).

See the [flood manual](../../examples/single_agent/README.md) for inputs and outputs. Cloud models use `--model anthropic:<id>`, `openai:<id>` or `gemini:<id>`. Set `ANTHROPIC_API_KEY` for Anthropic, `OPENAI_API_KEY` for OpenAI or `GOOGLE_API_KEY` for Gemini. Cloud models also need the provider's own package: `python -m pip install anthropic`, `python -m pip install openai` or `python -m pip install google-generativeai`.

If it fails: see [Ollama troubleshooting](../../docs/guides/troubleshooting_guide.md#3-ollama-connection-issues); for a finished output folder, choose a new one.

## Start a water application

Generate a folder for your own decision model:

```bash
python -m broker.tools.scaffold_domain my_water_model --framework generic --skills "action_a,action_b"
```

Expect `Scaffolded` and `examples/my_water_model_demo/` with configuration, a prompt and a runner. `--skills` lists the actions an agent can choose; WAGF calls actions skills.

Replace the placeholder actions with your water decisions, then follow [Build your own domain](#build-your-own-domain) below. To connect an existing hydrological or water-system model, follow the [coupling guide](../../docs/COUPLING_CONNECTORS.md).

If it fails: for name errors, use lowercase letters and underscores; for an existing folder, choose another name.

## Build your own domain

After scaffolding your water application, check the prompt and run the generated model with scripted responses:

```bash
python -m broker.tools.validate_prompt examples/my_water_model_demo/config/agent_types.yaml
python examples/my_water_model_demo/run_experiment.py --model mock --years 1 --agents 1
```

The first command reports configuration errors and warnings. The second writes audit output under `examples/my_water_model_demo/results/smoke/`. The generated example is incomplete on purpose, so the run prints `Validation FAILED` and `Max retries (3) reached`. It worked if it ends with `Done. Audit + traces under: ...`.

To run it again, add `--output results/smoke2` (relative to `examples/my_water_model_demo/`) or delete `results/smoke/` first; WAGF refuses to overwrite a finished run.

Use the [new-domain guide](../../docs/guides/HOW_TO_ADD_A_NEW_DOMAIN.md) to supply model state, prompts, rules and action execution. Follow the [verification ladder](../../.claude/skills/wagf-verification-ladder/SKILL.md): environment, configuration, mock run, domain tests, real-model pilot, then acceptance before a larger study.

If you use an AI coding assistant such as Claude Code, the repository includes step-by-step guides for it, called skills; see [WAGF skills](../../docs/skills/wagf-skills.md) and [AI-assisted setup](../../docs/AI_ASSISTED_SETUP.md).

## Documentation

| You want to | Read |
|---|---|
| Understand the design and find files | [Architecture](../../ARCHITECTURE.md), [runtime architecture](../../docs/architecture/architecture.md), [repository map](../../docs/REPO_MAP.md) |
| Check framework constraints | [Broker invariants](../../broker/INVARIANTS.md) |
| Configure rules, prompts and model settings | [Configuration reference](../../docs/references/yaml_configuration_reference.md), [governance guide](../../docs/guides/governance_layers.md) |
| Design and validate a study | [Experiment design](../../docs/guides/experiment_design_guide.md), [calibration guide](../../docs/guides/calibration_guide.md) |
| Connect a model or add a domain | [Coupling](../../docs/COUPLING_CONNECTORS.md), [DomainPack](../../docs/guides/domain_pack_guide.md) |
| Use an AI coding assistant such as Claude Code with step-by-step guides, called skills | [Skills index](../../docs/skills/wagf-skills.md), [AI-assisted setup](../../docs/AI_ASSISTED_SETUP.md) |
| Analyse or recover a run | [Audit schema](../../docs/AUDIT_SCHEMA.md), [reproduction guide](../../reproduction/README.md), [irrigation replay runbook](../../examples/irrigation_abm/README.md#resuming-a-crashed-run) |
| Resolve errors or check changes | [Troubleshooting](../../docs/guides/troubleshooting_guide.md), [CHANGELOG](../../CHANGELOG.md) |

## Testing and reproducibility

Install the test dependencies and run the automated tests, excluding tests named `real_llm`. The automated tests also check the generated-domain workflow; see [.github/workflows/test.yml](../../.github/workflows/test.yml).

```bash
python -m pip install -r requirements.txt
python -m pip install -e ".[dev,web,analysis]"
python -m pytest tests/ broker/ examples/single_agent/tests -ra --tb=short --continue-on-collection-errors -k "not real_llm"
```

Runs write `reproducibility_manifest.json`, `config_snapshot.yaml` and `run_integrity.json` alongside the traces. Prompt files are referenced by path, not copied into the configuration snapshot; keep them with your run inputs. Record the code revision and retain the inputs: a seed alone does not make live language-model responses identical.

Optional columns record every attempt of a decision. The irrigation runner can also save each model call to a file and replay it to resume a crashed run; see the [irrigation replay runbook](../../examples/irrigation_abm/README.md#resuming-a-crashed-run).

Default traces do not retain every retry's complete prompt and response. The [audit schema](../../docs/AUDIT_SCHEMA.md) explains placeholders and proposed versus executed actions.

The comparison tool ignores timestamps, run times and the order of unordered lists; the recovery tool rebuilds CSVs from JSONL. Inspect their usage:

```bash
python -m broker.tools.compare_audit_csv --help
python -m broker.tools.recover_csv_from_jsonl --help
```

## Related publications

The household flood example builds on Yang and Chiou (2026):

```bibtex
@article{yang2026wrr,
  author  = {Yang, Y. C. Ethan and Chiou, Wenyu},
  title   = {Leveraging Large Language Models for Agent-Based Simulation of Human-Water System Interactions},
  journal = {Water Resources Research},
  year    = {2026},
  volume  = {62},
  number  = {6},
  pages   = {e2025WR042111},
  doi     = {10.1029/2025WR042111}
}
```

The irrigation example re-implements the irrigation decision setup of Hung and Yang (2021):

Hung, F., & Yang, Y. C. E. (2021). Assessing adaptive irrigation impacts on water scarcity in nonstationary environments — A multi-agent reinforcement learning approach. *Water Resources Research*, 57, e2020WR029262. <https://doi.org/10.1029/2020WR029262>
