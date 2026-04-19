---
phase: 2 (Tier 2 Item #4)
date: 2026-04-18
scope: broker-memory-governance scope decision
author: Claude
---

# Memory Write Policy — Broker vs Examples Scope Decision

## Question

Audit Gap D2 asked: **is the 2026-04-11 broker-memory-governance generalization (commit `9057097`) framework-level or Paper-3-only?** If Paper-3-only, move to `examples/multi_agent/flood/`.

## Inspection

Files changed by `9057097` under `broker/`:

- `broker/components/memory/{README.md, __init__.py, content_types.py, initial_loader.py, policy_classifier.py, policy_filter.py}`
- `broker/config/{__init__.py, memory_policy.py}`
- `broker/core/{experiment_builder.py, experiment_runner.py}`
- `broker/tests/{test_experiment_builder_policy.py, test_initial_loader.py, test_memory_content_types.py, test_memory_policy_filter.py}`

Key file reviewed: `broker/components/memory/policy_classifier.py`.

## `policy_classifier.py` defaults

```python
_DEFAULT_RULES = {
    "flood_experience": EXTERNAL_EVENT,
    "flood_event": EXTERNAL_EVENT,
    "damage": EXTERNAL_EVENT,
    "insurance_claim": INITIAL_FACTUAL,
    "insurance_history": INITIAL_FACTUAL,
    "social_observation": SOCIAL_OBSERVATION,
    "neighbor_observation": SOCIAL_OBSERVATION,
    "policy_decision": INSTITUTIONAL_STATE,
    "institutional_event": INSTITUTIONAL_STATE,
}
```

## Assessment

1. **Water-domain defaults**, not Paper-3-specific. `flood_experience`, `damage`, `insurance_claim` apply equally to NW single-agent flood and Paper 3 multi-agent flood. These are flood-domain concepts, not multi-agent concepts.

2. **`policy_decision` and `institutional_event`** refer to government/insurance agent actions — which exist in Paper 3 MA flood but NOT in NW single-agent. However these defaults are never REACHED in NW runs because NW households don't emit those categories. They just sit dormant.

3. **Extension point exists**: `classify(metadata, domain_mapping=...)` accepts a per-domain override, so future domains (groundwater, wastewater, etc.) can supply their own `domain_mapping` without modifying the broker.

4. **The rationalization-ratchet problem is domain-general**: any LLM agent that writes its own reasoning back to memory and re-retrieves it can experience this failure mode. NW single-agent doesn't currently trigger the ratchet because its persona prompts don't write-back reasoning aggressively, but a future NW variant could — and would benefit from the same protection.

## Ruling

**KEEP in broker**. The memory-write-policy infrastructure is correctly scoped as framework-level, with domain-specific defaults that happen to be water/flood (appropriate given the framework's current scope). Paper-3-specific concepts (dual-role memory, renter, MA social spillover) are NOT in the broker and correctly live in `examples/multi_agent/flood/`.

## Minor docstring clarification recommended (S2 follow-up)

In `broker/components/memory/policy_classifier.py`, the module docstring could add one sentence:

> "Default rules cover flood-domain categories because flood and irrigation are the framework's current consumer domains. New domains should pass a `domain_mapping` override at classifier construction rather than editing these defaults."

This makes the scope boundary explicit to a future reader. Not urgent; Tier 4 hygiene.

## Implication for NW paper

- Methods v4 section describing `content_type` classification is consistent with this decision.
- No paper rewrite needed.
- No Paper-3 scope bleed into NW narrative.

## Decision closed

Gap D2 resolved. `memory_write_policy` stays in broker. Domain-mapping extension point is the clean separation. Recommended docstring tweak queued as Tier 4.
