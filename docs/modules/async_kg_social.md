# Asynchronous Knowledge-Graph Social Engine

This module provides a domain-generic, topology-scoped asynchronous social knowledge graph for multi-actor simulations. It complements the synchronous `SocialProvider` and `SocialMediaProvider` in `broker/components/context/providers.py` by storing structured, delayed, and expiring social facts in memory and synchronizing them into agent memory under Invariant 7 (`broker/INVARIANTS.md`).

---

## 1. Core Components

- `broker/components/social/knowledge_graph.py (KnowledgeTriple)`: Dataclass representing a social fact (`subject`, `predicate`, `obj`, optional numeric `value`, rendered `text`, `author_id`, `author_role`, `published_period`, `delivery_delay`, optional `ttl_periods`, `visibility`, `target_ids`, `confidence`, and `metadata`). Exposes `available_period = published_period + delivery_delay`.
- `broker/components/social/knowledge_graph.py (AsyncKnowledgeGraph)`: In-memory store managing delayed visibility, TTL expiry, topology-based visibility filtering, deterministic age-decayed ranking, idempotent memory synchronization, and snapshot serialization.
- `broker/components/social/kg_provider.py (KnowledgeGraphSocialProvider)`: `ContextProvider` subclass (`broker/components/context/providers.py (ContextProvider)`) that queries visible triples for the target observer, optionally syncs unseen triples to a memory engine, and populates `context[context_key]` (default `"social_gossip"`) for `broker/components/context/tiered.py (TieredContextBuilder)`.
- `broker/components/social/__init__.py`: Re-exports `AsyncKnowledgeGraph`, `KnowledgeTriple`, and lazily resolves `KnowledgeGraphSocialProvider` while preserving existing exports and `FilterRegistry` registrations.

---

## 2. Asynchronous Timing and Visibility Scopes

### Timing Rules

- **Delayed delivery**: A triple asserted at `published_period` with `delivery_delay >= 0` is invisible before `available_period = published_period + delivery_delay` and becomes visible when `available_period <= current_period`.
- **Expiration (TTL)**: When `ttl_periods` is set, the triple remains visible while `current_period < available_period + ttl_periods` and is excluded once that window elapses.
- **Age-decayed ranking**: Visible triples are ranked deterministically by `confidence * age_weight(available_period, current_period, half_life_periods)` using `broker/components/social/post.py (age_weight)`, breaking ties deterministically by recency and insertion order.

### Visibility Scopes

| Scope | Resolution |
| :--- | :--- |
| `"global"` | Visible to every observer |
| `"neighbors"` | Visible to neighbors returned by `broker/components/social/graph.py (SocialGraph.get_neighbors)` |
| `"followers"` | Visible to observers that follow the author via `broker/components/social/follower_network.py (FollowerNetwork.get_followed)` |
| `"direct"` | Visible only to observers listed in `KnowledgeTriple.target_ids` |

---

## 3. Invariant 7 and Memory Synchronization

Social knowledge-graph facts represent **only** executed actions and world or institutional outcomes. When `strict_no_governance_trace=True` (the default), `broker/components/social/knowledge_graph.py (AsyncKnowledgeGraph.assert_fact)` and `broker/components/social/knowledge_graph.py (AsyncKnowledgeGraph.record_executed_action)` inspect triple fields and metadata against `broker/core/run_integrity.py (GOVERNANCE_PHRASES)` and raise `ValueError` if any governance-trace phrase is present.

`broker/components/social/knowledge_graph.py (AsyncKnowledgeGraph.sync_to_memory)` maintains a per-observer delivered-triple cursor so each triple is written at most once per observer, even when delayed triples become visible out of insertion order. Writes include `metadata={"origin": "social", "period": current_period, "importance": ..., "emotion": "neutral", "source": "social"}` so `broker/components/memory/origin_gate.py (OriginGate)` accepts and logs them into `memory_log.jsonl`.

---

## 4. Usage

```python
from broker.components.context.tiered import TieredContextBuilder
from broker.components.social import AsyncKnowledgeGraph
from broker.components.social.graph import CustomGraph

graph = CustomGraph(["A1", "A2"], lambda _ids: [("A1", "A2")])
kg = AsyncKnowledgeGraph(social_graph=graph, half_life_periods=2.0)

kg.record_executed_action(
    agent_id="A1",
    agent_role="provider",
    action_name="adjust_capacity",
    period=1,
    number_text="0.25",
    delivery_delay=1,
    visibility="neighbors",
    outcome_text="capacity adjusted",
)

period_state = {"period": 2}
provider = kg.as_context_provider(
    lambda: period_state["period"],
    memory_engine=memory_engine,
    top_k=5,
)
builder = TieredContextBuilder(
    agents=agents,
    memory_engine=memory_engine,
    extend_providers=[provider],
)
```

Verified by `broker/tests/test_async_kg_social.py`.
