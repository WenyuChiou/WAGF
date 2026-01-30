"""
Generic drift detection for multi-agent population behavior monitoring.

Provides:
- DriftDetector: Tracks population-level decision entropy and individual stagnation
- DriftReport: Population-level drift snapshot
- AgentDriftReport: Per-agent drift metrics
- DriftAlert: Triggered when thresholds are exceeded

This module is domain-agnostic. It works with any string-valued decisions
and configurable thresholds.

Reference: Task-058C (Drift Detection & Social Norms)
Literature: AgentSociety (Piao et al., 2025) — population behavior monitoring
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class AgentDriftReport:
    """Per-agent drift metrics.

    Attributes:
        agent_id: Agent identifier
        jaccard_similarity: Similarity between recent and prior decision sets (0-1)
        decision_history: Last N decisions for this agent
        is_stagnant: Whether the agent is flagged as stagnant
    """
    agent_id: str
    jaccard_similarity: float
    decision_history: List[str]
    is_stagnant: bool


@dataclass
class DriftReport:
    """Population-level drift snapshot.

    Attributes:
        step: Simulation step/year
        decision_entropy: Shannon entropy of decision distribution (bits)
        dominant_action: Most common action
        dominant_action_pct: Fraction choosing the dominant action
        stagnation_rate: Fraction of agents flagged as stagnant
        agent_reports: Per-agent drift reports (if requested)
    """
    step: int
    decision_entropy: float
    dominant_action: str
    dominant_action_pct: float
    stagnation_rate: float
    agent_reports: List[AgentDriftReport] = field(default_factory=list)


@dataclass
class DriftAlert:
    """Alert triggered when drift thresholds are exceeded.

    Attributes:
        alert_type: "LOW_ENTROPY" | "HIGH_STAGNATION" | "MODE_COLLAPSE"
        message: Human-readable description
        step: When the alert was triggered
        value: The metric value that triggered the alert
        threshold: The threshold that was exceeded
    """
    alert_type: str
    message: str
    step: int
    value: float
    threshold: float


class DriftDetector:
    """Tracks population-level decision entropy and individual stagnation.

    Args:
        entropy_threshold: Shannon entropy (bits) below which LOW_ENTROPY alert fires
        stagnation_threshold: Fraction of stagnant agents above which HIGH_STAGNATION fires
        collapse_threshold: Dominant action fraction above which MODE_COLLAPSE fires
        history_window: Number of recent decisions to keep per agent
        jaccard_stagnation_threshold: Jaccard similarity above which an agent is stagnant
    """

    def __init__(
        self,
        entropy_threshold: float = 0.5,
        stagnation_threshold: float = 0.6,
        collapse_threshold: float = 0.9,
        history_window: int = 5,
        jaccard_stagnation_threshold: float = 0.8,
    ):
        self.entropy_threshold = entropy_threshold
        self.stagnation_threshold = stagnation_threshold
        self.collapse_threshold = collapse_threshold
        self.history_window = history_window
        self.jaccard_stagnation_threshold = jaccard_stagnation_threshold

        # State: agent_id -> list of recent decisions
        self._agent_history: Dict[str, List[str]] = {}
        # Previous window set per agent (for Jaccard)
        self._agent_prev_set: Dict[str, Set[str]] = {}
        self._reports: List[DriftReport] = []

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_decision(self, agent_id: str, decision: str) -> None:
        """Record a single agent's decision for the current step."""
        history = self._agent_history.setdefault(agent_id, [])
        history.append(decision)
        # Trim to window size
        if len(history) > self.history_window * 2:
            self._agent_history[agent_id] = history[-self.history_window * 2:]

    def record_decisions(self, decisions: Dict[str, str]) -> None:
        """Record decisions for multiple agents at once.

        Args:
            decisions: Mapping of agent_id -> decision string
        """
        for agent_id, decision in decisions.items():
            self.record_decision(agent_id, decision)

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def compute_snapshot(self, step: int, include_agents: bool = False) -> DriftReport:
        """Compute population-level drift metrics for the current step.

        Args:
            step: Current simulation step
            include_agents: Whether to include per-agent reports
        """
        # Collect latest decision per agent
        latest: Dict[str, str] = {}
        for agent_id, history in self._agent_history.items():
            if history:
                latest[agent_id] = history[-1]

        # Decision distribution
        counts: Dict[str, int] = {}
        for decision in latest.values():
            counts[decision] = counts.get(decision, 0) + 1

        total = len(latest)
        if total == 0:
            report = DriftReport(
                step=step, decision_entropy=0.0,
                dominant_action="", dominant_action_pct=0.0,
                stagnation_rate=0.0,
            )
            self._reports.append(report)
            return report

        # Shannon entropy
        entropy = 0.0
        for count in counts.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)

        # Dominant action
        dominant_action = max(counts, key=counts.get)  # type: ignore[arg-type]
        dominant_pct = counts[dominant_action] / total

        # Per-agent stagnation (Jaccard similarity)
        agent_reports: List[AgentDriftReport] = []
        stagnant_count = 0
        for agent_id, history in self._agent_history.items():
            if len(history) < 2:
                continue

            # Split into recent half and prior half
            mid = len(history) // 2
            recent_set = set(history[mid:])
            prior_set = self._agent_prev_set.get(agent_id, set(history[:mid]))

            # Jaccard similarity
            if recent_set or prior_set:
                intersection = len(recent_set & prior_set)
                union = len(recent_set | prior_set)
                jaccard = intersection / union if union > 0 else 0.0
            else:
                jaccard = 1.0

            is_stagnant = jaccard >= self.jaccard_stagnation_threshold
            if is_stagnant:
                stagnant_count += 1

            # Update prior set for next comparison
            self._agent_prev_set[agent_id] = recent_set

            if include_agents:
                agent_reports.append(AgentDriftReport(
                    agent_id=agent_id,
                    jaccard_similarity=jaccard,
                    decision_history=list(history[-self.history_window:]),
                    is_stagnant=is_stagnant,
                ))

        stagnation_rate = stagnant_count / total if total > 0 else 0.0

        report = DriftReport(
            step=step,
            decision_entropy=entropy,
            dominant_action=dominant_action,
            dominant_action_pct=dominant_pct,
            stagnation_rate=stagnation_rate,
            agent_reports=agent_reports,
        )
        self._reports.append(report)
        return report

    def check_alerts(self, report: DriftReport) -> List[DriftAlert]:
        """Check a DriftReport against thresholds and return any alerts."""
        alerts: List[DriftAlert] = []

        if report.decision_entropy < self.entropy_threshold and report.dominant_action:
            alerts.append(DriftAlert(
                alert_type="LOW_ENTROPY",
                message=f"Decision entropy {report.decision_entropy:.2f} bits "
                        f"< threshold {self.entropy_threshold:.2f}",
                step=report.step,
                value=report.decision_entropy,
                threshold=self.entropy_threshold,
            ))

        if report.stagnation_rate > self.stagnation_threshold:
            alerts.append(DriftAlert(
                alert_type="HIGH_STAGNATION",
                message=f"Stagnation rate {report.stagnation_rate:.0%} "
                        f"> threshold {self.stagnation_threshold:.0%}",
                step=report.step,
                value=report.stagnation_rate,
                threshold=self.stagnation_threshold,
            ))

        if report.dominant_action_pct > self.collapse_threshold:
            alerts.append(DriftAlert(
                alert_type="MODE_COLLAPSE",
                message=f"Mode collapse: {report.dominant_action_pct:.0%} chose "
                        f"'{report.dominant_action}' "
                        f"(threshold {self.collapse_threshold:.0%})",
                step=report.step,
                value=report.dominant_action_pct,
                threshold=self.collapse_threshold,
            ))

        return alerts

    @property
    def reports(self) -> List[DriftReport]:
        """Return all computed drift reports."""
        return list(self._reports)

    def reset(self) -> None:
        """Clear all recorded history and reports."""
        self._agent_history.clear()
        self._agent_prev_set.clear()
        self._reports.clear()
