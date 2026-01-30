from dataclasses import dataclass, field
from typing import Dict


@dataclass
class GlobalMemoryConfig:
    """
    Global (system-wide) memory configuration.

    These defaults apply across all domains unless overridden by
    domain-specific configs or explicit engine arguments.
    """
    arousal_threshold: float = 0.5
    ema_alpha: float = 0.3
    window_size: int = 5
    top_k_significant: int = 2
    consolidation_prob: float = 0.7
    consolidation_threshold: float = 0.6
    decay_rate: float = 0.1
    retrieval_weights: Dict[str, float] = field(default_factory=lambda: {
        "recency": 0.3,
        "importance": 0.5,
        "context": 0.2,
    })
