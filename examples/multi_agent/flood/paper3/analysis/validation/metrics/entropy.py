"""Shannon entropy computation for action distributions."""

import math
from collections import Counter


def _compute_entropy(counts: Counter) -> float:
    """Compute Shannon entropy of action distribution."""
    total = sum(counts.values())
    if total == 0:
        return 0.0

    entropy = 0.0
    for count in counts.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)

    return entropy
