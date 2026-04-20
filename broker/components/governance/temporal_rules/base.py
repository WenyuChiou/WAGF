"""Temporal Rule Framework — Generic protocols + dataclasses.

Extends WAGF validator architecture from point-in-time rules (R1-R4)
to sequence-level rules operating on an agent's trajectory. Framework
is domain-agnostic; domain-specific behaviour is injected via a
DomainTemporalAdapter implementation (see broker/INVARIANTS.md §5).

Theory notes embedded per rule class in `rules.py`. Framework itself
is neutral; it provides the scaffolding for rule evaluation, not a
claim about which rules are "correct."
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Set, runtime_checkable


@dataclass
class AgentTurn:
    """One agent-year observation. Built from an audit row.

    Framework does not prescribe which fields are present — the adapter
    is responsible for mapping domain concepts to the optional hooks
    below. `raw` holds the complete audit row for adapter-specific use.
    """

    agent_id: str
    year: int
    threat_label: Optional[str] = None   # VL/L/M/H/VH if available
    coping_label: Optional[str] = None
    final_skill: Optional[str] = None
    top_emotion: Optional[str] = None
    retrieved_memories: List[Dict[str, Any]] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Violation:
    """A rule-trigger event on a single agent-year."""

    agent_id: str
    year: int
    rule_id: str                         # e.g. "M1"
    severity: str = "warn"               # "warn" | "block" (post-hoc uses warn)
    rationale: str = ""
    window_years: List[int] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class DomainTemporalAdapter(Protocol):
    """Domain plugs in three semantic callbacks; framework stays generic.

    Implementations live under `examples/<domain>/adapters/` per
    Invariant 5. A NullTemporalAdapter is provided for tests and as a
    safety default — it causes all rules to pass (no triggers).
    """

    def is_salient_event(self, memory: Dict[str, Any]) -> bool:
        """Return True if `memory` represents a domain-salient event
        (e.g., flood occurrence, drought tier escalation).
        Typically checks `memory['emotion']` against a salience set.
        """
        ...

    def is_irreversible(self, skill_id: str) -> bool:
        """Return True if `skill_id` is an irreversible / high-commitment
        action (domain-specific; see each adapter for the list)."""
        ...

    def low_appraisal_set(self) -> Set[str]:
        """Return the set of appraisal labels considered 'low threat'
        for the M1 coherence check (e.g., {'VL', 'L'})."""
        ...

    def high_volatility(self, window: List[AgentTurn]) -> bool:
        """Return True if state varied enough over window to warrant
        behaviour reconsideration (used by M2). Default impl can look
        at appraisal label variance across the window."""
        ...


class NullTemporalAdapter:
    """Safety default: causes every rule to pass without flag.
    Use in tests to confirm framework is domain-neutral."""

    def is_salient_event(self, memory: Dict[str, Any]) -> bool:
        return False

    def is_irreversible(self, skill_id: str) -> bool:
        return False

    def low_appraisal_set(self) -> Set[str]:
        return set()

    def high_volatility(self, window: List[AgentTurn]) -> bool:
        return False


@runtime_checkable
class TemporalRule(Protocol):
    """Protocol for a single temporal rule.

    Rule checks a trajectory window ending at `current_year` and
    returns a Violation if the rule's coherence condition is breached,
    else None. Framework guarantees to pass adapter-normalised AgentTurn
    objects; rule implementation trusts adapter contract.
    """

    rule_id: str
    window_size: int
    severity: str  # "warn" | "block"

    def check(
        self,
        current: AgentTurn,
        history: List[AgentTurn],
        adapter: DomainTemporalAdapter,
    ) -> Optional[Violation]:
        ...
