"""
Domain packs — pluggable domain-specific content for the governance framework.

Each sub-package (e.g., ``broker.domains.water``) auto-registers its
psychological frameworks, thinking-validator checks, and default agent
types when imported.  The discovery mechanism scans this directory for
sub-packages that contain an ``__init__.py`` with a ``register()``
function and invokes it automatically.

To add a new domain:
    1. Create ``broker/domains/<name>/__init__.py`` with a ``register()`` function.
    2. Implement your frameworks, checks, and defaults in that sub-package.
    3. The framework will discover and register them at import time.

See ``broker/domains/water/`` for a reference implementation.
"""

import importlib
import logging
import pkgutil

logger = logging.getLogger(__name__)


def _discover_domain_packs() -> None:
    """Import all sub-packages so they can self-register."""
    for importer, modname, ispkg in pkgutil.iter_modules(__path__):
        if ispkg and not modname.startswith("_"):
            try:
                mod = importlib.import_module(f"{__name__}.{modname}")
                if hasattr(mod, "register"):
                    mod.register()
                    logger.debug("Domain pack '%s' registered", modname)
                else:
                    logger.debug("Domain pack '%s' loaded (no register())", modname)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to load domain pack '%s': %s", modname, exc)


_discover_domain_packs()
