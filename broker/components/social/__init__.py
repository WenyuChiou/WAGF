"""Social graph and perception sub-package.

Modules:
    graph           — SocialGraph, NeighborhoodGraph, create_social_graph
    config          — SocialGraphSpec, AGENT_SOCIAL_SPECS
    perception      — HouseholdPerceptionFilter, PerceptionFilterRegistry
    filter_registry — FilterRegistry (Phase 6B-4) for neighbor-filter plugins

Phase 6B-4: register the legacy `has_insurance` neighbor filter at
package import time so `_get_filtered_neighbors` can dispatch via the
registry instead of a hardcoded if/else. Adding a new filter is now a
one-line `FilterRegistry.register(name, fn)` call from any domain
package.
"""
from broker.components.social.filter_registry import FilterRegistry


def _has_insurance_filter(agent) -> bool:
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


FilterRegistry.register("has_insurance", _has_insurance_filter)
