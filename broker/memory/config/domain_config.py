from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class DomainMemoryConfig:
    """Domain-specific memory configuration."""
    stimulus_key: Optional[str] = None
    sensory_cortex: Optional[List[Dict[str, Any]]] = None


def __getattr__(name):
    if name == "FloodDomainConfig":
        import warnings

        from broker.domains.water.memory_config import FloodDomainConfig

        warnings.warn(
            "FloodDomainConfig moved to broker.domains.water.memory_config; import from there",
            DeprecationWarning,
            stacklevel=2,
        )
        return FloodDomainConfig
    raise AttributeError(name)
