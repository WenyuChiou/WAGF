# Model state in prompts and checks

This guide explains how values from your world model reach an agent's prompt, how physical checks and `expression:` rules read them, and how to see a rule block under `--model mock`.

## 1. World value to prompt

Each step, the runner calls `sim_engine.advance_step()` (or `advance_year()`) to produce the `env` dict. It then calls your `pre_year` or `pre_step` hook (`broker/core/experiment_runner.py (ExperimentRunner.run)`).

Copy world values into `agent.dynamic_state[key]` inside that hook:

- `TieredContextBuilder` copies scalar values (`str`, `int`, `float`, `bool`) from `agent.dynamic_state` into `context["personal"]` and `context["state"]`.
- `TieredContextBuilder.format_prompt` then copies those scalar values into `template_vars` before formatting the prompt (`broker/components/context/tiered.py (TieredContextBuilder.build, TieredContextBuilder.format_prompt)`).
- Scalar entries on `environment_context` also flatten into `template_vars` if no earlier key set them, while writing `agent.dynamic_state[key]` updates the agent's own state tier and takes precedence.

Wire your hook through the `hooks` slot under `global_config.run` (`broker/run/_entry.py (_build_runner)`). The slot table and a full `run:` block are in [HOW_TO_ADD_A_NEW_DOMAIN.md](HOW_TO_ADD_A_NEW_DOMAIN.md#running-a-case-python--m-brokerrun). Your slot function receives `ctx` (`broker/run/_entry.py (RunContext)`) and returns a dict of hook callables: `pre_year`, `pre_step`, `post_step`, `post_year`, `post_step_end`, and optional `after_run`. See `examples/reservoir_control/ops_case.py (build_hooks, sync_prompt_env)` and `examples/reservoir_control/config/reservoir_agent_types.yaml` for a working example.

If a prompt uses `{storage}` and nothing sets `"storage"` in `template_vars`, `SafeFormatter` renders `{storage}` as `[N/A]` (`broker/components/context/builder.py (SafeFormatter)`). Declare hook-filled placeholders under `shared.template_vars` or `<agent_type>.template_vars` in `agent_types.yaml` as a list of names or a mapping (`broker/tools/validate_prompt.py (collect_template_vars)`).

When you run `python -m broker.tools.validate_prompt`, it extracts single-brace placeholders from the prompt (`broker/tools/validate_prompt.py (extract_placeholders, validate_agent_type)`). It prints a `WARN` (exiting 0 unless `--strict` is set) for any placeholder not in `BROKER_FILLED_PLACEHOLDERS`, DomainPack extensions, `response_format.fields`, or `template_vars`, noting that `SafeFormatter` will render it as `[N/A]`.

Declaring `template_vars` only informs static validation. Your hook still must fill `agent.dynamic_state[key]` at runtime.

```python
# hooks.py — wired via `global_config.run.hooks: hooks:build_hooks`
# with `shared.template_vars: [storage_now]` in agent_types.yaml.
def build_hooks(ctx):
    def on_pre_year(year, env, agents):
        for agent in agents.values():
            # Rounded for the prompt; checks still read the exact env["storage"].
            agent.dynamic_state["storage_now"] = round(env["storage"], 1)
    return {"pre_year": on_pre_year}
```

Round a value before it goes into the prompt: a raw float such as `236.41433141136787` costs tokens and invites the model to copy digits that mean nothing. The example stores the rounded value under a new name, `storage_now`. Under the world's own name (`storage`) the agent state and `env_state` would hold two different values for one key, and the checks would log the key-collision diagnostic from section 2 at every decision. A copy under the same name with the same value is not reported.

## 2. World value to a physical check

During each decision, `SkillBrokerEngine.process_step` builds `validation_context` and passes it to every validator in `SkillBrokerEngine._run_validators` (`broker/core/skill_broker_engine.py (SkillBrokerEngine.process_step, SkillBrokerEngine._run_validators)`):

| Key | Value |
|---|---|
| `"agent_state"` | The context dict returned by `context_builder.build(...)` |
| `"agent_type"` | The agent's type string (`"base_type"` is also added in `_run_validators` when available) |
| `"env_state"` | `env_context`, the world-state dict for this step |
| `*flat_state` | Flattened scalar keys from `context.get("state", {})` |
| `*flat_env` | Flattened keys from `env_context` |
| `"proposed_magnitude"` | Present when `skill_proposal.magnitude_pct` is not `None` |
| `"proposed_parameters"` | Present when `skill_proposal.parameters` is non-empty |
| `"_frozen_construct_labels"` | Present when `global_config.governance.appraisal_freeze` is true |

World state lives in `context["env_state"]`. The agent's own state lives in `context["agent_state"]["state"]` (also unwrapped by `broker/governance/expression_condition.py (agent_state_from_context)`).

If the agent's `state` and `env_context` share a key name with different values, Python debug mode (`__debug__`) logs the warning `[Governance:Diagnostic] Key collision in validation context: ... env_context takes precedence. Consider using distinct key names.` (`broker/core/skill_broker_engine.py (SkillBrokerEngine.process_step)`). Because `validation_context` unpacks `flat_state` before `flat_env`, the world value overwrites the agent's value at the top level of `validation_context`. Give world and agent fields distinct names, or read `context["env_state"]` and `context["agent_state"]["state"]` directly in your checks.

Wire case-local checks through `global_config.run.validators` (`broker/run/_entry.py (_build_runner)`). `ValidatorRegistry` `"physical"` checks also receive this same `context` dict.

```python
# checks.py — wired via `global_config.run.validators: checks:build_validators`
from broker.interfaces.skill_types import ValidationResult

def check_min_storage(proposal, context, skill_registry):
    storage = context.get("env_state", {}).get("storage")
    if proposal and proposal.skill_name == "release_water" and storage is not None and storage < 6.0:
        return ValidationResult(
            valid=False, validator_name="min_storage",
            errors=["Release blocked: storage is below 6.0."],
            metadata={"rule_id": "min_storage", "deterministic": True},
        )
    return ValidationResult(valid=True, validator_name="min_storage")

def build_validators(ctx):
    return [check_min_storage]
```

## 3. `expression:` rules

In `thinking_rules`, an `expression:` condition runs an arithmetic comparison over world values and `proposed_magnitude` (`broker/governance/expression_condition.py (lookup_world_variable, evaluate_expression_condition)`).

With the default `scope: auto`, variable lookup checks `context["env_state"]` first, then the agent's `state` (`broker/governance/rule_types.py (RuleCondition)`), and then the flattened `context` (where `proposed_magnitude` lives). Setting `scope: env` or `scope: state` restricts the lookup to that single plane. A missing variable stops the rule from firing and records a `world_variable_missing` warning.

See the `expression` row in [yaml_configuration_reference.md](../references/yaml_configuration_reference.md#245-rulecondition-evaluation-advanced) for operators and evaluation details.

Put the rule under the governance profile the run uses, which is `global_config.run.governance` (or `--governance`). A case made by `broker.tools.scaffold_domain` runs `governance: default`, so its rules go under `<agent_type>: governance: default: thinking_rules:` (the scaffold's agent type is `agent`). `expression:` works in any profile, not only `strict`.

```yaml
# Under an agent type's `governance: <profile>:` block,
# e.g. `governance: strict:` in reservoir_agent_types.yaml.
thinking_rules:
  - id: flood_control_overflow
    conditions:
      - expression: "storage_now > 20.0 and proposed_magnitude < 1"
    blocked_skills: [set_release]
    level: ERROR
    message: "Storage is above 20.0; release the full amount (1.0)."
```

## 4. Seeing a block with the mock model

The stock mock (`--model mock`) searches the prompt for numbered options using `r'(\d+)\.\s+\w+'`, picks the first match (or `1` if none matches), and returns `{"decision": decision_id}` with no construct labels or numeric `magnitude` (`broker/utils/llm_utils.py (create_llm_invoke)`). Because `{options_text}` numbers eligible skills starting at `1.`, the stock mock always picks option 1.

To see a rule block under `--model mock`, use one of two options:

1. In a physical-only config (`psychological_framework: none`, with no required construct or numeric fields), list the unsafe skill first in `actions:` and `skill_registry.yaml` so option 1 triggers the rule.
2. Supply a scripted responder through `global_config.run.mock` (`broker/run/_entry.py (_slot_factory, _mock_invokes)`). When `is_mock_model(ctx.model)` is true (`broker/utils/llm_utils.py (is_mock_model)`), `broker.run` calls your factory with `ctx` and expects a callable `prompt -> (text, LLMStats)` or `{agent_type: callable}`, as in `examples/reservoir_control/ops_case.py (operator_mock, scripted_operator)`.

```python
# mock.py — wired via `global_config.run.mock: mock:build_mock`
import json
from broker.utils.llm_utils import LLMStats

def build_mock(ctx):
    def respond(prompt):
        # New cases declare the action number on [0, 1]; 50 or 100 would be
        # clamped to 1.0 by the parser.
        mag = 0.5 if "BLOCKED" in prompt else 1.0
        return json.dumps({"decision": 1, "magnitude": mag}), LLMStats(success=True)
    return respond
```

## 5. A current limit

`ExperimentRunner.run` builds one `env` dict at the start of each step by calling `sim_engine.advance_step()` (or `advance_year()`). Every agent in that step (within the same phase) is checked against that same `env` dict (`broker/core/experiment_runner.py (ExperimentRunner.run, _run_agents_sequential, _run_agents_parallel)`).

In practice, two agents drawing on one reservoir in the same step are each checked against the same starting `storage`. Neither agent's validator sees the other agent's pending withdrawal during that step.

```python
# Step 1: advance_step() runs once, so Agent A and Agent B both see storage=8.0.
env = sim_engine.advance_step()  # {"current_year": 1, "storage": 8.0}
for agent in phase_agents:
    # Each agent's validation_context["env_state"] receives this same env dict.
    broker.process_step(agent.id, step_id, run_id, seed, llm_invoke, env_context=env)
```
