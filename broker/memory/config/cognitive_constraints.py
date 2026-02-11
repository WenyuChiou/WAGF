"""
Cognitive Constraints Configuration based on psychological research.

This module provides configurable memory capacity constraints derived from
well-established cognitive science literature:

- Miller, G. A. (1956). The magical number seven, plus or minus two:
  Some limits on our capacity for processing information.
  Psychological Review, 63(2), 81-97. DOI: 10.1037/h0043158

- Cowan, N. (2001). The magical number 4 in short-term memory:
  A reconsideration of mental storage capacity.
  Behavioral and Brain Sciences, 24(1), 87-114. DOI: 10.1017/S0140525X01003922

Application to Dual-Process Theory (System 1/2):
- System 1 (Low arousal): Automatic processing, uses Cowan's 4±1 limit
- System 2 (High arousal): Deliberate processing, uses Miller's 7±2 limit

Reference: Task-050E Memory Optimization
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class CognitiveConstraints:
    """
    Configurable memory capacity constraints based on cognitive science.

    The defaults are derived from well-established psychological research:
    - Miller's Law (1956): Working memory holds 7±2 chunks
    - Cowan's revision (2001): Pure focus attention holds 4±1 items

    Attributes:
        system1_memory_count: Memories for System 1 (routine, automatic)
            Default: 5 (Cowan's 4±1, using upper bound)
        system2_memory_count: Memories for System 2 (crisis, deliberate)
            Default: 7 (Miller's 7±2, using median)
        working_capacity: Total working memory capacity
            Default: 10 (allows buffer for consolidation)
        top_k_significant: High-importance memories from long-term
            Default: 2 (supplements recent memories)

    Example:
        >>> constraints = CognitiveConstraints()
        >>> constraints.system1_memory_count
        5
        >>> constraints.system2_memory_count
        7

        >>> # Custom configuration
        >>> constraints = CognitiveConstraints(
        ...     system1_memory_count=4,  # More conservative
        ...     system2_memory_count=9,  # Miller's upper bound
        ... )

        >>> # Get dynamic memory count based on arousal
        >>> constraints.get_memory_count(arousal=0.0)  # System 1
        5
        >>> constraints.get_memory_count(arousal=1.0)  # System 2
        7
    """

    # System 1: Routine processing (Cowan 2001: 4±1)
    system1_memory_count: int = 5

    # System 2: Deliberate processing (Miller 1956: 7±2)
    system2_memory_count: int = 7

    # Working memory capacity
    working_capacity: int = 10

    # Long-term significant memories to supplement recent memories
    top_k_significant: int = 2

    # Literature references (for documentation and traceability)
    references: List[str] = field(default_factory=lambda: [
        "Miller, G. A. (1956). Psychological Review, 63(2), 81-97. DOI:10.1037/h0043158",
        "Cowan, N. (2001). Behavioral and Brain Sciences, 24(1), 87-114. DOI:10.1017/S0140525X01003922",
    ])

    # DOI constants for programmatic access
    MILLER_1956_DOI: str = field(default="10.1037/h0043158", repr=False)
    COWAN_2001_DOI: str = field(default="10.1017/S0140525X01003922", repr=False)

    def get_memory_count(self, arousal: float, threshold: float = 0.5) -> int:
        """
        Get memory count based on current arousal level.

        Interpolates between System 1 and System 2 counts based on
        distance from the arousal threshold.

        Args:
            arousal: Current arousal level [0-1]
            threshold: Arousal threshold for System 2 activation

        Returns:
            Number of memories to retrieve

        Example:
            >>> c = CognitiveConstraints()
            >>> c.get_memory_count(arousal=0.0)  # Pure System 1
            5
            >>> c.get_memory_count(arousal=1.0)  # Pure System 2
            7
            >>> c.get_memory_count(arousal=0.5)  # Transition
            7
        """
        if arousal <= threshold * 0.5:
            # Pure System 1 mode
            return self.system1_memory_count
        elif arousal >= threshold:
            # Pure System 2 mode
            return self.system2_memory_count
        else:
            # Linear interpolation in transition zone
            t = (arousal - threshold * 0.5) / (threshold * 0.5)
            interpolated = self.system1_memory_count * (1 - t) + self.system2_memory_count * t
            return int(round(interpolated))

    def get_total_context_size(self, arousal: float, threshold: float = 0.5) -> int:
        """
        Get total context size (recent + significant memories).

        System 1: 5 recent + 2 significant = 7 (Miller's median)
        System 2: 7 recent + 2 significant = 9 (Miller's upper bound)

        Args:
            arousal: Current arousal level [0-1]
            threshold: Arousal threshold for System 2 activation

        Returns:
            Total number of memories in context

        Example:
            >>> c = CognitiveConstraints()
            >>> c.get_total_context_size(arousal=0.0)  # 5 + 2
            7
            >>> c.get_total_context_size(arousal=1.0)  # 7 + 2
            9
        """
        return self.get_memory_count(arousal, threshold) + self.top_k_significant

    def validate(self) -> bool:
        """
        Validate constraints are within reasonable bounds.

        Returns:
            True if valid, raises ValueError otherwise
        """
        if self.system1_memory_count < 1:
            raise ValueError("system1_memory_count must be >= 1")
        if self.system2_memory_count < self.system1_memory_count:
            raise ValueError("system2_memory_count must be >= system1_memory_count")
        if self.working_capacity < self.system2_memory_count:
            raise ValueError("working_capacity must be >= system2_memory_count")
        if self.top_k_significant < 0:
            raise ValueError("top_k_significant must be >= 0")
        return True


# =============================================================================
# Pre-configured Profiles
# =============================================================================

# Miller's Law standard profile (recommended default)
MILLER_STANDARD = CognitiveConstraints(
    system1_memory_count=5,
    system2_memory_count=7,
    working_capacity=10,
    top_k_significant=2,
)

# Cowan's conservative profile (for resource-constrained scenarios)
COWAN_CONSERVATIVE = CognitiveConstraints(
    system1_memory_count=3,
    system2_memory_count=5,
    working_capacity=7,
    top_k_significant=2,
)

# Extended context profile (for complex reasoning tasks)
EXTENDED_CONTEXT = CognitiveConstraints(
    system1_memory_count=7,
    system2_memory_count=9,
    working_capacity=15,
    top_k_significant=3,
)

# Minimal profile (for fast inference / small models)
MINIMAL = CognitiveConstraints(
    system1_memory_count=3,
    system2_memory_count=4,
    working_capacity=5,
    top_k_significant=1,
)


__all__ = [
    "CognitiveConstraints",
    "MILLER_STANDARD",
    "COWAN_CONSERVATIVE",
    "EXTENDED_CONTEXT",
    "MINIMAL",
]
