"""
Explainable AI (XAI) components.

- counterfactual.py: CounterfactualEngine (Phase 4A - Claude Code)
- feasibility.py: CategoricalFeasibilityScorer (Phase 4 Enhancement)
"""

from .counterfactual import (
    CounterfactualEngine,
    explain_blocked_action,
)
from .feasibility import (
    CategoricalFeasibilityScorer,
    TransitionInfo,
    create_default_scorer,
    # Domain matrices
    EDUCATION_FEASIBILITY,
    EDUCATION_RATIONALES,
    FINANCE_FEASIBILITY,
    FINANCE_RATIONALES,
    FLOOD_FEASIBILITY,
    FLOOD_RATIONALES,
    HEALTH_FEASIBILITY,
    HEALTH_RATIONALES,
)
from ..types import CounterFactualStrategy

__all__ = [
    # Counterfactual Engine
    "CounterFactualStrategy",
    "CounterfactualEngine",
    "explain_blocked_action",
    # Feasibility Scoring (Phase 4)
    "CategoricalFeasibilityScorer",
    "TransitionInfo",
    "create_default_scorer",
    # Domain matrices
    "EDUCATION_FEASIBILITY",
    "EDUCATION_RATIONALES",
    "FINANCE_FEASIBILITY",
    "FINANCE_RATIONALES",
    "FLOOD_FEASIBILITY",
    "FLOOD_RATIONALES",
    "HEALTH_FEASIBILITY",
    "HEALTH_RATIONALES",
]
