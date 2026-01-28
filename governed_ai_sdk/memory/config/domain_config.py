from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class DomainMemoryConfig:
    """Domain-specific memory configuration."""
    stimulus_key: Optional[str] = None
    sensory_cortex: Optional[List[Dict[str, Any]]] = None


@dataclass
class FloodDomainConfig(DomainMemoryConfig):
    """Flood domain specialization (placeholder for future fields)."""
    pass
