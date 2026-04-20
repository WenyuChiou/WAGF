"""Temporal Rule Framework — sequence-level governance extension.

Provides a domain-agnostic scaffold for rules that evaluate agent
trajectories over time, complementing the point-in-time validator
layer (R1-R4). Domain-specific behaviour is injected via
DomainTemporalAdapter (see base.py).

See broker/INVARIANTS.md §5 for domain-genericity contract.
See .ai/wagf_module_audit_2026-04-19.md for V2 roadmap context.

Public API:
    AgentTurn                                — per-year observation
    Violation                                — rule-trigger event
    TemporalRule (Protocol)                  — rule interface
    DomainTemporalAdapter (Protocol)         — domain-plugin interface
    NullTemporalAdapter                      — safety default (no triggers)
    AppraisalHistoryCoherence (M1)
    BehavioralInertia (M2)
    EvidenceGroundedIrreversibility (M3)
    DEFAULT_RULES                            — [M1, M2, M3]
    TemporalRuleEvaluator                    — post-hoc orchestrator
    TrajectoryEvaluation                     — aggregate result
"""
from .base import (
    AgentTurn,
    DomainTemporalAdapter,
    NullTemporalAdapter,
    TemporalRule,
    Violation,
)
from .evaluator import TemporalRuleEvaluator, TrajectoryEvaluation
from .rules import (
    DEFAULT_RULES,
    AppraisalHistoryCoherence,
    BehavioralInertia,
    EvidenceGroundedIrreversibility,
)

__all__ = [
    "AgentTurn",
    "AppraisalHistoryCoherence",
    "BehavioralInertia",
    "DEFAULT_RULES",
    "DomainTemporalAdapter",
    "EvidenceGroundedIrreversibility",
    "NullTemporalAdapter",
    "TemporalRule",
    "TemporalRuleEvaluator",
    "TrajectoryEvaluation",
    "Violation",
]
