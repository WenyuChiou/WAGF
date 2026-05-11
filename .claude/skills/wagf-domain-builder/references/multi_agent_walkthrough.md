# Multi-Agent Walkthrough (Phase 6E, 2026-05-11)

When the user's S0 interview indicates multiple agent types interacting,
S5 edit-5 (ExperimentBuilder wiring) is materially different from the
single-agent template scaffolded by `broker.tools.scaffold_domain`. This
doc is the canonical reference for that multi-agent path. The
single-agent path stays in `edit_pass_checklist.md`.

Canonical reference example: `examples/vaccination_ma_demo/` — proven
working with 3 agent types (institutional → intermediary → individual)
end-to-end against gemma3:1b on 2026-05-10. Copy this skeleton; don't
write from scratch.

## When the multi-agent path applies

User answer to S0 question 6 is YES (multi-agent). Specifically:
- Two or more distinct `agent_type` values
- At least one agent's decision is consumed as input to another agent's
  decision in the same simulation step
- Cross-agent state is the load-bearing channel (not just shared
  environment variables that happen to be visible to all)

Tier 1 (broadcast comm via env-dict-whitelist): proven to work for ≤6
agent types, ≤200 agents.

Tier 2 (+ spatial gossip via InteractionHub +
SpatialNeighborhoodGraph): proven for vaccination_ma_demo
`--tier2-gossip` mode 2026-05-11.

## The 5 things multi-agent needs that single-agent doesn't

### 1. `lifecycle_hooks.py` writing cross-agent state into `env`

Single-agent uses `with_simulation(environment)` where the environment
class's `execute_skill()` mutates state. Multi-agent uses
`with_lifecycle_hooks(pre_year=, post_step=, post_year=)` instead —
each hook receives `(year, env, agents)` or `(agent, result)` and
mutates the shared `env` dict.

Critical: the env-dict is THE coupling channel. Agent A writes to a
named key; Agent B reads from it via `TieredContextBuilder`'s
`dynamic_whitelist`.

```python
class MyDomainHooks:
    def __init__(self, environment, memory_engine):
        self.env = environment
        # ... set defaults for every cross-agent key

    def pre_year(self, year, env, agents):
        # CRITICAL: see "Dual-dict gotcha" below
        env.update(self.env)
        self.env = env  # alias for the rest of the year
        self.env["year"] = year

    def post_step(self, agent, result):
        if result.outcome not in (SkillOutcome.APPROVED, SkillOutcome.RETRY_SUCCESS):
            return
        decision = result.approved_skill.skill_name  # EXECUTED-ONLY rule
        if agent.agent_type == "institutional_type":
            self.env["public_signal_label"] = ...
            self.env["public_signal_text"] = ...
        elif agent.agent_type == "individual":
            # update per-individual state
```

Read `examples/vaccination_ma_demo/lifecycle_hooks.py` for the canonical
shape. It's ~190 LOC and contains every pattern any multi-agent domain
needs.

### 2. `run_experiment.py` ExperimentBuilder wiring

Three additions vs single-agent:

```python
# a. The whitelist — keys lifecycle_hooks writes AND prompt templates read.
DYNAMIC_WHITELIST = [
    "year",
    "public_signal_label",
    "public_signal_text",
    # ... EVERY cross-agent placeholder
]

# b. TieredContextBuilder with the whitelist
ctx_builder = TieredContextBuilder(
    agents=agents,
    # hub omitted for Tier 1; pass InteractionHub for Tier 2
    memory_engine=memory_engine,
    yaml_path=str(CONFIG_YAML),
    dynamic_whitelist=DYNAMIC_WHITELIST,
    prompt_templates=load_prompt_templates(str(CONFIG_YAML)),
)

# c. ExperimentBuilder with lifecycle hooks + phase order
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
        [["institutional_type"], ["intermediary_type"], ["individual"]]
    )
    .with_governance("strict", str(CONFIG_YAML))
    # ... rest unchanged from single-agent
).build()
```

`with_phase_order([[a, b], [c]])` — agents whose type matches `a` or `b`
run first, then `c`. Within a phase, agents iterate in dict insertion
order.

### 3. Prompt templates referencing whitelisted keys

Each agent type's prompt template references the cross-agent keys as
`{placeholder}` substitutions:

```text
What you know about the broader situation:
- Public health authority advisory this year: {public_signal_label}
  ({public_signal_text})
```

EVERY `{placeholder}` referenced in EVERY prompt template MUST appear
in the `DYNAMIC_WHITELIST` (otherwise `SafeFormatter` renders the
literal string `{public_signal_label}` in the prompt — silent UX bug).
Run `python -m broker.tools.validate_prompt config/agent_types.yaml`
after every prompt edit; it surfaces missing placeholders as WARN.

### 4. `register_social_spec()` for non-default agent types

If your domain has agent types not in the water-domain default registry
(`household_*`, `government`, `insurance`), register them at package
import time so `get_social_spec(agent)` doesn't fall back to the
catch-all `DEFAULT_SOCIAL_SPEC`:

```python
# In examples/<your_domain>/__init__.py (Tier 2 only — Tier 1 doesn't need)
from broker.components.social.config import (
    register_social_spec, SocialGraphSpec,
)

register_social_spec(
    "individual",
    SocialGraphSpec(graph_type="spatial", radius=3),
    overwrite=True,
)
register_social_spec(
    "institutional_type",
    SocialGraphSpec(graph_type="global"),
    overwrite=True,
)
```

Phase 6C-v4 G1b API. Tier 1 broadcast-only demo works without this
(default spatial radius=2 is harmless when no InteractionHub is wired).
Required for Tier 2 (spatial gossip) so `SpatialNeighborhoodGraph`
knows each agent type's expected topology.

### 5. (Optional) `InteractionHub` + `SpatialNeighborhoodGraph` for Tier 2

Skip if Tier 1 (broadcast only). For Tier 2 spatial gossip:

```python
from broker.components.social.graph import SpatialNeighborhoodGraph
from broker.components.analytics.interaction import InteractionHub

individual_positions = {
    aid: (agent.dynamic_state["grid_x"], agent.dynamic_state["grid_y"])
    for aid, agent in agents.items()
    if agent.agent_type == "individual"
}

graph = SpatialNeighborhoodGraph(
    agent_ids=list(individual_positions.keys()),
    positions=individual_positions,
    radius=3.0,
)
hub = InteractionHub(
    graph=graph,
    memory_engine=memory_engine,
    spatial_observables=["vaccinated"],  # attributes to aggregate per neighbor
)

# Then pass hub=hub to TieredContextBuilder instead of None.
```

Each individual's prompt then gets `{neighbor_action_summary}` populated
with what their spatial neighbors decided last year (or a domain-neutral
cold-start string in year 1).

## The dual-dict gotcha (Phase 6E Finding #3 — MUST READ)

`ExperimentRunner` creates a fresh `env = {}` at the start of every
year when no `with_simulation(env)` is configured. If your lifecycle
hook keeps its OWN `self.env` dict and only `env.update(self.env)` once
in `pre_year`, mid-year writes to `self.env` from `post_step` won't
propagate to subsequent agents' context_builder reads.

**The fix is one line.** In `pre_year`, AFTER the update, alias
`self.env = env` so the two dicts become the same object for the rest
of the year:

```python
def pre_year(self, year, env, agents):
    env.update(self.env)   # carry over persistent state
    self.env = env         # ← THE FIX. alias for rest of year.
    self.env["year"] = year
    # ... rest of pre_year
```

Flood Paper 3 doesn't hit this because it uses `with_simulation(
TieredEnvironment(...))` which gives ExperimentRunner a persistent env
object that `advance_year` mutates in place. For non-water multi-agent
without a simulation engine, you MUST use the aliasing pattern.

Symptoms when you forget:
- Prompts show stale state from year start
- Cross-agent coupling appears not to work
- Year-2+ vaccination uptake / community support / advisory signals
  appear "frozen"

`tests/test_multi_agent_coupling.py::TestEnvDictAliasingPattern`
documents both the correct pattern and the negative case for posterity.

## S5 edit-5 checklist (multi-agent)

Run from `examples/<your_domain>_demo/` unless noted.

1. Copy `examples/vaccination_ma_demo/run_experiment.py` as your
   template. Don't write from scratch.
2. Edit `synth_agents()` for your N agent types (grid_x/grid_y only for
   Tier 2 spatial; not needed Tier 1).
3. Edit lifecycle_hooks.py to write the cross-agent keys your domain
   needs. Per-agent-type if/elif branches in `post_step`.
4. Edit `DYNAMIC_WHITELIST` in run_experiment.py to list EVERY key the
   prompts reference.
5. Edit `with_phase_order([[t1], [t2], [t3]])` to declare your execution
   tiers.
6. (Tier 2 only) Build SpatialNeighborhoodGraph + InteractionHub; pass
   `hub=hub` to TieredContextBuilder.
7. Verify config: `python -m broker.tools.validate_prompt
   examples/<domain>_demo/config/agent_types.yaml` — expect OK clean.
8. Smoke: `python examples/<domain>_demo/run_experiment.py --model
   gemma3:1b --years 2 --agents N --seed 42 --output results/smoke_42`
9. Inspect: audit CSVs split per agent_type, all APPROVED, traces
   show cross-agent state actually rendered in prompts.

## Common multi-agent BLOCKERs (with fix path)

| Symptom | Root cause | Fix |
|---|---|---|
| `TypeError: TieredContextBuilder.__init__() missing 1 required positional argument: 'hub'` | Pre-Phase 6E broker | Update broker; signature is now `hub: Optional[InteractionHub] = None` |
| `KeyError: 'skill_id'` at build time | skill_registry.yaml uses `- id:` | Change to `- skill_id:` (different from agent_types.yaml actions block which uses `- id:`) |
| Mid-year cross-agent writes don't reach prompts | Dual-dict gotcha — Finding #3 | `self.env = env` aliasing in pre_year |
| Prompt shows literal `{placeholder}` strings | Key missing from `dynamic_whitelist` | Add the key; rerun smoke |
| Cold-start `neighbor_action_summary` mentions flood vocabulary | Pre-Phase-6E broker (Tier 2 only) | Update broker; text is now domain-neutral |
| `proposed_skill` value confusing reader | Reading `result.skill_proposal.skill_name` in post_step | Use `result.approved_skill.skill_name` (WAGF EXECUTED-ONLY rule from Paper 3) |

## Acceptance criteria (S6 pass)

Multi-agent domain meets S6 pass when ALL hold:

1. `validate_prompt` exits 0 clean
2. `run_experiment.py` exits 0 with N×Y×T traces (N agents, Y years, T agent types)
3. Audit CSV auto-splits by agent_type (one CSV per type)
4. All traces APPROVED or REJECTED with valid reasoning (no `[Adapter:Error]` blocks)
5. Cross-agent state rendered in downstream agents' prompts (spot-check a year-2 individual prompt for institutional output)
6. Tier 1: `dynamic_whitelist` keys all appear in at least one prompt template
7. Tier 2 only: `{neighbor_action_summary}` renders with year-2 neighbor decisions

Hand off to `wagf-experiment-designer` once these pass.

## Reference

- `examples/vaccination_ma_demo/` — canonical 3-agent-type demo
- `examples/multi_agent/flood/` — Paper 3 (4 agent types: government, insurance, household_owner, household_renter)
- `docs/guides/HOW_TO_ADD_A_NEW_DOMAIN.md` "Building a multi-agent domain" section
- `tests/test_multi_agent_coupling.py` — integration tests including dual-dict aliasing pattern
- `broker/components/context/tiered.py:270` — TieredContextBuilder signature with Optional hub
- `broker/components/social/config.py:register_social_spec` — Phase 6C-v4 G1b API
- `broker/components/analytics/interaction.py:170` — get_neighbor_action_summary (Tier 2)
