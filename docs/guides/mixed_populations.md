# Mixed populations: rule-based, hybrid and LLM agents in one run

A WAGF run can hold agents decided by a language model, agents decided
by a calibrated behavioural rule, and agents that use a rule table with
the model as fallback — all in the same simulation, all through the
same governance pipeline, all landing in the same audit CSVs.

This guide covers what to write in `agent_types.yaml`, what "the same
pipeline" does and does not mean, and how to read the resulting rows.

---

## 1. Why the framework can do this at all

`SkillBrokerEngine.process_step` takes a callable and a prompt. It
builds the context, hands the prompt over, takes back whatever comes,
turns it into a `SkillProposal`, runs the validators, runs the
governance retry loop if something blocks, executes what survives, and
writes the audit row. At no point does it require that the callable be
a language model — it never was a requirement, only an assumption.

What was missing until v0.9 was a way to *say* an agent type uses
something else. The only route was to reach into a running experiment
from a script and replace its invoke function. That works once, for
whoever wrote the script. It cannot be reviewed in a config diff, does
not appear in the audit CSV, and cannot be reproduced by someone
handed the results.

The `decider:` key makes it a declaration.

---

## 2. Declaring a decider

`decider:` is a **per-agent-type** key in `agent_types.yaml`. Absent
means `llm`, which is what every existing config means, so adding this
key to the schema changed nothing for any config that does not use it.

```yaml
household_owner:
  decider: llm          # the default; you may simply omit it

household_renter:
  decider:
    name: rule_based
    params:
      default_action: do_nothing
      rules:
        - id: repeat_loss_relocate
          action: relocate
          when:
            flood_zone: {not_in: [LOW]}
            flood_count: {gte: 2}
```

Two forms are accepted: a bare registered name, or a mapping with
`name` and `params`.

**Put it under the agent type, not under `global_config`.** A `decider:`
in `global_config` is read by nothing. The run starts, finishes, and
produces a perfectly valid all-LLM corpus from a config whose author
believed they had configured a mixed one. `validate_prompt` warns about
this specifically, because nothing in the output artifacts can catch it
afterwards.

### The built-in deciders

| Name | What decides | Params |
|---|---|---|
| `llm` | the agent type's language model — the default | none |
| `rule_based` | a rule table, top to bottom, first match wins | `rules`, `default_action`, `reasoning` |
| `hybrid` | the rule table first; the model answers whatever no rule matched | `rules`, `reasoning` |
| `parametric` | a decision object the domain supplies, named by dotted path | `target`, `init`, `method`, `fields` |

A domain can register deciders of its own — see §6.

### Rule tables

Every rule is `{id, action, when, reasoning}`. `action` is a skill id
from the registry. `when` is a mapping of field name to condition;
**every** condition must hold for the rule to fire, and the first rule
whose conditions all hold wins. A rule with no `when` matches
everything and is the table's own catch-all.

Conditions take a literal (`flood_zone: HIGH`), a list (`flood_zone:
[HIGH, VERY_HIGH]`, meaning membership), or an operator mapping:
`eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`.

Field names resolve in this order: `agent_id` / `agent_type`, then this
period's environment dict, then the agent — its `custom_attributes`,
`fixed_attributes` and `dynamic_state` (the same three
`InteractionHub.build_tiered_context` composes, in the same order), then
its raw state params, then a plain attribute on it.

**The environment comes before the agent, and you can override that per
field.** An agent very often carries its own copy of a world variable,
refreshed at the end of the period; an agent-first lookup then answers a
rule with last period's number while the environment publishes this
period's. Write `scope:` inside the condition to say which plane you
mean:

```yaml
        - id: loss_ratio_crisis
          action: significantly_improve_crs
          when:
            loss_ratio: {gte: 1.2, scope: env}    # the world's number
        - id: deeply_exposed
          action: elevate_house
          when:
            flood_depth: {gte: 1.0, scope: agent}  # this household's own
```

| `scope:` | Reads |
|---|---|
| `auto` (default) | the environment, then the agent |
| `env` | the environment only |
| `agent` | the agent only (identity, the three state dicts, state params, attributes) |

`scope` is not an operator — it sits alongside them in the same mapping
and is stripped before the condition is evaluated. An unrecognised scope
raises when the table is built rather than being coerced to `auto`: a
coerced scope reads a plane the config did not name and goes on looking
like it works. This mirrors the `scope:` on world-grounded thinking-rule
conditions, deliberately, so there is one vocabulary to learn.

Because `agent_id` always resolves, a literal subset of the population
is expressible without the domain inventing a marker attribute:

```yaml
        - id: pilot_cohort
          action: elevate_house
          when:
            agent_id: {in: [H0001, H0007, H0042]}
```

**A field nothing in scope carries never matches, and says so.** Absence
is not satisfaction — the alternative would fire the rule on every agent
of a type that never had the field, which looks exactly like a working
rule. But silence about it was worse: an unresolvable field makes its
rule permanently false, and a permanently-false rule is indistinguishable
in every artifact from a rule that was evaluated and did not match. So
each unresolved `(agent type, field)` is logged once and counted per row
into `run_integrity.json` → `rule_field_unresolved`. Check that key
before reading any rule-based arm. A condition that cannot be evaluated
at all (`"HIGH" >= 2`) also does not fire, and logs why once.

**Watch the field names against what the agents actually carry.** The
common failure is a name that exists in the domain's vocabulary but not
on the agent object — the value lives in `fixed_attributes` under a
different key, or only in the environment. The symptom is not an error;
it is an arm in which every row is the `default_action`.

`rule_based` **requires** `default_action`. Without it, an agent no
rule matched has no action to propose, the step aborts, and that arm's
row count silently shrinks against the arm it is being compared with.
`hybrid` **rejects** `default_action` for the mirror-image reason: the
model is its fallback, and declaring a constant one instead means you
wanted `rule_based`.

---

## 3. What "apples-to-apples" means here

Everything below happens identically for a rule-based agent and a
model-driven one:

- the same context build, from the same memory engine, with the same
  retrieval and the same prompt assembled (a rule-based agent's prompt
  is built and simply not read — which is what keeps the two arms'
  memory state comparable);
- the same `SkillProposal`, the same registry eligibility check, the
  same validators, the same rule tiers;
- the same governance retry loop, the same `REJECTED` /
  `REJECTED_FALLBACK` semantics, the same `on_retry_exhausted` policy;
- the same audit row, with the same columns and the same meanings.

A rule-based agent is genuinely blocked by governance when it proposes
something the rules forbid, and the block is recorded the same way. In
the flood example above, an owner decided by the calibrated logistic
proposes `buy_insurance`, the `mg_insurance_barrier` rule blocks it,
and the row lands `REJECTED` with the registry default executed —
governance acting on a non-LLM agent, in the same columns, for the
same reason it would act on a model.

**Blocked deterministic agents retry once, not to exhaustion.** A rule
table asked the same question twice gives the same answer, so a
governance retry re-proposes exactly what was just blocked. The retry
loop's early-exit notices the same blocking rule ids on consecutive
attempts and stops, so such rows read `retry_count: 1` rather than the
configured maximum. Read that as "the decider had nothing else to
offer", not as a governance layer that gave up early — a model-driven
agent under the same rule may well retry to the maximum, and comparing
the two arms' raw retry counts without this in mind understates how
hard the rule pushed on the rule-based one.

**A hybrid whose rule answered does not consult the model on retry
either.** The retry loop calls the same callable again, the same rule
matches the same state, and the identical proposal comes back — so a
hybrid row that was blocked stays `decider_path: rule` and the model is
never asked, even though the model is nominally its fallback. This is
deliberate: `hybrid` means "the model handles what no rule COVERS", not
"the model handles what governance REJECTED", and switching to the model
on rejection would make the rule table a suggestion. The consequence to
read for is that a blocked hybrid row exhausts its retries against a
constant, exactly like a `rule_based` one, and its `decider_path` stays
`rule` throughout. If you want the model to get a second look at cases
the rules mishandle, that is a change to the rule table, not to the
retry.

### What differs, and how those columns read

**The LLM statistics columns describe a call that did not happen.**
`llm_retries` reads `0`, `llm_success` reads `True`, and the token
columns (`prompt_tokens`, `response_tokens`, `context_utilization`,
`num_ctx`) are absent or zero. Nothing failed, because nothing was
called. Do not average these columns across a mixed run — filter on
`decider` first, or the LLM arm's retry rate is diluted by rows that
could not retry.

`llm_calls` belongs on that list and is the most misleading of them: it
reads **`1`** on a rule-answered row, not `0`. The retry loop increments
it immediately after the decider callable returns, before it looks at
what came back, so a rule table that answered without touching a model
still counts as one call. Summing `llm_calls` over a mixed run therefore
overstates model usage by exactly the number of rule-answered rows —
which, in a run whose point is to spend the model budget on the hard
cases, is the number you were trying to measure. Group by
`decider_path` first: `rule` and `rule_default` rows made no call.

The `mem_*` family is the opposite trap. `mem_top_source`,
`mem_top_score` and their siblings describe a retrieval that DID happen
— the context build is identical for every decider, which is what keeps
the arms' memory state comparable — but nothing consumed it, because a
rule table does not read the prompt those memories went into. Read them
as "what this agent would have been shown", never as an input to the
decision.

**`parse_layer` reads `decider:<name>`, not a parser route.** A rule
table has no text to parse. Fabricating model-shaped text so the parser
could re-extract the answer would put a fictional parse layer in the
audit trail; the column says plainly which decider produced the row
instead. `parse_confidence` is `1.0` for the same reason — the answer
was not inferred from anything.

**`raw_output` is a small JSON object naming the rule that fired**, for
example `{"decider": "rule_based", "decision": "relocate", "path":
"rule", "rule": "repeat_loss_relocate"}`. That column is where a reader
looks to see what the agent produced, and for a rule-based row the
honest answer is the rule, not a blank.

**Construct labels are a DECLARATION, not a self-report.** A rule table
reports the appraisals its author says the rule encodes:

```yaml
        - id: repeat_loss_relocate
          action: relocate
          when: {flood_count: {gte: 2}}
          reasoning: {TP_LABEL: VH, CP_LABEL: L}
```

This is how a behavioural rule is specified in a conventional ABM, and
declaring it is what lets the *same* governance rules evaluate this
agent type and the model-driven ones. It is not the model's own
appraisal, and the `decider` column is how a reader tells the two
apart — never treat a `reason_*` column as self-reported without
checking which decider produced the row.

Omitting `reasoning` is also a legitimate choice: the rules that read
those constructs then do not fire on those rows, which is recorded
rather than assumed. It is a fact about the comparison, not a defect
in it. What is never acceptable is a decider inventing a middle value
so that a rule appears to have been evaluated.

**The `parametric` decider's own labels are a different case again, and
worth spelling out separately from the flat declaration above:** the
flood owner's `TP_LABEL` / `CP_LABEL` are a deterministic transform of
the survey `tp_score` / `cp_score` the decider reads off the agent
(Likert 1-5, via its `appraisal_scale`) — a value the LLM arm never sees
as a prompt placeholder and never rates itself, so comparing the two
arms' construct-label *distributions* compares a measurement artifact
against a self-report, not a behavioural finding.

---

## 4. The audit columns

When any agent type in the active config declares a decider other than
`llm` — or when an operator writes
`global_config.audit.decider_columns: true` — every audit row gains two
columns:

| Column | Meaning |
|---|---|
| `decider` | the registered name of what produced this row: `llm`, `rule_based`, `hybrid`, a domain's own — or `<name>@<domain>` when a domain has deliberately replaced a built-in |
| `decider_path` | which way that thing went on this decision |

`decider_path` takes one of five documented values:

| Value | Meaning |
|---|---|
| `llm` | a model produced this row |
| `rule` | a rule in the table matched |
| `rule_default` | NO rule matched; the declared `default_action` was proposed |
| `parametric` | a domain decision object produced it |
| `aborted` | the step crashed or never parsed — a sentinel row, no decision was reached |

`rule` and `rule_default` are kept apart on purpose. A table whose
fields all fail to resolve answers every decision with its default, and
if both read `rule` the CSV of that run is indistinguishable from one
where the rules were evaluated and did not match — an arm that is a
constant wearing a rule table's name. `run_integrity.json` counts the
split as `rule_default_rows` and warns when a decider's every row is one.

`decider_path` is also the load-bearing column for hybrids. Without it a
hybrid arm is indistinguishable in the CSV from either pure arm, and
there is no way to say how much of its behaviour the model produced.

A config where every agent type is (or defaults to) `llm` emits neither
key. CSV fieldnames are derived from row keys, so a default run gains
no columns and every frozen corpus reruns byte-identically. Only
AGENT-TYPE blocks count: a `decider:` written under `shared:` or
`global_config:` is read by nothing and does not switch the columns on
(it would produce an all-`llm` corpus carrying a provenance column that
says so on every row). `validate_prompt` warns about the misplaced key.

`run_integrity.json` carries the census the composition claim is checked
against — read it before reading the CSV:

| Key | What it answers |
|---|---|
| `decider_rows` | `{decider: rows}` — the composition that actually happened |
| `decider_rows_total` | their sum; warns when it does not account for every row in the CSV |
| `decider_declared` | the decider names the CONFIG asked for |
| `decider_arms_with_zero_rows` | declared arms that produced NOTHING — the failure the CSV cannot show |
| `decider_aborted_rows` | sentinel rows per decider (no decision was reached on these) |
| `rule_default_rows` | rows that fell through to `default_action`, per decider |
| `rule_field_unresolved` | `{agent type: {field: n}}` — conditions that could never hold |
| `rule_firings` | `{agent type: {rule id: n}}` — which rules fired, and how often |

`rule_firings` counts DECISIONS, not rows: a governance retry re-walks
the table and counts again, so a rule's firing count exceeds its row
count by however often rows it produced were blocked and retried.

The run warns when every row came from a single non-`llm` decider (that
run holds no mixed population), when a declared arm produced no rows at
all, and when an arm's every row was its `default_action`.

Full column semantics: `docs/AUDIT_SCHEMA.md`.

---

## 5. Running the flood example

`examples/multi_agent/flood/config/ma_agent_types_mixed_population.yaml`
is the frozen paper-3 config plus `decider:` keys on three of its four
live agent types. The frozen file is untouched and stays the default.

```bash
python examples/multi_agent/flood/run_unified_experiment.py \
    --model mock --agents 4 --years 2 --seed 42 --mode random \
    --mixed-population --output results/mixed
```

| Agent type | Decider | Decides how |
|---|---|---|
| `household_owner` | `flood_household_parametric` | the calibrated anchored logistic, no model call |
| `household_renter` | `rule_based` | a rule table written out in the YAML |
| `insurance` | `hybrid` | rule table for the obvious years, model for the rest |
| `government` | (absent) `llm` | unchanged |

The four audit CSVs carry the same columns apart from the `reason_*`
ones each decider's own reasoning dict produces — which is the same way
an LLM agent's reasoning keys produce its columns.

---

## 6. Shipping a decider from your own domain

A calibrated behavioural model is domain science. Putting it in
`broker/` would put a domain's variables in the generic namespace, so
domains contribute deciders through the `DomainPack` hook instead:

```python
class MyDomainPack(DefaultDomainPack):
    name = "my_domain"

    def decider_factories(self):
        from examples.my_domain.decider import make_decider_factory
        return {"my_domain_threshold": make_decider_factory()}
```

A factory has the signature `(agent_type_config, runtime) -> Callable`
and must return the decide function itself. `runtime` carries
`llm_invoke`, `agent`, `agent_id`, `agent_type`, `env` and `seed`. The
returned callable takes the prompt and returns a `str`, a
`SkillProposal`, or a `(payload, LLMStats)` pair — the retry loop
accepts all three. `broker.agents.deciders.make_proposal` builds the
pair for you.

Configs then name it like any built-in: `decider: my_domain_threshold`.

**Pick a name no built-in has.** Offering a factory under `llm`,
`rule_based`, `hybrid` or `parametric` is refused with a `ValueError`:
whichever module imported first would otherwise decide what every config
in the process means by that word, and the audit CSV would call both
things `rule_based`. If replacing a built-in is genuinely what you want,
say so per name, and every row it produces is labelled `<name>@<domain>`
so the CSV keeps the two apart:

```python
    def decider_factories(self):
        return {"rule_based": {"factory": my_rule_based,
                               "override_builtins": True}}
```

**Read what the agents actually carry, and raise when it is absent.** A
decider that substitutes a plausible default for a field it could not
find produces a full CSV of plausible decisions in which every
unreadable agent decided alike — and nothing in the artifacts says so.
Split your inputs explicitly: the fields that MOVE the decision raise,
naming the agent and the holders searched; the fields whose absence has
a meaning (no recorded flood history means no floods) take a documented
default and name themselves in the row, the way the flood decider writes
`fields_defaulted` into its reasoning and its `raw_output`.

If your decider samples, seed it from something stable — the agent id
and the step, not a shared RNG object. A decider whose answer depends
on how many agents ran before it is not reproducible under a thread
pool, and the audit trail of such a run looks entirely reasonable.

### Deciders are rebuilt each step, on purpose

A non-default decider is constructed fresh for each agent at each step.
The `llm` default is not: it comes from the same cache
`get_llm_invoke` uses and is the identical object. The asymmetry is
deliberate — a rule table reads the agent's current state and this
period's environment, and a decider cached at year one would answer
year thirteen from year one's numbers.

---

## 7. When something is wrong

An unregistered decider name is refused at both ends. `validate_prompt`
reports it as a BLOCKER before the batch launches, and
`DeciderRegistry.build` raises at the agent type's first decision.
Neither falls back to `llm`: a silent fallback would turn a
mixed-population config into an all-LLM run with nothing in the
artifacts saying so, and the mistake would surface after the analysis
was written.

A declared decider that cannot be BUILT — an unregistered name, a
`rule_based` table with no `default_action`, a `parametric` target whose
module does not import, a `scope:` that is not one of the three — stops
the run before year one, with a traceback naming the agent type. It is
resolved once at run start on purpose: evaluated per agent inside the
loop, the same failure was caught by the handler that exists for a model
timing out, so every agent of that type became an ABORTED sentinel
stamped with the decider it never ran and the process exited 0.

A rule's `reasoning` must report either NOTHING or every `*_LABEL` in
that agent type's `parsing.constructs`. A partial report makes the retry
loop ask for the missing ones, a rule table answers the retry
identically, and every row that rule produces exhausts its retries and
lands ABORTED. `validate_prompt` reports a partial report as a BLOCKER.

**Replay and factor ablation (`broker.experiments.replay`) support
LLM-decided rows only.** `build_replay_decider` refuses — for both the
parse-only default and `--with-governance` — the moment the loaded
config declares a non-`llm` decider on any agent type: neither replay
path can honestly stand in for a rule table or a `parametric` object, so
filter a mixed-population corpus down to `decider == 'llm'` rows before
replaying it, or point `--agent-config` at an LLM-only config. See
`docs/guides/ablation_guide.md`.

Run the config-time check before any batch:

```bash
python -m broker.tools.validate_prompt path/to/agent_types.yaml
```

If your decider is shipped by a domain, import the example package
first so its pack is registered — otherwise the check can only report
that the name is unknown to *this* process, and says so as a WARN
rather than a BLOCKER.

---

## 8. What this does not do yet

**Per-agent-type social topology is not wired.** `SocialGraphSpec`,
`AGENT_SOCIAL_SPECS` and `configure_social_graph_for_agent` exist and
have no production caller: neighbour sets still come from the runner's
`--neighbor-mode` graph for every agent type alike. A mixed population
can therefore differ in how its agents DECIDE but not yet in who each
agent can SEE. Wiring it means changing neighbour construction, which
is the most reproduction-sensitive path in the multi-agent runner
outside the prompt, so it is deliberately left for its own change with
its own byte-identity evidence.

**`MessagePool` and `GameMaster` remain EXPERIMENTAL** and have no
message producers. A decider cannot send or read messages through them.

---

## Related

- `docs/AUDIT_SCHEMA.md` — the `decider` / `decider_path` columns
- `docs/references/yaml_configuration_reference.md` §2.3.5 — the
  `decider:` key
- `docs/guides/governance_layers.md` — what the validators do to any
  proposal, whoever produced it
- `docs/guides/calibration_guide.md` — fitting the numbers a
  `parametric` decider runs on
