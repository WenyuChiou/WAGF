"""
EntropyCalibrator - Quantify governance friction with entropy metrics.
"""

from __future__ import annotations

from collections import Counter
from math import log2
from typing import Iterable, Dict, List

from cognitive_governance.v1_prototype.types import EntropyFriction


class EntropyCalibrator:
    """
    Compute entropy-based governance friction metrics.
    """

    def calculate_friction(
        self,
        raw_actions: List[str],
        governed_actions: List[str],
    ) -> EntropyFriction:
        """
        Calculate entropy friction between raw and governed actions.

        Args:
            raw_actions: Intended actions (pre-governance).
            governed_actions: Allowed actions (post-governance).
        """
        s_raw = self._shannon_entropy(raw_actions)
        s_gov = self._shannon_entropy(governed_actions)
        friction_ratio = s_raw / max(s_gov, 1e-6)
        kl_div = self._kl_divergence(raw_actions, governed_actions)

        return EntropyFriction(
            S_raw=s_raw,
            S_governed=s_gov,
            friction_ratio=friction_ratio,
            kl_divergence=kl_div,
            raw_action_count=len(raw_actions),
            governed_action_count=len(governed_actions),
            blocked_action_count=max(len(raw_actions) - len(governed_actions), 0),
        )

    def _shannon_entropy(self, actions: Iterable[str]) -> float:
        counts = Counter(actions)
        total = sum(counts.values())
        if total == 0:
            return 0.0
        entropy = 0.0
        for count in counts.values():
            p = count / total
            entropy -= p * log2(p)
        return entropy

    def _distribution(self, actions: Iterable[str]) -> Dict[str, float]:
        counts = Counter(actions)
        total = sum(counts.values())
        if total == 0:
            return {}
        return {k: v / total for k, v in counts.items()}

    def _kl_divergence(self, raw_actions: Iterable[str], governed_actions: Iterable[str]) -> float:
        raw_dist = self._distribution(raw_actions)
        gov_dist = self._distribution(governed_actions)
        if not raw_dist:
            return 0.0

        eps = 1e-12
        kl = 0.0
        for action, p_raw in raw_dist.items():
            p_gov = gov_dist.get(action, 0.0)
            p_gov = max(p_gov, eps)
            kl += p_raw * log2(p_raw / p_gov)
        return kl


def create_calibrator() -> EntropyCalibrator:
    """Factory helper for EntropyCalibrator."""
    return EntropyCalibrator()
