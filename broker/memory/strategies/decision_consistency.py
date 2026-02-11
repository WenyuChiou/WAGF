"""
Decision-Consistency Surprise (DCS) Strategy.

Domain-agnostic surprise computation based on an agent's own action history.
Detects behavioral inconsistency: when an agent breaks its established pattern,
surprise is high — even without environmental novelty.

This fills a gap in the existing surprise strategies:
- EMA: tracks a single environmental variable (requires domain knowledge)
- Symbolic: tracks multi-variate state signatures (requires sensor config)
- DCS: tracks the agent's OWN decision sequence (zero domain config needed)

Algorithm:
    1. Maintain a frequency distribution of past actions.
    2. On each new action, surprise = 1 - P(action | history).
    3. Optionally track bigram transitions for sequence-aware surprise.

References:
- Itti & Baldi (2009): Bayesian Surprise
- Sun et al. (2016): KISS principle for ABM mechanism complexity
- Task-040 Memory Module Optimization (P2 Innovation)
"""

from typing import Dict, Any, Optional, List
from collections import Counter
import math


class DecisionConsistencySurprise:
    """
    Frequency-based surprise from an agent's own action history.

    Implements the SurpriseStrategy protocol for pluggable integration
    with HumanCentricMemoryEngine or UnifiedCognitiveEngine.

    Modes:
        - "unigram": Surprise based on individual action frequency.
          P(action) = count(action) / total_actions
          Surprise = 1 - P(action)
        - "bigram": Surprise based on transition frequency.
          P(action | prev_action) = count(prev→action) / count(prev)
          Surprise = 1 - P(action | prev_action)

    Args:
        mode: "unigram" or "bigram" (default: "unigram")
        smoothing: Laplace smoothing parameter for unseen actions (default: 1)

    Example:
        >>> dcs = DecisionConsistencySurprise(mode="unigram")
        >>> s1 = dcs.update({"action": "maintain_demand"})  # Novel → 1.0
        >>> s2 = dcs.update({"action": "maintain_demand"})  # Repeated → lower
        >>> s3 = dcs.update({"action": "increase_demand"})  # New action → high
    """

    def __init__(
        self,
        mode: str = "unigram",
        smoothing: int = 1,
        action_key: str = "action",
    ):
        if mode not in ("unigram", "bigram"):
            raise ValueError(f"mode must be 'unigram' or 'bigram', got '{mode}'")
        if smoothing < 0:
            raise ValueError(f"smoothing must be non-negative, got {smoothing}")

        self._mode = mode
        self._smoothing = smoothing
        self._action_key = action_key

        # Unigram counts
        self._action_counts: Counter = Counter()
        self._total_actions: int = 0

        # Bigram counts (prev_action → action)
        self._bigram_counts: Dict[str, Counter] = {}
        self._bigram_totals: Counter = Counter()
        self._prev_action: Optional[str] = None

        # Trace
        self._last_surprise: float = 0.0
        self._last_trace: Optional[Dict[str, Any]] = None

    def _extract_action(self, observation: Dict[str, Any]) -> str:
        """Extract action string from observation dict."""
        action = observation.get(self._action_key, "unknown")
        return str(action)

    def _unigram_surprise(self, action: str) -> float:
        """Compute surprise using unigram (marginal) frequency.

        With Laplace smoothing:
            P(action) = (count + α) / (total + α × |V|)
        where |V| is the vocabulary size (number of distinct actions seen + 1).
        """
        vocab_size = len(self._action_counts) + 1  # +1 for unseen actions
        count = self._action_counts.get(action, 0)
        prob = (count + self._smoothing) / (
            self._total_actions + self._smoothing * vocab_size
        )
        return 1.0 - prob

    def _bigram_surprise(self, action: str) -> float:
        """Compute surprise using bigram (transition) frequency.

        P(action | prev) = (count(prev→action) + α) / (count(prev) + α × |V|)
        Falls back to unigram if no previous action exists.
        """
        if self._prev_action is None:
            return self._unigram_surprise(action)

        prev = self._prev_action
        vocab_size = len(self._action_counts) + 1
        bigram_count = self._bigram_counts.get(prev, Counter()).get(action, 0)
        prev_total = self._bigram_totals.get(prev, 0)

        prob = (bigram_count + self._smoothing) / (
            prev_total + self._smoothing * vocab_size
        )
        return 1.0 - prob

    def update(self, observation: Dict[str, Any]) -> float:
        """Update action history and return surprise.

        Args:
            observation: Dict containing action key (default: "action").
                         Example: {"action": "increase_demand"}

        Returns:
            Surprise value [0-1]. High = inconsistent with history.
        """
        action = self._extract_action(observation)

        # Compute surprise BEFORE updating counts (novelty-first)
        if self._mode == "bigram":
            surprise = self._bigram_surprise(action)
        else:
            surprise = self._unigram_surprise(action)

        # Update counts
        self._action_counts[action] += 1
        self._total_actions += 1

        if self._prev_action is not None:
            if self._prev_action not in self._bigram_counts:
                self._bigram_counts[self._prev_action] = Counter()
            self._bigram_counts[self._prev_action][action] += 1
            self._bigram_totals[self._prev_action] += 1

        # Capture trace
        self._last_surprise = surprise
        self._last_trace = {
            "strategy": "DecisionConsistency",
            "mode": self._mode,
            "action": action,
            "prev_action": self._prev_action,
            "surprise": surprise,
            "action_distribution": dict(self._action_counts),
            "total_actions": self._total_actions,
        }

        self._prev_action = action
        return surprise

    def get_surprise(self, observation: Dict[str, Any]) -> float:
        """Calculate surprise WITHOUT updating internal state.

        Args:
            observation: Dict containing action key

        Returns:
            Surprise value [0-1]
        """
        action = self._extract_action(observation)
        if self._mode == "bigram":
            return self._bigram_surprise(action)
        return self._unigram_surprise(action)

    def get_arousal(self) -> float:
        """Get last computed surprise (arousal level)."""
        return self._last_surprise

    def get_trace(self) -> Optional[Dict[str, Any]]:
        """Get trace data for explainability."""
        return self._last_trace

    def get_action_distribution(self) -> Dict[str, float]:
        """Get normalized action frequency distribution.

        Returns:
            Dict mapping action → probability.
            Useful for monitoring agent behavioral drift.
        """
        if self._total_actions == 0:
            return {}
        return {
            action: count / self._total_actions
            for action, count in self._action_counts.items()
        }

    def get_entropy(self) -> float:
        """Compute Shannon entropy of the action distribution.

        Higher entropy = more diverse behavior (less predictable).
        Lower entropy = more consistent behavior (highly predictable).

        Returns:
            Entropy in bits. 0.0 = always same action.
        """
        if self._total_actions == 0:
            return 0.0

        entropy = 0.0
        for count in self._action_counts.values():
            if count > 0:
                p = count / self._total_actions
                entropy -= p * math.log2(p)
        return entropy

    def reset(self) -> None:
        """Reset all state for new simulation."""
        self._action_counts.clear()
        self._total_actions = 0
        self._bigram_counts.clear()
        self._bigram_totals.clear()
        self._prev_action = None
        self._last_surprise = 0.0
        self._last_trace = None
