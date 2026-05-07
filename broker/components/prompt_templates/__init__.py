"""Prompt-template helpers — generic broker contracts.

Phase 6B-2 (2026-05-04): the flood-domain `MemoryTemplateProvider` was
relocated to `broker.domains.water.flood_memory_templates`. This package
now exports only the generic `MemoryTemplate` dataclass.

For backward compatibility, the legacy `MemoryTemplateProvider` name is
re-exported via PEP 562 lazy `__getattr__` and resolves to
`FloodMemoryTemplateProvider`. New code should import the explicit
domain provider directly.
"""
from .memory_templates import MemoryTemplate

__all__ = [
    "MemoryTemplate",
    "MemoryTemplateProvider",  # legacy alias, lazy-resolved below
]


def __getattr__(name: str):
    if name == "MemoryTemplateProvider":
        from broker.domains.water.flood_memory_templates import FloodMemoryTemplateProvider
        return FloodMemoryTemplateProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
