from .defaults import GlobalMemoryConfig
from .domain_config import DomainMemoryConfig
from .cognitive_constraints import (
    CognitiveConstraints,
    MILLER_STANDARD,
    COWAN_CONSERVATIVE,
    EXTENDED_CONTEXT,
    MINIMAL,
)

__all__ = [
    "GlobalMemoryConfig",
    "DomainMemoryConfig",
    "FloodDomainConfig",
    # Cognitive Constraints (Task-050E)
    "CognitiveConstraints",
    "MILLER_STANDARD",
    "COWAN_CONSERVATIVE",
    "EXTENDED_CONTEXT",
    "MINIMAL",
]


def __getattr__(name):
    if name == "FloodDomainConfig":
        from .domain_config import FloodDomainConfig

        return FloodDomainConfig
    raise AttributeError(name)
