"""
Temporal Consistency Score (TCS) — Construct-Level Drift Detection.

Detects *impossible* psychological construct transitions between
consecutive years for individual agents.  Unlike ``drift_detector.py``
which tracks action-level diversity at the population level, TCS
validates construct-level coherence at the individual level.

Impossible transitions (PMT example):
    - TP: VL → VH in one step without a flood event
    - CP: VH → VL without a financial shock
    - Relocated agent changing TP/CP (should be frozen)

The transition matrix approach allows domain-specific rules:
    PMT:  TP/CP labels (VL, L, M, H, VH)
    WSA:  WSA/ACA labels (same scale)

References:
    Grimm et al. (2005) — Multi-level pattern validation
    Thiele et al. (2014) — Temporal pattern extraction

Part of SAGE C&V Framework (feature/calibration-validation).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Label ordering for transition distance
# ---------------------------------------------------------------------------

LABEL_ORDER: Dict[str, int] = {"VL": 0, "L": 1, "M": 2, "H": 3, "VH": 4}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TransitionMatrix:
    """Observed transition counts between construct levels.

    Attributes:
        construct: Construct name (e.g., "TP_LABEL").
        labels: Ordered label set.
        counts: 2D array of transition counts [from][to].
        impossible_mask: 2D boolean array marking impossible transitions.
        impossible_count: Total impossible transitions observed.
        total_count: Total transitions observed.
    """
    construct: str
    labels: List[str]
    counts: np.ndarray
    impossible_mask: np.ndarray
    impossible_count: int
    total_count: int

    @property
    def tcs(self) -> float:
        """Temporal Consistency Score: 1 - (impossible / total)."""
        if self.total_count == 0:
            return 1.0
        return 1.0 - (self.impossible_count / self.total_count)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "construct": self.construct,
            "labels": self.labels,
            "counts": self.counts.tolist(),
            "impossible_mask": self.impossible_mask.tolist(),
            "impossible_count": self.impossible_count,
            "total_count": self.total_count,
            "tcs": self.tcs,
        }


@dataclass
class AgentTCSResult:
    """Per-agent temporal consistency result.

    Attributes:
        agent_id: Agent identifier.
        tcs: Agent-level TCS (1 = fully consistent).
        impossible_transitions: List of (year, construct, from, to) tuples.
        total_transitions: Total construct transitions for this agent.
    """
    agent_id: str
    tcs: float
    impossible_transitions: List[Tuple[int, str, str, str]] = field(
        default_factory=list
    )
    total_transitions: int = 0


@dataclass
class TemporalReport:
    """Aggregated TCS report.

    Attributes:
        overall_tcs: Population-level TCS.
        tcs_by_construct: Per-construct TCS values.
        tcs_by_agent: Per-agent TCS results.
        transition_matrices: Per-construct transition matrices.
        n_agents: Number of agents evaluated.
        n_total_transitions: Total transitions across all agents.
        n_impossible: Total impossible transitions.
    """
    overall_tcs: float
    tcs_by_construct: Dict[str, float] = field(default_factory=dict)
    tcs_by_agent: List[AgentTCSResult] = field(default_factory=list)
    transition_matrices: List[TransitionMatrix] = field(default_factory=list)
    n_agents: int = 0
    n_total_transitions: int = 0
    n_impossible: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_tcs": self.overall_tcs,
            "tcs_by_construct": self.tcs_by_construct,
            "n_agents": self.n_agents,
            "n_total_transitions": self.n_total_transitions,
            "n_impossible": self.n_impossible,
            "transition_matrices": [
                m.to_dict() for m in self.transition_matrices
            ],
        }


# ---------------------------------------------------------------------------
# Temporal Coherence Validator
# ---------------------------------------------------------------------------

class ActionStabilityValidator:
    """Construct-free temporal validation using action-level entropy.

    For ABMs without ordinal constructs, this measures year-over-year
    stability of action choices at the agent level.  Detects:

    - Erratic switching: agent changes action every year without reason
    - Lock-in: agent never changes despite changing conditions
    - Population stability: per-year action entropy trend

    Parameters
    ----------
    decision_col : str
        Column containing the chosen action.
    """

    def __init__(self, decision_col: str = "yearly_decision"):
        self._decision_col = decision_col

    def compute(
        self,
        df: pd.DataFrame,
        start_year: int = 1,
    ) -> Dict[str, Any]:
        """Compute action stability metrics.

        Parameters
        ----------
        df : DataFrame
            Must have agent_id, year, and decision column.
        start_year : int
            First year to include.

        Returns
        -------
        dict
            switch_rate: Fraction of agent-year transitions that changed.
            lock_in_rate: Fraction of agents that never changed.
            entropy_by_year: Per-year Shannon entropy of action distribution.
            agent_switch_rates: Per-agent switch rate.
        """
        df = df[df["year"] >= start_year].sort_values(
            ["agent_id", "year"]
        ).copy()

        if df.empty or self._decision_col not in df.columns:
            return {
                "switch_rate": 0.0,
                "lock_in_rate": 0.0,
                "entropy_by_year": {},
                "agent_switch_rates": {},
            }

        total_transitions = 0
        total_switches = 0
        agent_switches: Dict[str, float] = {}

        for agent_id, agent_df in df.groupby("agent_id"):
            decisions = agent_df[self._decision_col].tolist()
            if len(decisions) < 2:
                agent_switches[str(agent_id)] = 0.0
                continue

            n_trans = len(decisions) - 1
            n_switch = sum(
                1 for i in range(1, len(decisions))
                if decisions[i] != decisions[i - 1]
            )
            total_transitions += n_trans
            total_switches += n_switch
            agent_switches[str(agent_id)] = (
                n_switch / n_trans if n_trans > 0 else 0.0
            )

        switch_rate = (
            total_switches / total_transitions
            if total_transitions > 0 else 0.0
        )
        lock_in_rate = (
            sum(1 for r in agent_switches.values() if r == 0.0)
            / len(agent_switches) if agent_switches else 0.0
        )

        # Per-year entropy
        entropy_by_year: Dict[int, float] = {}
        for year, year_df in df.groupby("year"):
            counts = year_df[self._decision_col].value_counts(normalize=True)
            probs = counts.values
            entropy = float(-sum(
                p * np.log2(p) for p in probs if p > 0
            ))
            entropy_by_year[int(year)] = round(entropy, 4)

        return {
            "switch_rate": round(switch_rate, 4),
            "lock_in_rate": round(lock_in_rate, 4),
            "entropy_by_year": entropy_by_year,
            "agent_switch_rates": agent_switches,
        }


class TemporalCoherenceValidator:
    """Validate temporal consistency of psychological construct transitions.

    Parameters
    ----------
    max_jump : int
        Maximum allowed label-order jump per year (default: 2).
        E.g., with 5-level scale (VL..VH), jumping from VL to VH
        is distance 4 — exceeding max_jump=2 flags it as impossible.
    label_order : dict, optional
        Mapping of label → ordinal position.  Default: PMT 5-level scale.
    construct_cols : list[str]
        Construct columns to check (default: ["ta_level", "ca_level"]).
    event_col : str, optional
        Column indicating a triggering event that justifies large jumps
        (e.g., ``"flood_occurred"``).  If an event occurred in year t,
        any jump in year t is allowed.
    relocated_col : str, optional
        Column indicating relocation status.  Transitions after relocation
        are flagged as impossible (agent should be frozen).
    """

    def __init__(
        self,
        max_jump: int = 2,
        label_order: Optional[Dict[str, int]] = None,
        construct_cols: Optional[List[str]] = None,
        event_col: Optional[str] = None,
        relocated_col: str = "relocated",
    ):
        self._max_jump = max_jump
        self._label_order = label_order or LABEL_ORDER
        self._construct_cols = construct_cols or ["ta_level", "ca_level"]
        self._event_col = event_col
        self._relocated_col = relocated_col
        self._labels = sorted(self._label_order.keys(),
                              key=lambda x: self._label_order[x])

    def compute_tcs(
        self,
        df: pd.DataFrame,
        start_year: int = 1,
    ) -> TemporalReport:
        """Compute TCS for all agents in a simulation DataFrame.

        Parameters
        ----------
        df : DataFrame
            Must have: agent_id, year, and construct columns.
        start_year : int
            First year to include.

        Returns
        -------
        TemporalReport
        """
        df = df[df["year"] >= start_year].sort_values(["agent_id", "year"]).copy()

        # Track per-construct transition matrices
        n_labels = len(self._labels)
        label_to_idx = {l: i for i, l in enumerate(self._labels)}
        construct_counts = {
            c: np.zeros((n_labels, n_labels), dtype=int)
            for c in self._construct_cols if c in df.columns
        }
        construct_impossible = {
            c: np.zeros((n_labels, n_labels), dtype=bool)
            for c in self._construct_cols if c in df.columns
        }

        # Pre-compute impossible mask based on max_jump
        for c in construct_counts:
            for i in range(n_labels):
                for j in range(n_labels):
                    if abs(i - j) > self._max_jump:
                        construct_impossible[c][i, j] = True

        agent_results: List[AgentTCSResult] = []
        total_impossible = 0
        total_transitions = 0

        for agent_id, agent_df in df.groupby("agent_id"):
            if len(agent_df) < 2:
                agent_results.append(AgentTCSResult(
                    agent_id=str(agent_id), tcs=1.0, total_transitions=0
                ))
                continue

            agent_impossible: List[Tuple[int, str, str, str]] = []
            agent_transitions = 0

            for i in range(1, len(agent_df)):
                prev_row = agent_df.iloc[i - 1]
                curr_row = agent_df.iloc[i]
                curr_year = int(curr_row["year"])

                # Check if event justifies large jump
                event_occurred = False
                if self._event_col and self._event_col in curr_row.index:
                    event_occurred = bool(curr_row[self._event_col])

                # Check if agent is relocated (should be frozen)
                prev_relocated = False
                if self._relocated_col in prev_row.index:
                    prev_relocated = bool(prev_row[self._relocated_col])

                for construct in construct_counts:
                    if construct not in curr_row.index:
                        continue

                    prev_label = str(prev_row.get(construct, "M")).upper()
                    curr_label = str(curr_row.get(construct, "M")).upper()

                    if prev_label not in label_to_idx or curr_label not in label_to_idx:
                        continue

                    prev_idx = label_to_idx[prev_label]
                    curr_idx = label_to_idx[curr_label]

                    construct_counts[construct][prev_idx, curr_idx] += 1
                    agent_transitions += 1
                    total_transitions += 1

                    # Check for impossible transition
                    is_impossible = False

                    if prev_relocated and prev_label != curr_label:
                        # Relocated agent changed construct — impossible
                        is_impossible = True

                    elif not event_occurred and construct_impossible[construct][prev_idx, curr_idx]:
                        # Large jump without triggering event
                        is_impossible = True

                    if is_impossible:
                        agent_impossible.append(
                            (curr_year, construct, prev_label, curr_label)
                        )
                        total_impossible += 1

            agent_tcs = (
                1.0 - len(agent_impossible) / agent_transitions
                if agent_transitions > 0 else 1.0
            )
            agent_results.append(AgentTCSResult(
                agent_id=str(agent_id),
                tcs=agent_tcs,
                impossible_transitions=agent_impossible,
                total_transitions=agent_transitions,
            ))

        # Build transition matrices
        matrices: List[TransitionMatrix] = []
        tcs_by_construct: Dict[str, float] = {}
        for construct in construct_counts:
            counts = construct_counts[construct]
            imp_mask = construct_impossible[construct]
            imp_count = int(np.sum(counts[imp_mask]))
            tot_count = int(np.sum(counts))

            tcs_val = 1.0 - (imp_count / tot_count) if tot_count > 0 else 1.0
            tcs_by_construct[construct] = tcs_val

            matrices.append(TransitionMatrix(
                construct=construct,
                labels=self._labels,
                counts=counts,
                impossible_mask=imp_mask,
                impossible_count=imp_count,
                total_count=tot_count,
            ))

        overall_tcs = (
            1.0 - total_impossible / total_transitions
            if total_transitions > 0 else 1.0
        )

        return TemporalReport(
            overall_tcs=overall_tcs,
            tcs_by_construct=tcs_by_construct,
            tcs_by_agent=agent_results,
            transition_matrices=matrices,
            n_agents=len(agent_results),
            n_total_transitions=total_transitions,
            n_impossible=total_impossible,
        )
