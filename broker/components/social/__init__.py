"""Social graph and perception sub-package.

STATUS: EXPERIMENTAL (Multi-Actor / Social Extension — Pre-1.0 API).
Inactive on default single-agent-type ``python -m broker.run`` runs unless
explicitly wired via lifecycle hooks or ``social_feeds.enable: true``.
Subject to interface evolution in follow-up multi-actor and asynchronous
knowledge-graph social studies.

Modules:
    graph           — SocialGraph, NeighborhoodGraph, create_social_graph
    config          — SocialGraphSpec, AGENT_SOCIAL_SPECS
    perception      — QualitativePerceptionFilter, PerceptionFilterRegistry
    filter_registry — FilterRegistry (Phase 6B-4) for neighbor-filter plugins
    knowledge_graph — AsyncKnowledgeGraph, KnowledgeTriple
    kg_provider     — KnowledgeGraphSocialProvider

Phase 6B-4: register the legacy `has_insurance` neighbor filter at
package import time so `_get_filtered_neighbors` can dispatch via the
registry instead of a hardcoded if/else. Adding a new filter is now a
one-line `FilterRegistry.register(name, fn)` call from any domain
package.
"""
from broker.components.social.filter_registry import FilterRegistry


def _has_account_state_filter(agent) -> bool:
    """Default flood-domain filter: include only agents whose
    `has_insurance` attribute is truthy. Lookup tolerates dict-like
    agents and object agents (mirrors `_get_agent_attr` in config.py)."""
    if isinstance(agent, dict):
        if "has_insurance" in agent:
            return bool(agent["has_insurance"])
        ds = agent.get("dynamic_state", {})
        if isinstance(ds, dict) and "has_insurance" in ds:
            return bool(ds["has_insurance"])
        return False
    return bool(getattr(agent, "has_insurance", False))


FilterRegistry.register("has_insurance", _has_account_state_filter)


def __getattr__(name: str):
    """Lazily resolve experimental social KG exports so flag-OFF runs never load them."""
    if name in ("AsyncKnowledgeGraph", "KnowledgeTriple"):
        from broker.components.social import knowledge_graph

        return getattr(knowledge_graph, name)
    if name == "KnowledgeGraphSocialProvider":
        from broker.components.social.kg_provider import KnowledgeGraphSocialProvider

        return KnowledgeGraphSocialProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "FilterRegistry",
    "AsyncKnowledgeGraph",
    "KnowledgeTriple",
    "KnowledgeGraphSocialProvider",
]
