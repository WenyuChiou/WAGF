# Social-tier context injection — canonical reference

**Phase 6S-C deliverable** (2026-05-26). Companion to
`.research/domain_pack_protocol_reference.md`. Audience: anyone
building a new domain that needs social-context signals
("I observe N% of neighbors elevated", "outbreak hotspot in nearby
region", "the dispatcher issued a congestion advisory") rendered
into agent prompts.

Mirrors the Phase 6R-A protocol-reference pattern: this is the
single source of truth for the 3-tier social-context pipeline;
user-facing teaching content
(`docs/guides/HOW_TO_ADD_A_NEW_DOMAIN.md` Step 7) links here rather
than duplicating it.

---

## 1. Tier inventory — 3-tier architecture

WAGF agent prompts assemble context from **three cohesive tiers**.
Each tier maps to a separate context dict slot, has its own
provider, its own verbalisation policy, and its own prompt-template
placeholder family.

| Tier | Scope | Context-dict key | Render function | Primary placeholders |
|---|---|---|---|---|
| **T1 — Personal** | Agent's own state | `personal` | direct field injection | (varies — agent-state-driven, e.g. `{narrative_persona}`) |
| **T2 — Local** | Spatial / social radius | `local["spatial"]` · `local["social"]` · `local["visible_actions"]` · `local["observable_attrs"]` | `tiered.py:507-517` | `{social_gossip}`, `{neighbor_action_summary}`, `my_*` prefixed observables |
| **T3 — Global** | Society-wide signals · institutional policy | `global` · `institutional` | `tiered.py:533-536` | `{global_news}`, `inst_*` prefixed fields |

Render lives in `broker/components/context/tiered.py:format_prompt()`
(approximately lines 480–644). Key statements:

```python
# T2 gossip (tiered.py:507-509)
template_vars["social_gossip"] = (
    "\n".join([f"- {s}" for s in social]) if social else ""
)
template_vars["neighbor_action_summary"] = l.get(
    "neighbor_action_summary", ""
)

# T3 news (tiered.py:533-536)
template_vars["global_news"] = (
    "\n".join([f"- {news}" for news in g]) if g else ""
)
```

## 2. Provider call-graph

Six provider classes populate the tiered context, called in the order
`TieredContextBuilder.build()` (`tiered.py:455-476`) dispatches them.

| Provider | File:line | Tier | Output |
|---|---|---|---|
| `SocialProvider` | `providers.py:153-184` | T2 | `local["social"]` (gossip strings), `local["spatial"]` (aggregates), `local["visible_actions"]` (neighbor decision verbs), `local["observable_attrs"]` |
| `InteractionHub.get_neighbor_action_summary` | `analytics/interaction.py:172-216` | T2 | `local["neighbor_action_summary"]` (single-sentence prose: *"Among your N neighbors last year: M took action X, K took action Y."*) |
| `InteractionHub.get_social_context` | `analytics/interaction.py:324-374` | T2 | Gossip via memory-engine sampling of chatty neighbors' episodic / semantic memories |
| `ObservableStateProvider` | `providers.py:288-364` | T2 / T3 | `context["observables"]` dict — raw aggregate metrics (neighbor count, community rate, regional %); also injects `my_*` prefixed per-agent neighborhood-scope copies (line 343) |
| `PerceptionAwareProvider` | `providers.py:439-541` | filter | LAST in chain — applies the registered domain's `HouseholdPerceptionFilter` to verbalise observables into qualitative descriptors |
| `InstitutionalProvider` | `providers.py:216-237` | T3 | `global` (news list), `institutional` (policy / regime info), `local["environment"]` — pulls from `TieredEnvironment.global_state` / `local_states` / `institutions` |

The provider chain order matters: `PerceptionAwareProvider` MUST run
**after** the raw-data-writing providers so it can verbalise their
output. The chain is configured in
`TieredContextBuilder._build_providers()` (approximately `tiered.py:380-420`).

## 3. Social-graph layer — neighbor-set determination

`broker/components/social/config.py:90-165` houses the dispatcher.
Function `get_social_spec(agent) → SocialGraphSpec` composes a key
from agent attributes and looks it up in `AGENT_SOCIAL_SPECS`:

```python
# config.py:92-165 (post-Phase-6R-B-2 — agent_type required)
def get_social_spec(agent: Any) -> SocialGraphSpec:
    if isinstance(agent, dict):
        agent_type = agent.get("agent_type")  # 6R-B-2: raises on None
    else:
        agent_type = getattr(agent, "agent_type", None)
    if not agent_type:
        raise ValueError(...)
    agent_type_lower = agent_type.lower()
    if agent_type_lower in AGENT_SOCIAL_SPECS:
        return AGENT_SOCIAL_SPECS[agent_type_lower]
    # Household composite-key path
    if agent_type_lower in ("household", "household_owner", "household_renter"):
        composed = f"household_{mg_key}_{tenure_key}"
        if composed in AGENT_SOCIAL_SPECS:
            return AGENT_SOCIAL_SPECS[composed]
    return DEFAULT_SOCIAL_SPEC
```

### `SocialGraphSpec` graph types

| Graph type | Semantics | Example |
|---|---|---|
| `spatial` | Euclidean / Manhattan distance on `(grid_x, grid_y)` within `radius` | `household_nmg_owner: SocialGraphSpec(graph_type="spatial", radius=2)` |
| `global` | Connect to ALL agents (institutional / observer roles) | `government: SocialGraphSpec(graph_type="global")` |
| `filtered_global` | Connect to every agent matching `filter_fn` | `insurance: SocialGraphSpec(graph_type="filtered_global", filter_fn="has_insurance")` |
| `DEFAULT_SOCIAL_SPEC` | Fallback (spatial radius=2) when key not registered | _N/A_ |

### Water-domain specs

Registered in `broker/domains/water/social_specs.py` at package import
time:

- `household_nmg_owner` / `household_nmg_renter`: spatial radius 2
- `household_mg_owner` / `household_mg_renter`: spatial radius 1 (mobility constraint)
- `government`: global
- `insurance`: filtered_global on `has_insurance`

Spatial implementation: `SpatialNeighborhoodGraph` in
`broker/components/social/graph.py:179-330` — `get_neighbors_within_radius(agent_id, radius)`
with fallback `connect-to-k-nearest` when `< fallback_k` (default 2)
agents are within radius.

## 4. Perception / verbalisation — 2-stage pipeline

### Stage 1: Observation → Observable State

`ObservableStateManager.compute()` runs per-metric compute functions
across the agent's neighbor set. Outputs go to
`context["observables"]["by_neighborhood"][agent_id][metric_name]` as
**raw numeric values** (e.g. `neighbor_insurance_rate: 0.45`).

Defined in `broker/components/analytics/observable.py:29-117`.
Scopes: `COMMUNITY` (society-wide) / `NEIGHBORS` (per-agent) /
`TYPE` (per-agent-type) / `SPATIAL` (per-region).

### Stage 2: Observable → Descriptor

`HouseholdPerceptionFilter.filter()` (`perception.py:40-160`) applies
the registered `DescriptorMapping` from the domain pack:

```python
# flood_perception.py:95-109 — flood example
NEIGHBOR_COUNT_DESCRIPTORS = DescriptorMapping(
    field_name="neighbors_insured_description",
    ranges=[
        (0, 1, "no neighbors"),
        (1, 3, "a few neighbors"),
        (3, 6, "some neighbors"),
        (6, 11, "many neighbors"),
        (11, math.inf, "most neighbors"),
    ],
)
FLOOD_DEPTH_DESCRIPTORS = DescriptorMapping(...)
```

The filter:
1. Reads `context["observables"][input_field]` (raw float).
2. Looks up the matching range → string descriptor.
3. Writes `context[output_field]` (e.g. `"neighbors_insured_description": "many"`).
4. Strips the raw `input_field` (so the LLM never sees the float).

### `HouseholdPerceptionFilter._filter_for_mg` (perception.py:179-221)

Marginalised-group (MG) agents currently lose **ALL**
`community_observable_fields` — even SPATIAL-scoped ones that are
agent-specific. Phase 1 audit identified this as Gap #4 (Phase 6S-D
target).

### Domain customisation hooks (Phase 6H Item 5 / Phase 6R-D-1
PerceptionPack)

DomainPack overrides:

```python
class FloodPerceptionMixin:
    def perception_descriptors(self) -> Dict[str, Any]:
        """Maps observable fields to DescriptorMapping rules."""
        return dict(PERCEPTION_DESCRIPTORS)

    def perception_field_policy(self) -> Dict[str, List[str]]:
        """Field-name lists controlling strip / aggregate behaviour."""
        return {
            "dollar_fields": list(DOLLAR_AMOUNT_FIELDS),
            "percentage_fields": list(PERCENTAGE_FIELDS),
            "community_observable_fields": list(COMMUNITY_OBSERVABLE_FIELDS),
            "neighbor_action_fields": list(NEIGHBOR_ACTION_FIELDS),
        }

    def passthrough_agent_types(self) -> Set[str]:
        """Agent types that see RAW numerical data (no verbalisation)."""
        return {"government", "insurance"}
```

`PerceptionFilterRegistry._register_default_filters()` at
`perception.py:341-360` reads these hooks at registry-init time.

## 5. Domain customisation surface — new-domain recipe

To inject social context in a NEW non-water domain (e.g. traffic,
vaccination, supply-chain):

### Step 1 — Register social specs

Inside your example package's `__init__.py` (after broker imports):

```python
from broker.components.social.config import register_social_spec, SocialGraphSpec

# Per-agent-type topology
register_social_spec(
    "commuter",
    SocialGraphSpec(graph_type="spatial", radius=3),
)
register_social_spec(
    "dispatcher",
    SocialGraphSpec(graph_type="global"),
)
```

### Step 2 — Define observable metrics

`broker/components/analytics/observable.py` provides `create_rate_metric`,
`create_count_metric`, `create_sum_metric` factories. Wire them in your
domain's adapter module:

```python
from broker.components.analytics.observable import (
    create_rate_metric, ObservableScope,
)

def create_traffic_observables():
    return [
        create_rate_metric(
            "neighbor_transit_rate",
            condition=lambda a: getattr(a, "uses_transit", False),
            scope=ObservableScope.NEIGHBORS,
        ),
        create_rate_metric(
            "regional_congestion_index",
            condition=lambda a: getattr(a, "delayed_today", False),
            scope=ObservableScope.SPATIAL,
        ),
    ]
```

### Step 3 — Define perception descriptors

In your domain's `<domain>_perception.py`:

```python
from broker.components.social.descriptor import DescriptorMapping

TRAFFIC_DESCRIPTORS = {
    "neighbor_transit_rate": DescriptorMapping(
        field_name="neighbor_transit_description",
        ranges=[
            (0.0, 0.2, "few neighbors switched to transit"),
            (0.2, 0.5, "some neighbors switched to transit"),
            (0.5, 0.8, "many neighbors switched to transit"),
            (0.8, 1.01, "almost everyone switched to transit"),
        ],
    ),
}

PERCEPTION_FIELD_POLICY = {
    "dollar_fields": [],
    "percentage_fields": ["regional_congestion_index"],
    "community_observable_fields": ["regional_congestion_index"],
    "neighbor_action_fields": ["neighbor_transit_rate"],
}
```

### Step 4 — Define visible neighbor actions

In `<domain>_interaction.py` or your DomainPack:

```python
TRAFFIC_VISIBLE_ACTION_SPECS = [
    {
        "state_keys": ["uses_transit"],
        "action": "switched_to_transit",
        "description": "Neighbor {nid} switched to transit",
    },
    {
        "state_keys": ["carpooling"],
        "action": "started_carpooling",
        "description": "Neighbor {nid} started carpooling",
    },
]
```

### Step 5 — Register in `DomainPack` via PerceptionMixin

```python
class TrafficPerceptionMixin:
    def perception_descriptors(self):
        return dict(TRAFFIC_DESCRIPTORS)

    def perception_field_policy(self):
        return PERCEPTION_FIELD_POLICY

    def passthrough_agent_types(self):
        # Dispatchers reason with raw congestion numbers; commuters
        # verbalise.
        return {"dispatcher"}
```

### Step 6 — Reference in prompt template

`examples/<domain>/config/prompts/commuter.txt`:

```
You are a daily commuter.

Recent peer behaviour:
{neighbor_transit_description}
{social_gossip}

Today's regional status: {regional_congestion_index_description}

{response_format}
```

## 6. Prompt placeholder reference — what renders into LLM prompts

| Placeholder | Source | Format | Filter behaviour |
|---|---|---|---|
| `{social_gossip}` | `local["social"]` | Multi-line bulleted list (`"- str1\n- str2"`) | Stripped for MG (community-level filter) |
| `{neighbor_action_summary}` | `InteractionHub.get_neighbor_action_summary` | Single-line prose | Always rendered (no MG strip) |
| `{global_news}` | `global` list | Multi-line bulleted list | Stripped for MG agents (T3 community-level) |
| `{my_<field>}` | `ObservableStateProvider` per-agent injection | Verbalised descriptor (post-filter) | Retained for MG (per-agent scope) |
| `{<field>_description}` | Output of `DescriptorMapping` | Single string | Retained for non-passthrough agents |
| `inst_<field>` | `InstitutionalProvider` | Numeric or short string | Not stripped (institutional policy is visible to all) |
| `{<raw_field>}` | (passthrough only) | Raw float / int | Visible only to `passthrough_agent_types()` set |

## 7. Known gaps — future debt

Identified by Phase 6S Phase 1 audit (Explore agent 1, 2026-05-26).
2 of these (Gap #1 + Gap #4) are addressed by Phase 6S-D
(perception-filter audit); the rest are documented for future work.

1. **Observable injection asymmetry** (Phase 6S-D fix): raw numeric
   fields can reach the LLM prompt for non-passthrough agents if a
   field isn't whitelisted in `percentage_fields`. The perception
   filter chain should enforce strict raw→descriptor transformation
   for every numeric field.
2. **Gossip source opacity** (deferred): gossip strings lack tier
   annotation. An agent receives `"Neighbor X mentioned: 'Y'"` but
   no indication whether Y is recent / belief / hearsay.
3. **Agent-type permission model is binary** (deferred): passthrough
   agents see EVERY numeric field as raw; can't selectively
   verbalise per-field. Paper-3 government agents might want
   community-rate verbalised but neighborhood-rate raw.
4. **MG observable threshold too aggressive** (Phase 6S-D fix): MG
   agents lose ALL `community_observable_fields` regardless of
   scope. SPATIAL-scoped fields are agent-specific and shouldn't be
   stripped.
5. **Visible actions lack confidence** (deferred): legacy hardcoded
   path treats observation as certain. SDK observer path supports
   optional confidence via `result.observation_accuracy` but isn't
   wired through to the prompt.
6. **Placeholder naming inconsistency** (cosmetic, deferred):
   `{social_gossip}` is a bulleted list, `{neighbor_action_summary}`
   is a prose sentence — different formats for similar concepts.

## 8. Maintenance contract

When adding a new tier-aware feature:

1. **Decide tier scope** — T1 / T2 / T3. Don't blur scopes (a
   community-rate observable shouldn't be injected as per-agent T2).
2. **Pick provider** — extend an existing one (`SocialProvider`,
   `ObservableStateProvider`) rather than adding new ones; the
   chain ordering matters and adding providers is high-risk.
3. **Update this doc** — add the new placeholder / metric to the
   relevant section's table.
4. **Update PerceptionPack contract** — if your feature touches
   verbalisation rules, extend `perception_descriptors()` or
   `perception_field_policy()` keys; do NOT add hardcoded paths
   in `broker/components/social/perception.py`.

When in doubt: read the FloodPerceptionMixin
(`examples/governed_flood/adapters/flood_pack.py`) for the canonical
recipe.
