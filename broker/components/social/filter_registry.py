"""FilterRegistry — plugin-style registration for neighbor-filter callables.

The previous implementation in `broker/components/social/config.py:332-338`
hardcoded `if filter_fn == "has_insurance":` as the only filter. This
registry replaces that hard dispatch with a plugin lookup so domain
packages (or future filter additions) can register their own predicates
without editing broker code.

Pattern matches `ValidatorRegistry` (Phase 6B-1) and `SkillRegistry`
in `broker/components/governance/registry.py`.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


# Type alias for a filter callable: takes an agent (object or dict), returns bool.
FilterFn = Callable[[Any], bool]


class FilterRegistry:
    """Plugin registry mapping filter-name -> predicate callable.

    Domain packages register filters at their `__init__.py` import time
    or at module load. The default flood-domain `has_insurance` filter
    is registered by `broker.components.social` itself for backward
    compatibility.

    Lookup is forgiving: unknown filter names return None, and the
    caller falls back to "include all neighbors" semantics — same
    behavior as the legacy if/else in social/config.py.
    """
    _filters: Dict[str, FilterFn] = {}
    _missing_warned: set = set()

    @classmethod
    def register(cls, name: str, fn: FilterFn) -> None:
        """Register a filter callable under a string name.

        Idempotent: re-registering the same name overwrites the previous
        callable. Useful for tests and reload-style development.
        """
        if not name or not isinstance(name, str):
            raise ValueError(f"FilterRegistry.register: name must be a non-empty string, got {name!r}")
        if not callable(fn):
            raise ValueError(f"FilterRegistry.register: fn must be callable, got {fn!r}")
        cls._filters[name] = fn

    @classmethod
    def get(cls, name: Optional[str]) -> Optional[FilterFn]:
        """Return the callable registered under `name`, or None if not
        found / name is None.

        For unknown non-empty names, emits a one-time warning so
        misspelled filter names surface instead of silently
        no-op-falling-through.
        """
        if not name:
            return None
        fn = cls._filters.get(name)
        if fn is None and name not in cls._missing_warned:
            logger.warning(
                "FilterRegistry: no filter registered under name=%r. "
                "Falling back to 'include all neighbors'. "
                "Registered names: %s",
                name, sorted(cls._filters.keys()),
            )
            cls._missing_warned.add(name)
        return fn

    @classmethod
    def names(cls) -> list:
        """List all currently-registered filter names."""
        return sorted(cls._filters.keys())

    @classmethod
    def clear(cls) -> None:
        """Reset registry. Tests use this between fixtures."""
        cls._filters.clear()
        cls._missing_warned.clear()
