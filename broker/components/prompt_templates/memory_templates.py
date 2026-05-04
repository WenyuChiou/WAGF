"""
Memory template generic contracts.

Phase 6B-2 (2026-05-04): the prior contents of this file (a flood-domain
MemoryTemplateProvider with FEMA / flood_zone / SFHA / NFIP logic) have
been relocated to `broker/domains/water/flood_memory_templates.py` and
renamed to `FloodMemoryTemplateProvider`. What remains here is the
generic `MemoryTemplate` dataclass — the data contract the broker layer
cares about, with no flood-domain assumptions baked in.

The broker does NOT enforce a specific provider class shape via ABC; it
duck-types the `generate_all(profile_dict) -> List[MemoryTemplate]`
classmethod / method contract. Domain providers are free to use either
classmethods (legacy flood pattern) or instance methods.

For backward compatibility, the legacy `MemoryTemplateProvider` name is
re-exported via PEP 562 lazy `__getattr__` and resolves to
`FloodMemoryTemplateProvider`.
"""
from dataclasses import dataclass


@dataclass
class MemoryTemplate:
    """Generated memory with metadata."""
    content: str
    category: str
    emotion: str = "neutral"
    source: str = "personal"


__all__ = ["MemoryTemplate", "MemoryTemplateProvider"]


# --- Backward-compat for legacy callers ---
def __getattr__(name: str):
    if name == "MemoryTemplateProvider":
        from broker.domains.water.flood_memory_templates import FloodMemoryTemplateProvider
        return FloodMemoryTemplateProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
