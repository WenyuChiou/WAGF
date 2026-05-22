"""Flood-Risk Household ABM (governed) — Paper 1b reference experiment.

Phase 6C-v2 (2026-05-10): registers FloodDomainPack at import time so
broker pipeline code can dispatch via DomainPackRegistry.get_or_default(
"flood") instead of hardcoded if-domain branches in reflection,
event manager, experiment_runner, and providers.

Phase 6J-D (2026-05-22): also imports ``.validators`` on package
import so the flood builtin validator checks register without
``broker/domains/water/validator_bundles.py`` having to reverse-import
from ``examples/`` (the prior lazy ``_ensure_flood_registered``
fallback was removed). Any code that touches anything under
``examples.governed_flood.*`` triggers this ``__init__.py`` and the
``validators`` import that follows, populating ``ValidatorRegistry``
before the first call to ``build_domain_validators("flood")``.
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

# Register the flood builtin validator checks. Kept in its own
# try/except so a transient ``validators`` import failure cannot mask
# the DomainPack registration above (and vice versa).
try:
    from examples.governed_flood import validators  # noqa: F401
except ImportError:
    pass
