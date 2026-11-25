# How to add a new domain to WAGF

This guide describes adding a water-resource domain to the WAGF framework. After Phase 6C-v2 (2026-05-10), adding a new domain requires **one class** (a `DomainPack`) and **one registration call**. Zero edits to `broker/`.

> **Phase 6R-D update (2026-05-26)**: `DomainPack` is now formally
> composed of 7 sub-protocols (`ReflectionPack` / `MemoryPack` /
> `SkillPack` / `EventPack` / `PerceptionPack` / `GovernancePack` /
> `SetupPack`) — see the new "Sub-protocol architecture (Phase 6R-D)"
> subsection below. The single-class
> `class XDomainPack(DefaultDomainPack)` pattern this guide teaches
> STILL works (it remains the scaffold default + simplest entry
> point); mixin decomposition is opt-in for advanced cohesion. Full
> per-method consumer-graph reference at
> `docs/references/domain_pack_protocol_reference.md`.

## Minimum DomainPack surface (Phase 6Q-A, 2026-05-26)

`DomainPack` has ~30 methods but only **3 are MUST-override** — every other method has a safe no-op default on `DefaultDomainPack`. The 3-method minimum:

| # | Method | Why it's required |
|---|---|---|
| 1 | `name` (class attribute) | Registry key — used by `DomainPackRegistry.register("<name>", pack)` and every downstream `get_or_default(domain)` lookup. |
| 2 | `reflection_status_text(context)` | Used only where reflection runs: the paper runners, and `python -m broker.run` when `global_config.reflection.enabled` is true. Without this the reflection prompt collapses to a generic identity line; the LLM has nothing domain-flavoured to reason from. |
| 3 | `importance_profiles()` | Without this every memory carries the same baseline (0.5), so retrieval loses domain salience. |

Override additional methods only as your domain needs them — common second-tier additions are `event_handlers()` (env mutations from policy/hazard events), `extreme_actions()` (one-way actions for `ThinkingValidator`), and `affordability_constraints()` (Tier-0 financial gates). The full surface is documented inline at `broker/domains/protocol.py::DomainPack`.

## Prerequisites

- Python 3.10+, the WAGF repo cloned, `pip install -e .` run.
- A model/LLM you can call (the irrigation example uses `gemma3:4b` via Ollama; small smoke tests use `gemma3:1b`).
- Familiarity with the existing irrigation example at `examples/irrigation_abm/` is the fastest way to get the gestalt.

## Architectural overview

WAGF treats each domain as a **plug-in** built from these registry-driven layers:

| Layer | What it does | Where it lives |
|---|---|---|
| **DomainPack** | Single facade for all domain-specific behavior (reflection text, emotion classification, event handlers, etc.) | Your example package, registered to `DomainPackRegistry` |
| **Skill registry** | YAML-driven list of available skills with preconditions and conflicts | `examples/<your_domain>/config/skill_registry.yaml` |
| **Validator checks** | Python functions that veto invalid skill proposals | `examples/<your_domain>/validators/` |
| **Validator rules** | YAML-driven cross-field veto rules | `examples/<your_domain>/config/agent_types.yaml` |
| **Memory engine** | Stores each agent's memories and returns the ones put in the prompt | `global_config.memory.engine_type` in your YAML: `window` (default) or `humancentric` (see [Running a case](#running-a-case-python--m-brokerrun)). The universal engine needs the case's own runner, as the multi-agent flood runner has. |
| **Prompt template** | The chat template that frames each turn for the LLM | `examples/<your_domain>/config/prompts/<agent_type>.txt`, set as `prompt_template_file: prompts/<agent_type>.txt` (relative to the YAML file's folder) |
| **Lifecycle hooks** | Year-by-year orchestration (env update → agent context → reflection → memory) | the `hooks` slot under `global_config.run` in `examples/<your_domain>/config/agent_types.yaml`, a function in your case folder (see [Running a case](#running-a-case-python--m-brokerrun)) |

The broker pipeline calls into your `DomainPack` for any domain-specific decision; everything else is YAML-driven. **No `broker/` edits.**

### Sub-protocol architecture (Phase 6R-D, optional advanced pattern)

Phase 6R-D-1 (2026-05-26) split the `DomainPack` Protocol into seven
sub-protocols, one per cohesive method group:

| Sub-protocol | Methods | Consumer subsystem |
|---|---|---|
| `ReflectionPack` | 4 | `broker/components/cognitive/reflection.py` |
| `MemoryPack` | 6 | `broker/components/memory/*.py` |
| `SkillPack` | 4 | `broker/core/experiment_runner.py` + validators |
| `EventPack` | 2 | multi-agent event dispatcher |
| `PerceptionPack` | 3 | `broker/components/social/perception.py` |
| `GovernancePack` | 8 | governance + validators + `validate_prompt` |
| `SetupPack` | 5 | `broker/core/agent_initializer.py` + orchestration |

Broker consumer subsystems now use **typed accessors** to narrow the
DomainPack surface they need:

```python
# Old (still works):
pack = DomainPackRegistry.get_or_default(domain)
status = pack.reflection_status_text(context)

# New typed accessor (Phase 6R-D-3) — Python type-checker can verify
# the call site only touches ReflectionPack methods:
ref_pack = DomainPackRegistry.get_reflection_pack(domain)
status = ref_pack.reflection_status_text(context)
```

If your pack is large enough to benefit from internal organisation,
the Phase 6R-D-5/6 example packs (`FloodDomainPack` /
`IrrigationDomainPack`) use the **sub-pack
mixin pattern**:

```python
class FloodReflectionMixin:
    def reflection_status_text(self, context): ...
    def reflection_questions(self): ...
    # ... 2 more ReflectionPack methods

class FloodMemoryMixin:
    def importance_profiles(self): ...
    # ... 5 more MemoryPack methods

# ... one mixin per sub-protocol the pack overrides

class FloodDomainPack(
    FloodReflectionMixin,
    FloodMemoryMixin,
    # ... 5 more mixins (or fewer if pack doesn't override every sub-protocol)
    DefaultDomainPack,  # MUST be last — provides no-op fallbacks
):
    name: str = "flood"

    def __init__(self) -> None:
        self._inner = FloodAdapter()  # shared state visible to all mixins
```

**Acceptance criteria for the mixin pattern**:

1. Each mixin class is named `<Domain><SubProtocol>Mixin` (no
   trailing `Pack` to avoid confusion with the Protocol classes).
2. The composite class inherits from the mixins **before**
   `DefaultDomainPack` so Python MRO finds your overrides first.
3. `isinstance(YourDomainPack(), ReflectionPack)` (and the other
   6 sub-protocols + composite `DomainPack`) all return `True` —
   regression test at `broker/tests/test_sub_protocol_split.py`
   verifies this for the production packs.
4. The static gate at
   `broker/tests/test_phase_6r_d_decomposition_gate.py` pins the
   mixin pattern for `Flood / Irrigation`.

**Sub-protocol single-source-of-truth**:
`docs/references/domain_pack_protocol_reference.md` carries the per-method
consumer-graph + MUST/SHOULD/MAY classification for all 32 methods.
Consult before adding a NEW method to `DomainPack` Protocol.

### Inject social-tier context (optional)

If your domain needs agents to reason about peer behaviour
("I observe N% of commuters switched to transit"), community-wide
signals ("drought hotspot in nearby region"), or institutional
narratives ("the dispatcher issued a congestion advisory"), WAGF
provides a **3-tier social-context pipeline**:

- **T1 (personal)** — agent's own state
- **T2 (local)** — neighbours / spatial radius / gossip
- **T3 (global)** — society-wide news / institutional policy

The pipeline is **already wired** in `broker/components/context/tiered.py` —
new domains plug in via the PerceptionMixin hooks
(`perception_descriptors` / `perception_field_policy` /
`passthrough_agent_types`) demonstrated in the flood domain's
`FloodPerceptionMixin` reference and via social-spec registration
in your package's `__init__.py`.

**6-step recipe**: register social specs → define observable
metrics → define perception descriptors → define visible neighbour
actions → register in DomainPack's PerceptionMixin → reference in
prompt template.

Reference implementation: the flood domain — search
`examples/governed_flood/adapters/flood_perception.py` for
`DescriptorMapping` examples + `examples/governed_flood/adapters/flood_pack.py`
for the PerceptionMixin wiring.

Domains that DON'T need social context can skip this step — agents
will still receive their T1 personal block; gossip / community
fields render as empty strings.

## Common pitfalls

### Setup-time pitfalls

> Warning: registered checks are dispatched only when `global_config.governance.domain` and `global_config.governance.dispatch_domain_physical: true` are both set in `agent_types.yaml`; without the flag, registration silently never fires.

| Symptom | Cause | Fix |
|---|---|---|
| All traces have `proposed_skill = default_skill_name` | YAML missing `default_skill:` | Add to `skill_registry.yaml` top level |
| `[DomainPack] No pack registered` warning | Pack class not imported / not registered | Verify `examples/<your_domain>/__init__.py` runs at startup |
| Reflection prompt has no domain text | `reflection_status_text` returns `None` for your agent_type | Check the `getattr(context, "agent_type", None) == "individual"` gate |
| `rules_*_hit` columns are 0 | Validator checks don't set `metadata["category"]` | Add `metadata={"category": "physical"}` (or appropriate slot) to ValidationResult |
| Audit `state_before` missing your key fields | Your env-state dict and your agent-state dict have key collisions | Use distinct names (e.g., `agent_drought_severity` for agent state, `drought_severity` for env) |
| LLM proposes invalid skill names | Skill registry / prompt mismatch | Ensure prompt's enum matches `skill_registry.yaml` skill_ids |

### Parser / validator pitfalls (Phase 6C-v4 findings)

These 6 BLOCKERs can cause a new domain to produce no valid LLM decisions:

| # | Symptom | Root cause | Fix |
|---|---|---|---|
| 1 | `ValueError: slot must be one of (physical, personal, social, semantic, ...)` when registering Python checks | `ValidatorRegistry` does not accept `"thinking"` as a slot — thinking-validator checks come from YAML `thinking_rules:` block, not the registry | Move thinking checks into `agent_types.yaml: thinking_rules:` (preferred — NOT `rules:`; the loader `get_thinking_rules()` at `broker/utils/agent_config.py:859` only recognises `thinking_rules` or `coherence_rules`. A bare `rules:` block is silently dead config — Phase 6N-C 2026-05-23 finding). Python `BuiltinCheck` callables can only register under physical/personal/social/semantic slots. |
| 2 | Prompt template renders with `[N/A]` literals | Unfilled custom `{placeholder}` — broker only auto-fills `{narrative_persona}, {memory}, {skills}, {rating_scale}` and any agent-attribute `{xxx}` | Use only the 4 standard placeholders; for custom narrative, set agent attributes (e.g. `agent.water_situation_text`) in your lifecycle hook |
| 3 | Logs say `Empty/Null response received` but Ollama responds (verify via curl) | The log message conflated LLM-empty with parser-side rejection. Post-v4 the broker distinguishes: `LLM returned empty response (...)` vs `LLM responded (N chars) but parser rejected — see [Adapter:Error] diagnostic above` | If you see the second message, look at the `[Adapter:Error]` diagnostic block which shows `raw_output`, `parse_layer reached`, `expected keys`, `valid skills for this agent_type`. The diagnostic names the exact gap. |
| 4 | `[Adapter:Error]` diagnostic says LLM JSON keys don't match expected | YAML `shared.response_format.fields[].key` (e.g. `susceptibility_assessment`) must match the EXACT key the LLM emits in JSON (per your prompt example) | Sync prompt template's JSON example keys with YAML schema keys. Currently manual; v5 will auto-derive `{response_format}` from YAML to eliminate this risk. |
| 5 | `[Adapter:Error]` diagnostic shows `valid skills for this agent_type: []` | Missing `actions:` block under your agent type in `agent_types.yaml` | Add `actions:` block listing every skill ID + aliases. `skill_registry.yaml`'s `eligible_agent_types` is NOT auto-translated. See the irrigation config reference. |
| 6 | `[Governance:Initial] ... missing required fields: <appraisal_key>, ...` even though LLM JSON contains those keys | Missing `parsing.constructs:` block. Parser doesn't know to extract `appraisal_key.label` → `APPRAISAL_LABEL` construct without this mapping | Add `parsing:` block with `constructs:` mapping each construct name to its JSON key + label regex. See the irrigation config reference. |

If your smoke run produces 0 traces and the error doesn't match any row above, run with the in-built diagnostic by checking the `[Adapter:Error]` block in stdout. The diagnostic was added in Phase 6C-v4 (commit `bd86634`) specifically to make new-domain debugging tractable.

### One-command scaffolding (Phase 6C-v4 cycle 4, 2026-05-10)

You almost never want to hand-write the directory + YAML + DomainPack from scratch. Generate a minimal working skeleton with one command:

```bash
python -m broker.tools.scaffold_domain energy_consumer \
    --output examples/energy_demo \
    --skills "increase_use,maintain_use,decrease_use"
```

This writes 10 files (12 with `--framework custom`) that already:

- Pass `validate_prompt` clean on first run (no manual sync needed)
- Use the broker-filled `{response_format}` placeholder (no hand-rolled JSON to drift)
- Include all 6 required YAML blocks identified by the Phase 6C-v4 BLOCKER inventory
- Wire up DomainPack registration and the validator registry
- Write `world.py` (a `SyntheticEnvironment` and `build_world(ctx)`) and a `global_config.run` block (`world: world:build_world`, governance `default`, 3 years, 5 agents, output `results/smoke`). There is no runner file: `python -m broker.run` runs the case.

The output folder name must be a Python identifier, because `broker.run` imports the case folder as a package.

Pass `--framework custom` to also scaffold a `cognition/` package with framework-registration boilerplate (use this when your domain needs a NEW psychological model like HBM, TPB, etc.). Otherwise the default uses pre-registered PMT and skips `cognition/` entirely.

Pass `--physical-only` for decisions with no appraisal step (a pump schedule, a gate setting). It writes `psychological_framework: none` explicitly: no rating scale, no appraisal fields or constructs, a prompt without appraisal wording, and one retry setting (`global_config.governance.max_retries: 3`). It cannot be combined with `--framework`.

Pass `--magnitude` to also scaffold the agent's action number on [0, 1] (see [The action number](#the-action-number)). It combines with `--framework` and with `--physical-only`.

Next, edit `config/prompts/agent.txt`, the DomainPack adapter, and `world.py` to describe your specific domain. The scaffold is a starting point — not a finished example. Then run it:

```bash
python -m broker.run examples/energy_demo/config/agent_types.yaml --model mock --years 1 --agents 1
```

Before the run starts, `broker.run` prints a header line `[broker.run] <config> | model=mock years=1 agents=1 output=<dir>`. With the mock model the empty scaffold then prints retry warnings, including `Max retries (3) reached`; that is expected. The run worked if the command exits with code 0. A finished output folder is never overwritten: pass a new `--output`, or move the old folder aside.

### The action number

When an agent chooses how much to do (how much to release, how much to cut), that number is its action number. A new case puts it on [0, 1], so 0.5 means half. Declare it as a numeric response field:

```yaml
response_format:
  fields:
    - { key: "magnitude", type: "numeric", min: 0, max: 1, unit: "fraction", required: true,
        description: "Fraction from 0 to 1 (0.5 means half), for example 0.5" }
```

- **The scaffold writes it for you.** `python -m broker.tools.scaffold_domain <domain> --magnitude` adds this field, a prompt line asking for a fraction, a `world.py` that uses the number, and a `mock_llm.py` (wired through the `mock` slot) so `--model mock` answers with 0.35 and you can see a number on [0, 1] reach the world. It works with the default framework and with `--physical-only`. Without the flag the output is unchanged.
- **The parser clamps.** It reads the response field of `type: numeric` (named `magnitude_pct`, then `magnitude`, else the first numeric field) and clamps the model's answer to the field's `min` and `max`, with a parsing warning. A model that answers 50 on a 0 to 1 field is recorded as 1.0. So the prompt must ask for a fraction in plain words; the `max: 1` is a safety net, not the instruction.
- **The world reads `parameters["magnitude_pct"]`.** In `execute_skill(approved_skill)`, `approved_skill.parameters.get("magnitude_pct")` holds the number. That name is only the carrier: it holds the [0, 1] value, and rules see it as `proposed_magnitude`. It is absent when the model gave none.
- **Checks.** `validate_prompt` warns on a field named `magnitude` or `magnitude_pct` whose `max` is above 1 or missing, and `--strict` makes that an error. `python -m broker.run CONFIG --strict-keys` (or `run.strict_keys: true`) refuses it with exit code 2. A case that keeps another scale, such as a percent or a flow in cubic metres per second, should name its field something else (`release_pct`, `release_rate_cms`).
- **Limit: do not turn on `multi_skill` with a [0, 1] action number.** The second action's number is read as a whole number, and a field `min` of 0 counts as unset, so it must lie from 1 to the field's `max` (1 to 100 when none is declared). An answer of 0.35 becomes 0 and is dropped with a warning. Paper cases keep their own scales and are not affected.

### Running a case: `python -m broker.run`

`python -m broker.run CONFIG` is the single entry for every new case (`broker/run/_entry.py`). It reads defaults and Python slots from `global_config.run` in the agent-types YAML; command-line flags override them. It pins `TieredContextBuilder` and writes the reproducibility manifest plus `broker_run.json` (the settings and slots it used). The paper runners (`examples/irrigation_abm/run_experiment.py` and the flood runners) keep their own commands.

```yaml
global_config:
  run:
    world: world:build_world        # your model; default is a tiny stand-in world
    agents: agents:build_agents     # optional
    hooks: hooks:build_hooks        # optional
    validators: checks:build_checks # optional
    mock: mock:build_mock           # optional, used only with --model mock
    model: mock
    years: 3
    agent_count: 5
    seed: 42
    output: results/smoke           # relative to the case folder
    governance: default
    skill_registry: skill_registry.yaml  # relative to this YAML's folder
    workers: 1
    phase_order: [[farmer], [regulator]] # multi-agent only
```

Every key is optional. An unknown `run:` key is refused. Each slot is `module:function`, and the function takes one argument, `ctx` (a `broker.run.RunContext` with the config, case folder, model, years, agent count, seed, output folder and the objects built so far).

| Slot | The function returns | When absent |
|---|---|---|
| `world` | Your environment object (`advance_step()` and `execute_skill(...)`). For a coupled model, return `broker.run.Coupled(contract, sources, domain)`. | A tiny stand-in world that advances the year and executes every approved action successfully, with no state change |
| `agents` | A dict of agent name to `BaseAgent` | `agent_count` agents are built for the one agent type in the YAML, with every skill in the skill registry that is eligible for that type. More than one agent type is refused until you set `agents`. |
| `hooks` | A dict of lifecycle hooks: `pre_year`, `pre_step`, `post_step`, `post_year`, `post_step_end`. An optional `after_run(output_dir)` runs once after the run. | No hooks |
| `validators` | A sequence of custom validator callables | None |
| `mock` | A dict of agent type to scripted responder (a function that returns the model's reply) | The built-in mock model reply. Used only with `--model mock`. |

Defaults when neither the YAML nor the command line sets a value: model `mock`, years 1, agents 1, seed 42, governance `default`, workers 1, output `results/<config file name without .yaml>` in the case folder, skill registry `skill_registry.yaml` next to the YAML.

Command-line overrides: `--model`, `--years`, `--agents`, `--seed`, `--output`, `--governance`, `--skill-registry`, `--workers`, `--thinking-mode`, `--slot NAME=module:attr` and `--allow-module dotted.name`. On the command line `--output` and `--skill-registry` are relative to the current directory, not to the case folder.

**Import rule.** A slot in the YAML may import only modules inside the case's own folder: the YAML's folder, or its parent when that folder is named `config`. Real paths are checked, so `..`, symlinks and junctions that leave the folder are refused with a clear error. Any other module needs a command-line flag: `--allow-module dotted.name` or `--slot name=dotted.name:attr`. The case folder name must be a Python identifier. The same rule covers `decider: {name: parametric, params: {target: module:attr}}` in an agent type: the target must name a module in the case folder by its importable dotted name (for example `examples.my_domain.decider:MyDecider`), or be allowed with `--allow-module`.

**Physical-only cases.** For agents with no appraisal, set `psychological_framework: none`. `ExperimentBuilder.build()` and `validate_prompt` then refuse a `none` agent that still has appraisal fields, constructs (its own or inherited from the `default` block), `{rating_scale}` or PMT wording, or `construct` references in rules (`AgentTypeConfig.check_theory_free` in `broker/utils/agent_config.py`). An agent type with no declared framework still falls back to PMT, with one warning per agent type.

**Multi-agent cases.** Only `phase_order` comes from the YAML. A social graph, a different memory engine per agent type, or the universal engine still needs the case's own runner, as the paper runners have.

**Memory, reflection and prompt size.** `global_config.memory.engine_type` picks one engine for the whole run:

- `window` (the default): the prompt gets the most recent `retrieval_top_k` memories. Set `retrieval_top_k` (default 3) under `memory:` in the agent type block, or in the `default` block; it is not read from `global_config.memory`. A `global_config.memory.window_size` you write caps how many the engine keeps, so the prompt holds the smaller of the two; without it the engine keeps the last 100.
- `humancentric`: the prompt gets the `window_size` most recent memories plus the `top_k_significant` most important ones the engine has moved to long-term memory (a memory with importance at or above `consolidation_threshold` moves there by chance, or always with `deterministic_consolidation: true`). `retrieval_top_k` does not apply. `broker.run` uses window_size 3, top_k_significant 2 and ranking_mode legacy unless the YAML says otherwise, and seeds the engine with the run seed (or `memory.seed`).

Any other engine name is refused. Reflection is off unless `global_config.reflection.enabled` is true. Then, after the case's own `post_year` hook, each agent whose turn it is (every `interval` years, default 1, and in a year it ran a skill listed in `reflection.triggers.decision_types`) gets a reflection prompt built from its retrieved memories and the `questions` of its agent type. The reply is stored as a memory `Reflection (year N): ...` with importance `importance_boost` (default 0.9), so the humancentric engine keeps it in long-term memory, and logged in `reflection_log.jsonl`. Under `--model mock` the reply is a fixed line. Settings `broker.run` cannot honour (a `batch_size` other than 1, the `crisis`, `periodic_interval` and `institutional_threshold` triggers, the grounded-reflection keys, `keep_latest_only` with the window engine) are refused. The engine and reflection settings used, and how many reflections were stored, are written to `broker_run.json`. The context builder refuses a prompt whose estimated size (characters ÷ 4) is over 16384 tokens, a default with no YAML key, and never cuts a prompt short. `llm.num_ctx` is not checked against the prompt.

**Provenance.** The manifest's `run_environment` records the WAGF version, the versions of its dependencies, the operating system, the Ollama server version (Ollama models only), and the WAGF source commit when WAGF is a git checkout. `broker.run` also records four checks in `broker_run.json`: a clean git tree (both the current directory's tree and the WAGF source tree), a model digest, the metadata lookups, and the manifest write. Add `--strict-provenance` to turn a failed check into a refusal. A dirty tree, a missing digest or a failed metadata lookup stops the run before it starts (exit 2). A failed manifest write is reported after the run (exit 1). Mock and cloud models have no digest, so that check is marked not applicable; the other three still apply. The git checks read the working tree of the current directory, so run from inside a git checkout. To share a run, use `python reproduction/check_share.py --stage <dest> <output folder>`.

### Pre-flight check before first run (Phase 6C-v4 cycle 3, 2026-05-10)

Before running your first experiment, run the static validator to catch the 6 BLOCKERs at config time:

```bash
python -m broker.tools.validate_prompt examples/<your_domain>/config/agent_types.yaml
```

Exit codes:

- `0` — clean (or only WARN-level issues)
- `1` — at least one ERROR (will produce 0 valid LLM decisions if run)

The CLI checks:

1. Each agent type declares `actions:` (either top-level or nested under `parsing.actions`)
2. Every `response_format.fields[].construct` has a matching `parsing.constructs:` entry
3. Inline JSON example keys in the prompt match `response_format.fields[].key` (catches the Finding 4 typo case — `susceptibility_appraisal` vs `susceptibility_assessment`)
4. Every `{placeholder}` in the prompt is either broker-filled or YAML-declared (WARN; many domains intentionally fill custom placeholders via lifecycle hooks)
5. The `prompt_template_file` path actually resolves (handles both `yaml-dir-relative` and `example-root-relative` conventions). A path found only from a parent folder gets a WARN, because `python -m broker.run` looks only in the YAML file's folder.

   `broker.run` refuses (exit 2) a `prompt_template_file` it cannot find there, and an agent type that sets both `prompt_template` and `prompt_template_file`. Write the path from the YAML file's folder, for example `prompts/<agent_type>.txt`.

To restrict checking to one agent type:

```bash
python -m broker.tools.validate_prompt agent_types.yaml --agent-type household_owner
```

Use `--strict` to fail on warnings as well as errors (useful in CI).

### Multi-agent orchestration: `from_domain()`

Removed 2026-09 (unused expansion); see CHANGELOG [Unreleased]. (`PhaseOrchestrator` had no production importer; multi-agent runners order phases via `ExperimentBuilder.with_phase_order()` instead.)

### Custom social specs: `register_social_spec()`

If your domain's agents have different social graph topology than the water-domain defaults (spatial + household_* / global + government), register them at domain import time:

```python
# In examples/<your_domain>/__init__.py
from broker.components.social.config import (
    register_social_spec, SocialGraphSpec,
)

register_social_spec(
    "irrigation_individual",
    SocialGraphSpec(graph_type="spatial", radius=3),
)
register_social_spec(
    "energy_consumer",
    SocialGraphSpec(graph_type="global"),
)
```

Without registration, unknown agent types fall back to `DEFAULT_SOCIAL_SPEC` (spatial, radius=2). The fallback works but is rarely what a domain author wants — register explicitly for clarity.

### Building a multi-agent domain (Phase 6E, 2026-05-10)

Multi-agent domains (multiple agent types interacting via cross-agent state) need a few extra wiring steps — see `examples/multi_agent/flood/` (Paper 3 multi-agent flood, 402 agents × 13 yr, production-grade reference) for the canonical multi-agent pattern.

**The cross-agent coupling pattern (the load-bearing one)**:

WAGF multi-agent uses an **env-dict-whitelist** pattern. There is NO direct agent-to-agent method call. Instead:

1. A lifecycle hook's `pre_year` / `post_step` writes cross-agent state to a shared `env` dict (e.g. `env["advisory_strength_label"] = "strong"`).
2. The `TieredContextBuilder` is constructed with `dynamic_whitelist=[...keys...]`. Whitelisted keys are auto-injected into EVERY agent's context.
3. Each agent's prompt template references the keys as `{placeholder}` substitutions.

This pipeline (`env → whitelist → context → template_vars → SafeFormatter`) has **zero flood-specific branching in broker/** per Phase 6E Phase 1 trace audit. The whitelist literal in your multi-agent case's own runner IS the abstraction point — declaring `crop_yield`, `advisory_strength`, `commute_congestion`, or any other domain-specific cross-agent variable is one-line.

**Concrete pattern (from `examples/multi_agent/flood/run_unified_experiment.py`)**:

```python
from broker.components.context.tiered import TieredContextBuilder, load_prompt_templates

# Cross-agent state keys — must match EVERY key the lifecycle hook
# writes AND EVERY placeholder the prompt templates reference. The full
# This is a representative slice of cross-agent keys.
# A key in your prompt template but missing from this list will render
# as the literal string "{key}" in the prompt — confusing for small LLMs
# and silent at runtime (the only signal is `validate_prompt` WARN).
DYNAMIC_WHITELIST = [
    "year",
    "advisory_strength_label",
    "advisory_text",
    "drought_severity_label",
    "community_support_text",
    # ...add EVERY cross-agent placeholder your prompts reference.
    # See examples/multi_agent/flood/run_unified_experiment.py for the full
    # complete list.
]

ctx_builder = TieredContextBuilder(
    agents=agents,
    # hub omitted (or hub=None) for non-spatial domains — no
    # InteractionHub means no gossip / neighbor sharing
    memory_engine=memory_engine,
    yaml_path=str(CONFIG_YAML),
    dynamic_whitelist=DYNAMIC_WHITELIST,
    prompt_templates=load_prompt_templates(str(CONFIG_YAML)),
)

runner = (
    ExperimentBuilder()
    .with_agents(agents)
    .with_lifecycle_hooks(
        pre_year=hooks.pre_year,
        post_step=hooks.post_step,
        post_year=lambda year, ags: hooks.post_year(year, ags, memory_engine),
    )
    .with_context_builder(ctx_builder)
    .with_phase_order(
        [["water_authority"], ["water_district"], ["individual"]]
    )
    # ... rest of builder chain
).build()
```

**`with_phase_order([[t1], [t2], [t3]])`** — agents whose `agent_type` matches `t1` execute first; their `post_step` writes new env values; then `t2`'s context_builder reads those values before deciding. Within a phase, agents execute in the order they appear in the agent dict. This is what gives you "institutional → intermediary → citizen" cross-tier information flow.

**CRITICAL — the dual-dict gotcha (Phase 6E Finding #3)**:

When you DON'T provide a `.with_simulation(env)` engine, `ExperimentRunner` creates a fresh `env = {}` at the start of each year and passes it to your `pre_year(year, env, agents)`. If your lifecycle hook keeps its own `self.env` dict separately, **mid-year writes to `self.env` won't propagate to `ctx_builder`** because `ctx_builder` reads from the runner's `env`, not yours.

The fix is one line — alias `self.env = env` in pre_year so the two are the same dict for the rest of the year:

```python
def pre_year(self, year, env, agents):
    # First sync any persistent state we carried over from last year:
    env.update(self.env)
    # Then ALIAS self.env to runner's env — post_step writes now land
    # directly in the dict ctx_builder reads.
    self.env = env
    self.env["year"] = year
    # ... rest of pre_year
```

Flood Paper 3 doesn't hit this because it uses `.with_simulation(TieredEnvironment(...))` which returns a persistent env dict that `advance_year` mutates in place. For multi-agent domains WITHOUT a simulation engine, use the aliasing pattern above.

**Reference**: `examples/multi_agent/flood/` — Paper 3 multi-agent flood (production-grade). The `lifecycle_hooks` directory carries the canonical aliasing implementation.

**Skill registry schema asymmetry**: `skill_registry.yaml` uses `- skill_id: <id>` (different from `agent_types.yaml` actions block which uses `- id: <id>`). This is an artefact of WAGF's history. The `validate_prompt` CLI does not check skill_registry.yaml's schema; the broker raises `KeyError('skill_id')` at experiment-build time if you use the wrong field. Phase 6C-v4 `scaffold_domain` was patched in Phase 6E to emit the correct field; if you hand-write a skill_registry.yaml, use `skill_id:`.

## What you DO NOT have to do

- ✗ Edit `broker/components/cognitive/reflection.py` — DomainPack handles it
- ✗ Edit `broker/core/experiment_runner.py` — DomainPack handles it
- ✗ Edit the multi-agent event dispatcher — DomainPack handles it
- ✗ Edit `broker/domains/water/validator_bundles.py` — registry handles it
- ✗ Edit `broker/components/context/providers.py` — DomainPack handles it

## Reference

- `examples/irrigation_abm/` — reference implementation (water demand)
- `examples/governed_flood/` — reference implementation (flood adaptation)
- `broker/domains/protocol.py` — DomainPack Protocol contract (Phase 6R-D-1: 7 sub-protocols defined here)
- `broker/domains/default.py` — DefaultDomainPack no-op fallback
- `broker/domains/registry.py` — DomainPackRegistry semantics (Phase 6R-D-3: typed accessors `get_<x>_pack`)
- `tests/test_domain_pack_contract.py` — regression tests; copy/paste pattern for your own pack
- `examples/multi_agent/flood/` — Paper 3 multi-agent reference (production-grade)
- `tests/test_multi_agent_coupling.py` — integration tests covering Findings #1 and #3
- **`docs/references/domain_pack_protocol_reference.md`** (Phase 6R-A) — canonical per-method consumer-graph + MUST/SHOULD/MAY classification for all 32 DomainPack methods. Consult when planning your overrides.
- **`broker/tests/test_sub_protocol_split.py`** (Phase 6R-D-1) — pins the 7-sub-protocol structure + isinstance contract for registered packs.
- **`broker/tools/gen_test_fixture.py`** (Phase 6R-A) — generate a minimal test-fixture DomainPack package without paper-grade scaffolding overhead.
- **`broker/tools/compare_audit_csv.py`** (Phase 6R-C-0) — column-aware audit byte-identity diff (normalises timestamps + set iteration). Use for paper-1b byte-identity verification on any refactor that touches generic broker code.

## Asking for help

Open an issue at the WAGF repo with the tag `new-domain` and your example
package as a tarball. Include the smoke test output and which step failed.
