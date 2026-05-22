"""Flood-Risk Household ABM (governed) — Paper 1b reference experiment.

Phase 6C-v2 (2026-05-10): registers FloodDomainPack at import time so
broker pipeline code can dispatch via DomainPackRegistry.get_or_default(
"flood") instead of hardcoded if-domain branches in reflection,
event manager, experiment_runner, and providers.

Validator checks are still auto-registered via
``examples.governed_flood.validators.__init__`` (Phase 6B-1 path).
"""
try:
    from broker.domains.registry import DomainPackRegistry
    from examples.governed_flood.adapters.flood_pack import FloodDomainPack
    DomainPackRegistry.register("flood", FloodDomainPack())
except ImportError:
    # During partial bring-up, broker.domains may not yet be importable.
    # Silent skip preserves prior behaviour. NOTE: this guard is
    # legitimate — examples/ can be imported before broker/ is on the
    # path. It is NOT the same as the unreachable broker-to-broker
    # ImportError fallback removed from ma_manager.py in Phase 6J-B;
    # do not delete this one by analogy.
    pass
