# Governance layers: hard rules, soft rules, and what each one can prove

WAGF simulates a language model agent under two kinds of control, and they are
not variations of one another. This guide states what each layer does, what a
rule's *grounding* is and why it decides how much a blocked decision proves, and
what the self-report rules in the shipped profiles can and cannot establish.

Read it before writing a rule, and before writing a sentence of a paper about
one.

---

## 1. The two layers

Think of a permit office. A **hard rule** is the clerk who refuses to stamp the
form: you do not leave with a permit, you fill the form in again. A **soft
rule** is the note stapled to the form saying the roof pitch looks wrong. The
note changes nothing by itself. Whether it changes what the applicant does next
is a question you can only answer if the note was actually handed over and
somebody wrote down that it was.

| Layer | YAML | What happens | Audit |
|---|---|---|---|
| Hard | `level: ERROR` | The proposal is rejected. The broker builds an `InterventionReport`, re-prompts, and repeats up to `max_retries`. On exhaustion the domain's `on_retry_exhausted` policy decides what executes. | `failed_rules`, `rules_triggered`, `status` |
| Soft | `level: WARNING` | The proposal is **approved and executed**. Under `advise_mode: feedback` the finding is also rendered into one extra, non-blocking prompt. | `warning_rules`, and under `advise_mode` also `advise_findings` + `advise_shown` |

The retry loop reads only `v.errors`, and a WARNING result carries an empty
`errors` list by construction. That is why, before the `advise_mode` key
existed, a WARNING rule could not reach the model **at all** — so the old lab
claim that "WARNING rules produce about 0% behaviour change" was not a finding.
It was the architecture restating itself. PR-1 deleted the claim; this layer
makes the underlying question answerable.

### `advise_mode` — the three settings

| Value | Extra LLM calls | Model told? | Row records | Use it to |
|---|---|---|---|---|
| `off` (default) | 0 | no | nothing | reproduce a published run exactly |
| `record` | 0 | no | `advise_findings`, `advise_shown=False` | measure how often soft rules fire, with behaviour provably unchanged |
| `feedback` | at most 1 per decision | yes | the above plus `advise_shown=True`, `advise_skill_before` / `_after`, `advise_executed_stage` | measure whether being told changed the action within the same decision |

Under `feedback` the advisory call is issued only when the proposal is
otherwise APPROVED. If a hard rule is already blocking, the retry loop is about
to re-prompt anyway, and inserting an advisory call first would mix the two
channels inside one decision and make the contrast unreadable. The finding is
still recorded, with `advise_shown=False` saying plainly that the model was not
told.

`advise_shown` is set before the call and never cleared. The claim the column
supports is "the model was shown this advice", and that became true when the
prompt was sent, whatever came back. It is set from the number of reports the
renderer actually delivered (`advise_reports_shown`), not asserted: an adapter
that dropped them all sends a prompt with no advice in it, and that decision is
a resample rather than an observation about advice.

### Advice never blocks — including when the advice made things worse

The `status` of a decision under `feedback` is exactly what it would have been
with the channel off. If the model's post-advice proposal would fail validation,
it is discarded rather than re-prompted: the pre-advice proposal executes,
`advise_executed_stage` reads `pre`, and `advise_post_validation_invalid` plus
`advise_post_validation_rules` say what it would have tripped. The post-advice
results still reach the decision's validation history, so the trace records what
the advice produced.

The alternative — letting the post-advice result decide — would open the
governance retry loop through the back door on exactly the decisions where
advice mattered most, and "advice never blocks" would be false in the Methods
for precisely those rows.

### What is NOT a soft finding

Three kinds of WARNING result are deliberately left out of `advise_findings`:

| Excluded | Why |
|---|---|
| Results demoted by `governance.advise` (P0-1c) | They are ERROR rules the arm config turned into advisories; they already have their own advisory call and their own `advisory_*` columns. Counting them here shows one finding to the model twice. |
| Results converted by SHADOW mode | Shadow is suppressed *enforcement*, recorded in `shadow_blocked`. Feeding a suppressed hard rule back as advice would turn a shadow arm into a quiet advice arm, with nothing in the row saying so. |
| Results carrying no rule id | They cannot be named, so they are counted in `soft_findings_unidentified` instead. Including them produced rows with `advise_shown=True` and `advise_findings=""` — a call was made, the model was told something, and the row named nothing. |

Ids in the cell carry their validator category (`thinking:low_coping_block`,
`social:norm_drift`) because one cell can hold findings from several tiers, and
a bare id does not say which layer produced it. `construct_missing` and
`world_variable_missing` carry the field instead
(`construct_missing:TP_LABEL`) — their rule id is the same string every time.

> **Not the same key as `governance.advise`.** That one (P0-1c) *demotes* rules
> authored as ERROR into advisories for an experiment arm. `advise_mode`
> governs rules already authored as WARNING. Writing one where you meant the
> other is the mistake `validate_prompt` now names for you.

### `retry_feedback_mode` — red-team objection 3: is it the content, or just another try?

`global_config.governance.retry_feedback_mode` is `full` (default) or `placebo`.
It governs only the **Hard** row above: the BLOCKING governance retry loop
(`RetryMixin._governance_retry_loop`), which fires after an ERROR-level
validator rejection and re-prompts up to `max_retries` times.

A published effect of governance could, in principle, be nothing more than
"the model got a second attempt" — not "the model was told which rule it
broke and why". `retry_feedback_mode` makes that separable, and states
precisely WHAT it isolates: **rule-specific content (identity, reason,
suggestion) is removed; the governance framing (that the previous answer was
not accepted) is kept.** The arm therefore tests "rule-specific information"
against "another attempt with the same framing" — not against "another
attempt with no framing at all" (nothing states or implies the latter).

| Value | Validator behaviour | Content in the retry prompt | Audit (`failed_rules`, `error_messages`) |
|---|---|---|---|
| `full` (default) | rejects on the same rules, same schedule, same `on_retry_exhausted` fallback | the rendered `InterventionReport`(s): rule id, reason, suggestion | the real validation results |
| `placebo` | identical — same rules, same schedule, same fallback | the adapter's wrapper only — header + closer + the original prompt, no rules block at all (`format_intervention_prompt(..., include_reports=False)`, the same "A''" mechanism `governance.advise`'s own `mode="wrapper"` uses for the advisory channel). Header/closer text still depends on `intervention_framing` ("was flagged by..." / "triggered..."), but neither wording names a rule id, a blocked skill, a reason, or a suggestion. | the real validation results — unchanged |

**What changes is exactly one thing: the text of the retry prompt.** The
validator still decides *when* a proposal is rejected; the retry count, the
early-exit logic, and the `on_retry_exhausted` fallback are all untouched. The
audit CSV's `failed_rules` / `error_messages` columns are built from the
`ValidationResult` objects the validators returned, never from the retry
prompt text, so they read identically in both modes — a reader of the CSV can
always see what actually blocked a decision, even in the arm where the model
itself was never told. The synthetic `format_violation` report built for an
UNPARSABLE retry attempt is covered the same way — it, too, is only ever
turned into text by the report-rendering path, which `placebo` never calls.

This is a **separate switch from `governance.advise`'s own placebo mode**
(P0-1c, `_advise_pass.py`, arm B'). Both happen to be named `"placebo"`, but
they are mechanically different: `governance.advise`'s `mode="placebo"` keeps
the SAME report count/shape and replaces each report's text with a fixed
sentence, for the separate, NON-BLOCKING single advisory call issued for
rules *demoted* from ERROR. `retry_feedback_mode: placebo` renders NO reports
at all (the wrapper-only A'' control), for the actual BLOCKING retry loop.
They gate different code paths, different config keys, and never share
state — running one does not imply or affect the other.

**Interaction warning.** If `retry_feedback_mode: placebo` is set while
`governance.advise` (`_advise_mode`) or the soft-rule channel's `advise_mode`
(`_soft_advise_mode`) is anything other than `off`, the engine logs a
WARNING at construction: the retry PROMPT is content-free, but either
advisory channel can still show the SAME decision rule-specific content in a
*different* prompt (the one-shot advisory call), so a "placebo" corpus meant
to be content-free end-to-end needs both set to `off` too.

Default `full` reproduces the shipped retry prompt byte-for-byte; every
frozen baseline (v21 / paper-3 mock) reruns unchanged unless the key is set
explicitly. CLI: `examples/single_agent/run_flood.py --retry-feedback-mode
{full,placebo}` overrides the resolved config value for that run; the
resolved mode is logged in the SAME shape both at engine construction and
again (if overridden) after the CLI override is applied
(`[Governance] retry_feedback_mode=...`, so the LAST such line in a run's
output always names the value in effect), and recorded in the reproducibility
manifest's `retry_feedback_mode` field.

---

## 2. Grounding: what a rule's antecedent is anchored in

Every rule condition reads one of two things.

**Self-report.** A construct label the model emitted in the same generation —
`TP_LABEL`, `WSA_LABEL`, `RISK_APPETITE`. Written as
`{construct: TP_LABEL, values: ["VL", "L"]}`.

**World.** A variable the simulator publishes and the model cannot author.
Written as `{variable: flood_event, scope: env, operator: is_true}`, or in the
older dataclass shape `{type: precondition, field: at_capacity, ...}`.

A rule is `grounding: world` when at least one of its conditions reads the
world, and `self_report` otherwise. The loader infers this and you can override
it with an explicit `grounding:` key. Prose does not count: a rule that only
mentions the world in its `message:` stays self-report, because a message is
not an antecedent.

### Why the distinction decides what a result proves

Consider two agents in the reference flood testbed, both reporting
`TP_LABEL: VL` and both choosing `do_nothing`. One of them lives on a parcel
that flooded this year. Under `strict`, the two decisions are **identical to
every rule in the profile**, because every rule in `strict` reads only the
labels — and the labels are the same. The rule checks one JSON object against
itself, and a reviewer is right to say so.

Under `grounded_v1`, one is approved and one is blocked, and the only thing
that differs is the world. Here is that run, three agents, seed 42, flood years
3/4/9, harness holding `TP_LABEL: VL` and `do_nothing` fixed:

| year | `flood_event` | status | `rules_world_grounded` |
|---|---|---|---|
| 1 | False | APPROVED | |
| 2 | False | APPROVED | |
| 3 | True | REJECTED | `observed_flood_low_threat_inaction` |

The self-report never changes. The verdict does. That contrast is what a
world-grounded rule buys, and no rule conditioned on `TP_LABEL` alone can
produce it.

### Which rules are grounded, per profile

| Domain | Profile | Rule | Antecedent | Grounding |
|---|---|---|---|---|
| flood (`examples/single_agent`) | `strict` | `extreme_threat_block` | `TP_LABEL in [H, VH]` | self-report |
| | `strict` | `low_coping_block` (WARNING) | `CP_LABEL in [VL, L]` | self-report |
| | `strict` | `relocation_threat_low` | `TP_LABEL in [VL, L]` | self-report |
| | `strict` | `elevation_threat_low` | `TP_LABEL in [VL, L]` | self-report |
| | `grounded_v1` | *all four of the above, verbatim* | | self-report |
| | `grounded_v1` | `observed_flood_low_threat_inaction` | `flood_event is true` **and** `TP_LABEL in [VL, L]` | **world** |
| irrigation (`examples/irrigation_abm`) | `strict` | `high_threat_no_maintain` (WARNING) | `WSA_LABEL == VH` | self-report |
| | `strict` | `low_threat_no_increase` | `WSA_LABEL == VL` | self-report |
| | `strict` | `high_threat_high_cope_no_increase` | `WSA_LABEL` **and** `ACA_LABEL` | self-report |
| | `grounded_v1` | *all three of the above, verbatim* | | self-report |
| | `grounded_v1` | `observed_scarcity_low_wsa_increase` | `drought_index > 0.08` **and** `WSA_LABEL in [VL, L]` | **world** |

`grounded_v1` is **additive**. It repeats the `strict` rules unchanged and adds
one world-grounded rule, so a `strict`-versus-`grounded_v1` comparison is a
comparison of that one rule and nothing else. Identity rules
(`precondition:`-driven physical constraints such as "the house is already
elevated") were always world-grounded; they are not new here and are not what
the finding was about. They are now STAMPED as world-grounded, so an identity
block lands in `rules_world_grounded` rather than falling to the self-report
default — before that, a count of self-report blocks silently included every
physical constraint.

### Picking a threshold

The irrigation threshold is `drought_index > 0.08`, and the number is derived
from the environment's own distribution: across 126 basin-years (seeds 42/43/44)
the index has median 0.017, 85th percentile 0.083, maximum 0.160. So the rule
fires in roughly the driest one year in six.

A "sounds severe" 0.4 would have been worse than useless — the synthetic basin
never reaches it in 42 years, so the rule could not fire, and a rule that cannot
fire is indistinguishable in the audit trail from a rule that was never
violated. That is the same class of silent-nothing this whole PR exists to
remove. **Recalibrate for a real basin**; copying the number copies this
testbed's climate.

#### Two other thresholds read the same variable, and none of the three know about each other

`drought_index` is already a decision boundary in two other places, at very
different values:

| Where | Threshold | What it decides | Reaches the LLM arm? |
|---|---|---|---|
| `grounded_v1` (this rule) | `> 0.08` | Blocks a demand increase when the farmer rated scarcity low | yes — this is the governance path |
| `examples/irrigation_abm/learning/fql_skill_mapper.py::compute_wsa_label` | `< 0.2` → `VL`, `< 0.4` → `L`, … | Derives a WSA label for the **reinforcement-learning baseline** arm | no |
| `examples/irrigation_abm/adapters/irrigation_pack.py::appraisal_grounding_map` | `drought_index_bump_threshold: 0.6` | Bumps the expected WSA one level in the post-hoc appraisal-grounding audit tool | no |

**They are not cross-referenced anywhere.** Changing one does not change the
others, and nothing checks that they stay coherent. Treat the table as the
inventory to re-read before moving any of them.

**Does `compute_wsa_label` make the grounded rule tautological?** Checked, and
no — for the arm the rule runs in. `compute_wsa_label` has exactly one caller,
`run_fql_baseline.py`, which is the FQL (reinforcement-learning) baseline arm.
That arm runs the twelve hand-written irrigation validators directly and never
touches the YAML `thinking_rules` path, so the grounded rule cannot fire there
at all. In the LLM arm (`run_experiment.py`) `WSA_LABEL` comes from the model's
own reasoning block, so `drought_index > 0.08` and `WSA_LABEL in [VL, L]` are
genuinely independent antecedents — which is the whole reason the rule can
detect a contradiction.

Two caveats worth stating rather than discovering later. First, the FQL
baseline's `wsa_label` IS a deterministic function of `drought_index`, so if that
arm were ever routed through the YAML rule path the rule would be near-tautology
there (`drought_index` in `(0.08, 0.4)` implies `VL`/`L` by construction) — the
rule is kept as-is because that routing does not exist, not because it would be
harmless. Second, the LLM arm's prompt does contain the drought index as text
(`irrigation_personas.build_water_situation_text`), so the model has seen the
number it is being contradicted about. That makes the rule a check on whether
the model USED what it was shown, which is a weaker claim than a hidden-variable
contradiction and should be described that way.

### Which variables you can ground on

Only what the environment actually publishes reaches the validator.

| Domain | Available in `scope: env` | Available in `scope: state` |
|---|---|---|
| flood | `flood_event`, `grant_available`, `current_year`, `premium_rate` | `elevated`, `has_insurance`, `relocated`, `flood_threshold`, `trust_in_insurance`, `trust_in_neighbors` |
| irrigation | `year`, `drought_index`, `total_available_water`, `total_basin_demand` | `at_allocation_cap`, `below_minimum_utilisation`, and the rest of the agent's state tier |

To ground on something not listed, publish it from the domain's
`advance_year()` / environment adapter first. Do not add it to `broker/` — the
genericity invariant test will catch a domain token in generic code, correctly.

### Always write `scope:`

The broker builds its validation context as `{"env_state": env, **agent_state,
**env}`. A name carried by both planes therefore resolves to the env copy, and
the agent's own value is unreachable. `scope: env` / `scope: state` says which
one you meant; `scope: auto` (the default) searches env, then agent state, then
the flattened context.

The five accepted values are `env`, `state`, `social`, `context`, `auto`.
Anything else is **coerced to `auto`** — and `auto` searches env first, so
`scope: environment` appears to work right up until the agent's own state
carries the same name, at which point the rule silently reads the wrong plane.
The coercion warns once at runtime, and `python -m broker.tools.validate_prompt`
rejects it at config time, which is while it is still one character to fix.

### A variable the environment never published

A world variable that cannot be read makes the rule **not fire**. That is
deliberate and it is the safe direction: blocking an action on evidence nobody
has is worse than missing a violation.

But it is recorded. The row gains a `world_variable_missing` WARNING naming the
rule and the variable, and the id appears in `rules_world_grounded` for that
row. Without it, "the world had nothing to object to" and "the rule could not
read the world" produce the same row, and only the first is evidence about the
agent.

At the run level, `run_integrity.json` carries `world_grounded_rows` and
`world_rules_unevaluable_rows`. When every row of a grounded run was
unevaluable, `integrity_ok` goes false and the runner prints a guardrail block:
that run's audit CSV is byte-for-byte the shape of a self-report-only run, so
nothing else would have told you the grounded profile was decorative. The usual
causes are a variable the domain does not publish, and a `scope:` naming the
wrong plane.

**This coverage is the `AgentValidator` plane only.** `ThinkingValidator`
(reached only through `validate_all` / `build_domain_validators` — "available
architecture, not the production default", not a plane any shipped domain
routes a decision through) has no `world_variable_missing` finding and no
`run_integrity.json` census entry: a missing world variable there silently
makes the condition not match, the same silent shape the AgentValidator plane
had before this WARNING existed. Deliberately not duplicated — no shipped
domain reaches it, and the top-level `governance:`-plane world rules it would
evaluate that the `AgentValidator` plane does not already cover are not
shipped in any current domain either, so there is no production row that
would gain a grounding column from a second census. A `logger.warning`
(deduped per `(rule_id, variable)` per process) at the miss site is the
lighter substitute.

---

## 3. Missing constructs: one rule, three former answers

A rule asks about `TP_LABEL` and the model never emitted one. Three evaluators
used to answer differently:

| Evaluator | Legacy answer |
|---|---|
| `AgentValidator._run_rule_set` | label resolves to `""`, rule does not fire, **nothing recorded** |
| `ThinkingValidator._evaluate_single_condition` | label **fabricated as `"M"`**, so a rule written for `values: ["M"]` fires on a decision whose construct the model never emitted |
| `RuleCondition._get_value_from_context` | value is `None`, rule does not fire |

The reconciled rule, active under `validators.framework_aware_labels: true`:

> **A missing construct makes the rule not fire, and records a
> `construct_missing` WARNING finding. No middle value is ever assumed.**

The finding matters as much as the non-firing. Without it, a row where the rule
was skipped for lack of data is indistinguishable from a row where the rule was
evaluated and passed — and only one of those is evidence about the agent.

With the flag off, all three legacy behaviours are preserved byte-for-byte,
including the fabricated `"M"`. That is deliberate: the published corpora were
produced under them and must keep reproducing.

**The flag has to reach both evaluators.** `AgentValidator` reads it from the
config it was built with; `ThinkingValidator` gets it from
`build_domain_validators`. Half-wiring it does not produce a half-fixed run — it
produces a run where the two disagree about the same rule on the same decision,
one recording `construct_missing` and not firing while the other assumes `"M"`
and fires. `SkillBrokerEngine` logs the resolved value once at startup and warns
when the evaluators disagree; pass `config=` (or an explicit boolean) to
`build_domain_validators` when a process holds more than one config.

**Interaction with `advise_mode`.** Under the flag a `construct_missing` finding
is an ordinary WARNING result, so with `advise_mode: record` it appears in
`advise_findings` as `construct_missing:<FIELD>`, and with `advise_mode:
feedback` its text is shown to the model like any other soft finding. That is
usually what you want — "you did not report a threat appraisal" is exactly the
kind of thing worth telling a model — but it does mean turning both flags on at
once changes the advisory prompt's content, not only its bookkeeping. Turn them
on in separate arms if you need to attribute the effect.

---

## 4. Framework-aware labels

Framework registration is generic. A domain declares
`psychological_framework: financial` and the registry supplies
`AGGRESSIVE -> A`, `CONSERVATIVE -> C`.

Enforcement was not generic. `AgentValidator.get_label` normalised every label
through a hardcoded `VL / L / M / H / VH` alphabet and, on a miss, truncated to
the first two characters — so `AGGRESSIVE` became `"AG"`, matched nothing, and
**every `financial` rule silently never fired**. The failure mode is the
dangerous kind: a rule that never fires and a rule that is never violated
produce the same audit trail.

`validators.framework_aware_labels: true` resolves labels against the agent
type's own registered alphabet, normalises the **expected** side of the
comparison the same way, and drops the two-character truncation. A five-level
domain behaves identically either way — the flag fixes a resolution bug, it
does not redefine the common alphabet.

Default OFF, because the truncation is load bearing for the frozen corpora.
`test_financial_labels_truncate_and_never_fire_with_flag_off` pins the defect on
purpose.

---

## 5. What the self-report rules can and cannot establish

This is the part to be careful about in a paper.

**They can establish** that the agent's chosen action is inconsistent with the
appraisal it stated in the same breath, and that the framework detected the
inconsistency, blocked the action, re-prompted, and recorded every step. That is
a real and auditable property of a governed language agent, and it is what the
appraisal-action inconsistency metrics measure. Nothing here retracts it.

**They cannot establish** that the appraisal was *wrong*. A self-report rule has
no access to anything outside the generation it is checking, so an agent whose
labels are internally consistent and jointly detached from the simulated world
passes every rule in `strict` — every year, indefinitely. The framework has no
opinion about that agent, and an audit trail full of approvals is not evidence
that it was behaving sensibly. It is evidence that nothing in the profile was
in a position to disagree.

**They cannot establish faithfulness.** A construct label is an output token.
Treating agreement between two of the model's own outputs as evidence that the
first one described an internal state is the circularity the grounded rules
exist to break, and adding more self-report rules does not weaken it — it is a
property of the antecedent, not of the rule count.

So: report a self-report block as a *coherence* result and a world-grounded
block as a *contradiction* result, keep them in separate columns
(`rules_self_report` and `rules_world_grounded` exist for exactly this), and do
not let a total of "rules triggered" carry both.

---

## 6. Reproducing the runs in this guide

```bash
# flood, grounded profile
python examples/single_agent/run_flood.py --model mock --agents 3 --years 3 \
    --seed 42 --memory-engine humancentric --governance-mode grounded_v1

# irrigation, grounded profile
python examples/irrigation_abm/run_experiment.py --model mock --agents 3 \
    --years 3 --seed 42 --governance-mode grounded_v1
```

The shipped `--model mock` emits `{"decision": N}` and no construct labels, so
every row fails the response-format check first and no thinking rule of any kind
can fire. The tables above come from runs driven by a mock that does emit
labels. Nothing in `broker/` was changed to produce them; if you want to
reproduce them, supply an LLM (or a stand-in) that returns the domain's
construct fields.

`tests/integration/test_grounded_governance_e2e.py` does exactly that, and is
the shortest way to see the whole path work: it drives `ExperimentRunner`
against this repo's flood config under `grounded_v1` with a label-emitting mock,
then asserts on the rows of the resulting
`household_governance_audit.csv` — approved in the quiet years, REJECTED with
`rules_world_grounded=observed_flood_low_threat_inaction` in the flood years,
with the self-report identical on every row.

---

## 7. Related

- `docs/AUDIT_SCHEMA.md` — the `rules_world_grounded` / `rules_self_report` and
  `advise_findings` / `advise_shown` columns, and their key gating.
- `docs/references/yaml_configuration_reference.md` — `governance.advise_mode`,
  `validators.framework_aware_labels`, `audit.grounding_columns`, and the
  `variable` / `scope` condition fields.
- `broker/INVARIANTS.md` — Invariant 5 (domain genericity): the world variables
  live in the domain, never in `broker/`.
