"""Multi-agent coordination sub-package.

STATUS: EXPERIMENTAL (Multi-Actor / Coordination Extension — Pre-1.0 API).
Inactive on default single-agent-type ``python -m broker.run`` runs unless
explicitly wired via ``run.social`` / ``run.coordinator`` or lifecycle hooks.

Modules:
    bridge      — MultiActorLifecycleBridge
    coordinator — CoordinatorStrategy, GameMaster, PassthroughStrategy
    conflict    — ConflictDetector, ConflictResolver
    messages    — MessagePool, Subscription
    provider    — MessagePoolProvider
"""

from .bridge import MultiActorLifecycleBridge

__all__ = ["MultiActorLifecycleBridge"]
