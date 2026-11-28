# Writing retry feedback for governance rules

This guide is for a water modeller writing `thinking_rules` or
`identity_rules` for an agent. A blocking rule should tell the agent why its
judgment makes the proposed action unavailable and, when useful, what to
reconsider.

## 1. What the agent sees on a retry

With `global_config.governance.retry_feedback_mode: full`, the broker turns
each blocking result into an `InterventionReport`, renders at most
`max_reports_per_retry`, and places that feedback before the original prompt.
The renderer uses `plain` wording. Each report names the agent's choice and
gives the rule's reason. This example uses the irrigation rule
`high_scarcity_no_increase` from the executed variant and the flood rule
`relocation_threat_low`.

```text
Your previous answer cannot be used in this decision.

- You chose 'increase demand'. Under the rule on increases under scarcity, an increase is not available in this decision: at the start of this decision you judged water to be scarce this year, and a larger request when water is scarce draws more from a supply you share with other users.
- You chose 'relocate'. Under the rule on relocating without threat, relocating is not available in this decision: at the start of this decision you judged the flood threat to be low.

Please answer again, taking the information above into account.

Choose one action for this water-management decision.
```

An answer that could not be read gets the line `- Your answer could not be
read: it did not follow the required response format.` In `placebo` mode,
`plain` sends the header and the closer only. With `feasible_set_feedback`,
the list after the reasons reads `Actions that pass every rule in this
decision: …`. In `silent` mode the agent receives the original prompt.

## 2. Give every blocking rule one message

Put a `message` on every `level: ERROR` rule. Address the agent as “you,” name
the judgment it made, and explain why that judgment makes the action
unavailable. Keep an optional `suggestion` narrower: tell the agent what to
reconsider without dictating an unrelated answer.

For water YAML, thinking-rule suggestions are copied into the retry report.
Identity-rule suggestions are not currently forwarded by
`broker/utils/agent_config.py (AgentTypeConfig.get_identity_rules)`. A custom
validator can supply suggestion metadata through
`metadata["suggestion"]`, as the irrigation supply validator does. Only the rule message reaches the agent.

The irrigation thinking rules in
`examples/irrigation_abm/config/agent_types.yaml` show the pattern:

- `high_scarcity_no_increase`: “Demand increase blocked under the rule on
  increases under scarcity: at the start of this decision you judged water to
  be scarce this year, and a larger request when water is scarce draws more
  from a supply you share with other users.” Its suggestion says that an
  increase is unavailable in this decision.
- `low_scarcity_no_decrease`: “Demand decrease blocked under the rule on
  decreases without scarcity: at the start of this decision you judged that
  water is not scarce this year, and cutting your request when water is not
  scarce gives up water you could use for production.” Its suggestion says
  that a decrease is unavailable in this decision.

The `with_validator` and `without_validator` variants word the same two
rules without "blocked": "Under the rule on increases under scarcity, an
increase is not available in this decision: at the start of this decision you
judged water to be scarce this year, ..." (and the same form for decreases).

The irrigation limit rules in the same config use short messages because the
world state already settles the question:

- `water_right_cap`: “Increase not available: your request is already at your
  water right.”
- `beneficial_use_limit`: “Increase not available: your request is already at
  about the most water your fields can use.”
- `minimum_utilisation_floor`: “Decrease not available: your request is already
  at the minimum-use floor (10% of your water right).”

The supply rule is a custom validator rather than a YAML thinking rule. It puts
the agent's own values into the result before the report is rendered. With a
100,000 acre-ft keep request and 50,000 acre-ft expected delivery, the real
validator produced:

> Under the shortage-sharing rule, an increase is not available this year: if
> you request the 100,000 acre-ft you received last year, you can expect 50,000
> acre-ft this year (50.0%), because the water your sub-basin can draw this year, a fixed
> share of the natural flow of its rivers, is below the combined requests of
> its users, and the shortfall is shared in proportion to requests. When water
> is short it is shared in proportion to requests, so a larger request would
> raise your share only by lowering the deliveries of other users in your
> sub-basin; it would not add water to your sub-basin.

That formatting happens in
`examples/irrigation_abm/validators/irrigation_validators.py
(supply_gap_block_increase)`. The values come from
`supply_keep_request_af`, `supply_expected_at_keep_af`, and `supply_ratio` in
the validation context.

The flood rules in `examples/single_agent/agent_types.yaml` use the same
pattern. These are their exact messages:

- `extreme_threat_block`: “Under the rule on severe-threat response, doing
  nothing is not available in this decision: at the start of this decision you
  judged the flood threat to be high and your coping appraisal was not very low
  or low.”
- `relocation_threat_low`: “Under the rule on relocating without threat,
  relocating is not available in this decision: at the start of this decision
  you judged the flood threat to be low.”
- `elevation_threat_low`: “Under the rule on elevating without threat,
  elevating your house is not available in this decision: at the start of this
  decision you judged the flood threat to be low.”
- `observed_flood_low_threat_inaction` (`grounded_v1`): “Doing nothing is not
  available in this decision: a flood occurred this year, which your own low
  threat rating does not account for. Re-appraise the threat against what
  happened, then choose.”
- `elevation_block` (identity rule, all strict-type profiles): “Under the rule
  on a house already elevated, elevating your house again is not available:
  your house is already elevated.”

The first three rules and `elevation_block` also carry the exact optional suggestions used by the
strict and `grounded_v1` profiles.

Some validators support message templates. The generic formatter in
`broker/validators/governance/base_validator.py
(BaseValidator._format_rule_message)` accepts `{context.decision}`,
`{context.agent_id}`, any reasoning field such as `{context.TP_LABEL}`, and
`{rule.id}`, `{rule.blocked_skills}`, `{rule.level}`, `{rule.category}`, or
`{rule.subcategory}`. Missing fields are left visible instead of crashing.
The two water runners evaluate their YAML thinking and identity rules through
`broker/validators/agent/agent_validator.py (AgentValidator)`, which treats
their `message` values as literal text. Do not put template placeholders in
those water YAML messages.

## 3. If a message is missing

An omitted or empty message does not leave an empty reason. It exposes an
internal fallback. A whitespace-only message is technically rendered as
whitespace by the validators, but the configuration warning described below
still flags it as blank. For the `AgentValidator` used by both water examples,
the fallback bodies are:

```text
Thinking Block: <skill> restricted by thinking rules
Identity Block: <skill> restricted by <precondition>
```

With the default `rule_id_prefix: true`, each begins with `[Rule: <id>] `.
Both water examples set `rule_id_prefix: false`, so that prefix is absent. A
rule evaluated through `broker/validators/governance/base_validator.py
(BaseValidator._format_rule_message)` instead falls back to:

```text
[Rule: <id>] Validation failed for skill: <skill>
```

An identity failure may also produce a skill-registry backstop such as
`Precondition failed: '<precondition>' (field is True)`. Set
`hide_registry_backstop_reports: true` when a clear identity-rule message
already explains the same block and internal field names would only repeat it.

When an agent-type configuration is loaded, WAGF logs one `WARNING` per
resolved config file for each getter-selected blocking thinking or identity
rule whose `message` is missing or blank. The warning names the agent type,
the profile or labeled legacy-fallback scope, the rule id, and exact fallback
text. This diagnostic never blocks configuration loading.

## 4. Retry options

These keys live under `global_config.governance` unless stated otherwise.

| Option | Default | When to use it |
|---|---:|---|
| `max_reports_per_retry` | `3` | Limit how many blocking reports are shown on one retry. Extra reports are noted as truncated. |
| `feasible_set_feedback` | `false` | Add the actions that pass every rule this step. Use it when the valid menu changes with water-system state. |
| `plain_action_names` | `false` | Replace skill ids such as `increase_demand` with `increase demand` in retry reports. |
| `rule_id_prefix` | `true` | Prefix AgentValidator messages with `[Rule: <id>]`. Turn it off when ids are implementation detail. |
| `hide_registry_backstop_reports` | `false` | Leave registry backstops out of retry text after an identity rule already blocks the action. Audit results remain complete. |
| `retry_feedback_mode` | `full` | `full` shows reports; `silent` sends the original prompt again; `placebo` sends only the retry wrapper. Silent and placebo test whether the reason itself matters. |
| `intervention_framing` | `plain` | Each report shows the agent’s choice and the rule’s reason. |
| `placebo_closer` | unset | Override the default placebo closer, “Please answer again.” |
| `max_retries` | `3` | Set the maximum governance retries after blocked proposals. |
| `on_retry_exhausted` | `default` | `default` executes the registry's `default_skill`; `keep_proposal` executes the blocked proposal and is refused when coupling is enabled. |
| `audit.retry_prompt_columns` | `false` | Record the exact text sent on every governance retry in raw JSONL `retry_prompts` for review. It does not add a CSV column. |

- **Flood:** uses three retries and three reports, hides rule-id prefixes and
  duplicate registry backstops, uses plain action names and the `plain`
  framing, and records retry prompts so reviewers can inspect what
  the agent was told; other values above remain at their defaults.
- **Irrigation:** uses three retries and three reports, adds feasible actions,
  hides rule-id prefixes and duplicate registry backstops, uses plain action
  names and sets a placebo-safe closer. The base config leaves retry-prompt
  recording off. Both validator variants use plain wording and enable
  `audit.retry_prompt_columns`. The `with_validator` arm runs in strict mode
  with the beneficial-use limit on. The `without_validator` arm runs in
  disabled mode with the limit off.

The option readers and defaults are in
`broker/utils/agent_config.py (AgentTypeConfig)`. Retry-prompt provenance is
described further in [the audit schema](../AUDIT_SCHEMA.md).

## 5. ERROR and WARNING are different

`level: ERROR` blocks the proposal, creates an error report, and can open the
retry loop. `level: WARNING` records an observation but leaves the result
valid. A WARNING never reaches the agent in the governance retry prompt. Use a
WARNING for audit-only guidance; use an ERROR when the agent must choose again.

## 6. Checklist

- Give every blocking thinking and identity rule a non-blank `message`.
- Address the agent as “you”; name its judgment and why the action is
  unavailable.
- Add a `suggestion` only when it helps the next attempt.
- Use literal text for water-example YAML rules; format live numbers in a
  validator result.
- Choose `ERROR` only when the proposal must be retried.
- Enable `audit.retry_prompt_columns` when reviewers need the exact retry text.
- Run a blocked case and read the recorded retry prompt before a study launch.
