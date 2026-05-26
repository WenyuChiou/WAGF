"""
Domain packs — pluggable domain-specific content for the governance framework.

Phase 6Q-G (2026-05-26): auto-discovery removed. Pre-6Q-G this
package ran ``_discover_domain_packs()`` at module-load time —
``pkgutil.iter_modules(__path__)`` scanned every sub-package under
``broker/domains/`` and invoked its ``register()`` function. Even a
bare ``from broker.domains.protocol import DomainPack`` triggered
the package ``__init__``, which then unconditionally loaded
``broker.domains.water`` (the only registered sub-package) +
``broker.domains.water.pmt`` + ``utility`` + ``financial`` +
``cognitive_appraisal`` + ``thinking_checks`` + ``social_specs`` —
seven water-namespace modules pulled into sys.modules for every
non-water consumer. This was the root cause of the Phase 6Q-F-1
runtime gate failure.

**New registration contract (post-6Q-G)**: each domain still
self-registers via its ``__init__.py`` module-level call at the
bottom of the file, but the trigger is the **explicit import** of
that sub-package — NOT auto-discovery. Production paths that need
water frameworks register them by importing the water domain
(directly or transitively through an example package such as
``examples.governed_flood``). Tests that exercise framework-
registered names without importing an example package must add
``import broker.domains.water  # noqa`` at the top of the file —
the dependency is now declared explicitly.

To add a new domain:
    1. Create ``broker/domains/<name>/__init__.py`` with module-level
       ``register()`` calls at the bottom (water serves as the
       reference).
    2. Implement your frameworks, checks, and defaults in that sub-
       package.
    3. Have **consumers** import your sub-package explicitly; the
       framework no longer auto-discovers it.

See ``broker/domains/water/__init__.py`` for the reference
implementation. ``broker.domains.water.register()`` fires at
module-load time when the package is imported — it just isn't
called by ``broker.domains`` package init anymore.
"""
