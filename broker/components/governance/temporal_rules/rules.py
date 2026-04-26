"""Three domain-agnostic temporal rules: M1, M2, M3.

Each rule implements the TemporalRule protocol. Domain knowledge is
delegated entirely to DomainTemporalAdapter — no domain-specific
tokens appear in this file (Invariant 5).

## Theory grounding per rule

Rules are NOT assertions of universal truth about rational behaviour.
They are domain-tunable heuristics grounded in behavioural-science
literature; each should be interpreted as "flagged for attention"
rather than "classified as irrational." See each rule's docstring
for the theoretical anchor.
"""
from __future__ import annotations

from typing import List, Optional

from .base import AgentTurn, DomainTemporalAdapter, TemporalRule, Violation


class AppraisalHistoryCoherence:
    """M1 — Appraisal should reflect recent salient history.

    Theoretical anchor: Kahneman availability heuristic (Tversky &
    Kahneman 1973); memory consolidation literature (Ebbinghaus;
    Park et al. 2023). Empirical window calibration: Bubeck & Botzen
    (2018) post-flood risk perception decay ~3–5 yr.

    Trigger: agent has at least one salient event in memory within
    window AND current appraisal is in low-threat set.
    """

    rule_id = "M1"
    window_size = 3
    severity = "warn"

    def check(
        self,
        current: AgentTurn,
        history: List[AgentTurn],
        adapter: DomainTemporalAdapter,
    ) -> Optional[Violation]:
        if current.threat_label is None:
            return None
        if current.threat_label not in adapter.low_appraisal_set():
            return None

        # Scan memory for any salient event in the recent window
        window_history = [
            t for t in history
            if current.year - self.window_size <= t.year < current.year
        ]
        salient_years: List[int] = []
        for turn in window_history:
            for mem in turn.retrieved_memories:
                if adapter.is_salient_event(mem):
                    salient_years.append(turn.year)
                    break

        if not salient_years:
            return None

        return Violation(
            agent_id=current.agent_id,
            year=current.year,
            rule_id=self.rule_id,
            severity=self.severity,
            rationale=(
                f"threat_label={current.threat_label!r} is in low set "
                f"despite salient event(s) retrieved in year(s) {salient_years}"
            ),
            window_years=salient_years,
            metadata={"low_set": sorted(adapter.low_appraisal_set())},
        )


class BehavioralInertia:
    """M2 — Same action for N years under environmental volatility.

    Theoretical anchor: cognitive inertia literature (Polites &
    Karahanna 2012); adaptive management review cycles (Pahl-Wostl
    2007). Window N=5 chosen to match quinquennial review heuristics.

    Trigger: same final_skill for window_size consecutive years AND
    the environment (appraisal labels) varied by at least two ordinal
    levels across the window.

    Rule is conservative: stable action under stable environment is
    NOT flagged (that is rational inertia, not irrational).
    """

    rule_id = "M2"
    window_size = 5
    severity = "warn"

    def check(
        self,
        current: AgentTurn,
        history: List[AgentTurn],
        adapter: DomainTemporalAdapter,
    ) -> Optional[Violation]:
        # Need full window of prior turns
        window = [
            t for t in history
            if current.year - self.window_size <= t.year < current.year
        ]
        if len(window) < self.window_size - 1:
            return None

        window_full = window + [current]
        skills = [t.final_skill for t in window_full if t.final_skill]
        if len(skills) < self.window_size:
            return None

        if len(set(skills)) != 1:
            return None  # not same action → inertia rule inactive

        if not adapter.high_volatility(window_full):
            return None  # stable env → rational inertia, not irrational

        return Violation(
            agent_id=current.agent_id,
            year=current.year,
            rule_id=self.rule_id,
            severity=self.severity,
            rationale=(
                f"final_skill={skills[0]!r} held constant for "
                f"{self.window_size} years under environmental volatility"
            ),
            window_years=[t.year for t in window_full],
            metadata={"action": skills[0]},
        )


class EvidenceGroundedIrreversibility:
    """M3 — Irreversible action at year 1 without prior evidence.

    Theoretical anchor: precautionary principle; real options theory
    (Dixit & Pindyck 1994); insurance-adoption literature showing
    evidence-based rather than prior-dominated decision patterns.

    Trigger: at year 1, agent executes an irreversible action AND no
    salient event is present in initial seed memories.

    Caveat: agents with strong priors (elderly, prior-flood history
    encoded via seed memories) may still take Y1 irreversible action.
    Adapter's `is_salient_event` must correctly classify seed
    memories carrying such priors as salient. See SI for
    false-positive discussion.
    """

    rule_id = "M3"
    window_size = 1  # year 1 only
    severity = "warn"

    def check(
        self,
        current: AgentTurn,
        history: List[AgentTurn],
        adapter: DomainTemporalAdapter,
    ) -> Optional[Violation]:
        if current.year != 1:
            return None
        if not current.final_skill or not adapter.is_irreversible(current.final_skill):
            return None

        # Look at initial seed memories (retrieved at year 1)
        for mem in current.retrieved_memories:
            if adapter.is_salient_event(mem):
                return None  # prior flood evidence present → rational

        return Violation(
            agent_id=current.agent_id,
            year=current.year,
            rule_id=self.rule_id,
            severity=self.severity,
            rationale=(
                f"irreversible action {current.final_skill!r} taken at year 1 "
                f"without any salient event in seed memory"
            ),
            window_years=[1],
            metadata={"action": current.final_skill},
        )


# Convenience registry for default flood/irrigation rule set
DEFAULT_RULES: List[TemporalRule] = [
    AppraisalHistoryCoherence(),
    BehavioralInertia(),
    EvidenceGroundedIrreversibility(),
]
